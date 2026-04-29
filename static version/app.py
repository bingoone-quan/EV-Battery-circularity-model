from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from battery_model.excel_automation import (
    BATTERY_CHEMISTRY_OPTIONS,
    LOCATION_OPTIONS,
    RESET_RECYCLE_MACRO,
    VEHICLE_SEGMENT_OPTIONS,
    VEHICLE_SEGMENT_TO_PACK_KWH,
    prepared_runtime_workbooks,
    read_gui_defaults,
)
from battery_model.simulation import MARKET_TYPE_TO_ALPHA, run_simulation

MODEL_SUPPORTED_CHEMISTRIES = {"NMC(811)", "NMC(111)", "NMC(532)", "NMC(622)", "NCA"}


def _safe_index(options: list[str], value: str, fallback: int = 0) -> int:
    """Return the matching option index if present, otherwise use the fallback."""
    try:
        return options.index(value)
    except ValueError:
        return fallback


def _format_signed_change(new_value: float, base_value: float, unit: str = "") -> str:
    """Format absolute and relative change for compact scenario comparison text."""
    delta = new_value - base_value
    if base_value == 0:
        relative_text = "n/a"
    else:
        relative_text = f"{(delta / base_value) * 100:+.1f}%"

    unit_suffix = f" {unit}" if unit else ""
    return f"{delta:+.2f}{unit_suffix} ({relative_text})"


def _build_summary_markdown(results: dict) -> str:
    """Build a compact Baseline vs Optimized comparison table for the GUI."""
    rows = [
        (
            "Avg Cycles (N)",
            f"{results['mean_N_base']:.2f}",
            f"{results['mean_N_opt']:.2f}",
            _format_signed_change(results["mean_N_opt"], results["mean_N_base"]),
        ),
        (
            "GHG Intensity (kg/cycle)",
            f"{results['mean_ghg_base']:.2f}",
            f"{results['mean_ghg_opt']:.2f}",
            _format_signed_change(results["mean_ghg_opt"], results["mean_ghg_base"], "kg/cycle"),
        ),
        (
            "Cost Intensity ($/cycle)",
            f"{results['mean_cost_base']:.2f}",
            f"{results['mean_cost_opt']:.2f}",
            _format_signed_change(results["mean_cost_opt"], results["mean_cost_base"], "$/cycle"),
        ),
    ]

    lines = [
        "| Metric | Baseline | Optimized | Change |",
        "| --- | ---: | ---: | ---: |",
    ]
    for metric, baseline, optimized, change in rows:
        lines.append(f"| {metric} | {baseline} | {optimized} | {change} |")
    return "\n".join(lines)


@st.cache_data(show_spinner=False)
def load_default_inputs() -> dict:
    """Cache the initial EverBatt values shown when the app opens."""
    return read_gui_defaults("EverBatt.xlsm")


def main():
    st.set_page_config(
        page_title="EV Battery Circularity Simulation",
        layout="wide",
    )

    defaults = load_default_inputs()

    st.title("EV Battery Circularity Simulation")
    st.caption("EverBatt-driven Markov model for lifecycle, GHG, and cost analysis")

    with st.sidebar:
        st.header("EverBatt Inputs")
        battery_chemistry = st.selectbox(
            "Battery chemistry",
            BATTERY_CHEMISTRY_OPTIONS,
            index=_safe_index(
                BATTERY_CHEMISTRY_OPTIONS,
                defaults["battery_chemistry"],
                fallback=0,
            ),
        )
        location = st.selectbox(
            "Location",
            LOCATION_OPTIONS,
            index=_safe_index(LOCATION_OPTIONS, defaults["location"], fallback=0),
        )
        feedstock_tonnes = st.number_input(
            "Feedstock tonnes (tonnes/year)",
            min_value=0.0,
            value=float(defaults["feedstock_tonnes"]),
            step=1000.0,
            format="%.2f",
        )
        throughput = st.number_input(
            "Throughput (GWh/year)",
            min_value=0.0,
            value=float(defaults["throughput"]),
            step=1.0,
            format="%.2f",
        )

        st.header("Battery Size")
        vehicle_segment = st.selectbox(
            "Vehicle segment",
            VEHICLE_SEGMENT_OPTIONS,
            index=_safe_index(
                VEHICLE_SEGMENT_OPTIONS,
                defaults["vehicle_segment"],
                fallback=2,
            ),
        )
        if vehicle_segment == "Custom":
            cell_energy_kwh = st.number_input(
                "Cell energy (kWh)",
                min_value=0.001,
                value=float(defaults["cell_energy_kwh"]),
                step=0.01,
                format="%.4f",
            )
            cell_mass_kg = st.number_input(
                "Cell mass (kg)",
                min_value=0.001,
                value=float(defaults["cell_mass_kg"]),
                step=0.01,
                format="%.4f",
            )
            module_capacity_ah = st.number_input(
                "Module capacity (Ah)",
                min_value=0.1,
                value=float(defaults["module_capacity_ah"]),
                step=1.0,
                format="%.2f",
            )
            st.caption(
                "Custom mode writes the confirmed EverBatt user-defined cells and keeps the other workbook parameters at their defaults."
            )
            target_pack_kwh = None
        else:
            target_pack_kwh = float(VEHICLE_SEGMENT_TO_PACK_KWH[vehicle_segment])
            cell_energy_kwh = None
            cell_mass_kg = None
            module_capacity_ah = None
            st.caption(
                f"Preset target pack capacity: {target_pack_kwh:.0f} kWh. "
                "Cell energy, cell mass, and module capacity are auto-scaled from the current chemistry defaults."
            )

        st.header("Model Settings")
        subsidy_opt = st.slider(
            "Government subsidy strength",
            min_value=0.0,
            max_value=1.0,
            value=0.50,
            step=0.01,
        )
        market_type = st.selectbox(
            "Market response",
            list(MARKET_TYPE_TO_ALPHA.keys()),
            index=1,
        )
        process = st.selectbox("Process", ["Pyro", "Hydro", "Direct"], index=2)
        regen = st.selectbox("Regen", ["Pyro", "Hydro", "Direct"], index=2)

        st.divider()
        st.caption("Baseline subsidy is fixed at 0.23")
        run_clicked = st.button("Run Simulation", type="primary", use_container_width=True)

    info_col1, info_col2 = st.columns([1.4, 1])
    with info_col1:
        st.subheader("Run Setup")
        st.markdown(
            f"""
            **Battery chemistry:** `{battery_chemistry}`  
            **Location:** `{location}`  
            **Feedstock tonnes:** `{feedstock_tonnes:.2f} tonnes/year`  
            **Throughput:** `{throughput:.2f} GWh/year`  
            **Vehicle segment:** `{vehicle_segment}`  
            **Market response:** `{market_type}` (`alpha = {MARKET_TYPE_TO_ALPHA[market_type]:.1f}`)  
            **Macro refresh:** `{RESET_RECYCLE_MACRO}`  
            """
        )
        if vehicle_segment == "Custom":
            st.markdown(
                f"""
                **Custom cell energy:** `{cell_energy_kwh:.4f} kWh`  
                **Custom cell mass:** `{cell_mass_kg:.4f} kg`  
                **Custom module capacity:** `{module_capacity_ah:.2f} Ah`  
                """
            )
        else:
            st.markdown(f"**Preset target pack capacity:** `{target_pack_kwh:.2f} kWh`")
    with info_col2:
        st.subheader("Scenario Notes")
        st.write(
            "The app writes the selected inputs into temporary EverBatt and B2U workbooks, "
            "synchronizes the battery size assumptions across both files, and then runs "
            "the Python Monte Carlo model. Baseline vs Optimized changes policy subsidy, "
            "while market response controls the shared subsidy sensitivity for both scenarios."
        )

    if battery_chemistry not in MODEL_SUPPORTED_CHEMISTRIES:
        st.warning(
            "The current GUI and Python model support `NMC(811)`, `NMC(111)`, "
            "`NMC(532)`, `NMC(622)`, and `NCA`."
        )
        return

    if not run_clicked:
        st.info("Choose the inputs in the sidebar and click `Run Simulation` to generate results.")
        return

    runtime_battery_profile = None
    try:
        with st.spinner("Running EverBatt and the Python simulation..."):
            with prepared_runtime_workbooks(
                source_excel_filename="EverBatt.xlsm",
                source_b2u_excel_filename="nrel-b2u-repurposing-cost-calculator-jun2020.xlsm",
                battery_chemistry=battery_chemistry,
                location=location,
                feedstock_tonnes=feedstock_tonnes,
                throughput=throughput,
                target_pack_kwh=target_pack_kwh,
                module_capacity_ah=module_capacity_ah,
                cell_energy_kwh=cell_energy_kwh,
                cell_mass_kg=cell_mass_kg,
            ) as runtime_bundle:
                runtime_battery_profile = runtime_bundle["battery_profile"]
                results = run_simulation(
                    excel_filename=str(runtime_bundle["everbatt_path"]),
                    b2u_excel_filename=str(runtime_bundle["b2u_path"]),
                    show_plots=False,
                    subsidy_opt=subsidy_opt,
                    market_type=market_type,
                    process=process,
                    regen=regen,
                    return_figures=True,
                )
    except Exception as exc:
        st.error(f"Simulation failed: {exc}")
        return

    st.success("Simulation completed successfully.")

    summary_cols = st.columns(5)
    summary_cols[0].metric("Battery Type", results["battery_type"])
    summary_cols[1].metric("Baseline Subsidy", f"{results['subsidy_base']:.2f}")
    summary_cols[2].metric("Optimized Subsidy", f"{results['subsidy_opt']:.2f}")
    summary_cols[3].metric("Pack Capacity", f"{runtime_battery_profile['pack_capacity_kwh']:.1f} kWh")
    summary_cols[4].metric("Pack Mass", f"{runtime_battery_profile['pack_mass_kg']:.1f} kg")
    st.caption(
        f"Market response: {results['market_type']} (subsidy_alpha = {results['subsidy_alpha']:.1f}) | "
        f"Vehicle segment: {vehicle_segment} | Modules per pack: {runtime_battery_profile['modules_per_pack']}"
    )

    st.subheader("Scenario Comparison")
    st.markdown(_build_summary_markdown(results))

    with st.expander("Simulation Context", expanded=True):
        st.write(results["context_info"])
        st.write(f"Technology used: {results['tech_info']}")
        st.write(f"Economics info: {results['cost_info']}")
        st.write(
            f"Battery size info: pack capacity = {runtime_battery_profile['pack_capacity_kwh']:.2f} kWh, "
            f"pack mass = {runtime_battery_profile['pack_mass_kg']:.2f} kg, "
            f"module energy = {runtime_battery_profile['module_energy_kwh']:.2f} kWh, "
            f"cell energy = {runtime_battery_profile['cell_energy_kwh']:.4f} kWh, "
            f"cell mass = {runtime_battery_profile['cell_mass_kg']:.4f} kg, "
            f"module capacity = {runtime_battery_profile['module_capacity_ah']:.2f} Ah, "
            f"modules per pack = {runtime_battery_profile['modules_per_pack']}"
        )
        st.write(
            f"Scenario setup: baseline subsidy = {results['subsidy_base']:.2f}, "
            f"optimized subsidy = {results['subsidy_opt']:.2f}, "
            f"market response = {results['market_type']} (alpha = {results['subsidy_alpha']:.1f}), "
            f"process = {results['process']}, regen = {results['regen']}"
        )

    st.subheader("Distribution Comparison")
    st.pyplot(results["fig_hist"], use_container_width=True)
    plt.close(results["fig_hist"])

    st.subheader("Lifecycle Relationships")
    st.pyplot(results["fig_relationship"], use_container_width=True)
    plt.close(results["fig_relationship"])


if __name__ == "__main__":
    main()
