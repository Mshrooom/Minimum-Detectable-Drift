# Blender / BlenderGIS scene

This folder turns the audited FPV catalogue and event cases into a reproducible
Blender scene. It follows the spinning-globe visual grammar requested for the
portfolio while preserving the scientific semantics of the project.

## Build

From the repository root on Windows:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 3.6\blender.exe' -b --python blender\build_fpv_globe.py
```

Outputs:

- `blender/output/fpv_earth_observatory.blend` — editable master scene;
- `docs/assets/blender/fpv_globe_scene.glb` — portable animated scene;
- `docs/assets/blender/fpv_globe_preview.png` — rendered portfolio preview;
- `blender/output/scene_manifest.json` — audit of counts and event semantics.

The scene contains separate collections for the Earth, 517 geolocated catalogue
records, country-density columns, documented event evidence and annotation.

## BlenderGIS role

BlenderGIS is the recommended bridge for adding a local georeferenced basemap,
GeoTIFF or DEM to a *site-scale inset*. Install the official add-on, enable it,
set the scene CRS to the raster CRS, and import one of the tracked GeoTIFFs under
`qgis/rasters/`. The global globe itself uses an explicit WGS84 lon/lat →
geocentric transform because a flat projected GIS scene must not be wrapped onto
a sphere without a defined transform.

The master build does not download imagery or elevation, so it remains
deterministic. BlenderGIS web basemaps are optional presentation layers and must
not be treated as measurement inputs.

## Motion semantics

- Yamakura pulses at its documented event location. It represents localized
  structural change; no rigid translation vector was resolved.
- Omkareshwar pulses as a below-detection case. This is not evidence of zero
  physical movement.
- Tengeh is the only translated marker. It replays the controlled 40 m eastward
  synthetic injection and is visually exaggerated 15,000× so it can be seen at
  globe scale.

Do not relabel these animations as observed global FPV drift.
