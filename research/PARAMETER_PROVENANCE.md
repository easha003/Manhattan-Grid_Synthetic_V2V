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

**Count as of this revision: 5 exact, 3 standard, 2 conservative, 18 VERIFIED,
8 unsourced, 4 guards.** The 18 were all TR 37.885 and have now been checked
against the ns-3 implementation of Table 6.2.1-1 plus an independent quotation.

**The check found two errors**, which is the argument for having done it. The
three NLOS coefficients were cyclically permuted, and the NLOSv blockage spread
was applied as one value where the document gives two. Details in the tier-2
section below.

---

## Tier 1 — changes a headline result

| Parameter | Value | Status | What it decides |
|---|---:|---|---|
| headlamp pattern artifact | **absent** | **still missing** | Every optical number. M4 cannot produce a result without it. |
| `RESPONSIVITY_A_PER_W` | 0.4 | **declared, datasheet-consistent** | Scales optical photocurrent linearly. |

Two entries left. Three were resolved and the story of each is worth keeping.

### Resolved — `desired_time_headway_s`, and it was not the leading term after all

**Cited.** Treiber, Hennecke and Helbing (2000) use 1.6 s for freeway traffic;
Treiber's own published defaults give **1.5 s** for cars, with the note that city
traffic should adapt the desired *speed* while the other parameters "essentially
can be left unchanged". Our 1.2 s is therefore **more aggressive than the
reference** — shorter gaps, higher capacity, and since the optical budget divides
by the bumper gap, a *better* V-VLC link than a Treiber-parameterised model would
give. That is now declared rather than silently favourable.

**And the sensitivity says the promotion was overstated.** Measured across the
band:

| T | mean gap, ρ=10 | mean gap, ρ=30 | ρ=10→30 optical change |
|---:|---:|---:|---:|
| 1.0 s | 31.93 m | 10.94 m | **+10.88 dB** |
| 1.2 s | 30.49 m | 10.92 m | **+9.97 dB** |
| 1.5 s | 31.07 m | 11.44 m | **+9.50 dB** |

The claim that V-VLC strengthens with density holds at every headway, with
**1.4 dB of spread against a 9.5 dB effect**. And the gaps barely move with *T*
at all — at ρ=20 they are 16.55, 18.06 and 16.98 m, non-monotonic and inside
1.5 m. **The bumper gap is set by density, not by the car-following model**,
because tagged pairs are already constrained to a 5–100 m window.

So the earlier framing — "an unsourced number moved from the edge of the model
to the middle of it" — was half right. It did move into the optical budget, and
it turned out not to matter there. Worth recording that the alarm was raised and
then measured away rather than quietly dropped.

### Resolved — the photodiode, and it cost 11 dB

**Sourced to a Vishay BPW34**, a commodity silicon PIN part with a published
datasheet (Vishay document 81521): radiant sensitive area **7.5 mm²**, junction
capacitance **70 pF at 1 MHz, zero bias**.

The assumed area was 1.0e-4 m² — a round 100 mm², **13× this part**, and
therefore **11.25 dB optimistic**, since received power scales linearly with
area. That is the single largest correction the sourcing exercise has produced.

It also cuts the other way, which is the trade the receiver module exists to
make explicit: the smaller part *raises* the RC ceiling from 284 Ω to 455 Ω, so
the front end became easier to build at the same moment the optical budget
became harder. Area is not free.

Zero-bias capacitance is the pessimistic end — a real receiver reverse-biases
the diode and gets substantially less — so the bandwidth feasibility check is
conservative.

### Resolved — `NLOSV_BLOCKAGE_MEAN_TALL_DB`

Verified against Table 6.2.1-1. See tier 2.

---

## Tier 2 — TR 37.885, verified, and it found two errors

Checked against the ns-3 implementation of Table 6.2.1-1 (`ThreeGppV2vUrban\
PropagationLossModel`) and an independent quotation of the same expressions.

### What was wrong

**The three NLOS coefficients were cyclically permuted.**

| | intercept | log₁₀(d) | log₁₀(f_c) |
|---|---:|---:|---:|
| was | 18.9 | 36.85 | 30.0 |
| **is** | **36.85** | **30.0** | **18.9** |

The error was distance-dependent and changed sign inside the window —
understating NLOS loss by **4.6 dB at 5 m** and overstating it by **4.3 dB at
100 m**. Downstream, NLOS deep-fade outage at 100 m falls from 28% to **11.7%**,
and at 50 m from 2.6% to **1.5%**.

**The tell was physical, not numerical.** An NLOS intercept of 18.9 dB against a
LOS intercept of 38.77 dB is a 20 dB gap between two quantities that are both
"loss at one metre"; and a distance exponent of 3.685 paired with that intercept
is not a shape any measurement campaign produces. A cheap invariant now asserts
the two intercepts sit within 10 dB of each other, which fails for *any*
permutation of the three.

**The unit test did not catch it, because it restated the implementation.** It
asserted `18.9 + 36.85·log₁₀(d) + 30·log₁₀(f_c)` and passed — it had locked the
error in rather than testing against the document. A test that only echoes the
code is worth very little, and this is the concrete cost of one.

**The NLOSv blockage spread has two values, not one.** σ = 4.5 dB when both
antennas sit below the blocker, 4.0 dB when the blocker falls between them. A
single 4.5 was used for both, widening the mixed case by half a decibel. Minor,
and unreachable in this profile anyway since equal antenna heights make the
mixed branch dead.

### What was right

Everything else. LOS intercept, both slopes, all three shadowing spreads, both
blockage means, both blockage distance coefficients, all three decorrelation
distances, the Rician K-factor and the delay spread.

**The 541 m question is resolved: the term is correct as written.** The
coefficients 15 and 41 are confirmed, so `max(0, 15·log₁₀(d) − 41)` genuinely
targets ranges this study never reaches, and vehicle blockage really is a flat
offset across the whole pair window. NLOSv severity is not inferable from
separation — that is the model, not a transcription slip.

One new fact worth recording: **TR 37.885 uses blocker heights of 1.6 m and
3.0 m**, chosen probabilistically, rather than the simulated vehicle's own
height. This project passes the actual fleet height instead. That is a defensible
divergence — we have real bodies and can use them — but it interacts with the
"a passenger car costs the radio nothing" finding, since the document's own car
height and its car antenna height are also close together. Worth a sentence in
the paper rather than silence.

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

1. ~~**Verify TR 37.885**~~ — **done.** Found the NLOS coefficients permuted and
   the blockage spread collapsed to one value; both fixed. The 541 m term is
   confirmed correct.
2. ~~**Cite and band `desired_time_headway_s`**~~ — **done.** Cited to Treiber;
   the sensitivity says the optical result is robust across the band and that
   the gap is set by density rather than by the headway.
3. **Source or synthesise the headlamp pattern** — blocks every optical number.
   Prefer a published measurement; a declared synthetic beam with a hot spot and
   a cutoff beats the Lambertian comparison, which W17 explicitly warns against
   relying on.
4. ~~**Give the optical front end real part numbers**~~ — **mostly done.** Area
   and capacitance sourced to the BPW34 datasheet, costing 11.25 dB. Only
   responsivity remains declared, and it is datasheet-consistent for a silicon
   detector at white-LED wavelengths.

Tier 4 can stay as it is, provided this table exists.

---

## What the verification taught, beyond the two fixes

The unit test for the NLOS formula **restated the implementation** and therefore
passed against a permuted formula. It could not have failed. Every value in this
table that is checked only by a test asserting the same arithmetic the code
performs is in that position, and the fix is not more tests but *different* ones:
invariants about what kind of quantity a value is. Two intercepts that both mean
"loss at one metre" cannot differ by 20 dB, whatever the coefficients are — that
assertion catches any permutation and it does not need to know the right answer.

That is now the standard the remaining tiers should be held to.
