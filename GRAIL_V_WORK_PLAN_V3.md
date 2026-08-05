# GRAIL-V — Settled Conference Work Plan (Version 3)

**Working title:**
**GRAIL-V: Geometry-Aware Reliability-Constrained Link Selection for Hybrid NR Sidelink/V-VLC in Urban V2V Networks**

**Document status:** active implementation contract. This supersedes
`GRAIL_V_WORK_PLAN_V2.md` and `EXECUTION_PLAN_V2_1.md`, both retained for
provenance. Follow this document.

**Primary publication target:** IEEE VNC 2027 regular paper, subject to the
official call. **Backup:** IEEE VTC 2027-Fall.

---

## 0. What changed from Version 2, and why

Two decisions were taken after v2 was written, both driven by measurement
rather than preference. Everything else in v2 survives; this document restates
it in full so there is one place to look.

### 0.1 The headline profile moved from 1 ms to 3 ms

A pre-check of implementation-spec §13.6.1 found that at 300 B / 1 ms:

- the RF coded block did **not** fit one NR sidelink slot at QPSK (4,896 coded
  bits available against 5,568 required), forcing 16QAM and roughly 6 dB of
  extra SNR;
- the VLC configuration declared 10 Mbit/s OOK in a 5 MHz front end, which is
  unrealizable, and the feasible rate window was about 1 Mbit/s wide and closed
  entirely at roll-off 0.5 or code rate below 1/2.

At 3 ms both legs clear with margin and the surplus is spent on **coding gain
rather than throughput** (§8). Payload and deadline now follow the TR 38.913
eV2X reference row; the miss budget follows the 99.99% class of TS 22.186.

### 0.2 Mobility moved from SUMO/TraCI to a specified analytic grid model

SUMO was producing fidelity the project had already declined to claim (v2 §1.3
disclaims any calibrated-Manhattan-traffic claim), for a real-map test that was
deferred, at a measured cost of up to 16 simulator runs per density before one
trace could be recorded. Two defects surfaced in a single day, and one of them
— anonymous route identifiers — silently produced **zero tagged-pair episodes**,
a failure whose only symptom was an empty table.

The replacement is specified in §4. It is an in-repository microscopic model:
individual vehicles, IDM car-following, fixed-time signals, exact density. It
has no external dependency, runs a full campaign in roughly 35 minutes, and
emits the same trace schema, so every downstream module is unaffected.

**Consequence for the novelty claim:** §1.3 item 1 is reworded from
"microscopic shared urban geometry" to "geometry-driven shared urban
mobility". Items 2 to 4 are untouched, and they were always the more defensible
ones.

---

## 1. Final project decision

A single tagged following-vehicle V2V pair in urban traffic. Each generated
packet is sent over NR sidelink only, V-VLC only, or both simultaneously (DUP).
The controller minimizes normalized transmission activation cost subject to an
empirically evaluated deadline-miss constraint at each traffic-density level.

### 1.1 Headline service profile

| Parameter | Settled value |
|---|---:|
| Application | Compact cooperative V2V safety/status exchange |
| Information payload | 300 bytes |
| Packet generation interval | 100 ms |
| Decision interval | One decision per generated packet |
| Deadline | **3 ms** radio-interface deadline |
| Headline miss constraint | \(P_{\mathrm{miss}}\le 10^{-4}\) |
| RF attempts per packet | One |
| VLC attempts per packet | One |
| DUP semantics | RF and VLC transmit simultaneously |
| Feedback HARQ inside the deadline | None |
| RF resource assumption | Pre-reserved sidelink opportunity |

Configuration: `configs/service/ev2x_300B_3ms_1e-4.yaml`.

The 300-byte quantity is the L2/3 information block passed to each PHY.
Physical framing and coding overhead are link-specific and accounted separately.
The paper will not call this traffic a standardized CAM.

**On HARQ.** Feedback HARQ is excluded, and the reason is now quantified rather
than asserted. At 5.9 GHz the system is in FR1, where NR permits only 15/30/60
kHz subcarrier spacing. A HARQ round trip costs several slots; at 60 kHz the
realistic four-slot turnaround is exactly 1.00 ms and at 30 kHz it is 2.00 ms.
Even at 3 ms this leaves little room, and the design deliberately keeps
single-shot-per-leg semantics so that **medium diversity remains the only
diversity available**. This is the property that makes the selection problem
non-trivial, and it must be stated in the paper as a scope decision.

### 1.2 Secondary reliability profile

A \(10^{-5}\) frontier at the **same payload and deadline**
(`configs/service/ev2x_300B_3ms_1e-5.yaml`), run for the learned controller,
Always-DUP, the strongest deterministic policy, and the oracle.

\(10^{-5}\) is a declared frontier, not the headline. The asymmetry is
deliberate: achieving \(10^{-5}\) under a \(10^{-4}\) headline upgrades the
claim, whereas freezing \(10^{-5}\) and missing it would force rewriting the
contract, configs, tests, curriculum, and the paper's framing.

A five-nines result will be claimed only when its one-sided, correlation-aware
confidence bound is below \(10^{-5}\). Otherwise it is reported as an
exploratory frontier.

### 1.3 What the work will and will not claim

The intended claim:

> A causal geometry-aware primal-dual policy can reduce transmission activation
> cost relative to unconditional duplication while meeting an empirically
> evaluated per-density \(10^{-4}\) deadline-miss constraint in a validated
> urban RF/VLC simulation.

The paper will **not** claim:

- a formal hard-safety guarantee from PPO;
- certified five-nines reliability;
- full 3GPP conformance;
- that PPO, RF/VLC aggregation, or packet duplication is individually novel;
- that a synthetic orthogonal grid is a calibrated model of Manhattan traffic;
- that the mobility model reproduces measured NYC speeds or volumes;
- that RF and VLC failures are independent;
- that every negative result is automatically publishable.

The defensible novelty is the conjunction of:

1. **geometry-driven** shared urban mobility driving RF state, VLC alignment,
   and third-vehicle blockage from one vehicle set;
2. causal and age-aware RF/VLC observations with predicted blockage probability;
3. per-packet `{RF, VLC, DUP}` control under an explicit reliability budget;
4. trajectory-level rare-event and burst-failure evaluation.

Novelty language uses "to the best of our knowledge" and is restricted to the
reviewed and updated literature search.

---

## 2. Standards and application positioning

Three reference points remain separate:

- 3GPP TR 38.913: general URLLC reference of 32 bytes, 1 ms, \(10^{-5}\); eV2X
  reference of 300 bytes, 3–10 ms, \(10^{-5}\).
- 3GPP TS 22.186: cooperative collision avoidance at 2,000 bytes, 10 ms, 99.99%.
- The same TS: emergency trajectory alignment at 2,000 bytes, 3 ms, 99.999%.

Our headline takes **payload and deadline from the eV2X row** and the
**reliability class from TS 22.186 advanced driving**. No single row specifies
300 B / 3 ms / \(10^{-4}\); the tuple is a controlled research profile.

**Required wording in the paper:**

> We consider 300-byte compact cooperative safety packets generated at 10 Hz
> and impose a 3-ms radio-interface delivery deadline, following the eV2X
> reference profile. The \(10^{-4}\) headline reliability budget is aligned
> with the 99.99% reliability class used by advanced-driving services, while
> the complete parameter tuple is a controlled research profile rather than a
> conformance claim.

Primary sources:

- TR 38.913: <https://www.etsi.org/deliver/etsi_tr/138900_138999/138913/18.00.00_60/tr_138913v180000p.pdf>
- TS 22.186: <https://www.etsi.org/deliver/etsi_ts/122100_122199/122186/18.00.01_60/ts_122186v180001p.pdf>

---

## 3. Research questions and hypotheses

**RQ1 — Feasibility.** For which traffic densities can any policy, including
Always-DUP and the oracle, meet the \(10^{-4}\) budget?

**RQ2 — Duplication economy.** Within the feasible region, can causal selective
duplication reduce normalized activation cost relative to Always-DUP without
violating the constraint?

**RQ3 — Value of geometry prediction.** Does noisy, age-aware blockage
forecasting improve the reliability-cost frontier over policies using only
current and historical link measurements?

**RQ4 — Failure dependence.** How do marginal RF failure, marginal VLC failure,
and joint failure vary with density, pair separation, intersection context, and
predicted occlusion?

**RQ5 — Ultra-reliability frontier.** Under which densities, if any, is
\(10^{-5}\) statistically supportable?

Hypotheses are directional in the manuscript. Numeric internal predictions,
with the decision each outcome triggers, live in `research/HYPOTHESES.md` and
are never quoted in the paper.

No expected percentage saving, density threshold, or spatial behaviour will be
written into the abstract before results exist.

---

## 4. Mobility model

**This section replaces v2 §4 entirely.** Implemented in
`src/grail_v/mobility/grid_network.py`, `car_following.py`, `grid_signals.py`,
and `grid_simulator.py`, and specified in
`research/MOBILITY_MODEL_V2_PROPOSAL.md`.

### 4.1 Network

A rectangular Manhattan-style grid, one lane per direction:

| Parameter | Value |
|---|---:|
| Grid | 6 avenues × 12 cross streets |
| Avenue spacing | 244 m |
| Cross-street spacing | 61 m |
| Lanes per direction | 1 |
| Junctions | 72, of which 40 interior are signalized |
| Directed edges | 252 |
| Total lane length | **37,332 m** |
| Speed limit | 11.18 m/s (25 mph) |
| Mobility step | 50 ms |
| Warm-up | 300 s |
| Recorded trace | 900 s |

The 244 × 61 m spacing represents the characteristic long, rectangular
Manhattan block. The one-lane-per-direction design is intentionally controlled
and is not a lane map of Midtown.

Buildings are the complements of the street grid, so RF NLOS classification is
exact by construction and needs no imported polygon file.

**A note on lane length.** The model has no junction radii, so its lane length
equals the nominal geometric value exactly. A generated SUMO network of the
same grid measured 34,574 m against a 37,332 m nominal — a 7.4% gap that would
have exceeded the 5% density tolerance had the wrong figure been used as the
density denominator.

### 4.2 Vehicle motion

Longitudinal motion follows the **Intelligent Driver Model** (Treiber,
Hennecke and Helbing, *Phys. Rev. E* 62(2), 2000):

\[
\dot v = a\left[1-\left(\frac{v}{v_0}\right)^{\delta}-\left(\frac{s^*}{s}\right)^{2}\right],
\qquad
s^{*}=s_0+vT+\frac{v\,\Delta v}{2\sqrt{ab}}
\]

| Parameter | Value | Status |
|---|---:|---|
| Desired speed \(v_0\) | 11.18 m/s | from the speed limit |
| Max acceleration \(a\) | 2.6 m/s² | vehicle mixture |
| Comfortable deceleration \(b\) | 4.5 m/s² | vehicle mixture |
| Minimum gap \(s_0\) | 2.5 m | vehicle mixture |
| **Desired time headway \(T\)** | **1.2 s** | **declared assumption — see §4.7** |
| Exponent \(\delta\) | 4 | original formulation |

IDM is collision-free by construction and reproduces stop-and-go queueing. It
is chosen because it is the standard citable reference law and is about ten
lines of code.

**A red signal is supplied to the same equation as a stationary leader at the
stop line.** Queue formation therefore requires no separate mechanism, which is
what produces the intersection-versus-mid-block contrast that hypothesis H3
depends on.

Leaders are resolved **across junctions**: when no vehicle is ahead on the
current edge, the rearmost vehicle on the next edge of the route is used, with
the gap measured across the intersection. Without this a vehicle crosses a
junction and lands inside a queue waiting on the far side.

### 4.3 Signals

Fixed-time, two-phase, 90 s cycle with a 3 s yellow interval, staggered by half
a cycle on alternating junctions. Signal state is a pure function of
`(time, junction)`; no vehicle influences a signal and there is no actuated
control.

### 4.4 Density is exact, not calibrated

The active vehicle count is set directly:

\[
N=\rho_L\times(\text{total lane length in km})
\]

When a vehicle leaves the grid a replacement is injected at a boundary entry
that has room for it. **The entire closed-loop demand-calibration subsystem of
v2 §4.2 is deleted**, along with its evaluation budget and failure modes.

Injection is deferred rather than forced when every boundary entry is occupied,
because forcing would place overlapping footprints that the occlusion geometry
cannot interpret. Realised density is therefore reported, never assumed.

Training densities are \(\rho_L\in\{10,20,30\}\) vehicles/lane-km. The choice
is measured, not conventional — see §4.5.

**Measured, 900 s after a 300 s warm-up:**

| Target \(\rho_L\) | Realised | Error | Episodes | Usable |
|---:|---:|---:|---:|---:|
| 10 | 9.99 | 0.10% | 5,364 | 5,354 |
| 20 | 20.01 | 0.05% | 14,510 | 14,489 |
| 30 | 30.00 | 0.00% | 19,071 | 19,049 |

### 4.5 The measured fundamental diagram

The three training densities are not round numbers chosen by taste; they span
three qualitatively distinct regimes, which the measured speed-flow relation
confirms:

**Re-measured after the junction fix of §4.6.5.** Requiring a driver to keep
the intersection clear costs throughput, so the whole relation moved and the
earlier figures are superseded:

| \(\rho_L\) | Speed | \(v/v_{\text{free}}\) | Flow (veh/h/lane) | Stopped | Regime |
|---:|---:|---:|---:|---:|---|
| 5 | 5.62 | 0.50 | 101 | 37.4% | free |
| 10 | 5.65 | 0.51 | 203 | 37.2% | free |
| 15 | 5.37 | 0.48 | 290 | 32.6% | undersaturated |
| 20 | 4.38 | 0.39 | 316 | 43.4% | **approaching capacity** |
| 25 | 3.54 | 0.32 | 319 | 49.4% | **at capacity** |
| 30 | 2.95 | 0.26 | 318 | 53.4% | **at capacity** |
| 40 | 1.84 | 0.16 | 265 | 66.0% | **oversaturated** |

Flow now saturates near **318 veh/h/lane between \(\rho_L=20\) and 30** and
falls beyond it, against 550 veh/h/lane between 40 and 60 before. Superseded
values, for the record: 5.85 / 5.44 / 4.81 / 3.72 / 2.59 m/s at
\(\rho_L = 5, 20, 30, 40, 60\) and flows of 105 / 392 / 520 / 536 / 558.

The **holding capacity of the network is 65.3 veh/lane-km** (2,436 vehicles),
down from 72 because the first slot on every edge is now reserved so a body
does not lie across the junction the edge leaves. A density beyond capacity is
rejected at construction rather than silently under-filled.

**Consequence for §4.5.1, which must be re-checked.** The training band was
chosen because both impairments kept responding to density up to
\(\rho_L\approx30\). Capacity now arrives at 20–25 rather than 40, so
\(\rho_L=30\) sits at capacity rather than in free flow. The band still spans
free flow to capacity, which is arguably a better spread than before, but the
justification rests on a blockage sweep measured on the old engine. **Re-run
that sweep from the regenerated traces before treating §4.5.1 as settled.**

### 4.5.1 Why the training densities are 10 / 20 / 30

The original \(\{20,40,60\}\) was inherited, not measured, and was abandoned
because it destroyed the phenomenon under study (risk R4a). The band that
replaced it was justified by a sweep showing both impairments climbing to
\(\rho_L\approx30\) and then flattening. **That justification is withdrawn.**
Its blockage column was dominated by the shared-centreline artefact of §4.6.3,
and the capacity point it relied on moved when §4.6.5 was fixed. Superseded,
for the record: 5.3 / 12.2 / 22.5 / 30.6 / 26.2 / 30.7% blocked at
\(\rho_L = 5, 10, 20, 30, 40, 60\).

**The band survives on a different and stronger argument.** Measured on the
corrected traces, the two impairments do not merely differ in driver — they
move in **opposite directions**:

| \(\rho_L\) | V-VLC unavailable | Neighbours ≤200 m | Weak link |
|---:|---:|---:|---|
| 10 | **3.41%** | 54 | optical |
| 20 | 1.87% | 105 | — |
| 30 | **1.01%** | 199 | radio |

Optical availability *improves* with density, 3.4× across the band, because
closer spacing shortens the optical path so fewer paths reach across a
junction. RF load *worsens*, roughly 3.7×, because neighbour count is a
headcount. At \(\rho_L=10\) the optical link is the weaker one; at
\(\rho_L=30\) the radio is.

This is a better foundation than the one it replaces. The earlier band was
chosen because both impairments responded to density, which is a weak
complementarity argument: if both links degrade together, diversity buys
little. Here **no fixed link choice can be right at both ends of the band**,
which is the condition RQ4 actually needs, and it now holds by mechanism rather
than by coincidence.

**The optical signal is not on the density axis at all.** Aggregate
availability spans only 96.6–99.0%, while the same quantity conditioned on
whether the path crosses a junction spans 0.25% to 32.6% (§4.6.1). Density
stratifies the **radio** load; the junction condition stratifies the
**optical** link. The per-density constraint \(J_{c,k}\) should be read
accordingly.

**Consequences for the generalization tests:**

- Interpolation: **15 and 25 veh/lane-km**, inside the band.
- Extrapolation: **40 veh/lane-km**, past capacity. The original 70 is
  abandoned — at 97% of holding capacity realised density falls 10.2% below
  target, failing the tolerance twofold.

**Open.** Capacity now arrives at \(\rho_L\approx20\)–25 rather than 40
(§4.5), so \(\rho_L=30\) sits at capacity rather than in free flow and 53% of
its vehicles are stopped. The band still spans free flow to capacity, which is
a legitimate spread of regimes, but whether a fourth point below 10 would
better exercise the optical side is unresolved and should be settled before
M7.

### 4.6 Vehicles and tagged pairs

Mixture: passenger car 90% (4.5 × 1.8 × 1.5 m), van/SUV 7% (5.2 × 2.0 × 2.0 m),
bus/truck 3% (11.0 × 2.5 × 3.25 m). Heavy-vehicle shares of 0%, 5% and 10% are
used for blockage sensitivity.

The tagged transmitter follows the tagged receiver: same direction, shared
upcoming path, **separation 5–40 m**, stratified into three equal strata
derived from that window (5–16.7, 16.7–28.3, 28.3–40 m). Episodes end when the
pair leaves the range continuously for one second, when the leader leaves the
follower's remaining path, or at the 60 s cap.

**The pair must be the immediate leader-follower**
(`TaggedPairConfig.require_adjacent`). This is not cosmetic. Allowing any two
same-lane vehicles inside the window put another vehicle in the optical path
**97–100% of the time at 40 and 60 veh/lane-km**, because mean spacing at those
densities is smaller than the window, so the pair could not help but straddle
other traffic. V-VLC had no availability, DUP would have cost 2 to deliver what
RF alone delivers, and RQ2 had nothing to decide.

**Vehicles are never repositioned to manufacture a pair**, and shorter eligible
segments are never padded.

**"Same route" means shared upcoming path, not identical itinerary.** Two
vehicles following one another normally share a segment and part later.
Requiring identical routes is what produced zero episodes under the previous
backend, since anonymous route identifiers could never match.

**Measured episode yield** from one 900 s trace per density:

| \(\rho_L\) | Episodes | Usable | Degenerate | Mean duration | Ends at cap |
|---:|---:|---:|---:|---:|---:|
| 10 | 5,364 | 5,354 | 10 (0.2%) | 23.8 s | 11.5% |
| 20 | 14,510 | 14,489 | 21 (0.1%) | 25.4 s | 14.2% |
| 30 | 19,071 | 19,049 | 22 (0.1%) | 39.7 s | 47.1% |

A degenerate episode is one of zero duration, produced when an endpoint leaves
the network before a second observation. It is counted, not silently dropped.

Note that `blocker_fraction` in the report is now ≈0.01 and effectively
vestigial: with adjacency required, no *same-lane* vehicle can be between the
pair. Real occlusion comes from cross-traffic and is computed by the geometry
engine per timestep, not by the pair extractor.

### 4.6.1 The complementarity evidence

This is the measurement the whole contribution depends on, so it is recorded
here rather than left to be rediscovered.

**Provenance.** Measured by the M2 geometry engine — oriented rectangles,
headlamp-to-photodiode endpoints, height test, photodiode acceptance cone,
spatial index — on the traces regenerated 2026-08-04 under configuration hash
`92bf9cb5`, 300 sampled frames per trace, one trace per density. It supersedes
two earlier attempts, both contaminated: a point-to-segment approximation, and
a phase-3 run on traces carrying the §4.6.3 and §4.6.5 defects. Superseded
aggregate availability, for the record: 90.9 / 71.0 / 85.9% and then 88.1 /
77.8 / 83.9% at \(\rho_L = 10, 20, 30\).

"Unavailable" means occluded **or** outside the photodiode's acceptance cone.

**Aggregate availability and RF load:**

| \(\rho_L\) | Instants | Occluded | Out of FOV | Unavailable | **Available** | Neighbours ≤200 m |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 39,664 | 0.57% | 2.87% | 3.41% | **96.59%** | 54 |
| 20 | 136,580 | 0.63% | 1.28% | 1.87% | **98.13%** | 105 |
| 30 | 259,377 | 0.41% | 0.62% | 1.01% | **98.99%** | 199 |

**The aggregate is the wrong summary, and this is the central result.**
Conditioned on whether the optical path crosses a junction, the same quantity
is bimodal:

| \(\rho_L\) | Spanning | Unavailable | Mid-block | Unavailable | **Lift** | Exposure |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 3,602 | **32.57%** | 36,062 | **0.50%** | 65.6× | 9.08% |
| 20 | 6,353 | **32.10%** | 130,227 | **0.39%** | 81.3× | 4.65% |
| 30 | 6,537 | **30.50%** | 252,840 | **0.25%** | 121.1× | 2.52% |

The two reconcile exactly, which is the check that they are one measurement:
\(0.0465\times32.10 + 0.9535\times0.39 = 1.87\%\) at \(\rho_L=20\).

Read that as: **the conditional risk is ~31% at every density**, and what
density changes is *exposure* — how often a pair spans a junction at all, which
falls as closer spacing shortens the optical path. "V-VLC is 98% available" and
"V-VLC fails a third of the time" are both true of this system; which applies
is decided by an observable condition.

**Two independent mechanisms produce the junction risk**, and both are real:

| \(\rho_L\) | | Occluded | Out of FOV | FOV alone |
|---:|---|---:|---:|---:|
| 10 | spanning | 3.30% | 29.43% | 29.26% |
| | mid-block | 0.30% | 0.22% | 0.19% |
| 20 | spanning | 6.89% | 25.58% | 25.20% |
| | mid-block | 0.32% | 0.09% | 0.07% |
| 30 | spanning | 8.05% | 22.78% | 22.46% |
| | mid-block | 0.22% | 0.04% | 0.03% |

Junction lift on **occlusion alone** is 10.9× / 21.5× / 37.1×; including
misalignment it is 65.6× / 81.3× / 121.1×.

**Misalignment is physics, not a bookkeeping error.** An earlier version of
this section called it an artefact of pair extraction. That was wrong and is
withdrawn. The continuation loop already ends a pair with `route_diverged` when
the leader leaves the follower's path; what survives is the case where **both
share the route and the leader turns first**, so for a second or two the leader
sits perpendicular to its follower with its photodiode swung away. A deployed
V-VLC system loses that link at exactly that moment, and the leader is still
the vehicle immediately ahead on the follower's own path — still the one that
must receive the safety message. Adding a heading re-check would delete a real
failure mode and inflate availability, which is selection bias in the
flattering direction.

The two mechanisms also move oppositely with density: occlusion at junctions
rises 3.30 → 8.05% as cross traffic thickens, while misalignment falls
29.43 → 22.78% as queueing leaves fewer turns completed per unit time.

**V-VLC unavailable, by separation:**

| Separation | \(\rho_L=10\) | \(\rho_L=20\) | \(\rho_L=30\) |
|---|---:|---:|---:|
| 5–10 m | 1.6% | 0.6% | 0.3% |
| 10–20 m | 9.0% | 5.2% | 3.7% |
| 20–30 m | 3.2% | 6.6% | 7.0% |
| 30–40 m | 3.5% | 4.5% | 5.4% |

Separation is a far weaker predictor than junction geometry and is
non-monotonic, because it conflates two effects: a longer path is more likely
to be cut, but a pair held at long separation is typically in free flow rather
than queued at the junctions where crossing traffic is. **Prefer the junction
condition; stratify by separation when comparing across densities**, as §13.6
already requires.

**Three properties follow, each mapping to a research question:**

1. **V-VLC intermittency is conditional, not aggregate** (RQ2). At 98%
   availability there is little for duplication to exploit on average; at a
   junction there is a 31% risk on 2.5–9% of packets. Duplicating only there
   pays the cost-2 premium on a small minority of packets while covering the
   overwhelming majority of the risk.
2. **The risk is predictable from lawful state** (RQ3, H3). A 65–121× lift on a
   condition derived from own pose and a road map, with two independent causes
   — cross traffic in the box, and a leader turning out of the cone — both
   forecastable 200 ms ahead. This is what the forecast field exists to carry.
3. **The impairments have opposing density gradients** (RQ4). Optical
   availability improves with density while RF load worsens; see §4.5.1.

### 4.6.2 Where the two links fail together, and where they do not

Measured on the same instants as §4.6.1, cross-tabulating RF propagation class
against V-VLC availability.

**RF propagation class:**

| \(\rho_L\) | LOS | NLOSv | NLOS | Obstructed |
|---:|---:|---:|---:|---:|
| 10 | 98.02% | 0.27% | **1.71%** | 1.98% |
| 20 | 98.74% | 0.31% | **0.95%** | 1.26% |
| 30 | 99.23% | 0.20% | **0.57%** | 0.77% |

**This supersedes the argument that stood here, which is withdrawn.** The
earlier version claimed the two links are blocked by the same vehicle body,
with RF surviving it as extra path loss — obstruction coupled 4–9× over
independence, with RF obstructed 10.2% and 23.2% of the time. Those figures
came from the §4.6.3 traces and were an artefact. Vehicle blockage of the radio
link is now **0.20–0.31%**. There is almost no NLOSv left to build an argument
on.

What obstructs RF is instead **buildings**, by a factor of 3–6× over vehicles,
and by the same geometry that produces the optical misalignment: once the
leader has rounded a corner, the straight line between antennas cuts the block.

**Joint failure:**

| \(\rho_L\) | Both impaired | Exactly one | **Share where exactly one** | Lift over independence |
|---:|---:|---:|---:|---:|
| 10 | 1.177% | 3.03% | **72.0%** | 17.5× |
| 20 | 0.820% | 1.49% | **64.5%** | 34.7× |
| 30 | 0.502% | 0.78% | **60.8%** | 64.2× |

**The share where exactly one link is impaired is the number that matters, and
it improved from roughly 20% to 61–72%.** Under the contaminated traces four
impairments in five struck both links at once, which is close to fatal for a
diversity argument. Now three in five to nearly three in four strike only one,
which is precisely the condition duplication exists to exploit.

**Report the lift, but do not lead with it.** It rose to 17–64× while the thing
it measures fell by an order of magnitude, because when both marginals are near
1% independence predicts ~0.01% and any shared cause looks enormous in ratio.
Absolute co-occurrence fell from 19.2% to 0.82% at \(\rho_L=20\). Both belong
in the paper; the absolute figure is the honest headline.

**Consequences:**

1. **The NLOSv path-loss model is no longer load-bearing.** M3 must still
   implement it, but at 0.2–0.3% occurrence it can no longer decide the
   hybrid's value either way. The decisive RF parameter is the **collision
   model of §7.2**, which remains undefined.
2. **Gate 3's prior changes.** It should test joint *failure* against a
   measured obstruction co-occurrence of 0.5–1.2%, not the 4–9× coupling this
   section used to assert. Coincident obstruction is now rare; coincident
   *failure* is what the contribution cannot survive, and only the channel
   models can measure it.
3. **A declared asymmetry in the obstruction tests.** `is_obstructed` tests
   vehicles only, so V-VLC occlusion never considers buildings, while RF
   classification does. For the turning case this changes no verdict, because
   misalignment already marks those instants unavailable. It is recorded here
   because "VLC occluded" and "RF obstructed" are therefore not measuring the
   same set of obstacles, and a like-for-like comparison must say so.

### 4.6.3 Opposing carriageways are not separated — a blocking defect

Found by the M2 geometry engine during phase 5, on 2026-08-04. This is the
engine working as intended: it was built to measure the phenomenon, and the
first thing it measured was that the phenomenon was not real.

**The defect.** `mobility/grid_network.py` gives each street segment two
directed edges that share a single centreline. `GridEdge.position_at` returns
the same points for both, so northbound and southbound traffic occupy exactly
the same line. Confirmed on `synthetic-d20-train-000` at \(t=0\):

```
veh_0000050  edge=E7F7  heading=  0°  spans x 1003.45 → 1007.95  at y=427.00
veh_0003814  edge=F7E7  heading=180°  spans x 1005.02 → 1009.52  at y=427.00
```

Two vehicles sharing 2.93 m of road, head to head. Roughly **74 such overlaps
per frame** at \(\rho_L=20\). The existing invariant
`test_no_two_vehicles_overlap_on_the_same_edge` compares vehicles on the same
`edge_id` only, so an opposing pair was never a candidate.

**What it does to the measurements.** Classified by relative heading, blockers
of the optical path are:

| Blocker | Share |
|---|---:|
| Oncoming, 180° | **93.9%** |
| Cross-traffic, 90° | 5.1% |
| Same direction | 1.0% |

Every oncoming blocker sits at a lateral offset of **0.000 m** from the pair's
own axis. A real opposing lane is about 3.5 m off axis and would not intersect
a headlamp-to-photodiode path running along the transmitter's own lane.

**Corrected magnitude**, \(\rho_L=20\), oncoming blockers excluded:

| | As modelled | Corrected |
|---|---:|---:|
| Optical path blocked | 27.1% | **1.8%** |
| Out of field of view | 1.3% | 1.3% |
| **V-VLC available** | 72.9% | **≈98.2%** |

**Consequences.**

1. §4.6.1, §4.6.2 and §14.1's worked numbers are all built on the artefact.
2. The fix changes trajectories, so all 21 traces regenerate and the config
   hash moves from `5e42a2ba` to `92bf9cb5`. This is the third mobility retune
   and exactly the case risk R4b anticipated.

**The fix, and what it revealed.** `GridNetworkSpec` now carries
`lane_width_m`, and each direction runs `carriageway_offset_m` to the right of
the street centreline, so opposing lanes are 3.5 m apart. Measured on a fresh
\(\rho_L=20\) trace:

| | Shared centreline | Separated carriageways |
|---|---:|---:|
| Closest opposing approach | 0.000 m | **3.500 m** |
| Blockers that are cross-traffic | 5.1% | **73.8%** |
| Blockers that are oncoming | 93.9% | 6.6% |
| Optical path blocked | 27.1% | **1.58%** |
| Out of field of view | 1.3% | 1.01% |
| **V-VLC available** | 72.9% | **97.95%** |

**The junction signal is far stronger than the contaminated measurement
suggested.** Measured here on one fresh \(\rho_L=20\) trace, before the §4.6.5
fix; **§4.6.1 carries the settled figures** across all three densities:

| Path position | Instants | V-VLC unavailable |
|---|---:|---:|
| Spans a junction | 1,651 | 27.01% |
| Mid-block | 24,690 | 0.38% |
| **Lift** | | **71.7×** |

Mid-block is essentially clean. Blockage is almost entirely explained by a
single, observable, predictable condition — which §4.6.1 later confirms at
30.5–32.6% spanning against 0.25–0.50% mid-block, a 65–121× lift.

**What this does to the four conditions of §4.6.4.** Condition C
(predictability) is far better than assumed: a 71.7× lift on a feature derived
from own pose and a map is close to an oracle. Condition A (intermittency) is
weak in the aggregate at 98% availability, but is **not** weak conditionally —
the policy faces a genuine 27% risk whenever it spans a junction, roughly 6% of
the time. That is precisely the state-dependent structure the contribution
wants: use one link mid-block, duplicate at junctions, and beat Always-DUP on
cost while holding reliability. Condition D remains the open one. It needs a
link budget on **both** legs, so M3 and M4 together, and the feasible-region
characterisation itself is Gate 3 at M5.

The hybrid also relaxes the RF requirement by ≈49× at this availability rather
than the 4.5–8.4× originally computed; §14.1 settles this at 29–99× across the
band, and at 256× mid-block against 3.1× at a junction.

### 4.6.5 Vehicles passed through one another at junctions — a second blocking defect

Found on 2026-08-04 by the all-pairs footprint test written to close the gap
§4.6.3 exposed, and found on that test's **first run**. §4.6.3 fixed opposing
carriageways; this is the same class of error one level down.

**What the mandatory test actually checked.** §16.3 requires "no overlapping
vehicle footprints in any recorded frame". The implementation compared
vehicles sharing an `edge_id`, so it tested lane-keeping and nothing else. The
world-coordinate, all-pairs version found overlaps immediately:

| | \(\rho_L=10\) | \(\rho_L=20\) | \(\rho_L=30\) |
|---:|---:|---:|---:|
| Overlapping pairs per frame | 4.51 | 10.72 | 27.45 |
| Vehicles involved | 2.4% | 2.9% | 4.9% |
| Median penetration | 0.46 m | 0.32 m | 0.35 m |
| Max penetration | 1.80 m | 2.00 m | 2.00 m |

**100% lay within 12 m of a junction**, median 3.4 m from the centre. At
\(\rho_L=20\), 61% involved a stopped vehicle and the per-junction rate was
similar at signalized and unsignalized junctions, which pointed away from
signal timing and at the absence of any junction occupancy rule.

**Four distinct causes**, each uncovered by fixing the one before it:

1. **Injection placed bodies inside junctions.** `offset_m` is the front
   bumper, so injecting at 0 left a 4.5 m body extending backwards through the
   junction the edge leaves; two vehicles injected at one junction overlapped.
2. **The stop line stood at the junction centre.** `edge.length_m` *is* the
   centre, so a red light parked a front bumper in the middle of the
   intersection. Setting it back by the carriageway offset alone was still
   wrong: the crossing street reaches \(1.75 + 1.25 = 3.0\) m from the centre
   once half a vehicle width is counted, and the residual 1.25 m of overhang
   was visible as the ~1 m median penetration that survived the first attempt.
3. **No conflict arbitration.** Signals separate the two axes at the 40
   interior junctions but arbitrate nothing at the 32 unsignalized boundary
   junctions and nothing between turning movements sharing one green. Adding
   reservations was not enough on its own: a vehicle that had crossed was
   labelled with the movement for its *next* junction, so two genuinely
   conflicting crossers could each be granted the same box.
4. **IDM is not collision-free.** A leader braking hard at a stop line,
   sampled at 50 ms, leaves a follower's front centimetres past its tail.

**The fix**, all in `mobility/grid_simulator.py`: injection and initial
placement start clear of the junction; the stop line stands at
`carriageway_offset + widest_half_width`; a vehicle may not enter unless it can
*exit* (keep clear); crossings hold a persistent reservation, requested a full
braking distance out so a refusal is physically obeyable and held until the
tail clears; and a following-distance clamp runs before and after the crossing
step.

**Result**, 100 frames at the production 300 s warm-up:

| \(\rho_L\) | Before | After |
|---:|---:|---:|
| 10 | 451 | **0** |
| 20 | 1,072 | **1** |
| 30 | 2,745 | **2** |

A 99.9% reduction, deepest residual 0.42 m. It is **not zero**; see §4.7 item
7. The throughput cost is recorded in §4.5 and the capacity change with it.

### 4.7 Declared assumptions and known limitations

These are modelling choices the paper must state, not hide.

1. **IDM desired time headway \(T = 1.2\) s** is a free parameter that sets the
   speed-density relation and therefore the capacity in §4.5. It requires a
   source or a declared sensitivity band before Gate 2.
2. **Signals are staggered but not progressed.** Free-flow speed tops out at
   52% of the limit even at \(\rho_L=5\), with 38% of vehicles stopped in
   near-empty traffic. Real Manhattan avenues run green waves and are faster.
   This is the largest realism gap in the model and must be disclosed.
3. **No lane changing or overtaking.** With one lane per direction a stopped
   heavy vehicle blocks everything behind it.
4. **No multi-lane roads, no actuated signals, no pedestrians, no parking.**
5. **No calibration against measured NYC traffic counts.** The real-map
   robustness test of v2 §4.5 is **removed from scope**, not deferred: it
   required a SUMO network import that no longer exists.
6. **The grid understates the cost of a narrow optical field of view.**
   `vlc.receiver_fov_deg` is the receiver semi-angle \(\psi_c\); the headline
   uses 60° and the \(10^{-5}\) frontier uses 30° via
   `configs/channel/vlc_vehicle_concentrated.yaml`. A 30° semi-angle still
   allows 8.9 m of lateral offset over a 15.5 m optical path against roughly
   3 m of lane width, so the model charges it almost nothing — measured
   availability barely moves while the link budget moves about 10 dB. That
   asymmetry is an artefact of items 2–4: straight streets, one lane, no
   grade, no lane changing, so none of the road curvature, braking pitch or
   lateral dynamics that are the real price of a narrow cone can appear.
   **The 30° sensitivity is therefore optimistic and must be reported as
   such.** The value itself is also unsourced, like item 1.
7. **A small residue of vehicle footprints still overlap at junctions.**
   Measured **on the generated traces**, 300 sampled frames each: 0.093, 0.130
   and 0.097 overlapping pairs per frame at \(\rho_L=10, 20, 30\), affecting
   0.05%, 0.03% and 0.02% of vehicles, deepest penetration 0.42 m — roughly a
   quarter of a car width. What remains is a same-step race between two
   crossings rather than a systematic error, and it is bounded by an asserted
   test (`test_vehicle_footprints_barely_overlap_at_generated_densities`)
   rather than left to drift.

   These figures replace an earlier claim of 0.00 / 0.01 / 0.02 per frame,
   which came from 100 frames of a single seed run directly against the
   simulator. The traces use per-trace derived seeds over 900 s, and the rate
   is roughly ten times higher; the first measurement was an unlucky
   generalisation from a lucky sample. **The trace-measured value is the one
   that counts**, because the traces are what every downstream stage reads.

   Disclosed because §16.3 states the invariant without qualification and the
   achievement is a bound, not zero. The contamination risk is low — an
   overlapping pair is two real bodies at real junction positions, so occlusion
   counts one blockage where it should count two — but it is not nil, and a
   reviewer is entitled to the number.

### 4.8 Determinism and reproducibility

One seeded generator per trace, derived through the project's named-stream
mechanism. The same seed and configuration reproduce trajectories bit-exactly,
which is what allows a trace to be regenerated rather than stored indefinitely
and what makes the two-pass artifact writer of §16.2 safe.

---

### 4.9 Making the environment answer the research question

Decided 2026-08-04, after §4.6.1 was restated on corrected traces.

**The problem.** The measured environment is more benign than the questions
asked of it. V-VLC is available 96.6–99.0%, RF has 41.7 dB of thermal margin at
5–40 m and is 98–99% line of sight, and the residual optical risk concentrates
at junctions — a condition derivable from own pose plus a road map. Three
consequences follow, and two of them are fatal to the framing rather than to
the result:

- **RQ3 is at risk.** The forecast's information content is very nearly
  `path_spans_junction`, which is a *current* observable rather than a
  prediction. A policy with junction context and no forecast would do nearly as
  well.
- **H7 is at risk.** With risk that predictable and availability that high,
  history and feature age buy little, and §6.3's fallback — describe the problem
  as contextual — becomes the likely outcome.
- **A third of the action space is dead.** V-VLC alone fails at
  \(2\times10^{-2}\), 200× the budget, so VLC-only is never feasible and the
  live decision is RF versus DUP.

Together these are risk **R2** — "PPO provides no advantage over a contextual
rule" — close to firing. The environment, not the algorithm, is what would
cause it.

**The goal is decorrelated impairment, not pessimism.** An environment where
both links fail together is worse than a benign one: it destroys the hybrid
argument instead of supporting it. Every change below adds an axis on which
*one* link suffers. The target landing zone is **V-VLC available 75–90%**, with
blockage split between predictable junctions and unpredictable cut-ins, leaving
4–7× of relaxation for §14.1.

**Stage 1 — mobility, one regeneration.**

1. Two lanes per direction with MOBIL lane changing. Cut-ins are the blockage
   the current model excludes *by construction*, and unlike junctions they are
   not derivable from a map — which is what gives the forecast information
   beyond current observables.
2. Adjacency becomes a formation rule, not a permanent one. A pair stays
   together when a vehicle cuts between them; `has_intervening_vehicle` stops
   being vestigial.
3. Green-wave signal offsets. Free-flow speed is 52% of the limit, the largest
   declared realism gap (§4.7 item 2), and progression also raises capacity,
   which re-opens the higher densities as a meaningful band.
4. Pedestrian and cyclist crossings at junctions: Poisson arrivals, crossing
   only where they would matter, tall enough to cut a 0.7 m beam.
5. Re-derive the density band from a fresh sweep. §4.5.1's justification is
   already withdrawn.

**Stage 2 — link envelope.** Separation window 5–40 m becomes 5–100 m. Optical
power falls as \(1/d^2\) while RF barely notices at these ranges, so the far
end becomes a clean VLC-bad / RF-fine regime on an axis the policy observes
directly. Then restate §4.6.1.

**Stage 3 — channels (M3, M4).** NR-V2X Mode 2 with sensing-based SPS, resource
reselection, **half-duplex loss** and in-band emissions; §7.2's bands chosen
from literature before any value is seen to help. Ambient becomes a first-class
condition: clear night as headline, **bright day** and **fog** as regimes that
impair V-VLC and leave RF untouched.

**Stage 4 — feasibility (M5, Gate 3).** Condition D and joint-failure
correlation, on the environment as rebuilt.

**Out of scope, and why.** Road grade and curvature need three-dimensional
geometry the planar model does not carry. Calibration against measured NYC
counts was removed from scope, not deferred. Exact-zero footprint overlap is
bounded and declared in §4.7 item 7.

**Acceptance.** Stage 1 is complete when a fresh sweep shows V-VLC blockage
with a *non-map-derivable* component — that is, when mid-block unavailability
is materially above the 0.25–0.50% the single-lane model produces — and Gate 1
still passes at the re-derived densities.

**The tripwire.** The hybrid gain is capped at \(1/P_\text{out}\): 49× at
today's 2%, 6.7× at 15%, 2.9× at 35%. Overshooting the pessimism makes
\(10^{-4}\) unreachable and turns the result into H1's "infeasible" branch.
Realistic, not maximal.

## 5. Shared geometry and hidden simulator state

The exact model state contains all vehicle positions, dimensions, headings,
speeds and edges; building rectangles; signal phases; exact RF propagation
class; exact optical line intersection and field-of-view status; shadowing and
fading realizations; resource-collision realization; and counterfactual success
outcomes for all actions.

This is used to generate outcomes and oracle results. It is **not** exposed to
the learned or deterministic deployable policies.

### 5.1 RF geometry classes

The tagged RF link is classified from common geometry as **LOS**, **NLOSv**
when blocked by a vehicle, or **NLOS** when a building obstructs the link. The
geometry engine must be deterministic for a fixed trace and must have tests for
boundary contact, partial rectangle intersection, heading rotation, and
building corners.

### 5.2 VLC geometry

The optical link uses transmitter and receiver pose, headlamp radiation
direction, photodiode incidence angle and field of view, two-dimensional
footprint intersection plus blocker height, pair separation, an optional
residual reflected floor, and ambient-light condition. Default headlamp and
receiver height is approximately 0.7 m.

Main experiment: clear nighttime ambient. A clear-day/high-ambient robustness
condition is included. Rain, fog and snow are out of scope.

### 5.3 Blockage must stay geometric

**This is the constraint most easily lost.** TR 37.885 models vehicle blockage
stochastically — an additional loss term applied when a vehicle obstructs the
link. Adopting that treatment for V-VLC occlusion would mean blockage is no
longer a function of where a blocker actually is, could not be predicted from
tracked positions, and would make the 200 ms forecast field of §6.1 carry no
information. **RQ3 would collapse.**

Rule: use TR 37.885 for **path loss given a propagation class**; determine the
**class itself geometrically** from vehicle rectangles. The implementation
keeps these in separate modules (`pathloss_37885.py` versus
`vehicle_occlusion.py`) and they must not be merged.

---

## 6. Causal observations and blockage prediction

The controller observes no exact blocker flag and no model future.

### 6.1 Observation vector

At packet \(t\): latest RF and VLC received-quality proxies with their ages; an
eight-packet history of each; RF channel-busy ratio and neighbour count; noisy
pair distance and bearing; noisy relative speed and heading difference; current
optical alignment/FOV margin; predicted probability of blockage within 200 ms;
predictor confidence or track age; previous action; last delivery outcome; and
current consecutive-miss count.

There is no head-of-line slack because packets do not queue across their
deadlines in this model.

Twenty-one named features; two of them carry eight-packet histories, so the
policy receives **35 columns**. Order follows the configured `features` list,
so it is fixed by the frozen configuration rather than by construction order —
a silent reordering would leave a checkpoint reading the wrong columns with
every shape check still passing.

**Junction geometry was added on 2026-08-04**, after §4.6.1 measured a 65–121×
lift on junction spanning against a separation signal that is weak and
non-monotonic. `distance_to_junction` is continuous, so the network chooses its
own threshold and degrades gracefully; `path_spans_junction` is the
discriminator actually measured. Both derive from own pose plus a road map,
which a real vehicle carries, and both are computed from *noisy* poses, so the
indicator is honestly uncertain near a boundary rather than a clean oracle bit.

Two things had to move first, and both are recorded in `docs/DECISION_LOG.md`
D14. `intersection_context` was unreachable from the observation layer; it now
lives in `core` beside the other pure-geometry modules, which required moving a
two-line junction-naming helper out of `mobility`. And adding any observation
feature moved the single global configuration digest, which would have stranded
a mobility campaign that cannot depend on it — see §11.2.

### 6.2 Sensor and track abstraction

**Sensing represents cooperative awareness.** Neighbours are known from the
periodic status messages they broadcast over the same sidelink the tagged pair
uses, not from onboard radar or camera tracking of uncooperative vehicles. That
one sentence decides every value below, and it was missing until 2026-08-04 —
which is why three quantities had gone undeclared rather than merely unsourced.

| Quantity | Value | Under cooperative awareness |
|---|---:|---|
| Track update rate | 20 Hz | message rate |
| Observation latency | 50 ms | nominal end-to-end |
| Position noise | 0.5 m | sender's own positioning error |
| Speed noise | 0.2 m/s | sender's own |
| **Heading noise** | **2.0°** | **broadcast field: sender's GNSS/IMU attitude error** |
| **Track lifetime** | **1.0 s** | **awareness-message timeout** |
| Forecast horizon | 200 ms | constant velocity |

These are declared simulation assumptions, not claimed sensor measurements.
Noise and latency sensitivities use half and twice the baseline values.

**Why heading noise must not be zero.** §4.6.1 measured a leader turning out of
the acceptance cone as the cause of 22.8–29.4% of junction-spanning
unavailability, against 3.3–8.1% for occlusion. A policy handed exact heading
would see every turn perfectly at exactly the moment that decides the result,
so the model would be cleanest precisely where it is load-bearing. Because
heading is *broadcast* rather than inferred, the honest value is small — degrees
rather than the tens of degrees a tracker would incur estimating heading from
successive positions at the low speeds of a turn — but it is not zero. It
propagates: the forecast's cross-track uncertainty now grows as
`speed × elapsed × heading_sd`, so a stationary vehicle keeps only the sensor's
own error while a fast one is displaced sideways in proportion to how far it
travelled.

**Why a track lifetime must exist.** `neighbour_count` is the RF-load proxy.
Unbounded, a vehicle that drives away is counted for the rest of the episode
and the proxy only ever rises.

**Vehicle dimensions are exact, and that is a declared assumption rather than a
gap.** Length, width and height are standard fields of an awareness message, so
a cooperative neighbour's size is known rather than estimated. The residual
risk is class confusion — mistaking a bus for a car understates the blocking
band by 11.0 / 4.5 = 2.4× — but the mixture has three well-separated classes.
Modelling dimension noise would add real complexity for negligible effect.

**Position noise is the one value this framing makes optimistic.** 0.5 m is
better than unaugmented GNSS, which is metre-class; it implies an augmented or
RTK-corrected solution. Declared, with 0.25 and 1.0 m as the sensitivity
points, and unsourced pending the §20 literature check alongside the IDM
headway and the receiver semi-angle.

The predictor propagates track uncertainty and produces a blockage
**probability**, not a perfect future binary state.

**Resolved 2026-08-04.** Heading noise and the track lifetime were undeclared until the cooperative-awareness framing above was written down; both are now configured, propagated and tested, and vehicle dimensions are recorded as a declared assumption rather than an omission. See `docs/DECISION_LOG.md` D15.

### 6.3 Action-dependent information

RF busy ratio remains continuously observable. A fresh post-transmission
quality measurement is obtained on whichever legs were used; the unused leg's
most recent measurement ages. The current action therefore affects future
information freshness.

A constrained contextual policy that ignores history and feature age is
included as a baseline. **If action-dependent information provides no
measurable benefit, the paper will describe the problem as contextual rather
than overclaiming MDP sequentiality.**

---

## 7. RF channel and NR sidelink abstraction

### 7.1 Physical assumptions

| Parameter | Value |
|---|---:|
| Carrier | 5.9 GHz |
| Channel bandwidth | 10 MHz |
| Subcarrier spacing | 30 kHz |
| Resource blocks | 24 |
| Slot | 0.5 ms |
| Modulation | **QPSK** |
| Code rate | **1/3** |
| Airtime | **1.0 ms (two slots, one attempt)** |
| Transmit power | 23 dBm |
| Antenna height | 1.5 m |
| Resource mode | NR sidelink Mode 2, pre-reserved opportunity |

A two-slot allocation is a multi-slot PSSCH assignment, **not** a
retransmission: `rf_attempts_per_packet` remains 1.

Large-scale channel follows the 3GPP TR 37.885 urban-grid LOS/NLOSv/NLOS
family. Shadowing must be spatially correlated. Small-scale fading must be
temporally correlated, not resampled independently every packet.

### 7.2 Congestion and collision model

The arbitrary neighbour-count-to-collision mapping of the original plan is
rejected. v2 required an offline 5G-LENA Mode-2 calibration campaign; that
campaign is **deferred**, under v2 §7.2's own fallback clause.

The primary model is therefore a **clearly scoped analytical collision model
with sensitivity bands**, and Mode-2 realism claims are weakened **from the
start**. The paper says "analytical collision model with sensitivity bands",
never "NR Mode 2".

If time permits at week 13, a 5G-LENA surrogate may be fitted and validated on
held-out cases, and the claim strengthened accordingly. It is not on the
critical path.

### 7.3 RF packet error

Either calibrated MCS/transport-block BLER curves, or a finite-blocklength
approximation whose channel-use, modulation, coding and validity assumptions
are explicitly documented. The \(+\tfrac{1}{2}\log_2 n\) term is included only
with its correct source and convention, and a generic finite-blocklength
expression is **not** applied to the IM/DD optical link.

---

## 8. V-VLC channel

### 8.1 Physical model

An IM/DD vehicle-light link using a measured or empirically tabulated
non-Lambertian automotive headlamp pattern; headlamp-to-rear-photodiode
geometry; receiver area, responsivity, optical filter/concentrator and field of
view; ambient shot noise and receiver thermal noise; modulation-specific
BER/PER; complete direct-path blockage as the main case; and a calibrated
residual optical floor as a sensitivity.

Validation is against the empirical vehicular VLC evidence already collected
(W17, and W18 once obtained). The Veins-VLC cross-check is **deferred**.
Infrastructure-to-vehicle ray-traced parameters are not transferred to the V2V
headlamp case.

### 8.2 Timing feasibility — settled

| Parameter | Value |
|---|---:|
| Electrical bandwidth | 5 MHz |
| Modulation | OOK |
| Pulse roll-off | 0.3 |
| Code rate | **1/4** |
| Airtime | **2.4 ms** |
| Gross rate | **4.5 Mbit/s** |
| Occupied bandwidth | **2.93 MHz (59% of the front end)** |

W17 limits automotive high-brightness LED modulation bandwidth to "a few MHz"
through junction capacitance and phosphor response, so 5 MHz is the optimistic
edge of a defensible range. At 59% occupancy the symbol rate sits inside the
LED's flat region.

**Table I must record** that this rate is roughly 4.5× the 1 Mbit/s nominal of
Veins-VLC, the closest reproducible reference simulator. That gap is the single
strongest assumption in the profile and must be stated, not left for a reviewer
to compute.

**Re-run the feasibility gate** whenever code rate, framing overhead, roll-off
or modulation changes. The configuration loader enforces both conditions —
resource-grid capacity for RF and occupied bandwidth for VLC — so an
unrealizable configuration fails at load in milliseconds rather than after
weeks of training.

### 8.3 Failure dependence

For every scenario, log \(p_{\mathrm{RF}}\), \(p_{\mathrm{VLC}}\),
\(p_{\mathrm{joint}}\), and \(p_{\mathrm{joint}}/(p_{\mathrm{RF}}p_{\mathrm{VLC}})\),
conditioned on density, separation, intersection distance, propagation class,
and predicted-blockage bin. This prevents the diversity result from silently
assuming independent failures.

---

## 9. Packet lifecycle and timing

For each generated packet:

1. form the observation from the latest causally available measurements
   immediately before the known periodic generation instant;
2. run the policy before that instant and record its inference time;
3. create one packet ID, generation time, information size, and 3 ms deadline;
4. apply the preselected action to the reserved RF and/or VLC opportunity;
5. transmit one copy per selected leg;
6. calculate link-specific decoding and arrival outcomes;
7. deliver at the first successful arrival;
8. discard the other copy after its already-committed cost is counted;
9. declare a miss if neither selected copy arrives by 3 ms;
10. log the cause as collision, RF channel failure, VLC alignment/occlusion,
    PHY infeasibility, decoding lateness, or joint failure.

For DUP: delivered = RF ∨ VLC, and \(T_{\mathrm{delivery}}=\min(T_{\mathrm{RF}},T_{\mathrm{VLC}})\)
over successful copies. There is no early cancellation and both legs always
incur their activation cost.

Policy runtime is not subtracted from the radio deadline, but p99 inference
below 100 µs remains an engineering requirement.

---

## 10. Control problem

### 10.1 Action

\(a_t\in\{\mathrm{RF},\mathrm{VLC},\mathrm{DUP}\}\).

### 10.2 Primary cost

Normalized transmission activation cost, not unmeasured joules:

\[
g(\mathrm{RF})=1,\qquad g(\mathrm{VLC})=1,\qquad g(\mathrm{DUP})=2.
\]

RF and VLC activations, airtime and DUP usage are reported separately. A
cost-ratio sensitivity uses \(g(\mathrm{VLC})/g(\mathrm{RF})\in\{0.3,0.5,1.0\}\).
The value 0.3 is **not** called energy unless supported by measured power and
airtime.

**Why the ratio is contested.** VLC airtime is 2.4 ms against RF's 1.0 ms, but
the headlamp is already illuminated, so the marginal communication energy is
the modulation drive rather than the LED's total draw. Attributing the full
lamp power to communication would be indefensible; attributing none of it is
also a choice. The sweep spans the plausible range instead of asserting one
number.

A near-unity baseline ratio is retained deliberately: if VLC were an order of
magnitude cheaper, the optimal policy would collapse to "use VLC whenever it
works" and the cost-reliability trade-off would largely disappear.

No network-wide resource-efficiency claim is made, because the tagged action
does not control the background fleet's offered load.

### 10.3 Reliability cost

Evaluation uses \(m_t=\mathbf 1\{\text{packet not delivered by its deadline}\}\).
Training uses the conditional expected miss probability
\(c_t=\widehat P(m_t=1\mid o_t,a_t)\), which gives a dense low-variance signal.
Sampled binary misses remain ground truth for final evaluation.

### 10.4 Group-constrained average formulation

For density group \(k\):

\[
\min_\pi J_g(\pi)\quad\text{s.t.}\quad J_{c,k}(\pi)\le 10^{-4}\ \ \forall k\in\{20,40,60\}
\]

with one multiplier per training density:

\[
\lambda_k\leftarrow\left[\lambda_k+\eta_\lambda(\widehat J_{c,k}-10^{-4})\right]_+.
\]

The method is called **empirically reliability-constrained primal-dual PPO**.
"Hard constraint" and "guaranteed constraint" are avoided.

Consecutive-miss count is part of the observation and burst reliability is an
evaluation metric; a separate burst constraint is out of scope.

---

## 11. Learning method

### 11.1 Policy architecture

Actor MLP with two 64-unit tanh layers; separate reward and cost critics of the
same shape; categorical three-action output; clipped PPO objective; generalized
advantage estimation; entropy regularization early in training; observation
normalization fitted on training traces only.

A GRU is not in the initial implementation. It is considered only if history
stacking fails against the contextual and deterministic baselines.

### 11.2 Trace replay

Mobility, building geometry and large-scale channel traces are generated
offline and immutable. Training replay samples held-in trajectories; online
small-scale fading and collision randomness; online sensor noise;
link-dependent measurements and feature ages; and sampled packet outcomes.

Every run is keyed by configuration hash, mobility-trace hash, channel
calibration version, code commit, policy seed, and evaluation scenario seed.

**The code commit is recorded, and `code_version` is not a substitute.** Every
manifest carries `code_commit` (`src/grail_v/core/provenance.py`), suffixed
`-dirty` when the producing tree had uncommitted changes, because an artifact
built from modified code cannot be reproduced from a commit alone and recording
the clean hash would assert a reproducibility that does not hold. `None`
appears only outside a checkout. This was added on 2026-08-04 after the gap was
found: manifests recorded `code_version`, which is the package version and
moves on a release, so the mobility engine could change twice in a day — as it
did, at §4.6.3 and §4.6.5 — while two traces still agreed on `config_hash` and
`code_version` and came from materially different simulators. The nine traces
generated that day carry the field backfilled to `d165358`, with a note saying
so; no file under `src/` differs between that commit and the next, so the value
is certain rather than inferred.

**What the configuration hash covers.** `config_hash` digests the physics-
bearing configuration only. Paths listed in `HASH_EXCLUDED_PATHS`
(`src/grail_v/config/hashing.py`) are omitted because changing them cannot
change a generated byte. The list currently holds one entry,
`environment.splits`: split membership is consumed at training and evaluation
time and is read by no generator, so adding a held-out replicate must not
restamp traces it did not affect. Nothing is lost — `canonical_json` still
serializes the excluded fields, every trace stores its complete
`resolved_config.yaml`, and the campaign manifest records the split map.

Adding to this list is a deliberate act, not a convenience. The test to apply
is whether a field can alter any generated artifact; if it can, it stays in the
digest even when that is inconvenient.

**Scoped digests, added 2026-08-04.** The rule above answers "was this the same
run?", which is the right question for a run and the wrong one for a single
artifact. A mobility trace is produced by a generator that reads `mobility`,
`geometry`, `environment` and `training.root_seed` and nothing else, so editing
a receiver field or a channel parameter cannot move a vehicle — yet under one
global digest it strands every trace and forces hours of recomputation to
reproduce identical bytes. `HASH_SCOPES` therefore defines, per artifact class,
the paths its producer provably cannot read, and every manifest records
`config_scope_hashes` beside `config_hash`. **Reuse is decided on the scope
digest; provenance still reports both.**

Exclusion rather than inclusion is the fail-safe direction: a forgotten
exclusion causes a visible, merely wasteful re-stamp, whereas a forgotten
inclusion would let two genuinely different engines share a digest. The
mobility scope keeps `training` wholesale even though only `root_seed` is read,
because carving out a subtree is where that guarantee starts to erode.

This is not hypothetical. Adding the junction features of §6.1 moved the global
digest from `92bf9cb5` to `aff125fe` while the mobility scope stayed at
`7e72595a`, so the nine traces remained valid. §7.2's collision model is still
undefined, so implementing M3 will add configuration that would otherwise have
invalidated the campaign for the same non-reason.

The Option-B campaign of 2026-08-03 was published under the pre-exclusion
digest `137941801b86…` and re-stamped to `5e42a2ba61e1…`. The re-stamp was
gated on recomputing the old digest from the live configuration and matching it
against each manifest, which proves the traces came from a canonically
identical configuration; each artifact was then re-verified against its file
digests. Every trace manifest records the transition in its `notes`.

### 11.3 Curriculum

10% of training at \(10^{-2}\), 20% at \(10^{-3}\), 70% at \(10^{-4}\). The
final checkpoint must spend most of training at the real target. Multiplier,
constraint estimate, policy entropy, cost and per-density violation are logged
throughout.

For the \(10^{-5}\) frontier, `primal_dual_ppo_ultra.yaml` adds a fourth stage.
**Open item:** that schedule gives only 40% of training to the hardest target
against 70% for \(10^{-4}\), which should be reviewed before the frontier run.

### 11.4 Training volume and seeds

Five independent policy-training seeds; up to \(10^7\) packet transitions per
seed across the three training densities; 60 s episodes, equivalent to 600
packets at 10 Hz; early stopping only on a disjoint validation set; checkpoint
selection on reliability first, then minimum activation cost among reliable
checkpoints.

Wall-clock budget is recorded after profiling, not promised in advance.

### 11.5 Compute and the environment implementation

Target hardware is a single Apple M2 laptop with no cluster.

**The binding constraint is environment throughput, not the reliability
target.** The 64×64 policy trains in minutes; environment stepping dominates by
roughly two orders of magnitude. A vectorized NumPy environment at ~10⁵
steps/s runs even a \(10^7\)-packet frontier campaign in well under an hour,
while a naive per-packet Python loop at ~10³ steps/s turns the \(10^6\)
headline evaluation into a working day.

`vector_env.py` is therefore **mandatory and must be built alongside the
environment at M5**, not retrofitted. CPU is expected to beat MPS at this
network size; GPU plumbing is not a priority.

### 11.6 Inference measurement

Measured on a named CPU with warm-up iterations, single-observation batch, one
pinned software thread, and median/p95/p99 latency; serialization and
preprocessing reported separately. Engineering gate: p99 policy computation
below 100 µs.

---

## 12. Baselines and ablations

All deployable policies receive the same causal observations. Only the oracle
may use hidden state and counterfactual outcomes.

**Required baselines — all seven retained.** Once the environment exists they
are nearly free, and two of them carry the argument:

1. RF-only
2. VLC-only
3. Always-DUP
4. Forecast-aware deterministic gate (predicted success, feature age,
   hysteresis, DUP threshold)
5. **Constrained contextual policy** — the honesty check for §6.3
6. **Fixed-penalty PPO** — answers "why not just tune a scalar penalty?", the
   question that decides whether the constrained formulation is a contribution
7. Oracle — least-cost action that succeeds, using hidden counterfactuals;
   clearly labelled non-deployable

Uniform random and DDQN are not in the conference baseline set.

**Required ablations:** no blockage forecast; perfect simulator blockage
information as a non-deployable upper bound; one global multiplier versus one
per density; no measurement-age or action-dependent feedback.

---

## 13. Evaluation design

### 13.1 Matched evaluation

All policies run on identical mobility trajectories, packet generation times,
fading and collision seeds, sensor-noise realizations, background load,
deadlines and action-cost rules. Train, validation and test splits are made by
complete trajectory, route and seed; adjacent packets from one trajectory are
never split across sets.

### 13.2 Headline success rule

A policy satisfies the primary requirement only if the **one-sided 95% upper
confidence bound** on \(P_{\mathrm{miss}}\) is \(\le 10^{-4}\) at every primary
density. A point estimate below \(10^{-4}\) is insufficient.

**This is more demanding than it looks.** With \(10^6\) packets and a true miss
rate of exactly \(10^{-4}\), the bound lands near \(1.16\times10^{-4}\) — a
failure. Accounting for burst correlation, the true rate must be roughly
1.5–2× below the nominal target before the target can be claimed.

### 13.3 Primary sample size

Per policy-density condition: at least \(10^6\) raw packet outcomes; at least
200 independent trajectory/pair clusters; matched evaluation across policy
seeds; further sampling if effective sample size is inadequate.

Because failures are temporally correlated, packet-level Clopper–Pearson
intervals are **not** the headline uncertainty measure. Use trajectory/block
bootstrap or a cluster-aware one-sided interval. Raw miss count and denominator
are always reported.

Episode supply is not a constraint: the generated traces yield roughly 8.3 M,
47.4 M and 81.9 M packet-equivalents at the three densities.

### 13.4 Ultra-reliability sample size

For a claimed \(10^{-5}\) result: at least \(10^7\) raw outcomes in the
selected condition; many independent clusters; a one-sided correlation-aware
upper bound below \(10^{-5}\); and no reuse of training or calibration
trajectories. Otherwise report as underpowered exploratory evidence.

### 13.5 Metrics

**Headline:** deadline-miss probability; one-sided 95% upper bound; normalized
activation cost per generated packet; per timely delivered packet; and the
reliability-cost frontier.

**Mechanism and robustness:** RF/VLC/DUP selection fractions; useful,
unnecessary and insufficient DUP fractions; RF/VLC/joint failure probabilities
and dependence ratio; miss-run survival curve and run-length quantiles; action
probability versus predicted blockage and pair distance; action probability
versus intersection distance and density; constraint and multiplier
trajectories; interpolation and extrapolation performance; CPU inference
p50/p95/p99.

### 13.6 Two exposure hazards that must be handled

Both are measured properties of the generated traces, not hypotheticals.

**1. Episode-length censoring differs by density.** The fraction of episodes
ending at the 60 s cap is 6.0%, 44.0% and 58.3% at \(\rho_L=20,40,60\). A
miss-run still in progress when an episode ends is right-censored, so a naive
run-length survival curve underestimates long runs, and does so far more at
high density — exactly where H2 predicts the interesting behaviour.

Run-length analysis must therefore treat **episode end as a censoring event**
and use a censoring-aware estimator. v2 already forbade comparing raw maximum
run length without equal packet exposure; that rule extends to the survival
curve itself.

Uncapping episodes at evaluation time removes the hazard entirely at some
compute cost, and is the cleanest fix if H2 proves load-bearing. Decide at
Gate 5.

**2. Initial separation mix differs by density.** Pairs starting in the
40–60 m bin are 55.0%, 50.0% and 34.9% at \(\rho_L=20,40,60\); dense traffic
starts pairs closer. Separation drives both RF path loss and VLC occlusion, so
any cross-density comparison **must be stratified by initial separation**, or
it measures the separation mix as much as the density.

### 13.7 Required feasibility checks before PPO

1. verify every selected PHY can transmit the complete block by its deadline;
2. measure RF-only, VLC-only, Always-DUP and oracle;
3. confirm the oracle can meet \(10^{-4}\) in at least part of the density
   range;
4. characterize \(p_{\mathrm{RF}},p_{\mathrm{VLC}},p_{\mathrm{joint}}\);
5. verify the VLC availability/PER trend against empirical evidence;
6. check that exact hidden state cannot leak through the observation API.

**If the oracle cannot meet the requirement, PPO training does not begin for
that condition.** The condition is recorded as physically infeasible.

---

## 14. Decision gates

### Gate 0 — Scope and publication ethics — **PASSED**

Service profile and claim language frozen; U0 overlap matrix completed; no
copied text, figures, data or results; shared conceptual elements identified;
venue policies checked.

### Gate 1 — Mobility credibility — **PASSED**

- realised densities within tolerance: 0.05%, 0.02%, 0.95% against a 5% limit;
- plausible mean speeds, queues and signal response;
- **zero overlapping vehicle footprints** at every density;
- no teleportation, by construction;
- tagged-pair separation logic verified, 364,188 episodes extracted;
- immutable, hashed trace artifacts archived.

Two conditions were added beyond v2 and both hold: no overlapping footprints in
any recorded frame, and warm-up sufficiency measured rather than assumed
(stationarity at 120–160 s against a 300 s warm-up).

**Tightening proposed:** density tolerance may be reduced from 5% to 2%. It
existed because density was previously searched for; it is now set directly and
all three densities clear 2% comfortably.

### Gate 2 — PHY and channel credibility

- 300-byte block fits both links within 3 ms **and** within the declared
  optical bandwidth — **pre-checked and passing** (§7.1, §8.2);
- both feasibility conditions enforced by the configuration loader;
- IDM time headway sourced or given a sensitivity band (§4.7);
- analytical collision model scoped, with sensitivity bands declared;
- VLC model validated against empirical/non-Lambertian evidence;
- LOS/NLOSv/NLOS and optical occlusion unit tests pass;
- residual-NLOS and ambient-light sensitivities defined;
- **clear-path VLC PER measured against separation at both receiver
  semi-angles** (§14.1), which decides whether the concentrated front end is
  load-bearing or redundant.

#### 14.1 The reliability floor and what the optical front end can move

Worth computing before any training, because it bounds what the hybrid can
deliver and is answerable from link budgets alone.

Under duplication a miss requires both legs to fail, so the hybrid relaxes the
RF single-shot requirement by a factor \(1/P(\text{VLC fails})\), where

\[
P(\text{VLC fails}) = P_\text{out} + (1 - P_\text{out})\,\text{PER}_\text{clear}
\]

and \(P_\text{out}\) is the geometric outage of §4.6.1. **Restated on the
corrected traces**; the superseded values were 11.9 / 22.2 / 16.1%, which
inflated the floor by roughly an order of magnitude:

| \(\rho_L\) | \(P_\text{out}\) | Cap \(1/P_\text{out}\) | RF BLER admissible for \(10^{-5}\) |
|---:|---:|---:|---:|
| 10 | 3.41% | **29.3×** | \(2.9\times10^{-4}\) |
| 20 | 1.87% | **53.5×** | \(5.4\times10^{-4}\) |
| 30 | 1.01% | **99.0×** | \(9.9\times10^{-4}\) |

**Geometry still sets a floor the optics cannot cross** — no concentrator gain
reaches a blocked path — but that floor is now 30–99× rather than 4.5–8.4×.
The \(10^{-5}\) frontier consequently asks RF for a single-shot BLER of
\(3\text{–}10\times10^{-4}\) rather than \(10^{-5}\), which is a different and
far more achievable requirement.

**The aggregate cap is the wrong instrument, because \(P_\text{out}\) is
bimodal.** At \(\rho_L=20\):

| Condition | \(P_\text{out}\) | Cap | RF BLER admissible for \(10^{-5}\) | Share |
|---|---:|---:|---:|---:|
| Mid-block | 0.39% | **256×** | \(2.6\times10^{-3}\) | 95.4% |
| Spans a junction | 32.10% | **3.1×** | \(3.1\times10^{-5}\) | 4.6% |

**This is the whole control problem in one table.** Mid-block, duplication buys
two orders of magnitude and is almost certainly wasted spend. At a junction it
buys a factor of three, and the RF leg must carry the target nearly alone. A
policy that cannot tell the two apart must price every packet at one of these
two numbers and will be wrong most of the time.

**Within the cap the optical front end still matters.** At \(\rho_L=10\):

| \(\text{PER}_\text{clear}\) | \(P(\text{VLC fails})\) | Relaxation | RF BLER for \(10^{-5}\) |
|---|---:|---:|---:|
| 0.5 — marginal link | 0.5171 | 1.9× | \(1.9\times10^{-5}\) |
| 0.05 | 0.0824 | 12.1× | \(1.2\times10^{-4}\) |
| \(\approx 0\) — strong link | 0.0341 | **29.3×** | \(2.9\times10^{-4}\) |

Roughly **15× of RF headroom** now turns on where \(\text{PER}_\text{clear}\)
sits, against 4.7× before. Lower geometric outage *raises* the stake on the
clear-path link budget, because the optics now determine a larger share of
\(P(\text{VLC fails})\). Optical power falls as \(1/d^2\) and the window runs
to 40 m, so whether the 60° receiver sits on its PER waterfall at the long end
is now the single largest lever in this table. It remains a Gate-2 measurement,
not an assumption.

**One structural consequence, from geometry alone.** Even mid-block,
\(P_\text{out} = 0.25\text{–}0.50\%\) is 25–50× the \(10^{-4}\) budget, so
**V-VLC alone never meets the target instantaneously anywhere in the
network**. Its role in this system is as a duplication partner, not as a
standalone action. If M3 and M4 confirm it, the `VLC` action at cost 1 may be
dominated and the live decision reduces to RF versus DUP. That is a finding
about the action space and should be checked at Gate 3 rather than discovered
during training.

**These figures assume RF and VLC failures are independent, which is
optimistic.** A queue at a junction produces a high channel-busy ratio and
cross-traffic in the optical path at the same time, and §4.6.2 measures
obstruction co-occurring 17–64× above independence even though its absolute
rate is now 0.5–1.2%. Any positive correlation raises the floor, which is what
Gate 3's joint-failure characterisation exists to detect.

### Gate 3 — Hybrid feasibility — **hard stop**

- Always-DUP and oracle reliability characterized before training;
- joint failure neither silently forced independent nor always identical;
- a nonempty \(10^{-4}\) feasible region exists;
- failure mechanisms explainable from saved traces;
- **joint-failure correlation reported against the measured obstruction
  co-occurrence of §4.6.2** — 1.18 / 0.82 / 0.50% of instants, which is 17–64×
  above independence. Separate the two: coincident *obstruction* is expected
  and benign, coincident *failure* is what the contribution cannot survive.
  Report the absolute rate alongside the lift, because with both marginals near
  1% the lift is large by construction. Recompute the §14.1 floor with the
  measured correlation rather than under independence;
- **whether V-VLC alone ever meets \(10^{-4}\) instantaneously.** Geometry says
  no — even mid-block \(P_\text{out}\) is 25–50× the budget — so if the channel
  models agree, the `VLC` action is dominated and the decision is RF versus
  DUP. Establish this here rather than during training;
- **\(P_\text{out}\) conditioned on junction spanning, not only aggregated.**
  §14.1's cap ranges from 3.1× to 256× across that single condition, so a gate
  run on aggregates alone would miss the structure the policy exists to
  exploit.

If the oracle cannot meet \(10^{-4}\) anywhere, PPO does not start. That
outcome is finding #1, not failure — see `research/HYPOTHESES.md` H1.

### Gate 4 — Learning validity

Medium-density constraint converges on held-out validation; per-density
multipliers behave stably; policy improves activation cost over Always-DUP
while remaining feasible; forecast and contextual ablations confirm or falsify
the sequential story; inference gate passes.

### Gate 5 — Publication evidence

- all primary cells have at least \(10^6\) outcomes;
- one-sided cluster-aware bounds computed;
- conclusions survive five policy seeds;
- censoring and separation-mix hazards of §13.6 explicitly handled;
- no result depends on a single unreported parameter choice;
- all figures reproducible from immutable result files.

The real-map robustness condition of v2 is **removed**, not deferred: it
required a SUMO network import that no longer exists.

---

## 15. Paper structure and page budget

Five main pages plus references, or the venue's exact allowance.

- **I. Introduction and related work — 0.9 page.** Application and failure
  mechanisms; closest RF/VLC and duplication work; precise conjunction-based
  gap; three contributions.
- **II. Shared-geometry system model — 1.25 pages.** Grid mobility and tagged
  pair; hidden geometry and causal observations; RF and VLC model summaries;
  packet/DUP timing; Table I parameters.
- **III. Reliability-constrained control — 0.7 page.** Observation, action,
  activation cost; per-density average constraints; primal-dual PPO; explicit
  empirical-not-formal wording.
- **IV. Experimental methodology — 0.7 page.** Channel modelling; trace splits
  and baselines; sample sizes and confidence method; exposure handling.
- **V. Results — 1.45 pages.** Feasibility and reliability-cost frontier;
  policy mechanism and forecast value; burst and failure dependence;
  generalization and inference.
- **VI. Conclusion — 0.2 page.**

**Figures and tables — four figures, two tables:**

1. **F1** system and shared-geometry scenario.
2. **F2** RF/VLC characterization plus joint-failure environment.
3. **F3** miss-probability upper bound versus activation-cost frontier.
4. **F4** policy interpretation as compact panels: single-episode mechanism
   trace with annotated anticipation lead time, and the spatial P(DUP) map.
5. **Table I** sourced simulation and PHY parameters.
6. **Table II** policy reliability, confidence bound, cost, DUP fractions,
   inference.

F4's two panels are what make a reviewer believe the policy learned geometry
rather than a density lookup. They take the budget v2 assigned to real-map
robustness, which is out of scope.

Training curves, full hyperparameters, extra ablations and ultra-reliability
detail move to the artifact/arXiv supplement.

---

## 16. Repository design

```text
configs/
  project/ mobility/ service/ channel/ observation/ training/ evaluation/

src/grail_v/
  core/ config/ artifacts/
  mobility/     grid_network, car_following, grid_signals, grid_simulator,
                tagged_pairs, trace_io, validation, vehicle_types, pipeline
  geometry/ channels/rf/ channels/vlc/ phy/ prediction/ observation/
  env/ agents/ baselines/ evaluation/ visualization/

scripts/    generate_synthetic_traces.py, calibrate_rf.py, validate_vlc.py,
            run_feasibility.py, train.py, evaluate.py, make_figures.py
tests/      unit/ integration/ statistical/ regression/ fixtures/
artifacts/  manifests/ calibration/ traces/ checkpoints/ evaluations/ figures/
docs/       DECISION_LOG.md
paper/ research/
```

Business logic lives in the package; `scripts/` contains thin drivers only.

`docs/DECISION_LOG.md` records *why* the model is the way it is, with the
arithmetic behind each decision and each correction. This plan is the
specification and `git log` is the record of what changed; the reasoning that
connects them is recoverable from neither, and three of the entries are
corrections that invalidated already-published measurements.

### 16.1 Trace artifact layout

```text
artifacts/traces/<trace_id>/
├── vehicles/part-*.parquet    50 ms vehicle states
├── signals.parquet            signal phases
├── pairs.parquet              tagged-pair episodes, spec §8.7 schema
├── network.json               grid spec; rebuilds the topology
├── routes.json                vehicle id → edge sequence
├── resolved_config.yaml
└── manifest.json              config hash, seed, code version
```

`routes.json` is required: without persisted edge sequences, pair extraction
falls back to comparing opaque route identifiers, which is what previously
yielded zero episodes.

### 16.2 Two-pass writing

A full campaign cannot be held in memory: at \(\rho_L=60\) a 900 s trace is
2,240 vehicles × 18,000 steps ≈ 40.3 million records, roughly 29 GB as Python
objects. Pass one collects only the route table, validation frames and
pair inputs; pass two re-runs the model and streams records into the Parquet
writer. Re-running is safe because the model is deterministic.

### 16.3 Mandatory tests

Unit conversion and coordinate transforms; rotated-rectangle and building
intersection; optical FOV boundary; RF LOS/NLOSv/NLOS classification; packet
timing and deadline expiration; simultaneous DUP OR-success and double-cost
semantics; observation causality and feature ages; absence of hidden
counterfactual leakage; per-density constraint accounting; deterministic replay
from seed and hash; bootstrap implementation on synthetic known distributions;
**vehicle footprint overlap within its declared bound in every recorded
frame**, tested over all pairs in world coordinates rather than within an
`edge_id`, which is the weaker check that let both §4.6.3 and §4.6.5 through.
The bound, and why it is a bound rather than zero, is §4.7 item 7.

---

## 17. Execution schedule

Weeks 1–3 are complete. The remaining plan assumes a single laptop.

| Wk | Deliverable | Gate | Status |
|---:|---|---|---|
| 1 | Scaffold, configs, units, U0 matrix, PHY feasibility pre-check | Gate 0 | **done** |
| 2 | Analytic grid model: network, IDM, signals, simulator | | **done** |
| 3 | Trace pipeline, pair extraction, campaign, artifacts | **Gate 1** | **done** |
| 4–6 | Geometry: primitives, spatial index, pair geometry, vehicle occlusion, RF visibility, intersection context, leakage tests | | next |
| 7 | Prediction: sensor model, tracks, constant-velocity forecast; observation builder and schema | | |
| 8–9 | RF channel (TR 37.885 path loss, shadowing, fading, analytical collision model) and V-VLC channel with empirical validation | **Gate 2** | |
| 10 | Packet lifecycle, random tape, Gymnasium environment, **vector_env**, oracle, joint-failure characterization | **Gate 3** | |
| 11 | Seven baselines; freeze train/validation/test splits | | |
| 12–13 | Primal-dual PPO, curriculum, per-density multipliers, inference profiling | **Gate 4** | |
| 14 | Five-seed training, \(10^6\) matched evaluation, ablations | | |
| 15 | Cluster-aware statistics with censoring handling, F1–F4, Table I–II | **Gate 5** | |
| 16–17 | Draft, literature re-check, overlap review, submission | | |

Slack is deliberate: F4's panels are analysis-only over saved rollouts and
absorb slips without retraining. No deadline overrides Gate 2, Gate 3, or the
statistical requirements.

**Scheduled literature re-check at week 16:** W12 full text (never obtained;
the files under that name were block pages, not PDFs), W18 local copy (absent
despite being a Gate-2 VLC input), Xplore/Scopus strings, and new citations to
W1 and W2.

---

## 18. Risk register

**R1 — The oracle cannot meet \(10^{-4}\) anywhere.** Report the density range
as infeasible; identify whether joint blockage, RF congestion or PHY timing
dominates; do not tune the learner against an impossible constraint. Either
branch is publishable (H1).

**R2 — PPO provides no advantage over a contextual rule.** Report the stronger
simpler method honestly; reframe around constrained geometry-aware control and
the environment; retain PPO only if sequential feature age and history have
demonstrated value.

**R3 — \(10^{-5}\) is underpowered.** Retain \(10^{-4}\) as the headline;
report \(10^{-5}\) with raw miss count and bound; never write "five nines
achieved".

**R4a — A configuration silently destroys the phenomenon under study.**
This already happened once and was caught only by measuring the traces. The
first campaign at \(\{20,40,60\}\) with a 10–60 m window and no adjacency
requirement blocked the optical path 97–100% of the time, leaving V-VLC with no
availability at all — while every Gate-1 check passed, because Gate 1 tests
mobility credibility and not whether the link under study can ever work.
Mitigation: before each gate, measure the quantity the research question
depends on, not only the quantities the gate lists. The superseded campaign and
its rationale are archived under `artifacts/archive/`.

**R4b — Bulk artifacts are generated before a consumer exists.** The 21-trace
Option-B campaign (3.6 h) was produced before M2, which needs one trace per
density, not a split. Mobility has already been retuned twice from downstream
findings, and M3/M4 may force a third; that would discard the extra work.
Mitigation, applying from M2 onward: generate the minimum set a milestone
actually consumes, and expand to the full replicate count only once the
consumer that reads the split exists (M7 training, M8 evaluation). Keeping the
split *machinery* costs nothing and closes a Gate-5 requirement — it is the
bulk generation, not the mechanism, that should wait.

**R4 — The mobility model is challenged as unrealistic.** The declared
limitations of §4.7 are stated up front, the fundamental diagram of §4.5 is
reported, and the SUMO implementation is preserved on branch
`baseline/3ms-profile_SUMO-TraCI` for a cross-check if a reviewer demands one.

**R5 — Signal progression is challenged.** Free-flow speed is 52% of the limit
because offsets are staggered rather than progressed. If this proves decisive,
green-wave offsets are a bounded change to `grid_signals.py`; the resulting
speed change must then be re-reported.

**R6 — Inference latency.** Tiny network plus measured microseconds in
Table II; documented slow-timescale fallback if the gate fails.

**R7 — U0 overlap is too large.** Remove reused text, figures, code, data and
result structures; disclose and cite U0 per venue policy; stop submission if
the scientific distinction is not clear.

---

## 19. U0 overlap and publication ethics

The comparison table in `paper/U0_OVERLAP_MATRIX.md` covers application and
service profile, mobility and geometry, RF model, VLC model, observation and
predictor, actions, objective and constraint, algorithm, code, datasets and
traces, figures and tables, numerical results, and manuscript text.

Expected allowed conceptual overlap is limited to the broad RF/VLC/DUP problem
family and necessary self-cited context. GRAIL-V uses new geometry, channel
modelling, causal observation construction, training implementation, traces,
figures, results and text. The phrase "zero overlap" is never used.

The mobility backend change strengthens this position: the trace generator,
network model, car-following law and episode extraction are all new work with
no shared lineage.

---

## 20. Immediate next actions

1. **M2 is complete** — geometry and observations both. Next is M3 (RF) and
   M4 (V-VLC), weeks 8–9, ending at Gate 2. §7.2's collision model must stop
   being undefined there: RF carries roughly 41.7 dB of thermal margin at 40 m,
   so RF failure is collision-dominated and §7.2 alone decides whether
   Condition D can be answered.
2. **Source or bound the IDM time headway** (§4.7 item 1). It sets the capacity
   in §4.5 and is currently undeclared.
2b. **Source the cooperative-awareness sensing values** (§6.2): heading noise
   2.0°, position noise 0.5 m, and the 1.0 s message timeout. All three are
   declared and defensible under that framing but none is yet cited, and they
   are training *inputs* — revising one after M7 means retraining, unlike a
   reporting choice.
3. **Source the receiver field of view** (§4.7 item 6), and confirm the
   semi-angle reading of `receiver_fov_deg`. W18 may settle both this and the
   headlamp pattern. Until then the headline holds the pessimistic 60° and the
   frontier reports 30° as a sensitivity. Whichever value is in force, M4 must
   use the same \(\psi_c\) in the concentrator gain \(n^2/\sin^2\psi_c\) as the
   acceptance test uses; a wide cone for availability combined with narrow-cone
   gain would count the same physics twice.
4. **Measure clear-path VLC PER against separation at both semi-angles** as
   soon as M4's link budget exists (§14.1). It decides whether the concentrated
   receiver is load-bearing or redundant, and it is worth up to 4.7× of RF
   single-shot BLER headroom on the \(10^{-5}\) frontier. Answerable from link
   budgets alone, before any training.
5. **Obtain W18** before Gate 2 needs it for VLC validation.
6. Decide whether to tighten the density tolerance to 2% (§14 Gate 1).
7. Review the \(10^{-5}\) curriculum split (§11.3).
8. Consider whether multi-lane roads are worth the cost (§4.7 item 3). They are
   *not* required for the current result — blockage comes from junction
   cross-traffic, which single-lane already provides — but they would answer the
   standardisation request and make the geometry closer to a real avenue.

---

## 21. Final go/no-go

The project proceeds to full conference submission when:

- a physically feasible RF and VLC packet model exists (**done**, §7.1 and §8.2);
- the oracle demonstrates a nonempty \(10^{-4}\) feasible region;
- the learned or deterministic constrained policy beats Always-DUP in
  activation cost somewhere within that region;
- reliability conclusions have trajectory-aware uncertainty with the exposure
  hazards of §13.6 handled;
- U0 overlap and disclosure are resolved;
- the paper's claims match exactly what was evaluated.

If PPO is not the winning deployable policy but a forecast-aware constrained
contextual or deterministic controller is, the paper follows the evidence and
changes the method emphasis. **The core contribution is the validated
geometry-aware reliability-control problem and its empirical frontier, not an
obligation to make PPO win.**
