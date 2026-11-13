# /// script
# [tool.marimo.opengraph]
# title = "Output curves"
# description = "Output curve report with on-resistance, linear transconductance, and saturation current."
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="full", app_title="EGOFET — Output curves")


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

    from src.analysis import extract_output_metrics
    from src.plotting import plot_grid, plot_output
    from src.readers.keithley_dean import list_measurements, read_all_curves

    data_folder = _PROJECT_ROOT / "data" / "raw"
    hdf5_files = sorted(p.name for p in data_folder.glob("*.hdf5"))

    default_file = "transf-outp_example.hdf5"
    if default_file not in hdf5_files:
        default_file = hdf5_files[0] if hdf5_files else None
    return (
        data_folder,
        default_file,
        extract_output_metrics,
        hdf5_files,
        list_measurements,
        plot_grid,
        plot_output,
        read_all_curves,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Curvas de output — EGOFET

    Reporte de las mediciones $I_{DS}$ vs $V_{DS}$ a $V_{GS}$ constante. Para
    cada curva se calculan, sobre la rama de ida:

    - $g_{lin}$ y $R_{on}$ en la región lineal ($|V_{DS}|$ pequeño).
    - $I_{sat}$ al final del barrido.
    - $g_m = dI_{sat}/dV_{GS}$ para cada medición.

    Todos los parámetros son data-driven: no requieren geometría del dispositivo.
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
    output_measurements = [
        m["name"] for m in list_measurements(hdf5_path) if m["mode"] == "output"
    ]
    mo.stop(
        not output_measurements,
        mo.callout(
            mo.md("Este archivo no tiene mediciones de tipo `output`."),
            kind="warn",
        ),
    )
    return hdf5_path, output_measurements


@app.cell(hide_code=True)
def _(mo, output_measurements):
    highlight_widget = mo.ui.dropdown(
        options=output_measurements,
        value=output_measurements[0],
        label="Medición destacada",
        searchable=True,
        full_width=True,
    )
    exclude_widget = mo.ui.multiselect(
        options=output_measurements,
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
    linear_widget = mo.ui.slider(
        start=0.02,
        stop=0.30,
        step=0.01,
        value=0.10,
        label=r"Límite lineal $|V_{DS}|$ (V)",
        show_value=True,
        debounce=True,
    )

    mo.accordion(
        {
            "Opciones": mo.vstack(
                [
                    mo.hstack([highlight_widget], wrap=True),
                    exclude_widget,
                    mo.hstack(
                        [ncols_widget, linear_widget],
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
        exclude_widget,
        highlight_widget,
        linear_widget,
        ncols_widget,
    )


@app.cell(hide_code=True)
def _(exclude_widget, mo, output_measurements):
    selected_measurements = [
        m for m in output_measurements if m not in exclude_widget.value
    ]
    mo.md(
        f"**{len(selected_measurements)}** de **{len(output_measurements)}** "
        "mediciones de output seleccionadas."
    )
    return (selected_measurements,)


@app.cell(hide_code=True)
def _(
    extract_output_metrics,
    hdf5_path,
    linear_widget,
    mo,
    selected_measurements,
):
    mo.stop(
        not selected_measurements,
        mo.callout(mo.md("No hay mediciones seleccionadas."), kind="warn"),
    )
    df_curves, df_summary = extract_output_metrics(
        hdf5_path,
        selected_measurements,
        linear_limit=linear_widget.value,
    )
    mo.stop(
        df_summary.empty,
        mo.callout(
            mo.md("No se pudieron calcular métricas con la selección actual."),
            kind="warn",
        ),
    )
    return df_curves, df_summary


@app.cell(hide_code=True)
def _(df_curves, df_summary, mo):
    _ron = df_summary["R_on_min (ohm)"].min()
    _gm = df_summary["gm_max (A/V)"].max()
    mo.hstack(
        [
            mo.stat(str(len(df_summary)), label="Mediciones", bordered=True),
            mo.stat(str(len(df_curves)), label="Curvas", bordered=True),
            mo.stat(
                f"{df_summary['I_sat_max (A)'].max():.3e} A",
                label="I_sat máxima",
                bordered=True,
            ),
            mo.stat(
                f"{df_summary['g_lin_max (S)'].max():.3e} S",
                label="g_lin máxima",
                bordered=True,
            ),
            mo.stat(
                f"{_ron:.3e} Ω" if _ron == _ron else "—",
                label="R_on mínima",
                bordered=True,
            ),
            mo.stat(
                f"{_gm:.3e} A/V" if _gm == _gm else "—",
                label="g_m máxima",
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
    hdf5_path,
    linear_widget,
    mo,
    ncols_widget,
    plot_grid,
    plot_output,
    plt,
    selected_measurements,
):
    _fig = plot_grid(
        hdf5_path,
        selected_measurements,
        plot_output,
        ncols=ncols_widget.value,
        figsize_per=(4.5, 3.6),
    )
    for _ax in _fig.axes:
        _ax.axvspan(
            -linear_widget.value,
            linear_widget.value,
            color="C1",
            alpha=0.12,
            zorder=0,
        )
    _fig.suptitle("Curvas de output — región lineal sombreada", fontsize=13)
    _fig.tight_layout(rect=[0, 0, 1, 0.97])
    _view = mo.as_html(_fig)
    plt.close(_fig)
    _view
    return


@app.cell(hide_code=True)
def _(
    df_curves,
    df_summary,
    highlight_widget,
    hdf5_path,
    linear_widget,
    mo,
    np,
    plt,
    read_all_curves,
):
    _curves = read_all_curves(hdf5_path, highlight_widget.value)
    _metrics = df_curves[df_curves["measurement"] == highlight_widget.value]
    _summary = df_summary[df_summary["measurement"] == highlight_widget.value]

    if not _curves or _metrics.empty:
        _view = mo.callout(
            mo.md("No hay datos para la medición destacada."), kind="warn"
        )
    else:
        _fig, (_ax1, _ax2) = plt.subplots(1, 2, figsize=(12, 4.4))

        for _curve in _curves:
            _v_gs = float(_curve["v_gs"][0])
            _ax1.plot(
                _curve["v_ds"],
                _curve["i_ds"],
                "o-",
                ms=2.5,
                lw=1,
                label=f"$V_{{GS}}$={_v_gs:+.2f} V",
            )
        _ax1.axvspan(
            -linear_widget.value,
            linear_widget.value,
            color="C1",
            alpha=0.15,
            zorder=0,
        )
        _ax1.set_xlabel(r"$V_{DS}$ (V)")
        _ax1.set_ylabel(r"$I_{DS}$ (A)")
        _ax1.set_title(f"Output — {highlight_widget.value}", fontsize=10)
        _ax1.grid(True, alpha=0.3)
        _ax1.legend(fontsize=7, title=r"$V_{GS}$")

        _ordered = _metrics.sort_values("V_GS (V)")
        _ax2.plot(
            _ordered["V_GS (V)"],
            _ordered["I_sat (A)"],
            "o-",
            color="C0",
            label=r"$I_{sat}$",
        )
        _ax2.set_xlabel(r"$V_{GS}$ (V)")
        _ax2.set_ylabel(r"$I_{sat}$ (A)", color="C0")
        _ax2.grid(True, alpha=0.3)

        _ax3 = _ax2.twinx()
        _gm = np.gradient(
            _ordered["I_sat (A)"].to_numpy(dtype=float),
            _ordered["V_GS (V)"].to_numpy(dtype=float),
        )
        _ax3.plot(
            _ordered["V_GS (V)"],
            _gm,
            "s--",
            color="C3",
            label=r"$g_m$",
        )
        _ax3.set_ylabel(r"$g_m$ (A/V)", color="C3")
        _ax2.set_title("Corriente de saturación y transconductancia", fontsize=10)

        _fig.tight_layout()
        _stats = (
            f"**g_lin = {_summary['g_lin_max (S)'].iloc[0]:.3e} S**, "
            f"**R_on = {_summary['R_on_min (ohm)'].iloc[0]:.3e} Ω**, "
            f"**g_m = {_summary['gm_max (A/V)'].iloc[0]:.3e} A/V**"
            if not _summary.empty
            else ""
        )
        _view = mo.vstack([mo.as_html(_fig), mo.md(_stats)], gap=1)
        plt.close(_fig)
    _view
    return


@app.cell(hide_code=True)
def _(df_summary, mo):
    mo.ui.table(
        df_summary,
        pagination=False,
        selection=None,
        show_download=False,
        format_mapping={
            "V_GS_min (V)": "{:.3f}",
            "V_GS_max (V)": "{:.3f}",
            "I_sat_max (A)": "{:.3e}",
            "g_lin_max (S)": "{:.3e}",
            "R_on_min (ohm)": "{:.3e}",
            "gm_max (A/V)": "{:.3e}",
            "V_GS_gm (V)": "{:.3f}",
        },
        label="Resumen por medición",
    )
    return


@app.cell(hide_code=True)
def _(df_curves, df_summary, mo):
    mo.accordion(
        {
            "Métricas por curva": mo.ui.table(
                df_curves,
                pagination=True,
                page_size=12,
                selection=None,
                show_download=False,
                format_mapping={
                    "V_GS (V)": "{:.3f}",
                    "I_sat (A)": "{:.3e}",
                    "g_lin (S)": "{:.3e}",
                    "R_on (ohm)": "{:.3e}",
                    "R^2_lin": "{:.4f}",
                },
                label="Una fila por curva",
            )
        }
    )
    return


@app.cell(hide_code=True)
def _(Path, df_curves, df_summary, file_widget, mo):
    _stem = Path(file_widget.value).stem
    mo.hstack(
        [
            mo.download(
                data=lambda: df_summary.to_csv(index=False),
                filename=f"output_summary_{_stem}.csv",
                mimetype="text/csv",
                label="Descargar resumen (CSV)",
            ),
            mo.download(
                data=lambda: df_curves.to_csv(index=False),
                filename=f"output_curves_{_stem}.csv",
                mimetype="text/csv",
                label="Descargar curvas (CSV)",
            ),
        ],
        justify="start",
        wrap=True,
        gap=1,
    )
    return


@app.cell(hide_code=True)
def _(
    exclude_widget,
    file_widget,
    linear_widget,
    mo,
    output_measurements,
    selected_measurements,
):
    _excluded = ", ".join(exclude_widget.value) if exclude_widget.value else "—"
    mo.md(f"""
    ---

    **Configuración de la corrida**

    | Parámetro | Valor |
    |---|---|
    | Archivo | `{file_widget.value}` |
    | Mediciones de output | {len(output_measurements)} |
    | Mediciones incluidas | {len(selected_measurements)} |
    | Mediciones excluidas | {_excluded} |
    | Límite lineal $|V_{{DS}}|$ | {linear_widget.value:.2f} V |
    """)
    return


if __name__ == "__main__":
    app.run()
