# Dynamic EV Battery Circularity Model

This folder contains the dynamic extension of the original Yamada-style battery circularity model.

The original static version remains untouched in the parent project. Everything added for the dynamic extension lives inside `dynamic version/`.

## What Is New Here

- Year-by-year cohort-based simulation instead of a single static absorbing-chain result
- Dynamic policy ramp instead of only a fixed optimized subsidy point
- Separate EV-use and cascade-use stock trajectories
- Batch export for scenario comparison and later thesis figures
- Dedicated GUI for dynamic settings and representative vehicle segments

## Input Files

The dynamic version reuses the same Excel workbooks:

- `EverBatt.xlsm`
- `nrel-b2u-repurposing-cost-calculator-jun2020.xlsm`

They are resolved from:

1. `dynamic version/`
2. `dynamic version/data/`
3. the parent project `data/`

So the current setup works directly with the parent project's `data/` folder.

## How To Run

Open PowerShell in the parent project folder, then run:

```powershell
cd ".\dynamic version"
```

Install dependencies if needed:

```powershell
pip install -r .\requirements.txt
```

Run the dynamic CLI model:

```powershell
python .\run.py --n-sims 200 --years 20 --no-show
```

Run the dynamic GUI:

```powershell
python -m streamlit run .\app.py
```

Run one batch export:

```powershell
python .\run_dynamic_batch.py --chemistries "NMC(811)" --segments Sedan --markets "Moderate Market" --processes Direct --regens Direct --years 5 --n-sims 10
```

## Batch Outputs

The batch runner writes:

- `dynamic version/outputs/dynamic_batch_summary.csv`
- `dynamic version/outputs/dynamic_batch_series.csv`

`dynamic_batch_summary.csv` is best for cross-scenario comparison tables.

`dynamic_batch_series.csv` is best for line plots such as in-use stock, cumulative landfill, cumulative recovery, GHG, and cost over time.

## Notes

- The dynamic version still uses the Yamada circular structure, but it extends it into a non-homogeneous yearly process.
- GUI vehicle-size presets currently represent representative segments: `Sedan`, `Wagon`, `SUV`, plus `Custom`.
- The GUI writes battery-size inputs into the confirmed EverBatt user-defined cells and synchronizes the B2U module assumptions.
- To avoid fragile Excel save behavior on Windows, the dynamic workflow reads from live runtime workbooks after recalculation instead of relying on saved temporary files.
