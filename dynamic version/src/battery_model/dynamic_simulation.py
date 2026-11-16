"""Dynamic time-evolving extension of the Yamada-style battery circularity model."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from battery_model.config import Scenario, TechConfig
from battery_model.dynamic_plotting import (
    create_dynamic_impact_figure,
    create_dynamic_stock_figure,
    create_dynamic_transition_figure,
)
from battery_model.everbatt import Get_EverBatt_Context, Get_EverBatt_Cost, Get_EverBatt_GHG
from battery_model.excel_reader import read_excel_scalar
from battery_model.paths import OUTPUTS_DIR, ensure_project_dirs, resolve_input_file
from battery_model.yamada import _get_battery_properties

MARKET_TYPE_TO_ALPHA = {
    "Sluggish Market": 0.8,
    "Moderate Market": 0.5,
    "Sensitive Market": 0.3,
}


@dataclass
class DynamicSettings:
    years: int = 20
    policy_ramp_years: int = 5
    ev_weibull_shape: float = 3.0
    cascade_weibull_shape: float = 2.0
    cascade_lifetime_factor: float = 0.65
    cascade_health_exponent: float = 0.8
    recycle_efficiency_decay: float = 0.08
    min_recovery_rate: float = 0.25
    collection_rate_cascade: float = 0.98
    alpha_pen: float = 0.05
    k_pen: float = 2.0
    min_health: float = 0.20
    depletion_threshold: float = 0.05


def _read_battery_type(excel_filename: str) -> str:
    try:
        battery_type = read_excel_scalar(excel_filename, "Input", "E9:E9")
        return str(battery_type)
    except Exception:
        print("Warning: Failed to read battery type from Excel")
        return "Unknown"


def _resolve_excel_source(excel_source):
    """Keep live Excel workbooks untouched and only resolve path-like inputs."""
    if isinstance(excel_source, (str, Path)):
        return str(resolve_input_file(str(excel_source)))
    return excel_source


def _read_base_recovery_rate(excel_filename: str) -> float:
    try:
        return float(read_excel_scalar(excel_filename, "Input", "F60:F60"))
    except Exception:
        return 0.90


def _read_cascade_economics(excel_filename: str, b2u_excel_filename: str):
    try:
        cascade_net_profit_kwh = float(
            read_excel_scalar(b2u_excel_filename, "Repurposing", "G175:G175")
        )
        pack_energy_density = float(read_excel_scalar(excel_filename, "Man Par.", "AJ88:AJ88"))
    except Exception as exc:
        print(
            "Warning: Failed to read cascade-utilization or energy-density data, "
            f"default values will be used. Error: {exc}"
        )
        cascade_net_profit_kwh = 1.7
        pack_energy_density = 0.16
    return cascade_net_profit_kwh, pack_energy_density


def _weibull_survival(age: float, scale: float, shape: float) -> float:
    """Return the survival fraction at a given cohort age."""
    scale = max(scale, 1e-6)
    shape = max(shape, 1e-6)
    return float(np.exp(-((max(age, 0.0) / scale) ** shape)))


def _annual_retention(age: int, scale: float, shape: float) -> float:
    """Return the conditional survival probability from age t to t+1."""
    survival_now = _weibull_survival(age, scale, shape)
    if survival_now <= 1e-12:
        return 0.0
    survival_next = _weibull_survival(age + 1, scale, shape)
    return float(np.clip(survival_next / survival_now, 0.0, 1.0))


def _build_subsidy_path(years: int, start: float, end: float, ramp_years: int) -> np.ndarray:
    """Create a policy path that ramps from baseline to the policy-enhanced level."""
    years = max(int(years), 1)
    if ramp_years <= 0:
        return np.full(years, end, dtype=float)

    ramp_years = max(1, int(ramp_years))
    path = np.full(years, end, dtype=float)
    ramp_steps = min(years, ramp_years)
    path[:ramp_steps] = np.linspace(start, end, ramp_steps)
    return path


def _collection_rate_from_subsidy(subsidy: float, subsidy_alpha: float) -> float:
    """Mirror the Yamada-style policy-strength response for EV collection."""
    base_ev_collection = 0.25
    max_policy_ceiling = 0.90
    subsidy_k = (max_policy_ceiling / base_ev_collection) - 1.0
    rate = base_ev_collection * (1.0 + subsidy_k * (subsidy**subsidy_alpha))
    return float(min(rate, max_policy_ceiling))


def _sample_chemistry_path_inputs(battery_type: str, base_r_input: float, rng) -> dict:
    """Sample one chemistry-specific parameter set for a Monte Carlo path."""
    props = _get_battery_properties(battery_type)
    scale_ev = max(1.0, rng.normal(props["w_mean"], props["w_std"]))
    base_cascade_cap = rng.uniform(props["casc_min"], props["casc_max"])
    r_effective_base = np.clip(base_r_input + rng.normal(0.0, 0.005), 0.0, 0.98) * props[
        "loop_rate"
    ]
    return {
        "scale_ev": float(scale_ev),
        "base_cascade_cap": float(base_cascade_cap),
        "r_effective_base": float(r_effective_base),
    }


def _merge_cohorts(cohorts: list[dict], scale_digits: int = 3) -> list[dict]:
    """Merge cohorts with identical age and nearly identical scale to keep paths compact."""
    merged = {}
    for cohort in cohorts:
        if cohort["mass"] <= 1e-12:
            continue
        key = (int(cohort["age"]), round(float(cohort["scale"]), scale_digits))
        merged[key] = merged.get(key, 0.0) + float(cohort["mass"])

    return [
        {"age": age, "scale": scale, "mass": mass}
        for (age, scale), mass in sorted(merged.items(), key=lambda item: (item[0][0], item[0][1]))
    ]


def _empty_series(years: int) -> dict:
    """Allocate the yearly series collected for one simulation path."""
    length = years + 1
    return {
        "ev_stock": np.zeros(length),
        "cascade_stock": np.zeros(length),
        "in_use_stock": np.zeros(length),
        "annual_landfill": np.zeros(length),
        "annual_recovered": np.zeros(length),
        "annual_recycle_input": np.zeros(length),
        "landfill_cumulative": np.zeros(length),
        "recovered_cumulative": np.zeros(length),
        "ghg_cumulative": np.zeros(length),
        "cost_cumulative": np.zeros(length),
        "collection_rate": np.zeros(length),
        "recovery_rate": np.zeros(length),
        "subsidy_path": np.zeros(length),
    }


def _scalar_summary(samples: np.ndarray) -> dict:
    """Summarize one scalar Monte Carlo output."""
    return {
        "mean": float(np.mean(samples)),
        "p10": float(np.percentile(samples, 10)),
        "p90": float(np.percentile(samples, 90)),
    }


def _series_summary(samples: np.ndarray) -> dict:
    """Summarize one time-series Monte Carlo output."""
    return {
        "mean": np.mean(samples, axis=0),
        "p10": np.percentile(samples, 10, axis=0),
        "p90": np.percentile(samples, 90, axis=0),
    }


def _run_single_dynamic_path(
    sampled_inputs: dict,
    subsidy_path: np.ndarray,
    subsidy_alpha: float,
    settings: DynamicSettings,
    ghg,
    cost,
    tech_config: TechConfig,
    input_mass: float = 1.0,
) -> tuple[dict, dict]:
    """
    Run one yearly time-evolving Markov path.

    The model keeps the Yamada circular structure but replaces the static
    fundamental-matrix solution with a cohort-based yearly propagation. EV-use and
    cascade-use stocks are represented as age cohorts with Weibull-style survival.
    """
    years = len(subsidy_path)
    series = _empty_series(years)

    ev_cohorts = [{"age": 0, "scale": sampled_inputs["scale_ev"], "mass": input_mass}]
    cascade_cohorts: list[dict] = []
    total_ev_entries = input_mass
    total_cascade_entries = 0.0
    cumulative_landfill = 0.0
    cumulative_recovered = 0.0
    cumulative_ghg = 0.0
    cumulative_cost = 0.0

    initial_collection_rate = _collection_rate_from_subsidy(subsidy_path[0], subsidy_alpha)
    series["ev_stock"][0] = input_mass
    series["in_use_stock"][0] = input_mass
    series["collection_rate"][0] = initial_collection_rate
    series["recovery_rate"][0] = sampled_inputs["r_effective_base"]
    series["subsidy_path"][0] = subsidy_path[0]

    for year in range(years):
        current_subsidy = float(subsidy_path[year])
        collection_rate_ev = _collection_rate_from_subsidy(current_subsidy, subsidy_alpha)
        recycle_burden = cumulative_recovered / input_mass
        recovery_rate = float(
            np.clip(
                sampled_inputs["r_effective_base"]
                * (1.0 - settings.recycle_efficiency_decay * recycle_burden),
                settings.min_recovery_rate,
                0.98,
            )
        )

        next_ev_cohorts: list[dict] = []
        next_cascade_cohorts: list[dict] = []
        recycle_input_mass = 0.0
        landfill_this_year = 0.0
        cascade_entry_mass = 0.0

        for cohort in ev_cohorts:
            retention = _annual_retention(
                cohort["age"],
                cohort["scale"],
                settings.ev_weibull_shape,
            )
            stay_mass = cohort["mass"] * retention
            exit_mass = cohort["mass"] - stay_mass

            if stay_mass > 1e-12:
                next_ev_cohorts.append(
                    {
                        "age": cohort["age"] + 1,
                        "scale": cohort["scale"],
                        "mass": stay_mass,
                    }
                )

            if exit_mass <= 1e-12:
                continue

            health = max(
                settings.min_health,
                _weibull_survival(
                    cohort["age"] + 1,
                    cohort["scale"],
                    settings.ev_weibull_shape,
                ),
            )
            early_fail_factor = 3.5 / max(cohort["scale"], 1e-6)
            direct_recycle_share = min(0.15, 0.02 * early_fail_factor)
            direct_landfill_share = min(0.10, 0.01 * early_fail_factor)

            direct_recycle_mass = exit_mass * direct_recycle_share
            direct_landfill_mass = exit_mass * direct_landfill_share
            managed_eol_mass = max(0.0, exit_mass - direct_recycle_mass - direct_landfill_mass)

            cascade_probability = float(
                np.clip(
                    sampled_inputs["base_cascade_cap"]
                    * (health**settings.cascade_health_exponent),
                    0.0,
                    0.95,
                )
            )
            to_cascade_mass = managed_eol_mass * cascade_probability
            remaining_eol_mass = managed_eol_mass - to_cascade_mass
            to_recycle_mass = remaining_eol_mass * collection_rate_ev
            to_landfill_mass = remaining_eol_mass - to_recycle_mass

            if to_cascade_mass > 1e-12:
                cascade_scale = max(
                    1.0,
                    cohort["scale"]
                    * settings.cascade_lifetime_factor
                    * (0.75 + 0.25 * health),
                )
                next_cascade_cohorts.append(
                    {
                        "age": 0,
                        "scale": cascade_scale,
                        "mass": to_cascade_mass,
                    }
                )
                cascade_entry_mass += to_cascade_mass

            recycle_input_mass += direct_recycle_mass + to_recycle_mass
            landfill_this_year += direct_landfill_mass + to_landfill_mass

        for cohort in cascade_cohorts:
            retention = _annual_retention(
                cohort["age"],
                cohort["scale"],
                settings.cascade_weibull_shape,
            )
            stay_mass = cohort["mass"] * retention
            exit_mass = cohort["mass"] - stay_mass

            if stay_mass > 1e-12:
                next_cascade_cohorts.append(
                    {
                        "age": cohort["age"] + 1,
                        "scale": cohort["scale"],
                        "mass": stay_mass,
                    }
                )

            if exit_mass > 1e-12:
                recycle_input_mass += exit_mass * settings.collection_rate_cascade
                landfill_this_year += exit_mass * (1.0 - settings.collection_rate_cascade)

        loop_burden = (cumulative_recovered + recycle_input_mass) / input_mass
        if tech_config.regen == "Direct":
            dynamic_penalty = 1.0 + settings.alpha_pen * (loop_burden**settings.k_pen)
        else:
            dynamic_penalty = 1.0

        recovered_mass = recycle_input_mass * recovery_rate
        landfill_this_year += recycle_input_mass - recovered_mass

        if recovered_mass > 1e-12:
            next_ev_cohorts.append(
                {
                    "age": 0,
                    "scale": sampled_inputs["scale_ev"],
                    "mass": recovered_mass,
                }
            )
            total_ev_entries += recovered_mass

        total_cascade_entries += cascade_entry_mass

        yearly_ghg = recycle_input_mass * (ghg.E_trans + ghg.E_loop * dynamic_penalty)
        yearly_cost = (
            recycle_input_mass * (cost.C_trans + cost.C_loop * dynamic_penalty)
            + cascade_entry_mass * cost.C_casc_net
        )
        if year == 0:
            yearly_ghg += input_mass * ghg.E_mfg
            yearly_cost += input_mass * cost.C_mfg

        cumulative_landfill += landfill_this_year
        cumulative_recovered += recovered_mass
        cumulative_ghg += yearly_ghg
        cumulative_cost += yearly_cost

        ev_cohorts = _merge_cohorts(next_ev_cohorts)
        cascade_cohorts = _merge_cohorts(next_cascade_cohorts)

        idx = year + 1
        ev_stock = sum(cohort["mass"] for cohort in ev_cohorts)
        cascade_stock = sum(cohort["mass"] for cohort in cascade_cohorts)
        series["ev_stock"][idx] = ev_stock
        series["cascade_stock"][idx] = cascade_stock
        series["in_use_stock"][idx] = ev_stock + cascade_stock
        series["annual_landfill"][idx] = landfill_this_year
        series["annual_recovered"][idx] = recovered_mass
        series["annual_recycle_input"][idx] = recycle_input_mass
        series["landfill_cumulative"][idx] = cumulative_landfill
        series["recovered_cumulative"][idx] = cumulative_recovered
        series["ghg_cumulative"][idx] = cumulative_ghg
        series["cost_cumulative"][idx] = cumulative_cost
        series["collection_rate"][idx] = collection_rate_ev
        series["recovery_rate"][idx] = recovery_rate
        series["subsidy_path"][idx] = current_subsidy

    years_axis = np.arange(years + 1)
    in_use_stock = series["in_use_stock"]
    depletion_candidates = years_axis[in_use_stock <= settings.depletion_threshold]
    depletion_year = int(depletion_candidates[0]) if depletion_candidates.size else int(years_axis[-1])

    summary = {
        "final_in_use_stock": in_use_stock[-1],
        "peak_in_use_stock": float(np.max(in_use_stock)),
        "peak_in_use_year": int(years_axis[np.argmax(in_use_stock)]),
        "cumulative_landfill": cumulative_landfill,
        "cumulative_recovered": cumulative_recovered,
        "cumulative_ghg": cumulative_ghg,
        "cumulative_cost": cumulative_cost,
        "equivalent_service_loops": (total_ev_entries + total_cascade_entries) / input_mass,
        "depletion_year": depletion_year,
    }
    return series, summary


def _allocate_monte_carlo_store(n_sims: int, years: int) -> dict:
    """Allocate arrays for scenario-level Monte Carlo storage."""
    length = years + 1
    series_store = {
        key: np.zeros((n_sims, length))
        for key in [
            "ev_stock",
            "cascade_stock",
            "in_use_stock",
            "annual_landfill",
            "annual_recovered",
            "annual_recycle_input",
            "landfill_cumulative",
            "recovered_cumulative",
            "ghg_cumulative",
            "cost_cumulative",
            "collection_rate",
            "recovery_rate",
            "subsidy_path",
        ]
    }
    summary_store = {
        key: np.zeros(n_sims)
        for key in [
            "final_in_use_stock",
            "peak_in_use_stock",
            "peak_in_use_year",
            "cumulative_landfill",
            "cumulative_recovered",
            "cumulative_ghg",
            "cumulative_cost",
            "equivalent_service_loops",
            "depletion_year",
        ]
    }
    return {"series": series_store, "summary": summary_store}


def _finalize_monte_carlo_store(store: dict) -> dict:
    """Convert raw Monte Carlo arrays into summary statistics."""
    return {
        "series": {key: _series_summary(values) for key, values in store["series"].items()},
        "summary": {key: _scalar_summary(values) for key, values in store["summary"].items()},
    }


def run_dynamic_simulation(
    n_sims: int = 500,
    years: int = 20,
    excel_filename: str = "EverBatt.xlsm",
    b2u_excel_filename: str = "nrel-b2u-repurposing-cost-calculator-jun2020.xlsm",
    show_plots: bool = True,
    return_figures: bool = False,
    subsidy_base: float = 0.23,
    subsidy_opt: float = 0.5,
    policy_ramp_years: int = 5,
    market_type: str = "Moderate Market",
    process: str = "Direct",
    regen: str = "Direct",
    ev_weibull_shape: float = 3.0,
    cascade_weibull_shape: float = 2.0,
    cascade_lifetime_factor: float = 0.65,
    cascade_health_exponent: float = 0.8,
    recycle_efficiency_decay: float = 0.08,
    random_seed: int = 42,
    build_figures: bool = True,
):
    """Run the dynamic time-evolving Markov simulation."""
    ensure_project_dirs()

    excel_source = _resolve_excel_source(excel_filename)
    b2u_excel_source = _resolve_excel_source(b2u_excel_filename)

    battery_type = _read_battery_type(excel_source)
    print(f"=== Dynamic battery type: {battery_type} ===")

    context, context_info = Get_EverBatt_Context(excel_source)
    print("\n=== Dynamic Simulation Context ===")
    print(context_info)
    print("--------------------------------")
    _ = context

    base_r_val = _read_base_recovery_rate(excel_source)
    tech_config = TechConfig(process=process, regen=regen)
    ghg, tech_info = Get_EverBatt_GHG(excel_source, battery_type, tech_config)
    cost, cost_info = Get_EverBatt_Cost(excel_source, battery_type, tech_config)

    cascade_net_profit_kwh, pack_energy_density = _read_cascade_economics(
        excel_source, b2u_excel_source
    )
    cost.C_casc_net = -cascade_net_profit_kwh * pack_energy_density

    subsidy_alpha = MARKET_TYPE_TO_ALPHA.get(market_type, 0.5)
    _ = Scenario(subsidy=subsidy_base, subsidy_alpha=subsidy_alpha)
    settings = DynamicSettings(
        years=years,
        policy_ramp_years=policy_ramp_years,
        ev_weibull_shape=ev_weibull_shape,
        cascade_weibull_shape=cascade_weibull_shape,
        cascade_lifetime_factor=cascade_lifetime_factor,
        cascade_health_exponent=cascade_health_exponent,
        recycle_efficiency_decay=recycle_efficiency_decay,
    )

    baseline_path = np.full(years, subsidy_base, dtype=float)
    optimized_path = _build_subsidy_path(years, subsidy_base, subsidy_opt, policy_ramp_years)
    rng = np.random.default_rng(random_seed)

    monte_carlo = {
        "baseline": _allocate_monte_carlo_store(n_sims, years),
        "optimized": _allocate_monte_carlo_store(n_sims, years),
    }

    for sim_idx in range(n_sims):
        sampled_inputs = _sample_chemistry_path_inputs(battery_type, base_r_val, rng)

        baseline_series, baseline_summary = _run_single_dynamic_path(
            sampled_inputs=sampled_inputs,
            subsidy_path=baseline_path,
            subsidy_alpha=subsidy_alpha,
            settings=settings,
            ghg=ghg,
            cost=cost,
            tech_config=tech_config,
        )
        optimized_series, optimized_summary = _run_single_dynamic_path(
            sampled_inputs=sampled_inputs,
            subsidy_path=optimized_path,
            subsidy_alpha=subsidy_alpha,
            settings=settings,
            ghg=ghg,
            cost=cost,
            tech_config=tech_config,
        )

        for key, values in baseline_series.items():
            monte_carlo["baseline"]["series"][key][sim_idx, :] = values
        for key, value in baseline_summary.items():
            monte_carlo["baseline"]["summary"][key][sim_idx] = value

        for key, values in optimized_series.items():
            monte_carlo["optimized"]["series"][key][sim_idx, :] = values
        for key, value in optimized_summary.items():
            monte_carlo["optimized"]["summary"][key][sim_idx] = value

    baseline = _finalize_monte_carlo_store(monte_carlo["baseline"])
    optimized = _finalize_monte_carlo_store(monte_carlo["optimized"])
    years_axis = np.arange(years + 1)

    comparison = {
        key: optimized["summary"][key]["mean"] - baseline["summary"][key]["mean"]
        for key in baseline["summary"]
    }

    fig_stock = None
    fig_impacts = None
    fig_transitions = None
    if build_figures:
        fig_stock = create_dynamic_stock_figure(years_axis, baseline["series"], optimized["series"])
        fig_impacts = create_dynamic_impact_figure(years_axis, baseline["series"], optimized["series"])
        fig_transitions = create_dynamic_transition_figure(
            years_axis,
            baseline["series"],
            optimized["series"],
        )

    print("\n=== Dynamic Simulation Results ===")
    print(f"Technology Used: {tech_info}")
    print(f"Economics Info:  {cost_info}")
    print("----------------------------------")
    print(
        "Equivalent service loops | "
        f"{baseline['summary']['equivalent_service_loops']['mean']:.2f} -> "
        f"{optimized['summary']['equivalent_service_loops']['mean']:.2f}"
    )
    print(
        "Final in-use stock       | "
        f"{baseline['summary']['final_in_use_stock']['mean']:.3f} -> "
        f"{optimized['summary']['final_in_use_stock']['mean']:.3f}"
    )
    print(
        "Cumulative landfill      | "
        f"{baseline['summary']['cumulative_landfill']['mean']:.3f} -> "
        f"{optimized['summary']['cumulative_landfill']['mean']:.3f}"
    )
    print(
        "Cumulative GHG           | "
        f"{baseline['summary']['cumulative_ghg']['mean']:.2f} -> "
        f"{optimized['summary']['cumulative_ghg']['mean']:.2f}"
    )
    print(
        "Cumulative cost          | "
        f"{baseline['summary']['cumulative_cost']['mean']:.2f} -> "
        f"{optimized['summary']['cumulative_cost']['mean']:.2f}"
    )

    if build_figures and show_plots:
        plt.show()
    elif build_figures and return_figures:
        pass
    elif build_figures:
        fig_stock.savefig(OUTPUTS_DIR / "dynamic_stock_trajectories.png", dpi=300, bbox_inches="tight")
        fig_impacts.savefig(OUTPUTS_DIR / "dynamic_cumulative_impacts.png", dpi=300, bbox_inches="tight")
        fig_transitions.savefig(
            OUTPUTS_DIR / "dynamic_transition_paths.png",
            dpi=300,
            bbox_inches="tight",
        )
        plt.close(fig_stock)
        plt.close(fig_impacts)
        plt.close(fig_transitions)

    return {
        "battery_type": battery_type,
        "context_info": context_info,
        "tech_info": tech_info,
        "cost_info": cost_info,
        "years_axis": years_axis,
        "subsidy_base": subsidy_base,
        "subsidy_opt": subsidy_opt,
        "policy_ramp_years": policy_ramp_years,
        "market_type": market_type,
        "subsidy_alpha": subsidy_alpha,
        "process": process,
        "regen": regen,
        "dynamic_settings": settings,
        "baseline": baseline,
        "optimized": optimized,
        "comparison": comparison,
        "fig_stock": fig_stock if (build_figures and return_figures) else None,
        "fig_impacts": fig_impacts if (build_figures and return_figures) else None,
        "fig_transitions": fig_transitions if (build_figures and return_figures) else None,
    }


def _build_parser():
    parser = argparse.ArgumentParser(description="Dynamic extension of the EV battery circularity model.")
    parser.add_argument("--n-sims", type=int, default=300, help="Number of Monte Carlo simulations.")
    parser.add_argument("--years", type=int, default=20, help="Number of simulated years.")
    parser.add_argument(
        "--excel",
        default="EverBatt.xlsm",
        help="EverBatt workbook placed in the dynamic version root, parent project root, or data folder.",
    )
    parser.add_argument(
        "--b2u-excel",
        default="nrel-b2u-repurposing-cost-calculator-jun2020.xlsm",
        help="B2U workbook placed in the dynamic version root, parent project root, or data folder.",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Save figures instead of opening plot windows.",
    )
    parser.add_argument("--subsidy-opt", type=float, default=0.5, help="Policy-enhanced target.")
    parser.add_argument(
        "--policy-ramp-years",
        type=int,
        default=5,
        help="Years needed for the policy-enhanced scenario to reach the target policy strength.",
    )
    parser.add_argument(
        "--market-type",
        default="Moderate Market",
        choices=list(MARKET_TYPE_TO_ALPHA.keys()),
        help="Market response scenario controlling the policy-response exponent.",
    )
    parser.add_argument(
        "--process",
        default="Direct",
        choices=["Pyro", "Hydro", "Direct"],
        help="Recycling process pathway.",
    )
    parser.add_argument(
        "--regen",
        default="Direct",
        choices=["Pyro", "Hydro", "Direct"],
        help="Cathode regeneration pathway.",
    )
    parser.add_argument(
        "--ev-shape",
        type=float,
        default=3.0,
        help="Weibull shape used for EV-use cohorts.",
    )
    parser.add_argument(
        "--cascade-shape",
        type=float,
        default=2.0,
        help="Weibull shape used for cascade-use cohorts.",
    )
    parser.add_argument(
        "--cascade-factor",
        type=float,
        default=0.65,
        help="Relative lifetime factor applied to cascade-use cohorts.",
    )
    parser.add_argument(
        "--recovery-decay",
        type=float,
        default=0.08,
        help="How strongly recycling efficiency declines with cumulative loop burden.",
    )
    return parser


def main():
    parser = _build_parser()
    args = parser.parse_args()
    run_dynamic_simulation(
        n_sims=args.n_sims,
        years=args.years,
        excel_filename=args.excel,
        b2u_excel_filename=args.b2u_excel,
        show_plots=not args.no_show,
        subsidy_opt=args.subsidy_opt,
        policy_ramp_years=args.policy_ramp_years,
        market_type=args.market_type,
        process=args.process,
        regen=args.regen,
        ev_weibull_shape=args.ev_shape,
        cascade_weibull_shape=args.cascade_shape,
        cascade_lifetime_factor=args.cascade_factor,
        recycle_efficiency_decay=args.recovery_decay,
    )


if __name__ == "__main__":
    main()
