# EGOFET Toolkit

Analysis and reporting toolkit for Electrolyte-Gated Organic Field-Effect
Transistors (EGOFETs). It covers the path from raw Keithley/HDF5 measurements to
parameter extraction, interactive exploration, and shareable Marimo reports.

This is the cleaned, analysis-focused version of the internal EGOFET project:
the fabrication/measurement tracking layer is out of scope here, while the
readers, plotting helpers, analysis routines, and example data stay in.

## Who it is for

| Audience | What you can do |
|----------|-----------------|
| **Developers** | Read and modify `src/`, run the exploratory Jupyter notebooks, build and extend the Marimo apps, and export reports. |
| **Consumers** (non-programmers) | Open a prepared app or HTML report, pick an HDF5 file, adjust the widgets, and export the resulting tables. No Python editing required. |

Reports are **reactive**: every parameter is exposed as a widget with a sensible
default, so a consumer can change the analysis without touching the code.

## Repository layout

```
egofets-toolkit/
├── data/
│   ├── raw/                    # Keithley HDF5 measurements (example files included)
│   ├── processed/              # Derived tables and CSVs
│   └── photos/                 # Sample photos
├── notebooks/
│   ├── 01_exploration/         # HDF5 structure and dataset inspection
│   ├── 02_transfer_curves/     # Transfer curve analysis and report app
│   ├── 03_output_curves/       # Output curve analysis
│   ├── 04_calibration_curve/   # Calibration curve construction
│   ├── 05_presentation/        # Marimo layout experiments (internal)
│   └── _legacy/                # Superseded Jupyter reports (reference only)
├── src/
│   ├── readers/                # HDF5 readers and inspection helpers
│   ├── analysis.py             # Parameter extraction (V_th, fits)
│   ├── plotting.py             # Matplotlib figures for transfers/outputs/stability
│   └── io/                     # Figure, data, and script saving utilities
├── consumer/                   # Desktop launcher, report manifest, shortcut installer
├── output/                     # Generated HTML reports and figures
├── environment.yml             # Conda environment
├── pyproject.toml              # Dependency metadata for uv
├── uv.lock                     # Resolved uv dependency lock
├── .python-version             # Interpreter pinned for uv
└── README.md
```

## Requirements

- Python 3.10 or newer (3.10–3.14).
- Core dependencies: `h5py`, `pandas`, `numpy`, `scipy`, `matplotlib`,
  `marimo`, `jupyter`, `ipykernel`.

## Installation

### Conda

```bash
conda env create -f environment.yml
conda activate egofets
```

### uv

```bash
uv sync
source .venv/bin/activate        # Linux / macOS
# Windows: .venv\Scripts\activate
```

`uv sync` creates `.venv` using the interpreter pinned in `.python-version` and
installs every dependency. If you prefer not to activate the environment,
prefix the commands below with `uv run`.

### Consumer setup (developers only)

Run this once, with the interpreter that will power the launcher:

```bash
.venv/bin/python consumer/install_shortcuts.py
# or
conda run -n egofets python consumer/install_shortcuts.py
```

It creates a desktop/start-menu shortcut for Linux or Windows. Validate the
consumer mode without opening the GUI:

```bash
.venv/bin/python consumer/launcher.py --check
.venv/bin/python consumer/launcher.py --export
```

## Quick start

```bash
# Explore a raw measurement file (Jupyter)
jupyter lab notebooks/01_exploration/01_exploration_analysis.ipynb

# Develop a Marimo app (code visible, reactive)
marimo edit notebooks/02_transfer_curves/02_transfer_marimo.py

# Present the app read-only (code hidden)
marimo run notebooks/02_transfer_curves/02_transfer_marimo.py

# Export a static HTML report
marimo export html notebooks/02_transfer_curves/02_transfer_marimo.py -o report.html

# Open the consumer launcher (desktop control panel)
python consumer/launcher.py
```

The apps read from `data/raw/` and default to the bundled examples:

- `transf-outp_example.hdf5` — transfer, output, and stability measurements.
- `calibration_curve_example.hdf5` — calibration batches.

### For non-programmers

The `consumer/` folder provides a desktop launcher. After the one-time setup,
consumers double-click **EGOFET Toolkit**:

1. The control panel shows the environment status and a few actions.
2. **Open reports** starts a local Marimo gallery in the browser, with one card
   per report.
3. **Generate HTML reports** writes a static copy of every report to
   `output/reports/`.
4. Closing the window (or **Quit**) stops the local server.

The launcher only exposes static HTML export; WebAssembly export is
intentionally disabled for now. The server listens on `127.0.0.1` and is not
reachable from the network.

## Data

| Folder | Contents |
|--------|----------|
| `data/raw/` | Raw Keithley HDF5 files. One file per measurement session. |
| `data/processed/` | Derived tables and CSVs produced by analyses. |
| `data/photos/` | Photos of wafers, pieces, and devices. |

The Marimo apps discover files dynamically from `data/raw/`, so adding a new
HDF5 file is enough for it to appear in the file selector.

## Library (`src`)

`src` is imported directly from the repository root; the notebooks add the
project root to `sys.path`, so no package installation is needed.

| Module | Purpose | Main API |
|--------|---------|----------|
| `src.readers` | Inspect and read HDF5 measurements | `list_measurements`, `read_curve`, `read_all_curves`, `print_structure`, `view_tree_content` |
| `src.plotting` | Matplotlib figures | `plot_transfer`, `plot_output`, `plot_grid`, `plot_i_vs_time` |
| `src.analysis` | Parameter extraction | `extract_vth_for_transfers` |
| `src.io` | Save figures, data, and code | `SaveConfig`, `save_figure`, `save_result`, `record_script` |

Example:

```python
from src.readers import list_measurements

for measurement in list_measurements("data/raw/transf-outp_example.hdf5"):
    print(measurement["name"], measurement["mode"], measurement["n_curves"])
```

## Notebooks

Each analysis follows the same three-file convention:

| File | Role | Audience |
|------|------|----------|
| `01_<analysis>_analysis.ipynb` | Full exploratory analysis: every step, check, and intermediate result. | Developers |
| `02_<analysis>_marimo.py` | The same analysis as a reactive Marimo app with widgets. | Developers and consumers |
| `03_<analysis>_report.py` | Condensed report app: runs with default parameters and exports HTML plus downloadable figures. | Consumers |

Current status:

| Analysis | `01` analysis | `02` Marimo app | `03` report app |
|----------|---------------|-----------------|-----------------|
| Exploration | `01_exploration/01_exploration_analysis.ipynb` | `01_exploration/02_exploration_marimo.py` | — |
| Transfer curves | `02_transfer_curves/01_transfer_analysis.ipynb` | `02_transfer_curves/02_transfer_marimo.py` | — |
| Output curves | `03_output_curves/01_output_analysis.ipynb` | Pending | — |
| Calibration | `04_calibration_curve/01_calibration_analysis.ipynb` | `04_calibration_curve/02_calibration_marimo.py` | — |
| Presentation lab | `05_presentation/01_layout_lab.py` (internal) | — | — |

Superseded Jupyter reports are kept in `notebooks/_legacy/` for reference.
Supporting theory and extraction notes (`*.md`) live next to the analysis they
belong to.

## HDF5 data format

The files are generated by a Keithley 2600 SourceMeter with two channels
(`a`/GS and `b`/DS). `src/readers/keithley_dean.py` detects the measurement mode
from the `measurement_mode` attribute of each top-level group:

- **transfer** — $V_{GS}$ sweep at fixed $V_{DS}$; the group contains `curve_N`
  subgroups.
- **output** — $V_{DS}$ sweep at fixed $V_{GS}$; the group contains `curve_N`
  subgroups.
- **stability** — chronoamperometry; datasets live directly in the group.

Each curve stores `measured_V_GS`, `measured_V_DS`, `measured_I_DS`,
`measured_I_GS`, `calculated_V_GS`, `calculated_V_DS`, and `time`.

## Roadmap

- Portable distribution (`conda-pack`) for machines without a prepared
  environment.
- `03_<analysis>_report.py` apps with HTML export and per-figure download
  (Plotly, or a Matplotlib download button).
- Marimo conversion of the output curve analysis.
- Translation of notebooks and docstrings from Spanish to English.

## License and contact

MIT License © 2026 David Ibarra.

Nanomol Research Group — ICMAB (CSIC)
Contact: [dibarra@icmab.es](mailto:dibarra@icmab.es)
