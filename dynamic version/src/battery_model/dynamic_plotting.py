"""Plot helpers for the dynamic Markov battery simulation."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np


def _plot_band(ax, x_values, series, color, label):
    """Plot a mean line with a shaded uncertainty band."""
    ax.plot(x_values, series["mean"], color=color, linewidth=2.2, label=label)
    ax.fill_between(
        x_values,
        series["p10"],
        series["p90"],
        color=color,
        alpha=0.16,
        linewidth=0,
    )


def create_dynamic_stock_figure(years_axis, baseline, optimized):
    """Create a figure focused on stock evolution and yearly material routing."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), facecolor="white")
    ax1, ax2 = axes

    _plot_band(ax1, years_axis, baseline["in_use_stock"], color="#5b6570", label="Baseline In-use")
    _plot_band(ax1, years_axis, optimized["in_use_stock"], color="#18794e", label="Policy-enhanced In-use")
    _plot_band(ax1, years_axis, baseline["cascade_stock"], color="#9ea7ad", label="Baseline Cascade")
    _plot_band(ax1, years_axis, optimized["cascade_stock"], color="#5cbf8f", label="Policy-enhanced Cascade")
    ax1.set_title("Dynamic In-Use Stock Trajectories")
    ax1.set_xlabel("Year")
    ax1.set_ylabel("kg per initial kg battery")
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="upper right")

    _plot_band(ax2, years_axis, baseline["annual_recovered"], color="#3b82f6", label="Baseline Recovered")
    _plot_band(ax2, years_axis, optimized["annual_recovered"], color="#0f766e", label="Policy-enhanced Recovered")
    _plot_band(ax2, years_axis, baseline["annual_landfill"], color="#ef4444", label="Baseline Landfill")
    _plot_band(ax2, years_axis, optimized["annual_landfill"], color="#b91c1c", label="Policy-enhanced Landfill")
    ax2.set_title("Yearly Recovered and Landfilled Mass")
    ax2.set_xlabel("Year")
    ax2.set_ylabel("kg per initial kg battery")
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc="upper right")

    fig.tight_layout()
    return fig


def create_dynamic_impact_figure(years_axis, baseline, optimized):
    """Create a figure showing cumulative environmental and economic performance."""
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), facecolor="white")
    ax1, ax2, ax3, ax4 = axes.flatten()

    _plot_band(ax1, years_axis, baseline["ghg_cumulative"], color="#5b6570", label="Baseline")
    _plot_band(ax1, years_axis, optimized["ghg_cumulative"], color="#18794e", label="Policy-enhanced")
    ax1.set_title("Cumulative GHG")
    ax1.set_xlabel("Year")
    ax1.set_ylabel("kg CO2e per initial kg battery")
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="upper left")

    _plot_band(ax2, years_axis, baseline["cost_cumulative"], color="#5b6570", label="Baseline")
    _plot_band(ax2, years_axis, optimized["cost_cumulative"], color="#c17b00", label="Policy-enhanced")
    ax2.set_title("Cumulative Cost")
    ax2.set_xlabel("Year")
    ax2.set_ylabel("USD per initial kg battery")
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc="upper left")

    _plot_band(ax3, years_axis, baseline["recovered_cumulative"], color="#3b82f6", label="Baseline")
    _plot_band(ax3, years_axis, optimized["recovered_cumulative"], color="#0f766e", label="Policy-enhanced")
    ax3.set_title("Cumulative Recovered Mass")
    ax3.set_xlabel("Year")
    ax3.set_ylabel("kg per initial kg battery")
    ax3.grid(True, alpha=0.3)
    ax3.legend(loc="upper left")

    _plot_band(ax4, years_axis, baseline["landfill_cumulative"], color="#ef4444", label="Baseline")
    _plot_band(ax4, years_axis, optimized["landfill_cumulative"], color="#b91c1c", label="Policy-enhanced")
    ax4.set_title("Cumulative Landfilled Mass")
    ax4.set_xlabel("Year")
    ax4.set_ylabel("kg per initial kg battery")
    ax4.grid(True, alpha=0.3)
    ax4.legend(loc="upper left")

    fig.tight_layout()
    return fig


def create_dynamic_transition_figure(years_axis, baseline, optimized):
    """Create a figure showing the time-varying transition drivers."""
    fig, axes = plt.subplots(3, 1, figsize=(11, 9), facecolor="white", sharex=True)
    ax1, ax2, ax3 = axes

    ax1.plot(years_axis, baseline["subsidy_path"]["mean"], color="#5b6570", linewidth=2.0, label="Baseline")
    ax1.plot(years_axis, optimized["subsidy_path"]["mean"], color="#18794e", linewidth=2.0, label="Policy-enhanced")
    ax1.set_title("Policy-Strength Path")
    ax1.set_ylabel("Policy strength")
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="upper right")

    _plot_band(ax2, years_axis, baseline["collection_rate"], color="#5b6570", label="Baseline")
    _plot_band(ax2, years_axis, optimized["collection_rate"], color="#18794e", label="Policy-enhanced")
    ax2.set_title("Collection Rate Path")
    ax2.set_ylabel("Collection rate")
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc="upper right")

    _plot_band(ax3, years_axis, baseline["recovery_rate"], color="#5b6570", label="Baseline")
    _plot_band(ax3, years_axis, optimized["recovery_rate"], color="#18794e", label="Policy-enhanced")
    ax3.set_title("Effective Recovery Rate Path")
    ax3.set_xlabel("Year")
    ax3.set_ylabel("Recovery rate")
    ax3.grid(True, alpha=0.3)
    ax3.legend(loc="upper right")

    fig.tight_layout()
    return fig
