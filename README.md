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

These files are intentionally ignored by Git because they may be large, local, or proprietary. Place them in the relevant `data/` folder before running the model locally.

## Notes

- Generated outputs, temporary files, Python caches, and local Excel input workbooks are excluded from version control.
- Research papers and presentation assets under `new battery/` are also excluded from version control.
- See the README files inside `static version/` and `dynamic version/` for model-specific details.

## License and Attribution

Copyright 2026 Yidi Quan.

This project is licensed under the Apache License 2.0. You may use, modify,
distribute, and use the software commercially under the terms of the license.
Redistributions and modified versions must retain the copyright, license, and
attribution notices.

Academic use should cite this repository and, where applicable, the associated
master's thesis or publication. Please do not present this work or substantial
parts of it as your own original work without proper attribution.
