# Proposal — replace SUMO/TraCI with a specified Manhattan-grid V2V mobility model

**Status:** proposal for supervisor review. No code has been changed.

**Decision requested:** approve, reject, or amend the model defined in §4 before
any implementation work begins.

---

## 1. Why this is being proposed

GRAIL-V currently generates mobility with Eclipse SUMO driven over TraCI. The
project's contribution is **constrained reinforcement learning for per-packet
`{RF, VLC, DUP}` link selection**, not traffic modelling. SUMO is being used
only to produce vehicle trajectories from which RF and V-VLC channel conditions
are derived.

Three observations motivate replacing it:

1. **The fidelity is already disclaimed.** Work plan §1.3 states the project
   will not claim "that a synthetic orthogonal grid is a calibrated model of all
   Manhattan traffic." The microscopic realism SUMO provides is therefore not
   being converted into a claim.
2. **The one test that needed SUMO is deferred.** The OSM real-map robustness
   test is deferred in `EXECUTION_PLAN_V2_1.md` §2 under work plan Risk 6.
3. **Measured cost.** A single-density trial on the target hardware
   (MacBook Pro, M2) required a closed-loop density search of up to 16 SUMO
   runs before one trace could be recorded, and surfaced two defects in one
   day (a 64-bit seed rejected by SUMO's 32-bit `--seed`, and vehicle route
   identifiers that made tagged-pair extraction return zero episodes).

A specified analytical grid model removes the external toolchain, removes the
density calibration loop entirely, and reduces campaign runtime from hours to
seconds — at the cost of microscopic realism that is not being claimed.

---

## 2. What must be preserved

These four properties are load-bearing for the research questions. Any
replacement model that drops one of them invalidates a stated result.

| # | Property | Why it cannot be dropped |
|---|---|---|
| 1 | Individual vehicle **positions and dimensions** | VLC occlusion is a rectangle-intersects-line test against real blockers. A density statistic cannot answer it. |
| 2 | Vehicle **headings** | V-VLC is directional: headlamp radiation pattern and photodiode field of view both depend on relative orientation. |
| 3 | **Signal stopping and queue formation** | Hypothesis H3 predicts P(DUP \| intersection approach) exceeds P(DUP \| mid-block). That contrast exists because vehicles bunch at red lights. Free-flow spacing destroys it. |
| 4 | **Deterministic replay from a seed** | Work plan §13.1 requires all policies to be evaluated on identical trajectories. |

### 2.1 The failure mode that would invalidate RQ3

3GPP TR 37.885 models NLOSv (vehicle blockage) **stochastically** — an
additional loss term applied when a vehicle obstructs the link. Adopting that
treatment for V-VLC occlusion would be a serious error:

- blockage would no longer be a function of where a blocker actually is;
- it could not be predicted from tracked vehicle positions;
- the observation field "predicted probability of blockage within 200 ms"
  (work plan §6.1) would carry no information;
- **RQ3, the value of geometry prediction, would collapse.**

**Rule:** use TR 37.885 for *path loss given a propagation class*; determine the
*class itself* geometrically from vehicle rectangles. This separation already
exists in the implementation spec (`pathloss_37885.py` versus
`vehicle_occlusion.py`) and must be preserved.

---

## 3. What is gained and lost

| | SUMO (current) | Proposed model |
|---|---|---|
| Vehicle spacing | Emerges from car-following | From a declared car-following law |
| Queueing at signals | Emergent | Explicit, same mechanism |
| Lane changing | Yes | No (single lane per direction) |
| Density control | Closed-loop search, up to 16 runs | **Exact, set directly** |
| Campaign runtime | Hours | Seconds |
| External dependency | SUMO + TraCI + netgenerate | None |
| Novelty claim §1.3(1) | "microscopic urban geometry" | "geometry-driven shared mobility" |

Novelty items 2–4 — causal age-aware observations, per-packet control under an
explicit reliability budget, and trajectory-level rare-event evaluation — are
unaffected.

---

## 4. Model definition

### 4.1 Geometry

A rectangular grid of one-way-per-direction streets. Two candidate parameter
sets; **this is an open decision (§8, D1)**:

| Parameter | Option A — current project | Option B — TR 37.885 urban grid |
|---|---|---|
| Block spacing | 244 m × 61 m | *pin to the standard's clause* |
| Lanes per direction | 1 | *pin to the standard's clause* |
| Speed limit | 11.18 m/s (25 mph) | *pin to the standard's clause* |

Option A reflects the characteristic long, rectangular Manhattan block and is
what the frozen configuration currently encodes. Option B buys standardised
scenario alignment with the propagation model already cited.

**Exact TR 37.885 values must be read from the standard, not assumed.** They are
deliberately left blank here.

Buildings are the complements of the street grid: a rectangular block occupies
the interior of each city block. This makes RF NLOS (building-obstructed)
determination exact — two vehicles on perpendicular streets separated by a
block corner are NLOS by construction.

### 4.2 Vehicle state

Each vehicle `i` carries:

```
position along its current edge   s_i      [m]
speed                             v_i      [m/s]
current edge                      e_i
lane                              lane_i
planned route (edge sequence)     R_i
type (car / van / truck)          with length, width, height
```

Cartesian `(x, y)` and `heading` are derived from `(e_i, s_i)` and the edge's
geometry. Vehicle dimensions follow the existing configured mixture
(90% passenger car, 7% van/SUV, 3% bus/truck).

### 4.3 Longitudinal motion — Intelligent Driver Model

Motion follows the IDM (Treiber, Hennecke and Helbing, *Phys. Rev. E* 62(2),
2000), a standard, citable, deterministic car-following law:

```
dv/dt = a [ 1 − (v/v₀)^δ − (s*/s)² ]

s* = s₀ + v·T + v·Δv / (2√(a·b))
```

with `s` the bumper-to-bumper gap to the leader, `Δv = v − v_leader`, and
parameters: desired speed `v₀`, free acceleration `a`, comfortable deceleration
`b`, minimum gap `s₀`, desired time headway `T`, exponent `δ = 4`.

IDM is chosen because it is **the** reference microscopic car-following model,
is roughly ten lines of code, is collision-free by construction, and reproduces
realistic headway distributions and stop-and-go queueing — which is exactly the
mechanism property 3 of §2 requires.

**A red signal is modelled as a stationary virtual leader at the stop line.**
Queue formation therefore requires no additional mechanism: it falls directly
out of the same equation.

### 4.4 Traffic signals

Fixed-time signals at interior junctions, matching the current configuration:

- cycle 90 s;
- two phases (north–south green, east–west green) plus a yellow interval;
- staggered offsets across junctions, so greens are not synchronised.

Signal state is a deterministic function of `(t, junction_id)`. No adaptive
control.

### 4.5 Routing and turning

On reaching a junction a vehicle samples its next edge with the configured turn
probabilities — left 25%, straight 50%, right 25% for the headline profile;
left 10%, straight 80%, right 10% for the straight-heavy sensitivity. U-turns
are prohibited.

The realised edge sequence is retained as the vehicle's `planned_route`, which
resolves the tagged-pair route-sharing test directly (see §5.1).

### 4.6 Density control — no calibration loop

**Density becomes an exact input rather than a searched-for output.**

The model maintains a constant active vehicle count `N`, chosen from the target
density and the network's total lane length:

```
N = ρ_L × (total lane length in km)
```

When a vehicle leaves the grid, one new vehicle is injected at a randomly chosen
boundary entry with a fresh sampled route and type. Realised density is then
exactly `ρ_L` at every timestep, by construction.

This eliminates the entire closed-loop calibration subsystem — the demand
scaling search, its evaluation budget, and its failure modes.

**Reporting requirement:** every trace manifest must continue to report realised
density, mean speed, stopped fraction, and queue statistics, even though density
is now exact. Work plan §4.2's prohibition on inferring density from requested
flow is satisfied trivially, but the other statistics remain evidence of
plausible traffic.

### 4.7 Warm-up

Vehicles are initially placed with uniform random spacing, which is not a
steady state — queues have not yet formed. A warm-up interval is still
discarded before recording. Its length is a validation output (§7), not an
assumed constant: it is chosen as the time after which mean speed and stopped
fraction are stationary.

### 4.8 Determinism

One seeded generator per trace, derived through the project's existing named
stream mechanism. Given the same seed and configuration, the trajectory set is
bit-identical. Vehicles are never teleported and are never repositioned to
manufacture a tagged pair.

---

## 5. Interface contract — the trace schema

**This is the reason the change is affordable.** Every downstream module
consumes trajectories through one schema. A model emitting that schema is a
drop-in replacement, and geometry, channels, prediction, observation, PHY,
environment, agents, baselines and evaluation are all unaffected.

Vehicle records, per implementation spec §8.6:

```
trace_id, time_s, vehicle_id, x_m, y_m, heading_rad, speed_mps,
acceleration_mps2, length_m, width_m, height_m, lane_id, edge_id,
route_id, vehicle_type
```

Signal records retain junction identity, phase, and state.

### 5.1 One required correction

The tagged-pair extractor tests whether two vehicles share a route. Under SUMO,
routes were written anonymously, so every vehicle received a unique
auto-generated identifier and the test could never succeed — this produced zero
tagged-pair episodes in the trial run.

The proposed model must therefore expose each vehicle's **planned route as an
edge sequence**, not only an opaque identifier, so that "same route" can be
evaluated as *shared upcoming path* rather than *identical itinerary*. Two
vehicles following one another share a segment; they rarely share a whole
route. This is consistent with implementation spec §8.7, which terminates an
episode when "the routes diverge".

---

## 6. Explicit non-goals

The model does **not** provide, and no result may assume:

- lane changing or overtaking;
- multi-lane roads (unless Option B in §4.1 is adopted);
- adaptive or actuated signal control;
- pedestrians, cyclists, parking, or public-transport stops;
- calibration against measured NYC traffic counts;
- any claim that the grid reproduces real Manhattan traffic.

---

## 7. Validation plan

The model replaces SUMO but not the evidence burden. Two gates apply.

**Gate 1 — mobility credibility.** Unchanged conditions, evaluated by the
existing validator: realised density within tolerance, plausible mean speed
relative to the limit, queues forming and clearing at signals, positive
throughput, no teleportation, tagged-pair episodes present with the required
separation and duration semantics.

Two additional checks are proposed, both currently absent:

- **No overlapping vehicle footprints in any recorded frame.** IDM is
  collision-free by construction, so this should hold exactly. It is worth
  asserting because the SUMO trial produced 347 junction-collision warnings
  under `--collision.action warn`, which allowed overlapping vehicles to be
  recorded — a condition the occlusion geometry cannot meaningfully interpret.
- **Warm-up sufficiency:** mean speed and stopped fraction stationary over the
  recorded window.

**Gate 2 — optical realism.** The model's V-VLC availability-versus-distance
and blockage-rate statistics must be compared against the empirical vehicular
VLC evidence already collected (W17, and W18 once obtained). This is what makes
the simplification defensible rather than merely convenient: if blockage
statistics match empirical evidence, the simpler model has earned its place.

---

## 8. Open decisions for supervisor

| # | Decision | Options |
|---|---|---|
| **D1** | Grid geometry | (A) keep 244 m × 61 m, 1 lane/direction; (B) adopt TR 37.885 urban grid values |
| **D2** | Scope of "standardised" | Does the instruction cover mobility geometry only, or also the vehicle drop and speed models? |
| **D3** | Car-following law | IDM as proposed, or a simpler constant-speed/cellular-automaton model |
| **D4** | Novelty wording | Confirm §1.3 item 1 is reworded from "microscopic" to "geometry-driven" |
| **D5** | Retain SUMO? | Delete the mobility package, or retain it unused as a cross-check for one trace |

On **D5** the recommendation is to retain the existing SUMO path initially and
cross-check one trace's blockage statistics against the new model. If the two
agree within a declared tolerance, the simplification is evidenced rather than
asserted, and SUMO can then be removed.

---

## 9. Implementation estimate

| Item | Estimate |
|---|---|
| Grid geometry and edge/lane addressing | ~200 lines |
| IDM update, signals as virtual leaders | ~150 lines |
| Routing, turning, boundary injection | ~150 lines |
| Trace assembly to the existing schema | ~150 lines |
| Validation additions | ~100 lines |
| **Total** | **~750 lines**, replacing ~4,000 |

Removed: SUMO, TraCI, `netgenerate`, external process management, the density
calibration subsystem, and the trace-generation pipeline built around them.

Expected campaign runtime: **seconds**, against hours today. On single-laptop
hardware with no cluster, this is the difference between iterating daily and
iterating hourly — and it is the RL training and evaluation loop, not the
mobility, that the project's remaining schedule is spent on.
