# Superseded — 21-trace Option-B campaign, pre-junction-fix

**Archived 2026-08-04. Do not use for any downstream work.**

Config hash `5e42a2ba61e1…` · generated 2026-08-03 · 9 train / 3 validation /
9 test at \(\rho_L\in\{10,20,30\}\).

## Why these are superseded

Two independent defects, both found by the M2 geometry engine after these
traces were written, and both of the same kind: an invariant stated in one form
and implemented in a weaker one.

**1. Opposing carriageways shared a centreline** (work plan §4.6.3,
`docs/DECISION_LOG.md` D9). Both directed edges of a street returned the same
coordinates, so northbound and southbound traffic occupied one line — roughly
74 physical vehicle overlaps per frame at \(\rho_L=20\), head to head. 93.9% of
all measured optical blockage was oncoming traffic sitting at exactly 0.000 m
lateral offset. The overlap invariant never caught it because it compared
vehicles sharing an `edge_id`, and `E7F7 ≠ F7E7`.

Corrected at \(\rho_L=20\): optical path blocked 27.1% → 1.58%, V-VLC available
72.9% → 97.95%.

**2. Vehicles passed through one another at junctions** (§4.6.5, D11). Injection
placed bodies inside the junction they spawned at; the stop line stood at the
junction *centre*; nothing arbitrated conflicting crossings; and IDM is not
collision-free under hard braking. 4.51 / 10.72 / 27.45 overlapping pairs per
frame at \(\rho_L=10/20/30\), all within 12 m of a junction.

## What this invalidates

Every blockage figure derived from these traces, which is work plan §4.6.1,
§4.6.2, and §14.1's worked numbers. Those sections are marked superseded in
place rather than deleted, so the correction can be audited.

The mobility fixes also changed the fundamental diagram: flow now saturates
near 318 veh/h/lane between \(\rho_L=20\) and 30 rather than 550 between 40 and
60, and holding capacity falls from 72 to 65.3 veh/lane-km. §4.5 carries the
re-measured relation and the superseded one.

## Retained for audit only

The parquet bulk is kept locally and untracked, as with the earlier archives;
`ARCHIVE_NOTE.md` and `campaign_manifest.json` are the tracked provenance
record. Each trace's own `resolved_config.yaml` and `manifest.json` remain
beside it, including the `notes` recording the earlier `137941801b86…` →
`5e42a2ba61e1…` re-stamp.

## Preceded by

- `2026-08-02_single-realization-no-splits`
- `2026-08-02_rho-20-40-60_sep-10-60m` — risk R4a, the configuration that
  destroyed the phenomenon under study
