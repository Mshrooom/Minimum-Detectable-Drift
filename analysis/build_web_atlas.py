"""Build browser-ready, georeferenced evidence layers from tracked rasters.

The output is a GitHub Pages supplement. Every rendered layer is generated
from a GeoTIFF already tracked in ``qgis/rasters`` or from the exact frozen
registration/injection functions used by the benchmark.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import matplotlib
import numpy as np
import rasterio
from matplotlib import colormaps
from PIL import Image
from rasterio.features import shapes


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "qgis" / "rasters"
OUTPUT = ROOT / "docs" / "assets" / "maps"
sys.path.insert(0, str(ROOT / "src"))

from cross_sensor_inference import (  # noqa: E402
    align_land,
    background_for,
    controls_from_fractions,
    ecc,
    inject,
    to_db,
    tracking_box,
)


def bounds_coordinates(bounds: rasterio.coords.BoundingBox) -> list[list[float]]:
    return [
        [bounds.left, bounds.top],
        [bounds.right, bounds.top],
        [bounds.right, bounds.bottom],
        [bounds.left, bounds.bottom],
    ]


def rgba_gray(array: np.ndarray, low: float | None = None, high: float | None = None) -> np.ndarray:
    finite = np.isfinite(array)
    if low is None or high is None:
        low, high = np.nanpercentile(array[finite], [2, 98])
    normalized = np.clip((array - low) / max(high - low, 1e-9), 0, 1)
    gray = (normalized * 255).astype("uint8")
    alpha = np.where(finite, 255, 0).astype("uint8")
    return np.dstack([gray, gray, gray, alpha])


def rgba_diverging(array: np.ndarray, limit: float | None = None) -> np.ndarray:
    finite = np.isfinite(array)
    if limit is None:
        limit = float(np.nanpercentile(np.abs(array[finite]), 98))
    normalized = np.clip((array + limit) / max(2 * limit, 1e-9), 0, 1)
    rgba = (colormaps["RdBu_r"](normalized) * 255).astype("uint8")
    rgba[..., 3] = np.where(finite, 255, 0).astype("uint8")
    return rgba


def save_png(name: str, rgba: np.ndarray) -> str:
    path = OUTPUT / name
    Image.fromarray(rgba, mode="RGBA").save(path, optimize=True)
    return f"assets/maps/{name}"


def mask_features(path: Path, site: str, properties: dict | None = None) -> list[dict]:
    with rasterio.open(path) as dataset:
        mask = dataset.read(1) > 0
        features = []
        for geometry, value in shapes(mask.astype("uint8"), mask=mask, transform=dataset.transform):
            if value != 1:
                continue
            props = {"site": site, "kind": "footprint"}
            props.update(properties or {})
            features.append({"type": "Feature", "properties": props, "geometry": geometry})
    return features


def pixel_box_feature(transform, box: tuple[int, int, int, int], label: str) -> dict:
    x1, y1, x2, y2 = box
    west, north = transform * (x1, y1)
    east, south = transform * (x2, y2)
    return {
        "type": "Feature",
        "properties": {"name": label, "kind": "control"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[west, north], [east, north], [east, south], [west, south], [west, north]]],
        },
    }


def point_from_pixel(transform, col: float, row: float) -> list[float]:
    x, y = transform * (col + 0.5, row + 0.5)
    return [float(x), float(y)]


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    config = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))

    # Tengeh: real Sentinel-1 pair plus exact frozen registration/injection stages.
    with rasterio.open(SOURCE / "o171_s1a_20220108t112532_vv.tif") as ds:
        tengeh_pre = to_db(ds.read(1))
        tengeh_transform, tengeh_bounds = ds.transform, ds.bounds
    with rasterio.open(SOURCE / "o171_s1a_20220120t112532_vv.tif") as ds:
        tengeh_post = to_db(ds.read(1))
    with rasterio.open(SOURCE / "tengeh_fpv_mask.tif") as ds:
        tengeh_mask = (ds.read(1) > 0).astype("uint8")

    controls = controls_from_fractions(tengeh_mask.shape, config["stable_control_fractional_boxes"])
    aligned, land_dx, land_dy, land_ok = align_land(tengeh_pre, tengeh_post, controls)
    if not land_ok:
        raise RuntimeError("Stable-land registration failed for atlas pair")
    background = background_for(aligned, tengeh_mask, int(round(config["inpaint_radius_m"] / 10)))
    injected = inject(aligned, background, tengeh_mask, 4.0, 0.0)
    box = tracking_box(tengeh_mask, int(round(config["tracking_padding_m"] / 10)))
    dx, dy, coefficient, accepted = ecc(
        tengeh_pre,
        injected,
        tengeh_mask,
        box,
        int(round(config["tracking_mask_expansion_m"] / 10)),
        config["minimum_ecc_coefficient"],
        config["maximum_shift_m"] / 10,
    )
    joint_low, joint_high = np.nanpercentile(np.concatenate([tengeh_pre.ravel(), aligned.ravel()]), [2, 98])
    tengeh_layers = [
        {"id": "pre", "label": "Reference · 08 Jan 2022", "url": save_png("tengeh_s1_vv_20220108.png", rgba_gray(tengeh_pre, joint_low, joint_high)), "kind": "SAR amplitude · dB"},
        {"id": "post", "label": "Comparison · 20 Jan 2022", "url": save_png("tengeh_s1_vv_20220120.png", rgba_gray(tengeh_post, joint_low, joint_high)), "kind": "SAR amplitude · dB"},
        {"id": "aligned", "label": "Land-registered comparison", "url": save_png("tengeh_s1_vv_aligned.png", rgba_gray(aligned, joint_low, joint_high)), "kind": "registered SAR amplitude · dB"},
        {"id": "difference", "label": "Registered change", "url": save_png("tengeh_s1_vv_difference.png", rgba_diverging(aligned - tengeh_pre)), "kind": "post − pre · dB"},
        {"id": "inpainted", "label": "Original footprint inpainted", "url": save_png("tengeh_s1_vv_inpainted.png", rgba_gray(background, joint_low, joint_high)), "kind": "inpainting stage · dB"},
        {"id": "injected", "label": "40 m east injection", "url": save_png("tengeh_s1_vv_injected_40m_east.png", rgba_gray(injected, joint_low, joint_high)), "kind": "controlled ground truth · dB"},
    ]
    ys, xs = np.where(tengeh_mask > 0)
    cx, cy = float(xs.mean()), float(ys.mean())
    origin = point_from_pixel(tengeh_transform, cx, cy)
    vectors = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"name": "Injected vector", "kind": "injected", "magnitude_m": 40.0}, "geometry": {"type": "LineString", "coordinates": [origin, point_from_pixel(tengeh_transform, cx + 4.0, cy)]}},
            {"type": "Feature", "properties": {"name": "Recovered vector", "kind": "recovered", "magnitude_m": round(float(np.hypot(dx, dy) * 10), 3)}, "geometry": {"type": "LineString", "coordinates": [origin, point_from_pixel(tengeh_transform, cx + dx, cy + dy)]}},
        ],
    }
    tengeh_overlays = {
        "type": "FeatureCollection",
        "features": mask_features(SOURCE / "tengeh_fpv_mask.tif", "Tengeh")
        + [pixel_box_feature(tengeh_transform, c, f"Stable-land control {i + 1}") for i, c in enumerate(controls)],
    }

    # Yamakura: actual event-bracketing pair and stored damage/control ROIs.
    y_layers = []
    for filename, identifier, label, kind, diverging in [
        ("orbit_39_2019-09-06_vv_pre_db.tif", "pre", "Pre-event · 06 Sep 2019", "Sentinel-1 VV · dB", False),
        ("orbit_39_2019-09-18_vv_post_db.tif", "post", "Post-event · 18 Sep 2019", "Sentinel-1 VV · dB", False),
        ("orbit_39_vv_event_difference_db.tif", "difference", "Event difference", "post − pre · dB", True),
    ]:
        with rasterio.open(SOURCE / filename) as ds:
            array = ds.read(1)
            y_bounds = ds.bounds
            rendered = rgba_diverging(array) if diverging else rgba_gray(array, -20, 3)
            y_layers.append({"id": identifier, "label": label, "url": save_png(filename.replace(".tif", ".png"), rendered), "kind": kind})
    y_rois = json.loads((ROOT.parent / "outputs" / "qgis_yamakura_pilot" / "yamakura_analysis_rois.geojson").read_text(encoding="utf-8"))
    for feature in y_rois["features"]:
        feature["properties"]["kind"] = "control" if feature["properties"].get("role") == "control" else "target"

    # Omkareshwar: public NISAR Worldview screen, explicitly not the GCOV inference input.
    with rasterio.open(SOURCE / "nisar_track084_2026-07-02_rgb.tif") as ds:
        rgb = np.transpose(ds.read([1, 2, 3]), (1, 2, 0))
        alpha = ds.read(4) if ds.count >= 4 else np.full(rgb.shape[:2], 255, dtype="uint8")
        nisar_rgba = np.dstack([rgb, alpha]).astype("uint8")
        nisar_bounds = ds.bounds
    nisar_url = save_png("omkareshwar_nisar_worldview_20260702.png", nisar_rgba)
    nisar_rois = json.loads((ROOT.parent / "outputs" / "qgis_nisar_omkareshwar_motion" / "nisar_omkareshwar_rois.geojson").read_text(encoding="utf-8"))
    for feature in nisar_rois["features"]:
        feature["properties"]["kind"] = "target" if feature["properties"].get("roi") == "fpv_cluster" else "control"

    md = {
        "Piolenc": {"center": [4.728, 44.1555], "L": [11, 17, 25], "C": [19, 26, 32], "L_pairs": 6, "C_pairs": 129},
        "Sirindhorn": {"center": [105.444, 15.198], "L": [15, 21, 24], "C": [16, 21, 30], "L_pairs": 3, "C_pairs": 92},
        "Tengeh": {"center": [103.643, 1.35], "L": [12, 18, 25], "C": [12, 17, 21], "L_pairs": 6, "C_pairs": 49},
    }
    site_features = []
    for site, values in md.items():
        site_features.append({
            "type": "Feature",
            "properties": {"site": site, **{k: v for k, v in values.items() if k != "center"}},
            "geometry": {"type": "Point", "coordinates": values["center"]},
        })

    data = {
        "version": "0.3.0",
        "overview": {"sites": {"type": "FeatureCollection", "features": site_features}},
        "scenes": {
            "tengeh": {
                "title": "Tengeh controlled injection",
                "subtitle": "Real Sentinel-1 pair · orbit 171 · VV · frozen algorithm",
                "bounds": bounds_coordinates(tengeh_bounds),
                "layers": tengeh_layers,
                "overlays": tengeh_overlays,
                "vectors": vectors,
                "metrics": {"land_bias_px": [round(float(land_dx), 4), round(float(land_dy), 4)], "injected_m": 40.0, "recovered_east_m": round(float(dx * 10), 3), "recovered_south_m": round(float(dy * 10), 3), "ecc": round(float(coefficient), 4), "accepted": bool(accepted)},
                "interpretation": "The map exposes each transformation stage. Recovery is accepted but underestimates the known 40 m translation, illustrating why probability curves—not a single attractive vector—define observability.",
            },
            "yamakura": {
                "title": "Yamakura event localization",
                "subtitle": "Typhoon Faxai bracket · relative orbit 39 · VV",
                "bounds": bounds_coordinates(y_bounds),
                "layers": y_layers,
                "overlays": y_rois,
                "metrics": {"damage_sector_channels": "6/6", "whole_array_translation_channels": "0/6", "pre": "2019-09-06", "post": "2019-09-18"},
                "interpretation": "Backscatter change repeatedly localized to the documented damage sector, while the rigid whole-array displacement test remained below threshold. This separates structural-change evidence from translation evidence.",
            },
            "omkareshwar": {
                "title": "Omkareshwar NISAR feasibility screen",
                "subtitle": "Public Worldview rendering · track 084 · 02 Jul 2026",
                "bounds": bounds_coordinates(nisar_bounds),
                "layers": [{"id": "rgb", "label": "NISAR Worldview RGB", "url": nisar_url, "kind": "rendered visualization · not calibrated GCOV"}],
                "overlays": nisar_rois,
                "metrics": {"dates_screened": 8, "temporal_pairs": 7, "maximum_apparent_shift_m": 3.39, "screen_threshold_m": 3.55},
                "interpretation": "This layer documents target visibility and ROI design only. It is excluded from the calibrated L/C sensitivity benchmark because rendered Worldview pixels are not native Level-2 GCOV measurements.",
            },
        },
    }
    js = "window.ATLAS_DATA = " + json.dumps(data, separators=(",", ":"), ensure_ascii=False) + ";\n"
    (ROOT / "docs" / "assets" / "atlas-data.js").write_text(js, encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "layers": sum(len(s["layers"]) for s in data["scenes"].values()), "tengeh_metrics": data["scenes"]["tengeh"]["metrics"]}, indent=2))


if __name__ == "__main__":
    main()
