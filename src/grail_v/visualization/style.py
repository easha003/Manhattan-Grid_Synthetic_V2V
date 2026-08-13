"""Figure style for the paper.

Two-column IEEE conference format, so a single-column figure is
\\SI{3.5}{\\inch} wide and every point of type in it competes with 8 pt body
text. The settings below exist so that a figure dropped into the template is
legible at print size without rescaling -- rescaling is what produces the
mismatched font sizes that make a figure look pasted in.

Output is vector PDF. A rasterised plot in a paper is a decision to have the
reviewer squint.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

#: IEEE two-column geometry, inches.
COLUMN_W = 3.5
DOUBLE_W = 7.16

#: Semantic colours, used consistently across every figure: the radio is blue,
#: the light is amber, duplication violet, and the bound green. A reader who
#: learns the mapping on one figure keeps it on the next.
RF = "#1F5FA0"
VLC = "#C07A00"
DUP = "#5D45A0"
BOUND = "#1B6E46"
BUDGET = "#9E3D24"
GREY = "#5A6472"


def apply() -> None:
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "DejaVu Serif"],
        "mathtext.fontset": "dejavuserif",
        "font.size": 8,
        "axes.labelsize": 8,
        "axes.titlesize": 8,
        "legend.fontsize": 7,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "axes.linewidth": 0.6,
        "grid.linewidth": 0.4,
        "lines.linewidth": 1.1,
        "patch.linewidth": 0.6,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "xtick.direction": "in",
        "ytick.direction": "in",
        "xtick.top": True,
        "ytick.right": True,
        "legend.frameon": False,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.color": GREY,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.01,
        "pdf.fonttype": 42,
    })


def save(fig, path) -> None:
    fig.savefig(path, format="pdf")
    plt.close(fig)
