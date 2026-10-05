# Methods

## Question

At a common spatial grid and under a frozen detector, what persistent rigid
translation is required before floating-photovoltaic motion becomes
directionally recoverable from NISAR L-band and Sentinel-1 C-band amplitude
imagery?

## Study sites

The benchmark uses three geographically distinct installations: Tengeh
(Singapore), Piolenc (France), and Sirindhorn (Thailand). Their masks were
defined before inspecting cross-sensor test outcomes.

## Acquisition split

Within each sensor/site/geometry stratum, acquisition-disjoint temporal pairs
were ordered chronologically. The earliest 60% calibrated thresholds; the later
40% formed an untouched synthetic-injection test block. No scene crosses the
split.

## Harmonization

Two analysis regimes were evaluated:

- `matched_10m`: source pixels no coarser than 12.5 m, resampled to 10 m.
- `harmonized_20m`: source pixels no coarser than 25 m, resampled to 20 m.

The 20 m regime is the primary comparison because it retains all three NISAR
sites. The 10 m NISAR result contains only six test pairs and is exploratory.

## Detector

Stable land controls estimate the pair-specific registration offset. The array
footprint in the comparison image is inpainted and translated synthetically by
1–60 m in eight directions. Masked enhanced correlation coefficient alignment
recovers a translation vector.

A recovery requires:

1. accepted land registration and ECC quality;
2. recovered magnitude exceeding a calibration-only 95th-percentile threshold;
3. angular error no greater than 45 degrees.

The co-polarized channel is the primary cross-mission detector. A frozen
dual-polarization consensus detector is secondary and requires both channels to
alarm with recovered directions agreeing within 45 degrees.

## Outcomes

Directionally correct recovery probability is evaluated at every integer metre
from 1 to 60. Isotonic regression enforces a monotonic sensitivity curve.
MD50, MD80, and MD95 are the first injected magnitudes reaching recovery
probabilities of 0.50, 0.80, and 0.95. Confidence intervals use acquisition-pair
clustered bootstrap resampling.

## Interpretation boundary

This is an observability benchmark based on synthetic persistent translation.
It is not evidence that a real installation moved, and it is not a universal
ranking of L-band and C-band SAR. The early NISAR archive yields only 15 pooled
20 m test pairs, so site-specific estimates remain preliminary.

