# Technical references

## Global FPV catalogue

- Nobre, R. et al. (2024). [A global study of freshwater coverage by floating photovoltaics](https://doi.org/10.1016/j.solener.2023.112244). *Solar Energy*, 267, 112244 — source of the 643-record survey snapshot through April 2023.

## Mission and product documentation

- [NISAR mission quick facts](https://nisar.jpl.nasa.gov/mission/quick-facts/) —
  L-band wavelength, repeat cycle and mission characteristics.
- [NISAR radar description](https://nisar.jpl.nasa.gov/mission/observatory/radars/) —
  L-SAR architecture and mode-dependent resolution.
- [NISAR GCOV user guide](https://hyp3-docs.asf.alaska.edu/nisar-docs/gcov/) —
  calibrated covariance terms, gamma-zero RTC and 10/20 m posting.
- [Finding NISAR data with Earthaccess](https://nisar-docs.asf.alaska.edu/earthaccess/) —
  authenticated collection discovery used by the notebook.
- [ESA Sentinel-1 overview](https://www.esa.int/Applications/Observing_the_Earth/Copernicus/Sentinel-1) —
  mission context for C-band SAR.

## Algorithms and software

- [OpenCV `findTransformECC`](https://docs.opencv.org/3.4/dc/d6b/group__video__track.html) —
  area-based image alignment used for masked translation recovery.
- [QGIS raster analysis](https://docs.qgis.org/latest/en/docs/user_manual/working_with_raster/raster_analysis.html) —
  exploratory post-minus-pre raster construction.
- [Microsoft Planetary Computer STAC API](https://planetarycomputer.microsoft.com/docs/reference/stac/) —
  anonymous nearest-date Sentinel-2 L2A discovery used by the live EO panel.
- [BlenderGIS](https://github.com/domlysz/BlenderGIS) — optional georeferencing,
  GeoTIFF and DEM bridge for Blender site-scale insets. The deterministic global
  scene uses a documented WGS84-to-geocentric transform.
- [AnyMap spinning-globe tutorial](https://www.youtube.com/watch?v=9p8FIUij36k) —
  interaction reference for globe rotation, layer controls and 3D extrusion;
  the implementation here is original MapLibre/Blender code.

## Citation boundary

Mission documentation supports product and sensor facts. All numerical MD
results in this repository come from the tracked experiment outputs—not from
these external pages. This portfolio does not claim that its three-site sample
is a published global sensor validation.
