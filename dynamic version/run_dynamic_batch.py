from __future__ import annotations

import argparse
import csv
import itertools
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from battery_model.dynamic_simulation import MARKET_TYPE_TO_ALPHA, run_dynamic_simulation
from battery_model.excel_automation import (
    BATTERY_CHEMISTRY_OPTIONS,
    VEHICLE_SEGMENT_TO_PACK_KWH,
    prepared_runtime_workbooks,
)
from battery_model.paths import OUTPUTS_DIR, ensure_project_dirs


def _parse_csv_list(raw_value: str) -> list[str]:
    """Parse a comma-separated argument into a clean list."""
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _build_parser():
    parser = argparse.ArgumentParser(description="Batch runner for the dynamic battery model.")
    parser.add_argument(
        "--chemistries",
        default=",".join(BATTERY_CHEMISTRY_OPTIONS),
        help="Comma-separated chemistry labels.",
    )
    parser.add_argument(
        "--segments",
        default="Sedan,Wagon,SUV",
        help="Comma-separated preset vehicle segments.",
    )
    parser.add_argument(
        "--markets",
        default="Moderate Market,Sensitive Market",
        help="Comma-separated market response scenarios.",
    )
    parser.add_argument(
        "--processes",
        default="Direct,Hydro,Pyro",
        help="Comma-separated recycling process pathways.",
    )
    parser.add_argument(
        "--regens",
        default="Direct,Hydro,Pyro",
        help="Comma-separated regeneration pathways.",
    )
    parser.add_argument("--years", type=int, default=20, help="Dynamic simulation horizon.")
    parser.add_argument("--n-sims", type=int, default=200, help="Monte Carlo runs per scenario.")
    parser.add_argument("--subsidy-opt", type=float, default=0.5, help="Optimized subsidy target.")
    parser.add_argument("--policy-ramp-years", type=int, default=5, help="Years to reach subsidy target.")
    parser.add_argument("--feedstock-tonnes", type=float, default=60000, help="EverBatt feedstock input.")
    parser.add_argument("--throughput", type=float, default=50.0, help="EverBatt throughput input.")
    parser.add_argument("--location", default="U.S.", help="EverBatt location input.")
    return parser


def main():
    parser = _build_parser()
    args = parser.parse_args()

    chemistries = _parse_csv_list(args.chemistries)
    segments = _parse_csv_list(args.segments)
    markets = _parse_csv_list(args.markets)
    processes = _parse_csv_list(args.processes)
    regens = _parse_csv_list(args.regens)

    ensure_project_dirs()
    OUTPUTS_DIR.mkdir(exist_ok=True)
    summary_path = OUTPUTS_DIR / "dynamic_batch_summary.csv"
    series_path = OUTPUTS_DIR / "dynamic_batch_series.csv"

    summary_rows = []
    series_rows = []
    scenario_id = 1

    for chemistry, segment, market, process, regen in itertools.product(
        chemistries,
        segments,
        markets,
        processes,
        regens,
    ):
        if segment not in VEHICLE_SEGMENT_TO_PACK_KWH:
            raise ValueError(f"Unknown preset vehicle segment: {segment}")

        target_pack_kwh = VEHICLE_SEGMENT_TO_PACK_KWH[segment]
        print(
            f"Running scenario {scenario_id}: "
            f"{chemistry} | {segment} | {market} | {process}/{regen}"
        )

        with prepared_runtime_workbooks(
            source_excel_filename="EverBatt.xlsm",
            source_b2u_excel_filename="nrel-b2u-repurposing-cost-calculator-jun2020.xlsm",
            battery_chemistry=chemistry,
            location=args.location,
            feedstock_tonnes=args.feedstock_tonnes,
            throughput=args.throughput,
            target_pack_kwh=target_pack_kwh,
        ) as runtime_bundle:
            results = run_dynamic_simulation(
                n_sims=args.n_sims,
                years=args.years,
                excel_filename=runtime_bundle["everbatt_workbook"],
                b2u_excel_filename=runtime_bundle["b2u_workbook"],
                show_plots=False,
                return_figures=False,
                build_figures=False,
                subsidy_opt=args.subsidy_opt,
                policy_ramp_years=args.policy_ramp_years,
                market_type=market,
                process=process,
                regen=regen,
            )

        battery_profile = runtime_bundle["battery_profile"]
        baseline = results["baseline"]["summary"]
        optimized = results["optimized"]["summary"]

        summary_rows.append(
            {
                "scenario_id": scenario_id,
                "battery_chemistry": chemistry,
                "vehicle_segment": segment,
                "target_pack_kwh": target_pack_kwh,
                "actual_pack_kwh": battery_profile["pack_capacity_kwh"],
                "actual_pack_mass_kg": battery_profile["pack_mass_kg"],
                "location": args.location,
                "market_type": market,
                "process": process,
                "regen": regen,
                "years": args.years,
                "n_sims": args.n_sims,
                "baseline_loops": baseline["equivalent_service_loops"]["mean"],
                "optimized_loops": optimized["equivalent_service_loops"]["mean"],
                "baseline_final_in_use": baseline["final_in_use_stock"]["mean"],
                "optimized_final_in_use": optimized["final_in_use_stock"]["mean"],
                "baseline_landfill": baseline["cumulative_landfill"]["mean"],
                "optimized_landfill": optimized["cumulative_landfill"]["mean"],
                "baseline_recovered": baseline["cumulative_recovered"]["mean"],
                "optimized_recovered": optimized["cumulative_recovered"]["mean"],
                "baseline_ghg": baseline["cumulative_ghg"]["mean"],
                "optimized_ghg": optimized["cumulative_ghg"]["mean"],
                "baseline_cost": baseline["cumulative_cost"]["mean"],
                "optimized_cost": optimized["cumulative_cost"]["mean"],
                "baseline_depletion_year": baseline["depletion_year"]["mean"],
                "optimized_depletion_year": optimized["depletion_year"]["mean"],
            }
        )

        for scenario_name in ["baseline", "optimized"]:
            series = results[scenario_name]["series"]
            for year_idx, year_value in enumerate(results["years_axis"]):
                series_rows.append(
                    {
                        "scenario_id": scenario_id,
                        "scenario_type": scenario_name,
                        "battery_chemistry": chemistry,
                        "vehicle_segment": segment,
                        "market_type": market,
                        "process": process,
                        "regen": regen,
                        "year": int(year_value),
                        "in_use_stock_mean": series["in_use_stock"]["mean"][year_idx],
                        "cascade_stock_mean": series["cascade_stock"]["mean"][year_idx],
                        "recovered_cumulative_mean": series["recovered_cumulative"]["mean"][year_idx],
                        "landfill_cumulative_mean": series["landfill_cumulative"]["mean"][year_idx],
                        "ghg_cumulative_mean": series["ghg_cumulative"]["mean"][year_idx],
                        "cost_cumulative_mean": series["cost_cumulative"]["mean"][year_idx],
                        "collection_rate_mean": series["collection_rate"]["mean"][year_idx],
                        "recovery_rate_mean": series["recovery_rate"]["mean"][year_idx],
                        "subsidy_mean": series["subsidy_path"]["mean"][year_idx],
                    }
                )

        scenario_id += 1

    if summary_rows:
        with summary_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0].keys()))
            writer.writeheader()
            writer.writerows(summary_rows)

    if series_rows:
        with series_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(series_rows[0].keys()))
            writer.writeheader()
            writer.writerows(series_rows)

    print(f"Summary written to {summary_path}")
    print(f"Dynamic series written to {series_path}")


if __name__ == "__main__":
    main()
