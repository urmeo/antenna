"""Check the built wheel, installed CLI and plotting extra in an isolated venv."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile


def run(command: list[str], cwd: Path, env: dict[str, str]) -> str:
    print("Running:", " ".join(command), flush=True)
    result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True)
    if result.returncode:
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        raise SystemExit(result.returncode)
    return result.stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    args = parser.parse_args()
    wheels = list(args.dist.resolve().glob("*.whl"))
    if len(wheels) != 1:
        parser.error("--dist must contain exactly one built wheel")
    wheel = wheels[0]
    root = Path(__file__).resolve().parents[1]
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        assert "antenna/data/results.json" in names, "wheel is missing its dataset"
        assert any(name.endswith("/licenses/LICENSE") for name in names), "wheel is missing its license"

    with tempfile.TemporaryDirectory(prefix="antenna-release-") as directory:
        work = Path(directory)
        environment = work / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        scripts = environment / ("Scripts" if os.name == "nt" else "bin")
        python = scripts / ("python.exe" if os.name == "nt" else "python")
        cli = scripts / ("antenna.exe" if os.name == "nt" else "antenna")
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env["MPLCONFIGDIR"] = str(work / "matplotlib")
        run([str(python), "-m", "pip", "install", "--no-cache-dir", str(wheel) + "[plots]"], work, env)

        def antenna(*arguments: str) -> str:
            return run([str(cli), *arguments], work, env)

        antenna("--help")
        print(antenna("check"), end="")
        antenna("design")
        antenna("synth")
        reports = antenna("tables")
        assert "Pattern proxy columns are n/a:" in reports
        readme = work / "README.md"
        shutil.copyfile(root / "README.md", readme)
        antenna("tables", "--check", "--readme", str(readme))
        antenna("tables", "--write", "--readme", str(readme))
        antenna("tables", "--check", "--readme", str(readme))

        sweep = work / "synthetic.s1p"
        sweep.write_text("! Synthetic smoke test; not a measurement.\n# GHz S DB R 50\n"
                         "2.30 -6 0\n2.40 -14 0\n2.45 -32 0\n2.50 -13 0\n2.60 -5 0\n")
        metrics = antenna("ingest", str(sweep))
        assert "2.4500" in metrics and "-32.00" in metrics
        output = work / "plots"
        antenna("plot", "--out", str(output), "--s1p", str(sweep))
        expected = {"s11_sim_vs_meas.png", "reported_bands.png",
                    "resonance_vs_target.png", "s11_overlay.png"}
        assert {path.name for path in output.glob("*.png")} == expected
        for name in expected:
            image = (output / name).read_bytes()
            assert image.startswith(b"\x89PNG\r\n\x1a\n") and len(image) > 1000, name
        print("PASS: wheel dataset/license, installed CLI, tables, sweep ingestion and four PNG plots.")


if __name__ == "__main__":
    main()
