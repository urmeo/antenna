import json
import os
import stat
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import textwrap

import pytest

from antenna import fom, plots, tables
from antenna.__main__ import main
from antenna.design import patch_area_mm2
from antenna.results import load, validate
from antenna.tables import render_all


@pytest.fixture
def dataset():
    return load()


@pytest.fixture
def readme(tmp_path):
    return tmp_path / "README.md"


@pytest.fixture
def sweep_file(tmp_path):
    path = tmp_path / "valid.s1p"
    path.write_text("# GHz S DB\n2.4 -5 0\n2.45 -20 0\n2.5 -5 0\n")
    return path


class TestCli:
    def test_invalid_data_reports_a_short_error(self, tmp_path, capsys):
        data = tmp_path / "results.json"
        data.write_text(json.dumps({}))
        assert main(["check", "--data", str(data)]) == 2
        captured = capsys.readouterr()
        assert "invalid results structure" in captured.err
        assert "Traceback" not in captured.err

    @pytest.mark.parametrize("command", ["check", "tables", "design", "synth", "plot"])
    def test_missing_dataset_returns_a_short_error(self, command, tmp_path, capsys):
        missing = tmp_path / "missing.json"
        assert main([command, "--data", str(missing)]) == 2
        captured = capsys.readouterr()
        assert captured.out == ""
        assert str(missing) in captured.err
        assert "Traceback" not in captured.err

    @pytest.mark.parametrize("action", ["--write", "--check"], ids=["write", "check"])
    def test_missing_readme_reports_a_short_error(self, action, readme, capsys):
        assert main(["tables", action, "--readme", str(readme)]) == 2
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "README not found" in captured.err
        assert not readme.exists()

    def test_table_actions_are_mutually_exclusive(self, capsys):
        with pytest.raises(SystemExit) as error:
            main(["tables", "--write", "--check"])
        assert error.value.code == 2
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "not allowed with argument" in captured.err

    def test_ingest_validates_every_input_before_printing(self, tmp_path, capsys, sweep_file):
        assert main(["ingest", str(sweep_file), str(tmp_path / "missing.s1p")]) == 2
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "missing.s1p" in captured.err

    def test_ingest_exposes_reference_and_unavailable_bandwidth(self, tmp_path, capsys):
        path = tmp_path / "censored.s1p"
        path.write_text("# R 75 DB GHz\n2.4 -20 0\n2.45 -30 0\n")
        assert main(["ingest", str(path)]) == 0
        output = capsys.readouterr().out
        assert "75.00" in output and "n/a" in output
        assert "no complete band" in output

    def test_ingest_dc_threshold_band_has_unavailable_bandwidth(self, tmp_path, capsys):
        path = tmp_path / "dc.s1p"
        path.write_text("# GHz S DB R 50\n0 -10 0\n")
        assert main(["ingest", str(path)]) == 0
        captured = capsys.readouterr()
        assert captured.err == ""
        row = captured.out.splitlines()[1].split()
        assert row[1] == "0.0000"
        assert row[4] == "n/a"

    def test_ingest_derives_every_row_before_printing(self, tmp_path, capsys, monkeypatch, sweep_file):
        unavailable = tmp_path / "unavailable.s1p"
        unavailable.write_text(sweep_file.read_text())
        from antenna.touchstone import resonance

        calls = 0

        def fail_on_second_sweep(sweep):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ValueError("derived reading is unavailable")
            return resonance(sweep)

        monkeypatch.setattr("antenna.touchstone.resonance", fail_on_second_sweep)
        assert main(["ingest", str(sweep_file), str(unavailable)]) == 2
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "derived reading is unavailable" in captured.err

    def test_ingest_rejects_concatenated_options_without_output(self, tmp_path, capsys):
        path = tmp_path / "concatenated.s1p"
        path.write_text("# GHz S DB R 50\n2.4 -20 0\n# MHz S MA R 75\n2450 .1 0\n")
        assert main(["ingest", str(path)]) == 2
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "multiple Touchstone option lines are unsupported" in captured.err
        assert "%s:3" % path in captured.err
        assert "Traceback" not in captured.err

    def test_default_readme_is_in_current_directory(self, tmp_path, monkeypatch, capsys, readme):
        monkeypatch.chdir(tmp_path)
        readme.write_text("<!-- BEGIN:results-table -->\nstale\n<!-- END:results-table -->\n")
        assert main(["tables", "--write"]) == 0
        assert "stale" not in readme.read_text()
        assert main(["tables", "--check"]) == 0
        capsys.readouterr()
        readme.write_text(readme.read_text().replace("-53.08", "-50.00").replace("−53.08", "−50.00"))
        assert main(["tables", "--check"]) == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "results-table: table differs from source" in captured.err

    def test_tables_without_markers_fail(self, capsys, readme):
        readme.write_text("# No markers\n")
        assert main(["tables", "--write", "--readme", str(readme)]) == 2
        assert "no recognized table markers" in capsys.readouterr().err

    @pytest.mark.parametrize("arguments", [["--s1p"], ["--s1p", "missing.s1p"]],
                             ids=["empty-sweep-list", "missing-sweep"])
    def test_plot_rejects_bad_inputs_before_creating_outputs(self, tmp_path, capsys, arguments):
        output = tmp_path / "output"
        assert main(["plot", "--out", str(output)] + arguments) == 2
        assert not output.exists()
        assert "Traceback" not in capsys.readouterr().err

    def test_plot_checks_results_before_writing_overlay(self, tmp_path, capsys, sweep_file):
        data = tmp_path / "bad.json"
        data.write_text("{}")
        output = tmp_path / "output"
        assert main(["plot", "--data", str(data), "--out", str(output), "--s1p", str(sweep_file)]) == 2
        assert not output.exists()
        capsys.readouterr()

    def test_plot_validates_derived_values_before_writing_any_output(self, tmp_path, capsys,
                                                                  monkeypatch, dataset, sweep_file):
        dataset.geometries[0].dimensions_mm["R"] = 1e-300
        raw = asdict(dataset)
        geometries = raw.pop("geometries")
        data = tmp_path / "results.json"
        data.write_text(json.dumps({"meta": raw, "geometries": geometries}))
        output = tmp_path / "output"
        overlay_calls = []

        def write_overlay(paths, destination):
            overlay_calls.append(paths)
            Path(destination).write_bytes(b"overlay")
            return destination

        monkeypatch.setattr(plots, "_pyplot", lambda: None)
        monkeypatch.setattr(plots, "s11_overlay", write_overlay)
        assert main(["plot", "--data", str(data), "--out", str(output),
                     "--s1p", str(sweep_file)]) == 2
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "circular effective-radius correction" in captured.err
        assert overlay_calls == []
        assert not output.exists()

    @pytest.mark.parametrize("labels", [[], ["one", "extra"]], ids=["empty", "too-many"])
    def test_overlay_rejects_label_count_before_loading_matplotlib(self, labels, tmp_path,
                                                                 monkeypatch, sweep_file):
        def unexpected_pyplot():
            pytest.fail("invalid labels must be rejected before loading Matplotlib")

        monkeypatch.setattr(plots, "_pyplot", unexpected_pyplot)
        output = tmp_path / "output" / "overlay.png"
        with pytest.raises(ValueError, match="labels.*sweeps"):
            plots.s11_overlay([str(sweep_file)], str(output), labels=labels)
        assert not output.parent.exists()

    def test_plot_missing_matplotlib_has_install_message(self, tmp_path, monkeypatch, capsys):
        def missing():
            raise ModuleNotFoundError("No module named matplotlib", name="matplotlib")

        monkeypatch.setattr(plots, "_pyplot", missing)
        output = tmp_path / "output"
        assert main(["plot", "--out", str(output)]) == 2
        assert "python -m pip install matplotlib" in capsys.readouterr().err
        assert not output.exists()

    @pytest.mark.parametrize("quantity,explain", [("unknown", True), ("mixed", True),
                                               ("gain", False), ("directivity", False)],
                             ids=["unknown", "mixed", "gain", "directivity"])
    def test_tables_explain_when_pattern_proxies_are_unavailable(self, monkeypatch, capsys, quantity, explain, dataset):
        for geometry in dataset.geometries:
            geometry.simulation.pattern_quantity = "directivity" if quantity == "mixed" else quantity
        if quantity == "mixed":
            dataset.geometries[3].simulation.pattern_quantity = "gain"
        monkeypatch.setattr("antenna.__main__.load", lambda path: dataset)
        assert main(["tables"]) == 0
        output = capsys.readouterr().out
        assert ("Pattern proxy columns are n/a:" in output) is explain

    @pytest.mark.parametrize("command", ["check", "tables", "design", "synth", "plot"])
    def test_empty_dataset_path_returns_a_short_error(self, command, capsys):
        assert main([command, "--data", ""]) == 2
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "results path must not be empty" in captured.err
        assert "Traceback" not in captured.err

    def test_design_rejects_detuning_overflow_before_printing(self, tmp_path, capsys, dataset):
        raw = asdict(dataset)
        geometries = raw.pop("geometries")
        raw["design_frequency_ghz"] = 1e-308
        data = tmp_path / "results.json"
        data.write_text(json.dumps({"meta": raw, "geometries": geometries}))
        assert main(["design", "--data", str(data)]) == 2
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "detuning exceeds numeric range" in captured.err
        assert "Traceback" not in captured.err

    def test_ingest_rejects_unused_dataset_option(self, capsys, sweep_file):
        with pytest.raises(SystemExit) as error:
            main(["ingest", "--data", "results.json", str(sweep_file)])
        assert error.value.code == 2
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "unrecognized arguments" in captured.err


class TestTables:
    def test_num_uses_unicode_minus(self):
        assert tables._num(-53.08, 2) == "−53.08"
        assert tables._num(3.12, 2) == "3.12"
        assert tables._signed(0.85, 2) == "+0.85"

    def test_inject_is_idempotent(self, dataset, readme):
        readme.write_text(textwrap.dedent("""\
            # Title
            <!-- BEGIN:sim-table -->
            stale
            <!-- END:sim-table -->
            tail
        """))
        assert tables.inject(str(readme), dataset) == ["sim-table"]
        once = readme.read_text()
        tables.inject(str(readme), dataset)
        assert readme.read_text() == once
        assert "stale" not in once and "tail" in once

    def test_inject_without_markers_changes_nothing(self, dataset, readme):
        readme.write_text("# No markers here\n")
        assert tables.inject(str(readme), dataset) == []
        assert readme.read_text() == "# No markers here\n"

    def test_check_reports_missing_markers_and_stale_values(self, readme):
        readme.write_text("# No tables\n")
        assert tables.check(str(readme)) == ["no result table markers found"]
        readme.write_text("<!-- BEGIN:results-table -->\nstale\n<!-- END:results-table -->\n")
        assert tables.check(str(readme)) == ["results-table: table differs from source"]
        tables.inject(str(readme))
        assert tables.check(str(readme)) == []
        readme.write_text(readme.read_text() + "<!-- BEGIN:results-table -->")
        assert tables.check(str(readme)) == ["results-table: missing or duplicate marker"]

    @pytest.mark.parametrize("malformed", [
        "<!-- BEGIN:bandwidth-table -->\nstale\n",
        "<!-- END:bandwidth-table -->\n",
        "<!-- END:bandwidth-table -->\nstale\n<!-- BEGIN:bandwidth-table -->\n",
        "<!-- BEGIN:results-table -->\nduplicate\n<!-- END:results-table -->\n",
    ], ids=["missing-end", "missing-begin", "reversed", "duplicate"])
    def test_write_rejects_malformed_markers_before_changing_any_table(self, capsys, malformed, readme):
        original = "<!-- BEGIN:results-table -->\nstale\n<!-- END:results-table -->\n" + malformed
        readme.write_text(original)
        assert main(["tables", "--write", "--readme", str(readme)]) == 2
        assert readme.read_text() == original
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "marker" in captured.err
        assert "Traceback" not in captured.err

    def test_write_rejects_overlapping_blocks_without_changing_readme(self, capsys, readme):
        original = ("<!-- BEGIN:results-table -->\n<!-- BEGIN:bandwidth-table -->\n"
                    "stale\n<!-- END:results-table -->\n<!-- END:bandwidth-table -->\n")
        readme.write_text(original)
        assert main(["tables", "--write", "--readme", str(readme)]) == 2
        assert readme.read_text() == original
        assert "overlap" in capsys.readouterr().err

    @pytest.mark.parametrize("name,expected", [
        pytest.param(
            "Circular | alternate feed\nsecond line",
            "Circular \\| alternate feed<br>second line",
            id="pipe-and-newline",
        ),
        pytest.param(
            "Circular <inset> & gap <!-- BEGIN:results-table --> <!-- END:results-table -->",
            "Circular &lt;inset&gt; &amp; gap &lt;!-- BEGIN:results-table --&gt; "
            "&lt;!-- END:results-table --&gt;",
            id="html-and-marker-text",
        ),
    ])
    def test_custom_json_names_roundtrip_through_write_and_check(self, name, expected, tmp_path,
                                                               capsys, dataset, readme):
        dataset.geometries[0].name = name
        raw = asdict(dataset)
        geometries = raw.pop("geometries")
        data = tmp_path / "results.json"
        data.write_text(json.dumps({"meta": raw, "geometries": geometries}))
        readme.write_text("<!-- BEGIN:results-table -->\nstale\n<!-- END:results-table -->\n")
        args = ["tables", "--data", str(data), "--readme", str(readme)]

        assert main(args + ["--write"]) == 0
        once = readme.read_text()
        assert expected in once
        assert once.count("<!-- BEGIN:results-table -->") == 1
        assert once.count("<!-- END:results-table -->") == 1
        assert main(args + ["--check"]) == 0
        assert main(args + ["--write"]) == 0
        assert readme.read_text() == once
        capsys.readouterr()

    @pytest.mark.parametrize("body", ["stale", "  \nstale\n  ", "\n"],
                             ids=["compact", "padded", "empty"])
    def test_write_normalizes_compact_marked_blocks_and_is_idempotent(self, capsys, body, dataset, readme):
        readme.write_text("# Title\n<!-- BEGIN:results-table -->" + body + "<!-- END:results-table -->\ntail\n")
        args = ["tables", "--readme", str(readme)]
        assert main(args + ["--write"]) == 0
        assert main(args + ["--check"]) == 0
        expected = ("# Title\n<!-- BEGIN:results-table -->\n" + render_all(dataset)["results-table"] +
                    "\n<!-- END:results-table -->\ntail\n")
        assert readme.read_text() == expected
        assert main(args + ["--write"]) == 0
        assert readme.read_text() == expected
        capsys.readouterr()

    @pytest.mark.parametrize("failure", ["write", "replace"])
    def test_failed_table_update_preserves_original_bytes_and_mode(self, tmp_path, monkeypatch, failure):
        readme = tmp_path / "README.md"
        original = b"before\r\n<!-- BEGIN:results-table -->\r\nstale\r\n<!-- END:results-table -->\r\nafter\r\n"
        readme.write_bytes(original)
        readme.chmod(0o640)
        mode = stat.S_IMODE(readme.stat().st_mode)
        create_temporary = tables.tempfile.NamedTemporaryFile

        if failure == "write":
            def broken_temporary(*args, **kwargs):
                output = create_temporary(*args, **kwargs)
                write = output.write

                def interrupted_write(text):
                    write(text[:12])
                    output.flush()
                    raise OSError("disk full")

                output.write = interrupted_write
                return output

            monkeypatch.setattr(tables.tempfile, "NamedTemporaryFile", broken_temporary)
        else:
            def interrupted_replace(source, target):
                raise OSError("replacement denied")

            monkeypatch.setattr(tables.os, "replace", interrupted_replace)

        with pytest.raises(OSError, match="disk full|replacement denied"):
            tables.inject(str(readme))
        assert readme.read_bytes() == original
        assert stat.S_IMODE(readme.stat().st_mode) == mode
        assert list(tmp_path.iterdir()) == [readme]


    @pytest.mark.parametrize("symlink", [False, True], ids=["regular-file", "symlink"])
    def test_table_update_preserves_mode_and_follows_symlinks(self, tmp_path, symlink):
        target = tmp_path / "source.md"
        target.write_text("before\n<!-- BEGIN:results-table -->\nstale\n<!-- END:results-table -->\nafter\n")
        target.chmod(0o640)
        readme = tmp_path / "README.md" if symlink else target
        if symlink:
            readme.symlink_to(target.name)
        assert tables.inject(str(readme)) == ["results-table"]
        assert tables.check(str(readme)) == []
        assert target.read_text() == readme.read_text()
        assert stat.S_IMODE(target.stat().st_mode) == 0o640
        if symlink:
            assert readme.is_symlink()
        assert {path.name for path in tmp_path.iterdir()} == ({"README.md", "source.md"} if symlink else {"source.md"})


    def test_table_update_respects_read_only_target(self, tmp_path):
        readme = tmp_path / "README.md"
        original = b"<!-- BEGIN:results-table -->\nstale\n<!-- END:results-table -->\n"
        readme.write_bytes(original)
        readme.chmod(0o444)
        if os.access(readme, os.W_OK):
            pytest.skip("the current user can write read-only files")
        with pytest.raises(PermissionError):
            tables.inject(str(readme))
        assert readme.read_bytes() == original
        assert stat.S_IMODE(readme.stat().st_mode) == 0o444
        assert list(tmp_path.iterdir()) == [readme]


class TestReports:
    def test_readme_tables_match_source(self, dataset):
        text = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")
        for name in ("results-table", "bandwidth-table"):
            actual = text.split("<!-- BEGIN:%s -->\n" % name)[1].split("\n<!-- END:%s -->" % name)[0]
            assert actual == tables.render_all(dataset)[name]

    def test_reports_distinguish_recorded_and_derived_numbers(self, dataset):
        report = tables.results_table(dataset)
        assert "1.125" in report and "1.052" in report
        bands = tables.bandwidth_table(dataset)
        assert "3.12" in bands and "3.06" in bands
        assert "6.56" in bands

    @pytest.mark.parametrize("missing_count", [1, 5], ids=["one-missing", "all-missing"])
    def test_missing_measurements_are_unavailable_and_excluded_from_deltas(self, missing_count, dataset):
        for geometry in dataset.geometries[:missing_count]:
            geometry.measurement = None
        validate(dataset)
        results = tables.results_table(dataset).splitlines()[2:]
        for row in results[:missing_count]:
            cells = [cell.strip().strip("*") for cell in row.split("|")[1:-1]]
            assert cells[-3:] == ["n/a", "n/a", "n/a"]
        for render in (tables.measurement_table, tables.delta_table):
            report = render(dataset)
            assert len(report.splitlines()) == len(dataset.geometries) - missing_count + 2
            for geometry in dataset.geometries[:missing_count]:
                assert geometry.name not in report

    @pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")],
                             ids=["zero", "negative", "nan", "infinity"])
    def test_pattern_area_rejects_invalid_area(self, value):
        with pytest.raises(ValueError):
            fom.gain_per_area(5.54, value)

    def test_pattern_area_rejects_unit_conversion_underflow(self):
        with pytest.raises(ValueError, match="area.*too small"):
            fom.gain_per_area(0, 5e-324)

    @pytest.mark.parametrize("function,args", [
        (fom.gain_per_area, (3000, 1e-20)),
        (fom.gain_bandwidth_product, (3000, 1e100)),
    ], ids=["area-division-overflow", "bandwidth-product-overflow"])
    def test_pattern_proxy_rejects_nonfinite_calculated_results(self, function, args):
        with pytest.raises(ValueError, match="proxy.*numeric range"):
            function(*args)

    def test_pattern_proxy_is_not_labelled_verified_gain(self, dataset):
        report = tables.figure_of_merit_table(dataset)
        assert "Pattern proxy" in report and "Gain ÷ area" not in report

    @pytest.mark.parametrize("quantities", [
        ["unknown"] * 5,
        ["directivity", "directivity", "directivity", "gain", "directivity"],
        ["gain", "gain", "gain", "unknown", "gain"],
    ], ids=["all-unknown", "mixed-known-quantities", "partly-unknown"])
    def test_mixed_or_unknown_pattern_quantities_suppress_both_proxies(self, quantities, dataset):
        for geometry, quantity in zip(dataset.geometries, quantities):
            geometry.simulation.pattern_quantity = quantity
        assert not tables.pattern_proxies_available(dataset)
        report = tables.figure_of_merit_table(dataset)
        assert "Nominal patch area (mm²)" in report
        assert len(report.splitlines()) == len(dataset.geometries) + 2
        for geometry, row in zip(dataset.geometries, report.splitlines()[2:]):
            cells = [cell.strip().strip("*") for cell in row.split("|")[1:-1]]
            assert cells[2] == geometry.simulation.pattern_quantity
            assert cells[3] == "%.2f" % geometry.simulation.main_lobe_db
            assert cells[-2:] == ["n/a", "n/a"]
        simulation = tables.simulation_table(dataset)
        assert "Pattern quantity" in simulation
        for quantity in set(quantities):
            assert quantity in simulation

    @pytest.mark.parametrize("quantity", ["gain", "directivity"])
    def test_one_known_pattern_quantity_allows_both_proxies(self, quantity, dataset):
        for geometry in dataset.geometries:
            geometry.simulation.pattern_quantity = quantity
            geometry.simulation.bandwidth_pending = False
        assert tables.pattern_proxies_available(dataset)
        report = tables.figure_of_merit_table(dataset)
        for geometry, row in zip(dataset.geometries, report.splitlines()[2:]):
            cells = [cell.strip().strip("*") for cell in row.split("|")[1:-1]]
            area = patch_area_mm2(geometry.key, geometry.dimensions_mm)
            assert cells[-2:] == [
                "%.3f" % fom.gain_per_area(geometry.simulation.main_lobe_db, area),
                "%.3f" % fom.gain_bandwidth_product(
                    geometry.simulation.main_lobe_db, geometry.simulation.bandwidth_pct),
            ]

    @pytest.mark.parametrize("quantity", ["gain", "directivity"])
    def test_pending_bandwidth_suppresses_only_bandwidth_proxy(self, quantity, dataset):
        for geometry in dataset.geometries:
            geometry.simulation.pattern_quantity = quantity
        report = tables.figure_of_merit_table(dataset)
        for geometry, row in zip(dataset.geometries, report.splitlines()[2:]):
            cells = [cell.strip().strip("*") for cell in row.split("|")[1:-1]]
            s = geometry.simulation
            area = patch_area_mm2(geometry.key, geometry.dimensions_mm)
            assert cells[-2] == "%.3f" % fom.gain_per_area(s.main_lobe_db, area)
            if s.bandwidth_pending:
                assert cells[-1] == "n/a"
            else:
                assert cells[-1] == "%.3f" % fom.gain_bandwidth_product(
                    s.main_lobe_db, s.bandwidth_pct)

    def test_custom_geometry_labels_remain_in_one_markdown_cell(self, dataset):
        dataset.geometries[0].name = "Circular | alternate feed\r\nsecond line"
        validate(dataset)
        for report in render_all(dataset).values():
            assert len(report.splitlines()) == len(dataset.geometries) + 2
            assert "Circular \\| alternate feed<br>second line" in report.splitlines()[2]

    def test_backslash_before_pipe_preserves_a_literal_name(self, dataset):
        dataset.geometries[0].name = "Circular \\| feed"
        row = render_all(dataset)["results-table"].splitlines()[2]
        assert "Circular " + "\\" * 3 + "| feed" in row


class TestPlots:
    @pytest.mark.parametrize("renderer,failure", [
        pytest.param("s11-comparison", None, id="overview-success"),
        pytest.param("overlay", None, id="overlay-success"),
    ] + [pytest.param(renderer, failure, id=renderer + "-" + failure)
         for renderer in ("s11-comparison", "reported-bands", "resonance", "overlay")
         for failure in ("setup", "layout", "save")])
    def test_renderers_close_every_created_figure(self, tmp_path, monkeypatch, sweep_file,
                                                 renderer, failure):
        figures, closed = [], []
        target = {"s11-comparison": 0, "reported-bands": 1, "resonance": 2, "overlay": 0}[renderer]

        def subplots(**kwargs):
            assert kwargs == {"figsize": plots.FIGSIZE}
            figure, axes = Mock(), Mock()
            axes.bar.return_value = []
            if len(figures) == target:
                if failure == "setup":
                    axes.bar.side_effect = ValueError("render failed")
                    axes.plot.side_effect = ValueError("render failed")
                elif failure == "layout":
                    figure.tight_layout.side_effect = ValueError("render failed")
                elif failure == "save":
                    figure.savefig.side_effect = OSError("render failed")
            figures.append(figure)
            return figure, axes

        pyplot = SimpleNamespace(subplots=subplots, close=closed.append)
        monkeypatch.setattr(plots, "_pyplot", lambda: pyplot)
        destination = tmp_path / "plots"

        def render():
            if renderer == "overlay":
                return plots.s11_overlay([str(sweep_file)], str(destination / "s11_overlay.png"))
            return plots.overview(str(destination))

        if failure:
            with pytest.raises(OSError if failure == "save" else ValueError, match="render failed"):
                render()
            assert len(figures) == target + 1
            if failure in {"setup", "layout"}:
                figures[-1].savefig.assert_not_called()
        else:
            result = render()
            names = ["s11_overlay.png"] if renderer == "overlay" else [
                "s11_sim_vs_meas.png", "reported_bands.png", "resonance_vs_target.png"]
            expected = [str(destination / name) for name in names]
            assert ([result] if renderer == "overlay" else result) == expected
            assert len(figures) == len(expected)
            for figure, path in zip(figures, expected):
                figure.savefig.assert_called_once_with(path, dpi=plots.DPI)
            assert destination.is_dir()
        assert closed == figures
