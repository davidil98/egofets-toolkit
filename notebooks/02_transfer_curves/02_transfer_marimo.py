# /// script
# [tool.marimo.opengraph]
# title = "Transfer curves"
# description = "Interactive transfer report with V_th extraction."
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
    from scipy.stats import linregress

    return Path, linregress, mo, np, os, plt, sys


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Reporte de Transfer Curves — EGOFET

    Visualización de todas las mediciones de transfer de un archivo HDF5,
    con extracción automática de $V_{th}$ por el método $\sqrt{|I_{DS}|}$.

    Seleccionar el archivo, excluir mediciones y ajusta la ventana de extracción
    con los controles de abajo. Los resultados se pueden descargar como CSV.
    """)
    return


@app.cell(hide_code=True)
def _(Path, mo, os, sys):
    def find_project_root(marker="src"):
        cwd = Path(os.getcwd()).resolve()
        for parent in [cwd, *cwd.parents]:
            if (parent / marker).is_dir():
                return parent
        raise FileNotFoundError(f"No se encontro un directorio con '{marker}'")


    PROJECT_ROOT = find_project_root()
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from src.analysis import extract_vth_for_transfers
    from src.plotting import plot_transfer
    from src.readers.keithley_dean import (
        list_measurements,
        read_all_curves,
        read_curve,
    )

    data_folder = PROJECT_ROOT / "data" / "raw"
    hdf5_files = sorted(p.name for p in data_folder.glob("*.hdf5"))

    # Archivo que abre por defecto (si esta disponible).
    default_file = "transf-outp_example.hdf5"
    if default_file not in hdf5_files:
        default_file = hdf5_files[0] if hdf5_files else None

    file_widget = mo.ui.dropdown(
        options=hdf5_files,
        value=default_file,
        label="Archivo HDF5",
        searchable=True,
    )
    file_widget
    return (
        data_folder,
        extract_vth_for_transfers,
        file_widget,
        hdf5_files,
        list_measurements,
        plot_transfer,
        read_all_curves,
        read_curve,
    )


@app.cell(hide_code=True)
def _(data_folder, file_widget, hdf5_files, mo):
    mo.stop(
        not hdf5_files,
        mo.md(f"**No se encontraron archivos `.hdf5` en** `{data_folder}`"),
    )
    hdf5_path = data_folder / file_widget.value
    mo.md(f"`{hdf5_path}`")
    return (hdf5_path,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Mediciones
    """)
    return


@app.cell
def _(hdf5_path, list_measurements, mo):
    measurements = list_measurements(hdf5_path)
    transfer_measurements = [
        m["name"] for m in measurements if m["mode"] == "transfer"
    ]

    exclude_widget = mo.ui.multiselect(
        options=transfer_measurements,
        value=[],
        label="Excluir mediciones del análisis",
        full_width=True,
    )
    exclude_widget
    return exclude_widget, transfer_measurements


@app.cell
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
def _(mo):
    mo.md(r"""
    ## Parámetros de extracción de $V_{th}$

    La ventana $(V_{min}, V_{max})$ se busca en una grilla de 0.01 V para
    maximizar $R^2$ del ajuste lineal de $\sqrt{|I_{DS}|}$ vs $V_{GS}$
    (rama de ida).
    """)
    return


@app.cell
def _(mo):
    vmin_widget = mo.ui.range_slider(
        start=-0.60,
        stop=0.00,
        step=0.01,
        value=[-0.40, -0.38],
        label=r"Ventana de ajuste — $V_{min}$ (V)",
        show_value=True,
        debounce=True,
    )
    vmax_widget = mo.ui.range_slider(
        start=-0.60,
        stop=0.00,
        step=0.01,
        value=[-0.06, 0.00],
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
    interactive_widget = mo.ui.switch(value=False, label="Gráficos interactivos")

    mo.vstack(
        [
            vmin_widget,
            vmax_widget,
            r2_widget,
            mo.hstack([ncols_widget, direction_widget, interactive_widget]),
        ],
        gap=1,
    )
    return (
        direction_widget,
        interactive_widget,
        ncols_widget,
        r2_widget,
        vmax_widget,
        vmin_widget,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Curvas de transfer
    """)
    return


@app.cell
def _(
    direction_widget,
    hdf5_path,
    interactive_widget,
    mo,
    ncols_widget,
    plot_transfer,
    plt,
    selected_measurements,
):
    def plot_grid(
        path,
        measurement_names,
        plot_func,
        ncols=3,
        figsize_per=(5, 4),
        direction="both",
    ):
        n = len(measurement_names)
        if n == 0:
            return None
        nrows = (n + ncols - 1) // ncols
        fig, axes = plt.subplots(
            nrows,
            ncols,
            figsize=(figsize_per[0] * ncols, figsize_per[1] * nrows),
            squeeze=False,
        )
        axes_flat = axes.ravel()
        for ax, name in zip(axes_flat, measurement_names):
            plot_func(path, name, ax=ax, direction=direction)
        for ax in axes_flat[n:]:
            ax.set_visible(False)
        fig.tight_layout()
        return fig


    fig_curves = plot_grid(
        hdf5_path,
        selected_measurements,
        plot_transfer,
        ncols=ncols_widget.value,
        direction=direction_widget.value,
    )
    if fig_curves is None:
        _curves_view = mo.md("_No hay mediciones seleccionadas._")
    elif interactive_widget.value:
        _curves_view = mo.mpl.interactive(fig_curves)
    else:
        _curves_view = mo.as_html(fig_curves)
    _curves_view
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Extracción de $V_{th}$
    """)
    return


@app.cell
def _(
    extract_vth_for_transfers,
    hdf5_path,
    mo,
    selected_measurements,
    vmax_widget,
    vmin_widget,
):
    with mo.capture_stdout() as log_buffer:
        df_vth = extract_vth_for_transfers(
            hdf5_path,
            selected_measurements,
            v_min_range=tuple(vmin_widget.value),
            v_max_range=tuple(vmax_widget.value),
        )
    log = log_buffer.getvalue().strip()
    return df_vth, log


@app.cell
def _(df_vth, log, mo, r2_widget):
    parts = []
    if df_vth.empty:
        parts.append(
            mo.md(
                "_No se pudo extraer $V_{th}$ de las mediciones seleccionadas. "
                "Revisá la ventana de ajuste._"
            )
        )
    else:
        good = df_vth[df_vth["R^2"] >= r2_widget.value]
        stats = mo.hstack(
            [
                mo.stat(value=str(len(df_vth)), label="Fits", bordered=True),
                mo.stat(
                    value=str(len(good)),
                    label=f"R² ≥ {r2_widget.value:.2f}",
                    bordered=True,
                ),
                mo.stat(
                    value=(
                        f"{good['V_th (V)'].mean():.3f} V"
                        if len(good)
                        else "—"
                    ),
                    label="V_th medio (fits buenos)",
                    bordered=True,
                ),
                mo.stat(
                    value=f"{df_vth['V_th (V)'].mean():.3f} V",
                    label="V_th medio (todos)",
                    bordered=True,
                ),
            ],
            justify="start",
            wrap=True,
        )
        table = mo.ui.table(
            df_vth,
            pagination=False,
            selection=None,
            show_download=False,
            format_mapping={
                "V_DS (V)": "{:.3f}",
                "V_th (V)": "{:.3f}",
                "v_min (V)": "{:.2f}",
                "v_max (V)": "{:.2f}",
                "R^2": "{:.4f}",
            },
            label="Resultados por medición",
        )
        parts.extend([stats, table])

    if log:
        parts.append(
            mo.accordion(
                {"Mensajes de la extracción": mo.md(f"```\n{log}\n```")}
            )
        )

    mo.vstack(parts, gap=1)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Linealización de $\sqrt{|I_{DS}|}$

    Cada panel muestra la curva usada para el ajuste y la recta en la
    ventana que maximizó $R^2$.
    """)
    return


@app.cell
def _(
    df_vth,
    hdf5_path,
    interactive_widget,
    linregress,
    mo,
    ncols_widget,
    np,
    plt,
    read_all_curves,
    read_curve,
):
    def plot_linearized_grid(path, df, ncols=3, figsize_per=(5, 4)):
        n = len(df)
        if n == 0:
            return None
        nrows = (n + ncols - 1) // ncols
        fig, axes = plt.subplots(
            nrows,
            ncols,
            figsize=(figsize_per[0] * ncols, figsize_per[1] * nrows),
            squeeze=False,
        )
        axes_flat = axes.ravel()

        for ax, (_, row) in zip(axes_flat, df.iterrows()):
            name = row["measurement"]
            v_min_w = row["v_min (V)"]
            v_max_w = row["v_max (V)"]
            try:
                curves = read_all_curves(path, name)
                i_max = max(
                    range(len(curves)),
                    key=lambda i: abs(curves[i]["v_ds"][0]),
                )
                curve = curves[i_max]
                v_gs, i_ds = read_curve(
                    path, name, curve["curve_name"], direction="fwd"
                )
                sqrt_ids = np.sqrt(np.abs(i_ds))

                mask = (v_gs >= v_min_w) & (v_gs <= v_max_w)
                slope, intercept, r_value, _, _ = linregress(
                    v_gs[mask], sqrt_ids[mask]
                )
                v_th = -intercept / slope

                ax.plot(v_gs, sqrt_ids, "rs-", ms=3, label=r"$\sqrt{|I_{DS}|}$")
                x_fit = np.array([v_min_w, v_max_w])
                ax.plot(
                    x_fit,
                    slope * x_fit + intercept,
                    "g--",
                    lw=2,
                    label=f"fit ($V_{{th}}$={v_th:.3f} V, $R^2$={r_value**2:.4f})",
                )
                ax.axvline(v_min_w, color="gray", ls=":", lw=0.8)
                ax.axvline(v_max_w, color="gray", ls=":", lw=0.8)
                ax.set_xlabel(r"$V_{GS}$ (V)")
                ax.set_ylabel(r"$\sqrt{|I_{DS}|}$ ($\sqrt{A}$)")
                ax.set_title(name, fontsize=9)
                ax.legend(fontsize=7)
                ax.grid(True, alpha=0.3)
            except Exception as e:
                ax.text(
                    0.5,
                    0.5,
                    f"Error: {e}",
                    transform=ax.transAxes,
                    ha="center",
                    va="center",
                    wrap=True,
                )

        for ax in axes_flat[n:]:
            ax.set_visible(False)
        fig.tight_layout()
        return fig


    fig_linear = plot_linearized_grid(
        hdf5_path, df_vth, ncols=ncols_widget.value
    )
    if fig_linear is None:
        _linear_view = mo.md("_No hay datos de $V_{th}$ para graficar._")
    elif interactive_widget.value:
        _linear_view = mo.mpl.interactive(fig_linear)
    else:
        _linear_view = mo.as_html(fig_linear)
    _linear_view
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Exportar
    """)
    return


@app.cell
def _(Path, df_vth, file_widget, mo):
    if df_vth.empty:
        _download_view = mo.md("_No hay resultados para descargar._")
    else:
        _download_view = mo.download(
            data=lambda: df_vth.to_csv(index=False),
            filename=f"vth_{Path(file_widget.value).stem}.csv",
            mimetype="text/csv",
            label="Descargar resultados (CSV)",
        )
    _download_view
    return


@app.cell(hide_code=True)
def _(
    exclude_widget,
    file_widget,
    mo,
    selected_measurements,
    vmax_widget,
    vmin_widget,
):
    excluded = exclude_widget.value
    mo.md(f"""
    ---

    **Configuración de esta corrida**

    | Parámetro | Valor |
    |---|---|
    | Archivo | `{file_widget.value}` |
    | Mediciones incluidas | {len(selected_measurements)} |
    | Mediciones excluidas | {", ".join(excluded) if excluded else "—"} |
    | Ventana $V_{{min}}$ | {vmin_widget.value[0]:.2f} a {vmin_widget.value[1]:.2f} V |
    | Ventana $V_{{max}}$ | {vmax_widget.value[0]:.2f} a {vmax_widget.value[1]:.2f} V |
    """)
    return


if __name__ == "__main__":
    app.run()
