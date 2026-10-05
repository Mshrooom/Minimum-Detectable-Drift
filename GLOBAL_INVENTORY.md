# Global FPV inventory layer

The 3D Earth interface separates three fundamentally different evidence levels:

1. **Global catalogue:** all 643 records in the survey by Nobre et al. (2024),
   conducted through April 2023. The source provides usable coordinates for
   517 records; the remaining 126 remain counted but cannot be placed as points.
2. **SAR-calibrated benchmark:** Piolenc, Sirindhorn and Tengeh, where the
   repository contains acquisition-disjoint synthetic displacement experiments
   and MD50/80/95 values.
3. **Event audits:** Yamakura and Omkareshwar, where documented or suspected
   change was inspected but metre-accurate physical displacement is unavailable.

The globe is therefore global in catalogue coverage, not in motion inference.
It does not imply that all 643 installations are monitored, moving, or current.
No public source currently provides an exhaustive real-time global FPV registry.

## Reproduction

The publisher supplement is an Excel-generated PDF. Extract it with:

```bash
python analysis/extract_global_fpv_inventory.py --pdf path/to/mmc1.pdf
python analysis/build_3d_observatory.py
```

The parser requires exactly 643 rows, retains records without coordinates,
converts DMS coordinates to WGS84 decimal degrees and flags rows whose source
longitude omitted an E/W/O hemisphere.

## Source

Nobre, R. et al. (2024). *A global study of freshwater coverage by floating
photovoltaics*. Solar Energy, 267, 112244.
https://doi.org/10.1016/j.solener.2023.112244
