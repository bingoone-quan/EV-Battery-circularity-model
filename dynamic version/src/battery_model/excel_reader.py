"""Excel cell reading helpers with tolerant support for EverBatt .xlsm files."""

from __future__ import annotations

import atexit
import re
from functools import lru_cache
from io import BytesIO
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from openpyxl import load_workbook

from battery_model.paths import resolve_input_file

try:
    import pythoncom
    import win32com.client
except Exception:  # pragma: no cover - optional Windows fallback
    pythoncom = None
    win32com = None


_OPEN_COM_WORKBOOKS = []


def _normalize_range(cell_range: str) -> str:
    """Convert a MATLAB-style range like 'E9:E9' into a single Excel cell."""
    if ":" in cell_range:
        return cell_range.split(":", maxsplit=1)[0]
    return cell_range


def _is_workbook_handle(excel_source: Any) -> bool:
    """Return True when the caller passed a live Excel workbook handle."""
    return hasattr(excel_source, "Worksheets") and not isinstance(excel_source, (str, bytes))


def _resolve_workbook_path(excel_filename: str) -> str:
    """Resolve workbook names relative to the project root or data folder."""
    return str(resolve_input_file(excel_filename).resolve())


@lru_cache(maxsize=8)
def _load_workbook_cached(excel_filename: str):
    """Load and cache workbooks so repeated single-cell reads stay fast."""
    workbook_path = _resolve_workbook_path(excel_filename)
    try:
        return load_workbook(
            filename=workbook_path,
            data_only=True,
            read_only=True,
            keep_vba=True,
        )
    except Exception:
        return _load_workbook_tolerant(workbook_path)


def _patch_styles_xml(styles_xml: bytes) -> bytes:
    """
    Clamp invalid font family values so openpyxl can read legacy/custom workbooks.

    EverBatt.xlsm contains font family values above openpyxl's allowed maximum
    (14). This patch only relaxes that style metadata issue and does not touch
    cell data or formulas.
    """
    text = styles_xml.decode("utf-8", errors="ignore")
    text = re.sub(
        r'(<family val=")(\d+)("/>)',
        lambda match: (
            f'{match.group(1)}{min(int(match.group(2)), 14)}{match.group(3)}'
        ),
        text,
    )
    return text.encode("utf-8")


def _load_workbook_tolerant(workbook_path: str):
    """Load a workbook after patching known stylesheet incompatibilities in memory."""
    in_memory = BytesIO()
    with ZipFile(workbook_path, "r") as source_zip, ZipFile(
        in_memory, "w", ZIP_DEFLATED
    ) as patched_zip:
        for item in source_zip.infolist():
            data = source_zip.read(item.filename)
            if item.filename == "xl/styles.xml":
                data = _patch_styles_xml(data)
            patched_zip.writestr(item, data)

    in_memory.seek(0)
    return load_workbook(
        filename=in_memory,
        data_only=True,
        read_only=True,
        keep_vba=True,
    )


@lru_cache(maxsize=1)
def _get_excel_app():
    """Create one hidden Excel COM instance for workbooks openpyxl cannot parse."""
    if pythoncom is None or win32com is None:
        raise RuntimeError("win32com is not available for Excel COM fallback.")

    pythoncom.CoInitialize()
    app = win32com.client.DispatchEx("Excel.Application")
    app.Visible = False
    app.DisplayAlerts = False
    return app


@lru_cache(maxsize=8)
def _open_workbook_via_com(excel_filename: str):
    """Open a workbook through the local Excel application."""
    app = _get_excel_app()
    workbook_path = _resolve_workbook_path(excel_filename)
    workbook = app.Workbooks.Open(workbook_path, UpdateLinks=False, ReadOnly=True)
    _OPEN_COM_WORKBOOKS.append(workbook)
    return workbook


def _close_excel_resources():
    """Close cached COM workbooks and the Excel application at process exit."""
    for workbook in _OPEN_COM_WORKBOOKS:
        try:
            workbook.Close(SaveChanges=False)
        except Exception:
            pass

    try:
        if hasattr(_get_excel_app, "cache_info") and _get_excel_app.cache_info().currsize:
            app = _get_excel_app()
            app.Quit()
    except Exception:
        pass


atexit.register(_close_excel_resources)


def read_excel_scalar(excel_filename: str, sheet_name: str, cell_range: str) -> Any:
    """Read one value from a workbook using the same sheet/range style as MATLAB."""
    cell = _normalize_range(cell_range)
    if _is_workbook_handle(excel_filename):
        worksheet = excel_filename.Worksheets(sheet_name)
        return worksheet.Range(cell).Value

    try:
        workbook = _load_workbook_cached(excel_filename)
        worksheet = workbook[sheet_name]
        return worksheet[cell].value
    except Exception:
        workbook = _open_workbook_via_com(excel_filename)
        worksheet = workbook.Worksheets(sheet_name)
        return worksheet.Range(cell).Value
