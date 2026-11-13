# EGOFET Toolkit — Consumer Guide

This folder contains the desktop launcher for people who want to use the
reports without touching Python or a terminal.

## Start the toolkit

Double-click **EGOFET Toolkit** on the desktop or in the applications menu.

If the shortcut does not exist yet, ask the toolkit maintainer to run the setup
once. See [For maintainers](#for-maintainers) below.

## What the buttons do

| Button | Action |
|--------|--------|
| **Open reports** | Starts a local Marimo gallery and opens it in your browser. |
| **Generate HTML reports** | Creates a static HTML copy of every report in `output/reports/`. |
| **Open data folder** | Opens `data/raw/`, where the HDF5 measurement files live. |
| **Open reports folder** | Opens `output/reports/`, where the exported HTML files are saved. |
| **Stop server** | Stops the local report server. |
| **Quit** | Stops the server and closes the toolkit. |

## Using a report

1. Click **Open reports**.
2. Choose a report card: *Transfer curves*, *Output curves*,
   *Calibration curve*, or *Data exploration*.
3. Pick an HDF5 file from the dropdown and adjust the widgets on the page.
4. The plots and tables update automatically.

The gallery opens the report versions of each analysis: the code is hidden and
the controls are limited to the options a consumer needs. The full analysis
apps are only for maintainers and open with `marimo edit`.

The report server runs only on your computer (`127.0.0.1`). Other people cannot
access it from the network.

## Exporting a report

Click **Generate HTML reports**. The toolkit runs every report with its default
settings and saves one HTML file per report in `output/reports/`.

- The exported HTML is a static snapshot: it shows the results for the default
  widget values, so change the widgets before exporting if you need a specific
  configuration.
- The export does not use WebAssembly and does not require internet.
- The source notebook is not included in the HTML.

## Closing

Close the window with the **X** or the **Quit** button. The local server is
stopped automatically.

## Troubleshooting

**The window does not open.**
Ask the toolkit maintainer to reinstall the shortcut. The environment or the
repository may have moved.

**"Marimo not found" or an environment error.**
The Python environment is incomplete. Ask the maintainer to update it:

```bash
uv sync
# or
conda env update -f environment.yml
```

**The browser does not open.**
Open the address shown in the Activity panel while the toolkit is running. It
looks like `http://127.0.0.1:<port>`.

**Windows shows a firewall prompt.**
The server only listens on the local machine. Allow access on private networks
or cancel it if you do not need the browser connection.

## For maintainers

Setup once, using the environment that will run the launcher:

```bash
# uv
uv sync
.venv/bin/python consumer/install_shortcuts.py

# conda
conda env update -f environment.yml
conda run -n egofets python consumer/install_shortcuts.py
```

Validate without opening the GUI:

```bash
.venv/bin/python consumer/launcher.py --check
.venv/bin/python consumer/launcher.py --export
```

To change which reports consumers see, edit `consumer/reports.json`. The
manifest points to the `03_*_report.py` apps; the `02_*_marimo.py` analysis
apps and the Jupyter notebooks are developer material and are not listed there.
