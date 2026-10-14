from pathlib import Path

import pytest

from antenna import fom, tables
from antenna.design import patch_area_mm2
from antenna.results import load


def test_readme_tables_match_source():
    text = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")
    for name in ("results-table", "bandwidth-table"):
        actual = text.split("<!-- BEGIN:%s -->\n" % name)[1].split("\n<!-- END:%s -->" % name)[0]
        assert actual == tables.render_all(load())[name]


def test_reports_distinguish_recorded_and_derived_numbers():
    report = tables.results_table(load())
    assert "1.125" in report and "1.052" in report
    bands = tables.bandwidth_table(load())
    assert "3.12" in bands and "3.06" in bands
    assert "6.56" in bands


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")])
def test_pattern_area_rejects_invalid_area(value):
    with pytest.raises(ValueError):
        fom.gain_per_area(5.54, value)


def test_pattern_area_rejects_unit_conversion_underflow():
    with pytest.raises(ValueError, match="area.*too small"):
        fom.gain_per_area(0, 5e-324)


@pytest.mark.parametrize("function,args", [
    (fom.gain_per_area, (3000, 1e-20)),
    (fom.gain_bandwidth_product, (3000, 1e100)),
])
def test_pattern_proxy_rejects_nonfinite_calculated_results(function, args):
    with pytest.raises(ValueError, match="proxy.*numeric range"):
        function(*args)


def test_pattern_proxy_is_not_labelled_verified_gain():
    report = tables.figure_of_merit_table(load())
    assert "Pattern proxy" in report and "Gain ÷ area" not in report


@pytest.mark.parametrize("quantities", [
    ["unknown"] * 5,
    ["directivity", "directivity", "directivity", "gain", "directivity"],
    ["gain", "gain", "gain", "unknown", "gain"],
])
def test_mixed_or_unknown_pattern_quantities_suppress_both_proxies(quantities):
    ds = load()
    for geometry, quantity in zip(ds.geometries, quantities):
        geometry.simulation.pattern_quantity = quantity
    assert not tables.pattern_proxies_available(ds)
    report = tables.figure_of_merit_table(ds)
    assert "Nominal patch area (mm²)" in report
    assert len(report.splitlines()) == len(ds.geometries) + 2
    for geometry, row in zip(ds.geometries, report.splitlines()[2:]):
        cells = [cell.strip().strip("*") for cell in row.split("|")[1:-1]]
        assert cells[2] == geometry.simulation.pattern_quantity
        assert cells[3] == "%.2f" % geometry.simulation.main_lobe_db
        assert cells[-2:] == ["n/a", "n/a"]
    simulation = tables.simulation_table(ds)
    assert "Pattern quantity" in simulation
    for quantity in set(quantities):
        assert quantity in simulation


@pytest.mark.parametrize("quantity", ["gain", "directivity"])
def test_one_known_pattern_quantity_allows_both_proxies(quantity):
    ds = load()
    for geometry in ds.geometries:
        geometry.simulation.pattern_quantity = quantity
    assert tables.pattern_proxies_available(ds)
    report = tables.figure_of_merit_table(ds)
    for geometry, row in zip(ds.geometries, report.splitlines()[2:]):
        cells = [cell.strip().strip("*") for cell in row.split("|")[1:-1]]
        area = patch_area_mm2(geometry.key, geometry.dimensions_mm)
        assert cells[-2:] == [
            "%.3f" % fom.gain_per_area(geometry.simulation.main_lobe_db, area),
            "%.3f" % fom.gain_bandwidth_product(
                geometry.simulation.main_lobe_db, geometry.simulation.bandwidth_pct),
        ]
