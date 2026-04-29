"""Generate a one-page explainer figure for the Weibull lifetime assumption."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


OUTPUT_NAME = "weibull_explainer_onepage.png"


def weibull_survival(age, scale, shape):
    age = np.maximum(np.asarray(age, dtype=float), 0.0)
    scale = max(float(scale), 1e-6)
    shape = max(float(shape), 1e-6)
    return np.exp(-((age / scale) ** shape))


def annual_exit(age, scale, shape):
    s_now = weibull_survival(age, scale, shape)
    s_next = weibull_survival(np.asarray(age) + 1.0, scale, shape)
    out = np.zeros_like(s_now, dtype=float)
    mask = s_now > 1e-12
    out[mask] = 1.0 - (s_next[mask] / s_now[mask])
    return np.clip(out, 0.0, 1.0)


def _style_axis(ax):
    ax.grid(True, alpha=0.18, linewidth=0.8)
    for spine in ax.spines.values():
        spine.set_alpha(0.2)


def create_figure():
    ages = np.linspace(0, 15, 301)
    age_year = np.arange(0, 15)

    fig = plt.figure(figsize=(14, 9), facecolor="#fbfaf6")
    gs = fig.add_gridspec(2, 2, hspace=0.28, wspace=0.18)

    ax1 = fig.add_subplot(gs[0, 0], facecolor="white")
    ax2 = fig.add_subplot(gs[0, 1], facecolor="white")
    ax3 = fig.add_subplot(gs[1, 0], facecolor="white")
    ax4 = fig.add_subplot(gs[1, 1], facecolor="white")

    shape_specs = [
        (1.2, "#4c78a8", "shape = 1.2"),
        (2.0, "#f58518", "shape = 2.0"),
        (3.0, "#54a24b", "shape = 3.0"),
    ]
    scale_demo = 8.0

    for shape, color, label in shape_specs:
        ax1.plot(
            ages,
            weibull_survival(ages, scale_demo, shape),
            color=color,
            linewidth=2.6,
            label=label,
        )
    ax1.axvline(scale_demo, color="#444444", linestyle="--", linewidth=1.2)
    ax1.text(scale_demo + 0.15, 0.08, "scale", color="#444444", fontsize=10)
    ax1.set_title("1. Survival Curve: remaining share in use", loc="left", fontsize=13, pad=10)
    ax1.set_xlabel("Age (years)")
    ax1.set_ylabel("Survival fraction")
    ax1.set_xlim(0, 15)
    ax1.set_ylim(0, 1.02)
    ax1.legend(frameon=False, loc="upper right")
    _style_axis(ax1)

    for shape, color, label in shape_specs:
        ax2.plot(
            age_year,
            annual_exit(age_year, scale_demo, shape),
            color=color,
            linewidth=2.6,
            marker="o",
            markersize=4.5,
            label=label,
        )
    ax2.set_title("2. Annual Exit Probability: chance of retiring next year", loc="left", fontsize=13, pad=10)
    ax2.set_xlabel("Current age (years)")
    ax2.set_ylabel("Exit probability")
    ax2.set_xlim(0, 14)
    ax2.set_ylim(0, 1.0)
    _style_axis(ax2)

    scale_specs = [
        (6.0, "#e45756", "scale = 6"),
        (8.0, "#4c78a8", "scale = 8"),
        (10.0, "#72b7b2", "scale = 10"),
    ]
    fixed_shape = 3.0
    for scale, color, label in scale_specs:
        curve = weibull_survival(ages, scale, fixed_shape)
        ax3.plot(ages, curve, color=color, linewidth=2.8, label=label)
        marker_y = float(weibull_survival(scale, scale, fixed_shape))
        ax3.scatter([scale], [marker_y], color=color, s=30, zorder=3)
    ax3.set_title("3. Scale Parameter: moves the retirement window left or right", loc="left", fontsize=13, pad=10)
    ax3.set_xlabel("Age (years)")
    ax3.set_ylabel("Survival fraction")
    ax3.set_xlim(0, 15)
    ax3.set_ylim(0, 1.02)
    ax3.legend(frameon=False, loc="upper right")
    _style_axis(ax3)

    model_ev_scale = 8.0
    model_cascade_scale = model_ev_scale * 0.65 * (0.75 + 0.25 * 0.7)
    ev_curve = weibull_survival(ages, model_ev_scale, 3.0)
    cascade_curve = weibull_survival(ages, model_cascade_scale, 2.0)
    ax4.plot(ages, ev_curve, color="#2c7a4b", linewidth=3.0, label="EV use in model")
    ax4.plot(ages, cascade_curve, color="#c17b00", linewidth=3.0, label="Cascade use in model")
    ax4.fill_between(ages, 0, ev_curve, color="#2c7a4b", alpha=0.08)
    ax4.fill_between(ages, 0, cascade_curve, color="#c17b00", alpha=0.10)
    ax4.text(
        0.04,
        0.95,
        "In your dynamic model:\nEV cohorts use shape = 3.0\nCascade cohorts use shape = 2.0\nCascade life is shorter via a smaller scale",
        transform=ax4.transAxes,
        va="top",
        ha="left",
        fontsize=10.5,
        bbox={"boxstyle": "round,pad=0.4", "facecolor": "#fff7e8", "edgecolor": "#e2c98a"},
    )
    ax4.annotate(
        "Steeper late-life retirement",
        xy=(8.5, float(weibull_survival(8.5, model_ev_scale, 3.0))),
        xytext=(9.5, 0.72),
        arrowprops={"arrowstyle": "->", "color": "#2c7a4b", "lw": 1.2},
        fontsize=10,
        color="#2c7a4b",
    )
    ax4.annotate(
        "Second-life stock declines earlier",
        xy=(4.8, float(weibull_survival(4.8, model_cascade_scale, 2.0))),
        xytext=(7.6, 0.28),
        arrowprops={"arrowstyle": "->", "color": "#c17b00", "lw": 1.2},
        fontsize=10,
        color="#9a6200",
    )
    ax4.set_title("4. How the model uses Weibull", loc="left", fontsize=13, pad=10)
    ax4.set_xlabel("Age (years)")
    ax4.set_ylabel("Survival fraction")
    ax4.set_xlim(0, 15)
    ax4.set_ylim(0, 1.02)
    ax4.legend(frameon=False, loc="upper right")
    _style_axis(ax4)

    fig.suptitle(
        "Why Weibull Works for Battery Lifetime Modeling",
        fontsize=21,
        fontweight="bold",
        x=0.06,
        ha="left",
        y=0.97,
    )
    fig.text(
        0.06,
        0.928,
        "Weibull is intuitive because it can represent age-dependent retirement: batteries do not fail at a constant rate, "
        "and shape/scale control both when and how sharply retirement happens.",
        fontsize=11.5,
        color="#444444",
    )
    fig.text(
        0.06,
        0.03,
        "Reading guide: shape controls how the failure risk changes with age; scale controls the timing of retirement. "
        "This is why Weibull is a convenient choice for EV-use and second-life cohorts.",
        fontsize=11,
        color="#444444",
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
