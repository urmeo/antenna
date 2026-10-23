# Antenna

Five FR4 patch antenna shapes designed for 2.45 GHz, simulated in CST, fabricated and measured with a VNA. Python checks the reported values and generates tables and plots.

**Keywords:** Microstrip antennas · S-parameters · CST simulation · VNA measurements

## Pipeline

<p align="center">
  <a href="images/pipeline.svg"><img src="images/pipeline.svg" alt="Design, simulation, fabrication and VNA measurement feed report-based Python checks; eight data warnings remain." width="760"></a>
</p>

[Full-size diagram](images/pipeline.svg) · [Edit in Figma](https://www.figma.com/design/NjLkmRozV5EbUtvv6ulIFG?node-id=2-2)

[Results](#results) · [Design](#design) · [Gallery](#gallery) · [Run](#run) · [Limits](#evidence-limits) · [References](#references)

## Results

S11 minima are reported at each shape’s resonance. **Circular has the deepest reported minimum and the only listed band covering 2.45 GHz.**

### S11 and VSWR

<!-- BEGIN:results-table -->
| Shape | Simulated S11 (dB) | Measured S11 (dB) | Reported VSWR | VSWR from measured S11 |
|---|---|---|---|---|
| **Circular** | **−53.08** | **−31.99** | **1.125** | **1.052** |
| F-shaped | −30.02 | −16.98 | 1.167 | 1.330 |
| Triangular | −18.86 | −15.37 | 1.368 | 1.411 |
| Square | −16.38 | −14.46 | 1.536 | 1.467 |
| Hexagonal | −14.78 | −13.93 | 1.694 | 1.504 |
<!-- END:results-table -->

All five measured S11/VSWR pairs disagree under a shared frequency and port reference; those conditions are undocumented. The pairs remain unverified; calculated VSWR is a consistency check.

<p align="center">
  <a href="outputs/s11_sim_vs_meas.png"><img src="outputs/s11_sim_vs_meas.png" alt="Reported simulated and measured S11 minima" width="760"></a>
  <br><sub>Reported S11 minima</sub>
</p>

### Reported simulation bands

<!-- BEGIN:bandwidth-table -->
| Shape | Reported band (GHz) | Reported BW (%) | BW from edges (%) |
|---|---|---|---|
| **Circular** | **2.3990 to 2.4735** | **3.12** | **3.06** |
| F-shaped | 2.2994 to 2.3735 | 2.98 | 3.17 |
| Triangular | 2.1380 to 2.2830 | 2.45 | 6.56 |
| Square | 2.0930 to 2.1732 | 2.41 | 3.76 |
| Hexagonal | 2.0945 to 2.2455 | 2.12 | 6.96 |
<!-- END:bandwidth-table -->

BW from edges uses `100 × (upper − lower) / midpoint`. Triangular, square and hexagonal percentages disagree with their listed edges. The threshold and normalization frequency are undocumented; all bands remain unverified. Circular is **3.62%** on [p. 6](docs/simulation-and-results.pdf#page=6) and **3.12%** on [p. 20](docs/simulation-and-results.pdf#page=20).

<p align="center">
  <a href="outputs/reported_bands.png"><img src="outputs/reported_bands.png" alt="Reported simulation bands relative to the 2.45 GHz target" width="760"></a>
  <br><sub>Reported simulation bands</sub>
</p>

### Supporting plots

<p align="center">
  <a href="outputs/s11_circular_cst.png"><img src="outputs/s11_circular_cst.png" alt="Circular patch S11 plot from CST" width="760"></a>
  <br><sub>Circular patch · CST S11</sub>
</p>

<p align="center">
  <a href="outputs/resonance_vs_target.png"><img src="outputs/resonance_vs_target.png" alt="Approximate closed-form resonance compared with the 2.45 GHz target" width="760"></a>
  <br><sub>Closed-form resonance estimates</sub>
</p>

## Design

Reconstruction inputs. Closed-form estimates use an equilateral approximation for the triangle, an equal-area circle for the hexagon and an enclosing rectangle for the F-shape.

### Substrate and feed

| Parameter | Value |
|---|---|
| Substrate | FR4; εr 4.4; loss tangent 0.02 |
| Substrate thickness | 1.4 mm |
| Copper thickness | 0.036 mm |
| Ground plane | 75.20 × 58.76 mm |
| Feed width / gap | 2.7 / 1 mm |

### Patch dimensions

| Shape | Dimensions (mm) |
|---|---|
| Circular | Radius 17 |
| F-shaped | 37.60 × 29.38; vertical 10; bars 8; gap 3; middle 25 |
| Triangular | Base 37.60; height 29.38 |
| Square | Side 29.38 |
| Hexagonal | Side 17 |

## Gallery

### Antennas

<table>
  <tr>
    <td align="center" width="50%" valign="top">
      <a href="images/antennas/all-five-geometries.jpg"><img src="images/antennas/all-five-geometries.jpg" alt="Fabricated samples of all five patch geometries" width="320"></a>
      <br><sub>All five geometries</sub>
    </td>
    <td align="center" width="50%" valign="top">
      <a href="images/antennas/circular-patch.jpg"><img src="images/antennas/circular-patch.jpg" alt="Fabricated circular patch antennas" width="320"></a>
      <br><sub>Circular</sub>
    </td>
  </tr>
  <tr>
    <td align="center" width="50%" valign="top">
      <a href="images/antennas/f-shaped-patch.jpg"><img src="images/antennas/f-shaped-patch.jpg" alt="Fabricated F-shaped patch antennas" width="320"></a>
      <br><sub>F-shaped</sub>
    </td>
    <td align="center" width="50%" valign="top">
      <a href="images/antennas/triangular-patch.jpg"><img src="images/antennas/triangular-patch.jpg" alt="Fabricated triangular patch antennas" width="320"></a>
      <br><sub>Triangular</sub>
    </td>
  </tr>
  <tr>
    <td align="center" width="50%" valign="top">
      <a href="images/antennas/square-patch.jpg"><img src="images/antennas/square-patch.jpg" alt="Fabricated square patch antennas" width="320"></a>
      <br><sub>Square</sub>
    </td>
    <td align="center" width="50%" valign="top">
      <a href="images/antennas/hexagonal-patch.jpg"><img src="images/antennas/hexagonal-patch.jpg" alt="Fabricated hexagonal patch antennas" width="320"></a>
      <br><sub>Hexagonal</sub>
    </td>
  </tr>
</table>

### Fabrication

<table>
  <tr>
    <td align="center" width="50%" valign="top">
      <a href="images/fabrication/fr4-substrate-blank.jpg"><img src="images/fabrication/fr4-substrate-blank.jpg" alt="Blank FR4 substrate" width="320"></a>
      <br><sub>FR4 substrate</sub>
    </td>
    <td align="center" width="50%" valign="top">
      <a href="images/equipment/laminator.jpg"><img src="images/equipment/laminator.jpg" alt="Laminator used for fabrication" width="320"></a>
      <br><sub>Laminator</sub>
    </td>
  </tr>
  <tr>
    <td align="center" width="50%" valign="top">
      <a href="images/equipment/uv-exposure-open.jpg"><img src="images/equipment/uv-exposure-open.jpg" alt="Open UV exposure unit" width="320"></a>
      <br><sub>UV exposure · open</sub>
    </td>
    <td align="center" width="50%" valign="top">
      <a href="images/equipment/uv-exposure-closed.jpg"><img src="images/equipment/uv-exposure-closed.jpg" alt="Closed UV exposure unit" width="320"></a>
      <br><sub>UV exposure · closed</sub>
    </td>
  </tr>
  <tr>
    <td align="center" width="50%" valign="top">
      <a href="images/fabrication/circular-patch-naoh-bath.jpg"><img src="images/fabrication/circular-patch-naoh-bath.jpg" alt="Circular patch in a sodium hydroxide bath" width="320"></a>
      <br><sub>NaOH bath</sub>
    </td>
    <td align="center" width="50%" valign="top">
      <a href="images/equipment/etching-machine.jpg"><img src="images/equipment/etching-machine.jpg" alt="Etching machine used for fabrication" width="101"></a>
      <br><sub>Etching machine</sub>
    </td>
  </tr>
</table>

### Measurement

<p align="center">
  <a href="images/equipment/vna-smith-chart.jpg"><img src="images/equipment/vna-smith-chart.jpg" alt="VNA setup showing a Smith chart over 4.1–4.4 GHz" width="101"></a>
  <br><sub>VNA setup · 4.1–4.4 GHz display</sub>
</p>

## Run

Python 3.9+; run from the repository root:

```bash
python -m pip install -r requirements.txt "pytest>=7"
export PYTHONPATH="$PWD/src"
python -m antenna check
python -m antenna tables --check --readme README.md
python -m pytest
```

### Commands

| Task | Command |
|---|---|
| Plot comparisons | `python -m antenna plot --out outputs` |
| Analyze a sweep | `python -m antenna ingest path/to/trace.s1p` |
| Update README tables | `python -m antenna tables --write --readme README.md` |
| Estimate resonance / dimension | `python -m antenna design` / `python -m antenna synth` |

### CST model

Open [`cst/patch-antenna.bas`](cst/patch-antenna.bas) in CST’s VBA editor, choose `PatchShape`, and run in a fresh project. Its gap-coupled feed differs from the reported inset feeds and requires CST validation.

## Tech Stack

| Tool | Use |
|---|---|
| Python 3.9+ | Report checks and derived tables |
| Matplotlib | S11, bandwidth and resonance plots |
| pytest | Analysis and command-line checks |
| CST / VBA | Simulation and model reconstruction |
| VNA | Measurements recorded in the source reports |

## Evidence limits

Source reports: [Simulation and results](docs/simulation-and-results.pdf) · [Fabrication and measurement](docs/fabrication-and-measurement.pdf) · [Methodology](docs/methodology.pdf)

- Original CAD/CST files, raw sweeps, reading/calibration records and repeat measurements are unavailable.
- Four radiation values are simulated directivity and one is simulated gain. No measured gain or common gain ranking is established.
- Keep new raw sweeps, reading frequencies and calibration records separate from these historical values.

Check status: **0 errors · 8 unresolved warnings · 3 informational estimates**. Software checks do not validate hardware performance or 2.45 GHz suitability.

## Roadmap

- [ ] Add original CAD/CST models, raw sweeps, calibration records and repeat measurements.
- [ ] Verify reported S11/VSWR pairs and bandwidth values at documented reading frequencies.
- [ ] Validate the reconstructed gap-coupled feed against the reported inset feeds.

## References

- Balanis (2016). [Antenna Theory, 4th ed.](https://www.wiley.com/en-us/Antenna+Theory%3A+Analysis+and+Design%2C+4th+Edition-p-9781118642061).
- Garg et al. (2001). [Microstrip Antenna Design Handbook](https://us.artechhouse.com/Microstrip-Antenna-Design-Handbook-P619.aspx).
- Pozar (1992). [Microstrip Antennas](https://doi.org/10.1109/5.119568).
- IBIS Open Forum (2024). [Touchstone v2.1 specification](https://www.ibis.org/touchstone_ver2.1/touchstone_ver2_1.pdf).

## License

[MIT License](LICENSE)
