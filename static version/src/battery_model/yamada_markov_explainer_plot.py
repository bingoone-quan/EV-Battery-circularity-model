"""Create a one-page explainer figure for the Yamada Markov-chain principle."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


OUTPUT_NAME = "yamada_markov_explainer_onepage.png"


def _add_box(ax, xy, width, height, text, fc, ec="#2f2f2f", fontsize=13, weight="bold"):
    x, y = xy
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.02,rounding_size=0.03",
        facecolor=fc,
        edgecolor=ec,
        linewidth=1.5,
    )
    ax.add_patch(patch)
    ax.text(
        x + width / 2,
        y + height / 2,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        fontweight=weight,
        color="#1f1f1f",
    )


def _add_arrow(ax, start, end, text="", color="#4b5563", rad=0.0, text_offset=(0.0, 0.0), lw=1.8):
    arrow = FancyArrowPatch(
        start,
        end,
        arrowstyle="->",
        mutation_scale=15,
        linewidth=lw,
        color=color,
        connectionstyle=f"arc3,rad={rad}",
    )
    ax.add_patch(arrow)
    if text:
        mx = (start[0] + end[0]) / 2 + text_offset[0]
        my = (start[1] + end[1]) / 2 + text_offset[1]
        ax.text(mx, my, text, fontsize=11, color=color, ha="center", va="center")


def create_figure():
    fig = plt.figure(figsize=(14, 9), facecolor="#faf8f2")
    gs = fig.add_gridspec(2, 2, height_ratios=[1.2, 1.0], hspace=0.18, wspace=0.12)

    ax_top = fig.add_subplot(gs[0, :], facecolor="white")
    ax_left = fig.add_subplot(gs[1, 0], facecolor="white")
    ax_right = fig.add_subplot(gs[1, 1], facecolor="white")

    for ax in (ax_top, ax_left, ax_right):
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_alpha(0.15)

    ax_top.set_xlim(0, 1)
    ax_top.set_ylim(0, 1)

    _add_box(ax_top, (0.05, 0.62), 0.14, 0.16, "State 1\nProduction", "#dbeafe")
    _add_box(ax_top, (0.25, 0.62), 0.14, 0.16, "State 2\nEV Use", "#dcfce7")
    _add_box(ax_top, (0.45, 0.62), 0.14, 0.16, "State 3\nEOL Sorting", "#fef3c7")
    _add_box(ax_top, (0.65, 0.62), 0.14, 0.16, "State 4\nCascade Use", "#fde68a")
    _add_box(ax_top, (0.83, 0.62), 0.12, 0.16, "State 5\nRecycle", "#fecaca")
    _add_box(ax_top, (0.83, 0.26), 0.12, 0.16, "State 6\nLandfill", "#e5e7eb")

    _add_arrow(ax_top, (0.19, 0.70), (0.25, 0.70), "1.0", text_offset=(0.0, 0.04))
    _add_arrow(ax_top, (0.39, 0.70), (0.45, 0.70), r"$p_{aging}$", text_offset=(0.0, 0.04))
    _add_arrow(ax_top, (0.52, 0.62), (0.72, 0.62), r"$p_{cascade}$", text_offset=(0.0, -0.05))
    _add_arrow(ax_top, (0.59, 0.70), (0.83, 0.70), r"$(1-p_{cascade}) \cdot c_{EV}$", text_offset=(0.0, 0.05))
    _add_arrow(ax_top, (0.52, 0.62), (0.89, 0.42), r"$(1-p_{cascade}) \cdot (1-c_{EV})$", rad=-0.05, text_offset=(0.0, -0.02))
    _add_arrow(ax_top, (0.32, 0.62), (0.89, 0.42), r"$p_{early,landfill}$", rad=-0.32, text_offset=(0.0, -0.05))
    _add_arrow(ax_top, (0.32, 0.62), (0.86, 0.62), r"$p_{early,recycle}$", rad=0.18, text_offset=(0.0, 0.06))
    _add_arrow(ax_top, (0.79, 0.70), (0.83, 0.70), r"$c_{cascade}$", text_offset=(0.0, 0.04))
    _add_arrow(ax_top, (0.72, 0.62), (0.89, 0.42), r"$1-c_{cascade}$", rad=-0.1, text_offset=(0.0, -0.04))
    _add_arrow(ax_top, (0.83, 0.62), (0.19, 0.78), r"$r_{effective}$", rad=0.35, text_offset=(-0.02, 0.08), color="#b91c1c", lw=2.2)
    _add_arrow(ax_top, (0.83, 0.62), (0.89, 0.42), r"$1-r_{effective}$", text_offset=(0.0, 0.03), color="#b91c1c", lw=2.0)
    _add_arrow(ax_top, (0.95, 0.34), (0.95, 0.34), "", color="#6b7280")
    ax_top.text(0.955, 0.34, "absorbing", fontsize=10.5, color="#6b7280", ha="left", va="center")

    ax_top.text(
        0.03,
        0.92,
        "1. Yamada Markov Chain Structure",
        fontsize=17,
        fontweight="bold",
        ha="left",
        color="#111827",
    )
    ax_top.text(
        0.03,
        0.08,
        "A battery unit moves across discrete states. Recycling sends material back to production, which creates the loop "
        "that the fundamental matrix can count.",
        fontsize=11.5,
        color="#374151",
        ha="left",
    )

    ax_left.set_xlim(0, 1)
    ax_left.set_ylim(0, 1)
    ax_left.text(0.04, 0.92, "2. Transition Matrix Partition", fontsize=16, fontweight="bold", ha="left", color="#111827")
    matrix_text = "A = [ Q   R ]\n    [ 0   I ]"
    ax_left.text(
        0.19,
        0.58,
        matrix_text,
        fontsize=25,
        ha="center",
        va="center",
        color="#111827",
        family="monospace",
    )
    ax_left.text(0.42, 0.70, r"$Q$: transitions among transient states", fontsize=12.5, color="#1f2937", ha="left")
    ax_left.text(0.42, 0.56, r"$R$: transitions from transient to absorbing states", fontsize=12.5, color="#1f2937", ha="left")
    ax_left.text(0.42, 0.42, r"$I$: once in landfill, the process stops", fontsize=12.5, color="#1f2937", ha="left")
    ax_left.text(
        0.04,
        0.17,
        "In the code, the first five states are treated as transient and the last state\n"
        "is the absorbing landfill state. This is why we extract Q from the upper-left block.",
        fontsize=11.2,
        color="#4b5563",
        ha="left",
    )

    ax_right.set_xlim(0, 1)
    ax_right.set_ylim(0, 1)
    ax_right.text(0.04, 0.92, "3. Fundamental Matrix and Circularity Count", fontsize=16, fontweight="bold", ha="left", color="#111827")
    ax_right.text(0.08, 0.70, r"$N = (I - Q)^{-1} = I + Q + Q^2 + Q^3 + \cdots$", fontsize=22, ha="left", color="#111827")
    ax_right.text(
        0.08,
        0.52,
        "Interpretation:\n"
        "Each power of Q counts one more round of movement among non-absorbing states.\n"
        "Because recycling returns material to production, repeated passages can occur.",
        fontsize=12.2,
        color="#374151",
        ha="left",
        va="center",
    )
    ax_right.text(
        0.08,
        0.28,
        r"In this implementation, the circularity indicator is taken as $N_{1,2}$,"
        "\nwhich measures the expected visits linked to the EV-use stage after entering the chain.",
        fontsize=12.2,
        color="#374151",
        ha="left",
    )
    ax_right.text(
        0.08,
        0.10,
        "Main intuition: stronger recycling and more return flow increase repeated use loops,\n"
        "so the expected circularity count N becomes larger.",
        fontsize=11.5,
        color="#7c2d12",
        ha="left",
    )

    fig.suptitle(
        "Yamada-Based Markov Chain Principle for Battery Circularity",
        fontsize=22,
        fontweight="bold",
        x=0.03,
        y=0.98,
        ha="left",
    )
    fig.text(
        0.03,
        0.94,
        "A one-page schematic of how discrete state transitions and the fundamental matrix are used to quantify the expected "
        "number of circular loops before final disposal.",
        fontsize=11.5,
        color="#4b5563",
        ha="left",
    )
    return fig


def main():
    script_path = Path(__file__).resolve()
    project_root = script_path.parents[2]
    output_path = project_root / "outputs" / OUTPUT_NAME
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig = create_figure()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(output_path)


if __name__ == "__main__":
    main()
