# Source audit

Values are transcribed from the reports; Python checks numerical consistency. Page references use PDF pages, starting at 1.

## Reported and derived results

Simulated S11, VSWR, bandwidth, main-lobe magnitude and side-lobe level follow [simulation report p. 20](simulation-and-results.pdf#page=20). Per-shape sources:

| Shape | Simulation band edges | Measured S11 and VSWR | Radiation figure at 2.45 GHz |
|---|---|---|---|
| Circular | [p. 6](simulation-and-results.pdf#page=6) | [Table 5.1, p. 6](fabrication-and-measurement.pdf#page=6) | [Fig. 4.4, p. 7](simulation-and-results.pdf#page=7): directivity |
| F-shaped | [p. 9](simulation-and-results.pdf#page=9) | [Table 5.2, p. 7](fabrication-and-measurement.pdf#page=7) | [Fig. 4.9, p. 10](simulation-and-results.pdf#page=10): directivity |
| Triangular | [p. 12](simulation-and-results.pdf#page=12) | [Table 5.3, p. 8](fabrication-and-measurement.pdf#page=8) | [Fig. 4.14, p. 13](simulation-and-results.pdf#page=13): directivity |
| Square | [p. 15](simulation-and-results.pdf#page=15) | [Table 5.4, p. 9](fabrication-and-measurement.pdf#page=9) | [Fig. 4.19, p. 16](simulation-and-results.pdf#page=16): gain |
| Hexagonal | [p. 18](simulation-and-results.pdf#page=18) | [Table 5.5, p. 10](fabrication-and-measurement.pdf#page=10) | [Fig. 4.24, p. 19](simulation-and-results.pdf#page=19): directivity |

Derived checks:

- VSWR: `|Γ| = 10^(S11_dB / 20)`, `VSWR = (1 + |Γ|) / (1 − |Γ|)`, at the same frequency and port reference.
- Bandwidth: `100 × (upper − lower) / midpoint`; source edges and their threshold remain unverified.

`antenna check` reports **8 unresolved warnings**: five measured S11/VSWR conflicts and three bandwidth conflicts (triangle, square, hexagon). Three informational messages flag approximate resonance estimates away from the target. Exit success means no configured hard errors.

Circular bandwidth is 3.62% on [p. 6](simulation-and-results.pdf#page=6) and 3.12% on [p. 20](simulation-and-results.pdf#page=20); the dataset retains 3.12%. Differences within the checker’s tolerance remain unverified.

## Radiation quantities

The figures are simulated `Phi = 90°` cuts at 2.45 GHz: four directivity figures and one gain figure (square). They establish no measured gain or common gain ranking. The toolkit suppresses mixed-quantity gain-per-area and gain-bandwidth proxies.

## Reconstruction parameters and feed

[Table 4.1, simulation report p. 4](simulation-and-results.pdf#page=4), explicitly lists `W = 37.60 mm`, `L = 29.38 mm`, ground dimensions `2W × 2L`, conductor thickness `0.036 mm`, substrate thickness `1.4 mm`, `Fi = 7 mm` and `Gpf = 1 mm`.

The repository also uses FR4 permittivity 4.4, loss tangent 0.02, feed width 2.7 mm, circular radius 17 mm, hexagonal side 17 mm and F-bar dimensions 10/8/3/25 mm. These are reconstruction inputs; the supplied dimension table does not establish them. Assigning `W` and `L` to individual shape dimensions is also part of the reconstruction.

The source geometries show inset feeds: [Fig. 4.1, p. 5](simulation-and-results.pdf#page=5), [Fig. 4.6, p. 8](simulation-and-results.pdf#page=8), [Fig. 4.11, p. 11](simulation-and-results.pdf#page=11), [Fig. 4.16, p. 14](simulation-and-results.pdf#page=14) and [Fig. 4.21, p. 17](simulation-and-results.pdf#page=17). Table 4.1 calls `Fi` a feed-line length; the original CAD is needed to resolve its exact geometric interpretation.

The [CST macro](../cst/patch-antenna.bas) stops its feed `Gpf` before the patch edge and omits inset slots and `Fi`. This gap-coupled reconstruction differs from the original geometry and requires CST validation. Run it in a fresh project: reset deletes the named antenna component, port, materials and monitors.

Closed-form estimates use an equilateral model for the isosceles triangle, an equal-area circle for the hexagon and the enclosing rectangle for the F shape. They do not establish the fabricated antennas’ resonance.

## Evidence still needed

Original CAD/CST files, raw CST/VNA sweeps, calibration logs and repeat measurements are unavailable. Resolving report conflicts, validating the reconstruction and establishing performance at 2.45 GHz require original files or new simulations and measurements.
