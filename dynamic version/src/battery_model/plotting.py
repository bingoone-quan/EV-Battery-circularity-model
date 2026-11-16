"""Plot helpers for the battery circularity simulation outputs."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np


def create_histogram_figure(
    battery_type,
    N_base,
    N_opt,
    Intensity_GHG_base,
    Intensity_GHG_opt,
    Intensity_Cost_base,
    Intensity_Cost_opt,
):
    """Create the 1x3 histogram comparison figure."""
    fig = plt.figure(figsize=(14, 4.5), facecolor="white")

    ax1 = fig.add_subplot(1, 3, 1)
    ax1.hist(N_base, bins=50, density=True, color=(0.2, 0.4, 0.6), edgecolor="none")
    ax1.hist(
        N_opt,
        bins=50,
        density=True,
        color=(0.8, 0.4, 0.2),
        edgecolor="none",
        alpha=0.7,
    )
    ax1.set_title(f"{battery_type} Battery Cycles (N)", fontsize=12)
    ax1.set_xlabel("Number of Lifecycles")
    ax1.set_ylabel("Probability Density")
    ax1.legend(["Baseline", "Policy-enhanced"])
    ax1.grid(True)

    ax2 = fig.add_subplot(1, 3, 2)
    ax2.hist(
        Intensity_GHG_base,
        bins=50,
        density=True,
        color=(0.2, 0.4, 0.6),
        edgecolor="none",
    )
    ax2.hist(
        Intensity_GHG_opt,
        bins=50,
        density=True,
        color=(0.4, 0.8, 0.4),
        edgecolor="none",
        alpha=0.7,
    )
    ax2.set_title("GHG Intensity (kg CO_2e / Cycle)", fontsize=12)
    ax2.set_xlabel("kg CO_2e per Lifecycle")
    ax2.set_ylabel("Probability Density")
    ax2.legend(["Baseline", "Policy-enhanced"])
    ax2.grid(True)

    ax3 = fig.add_subplot(1, 3, 3)
    ax3.hist(
        Intensity_Cost_base,
        bins=50,
        density=True,
        color=(0.2, 0.4, 0.6),
        edgecolor="none",
    )
    ax3.hist(
        Intensity_Cost_opt,
        bins=50,
        density=True,
        color=(0.8, 0.7, 0.2),
        edgecolor="none",
        alpha=0.7,
    )
    ax3.set_title("Net Cost Intensity ($ / Cycle)", fontsize=12)
    ax3.set_xlabel("Net System Cost (USD $)")
    ax3.set_ylabel("Probability Density")
    ax3.legend(["Baseline", "Policy-enhanced"])
    ax3.grid(True)

    fig.tight_layout()
    return fig


def _plot_binned_trend(ax, x_values, y_values, color, label):
    """Overlay a simple binned mean trend line on top of a scatter cloud."""
    x_values = np.asarray(x_values)
    y_values = np.asarray(y_values)

    finite_mask = np.isfinite(x_values) & np.isfinite(y_values)
    x_values = x_values[finite_mask]
    y_values = y_values[finite_mask]

    if x_values.size < 10:
        return

    bins = np.linspace(np.min(x_values), np.max(x_values), 12)
    if np.unique(bins).size < 3:
        return

    bin_ids = np.digitize(x_values, bins)
    x_means = []
    y_means = []
    for idx in range(1, len(bins)):
        mask = bin_ids == idx
        if np.any(mask):
            x_means.append(np.mean(x_values[mask]))
            y_means.append(np.mean(y_values[mask]))

    if x_means:
        ax.plot(
            x_means,
            y_means,
            color=color,
            linewidth=2.2,
            marker="o",
            markersize=4,
            label=label,
        )


def create_relationship_figure(
    battery_type,
    N_base,
    N_opt,
    Intensity_GHG_base,
    Intensity_GHG_opt,
    Intensity_Cost_base,
    Intensity_Cost_opt,
):
    """
    Create a 2D relationship figure that highlights the observed main pattern:
    higher N generally corresponds to lower GHG and cost intensity.
    """
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), facecolor="white")

    ax1, ax2 = axes

    ax1.scatter(
        N_base,
        Intensity_GHG_base,
        s=16,
        color=(0.6, 0.6, 0.6),
        alpha=0.25,
        label="Baseline Samples",
    )
    ax1.scatter(
        N_opt,
        Intensity_GHG_opt,
        s=18,
        color=(0.2, 0.55, 0.3),
        alpha=0.25,
        label="Policy-enhanced Samples",
    )
    _plot_binned_trend(ax1, N_base, Intensity_GHG_base, color=(0.35, 0.35, 0.35), label="Baseline Trend")
    _plot_binned_trend(ax1, N_opt, Intensity_GHG_opt, color=(0.0, 0.45, 0.15), label="Policy-enhanced Trend")
    ax1.set_title(f"{battery_type}: N vs GHG Intensity", fontsize=12)
    ax1.set_xlabel("Expected Cycles (N)")
    ax1.set_ylabel("GHG Intensity (kg CO_2e / Cycle)")
    ax1.grid(True)
    ax1.legend(loc="upper right")

    ax2.scatter(
        N_base,
        Intensity_Cost_base,
        s=16,
        color=(0.6, 0.6, 0.6),
        alpha=0.25,
        label="Baseline Samples",
    )
    ax2.scatter(
        N_opt,
        Intensity_Cost_opt,
        s=18,
        color=(0.8, 0.45, 0.1),
        alpha=0.25,
        label="Policy-enhanced Samples",
    )
    _plot_binned_trend(ax2, N_base, Intensity_Cost_base, color=(0.35, 0.35, 0.35), label="Baseline Trend")
    _plot_binned_trend(ax2, N_opt, Intensity_Cost_opt, color=(0.75, 0.35, 0.0), label="Policy-enhanced Trend")
    ax2.set_title(f"{battery_type}: N vs Cost Intensity", fontsize=12)
    ax2.set_xlabel("Expected Cycles (N)")
    ax2.set_ylabel("Net Cost Intensity ($ / Cycle)")
    ax2.grid(True)
    ax2.legend(loc="upper right")

    fig.suptitle("Lifecycle Performance Relationships", fontsize=14, fontweight="bold")
    fig.tight_layout()
    return fig
