# Decision log

Why the model is the way it is, with the arithmetic that forced each change.

This file exists because the *what* is recoverable from `git log` and the
*specification* is in `GRAIL_V_WORK_PLAN_V3.md`, but the reasoning that
connects them is not recoverable from either. Three of the entries below are
corrections to earlier decisions, and two of those invalidated measurements
that had already been published. A reviewer asking "why 10/20/30?" or "why did
the trace hash change twice?" should find the answer here rather than in a
commit message.

**Scope.** M1 (mobility) and M2 (geometry), 2 August – 4 August 2026. Entries
are in commit order. Each records the decision, the evidence that forced it,
the calculation, and what it invalidated.

**Convention.** Superseded values are kept, never deleted. A measurement that
turned out to be an artefact is more useful than its absence, because it is
what makes the correction auditable.

---

## Config-hash chain

Three digests exist in the project's history. Any artifact carrying one of the
first two is stale.

| Digest | From | Reason for the move |
|---|---|---|
| `137941801b86…` | Option-B campaign, 3 Aug | superseded by D3 |
| `5e42a2ba61e1…` | D3 — split membership excluded from the digest | superseded by D9 |
| `92bf9cb56f1e…` | D9 — `lane_width_m` added, carriageways separated | current |

---

## D1 — Training densities are 10 / 20 / 30, and tagged pairs must be adjacent

`91b588e` · 2 Aug · work plan §4.5.1, §4.6, R4a

**Decision.** \(\rho_L\in\{10,20,30\}\) instead of \(\{20,40,60\}\); the tagged
pair must be the immediate leader-follower (`TaggedPairConfig.require_adjacent`);
separation window 10–60 m → 5–40 m; report bins derived from the window rather
than fixed at 10/20/40/60.

**What was wrong.** Any two same-lane vehicles inside the window could form a
pair. Mean lane spacing is

\[
s = \frac{1000}{\rho_L}\ \text{m}
\qquad
\rho_L = 20 \to 50.0,\quad 40 \to 25.0,\quad 60 \to 16.7\ \text{m}
\]

and the expected number of vehicles between a pair separated by \(d\) is

\[
\mathbb{E}[n_\text{between}] \approx \frac{d}{s} - 1
\]

At \(\rho_L=40\), \(d=60\): \(60/25 - 1 = 1.4\). At \(\rho_L=60\):
\(60/16.7 - 1 = 2.6\). The pair could not help but straddle other traffic.
Measured blockage was **97–100% at every separation bin**. V-VLC had no
availability, DUP would have cost 2 to deliver what RF alone delivers, and RQ2
had nothing to decide.

**Why this was not caught by a gate.** Every Gate-1 check passed. Gate 1 tests
mobility credibility — realised density, fundamental diagram, determinism — not
whether the link under study can ever work. That gap is now recorded as risk
**R4a**: *before each gate, measure the quantity the research question depends
on, not only the quantities the gate lists.*

**Why the band moved down.** Both impairments stop responding above
\(\rho_L\approx30\):

| \(\rho_L\) | Optical path blocked | Neighbours ≤200 m |
|---:|---:|---:|
| 5 | 5.3% | 30 |
| 10 | 12.2% | 67 |
| 20 | 22.5% | 114 |
| **30** | **30.6%** | **180** |
| 40 | 26.2% | 156 |
| 60 | 30.7% | 197 |

Dynamic range across the three chosen training points:

\[
\{20,40,60\}:\quad \frac{30.7}{22.5} = 1.36\times,\qquad \frac{197}{114} = 1.73\times
\]
\[
\{10,20,30\}:\quad \frac{30.6}{12.2} = 2.51\times,\qquad \frac{180}{67} = 2.69\times
\]

Two of the three old points were effectively one operating condition. Past
capacity, neighbour count *falls* because vehicles pack into queues rather than
spreading through the sensing radius — beyond \(\rho_L=30\) the model measures
queueing, not communication.

**Window and bins.** 5–40 m holds 82–91% of adjacent pairs. The old fixed bin
edges put **45% of \(\rho_L=30\) pairs into "outside"**, hiding the
stratification the research question depends on.

**Invalidated.** The first trace campaign, archived under `artifacts/archive/`
with its rationale.

---

## D2 — Reserved configuration fields are marked, not deleted

`a7e268a` · 3 Aug

`straight_heavy_turn_probabilities` describes an arterial-flow variant that is
specified but not in use. It is retained with a comment marking it reserved,
rather than removed, because deleting it would lose the specification and
re-adding it later would change the config hash for a field that no generator
reads.

---

## D3 — The config hash digests physics-bearing configuration only

`3f79c18` · 3 Aug · work plan §11.2 · [`src/grail_v/config/hashing.py`](../src/grail_v/config/hashing.py)

**Decision.**

```python
HASH_EXCLUDED_PATHS: Final[tuple[tuple[str, ...], ...]] = (("environment", "splits"),)
```

**Why.** SHA-256 avalanches: one changed character in the serialized
configuration produces an unrelated digest. So everything inside the digest
becomes a versioning axis. Split membership is consumed at training and
evaluation time and is read by **no generator** — including it meant that
adding a held-out replicate would re-stamp 21 traces whose bytes it could not
have changed.

**The test to apply, and it is deliberately strict.** *Can this field alter any
generated artifact?* If it can, it stays in the digest even when that is
inconvenient. Adding to `HASH_EXCLUDED_PATHS` is a deliberate act, not a
convenience.

**Nothing is lost.** `canonical_json` still serializes the excluded fields,
every trace stores its complete `resolved_config.yaml`, and the campaign
manifest records the split map.

**The re-stamp was gated, not asserted.** `137941801b86…` → `5e42a2ba61e1…`
proceeded only after recomputing the *old* digest from the live configuration
and matching it against each manifest, which proves the traces came from a
canonically identical configuration; each artifact was then re-verified against
its file digests. `canonical_json` was left unpruned precisely so that proof
was possible — pruning both would have destroyed the evidence. Every trace
manifest records the transition in its `notes`.

---

## D4 — Stored vehicle position is the front bumper

`0d5e158` · 3 Aug · [`src/grail_v/geometry/primitives.py`](../src/grail_v/geometry/primitives.py)

**Decision.** `rectangle_from_front()` is the only place the convention is
applied; every footprint in the project is built through it.

**How the convention was established.** From the car-following gap arithmetic:

\[
\text{gap} = x_\text{leader} - x_\text{follower} - L_\text{leader}
\]

Only one leader length is subtracted. Under a centre convention it would have
to be \(-\tfrac{1}{2}L_\text{leader} - \tfrac{1}{2}L_\text{follower}\).

**What the wrong convention would have cost.** Building a rectangle *centred*
on the stored point pushes phantom body \(L/2\) ahead of the true bumper:

| Class | \(L\) | Phantom overhang |
|---|---:|---:|
| passenger | 4.5 m | 2.25 m |
| van | 5.2 m | 2.60 m |
| bus/truck | 11.0 m | **5.50 m** |

**Verified empirically**, which is what settled it: on a real frame the centre
convention produced **92 overlapping pairs against 0** under the front
convention, and every one of the 92 was a `bus_truck` behind a shorter vehicle
— exactly the \(L/2\) scaling. Every occlusion measurement would otherwise have
run on bodies that intersect each other.

---

## D5 — VLC runs follower-front to leader-rear; RF runs centre to centre

`89b1f93` · 3 Aug · [`src/grail_v/geometry/link_endpoints.py`](../src/grail_v/geometry/link_endpoints.py)

**Decision.** The optical path is headlamp (follower front, 0.7 m) to
photodiode (leader rear, 0.7 m). The RF path is antenna to antenna
(centre, 1.5 m). Both horizontal.

**Consequence for path length.** The optical path is shorter than the
separation:

\[
\ell_\text{opt} = d - L_\text{leader}
\qquad 20 - 4.5 = 15.5\ \text{m}
\]

This 15.5 m is the figure every later field-of-view calculation uses.

**Consequence for the occlusion test.** A horizontal path at fixed height
reduces 3-D occlusion to a planar intersection plus one scalar compare: a body
of height \(h\) blocks a path at height \(z\) iff \(h \ge z\). But the shortest
configured vehicle is 1.5 m, and

\[
h_\text{min} = 1.5 \;\ge\; z_\text{RF} = 1.5 \;>\; z_\text{opt} = 0.7
\]

so the height test passes for **every** vehicle on **both** links. That single
inequality is the structural cause of the obstruction coupling in §4.6.2 —
anything that cuts the optical path also meets the antenna path. It is why the
contribution is *"same obstruction, different consequence"* rather than
*"blocked at different times"*.

---

## D6 — Occlusion uses exact oriented rectangles, not point-to-segment

`0d5e158`, `89b1f93` · 3 Aug

**Decision.** Slab clipping in the rectangle's local frame, which is exact
under rotation. Boundary contact counts as intersection.

**What the approximation got wrong.** It treated each vehicle as a point with a
half-width tolerance. For a vehicle crossing *perpendicular* to the link, the
blocking cross-section is its length, not its width:

\[
\frac{L}{W} = \frac{4.5}{1.8} = 2.5\times
\qquad\text{bus/truck: } \frac{11.0}{2.5} = 4.4\times
\]

Cross-traffic is the dominant blocker class, so the approximation understated
blockage precisely where it mattered most.

---

## D7 — `vlc.receiver_fov_deg` is the receiver semi-angle \(\psi_c\)

`805c1ae`, `8736861` · 3 Aug · work plan §4.7 item 6 ·
[`configs/channel/vlc_vehicle.yaml`](../configs/channel/vlc_vehicle.yaml)

**Decision.** 60° is the semi-angle, not a full cone — the photodiode accepts
light up to 60° off boresight, for a total opening of 120°. Geometry applies
the interpretation in exactly one place,
`grail_v/geometry/pair_geometry.py`. The \(10^{-5}\) frontier uses 30° via
`vlc_vehicle_concentrated.yaml`.

**Why the ambiguity mattered.** Kahn–Barry concentrator gain, valid for
\(0 \le \psi \le \psi_c\):

\[
g(\psi) = \frac{n^2}{\sin^2 \psi_c}
\]
\[
\psi_c = 60°: \ \sin^2 60° = \tfrac{3}{4} \Rightarrow g = 1.333\,n^2
\qquad
\psi_c = 30°: \ \sin^2 30° = \tfrac{1}{4} \Rightarrow g = 4.000\,n^2
\]
\[
\text{ratio } 3.0\times = 10\log_{10} 3 = 4.77\ \text{dB optical}
\;\Rightarrow\; 9.54\ \text{dB electrical}
\]

Background collection runs the other way, but barely:

\[
P_\text{bg} \propto \frac{2\pi n^2}{1 + \cos\psi_c}
\qquad
60°: \frac{2\pi}{1.5} = 4.189\,n^2,
\quad
30°: \frac{2\pi}{1.866} = 3.367\,n^2
\]
\[
\text{ratio } 1.244 \Rightarrow 0.95\ \text{dB less shot noise at }30°
\]
\[
\textbf{net} \approx 10.5\ \text{dB background-limited},\quad
9.54\ \text{dB thermal-limited}
\]

≈10 dB either way. **The wider cone collects less signal for almost no noise
relief**, which makes 60° the pessimistic choice — pessimistic *for* V-VLC
rather than against it. The headline therefore claims a weaker optical front end
than a well-designed receiver would deliver, so the hybrid result strengthens
under scrutiny rather than weakening.

**Declared limitation.** Lateral tolerance at 30° over the optical path:

\[
15.5 \tan 30° = 8.95\ \text{m} \quad\text{against } 3.5\ \text{m of lane width}
\]

The grid is straight, single-lane, and without grade or lane changing, so it
cannot represent the road curvature, braking pitch or lateral dynamics that are
the real price of a narrow cone. Measured availability barely moves while the
link budget moves 10 dB. **The 30° sensitivity is optimistic on alignment and
must be reported as such**; the link-budget half is not optimistic in the same
way, and the two must be reported separately. The value is also unsourced.

**Cross-cutting constraint for M4.** Whatever \(\psi_c\) is in force, the
concentrator gain and the acceptance test must use the same value. A wide cone
for availability combined with narrow-cone gain in the link budget counts the
same physics twice.

---

## D8 — The reliability floor is geometric, and the optics cannot cross it

`8736861` · 3 Aug · work plan §14.1

**The relation.** Under duplication a miss requires both legs to fail, so the
hybrid relaxes the RF single-shot requirement by \(1/P(\text{VLC fails})\),
where

\[
P(\text{VLC fails}) = P_\text{out} + (1 - P_\text{out})\,\text{PER}_\text{clear}
\]

**The cap.** No concentrator gain reaches a blocked path, so the benefit is
capped at \(1/P_\text{out}\) regardless of transmit power or optics. The
concentrator acts only on \(\text{PER}_\text{clear}\), moving
\(P(\text{VLC fails})\) toward its geometric floor without going below it.

**The size of the move**, at \(P_\text{out} = 0.119\):

| \(\text{PER}_\text{clear}\) | \(P(\text{VLC fails})\) | Relaxation | RF BLER for \(10^{-5}\) |
|---|---:|---:|---:|
| 0.5 — marginal | \(0.119 + 0.881(0.5) = 0.560\) | 1.79× | \(1.8\times10^{-5}\) |
| 0.05 | \(0.119 + 0.881(0.05) = 0.163\) | 6.13× | \(6.1\times10^{-5}\) |
| ≈0 — strong | \(0.119\) | **8.40×** | \(8.4\times10^{-5}\) |

\[
\frac{8.40}{1.79} = 4.7\times \text{ of RF headroom turns on } \text{PER}_\text{clear}
\]

which can decide whether the \(10^{-5}\) frontier is reachable at all. **Which
end applies is a Gate-2 measurement, not an assumption** — optical power falls
as \(1/d^2\) and the window runs to 40 m, so the 60° receiver may sit on its PER
waterfall exactly where blockage is highest. If \(\text{PER}_\text{clear}\) is
already negligible at 40 m with 60°, the concentrated layer is redundant and the
headline value is simply correct.

**Independence is assumed and is optimistic.** A queue at a junction produces a
high channel-busy ratio and cross-traffic in the optical path at the same time.
Any positive correlation raises the floor, which is what Gate 3 exists to
detect.

> The \(P_\text{out}\) values used above (11.9 / 22.2 / 16.1%) are contaminated
> by D9. The corrected \(\rho_L=20\) figure is 2.05%, giving a cap of 48.8×.
> Recompute this table on regenerated traces.

---

## D9 — Opposing carriageways are separated by 3.5 m

`d3df905`, `432c2a1` · 4 Aug · work plan §4.6.3 ·
[`src/grail_v/mobility/grid_network.py`](../src/grail_v/mobility/grid_network.py)

**The largest correction in the project so far.** The geometry engine was built
to measure blockage; the first thing it measured was that the blockage was not
real.

**The defect.** Each street carried two directed edges sharing one centreline,
so `GridEdge.position_at` returned identical points for both directions.
Confirmed on `synthetic-d20-train-000` at \(t=0\):

```
veh_0000050  edge=E7F7  heading=  0°  spans x 1003.45 → 1007.95  at y=427.00
veh_0003814  edge=F7E7  heading=180°  spans x 1005.02 → 1009.52  at y=427.00
```

\[
\text{overlap} = 1007.95 - 1005.02 = 2.93\ \text{m, head to head}
\]

Roughly **74 such overlaps per frame** at \(\rho_L=20\).

**Why the existing invariant missed it.**
`test_no_two_vehicles_overlap_on_the_same_edge` compared vehicles on the same
`edge_id`, and `E7F7 ≠ F7E7`, so an opposing pair was never a candidate.

**Why the earlier blocker classification was wrong.** Blockers had been
classified by `edge_id` and reported as "cross-traffic". Reclassified by
relative heading:

| Blocker | As published | Corrected |
|---|---:|---:|
| Oncoming, 180° | **93.9%** | 6.6% |
| Cross-traffic, 90° | 5.1% | **73.8%** |

Every oncoming blocker sat at a lateral offset of exactly 0.000 m. The right
story — cross-traffic sweeping a junction — had been attached to the wrong
evidence.

**The fix.**

\[
\text{carriageway\_offset} = \tfrac{1}{2}(\text{lanes\_per\_direction})(\text{lane\_width})
= \tfrac{1}{2}(1)(3.5) = 1.75\ \text{m per direction}
\]

giving 3.5 m between opposing lanes, applied through
`GridEdge.right_unit = (\sin h, -\cos h)`. Clearance from the link axis to the
widest body in the mixture:

\[
3.5 - 1.25 = 2.25\ \text{m} \qquad (\text{was } 0.000\ \text{m — dead centre})
\]

`lane_width_m` is physics-bearing, so it belongs in the digest: hash
`5e42a2ba` → `92bf9cb5`.

**Measured, fresh \(\rho_L=20\) trace:**

| | Shared centreline | Separated |
|---|---:|---:|
| Closest opposing approach | 0.000 m | **3.500 m** |
| Optical path blocked | 27.1% | **1.58%** |
| Out of field of view | 1.3% | 1.01% |
| **V-VLC available** | 72.9% | **97.95%** |

**And the signal it exposed:**

| Path position | Instants | V-VLC unavailable |
|---|---:|---:|
| Spans a junction | 1,651 | **27.01%** |
| Mid-block | 24,690 | **0.38%** |
| **Lift** | | **71.7×** |

The two tables reconcile, which is the check that they are the same
measurement:

\[
\text{exposure} = \frac{1651}{26341} = 6.27\%
\]
\[
(0.0627)(27.01) + (0.9373)(0.38) = 1.69 + 0.36 = 2.05\% \;\Rightarrow\; 97.95\%\ \checkmark
\]

**What this does to the contribution — it relocates it, and improves it.**
Condition A (intermittency) is weak in aggregate at 98% availability but
**not** conditionally: the policy faces a genuine 27% risk whenever it spans a
junction, roughly 6% of the time. That is precisely the state-dependent
structure the contribution wants — one link mid-block, duplicate at junctions,
beating Always-DUP on cost while holding reliability. Condition C
(predictability) is close to an oracle: a 71.7× lift on a feature derived from
own pose and a map. Condition D remains open: it needs a link budget on both
legs (M3 and M4), then the Gate-3 feasibility measurement at M5.

The RF relaxation also improves:

\[
\frac{1}{P_\text{out}} = \frac{1}{0.0205} = 48.8\times
\qquad\text{against the } 4.5\text{–}8.4\times \text{ of §14.1}
\]

**Invalidated.** §4.6.1, §4.6.2 and §14.1's worked numbers; the 21-trace
campaign. This is the third mobility retune and exactly the case risk **R4b**
anticipated: *generate the minimum set a milestone actually consumes, and
expand to the full replicate count only once the consumer that reads the split
exists.*

---

## D10 — The spatial index is a filter, and the leakage barrier is a test

`ad08c44` · 4 Aug · [`src/grail_v/geometry/spatial_index.py`](../src/grail_v/geometry/spatial_index.py),
[`tests/unit/test_geometry_leakage.py`](../tests/unit/test_geometry_leakage.py)

**Index.** A naive obstruction query scans every vehicle in the frame — 1,120
at \(\rho_L=30\). Cell size defaults to the largest footprint diagonal:

\[
\sqrt{11.0^2 + 2.5^2} = \sqrt{127.25} = 11.28\ \text{m}
\qquad\text{floored at } 5.0\ \text{m}
\]

Measured on a 747-vehicle frame with 419 live pairs:

| | Time |
|---|---:|
| Brute force | 1,137 ms |
| Index build | 5.6 ms |
| Indexed queries | **2.7 ms** |

425× on queries, 138× including build, identical verdicts, mean 2.9 candidates
from 747 — a \(747/2.9 = 258\times\) reduction in the exact tests performed.

**It is a filter, not a decision.** `candidates()` returns a *superset*; the
exact test still runs in `vehicle_occlusion`. Extra candidates cost time and
never correctness; missing ones would silently drop blockers with nothing
downstream able to detect it. Hence the index was built **last** in M2 and is
tested by asserting agreement with the brute-force scan it replaces, over
random scenes rather than one hand-built case. A separate test asserts the
filter actually *narrows* — one that returned everything would pass the
equivalence tests and be useless.

**Why this matters for the paper, not just for runtime.** The per-bin blockage
figures were not converged: re-running \(\rho_L=10\) at 120 and 240 sampled
frames moved the 10–20 m bin between 19.0% and 28.3% while aggregate
availability moved only 88.1% to 86.8%. Occlusion is deterministic — the
240-frame run reproduced the 120-frame occlusion figures exactly — so that is
sampling, not instability. The index is what makes dense enough sampling
affordable to settle it.

**Leakage guards.** Three, because they fail differently:

1. the configuration cannot **name** a forbidden observation field — each
   checked individually, not just the first;
2. the observation package cannot **import** the geometry engine — installed
   while that package is still empty, so its first module cannot take the
   shortcut;
3. no geometry module may grow an `as_observation` / `to_features` /
   `as_policy_input` / `observe` helper, which is how exact state usually
   escapes, because it looks convenient.

Both import guards parse the module with `ast` rather than searching text. A
text search matches prose, and these files discuss the forbidden names at
length, so a grep-based guard fires on its own explanations.

**The single deliberate exception** is `intersection_context`: junction distance
and span derive from own pose plus a road map, which a real vehicle has. Every
other geometry result depends on where *other* vehicles are, which it does not.
A test pins that it reaches neither occlusion nor RF visibility, so the 200 ms
forecast keeps a lawful input.

---

## D11 — Junctions arbitrate crossings, and the overlap invariant is tested over all pairs

4 Aug · work plan §4.6.5, §4.7 item 7 ·
[`src/grail_v/mobility/grid_simulator.py`](../src/grail_v/mobility/grid_simulator.py)

**Found by writing the test D9 said was missing**, and found on its first run.
§16.3 requires "no overlapping vehicle footprints in any recorded frame"; the
implementation compared vehicles sharing an `edge_id`, so it tested
lane-keeping only. That is the same gap D9 exploited, one level down.

**Measured before the fix:** 4.51 / 10.72 / 27.45 overlapping pairs per frame
at \(\rho_L=10/20/30\), involving 2.4–4.9% of vehicles, up to 2.0 m deep.
**100% within 12 m of a junction**, median 3.4 m from centre.

**Four causes, each hidden behind the one before it.** The instructive part is
that three of the four were geometric mistakes about where the junction *is*:

1. Injection put the front bumper at `offset_m = 0`, so a 4.5 m body extended
   backwards through the junction the edge leaves.
2. The stop line stood at `edge.length_m`, which *is* the junction centre. Even
   set back by the carriageway offset it was wrong, because the crossing street
   reaches further than the offset alone:

\[
\text{box reach} = \text{carriageway offset} + \tfrac{1}{2}(\text{widest body})
= 1.75 + 1.25 = 3.0\ \text{m}
\]

   The missing 1.25 m of overhang was exactly the ~1 m median penetration that
   survived the first attempt — the measurement named its own cause.

3. No conflict arbitration existed, and adding reservations was insufficient
   until a second bug was fixed: a vehicle that had already crossed was
   labelled with the movement for its **next** junction, so two conflicting
   crossers could each be granted the same box.
4. IDM is not collision-free. A leader braking hard at a stop line, sampled at
   50 ms, leaves a follower's front past its tail.

**Result** over 100 frames at the production warm-up: 451 → 0, 1,072 → 1,
2,745 → 2. A 99.9% reduction, deepest residual 0.42 m.

**It is a bound, not zero**, and §4.7 item 7 says so. The remaining cases are a
same-step race between two crossings, asserted by test rather than assumed.
Chasing exact zero was weighed against the cost: each remaining case is rarer
than the last, and the residue is two real bodies at real junction positions,
so occlusion undercounts blockers rather than inventing them.

**Cost, which is real.** Requiring a driver to keep the box clear reduces
throughput. Flow now saturates near 318 veh/h/lane between \(\rho_L=20\) and 30
against 550 between 40 and 60; holding capacity falls 72 → 65.3 veh/lane-km
because the first slot on every edge is reserved. Density remains exact.
\(\rho_L=30\) now sits at capacity rather than in free flow, so **§4.5.1's
choice of training band must be re-checked from the regenerated traces.**

**The lesson, which is D9's lesson repeated.** Both defects survived because an
invariant was written down in one form and implemented in a weaker one. The
implemented form passed. Prefer assertions that make no assumption about the
structures they are checking: the all-pairs world-coordinate test knows nothing
about lanes, headings or edge identity, so it keeps holding when those change.

---

## D12 — The evidence base, restated on corrected traces

4 Aug · work plan §4.5.1, §4.6.1, §4.6.2, §14.1

Nine traces regenerated at `92bf9cb5` against the settled engine — one per
split per density, which is the minimum the pipeline emits and what R4b
prescribes. Seeds are content-addressed by `trace_id`, so the eventual 21-trace
campaign reproduces these exactly; only a code or config change between now and
M7 would force a full regeneration rather than a top-up. Gate 1 passes on all
nine.

Measured at 300 sampled frames per trace, the headline moved as follows.

**V-VLC availability 96.59 / 98.13 / 99.0%** at \(\rho_L = 10/20/30\), against
88.1 / 77.8 / 83.9% before. The aggregate at \(\rho_L=20\) is unchanged from
the single post-D9 trace (97.95% → 98.13%), which confirms D9 was the whole of
the earlier error and nothing since has moved it.

**The aggregate is the wrong summary.** Conditioned on junction spanning the
same quantity is bimodal — 0.25–0.50% mid-block against 30.5–32.6% spanning, a
65–121× lift — and the conditional risk is nearly constant across density while
*exposure* varies (9.08 → 2.52%). Density stratifies the radio; the junction
condition stratifies the optics.

**Two real mechanisms, not one.** Cross-traffic occlusion lifts 10.9–37.1× at a
junction; leader-turn misalignment supplies the rest. An earlier draft called
misalignment an artefact of pair extraction and recommended a heading re-check.
**That was wrong and the change was cancelled before it was made.** The
continuation loop already ends a pair on route divergence; what survives is a
leader turning *on a shared route*, which a deployed system genuinely loses.
Re-checking would have deleted a real failure mode and inflated availability —
selection bias in the flattering direction, the same error class as D1 and D9.

**§4.6.2's premise collapsed.** RF vehicle blockage is 0.20–0.31%, against the
10.2–23.2% the old argument rested on, and RF obstruction is now dominated by
*buildings* 3–6× over vehicles. The "same body blocks both, RF survives it"
claim is withdrawn. What replaced it is better: the share of impairments
striking **exactly one** link rose from ~20% to **61–72%**, which is the
condition diversity actually requires.

**§14.1's floor fell by an order of magnitude.** \(1/P_\text{out}\) is now
29–99× rather than 4.5–8.4×, so \(10^{-5}\) asks RF for \(3\text{–}10\times
10^{-4}\) single-shot BLER rather than \(10^{-5}\). Conditionally it ranges
256× mid-block to 3.1× at a junction — the control problem in one number. And
because the floor fell, the stake on the clear-path link budget *rose*, from
4.7× of RF headroom to 15×.

**One structural finding.** Even mid-block, \(P_\text{out}=0.25\text{–}0.50\%\)
is 25–50× the \(10^{-4}\) budget, so V-VLC alone never meets the target
instantaneously anywhere. Its role is as a duplication partner; the `VLC`
action at cost 1 may be dominated. Added to Gate 3 to be settled before
training rather than discovered during it.

---

## Known stale, as of 4 August 2026

1. **The 21 published traces** carry `5e42a2ba` and pre-D9 physics. Archived
   under `artifacts/archive/2026-08-04_pre-junction-fix/`; superseded by the
   nine regenerated in D12.
2. **§4.5.1's density-sweep table** is withdrawn, not restated. Its blockage
   column was the §4.6.3 artefact and the capacity point moved with §4.6.5. The
   band now rests on opposing gradients; whether a fourth point below
   \(\rho_L=10\) would better exercise the optical side is unresolved.
3. **Only replicate 000 exists per split.** No across-seed variance until M7,
   which is deliberate.
4. **`is_obstructed` tests vehicles only**, so V-VLC occlusion never considers
   buildings while RF classification does. It changes no verdict today, because
   misalignment already marks the turning case unavailable, but the two are not
   measuring the same set of obstacles. Declared in §4.6.2 consequence 3.

## Open, and decisive

- **Condition D** — does a single link ever meet \(10^{-4}\) instantaneously?
  Needs a link budget on both legs (M3 RF, M4 V-VLC), then the feasible-region
  measurement at Gate 3 (M5). If no single link ever qualifies, "always DUP" is
  optimal and the CMDP is trivial; that outcome is finding #1, not failure (H1).
- **§7.2, the collision model, is undefined** and is the decisive RF parameter.
  RF carries roughly 41.7 dB of thermal margin at 40 m, so RF failure is
  collision-dominated — §7.2 alone determines whether Condition D can be
  answered yes. It must be scoped with literature-backed sensitivity bands
  **chosen before seeing which values favour the result**.
- Unsourced parameters: IDM desired time headway \(T = 1.2\) s (§4.7 item 1) and
  the receiver semi-angle (§4.7 item 6).
