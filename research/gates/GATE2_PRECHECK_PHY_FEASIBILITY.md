# Gate-2 pre-check — PHY feasibility of the headline profile

> **Historical for §1–§6; current result in §7.** This document first evaluated
> the former 300 B / **1 ms** / 10⁻⁴ profile. The headline is now
> 300 B / **3 ms** / 10⁻⁴ (`configs/service/ev2x_300B_3ms_1e-4.yaml`).
>
> The 1-ms profiles have since been deleted, so §1–§6 no longer describe any
> loadable configuration. They are retained as **the recorded justification for
> choosing 3 ms**: they are where the RF leg's forced 16QAM and the ~1 Mbit/s
> VLC window were found. That reasoning belongs in the paper's profile
> rationale and should not be re-derived.
>
> Both configuration corrections identified in §5 have been applied, and both
> checks are now enforced by the configuration loader.

**Status:** unconditional pass on both legs at the 3-ms headline (§7).
Conditional pass only, at 1 ms (§2–§3) — which is why the headline moved.

**Scope:** `CODE_IMPLEMENTATION_SPEC.md` §13.6.1 and
`GRAIL_V_WORK_PLAN_V2.md` §8.2 require that every selected PHY be shown to
carry the complete coded information block within its allocated airtime before
any learned result is produced. This document runs that check against the
frozen headline profile and the currently declared channel configurations.

**Inputs:**

- `configs/service/headline_300B_1ms_1e-4.yaml` *(deleted; §1–§6 evaluated it
  as it stood at the time)*
- [`configs/service/ev2x_300B_3ms_1e-4.yaml`](../../configs/service/ev2x_300B_3ms_1e-4.yaml)
  *(current headline, §7)*
- [`configs/channel/vlc_vehicle.yaml`](../../configs/channel/vlc_vehicle.yaml)
- [`configs/channel/rf_nr_v2x.yaml`](../../configs/channel/rf_nr_v2x.yaml)
- W17 (Memedi & Dressler, *IEEE COMST* 2021), local full text
- W1 dossier, Veins-VLC reference configuration

---

## 1. Method

For each leg, with information payload \(B\) bytes, framing overhead \(F\)
bytes, code rate \(r\), and airtime budget \(T_\mathrm{air}\):

\[
N_\mathrm{coded}=\frac{8(B+F)}{r},
\qquad
R_\mathrm{min}=\frac{N_\mathrm{coded}}{T_\mathrm{air}}.
\]

The leg passes only if the declared gross rate is at least \(R_\mathrm{min}\)
**and** that rate is physically supportable by the declared front end. The
second condition is the one v1 of the work plan omitted entirely.

---

## 2. V-VLC leg

### 2.1 Timing

| Quantity | Value |
|---|---:|
| Information payload | 300 B |
| Framing overhead | 32 B |
| Information + framing | 332 B = 2,656 bits |
| Code rate | 1/2 |
| Coded block | **5,312 bits** |
| Airtime budget | 800 µs |
| **Minimum gross rate** | **6.64 Mbit/s** |
| Configured gross rate | 10 Mbit/s |
| Resulting airtime | 531 µs (269 µs slack) |

Timing alone passes.

### 2.2 Bandwidth — where it fails

The configuration declares OOK at an electrical bandwidth of 5 MHz. OOK carries
one bit per symbol, so the symbol rate equals the bit rate, and the occupied
baseband bandwidth under raised-cosine shaping with roll-off \(\beta\) is
\(B=(1+\beta)R_s/2\).

| Gross rate | β = 0.2 | β = 0.3 | β = 0.5 |
|---:|---:|---:|---:|
| 6.64 Mbit/s (minimum) | 3.98 MHz | 4.32 MHz | 4.98 MHz |
| 10 Mbit/s (configured) | 6.00 MHz | **6.50 MHz** | 7.50 MHz |

**The configured 10 Mbit/s does not fit the configured 5 MHz front end.** It
requires zero excess bandwidth (β = 0, ideal sinc pulses), which is not a
physically realizable pulse shape. The two numbers in
`vlc_vehicle.yaml` are mutually inconsistent.

### 2.3 The feasible window

Inverting the constraint — the maximum OOK rate that fits 5 MHz — gives a
narrow but nonempty window:

| Roll-off β | Feasible gross-rate window | Width |
|---:|---|---:|
| 0.2 | 6.64 – 8.33 Mbit/s | 1.69 Mbit/s |
| 0.3 | 6.64 – 7.69 Mbit/s | 1.05 Mbit/s |
| 0.5 | 6.64 – 6.67 Mbit/s | **closed** |

The headline profile is feasible, but only inside this window. Two parameters
close it:

- **roll-off ≥ 0.5** — window collapses;
- **code rate < 1/2** — at rate 1/3 the coded block is 7,968 bits, requiring
  9.96 Mbit/s and 6.47 MHz. Fails outright.

Both are ordinary outcomes of channel calibration. The margin is real but thin,
and it must be declared rather than discovered at week 9.

### 2.4 Evidence check against W17

W17 §III-B, on automotive front ends, is direct:

> "These are high power LEDs with high capacitance (therefore slow raise time),
> which limits the modulation bandwidth (and therefore the effective
> communication time) only to a few MHz."

The declared 5 MHz sits at the optimistic edge of "a few MHz" and is
defensible. The required ~4.3–4.6 MHz occupied bandwidth fits inside it.
W17 also records the escape route if more is needed:

> "This approach [blue optical filtering] can increase the modulation bandwidth
> to tens of MHz and to support higher data rates … However, it does so at the
> expense of decreased SNR."

That is available, but it is a declared receiver-design assumption with an SNR
cost that must then be carried in the link budget — not a free parameter.

### 2.5 Reference-point sanity check

W1's Veins-VLC configuration — the closest reproducible V-VLC simulator, per
W17 §IX — uses a nominal **1 Mbit/s** VLC rate. At that rate the 5,312-bit
coded block takes **5.31 ms**, which misses a 1 ms deadline by 5× and a 3 ms
deadline by 1.8×.

The project's own W1 dossier already flagged this
(`research/literature/W1_W8.md`, coding implication 4). This is worth stating
plainly in the paper: **our VLC configuration is roughly 7× the rate of the
standard reference simulator's**, and that gap is the single strongest
assumption in the headline profile. It should appear in Table I with its
justification, not be left for a reviewer to compute.

### 2.6 Verdict

**Conditional pass.** Correct the configuration to a rate inside the feasible
window and declare the roll-off explicitly.

---

## 3. NR sidelink leg

### 3.1 Timing

| Quantity | Value |
|---|---:|
| Information payload | 300 B |
| Framing overhead | 48 B |
| Information + framing | 348 B = 2,784 bits |
| Code rate | 1/2 |
| Coded block | **5,568 bits** |
| Airtime budget | 500 µs (one slot) |
| **Minimum gross rate** | **11.14 Mbit/s** |
| Configured gross rate | 12 Mbit/s |
| Resulting airtime | 464 µs (36 µs slack, 7.2%) |

Timing passes, but with only 7% margin.

### 3.2 Resource-element budget — where it fails

The configuration was never checked against the actual slot capacity. At
10 MHz with 30 kHz subcarrier spacing:

| Quantity | Value |
|---|---:|
| Resource blocks | 24 |
| Subcarriers | 288 |
| Symbols per slot | 14 |
| Gross REs per slot | 4,032 |

NR sidelink overhead removes a large fraction of these:

| Overhead | Symbols | REs |
|---|---:|---:|
| AGC symbol (symbol 0, repeated) | 1 | 288 |
| Guard symbol (final) | 1 | 288 |
| PSSCH DMRS (2-symbol pattern) | 2 | 576 |
| PSCCH (3 symbols × ~12 PRB) | — | ~432 |
| **Remaining for PSSCH data** | | **≈ 2,448** |

Now compare against the coded block:

| Modulation | Coded bits available | Required | Fits? |
|---|---:|---:|:--:|
| QPSK (2 bits/RE) | 4,896 | 5,568 | **No — short by 12%** |
| 16QAM (4 bits/RE) | 9,792 | 5,568 | Yes |

**The headline block does not fit one slot at QPSK ½.** The declared
12 Mbit/s implies about 6,000 coded bits per 500 µs, but QPSK ½ over this slot
delivers at most ~4,896 — an effective ceiling near **9.8 Mbit/s**.

### 3.3 Consequence

The RF leg requires **16QAM or higher**, which costs roughly 6 dB of SNR
relative to QPSK. That is not fatal — 23 dBm at short pair separations has the
budget — but it directly changes:

- which TR 37.885 propagation classes can close the link at all;
- the BLER curves in spec §10.6;
- the NLOSv margin, and therefore how often RF alone is viable;
- **the paper's central premise**, because a higher-order MCS makes RF fail
  earlier under blockage, which is the mechanism the hybrid argument rests on.

This must be settled before `channels/rf/bler.py` is written.

### 3.4 Verdict

**Conditional pass**, contingent on declaring 16QAM (or a two-slot allocation,
which the 1 ms deadline does allow: 2 × 500 µs = 1 ms leaves no decoding time
and is therefore rejected).

---

## 4. Overall verdict

| Leg | Timing | Front end | Verdict |
|---|:--:|:--:|---|
| V-VLC | Pass | **Fail as configured** | Conditional — narrow rate window |
| NR sidelink | Pass (7% margin) | **Fail at QPSK ½** | Conditional — needs 16QAM |

**The 1 ms headline profile survives.** No move to 3 ms is required. Work-plan
Risk 1 does not fire.

Both failures are configuration errors, not physical impossibilities — which
is precisely what this gate exists to catch, and precisely what would have been
found at week 9 instead of week 1 under the v1 plan.

---

## 5. Required actions

1. **`vlc_vehicle.yaml`** — set `gross_bit_rate_bps` inside the feasible
   window and add an explicit `pulse_roll_off` field. Recommended: 7.0 Mbit/s
   at β = 0.3 → 4.55 MHz occupied, inside the 5 MHz front end, 759 µs airtime
   inside the 800 µs budget. Margins: 5% time, 9% bandwidth.
2. **`rf_nr_v2x.yaml`** — add an explicit `modulation` field set to `16qam`,
   and reduce `gross_bit_rate_bps` to the value implied by the RE budget.
3. **Both** — add the RE/bandwidth derivations above as a unit test so the gate
   cannot silently regress when calibration changes a parameter
   (spec §25.1 already requires packet-timing tests; extend them to capacity).
4. **Table I** — record the 7× gap to the Veins-VLC reference rate with its
   justification.
5. **Re-run this gate** whenever code rate, framing overhead, roll-off, or
   modulation changes. Any of them can close the VLC window.

---

## 6. Provenance

| Item | Source | Type |
|---|---|---|
| "only a few MHz" LED bandwidth limit | W17 §III-B, local full text | Direct |
| Blue-filter mitigation to "tens of MHz" | W17 §III-B, local full text | Direct |
| Veins-VLC 1 Mbit/s nominal rate | W1 dossier, `W1_W8.md` | Direct |
| 24 RB at 10 MHz / 30 kHz SCS | 3GPP TS 38.101-1 numerology | Reference |
| Sidelink AGC/guard/DMRS/PSCCH overhead | NR sidelink slot structure | Reference |
| Raised-cosine occupied bandwidth | Standard result | Calculated |
| All rate and RE arithmetic | This document §2–3 | Calculated |

The two "Reference" rows should be pinned to exact 3GPP clause numbers before
Table I is finalized.

---

## 7. Re-run at the 3-ms headline

The headline moved to 300 B / 3 ms / 10⁻⁴. The gate was re-run against the new
profile; both legs now pass **unconditionally**, and the surplus is spent on
coding gain rather than throughput.

### 7.1 V-VLC — rate 1/4, OOK, 2.4 ms airtime

| Quantity | 1 ms (former) | 3 ms (headline) |
|---|---:|---:|
| Code rate | 1/2 | **1/4** |
| Coded block | 5,312 bits | 10,624 bits |
| Airtime budget | 800 µs | 2,400 µs |
| Minimum gross rate | 6.64 Mbit/s | 4.43 Mbit/s |
| Configured gross rate | 7.0 Mbit/s | **4.5 Mbit/s** |
| Occupied bandwidth (β = 0.3) | 4.55 MHz | **2.93 MHz** |
| Share of the 5 MHz front end | 91% | **59%** |

The 1-ms feasible window was 6.64–7.69 Mbit/s — about 1 Mbit/s wide, and
closed entirely at roll-off 0.5 or code rate below 1/2. At 3 ms the symbol
rate sits at 59% of the declared front end, comfortably inside the LED's flat
region, while the code strengthens from rate 1/2 to rate 1/4.

### 7.2 NR sidelink — QPSK, rate 1/3, two-slot allocation

| Quantity | 1 ms (former) | 3 ms (headline) |
|---|---:|---:|
| Modulation | **16QAM (mandatory)** | **QPSK** |
| Code rate | 1/2 | **1/3** |
| Coded block | 5,568 bits | 8,352 bits |
| Airtime | 500 µs (1 slot) | 1,000 µs (2 slots) |
| Grid capacity (24 RB, 40% overhead) | 9,677 bits at 16QAM | 9,677 bits at QPSK |
| Margin | — | **14%** |

At 1 ms the block did not fit one slot at QPSK (4,896 available against 5,568
required), forcing 16QAM and roughly 6 dB of SNR. **The 3-ms deadline permits a
two-slot allocation, which removes the 16QAM requirement entirely** and buys a
rate-1/3 code on top. This is a multi-slot PSSCH allocation, not a
retransmission: `service.rf_attempts_per_packet` remains 1.

### 7.3 Verdict

| Leg | Timing | Front end | Verdict |
|---|:--:|:--:|---|
| V-VLC | Pass | Pass, 41% bandwidth margin | **Unconditional pass** |
| NR sidelink | Pass | Pass at QPSK, 14% grid margin | **Unconditional pass** |

Neither leg is operating against a ceiling, and the reliability margin needed
for the 10⁻⁵ frontier now comes from coding gain rather than from pushing the
hardware.

### 7.4 The gate is now enforced in code

Both corrections identified in §5 have been applied, and — more importantly —
both checks are now invariants the configuration loader enforces at load time:

- `RFConfig.available_coded_bits()` computes the resource-element ceiling from
  bandwidth, numerology, modulation, and overhead;
  `_validate_rf_resource_grid` rejects any declared rate above it.
- `VLCConfig.occupied_bandwidth_hz()` computes occupied baseband bandwidth
  from the gross rate, modulation order, and roll-off;
  `_validate_vlc_bandwidth` rejects any rate exceeding the optical front end.

The 10 Mbit/s-in-5 MHz contradiction that this document originally found by
hand now fails in milliseconds with an explicit error. Gate 2 can no longer
silently regress when calibration changes a parameter.
