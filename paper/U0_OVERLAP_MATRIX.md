# U0–GRAIL-V Overlap and Independent-Contribution Matrix

**Artifact purpose:** Gate-0 publication-governance record  
**Artifact status:** Provisional; author verification is required  
**Prepared:** 2026-07-28  
**GRAIL-V implementation baseline:** `GRAIL_V_WORK_PLAN_V3.md` and
`CODE_IMPLEMENTATION_SPEC.md`

## 1. Gate status

This document records what can currently be established about the relationship
between GRAIL-V and the private/under-review work identified as U0,
*Belief-State Predictive Hybrid RF–VLC V2V*.

The available project records establish only the following facts about U0:

- it is private and under review;
- it concerns hybrid RF/VLC V2V;
- its target concept includes a predictive belief state; and
- its control objective is reliability-aware.

No U0 manuscript, supplement, source-code snapshot, dataset manifest, figure
source, or result archive is available in the repository. Consequently, the
matrix below confirms **conceptual overlap in the problem family**, but it
cannot yet establish component-level independence.

**Current Gate-0 decision: NOT YET PASSED.**

Gate 0 may be marked passed only after an author compares the exact submitted
version of U0 and its associated artifacts against this matrix, resolves every
`AUTHOR-VERIFY` item, records the evidence, and completes the declaration in
Section 7.

## 2. Evidence boundary

This matrix is based only on:

1. [GRAIL_V_WORK_PLAN_V3.md](../GRAIL_V_WORK_PLAN_V3.md);
2. [CODE_IMPLEMENTATION_SPEC.md](../CODE_IMPLEMENTATION_SPEC.md); and
3. [research/literature/MASTER_SYNTHESIS.md](../research/literature/MASTER_SYNTHESIS.md).

The literature synthesis explicitly states that U0 is not publicly retrievable
and is not independent prior-art evidence. A feature inferred from U0's title
or one-line project description is therefore labeled as conceptual, not as a
verified technical detail.

Status terms used below:

- **CONFIRMED:** supported directly by the three records listed above.
- **CONCEPTUAL OVERLAP:** both works occupy the same broad problem family, but
  this does not establish shared implementation or expression.
- **AUTHOR-VERIFY:** the U0 primary artifact must be inspected before a
  comparison can be made.
- **PROHIBITED REUSE:** the GRAIL-V artifact must be independently created
  unless reuse is explicitly authorized, disclosed, cited, and permitted by
  the applicable venue and rights holder.

## 3. Technical and publication overlap matrix

| Dimension | GRAIL-V frozen design | U0 fact currently supported | Current overlap determination | Evidence/action required before Gate-0 approval |
|---|---|---|---|---|
| Application and positioning | Compact cooperative V2V safety/status exchange. The complete profile is presented as a controlled stress case, not a standardized CAM or a 3GPP conformance profile. | Hybrid RF/VLC V2V is confirmed at the title/concept level. The application is otherwise unknown. | **CONCEPTUAL OVERLAP:** same hybrid V2V domain. Application-level distinction is not assessable. | **AUTHOR-VERIFY:** record U0's exact application, use case, standards claim, topology, and intended contribution. If both papers use the same use case, state that shared context explicitly and identify the independent scientific question. |
| Service profile | Headline: 300-byte L2/3 information block, 100-ms generation interval, 3-ms radio-interface deadline, one attempt per selected leg, no feedback HARQ, and \(P_{\mathrm{miss}}\leq10^{-4}\). A \(10^{-5}\) frontier uses the same payload and deadline. | Payload, arrival process, deadline, target reliability, retransmission assumptions, and deadline boundary are unknown. | **AUTHOR-VERIFY.** No profile-level distinction is presently established. | Extract U0's payload, overhead boundary, generation process, deadline definition, reliability metric/target, HARQ/repetition rules, and resource reservation assumptions into a signed comparison note. |
| Mobility and road network | New microscopic SUMO design: controlled 6-avenue × 12-cross-street rectangular Manhattan-style grid; 244 m × 61 m spacing; 25 mph; 20/40/60 vehicles per lane-km; signalized queues; same-route following pair at 10–60 m; separate OSM/NYC-count robustness test. | U0 simulator, map, density definition, routes, vehicle mix, tagged-pair construction, and traffic calibration are unknown. | **AUTHOR-VERIFY.** The planned GRAIL-V design is fully specified, but its independence from U0 is unconfirmed. | Compare network files, bounding boxes, route/demand generators, random seeds, density definitions, tagged-pair rules, and calibration data. GRAIL-V must use newly generated manifests and trace hashes. Any common public map or traffic source must be disclosed as a shared external source. |
| Shared geometry and hidden state | One geometry engine drives vehicle/building obstruction, RF LOS/NLOSv/NLOS, optical alignment/FOV, and oracle-only counterfactual outcomes. Exact geometry and future state remain hidden from deployable policies. | U0's geometry representation and simulator-hidden variables are unknown. | **AUTHOR-VERIFY.** A belief-state title alone does not reveal the underlying geometry model. | Compare coordinate systems, blocker shapes, building treatment, geometry algorithms, hidden-state definitions, and oracle access. Do not copy U0 geometry code or regression fixtures. |
| RF model | 5.9 GHz, 10 MHz, 30 kHz SCS, nominal 0.5-ms slot, 23 dBm, TR 37.885 urban-grid LOS/NLOSv/NLOS family, correlated shadowing/fading, and a deployable-input Mode-2 collision/BLER surrogate calibrated offline against held-out 5G-LENA campaigns. | U0's RF technology, carrier, equations, propagation classes, congestion/resource model, calibration source, and fading assumptions are unknown. | **AUTHOR-VERIFY.** Hybrid RF is the only confirmed common element. | Compare every RF equation, numerical constant, parameter source, simulator configuration, calibration sample, fitted model, and validation split. Shared standards equations are acceptable only when independently implemented and cited to the primary standard; document that common external origin. |
| V-VLC model | IM/DD headlamp-to-rear-photodiode link using a measured or empirically tabulated non-Lambertian automotive pattern, receiver FOV/orientation, ambient and thermal noise, modulation-specific BER/PER, explicit blocker geometry, full direct-path blockage as the main case, and a separately calibrated residual-floor sensitivity. The 300-byte coded block must pass a 3-ms timing gate within the declared optical bandwidth. | U0's optical geometry, radiation pattern, modulation, receiver, noise, blockage, timing, and empirical calibration are unknown. | **AUTHOR-VERIFY.** Hybrid VLC is the only confirmed common element. | Compare equations, headlamp tables, receiver parameters, modulation/coding, noise terms, blockage treatment, source data, and validation plots. Do not transfer U0 parameter tables or fitted constants without explicit source tracing and disclosure. |
| Observation construction | Causal, age-aware vector containing latest and eight-step RF/VLC quality histories, feature ages, CBR, neighbor count, noisy pair kinematics, optical margin, predicted blockage probability/confidence, previous action, prior delivery, and consecutive-miss count. Exact blocker state and counterfactual outcomes are excluded. | “Predictive belief state” is confirmed conceptually. Its inputs, history, uncertainty representation, causality rules, and latent-state access are unknown. | **CONFIRMED CONCEPTUAL OVERLAP:** both works use predictive information/belief in hybrid V2V control. The exact observation overlap is not assessable. | **AUTHOR-VERIFY:** produce a field-by-field schema comparison. Identify any identical feature, normalization, history window, age encoding, state-update equation, or belief representation. Shared conceptual prediction must be disclosed; exact state construction must be independently justified. |
| Predictor and sensing model | Simulated tracks at 20 Hz with 50-ms nominal latency, 0.5-m position noise, 0.2-m/s speed noise, uncertainty propagation, and a 200-ms constant-velocity blockage-probability forecast. Half/double noise and latency sensitivities are required. | U0 uses prediction at a concept level. Predictor type, horizon, track source, error model, and output semantics are unknown. | **CONFIRMED CONCEPTUAL OVERLAP:** prediction is central to both. Algorithmic or numerical overlap remains unknown. | Compare predictor equations/model architecture, horizon, sensor source, noise, latency, uncertainty calibration, training data, output definition, and update schedule. If U0 also uses constant velocity or the same horizon, explain why the GRAIL-V implementation and experiment remain distinct. |
| Action space and duplication semantics | Exactly `{RF, VLC, DUP}` per packet. DUP commits simultaneous copies to both links, succeeds on first timely arrival, incurs both activation costs, and has no early cancellation. | The project plan anticipates possible RF/VLC/DUP-family overlap, but the available U0 record does not verify its action set or DUP timing. | **AUTHOR-VERIFY.** Same broad link-selection family is possible; exact action overlap is unknown. | Record U0's actions, granularity, scheduling time, simultaneous/sequential semantics, retransmission/cancellation behavior, and delivery rule. If the three-action set is shared, disclose it as conceptual overlap and distinguish the state, objective, environment, and evaluation rather than claiming the action set as novel. |
| Primary objective/cost | Minimize long-run normalized leg-activation cost: RF = 1, VLC = 1, DUP = 2; report link use and sensitivity to VLC/RF ratios 0.3/0.5/1.0. No unsupported joule or network-wide resource-efficiency claim. | U0 is reliability-aware; its optimized utility, energy/resource definition, weights, and normalization are unknown. | **CONCEPTUAL OVERLAP:** reliability/resource trade-off may be shared, but the objective cannot be compared. | Compare objective equations, units, constants, discounting/averaging, switching terms, and normalization. GRAIL-V's cost constants must be independently defined; do not inherit U0 constants, labels, or reward decomposition. |
| Reliability constraint | Per-density long-run average deadline-miss constraints at 20/40/60 vehicles per lane-km, each with budget \(10^{-4}\). Training uses conditional expected miss risk; evaluation uses sampled binary misses and one-sided cluster-aware confidence bounds. Claims are empirical, not formal hard guarantees. | U0 is described only as reliability-aware. It is unknown whether reliability is a constraint, reward penalty, chance constraint, outage metric, or heuristic. | **CONCEPTUAL OVERLAP:** reliability is central to both. Mathematical-formulation overlap is unknown. | Compare event definitions, denominators, constraint equations, target values, group conditioning, estimator, statistical decision rule, and claim language. Any common formulation must be cited/disclosed and re-derived in GRAIL-V's setting. |
| Learning/control algorithm | Empirically reliability-constrained primal-dual PPO with separate reward and cost critics, one dual multiplier per density, clipped PPO, GAE, an explicit reliability curriculum, and action-dependent information freshness. A constrained contextual policy tests whether sequential RL is necessary. | “Belief-state predictive” and “reliability-aware control” are known. U0's policy class, optimizer, network, dual method, recurrence, and training procedure are unknown. | **AUTHOR-VERIFY.** Algorithmic independence is not established. | Compare pseudocode line by line; network inputs/layers; losses; dual updates; replay/on-policy design; curricula; hyperparameters; checkpoint rules; and seeds. If U0 uses PPO or a dual method, the paper must not present those generic algorithms as GRAIL-V novelty, and independent code provenance must be demonstrated. |
| Baselines and ablations | New evaluations of RF-only, VLC-only, Always-DUP, forecast-aware deterministic gate, constrained contextual policy, fixed-penalty PPO, and oracle; ablations cover forecast, perfect hidden blockage, multiplier grouping, and measurement age. | U0 baseline and ablation set is unknown. | **AUTHOR-VERIFY.** Reusing an evaluation structure can create substantive overlap even when the main algorithm differs. | Compare baseline definitions, thresholds, oracle logic, ablation questions, tuning protocol, names, ordering, and presentation. Reimplement required generic baselines and generate new outputs; disclose any baseline uniquely introduced by U0. |
| Software/code | GRAIL-V is specified as a new modular Python package with separate mobility, geometry, channel, prediction, environment, agent, evaluation, and artifact layers; typed interfaces, schema versions, deterministic randomness, tests, and provenance manifests are mandatory. | U0's repository, language, modules, dependencies, authorship, licenses, and code availability are unknown. | **PROHIBITED REUSE / AUTHOR-VERIFY.** New architecture is planned, but file-level independence cannot yet be certified. | Inventory all U0 source files and compare names, structure, APIs, equations, constants, comments, tests, and commit ancestry. GRAIL-V must not import, copy, translate, or mechanically rewrite U0 code unless explicitly authorized, licensed, disclosed, and technically justified. Record any independently reused public library or standards implementation by source and license. |
| Calibration data | New 5G-LENA RF calibration campaigns and separately sourced empirical/non-Lambertian optical calibration are required, each with versioned manifests and held-out validation cases. | U0 calibration inputs and fitted artifacts are unknown. | **AUTHOR-VERIFY.** Common public calibration sources may be legitimate but must not be hidden. | Compare raw source files, downloads, preprocessing, splits, fitted coefficients, and hashes. If the same public dataset is used, record it as a common external input and use a documented independent pipeline or explain the permitted reuse. |
| Mobility/training/evaluation data | New immutable SUMO traces, NYC robustness traces, online channel/sensor randomness, trajectory-level train/validation/test splits, and policy-specific results. Training/model-calibration trajectories cannot enter final evaluation. | U0 traces, scenario seeds, split rules, checkpoints, and evaluation records are unknown. | **PROHIBITED REUSE / AUTHOR-VERIFY.** GRAIL-V requires new data, but this must be confirmed by hash/provenance comparison. | Create manifests for both projects and compare every raw/generated artifact hash. No U0 trace, split, random tape, checkpoint, cached output, or result file may be relabeled as GRAIL-V evidence. |
| Planned figures and tables | Four main figures: system/shared geometry; RF/VLC calibration and joint-failure characterization; reliability–activation-cost frontier; and policy/burst/real-map interpretation. Two tables: sourced parameters and policy results. | U0 figures, tables, visual encodings, captions, source drawings, and result layout are unavailable. | **PROHIBITED REUSE / AUTHOR-VERIFY.** Generic topics may coincide, but expressive and data overlap cannot be assessed. | Compare every panel, axis, legend, caption, diagram object, icon, color mapping, table column, and source asset. Recreate GRAIL-V visuals from new source files and new results. Do not trace, restyle, or rearrange U0 artwork as a substitute for independent creation. |
| Numerical results | No GRAIL-V scientific results exist at Gate 0. Planned outputs include miss probability and upper bound, activation cost, action fractions, RF/VLC/joint failures, burst statistics, generalization, real-map delta, and CPU latency. | U0's numerical findings and raw denominators are unknown. | **PROHIBITED REUSE / AUTHOR-VERIFY.** There is currently nothing to compare on the GRAIL-V side. | Before drafting results, register immutable GRAIL-V result hashes and generation commands. Compare claimed metrics and experiment cells with U0. Do not reuse U0 numbers, plots, tables, trained policies, or derived statistics; cite U0 explicitly if a U0 result is discussed. |
| Conclusions and claims | GRAIL-V will claim only an empirically evaluated per-density reliability–activation-cost result in its validated simulator, plus measured prediction value and failure dependence. It will not claim formal safety, certified five nines, full conformance, independent RF/VLC failures, or novelty of PPO/duplication alone. | U0's contributions, novelty wording, findings, limitations, and conclusion are unavailable. | **AUTHOR-VERIFY.** Broad topical similarity is confirmed; claim-level distinction is unknown. | Compare abstracts, contribution lists, hypotheses, novelty statements, result claims, limitations, and conclusions. Rewrite or narrow GRAIL-V if the scientific distinction is not clear to a reasonable reader. |
| Manuscript text | GRAIL-V manuscript text has not yet been drafted. The current plan and engineering specification define scope but are not paper prose. | U0 manuscript text is unavailable. | **PROHIBITED REUSE / AUTHOR-VERIFY.** Textual independence cannot be tested yet. | Draft GRAIL-V from its new evidence and cite source material directly. Run a documented text-similarity review against the exact U0 submitted manuscript, including abstract, related work, equations, captions, tables, and supplementary text. Remove copied or close paraphrasing unless a short necessary quotation is permitted and cited. |
| Bibliography and external sources | GRAIL-V will cite primary standards, calibrated simulators/data, channel evidence, and the reviewed RF/VLC/RL literature according to the claim supported. | U0 bibliography is unknown. | Shared citations alone are not evidence of misconduct, but copied selection/order/annotations can indicate derivative drafting. | Compare source provenance. Cite primary sources directly rather than copying U0's descriptions. Verify every citation was read and supports the associated GRAIL-V statement. |

## 4. Confirmed common ground that must be disclosed

The current evidence is sufficient to record these similarities:

1. both works address hybrid RF/VLC communication in V2V;
2. both use prediction or belief about future/latent link conditions; and
3. both are concerned with reliability-aware control.

The GRAIL-V plan also anticipates possible overlap in RF/VLC/DUP link-selection
semantics. Because U0's exact action set is unavailable, that point remains
unverified and must not be stated as either a similarity or a distinction in a
submission until the author checks U0.

These common concepts are not claimed as individual GRAIL-V novelties. GRAIL-V's
proposed contribution is instead the conjunction of:

- new microscopic shared urban geometry;
- calibrated RF and empirical V-VLC link models;
- causal, noisy, age-aware observation construction;
- an explicit per-density empirical deadline-miss constraint;
- independently implemented control and baselines; and
- trajectory-level rare-event, joint-failure, and burst evaluation.

That conjunction remains a **proposed distinction**, not a verified distinction
from U0, until the primary U0 artifacts have been compared.

## 5. Reuse and provenance rules

The following rules apply throughout implementation and paper preparation:

1. **Code:** do not import, copy, translate, or mechanically rewrite U0 code.
   Any exception requires written authorization, license compatibility,
   technical necessity, explicit provenance, citation where appropriate, and
   venue-policy review before the code enters the GRAIL-V tree.
2. **Data:** create new GRAIL-V mobility, calibration, training, validation, and
   test manifests. Shared public source data must be identified by source,
   version, license, and hash.
3. **Parameters and equations:** standard equations and public parameters may be
   shared only through their primary external source. Record units, validity
   domain, implementation, and calibration independently.
4. **Figures and tables:** build every GRAIL-V figure and table from GRAIL-V
   source assets and immutable result records. Do not reuse a U0 source drawing,
   panel arrangement, caption, or result table.
5. **Results:** all GRAIL-V numerical evidence must be regenerated by the
   GRAIL-V pipeline. U0 results may appear only as clearly cited prior/related
   evidence.
6. **Text:** write new prose from the GRAIL-V design and evidence. Common
   terminology, standards names, and mathematical symbols do not remove the
   requirement for independent expression and correct citation.
7. **Disclosure:** identify U0 to the selected venue whenever its policy requires
   disclosure of related, concurrent, or prior work. Supply the manuscript and a
   concise distinction statement if requested.
8. **Change control:** rerun this review if U0 is revised, accepted, rejected,
   published, or extended, or if GRAIL-V's design changes materially.

## 6. Required author-verification register

| ID | Required evidence | Status | Resolution record |
|---|---|---|---|
| V01 | Exact U0 manuscript version submitted to the venue, including title page, appendices, and revision date/hash | Missing | — |
| V02 | U0 submission metadata: venue, status, submission identifier, authors, and applicable related-work/disclosure policy | Missing | — |
| V03 | U0 supplementary material and algorithm/pseudocode, if any | Missing | — |
| V04 | U0 source-code inventory, repository/commit snapshot, authorship, and license | Missing | — |
| V05 | U0 data, trace, calibration, checkpoint, and result manifests or an author attestation that no such reusable artifacts exist | Missing | — |
| V06 | U0 editable figure/table sources and a panel-by-panel comparison | Missing | — |
| V07 | Field-level technical comparison for service, state, predictor, action, objective, constraint, and algorithm | Missing | — |
| V08 | File/hash comparison demonstrating new GRAIL-V traces, calibration artifacts, checkpoints, and results | Pending implementation | — |
| V09 | Documented manuscript text-similarity review against the exact U0 submission | Pending GRAIL-V draft | — |
| V10 | Written related-work/disclosure statement reviewed against the selected venue's current policy | Pending venue selection/submission | — |
| V11 | Author determination that the remaining scientific contribution is sufficiently distinct; otherwise scope change or stop decision | Pending V01–V10 | — |

Sensitive U0 materials do not need to be committed to this repository. The
resolution record may instead cite a private immutable location and cryptographic
hash, provided every author who approves the submission can inspect it.

## 7. Gate-0 author declaration

Complete this section only after V01–V11 are resolved.

```text
U0 manuscript identifier/hash:
U0 code identifier/hash or “no code artifact”:
U0 data/result identifier/hash or “no data/result artifact”:
GRAIL-V commit reviewed:
Selected venue and policy version/date:

Confirmed shared concepts:

Confirmed technical distinctions:

Authorized/disclosed reuse, if any:

Items removed or redesigned after review:

Required disclosure/citation wording:

Gate-0 decision: PASS / FAIL
Reviewer name:
Reviewer role:
Review date:
Co-author concurrence:
```

A `PASS` decision means that the evidence supports a clear, honestly disclosed
scientific distinction and that prohibited reuse has been excluded or properly
resolved. It does not itself guarantee acceptance or replace the selected
venue's publication-ethics review.
