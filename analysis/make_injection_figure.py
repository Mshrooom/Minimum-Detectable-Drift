"""Create the portfolio injection figure from tracked, real raster inputs.

This is a visual audit of the same inpainting, translation and ECC functions
used by ``src/cross_sensor_inference.py``. It is not a separately tuned model.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import rasterio


ROOT = Path(__file__).resolve().parents[1]
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


def stretch(array: np.ndarray) -> np.ndarray:
    low, high = np.nanpercentile(array, [2, 98])
    return np.clip((array - low) / max(high - low, 1e-6), 0, 1)


def main() -> None:
    config = json.loads((ROOT / "config/experiment.json").read_text(encoding="utf-8"))
    raster_dir = ROOT / "qgis/rasters"
    with rasterio.open(raster_dir / "o171_s1a_20220108t112532_vv.tif") as source:
        reference = to_db(source.read(1))
    with rasterio.open(raster_dir / "o171_s1a_20220120t112532_vv.tif") as source:
        comparison = to_db(source.read(1))
    with rasterio.open(raster_dir / "tengeh_fpv_mask.tif") as source:
        mask = (source.read(1) > 0).astype("uint8")

    resolution_m = 10.0
    controls = controls_from_fractions(mask.shape, config["stable_control_fractional_boxes"])
    aligned, land_dx, land_dy, land_ok = align_land(reference, comparison, controls)
    if not land_ok:
        raise RuntimeError("Stable-land registration failed for the tracked example pair")

    background = background_for(
        aligned, mask, int(round(config["inpaint_radius_m"] / resolution_m))
    )
    injected_m = 40.0
    injected = inject(aligned, background, mask, injected_m / resolution_m, 0.0)
    box = tracking_box(mask, int(round(config["tracking_padding_m"] / resolution_m)))
    dx, dy, coefficient, accepted = ecc(
        reference,
        injected,
        mask,
        box,
        int(round(config["tracking_mask_expansion_m"] / resolution_m)),
        config["minimum_ecc_coefficient"],
        config["maximum_shift_m"] / resolution_m,
    )

    ys, xs = np.where(mask > 0)
    pad = 20
    x1, x2 = max(0, xs.min() - pad), min(mask.shape[1], xs.max() + pad)
    y1, y2 = max(0, ys.min() - pad), min(mask.shape[0], ys.max() + pad)
    extent = [x1, x2, y2, y1]

    fig, axes = plt.subplots(1, 4, figsize=(15, 4.5))
    panels = [
        (reference, "A  Reference SAR", "Sentinel-1 VV · 8 Jan 2022"),
        (aligned, "B  Land-registered pair", f"bias = ({land_dx:.2f}, {land_dy:.2f}) px"),
        (background, "C  Original footprint inpainted", "prevents duplicate-array artefacts"),
        (injected, "D  40 m east injection", f"ECC = {coefficient:.3f} · accepted = {accepted}"),
    ]
    for axis, (array, title, subtitle) in zip(axes, panels, strict=True):
        axis.imshow(stretch(array), cmap="gray", extent=[0, array.shape[1], array.shape[0], 0])
        axis.contour(mask, levels=[0.5], colors=["#f7d154"], linewidths=1.0)
        axis.set_xlim(x1, x2)
        axis.set_ylim(y2, y1)
        axis.set_xticks([])
        axis.set_yticks([])
        axis.set_title(
            f"{title}\n{subtitle}",
            loc="left",
            fontsize=10.5,
            fontweight="bold",
            linespacing=1.45,
        )

    # Measured vector is plotted in pixel coordinates at the source-mask centre.
    cx, cy = float(xs.mean()), float(ys.mean())
    axes[-1].arrow(
        cx,
        cy,
        dx,
        dy,
        width=0.25,
        head_width=2.0,
        head_length=2.0,
        color="#2ad6c9",
        length_includes_head=True,
        zorder=5,
    )
    measured_east, measured_south = dx * resolution_m, dy * resolution_m
    fig.suptitle(
        "Synthetic translation as a controlled observability experiment",
        fontsize=16,
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.025,
        f"Injected: 40.0 m east · recovered: {measured_east:.1f} m east, {measured_south:.1f} m south · "
        "yellow = original optical-derived FPV mask",
        ha="center",
        fontsize=9,
    )
    fig.subplots_adjust(left=0.02, right=0.99, top=0.78, bottom=0.12, wspace=0.08)
    output = ROOT / "docs/assets/research/injection_pipeline_real_raster.png"
    fig.savefig(output, dpi=180, bbox_inches="tight", facecolor="white")
    print(output)
    print(
        json.dumps(
            {
                "injected_east_m": injected_m,
                "recovered_east_m": measured_east,
                "recovered_south_m": measured_south,
                "ecc_coefficient": coefficient,
                "accepted": bool(accepted),
                "land_dx_px": land_dx,
                "land_dy_px": land_dy,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
