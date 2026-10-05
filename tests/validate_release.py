"""Fast integrity checks for the compact GitHub release."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    md = pd.read_csv(ROOT / "data/derived/md_boundaries.csv")
    sites = pd.read_csv(ROOT / "data/derived/site_md_summary.csv")
    audit = json.loads((ROOT / "data/derived/summary.json").read_text(encoding="utf-8"))
    preparation = json.loads(
        (ROOT / "data/derived/preparation_audit.json").read_text(encoding="utf-8")
    )

    assert len(md) == 8
    assert len(sites) == 6
    assert set(sites["band"]) == {"L", "C"}
    assert set(sites["site"]) == {"Piolenc", "Sirindhorn", "Tengeh"}
    assert not sites.duplicated(["site", "sensor"]).any()
    assert (sites.filter(regex=r"^md(50|80|95)_").apply(pd.to_numeric) > 0).all().all()

    primary = md.loc[md["regime"].eq("harmonized_20m")].set_index(["sensor", "detector"])
    assert int(primary.loc[("NISAR_L", "copol"), "MD95_m"]) == 25
    assert int(primary.loc[("S1_C", "copol"), "MD95_m"]) == 30
    assert int(primary.loc[("NISAR_L", "dualpol_consensus"), "MD95_m"]) == 27
    assert int(primary.loc[("S1_C", "dualpol_consensus"), "MD95_m"]) == 36

    assert preparation == {
        "scenes": 1377,
        "channel_pair_rows": 1356,
        "unique_pairs": 678,
        "calibration_pairs": 393,
        "test_pairs": 285,
        "cross_split_scene_overlap": [],
    }
    assert audit["self_test"]["status"] == "PASS"
    assert audit["channel_trials"] == 538560
    assert audit["consensus_trials"] == 269280

    notebook = json.loads(
        (ROOT / "notebooks/cross_sensor_observability_kaggle.ipynb").read_text(encoding="utf-8")
    )
    assert notebook["nbformat"] == 4

    required_research_files = [
        "GLOBAL_INVENTORY.md",
        "RESEARCH_REPORT.md",
        "QGIS_WORKFLOW.md",
        "REFERENCES.md",
        "docs/index.html",
        "docs/paper.html",
        "docs/atlas.html",
        "docs/assets/atlas.js",
        "docs/assets/atlas-data.js",
        "docs/assets/atlas.css",
        "docs/assets/earth.js",
        "docs/assets/earth-data.js",
        "docs/assets/earth.css",
        "docs/assets/blender/fpv_globe_preview.png",
        "docs/assets/blender/fpv_globe_scene.glb",
        "docs/assets/world-countries.geojson",
        "docs/vendor/maplibre-gl/maplibre-gl.js",
        "docs/vendor/maplibre-gl/maplibre-gl.css",
        "data/external/global_fpv_inventory_2023.csv",
        "data/external/global_fpv_inventory_2023_audit.json",
        "docs/assets/maps/tengeh_s1_vv_injected_40m_east.png",
        "docs/assets/maps/orbit_39_vv_event_difference_db.png",
        "docs/assets/maps/omkareshwar_nisar_worldview_20260702.png",
        "docs/assets/research/cross_sensor_copol_20m.png",
        "docs/assets/research/cross_sensor_dual_20m.png",
        "docs/assets/research/injection_pipeline_real_raster.png",
        "docs/assets/research/qgis_raster_calculator.png",
        "qgis/projects/omkareshwar_sentinel1_pilot.qgz",
        "qgis/projects/yamakura_positive_event_pilot.qgz",
        "qgis/rasters/tengeh_fpv_mask.tif",
        "blender/build_fpv_globe.py",
        "blender/output/fpv_earth_observatory.blend",
        "blender/output/scene_manifest.json",
    ]
    for relative_path in required_research_files:
        path = ROOT / relative_path
        assert path.is_file() and path.stat().st_size > 0, relative_path

    site_html = (ROOT / "docs/paper.html").read_text(encoding="utf-8")
    assert "807,840" in site_html
    assert "MD95" in site_html
    assert "not established" in site_html.lower()
    earth_html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
    assert "FPV Earth" in earth_html
    assert "earth-data.js" in earth_html
    assert "LIVE EO LOOKUP" in earth_html
    assert "Animate evidence" in earth_html
    assert "fpv_globe_preview.png" in earth_html
    assert "vendor/maplibre-gl/maplibre-gl.js" in earth_html
    scene_manifest = json.loads(
        (ROOT / "blender/output/scene_manifest.json").read_text(encoding="utf-8")
    )
    assert scene_manifest["geolocated_rendered"] == 517
    assert "synthetic" in scene_manifest["event_semantics"]["Tengeh"]
    inventory = pd.read_csv(ROOT / "data/external/global_fpv_inventory_2023.csv")
    inventory_audit = json.loads(
        (ROOT / "data/external/global_fpv_inventory_2023_audit.json").read_text(encoding="utf-8")
    )
    assert len(inventory) == 643
    assert int(inventory[["latitude", "longitude"]].notna().all(axis=1).sum()) == 517
    assert inventory_audit["countries"] == 28
    assert inventory_audit["coordinate_missing_rows"] == 126
    atlas_html = (ROOT / "docs/atlas.html").read_text(encoding="utf-8")
    assert "Cross-Sensor SAR Observability" in atlas_html
    assert "atlas-data.js" in atlas_html
    atlas_data = (ROOT / "docs/assets/atlas-data.js").read_text(encoding="utf-8")
    assert "tengeh_s1_vv_injected_40m_east.png" in atlas_data
    assert '"recovered_east_m":30.122' in atlas_data
    print("Release integrity: PASS")


if __name__ == "__main__":
    main()
