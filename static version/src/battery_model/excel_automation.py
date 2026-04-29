"""Excel automation helpers for GUI-driven EverBatt runs."""

from __future__ import annotations

import gc
import shutil
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from battery_model.excel_reader import read_excel_scalar
from battery_model.paths import resolve_input_file

try:
    import pythoncom
    import win32com.client
except Exception:  # pragma: no cover - optional dependency for GUI automation
    pythoncom = None
    win32com = None


BATTERY_CHEMISTRY_CELLS = [("Input", "E9"), ("Input", "C28"), ("Input", "E38")]
LOCATION_CELLS = [("Input", "E10"), ("Input", "E33"), ("Input", "E41"), ("Input", "E52")]
FEEDSTOCK_CELL = ("Input", "F28")
THROUGHPUT_CELL = ("Input", "G8")
RESET_RECYCLE_MACRO = "Reset_recycle"

BATTERY_CHEMISTRY_OPTIONS = [
    "NMC(811)",
    "NMC(111)",
    "NMC(532)",
    "NMC(622)",
    "NCA",
]

LOCATION_OPTIONS = ["U.S.", "China", "Korea", "California"]
VEHICLE_SEGMENT_TO_PACK_KWH = {
    "Sedan": 60.0,
    "Wagon": 80.0,
    "SUV": 100.0,
}
VEHICLE_SEGMENT_OPTIONS = [*VEHICLE_SEGMENT_TO_PACK_KWH.keys(), "Custom"]

EVERBATT_CELLS_PER_MODULE_CELL = ("Man Par.", "AC13")
EVERBATT_MODULES_PER_PACK_SELECTED_CELL = ("Man Par.", "AC14")
EVERBATT_MODULE_CAPACITY_SELECTED_CELL = ("Man Par.", "AG14")
EVERBATT_MODULE_CAPACITY_USER_CELL = ("Man Par.", "AI14")
EVERBATT_CELL_ENERGY_SELECTED_CELL = ("Man Par.", "C15")
EVERBATT_CELL_ENERGY_USER_CELL = ("Man Par.", "L15")
EVERBATT_CELL_MASS_SELECTED_CELL = ("Man Par.", "C16")
EVERBATT_CELL_MASS_USER_CELL = ("Man Par.", "L16")
EVERBATT_TOTAL_MODULE_MASS_CELL = ("Man Par.", "AD88")
EVERBATT_PACK_MASS_CELL = ("Man Par.", "AE88")
EVERBATT_PACK_CAPACITY_CELL = ("Man Par.", "AH88")

B2U_MODULE_ENERGY_CELL = ("Repurposing", "C2")
B2U_MODULE_SPECIFIC_ENERGY_CELL = ("Repurposing", "C4")
B2U_CELLS_PER_MODULE_CELL = ("Repurposing", "C13")


def _read_first_available_scalar(excel_filename: str, refs: list[tuple[str, str]]):
    """Return the first non-empty scalar found in the provided sheet/range references."""
    for sheet_name, cell_range in refs:
        value = read_excel_scalar(excel_filename, sheet_name, cell_range)
        if value is not None:
            return value
    return None


def _infer_vehicle_segment(pack_capacity_kwh: float) -> str:
    """Map the current pack capacity to the nearest preset vehicle segment."""
    if not VEHICLE_SEGMENT_TO_PACK_KWH:
        return "Custom"

    return min(
        VEHICLE_SEGMENT_TO_PACK_KWH,
        key=lambda label: abs(VEHICLE_SEGMENT_TO_PACK_KWH[label] - pack_capacity_kwh),
    )


def read_gui_defaults(excel_filename: str = "EverBatt.xlsm") -> dict:
    """Read the initial values shown in the GUI from the EverBatt input sheet."""
    throughput_value = _read_first_available_scalar(
        excel_filename,
        [("Input", "G8:G8"), ("Input", "E8:E8")],
    )
    pack_capacity_kwh = float(read_excel_scalar(excel_filename, "Man Par.", "AH88:AH88"))
    modules_per_pack = int(
        round(float(read_excel_scalar(excel_filename, "Man Par.", "AC14:AC14")))
    )
    cells_per_module = int(
        round(float(read_excel_scalar(excel_filename, "Man Par.", "AC13:AC13")))
    )
    module_capacity_ah = float(read_excel_scalar(excel_filename, "Man Par.", "AG14:AG14"))
    cell_energy_kwh = float(read_excel_scalar(excel_filename, "Man Par.", "C15:C15"))
    cell_mass_kg = float(read_excel_scalar(excel_filename, "Man Par.", "C16:C16"))

    return {
        "battery_chemistry": str(read_excel_scalar(excel_filename, "Input", "E9:E9")),
        "location": str(read_excel_scalar(excel_filename, "Input", "E10:E10")),
        "feedstock_tonnes": float(read_excel_scalar(excel_filename, "Input", "F28:F28")),
        "throughput": float(throughput_value) if throughput_value is not None else 50.0,
        "pack_capacity_kwh": pack_capacity_kwh,
        "modules_per_pack": modules_per_pack,
        "cells_per_module": cells_per_module,
        "module_capacity_ah": module_capacity_ah,
        "cell_energy_kwh": cell_energy_kwh,
        "cell_mass_kg": cell_mass_kg,
        "vehicle_segment": _infer_vehicle_segment(pack_capacity_kwh),
    }


def _require_excel_com() -> None:
    """Raise a clear error if Excel automation dependencies are not available."""
    if pythoncom is None or win32com is None:
        raise RuntimeError(
            "Excel automation requires pywin32. Install it before using the Streamlit GUI."
        )


def _write_input_block(worksheet, cell_refs, value) -> None:
    """Write one GUI input value to every mapped Excel cell."""
    for _, cell_ref in cell_refs:
        worksheet.Range(cell_ref).Value = value


def _apply_gui_inputs(
    workbook,
    battery_chemistry: str,
    location: str,
    feedstock_tonnes: float,
    throughput: float,
) -> None:
    """Write the GUI-controlled values into the workbook input sheet."""
    input_sheet = workbook.Worksheets("Input")
    _write_input_block(input_sheet, BATTERY_CHEMISTRY_CELLS, battery_chemistry)
    _write_input_block(input_sheet, LOCATION_CELLS, location)
    input_sheet.Range(FEEDSTOCK_CELL[1]).Value = feedstock_tonnes
    input_sheet.Range(THROUGHPUT_CELL[1]).Value = throughput


def _build_runtime_battery_profile(workbook) -> dict:
    """Read the current battery size values from the prepared EverBatt workbook."""
    man_par_sheet = workbook.Worksheets(EVERBATT_CELLS_PER_MODULE_CELL[0])

    cells_per_module = float(man_par_sheet.Range(EVERBATT_CELLS_PER_MODULE_CELL[1]).Value)
    modules_per_pack = int(
        round(float(man_par_sheet.Range(EVERBATT_MODULES_PER_PACK_SELECTED_CELL[1]).Value))
    )
    module_capacity_ah = float(
        man_par_sheet.Range(EVERBATT_MODULE_CAPACITY_SELECTED_CELL[1]).Value
    )
    cell_energy_kwh = float(man_par_sheet.Range(EVERBATT_CELL_ENERGY_SELECTED_CELL[1]).Value)
    cell_mass_kg = float(man_par_sheet.Range(EVERBATT_CELL_MASS_SELECTED_CELL[1]).Value)
    total_module_mass_kg = float(man_par_sheet.Range(EVERBATT_TOTAL_MODULE_MASS_CELL[1]).Value)
    pack_mass_kg = float(man_par_sheet.Range(EVERBATT_PACK_MASS_CELL[1]).Value)
    pack_capacity_kwh = float(man_par_sheet.Range(EVERBATT_PACK_CAPACITY_CELL[1]).Value)

    module_energy_kwh = cell_energy_kwh * cells_per_module
    module_mass_kg = total_module_mass_kg / modules_per_pack if modules_per_pack else 0.0
    module_specific_energy_whkg = (
        (module_energy_kwh * 1000.0) / module_mass_kg if module_mass_kg > 0 else 0.0
    )

    return {
        "cells_per_module": int(round(cells_per_module)),
        "modules_per_pack": modules_per_pack,
        "module_capacity_ah": module_capacity_ah,
        "cell_energy_kwh": cell_energy_kwh,
        "cell_mass_kg": cell_mass_kg,
        "module_energy_kwh": module_energy_kwh,
        "module_mass_kg": module_mass_kg,
        "module_specific_energy_whkg": module_specific_energy_whkg,
        "pack_capacity_kwh": pack_capacity_kwh,
        "pack_mass_kg": pack_mass_kg,
    }


def _apply_battery_design_inputs(
    workbook,
    target_pack_kwh: float | None = None,
    module_capacity_ah: float | None = None,
    cell_energy_kwh: float | None = None,
    cell_mass_kg: float | None = None,
) -> dict:
    """
    Write battery-size overrides into the confirmed EverBatt user-defined cells.

    Preset vehicle classes only target pack size. The detailed user-defined values
    are scaled from the chemistry-specific defaults so all other workbook inputs
    can remain at their default values.
    """
    man_par_sheet = workbook.Worksheets(EVERBATT_CELLS_PER_MODULE_CELL[0])
    workbook.Application.CalculateFull()

    profile_before = _build_runtime_battery_profile(workbook)
    default_cell_energy_kwh = profile_before["cell_energy_kwh"]
    if default_cell_energy_kwh <= 0:
        raise RuntimeError("Failed to derive the default cell energy from the EverBatt workbook.")

    if cell_energy_kwh is None and target_pack_kwh is not None:
        pack_denominator = profile_before["cells_per_module"] * profile_before["modules_per_pack"]
        cell_energy_kwh = float(target_pack_kwh) / pack_denominator

    if cell_energy_kwh is None:
        cell_energy_kwh = default_cell_energy_kwh

    scale_factor = float(cell_energy_kwh) / default_cell_energy_kwh

    if cell_mass_kg is None:
        cell_mass_kg = profile_before["cell_mass_kg"] * scale_factor
    if module_capacity_ah is None:
        module_capacity_ah = profile_before["module_capacity_ah"] * scale_factor

    man_par_sheet.Range(EVERBATT_MODULE_CAPACITY_USER_CELL[1]).Value = float(module_capacity_ah)
    man_par_sheet.Range(EVERBATT_CELL_ENERGY_USER_CELL[1]).Value = float(cell_energy_kwh)
    man_par_sheet.Range(EVERBATT_CELL_MASS_USER_CELL[1]).Value = float(cell_mass_kg)
    workbook.Application.CalculateFull()
    return _build_runtime_battery_profile(workbook)


def _apply_b2u_battery_profile(workbook, battery_profile: dict) -> None:
    """Sync the module-level battery assumptions into the B2U workbook."""
    repurposing_sheet = workbook.Worksheets(B2U_MODULE_ENERGY_CELL[0])

    repurposing_sheet.Range(B2U_MODULE_ENERGY_CELL[1]).Value = battery_profile["module_energy_kwh"]
    repurposing_sheet.Range(B2U_CELLS_PER_MODULE_CELL[1]).Value = battery_profile["cells_per_module"]
    if battery_profile["module_specific_energy_whkg"] > 0:
        repurposing_sheet.Range(B2U_MODULE_SPECIFIC_ENERGY_CELL[1]).Value = (
            battery_profile["module_specific_energy_whkg"]
        )
    workbook.Application.CalculateFull()


def _refresh_everbatt_with_macro(workbook, macro_name: str = RESET_RECYCLE_MACRO) -> None:
    """Run the Excel macro that refreshes the recycle cost calculations."""
    workbook.Application.Run(f"'{workbook.Name}'!{macro_name}")
    workbook.Application.CalculateFull()


def _close_workbook(workbook) -> None:
    """Close a workbook object without shutting down the Excel app."""
    if workbook is not None:
        workbook.Close(SaveChanges=False)


def _shutdown_excel_app(app) -> None:
    """Quit Excel and give Windows a moment to release workbook file locks."""
    if app is not None:
        app.Quit()
    gc.collect()
    time.sleep(0.5)


def _close_excel_runtime(app, workbook) -> None:
    """Release Excel COM handles before Python reads the prepared workbook."""
    if workbook is not None:
        workbook.Close(SaveChanges=False)
    if app is not None:
        app.Quit()

    # Give Excel a brief moment to release the file lock on the copied workbook.
    del workbook
    del app
    gc.collect()
    time.sleep(0.5)


@contextmanager
def prepared_runtime_workbook(
    source_excel_filename: str,
    battery_chemistry: str,
    location: str,
    feedstock_tonnes: float,
    throughput: float,
    macro_name: str = RESET_RECYCLE_MACRO,
):
    """
    Create a temporary EverBatt workbook, apply GUI inputs, run the refresh macro,
    and yield the prepared workbook path for the simulation to read.
    """
    _require_excel_com()

    source_path = resolve_input_file(source_excel_filename)
    temp_dir = tempfile.TemporaryDirectory(prefix="everbatt_runtime_")
    runtime_path = Path(temp_dir.name) / source_path.name
    shutil.copy2(source_path, runtime_path)

    pythoncom.CoInitialize()
    app = win32com.client.DispatchEx("Excel.Application")
    app.Visible = False
    app.DisplayAlerts = False

    workbook = None
    try:
        workbook = app.Workbooks.Open(Filename=str(runtime_path), ReadOnly=False)
        _apply_gui_inputs(
            workbook,
            battery_chemistry=battery_chemistry,
            location=location,
            feedstock_tonnes=feedstock_tonnes,
            throughput=throughput,
        )
        _refresh_everbatt_with_macro(workbook, macro_name=macro_name)
        workbook.Save()
        _close_excel_runtime(app, workbook)
        workbook = None
        app = None
        pythoncom.CoUninitialize()
        yield runtime_path
    finally:
        if workbook is not None:
            try:
                _close_excel_runtime(app, workbook)
            except Exception:
                pass
            finally:
                workbook = None
                app = None
                pythoncom.CoUninitialize()
        elif app is not None:
            try:
                _close_excel_runtime(app, None)
            except Exception:
                pass
            finally:
                app = None
                pythoncom.CoUninitialize()

        for _ in range(5):
            try:
                temp_dir.cleanup()
                break
            except PermissionError:
                time.sleep(0.2)


@contextmanager
def prepared_runtime_workbooks(
    source_excel_filename: str,
    source_b2u_excel_filename: str,
    battery_chemistry: str,
    location: str,
    feedstock_tonnes: float,
    throughput: float,
    target_pack_kwh: float | None = None,
    module_capacity_ah: float | None = None,
    cell_energy_kwh: float | None = None,
    cell_mass_kg: float | None = None,
    macro_name: str = RESET_RECYCLE_MACRO,
):
    """
    Prepare synchronized EverBatt and B2U runtime workbooks for one GUI run.

    EverBatt receives the current scenario inputs plus either a preset pack-size
    target or direct user-defined battery parameters. B2U is then refreshed with
    the derived module-level battery profile so the cascade-cost workbook follows
    the same battery specification.
    """
    _require_excel_com()

    source_everbatt_path = resolve_input_file(source_excel_filename)
    source_b2u_path = resolve_input_file(source_b2u_excel_filename)
    temp_dir = tempfile.TemporaryDirectory(prefix="battery_runtime_")
    runtime_everbatt_path = Path(temp_dir.name) / source_everbatt_path.name
    runtime_b2u_path = Path(temp_dir.name) / source_b2u_path.name
    shutil.copy2(source_everbatt_path, runtime_everbatt_path)
    shutil.copy2(source_b2u_path, runtime_b2u_path)

    pythoncom.CoInitialize()
    excel_initialized = True
    app = win32com.client.DispatchEx("Excel.Application")
    app.Visible = False
    app.DisplayAlerts = False

    everbatt_workbook = None
    b2u_workbook = None
    battery_profile = None

    try:
        everbatt_workbook = app.Workbooks.Open(
            Filename=str(runtime_everbatt_path),
            ReadOnly=False,
        )
        _apply_gui_inputs(
            everbatt_workbook,
            battery_chemistry=battery_chemistry,
            location=location,
            feedstock_tonnes=feedstock_tonnes,
            throughput=throughput,
        )
        _apply_battery_design_inputs(
            everbatt_workbook,
            target_pack_kwh=target_pack_kwh,
            module_capacity_ah=module_capacity_ah,
            cell_energy_kwh=cell_energy_kwh,
            cell_mass_kg=cell_mass_kg,
        )
        _refresh_everbatt_with_macro(everbatt_workbook, macro_name=macro_name)
        battery_profile = _build_runtime_battery_profile(everbatt_workbook)
        everbatt_workbook.Save()
        _close_workbook(everbatt_workbook)
        everbatt_workbook = None

        b2u_workbook = app.Workbooks.Open(
            Filename=str(runtime_b2u_path),
            ReadOnly=False,
        )
        _apply_b2u_battery_profile(b2u_workbook, battery_profile)
        b2u_workbook.Save()
        _close_workbook(b2u_workbook)
        b2u_workbook = None

        _shutdown_excel_app(app)
        app = None
        pythoncom.CoUninitialize()
        excel_initialized = False

        yield {
            "everbatt_path": runtime_everbatt_path,
            "b2u_path": runtime_b2u_path,
            "battery_profile": battery_profile,
        }
    finally:
        if everbatt_workbook is not None:
            try:
                _close_workbook(everbatt_workbook)
            except Exception:
                pass
            finally:
                everbatt_workbook = None

        if b2u_workbook is not None:
            try:
                _close_workbook(b2u_workbook)
            except Exception:
                pass
            finally:
                b2u_workbook = None

        if app is not None:
            try:
                _shutdown_excel_app(app)
            except Exception:
                pass
            finally:
                app = None

        if excel_initialized:
            pythoncom.CoUninitialize()

        for _ in range(5):
            try:
                temp_dir.cleanup()
                break
            except PermissionError:
                time.sleep(0.2)
