"""Regenerate site-level harmonized-20 m MD point estimates.

Usage:
  python analysis/summarize_sites.py \
    --channel-trials /path/to/channel_trials.csv \
    --consensus-trials /path/to/dualpol_consensus_trials.csv \
    --power-audit /path/to/power_audit.csv \
    --output data/derived/site_md_summary_regenerated.csv

The pooled, bootstrapped results remain authoritative for cross-sensor
inference. This script produces the site point estimates used by the map; it
does not manufacture site-level confidence intervals from sparse NISAR pairs.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


SITE_METADATA = {
    "piolenc": ("Piolenc", "France", "FRA", 44.1555, 4.7280),
    "sirindhorn": ("Sirindhorn", "Thailand", "THA", 15.1980, 105.4440),
    "tengeh": ("Tengeh", "Singapore", "SGP", 1.3500, 103.6430),
}


def pava(values: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Weighted non-decreasing pooled-adjacent-violators fit."""
    blocks: list[list[float]] = []
    for index, (value, weight) in enumerate(zip(values, weights, strict=True)):
        blocks.append([float(value), float(weight), index, index])
        while len(blocks) >= 2 and blocks[-2][0] > blocks[-1][0]:
            right = blocks.pop()
            left = blocks.pop()
            total_weight = left[1] + right[1]
            mean = (left[0] * left[1] + right[0] * right[1]) / total_weight
            blocks.append([mean, total_weight, left[2], right[3]])
    fitted = np.empty(len(values), dtype=float)
    for mean, _, start, stop in blocks:
        fitted[int(start) : int(stop) + 1] = mean
    return fitted


def boundaries(frame: pd.DataFrame) -> tuple[int | str, int | str, int | str]:
    grouped = frame.groupby("magnitude_m", sort=True)["recovered"].agg(["sum", "count"])
    fitted = pava((grouped["sum"] / grouped["count"]).to_numpy(), grouped["count"].to_numpy())
    magnitudes = grouped.index.to_numpy(dtype=int)

    def first_at(target: float) -> int | str:
        matches = np.flatnonzero(fitted >= target)
        return int(magnitudes[matches[0]]) if matches.size else "not_reached"

    return first_at(0.50), first_at(0.80), first_at(0.95)


def read_trials(path: Path, polarisation: str | None = None) -> pd.DataFrame:
    columns = ["pair_id", "sensor", "site", "regime", "magnitude_m", "recovered"]
    if polarisation is not None:
        columns.append("polarisation")
    frame = pd.read_csv(path, usecols=columns)
    frame = frame.loc[frame["regime"].eq("harmonized_20m")]
    if polarisation is not None:
        frame = frame.loc[frame["polarisation"].eq(polarisation)]
    return frame


def build_summary(
    channel_path: Path, consensus_path: Path, power_audit_path: Path
) -> pd.DataFrame:
    copol = read_trials(channel_path, "copol")
    dual = read_trials(consensus_path)
    power = pd.read_csv(power_audit_path).set_index(["sensor", "site"])
    records: list[dict[str, object]] = []
    for (sensor, site), group in copol.groupby(["sensor", "site"], sort=True):
        dual_group = dual.loc[dual["sensor"].eq(sensor) & dual["site"].eq(site)]
        name, country, iso3, latitude, longitude = SITE_METADATA[site]
        md50_c, md80_c, md95_c = boundaries(group)
        md50_d, md80_d, md95_d = boundaries(dual_group)
        records.append(
            {
                "site": name,
                "country": country,
                "iso3": iso3,
                "latitude": latitude,
                "longitude": longitude,
                "sensor": "NISAR" if sensor == "NISAR_L" else "Sentinel-1",
                "band": "L" if sensor == "NISAR_L" else "C",
                "calibration_pairs": int(power.loc[(sensor, site), "calibration_pairs"]),
                "test_pairs": group["pair_id"].nunique(),
                "md50_copol_m": md50_c,
                "md80_copol_m": md80_c,
                "md95_copol_m": md95_c,
                "md50_dual_m": md50_d,
                "md80_dual_m": md80_d,
                "md95_dual_m": md95_d,
            }
        )
    return pd.DataFrame.from_records(records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel-trials", type=Path, required=True)
    parser.add_argument("--consensus-trials", type=Path, required=True)
    parser.add_argument("--power-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = build_summary(args.channel_trials, args.consensus_trials, args.power_audit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.output, index=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
