import marimo

__generated_with = "0.25.2"
app = marimo.App(width="full", app_title="EGOFET — Transfer analysis")


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

    from src.analysis import (
        clean_forward_branch,
        extract_transfer_metrics,
        forward_gm,
    )
    from src.plotting import plot_transfer, plot_transfer_linearized
    from src.readers.keithley_dean import (
        list_measurements,
        read_all_curves,
        read_curve,
        view_measurements,
    )

    data_folder = _PROJECT_ROOT / "data" / "raw"
    hdf5_files = sorted(p.name for p in data_folder.glob("*.hdf5"))

    default_file = "transf-outp_example.hdf5"
    if default_file not in hdf5_files:
        default_file = hdf5_files[0] if hdf5_files else None
    return (
        clean_forward_branch,
        data_folder,
        default_file,
        extract_transfer_metrics,
        forward_gm,
        hdf5_files,
        list_measurements,
        plot_transfer,
        plot_transfer_linearized,
        read_all_curves,
        read_curve,
        view_measurements,
    )


@app.cell
def _(mo):
    mo.md(r"""
    # Análisis de curvas de transferencia — EGOFET

    Versión paso a paso del análisis de curvas $I_{DS}$ vs $V_{GS}$ a $V_{DS}$
    constante. El recorrido sigue el notebook `01_transfer_analysis.ipynb`:

    1. Carga y exploración de las mediciones.
    2. Regímenes de operación y linealización $\sqrt{|I_{DS}|}$.
    3. Extracción de $V_{th}$ con ventana elegida a mano.
    4. $SS$, $I_{on}/I_{off}$ y transconductancia.
    5. Comparación entre mediciones o batches.

    Esta app es para desarrollo: se abre con `marimo edit` y muestra el código.
    La versión condensada para consumidores es `03_transfer_report.py`.
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
    transfer_measurements = [
        m["name"] for m in measurements if m["mode"] == "transfer"
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
    return hdf5_path, measurements, transfer_measurements


@app.cell
def _(mo):
    mo.md(r"""
    ## 1. Curvas de transferencia

    Cada medición `transfer` contiene varias curvas, una por $V_{DS}$. La curva
    con mayor $|V_{DS}|$ es la que mejor aproxima el régimen de saturación y se
    usa para extraer $V_{th}$.
    """)
    return


@app.cell
def _(mo, transfer_measurements):
    measurement_widget = mo.ui.dropdown(
        options=transfer_measurements,
        value=transfer_measurements[0] if transfer_measurements else None,
        label="Medición a inspeccionar",
        searchable=True,
        full_width=True,
    )
    exclude_widget = mo.ui.multiselect(
        options=transfer_measurements,
        value=[],
        label="Mediciones excluidas de la comparación",
        full_width=True,
    )
    mo.vstack([measurement_widget, exclude_widget], gap=1)
    return exclude_widget, measurement_widget


@app.cell
def _(hdf5_path, measurement_widget, mo, pd, read_all_curves):
    _curves = read_all_curves(
        hdf5_path, measurement_widget.value, direction="fwd"
    )
    _rows = [
        {
            "curva": c["curve_name"],
            "V_DS (V)": float(c["v_ds"][0]),
            "V_GS mín (V)": float(min(c["v_gs"])),
            "V_GS máx (V)": float(max(c["v_gs"])),
            "puntos": len(c["v_gs"]),
        }
        for c in _curves
    ]
    df_curves = pd.DataFrame(_rows).sort_values("V_DS (V)", key=abs)
    mo.ui.table(
        df_curves,
        selection=None,
        pagination=False,
        show_download=False,
        format_mapping={
            "V_DS (V)": "{:.3f}",
            "V_GS mín (V)": "{:.3f}",
            "V_GS máx (V)": "{:.3f}",
        },
        label="Curvas de la medición seleccionada",
    )
    return (df_curves,)


@app.cell
def _(hdf5_path, measurement_widget, mo, plt, plot_transfer):
    _fig, _ax = plot_transfer(
        hdf5_path, measurement_widget.value, direction="both"
    )
    _ax.set_title(f"Transfer — {measurement_widget.value}", fontsize=11)
    _view = mo.as_html(_fig)
    plt.close(_fig)
    _view
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## 2. Regímenes de operación y linealización

    En un FET la operación se divide en dos regímenes según:

    $$|V_{DS}| \geq |V_{GS} - V_{th}| \quad \text{(saturación)}$$

    En **saturación**, y suponiendo movilidad constante, la corriente sigue la
    ley cuadrática:

    $$|I_{DS}^{sat}| = \frac{1}{2}\,\mu_{sat}\,C\,\frac{W}{L}\,(V_{GS} - V_{th})^2$$

    Tomando raíz cuadrada queda una relación **lineal**:

    $$\sqrt{|I_{DS}|} = \sqrt{\tfrac{1}{2}\mu_{sat}\,C\,\tfrac{W}{L}}\cdot(V_{GS} - V_{th})$$

    La recta tiene pendiente $m$ (relacionada con la movilidad) y cruza el eje
    $V_{GS}$ en $V_{th}$:

    $$V_{th} = -\frac{b}{m}$$

    Con $W$, $L$ en m y $C$ en F/m², la movilidad de saturación es

    $$\mu_{sat}C = \frac{2L}{W}\,m^2$$

    que se convierte a cm²/V·s multiplicando por $10^4$. Como en un EGOFET el
    dieléctrico es el medio acuoso, $C$ suele absorberse en el producto
    $\mu_{sat}C$ salvo que se mida la capacitancia de la doble capa.
    """)
    return


@app.cell
def _(
    clean_forward_branch,
    hdf5_path,
    measurement_widget,
    mo,
    np,
    plt,
    read_all_curves,
):
    _curves = read_all_curves(
        hdf5_path, measurement_widget.value, direction="fwd"
    )
    _curve = max(_curves, key=lambda c: abs(float(c["v_ds"][0])))
    v_gs_fit, i_ds_fit = clean_forward_branch(_curve["v_gs"], _curve["i_ds"])
    sqrt_ids = np.sqrt(np.abs(i_ds_fit))

    _fig, _ax = plt.subplots(figsize=(8.5, 4.6))
    _ax.plot(v_gs_fit, i_ds_fit * 1e9, "o-", ms=3, color="C0", label=r"$I_{DS}$")
    _ax.set_xlabel(r"$V_{GS}$ (V)")
    _ax.set_ylabel(r"$I_{DS}$ (nA)", color="C0")
    _ax.grid(True, alpha=0.3)

    _ax2 = _ax.twinx()
    _ax2.plot(v_gs_fit, sqrt_ids, "s-", ms=3, color="C3", label=r"$\sqrt{|I_{DS}|}$")
    _ax2.set_ylabel(r"$\sqrt{|I_{DS}|}$ ($\sqrt{A}$)", color="C3")

    _ax.set_title(
        f"{measurement_widget.value} — $V_{{DS}}={float(_curve['v_ds'][0]):.3f}$ V",
        fontsize=11,
    )
    _view = mo.as_html(_fig)
    plt.close(_fig)
    _view
    return i_ds_fit, sqrt_ids, v_gs_fit


@app.cell
def _(mo):
    mo.md(r"""
    ### Ventana de ajuste

    La ventana se elige sobre la zona donde $\sqrt{|I_{DS}|}$ es lineal. La
    segunda derivada sirve de referencia: en la región lineal
    $d^2\sqrt{|I_{DS}|}/dV_{GS}^2 \approx 0$. Movés los extremos y el ajuste se
    recalcula.
    """)
    return


@app.cell
def _(mo):
    window_widget = mo.ui.range_slider(
        start=-1.00,
        stop=0.50,
        step=0.01,
        value=[-0.40, -0.12],
        label=r"Ventana de ajuste $[V_{min}, V_{max}]$ (V)",
        show_value=True,
        debounce=True,
    )
    window_widget
    return (window_widget,)


@app.cell
def _(
    linregress,
    mo,
    np,
    plt,
    sqrt_ids,
    v_gs_fit,
    window_widget,
):
    _v_min, _v_max = window_widget.value
    _mask = (v_gs_fit >= _v_min) & (v_gs_fit <= _v_max)
    if _v_min >= _v_max or _mask.sum() < 3:
        _view = mo.callout(
            mo.md("Ventana inválida: elegí al menos 3 puntos con $V_{min}<V_{max}$."),
            kind="warn",
        )
    else:
        _result = linregress(v_gs_fit[_mask], sqrt_ids[_mask])
        _v_th = -_result.intercept / _result.slope

        _d2 = np.gradient(np.gradient(sqrt_ids, v_gs_fit), v_gs_fit)
        _fig, (_ax1, _ax2) = plt.subplots(
            2,
            1,
            figsize=(9, 6.5),
            sharex=True,
            gridspec_kw={"height_ratios": [3, 1]},
        )
        _ax1.plot(v_gs_fit, sqrt_ids, "s-", ms=3, color="C3", label=r"$\sqrt{|I_{DS}|}$")
        _x_fit = np.array([_v_min, _v_max])
        _ax1.plot(
            _x_fit,
            _result.intercept + _result.slope * _x_fit,
            "--",
            color="C2",
            lw=2,
            label=(
                f"ajuste: $V_{{th}}$={_v_th:.3f} V, "
                f"$R^2$={_result.rvalue ** 2:.4f}"
            ),
        )
        _ax1.axvline(_v_min, color="gray", ls=":", lw=0.8)
        _ax1.axvline(_v_max, color="gray", ls=":", lw=0.8)
        _ax1.set_ylabel(r"$\sqrt{|I_{DS}|}$ ($\sqrt{A}$)")
        _ax1.grid(True, alpha=0.3)
        _ax1.legend(fontsize=8)

        _ax2.plot(v_gs_fit, _d2, "b-", lw=1.2)
        _ax2.axhline(0, color="k", lw=0.5, ls="--")
        _ax2.axvspan(_v_min, _v_max, color="C1", alpha=0.15)
        _ax2.set_xlabel(r"$V_{GS}$ (V)")
        _ax2.set_ylabel(r"$d^2\sqrt{|I_{DS}|}/dV_{GS}^2$")
        _ax2.grid(True, alpha=0.3)
        _fig.tight_layout()

        _view = mo.vstack(
            [
                mo.as_html(_fig),
                mo.md(
                    f"**Resultado:** $V_{{th}}$ = {_v_th:.3f} V, "
                    f"$R^2$ = {_result.rvalue ** 2:.4f}, "
                    f"{int(_mask.sum())} puntos en la ventana."
                ),
            ],
            gap=1,
        )
        plt.close(_fig)
    _view
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## 3. Métricas de conmutación

    **Subthreshold swing.** Cuantifica qué tan rápido pasa el transistor de off
    a on:

    $$SS = \left[\frac{d(\log_{10}|I_{DS}|)}{dV_{GS}}\right]^{-1}_{\max}
    \quad \text{(V/dec)}$$

    Cuanto menor, mejor. En EGOFETs suele estar entre 0.1 y 1 V/dec.

    **Relación $I_{on}/I_{off}$.** Compara la corriente encendida con la
    apagada. En este análisis se usa el máximo y el mínimo de $|I_{DS}|$ en el
    barrido. Cuanto mayor, mejor la modulación.

    **Transconductancia.**

    $$g_m = \left.\frac{\partial I_{DS}}{\partial V_{GS}}\right|_{V_{DS}}$$

    El $V_{GS}$ de $|g_m|$ máxima es un buen punto de lectura para calibración,
    porque ahí la corriente responde más a cambios de gate.
    """)
    return


@app.cell
def _(forward_gm, hdf5_path, measurement_widget, mo, np, plt, read_all_curves):
    _curves = read_all_curves(
        hdf5_path, measurement_widget.value, direction="fwd"
    )
    _fig, _ax = plt.subplots(figsize=(8.5, 4.2))
    for _curve in _curves:
        _v, _i, _gm = forward_gm(_curve["v_gs"], _curve["i_ds"])
        if _gm.size:
            _ax.plot(
                _v,
                _gm,
                lw=1.2,
                label=f"$V_{{DS}}$={float(_curve['v_ds'][0]):.2f} V",
            )
    _ax.axhline(0, color="gray", ls=":", lw=0.8)
    _ax.set_xlabel(r"$V_{GS}$ (V)")
    _ax.set_ylabel(r"$g_m$ (A/V)")
    _ax.set_title(f"Transconductancia — {measurement_widget.value}", fontsize=11)
    _ax.grid(True, alpha=0.3)
    _ax.legend(fontsize=8, title=r"$V_{DS}$")
    _fig.tight_layout()
    _view = mo.as_html(_fig)
    plt.close(_fig)
    _view
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## 4. Comparación entre mediciones

    Para cada medición se toma la curva de mayor $|V_{DS}|$, se busca la ventana
    $(V_{min}, V_{max})$ que maximiza $R^2$ de $\sqrt{|I_{DS}|}$ y se calculan
    las métricas de conmutación. Los rangos de búsqueda se ajustan abajo; el
    resultado se congela en la tabla.
    """)
    return


@app.cell
def _(mo):
    vmin_widget = mo.ui.range_slider(
        start=-0.60,
        stop=0.00,
        step=0.01,
        value=[-0.40, -0.20],
        label=r"Rango de búsqueda — $V_{min}$ (V)",
        show_value=True,
        debounce=True,
    )
    vmax_widget = mo.ui.range_slider(
        start=-0.60,
        stop=0.00,
        step=0.01,
        value=[-0.15, -0.05],
        label=r"Rango de búsqueda — $V_{max}$ (V)",
        show_value=True,
        debounce=True,
    )
    mo.hstack([vmin_widget, vmax_widget], gap=1, wrap=True, align="end")
    return vmax_widget, vmin_widget


@app.cell
def _(
    exclude_widget,
    extract_transfer_metrics,
    hdf5_path,
    mo,
    transfer_measurements,
    vmax_widget,
    vmin_widget,
):
    _selected = [
        m for m in transfer_measurements if m not in exclude_widget.value
    ]
    mo.stop(
        not _selected,
        mo.callout(mo.md("No hay mediciones seleccionadas."), kind="warn"),
    )
    with mo.capture_stdout() as _buffer:
        df_metrics = extract_transfer_metrics(
            hdf5_path,
            _selected,
            v_min_range=tuple(vmin_widget.value),
            v_max_range=tuple(vmax_widget.value),
        )
    _log = _buffer.getvalue().strip()
    mo.stop(
        df_metrics.empty,
        mo.callout(
            mo.md(
                "No se pudo extraer $V_{th}$ de las mediciones seleccionadas. "
                "Revisá los rangos de búsqueda."
            ),
            kind="warn",
        ),
    )
    return (df_metrics,)


@app.cell
def _(df_metrics, mo):
    _ss = df_metrics["SS (V/dec)"].median()
    _ratio = df_metrics["I_on/I_off"].median()
    mo.hstack(
        [
            mo.stat(str(len(df_metrics)), label="Mediciones", bordered=True),
            mo.stat(
                f"{df_metrics['V_th (V)'].mean():.3f} V", label="V_th medio", bordered=True
            ),
            mo.stat(
                f"{df_metrics['R^2'].mean():.3f}", label="R² medio", bordered=True
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


@app.cell
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
        label="Métricas por medición",
    )
    return


@app.cell
def _(df_metrics, hdf5_path, mo, plt, plot_transfer_linearized):
    _g = df_metrics.reset_index(drop=True)
    _ncols = 3
    _nrows = (len(_g) + _ncols - 1) // _ncols
    _fig, _axes = plt.subplots(
        _nrows, _ncols, figsize=(4.6 * _ncols, 3.6 * _nrows), squeeze=False
    )
    for _ax, (_, _row) in zip(_axes.ravel(), _g.iterrows()):
        plot_transfer_linearized(
            hdf5_path,
            _row["measurement"],
            _row["v_min (V)"],
            _row["v_max (V)"],
            ax=_ax,
        )
    for _ax in _axes.ravel()[len(_g):]:
        _ax.set_visible(False)
    _fig.suptitle("Ventanas elegidas por medición", fontsize=13, fontweight="bold")
    _fig.tight_layout(rect=[0, 0, 1, 0.97])
    _view = mo.as_html(_fig)
    plt.close(_fig)
    _view
    return


@app.cell
def _(Path, df_metrics, file_widget, mo):
    mo.download(
        data=lambda: df_metrics.to_csv(index=False),
        filename=f"transfer_metrics_{Path(file_widget.value).stem}.csv",
        mimetype="text/csv",
        label="Descargar métricas (CSV)",
    )
    return


@app.cell
def _(
    exclude_widget,
    file_widget,
    mo,
    transfer_measurements,
    vmax_widget,
    vmin_widget,
):
    _excluded = ", ".join(exclude_widget.value) if exclude_widget.value else "ninguna"
    mo.md(f"""
    ---

    **Configuración de la corrida**

    | Parámetro | Valor |
    |---|---|
    | Archivo | `{file_widget.value}` |
    | Mediciones de transfer | {len(transfer_measurements)} |
    | Mediciones excluidas | {_excluded} |
    | Rango $V_{{min}}$ | {vmin_widget.value[0]:.2f} a {vmin_widget.value[1]:.2f} V |
    | Rango $V_{{max}}$ | {vmax_widget.value[0]:.2f} a {vmax_widget.value[1]:.2f} V |
    """)
    return


if __name__ == "__main__":
    app.run()
