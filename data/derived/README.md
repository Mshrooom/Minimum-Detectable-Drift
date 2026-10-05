# Derived-data dictionary

These compact files are sufficient to audit every reported summary without
redistributing provider imagery or the 200+ MB trial-level tables.

| File | Purpose |
|---|---|
| `preparation_audit.json` | Scene, pair, split, and leakage counts from data preparation. |
| `calibration_shams.csv` | Zero-displacement calibration measurements used to set magnitude thresholds. |
| `thresholds.csv` | Frozen calibration-only thresholds by sensor, site, grid, and channel. |
| `detection_curves.csv` | Observed and isotonic recovery probability by injected magnitude. |
| `md_boundaries.csv` | Pooled MD50/80/95 estimates and pair-clustered 95% intervals. |
| `cross_sensor_advantage_curves.csv` | Difference in L- and C-band recovery curves, including uncertainty. |
| `crossover_summary.csv` | First magnitude satisfying the prespecified supported-advantage rule. |
| `power_audit.csv` | Independent-pair depth and adequacy flag by sensor and site. |
| `site_md_summary.csv` | Site-level point estimates used in the 3D map; no site CIs are claimed. |
| `summary.json` | Machine-readable experiment result and software versions. |

The separate `data/external/global_fpv_inventory_2023.csv` table contains all
643 catalogue records extracted from the peer-reviewed Nobre et al. (2024)
supplement. Of these, 517 contain mappable coordinates. This is a survey through
April 2023—not a complete or continuously updated 2026 registry.

`MDxx` means the first injected displacement where the monotonic fitted curve
reaches `xx%` directionally correct recovery. Values marked `not_reached` are
not extrapolated beyond the tested 60 m range.
