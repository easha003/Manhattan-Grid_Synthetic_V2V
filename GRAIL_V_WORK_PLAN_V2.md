# GRAIL-V — Settled Conference Work Plan (Version 2)

**Working title:**
**GRAIL-V: Geometry-Aware Reliability-Constrained Link Selection for Hybrid NR Sidelink/V-VLC in Urban V2V Networks**

**Document status:** implementation baseline

**Primary publication target:** IEEE VNC 2027 regular paper, subject to the official call

**Backup target:** IEEE VTC 2027-Fall regular paper

**Optional earlier target:** VTC 2027-Spring workshop only if all validation gates are passed without compressing the evaluation

This document supersedes the original `GRAIL_V_work_plan.md`. It incorporates the
paper-by-paper literature review and the subsequent decisions about the Manhattan
scenario, packet size, deadline, reliability target, observability, channel models,
training, statistics, and publication positioning.

---

## 1. Final project decision

The conference paper will study a single tagged following-vehicle V2V pair in
microscopic urban traffic. Each generated packet is sent over:

- NR sidelink only;
- vehicle visible-light communication (V-VLC) only; or
- both links simultaneously (DUP).

The controller minimizes normalized transmission activation cost while satisfying
an empirically evaluated deadline-miss constraint at each traffic-density level.

### 1.1 Headline service profile

| Parameter | Settled value |
|---|---:|
| Application | Compact cooperative V2V safety/status exchange |
| Information payload | 300 bytes |
| Packet generation interval | 100 ms |
| Decision interval | One decision per generated packet |
| Deadline | 1 ms radio-interface deadline |
| Headline miss constraint | \(P_{\mathrm{miss}}\leq 10^{-4}\) |
| Headline reliability | 99.99% |
| RF attempts per packet | One |
| VLC attempts per packet | One |
| DUP semantics | RF and VLC transmit simultaneously |
| Feedback HARQ inside 1 ms | None |
| RF resource assumption | Pre-reserved or semi-persistent sidelink opportunity |

The 300-byte quantity is the L2/3 information block passed to each PHY. Physical
framing and coding overhead are link-specific and must be accounted for separately.
The paper will not call this traffic a standardized CAM and will not claim that the
complete 300-byte/1-ms tuple is a 3GPP service profile.

### 1.2 Secondary reliability profiles

The conference paper will distinguish the headline claim from two secondary
questions:

1. **Standards-oriented eV2X frontier:** 300 bytes, 3 ms, target
   \(P_{\mathrm{miss}}\leq10^{-5}\).
2. **Extreme frontier:** 300 bytes, 1 ms, target
   \(P_{\mathrm{miss}}\leq10^{-5}\).

The \(10^{-5}\) experiments will be run only for the learned controller,
Always-DUP, the strongest deterministic policy, and the oracle. A five-nines result
will be claimed only when its one-sided, correlation-aware confidence bound is
below \(10^{-5}\). Otherwise it will be reported as an exploratory frontier.

A 2,000-byte service profile is not part of the headline conference experiment.
It may appear as a PHY-feasibility sensitivity point or later journal extension.

### 1.3 What the work will and will not claim

The intended claim is:

> A causal geometry-aware primal-dual policy can reduce transmission activation
> cost relative to unconditional duplication while meeting an empirically
> evaluated per-density \(10^{-4}\) deadline-miss constraint in a validated urban
> RF/VLC simulation.

The paper will not claim:

- a formal hard-safety guarantee from PPO;
- certified five-nines reliability;
- full 3GPP conformance;
- that PPO, RF/VLC aggregation, or packet duplication is individually novel;
- that a synthetic orthogonal grid is a calibrated model of all Manhattan traffic;
- that RF and VLC failures are independent;
- that every negative result is automatically publishable.

The defensible novelty is the conjunction of:

1. microscopic shared urban geometry driving mobility, RF state, VLC alignment,
   and third-vehicle blockage;
2. causal and age-aware RF/VLC observations with predicted blockage probability;
3. per-packet `{RF, VLC, DUP}` control under an explicit reliability budget; and
4. trajectory-level rare-event and burst-failure evaluation.

Novelty language will use “to the best of our knowledge” and will be restricted to
the reviewed and updated literature search.

---

## 2. Standards and application positioning

Three reference points must remain separate:

- 3GPP TR 38.913 gives a general URLLC reference of 32 bytes, 1 ms, and
  \(10^{-5}\), and an eV2X reference of 300 bytes, 3–10 ms, and \(10^{-5}\).
- 3GPP TS 22.186 gives cooperative collision avoidance at 2,000 bytes, 10 ms,
  and 99.99% reliability.
- The same TS gives emergency trajectory alignment at 2,000 bytes, 3 ms, and
  99.999% reliability.

Our headline profile deliberately studies a compact packet at an aggressive
radio-interface deadline while choosing \(10^{-4}\) as a statistically credible
conference constraint. It is a research stress case, not a copied standards row.

**Required wording in the paper:**

> We consider 300-byte compact cooperative safety packets generated at 10 Hz and
> impose a 1-ms radio-interface delivery deadline. The \(10^{-4}\) headline
> reliability budget is aligned with the 99.99% reliability class used by
> advanced-driving services, while the complete parameter tuple is a controlled
> stress scenario rather than a conformance profile.

Primary sources:

- 3GPP TR 38.913:
  <https://www.etsi.org/deliver/etsi_tr/138900_138999/138913/18.00.00_60/tr_138913v180000p.pdf>
- 3GPP TS 22.186:
  <https://www.etsi.org/deliver/etsi_ts/122100_122199/122186/18.00.01_60/ts_122186v180001p.pdf>

---

## 3. Research questions and hypotheses

### RQ1 — Feasibility

For which traffic densities can any policy, including Always-DUP and the oracle,
meet the \(10^{-4}\) deadline-miss budget?

### RQ2 — Duplication economy

Within the feasible region, can causal selective duplication reduce normalized
transmission activation cost relative to Always-DUP without violating the
constraint?

### RQ3 — Value of geometry prediction

Does noisy, age-aware blockage forecasting improve the reliability-cost frontier
over policies using only current and historical link measurements?

### RQ4 — Failure dependence

How do marginal RF failure, marginal VLC failure, and joint failure vary with
traffic density, pair separation, queue/intersection context, and predicted
occlusion?

### RQ5 — Ultra-reliability frontier

Under which densities and deadlines, if any, is \(10^{-5}\) statistically
supportable?

The hypotheses are directional rather than numerical:

- selective DUP will dominate unconditional DUP in activation cost where a
  feasible single-link opportunity exists often enough;
- forecast information will be most valuable before cut-ins, turns, and optical
  field-of-view loss;
- the benefit of hybrid diversity will shrink where common geometry or stale
  observations increase joint failure;
- the \(10^{-5}\) region will be smaller than the \(10^{-4}\) region and may
  require a relaxed 3-ms deadline.

No expected percentage saving, density threshold, run length, or spatial behavior
will be written into the abstract before results exist.

---

## 4. Mobility and urban scenario

### 4.1 Controlled Manhattan-style training network

The main environment is a rectangular Manhattan-style SUMO grid:

| Parameter | Settled value |
|---|---:|
| Grid size | 6 avenues × 12 cross streets |
| Blocks | 5 × 11 |
| Avenue spacing | 244 m |
| Cross-street spacing | 61 m |
| Main road abstraction | One lane per direction |
| Evaluation region | Interior 4 avenues × 8 cross streets |
| Default speed limit | 11.18 m/s (25 mph) |
| Mobility step | 50 ms |
| Nominal signal cycle | 90 s |
| Signal offsets | Staggered, not synchronized |
| Main turn probabilities | Left 25%, straight 50%, right 25% |
| Straight-heavy sensitivity | Left 10%, straight 80%, right 10% |
| Warm-up | 300 s |
| Saved trace duration | 900–1,800 s |

The approximately 244 m by 61 m spacing represents the characteristic long,
rectangular Manhattan block rather than the original 250 m square abstraction.
The one-lane-per-direction design is intentionally controlled and is not presented
as a literal lane map of Midtown.

SUMO will use microscopic car-following and lane-changing. Boundary vehicle
arrivals may be approximately Poisson, but steady-state vehicle positions will
not be described as a spatial Poisson process because signals, queues, and
car-following create correlations.

### 4.2 Density definition

Traffic density is defined unambiguously as:

\[
\rho_L(t)=
\frac{N_{\mathrm{active}}(t)}
{\text{total lane length in km}}.
\]

The training levels are:

\[
\rho_L\in\{20,40,60\}\ \text{vehicles/lane-km}.
\]

For the simplified one-lane-per-direction network these correspond to
approximately \(\{40,80,120\}\) vehicles per road-centerline kilometer, preserving
the intended low/medium/high levels of the original plan.

Entry flows will be tuned until the post-warm-up realized density is within 5% of
its target. Every trace manifest will also report mean speed, stopped fraction,
queue length, throughput, and unsuccessful insertions. Density will never be
inferred only from requested flow.

Interpolation tests will use 30 and 50 vehicles/lane-km. An extrapolation test
will use 70 vehicles/lane-km only if SUMO remains stable and the network is not
fully gridlocked.

### 4.3 Vehicles

The initial mixture is:

| Type | Share | Length | Width | Height |
|---|---:|---:|---:|---:|
| Passenger car | 90% | 4.5 m | 1.8 m | 1.5 m |
| Van/SUV | 7% | 5.2 m | 2.0 m | 2.0 m |
| Bus/truck | 3% | 10–12 m | 2.5 m | 3–3.5 m |

Heavy-vehicle shares of 0%, 5%, and 10% will be used for blockage sensitivity.
The final mixture for the real-map test will be checked against vehicle
classification information available in NYC DOT counts.

### 4.4 Tagged pair

The tagged transmitter follows the tagged receiver:

- same travel direction;
- same planned route;
- an episode begins when the natural trace contains an eligible pair separated
  by 10–60 m;
- results stratified into 10–20, 20–40, and 40–60 m;
- both vehicles may pass through intersections and make the same turn;
- an intermediate or adjacent large vehicle may block the optical line.

Perpendicular crossing-pair communication is excluded because a conventional
headlamp-to-rear-photodiode link does not support it without side-facing or
multi-directional optical hardware.

The tagged pair must be created without forcing impossible kinematics. The
service episode ends when the pair leaves the 10–60 m range continuously for one
second or their routes diverge. Vehicles are never teleported to preserve a pair.

### 4.5 Real Manhattan robustness network

The frozen policy will also be evaluated on one OSM-derived Manhattan subnetwork.
The region will be chosen through a reproducible data-coverage audit:

- approximately 1 km²;
- orthogonal street structure;
- no bridge or tunnel portal inside the region;
- no dominant superblock or pedestrian plaza unless explicitly modeled;
- sufficient NYC DOT volume-count coverage at boundary or interior approaches.

The selection audit, chosen bounding box, OSM snapshot date, edit log, lane
directions, prohibited turns, and signal corrections will be archived.

Boundary flows will be calibrated to one weekday off-peak period and one weekday
peak period using NYC DOT traffic counts. The paper will identify this as a
map-and-count-calibrated robustness test, not a complete Manhattan traffic model.

Primary sources:

- SUMO Manhattan tutorial: <https://sumo.dlr.de/docs/Tutorials/Manhattan.html>
- SUMO scenario guide: <https://sumo.dlr.de/docs/Tutorials/ScenarioGuide.html>
- NYC DOT traffic data:
  <https://www.nyc.gov/html/dot/html/about/datafeeds.shtml>

---

## 5. Shared geometry and hidden simulator state

The exact simulator state contains:

- all vehicle positions, dimensions, headings, speeds, and lane IDs;
- building polygons;
- traffic-signal phases;
- exact current RF propagation class;
- exact current optical line intersection and field-of-view status;
- shadowing/fading realizations;
- resource collision realization; and
- counterfactual success outcomes for all actions.

This information is used to generate outcomes and oracle results. It is not
directly exposed to the learned or deterministic deployable policies.

### 5.1 RF geometry classes

The tagged RF link is classified from common geometry as:

- LOS;
- NLOSv when blocked by a vehicle; or
- NLOS when buildings obstruct the link.

The geometry engine must be deterministic for a fixed trace and must have tests
for boundary contact, partial rectangle intersection, heading rotation, and
building-corner cases.

### 5.2 VLC geometry

The optical link uses:

- transmitter and receiver pose;
- headlamp radiation direction;
- photodiode incidence angle and field of view;
- two-dimensional footprint intersection plus blocker height;
- pair separation;
- optional residual reflected/NLOS floor; and
- ambient-light condition.

The default headlamp and receiver height is approximately 0.7 m. Exact dimensions
and optical parameters will be source-locked in the channel calibration manifest.

The main experiment uses clear nighttime ambient conditions. A clear-day/high-
ambient robustness condition is included. Rain, fog, and snow are excluded from
the conference scope.

---

## 6. Causal observations and blockage prediction

The controller observes no exact blocker flag and no simulator future.

### 6.1 Observation vector

At packet \(t\), the observation contains:

- latest RF received-quality proxy and its age;
- latest VLC received-quality proxy and its age;
- an eight-packet history of each quality proxy;
- RF channel-busy ratio and neighbor count;
- noisy pair distance and bearing;
- noisy relative speed and heading difference;
- current optical alignment/FOV margin;
- predicted probability of blockage within 200 ms;
- predictor confidence or track age;
- previous action;
- last delivery outcome; and
- current consecutive-miss count.

There is no head-of-line slack because packets do not queue across their
1-ms deadlines in the headline model.

### 6.2 Sensor/track abstraction

The baseline track model uses:

- 20 Hz track updates;
- 50 ms nominal observation latency;
- zero-mean position noise with 0.5 m standard deviation;
- zero-mean speed noise with 0.2 m/s standard deviation; and
- a 200 ms constant-velocity prediction horizon.

These are declared simulation assumptions, not claimed sensor measurements.
Noise and latency sensitivities will use half and twice the baseline values.

The predictor propagates track uncertainty and produces a blockage probability,
not a perfect future binary state. A simple Monte Carlo footprint propagation is
acceptable initially; an analytic approximation may replace it if verified
against the Monte Carlo output.

### 6.3 Action-dependent information

To preserve a defensible sequential decision problem:

- RF busy ratio remains continuously observable;
- a fresh post-transmission RF quality/ACK measurement is obtained when RF or
  DUP is used;
- a fresh VLC quality/ACK measurement is obtained when VLC or DUP is used;
- the unused link’s most recent quality measurement becomes older.

Thus the current action affects future information freshness. A constrained
contextual policy that ignores history and feature age will be included as a
baseline. If action-dependent information provides no measurable benefit, the
paper will describe the problem as contextual rather than overclaiming MDP
sequentiality.

---

## 7. RF channel and NR sidelink abstraction

### 7.1 Physical assumptions

The initial RF configuration is:

| Parameter | Main value |
|---|---:|
| Carrier | 5.9 GHz |
| Channel bandwidth | 10 MHz |
| Subcarrier spacing | 30 kHz |
| Nominal sidelink slot | 0.5 ms |
| Vehicle transmit power | 23 dBm |
| Antenna height | 1.5 m |
| Resource mode | NR sidelink Mode 2 with pre-reserved opportunity |

The large-scale channel follows the 3GPP TR 37.885 urban-grid LOS/NLOSv/NLOS
family. Shadowing must be spatially correlated. Small-scale fading must be
temporally correlated or generated from a defensible vehicular model rather than
resampled independently every packet.

### 7.2 Congestion and collision calibration

The original arbitrary monotonic neighbor-count-to-collision mapping is rejected.
Instead:

1. run offline 5G-LENA NR-V2X Mode-2 campaigns over the relevant density, CBR,
   distance, MCS, and propagation conditions;
2. fit a surrogate packet-collision/BLER model using only deployable inputs;
3. reserve complete simulation configurations for held-out validation;
4. report surrogate calibration error and tail error;
5. use the surrogate inside fast RL trace replay.

If 5G-LENA cannot produce a validated calibration in the project window, the
fallback is a clearly scoped analytical collision model plus sensitivity bands.
The paper will then weaken all Mode-2 realism claims.

### 7.3 RF packet error

The RF link will use either:

- calibrated MCS/transport-block BLER curves; or
- a finite-blocklength approximation whose channel-use, modulation, coding, and
  validity assumptions are explicitly documented.

The extra \(+\tfrac{1}{2}\log_2 n\) term will not be attributed to P11. It will be
included only with its correct source and convention. A single generic
finite-blocklength expression will not be applied automatically to VLC.

---

## 8. V-VLC channel

### 8.1 Physical model

The conference model is an IM/DD vehicle-light link using:

- a measured or empirically tabulated non-Lambertian automotive headlamp pattern;
- headlamp-to-rear-photodiode geometry;
- receiver area, responsivity, optical filter/concentrator, and field of view;
- ambient shot noise and receiver thermal noise;
- modulation-specific BER/PER;
- complete direct-path blockage as the main case; and
- a calibrated residual optical floor as a sensitivity.

The final model will be cross-checked against Veins-VLC or the closest reproducible
empirical headlamp implementation. W18’s infrastructure-to-vehicle ray-traced
parameters will not be transferred directly to the V2V headlamp case.

### 8.2 One-millisecond feasibility

Before learning, the PHY gate must verify:

\[
R_{\min}=\frac{8B_{\mathrm{PHY}}}{T_{\mathrm{air}}}.
\]

For a 300-byte information block:

- 2.4 Mbit/s is required if the full 1 ms is available;
- 3 Mbit/s is required if only 0.8 ms is available;
- approximately 6 Mbit/s is required at code rate 1/2 before other overhead.

The selected VLC hardware abstraction must therefore support the complete coded
block within its allocated airtime. A 1-Mbit/s VLC configuration cannot be used
for the headline profile.

The nominal optical electrical bandwidth starts at 5 MHz, but the gross rate,
modulation, code rate, and packet duration will be fixed only after this
feasibility calculation and empirical-model check. No result is produced until
the complete packet fits physically.

### 8.3 Failure dependence

For every scenario, log:

\[
p_{\mathrm{RF}},\quad
p_{\mathrm{VLC}},\quad
p_{\mathrm{joint}},
\quad\text{and}\quad
\frac{p_{\mathrm{joint}}}{p_{\mathrm{RF}}p_{\mathrm{VLC}}}.
\]

This prevents the diversity result from silently assuming independent failures.
Conditional values will be reported by density, separation, intersection
distance, propagation class, and predicted-blockage bin.

---

## 9. Packet lifecycle and timing

For each generated packet:

1. form the observation from the latest causally available measurements
   immediately before the known periodic generation instant;
2. run the policy before that instant and record its inference time;
3. create one packet ID, generation time, information size, and 1-ms
   radio-interface deadline;
4. apply the preselected action to the already-reserved RF and/or VLC opportunity;
5. transmit one copy per selected leg;
6. calculate link-specific decoding and arrival outcomes;
7. deliver the packet at the first successful arrival;
8. discard the other copy after its already-committed cost is counted;
9. declare a miss if neither selected copy arrives by 1 ms; and
10. log the cause as collision, RF channel failure, VLC alignment/occlusion,
    PHY infeasibility, decoding lateness, or joint failure.

The policy decision is scheduled before packet generation because the headline
traffic is periodic. The 1-ms clock begins when the L2/3 information block enters
the radio interface. Policy runtime is therefore not silently subtracted from
the radio deadline, but p99 inference below 100 microseconds remains an
engineering requirement so the action can be refreshed close to generation.

For DUP:

\[
\mathrm{delivered}=
\mathrm{RF\ delivered}\lor\mathrm{VLC\ delivered},
\]

\[
T_{\mathrm{delivery}}=
\min(T_{\mathrm{RF}},T_{\mathrm{VLC}})
\]

over successful copies.

There is no early cancellation in the headline design because the legs transmit
simultaneously. Both legs always incur their activation cost.

---

## 10. Control problem

### 10.1 Action

\[
a_t\in\{\mathrm{RF},\mathrm{VLC},\mathrm{DUP}\}.
\]

### 10.2 Primary cost

The conference paper reports normalized transmission activation cost rather than
unmeasured joules:

\[
g(\mathrm{RF})=1,\qquad
g(\mathrm{VLC})=1,\qquad
g(\mathrm{DUP})=2.
\]

RF and VLC activations, airtime, and DUP usage are also reported separately.
A cost-ratio sensitivity will use
\(g(\mathrm{VLC})/g(\mathrm{RF})\in\{0.3,0.5,1.0\}\).
The value 0.3 is not called energy unless supported by measured power and airtime.

No network-wide resource-efficiency claim will be made because the tagged action
does not control the background fleet’s offered load.

### 10.3 Reliability cost

Evaluation uses:

\[
m_t=
\mathbf{1}\{\text{generated packet is not delivered by its deadline}\}.
\]

Training uses the conditional expected miss probability:

\[
c_t=
\widehat P(m_t=1\mid o_t,a_t).
\]

Using \(c_t\) gives a dense low-variance cost signal. Sampled binary misses remain
the ground truth for final evaluation.

### 10.4 Group-constrained average formulation

For density group \(k\):

\[
J_g(\pi)=
\limsup_{T\to\infty}\frac{1}{T}
\mathbb E_\pi\left[\sum_{t=0}^{T-1}g(a_t)\right],
\]

\[
J_{c,k}(\pi)=
\limsup_{T\to\infty}\frac{1}{T}
\mathbb E_\pi\left[\sum_{t=0}^{T-1}m_t
\mid \rho_L\in k\right].
\]

The optimization is:

\[
\min_\pi J_g(\pi)
\quad\text{subject to}\quad
J_{c,k}(\pi)\le 10^{-4}
\quad\forall k\in\{20,40,60\}.
\]

One multiplier is maintained for each training density:

\[
\lambda_k\leftarrow
\left[
\lambda_k+\eta_\lambda
(\widehat J_{c,k}-10^{-4})
\right]_+.
\]

The method is called **empirically reliability-constrained primal-dual PPO**.
“Hard constraint” and “guaranteed constraint” are avoided.

Consecutive-miss count is part of the observation and burst reliability is an
evaluation metric. A separate burst constraint is excluded from the conference
scope.

---

## 11. Learning method

### 11.1 Policy architecture

The initial controller is:

- actor MLP: two 64-unit tanh layers;
- reward/value critic: two 64-unit tanh layers;
- cost critic: two 64-unit tanh layers;
- categorical three-action output;
- clipped PPO objective;
- generalized advantage estimation;
- entropy regularization during early training; and
- observation normalization fitted on training traces only.

A GRU is not part of the initial implementation. It will be considered only if
history stacking fails against the contextual and deterministic baselines.

### 11.2 Trace replay

SUMO mobility, building geometry, and large-scale channel traces are generated
offline and immutable. Training replay samples:

- held-in training trajectories;
- online small-scale fading and calibrated collision randomness;
- online sensor noise;
- link-dependent measurements and feature ages; and
- sampled packet outcomes.

Every run is keyed by:

- configuration hash;
- mobility-trace hash;
- channel-calibration version;
- code commit;
- policy seed; and
- evaluation scenario seed.

### 11.3 Curriculum

The reliability curriculum is:

- first 10% of training: \(10^{-2}\);
- next 20%: \(10^{-3}\);
- final 70%: \(10^{-4}\).

The final checkpoint must spend most of training at the real \(10^{-4}\) target.
The multiplier, constraint estimate, policy entropy, cost, and per-density
violation must be logged throughout.

### 11.4 Training volume and seeds

- Five independent policy-training seeds.
- Up to \(10^7\) packet transitions per seed across the three training densities.
- Sixty-second episodes, equivalent to 600 safety packets at 10 Hz.
- Early stopping only on a disjoint validation set.
- Checkpoint selection based on reliability first, then minimum activation cost
  among reliable checkpoints.

The exact wall-clock budget is recorded after profiling; it is not promised in
the paper before measurement.

### 11.5 Inference

Inference is measured on a named CPU with:

- warm-up iterations;
- single-observation batch;
- one pinned software thread;
- median, p95, and p99 latency; and
- serialization/preprocessing reported separately.

The engineering gate is p99 policy computation below 100 microseconds. The paper
will claim compatibility with 1 ms only if the complete observation-to-action
path leaves enough time for the modeled transmission and decoding.

---

## 12. Baselines and ablations

All deployable policies receive the same causal observations. Only the oracle may
use hidden state and counterfactual outcomes.

### 12.1 Required baselines

1. **RF-only**
2. **VLC-only**
3. **Always-DUP**
4. **Forecast-aware deterministic gate**
   Uses predicted RF/VLC success, feature age, hysteresis, and a DUP threshold.
5. **Constrained contextual policy**
   Same current observation but no history or action-dependent belief.
6. **Fixed-penalty PPO**
   Same architecture, one tuned scalar miss penalty, no multiplier.
7. **Oracle**
   Chooses the least-cost action that succeeds using hidden counterfactual
   outcomes; clearly labeled non-deployable.

Uniform random and DDQN are removed from the conference baseline set.

### 12.2 Required ablations

1. No blockage forecast.
2. Perfect simulator blockage information, labeled a non-deployable upper bound.
3. One global multiplier versus one multiplier per density.
4. No measurement-age/action-dependent feedback.

If page space is tight, ablations 2 and 3 move to the artifact or arXiv version.

---

## 13. Evaluation design

### 13.1 Matched evaluation

All policies run on identical:

- mobility trajectories;
- packet generation times;
- fading and collision seeds;
- sensor-noise realizations;
- background load;
- deadlines; and
- action-cost rules.

Train, validation, and test splits are made by complete trajectory, route, and
random seed. Adjacent packets from one trajectory are never split across sets.

### 13.2 Headline success rule

A policy satisfies the primary reliability requirement only if:

\[
\text{one-sided 95% upper confidence bound on }
P_{\mathrm{miss}}
\le 10^{-4}
\]

at every primary density.

A point estimate below \(10^{-4}\) is insufficient.

### 13.3 Primary sample size

For every policy-density condition:

- at least \(10^6\) raw packet outcomes;
- at least 200 independent trajectory/pair clusters, supplemented by
  within-trajectory blocks when justified;
- matched evaluation across policy seeds; and
- further sampling if the effective sample size is clearly inadequate.

Because failures are temporally correlated, packet-level Clopper–Pearson
intervals are not the headline uncertainty measure. Use trajectory/block
bootstrap or a cluster-aware one-sided interval. Raw miss count and denominator
are always reported.

### 13.4 Ultra-reliability sample size

For a claimed \(10^{-5}\) result:

- at least \(10^7\) raw outcomes in the selected condition;
- many independent trajectory/pair clusters;
- one-sided correlation-aware upper confidence bound below \(10^{-5}\); and
- no reuse of training or model-calibration trajectories.

If these conditions are not met, report the \(10^{-5}\) experiment as
underpowered exploratory evidence.

### 13.5 Metrics

Headline:

- deadline-miss probability;
- one-sided 95% upper confidence bound;
- normalized activation cost per generated packet;
- normalized activation cost per timely delivered packet; and
- reliability-cost frontier.

Mechanism and robustness:

- RF, VLC, and DUP selection fractions;
- useful, unnecessary, and insufficient DUP fractions;
- RF/VLC/joint failure probabilities and dependence ratio;
- miss-run survival curve and run-length quantiles;
- action probability versus predicted blockage and pair distance;
- action probability versus intersection distance and density;
- constraint and multiplier trajectories;
- interpolation/extrapolation performance;
- real-map performance delta; and
- CPU inference p50/p95/p99.

Raw maximum miss-run length is not compared without equal packet exposure.

### 13.6 Required feasibility checks before PPO

Before any learned result:

1. verify every selected PHY can transmit the complete block by its deadline;
2. measure RF-only, VLC-only, Always-DUP, and oracle;
3. confirm that the oracle can meet \(10^{-4}\) in at least part of the density
   range;
4. characterize \(p_{\mathrm{RF}},p_{\mathrm{VLC}},p_{\mathrm{joint}}\);
5. verify that the calibrated RF surrogate matches held-out 5G-LENA results;
6. verify the VLC availability/PER trend against empirical or Veins-VLC evidence;
7. check that exact hidden state cannot leak through the observation API.

If the oracle cannot meet the requirement, PPO training does not begin for that
condition. The condition is recorded as physically infeasible.

---

## 14. Decision gates

### Gate 0 — Scope and publication ethics

Pass conditions:

- service profile and claim language frozen;
- U0 overlap matrix completed;
- no copied text, figures, data, or results;
- shared conceptual elements identified for disclosure and citation;
- target venue policies checked.

### Gate 1 — Mobility credibility

Pass conditions:

- stable SUMO insertion and routing;
- realized densities within 5%;
- plausible mean speeds, queues, and signal response;
- no unexplained teleportation;
- tagged-pair separation logic verified;
- synthetic and real-map manifests archived.

### Gate 2 — PHY and channel credibility

Pass conditions:

- 300-byte block physically fits both selected links within 1 ms;
- RF surrogate validated on held-out 5G-LENA cases;
- VLC model validated against empirical/non-Lambertian evidence;
- LOS/NLOSv/NLOS and optical occlusion unit tests pass;
- residual-NLOS and ambient-light sensitivities defined.

### Gate 3 — Hybrid feasibility

Pass conditions:

- Always-DUP and oracle reliability characterized before training;
- joint failure is neither silently forced independent nor always identical;
- a nonempty \(10^{-4}\) feasible region exists;
- failure mechanisms can be explained from saved traces.

### Gate 4 — Learning validity

Pass conditions:

- medium-density constraint converges on held-out validation;
- per-density multipliers behave stably;
- policy improves activation cost over Always-DUP while remaining feasible;
- forecast/contextual ablations confirm or falsify the sequential story;
- inference gate passes.

### Gate 5 — Publication evidence

Pass conditions:

- all primary cells have at least \(10^6\) outcomes;
- one-sided cluster-aware bounds computed;
- conclusions survive five policy seeds;
- real-map robustness test complete;
- no result depends on a single unreported parameter choice;
- all figures reproducible from immutable result files.

---

## 15. Paper structure and page budget

The regular conference paper is designed for five main pages plus references or
the exact allowance of the selected venue.

### I. Introduction and related work — 0.9 page

- application and failure mechanisms;
- closest RF/VLC and duplication work;
- precise conjunction-based gap;
- three contributions.

### II. Shared-geometry system model — 1.25 pages

- Manhattan-style mobility and tagged pair;
- hidden geometry and causal observations;
- RF and VLC model summaries;
- packet/DUP timing;
- Table I parameters.

### III. Reliability-constrained control — 0.7 page

- observation, action, activation cost;
- per-density average constraints;
- primal-dual PPO;
- explicit empirical-not-formal wording.

### IV. Experimental methodology — 0.7 page

- channel calibration;
- trace splits and baselines;
- sample sizes and confidence method;
- real-map robustness.

### V. Results — 1.45 pages

- feasibility and reliability-cost frontier;
- policy mechanism/forecast value;
- burst and failure dependence;
- real-map and inference results.

### VI. Conclusion — 0.2 page

- what was demonstrated;
- infeasible regimes;
- multi-pair and weather extensions.

### Figures and tables

Only four main figures and two tables:

1. **F1:** system and shared-geometry scenario.
2. **F2:** RF/VLC calibration plus joint-failure environment characterization.
3. **F3:** miss-probability/upper-bound versus activation-cost frontier.
4. **F4:** policy interpretation, burst behavior, and real-map robustness as
   compact panels.
5. **Table I:** sourced simulation and PHY parameters.
6. **Table II:** policy reliability, confidence bound, cost, DUP fractions, and
   inference.

Training curves, full hyperparameters, extra ablations, and ultra-reliability
detail move to the artifact/arXiv supplement.

---

## 16. Reproducible repository design

```text
configs/
  mobility/
  channel/
  service/
  training/

src/grail_v/
  mobility/
  geometry/
  channels/rf/
  channels/vlc/
  phy/
  prediction/
  env/
  agents/
  baselines/
  evaluation/

scripts/
  generate_synthetic_traces.py
  import_manhattan_osm.py
  calibrate_rf_surrogate.py
  validate_vlc.py
  run_feasibility.py
  train.py
  evaluate.py
  make_figures.py

tests/
  unit/
  integration/
  regression/

artifacts/
  manifests/
  calibration/
  results/

paper/
```

Large generated traces and model checkpoints are not committed blindly. Each
artifact has a manifest with path, hash, generation command, source versions,
units, seed, and configuration.

### Mandatory tests

- unit conversion and coordinate transforms;
- rotated-rectangle and building intersection;
- optical FOV boundary;
- RF LOS/NLOSv/NLOS classification;
- packet timing and 1-ms expiration;
- simultaneous DUP OR-success and double-cost semantics;
- observation causality and feature ages;
- absence of hidden counterfactual leakage;
- per-density constraint accounting;
- deterministic replay from seed and hash;
- bootstrap implementation on synthetic known distributions.

---

## 17. Eighteen-week execution schedule

| Week | Deliverable | Gate |
|---:|---|---|
| 1 | Repository scaffold, configs, units, U0 overlap matrix, literature update strings | Gate 0 |
| 2–3 | Synthetic rectangular SUMO grid, vehicle demand, tagged pair, trace manifests, mobility tests | |
| 4 | NYC map/data audit, OSM import, network correction log, traffic-count calibration plan | Gate 1 |
| 5–6 | Shared geometry, RF propagation classes, vehicle/building occlusion, predictor and causality tests | |
| 7–8 | 5G-LENA Mode-2 calibration campaigns and held-out RF surrogate | |
| 7–8 | V-VLC empirical pattern integration, IM/DD PER, rate/timing and Veins-VLC cross-check | Gate 2 |
| 9 | Complete packet environment; RF/VLC/DUP/oracle feasibility; joint-failure analysis | Gate 3 |
| 10 | Strong deterministic and contextual baselines; freeze training/validation/test traces | |
| 11–12 | Primal-dual PPO, curriculum, per-density multipliers, inference profiling | Gate 4 |
| 13 | Five-seed full primary training and checkpoint selection | |
| 14 | Primary \(10^6\)-packet matched evaluations and ablations | |
| 15 | Real-map robustness and selected \(10^{-5}\) campaigns | |
| 16 | Cluster-aware statistics, final tables, four figures, reproducibility audit | Gate 5 |
| 17 | Full paper draft, internal technical review, overlap/disclosure review | |
| 18 | Revision, venue formatting, artifact freeze, submission | |

The schedule may finish earlier, but no publication deadline overrides Gate 2,
Gate 3, or the statistical requirements.

---

## 18. Risk register and fallback rules

### Risk 1 — The 1-ms optical packet does not fit

Response:

- increase the defensibly supported VLC rate or bandwidth if empirical hardware
  evidence supports it;
- otherwise move the headline deadline to 3 ms;
- never hide the infeasibility through an abstract capacity calculation.

### Risk 2 — NR Mode-2 calibration is too expensive

Response:

- reduce the calibration design using a space-filling parameter sample;
- fit and validate a compact surrogate;
- if validation remains poor, use the analytical fallback and weaken realism
  claims rather than presenting it as full Mode 2.

### Risk 3 — Always-DUP or oracle violates \(10^{-4}\)

Response:

- report that density/profile as infeasible;
- identify whether joint blockage, RF congestion, or PHY timing dominates;
- do not tune the learner against an impossible constraint;
- consider 3 ms only as a predeclared service-profile sensitivity.

### Risk 4 — PPO provides no advantage over a contextual rule

Response:

- report the stronger simpler method honestly;
- reframe the contribution around constrained geometry-aware control and
  environment/evaluation;
- retain PPO only if sequential feature age/history has demonstrated value.

### Risk 5 — \(10^{-5}\) is underpowered

Response:

- retain \(10^{-4}\) as the headline;
- report \(10^{-5}\) as an estimated frontier with its raw miss count and upper
  bound;
- do not use “five nines achieved.”

### Risk 6 — Real Manhattan import is unstable

Response:

- document every repair;
- use the controlled grid as the main experiment;
- omit the real-map claim if traffic calibration cannot pass Gate 1.

### Risk 7 — U0 overlap is too large

Response:

- remove reused text, figures, code, data, and result structures;
- replace inherited cost constants with the independently defined activation-cost
  formulation in this plan;
- disclose and cite U0 according to venue policy;
- stop submission if the scientific distinction is not clear.

---

## 19. U0 overlap and publication ethics

Before code is written, create a table comparing GRAIL-V and U0 across:

- application and service profile;
- mobility and geometry;
- RF model;
- VLC model;
- observation and predictor;
- actions;
- objective and constraint;
- algorithm;
- code;
- datasets/traces;
- figures/tables;
- numerical results; and
- manuscript text.

Expected allowed conceptual overlap is limited to the broad RF/VLC/DUP problem
family and any necessary self-cited context. GRAIL-V will use new geometry,
channel calibration, causal observation construction, training implementation,
traces, figures, results, and text. The phrase “zero overlap” will not be used.

---

## 20. Coding start order

Coding begins only after Gate 0 is documented. The implementation order is:

1. repository/configuration skeleton and units;
2. synthetic SUMO grid and density measurement;
3. tagged-pair extraction and immutable mobility traces;
4. exact hidden geometry and occlusion tests;
5. noisy causal observation and prediction;
6. independent RF and VLC channel validation;
7. packet lifecycle and RF/VLC/DUP baselines;
8. oracle feasibility and joint-failure analysis;
9. Gymnasium environment;
10. deterministic/contextual policies;
11. primal-dual PPO;
12. rare-event evaluation and paper figures.

The first coding milestone is therefore **not PPO**. It is a reproducible SUMO
trace containing realistic density, tagged-pair motion, and tested shared
geometry. Learning starts only after the physical feasibility gates pass.

---

## 21. Final go/no-go definition

The project proceeds to full conference submission when:

- a physically feasible RF and VLC packet model exists;
- the oracle demonstrates a nonempty \(10^{-4}\) feasible region;
- the learned or deterministic constrained policy beats Always-DUP in activation
  cost somewhere within that region;
- reliability conclusions have trajectory-aware uncertainty;
- the real-map robustness claim, if included, is calibrated and reproducible;
- U0 overlap and disclosure are resolved; and
- the paper’s claims match exactly what was evaluated.

If PPO is not the winning deployable policy but a forecast-aware constrained
contextual or deterministic controller is, the paper follows the evidence and
changes the method emphasis. The project’s core contribution is the validated
geometry-aware reliability-control problem and its empirical frontier, not an
obligation to make PPO win.
