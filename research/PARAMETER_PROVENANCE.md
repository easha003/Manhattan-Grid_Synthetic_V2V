# Parameter provenance

The "resolved parameter table" that implementation spec §12.2 requires and work
plan §4.7 gestures at. Every physical constant the model computes with, what
backs it, and — the column that matters — **which conclusion moves if it is
wrong**.

This exists because unsourced values were scattered across module docstrings
where no reviewer would assemble them. A reviewer who finds one assumes there
are others. A reviewer handed the complete list assumes we know our own model.

## Status vocabulary

| Status | Meaning |
|---|---|
| **exact** | A defined physical or mathematical constant. Nothing to source. |
| **standard** | A conventional value in wide use. Needs a citation, not an argument. |
| **conservative** | Chosen pessimistically *on purpose*, with a sensitivity declared. This is the correct treatment for a value that cannot be sourced. |
| **unverified** | Written from a standard functional form; coefficients **not checked** against the primary document. |
| **unsourced** | Order-of-magnitude engineering judgement. No document claimed. |
| **guard** | Not physics — a validity limit that refuses extrapolation. |

**Count as of this revision: 5 exact, 3 standard, 2 conservative, 18 unverified,
8 unsourced, 4 guards.** The 18 unverified are all in one place — TR 37.885 —
and are therefore one afternoon of document-checking rather than 18 separate
research problems.

---

## Tier 1 — changes a headline result

| Parameter | Value | Status | Band | What it decides |
|---|---:|---|---|---|
| `desired_time_headway_s` | 1.2 s | **standard, uncited** | needed: 1.0 / 1.2 / 1.5 | Traffic capacity → the density band → the constraint groups. **And**, since §12.3, the bumper gap — which the optical budget divides by, **squared**. |
| `NLOSV_BLOCKAGE_MEAN_TALL_DB` | 9.0 dB | **unverified** | — | The entire NLOSv link margin. With antennas and car roofs both at 1.5 m, this is the *only* blockage value that ever fires. |
| headlamp pattern artifact | **absent** | **missing** | — | Every optical number. M4 cannot produce a result without it. |
| `RESPONSIVITY_A_PER_W` | 0.4 | **unsourced** | — | Scales the optical photocurrent linearly, so it moves the optical SNR one-for-one. |
| `ACTIVE_AREA_M2` | 1.0e-4 | **unsourced** | — | Same, and it is not free to increase: capacitance forces load resistance down, so thermal-limited SNR goes as *A*, not *A*². |

`desired_time_headway_s` is the one I would fix first. It was flagged as
unsourced when it only set capacity, and §12.3 quietly promoted it to the
leading term in the optical link budget. Nothing about that code change made the
promotion visible — it only appeared by working through the geometry. **An
unsourced number moved from the edge of the model to the middle of it.**

It is also the cheapest to fix: 1.2 s sits well inside the range Treiber,
Hennecke and Helbing use for the IDM, and adjacent to SUMO's default. The work
is not finding a citation, it is running the sensitivity — does "optical
improves with density" survive *T* ∈ {1.0, 1.2, 1.5}?

---

## Tier 2 — TR 37.885, one document, 18 values

All claimed from the 3GPP urban-grid family. The functional forms are standard
and almost certainly right; the coefficients have **not been read off the
document**.

| Parameter | Value | Note |
|---|---:|---|
| `LOS_INTERCEPT_DB` | 38.77 | |
| `LOS_DISTANCE_COEFFICIENT` | 16.7 | |
| `LOS_FREQUENCY_COEFFICIENT` | 18.2 | |
| `LOS_SHADOWING_SIGMA_DB` | 3.0 | |
| `NLOS_INTERCEPT_DB` | 18.9 | |
| `NLOS_DISTANCE_COEFFICIENT` | 36.85 | |
| `NLOS_FREQUENCY_COEFFICIENT` | 30.0 | |
| `NLOS_SHADOWING_SIGMA_DB` | 4.0 | |
| `NLOSV_BLOCKAGE_MEAN_SHORT_DB` | 5.0 | **unreachable** — with equal antenna heights the "between the two antennas" branch cannot fire |
| `NLOSV_BLOCKAGE_MEAN_TALL_DB` | 9.0 | Tier 1 |
| `NLOSV_BLOCKAGE_DISTANCE_COEFFICIENT` | 15.0 | **suspect** — see below |
| `NLOSV_BLOCKAGE_DISTANCE_OFFSET_DB` | 41.0 | **suspect** — see below |
| `NLOSV_BLOCKAGE_SIGMA_DB` | 4.5 | |
| `LOS_DECORRELATION_M` | 10.0 | |
| `NLOSV_DECORRELATION_M` | 10.0 | |
| `NLOS_DECORRELATION_M` | 13.0 | |
| `LOS_RICIAN_K_DB` | 9.0 | Decides how much deeper NLOSv fades than LOS |
| `URBAN_RMS_DELAY_SPREAD_S` | 200 ns | Sets coherence bandwidth → whether a subchannel hop buys diversity |

**One specific reason to check rather than assume.** The blockage growth term
`max(0, 15·log₁₀(d) − 41)` turns positive only beyond **541 m**, so across the
entire 5–100 m pair window it contributes exactly nothing. Vehicle blockage is a
flat offset with no distance dependence at all. That is either correct — the
term genuinely targets ranges far beyond V2V — or one of the two coefficients is
transcribed wrong. Both readings are live and the difference is material,
because a distance-dependent blockage would make NLOSv severity partly
predictable from separation, and today it is not.

---

## Tier 3 — declared conservative, already handled correctly

| Parameter | Value | Sensitivity | Note |
|---|---:|---|---|
| `receiver_fov_deg` | 60° | **30° configured** | Deliberately the *pessimistic* choice. Concentrator gain goes as n²/sin²ψc, so the wider cone collects ~10 dB less. Choosing the weaker front end means the hybrid result gets stronger under scrutiny, not weaker. |
| `sensing_reliability` | 0.70 / 0.85 / 0.95 | **band is the deliverable** | §7.2 requires bands because the Mode-2 calibration is deferred. The band is wide on purpose: narrowing it without doing the calibration would assert the result of work not done. |

These two are the template. A value that cannot be sourced is acceptable if it
is chosen pessimistically and its sensitivity is reported. Tier 1 and Tier 2
should end up looking like this.

---

## Tier 4 — unsourced, low stakes

| Parameter | Value | Where it bites |
|---|---:|---|
| `FILTER_TRANSMISSION` | 0.9 | −0.5 dB optical; a plausible range barely moves it |
| `CONCENTRATOR_REFRACTIVE_INDEX` | 1.5 | Gain goes as n²; 1.4–1.6 is ±1.2 dB |
| `DETECTOR_CAPACITANCE_PER_AREA_F_PER_M2` | 1.12e-6 | Only through the front-end bandwidth feasibility check |
| `DEFAULT_LOAD_RESISTANCE_OHM` | 250 | Thermal noise, which is not the limiting term |
| `DEFAULT_NOISE_TEMPERATURE_K` | 298 | Same |
| `DEFAULT_PREAMPLIFIER_NOISE_FACTOR` | 1.5 | Same. Lumped deliberately rather than adopting a six-constant FET model |
| `DEFAULT_NOISE_FIGURE_DB` | 9.0 | The radio has 34–56 dB of margin; this changes nothing that matters |
| `heading_noise_std_deg` | 2.0 | Observation realism, not physics |

---

## Not a problem, and worth saying so

**The finite-blocklength decoding model is optimistic by construction** — it
assumes a mathematically ideal code, so a real QPSK rate-1/3 transport block is
worse by an unmodelled implementation margin.

This does not threaten any result. The link carries **34–56 dB of margin** over
what decoding requires across the whole pair window, and RF failure is
collision-dominated by two to four orders of magnitude. An optimistic decoder
that is essentially never the binding constraint cannot bias a conclusion drawn
from the constraint that *is* binding. Stated here so the objection closes
without work.

**Exact constants**, listed for completeness and requiring nothing:
`SPEED_OF_LIGHT_MPS`, `THERMAL_NOISE_DENSITY_DBM_PER_HZ` (10·log₁₀(kT)+30 at
290 K), `COHERENCE_TIME_COEFFICIENT` (0.423, Clarke's 0.5-correlation point),
plus the guards `MIN_BLOCKLENGTH`, `MIN_VALID_DISTANCE_M`,
`MIN_VALID_PATH_LENGTH_M`, `PLANAR_VERTICAL_EMISSION_RAD`.

---

## Order of work

1. **Verify TR 37.885** — one document, 18 values, and it is the most
   reviewer-facing item in the model. Resolve the 541 m question while there.
2. **Cite and band `desired_time_headway_s`** — cheap to cite, and the
   sensitivity run answers whether the optical-improves-with-density result is
   robust.
3. **Source or synthesise the headlamp pattern** — blocks every optical number.
   Prefer a published measurement; a declared synthetic beam with a hot spot and
   a cutoff beats the Lambertian comparison, which W17 explicitly warns against
   relying on.
4. **Give the optical front end real part numbers** — responsivity and active
   area are the two that scale the result linearly.

Tier 4 can stay as it is, provided this table exists.
