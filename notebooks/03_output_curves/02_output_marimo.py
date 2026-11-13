import marimo

__generated_with = "0.25.2"
app = marimo.App(width="full", app_title="EGOFET — Output analysis")


@app.cell
def _():
    import os
    import sys
    from pathlib import Path

    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    from scipy.stats import linregress

    return Path, linregress, mo, np, os, pd, plt, sys


@app.cell
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

    from src.analysis import extract_output_metrics, output_branch
    from src.plotting import plot_grid, plot_output
    from src.readers.keithley_dean import (
        list_measurements,
        read_all_curves,
        view_measurements,
    )

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
        output_branch,
        plot_grid,
        plot_output,
        read_all_curves,
        view_measurements,
    )


@app.cell
def _(mo):
    mo.md(r"""
    # Análisis de curvas de output — EGOFET

    Análisis paso a paso de curvas $I_{DS}$ vs $V_{DS}$ a $V_{GS}$ constante.
    El recorrido cubre:

    1. Regiones lineal y de saturación.
    2. Resistencia de encendido $R_{on}$ y transconductancia lineal $g_{lin}$.
    3. Corriente de saturación $I_{sat}$ y $g_m = dI_{sat}/dV_{GS}$.
    4. Comparación entre mediciones.

    Es la app de desarrollo (`marimo edit`, código visible). La versión
    condensada para consumidores es `03_output_report.py`.
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## 1. Regiones de operación

    Para $|V_{DS}|$ pequeño el canal se comporta como una resistencia
    controlada por gate (**región lineal**):

    $$I_{DS} \approx g_{lin}\,V_{DS}, \qquad R_{on} = \frac{1}{g_{lin}}$$

    Al aumentar $|V_{DS}|$ el canal se estrangula cerca del drenador y la
    corriente satura (**región de saturación**). En un EGOFET tipo p las
    corrientes son negativas; por eso se trabaja con $|I_{DS}|$.

    Estas métricas son data-driven: no necesitan $W$, $L$ ni la capacitancia
    del dieléctrico. Para reportar movilidad haría falta geometría y $C$.
    """)
    return


@app.cell
def _(data_folder, hdf5_files, mo):
    mo.stop(
        not hdf5_files,
        mo.callout(
            mo.md(f"No se encontraron archivos `.hdf5` en `{data_folder}`"),
            kind="warn",
        ),
    )
    return


@app.cell
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


@app.cell
def _(data_folder, file_widget, list_measurements, mo, pd):
    hdf5_path = data_folder / file_widget.value
    measurements = list_measurements(hdf5_path)
    output_measurements = [
        m["name"] for m in measurements if m["mode"] == "output"
    ]
    _summary = (
        pd.DataFrame(measurements)
        .groupby("mode")
        .agg(mediciones=("name", "count"), curvas=("n_curves", "sum"))
        .reset_index()
        if measurements
        else pd.DataFrame()
    )
    mo.vstack(
        [
            mo.md(f"**Archivo:** `{file_widget.value}`"),
            mo.ui.table(
                _summary,
                selection=None,
                pagination=False,
                show_download=False,
                label="Contenido del archivo por tipo de medición",
            ),
        ],
        gap=1,
    )
    return hdf5_path, measurements, output_measurements


@app.cell
def _(mo, output_measurements):
    mo.stop(
        not output_measurements,
        mo.callout(
            mo.md("Este archivo no tiene mediciones de tipo `output`."),
            kind="warn",
        ),
    )
    measurement_widget = mo.ui.dropdown(
        options=output_measurements,
        value=output_measurements[0],
        label="Medición a inspeccionar",
        searchable=True,
        full_width=True,
    )
    exclude_widget = mo.ui.multiselect(
        options=output_measurements,
        value=[],
        label="Mediciones excluidas de la comparación",
        full_width=True,
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
    mo.vstack(
        [
            measurement_widget,
            exclude_widget,
            linear_widget,
        ],
        gap=1,
    )
    return exclude_widget, linear_widget, measurement_widget


@app.cell
def _(
    hdf5_path,
    linear_widget,
    measurement_widget,
    mo,
    plot_output,
    plt,
):
    _fig, _ax = plot_output(hdf5_path, measurement_widget.value)
    _ax.axvspan(
        -linear_widget.value,
        linear_widget.value,
        color="C1",
        alpha=0.15,
        zorder=0,
        label="región lineal",
    )
    _ax.legend(fontsize=8, title=r"$V_{GS}$")
    _view = mo.as_html(_fig)
    plt.close(_fig)
    _view
    return


@app.cell
def _(hdf5_path, measurement_widget, mo, pd, read_all_curves):
    _curves = read_all_curves(hdf5_path, measurement_widget.value)
    _rows = [
        {
            "curva": c["curve_name"],
            "V_GS (V)": float(c["v_gs"][0]),
            "V_DS mín (V)": float(min(c["v_ds"])),
            "V_DS máx (V)": float(max(c["v_ds"])),
            "puntos": len(c["v_ds"]),
        }
        for c in _curves
    ]
    df_selected_curves = pd.DataFrame(_rows).sort_values("V_GS (V)")
    mo.ui.table(
        df_selected_curves,
        selection=None,
        pagination=False,
        show_download=False,
        format_mapping={
            "V_GS (V)": "{:.3f}",
            "V_DS mín (V)": "{:.3f}",
            "V_DS máx (V)": "{:.3f}",
        },
        label="Curvas de la medición seleccionada",
    )
    return (df_selected_curves,)


@app.cell
def _(mo):
    mo.md(r"""
    ## 2. Región lineal y resistencia de encendido

    Se toma la rama de ida del barrido (desde el inicio hasta el $V_{DS}$
    mínimo) y se ajusta una recta en $|V_{DS}| \le V_{lin}$. La pendiente es
    $g_{lin}$ y su inversa es $R_{on}$. El $R^2$ del ajuste indica si la región
    elegida es realmente lineal.

    Para el análisis se usa la curva con mayor $|V_{GS}|$, que es la más
    encendida y la que mejor define $R_{on}$.
    """)
    return


@app.cell
def _(
    df_selected_curves,
    hdf5_path,
    linear_widget,
    linregress,
    measurement_widget,
    mo,
    np,
    output_branch,
    plt,
    read_all_curves,
):
    _curves = read_all_curves(hdf5_path, measurement_widget.value)
    _on_state = max(_curves, key=lambda c: abs(float(c["v_gs"][0])))
    v_ds, i_ds = output_branch(_on_state["v_ds"], _on_state["i_ds"])
    _mask = np.abs(v_ds) <= linear_widget.value
    if _mask.sum() < 3:
        _view = mo.callout(
            mo.md("Muy pocos puntos en la región lineal; aumentá el límite."),
            kind="warn",
        )
    else:
        _result = linregress(v_ds[_mask], i_ds[_mask])
        _g_lin = abs(_result.slope)
        _r_on = 1.0 / _g_lin if _g_lin else float("nan")

        _fig, _ax = plt.subplots(figsize=(8.5, 4.4))
        _ax.plot(v_ds, i_ds, "o-", ms=3, color="C0", label="rama de ida")
        _xs = np.linspace(v_ds[_mask].min(), v_ds[_mask].max(), 50)
        _ax.plot(
            _xs,
            _result.intercept + _result.slope * _xs,
            "--",
            color="C2",
            lw=2,
            label="ajuste lineal",
        )
        _ax.axvspan(
            -linear_widget.value,
            linear_widget.value,
            color="C1",
            alpha=0.15,
            zorder=0,
            label="región lineal",
        )
        _ax.set_xlabel(r"$V_{DS}$ (V)")
        _ax.set_ylabel(r"$I_{DS}$ (A)")
        _ax.set_title(
            f"{measurement_widget.value} — $V_{{GS}}$={float(_on_state['v_gs'][0]):+.3f} V",
            fontsize=10,
        )
        _ax.grid(True, alpha=0.3)
        _ax.legend(fontsize=8)
        _fig.tight_layout()

        _view = mo.vstack(
            [
                mo.as_html(_fig),
                mo.md(
                    f"**$g_{{lin}}$ = {_g_lin:.3e} S**, "
                    f"**$R_{{on}}$ = {_r_on:.3e} Ω**, "
                    f"$R^2$ = {_result.rvalue ** 2:.4f}, "
                    f"{int(_mask.sum())} puntos."
                ),
            ],
            gap=1,
        )
        plt.close(_fig)
    _view
    return


@app.cell
def _(
    extract_output_metrics,
    hdf5_path,
    linear_widget,
    measurement_widget,
    mo,
):
    df_sel_curves, df_sel_summary = extract_output_metrics(
        hdf5_path,
        [measurement_widget.value],
        linear_limit=linear_widget.value,
    )
    mo.ui.table(
        df_sel_curves,
        selection=None,
        pagination=False,
        show_download=False,
        format_mapping={
            "V_GS (V)": "{:.3f}",
            "I_sat (A)": "{:.3e}",
            "g_lin (S)": "{:.3e}",
            "R_on (ohm)": "{:.3e}",
            "R^2_lin": "{:.4f}",
        },
        label="Métricas por curva — medición seleccionada",
    )
    return df_sel_curves, df_sel_summary


@app.cell
def _(
    df_sel_curves,
    measurement_widget,
    mo,
    np,
    plt,
):
    if df_sel_curves.empty:
        _view = mo.md("_No hay curvas para graficar._")
    else:
        _ordered = df_sel_curves.sort_values("V_GS (V)")
        _fig, _ax = plt.subplots(figsize=(8.5, 4.2))
        _ax.plot(
            _ordered["V_GS (V)"],
            _ordered["I_sat (A)"],
            "o-",
            color="C0",
            label=r"$I_{sat}$",
        )
        _ax.set_xlabel(r"$V_{GS}$ (V)")
        _ax.set_ylabel(r"$I_{sat}$ (A)", color="C0")
        _ax.grid(True, alpha=0.3)
        _ax2 = _ax.twinx()
        _gm = np.gradient(
            _ordered["I_sat (A)"].to_numpy(dtype=float),
            _ordered["V_GS (V)"].to_numpy(dtype=float),
        )
        _ax2.plot(_ordered["V_GS (V)"], _gm, "s--", color="C3", label=r"$g_m$")
        _ax2.set_ylabel(r"$g_m$ (A/V)", color="C3")
        _ax.set_title(
            f"$I_{{sat}}$ y $g_m$ — {measurement_widget.value}", fontsize=10
        )
        _fig.tight_layout()
        _view = mo.as_html(_fig)
        plt.close(_fig)
    _view
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## 3. Comparación entre mediciones

    Para cada medición se repiten las métricas con el mismo límite lineal. El
    resumen conserva el máximo de $g_{lin}$, el mínimo de $R_{on}$, la
    $I_{sat}$ máxima y la $g_m$ máxima.
    """)
    return


@app.cell
def _(
    exclude_widget,
    extract_output_metrics,
    hdf5_path,
    linear_widget,
    mo,
    output_measurements,
):
    _selected = [
        m for m in output_measurements if m not in exclude_widget.value
    ]
    mo.stop(
        not _selected,
        mo.callout(mo.md("No hay mediciones seleccionadas."), kind="warn"),
    )
    df_curves, df_summary = extract_output_metrics(
        hdf5_path,
        _selected,
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


@app.cell
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


@app.cell
def _(df_curves, df_summary, mo):
    mo.vstack(
        [
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
            ),
            mo.ui.table(
                df_curves,
                pagination=True,
                page_size=10,
                selection=None,
                show_download=False,
                format_mapping={
                    "V_GS (V)": "{:.3f}",
                    "I_sat (A)": "{:.3e}",
                    "g_lin (S)": "{:.3e}",
                    "R_on (ohm)": "{:.3e}",
                    "R^2_lin": "{:.4f}",
                },
                label="Métricas por curva",
            ),
        ],
        gap=1,
    )
    return


@app.cell
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


@app.cell
def _(
    exclude_widget,
    file_widget,
    linear_widget,
    mo,
    output_measurements,
):
    _excluded = ", ".join(exclude_widget.value) if exclude_widget.value else "ninguna"
    mo.md(f"""
    ---

    **Configuración de la corrida**

    | Parámetro | Valor |
    |---|---|
    | Archivo | `{file_widget.value}` |
    | Mediciones de output | {len(output_measurements)} |
    | Mediciones excluidas | {_excluded} |
    | Límite lineal $|V_{{DS}}|$ | {linear_widget.value:.2f} V |
    """)
    return


if __name__ == "__main__":
    app.run()
