from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from battery_model.dynamic_simulation import MARKET_TYPE_TO_ALPHA, run_dynamic_simulation
from battery_model.excel_automation import (
    BATTERY_CHEMISTRY_OPTIONS,
    B2U_COLLECTION_DISTANCE_MILES,
    B2U_COLLECTION_SCALE_OPTIONS,
    EVERBATT_TRANSPORT_DISTANCE_INPUTS,
    EVERBATT_TRANSPORT_MODE_OPTIONS,
    LOCATION_OPTIONS,
    RESET_RECYCLE_MACRO,
    VEHICLE_SEGMENT_OPTIONS,
    VEHICLE_SEGMENT_TO_PACK_KWH,
    prepared_runtime_workbooks,
    read_gui_defaults,
)

MODEL_SUPPORTED_CHEMISTRIES = {"NMC(811)", "NMC(111)", "NMC(532)", "NMC(622)", "NCA"}

HELP_TEXT = {
    "battery_chemistry": (
        "Battery chemistry used by EverBatt and by the dynamic model's chemistry-specific "
        "lifetime, cascade, and recovery assumptions."
    ),
    "location": "Manufacturing and recycling location used by EverBatt for cost and GHG factors.",
    "feedstock": "Annual battery feedstock entering the recycling system in the EverBatt workbook.",
    "throughput": "Annual battery manufacturing throughput used by the EverBatt workbook.",
    "vehicle_segment": (
        "Representative battery-size scenario. Presets adjust the confirmed EverBatt user-defined "
        "battery-size cells; Custom lets users enter those values directly."
    ),
    "cell_energy": "Energy stored by one cell. This mainly determines pack capacity under the fixed workbook structure.",
    "cell_mass": "Mass of one cell. This mainly affects pack mass and energy density.",
    "module_capacity": "User-defined module capacity in Ah, synchronized with EverBatt's module-capacity input.",
    "everbatt_transport": (
        "Controls EverBatt recycling-loop transportation. Defaults use the workbook values; "
        "custom distances write the user-defined distance cells."
    ),
    "b2u_collection_scale": (
        "B2U second-life collection scale. This controls the B2U workbook's local, regional, "
        "or national repurposing logistics assumption."
    ),
    "years": "How many years the dynamic model propagates the battery system forward.",
    "n_sims": (
        "Number of Monte Carlo repetitions. Higher values make means and uncertainty bands more stable, "
        "but the run takes longer."
    ),
    "subsidy_opt": (
        "Final policy-strength level in the policy-enhanced scenario. It affects EV battery collection rate through "
        "the policy-response function."
    ),
    "policy_ramp": (
        "Number of years needed for the policy-enhanced pathway to rise from the baseline value to the target value. "
        "A larger value means slower policy implementation."
    ),
    "market_type": (
        "Controls how strongly collection responds to the same policy-strength level. Sensitive markets react more; "
        "sluggish markets react less."
    ),
    "process": "Recycling process pathway read from EverBatt. It changes process-related GHG and cost.",
    "regen": "Cathode regeneration pathway read from EverBatt. It changes regeneration-related GHG and cost.",
    "ev_shape": (
        "Shape of the EV-use retirement curve. Higher values make retirements more concentrated later in life; "
        "lower values make retirements earlier and more spread out."
    ),
    "cascade_shape": (
        "Shape of the second-life retirement curve. Higher values make cascade retirements more concentrated later; "
        "lower values make them earlier and more dispersed."
    ),
    "cascade_factor": (
        "Relative second-life duration factor. A higher value means batteries remain in cascade use longer "
        "after leaving EV use."
    ),
    "recovery_decay": (
        "Controls whether effective recovery efficiency declines as cumulative recycled material increases. "
        "Set to 0 for no decay."
    ),
}

PARAMETER_GUIDE_MARKDOWN = """
| Parameter | Plain-language meaning | Higher value means |
| --- | --- | --- |
| `Simulation horizon` | How long the system is simulated | Longer-term cumulative effects are included |
| `Monte Carlo runs` | Number of repeated random simulations | More stable results, slower runtime |
| `Policy-enhanced target` | Final policy strength in the intervention case | Higher collection pressure |
| `Policy ramp years` | Speed of policy implementation | Slower arrival at the final policy-strength target |
| `Market response` | Sensitivity of collection to policy strength | Stronger market response increases collection faster |
| `EV-use Weibull shape` | Shape of EV battery retirement over time | Retirements become more concentrated later in life |
| `Cascade-use Weibull shape` | Shape of second-life retirement over time | Cascade retirements become more concentrated later |
| `Cascade lifetime factor` | Relative duration of second-life use | Second-life batteries stay in use longer |
| `Recovery efficiency decay` | Decline in effective recovery with repeated looping | Recovery efficiency falls more strongly over time |
"""


def _safe_index(options: list[str], value: str, fallback: int = 0) -> int:
    """Return the matching option index if present, otherwise use the fallback."""
    try:
        return options.index(value)
    except ValueError:
        return fallback


def _format_delta(new_value: float, base_value: float, unit: str = "") -> str:
    """Format absolute and relative scenario changes."""
    delta = new_value - base_value
    if abs(base_value) < 1e-12:
        relative_text = "n/a"
    else:
        relative_text = f"{(delta / base_value) * 100:+.1f}%"
    suffix = f" {unit}" if unit else ""
    return f"{delta:+.3f}{suffix} ({relative_text})"


def _build_summary_markdown(results: dict) -> str:
    """Build a compact comparison table for the dynamic results."""
    baseline = results["baseline"]["summary"]
    optimized = results["optimized"]["summary"]
    rows = [
        (
            "Equivalent service loops",
            baseline["equivalent_service_loops"]["mean"],
            optimized["equivalent_service_loops"]["mean"],
            "",
        ),
        (
            "Final in-use stock (kg/kg)",
            baseline["final_in_use_stock"]["mean"],
            optimized["final_in_use_stock"]["mean"],
            "kg/kg",
        ),
        (
            "Cumulative recovered (kg/kg)",
            baseline["cumulative_recovered"]["mean"],
            optimized["cumulative_recovered"]["mean"],
            "kg/kg",
        ),
        (
            "Cumulative landfill (kg/kg)",
            baseline["cumulative_landfill"]["mean"],
            optimized["cumulative_landfill"]["mean"],
            "kg/kg",
        ),
        (
            "Cumulative GHG (kg CO2e/kg)",
            baseline["cumulative_ghg"]["mean"],
            optimized["cumulative_ghg"]["mean"],
            "kg CO2e/kg",
        ),
        (
            "Cumulative cost (USD/kg)",
            baseline["cumulative_cost"]["mean"],
            optimized["cumulative_cost"]["mean"],
            "USD/kg",
        ),
        (
            "Depletion year",
            baseline["depletion_year"]["mean"],
            optimized["depletion_year"]["mean"],
            "years",
        ),
    ]

    lines = [
        "| Metric | Baseline | Policy-enhanced | Change |",
        "| --- | ---: | ---: | ---: |",
    ]
    for metric, base_value, opt_value, unit in rows:
        lines.append(
            f"| {metric} | {base_value:.3f} | {opt_value:.3f} | "
            f"{_format_delta(opt_value, base_value, unit)} |"
        )
    return "\n".join(lines)


@st.cache_data(show_spinner=False)
def load_default_inputs() -> dict:
    """Cache the initial EverBatt values shown when the app opens."""
    return read_gui_defaults("EverBatt.xlsm")


def main():
    st.set_page_config(
        page_title="Dynamic EV Battery Circularity Simulation",
        layout="wide",
    )

    defaults = load_default_inputs()

    st.title("Dynamic EV Battery Circularity Simulation")
    st.caption("Time-evolving extension of the EverBatt-driven Yamada Markov model")

    with st.sidebar:
        st.header("EverBatt Inputs")
        battery_chemistry = st.selectbox(
            "Battery chemistry",
            BATTERY_CHEMISTRY_OPTIONS,
            index=_safe_index(BATTERY_CHEMISTRY_OPTIONS, defaults["battery_chemistry"], fallback=0),
            help=HELP_TEXT["battery_chemistry"],
        )
        location = st.selectbox(
            "Location",
            LOCATION_OPTIONS,
            index=_safe_index(LOCATION_OPTIONS, defaults["location"], fallback=0),
            help=HELP_TEXT["location"],
        )
        feedstock_tonnes = st.number_input(
            "Feedstock tonnes (tonnes/year)",
            min_value=0.0,
            value=float(defaults["feedstock_tonnes"]),
            step=1000.0,
            format="%.2f",
            help=HELP_TEXT["feedstock"],
        )
        throughput = st.number_input(
            "Throughput (GWh/year)",
            min_value=0.0,
            value=float(defaults["throughput"]),
            step=1.0,
            format="%.2f",
            help=HELP_TEXT["throughput"],
        )

        st.header("Battery Size")
        vehicle_segment = st.selectbox(
            "Vehicle segment",
            VEHICLE_SEGMENT_OPTIONS,
            index=_safe_index(VEHICLE_SEGMENT_OPTIONS, defaults["vehicle_segment"], fallback=2),
            help=HELP_TEXT["vehicle_segment"],
        )
        if vehicle_segment == "Custom":
            cell_energy_kwh = st.number_input(
                "Cell energy (kWh)",
                min_value=0.001,
                value=float(defaults["cell_energy_kwh"]),
                step=0.01,
                format="%.4f",
                help=HELP_TEXT["cell_energy"],
            )
            cell_mass_kg = st.number_input(
                "Cell mass (kg)",
                min_value=0.001,
                value=float(defaults["cell_mass_kg"]),
                step=0.01,
                format="%.4f",
                help=HELP_TEXT["cell_mass"],
            )
            module_capacity_ah = st.number_input(
                "Module capacity (Ah)",
                min_value=0.1,
                value=float(defaults["module_capacity_ah"]),
                step=1.0,
                format="%.2f",
                help=HELP_TEXT["module_capacity"],
            )
            target_pack_kwh = None
        else:
            target_pack_kwh = float(VEHICLE_SEGMENT_TO_PACK_KWH[vehicle_segment])
            cell_energy_kwh = None
            cell_mass_kg = None
            module_capacity_ah = None

        st.header("Transport")
        everbatt_transport_mode = st.selectbox(
            "EverBatt recycling transport",
            EVERBATT_TRANSPORT_MODE_OPTIONS,
            index=0,
            help=HELP_TEXT["everbatt_transport"],
        )
        if everbatt_transport_mode == "Custom distances":
            everbatt_transport_distances = {}
            with st.expander("EverBatt custom distances", expanded=True):
                for label, _, _ in EVERBATT_TRANSPORT_DISTANCE_INPUTS:
                    everbatt_transport_distances[label] = st.number_input(
                        f"{label} (miles)",
                        min_value=0.0,
                        value=float(defaults["everbatt_transport_distances"][label]),
                        step=50.0,
                        format="%.2f",
                    )
        else:
            everbatt_transport_distances = None
            st.caption("EverBatt uses its workbook default recycling-loop distances.")

        b2u_collection_scale = st.selectbox(
            "B2U second-life collection scale",
            B2U_COLLECTION_SCALE_OPTIONS,
            index=_safe_index(
                B2U_COLLECTION_SCALE_OPTIONS,
                defaults["b2u_collection_scale"],
                fallback=2,
            ),
            help=HELP_TEXT["b2u_collection_scale"],
        )
        st.caption(
            f"B2U typical round-trip collection distance: "
            f"{B2U_COLLECTION_DISTANCE_MILES[b2u_collection_scale]:,} miles."
        )

        st.header("Dynamic Settings")
        years = st.slider(
            "Simulation horizon (years)",
            min_value=5,
            max_value=35,
            value=20,
            step=1,
            help=HELP_TEXT["years"],
        )
        n_sims = st.slider(
            "Monte Carlo runs",
            min_value=50,
            max_value=1000,
            value=300,
            step=50,
            help=HELP_TEXT["n_sims"],
        )
        subsidy_opt = st.slider(
            "Policy-enhanced target",
            min_value=0.0,
            max_value=1.0,
            value=0.50,
            step=0.01,
            help=HELP_TEXT["subsidy_opt"],
        )
        policy_ramp_years = st.slider(
            "Policy ramp years",
            min_value=1,
            max_value=15,
            value=5,
            step=1,
            help=HELP_TEXT["policy_ramp"],
        )
        market_type = st.selectbox(
            "Market response",
            list(MARKET_TYPE_TO_ALPHA.keys()),
            index=1,
            help=HELP_TEXT["market_type"],
        )
        process = st.selectbox("Process", ["Pyro", "Hydro", "Direct"], index=2, help=HELP_TEXT["process"])
        regen = st.selectbox("Regen", ["Pyro", "Hydro", "Direct"], index=2, help=HELP_TEXT["regen"])
        ev_shape = st.slider(
            "EV-use Weibull shape",
            min_value=1.2,
            max_value=5.0,
            value=3.0,
            step=0.1,
            help=HELP_TEXT["ev_shape"],
        )
        cascade_shape = st.slider(
            "Cascade-use Weibull shape",
            min_value=1.1,
            max_value=5.0,
            value=2.0,
            step=0.1,
            help=HELP_TEXT["cascade_shape"],
        )
        cascade_factor = st.slider(
            "Cascade lifetime factor",
            min_value=0.30,
            max_value=1.00,
            value=0.65,
            step=0.05,
            help=HELP_TEXT["cascade_factor"],
        )
        recovery_decay = st.slider(
            "Recovery efficiency decay",
            min_value=0.00,
            max_value=0.30,
            value=0.08,
            step=0.01,
            help=HELP_TEXT["recovery_decay"],
        )

        with st.expander("Parameter guide", expanded=False):
            st.markdown(PARAMETER_GUIDE_MARKDOWN)

        st.divider()
        st.caption("Baseline policy strength stays fixed at 0.23 throughout the horizon.")
        run_clicked = st.button("Run Dynamic Simulation", type="primary", use_container_width=True)

    info_col1, info_col2 = st.columns([1.4, 1])
    with info_col1:
        st.subheader("Run Setup")
        st.markdown(
            f"""
            **Battery chemistry:** `{battery_chemistry}`  
            **Location:** `{location}`  
            **Feedstock tonnes:** `{feedstock_tonnes:.2f} tonnes/year`  
            **Throughput:** `{throughput:.2f} GWh/year`  
            **Vehicle segment:** `{vehicle_segment}`<br>
            **EverBatt transport:** `{everbatt_transport_mode}`<br>
            **B2U collection scale:** `{b2u_collection_scale}`<br>
            **Simulation horizon:** `{years}` years  
            **Monte Carlo runs:** `{n_sims}`  
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
        st.subheader("Dynamic Extension Notes")
        st.write(
            "This version keeps the Yamada circular structure but updates the system year by year. "
            "EV-use and cascade-use stocks are represented as age cohorts, and the policy-enhanced scenario "
            "ramps policy over time instead of switching to a single static matrix."
        )
        st.write(
            "EverBatt recycling transport distances and B2U second-life collection scale are "
            "kept as separate model-native inputs."
        )

    if battery_chemistry not in MODEL_SUPPORTED_CHEMISTRIES:
        st.warning(
            "The current GUI and Python model support `NMC(811)`, `NMC(111)`, "
            "`NMC(532)`, `NMC(622)`, and `NCA`."
        )
        return

    if not run_clicked:
        st.info("Choose the inputs in the sidebar and click `Run Dynamic Simulation` to generate results.")
        return

    runtime_battery_profile = None
    try:
        with st.spinner("Preparing Excel workbooks and running the dynamic simulation..."):
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
                everbatt_transport_distances=everbatt_transport_distances,
                b2u_collection_scale=b2u_collection_scale,
            ) as runtime_bundle:
                runtime_battery_profile = runtime_bundle["battery_profile"]
                results = run_dynamic_simulation(
                    n_sims=n_sims,
                    years=years,
                    excel_filename=runtime_bundle["everbatt_workbook"],
                    b2u_excel_filename=runtime_bundle["b2u_workbook"],
                    show_plots=False,
                    return_figures=True,
                    subsidy_opt=subsidy_opt,
                    policy_ramp_years=policy_ramp_years,
                    market_type=market_type,
                    process=process,
                    regen=regen,
                    ev_weibull_shape=ev_shape,
                    cascade_weibull_shape=cascade_shape,
                    cascade_lifetime_factor=cascade_factor,
                    recycle_efficiency_decay=recovery_decay,
                )
    except Exception as exc:
        st.error(f"Dynamic simulation failed: {exc}")
        return

    st.success("Dynamic simulation completed successfully.")

    baseline = results["baseline"]["summary"]
    optimized = results["optimized"]["summary"]

    summary_cols = st.columns(5)
    summary_cols[0].metric("Battery Type", results["battery_type"])
    summary_cols[1].metric("Pack Capacity", f"{runtime_battery_profile['pack_capacity_kwh']:.1f} kWh")
    summary_cols[2].metric("Pack Mass", f"{runtime_battery_profile['pack_mass_kg']:.1f} kg")
    summary_cols[3].metric(
        "Eq. Service Loops",
        f"{optimized['equivalent_service_loops']['mean']:.2f}",
        delta=f"{optimized['equivalent_service_loops']['mean'] - baseline['equivalent_service_loops']['mean']:+.2f}",
    )
    summary_cols[4].metric(
        "Final In-Use Stock",
        f"{optimized['final_in_use_stock']['mean']:.3f}",
        delta=f"{optimized['final_in_use_stock']['mean'] - baseline['final_in_use_stock']['mean']:+.3f}",
    )
    st.caption(
        f"Policy ramp: {policy_ramp_years} years | Market response: {results['market_type']} "
        f"(alpha = {results['subsidy_alpha']:.1f}) | Vehicle segment: {vehicle_segment}"
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
            f"module capacity = {runtime_battery_profile['module_capacity_ah']:.2f} Ah."
        )
        st.write(
            f"Dynamic settings: horizon = {years} years, EV Weibull shape = {ev_shape:.1f}, "
            f"cascade Weibull shape = {cascade_shape:.1f}, cascade lifetime factor = {cascade_factor:.2f}, "
            f"recovery efficiency decay = {recovery_decay:.2f}, "
            f"EverBatt transport = {everbatt_transport_mode}, "
            f"B2U collection scale = {b2u_collection_scale}."
        )

    st.subheader("Dynamic Stock Evolution")
    st.pyplot(results["fig_stock"], use_container_width=True)
    plt.close(results["fig_stock"])

    st.subheader("Cumulative Environmental and Economic Effects")
    st.pyplot(results["fig_impacts"], use_container_width=True)
    plt.close(results["fig_impacts"])

    st.subheader("Time-Varying Transition Drivers")
    st.pyplot(results["fig_transitions"], use_container_width=True)
    plt.close(results["fig_transitions"])


if __name__ == "__main__":
    main()
