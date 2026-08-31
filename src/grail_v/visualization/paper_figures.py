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





# --------------------------------------------------------------------------
# Figure: the ceiling the radio cannot buy its way past
# --------------------------------------------------------------------------

def pool_ceiling(out: Path, *, contenders: dict[int, float], attempts_needed:
                 dict[int, int], pool: int, max_attempts: int = 8) -> None:
    """What the population asks of the resource pool, against what it holds.

    The figure the feasibility claim rests on, and the one quantity no other
    plot in this paper shows. Reliability here is bought with retransmissions,
    retransmissions are drawn from a pool of ``pool`` resources per generation
    period, and every vehicle draws from the same one -- so ``n * N <= pool`` is
    a supply constraint, not a performance one. Above the line there is no
    assignment of contenders to resources that gives each what it asked for, and
    the collision model cannot see it: it prices where one selection lands, not
    whether every selection can be honoured.

    Each density's marker sits at the attempt count that density needs to reach
    the budget. A marker above the line is the whole result -- the radio needs
    more of the pool than exists, and no amount of margin elsewhere changes
    that, because the deadline buys time and this is not a shortage of time.
    """

    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(style.COLUMN_W, 2.5))
    counts = np.arange(1, max_attempts + 1)
    shades = {10: 0.42, 20: 0.68, 30: 1.0}

    for rho in sorted(contenders):
        demand = contenders[rho] * counts / pool
        ax.plot(counts, demand, color=RF, alpha=shades[rho], lw=1.3)
        # Labelled on the line rather than in a legend: three lines in a
        # single-column figure spend more on a legend box than the labels are
        # worth, and the box lands on the steepest line.
        edge = int(np.searchsorted(demand, 1.9))
        edge = max_attempts if edge == 0 else min(edge, max_attempts)
        ax.annotate(rf"$\rho{{=}}{rho}$", (edge, demand[edge - 1]),
                    textcoords="offset points", xytext=(4, 0), fontsize=6.5,
                    color=RF, alpha=shades[rho], va="center")
        need = attempts_needed[rho]
        at = contenders[rho] * need / pool
        ax.plot(need, at, marker="o" if at <= 1.0 else "X", ms=5.5,
                color=BOUND if at <= 1.0 else BUDGET, zorder=5,
                markeredgecolor="white", markeredgewidth=0.7)

    ax.axhline(1.0, color=BUDGET, lw=0.9, ls="--")
    ax.text(0.95, 1.04, "pool exhausted", color=BUDGET, fontsize=6.5,
            ha="left", va="bottom")
    ax.set_xlabel("RF attempts per packet")
    ax.set_ylabel("pool claim  $nN/M$")
    ax.set_xlim(0.9, max_attempts + 0.45)
    ax.set_ylim(0, 2.0)
    ax.set_xticks(counts)
    style.save(fig, out)


# --------------------------------------------------------------------------
# Figure: what each medium reaches once the pool is enforced
# --------------------------------------------------------------------------

def feasibility_boundary(out: Path, *, achieved: dict[int, dict[str, float]],
                         attempts: dict[int, int], budget: float) -> None:
    """The best each strategy reaches using every attempt the pool affords.

    The companion to :func:`pool_ceiling`, and the reason that figure matters.
    Reliability is bought with retransmissions until the pool runs out, so each
    density is evaluated at *its own* ceiling rather than at a common attempt
    count -- ``rho = 10`` gets eight attempts, ``rho = 30`` gets two, and that
    asymmetry is the finding rather than an inconsistency in the experiment.

    Read across the budget line: the radio alone clears it by five orders where
    the pool is empty enough, and nothing clears it at either denser condition.
    Duplication does not rescue them, because a duplicated packet still spends
    the radio resources that were the binding constraint, and the optical leg
    carries a static outage no transmit power reaches.
    """

    import matplotlib.pyplot as plt

    order = ["RF", "VLC", "hybrid"]
    colour = {"RF": RF, "VLC": VLC, "hybrid": DUP}
    label = {"RF": "radio alone", "VLC": "light alone", "hybrid": "both"}
    rhos = sorted(achieved)

    fig, ax = plt.subplots(figsize=(style.COLUMN_W, 2.5))
    width = 0.26
    for offset, key in zip((-width, 0.0, width), order):
        ax.bar([i + offset for i in range(len(rhos))],
               [achieved[r][key] for r in rhos], width,
               color=colour[key], label=label[key], zorder=3)

    ax.axhline(budget, color=BUDGET, lw=1.0, ls="--", zorder=4)
    exponent = int(round(math.log10(budget)))
    ax.text(-0.45, budget * 1.5, rf"budget $10^{{{exponent}}}$", color=BUDGET,
            fontsize=6.5, ha="left", va="bottom")
    ax.set_yscale("log")
    ax.set_xticks(range(len(rhos)))
    ax.set_xticklabels([rf"$\rho{{=}}{r}$" + "\n" + f"{attempts[r]} attempts" for r in rhos])
    ax.set_ylabel("miss rate")
    ax.set_ylim(1e-11, 5.0)
    ax.legend(loc="upper left", fontsize=6.0, ncol=3, columnspacing=0.8,
              handlelength=1.2)
    style.save(fig, out)


# --------------------------------------------------------------------------
# Figure: the coupling the whole contribution rests on
# --------------------------------------------------------------------------

def density_coupling(out: Path, *, distributions: Path) -> None:
    """The optical path shortens exactly as contention rises.

    Both quantities are measured over the same tagged-pair instants of the same
    traces, which is the point: their opposition is a property of one traffic
    state rather than of two independently parameterised models. It is the
    reason a hybrid is worth carrying at all, and no comparable study can plot
    it, because none drives both media from a single mobility trace.
    """

    import matplotlib.pyplot as plt

    data = json.load(open(distributions))["densities"]
    rho = sorted(int(k) for k in data)

    def band(field):
        med = [data[str(r)][field]["quantiles"]["50"] for r in rho]
        lo = [data[str(r)][field]["quantiles"]["25"] for r in rho]
        hi = [data[str(r)][field]["quantiles"]["75"] for r in rho]
        return np.array(med), np.array(lo), np.array(hi)

    optical, o_lo, o_hi = band("optical_path_m")
    contend, c_lo, c_hi = band("contenders")

    fig, ax = plt.subplots(figsize=(style.COLUMN_W, 2.4))
    # Interquartile bars rather than filled bands: with three conditions the
    # fills overlap into a wash, and the spread at the sparsest density is wide
    # enough to swallow the trend it is meant to qualify.
    optical_h = ax.errorbar(rho, optical, yerr=[optical - o_lo, o_hi - optical], color=VLC,
                marker="o", ms=3.6, capsize=2.5, lw=1.2, elinewidth=0.8,
                label="optical path")
    ax.set_xlabel(r"density $\rho$ [veh/lane/km]")
    ax.set_ylabel("headlamp-to-photodiode path [m]", color=VLC)
    ax.tick_params(axis="y", colors=VLC)
    ax.set_ylim(0, max(o_hi) * 1.12)
    ax.set_xticks(rho)

    bx = ax.twinx()
    contend_h = bx.errorbar(rho, contend, yerr=[contend - c_lo, c_hi - contend], color=RF,
                marker="s", ms=3.4, capsize=2.5, lw=1.2, ls="--", elinewidth=0.8,
                label="contenders")
    bx.set_ylabel("contenders within 200 m", color=RF)
    bx.tick_params(axis="y", colors=RF)
    bx.set_ylim(0, max(c_hi) * 1.12)
    bx.grid(False)

    ax.legend([optical_h, contend_h], ["optical path", "contenders"],
              loc="upper center", ncol=2, columnspacing=1.0)
    ax.set_ylim(0, max(o_hi) * 1.35)
    style.save(fig, out)


# --------------------------------------------------------------------------
# Figure: the optical cliff, with the traffic that has to cross it
# --------------------------------------------------------------------------

def optical_cliff(out: Path, *, distributions: Path) -> None:
    """Range decides the optical link, and density decides the range.

    The packet error curve is nearly binary: an inverse-square budget against a
    steep coded threshold puts the transition inside a few metres. Plotting it
    alone says little. Overlaid with the measured distribution of optical path
    at each density, it explains the whole optical column of the results -- why
    the light fails most packets at low density and most of it arrives at high.
    """

    import matplotlib.pyplot as plt

    from grail_v.channels.vlc.model import VLCChannelRequest, VLCPacketRandomness
    from grail_v.config import load_headline_config
    from grail_v.core.pair_geometry import pair_geometry
    from grail_v.env.assembly import build_vlc_channel

    config = load_headline_config(Path.cwd())
    channel = build_vlc_channel(config)
    car_length, north = 4.5, 0.5 * math.pi

    class _V:
        def __init__(self, vid, x, y):
            self.vehicle_id, self.x_m, self.y_m, self.heading_rad = vid, x, y, north
            self.length_m, self.width_m, self.height_m, self.speed_mps = \
                car_length, 1.8, 1.5, 10.0

    gaps = np.linspace(1.5, 60.0, 260)
    paths, per = [], []
    for gap in gaps:
        geometry = pair_geometry(_V("t", 0.0, 0.0), _V("r", 0.0, gap + car_length))
        result = channel.evaluate(VLCChannelRequest(
            geometry=geometry, occluded=False, randomness=VLCPacketRandomness(0.5)))
        paths.append(geometry.optical_path_length_m)
        per.append(max(result.decoding_failure_probability, 1e-16))

    data = json.load(open(distributions))["densities"]
    rho = sorted(int(k) for k in data)

    # Optical path for a tagged pair is its separation less one vehicle
    # length, so the 10-60 m eligibility window maps to roughly 5.5-55.5 m
    # behind a passenger car. Outside it no pair is ever evaluated.
    window = (10.0 - car_length, 60.0 - car_length)

    fig, ax = plt.subplots(figsize=(style.COLUMN_W, 2.5))
    ax.axvspan(0, window[0], color=GREY, alpha=0.13, lw=0)
    ax.annotate("below\npair window", xy=(window[0] - 0.4, 1e-7), fontsize=6,
                color=GREY, ha="right", va="center")
    ax.semilogy(paths, per, color=BOUND, lw=1.4)
    ax.annotate("packet error", xy=(31.5, 3e-9), fontsize=6.8, color=BOUND,
                ha="right", va="center")
    ax.set_xlabel("headlamp-to-photodiode path [m]")
    ax.set_ylabel("optical packet error")
    ax.set_xlim(0, 60)
    ax.set_ylim(1e-16, 3.0)
    ax.set_yticks([1e-15, 1e-10, 1e-5, 1e0])

    bx = ax.twinx()
    for shade, r in zip((0.40, 0.68, 1.0), rho, strict=True):
        d = data[str(r)]["optical_path_m"]
        bx.plot(d["cdf_x"], d["cdf_p"], color=VLC, alpha=shade, lw=1.0,
                label=rf"$\rho={r}$")
    bx.set_ylabel("fraction of pairs at or below", color=VLC)
    bx.tick_params(axis="y", colors=VLC)
    bx.set_ylim(0, 1.05)
    bx.grid(False)
    bx.legend(loc="center right", title="path CDF", title_fontsize=6.5)
    style.save(fig, out)


__all__ = [
    "density_coupling",
    "headlamp_pattern",
    "optical_cliff",
    "feasibility_boundary",
    "pool_ceiling",
    "reliability_cost_frontier",
    "rf_failure_decomposition",
]
