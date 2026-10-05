# Contributing

Scientific corrections, reproducibility fixes, and additional acquisition-
disjoint sites are welcome. Please open an issue before changing the detector
or decision rule: performance-improving changes create a new benchmark version
and must not overwrite the frozen `v0.1.0` result.

Pull requests should pass `python tests/validate_release.py`, identify data
provenance, document any outcome-dependent choices, and avoid committing raw
credentials or provider-restricted imagery.
