# GRAIL-V — Falsifiable hypotheses (internal)

**This file is never quoted in the paper.** Work-plan v2 §3 correctly forbids
writing numeric expectations into the manuscript before results exist. That
prohibition is about the manuscript. Internally, the opposite discipline
applies: state in advance what each outcome would mean, so that a surprising
result triggers a decision rather than improvisation.

Adapted from work-plan v1 §V-F, updated to v2's formulation — normalized
activation cost rather than energy, per-density constraints, cluster-aware
statistics, and the empirical (not hard) constraint language.

**Recorded before any channel or environment code exists.** Do not edit
predictions after seeing results; append outcomes instead.

---

## H1 — Feasibility frontier

**Predict:** RF-only violates 10⁻⁴ above roughly 40 veh/lane-km from
congestion. VLC-only violates near intersections at all densities from
occlusion. The learned policy holds the constraint across the sweep at 20–35%
lower activation cost than Always-DUP.

**If falsified — no policy, including the oracle, is feasible at high density:**
this is **finding #1, not failure**. The paper becomes the density beyond which
hybrid redundancy cannot rescue a 1 ms deadline, with the mechanism attributed
(joint blockage vs RF congestion vs PHY timing) from saved traces. Work-plan v2
§13.6 forbids training PPO against an impossible constraint, and Risk 3 sets
the response.

**Both branches are publishable.** Decide which at Gate 3, week 10 — before any
training compute is spent.

**Decision rule:** if the oracle misses 10⁻⁴ at every density, stop and rewrite
around infeasibility. If it clears at some density, train only there.

---

## H2 — Burst tails

**Predict:** agent maximum consecutive-miss run ≤ 2–3 versus ≥ 5–8 for the best
single-link policy at 60 veh/lane-km; survival curves separate by at least an
order of magnitude at run ≥ 3.

**Grounds:** duplication across physically decorrelated media should break
exactly the runs that occlusion (VLC) or congestion (RF) alone would extend.

**If falsified — runs do not shorten:** the media are less decorrelated than
assumed. Report the dependence ratio \(p_\mathrm{joint}/(p_\mathrm{RF}
p_\mathrm{VLC})\) as the headline mechanism finding instead. v2 §8.3 already
requires logging it, which is what makes this branch survivable.

**Guard:** v2 §13.5 forbids comparing raw maximum run length without equal
packet exposure. Compare survival curves, not maxima.

---

## H3 — Geometry-aware behavior

**Predict:** P(DUP | intersection approach) exceeds P(DUP | mid-block) by ≥ 3×.
Median anticipation lead time — first defensive action before optical quality
collapses — falls in 100–300 ms, at or below the 200 ms forecast horizon.

**This is the hypothesis the paper's novelty rests on.** It is the difference
between a policy that learned geometry and one that learned a density lookup.

**Test:** the no-forecast ablation (v2 §12.2.1) should erase most of the margin
and widen the oracle gap. If it does not, the forecast feature is not being
used, and the "causal geometry-aware" framing is unsupported — reframe around
the constrained formulation and the environment instead.

**Figure:** this is what v1's F4 and F7 were for, reinstated in execution plan
v2.1 §5.3.

---

## H4 — Duplication economy

**Predict:** agent duplication-waste lands in single digits (W2's anchor: 7%),
while Always-DUP's waste — its share of packets where one link would have
sufficed — exceeds 60%, mirroring W2's 66% but with physically decorrelated
legs rather than two RF RATs.

**If falsified — waste stays high:** the feasible single-link opportunity is
rarer than assumed, which is itself a result about the 1 ms regime. Report the
frontier and say so.

---

## H5 — Formulation delta

**Predict:** the primal-dual agent tracks 10⁻⁴ tightly across densities, while
the fixed-penalty PPO baseline either overshoots reliability (overspending
activation cost) at low density or violates at high density under fixed
weights.

**This hypothesis is why the fixed-penalty baseline cannot be cut.** If a
single tuned scalar penalty matches the multiplier across all three densities,
the constrained machinery is decoration, and the paper should say so and lead
with the environment and evaluation instead.

**Related ablation:** one global multiplier vs one per density (v2 §12.2.3).
If the global multiplier suffices, per-density constraints are unnecessary
complexity — report it.

---

## H6 — Deployability

**Predict:** p99 policy inference below 100 µs on a named CPU (v2 §11.5's
engineering gate); median well below that. Interpolation to 30 and 50
veh/lane-km degrades miss probability by less than 3× while staying within
constraint.

**If falsified — inference misses the gate:** v2 §11.5 already restricts the
claim to "compatible with 1 ms only if the complete observation-to-action path
leaves enough time". Narrow the claim; do not narrow the network until the
architecture has been profiled rather than guessed.

---

## H7 — Sequentiality (added; not in v1)

**Predict:** the constrained contextual baseline — same observation, no history,
no feature age — underperforms the full policy, demonstrating that
action-dependent information freshness matters.

**If falsified:** v2 §6.3 has already committed the response in advance:
"If action-dependent information provides no measurable benefit, the paper will
describe the problem as contextual rather than overclaiming MDP sequentiality."
Follow it. This costs the sequential framing, not the paper.

---

## Outcomes log

Append results here as they arrive. Do not edit the predictions above.

| Hypothesis | Gate/week | Outcome | Decision taken |
|---|---|---|---|
| H1 | Gate 3, wk 10 | — | — |
| H2 | wk 14 | — | — |
| H3 | wk 14 | — | — |
| H4 | wk 14 | — | — |
| H5 | wk 14 | — | — |
| H6 | wk 12–13 | — | — |
| H7 | wk 14 | — | — |
