# Initial Cross-Sensor Observability Bounds for Floating Photovoltaic Motion

### A comparative sensitivity study of early NISAR L-band and historical Sentinel-1 C-band SAR

[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![QGIS](https://img.shields.io/badge/QGIS-reproducible%20raster%20lab-589632?logo=qgis&logoColor=white)](QGIS_WORKFLOW.md)
[![Experiment](https://img.shields.io/badge/design-acquisition--disjoint-137B80)](METHODS.md)
[![Status](https://img.shields.io/badge/status-initial%20bounds-F0A34A)](#what-the-project-establishes)

> **Research question:** after forcing early NISAR L-band GCOV and historical
> Sentinel-1 C-band RTC observations onto the same spatial grids and applying
> one frozen detector, how much persistent floating-photovoltaic translation is
> required before its direction is recovered reliably?

This repository is a complete research portfolio rather than a publication
claim. It contains the theory, QGIS exploration, tracked raster examples,
synthetic-injection algorithm, acquisition-disjoint experiment, uncertainty
analysis, negative results, and an explicit audit of what the current sample
cannot establish.

**[Open FPV Earth—the 3D global observatory →](docs/index.html)** · **[Open the georeferenced raster atlas →](docs/atlas.html)** · **[Read the complete research paper →](docs/paper.html)**

FPV Earth combines the complete 643-record peer-reviewed Nobre et al. global
survey (517 coordinate-mappable installations in 28 countries) with the three
sites where this repository actually calibrates SAR displacement sensitivity.
Its time control reconstructs the catalogue through 2023; its 3D motion lab
translates the real optical-derived footprints and reads exact pooled recovery
probabilities and site MD50/80/95 values. It never labels synthetic motion as
observed physical drift. Selecting a mapped record can query the nearest
Sentinel-2 L2A acquisition through the public Planetary Computer STAC catalogue;
that is an on-demand acquisition lookup, not a real-time camera. The calamity
mode animates the registered pre/post/change evidence while preserving each
event's actual outcome. The raster atlas remains the pixel-level audit surface.

An editable Blender companion is included in [`blender/`](blender/). Its WGS84
scene contains the 517 mapped records, country-density extrusions, a 360-frame
Earth rig and evidence-aware event markers. Yamakura is animated as localized
change, Omkareshwar as below detection, and Tengeh as a clearly labelled 40 m
controlled synthetic replay (15,000× visual exaggeration at globe scale). The
generated `.blend`, animated GLB, preview and semantic manifest are all tracked.

![Blender WGS84 globe built from the 517 geolocated FPV records](docs/assets/blender/fpv_globe_preview.png)

![Controlled translation on a real Tengeh Sentinel-1 raster](docs/assets/research/injection_pipeline_real_raster.png)

## Abstract

Floating photovoltaic (FPV) fields are structurally repetitive targets whose
apparent motion in SAR amplitude imagery is easily confounded by speckle,
viewing geometry and registration error. I tested whether radar wavelength
changes the practical observability boundary for persistent rigid translation.
Optical-derived FPV masks at Piolenc, Sirindhorn and Tengeh were combined with
NISAR L-band GCOV and Sentinel-1 C-band RTC rasters. Temporal pairs were split
chronologically into calibration (60%) and untouched test (40%) blocks without
sharing acquisitions. Stable land estimated registration nuisance motion.
Known translations of 1–60 m were injected in eight directions after the
original footprint was inpainted, and masked ECC recovered each vector.

At the primary 20 m grid, pooled co-polarized MD50/80/95 values were
**11/20/25 m for NISAR** and **17/23/30 m for Sentinel-1**. Dual-polarization
consensus gave **14/21/27 m** and **20/27/36 m**, respectively. The apparent
L-band advantage was not universal: Tengeh favoured Sentinel-1 in the co-pol
analysis and tied at dual-pol MD95. Most importantly, NISAR contributed only 15
test pairs versus 270 Sentinel-1 pairs. These are therefore **initial
observability bounds**, not a mission ranking.

## Theory tested

NISAR L-band operates at a 24 cm wavelength, while Sentinel-1 is a C-band
system. The working hypothesis was that a longer-wavelength structural
backscatter pattern might remain sufficiently persistent across dates to lower
the translation required for directional recovery. The counter-hypothesis was
that spatial resolution, array morphology, local background and temporal scene
quality dominate wavelength.

The result supports neither extreme. Pooled curves favour L-band, but the
site-level reversal at Tengeh shows that **band is only one term in an
observability system**.

## Experimental evidence

| Primary 20 m detector | NISAR L MD50 / MD80 / MD95 | Sentinel-1 C MD50 / MD80 / MD95 |
|---|---:|---:|
| Co-polarized | **11 / 20 / 25 m** | **17 / 23 / 30 m** |
| Dual-pol consensus | **14 / 21 / 27 m** | **20 / 27 / 36 m** |

| Site | Test pairs L / C | Co-pol MD95 L / C | Dual-pol MD95 L / C |
|---|---:|---:|---:|
| Piolenc, France | 6 / 129 | **25 / 32 m** | **24 / 38 m** |
| Sirindhorn, Thailand | 3 / 92 | **24 / 30 m** | **25 / 30 m** |
| Tengeh, Singapore | 6 / 49 | **25 / 21 m** | **32 / 32 m** |

Site results are point estimates only. The pooled NISAR MD95 95% intervals are
22–26 m (co-pol) and 23–32 m (dual-pol); all three NISAR site strata fail the
prespecified independent-pair adequacy target.

<p align="center">
  <img src="docs/assets/research/cross_sensor_copol_20m.png" width="49%" alt="Pooled co-polarized L and C band detection curves">
  <img src="docs/assets/research/cross_sensor_dual_20m.png" width="49%" alt="Pooled dual-polarization L and C band detection curves">
</p>

## From QGIS observation to controlled benchmark

The project began with manual multi-date raster inspection in QGIS. At
Omkareshwar, storm-spanning Sentinel-1 vectors stayed inside ordinary
stable-control variability. At Yamakura, the documented Typhoon Faxai failure
produced repeatable localized structural change in 6/6 orbit/polarization
channels, but whole-array translation remained below its quiet-pair thresholds.
Those two cases motivated a better question: **not “did this array move?” but
“how far must an array move before this sensor-detector system can resolve it?”**

![Yamakura structural change and unresolved rigid translation](docs/assets/research/yamakura_structural_change_result.png)

The tracked QGIS package includes two editable `.qgz` projects, real pre-event,
post-event and difference GeoTIFFs, three optical-derived FPV mask rasters, a
representative Sentinel-1 VV/VH temporal pair, and one NISAR Worldview RGB
GeoTIFF labelled visualization-only. See [QGIS_WORKFLOW.md](QGIS_WORKFLOW.md)
and [`qgis/`](qgis/).

## Frozen algorithm

1. Convert linear gamma-zero amplitude to decibels.
2. Resample both sensors to an explicit 10 m or 20 m grid.
3. Estimate pair-specific translation from four stable-land controls.
4. Warp the comparison raster to remove median land motion.
5. Inpaint the original optical-derived FPV footprint.
6. Translate the real array pixels by 1–60 m in eight directions.
7. Recover translation with masked, high-pass ECC.
8. Require accepted ECC quality, magnitude above the calibration-only 95th
   percentile and angular error ≤45°.
9. For dual-pol consensus, require both channels to alarm and agree within 45°.
10. Fit monotonic recovery curves and bootstrap complete acquisition pairs.

The implementation is in [`src/cross_sensor_inference.py`](src/cross_sensor_inference.py).

## What the project establishes

- A complete, auditable method for estimating **sensor–site–algorithm
  observability bounds** rather than interpreting one apparent vector.
- Lower preliminary pooled 20 m bounds for the available early NISAR L-band
  sample under the frozen detector.
- Strong site dependence that rejects a universal wavelength-only explanation.
- A reusable benchmark architecture that reports `not_reached` instead of
  extrapolating beyond the tested range.

It does **not** establish universal L-band superiority, centimetric physical
motion, or operational event detection. Synthetic persistence is controlled
ground truth; it is not a substitute for documented engineering displacement.

## Audit trail

- 1,377 prepared scene records.
- 678 unique temporal pairs.
- 393 calibration and 285 test pairs.
- zero calibration/test scene overlap.
- 538,560 channel trials and 269,280 dual-pol consensus trials.
- 5,000 acquisition-pair clustered bootstrap iterations.
- automated self-test error: 0.0265 px.

Every compact reported result is under [`data/derived/`](data/derived/). The
large trial-level tables are regenerated by the Kaggle notebook and excluded
from Git history. File hashes are recorded in [`provenance/`](provenance/).

## Repository map

```text
analysis/      figure and summary regeneration
blender/       reproducible WGS84 scene builder, editable .blend and manifest
config/        frozen experiment definition
data/derived/  compact numerical audit trail
docs/          interactive research narrative and 3D site analysis
notebooks/     complete Kaggle acquisition/inference notebook
qgis/          editable projects and selected real raster examples
results/       pooled publication-resolution curves
src/           data preparation and frozen inference engine
tests/         release-integrity checks
```

Start with [RESEARCH_REPORT.md](RESEARCH_REPORT.md), then use
[REPRODUCIBILITY.md](REPRODUCIBILITY.md) to recreate the analysis.

## Sources and licensing

Mission and product facts are linked in [REFERENCES.md](REFERENCES.md). Raw
provider imagery is not redistributed wholesale. The small tracked raster
examples are included for transparent workflow inspection; check
[DATA_LICENSE.md](DATA_LICENSE.md) before redistribution. Code is MIT licensed.
