# EV Battery Circularity Models

This repository contains Python implementations of EV battery circularity models developed for a master's thesis project.

## Project Structure

```text
python version/
|-- launcher.py                 # Launcher for selecting static or dynamic GUI
|-- static version/             # Static Yamada-style circularity model
|-- dynamic version/            # Dynamic year-by-year cohort extension
|-- start_launcher.bat          # Windows launcher shortcut
|-- start_static_gui.bat        # Windows shortcut for the static Streamlit app
|-- start_dynamic_gui.bat       # Windows shortcut for the dynamic Streamlit app
`-- README.md
```

## Static Model

The static model is in `static version/`.

Run from PowerShell:

```powershell
cd ".\static version"
python .\run.py --no-show
```

Run the GUI:

```powershell
python -m streamlit run .\app.py
```

## Dynamic Model

The dynamic model is in `dynamic version/`.

Run from PowerShell:

```powershell
cd ".\dynamic version"
python .\run.py --n-sims 200 --years 20 --no-show
```

Run the GUI:

```powershell
python -m streamlit run .\app.py
```

Run the batch exporter:

```powershell
python .\run_dynamic_batch.py --chemistries "NMC(811)" --segments Sedan --markets "Moderate Market" --processes Direct --regens Direct --years 5 --n-sims 10
```

## Dependencies

Install the required Python packages inside the model folder you want to run:

```powershell
pip install -r .\requirements.txt
```

## Input Workbooks

The models use Excel workbooks such as:

- `EverBatt.xlsm`
- `nrel-b2u-repurposing-cost-calculator-jun2020.xlsm`

The EverBatt and NREL B2U workbooks are included in each model's `data/` folder. They are third-party tools and are not relicensed under this project's Apache License; their original copyright and license terms continue to apply.

The NREL B2U Repurposing Cost Calculator workbook is included for convenience under its applicable DOE/NREL/Alliance software use agreement. Results generated with B2U-derived inputs depend on user-defined assumptions and should not be interpreted as being validated, endorsed, or approved by DOE, NREL, or Alliance.

## Notes

- Generated outputs, temporary files, and Python caches are excluded from version control.
- Research papers and presentation assets under `new battery/` are also excluded from version control.
- See the README files inside `static version/` and `dynamic version/` for model-specific details.

The Windows GUI launchers check for Streamlit and install it for the current Python user when it is missing. Python must already be installed, and an internet connection is needed for first-time installation.

## License and Attribution

Copyright 2026 Yidi Quan.

This project is licensed under the Apache License 2.0. You may use, modify,
distribute, and use the software commercially under the terms of the license.
Redistributions and modified versions must retain the copyright, license, and
attribution notices.

Academic use should cite this repository and, where applicable, the associated
master's thesis or publication. Please do not present this work or substantial
parts of it as your own original work without proper attribution.
