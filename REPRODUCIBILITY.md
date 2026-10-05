# Reproducibility

## Kaggle

1. Upload this repository as a private Kaggle Dataset.
2. Attach the private site-mask bundle separately.
3. Enable Internet and use a CPU/RAM runtime; no GPU is required.
4. Add `EARTHDATA_TOKEN` as a Kaggle Secret. Alternatively add both
   `EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD`.
5. Run `notebooks/cross_sensor_observability_kaggle.ipynb` from top to bottom.

The acquisition stage writes a locked pair table and checksum manifest. The
inference stage refuses to reuse an existing output directory, preventing a
partial run from being silently overwritten.

## Expected audit

- 1,377 scene records.
- 678 unique acquisition-disjoint temporal pairs.
- 393 calibration pairs and 285 test pairs.
- no calibration/test scene overlap.
- 538,560 channel trials.
- 269,280 dual-polarization consensus trials.
- sub-pixel self-test error below 0.05 px.

Exact scene totals can grow when providers release additional acquisitions.
For reproduction of the archived benchmark, respect the frozen end date in
`config/experiment.json`.

## Compact versus full outputs

This repository tracks compact derived tables and figures. Full channel and
consensus trial tables are intentionally excluded from Git because of their
size; regenerate them with the notebook or obtain them from the associated
research release once deposited.

