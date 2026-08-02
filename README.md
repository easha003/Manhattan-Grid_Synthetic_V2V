# GRAIL-V

GRAIL-V is a research implementation for geometry-aware,
reliability-constrained selection among NR sidelink, vehicle visible-light
communication (V-VLC), and simultaneous duplication in urban V2V traffic.

The current implementation is at Milestone M0. The research contract is in
[`GRAIL_V_WORK_PLAN_V2.md`](GRAIL_V_WORK_PLAN_V2.md), and the module-level
engineering contract is in
[`CODE_IMPLEMENTATION_SPEC.md`](CODE_IMPLEMENTATION_SPEC.md).

## Supported runtime

- Python 3.11 or 3.12
- Eclipse SUMO 1.27.0 for the currently validated local setup

Python 3.14 is intentionally outside the supported range.

## Development installation

Use a Python 3.11/3.12 environment, then run:

```bash
python -m pip install -e '.[dev]'
grailv doctor --sumo-home /path/to/sumo
pytest
ruff check src tests
ruff format --check src tests
mypy
```

SUMO can be supplied through `SUMO_HOME`, normal executable lookup, or the
`--sumo-home` option to `grailv doctor`.

## Current headline profile

- 300-byte information block
- one packet every 100 ms
- 3-ms radio-interface deadline
- deadline-miss budget \(10^{-4}\) per traffic-density group
- actions: RF, VLC, or simultaneous DUP
- pre-reserved NR sidelink opportunity with one attempt per selected leg
- no feedback HARQ inside the deadline
- normalized activation costs RF = 1, VLC = 1, and DUP = 2

Payload and deadline follow the 3GPP TR 38.913 eV2X reference row; the
\(10^{-4}\) budget follows the 99.99% reliability class of the TS 22.186
advanced-driving services. The complete tuple is a controlled research profile,
not a conformance claim. A \(10^{-5}\) frontier at the same payload and
deadline is declared in `configs/service/ev2x_300B_3ms_1e-5.yaml`; it upgrades
the claim if its one-sided upper bound supports it.

Generated traces, checkpoints, and evaluations belong under `artifacts/` with
versioned manifests. They are not source files.

## Publication-governance status

The Gate-0 comparison is recorded in
[`paper/U0_OVERLAP_MATRIX.md`](paper/U0_OVERLAP_MATRIX.md). It remains
provisional until the authors compare the exact U0 manuscript and artifacts and
check the selected venue's current related-submission policy.
