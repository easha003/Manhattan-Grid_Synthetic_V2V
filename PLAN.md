# GRAIL-V — current plan

This supersedes `GRAIL_V_WORK_PLAN_V3.md` and everything before it. Those are
kept unchanged for provenance; nothing in them is deleted, and nothing in them
is current. What follows is only what is still being worked on.

**Dropped from the earlier plans, deliberately:** the PPO / primal-dual learned
policy and its milestones, single-lane mobility, densities 20/40/60, the
one-RF-attempt profile, and the formal hard-safety framing. The measured reason
for dropping the learned policy is recorded below rather than left implicit.

## Where the work stands

The claim is established and measured. Campaign artifact:
`artifacts/evaluations/campaign-test-ev2x-300B-3ms-1e-5-wide-10000000.json`,
20.9 M packets across ρ = 10/20/30, 20 000-replicate bootstrap.

- The mode-2 resource pool binds before the link budget: `n·N ≤ 400`, and the
  profile asks 1.62× that at ρ = 30
- Neither medium alone meets 10⁻⁵ above ρ ≈ 17–18
- The pair meets it at activation cost 1.0, by **load relief** rather than
  diversity — duplication costs twice as much and is 8× worse
- Realizable with an observable selector at ρ = 20 (7.00e-06, cost 1.34); a
  bound only at ρ = 30

## Open work

### 1. Decide the realizability framing — blocking for submission

The headline allocation chooses on true optical risk. This must be stated, and
one of three positions taken. The measurements exist for all three:

- **Bound.** Rename it, state that realizing it needs optical availability
  observable before the transmit decision, and note that the config currently
  models optical feedback as action-dependent.
- **Realizable variant.** Report the light-plus-two-RF-attempts result, which
  works at ρ = 20 and fails at ρ = 30 for a reason that is not selector
  accuracy.
- **Report the gap.** Score a belief-driven allocation alongside the oracle.
  `run_equilibrium` already takes a `belief` callable and `PREDICTED` is
  reserved as a policy name; nothing scores one yet. Expect it to offload
  nothing, which is itself the finding.

Not choosing is the single most likely cause of a reject.

### 2. Paper

Target IEEE VNC — the community that knows why a pool constraint is
surprising, and where Wang *et al.* and Toghi *et al.* were published. Section
outline against that template, with figures assigned, is drafted; the material
is roughly three VTC papers' worth, so the conference version carries the pool
constraint, the equilibrium, the three-density result and the realizable
selector, and the rest goes to a journal extension.

Two citations are not optional:

- **Wang, Berry, Vukovic, Rao (VTC 2018)** — fixed-point model for C-V2X
  collision probability. Methodological precedent; the difference is that their
  fixed point is in collision probability at fixed load and this one is in the
  allocation.
- **Toghi, Saifuddin, Fallah, Mughal (VTC 2019)** — states the `n ≤ M`
  saturation density. The extension here is treating retransmissions as pool
  draw and making it a feasibility bound.

**Singh *et al.* (arXiv 2208.06287)** targets the same row (>99.999 %, <3 ms)
with link aggregation and claims to meet it. Position against it directly: it
is a vision article, its reliability is estimated rather than plotted (figures
reach ~1e-3), it models channel access as a probability with no resource pool,
and its mechanism is the one measured here as worse and more expensive. It also
names resource allocation under mobility as open work.

### 3. Journal extension

Occlusion onset rate resolved by separation and density; the three collision
sensitivity bands; the estimator wall; bistability of the fixed point; the full
mobility model description. Each is measured and committed; none fits in six
pages.

## Deferred, with reasons

**Beam-extent occlusion model.** `complete_blockage_main: true` makes occlusion
a step function. A real beam has spatial extent, so an edge entering it
attenuates over milliseconds rather than instantly, which would make the
in-flight occlusion term smaller and the result stronger. Deferred as a
research programme in its own right, not a config change.

**Narrow-pattern campaign at 10⁻⁵.** Would restore the beam-width band in
`fig_frontier`, which currently draws from one campaign. ~13 h of compute for
one shaded region; the figure reads without it.

**Learned policies.** Measured, not assumed: the campaign's clairvoyant
per-packet `ORACLE` reaches 4.753e-06 at ρ = 20 while the load-aware allocation
reaches 1.329e-06 at the same cost. A per-packet policy — learned or not —
cannot express a gain that comes from changing the channel everyone shares. Any
return to learning should be mean-field or multi-agent, where the joint
behaviour moves the contention.

## Housekeeping

- Three planning documents carry stale facts without a superseded banner:
  `GRAIL_V_WORK_PLAN_V3.md`, `GRAIL_V_WORK_PLAN_V2.md`,
  `research/HYPOTHESES.md`. Two others already have one.
- `docs/report/grail_v_report.tex` predates the M7 result.
- `run_evaluation` computes every bootstrap bound twice — once for the printed
  table, once for the JSON. Roughly an hour per density at 10 M packets.
- `run_equilibrium` holds per-packet Python objects for the whole population.
  Fine at 10 M on 9 GB; the two passes visit packets in the same order, so an
  array index would do the same work.
