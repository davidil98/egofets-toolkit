# /// script
# [tool.marimo.opengraph]
# title = "Data exploration"
# description = "Inspect HDF5 files, measurements, datasets, and attributes."
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="full", app_title="EGOFET — Data exploration")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # EXPLORATION FOR KEITHLEY .hdf5 FILES

    This notebook describe the development of code for data read and extraction of `.hdf5` files obtained by the keithley 2600A equipment and the Dean controller. At the same time, here's shown the marimo widget potential as a reactive notebook for presenting data treatment.
    There's two principal ways to use marimo via termina:

    ```bash
    marimo edit notebooks/01_exploration/02_exploration_marimo.py # for edit code

    marimo run notebooks/01_exploration/02_exploration_marimo.py # for display markdown and output-cells.
    ```

    We'll start loading the file frome this directory
    """)
    return


@app.cell(hide_code=True)
def _():
    import os
    import sys
    from pathlib import Path

    import h5py
    import marimo as mo
    import pandas as pd

    return Path, h5py, mo, os, pd, sys


@app.cell(hide_code=True)
def _(Path, mo, os, sys):
    def find_project_root(marker="src"):
        cwd = Path(os.getcwd()).resolve()
        for parent in [cwd, *cwd.parents]:
            if (parent / marker).is_dir():
                return parent
        raise FileNotFoundError(f"Could not find a directory containing '{marker}'")


    PROJECT_ROOT = find_project_root()
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from src.readers import print_structure, view_tree_content
    from src.readers.keithley_dean import (
        get_dset_array,
        get_dset_names,
        list_measurements,
    )

    data_folder = PROJECT_ROOT / "data" / "raw"
    hdf5_files = sorted(p.name for p in data_folder.glob("*.hdf5"))

    default_file = "transf-outp_example.hdf5"
    if default_file not in hdf5_files:
        default_file = hdf5_files[0] if hdf5_files else None

    file_widget = mo.ui.dropdown(
        options=hdf5_files,
        value=default_file,
        label="HDF5 file",
        searchable=True,
    )
    file_widget
    return (
        data_folder,
        file_widget,
        get_dset_array,
        get_dset_names,
        hdf5_files,
        list_measurements,
        print_structure,
        view_tree_content,
    )


@app.cell(hide_code=True)
def _(data_folder, file_widget, hdf5_files, mo):
    mo.stop(
        not hdf5_files,
        mo.md(f"**No `.hdf5` files found in** `{data_folder}`"),
    )
    hdf5_path = data_folder / file_widget.value
    mo.md(f"`{hdf5_path}`")
    return (hdf5_path,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 1. File tree

    Groups, datasets, and attributes in the selected file.
    """)
    return


@app.cell
def _(hdf5_path, print_structure, view_tree_content):
    print_structure(hdf5_path)
    view_tree_content(hdf5_path, attribute_name="measurement_mode")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 2. Measurements

    Pick a measurement and one of its curves (if it has any).
    """)
    return


@app.cell
def _(hdf5_path, list_measurements, mo):
    measurements = list_measurements(hdf5_path)
    measurement_names = [m["name"] for m in measurements]

    measurement_widget = mo.ui.dropdown(
        options=measurement_names,
        value=measurement_names[0] if measurement_names else None,
        label="Measurement",
        searchable=True,
    )
    measurement_widget
    return measurement_widget, measurements


@app.cell
def _(h5py, hdf5_path, measurement_widget, mo):
    curve_names = []
    if measurement_widget.value is not None:
        with h5py.File(hdf5_path, "r") as f:
            node = f[measurement_widget.value]
            curve_names = sorted(
                key for key, item in node.items() if isinstance(item, h5py.Group)
            )

    if curve_names:
        curve_widget = mo.ui.dropdown(
            options=curve_names,
            value=curve_names[0],
            label="Curve",
        )
    else:
        curve_widget = None

    _view = (
        curve_widget
        if curve_widget is not None
        else mo.md("_This measurement stores its datasets directly in the group._")
    )
    _view
    return (curve_widget,)


@app.cell
def _(
    curve_widget,
    get_dset_names,
    hdf5_path,
    measurement_widget,
    measurements,
    mo,
    pd,
):
    mode = next(
        (m["mode"] for m in measurements if m["name"] == measurement_widget.value),
        "unknown",
    )
    curve_name = curve_widget.value if curve_widget is not None else None
    datasets = get_dset_names(
        hdf5_path,
        measurement_widget.value,
        curve_name=curve_name,
    )
    dataset_table = pd.DataFrame(
        [
            {
                "dataset": d["name"],
                "shape": str(d["shape"]),
                "dtype": str(d["dtype"]),
            }
            for d in datasets
        ]
    )

    mo.vstack(
        [
            mo.md(f"**Mode:** `{mode}`  ·  **Curve:** `{curve_name or '—'}`"),
            mo.ui.table(dataset_table, pagination=False, selection=None),
        ]
    )
    return curve_name, datasets


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 3. Dataset preview

    Read the selected dataset and inspect its first values.
    """)
    return


@app.cell
def _(datasets, mo):
    dset_names = [d["name"] for d in datasets]
    dset_widget = mo.ui.dropdown(
        options=dset_names,
        value=dset_names[0] if dset_names else None,
        label="Dataset",
    )
    dset_widget
    return (dset_widget,)


@app.cell
def _(
    curve_name,
    dset_widget,
    get_dset_array,
    hdf5_path,
    measurement_widget,
    mo,
    pd,
):
    if dset_widget.value is None:
        _preview = mo.md("_Select a dataset._")
    else:
        (array,) = get_dset_array(
            hdf5_path,
            measurement_widget.value,
            curve_name=curve_name,
            dsets=[dset_widget.value],
        )
        _preview = mo.vstack(
            [
                mo.md(
                    f"**{dset_widget.value}** — shape `{array.shape}`, "
                    f"dtype `{array.dtype}`"
                ),
                mo.ui.table(
                    pd.DataFrame({"index": range(len(array)), "value": array}),
                    pagination=True,
                    page_size=10,
                    selection=None,
                ),
            ]
        )
    _preview
    return


if __name__ == "__main__":
    app.run()
