# /// script
# [tool.marimo.opengraph]
# title = "Transfer curves"
# description = "Transfer curve report with V_th, SS, I_on/I_off, and CSV export."
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="full", app_title="EGOFET — Transfer curves")


@app.cell(hide_code=True)
def _():
    import os
    import sys
    from pathlib import Path

    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    return Path, mo, np, os, pd, plt, sys


@app.cell(hide_code=True)
def _(Path, os, sys):
    def _find_project_root(marker="src"):
        cwd = Path(os.getcwd()).resolve()
        for parent in [cwd, *cwd.parents]:
            if (parent / marker).is_dir():
                return parent
        raise FileNotFoundError(f"No se encontro un directorio con '{marker}'")

    _PROJECT_ROOT = _find_project_root()
    if str(_PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(_PROJECT_ROOT))

    from src.analysis import extract_transfer_metrics
    from src.plotting import (
        plot_grid,
        plot_transfer,
        plot_transfer_linearized,
    )
    from src.readers.keithley_dean import list_measurements

    data_folder = _PROJECT_ROOT / "data" / "raw"
    hdf5_files = sorted(p.name for p in data_folder.glob("*.hdf5"))

    default_file = "transf-outp_example.hdf5"
    if default_file not in hdf5_files:
        default_file = hdf5_files[0] if hdf5_files else None
    return (
        data_folder,
        default_file,
        extract_transfer_metrics,
        hdf5_files,
        list_measurements,
        plot_grid,
        plot_transfer,
        plot_transfer_linearized,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Curvas de transferencia — EGOFET

    Reporte de todas las mediciones `transfer` de un archivo HDF5. Para cada
    medición se extrae $V_{th}$ por el método $\sqrt{|I_{DS}|}$ y se resumen
    $SS$, $I_{on}/I_{off}$ y $g_m$.

    Elegí el archivo, excluí mediciones y ajustá la ventana de extracción desde
    **Opciones**. La tabla de resultados se descarga como CSV.
    """)
    return


@app.cell(hide_code=True)
def _(data_folder, hdf5_files, mo):
    mo.stop(
        not hdf5_files,
        mo.callout(
            mo.md(f"No se encontraron archivos `.hdf5` en `{data_folder}`"),
            kind="warn",
        ),
    )
    return


@app.cell(hide_code=True)
def _(default_file, hdf5_files, mo):
    file_widget = mo.ui.dropdown(
        options=hdf5_files,
        value=default_file,
        label="Archivo HDF5",
        searchable=True,
        full_width=True,
    )
    file_widget
    return (file_widget,)


@app.cell(hide_code=True)
def _(data_folder, file_widget, list_measurements, mo):
    hdf5_path = data_folder / file_widget.value
    transfer_measurements = [
        m["name"] for m in list_measurements(hdf5_path) if m["mode"] == "transfer"
    ]
    mo.stop(
        not transfer_measurements,
        mo.callout(
            mo.md("Este archivo no tiene mediciones de tipo `transfer`."),
            kind="warn",
        ),
    )
    return hdf5_path, transfer_measurements


@app.cell(hide_code=True)
def _(mo, transfer_measurements):
    exclude_widget = mo.ui.multiselect(
        options=transfer_measurements,
        value=[],
        label="Mediciones excluidas",
        full_width=True,
    )
    ncols_widget = mo.ui.slider(
        start=1,
        stop=4,
        step=1,
        value=3,
        label="Columnas de la grilla",
        show_value=True,
    )
    direction_widget = mo.ui.dropdown(
        options={"Ambas": "both", "Ida": "fwd", "Vuelta": "reverse"},
        value="Ambas",
        label="Barrido a graficar",
    )
    vmin_widget = mo.ui.range_slider(
        start=-0.60,
        stop=0.00,
        step=0.01,
        value=[-0.40, -0.20],
        label=r"Ventana de ajuste — $V_{min}$ (V)",
        show_value=True,
        debounce=True,
    )
    vmax_widget = mo.ui.range_slider(
        start=-0.60,
        stop=0.00,
        step=0.01,
        value=[-0.15, -0.05],
        label=r"Ventana de ajuste — $V_{max}$ (V)",
        show_value=True,
        debounce=True,
    )
    r2_widget = mo.ui.slider(
        start=0.0,
        stop=1.0,
        step=0.05,
        value=0.80,
        label=r"$R^2$ mínimo para el resumen",
        show_value=True,
        debounce=True,
    )

    mo.accordion(
        {
            "Opciones": mo.vstack(
                [
                    exclude_widget,
                    mo.hstack(
                        [ncols_widget, direction_widget, r2_widget],
                        justify="start",
                        align="end",
                        gap=1,
                        wrap=True,
                    ),
                    mo.hstack(
                        [vmin_widget, vmax_widget],
                        justify="start",
                        align="end",
                        gap=1,
                        wrap=True,
                    ),
                ],
                gap=1,
            )
        }
    )
    return (
        direction_widget,
        exclude_widget,
        ncols_widget,
        r2_widget,
        vmax_widget,
        vmin_widget,
    )


@app.cell(hide_code=True)
def _(exclude_widget, mo, transfer_measurements):
    selected_measurements = [
        m for m in transfer_measurements if m not in exclude_widget.value
    ]
    mo.md(
        f"**{len(selected_measurements)}** de **{len(transfer_measurements)}** "
        "mediciones de transfer seleccionadas."
    )
    return (selected_measurements,)


@app.cell(hide_code=True)
def _(
    extract_transfer_metrics,
    hdf5_path,
    mo,
    selected_measurements,
    vmax_widget,
    vmin_widget,
):
    mo.stop(
        not selected_measurements,
        mo.callout(
            mo.md("No hay mediciones seleccionadas."),
            kind="warn",
        ),
    )
    df_metrics = extract_transfer_metrics(
        hdf5_path,
        selected_measurements,
        v_min_range=tuple(vmin_widget.value),
        v_max_range=tuple(vmax_widget.value),
    )
    mo.stop(
        df_metrics.empty,
        mo.callout(
            mo.md(
                "No se pudo extraer $V_{th}$ de las mediciones seleccionadas. "
                "Revisá la ventana de ajuste."
            ),
            kind="warn",
        ),
    )
    return (df_metrics,)


@app.cell(hide_code=True)
def _(df_metrics, mo, r2_widget):
    _good = df_metrics[df_metrics["R^2"] >= r2_widget.value]
    _ss = df_metrics["SS (V/dec)"].median()
    _ratio = df_metrics["I_on/I_off"].median()
    mo.hstack(
        [
            mo.stat(str(len(df_metrics)), label="Fits", bordered=True),
            mo.stat(
                str(len(_good)),
                label=f"R² ≥ {r2_widget.value:.2f}",
                bordered=True,
            ),
            mo.stat(
                f"{_good['V_th (V)'].mean():.3f} V"
                if len(_good)
                else "—",
                label="V_th medio (fits buenos)",
                bordered=True,
            ),
            mo.stat(
                f"{df_metrics['R^2'].mean():.3f}",
                label="R² medio",
                bordered=True,
            ),
            mo.stat(
                f"{_ss:.3f} V/dec" if _ss == _ss else "—",
                label="SS mediana",
                bordered=True,
            ),
            mo.stat(
                f"{_ratio:.1f}" if _ratio == _ratio else "—",
                label="I_on/I_off mediana",
                bordered=True,
            ),
        ],
        justify="start",
        wrap=True,
        gap=1,
    )
    return


@app.cell(hide_code=True)
def _(
    direction_widget,
    hdf5_path,
    mo,
    ncols_widget,
    plot_grid,
    plot_transfer,
    plt,
    selected_measurements,
):
    _fig = plot_grid(
        hdf5_path,
        selected_measurements,
        lambda path, name, ax, direction="fwd": plot_transfer(
            path, name, direction=direction_widget.value, ax=ax
        ),
        ncols=ncols_widget.value,
        figsize_per=(4.5, 3.6),
    )
    _view = mo.as_html(_fig)
    plt.close(_fig)
    _view
    return


@app.cell(hide_code=True)
def _(
    df_metrics,
    hdf5_path,
    mo,
    ncols_widget,
    plot_transfer_linearized,
    plt,
):
    _n = len(df_metrics)
    _ncols = ncols_widget.value
    _nrows = (_n + _ncols - 1) // _ncols
    _fig, _axes = plt.subplots(
        _nrows,
        _ncols,
        figsize=(4.5 * _ncols, 3.6 * _nrows),
        squeeze=False,
    )
    for _ax, (_, _row) in zip(_axes.ravel(), df_metrics.iterrows()):
        plot_transfer_linearized(
            hdf5_path,
            _row["measurement"],
            _row["v_min (V)"],
            _row["v_max (V)"],
            ax=_ax,
        )
    for _ax in _axes.ravel()[_n:]:
        _ax.set_visible(False)
    _fig.suptitle(
        "Linealización $\\sqrt{|I_{DS}|}$ y ventana elegida",
        fontsize=13,
        fontweight="bold",
    )
    _fig.tight_layout(rect=[0, 0, 1, 0.97])
    _view = mo.as_html(_fig)
    plt.close(_fig)
    _view
    return


@app.cell(hide_code=True)
def _(df_metrics, mo):
    mo.ui.table(
        df_metrics,
        pagination=False,
        selection=None,
        show_download=False,
        format_mapping={
            "V_DS (V)": "{:.3f}",
            "V_th (V)": "{:.3f}",
            "v_min (V)": "{:.2f}",
            "v_max (V)": "{:.2f}",
            "R^2": "{:.4f}",
            "SS (V/dec)": "{:.3f}",
            "I_on (A)": "{:.3e}",
            "I_off (A)": "{:.3e}",
            "I_on/I_off": "{:.1f}",
            "gm_max (A/V)": "{:.3e}",
            "V_GS_gm (V)": "{:.3f}",
        },
        label="Resultados por medición",
    )
    return


@app.cell(hide_code=True)
def _(Path, df_metrics, file_widget, mo):
    mo.download(
        data=lambda: df_metrics.to_csv(index=False),
        filename=f"transfer_metrics_{Path(file_widget.value).stem}.csv",
        mimetype="text/csv",
        label="Descargar resultados (CSV)",
    )
    return


@app.cell(hide_code=True)
def _(
    exclude_widget,
    file_widget,
    mo,
    selected_measurements,
    transfer_measurements,
    vmax_widget,
    vmin_widget,
):
    _excluded = ", ".join(exclude_widget.value) if exclude_widget.value else "—"
    mo.md(f"""
    ---

    **Configuración de la corrida**

    | Parámetro | Valor |
    |---|---|
    | Archivo | `{file_widget.value}` |
    | Mediciones de transfer | {len(transfer_measurements)} |
    | Mediciones incluidas | {len(selected_measurements)} |
    | Mediciones excluidas | {_excluded} |
    | Ventana $V_{{min}}$ | {vmin_widget.value[0]:.2f} a {vmin_widget.value[1]:.2f} V |
    | Ventana $V_{{max}}$ | {vmax_widget.value[0]:.2f} a {vmax_widget.value[1]:.2f} V |
    """)
    return


if __name__ == "__main__":
    app.run()
