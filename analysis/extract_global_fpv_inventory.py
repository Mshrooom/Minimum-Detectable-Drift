"""Extract the peer-reviewed 643-record global FPV inventory from its PDF table.

Source
------
Nobre et al. (2024), "A global study of freshwater coverage by floating
photovoltaics", Solar Energy 267, 112244.
DOI: https://doi.org/10.1016/j.solener.2023.112244

The publisher supplement is an Excel-exported PDF rather than a machine-readable
table. This parser preserves all 643 catalogue rows, converts mappable DMS
coordinates to WGS84 decimal degrees, and records whenever longitude hemisphere
had to be inferred from the country because the source cell omitted E/W/O.

Usage
-----
python analysis/extract_global_fpv_inventory.py --pdf path/to/mmc1.pdf
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import pandas as pd
import pdfplumber


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "external" / "global_fpv_inventory_2023.csv"
DEFAULT_AUDIT = ROOT / "data" / "external" / "global_fpv_inventory_2023_audit.json"

CONTINENTS = ("North America", "South America", "Asia", "Europe", "Africa", "Oceania")
WEST_COUNTRIES = {
    "USA", "Canada", "Chile", "Brazil", "Portugal", "England", "Spain",
    "Colombia", "Mexico", "Peru", "Argentina", "New Zealand",
}
YEAR_RE = re.compile(r"\s((?:19|20)\d{2}(?:/(?:19|20)\d{2})?|NA)\s")
DMS_RE = re.compile(
    r"(?P<deg>\d{1,3})\s*°\s*(?P<minute>\d{1,2})\s*[\'′]?\s*"
    r"(?P<second>\d{1,2}(?:[\.,]\d+)?)\s*[\"″]?\s*(?P<hem>[NSEWO])?",
    flags=re.IGNORECASE,
)


def number(value: str) -> float | None:
    value = value.strip()
    if value == "NA":
        return None
    return float(value.replace(",", "."))


def coordinate(match: re.Match[str], axis: str, country: str) -> tuple[float, bool]:
    value = (
        float(match.group("deg"))
        + float(match.group("minute")) / 60.0
        + float(match.group("second").replace(",", ".")) / 3600.0
    )
    hemisphere = (match.group("hem") or "").upper()
    inferred = not bool(hemisphere)
    if hemisphere in {"S", "W", "O"}:
        value = -value
    elif not hemisphere and axis == "longitude" and country in WEST_COUNTRIES:
        value = -value
    return value, inferred


def parse_coordinates(blob: str, country: str) -> tuple[float | None, float | None, bool]:
    if blob.strip() == "NA NA":
        return None, None, False
    matches = list(DMS_RE.finditer(blob))
    if len(matches) < 2:
        return None, None, False
    lat, lat_inferred = coordinate(matches[0], "latitude", country)
    lon, lon_inferred = coordinate(matches[1], "longitude", country)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None, None, lat_inferred or lon_inferred
    return lat, lon, lat_inferred or lon_inferred


def split_continent(text: str) -> tuple[str, str]:
    for continent in CONTINENTS:
        if text.startswith(continent + " "):
            return continent, text[len(continent) + 1 :]
    raise ValueError(f"Unrecognised continent in row: {text[:80]}")


def parse_row(raw: str, sequence: int) -> dict[str, object]:
    code_text, remainder = raw.strip().split(maxsplit=1)
    continent, remainder = split_continent(remainder)
    year_match = YEAR_RE.search(" " + remainder + " ")
    if not year_match:
        raise ValueError(f"Year not found in row: {raw}")
    padded = " " + remainder + " "
    country = padded[1 : year_match.start()].strip()
    year = year_match.group(1)
    after_year = padded[year_match.end() :].strip()
    fields = after_year.rsplit(maxsplit=6)
    if len(fields) != 7:
        raise ValueError(f"Expected coordinate blob plus six values: {raw}")
    coord_blob, lake_area, perimeter, fpv_area, coverage, shoreline, capacity = fields
    latitude, longitude, hemisphere_inferred = parse_coordinates(coord_blob, country)
    return {
        "inventory_id": f"NOBRE-{sequence:04d}",
        "source_code": int(code_text),
        "continent": continent,
        "country": country,
        "year": year,
        "latitude": latitude,
        "longitude": longitude,
        "coordinate_hemisphere_inferred": hemisphere_inferred,
        "lake_area_m2": number(lake_area),
        "lake_perimeter_m": number(perimeter),
        "fpv_area_m2": number(fpv_area),
        "fpv_coverage_pct": number(coverage),
        "shoreline_development": number(shoreline),
        "capacity_kwp": number(capacity),
    }


def extract(pdf_path: Path) -> pd.DataFrame:
    rows: list[str] = []
    with pdfplumber.open(pdf_path) as document:
        for page in document.pages:
            text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
            rows.extend(line for line in text.splitlines() if re.match(r"^\s*\d+\s+", line))
    if len(rows) != 643:
        raise RuntimeError(f"Expected 643 source rows, extracted {len(rows)}")
    frame = pd.DataFrame(parse_row(raw, index) for index, raw in enumerate(rows, start=1))
    return frame


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True, help="Publisher supplement PDF (mmc1.pdf)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()

    frame = extract(args.pdf)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False, float_format="%.8f")
    mapped = frame.latitude.notna() & frame.longitude.notna()
    audit = {
        "source_rows": int(len(frame)),
        "mappable_rows": int(mapped.sum()),
        "coordinate_missing_rows": int((~mapped).sum()),
        "countries": int(frame.country.nunique()),
        "survey_cutoff": "2023-04",
        "source_doi": "10.1016/j.solener.2023.112244",
        "source_pdf_sha256": __import__("hashlib").sha256(args.pdf.read_bytes()).hexdigest(),
        "notes": [
            "The source is a survey through April 2023, not a live global registry.",
            "Rows without coordinates remain in the CSV but cannot be rendered as points.",
            "O in the source longitude is treated as west (ouest).",
            "Omitted longitude hemispheres are inferred from country and explicitly flagged.",
        ],
    }
    args.audit.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
