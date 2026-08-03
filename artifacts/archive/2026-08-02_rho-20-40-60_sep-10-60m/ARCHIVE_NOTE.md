# Archived campaign — superseded

Generated 2026-08-02. Superseded the same day; retained for provenance only.
Do not use for M2 or any downstream work.

## What this campaign used

- densities: 20 / 40 / 60 veh/lane-km
- tagged-pair separation window: 10-60 m
- tagged pair: any two same-lane vehicles in the window (adjacency not required)

## Why it was replaced

Measurement on these very traces showed the configuration could not support the
hybrid comparison the project exists to make.

1. **The optical path was blocked 97-100% of the time at 40 and 60
   veh/lane-km**, at every separation bin. Mean vehicle spacing at those
   densities (25 m and 16.7 m) is smaller than the 10-60 m separation window,
   so the tagged pair could not help but straddle other vehicles. V-VLC had no
   availability, DUP would have cost 2 to deliver what RF alone delivers, and
   RQ2 had nothing to decide.

2. **Requiring adjacency alone does not fix it at these densities.** Adjacent
   gaps collapse to the 7.0 m IDM jam spacing at rho >= 40, with 74-75% of
   pairs below 10 m, so the 10-60 m window captured only about a fifth of them
   and the 40-60 m stratum held 0.5-2.5%.

3. **Both impairments stop responding to density above rho ~= 30.** Optical
   blockage rises 5.3% -> 30.6% from rho=5 to 30, then flattens (26.2% at 40,
   30.7% at 60). RF neighbour count within 200 m does the same: 30 -> 180
   through rho=30, then 156 and 197. Past capacity, congestion adds queueing
   rather than either impairment, so two of the three densities were
   effectively one operating point.

## What replaced it

- densities: 10 / 20 / 30 veh/lane-km — both impairments still rising, giving
  2.5x spread in optical blockage and 2.7x in neighbour count
- separation window: 5-40 m — holds 82-91% of adjacent pairs at these densities
- tagged pair: immediate leader-follower (`TaggedPairConfig.require_adjacent`)

Blockage now comes from cross-traffic sweeping the link at junctions, which is
intermittent, geometry-dependent, and predictable from tracked positions.
