import json
import math
import textwrap
from dataclasses import asdict

import pytest

from antenna import design, metrics
from antenna.check import consistency_issues
from antenna.results import load, validate
from antenna.touchstone import Sweep, band_edges, read_s1p, resonance


@pytest.fixture
def dataset():
    return load()


@pytest.fixture
def raw_dataset(dataset):
    raw = asdict(dataset)
    geometries = raw.pop("geometries")
    return {"meta": raw, "geometries": geometries}


class TestMetrics:
    @pytest.mark.parametrize("vswr", [1.05, 1.3, 2.0, 3.5])
    def test_s11_vswr_roundtrip(self, vswr):
        s11 = metrics.s11_db_from_vswr(vswr)
        assert metrics.vswr_from_s11_db(s11) == pytest.approx(vswr, rel=0, abs=1e-9)

    @pytest.mark.parametrize("s11_db,expected", [(-53.08, 1.004), (-16.38, 1.357), (-14.78, 1.446)])
    def test_known_pairs(self, s11_db, expected):
        assert metrics.vswr_from_s11_db(s11_db) == pytest.approx(expected, rel=0, abs=0.005)

    @pytest.mark.parametrize("reference,expected", [(None, 3.06), (2.45, 3.04)],
                             ids=["midpoint", "design-frequency"])
    def test_bandwidth_from_edges(self, reference, expected):
        assert metrics.fractional_bandwidth_pct(2.399, 2.4735, reference) == pytest.approx(
            expected, rel=0, abs=0.1
        )

    def test_total_reflection_is_infinite(self):
        assert metrics.vswr_from_s11_db(0.0) == float("inf")
        assert metrics.s11_db_from_vswr(1.0) == float("-inf")
        assert metrics.s11_db_from_vswr(float("inf")) == 0.0

    @pytest.mark.parametrize("vswr", [.5, 0, -1, -math.inf, math.nan, True],
                             ids=["below-one", "zero", "negative", "negative-infinity", "nan", "boolean"])
    def test_rejects_invalid_vswr(self, vswr):
        with pytest.raises(ValueError):
            metrics.s11_db_from_vswr(vswr)

    def test_near_unity_vswr_is_finite_and_positive_s11_does_not_overflow(self):
        assert math.isfinite(metrics.s11_db_from_vswr(math.nextafter(1, 2)))
        assert metrics.vswr_from_s11_db(1e300) == math.inf
        assert metrics.vswr_from_s11_db(-math.inf) == 1

    @pytest.mark.parametrize("s11_db", [-1e-12, -1e-15, -1e-17, -1e-20])
    def test_vswr_near_total_reflection_retains_precision(self, s11_db):
        expected = -1 / math.tanh(s11_db * (math.log(10) / 40))
        assert metrics.vswr_from_s11_db(s11_db) == pytest.approx(expected, rel=1e-14)

    @pytest.mark.parametrize("vswr,expected", [(1e10, -1.737177927613007e-9),
                                              (1e17, -1.737177927613007e-16),
                                              (1e20, -1.737177927613007e-19)])
    def test_large_finite_vswr_retains_negative_s11(self, vswr, expected):
        assert metrics.s11_db_from_vswr(vswr) == pytest.approx(expected, rel=1e-14, abs=0)

    def test_unrepresentably_large_vswr_remains_infinite(self):
        assert metrics.vswr_from_s11_db(-math.ulp(0.0)) == math.inf

    @pytest.mark.parametrize("value", [math.nan, math.inf, True, "-20"])
    def test_invalid_s11_is_rejected(self, value):
        for function in (metrics.vswr_from_s11_db, metrics.reflection_coefficient):
            with pytest.raises(ValueError):
                function(value)

    @pytest.mark.parametrize("low,high,reference", [(3, 2, None), (-1, 2, None), (0, 0, None),
                                                  (1, math.inf, None), (1, 2, 0), (1, 2, math.nan)],
                             ids=["reversed", "negative-edge", "dc-only", "infinite-edge",
                                  "zero-reference", "nan-reference"])
    def test_invalid_bandwidth_inputs(self, low, high, reference):
        with pytest.raises(ValueError):
            metrics.fractional_bandwidth_pct(low, high, reference)

    def test_zero_width_band_and_dc_edge(self):
        assert metrics.fractional_bandwidth_pct(2, 2) == 0
        assert metrics.fractional_bandwidth_pct(0, 2) == 200

    @pytest.mark.parametrize("frequency,reference,expected", [
        (0, 2.5, -100), (2.4, 2.5, -4), (2.6, 2.5, 4), (1e308, 1e308, 0),
    ])
    def test_signed_detuning(self, frequency, reference, expected):
        assert metrics.detuning_pct(frequency, reference) == pytest.approx(expected)

    @pytest.mark.parametrize("frequency,reference", [
        (-1, 2.5), (math.nan, 2.5), (2.5, 0), (2.5, True), (2.45, 1e-308),
    ], ids=["negative-frequency", "nan-frequency", "zero-reference", "boolean-reference", "overflow"])
    def test_invalid_or_unrepresentable_detuning_is_rejected(self, frequency, reference):
        with pytest.raises(ValueError):
            metrics.detuning_pct(frequency, reference)


class TestDesign:
    def test_square_resonates_near_target(self):
        f = design.rectangular_resonant_frequency(29.38, 29.38, 4.4, 1.4)
        assert 2.35 < f < 2.5, f

    def test_circular_resonates_near_target(self):
        f = design.circular_resonant_frequency(17.0, 4.4, 1.4)
        assert 2.30 < f < 2.50, f

    @pytest.mark.parametrize("key,dims,expected", [
        pytest.param("square", {"S": 29.38}, 29.38 ** 2, id="square"),
        pytest.param("circular", {"R": 17.0}, math.pi * 17 ** 2, id="circular"),
        pytest.param("triangular", {"Tb": 37.6, "Th": 29.38}, 37.6 * 29.38 / 2, id="triangular"),
        pytest.param("fshaped", {"W": 37.6, "L": 29.38, "Vw": 10, "Bh": 8, "Sh": 3, "Mw": 25},
                     634.6, id="fshaped"),
    ])
    def test_patch_areas(self, key, dims, expected):
        assert design.patch_area_mm2(key, dims) == pytest.approx(expected, rel=0, abs=1e-6)

    def test_hexagon_equivalent_radius_smaller_than_side(self):
        assert design.hexagon_equivalent_radius(17.0) < 17.0

    @pytest.mark.parametrize("key", ["circular", "square", "triangular", "hexagonal", "fshaped"])
    def test_synth_inverts_to_target(self, dataset, key):
        dims = next(geometry.dimensions_mm for geometry in dataset.geometries if geometry.key == key)
        primary = design.PRIMARY_DIMENSION[key]
        dimension = design.synthesize_dimension(key, dims, 4.4, 1.4, 2.45)
        trial = dict(dims, **{primary: dimension})
        assert design.resonant_frequency(key, trial, 4.4, 1.4) == pytest.approx(2.45, rel=0, abs=1e-3)

    def test_synth_rejects_unreachable_target(self):
        with pytest.raises(ValueError):
            design.synthesize_dimension("circular", {"R": 17.0}, 4.4, 1.4, 200.0)
        with pytest.raises(ValueError):
            design.synthesize_dimension("bowtie", {"R": 17.0}, 4.4, 1.4, 2.45)

    @pytest.mark.parametrize("value", [-1, 0, math.nan, math.inf, True])
    def test_physical_dimensions_and_material_are_validated(self, value):
        for function, args in [(design.circular_resonant_frequency, (value, 4.4, 1.4)),
                               (design.rectangular_resonant_frequency, (value, 29, 4.4, 1.4)),
                               (design.triangular_resonant_frequency, (value, 4.4)),
                               (design.hexagon_equivalent_radius, (value,)),
                               (design.effective_permittivity, (4.4, value, 29)),
                               (design.patch_area_mm2, ("square", {"S": value}))]:
            with pytest.raises(ValueError):
                function(*args)

    def test_missing_dimensions_and_invalid_dielectric(self):
        with pytest.raises(ValueError, match="dimension Th"):
            design.patch_area_mm2("triangular", {"Tb": 37.6})
        with pytest.raises(ValueError):
            design.circular_resonant_frequency(17, .5, 1.4)

    @pytest.mark.parametrize("changes", [{"Vw": 40}, {"Mw": 40}, {"L": 18}, {"Sh": -1}],
                             ids=["vertical-width", "middle-width", "short-length", "negative-gap"])
    def test_invalid_f_layout_is_rejected(self, changes):
        dims = dict(W=37.6, L=29.38, Vw=10, Bh=8, Sh=3, Mw=25)
        dims.update(changes)
        for function, args in [(design.patch_area_mm2, ("fshaped", dims)),
                               (design.resonant_frequency, ("fshaped", dims, 4.4, 1.4))]:
            with pytest.raises(ValueError):
                function(*args)

    def test_f_area_and_synthesis_respect_bar_layout(self):
        dims = dict(W=37.6, L=29.38, Vw=10, Bh=8, Sh=3, Mw=25)
        assert design.patch_area_mm2("fshaped", dims) == pytest.approx(634.6)
        length = design.synthesize_dimension("fshaped", dims, 4.4, 1.4, 2.45)
        assert length >= 19
        with pytest.raises(ValueError, match="outside"):
            design.synthesize_dimension("fshaped", dims, 4.4, 1.4, 20)

    @pytest.mark.parametrize("target", [0, -1, math.nan, math.inf])
    def test_invalid_synthesis_target_is_rejected(self, target):
        with pytest.raises(ValueError):
            design.synthesize_dimension("square", {"S": 29.38}, 4.4, 1.4, target)

    @pytest.mark.parametrize("scale", [1e-308, 1, 1e308])
    def test_effective_permittivity_depends_on_dimension_ratio(self, scale):
        expected = 2.7 + 1.7 / math.sqrt(13)
        assert design.effective_permittivity(4.4, scale, scale) == pytest.approx(expected)

    @pytest.mark.parametrize("middle_width,expected", [(4, 72), (10, 80)],
                             ids=["contained-middle-bar", "extended-middle-bar"])
    def test_f_area_counts_each_bar_extension_once(self, middle_width, expected):
        dims = dict(W=12, L=10, Vw=6, Bh=2, Sh=1, Mw=middle_width)
        assert design.patch_area_mm2("fshaped", dims) == expected

    def test_f_area_avoids_overflow_from_counting_overlaps(self):
        dims = dict(W=1e308, L=1, Vw=1e308, Bh=0.5, Sh=0, Mw=1e308)
        assert design.patch_area_mm2("fshaped", dims) == 1e308


class TestDataset:
    @pytest.mark.parametrize("raw", [{}, [], {"meta": {}, "geometries": []}],
                             ids=["missing-fields", "array-root", "empty-metadata"])
    def test_load_rejects_missing_fields_and_bad_structure(self, tmp_path, raw):
        path = tmp_path / "results.json"
        path.write_text(json.dumps(raw))
        with pytest.raises(ValueError):
            load(str(path))

    @pytest.mark.parametrize("text", ['{"meta": {}, "meta": {}}', '{"number": NaN}', '{"number": Infinity}'],
                             ids=["duplicate-key", "nan", "infinity"])
    def test_json_nonfinite_and_duplicate_keys_are_rejected(self, tmp_path, text):
        path = tmp_path / "results.json"
        path.write_text(text)
        with pytest.raises(ValueError):
            load(str(path))

    def test_unrepresentable_json_integer_is_a_validation_error(self, tmp_path, raw_dataset):
        raw_dataset["meta"]["design_frequency_ghz"] = 10 ** 400
        path = tmp_path / "results.json"
        path.write_text(json.dumps(raw_dataset))
        with pytest.raises(ValueError, match="finite number"):
            load(str(path))

    @pytest.mark.parametrize("duplicate", [False, True], ids=["empty", "duplicate"])
    def test_empty_and_duplicate_geometry_lists_are_rejected(self, dataset, duplicate):
        if duplicate:
            dataset.geometries.append(dataset.geometries[0])
        else:
            dataset.geometries.clear()
        with pytest.raises(ValueError, match="duplicate geometry" if duplicate else "nonempty"):
            validate(dataset)
        assert consistency_issues(dataset)[0].level == "error"

    @pytest.mark.parametrize("field,value", [("s11_db", math.nan), ("vswr", math.inf), ("vswr", .5),
                                           ("bandwidth_pct", -1), ("bandwidth_pct", math.nan),
                                           ("band_edges_ghz", [3, 2]), ("band_edges_ghz", [2]),
                                           ("band_edges_ghz", [2, math.nan]), ("bandwidth_pending", "false"),
                                           ("main_lobe_db", math.nan), ("s11_db", 2)],
                             ids=["nan-s11", "infinite-vswr", "vswr-below-one", "negative-bandwidth",
                                  "nan-bandwidth", "reversed-edges", "missing-edge", "nan-edge",
                                  "nonboolean-pending", "nan-pattern", "positive-passive-s11"])
    def test_invalid_simulation_is_an_error_even_when_bandwidth_pending(self, dataset, field, value):
        dataset.geometries[0].simulation.bandwidth_pending = True
        setattr(dataset.geometries[0].simulation, field, value)
        issues = consistency_issues(dataset)
        assert issues and issues[0].level == "error"
        assert issues[0].field == "validation"

    @pytest.mark.parametrize("field,value", [("s11_db", math.nan), ("vswr", -1), ("verified", "false"), ("read_at", "")],
                             ids=["nan-s11", "negative-vswr", "nonboolean-verified", "missing-read-frequency"])
    def test_invalid_unverified_measurement_is_an_error(self, dataset, field, value):
        setattr(dataset.geometries[0].measurement, field, value)
        assert consistency_issues(dataset)[0].level == "error"

    @pytest.mark.parametrize("field,value", [("design_frequency_ghz", math.nan), ("design_frequency_ghz", 0),
                                           ("ground_plane_mm", {"width": 75}), ("feed_mm", {"width": -1, "patch_gap": 1})],
                             ids=["nan-frequency", "zero-frequency", "missing-ground-length", "negative-feed-width"])
    def test_invalid_metadata_is_rejected(self, dataset, field, value):
        setattr(dataset, field, value)
        assert consistency_issues(dataset)[0].level == "error"

    @pytest.mark.parametrize("field,value", [("dimensions_mm", {}), ("highlight", 1)],
                             ids=["missing-dimensions", "nonboolean-highlight"])
    def test_invalid_geometry_fields_are_rejected(self, dataset, field, value):
        setattr(dataset.geometries[0], field, value)
        assert consistency_issues(dataset)[0].level == "error"

    def test_invalid_substrate_is_rejected(self, dataset):
        dataset.substrate.epsilon_r = math.nan
        assert consistency_issues(dataset)[0].level == "error"

    def test_load_retains_historical_values_and_pending_status(self, tmp_path, raw_dataset):
        path = tmp_path / "results.json"
        path.write_text(json.dumps(raw_dataset))
        ds = load(str(path))
        assert ds.geometries[0].simulation.bandwidth_pct == 3.12
        assert ds.geometries[0].measurement.vswr == 1.125
        issues = consistency_issues(ds)
        assert sum(issue.level == "warning" for issue in issues) == 8
        assert not any(issue.level == "error" for issue in issues)

    def test_legacy_results_default_to_unknown_pattern_quantity(self, tmp_path, raw_dataset):
        for geometry in raw_dataset["geometries"]:
            geometry["simulation"].pop("pattern_quantity", None)
        path = tmp_path / "legacy.json"
        path.write_text(json.dumps(raw_dataset))
        ds = load(str(path))
        assert all(g.simulation.pattern_quantity == "unknown" for g in ds.geometries)

    @pytest.mark.parametrize("quantity", [None, "dBi", "radiation", True, []],
                             ids=["null", "unit", "unknown-word", "boolean", "array"])
    def test_invalid_pattern_quantity_is_rejected(self, dataset, quantity):
        dataset.geometries[0].simulation.pattern_quantity = quantity
        with pytest.raises(ValueError, match="pattern quantity"):
            validate(dataset)

    def test_explicit_empty_path_does_not_select_bundled_results(self):
        with pytest.raises(ValueError, match="results path must not be empty"):
            load("")


class TestConsistency:
    def test_simulation_rows_are_self_consistent(self, dataset):
        for g in dataset.geometries:
            implied = metrics.vswr_from_s11_db(g.simulation.s11_db)
            assert implied == pytest.approx(g.simulation.vswr, rel=0, abs=0.01), g.name

    def test_no_hard_errors_in_canonical_data(self, dataset):
        errors = [i for i in consistency_issues(dataset) if i.level == "error"]
        assert errors == [], errors

    def test_checker_flags_measurement_discrepancy(self, dataset):
        warnings = [i for i in consistency_issues(dataset) if i.level == "warning" and i.field == "meas VSWR"]
        assert len(warnings) == 5

    def test_unacknowledged_bandwidth_error_fails_the_build(self, dataset):
        sim = dataset.geometries[0].simulation
        sim.bandwidth_pct = 99.0
        levels = [i.level for i in consistency_issues(dataset) if i.field == "bandwidth" and i.geometry == "Circular"]
        assert levels == ["error"]

    @pytest.mark.parametrize("reference,edges", [
        pytest.param(5e-324, [2.399, 2.4735], id="tiny-reference"),
        pytest.param(2.45, [1e-300, 1e308], id="extreme-edges"),
    ])
    def test_unrepresentable_bandwidth_returns_error_issue(self, dataset, reference, edges):
        dataset.design_frequency_ghz = reference
        dataset.geometries[0].simulation.band_edges_ghz = edges
        issues = consistency_issues(dataset)
        assert any(issue.level == "error" and issue.field == "bandwidth" and issue.geometry == "Circular"
                   for issue in issues)
        if reference == 5e-324:
            assert any(issue.level == "error" and issue.field == "resonance" for issue in issues)
            assert sum(issue.field == "meas VSWR" and issue.level == "warning" for issue in issues) == 5
            assert not any(issue.level == "info" and "inf" in issue.message for issue in issues)

    def test_invalid_resonance_preserves_measurement_checks(self, dataset):
        dataset.geometries[0].dimensions_mm["R"] = 1e-300
        issues = consistency_issues(dataset)
        assert any(issue.level == "error" and issue.field == "resonance" and issue.geometry == "Circular"
                   for issue in issues)
        assert sum(issue.field == "meas VSWR" and issue.level == "warning" for issue in issues) == 5


class TestTouchstone:
    def test_read_s1p_db_format(self, tmp_path):
        path = tmp_path / "sample.s1p"
        path.write_text(textwrap.dedent("""\
            ! circular patch measurement
            # GHz S DB R 50
            2.40 -12.0 -20
            2.45 -28.0 -30
            2.50 -11.0 -25
        """))
        sweep = read_s1p(str(path))
        assert sweep.freqs_ghz == [2.40, 2.45, 2.50]
        assert sweep.s11_db == [-12.0, -28.0, -11.0]

    def test_resonance_and_band_edges(self, tmp_path):
        path = tmp_path / "sweep.s1p"
        path.write_text(textwrap.dedent("""\
            # GHz S DB R 50
            2.30 -6.0 0
            2.40 -14.0 0
            2.45 -32.0 0
            2.50 -13.0 0
            2.60 -5.0 0
        """))
        sweep = read_s1p(str(path))
        f_res, depth = resonance(sweep)
        assert f_res == 2.45 and depth == -32.0
        lo, hi = band_edges(sweep)
        assert lo == pytest.approx(2.35)
        assert hi == pytest.approx(2.5375)

    def test_ma_format_and_hz_scaling(self, tmp_path):
        path = tmp_path / "ma.s1p"
        path.write_text("# HZ S MA R 50\n2450000000 0.1 -20\n")
        sweep = read_s1p(str(path))
        assert sweep.freqs_ghz == [2.45]
        assert sweep.s11_db == pytest.approx([-20], rel=0, abs=1e-9)

    @pytest.mark.parametrize("components", ["0 .1", "-.06 .08"], ids=["imaginary", "real-and-imaginary"])
    def test_ri_complex_magnitudes_and_khz_scaling(self, tmp_path, components):
        path = tmp_path / "complex.s1p"
        path.write_text("# kHz S RI R 75\n2450000 " + components + "\n")
        sweep = read_s1p(str(path))
        assert sweep.freqs_ghz == pytest.approx([2.45])
        assert sweep.s11_db == pytest.approx([-20])
        assert sweep.reference_ohms == 75

    def test_rejects_empty_and_malformed(self, tmp_path):
        empty = tmp_path / "empty.s1p"
        empty.write_text("! comments only\n# GHz S DB R 50\n")
        with pytest.raises(ValueError):
            read_s1p(str(empty))
        bad = tmp_path / "bad.s1p"
        bad.write_text("# GHz S DB R 50\n2.45 -20\n")
        with pytest.raises(ValueError):
            read_s1p(str(bad))

    @pytest.mark.parametrize("header", ["# MHz S DB R 50", "# R 50 DB S MHz", "# MHz DB", "# DB MHz R 75"])
    def test_reordered_and_partial_options(self, tmp_path, header):
        path = tmp_path / "options.s1p"
        path.write_text(header + "\n2450 -20 0\n")
        sweep = read_s1p(str(path))
        assert sweep.freqs_ghz == [2.45]
        assert sweep.s11_db == [-20]
        assert sweep.reference_ohms == (75 if "75" in header else 50)

    def test_empty_option_line_uses_defaults(self, tmp_path):
        path = tmp_path / "defaults.s1p"
        path.write_text("#\n2.4 0.1 0\n2.5 0.2 0\n")
        sweep = read_s1p(str(path))
        assert sweep.freqs_ghz == [2.4, 2.5]
        assert sweep.s11_db == pytest.approx([-20, 20 * math.log10(.2)])
        assert sweep.reference_ohms == 50

    @pytest.mark.parametrize("later_header", ["# MHz S MA R 75", "# GHz S DB R 50", "# MHz Z DB R -50", "#"],
                             ids=["changed", "identical", "malformed", "empty"])
    @pytest.mark.parametrize("preceding_data", ["", "2.4 -20 0\n"], ids=["before-data", "after-data"])
    def test_rejects_later_option_lines(self, tmp_path, later_header, preceding_data):
        path = tmp_path / "multiple-options.s1p"
        prefix = "# GHz S DB R 50\n" + preceding_data + "\n! second block\n"
        path.write_text(prefix + "  " + later_header + " ! later options\n2450 .1 0\n")
        with pytest.raises(ValueError, match="multiple Touchstone option lines are unsupported") as error:
            read_s1p(str(path))
        assert "%s:%d" % (path, len(prefix.splitlines()) + 1) in str(error.value)

    @pytest.mark.parametrize("header", ["# GHz Z RI R 50", "# GHz Y DB", "# THz S DB", "# GHz S DB R -50",
                                       "# GHz S DB R 0", "# GHz S DB R nan", "# R inf", "# R", "# R wrong",
                                       "# GHz MHz S DB", "# DB MA", "# S S", "# R 50 R 75"])
    def test_rejects_unsupported_or_invalid_options(self, tmp_path, header):
        path = tmp_path / "bad-options.s1p"
        path.write_text(header + "\n2.45 0.1 0\n")
        with pytest.raises(ValueError):
            read_s1p(str(path))

    @pytest.mark.parametrize("text", ["2.45 -20 0\n", "[Version] 2.0\n# GHz S DB\n2.45 -20 0\n",
                                      "# GHz S DB\n2.45 -20 0 1 0\n"])
    def test_requires_v1_option_line_and_one_port_data(self, tmp_path, text):
        path = tmp_path / "unsupported.s1p"
        path.write_text(text)
        with pytest.raises(ValueError):
            read_s1p(str(path))

    @pytest.mark.parametrize("row", ["nan -20 0", "inf -20 0", "2.45 nan 0", "2.45 -20 inf", "-2.45 -20 0"])
    def test_rejects_invalid_data_values(self, tmp_path, row):
        path = tmp_path / "bad-data.s1p"
        path.write_text("# GHz S DB\n" + row + "\n")
        with pytest.raises(ValueError):
            read_s1p(str(path))

    def test_ma_rejects_negative_magnitude_and_zero_reflection_is_valid(self, tmp_path):
        path = tmp_path / "magnitude.s1p"
        path.write_text("# GHz S MA\n2.45 -0.1 0\n")
        with pytest.raises(ValueError, match="nonnegative"):
            read_s1p(str(path))
        for fmt in ("MA", "RI"):
            path.write_text("# GHz S %s\n0 0 0\n2.45 .1 0\n" % fmt)
            sweep = read_s1p(str(path))
            assert sweep.s11_db == [-math.inf, -20]

    @pytest.mark.parametrize("frequencies", [[2.45, 2.45], [2.5, 2.4]], ids=["duplicate", "descending"])
    def test_requires_strictly_ascending_frequencies(self, tmp_path, frequencies):
        path = tmp_path / "order.s1p"
        path.write_text("# GHz S DB\n" + "".join("%s -20 0\n" % f for f in frequencies))
        with pytest.raises(ValueError, match="strictly increasing"):
            read_s1p(str(path))

    @pytest.mark.parametrize("frequencies,values", [
        pytest.param([], [], id="empty"),
        pytest.param([1, 2], [-20], id="length-mismatch"),
        pytest.param([1], [math.nan], id="nan-s11"),
        pytest.param([1], [math.inf], id="infinite-s11"),
        pytest.param(None, [-20], id="nonsequence-frequencies"),
        pytest.param([1], None, id="nonsequence-s11"),
        pytest.param([-1], [-20], id="negative-frequency"),
        pytest.param([1], ["-20"], id="nonnumeric-s11"),
    ])
    def test_sweep_validates_direct_input(self, frequencies, values):
        with pytest.raises(ValueError):
            Sweep(frequencies, values)

    @pytest.mark.parametrize("reference", [0, -50, math.nan, math.inf, True, "50"],
                             ids=["zero", "negative", "nan", "infinite", "boolean", "text"])
    def test_sweep_rejects_invalid_reference(self, reference):
        with pytest.raises(ValueError, match="reference impedance"):
            Sweep([2.45], [-20], reference)

    def test_sweep_mutation_is_revalidated(self):
        sweep = Sweep([1, 2], [-5, -20])
        sweep.freqs_ghz.clear()
        for function in (resonance, band_edges):
            with pytest.raises(ValueError):
                function(sweep)

    def test_disjoint_bands_are_not_merged(self):
        sweep = Sweep([1, 2, 3, 4, 5, 6, 7], [-5, -15, -5, -5, -20, -20, -5])
        assert band_edges(sweep) == pytest.approx((4 + 1 / 3, 6 + 2 / 3))

    def test_exact_threshold_crossings_and_single_threshold_point(self):
        assert band_edges(Sweep([1, 2, 3, 4, 5], [-5, -10, -20, -10, -5])) == (2, 4)
        assert band_edges(Sweep([1, 2, 3], [-5, -10, -5])) == (2, 2)

    @pytest.mark.parametrize("values,expected", [
        ([-10, -20, -5], (1, 2 + 2 / 3)),
        ([-5, -20, -10], (1 + 1 / 3, 3)),
        ([-10, -20, -10], (1, 3)),
        ([-10, -10, -20, -10, -10], (1, 5)),
        ([-10, -math.inf, -10], (1, 3)),
        ([-10], (1, 1)),
        ([-10, -10], (1, 2)),
        ([-10, -15, -5, -20, -10], (3 + 1 / 3, 5)),
    ], ids=["left", "right", "both", "plateaus", "zero-reflection", "single-point", "flat-band", "deepest-band"])
    def test_exact_threshold_samples_define_endpoint_boundaries(self, values, expected):
        sweep = Sweep(list(range(1, len(values) + 1)), values)
        assert band_edges(sweep) == pytest.approx(expected)

    def test_exact_endpoint_crossings_use_supplied_threshold(self):
        sweep = Sweep([1, 2, 3], [-6, -12, -6])
        assert band_edges(sweep, threshold_db=-6) == (1, 3)

    @pytest.mark.parametrize("values", [[-20, -5, -5], [-5, -5, -20], [-20, -20, -20],
                                       [-10, -20, -20], [-20, -20, -10],
                                       [-10.0001, -20, -5], [-5, -20, -10.0001],
                                       [-5, -5, -5], [-5, -math.inf, -5]],
                             ids=["left-incomplete", "right-incomplete", "both-incomplete",
                                  "exact-left-open-right", "open-left-exact-right", "below-left",
                                  "below-right", "no-band", "uninterpolatable-minimum"])
    def test_missing_or_uninterpolatable_crossings_are_unavailable(self, values):
        assert band_edges(Sweep([1, 2, 3], values)) is None

    def test_threshold_must_be_finite(self):
        with pytest.raises(ValueError):
            band_edges(Sweep([1, 2, 3], [-5, -20, -5]), math.nan)

    @pytest.mark.parametrize("threshold,expected", [(-10, (1.5, 2.5)),
                                                    (-5e307, (1.75, 2.25)),
                                                    (5e307, (1.25, 2.75))])
    def test_finite_extreme_db_values_do_not_overflow_interpolation(self, threshold, expected):
        sweep = Sweep([1, 2, 3], [1e308, -1e308, 1e308])
        assert band_edges(sweep, threshold) == pytest.approx(expected)

    def test_ri_overflow_reports_a_short_line_numbered_error(self, tmp_path, capsys):
        from antenna.__main__ import main

        path = tmp_path / "oversized.s1p"
        path.write_text("# GHz S RI R 50\n2.45 1.7e308 1.7e308\n")
        with pytest.raises(ValueError, match=r"oversized\.s1p:2:"):
            read_s1p(str(path))
        assert main(["ingest", str(path)]) == 2
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "oversized.s1p:2:" in captured.err
        assert "Traceback" not in captured.err
