"""Main simulation entry point and Monte Carlo workflow."""

from __future__ import annotations

import argparse

import matplotlib.pyplot as plt
import numpy as np

from battery_model.config import Scenario, TechConfig
from battery_model.everbatt import (
    Get_EverBatt_Context,
    Get_EverBatt_Cost,
    Get_EverBatt_GHG,
)
from battery_model.excel_reader import read_excel_scalar
from battery_model.paths import OUTPUTS_DIR, ensure_project_dirs, resolve_input_file
from battery_model.plotting import create_histogram_figure, create_relationship_figure
from battery_model.yamada import Calculate_Yamada_N_Matrix, Construct_Yamada_Matrix

MARKET_TYPE_TO_ALPHA = {
    "Sluggish Market": 0.8,
    "Moderate Market": 0.5,
    "Sensitive Market": 0.3,
}


def _read_battery_type(excel_filename: str) -> str:
    try:
        battery_type = read_excel_scalar(excel_filename, "Input", "E9:E9")
        return str(battery_type)
    except Exception:
        print("Warning: Failed to read battery type from Excel")
        return "Unknown"


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


def run_simulation(
    n_sims: int = 5000,
    excel_filename: str = "EverBatt.xlsm",
    b2u_excel_filename: str = "nrel-b2u-repurposing-cost-calculator-jun2020.xlsm",
    show_plots: bool = True,
    subsidy_base: float = 0.23,
    subsidy_opt: float = 0.5,
    market_type: str = "Moderate Market",
    process: str = "Direct",
    regen: str = "Direct",
    return_figures: bool = False,
):
    """Run the Monte Carlo battery circularity simulation."""
    ensure_project_dirs()

    excel_path = resolve_input_file(excel_filename)
    b2u_excel_path = resolve_input_file(b2u_excel_filename)

    input_mass = 1000.0
    P0 = np.array([input_mass, 0.0, 0.0, 0.0, 0.0], dtype=float)

    battery_type = _read_battery_type(str(excel_path))
    print(f"=== Battery type: {battery_type} ===")

    context, context_info = Get_EverBatt_Context(str(excel_path))
    print("\n=== Simulation Context ===")
    print(context_info)
    print("--------------------------")
    _ = context

    base_r_val = _read_base_recovery_rate(str(excel_path))

    tech_config = TechConfig(process=process, regen=regen)
    ghg, tech_info = Get_EverBatt_GHG(str(excel_path), battery_type, tech_config)
    cost, cost_info = Get_EverBatt_Cost(str(excel_path), battery_type, tech_config)

    cascade_net_profit_kwh, pack_energy_density = _read_cascade_economics(
        str(excel_path), str(b2u_excel_path)
    )

    net_cascade_cost_kwh = -cascade_net_profit_kwh
    cost.C_casc_net = net_cascade_cost_kwh * pack_energy_density

    print("--- Cascade Economics (Read from Excel) ---")
    print(f"Net Profit:  $ {cascade_net_profit_kwh:.2f} / kWh")
    print(f"Pack Density:  {pack_energy_density:.3f} kWh / kg")
    print(f"Net Cost:    $ {cost.C_casc_net:.3f} / kg")
    print("-------------------------------------------")

    subsidy_alpha = MARKET_TYPE_TO_ALPHA.get(market_type, 0.5)

    # design_effort was removed, so scenarios differ only by policy subsidy.
    # Market type controls the subsidy response curvature shared by both scenarios.
    scenario_base = Scenario(subsidy=subsidy_base, subsidy_alpha=subsidy_alpha)
    scenario_opt = Scenario(subsidy=subsidy_opt, subsidy_alpha=subsidy_alpha)

    N_base = np.zeros(n_sims)
    N_opt = np.zeros(n_sims)
    GHG_base = np.zeros(n_sims)
    GHG_opt = np.zeros(n_sims)
    Cost_base = np.zeros(n_sims)
    Cost_opt = np.zeros(n_sims)

    W_flow_base = np.zeros((n_sims, 5))
    W_flow_opt = np.zeros((n_sims, 5))
    Landfill_base = np.zeros(n_sims)
    Landfill_opt = np.zeros(n_sims)

    alpha_pen = 0.05
    k_pen = 2.0

    print("Starting simulation...")
    for i in range(n_sims):
        A_base, _ = Construct_Yamada_Matrix(
            scenario_base.subsidy,
            battery_type,
            base_r_val,
            subsidy_alpha=scenario_base.subsidy_alpha,
        )
        n_val_b, N_mat_b = Calculate_Yamada_N_Matrix(A_base)
        N_base[i] = n_val_b

        W_flow_base[i, :] = P0 @ N_mat_b
        R_vec_base = A_base[:5, 5]
        Landfill_base[i] = W_flow_base[i, :] @ R_vec_base

        A_opt, _ = Construct_Yamada_Matrix(
            scenario_opt.subsidy,
            battery_type,
            base_r_val,
            subsidy_alpha=scenario_opt.subsidy_alpha,
        )
        n_val_o, N_mat_o = Calculate_Yamada_N_Matrix(A_opt)
        N_opt[i] = n_val_o

        W_flow_opt[i, :] = P0 @ N_mat_o
        R_vec_opt = A_opt[:5, 5]
        Landfill_opt[i] = W_flow_opt[i, :] @ R_vec_opt

        N_recycle_base = N_mat_b[0, 4]
        N_recycle_opt = N_mat_o[0, 4]

        if tech_config.regen == "Direct":
            penalty_base = 1.0 + alpha_pen * (N_recycle_base**k_pen)
            penalty_opt = 1.0 + alpha_pen * (N_recycle_opt**k_pen)
        else:
            penalty_base = 1.0
            penalty_opt = 1.0

        GHG_loop_actual_base = ghg.E_loop * penalty_base
        Cost_loop_actual_base = cost.C_loop * penalty_base
        GHG_loop_actual_opt = ghg.E_loop * penalty_opt
        Cost_loop_actual_opt = cost.C_loop * penalty_opt

        GHG_base[i] = (1.0 * ghg.E_mfg) + (
            N_recycle_base * (ghg.E_trans + GHG_loop_actual_base)
        )
        GHG_opt[i] = (1.0 * ghg.E_mfg) + (
            N_recycle_opt * (ghg.E_trans + GHG_loop_actual_opt)
        )

        Cost_base[i] = (
            (1.0 * cost.C_mfg)
            + (N_mat_b[0, 3] * cost.C_casc_net)
            + (N_recycle_base * (cost.C_trans + Cost_loop_actual_base))
        )
        Cost_opt[i] = (
            (1.0 * cost.C_mfg)
            + (N_mat_o[0, 3] * cost.C_casc_net)
            + (N_recycle_opt * (cost.C_trans + Cost_loop_actual_opt))
        )

    with np.errstate(divide="ignore", invalid="ignore"):
        Intensity_GHG_base = GHG_base / N_base
        Intensity_GHG_opt = GHG_opt / N_opt
        Intensity_Cost_base = Cost_base / N_base
        Intensity_Cost_opt = Cost_opt / N_opt

    fig = create_histogram_figure(
        battery_type,
        N_base,
        N_opt,
        Intensity_GHG_base,
        Intensity_GHG_opt,
        Intensity_Cost_base,
        Intensity_Cost_opt,
    )
    fig_relationship = create_relationship_figure(
        battery_type,
        N_base,
        N_opt,
        Intensity_GHG_base,
        Intensity_GHG_opt,
        Intensity_Cost_base,
        Intensity_Cost_opt,
    )

    print("\n=== Simulation Results (Environmental & Economic) ===")
    print(f"Technology Used: {tech_info}")
    print(f"Economics Info:  {cost_info}")
    print(f"Penalty Applied: {str(tech_config.regen == 'Direct')}")
    print("------------------------------------------------------------")
    print("Metric (Per kg Battery) | Baseline   | Optimized  | Change ")
    print("------------------------|------------|------------|--------")

    mean_N_base = float(np.mean(N_base))
    mean_N_opt = float(np.mean(N_opt))
    print(
        f"Avg Cycles (N)          | {mean_N_base:.2f}       | {mean_N_opt:.2f}       | "
        f"+{(mean_N_opt - mean_N_base) / mean_N_base * 100:.1f}%"
    )

    mean_ghg_base = float(np.nanmean(Intensity_GHG_base))
    mean_ghg_opt = float(np.nanmean(Intensity_GHG_opt))
    print(
        f"GHG Intensity (kg/Cycle)| {mean_ghg_base:.2f}       | {mean_ghg_opt:.2f}       | "
        f"{(mean_ghg_opt - mean_ghg_base) / mean_ghg_base * 100:.1f}% "
    )

    mean_cost_base = float(np.nanmean(Intensity_Cost_base))
    mean_cost_opt = float(np.nanmean(Intensity_Cost_opt))
    print(
        f"Cost Intensity ($/Cycle)| $ {mean_cost_base:.2f}     | $ {mean_cost_opt:.2f}     | "
        f"{(mean_cost_opt - mean_cost_base) / mean_cost_base * 100:.1f}% "
    )
    print("------------------------------------------------------------")

    if show_plots:
        plt.show()
    elif return_figures:
        pass
    else:
        fig.savefig(OUTPUTS_DIR / "simulation_histograms.png", dpi=300, bbox_inches="tight")
        fig_relationship.savefig(
            OUTPUTS_DIR / "simulation_relationships.png",
            dpi=300,
            bbox_inches="tight",
        )
        plt.close(fig)
        plt.close(fig_relationship)

    return {
        "N_base": N_base,
        "N_opt": N_opt,
        "GHG_base": GHG_base,
        "GHG_opt": GHG_opt,
        "Cost_base": Cost_base,
        "Cost_opt": Cost_opt,
        "W_flow_base": W_flow_base,
        "W_flow_opt": W_flow_opt,
        "Landfill_base": Landfill_base,
        "Landfill_opt": Landfill_opt,
        "Intensity_GHG_base": Intensity_GHG_base,
        "Intensity_GHG_opt": Intensity_GHG_opt,
        "Intensity_Cost_base": Intensity_Cost_base,
        "Intensity_Cost_opt": Intensity_Cost_opt,
        "battery_type": battery_type,
        "context_info": context_info,
        "tech_info": tech_info,
        "cost_info": cost_info,
        "mean_N_base": mean_N_base,
        "mean_N_opt": mean_N_opt,
        "mean_ghg_base": mean_ghg_base,
        "mean_ghg_opt": mean_ghg_opt,
        "mean_cost_base": mean_cost_base,
        "mean_cost_opt": mean_cost_opt,
        "subsidy_base": subsidy_base,
        "subsidy_opt": subsidy_opt,
        "process": process,
        "regen": regen,
        "market_type": market_type,
        "subsidy_alpha": subsidy_alpha,
        "fig_hist": fig if return_figures else None,
        "fig_relationship": fig_relationship if return_figures else None,
    }


def _build_parser():
    parser = argparse.ArgumentParser(description="Python port of the MATLAB EV battery simulation.")
    parser.add_argument("--n-sims", type=int, default=5000, help="Number of Monte Carlo simulations.")
    parser.add_argument(
        "--excel",
        default="EverBatt.xlsm",
        help="EverBatt workbook placed in the project root or data folder.",
    )
    parser.add_argument(
        "--b2u-excel",
        default="nrel-b2u-repurposing-cost-calculator-jun2020.xlsm",
        help="B2U workbook placed in the project root or data folder.",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Save figures as PNG files instead of opening plot windows.",
    )
    parser.add_argument(
        "--subsidy-opt",
        type=float,
        default=0.5,
        help="Subsidy value for the optimized scenario.",
    )
    parser.add_argument(
        "--market-type",
        default="Moderate Market",
        choices=list(MARKET_TYPE_TO_ALPHA.keys()),
        help="Market response scenario controlling subsidy_alpha.",
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
    return parser


def main():
    parser = _build_parser()
    args = parser.parse_args()
    run_simulation(
        n_sims=args.n_sims,
        excel_filename=args.excel,
        b2u_excel_filename=args.b2u_excel,
        show_plots=not args.no_show,
        subsidy_opt=args.subsidy_opt,
        market_type=args.market_type,
        process=args.process,
        regen=args.regen,
    )
