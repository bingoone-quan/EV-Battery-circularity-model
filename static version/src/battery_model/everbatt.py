"""EverBatt-related Excel readers for context, emissions, and cost factors."""

from __future__ import annotations

from battery_model.config import ContextParams, CostVectors, GHGVectors, TechConfig
from battery_model.excel_reader import read_excel_scalar


def Get_EverBatt_Context(excel_filename: str):
    """Read the macro background parameters from EverBatt."""
    try:
        country = read_excel_scalar(excel_filename, "Input", "E10:E10")
        feedstock_tonnes = float(read_excel_scalar(excel_filename, "Input", "F28:F28"))
        throughput_gwh = float(read_excel_scalar(excel_filename, "Input", "E8:E8"))

        context_params = ContextParams(
            Country=str(country),
            Feedstock_tonnes=feedstock_tonnes,
            Throughput_GWh=throughput_gwh,
        )
        context_info = (
            f"Location: {context_params.Country} | "
            f"Feedstock: {context_params.Feedstock_tonnes:.0f} tonnes/yr |"
            f"GWhs of battery manufactured: {context_params.Throughput_GWh:.2f} GWh/yr"
        )

    except Exception as exc:
        print(f"Warning: Failed to read context parameters: {exc}")
        context_params = None
        context_info = "Context Load Failed."

    return context_params, context_info


def Get_EverBatt_GHG(excel_filename: str, battery_type: str, tech_selection: TechConfig):
    """Read and calculate the GHG factors from EverBatt."""
    ghg_vectors = GHGVectors()

    try:
        pack_kwh = float(read_excel_scalar(excel_filename, "Man Par.", "AH88:AH88"))
        pack_weight = float(read_excel_scalar(excel_filename, "Man Par.", "AE88:AE88"))
        cathode_ratio = float(read_excel_scalar(excel_filename, "Man Par.", "O20:O20"))
        if cathode_ratio > 1:
            cathode_ratio = cathode_ratio / 100.0
    except Exception as exc:
        raise RuntimeError(
            "Failed to read base parameters from [Man Par.], please check AH88, AE88, O20"
        ) from exc

    try:
        raw_mfg_g_kwh = float(read_excel_scalar(excel_filename, "Output", "H32:H32"))
        ghg_vectors.E_mfg = (raw_mfg_g_kwh * pack_kwh / pack_weight) / 1000.0
    except Exception:
        ghg_vectors.E_mfg = 0.0
        print("Warning: Failed to read E_mfg (H32)")

    try:
        raw_trans_g_kg = float(read_excel_scalar(excel_filename, "Output", "C58:C58"))
        ghg_vectors.E_trans = raw_trans_g_kg / 1000.0
    except Exception:
        ghg_vectors.E_trans = 0.0
        print("Warning: Failed to read E_trans (C58)")

    process_cells = {"Pyro": "J58", "Hydro": "K58", "Direct": "L58"}
    regen_cells = {"Pyro": "P58", "Hydro": "Q58", "Direct": "T58"}

    if tech_selection.process not in process_cells:
        raise ValueError(f"Unknown process technology: {tech_selection.process}")
    if tech_selection.regen not in regen_cells:
        raise ValueError(f"Unknown regeneration technology: {tech_selection.regen}")

    raw_proc_g_kg = float(
        read_excel_scalar(
            excel_filename,
            "Output",
            f"{process_cells[tech_selection.process]}:{process_cells[tech_selection.process]}",
        )
    )
    raw_regen_g_kg_cathode = float(
        read_excel_scalar(
            excel_filename,
            "Output",
            f"{regen_cells[tech_selection.regen]}:{regen_cells[tech_selection.regen]}",
        )
    )

    ghg_vectors.E_loop = (raw_proc_g_kg + (raw_regen_g_kg_cathode * cathode_ratio)) / 1000.0

    selected_info = (
        f"Tech: {tech_selection.process} (Process) + "
        f"{tech_selection.regen} (Regen) | Battery: {battery_type}"
    )

    print("--- EverBatt GHG Loaded ---")
    print(f"  Info: {selected_info}")
    print(f"  E_mfg:   {ghg_vectors.E_mfg:.3f} kg/kg")
    print(f"  E_trans: {ghg_vectors.E_trans:.3f} kg/kg")
    print(f"  E_loop:  {ghg_vectors.E_loop:.3f} kg/kg")
    print("---------------------------")

    return ghg_vectors, selected_info


def Get_EverBatt_Cost(excel_filename: str, battery_type: str, tech_selection: TechConfig):
    """Read and calculate the total net cost across the loop from EverBatt."""
    del battery_type

    cost_vectors = CostVectors()

    try:
        pack_kwh = float(read_excel_scalar(excel_filename, "Man Par.", "AH88:AH88"))
        pack_weight = float(read_excel_scalar(excel_filename, "Man Par.", "AE88:AE88"))
        cathode_ratio = float(read_excel_scalar(excel_filename, "Man Par.", "O20:O20"))
        if cathode_ratio > 1:
            cathode_ratio = cathode_ratio / 100.0
    except Exception as exc:
        raise RuntimeError("Failed to read base parameters from [Man Par.]") from exc

    energy_density = pack_kwh / pack_weight

    try:
        raw_mfg_kwh = float(read_excel_scalar(excel_filename, "Output", "H11:H11"))
        cost_vectors.C_mfg = raw_mfg_kwh * energy_density
        cost_vectors.C_trans = float(read_excel_scalar(excel_filename, "Output", "C37:C37"))

        process_cells = {
            "Pyro": ("J37", "J59"),
            "Hydro": ("K37", "K59"),
            "Direct": ("L37", "L59"),
        }
        regen_cells = {"Pyro": "P37", "Hydro": "Q37", "Direct": "T37"}

        if tech_selection.process not in process_cells:
            raise ValueError(f"Unknown process technology: {tech_selection.process}")
        if tech_selection.regen not in regen_cells:
            raise ValueError(f"Unknown regeneration technology: {tech_selection.regen}")

        cell_proc, cell_rev = process_cells[tech_selection.process]
        c_process = float(read_excel_scalar(excel_filename, "Output", f"{cell_proc}:{cell_proc}"))
        revenue = float(read_excel_scalar(excel_filename, "Output", f"{cell_rev}:{cell_rev}"))

        cell_regen = regen_cells[tech_selection.regen]
        c_regen_cathode = float(
            read_excel_scalar(excel_filename, "Output", f"{cell_regen}:{cell_regen}")
        )

        c_regen_pack = c_regen_cathode * cathode_ratio
        cost_vectors.C_loop = c_process + c_regen_pack - revenue

    except Exception as exc:
        print(f"Warning: Failed to read cost data: {exc}")
        c_process = 0.0
        c_regen_pack = 0.0
        revenue = 0.0

    cost_info = (
        f"Net Loop Cost: {cost_vectors.C_loop:.2f} $/kg "
        f"(Process: {c_process:.2f}, Regen: {c_regen_pack:.2f}, Revenue: -{revenue:.2f})"
    )

    print("--- EverBatt Cost Loaded ---")
    print(f"  Mfg Cost:   $ {cost_vectors.C_mfg:.2f} / kg")
    print(f"  Trans Cost: $ {cost_vectors.C_trans:.2f} / kg")
    print(f"  Loop Net:   $ {cost_vectors.C_loop:.2f} / kg")
    print("---------------------------")

    return cost_vectors, cost_info
