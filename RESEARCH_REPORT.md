# Research report

## Initial Cross-Sensor Observability Bounds for Floating Photovoltaic Motion

### Comparative sensitivity of early NISAR L-band and historical Sentinel-1 C-band SAR

## Abstract

This study estimates the minimum persistent translation at which a floating
photovoltaic (FPV) installation becomes directionally recoverable in SAR
amplitude imagery. It compares early NISAR L-band GCOV and historical
Sentinel-1 C-band RTC observations using one frozen image-domain detector,
common physical displacement injections and common 10 m/20 m analysis grids.
Three stable FPV sites—Piolenc, Sirindhorn and Tengeh—were used. Temporal pairs
were split chronologically into calibration and test blocks with no acquisition
shared across them. Stable land estimated nuisance registration. Real array
pixels were removed from the comparison image, the footprint was inpainted,
and the array was reintroduced at known 1–60 m translations in eight
directions. A detection required acceptable masked-ECC quality, recovered
magnitude above a calibration-only 95th-percentile threshold and angular error
no greater than 45°. At the primary harmonized 20 m grid, pooled NISAR
co-polarized MD50/80/95 values were 11/20/25 m, compared with 17/23/30 m for
Sentinel-1. Dual-polarization consensus yielded 14/21/27 m and 20/27/36 m.
Site results were heterogeneous and Tengeh did not show an L-band MD95
advantage. Because only 15 independent NISAR test pairs were available versus
270 Sentinel-1 pairs, the findings are reported as initial observability bounds
rather than a general sensor ranking.

## 1. Problem and motivation

FPV arrays are difficult amplitude-tracking targets. Their repeating module
patterns can produce visually convincing but incorrect shifts, while speckle,
incidence geometry, reservoir conditions and imperfect georegistration can
move the apparent correlation peak. A displacement vector from one pre/post
pair is therefore not self-validating.

Two formative QGIS experiments exposed this problem. Omkareshwar returned
finite storm-spanning Sentinel-1 vectors that remained inside the non-event
control distribution. Yamakura showed strong localized post-typhoon structural
change in all six orbit/polarization channels, while its whole-array
translation remained below quiet-pair limits. The correct scientific problem
became an observability problem: **under controlled ground truth, where is the
detection boundary?**

## 2. Hypothesis

NISAR L-band uses a 24 cm wavelength. The working hypothesis was that its
longer-wavelength structural response might remain more persistent across FPV
dates than C-band response, producing a lower translation-detection boundary
when pixel spacing and the detector are controlled.

The competing hypothesis was that wavelength is secondary to source spacing,
array morphology, viewing geometry, local clutter and pair quality. This
competing explanation predicts heterogeneous site-level results even if pooled
curves separate.

## 3. Data

### 3.1 Sites

| Site | Country | NISAR calibration/test pairs | Sentinel-1 calibration/test pairs |
|---|---|---:|---:|
| Piolenc | France | 4 / 6 | 181 / 129 |
| Sirindhorn | Thailand | 3 / 3 | 133 / 92 |
| Tengeh | Singapore | 4 / 6 | 68 / 49 |

FPV masks were delineated independently of radar test outcomes from optical
reference imagery. Each site package also recorded stable control regions and
split-lock metadata.

### 3.2 Sensors and analysis products

- **Sentinel-1 C-band:** radiometrically terrain-corrected amplitude rasters,
  using the co-polarized channel as the primary channel and cross-polarized
  imagery for consensus.
- **NISAR L-band:** calibrated Level-2 GCOV diagonal covariance terms. GCOV
  terms provide radiometrically and terrain-corrected gamma-zero power on 10 m
  or 20 m grids depending on acquisition mode.

The public NISAR Worldview RGB sequence displayed in the research narrative
was an earlier screening product. It is not a calibrated input to the final
cross-sensor curves.

## 4. Experimental design

### 4.1 Locked split

Within each sensor/site/geometry stratum, pairs were ordered chronologically.
The earliest 60% formed the calibration block and the later 40% the test block.
No scene could appear in both. The preparation audit contains 678 unique pairs:
393 calibration and 285 test, with an empty cross-split overlap list.

### 4.2 Harmonization

Two regimes were defined before inference:

- `matched_10m`: accept source spacing ≤12.5 m and resample to 10 m;
- `harmonized_20m`: accept source spacing ≤25 m and resample to 20 m.

The 20 m regime is primary because it retains all three NISAR sites. The 10 m
NISAR subset has six test pairs from Tengeh and is exploratory.

### 4.3 Registration nuisance model

Four stable-control boxes were placed at fixed fractional chip positions. Each
pair was converted to dB, high-pass filtered and registered using bidirectional
phase correlation with a Hanning window. The median accepted control shift was
removed from the comparison raster before any target inference.

### 4.4 Controlled translation

For every accepted comparison raster, the optical FPV mask selected real array
pixels; Telea inpainting reconstructed the original footprint; selected array
pixels were translated by a known vector; magnitudes covered every integer
metre from 1 to 60; and directions were 0°, 45°, 90°, 135°, 180°, 225°, 270°
and 315°. This creates known image-domain ground truth while retaining real
speckle, geometry, clutter and array texture.

### 4.5 Recovery and decision rule

Masked enhanced correlation coefficient alignment estimated translation on
high-pass patches. A channel recovery was scored correct only when stable-land
registration and ECC quality were accepted, recovered magnitude exceeded the
calibration-only 95th-percentile sham threshold, and angular error was ≤45°.

The secondary dual-pol detector required both channels to alarm and their
recovered directions to agree within 45°. The consensus vector was the
component-wise median of the two channel vectors.

### 4.6 Outcomes and uncertainty

For each magnitude, observed recovery probability was monotonized using
weighted isotonic regression. MD50, MD80 and MD95 are the first tested
magnitudes reaching 0.50, 0.80 and 0.95 recovery. Confidence intervals were
estimated with 5,000 bootstrap iterations that resampled acquisition pairs,
preserving the dependence among eight injected directions from the same pair.

## 5. Results

### 5.1 Primary pooled 20 m bounds

| Detector | Sensor | Pairs | MD50 (95% CI) | MD80 (95% CI) | MD95 (95% CI) |
|---|---|---:|---:|---:|---:|
| Co-pol | NISAR L | 15 | 11 (11–15) | 20 (16–23) | 25 (22–26) |
| Co-pol | Sentinel-1 C | 270 | 17 (16–17) | 23 (22–23) | 30 (29–32) |
| Dual consensus | NISAR L | 15 | 14 (12–17) | 21 (18–26) | 27 (23–32) |
| Dual consensus | Sentinel-1 C | 270 | 20 (20–21) | 27 (26–28) | 36 (34–38) |

The pooled point estimates favour NISAR in both detector variants. The much
wider NISAR uncertainty and the sample-depth imbalance must be retained in any
interpretation.

### 5.2 Site heterogeneity

Piolenc produces the largest separation: dual-pol MD95 is 24 m for NISAR and
38 m for Sentinel-1. Sirindhorn differs by five metres in dual-pol MD95. Tengeh
ties at 32 m in dual-pol and favours Sentinel-1 by four metres in co-pol MD95.
This counterexample prevents a defensible universal L-band claim.

### 5.3 Exploratory 10 m regime

Sentinel-1 reached co-pol MD95 at 15 m and dual-pol MD95 at 20 m. The NISAR
subset reached MD50/MD80 at 5/8 m (co-pol) and 6/8 m (dual-pol), but MD95 was
not reached through 60 m. Because only six NISAR pairs from one site met the
10 m source-spacing rule, this result is a sampling warning—not evidence of
catastrophic L-band failure.

## 6. Formative QGIS experiments

### Omkareshwar

Fifteen Sentinel-1 scenes from two relative orbits bracketed the April 2024
storm. The archived pilot's event vectors remained below empirical non-event
limits, so no storm-associated displacement was resolved. This demonstrated
why a finite vector is not automatically a physical detection.

### Yamakura

Seventy-eight dual-polarization Sentinel-1 scenes covered three relative
orbits around Typhoon Faxai. The documented damage sector exceeded every
matched quiet-pair structural-change limit (6/6), while the southern stable
sector produced 0/6 detections. Whole-array translation produced 0/6
detections. The result was therefore localized structural reconfiguration with
unresolved coherent translation.

### NISAR Worldview screen

Eight rendered public Worldview dates at Omkareshwar produced apparent motion
below their own stable-control limit. Because Worldview provides rendered RGB
rather than native calibrated covariance values, this was treated only as a
feasibility screen. The final comparison used authenticated calibrated GCOV
terms.

## 7. Discussion

The preliminary pooled result is consistent with better L-band observability
under this detector at 20 m. However, “L-band is better” is not the result. A
sensor–site–algorithm system determines the boundary. Tengeh demonstrates that
the ranking can reverse or disappear, and sparse NISAR dates make site
estimates unstable.

The project’s strongest contribution is methodological: it replaces subjective
pre/post arrows with a falsifiable sensitivity curve, prevents calibration/test
scene leakage, preserves pair-level dependence in uncertainty and reports
failure to reach a boundary without extrapolation.

## 8. Limitations

1. NISAR provides only 15 primary test pairs, versus 270 Sentinel-1 pairs.
2. NISAR site calibration blocks contain only three or four pairs.
3. Rigid synthetic translation does not reproduce rotation, fracture,
   partial-block motion or changing reservoir interaction.
4. Amplitude tracking does not estimate centimetric phase displacement.
5. Masks are optical-derived approximations of array support.
6. Three sites are insufficient for global ecological or engineering
   generalization.
7. No documented real event supplies metre-accurate translation ground truth
   for validating the cross-sensor ranking.

## 9. Conclusion

Under a common 20 m grid and one frozen direction-aware amplitude detector,
the available early NISAR sample reaches lower pooled synthetic-translation
boundaries than historical Sentinel-1. The effect is site dependent and the
NISAR sample is underpowered. The scientifically correct conclusion is:

> Early NISAR L-band observations provide promising but provisional lower
> pooled FPV motion-observability bounds; additional independent acquisitions
> and sites are required before claiming a general cross-band advantage.

This report is intentionally a research portfolio, not a submitted paper. The
methods, null results and limitations remain visible so future NISAR
acquisitions can extend—rather than rewrite—the benchmark.

