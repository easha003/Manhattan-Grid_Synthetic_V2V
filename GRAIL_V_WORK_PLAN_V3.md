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

| \(\rho_L\) | Speed | \(v/v_{\text{free}}\) | Flow (veh/h/lane) | Regime |
|---:|---:|---:|---:|---|
| 5 | 5.85 | 0.52 | 105 | free |
| 20 | 5.44 | 0.49 | 392 | **undersaturated** |
| 30 | 4.81 | 0.43 | 520 | approaching capacity |
| 40 | 3.72 | 0.33 | 536 | **at capacity** |
| 60 | 2.59 | 0.23 | 558 | **oversaturated** |

Flow saturates near 550 veh/h/lane between \(\rho_L=40\) and 60. The
**holding capacity of the network is 72 veh/lane-km**, and a density beyond it
is rejected at construction rather than silently under-filled.

### 4.5.1 Why the training densities are 10 / 20 / 30

The original \(\{20,40,60\}\) was inherited, not measured. A sweep of the two
quantities the hybrid argument actually depends on shows why it was the wrong
band:

| \(\rho_L\) | Optical path blocked | Neighbours within 200 m | Regime |
|---:|---:|---:|---|
| 5 | 5.3% | 30 | free |
| 10 | 12.2% | 67 | free |
| 20 | 22.5% | 114 | free |
| 30 | 30.6% | 180 | free |
| 40 | 26.2% | 156 | at capacity |
| 60 | 30.7% | 197 | oversaturated |

**Both impairments stop responding to density above \(\rho_L\approx30\).**
Blockage climbs cleanly to 30.6% and then flattens; neighbour count does the
same and even falls, because past capacity vehicles pack into queues rather
than spreading through the sensing radius. Under \(\{20,40,60\}\) two of the
three points were effectively one operating condition — 1.4× spread in
blockage and 1.7× in neighbours, against 2.5× and 2.7× for
\(\{10,20,30\}\).

Beyond \(\rho_L=30\) the model measures queueing, not communication.

**Consequences for the generalization tests:**

- Interpolation: **15 and 25 veh/lane-km**, inside the responsive band.
- Extrapolation: **40 veh/lane-km**, the first point past capacity. The
  original 70 is abandoned — at 97% of holding capacity realised density falls
  10.2% below target, failing the tolerance twofold.

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

**Optical path blocked, by separation** — the structure a policy can act on:

| Separation | \(\rho_L=10\) | \(\rho_L=20\) | \(\rho_L=30\) |
|---|---:|---:|---:|
| 5–10 m | 1.3% | 8.7% | 16.0% |
| 10–20 m | 3.6% | 41.5% | 21.5% |
| 20–30 m | 20.0% | 51.0% | 46.8% |
| 30–40 m | 36.1% | 32.0% | 30.1% |

**Aggregate availability and RF load:**

| \(\rho_L\) | VLC blocked | VLC available | Neighbours within 200 m |
|---:|---:|---:|---:|
| 10 | 9.1% | 90.9% | 54 |
| 20 | 29.0% | 71.0% | 105 |
| 30 | 14.1% | 85.9% | 199 |

Three properties follow, and each maps to a research question:

1. **V-VLC is genuinely intermittent** — available 71–91%, blocked 9–29%. There
   is a real trade-off for selective duplication to exploit (RQ2).
2. **Blockage varies 28× with separation at \(\rho_L=10\)** (1.3% → 36.1%) on a
   quantity the policy observes directly. A short link is nearly always clear; a
   long one is frequently swept by cross-traffic at junctions. That is the
   conditional structure the 200 ms forecast is meant to predict (RQ3, H3).
3. **The two impairments have different drivers.** Neighbour count scales
   cleanly 3.7× with density; optical blockage scales with separation and only
   weakly and non-monotonically with density. They do not track each other,
   which is the condition diversity requires (RQ4).

**Caveat on the density marginal.** Blockage is non-monotonic in density
(9.1% → 29.0% → 14.1%) because episode sampling weights pair-instants by
episode duration, and closely-spaced queued pairs persist far longer than
free-flowing ones. The median separation of sampled instants is therefore
7.0 m, 14.1 m and 7.0 m rather than monotone. **Cross-density comparisons must
be stratified by separation**, which §13.6 already requires for a related
reason.

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

### 4.8 Determinism and reproducibility

One seeded generator per trace, derived through the project's named-stream
mechanism. The same seed and configuration reproduce trajectories bit-exactly,
which is what allows a trace to be regenerated rather than stored indefinitely
and what makes the two-pass artifact writer of §16.2 safe.

---

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

### 6.2 Sensor and track abstraction

20 Hz track updates; 50 ms nominal observation latency; zero-mean position
noise with 0.5 m standard deviation; zero-mean speed noise with 0.2 m/s
standard deviation; 200 ms constant-velocity prediction horizon.

These are declared simulation assumptions, not claimed sensor measurements.
Noise and latency sensitivities use half and twice the baseline values.

The predictor propagates track uncertainty and produces a blockage
**probability**, not a perfect future binary state.

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
- residual-NLOS and ambient-light sensitivities defined.

### Gate 3 — Hybrid feasibility — **hard stop**

- Always-DUP and oracle reliability characterized before training;
- joint failure neither silently forced independent nor always identical;
- a nonempty \(10^{-4}\) feasible region exists;
- failure mechanisms explainable from saved traces.

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
paper/ research/
```

Business logic lives in the package; `scripts/` contains thin drivers only.

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
**no overlapping vehicle footprints in any recorded frame**.

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

1. **Begin M2 geometry** against the frozen traces in `artifacts/traces/`
   (config hash `6dc49408`). Buildings are derivable from `GridNetwork`;
   intersection distance is `edge.length_m - offset_m`. The occlusion engine
   must reproduce the separation-conditioned blockage of §4.6.1 — that table is
   its acceptance test.
2. **Source or bound the IDM time headway** (§4.7 item 1). It sets the capacity
   in §4.5 and is currently undeclared.
3. **Obtain W18** before Gate 2 needs it for VLC validation.
4. Decide whether to tighten the density tolerance to 2% (§14 Gate 1).
5. Review the \(10^{-5}\) curriculum split (§11.3).
6. Consider whether multi-lane roads are worth the cost (§4.7 item 3). They are
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
