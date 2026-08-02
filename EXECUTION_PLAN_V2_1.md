# GRAIL-V — Execution plan v2.1 (scope freeze)

**Status:** execution addendum. This document does **not** supersede
[`GRAIL_V_WORK_PLAN_V2.md`](GRAIL_V_WORK_PLAN_V2.md), which remains the
scientific contract, or
[`CODE_IMPLEMENTATION_SPEC.md`](CODE_IMPLEMENTATION_SPEC.md), which remains the
engineering contract. It fixes **what gets built in what order** for the
conference submission, and declares four v2 line items as deferred.

## 1. Why this exists

v2 is scientifically correct and its 18-week schedule assumes two external
simulator toolchains land on time. Neither is under our control. Measured
against the repository as it stands — M0 complete, M1 at roughly 85%, ~7.2k
lines of source and ~2.3k lines of tests for one and a half of ten milestones —
the remaining v2 scope does not fit a five-page conference paper's runway.

The response is **not** to reopen any v2 correction. Every deferral below is
already sanctioned by v2's own fallback text, and — the test applied
throughout — **none of them touches the four-part novelty conjunction of v2
§1.3**: shared urban geometry, causal age-aware observations, per-packet
control under a reliability budget, and trajectory-level rare-event evaluation.

## 2. Deferred, with authority

| Deferred item | v2 clause authorizing it | Replacement | Saving |
|---|---|---|---:|
| 5G-LENA Mode-2 calibration campaign | §7.2 fallback | Scoped analytical collision model + sensitivity bands | ~2 wk + tail risk |
| Real Manhattan OSM + NYC DOT calibration | Risk 6 | Synthetic grid only | ~1.5 wk |
| 10⁻⁵ ultra-reliability campaigns | §1.2, §13.4, Risk 5 | Discussion paragraph, no campaign | ~1 wk + 10⁷ runs |
| Veins-VLC cross-check | §8.1 ("closest reproducible") | W17/W18 tabulated curves | ~1 wk |

**Consequences accepted now, not retroactively:**

- Mode-2 realism claims are weakened **from the start**. The paper says
  "analytical collision model with sensitivity bands", never "NR Mode 2".
  Spec §10.5 `mode2_surrogate.py` and all of `tools/fiveg_lena/` leave the
  critical path.
- No real-map robustness claim unless it is reinstated at week 14.
- 10⁻⁵ appears only as discussion with raw miss counts, per Risk 5.

**Reinstatement points:** if the week-1 gate passed cleanly (it did — see
[`research/gates/GATE2_PRECHECK_PHY_FEASIBILITY.md`](research/gates/GATE2_PRECHECK_PHY_FEASIBILITY.md))
and weeks 8–9 finish early, real-map and 5G-LENA return at weeks 14–15 in that
order of preference.

## 3. Explicitly *not* cut

**All seven baselines of v2 §12.1 stay.** Once the environment exists they are
nearly free, and two of them carry the argument:

- **Fixed-penalty PPO** — answers "why not just tune a scalar penalty?", which
  is the reviewer question that decides whether the constrained formulation is
  a contribution or decoration.
- **Constrained contextual policy** — the honesty check. v2 §6.3 already
  commits to describing the problem as contextual rather than sequential if
  action-dependent information shows no measurable benefit.

Cutting these saves days and costs the paper.

## 4. Schedule

| Wk | Deliverable | Gate |
|---:|---|---|
| 1 | PHY feasibility gate (done), scope freeze (this doc), hypotheses file | — |
| 2–3 | M1 close-out: trace scripts, three densities, manifests | **Gate 1** |
| 4–6 | M2 geometry, occlusion, causality and leakage tests | — |
| 7 | Prediction and observation builder | — |
| 8–9 | RF (analytical + bands) and VLC channels; W17/W18 validation | **Gate 2** |
| 10 | Packet environment, oracle, joint-failure characterization | **Gate 3 — hard stop** |
| 11 | Seven baselines; freeze train/validation/test traces | — |
| 12–13 | Primal-dual PPO, curriculum, inference profiling | **Gate 4** |
| 14 | Five-seed training, 10⁶ matched evaluation, ablations | — |
| 15 | Cluster-aware statistics, F1–F4 | **Gate 5** |
| 16–17 | Draft, literature re-check, overlap review, submission | — |

**Gate 3 at week 10 is the genuine stop.** If the oracle cannot meet 10⁻⁴
anywhere, v2 §13.6 forbids starting PPO. See H1 in
[`research/HYPOTHESES.md`](research/HYPOTHESES.md) — that outcome is finding
#1, not failure.

Slack is deliberate: F4's mechanism panels are analysis-only over saved
rollouts and absorb slips without retraining.

## 5. Practices reinstated from work-plan v1

v1 was scientifically unpublishable as written, but six of its
project-management artifacts were dropped by v2 without replacement. They cost
days, not weeks, and are reinstated here.

1. **Bracketed draft abstract**, with `grep -n '\[' ` as a pre-submission
   check. v2's ban on pre-writing numbers is honored *by* the brackets, not
   violated by them. Write at week 15.
2. **Falsifiable hypotheses with numeric expectations** — internal only.
   Now at [`research/HYPOTHESES.md`](research/HYPOTHESES.md).
3. **v1's F4 and F7 as figure panels.** The single-episode mechanism trace
   with annotated anticipation lead time, and the spatial P(DUP) heat map, are
   what make a reviewer believe the policy learned geometry rather than a
   density lookup. They take the panel budget that v2 §15 assigned to real-map
   robustness — which is deferred anyway.
4. **Rebuttal pocket** — v1 §VII's eight pre-written objection responses,
   including W2's own "no structures in the vicinity" quote. Distinct from v2's
   risk register, which covers project risk rather than review defense.
5. **Declared slack** (§4 above).
6. **Scheduled literature re-check** at week 16: W12 full text, Xplore/Scopus
   strings, new citations to W1 and W2. v2 assumes this happens without
   calendaring it. Note that `W12_full.pdf` is currently a failed download —
   see the file audit.

## 6. Frozen decisions

- Headline profile stays **300 B / 1 ms / 10⁻⁴**. The week-1 gate cleared both
  legs; Risk 1 does not fire.
- VLC gross rate must sit inside the feasible window; RF requires 16QAM. Both
  configuration corrections are pending — see the gate document §5.
- `configs/service/ev2x_300B_3ms_1e-5.yaml` is retained as the Risk-1 fallback
  profile and must not be deleted.
