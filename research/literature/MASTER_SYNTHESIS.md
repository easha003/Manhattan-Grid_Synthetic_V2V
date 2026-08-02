# Master synthesis of the RF/VLC/RL literature workbook

## Purpose and scope

This document consolidates the paper-by-paper research performed from
`RF_VLC_RL_literature_review.xlsx`. It is a knowledge handoff for the coding plan that will follow;
it is not itself a commitment to a particular simulator architecture or training algorithm.

The workbook has 41 rows but represents **43 underlying works**:

- one private/under-review target work (`U0`);
- 16 `P` rows containing 17 works because `P7` combines two distinct papers; and
- 24 `W` rows containing 25 works because `W23` combines two distinct papers.

Each public title was resolved against DOI, publisher, repository, arXiv, or institutional
metadata. Forty works were examined from complete primary text or a complete
author-expanded/fully indexed equivalent. The remaining public access exceptions are:

- `W10`: the publisher abstract and bibliographic/reference evidence were available, but a lawful
  complete manuscript was not found; and
- `W24`: the IEEE primary record was verified, while the method and reported comparison were
  reconstructed from independent technical descriptions because the four-page primary text was
  closed.

`U0` is not publicly retrievable and is treated as the proposed/under-review target rather than as
independent prior evidence. These access tiers are kept explicit so that a secondary description is
never silently presented as a direct paper claim.

## Detailed dossiers

The full technical notes contain citations, access routes, equations and models, state/action/reward
definitions, experimental settings, results, limitations, and implementation transfer:

| Workbook entries | Detailed notes | Works covered |
|---|---|---:|
| P1–P8 | [P1_P8.md](P1_P8.md) | 9 |
| P9–P16 | [P9_P16.md](P9_P16.md) | 8 |
| W1–W8 | [W1_W8.md](W1_W8.md) | 8 |
| W9–W16 | [W9_W16.md](W9_W16.md) | 8 |
| W17–W22 | [W17_W22.md](W17_W22.md) | 6 |
| W23–W24 | [W23_W24.md](W23_W24.md) | 3 |

The dossiers distinguish four evidence types throughout:

- **Direct:** stated in, or immediately implied by, the primary source.
- **Calculated:** computed or approximately read from reported material.
- **Inference / transfer:** an engineering conclusion for the planned work, not a source claim.
- **Caveat:** missing detail, inconsistency, access limitation, or validity risk.

## Paper-by-paper map

### Target and primary collection

| ID | Work | What it contributes | Critical boundary |
|---|---|---|---|
| U0 | *Belief-State Predictive Hybrid RF–VLC V2V* | Target concept: predictive belief state, hybrid V2V, reliability-aware control | Private/under review; not independent literature evidence |
| P1 | *Reinforcement Learning Approach for Hybrid WiFi–VLC Networks* | Load-aware tabular association and a reusable indoor VLC model | Indoor, throughput-only, no packets/deadlines; IEEE paper recovered through the author's expanded thesis |
| P2 | *Reinforcement Learning Based Network Selection for Hybrid VLC and RF Systems* | Context-aware action masking and Q-table transfer across LTE/WLAN/VLC contexts | Thirty-second single-network choices; highly abstract network utilities |
| P3 | *Deep Reinforcement Learning-Based User Association in Hybrid LiFi/WiFi Indoor Networks* | Sequential PPO reduces combinatorial multi-user association | Indoor throughput maximization; no queue, switching delay, or reliability constraint |
| P4 | *Learning-Based Energy-Efficient Resource Management by Heterogeneous RF/VLC for Ultra-Reliable Low-Latency Industrial IoT Networks* | Latency decomposition, heterogeneous resource accounting, post-decision-state RL | Static factory and soft penalties; not a formal long-run CMDP guarantee |
| P5 | *Link Selection in Hybrid RF/VLC Systems Under Statistical Queueing Constraints* | Effective-capacity/SNC queue tails, handover service loss, RF/VLC selection and simultaneous service | Analytical stationary abstraction, not vehicular physical simulation or RL |
| P6 | *A Hybrid Handover Scheme for Vehicular VLC/RF Communication Networks* | Finite-buffer CTMDP, RF/VLC handover costs, overlap/blocked-link decisions | ON/OFF and Poisson-rate abstraction; no physical V-VLC or NR sidelink |
| P7a | *Reinforcement Learning for Joint V2I Network Selection and Autonomous Driving Policies* | Coupling between motion decisions and future connectivity | RF/THz V2I, scalar reward, no VLC or packet deadlines |
| P7b | *Generalized Multi-Objective Reinforcement Learning With Envelope Updates in URLLC-Enabled Vehicular Networks* | Preference-conditioned vector returns and held-preference evaluation | Finite-blocklength rate only; no queues, expiry events, or reliability constraint |
| P8 | *Power Control of 5G-Connected Vehicular Network Using PPO-Based Deep Reinforcement Learning Algorithm* | Standards-observable radio features and discrete power-control actions | One-step/contextual-bandit-like PPO; V2I rather than sidelink; inconsistent power reporting |
| P9 | *Hierarchical Multi-Objective Deep Reinforcement Learning for Packet Duplication in Multi-Connectivity for URLLC* | Duplication externalities, hierarchical leg/packet decisions, first-arrival logic | Reward shaping rather than a reliability guarantee; source has damaged/inconsistent units |
| P10 | *Dynamic Packet Duplication for Industrial URLLC* | Lagged-KPI random-forest gate and useful/unnecessary duplication diagnostics | Supervised thresholding, not RL; incomplete model/training disclosure |
| P11 | *Towards Ultra-Reliable 6G in-X Subnetworks: Dynamic Link Adaptation by Deep Reinforcement Learning* | Power/blocklength adaptation, finite-blocklength error, consecutive outage runs | Preprint; state specification omits a reward-relevant outage counter |
| P12 | *Generalization in Reinforcement Learning for Radio Access Networks* | Feature age, history, broad domain randomization, topology-shift testing | Downlink MCS/HARQ at enormous scale, not hybrid packet routing or CMDP control |
| P13 | *Generalization of Deep Reinforcement Learning for Jammer-Resilient Frequency and Power Allocation* | Unseen-topology testing and model aggregation precedent | Short letter with many missing deployment details; unrelated DS-CDMA jammer setting |
| P14 | *Proximal Policy Optimization Algorithms* | Clipped surrogate, GAE, repeated minibatch updates on fresh on-policy data | PPO clipping is an optimization stabilizer, not a safety constraint |
| P15 | *Dota 2 with Large Scale Deep Reinforcement Learning* | Recurrent PPO systems engineering, data-version/staleness discipline, long-run migration | Not communications; its scale and “surgery” claims must not be copied as necessity |
| P16 | *Adaptive Tuning of Parameterized Traffic Controllers via Multi-Agent Reinforcement Learning* | Slow learned adaptation over a trusted fast controller; fault-localized hierarchy | Macroscopic traffic control with 30-minute actions, not packet-level communication |

### Wider collection

| ID | Work | What it contributes | Critical boundary |
|---|---|---|---|
| W1 | *Deep Reinforcement Learning Algorithms for Hybrid V2X Communication: A Benchmarking Study* | Direct vehicular RF/VLC action precedent and measured headlamp-pattern awareness | Easy two-car geometry; reward costs and success construction are not reproducible |
| W2 | *DRL-Based RAT Selection in a Hybrid Vehicular Communication Network* | Load-aware link/duplication selection and explicit redundant-traffic cost | Dual-RF RATs rather than RF/VLC; action/output and reward descriptions conflict |
| W3 | *Toward 6G-V2X: Aggregated RF-VLC for Ultra-Reliable and Low-Latency Autonomous Driving* | Analytical complementarity and fixed RF/VLC aggregation | Ten-thousand-trial evidence cannot substantiate a five-nines claim |
| W4 | *Evaluation of a New Radio Technology and Visible Light Communication for a Platooning Application* | Separate NR-like platoon and empirical V-VLC evaluation | Does not implement the hybrid controller suggested in its discussion |
| W5 | *Leveraging on the Synergy Between Visible Light Communication (VLC) and Radio Frequency (RF) to Enhance Intelligent Transport Systems (ITS)* | Simple QoS/geometry switching concept | Two-page work-in-progress with insufficient channel/simulator detail |
| W6 | *Design and Optimization of a Hybrid VLC/THz Infrastructure-to-Vehicle Communication System for Intelligent Transportation* | Geometry, optical/THz physical models, threshold combining | Static I2V layout and preprint status; not V2V or learned control |
| W7 | *Deep Reinforcement Learning-Based Adaptive Handover Mechanism for VLC in a Hybrid 6G Network Architecture* | RSS/location-based DQN handover and switch-count evaluation | Indoor VLC AP selection; state, reward, and training details are incomplete |
| W8 | *DQN-Based Multi-User Power Allocation for Hybrid RF/VLC Networks* | Continuous-observation advantage and feasible discrete allocation | Indoor sum-rate power allocation, not duplication or packet reliability |
| W9 | *Towards 6G C-V2X Networks: A Comprehensive Survey on Mobility Management, Multi-RAT Coexistence, and Machine Learning (3M) Framework for C-ITS* | Multi-RAT mobility taxonomy, prediction motivation, evaluation axes | Survey framework dominated by RF technologies; not evidence of a realized RF/VLC controller |
| W10 | *A Survey of Handover Approaches in Visible Light-Based V2X Communications* | Confirms blockage/alignment/ping-pong as V-VLC handover concerns | Abstract/reference-level access only; detailed method claims cannot be verified |
| W11 | *Handover Decision Techniques for Vehicle-to-Vehicle Communication in 6G Networks: Exploring Applications, Challenges, Future Trends Ahead* | Broad V2V handover taxonomy and future research questions | Survey evidence is uneven and should not replace primary validation |
| W12 | *Multi-Technology Integration in Hybrid V2X Networks: A Survey, Challenges, and Open Issues* | Systematic integration challenges, coexistence, security, and open issues | Taxonomy, not an implemented design or measured reliability result |
| W13 | *Machine Learning-Based Handovers for Sub-6 GHz and mmWave Integrated Vehicular Networks* | Cross-band prediction, candidate activation, make-before-break/bi-casting | V2N radio handover; kernel predictor and simplified mobility/channel assumptions |
| W14 | *Intelligent Handover Algorithm for Vehicle-to-Network Communications With Double-Deep Q-Learning* | Radio-measurement state, switching penalty, DDQN, conventional baselines | V2N single-connectivity handover; no optical physics or formal constraint |
| W15 | *6G-AUTOR: Autonomic CSI-Free Transceiver via Realtime On-Device Signal Analytics* | Asynchronous local measurements, factorized resource/power actions, small-case oracle | Resource allocation rather than handover; “CSI-free” still uses prior signal/interference observations |
| W16 | *Deep Reinforcement Learning and Permissioned Blockchain for Content Caching in Vehicular Edge Computing and Networks* | Projection of learned proposals onto discrete feasible assignments | Caching study; Manhattan coordinates are not microscopic SUMO mobility |
| W17 | *Vehicular Visible Light Communications: A Survey* | Canonical V-VLC link factors, applications, simulators, and experimental limitations | Survey models form an assumption family, not a single universally valid channel |
| W18 | *Infrastructure-to-Vehicle Visible Light Communications: Channel Modelling and Performance Analysis* | Ray-traced/fitted I2V path-loss model with a stated validity domain | Infrastructure periodicity and luminaire geometry do not transfer directly to V2V headlamps |
| W19 | *A Proposal for VLC-Assisting IEEE 802.11p Communication for Vehicular Environment Using a Prediction-Based Handover* | Angle prediction, hysteresis/chatter control, deterministic fallback baseline | Heuristic and simplified channel/traffic model; no learned reliability control |
| W20 | *INVISIBLE 2.0: An Enhanced Interference-Based Handover Technique for Visible Light Communications in Vehicular Networks* | Horizontal/vertical deterministic decision logic and energy accounting | Reliability metric/inequality semantics are ambiguous and must be normalized before reuse |
| W21 | *Distinguishing Micromobility and Blockage in 6G Sub-THz Systems: A Machine Learning Approach* | Estimate an outage cause/belief rather than exposing latent simulator truth | Synthetic joint-impairment construction and weakly isolated data split; sub-THz rather than VLC |
| W22 | *Deep-Reinforcement-Learning-Based Mode Selection and Resource Allocation for Cellular V2X Communications* | Remaining-time/bytes state and learned mode/resource/power decomposition | Cellular V2X abstraction; a printed reliability-constraint inequality has the wrong direction |
| W23a | *Enhancing Urban Intersection Efficiency: Visible Light Communication and Learning-Based Control for Traffic Signal Optimization and Vehicle Management* | SUMO/DQN traffic-signal example using VLC-provided traffic state | VLC channel is assumed, not simulated; no RF/VLC link decision or packet reliability |
| W23b | *Decentralized Multi-Agent Reinforcement Learning with Visible Light Communication for Robust Urban Traffic Signal Control* | Shared DQN experience, neighbor coupling, pedestrian state, and adaptive green duration | Five-intersection simulation with ideal VLC; no real-world communication validation |
| W24 | *Multi-Attribute Vertical Handover Decision-Making Algorithm in a Hybrid VLC-Femto System* | AHP/cooperative-game multi-criteria vertical-handover baseline | Indoor apartment, non-RL, primary full text closed; reconstructed result must remain secondary evidence |

## Integrated technical knowledge

### 1. The problem is sequential, not a sequence of independent classifications

An RF/VLC/DUP choice affects more than the current packet. It changes queue occupancy, resource
consumption, interference/load, switching state, the information returned to the controller, and
possibly the service available to later packets. This makes a sequential MDP/POMDP formulation
defensible. A contextual bandit or supervised DUP gate remains valuable as a baseline, but it
cannot represent delayed queue and switching consequences unless those are deliberately removed
from the environment.

### 2. RF and V-VLC physics must remain separate before they are combined

The literature consistently supports complementarity:

- RF offers broader availability and is less sensitive to optical alignment and line-of-sight
  blockage, but it is exposed to shared-spectrum load, interference, and fading.
- V-VLC can offer spatial reuse and high quality at favorable range/alignment, but it is strongly
  affected by transmitter radiation pattern, receiver field of view, incidence/irradiance angle,
  orientation, weather/ambient conditions, and physical blockers.

Indoor ceiling-LiFi parameters from `P1`, `P3`–`P5`, `W7`, and `W8` are not vehicle-headlamp
parameters. Likewise, `W18`'s I2V streetlight periodicity is not a V2V rear/front-light model.
Empirical or validated non-Lambertian vehicle-light patterns should be preferred where available,
and every optical model should declare its geometry and calibration domain.

The combined simulator should distinguish:

- per-link independent randomness, such as receiver noise or small-scale interference variation;
- link-specific structured failures, such as VLC FoV loss or RF resource congestion; and
- common causes, such as a turn, stale pose, processing overload, or a blockage configuration that
  affects both controller knowledge and service.

Multiplying marginal RF and VLC failure probabilities assumes independence and can grossly
overstate duplication diversity.

### 3. Mobility and blockage belong in geometry, not in a magic availability bit

The desired Manhattan setting requires microscopic trajectories, lanes, headings, turns, relative
poses, buildings, and third-vehicle geometry. An optical line-of-sight flag should be the result of
ray/shape intersection and FoV/orientation checks in hidden simulator state. A deployed policy may
instead observe measurements or a blocker probability produced by an estimator.

This distinction is central:

```text
hidden truth: exact pose, blocker identity, instantaneous channel realization
controller observation: delayed/noisy measurements, kinematics if sensor-available, feature ages,
                        recent actions and ACKs, and an estimated blockage belief
```

Giving the policy exact future blockage duration, next-packet success, or unobservable
counterfactual link outcomes is information leakage.

### 4. Packet and queue semantics must be defined before reward design

A defensible packet lifecycle needs:

1. generation time, size, service class, and deadline;
2. finite-queue admission and a recorded overflow reason;
3. scheduling/access time for each selected leg;
4. a unique copy identity for duplicated attempts;
5. physical decoding outcome and arrival time;
6. first-success delivery, redundant-copy discard/cancellation behavior;
7. deadline expiry; and
8. separate logging of overflow, late arrival, channel failure, and infeasible action.

Mean PHY rate or mean delay is not equivalent to deadline delivery. Queueing works (`P5`, `P6`)
show why service variability and handover interruption can dominate even when average link capacity
looks sufficient.

### 5. Duplication is an OR-success operation with real externalities

For a packet duplicated across RF and VLC:

```text
delivered_by_deadline =
    rf_delivered_by_deadline OR vlc_delivered_by_deadline

delivery_time =
    min(arrival time of every successful copy)
```

Both scheduled legs consume airtime/energy/resource and may generate interference unless a modeled
early-cancellation mechanism prevents some work. “Always DUP” therefore supplies a reliability
upper baseline only under a fixed budget; it is not free diversity. The useful diagnostics from
`P9` and `P10` are:

- DUP rate;
- useful DUP: only the secondary copy rescued the deadline;
- unnecessary DUP: the primary alone would have met it;
- insufficient DUP: neither copy met it;
- resource cost per timely delivered packet; and
- impact on queues/load and other links.

### 6. The observation should be causal, measurable, and age-aware

The strongest reusable observation pattern across the collection is:

- relative range, bearing, speed, heading, intersection/map phase when sensor-available;
- current and lagged RF SINR/RSRP/CQI proxies, busy ratio/load, queue state;
- current and lagged optical received-power/SNR/alignment proxies, ambient/weather indication;
- rolling ACK/PRR and deadline-outcome history;
- head-of-line age or normalized deadline slack;
- previous action, time since switch, and recent switch/ping-pong history;
- consecutive miss-run state; and
- an age/staleness value for asynchronously updated features.

Feature age is not cosmetic: a measurement that is 1 ms old and one that is 100 ms old should not
be interpreted identically in a moving blockage scenario.

History stacking is the simplest initial partial-observability mechanism. A recurrent policy is
justified only if it improves held-out predictive/control performance after data ordering, hidden
state reset, and policy-version hygiene are verified.

### 7. Reliability should be a separate CMDP cost

A scalar reward that trades misses against energy with a fixed weight cannot guarantee a declared
miss budget. The clean formulation suggested by the combined evidence is:

```text
action a_t ∈ {RF, VLC, DUP}

performance reward r_t =
    timely utility
    - RF/VLC resource or energy use
    - switching/ping-pong cost
    - optional bounded latency preference

safety cost c_t =
    1{generated safety packet is not delivered by its deadline}

constraint:
    long-run or episodic expected cost ≤ epsilon
```

The exact denominator must be fixed: generated safety packets, admitted packets, or attempted
packets produce different miss probabilities. Generated packets is the most conservative when
queue overflow is part of system failure.

For a PPO/Lagrangian implementation, reward and cost critics, advantage normalization, dual update
sign, multiplier projection, budget convention, and update time scales must all be explicit. PPO's
clipping parameter limits the incentive from a probability ratio; it is not a reliability bound.

### 8. Baselines must share the same environment contract

The literature supports at least:

1. RF only;
2. VLC when feasible with a precisely defined fallback;
3. always DUP;
4. best instantaneous measured quality/max-rate;
5. single-threshold RF/VLC switching;
6. two-threshold hysteresis/time-to-trigger;
7. queue/deadline-aware deterministic switching;
8. a `P10`-style lagged-KPI predictor plus DUP gate;
9. a multi-attribute/AHP-style handover rule;
10. unconstrained PPO with a fixed miss penalty;
11. constrained/Lagrangian PPO; and
12. hidden-counterfactual oracle, clearly labeled non-deployable.

Every policy must receive the same causal information and be evaluated on immutable matched traces,
traffic, resources, cancellation rules, and seeds. Otherwise, action-policy differences become
confounded with environment differences.

### 9. Reliability evaluation is a rare-event problem

Zero observed misses is not zero failure probability. With zero failures in `N` effectively
independent trials, the rule-of-three approximation gives a one-sided 95% upper bound of roughly
`3/N`. An upper bound below `10^-5` therefore needs more than about 300,000 effectively independent
packet outcomes. Bursty traffic, shared blockers, or correlated fading reduce the effective sample
size.

Evaluation should report:

- the miss count and denominator, not just a rounded delivery percentage;
- a binomial confidence interval or one-sided upper bound;
- latency p50/p95/p99 and only those more extreme quantiles supported by sample size;
- outage/miss-run length distribution;
- per-regime conditional failure: intersection, blocker, density, weather, RF load;
- RF/VLC/DUP shares, switches, ping-pongs, resources, and energy;
- useful/unnecessary/insufficient duplication;
- constraint trajectory during training and held-out evaluation; and
- multiple training seeds plus disjoint scenario/trajectory test seeds.

This is a major weakness in the prior collection: `W3`'s 10,000 trials cannot statistically
establish its five-nines language, and no collected RF/VLC RL paper demonstrates a hard
rare-event-validated reliability constraint.

## Closest precedents and the actual research gap

The collected works cover individual layers:

| Layer | Closest entries |
|---|---|
| Vehicular RF/VLC choice or aggregation | W1, W3–W5, W19–W20 |
| Optical physics and empirical validity | W1, W4, W17–W18 |
| Queue-aware hybrid selection/handover | P5–P6 |
| Packet duplication and its cost | P9–P10, W2–W3 |
| Predictive handover or outage-cause belief | W13, W19, W21 |
| Learned mode/resource/power control | P4, P8, P11, W15, W22 |
| Generalization and age-aware state | P12–P13 |
| PPO implementation discipline | P14–P15 |
| Microscopic urban traffic examples | W23a–W23b |

No collected work jointly provides:

- Manhattan microscopic V2V mobility;
- physical NR-sidelink RF and physical vehicle-light VLC;
- explicit third-vehicle optical blockage;
- causal partial observation with blockage belief/history;
- per-packet `{RF, VLC, DUP}` control;
- queues and deadline-defined success;
- switching and duplication resource costs;
- a formal long-run reliability constraint; and
- held-out distribution-shift plus rare-event confidence evaluation.

That conjunction—not a broad claim that PPO, hybrid RF/VLC, or handover is individually new—is the
defensible gap.

## Corrections that materially change how the workbook should be used

1. `P7` and `W23` each contain two papers and must not be cited as one work.
2. `P3`, `P11`, and `P12` are preprints at the checked versions; `P14` and `P15` are technical
   reports rather than peer-reviewed communications papers.
3. `P8` is a 2024 final article and its method behaves more like a one-step contextual bandit than
   trajectory PPO.
4. `P11` does not contain the extra finite-blocklength correction term attributed to it in the
   workbook.
5. `W15` is resource allocation, not handover; `W16` is content caching and does not establish
   SUMO Manhattan mobility.
6. `W23a` and `W23b` use VLC as an assumed traffic-information channel; they do not simulate or
   control hybrid RF/VLC communications.
7. `W22`'s printed reliability-constraint transformation has the wrong inequality direction:
   an outage upper bound implies a minimum mean-SINR condition, not a maximum one. The reward uses
   the intended direction.
8. `W20`'s PER/PRR threshold notation and inequality direction are ambiguous and must be rewritten
   under one explicit “higher is better” or “lower is better” convention.
9. `P9` contains damaged mathematical exponents and inconsistent traffic units across text/tables;
   its qualitative duplication logic is reusable, but its printed units are unsafe calibration
   inputs.
10. Claims of “URLLC-aware,” “99.999%,” or “<1 ms” must be mapped to what was actually measured:
    rate approximation, mean latency, delay outage, reward penalty, or statistically supported
    deadline reliability are different evidence levels.

## Readiness for the coding-plan prompt

The literature has now supplied:

- the physical and algorithmic components worth reusing;
- the assumptions that must not be copied from indoor or V2N settings;
- the minimum packet/duplication/observation semantics needed for a valid environment;
- the analytical, heuristic, learning, and oracle baselines;
- the reproducibility and rare-event evaluation requirements; and
- a precise novelty statement that does not overclaim.

Implementation has intentionally not started. The next work plan can now be checked against this
evidence before code structure, equations, parameters, and validation gates are fixed.
