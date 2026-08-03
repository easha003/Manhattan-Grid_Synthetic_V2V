# Archived campaign — one realization per density, no splits

Correct configuration (10/20/30 veh/lane-km, 5-40 m, adjacent pairs) and
Gate 1 passed on all three densities. Superseded only because it produced a
single mobility realization per density.

## Why that is not enough

Work plan section 13.1 requires train, validation and test splits made by
complete trajectory, route and seed, with adjacent packets from one trajectory
never split across sets. With one trace per density there is nothing to split:
training, validation and test would draw from the same mobility realization, so
"held out" would be held out in name only, and early stopping on a disjoint
validation set (section 11.4) would be measuring the training distribution.

The declared split identifiers in configs/project/default.yaml at the time named
nine traces (synthetic-train-000 and so on) that had never been generated, which
is why the gap went unnoticed.

## What replaced it

Option B: 3 train / 1 validation / 3 test independent realizations per density,
21 traces. Trace identity now encodes density, split and replicate
(synthetic-d10-train-000), and the seed is derived from that full identity so
every trace is an independent realization. Two tests keep the configured split
identifiers and the generator's naming in agreement.

Test-split packet supply under Option B: 3.8M at rho=10, 11.0M at rho=20,
22.7M at rho=30 — clearing 1e6 everywhere and 1e7 at the two higher densities,
so the 1e-5 frontier is statistically supportable there and exploratory only at
rho=10.
