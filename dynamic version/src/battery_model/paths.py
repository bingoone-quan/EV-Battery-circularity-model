"""Project path helpers for inputs, outputs, and the package source root."""

from __future__ import annotations

from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
SRC_DIR = PACKAGE_DIR.parent
PROJECT_ROOT = SRC_DIR.parent
PARENT_PROJECT_ROOT = PROJECT_ROOT.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
PARENT_DATA_DIR = PARENT_PROJECT_ROOT / "data"


def ensure_project_dirs() -> None:
    """Create the standard project folders if they do not exist yet."""
    DATA_DIR.mkdir(exist_ok=True)
    OUTPUTS_DIR.mkdir(exist_ok=True)


def resolve_input_file(filename: str) -> Path:
    """
    Resolve an input workbook path.

    Search order:
    1. Absolute path provided by the user.
    2. Current dynamic-version project root.
    3. The current dynamic-version ./data folder.
    4. The parent project's ./data folder.
    """
    candidate = Path(filename).expanduser()
    if candidate.is_absolute():
        return candidate

    root_path = PROJECT_ROOT / candidate
    if root_path.exists():
        return root_path

    data_path = DATA_DIR / candidate
    if data_path.exists():
        return data_path

    parent_data_path = PARENT_DATA_DIR / candidate
    if parent_data_path.exists():
        return parent_data_path

    return data_path
