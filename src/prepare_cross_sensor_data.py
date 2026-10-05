from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import time
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import h5py
import numpy as np
import pandas as pd
import rasterio
import requests
from rasterio.crs import CRS
from rasterio.transform import from_origin
from rasterio.warp import transform as transform_coords


MPC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
MPC_CROP = "https://planetarycomputer.microsoft.com/api/data/v1/item/crop/420x320.tif"
GCOV_SHORT_NAME = "NISAR_L2_GCOV_PROVISIONAL_V1"
GCOV_GROUP = "/science/LSAR/GCOV/grids/frequencyA"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    # Provider inventories intentionally contain different metadata fields
    # (for example NISAR cycle/frame/mode versus Sentinel-1 satellite/orbit).
    # Preserve the union in deterministic first-seen order.
    fieldnames = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def find_masks(config: dict, input_root: Path) -> dict[str, Path]:
    found = {}
    for site, details in config["sites"].items():
        candidates = list(input_root.rglob(details["mask_filename"]))
        if not candidates:
            raise FileNotFoundError(
                f"Could not find {details['mask_filename']} under {input_root}"
            )
        if len(candidates) > 1:
            digests = {sha256(path) for path in candidates}
            if len(digests) != 1:
                raise RuntimeError(
                    f"Found {len(candidates)} non-identical copies of {details['mask_filename']}: "
                    + ", ".join(map(str, candidates))
                )
            print(
                f"Found {len(candidates)} byte-identical copies of {details['mask_filename']}; "
                f"using {sorted(candidates)[0]}",
                flush=True,
            )
        found[site] = sorted(candidates)[0]
    return found


def geometry(bbox: list[float]) -> dict:
    west, south, east, north = bbox
    return {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
        },
    }


def _mpc_search(bbox: list[float], temporal: str) -> list[dict]:
    payload = {"collections": ["sentinel-1-rtc"], "bbox": bbox, "datetime": temporal, "limit": 1000}
    response = requests.post(MPC_STAC, json=payload, timeout=120)
    response.raise_for_status()
    features = response.json()["features"]
    return [f for f in features if "vv" in f.get("assets", {})]


def _margin_score(item: dict, bbox: list[float]) -> float:
    cx = (bbox[0] + bbox[2]) / 2
    cy = (bbox[1] + bbox[3]) / 2
    west, south, east, north = item["bbox"]
    if west <= cx <= east and south <= cy <= north:
        return min(cx - west, east - cx, cy - south, north - cy)
    return -math.hypot(max(west - cx, 0, cx - east), max(south - cy, 0, cy - north))


def search_sentinel1(site: str, bbox: list[float], config: dict, site_config: dict) -> list[dict]:
    start = site_config.get("sentinel1_stable_start", config["sentinel1_date_start"])
    temporal = f"{start}T00:00:00Z/{config['date_end']}T23:59:59Z"
    raw = _mpc_search(bbox, temporal)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for item in raw:
        p = item["properties"]
        orbit = p.get("sat:relative_orbit")
        satellite = item["id"].split("_")[0]
        groups[(p["datetime"][:10], orbit, satellite)].append(item)
    records = []
    for (_, orbit, satellite), candidates in sorted(groups.items()):
        chosen = max(candidates, key=lambda item: (_margin_score(item, bbox), item["id"]))
        p = chosen["properties"]
        records.append(
            {
                "site": site,
                "sensor": "S1_C",
                "scene_id": chosen["id"],
                "date": p["datetime"][:10],
                "datetime": p["datetime"],
                "stratum": f"o{int(orbit):03d}_{p.get('sat:orbit_state','unknown')}_{satellite}",
                "relative_orbit": int(orbit),
                "orbit_state": p.get("sat:orbit_state", ""),
                "satellite": satellite,
                "polarizations": "copol;crosspol" if "vh" in chosen.get("assets", {}) else "copol",
                "item": chosen,
            }
        )
    return sorted(records, key=lambda row: (row["stratum"], row["date"]))


def download_sentinel1(records: list[dict], bbox: list[float], out: Path) -> list[dict]:
    raster_dir = out / "rasters" / "sentinel1"
    raster_dir.mkdir(parents=True, exist_ok=True)
    completed = []
    for index, record in enumerate(records, 1):
        assets = {"copol": "vv"}
        if "vh" in record["item"].get("assets", {}):
            assets["crosspol"] = "vh"
        paths = {}
        for label, asset in assets.items():
            target = raster_dir / f"{record['site']}__{record['scene_id']}__{label}.tif"
            if not target.exists() or target.stat().st_size < 10_000:
                for attempt in range(4):
                    try:
                        response = requests.post(
                            MPC_CROP,
                            params={
                                "collection": "sentinel-1-rtc",
                                "item": record["scene_id"],
                                "assets": asset,
                                "return_mask": "false",
                                "resampling": "bilinear",
                            },
                            json=geometry(bbox),
                            timeout=240,
                        )
                        response.raise_for_status()
                        if len(response.content) < 10_000:
                            raise RuntimeError("MPC returned an implausibly small raster")
                        target.write_bytes(response.content)
                        break
                    except Exception:
                        if attempt == 3:
                            raise
                        time.sleep(2 ** (attempt + 1))
            with rasterio.open(target) as ds:
                pixel_m = approximate_pixel_size_m(ds)
            paths[label] = str(target)
        clean = {k: v for k, v in record.items() if k != "item"}
        completed.append({**clean, "rasters": paths, "source_pixel_m": pixel_m})
        if index % 20 == 0 or index == len(records):
            print(f"Sentinel-1 chips {index}/{len(records)}", flush=True)
    return completed


def approximate_pixel_size_m(ds) -> float:
    if ds.crs and ds.crs.is_projected:
        return float((abs(ds.transform.a) + abs(ds.transform.e)) / 2)
    latitude = math.radians((ds.bounds.bottom + ds.bounds.top) / 2)
    east = abs(ds.transform.a) * 111_320 * math.cos(latitude)
    north = abs(ds.transform.e) * 110_574
    return float((east + north) / 2)


def _native_id(result: Any) -> str:
    meta = result.get("meta", {})
    umm = result.get("umm", {})
    return meta.get("native-id") or umm.get("GranuleUR") or str(result)


def parse_nisar_id(scene_id: str) -> dict:
    name = Path(scene_id).stem
    tokens = name.split("_")
    try:
        gcov = tokens.index("GCOV")
        cycle, relative_orbit, direction, frame, mode, pole = tokens[gcov + 1:gcov + 7]
        start = next(token for token in tokens[gcov + 7:] if re.fullmatch(r"20\d{6}T\d{6}", token))
    except (ValueError, StopIteration):
        raise ValueError(f"Unrecognized NISAR GCOV filename: {scene_id}")
    return {
        "cycle": cycle,
        "relative_orbit": relative_orbit,
        "orbit_state": "ascending" if direction == "A" else "descending",
        "frame": frame,
        "mode": mode,
        "pole": pole,
        "date": f"{start[:4]}-{start[4:6]}-{start[6:8]}",
        "datetime": start,
        "stratum": f"r{relative_orbit}_{direction}_f{frame}_{mode}_{pole}",
    }


def search_nisar(site: str, bbox: list[float], config: dict) -> list[dict]:
    import earthaccess

    results = earthaccess.search_data(
        short_name=GCOV_SHORT_NAME,
        bounding_box=tuple(bbox),
        temporal=(config["nisar_date_start"], config["date_end"]),
        count=-1,
    )
    records = []
    for result in results:
        scene_id = _native_id(result)
        try:
            parsed = parse_nisar_id(scene_id)
        except ValueError:
            continue
        records.append({"site": site, "sensor": "NISAR_L", "scene_id": scene_id, **parsed, "result": result})
    unique = {record["scene_id"]: record for record in records}
    return sorted(unique.values(), key=lambda row: (row["stratum"], row["date"]))


def _projection(group) -> CRS:
    projection = group["projection"]
    for key in ("epsg_code", "epsg"):
        value = projection.attrs.get(key)
        if value is not None:
            if isinstance(value, bytes):
                value = value.decode()
            digits = re.findall(r"\d+", str(value))
            if digits:
                return CRS.from_epsg(int(digits[-1]))
    for key in ("spatial_ref", "crs_wkt"):
        value = projection.attrs.get(key)
        if value is not None:
            if isinstance(value, bytes):
                value = value.decode()
            return CRS.from_wkt(str(value))
    raise RuntimeError("NISAR GCOV projection metadata was not found")


def _polarization_layers(group) -> dict[str, str]:
    keys = set(group.keys())
    if "HHHH" in keys:
        layers = {"copol": "HHHH"}
        if "HVHV" in keys:
            layers["crosspol"] = "HVHV"
        return layers
    if "VVVV" in keys:
        layers = {"copol": "VVVV"}
        if "VHVH" in keys:
            layers["crosspol"] = "VHVH"
        return layers
    return {}


def _subset_axis(values: np.ndarray, low: float, high: float) -> tuple[slice, np.ndarray]:
    indexes = np.flatnonzero((values >= min(low, high)) & (values <= max(low, high)))
    if not len(indexes):
        raise ValueError("Requested site bounds do not intersect NISAR coordinates")
    slc = slice(int(indexes.min()), int(indexes.max()) + 1)
    chosen = values[slc]
    return slc, chosen


def extract_nisar(records: list[dict], bbox: list[float], out: Path) -> list[dict]:
    import earthaccess

    raster_dir = out / "rasters" / "nisar"
    raster_dir.mkdir(parents=True, exist_ok=True)
    completed = []
    for index, record in enumerate(records, 1):
        opened = earthaccess.open([record["result"]])
        if not opened:
            raise RuntimeError(f"earthaccess.open returned no data for {record['scene_id']}")
        file_obj = opened[0]
        with h5py.File(file_obj, "r") as h5:
            if GCOV_GROUP not in h5:
                raise RuntimeError(f"Missing {GCOV_GROUP} in {record['scene_id']}")
            group = h5[GCOV_GROUP]
            layers = _polarization_layers(group)
            if not layers:
                continue
            crs = _projection(group)
            west, south, east, north = bbox
            xs_corner, ys_corner = transform_coords(
                CRS.from_epsg(4326), crs,
                [west, east, west, east], [south, south, north, north],
            )
            xs = np.asarray(group["xCoordinates"][:], dtype="float64")
            ys = np.asarray(group["yCoordinates"][:], dtype="float64")
            x_slice, x_selected = _subset_axis(xs, min(xs_corner), max(xs_corner))
            y_slice, y_selected = _subset_axis(ys, min(ys_corner), max(ys_corner))
            flip_x = bool(x_selected[0] > x_selected[-1])
            # GeoTIFF row zero must be north. Reverse only when source Y runs south-to-north.
            flip_y = bool(y_selected[0] < y_selected[-1])
            dx = float(np.median(np.abs(np.diff(x_selected))))
            dy = float(np.median(np.abs(np.diff(y_selected))))
            paths = {}
            for label, layer in layers.items():
                target = raster_dir / f"{record['site']}__{Path(record['scene_id']).stem}__{label}.tif"
                if not target.exists():
                    data = np.asarray(group[layer][y_slice, x_slice], dtype="float32")
                    if flip_y:
                        data = data[::-1, :]
                    if flip_x:
                        data = data[:, ::-1]
                    fill = group[layer].attrs.get("_FillValue")
                    if fill is not None:
                        data[data == fill] = np.nan
                    transform = from_origin(min(x_selected) - dx / 2, max(y_selected) + dy / 2, dx, dy)
                    with rasterio.open(
                        target,
                        "w",
                        driver="GTiff",
                        width=data.shape[1],
                        height=data.shape[0],
                        count=1,
                        dtype="float32",
                        crs=crs,
                        transform=transform,
                        nodata=np.nan,
                        compress="deflate",
                        predictor=3,
                    ) as dst:
                        dst.write(data, 1)
                paths[label] = str(target)
        clean = {k: v for k, v in record.items() if k != "result"}
        completed.append({**clean, "rasters": paths, "polarizations": ";".join(paths), "source_pixel_m": (dx + dy) / 2})
        if index % 5 == 0 or index == len(records):
            print(f"NISAR GCOV chips {index}/{len(records)}", flush=True)
    return completed


def nonoverlapping_pairs(records: list[dict], calibration_fraction: float) -> list[dict]:
    rows = []
    by_stratum: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_stratum[record["stratum"]].append(record)
    for stratum, members in by_stratum.items():
        members = sorted(members, key=lambda row: row["date"])
        candidates = [(members[i], members[i + 1]) for i in range(0, len(members) - 1, 2)]
        if len(candidates) < 2:
            continue
        cal_count = max(1, min(len(candidates) - 1, int(math.floor(len(candidates) * calibration_fraction))))
        for index, (pre, post) in enumerate(candidates):
            common_pols = sorted(set(pre["rasters"]) & set(post["rasters"]))
            for pol in common_pols:
                rows.append(
                    {
                        "pair_id": f"{pre['sensor']}__{pre['site']}__{stratum}__{pre['date']}__{post['date']}",
                        "site": pre["site"],
                        "sensor": pre["sensor"],
                        "stratum": stratum,
                        "polarisation": pol,
                        "split": "calibration" if index < cal_count else "test",
                        "date_pre": pre["date"],
                        "date_post": post["date"],
                        "scene_pre": pre["scene_id"],
                        "scene_post": post["scene_id"],
                        "pre_raster": pre["rasters"][pol],
                        "post_raster": post["rasters"][pol],
                        "source_pixel_m": max(float(pre["source_pixel_m"]), float(post["source_pixel_m"])),
                    }
                )
    return sorted(rows, key=lambda row: (row["sensor"], row["site"], row["stratum"], row["date_pre"], row["polarisation"]))


def inventory_rows(records: list[dict]) -> list[dict]:
    output = []
    for row in records:
        output.append({k: v for k, v in row.items() if k not in {"item", "result", "rasters"}} | {
            "raster_copol": row.get("rasters", {}).get("copol", ""),
            "raster_crosspol": row.get("rasters", {}).get("crosspol", ""),
        })
    return output


def prepare(config_path: Path, input_root: Path, output_root: Path) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    output_root.mkdir(parents=True, exist_ok=True)
    masks = find_masks(config, input_root)
    all_records, all_pairs = [], []
    for site, details in config["sites"].items():
        bbox = details["bbox"]
        print(f"\n=== {site}: Sentinel-1 inventory ===", flush=True)
        s1 = download_sentinel1(search_sentinel1(site, bbox, config, details), bbox, output_root)
        print(f"=== {site}: NISAR inventory ===", flush=True)
        nisar = extract_nisar(search_nisar(site, bbox, config), bbox, output_root)
        records = s1 + nisar
        pairs = nonoverlapping_pairs(records, float(config["calibration_fraction"]))
        for pair in pairs:
            pair["mask_raster"] = str(masks[site])
        all_records.extend(records)
        all_pairs.extend(pairs)
    write_csv(output_root / "scene_inventory.csv", inventory_rows(all_records))
    write_csv(output_root / "locked_pairs.csv", all_pairs)
    checksum_rows = []
    for path in sorted((output_root / "rasters").rglob("*.tif")):
        checksum_rows.append({"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)})
    for path in sorted(set(masks.values())):
        checksum_rows.append({"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)})
    write_csv(output_root / "input_checksums.csv", checksum_rows)
    pair_df = pd.DataFrame(all_pairs)
    audit = {
        "scenes": len(all_records),
        "channel_pair_rows": len(all_pairs),
        "unique_pairs": int(pair_df.pair_id.nunique()) if not pair_df.empty else 0,
        "calibration_pairs": int(pair_df[pair_df.split == "calibration"].pair_id.nunique()) if not pair_df.empty else 0,
        "test_pairs": int(pair_df[pair_df.split == "test"].pair_id.nunique()) if not pair_df.empty else 0,
        "cross_split_scene_overlap": sorted(
            set(pair_df[pair_df.split == "calibration"].scene_pre).union(pair_df[pair_df.split == "calibration"].scene_post)
            & set(pair_df[pair_df.split == "test"].scene_pre).union(pair_df[pair_df.split == "test"].scene_post)
        ) if not pair_df.empty else [],
    }
    (output_root / "pair_lock_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    if audit["cross_split_scene_overlap"]:
        raise RuntimeError("Calibration/test acquisition leakage detected")
    print(json.dumps(audit, indent=2))
    return audit
