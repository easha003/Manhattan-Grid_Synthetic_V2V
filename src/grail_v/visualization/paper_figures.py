"""The paper's figures, generated from artifacts rather than from notebooks.

Each function reads either a published evaluation artifact or the models
themselves, so a re-run refreshes the paper instead of silently leaving it
stale. Nothing here recomputes physics: where a number could be measured it is
read from ``artifacts/evaluations/*.json``, and where it is a property of a
model it is asked of the model.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from grail_v.visualization import style
from grail_v.visualization.style import BOUND, BUDGET, DUP, GREY, RF, VLC


# --------------------------------------------------------------------------
# Figure: what actually breaks the radio
# --------------------------------------------------------------------------

def rf_failure_decomposition(out: Path, *, measured: dict[int, int]) -> None:
    """Why the radio's design lever is not its link budget.

    Left: the access-layer mechanisms against contention. Collision rises with
    the number of contenders and half duplex is a flat duty cycle; neither
    responds to transmit power.

    Right: the finite-blocklength decoding curve, with the operating envelope
    drawn on it. At n = 2419 channel uses the curve is a cliff -- about a
    decibel separates a block that essentially always decodes from one that
    fails at the budget -- and the link sits far above it in every condition
    except deep NLOS shadowing at the far end of the pair window. That is the
    whole argument: decoding is negligible not because the margin is uniformly
    large but because the threshold is sharp and rarely approached.
    """

    import matplotlib.pyplot as plt

    from grail_v.channels.rf.bler import (
        LinkBudget,
        block_error_probability,
        required_snr_db,
        thermal_noise_dbm,
    )
    from grail_v.channels.rf.collision import (
        collision_probability,
        half_duplex_probability,
    )
    from grail_v.channels.rf.pathloss_37885 import median_path_loss_db
    from grail_v.config import load_headline_config
    from grail_v.core.enums import RFPropagationState
    from grail_v.env.assembly import build_rf_channel

    config = load_headline_config(Path.cwd())
    channel = build_rf_channel(config)
    parameters = channel.collision
    noise = thermal_noise_dbm(channel.bandwidth_hz)

    fig, (ax, bx) = plt.subplots(1, 2, figsize=(style.DOUBLE_W, 2.4))

    contenders = np.arange(1, 401)
    collision = np.array([collision_probability(int(n), parameters) for n in contenders])
    ax.semilogy(contenders, collision, color=RF, label="collision")
    ax.axhline(half_duplex_probability(parameters), color=DUP, ls="--",
               label="half duplex")
    for density, count in sorted(measured.items()):
        ax.axvline(count, color=GREY, lw=0.5, alpha=0.6)
        ax.annotate(rf"$\rho={density}$", xy=(count, 1.4e-3), fontsize=6.5,
                    rotation=90, ha="right", va="bottom", color=GREY)
    ax.set_xlabel("contenders within 200 m")
    ax.set_ylabel("per-attempt failure probability")
    ax.set_xlim(0, 400)
    ax.set_ylim(1e-3, 1.0)
    ax.legend(loc="lower right")

    snr_db = np.linspace(-2.0, 12.0, 400)
    bler = np.array([
        block_error_probability(10 ** (s / 10.0), blocklength=channel.blocklength,
                                information_bits=channel.information_bits)
        for s in snr_db
    ])
    bx.semilogy(snr_db, bler, color=BOUND)
    bx.axhline(1e-4, color=BUDGET, lw=0.8, ls="--")
    bx.annotate(r"$10^{-4}$", xy=(-1.7, 1.6e-4), fontsize=6.5, color=BUDGET, ha="left")

    # Where the link actually sits. Only the worst case is on this scale; the
    # benign ones are tens of decibels to the right, which is the point.
    cases = [
        ("LOS, 10 m", 10.0, RFPropagationState.LOS, 0.0, 0.0),
        ("NLOSv, 30 m", 30.0, RFPropagationState.NLOSV, 8.0, 9.0),
        ("NLOS, 60 m", 60.0, RFPropagationState.NLOS, 10.5, 0.0),
    ]
    need = required_snr_db(1e-4, blocklength=channel.blocklength,
                           information_bits=channel.information_bits)
    margins = {}
    for label, distance, state, shadow, blockage in cases:
        loss = median_path_loss_db(distance, channel.carrier_hz, state)
        budget = LinkBudget(
            tx_power_dbm=channel.tx_power_dbm, path_loss_db=loss + blockage,
            shadowing_db=shadow, fading_power_gain=1.0, noise_dbm=noise,
        )
        margins[label] = budget.snr_db - need
    worst = min(margins, key=margins.get)

    bx.axvline(need + margins[worst], color=GREY, lw=0.6)
    bx.annotate(f"{worst}\n{margins[worst]:+.1f} dB", xy=(need + margins[worst] + 0.3, 2e-9),
                fontsize=6.2, color=GREY, ha="left", va="center")
    benign = sorted(v for k, v in margins.items() if k != worst)
    bx.annotate(
        f"LOS and NLOSv cases\nlie at {benign[0]:+.0f} to {benign[-1]:+.0f} dB",
        xy=(11.7, 3e-4), fontsize=6.2, color=GREY, ha="right", va="bottom")
    bx.annotate("", xy=(11.9, 1.2e-4), xytext=(9.6, 1.2e-4),
                arrowprops=dict(arrowstyle="->", lw=0.6, color=GREY))
    bx.set_xlabel("post-detection SNR [dB]")
    bx.set_ylabel("block error probability")
    bx.set_xlim(-2, 12)
    bx.set_ylim(1e-15, 1.0)

    style.save(fig, out)


# --------------------------------------------------------------------------
# Figure: the beam, and that it is compliant by construction
# --------------------------------------------------------------------------

#: Label placement for the test-point overlay. Several points share a
#: coordinate to within a few tenths of a degree, so they are staggered by
#: hand rather than allowed to stack.
_LABEL_OFFSET = {
    "75L": (0.26, "center"), "50L": (-0.26, "center"),
    "75R": (0.26, "center"), "50R": (0.0, "left"), "50V": (-0.26, "center"),
    "25L": (0.26, "center"), "25R": (0.26, "center"),
    "B50L": (0.26, "center"), "BR": (0.26, "center"),
}

_R112_POINTS = [
    ("B50L", +0.57, -3.43, None, 350), ("BR", +1.00, +2.50, None, 1750),
    ("75R", -0.57, +1.15, 10100, None), ("75L", -0.57, -3.43, None, 10600),
    ("50L", -0.86, -3.43, None, 13200), ("50R", -0.86, +1.72, 10100, None),
    ("50V", -0.86, 0.00, 5100, None), ("25L", -1.72, -9.00, 1700, None),
    ("25R", -1.72, +9.00, 1700, None),
]


def headlamp_pattern(out: Path, *, artifacts: Path) -> None:
    """The modelled beam against the regulation that constrains it.

    The beam is the first thing a reviewer will interrogate, because measured
    radiation patterns are known to dominate V-VLC performance. This figure
    exists to answer that before it is asked: the left panel shows the pattern
    with every ECE R112 Class B test point and zone drawn on it, and the right
    panel shows what happens past the last regulated angle, where the
    regulation requires nothing and the two shipped variants disagree on
    purpose.
    """

    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    from grail_v.channels.vlc.headlamp_pattern import load_pattern

    wide = load_pattern(artifacts / "headlamp-r112-compliant-wide-v2")
    narrow = load_pattern(artifacts / "headlamp-r112-compliant-narrow-v2")
    efficacy = 300.0

    h = np.degrees(np.asarray(wide.horizontal_angles_rad))
    v = np.degrees(np.asarray(wide.vertical_angles_rad))
    grid = np.asarray(wide.intensity_w_per_sr) * efficacy

    fig, (ax, bx) = plt.subplots(
        1, 2, figsize=(style.DOUBLE_W, 2.5), gridspec_kw={"width_ratios": [1.35, 1.0]}
    )

    keep = (h >= -12) & (h <= 12)
    mesh = ax.pcolormesh(
        h[keep], v, np.maximum(grid[:, keep], 1.0),
        norm=__import__("matplotlib.colors", fromlist=["LogNorm"]).LogNorm(vmin=10, vmax=3e4),
        cmap="inferno", shading="auto", rasterized=True,
    )
    cb = fig.colorbar(mesh, ax=ax, pad=0.02)
    cb.set_label("luminous intensity [cd]", fontsize=7)
    cb.ax.tick_params(labelsize=6.5)

    ax.add_patch(Rectangle((-5.15, -1.72), 10.30, 0.86, fill=False,
                           ec="white", lw=0.8, ls="--"))
    ax.text(0, -1.95, "zone IV  $\\geq$2500\\,cd", color="white", fontsize=6,
            ha="center", va="top")
    for name, vv, hh, lo, hi in _R112_POINTS:
        if not (-12 <= hh <= 12):
            continue
        ax.plot(hh, vv, marker="o" if lo else "s", ms=2.6,
                mfc="white" if lo else "none", mec="white", mew=0.7)
        dy, ha = _LABEL_OFFSET.get(name, (0.22, "center"))
        ax.text(hh + (0.35 if ha == "left" else -0.35 if ha == "right" else 0.0),
                vv + dy, name, color="white", fontsize=5.6, ha=ha, va="center")
    ax.axvline(-9, color="white", lw=0.6, alpha=0.7)
    ax.axvline(+9, color="white", lw=0.6, alpha=0.7)
    ax.set_xlabel("horizontal angle [deg]")
    ax.set_ylabel("vertical angle [deg]")
    ax.set_ylim(-6, 2)
    ax.set_xlim(-12, 12)
    ax.grid(False)

    row = float(np.argmin(np.abs(v + 0.86)))
    cut_w = np.asarray(wide.intensity_w_per_sr)[int(row)] * efficacy
    cut_n = np.asarray(narrow.intensity_w_per_sr)[int(row)] * efficacy
    bx.semilogy(h, np.maximum(cut_w, 1e-1), color=VLC, label="wide")
    bx.semilogy(h, np.maximum(cut_n, 1e-1), color=RF, ls="--", label="narrow")
    bx.axvspan(-9, 9, color=GREY, alpha=0.12, lw=0)
    bx.text(0, 1.4e5, "specified by R112", ha="center", va="top",
            fontsize=6.5, color=GREY)
    for name, vv, hh, lo, hi in _R112_POINTS:
        if abs(vv + 0.86) < 1e-6 and lo:
            bx.plot(hh, lo, marker="_", ms=7, color="black", mew=1.1)
    bx.set_xlabel("horizontal angle at 0.86D [deg]")
    bx.set_ylabel("luminous intensity [cd]")
    bx.set_xlim(-25, 25)
    bx.set_ylim(1e-1, 2.2e5)
    bx.legend(loc="lower center", ncol=2)
    style.save(fig, out)


# --------------------------------------------------------------------------
# Figure: the reliability-cost frontier
# --------------------------------------------------------------------------

def reliability_cost_frontier(out: Path, *, wide: Path, narrow: Path, budget: float) -> None:
    """Where every strategy sits in the feasible region.

    This is the figure that turns "our method beats the baselines" into a
    statement about what is achievable at all. The frontier is the cheapest
    mean activation cost attaining each miss rate, given perfect knowledge of
    per-packet risk but no knowledge of outcomes; the band between the two
    headlamp variants is the part of the answer the regulation does not fix.
    """

    import matplotlib.pyplot as plt

    def load(path):
        d = json.load(open(path))
        return {int(g["density_veh_per_lane_km"]): g for g in d["densities"]}

    W, N = load(wide), load(narrow)
    densities = sorted(W)
    shades = {10: 0.42, 20: 0.68, 30: 1.0}

    fig, ax = plt.subplots(figsize=(style.COLUMN_W, 2.6))
    for rho in densities:
        alpha = shades[rho]
        fw = [(f["mean_cost"], f["achieved"]) for f in W[rho]["targeting"]["frontier"]]
        fn = [(f["mean_cost"], f["achieved"]) for f in N[rho]["targeting"]["frontier"]]
        cw, aw = zip(*sorted(fw))
        cn, an = zip(*sorted(fn))
        ax.fill_betweenx(aw, cw, cn, color=BOUND, alpha=0.10 * alpha + 0.05, lw=0)
        ax.plot(cw, aw, color=BOUND, alpha=alpha, label=rf"frontier, $\rho{{=}}{rho}$")

        rf_pt = W[rho]["policies"]["RF"]["expected_miss_rate"]
        dup_pt = W[rho]["policies"]["DUP"]["expected_miss_rate"]
        ax.plot(1.0, rf_pt, marker="o", ms=3.4, color=RF, alpha=alpha, ls="none")
        ax.plot(2.0, dup_pt, marker="s", ms=3.4, color=DUP, alpha=alpha, ls="none")

    ax.axhline(budget, color=BUDGET, lw=0.9, ls="--")
    ax.text(1.02, budget * 1.18, r"budget $10^{-4}$", color=BUDGET, fontsize=6.5, va="bottom")

    ax.plot([], [], marker="o", ms=3.4, color=RF, ls="none", label="RF only")
    ax.plot([], [], marker="s", ms=3.4, color=DUP, ls="none", label="duplicate all")
    ax.set_xlabel("mean activation cost")
    ax.set_ylabel("expected miss rate")
    ax.set_yscale("log")
    ax.set_xlim(0.95, 2.08)
    ax.set_ylim(1e-5, 1e-3)
    ax.legend(loc="upper right", ncol=1)
    style.save(fig, out)


__all__ = ["headlamp_pattern", "reliability_cost_frontier", "rf_failure_decomposition"]
