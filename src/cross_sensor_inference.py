from __future__ import annotations

import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject, transform as transform_coords


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    # Result tables can combine sensors, channels, strata, and aggregate rows
    # whose metadata fields differ. Preserve every field instead of assuming
    # that the first row defines the complete schema.
    fieldnames = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader(); writer.writerows(rows)


def pava(values: list[float], weights: list[float]) -> np.ndarray:
    blocks = [[float(v), float(w), i, i] for i, (v, w) in enumerate(zip(values, weights))]
    i = 0
    while i < len(blocks) - 1:
        if blocks[i][0] <= blocks[i + 1][0]:
            i += 1; continue
        weight = blocks[i][1] + blocks[i + 1][1]
        mean = (blocks[i][0] * blocks[i][1] + blocks[i + 1][0] * blocks[i + 1][1]) / weight
        blocks[i:i + 2] = [[mean, weight, blocks[i][2], blocks[i + 1][3]]]
        i = max(0, i - 1)
    result = np.zeros(len(values), dtype="float64")
    for value, _, start, end in blocks:
        result[start:end + 1] = value
    return result


def md_from_curve(magnitudes: list[int], fitted: np.ndarray, level: float):
    candidates = [m for m, p in zip(magnitudes, fitted) if p >= level]
    return int(candidates[0]) if candidates else None


def grid_for_bbox(bbox: list[float], resolution: float):
    lon = (bbox[0] + bbox[2]) / 2
    lat = (bbox[1] + bbox[3]) / 2
    zone = int((lon + 180) // 6) + 1
    epsg = 32600 + zone if lat >= 0 else 32700 + zone
    crs = CRS.from_epsg(epsg)
    xs, ys = transform_coords(
        CRS.from_epsg(4326), crs,
        [bbox[0], bbox[2], bbox[0], bbox[2]],
        [bbox[1], bbox[1], bbox[3], bbox[3]],
    )
    west = math.floor(min(xs) / resolution) * resolution
    east = math.ceil(max(xs) / resolution) * resolution
    south = math.floor(min(ys) / resolution) * resolution
    north = math.ceil(max(ys) / resolution) * resolution
    width = int(round((east - west) / resolution))
    height = int(round((north - south) / resolution))
    return crs, from_origin(west, north, resolution, resolution), width, height


def warp_raster(path: str, grid, is_mask: bool = False) -> np.ndarray:
    crs, transform, width, height = grid
    fill = 0 if is_mask else np.nan
    destination = np.full((height, width), fill, dtype="uint8" if is_mask else "float32")
    with rasterio.open(path) as source:
        reproject(
            source.read(1), destination,
            src_transform=source.transform, src_crs=source.crs,
            dst_transform=transform, dst_crs=crs,
            src_nodata=source.nodata, dst_nodata=fill,
            resampling=Resampling.nearest if is_mask else Resampling.bilinear,
        )
    if is_mask:
        return (destination > 0).astype("uint8")
    finite = np.isfinite(destination)
    if finite.sum() < destination.size * 0.5:
        raise ValueError(f"Less than half of the target chip is valid: {path}")
    replacement = float(np.nanmedian(destination))
    destination[~finite] = replacement
    return destination


def to_db(array: np.ndarray) -> np.ndarray:
    return np.clip(10 * np.log10(np.clip(array.astype("float32"), 1e-7, None)), -40, 10)


def highpass(array: np.ndarray) -> np.ndarray:
    first = cv2.GaussianBlur(array, (0, 0), 1)
    return (first - cv2.GaussianBlur(first, (0, 0), 5)).astype("float32")


def controls_from_fractions(shape, fractions):
    height, width = shape
    return [[int(a * width), int(b * height), int(c * width), int(d * height)] for a, b, c, d in fractions]


def phase_shift(first, second, box):
    x1, y1, x2, y2 = box
    a, b = highpass(first[y1:y2, x1:x2]), highpass(second[y1:y2, x1:x2])
    if min(a.shape) < 8 or float(np.std(a)) < 0.03 or float(np.std(b)) < 0.03:
        return None
    window = cv2.createHanningWindow((a.shape[1], a.shape[0]), cv2.CV_32F)
    forward, response_f = cv2.phaseCorrelate(a, b, window)
    reverse, response_r = cv2.phaseCorrelate(b, a, window)
    return (float((forward[0] - reverse[0]) / 2), float((forward[1] - reverse[1]) / 2), float((response_f + response_r) / 2))


def align_land(first, second, boxes):
    estimates = [value for value in (phase_shift(first, second, box) for box in boxes) if value and value[2] >= 0.05]
    if len(estimates) < 2:
        return second, float("nan"), float("nan"), False
    dx, dy = np.median(np.asarray(estimates)[:, :2], axis=0)
    matrix = np.float32([[1, 0, -dx], [0, 1, -dy]])
    aligned = cv2.warpAffine(second, matrix, (second.shape[1], second.shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return aligned, float(dx), float(dy), True


def tracking_box(mask, padding_px):
    ys, xs = np.where(mask > 0)
    if not len(xs):
        raise ValueError("Reprojected FPV mask is empty")
    return [max(0, xs.min() - padding_px), max(0, ys.min() - padding_px), min(mask.shape[1], xs.max() + padding_px + 1), min(mask.shape[0], ys.max() + padding_px + 1)]


def background_for(array, mask, radius_px):
    return cv2.inpaint(array.astype("float32"), (mask * 255).astype("uint8"), max(1, radius_px), cv2.INPAINT_TELEA)


def inject(array, background, mask, dx, dy):
    matrix = np.float32([[1, 0, dx], [0, 1, dy]])
    shifted_mask = cv2.warpAffine(mask.astype("float32"), matrix, (array.shape[1], array.shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    shifted_values = cv2.warpAffine((array * mask).astype("float32"), matrix, (array.shape[1], array.shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    return background * (1 - shifted_mask) + shifted_values


def ecc(reference, comparison, mask, box, expansion_px, min_coefficient, max_shift_px):
    x1, y1, x2, y2 = box
    template = highpass(reference[y1:y2, x1:x2])
    moving = highpass(comparison[y1:y2, x1:x2])
    expanded = cv2.dilate(mask, np.ones((2 * expansion_px + 1, 2 * expansion_px + 1), "uint8"), iterations=1)
    ecc_mask = (expanded[y1:y2, x1:x2] * 255).astype("uint8")
    warp = np.eye(2, 3, dtype="float32")
    try:
        coefficient, warp = cv2.findTransformECC(template, moving, warp, cv2.MOTION_TRANSLATION, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 150, 1e-6), ecc_mask, 5)
    except cv2.error:
        return float("nan"), float("nan"), float("nan"), False
    dx, dy = float(warp[0, 2]), float(warp[1, 2])
    accepted = bool(np.isfinite(dx) and np.isfinite(dy) and coefficient >= min_coefficient and abs(dx) <= max_shift_px and abs(dy) <= max_shift_px)
    return dx, dy, float(coefficient), accepted


def angle_error(east, south, true_east, true_south):
    return abs((math.degrees(math.atan2(south, east)) - math.degrees(math.atan2(true_south, true_east)) + 180) % 360 - 180)


def angle_between(e1, s1, e2, s2):
    return abs((math.degrees(math.atan2(s1, e1)) - math.degrees(math.atan2(s2, e2)) + 180) % 360 - 180)


def build_thresholds(shams: list[dict], config: dict):
    accepted = [row for row in shams if row["accepted"]]
    site_groups, pool_groups = defaultdict(list), defaultdict(list)
    for row in accepted:
        site_groups[(row["sensor"], row["site"], row["regime"], row["polarisation"])].append(row["magnitude_m"])
        pool_groups[(row["sensor"], row["regime"], row["polarisation"])].append(row["magnitude_m"])
    thresholds, rows = {}, []
    minimum = int(config["minimum_site_calibration_pairs"])
    for row in shams:
        key = (row["sensor"], row["site"], row["regime"], row["polarisation"])
        if key in thresholds:
            continue
        local = site_groups[key]
        if len(local) >= minimum:
            values, source = local, "site_specific"
        else:
            values, source = pool_groups[(row["sensor"], row["regime"], row["polarisation"])], "sensor_pooled_fallback"
        threshold = float(np.quantile(values, config["threshold_quantile"], method="higher")) if len(values) >= minimum else float("nan")
        thresholds[key] = threshold
        rows.append({"sensor": key[0], "site": key[1], "regime": key[2], "polarisation": key[3], "accepted_calibration_pairs": len(local), "threshold_source": source, "threshold_m": threshold})
    return thresholds, rows


def prepare_pairs(pair_df, config, grids, cache):
    prepared, shams = [], []
    for regime, spec in config["analysis_regimes"].items():
        eligible = pair_df[pair_df.source_pixel_m <= float(spec["maximum_source_pixel_m"])].copy()
        resolution = float(spec["target_resolution_m"])
        for count, row in enumerate(eligible.itertuples(index=False), 1):
            grid = grids[(row.site, regime)]
            mask_key = (row.mask_raster, row.site, regime, "mask")
            if mask_key not in cache:
                cache[mask_key] = warp_raster(row.mask_raster, grid, True)
            mask = cache[mask_key]
            arrays = []
            for path in (row.pre_raster, row.post_raster):
                key = (path, row.site, regime, "image")
                if key not in cache:
                    cache[key] = to_db(warp_raster(path, grid, False))
                arrays.append(cache[key])
            boxes = controls_from_fractions(mask.shape, config["stable_control_fractional_boxes"])
            aligned, land_dx, land_dy, land_ok = align_land(arrays[0], arrays[1], boxes)
            box = tracking_box(mask, int(round(config["tracking_padding_m"] / resolution)))
            background = background_for(aligned, mask, int(round(config["inpaint_radius_m"] / resolution))) if land_ok else aligned
            sham = inject(aligned, background, mask, 0, 0) if land_ok else aligned
            dx, dy, coefficient, accepted = ecc(arrays[0], sham, mask, box, int(round(config["tracking_mask_expansion_m"] / resolution)), config["minimum_ecc_coefficient"], config["maximum_shift_m"] / resolution) if land_ok else (np.nan, np.nan, np.nan, False)
            east, south = dx * resolution, dy * resolution
            sham_row = {
                "pair_id": row.pair_id, "sensor": row.sensor, "site": row.site, "stratum": row.stratum,
                "polarisation": row.polarisation, "split": row.split, "regime": regime,
                "date_pre": row.date_pre, "date_post": row.date_post,
                "land_dx_px": land_dx, "land_dy_px": land_dy, "land_accepted": land_ok,
                "east_m": east if accepted else np.nan, "south_m": south if accepted else np.nan,
                "magnitude_m": math.hypot(east, south) if accepted else np.nan,
                "ecc_coefficient": coefficient, "accepted": accepted,
            }
            prepared.append({"row": row, "regime": regime, "resolution": resolution, "reference": arrays[0], "comparison": aligned, "background": background, "mask": mask, "box": box, "land_ok": land_ok})
            if row.split == "calibration":
                shams.append(sham_row)
            if count % 25 == 0 or count == len(eligible):
                print(f"Prepared {regime}: {count}/{len(eligible)} channel pairs", flush=True)
    return prepared, shams


def run_trials(prepared, thresholds, config):
    rows = []
    test = [item for item in prepared if item["row"].split == "test"]
    for pair_index, item in enumerate(test, 1):
        row, resolution = item["row"], item["resolution"]
        threshold = thresholds[(row.sensor, row.site, item["regime"], row.polarisation)]
        for magnitude in config["magnitudes_m"]:
            for direction in config["directions_deg"]:
                radians = math.radians(direction)
                true_east, true_south = magnitude * math.cos(radians), magnitude * math.sin(radians)
                synthetic = inject(item["comparison"], item["background"], item["mask"], true_east / resolution, true_south / resolution)
                dx, dy, coefficient, accepted = ecc(item["reference"], synthetic, item["mask"], item["box"], int(round(config["tracking_mask_expansion_m"] / resolution)), config["minimum_ecc_coefficient"], config["maximum_shift_m"] / resolution) if item["land_ok"] else (np.nan, np.nan, np.nan, False)
                east, south = dx * resolution, dy * resolution
                measured = math.hypot(east, south) if accepted else np.nan
                error = angle_error(east, south, true_east, true_south) if accepted and measured > 0 else np.nan
                alarm = bool(accepted and np.isfinite(threshold) and measured > threshold)
                rows.append({
                    "pair_id": row.pair_id, "sensor": row.sensor, "site": row.site, "stratum": row.stratum,
                    "regime": item["regime"], "polarisation": row.polarisation,
                    "magnitude_m": magnitude, "direction_deg": direction,
                    "true_east_m": true_east, "true_south_m": true_south,
                    "measured_east_m": east if accepted else np.nan, "measured_south_m": south if accepted else np.nan,
                    "measured_magnitude_m": measured, "angular_error_deg": error,
                    "ecc_coefficient": coefficient, "accepted": accepted, "threshold_m": threshold,
                    "alarm": alarm, "recovered": bool(alarm and error <= config["direction_tolerance_deg"]),
                })
        if pair_index % 10 == 0 or pair_index == len(test):
            print(f"Full injections: {pair_index}/{len(test)} channel pairs", flush=True)
    return rows


def consensus_trials(channels, config):
    grouped = defaultdict(dict)
    for row in channels:
        key = (row["pair_id"], row["sensor"], row["site"], row["stratum"], row["regime"], row["magnitude_m"], row["direction_deg"])
        grouped[key][row["polarisation"]] = row
    output = []
    for key, pols in grouped.items():
        if not {"copol", "crosspol"}.issubset(pols):
            continue
        co, cross = pols["copol"], pols["crosspol"]
        accepted = co["accepted"] and cross["accepted"]
        agreement = angle_between(co["measured_east_m"], co["measured_south_m"], cross["measured_east_m"], cross["measured_south_m"]) if accepted else np.nan
        east = float(np.median([co["measured_east_m"], cross["measured_east_m"]])) if accepted else np.nan
        south = float(np.median([co["measured_south_m"], cross["measured_south_m"]])) if accepted else np.nan
        error = angle_error(east, south, co["true_east_m"], co["true_south_m"]) if accepted else np.nan
        alarm = bool(co["alarm"] and cross["alarm"] and agreement <= config["polarization_agreement_deg"])
        output.append({
            "pair_id": key[0], "sensor": key[1], "site": key[2], "stratum": key[3], "regime": key[4],
            "magnitude_m": key[5], "direction_deg": key[6], "polarization_agreement_deg": agreement,
            "measured_east_m": east, "measured_south_m": south, "angular_error_deg": error,
            "accepted": accepted, "alarm": alarm, "recovered": bool(alarm and error <= config["direction_tolerance_deg"]),
        })
    return output


def detector_table(channels, consensus):
    rows = [{**row, "detector": "copol"} for row in channels if row["polarisation"] == "copol"]
    rows.extend({**row, "detector": "dualpol_consensus"} for row in consensus)
    return rows


def bootstrap_curve(group: pd.DataFrame, magnitudes, iterations, seed):
    pair_ids = sorted(group.pair_id.unique())
    pair_arrays = []
    for pair_id in pair_ids:
        part = group[group.pair_id == pair_id]
        pair_arrays.append(np.array([part[part.magnitude_m == m].recovered.mean() for m in magnitudes]))
    matrix = np.stack(pair_arrays)
    weights = [1] * len(magnitudes)
    rng = np.random.default_rng(seed)
    curves, md_values = [], {0.50: [], 0.80: [], 0.95: []}
    for _ in range(iterations):
        curve = matrix[rng.integers(0, len(matrix), len(matrix))].mean(axis=0)
        fitted = pava(curve.tolist(), weights)
        curves.append(fitted)
        for level in md_values:
            value = md_from_curve(magnitudes, fitted, level)
            md_values[level].append((max(magnitudes) + 1) if value is None else value)
    return np.asarray(curves), md_values


def curves_and_boundaries(detector_rows, config, output):
    frame = pd.DataFrame(detector_rows)
    curve_rows, boundary_rows = [], []
    magnitudes = list(map(int, config["magnitudes_m"]))
    for index, (key, group) in enumerate(frame.groupby(["sensor", "regime", "detector"]), 1):
        probabilities = [group[group.magnitude_m == m].recovered.mean() for m in magnitudes]
        totals = [len(group[group.magnitude_m == m]) for m in magnitudes]
        fitted = pava(probabilities, totals)
        boots, md_values = bootstrap_curve(group, magnitudes, int(config["bootstrap_iterations"]), int(config["bootstrap_seed"]) + index)
        for i, magnitude in enumerate(magnitudes):
            curve_rows.append({"sensor": key[0], "regime": key[1], "detector": key[2], "magnitude_m": magnitude, "trials": totals[i], "pairs": group.pair_id.nunique(), "probability": probabilities[i], "isotonic_probability": fitted[i], "ci95_lower": np.quantile(boots[:, i], 0.025), "ci95_upper": np.quantile(boots[:, i], 0.975)})
        record = {"sensor": key[0], "regime": key[1], "detector": key[2], "pairs": group.pair_id.nunique()}
        for level, label in ((0.50, "MD50"), (0.80, "MD80"), (0.95, "MD95")):
            value = md_from_curve(magnitudes, fitted, level)
            record[f"{label}_m"] = value if value is not None else "not_reached"
            record[f"{label}_ci95_lower_m"] = float(np.quantile(md_values[level], 0.025))
            upper = float(np.quantile(md_values[level], 0.975))
            record[f"{label}_ci95_upper_m"] = f">{max(magnitudes)}" if upper > max(magnitudes) else upper
        boundary_rows.append(record)
    write_csv(output / "detection_curves.csv", curve_rows)
    write_csv(output / "md_boundaries.csv", boundary_rows)
    return pd.DataFrame(curve_rows), pd.DataFrame(boundary_rows), frame


def matched_depth(frame):
    keep = []
    for (regime, detector, site), group in frame.groupby(["regime", "detector", "site"]):
        nisar = sorted(group[group.sensor == "NISAR_L"].pair_id.unique())
        s1 = sorted(group[group.sensor == "S1_C"].pair_id.unique())
        n = min(len(nisar), len(s1))
        if n:
            s1_indices = np.rint(np.linspace(0, len(s1) - 1, n)).astype(int)
            selected = set(nisar[:n]) | {s1[i] for i in s1_indices}
            keep.append(group[group.pair_id.isin(selected)])
    return pd.concat(keep, ignore_index=True) if keep else frame.iloc[0:0]


def crossover_analysis(frame, config, label):
    rows, summary = [], []
    magnitudes = list(map(int, config["magnitudes_m"]))
    for offset, ((regime, detector), group) in enumerate(frame.groupby(["regime", "detector"]), 1):
        sensors = {sensor: part for sensor, part in group.groupby("sensor")}
        if not {"S1_C", "NISAR_L"}.issubset(sensors):
            continue
        boot = {}
        fitted_point = {}
        for sensor_index, sensor in enumerate(("S1_C", "NISAR_L")):
            part = sensors[sensor]
            probabilities = [part[part.magnitude_m == m].recovered.mean() for m in magnitudes]
            fitted_point[sensor] = pava(probabilities, [1] * len(magnitudes))
            boot[sensor], _ = bootstrap_curve(part, magnitudes, int(config["bootstrap_iterations"]), int(config["bootstrap_seed"]) + 1000 + offset * 10 + sensor_index)
        difference = boot["NISAR_L"] - boot["S1_C"]
        lower = np.quantile(difference, 0.025, axis=0)
        upper = np.quantile(difference, 0.975, axis=0)
        point = fitted_point["NISAR_L"] - fitted_point["S1_C"]
        supported = lower > 0
        crossover = None
        for i in range(len(magnitudes) - 2):
            if supported[i:i + 3].all():
                crossover = magnitudes[i]; break
        for i, magnitude in enumerate(magnitudes):
            rows.append({"comparison": label, "regime": regime, "detector": detector, "magnitude_m": magnitude, "P_L_minus_P_C": point[i], "ci95_lower": lower[i], "ci95_upper": upper[i], "l_band_supported_advantage": bool(supported[i])})
        summary.append({"comparison": label, "regime": regime, "detector": detector, "s1_pairs": sensors["S1_C"].pair_id.nunique(), "nisar_pairs": sensors["NISAR_L"].pair_id.nunique(), "supported_crossover_m": crossover if crossover is not None else "none_through_60m"})
    return rows, summary


def plot_curves(curves, crossover, output):
    for (regime, detector), group in curves.groupby(["regime", "detector"]):
        fig, axes = plt.subplots(1, 2, figsize=(13, 5.2), constrained_layout=True)
        colors = {"S1_C": "#2166ac", "NISAR_L": "#b2182b"}
        for sensor, part in group.groupby("sensor"):
            axes[0].fill_between(part.magnitude_m, part.ci95_lower, part.ci95_upper, color=colors[sensor], alpha=0.18)
            axes[0].plot(part.magnitude_m, part.isotonic_probability, color=colors[sensor], lw=2.2, label=sensor)
        axes[0].axhline(0.95, color="black", ls=":", lw=1)
        axes[0].set(xlabel="Injected displacement (m)", ylabel="Directionally correct detection probability", ylim=(0, 1.02), title=f"{regime} · {detector}")
        axes[0].legend(frameon=False); axes[0].grid(alpha=.2)
        part = crossover[(crossover.regime == regime) & (crossover.detector == detector) & (crossover.comparison == "all_available")]
        if not part.empty:
            axes[1].fill_between(part.magnitude_m, part.ci95_lower, part.ci95_upper, color="#8073ac", alpha=.22)
            axes[1].plot(part.magnitude_m, part.P_L_minus_P_C, color="#542788", lw=2)
        axes[1].axhline(0, color="black", ls=":", lw=1)
        axes[1].set(xlabel="Injected displacement (m)", ylabel="P(L-band) − P(C-band)", title="Cross-sensor advantage with 95% CI")
        axes[1].grid(alpha=.2)
        fig.savefig(output / f"curves__{regime}__{detector}.png", dpi=190, facecolor="white")
        plt.close(fig)


def self_test():
    rng = np.random.default_rng(1)
    image = rng.normal(0, 1, (140, 140)).astype("float32")
    mask = np.zeros_like(image, "uint8"); mask[50:90, 50:90] = 1
    image[50:90, 50:90] += rng.normal(4, 1, (40, 40))
    background = background_for(image, mask, 5)
    moved = inject(image, background, mask, 2.0, -1.5)
    dx, dy, coefficient, accepted = ecc(image, moved, mask, [35, 35, 105, 105], 4, .40, 8)
    error = math.hypot(dx - 2.0, dy + 1.5)
    if not accepted or error > .5:
        raise AssertionError(f"Synthetic ECC test failed: {(dx, dy, coefficient, error)}")
    return {"status": "PASS", "measured_dx": dx, "measured_dy": dy, "error_px": error}


def run(config_path: Path, pair_path: Path, output: Path):
    config = json.loads(config_path.read_text(encoding="utf-8"))
    output.mkdir(parents=True, exist_ok=False)
    test = self_test()
    pair_df = pd.read_csv(pair_path)
    if pair_df.empty:
        raise RuntimeError("No eligible acquisition-disjoint pairs were prepared")
    grids = {}
    for site, details in config["sites"].items():
        for regime, spec in config["analysis_regimes"].items():
            grids[(site, regime)] = grid_for_bbox(details["bbox"], float(spec["target_resolution_m"]))
    prepared, shams = prepare_pairs(pair_df, config, grids, {})
    thresholds, threshold_rows = build_thresholds(shams, config)
    write_csv(output / "calibration_shams.csv", shams)
    write_csv(output / "thresholds.csv", threshold_rows)
    channel_rows = run_trials(prepared, thresholds, config)
    consensus_rows = consensus_trials(channel_rows, config)
    write_csv(output / "channel_trials.csv", channel_rows)
    write_csv(output / "dualpol_consensus_trials.csv", consensus_rows)
    detector_rows = detector_table(channel_rows, consensus_rows)
    curves, boundaries, frame = curves_and_boundaries(detector_rows, config, output)
    all_rows, all_summary = crossover_analysis(frame, config, "all_available")
    matched = matched_depth(frame)
    matched_rows, matched_summary = crossover_analysis(matched, config, "matched_pair_depth") if not matched.empty else ([], [])
    crossover_rows, crossover_summary = all_rows + matched_rows, all_summary + matched_summary
    write_csv(output / "cross_sensor_advantage_curves.csv", crossover_rows)
    write_csv(output / "crossover_summary.csv", crossover_summary)
    crossover_frame = pd.DataFrame(crossover_rows)
    if not crossover_frame.empty:
        plot_curves(curves, crossover_frame, output)
    power = []
    unique_pairs = pair_df.drop_duplicates(["pair_id", "split"])
    for (sensor, site), group in unique_pairs.groupby(["sensor", "site"]):
        cal = int((group.split == "calibration").sum()); test_n = int((group.split == "test").sum())
        power.append({"sensor": sensor, "site": site, "calibration_pairs": cal, "test_pairs": test_n, "publishable_calibration_target": config["minimum_publishable_calibration_pairs"], "publishable_test_target": config["minimum_publishable_test_pairs"], "status": "ADEQUATE" if cal >= config["minimum_publishable_calibration_pairs"] and test_n >= config["minimum_publishable_test_pairs"] else "UNDERPOWERED"})
    write_csv(output / "power_audit.csv", power)
    summary = {
        "experiment": config["experiment_name"],
        "self_test": test,
        "channel_trials": len(channel_rows),
        "consensus_trials": len(consensus_rows),
        "md_boundaries": boundaries.to_dict("records"),
        "crossovers": crossover_summary,
        "power_audit": power,
        "interpretation_rule": "L-band dominance is supported only where the lower 95% bootstrap bound of P(L)-P(C) is above zero for three consecutive magnitudes.",
        "software": {"python": sys.version, "numpy": np.__version__, "opencv": cv2.__version__, "rasterio": rasterio.__version__},
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))
    return summary
