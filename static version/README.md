# EV Battery Circularity Simulation

Python port of the MATLAB-based master's thesis model for EV battery circularity evaluation.

## Current Layout

```text
python version/
├─ data/        # Recommended location for Excel input files
├─ outputs/     # Saved figures and future exported results
├─ src/
│  └─ battery_model/
│     ├─ config.py
│     ├─ excel_reader.py
│     ├─ everbatt.py
│     ├─ paths.py
│     ├─ plotting.py
│     ├─ simulation.py
│     └─ yamada.py
├─ run.py
├─ README.md
└─ requirements.txt
```

## Input Files

The simulation reads two Excel workbooks:

- `EverBatt.xlsm`
- `nrel-b2u-repurposing-cost-calculator-jun2020.xlsm`

They can be placed in either:

- the project root folder, or
- the `data/` folder

Both layouts are supported so the original workflow remains valid.
You do not have to move the Excel files manually unless you want the cleaner `data/` layout.

## How To Run

Open PowerShell in this folder and run:

```powershell
python .\run.py
```

For the Streamlit GUI, run:

```powershell
python -m streamlit run .\app.py
```

Run without opening plot windows and save the figures to `outputs/`:

```powershell
python .\run.py --no-show
```

Run a quick test with fewer Monte Carlo iterations:

```powershell
python .\run.py --n-sims 200 --no-show
```

## Notes

- The model logic, parameter settings, and Excel cell mappings are kept aligned with the MATLAB version.
- A compatibility patch is included so Python can read the EverBatt `.xlsm` workbook even when its stylesheet metadata is not fully compatible with `openpyxl`.
- Saved figures are written to the `outputs/` folder when `--no-show` is used.
- `design_effort` has been removed from the active model structure. The current version only analyzes the subsidy effect across scenarios.
- The Streamlit app writes GUI inputs into a temporary EverBatt workbook, runs the `Reset_recycle` macro, and then launches the Python simulation from the refreshed results.
- The current GUI and Python model support `NMC(811)`, `NMC(111)`, `NMC(532)`, `NMC(622)`, and `NCA`.
