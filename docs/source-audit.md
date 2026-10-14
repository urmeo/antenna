# Source audit

The dataset records values from the supplied reports. Python checks their numerical consistency; it does not independently verify antenna performance. All page references below use PDF page numbers, starting at 1.

## Reported and derived results

Simulated S11, VSWR, bandwidth, main-lobe magnitude and side-lobe level follow the comparison table on [simulation report p. 20](simulation-and-results.pdf#page=20). Measured S11 and VSWR follow Tables 5.1–5.5 in the fabrication report. The per-shape sources are:

| Shape | Simulation band edges | Measured S11 and VSWR | Radiation figure at 2.45 GHz |
|---|---|---|---|
| Circular | [p. 6](simulation-and-results.pdf#page=6) | [Table 5.1, p. 6](fabrication-and-measurement.pdf#page=6) | [Fig. 4.4, p. 7](simulation-and-results.pdf#page=7): directivity |
| F-shaped | [p. 9](simulation-and-results.pdf#page=9) | [Table 5.2, p. 7](fabrication-and-measurement.pdf#page=7) | [Fig. 4.9, p. 10](simulation-and-results.pdf#page=10): directivity |
| Triangular | [p. 12](simulation-and-results.pdf#page=12) | [Table 5.3, p. 8](fabrication-and-measurement.pdf#page=8) | [Fig. 4.14, p. 13](simulation-and-results.pdf#page=13): directivity |
| Square | [p. 15](simulation-and-results.pdf#page=15) | [Table 5.4, p. 9](fabrication-and-measurement.pdf#page=9) | [Fig. 4.19, p. 16](simulation-and-results.pdf#page=16): gain |
| Hexagonal | [p. 18](simulation-and-results.pdf#page=18) | [Table 5.5, p. 10](fabrication-and-measurement.pdf#page=10) | [Fig. 4.24, p. 19](simulation-and-results.pdf#page=19): directivity |

The README keeps reported values separate from two calculations:

- VSWR from S11 uses `|Γ| = 10^(S11_dB / 20)` and `VSWR = (1 + |Γ|) / (1 − |Γ|)`. This identity applies at the same frequency and port reference.
- Fractional bandwidth uses `100 × (upper − lower) / midpoint`. Recalculating a percentage does not verify the source band edges or their threshold.

For the canonical dataset, `antenna check` reports **8 warnings**: five measured S11/VSWR inconsistencies and three bandwidth inconsistencies for the triangular, square and hexagonal patches. Three informational messages describe approximate resonance estimates relative to the target. A successful exit means no configured hard errors; the warnings remain unresolved.

The circular bandwidth also conflicts within the report: [p. 6](simulation-and-results.pdf#page=6) gives 3.62%, while [p. 20](simulation-and-results.pdf#page=20) gives 3.12%. The dataset retains the comparison-table value. Smaller differences that fall within the checker's tolerance are not independently verified by passing the check.

## Radiation quantities

The four directivity figures and the square gain figure above are simulated pattern cuts at `Phi = 90°`, all labeled at 2.45 GHz. They report different quantities. Their main-lobe values must not be ranked as a common antenna gain metric, and no measured gain is established. Pattern proxies derived from this mixed set cannot establish a comparable gain-per-area or gain-bandwidth ranking.

## Reconstruction parameters and feed

[Table 4.1, simulation report p. 4](simulation-and-results.pdf#page=4), explicitly lists `W = 37.60 mm`, `L = 29.38 mm`, ground dimensions `2W × 2L`, conductor thickness `0.036 mm`, substrate thickness `1.4 mm`, `Fi = 7 mm` and `Gpf = 1 mm`.

The repository also uses FR4 permittivity 4.4, loss tangent 0.02, feed width 2.7 mm, circular radius 17 mm, hexagonal side 17 mm and F-bar dimensions 10/8/3/25 mm. These are reconstruction inputs; the supplied dimension table does not establish them. Assigning `W` and `L` to individual shape dimensions is also part of the reconstruction.

The source geometries show inset feeds: [Fig. 4.1, p. 5](simulation-and-results.pdf#page=5), [Fig. 4.6, p. 8](simulation-and-results.pdf#page=8), [Fig. 4.11, p. 11](simulation-and-results.pdf#page=11), [Fig. 4.16, p. 14](simulation-and-results.pdf#page=14) and [Fig. 4.21, p. 17](simulation-and-results.pdf#page=17). Table 4.1 calls `Fi` a feed-line length; the original CAD is needed to resolve its exact geometric interpretation.

The [CST macro](../cst/patch-antenna.bas) instead stops its feed `Gpf` before the patch edge, omits inset slots and does not use `Fi`. It is a simplified gap-coupled reconstruction. Its geometry and any new simulation results must not be presented as a reproduction of the original CST study. Run it in a fresh CST project; its reset routine deletes the named antenna component, port, materials and monitors.

Closed-form resonance and sizing calculations are estimates. The triangle uses an equilateral-patch model for an isosceles geometry; the hexagon uses an equal-area circle; the F shape uses its enclosing rectangle. These estimates do not establish the resonance of the fabricated antennas.

## Evidence still needed

The repository contains no original CST project/CAD, raw CST or VNA sweeps, calibration logs or repeat measurements. The supplied reports support transcription and comparison of reported values. Resolving their inconsistencies, validating the reconstruction and establishing performance at 2.45 GHz require the original files or new simulations and measurements. Passing software tests does not supply that evidence.
