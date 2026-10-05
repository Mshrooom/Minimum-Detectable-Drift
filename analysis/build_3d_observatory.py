"""Build the compact data bundle for the 3D global FPV observatory."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import rasterio
from rasterio.features import shapes


ROOT = Path(__file__).resolve().parents[1]
GLOBAL = ROOT / "data" / "external" / "global_fpv_inventory_2023.csv"
OUTPUT = ROOT / "docs" / "assets" / "earth-data.js"


def clean(value):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def mask_features(site: str) -> list[dict]:
    path = ROOT / "qgis" / "rasters" / f"{site.lower()}_fpv_mask.tif"
    with rasterio.open(path) as dataset:
        mask = dataset.read(1) > 0
        output = []
        for geometry, value in shapes(mask.astype("uint8"), mask=mask, transform=dataset.transform):
            if value == 1:
                output.append({
                    "type": "Feature",
                    "properties": {"site": site, "kind": "calibrated_footprint"},
                    "geometry": geometry,
                })
        return output


def global_inventory() -> tuple[dict, list[dict], dict, list[dict]]:
    frame = pd.read_csv(GLOBAL)
    mapped = frame.dropna(subset=["latitude", "longitude"]).copy()
    features = []
    registry = []
    for row in frame.itertuples(index=False):
        year = None
        if isinstance(row.year, str) and row.year[:4].isdigit():
            year = int(row.year[:4])
        registry.append({
            "id": row.inventory_id,
            "source_code": int(row.source_code),
            "country": row.country,
            "continent": row.continent,
            "year": year,
            "year_label": clean(row.year),
            "capacity_kwp": clean(row.capacity_kwp),
            "fpv_area_m2": clean(row.fpv_area_m2),
            "coverage_pct": clean(row.fpv_coverage_pct),
            "latitude": clean(row.latitude),
            "longitude": clean(row.longitude),
            "mappable": bool(pd.notna(row.latitude) and pd.notna(row.longitude)),
            "hemisphere_inferred": bool(row.coordinate_hemisphere_inferred),
        })
    for row in mapped.itertuples(index=False):
        year = None
        if isinstance(row.year, str) and row.year[:4].isdigit():
            year = int(row.year[:4])
        features.append({
            "type": "Feature",
            "properties": {
                "id": row.inventory_id,
                "source_code": int(row.source_code),
                "country": row.country,
                "continent": row.continent,
                "year": year,
                "year_label": row.year,
                "capacity_kwp": clean(row.capacity_kwp),
                "fpv_area_m2": clean(row.fpv_area_m2),
                "coverage_pct": clean(row.fpv_coverage_pct),
                "hemisphere_inferred": bool(row.coordinate_hemisphere_inferred),
            },
            "geometry": {"type": "Point", "coordinates": [float(row.longitude), float(row.latitude)]},
        })
    countries = []
    for country, group in frame.groupby("country", sort=True):
        mapped_count = int(group.latitude.notna().sum())
        capacity = group.capacity_kwp.sum(min_count=1)
        countries.append({
            "country": country,
            "catalogued": int(len(group)),
            "mappable": mapped_count,
            "capacity_kwp_known_sum": clean(capacity),
        })
    audit = json.loads((ROOT / "data" / "external" / "global_fpv_inventory_2023_audit.json").read_text(encoding="utf-8"))
    year_counts: dict[str, int] = {}
    for value in frame.year.fillna("NA").astype(str):
        key = value[:4] if value[:4].isdigit() else "unknown"
        year_counts[key] = year_counts.get(key, 0) + 1
    audit["year_counts"] = year_counts
    return {"type": "FeatureCollection", "features": features}, countries, audit, registry


def benchmark_sites() -> tuple[list[dict], dict]:
    frame = pd.read_csv(ROOT / "data" / "derived" / "site_md_summary.csv")
    sites: list[dict] = []
    footprints: list[dict] = []
    for site, group in frame.groupby("site", sort=True):
        first = group.iloc[0]
        sensor_data = {}
        for row in group.itertuples(index=False):
            key = "L" if row.band == "L" else "C"
            sensor_data[key] = {
                "sensor": row.sensor,
                "calibration_pairs": int(row.calibration_pairs),
                "test_pairs": int(row.test_pairs),
                "copol": [int(row.md50_copol_m), int(row.md80_copol_m), int(row.md95_copol_m)],
                "dual": [int(row.md50_dual_m), int(row.md80_dual_m), int(row.md95_dual_m)],
            }
        sites.append({
            "site": site,
            "country": first.country,
            "latitude": float(first.latitude),
            "longitude": float(first.longitude),
            "sensors": sensor_data,
        })
        footprints.extend(mask_features(site))
    return sites, {"type": "FeatureCollection", "features": footprints}


def pooled_curves() -> dict:
    frame = pd.read_csv(ROOT / "data" / "derived" / "detection_curves.csv")
    frame = frame[frame.regime.eq("harmonized_20m")]
    output: dict[str, dict[str, list[dict]]] = {}
    for (sensor, detector), group in frame.groupby(["sensor", "detector"], sort=True):
        key = "L" if sensor == "NISAR_L" else "C"
        output.setdefault(key, {})[detector] = [
            {
                "m": int(row.magnitude_m),
                "p": round(float(row.isotonic_probability), 4),
                "lo": round(float(row.ci95_lower), 4),
                "hi": round(float(row.ci95_upper), 4),
            }
            for row in group.itertuples(index=False)
        ]
    return output


def main() -> None:
    inventory, countries, audit, registry = global_inventory()
    sites, footprints = benchmark_sites()
    atlas_text = (ROOT / "docs" / "assets" / "atlas-data.js").read_text(encoding="utf-8")
    atlas = json.loads(atlas_text.split("=", 1)[1].strip().rstrip(";"))
    data = {
        "version": "0.5.0",
        "inventory": inventory,
        "registry": registry,
        "countries": countries,
        "audit": audit,
        "benchmark_sites": sites,
        "benchmark_footprints": footprints,
        "pooled_curves": pooled_curves(),
        "evidence_sites": [
            {
                "site": "Yamakura", "country": "Japan", "longitude": 140.134,
                "latitude": 35.4915, "role": "documented event",
                "event_name": "Typhoon Faxai", "event_date": "2019-09-09",
                "pre_date": "2019-09-06", "post_date": "2019-09-18",
                "classification": "localized structural change",
                "translation_status": "unresolved (0/6 channels)",
                "detail": "The documented damage sector exceeded matched quiet-pair limits in 6/6 channels; rigid whole-array translation remained unresolved.",
                "pre_image": "assets/maps/orbit_39_2019-09-06_vv_pre_db.png",
                "post_image": "assets/maps/orbit_39_2019-09-18_vv_post_db.png",
                "change_image": "assets/maps/orbit_39_vv_event_difference_db.png",
            },
            {
                "site": "Omkareshwar", "country": "India", "longitude": 76.210,
                "latitude": 22.2145, "role": "formative null",
                "event_name": "April 2024 storm window", "event_date": None,
                "pre_date": "2024-04-08", "post_date": "2024-04-20",
                "classification": "below detection",
                "translation_status": "unresolved",
                "detail": "Storm-spanning apparent vectors remained below their empirical non-event thresholds; this is not evidence of zero physical motion.",
                "change_image": "assets/research/omkareshwar_null_result.png",
            },
        ],
        "validated_replay": {
            "site": "Tengeh",
            "sensor": "Sentinel-1 C",
            "date_pre": "2022-01-08",
            "date_post": "2022-01-20",
            "injected_east_m": 40.0,
            "injected_north_m": 0.0,
            "recovered_east_m": atlas["scenes"]["tengeh"]["metrics"]["recovered_east_m"],
            "recovered_north_m": -atlas["scenes"]["tengeh"]["metrics"]["recovered_south_m"],
            "ecc": atlas["scenes"]["tengeh"]["metrics"]["ecc"],
            "accepted": atlas["scenes"]["tengeh"]["metrics"]["accepted"],
        },
        "claim_boundary": {
            "catalogue": "643 installations surveyed through April 2023; not a live or exhaustive 2026 census.",
            "motion": "Only controlled synthetic translation is animated. No global installation is labelled as physically moving.",
            "vertical": "Footprint extrusion is a visual selection device, not physical array height.",
            "eo": "Live EO means a current catalogue lookup for the nearest Sentinel-2 acquisition, not continuous real-time imaging.",
        },
    }
    OUTPUT.write_text("window.EARTH_DATA = " + json.dumps(data, separators=(",", ":"), ensure_ascii=False) + ";\n", encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT),
        "catalogued": audit["source_rows"],
        "mappable": len(inventory["features"]),
        "benchmark_sites": len(sites),
        "footprint_parts": len(footprints["features"]),
    }, indent=2))


if __name__ == "__main__":
    main()
