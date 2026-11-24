# /// script
# [tool.marimo.opengraph]
# title = "Calibration curve"
# description = "Calibration curve report: response vs concentration and batch fit."
# ///

import marimo

__generated_with = "0.23.5"
app = marimo.App(
    width="full",
    app_title="EGOFET — Calibration curve",
    layout_file="layouts/03_calibration_report.slides.json",
)


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

    from src.calibration import (
        MIN_POINTS,
        V_WINDOW_SIDE,
        calibration_frame,
        calibration_measurements,
        extract_reading,
        fit_calibration,
        get_batch_name,
        gm_summary,
        gm_table,
        i_ds_window_mean,
        parse_measurement_name,
        pick_v_read,
        window_bounds,
    )
    from src.readers.keithley_dean import list_measurements, read_all_curves
    from src.plotting import plot_grid, plot_transfer, plot_transfer_vread

    data_folder = _PROJECT_ROOT / "data" / "raw"
    hdf5_files = sorted(p.name for p in data_folder.glob("*.hdf5"))

    default_file = "calibration_curve_example.hdf5"
    if default_file not in hdf5_files:
        default_file = hdf5_files[0] if hdf5_files else None
    return (
        MIN_POINTS,
        V_WINDOW_SIDE,
        calibration_frame,
        calibration_measurements,
        data_folder,
        default_file,
        extract_reading,
        fit_calibration,
        get_batch_name,
        gm_summary,
        gm_table,
        hdf5_files,
        i_ds_window_mean,
        list_measurements,
        parse_measurement_name,
        pick_v_read,
        plot_grid,
        plot_transfer,
        plot_transfer_vread,
        read_all_curves,
        window_bounds,
    )


@app.cell(hide_code=True)
def _(data_folder, default_file, hdf5_files, mo):
    mo.stop(
        not hdf5_files,
        mo.callout(
            mo.md(f"No se encontraron archivos `.hdf5` en `{data_folder}`"),
            kind="warn",
        ),
    )

    file_widget = mo.ui.dropdown(
        options=hdf5_files,
        value=default_file,
        label="Selecciona archivo HDF5",
        searchable=True,
        full_width=True,
    )

    mo.vstack(
        [
            mo.md('''# Curva de calibración — EGOFET

    Reporte de la calibración de un archivo HDF5: $V_{READ}$ por
    transconductancia, respuesta normalizada $R$ y ajuste lineal-log por
    dispositivo y por batch.

    Seleccionar el archivo y, si hace falta, es posible excluir dispositivos
    desde **Opciones**. Las tablas se pueden descargar como CSV al final de la
    presentación.'''),
            file_widget,
        ],
        gap=1,
    )
    return (file_widget,)


@app.cell(hide_code=True)
def _(
    calibration_measurements,
    data_folder,
    file_widget,
    get_batch_name,
    list_measurements,
    mo,
    parse_measurement_name,
):
    hdf5_path = data_folder / file_widget.value
    measurements = list_measurements(hdf5_path)
    calibration, baseline = calibration_measurements(measurements)
    batches = sorted({get_batch_name(m) for m in calibration})
    devices = sorted({parse_measurement_name(m)[0] for m in calibration})

    # Validaciones. Buscar mediciones según nombre de medición y batch.
    # Se espera un solo batch por archivo.
    _issues = []
    if not calibration:
        _issues.append(
            "No se encontraron mediciones de calibración "
            "(`DnBm_<Ref|E-XX>_<sufijo>`)."
        )
    if len(batches) != 1:
        _issues.append(
            "Este reporte espera un solo batch por archivo; "
            f"hay {', '.join(batches) if batches else 'ninguno'}."
        )
    mo.stop(bool(_issues), mo.callout(mo.md("  \n".join(_issues)), kind="warn"))

    BATCH = batches[0]
    return BATCH, baseline, calibration, devices, hdf5_path


@app.cell(hide_code=True)
def _(
    BATCH,
    calibration,
    devices,
    file_widget,
    hdf5_path,
    mo,
    plot_grid,
    plot_transfer,
    plt,
):
    exclude_widget = mo.ui.multiselect(
        options=devices,
        value=[],
        label="Dispositivos excluidos",
        full_width=True,
    )
    ncols_widget = mo.ui.slider(
        start=1,
        stop=4,
        step=1,
        value=4,
        label="Columnas de la grilla",
        show_value=True,
    )
    window_widget = mo.ui.slider(
        start=0.01,
        stop=0.20,
        step=0.01,
        value=0.05,
        label="Ancho de ventana (V)",
        show_value=True,
    )

    _fig = plot_grid(
        hdf5_path,
        calibration,
        plot_transfer,
        ncols=4,
        figsize_per=(4.0, 3.2),
        title_suffix="Transfers de calibración (forward)",
    )
    _view_fig = mo.as_html(_fig)
    plt.close(_fig)

    mo.vstack(
        [
            mo.md(
                f"**Archivo:** `{file_widget.value}` · "
                f"**Batch:** {BATCH} · **Mediciones:** {len(calibration)}"
                f" · **Dispositivos:** {len(devices)}"
            ),
            mo.hstack(
                [exclude_widget, ncols_widget],
                justify="start",
                align="end",
                gap=1,
                wrap=True,
            ),
            _view_fig,
        ],
        gap=1,
    )
    return exclude_widget, window_widget


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Transconductancia y $V_{READ}$

    La transconductancia es la derivada de la corriente respecto de la tensión
    de gate:

    $$g_m = \frac{\partial I_{DS}}{\partial V_{GS}}$$

    Se calcula sobre la rama de ida de cada réplica. El punto de lectura
    $V_{READ}$ es la mediana del $V_{GS}$ donde $|g_m|$ es máxima, redondeada
    a 0.01 V. Usar un único $V_{READ}$ por batch hace comparables todas las
    mediciones de la calibración.
    """)
    return


@app.cell(hide_code=True)
def _(
    calibration,
    extract_reading,
    gm_summary,
    gm_table,
    hdf5_path,
    mo,
    pick_v_read,
):
    df_gm = gm_table(hdf5_path, calibration)
    df_gm_summary = gm_summary(df_gm)
    V_READ = pick_v_read(df_gm)

    mo.stop(
        V_READ != V_READ,
        mo.callout(
            mo.md("No se pudo determinar $V_{READ}$ con las curvas disponibles."),
            kind="warn",
        ),
    )

    # Lectura en un punto: un I_DS interpolado por réplica y normalizado
    # contra la Ref del mismo dispositivo.
    df_pts = extract_reading(hdf5_path, calibration, V_READ, method="point")
    missing_ref = sorted(
        set(df_pts["device"])
        - set(df_pts.loc[df_pts["condition"] == "Ref", "device"])
    )

    mo.ui.table(
        df_gm_summary,
        selection=None,
        pagination=False,
        show_download=False,
        format_mapping={"v_read": "{:.3f}", "gm_max": "{:.2e}"},
        label="$V_{GS}$ y $g_m$ máximos por medición",
    )
    return V_READ, df_pts, missing_ref


@app.cell(hide_code=True)
def _(V_READ, mo):
    mo.md(rf"""
    ## A) Lectura en un punto

    La forma más directa de construir la respuesta es interpolar la corriente
    en un único $V_{{GS}}$:

    $$I_{{DS}}(V_{{READ}})$$

    Para cada medición se promedian las réplicas y se normaliza contra la
    medición `Ref` del **mismo dispositivo**:

    $$R = \frac{{I_{{DS}} - I_{{DS,0}}}}{{I_{{DS,0}}}}$$

    En este archivo, $V_{{READ}} = {V_READ:.2f}$ V. Esta lectura es simple y
    directa, pero depende de un solo punto: si ese punto tiene ruido, el valor
    extraído también lo tiene. La sección siguiente muestra cómo reducirlo
    promediando una ventana de puntos.
    """)
    return


@app.cell(hide_code=True)
def _(
    BATCH,
    V_READ,
    calibration,
    hdf5_path,
    mo,
    plot_grid,
    plot_transfer_vread,
    plt,
):
    _fig = plot_grid(
        hdf5_path,
        calibration,
        lambda path, name, ax, direction="fwd": plot_transfer_vread(
            path, name, V_READ, ax=ax, direction=direction
        ),
        ncols=4,
        figsize_per=(4.0, 3.2),
        title_suffix=(
            f"{BATCH} — transfers con lectura en "
            f"$V_{{READ}}={V_READ:.2f}$ V"
        ),
    )
    _view = mo.as_html(_fig)
    plt.close(_fig)
    _view
    return


@app.cell(hide_code=True)
def _(V_READ, mo):
    mo.md(rf"""
    ## B) Ventana de puntos

    En lugar de un único valor, se promedian $N$ puntos de $I_{{DS}}$ en una
    ventana de ancho $w$ alrededor de $V_{{READ}}$:

    $$\bar I_{{DS}}(V_{{READ}};w) = \frac{{1}}{{N}}
    \sum_{{V_{{GS}}\in W}} I_{{DS}}(V_{{GS}})$$

    La ventana se elige **hacia el interior del barrido**:

    - si $V_{{READ}}$ cae en el borde inferior:
      $W = [V_{{READ}},\, V_{{READ}}+w]$;
    - si cae en el borde superior:
      $W = [V_{{READ}}-w,\, V_{{READ}}]$.

    En este archivo, $V_{{READ}} = {V_READ:.2f}$ V. La respuesta normalizada
    se calcula con la corriente media de la ventana:

    $$R_w = \frac{{\bar I_{{DS}} - \bar I_{{DS,0}}}}
    {{\bar I_{{DS,0}}}}$$

    Promediar varios puntos reduce la sensibilidad al ruido de una sola
    lectura. El ancho $w$ es un compromiso: una ventana grande promedia más,
    pero puede mezclar puntos fuera de la zona de interés. El slider controla
    $w$; las líneas punteadas de la figura marcan $V_{{READ}}$ y los bordes de
    la ventana.
    """)
    return


@app.cell(hide_code=True)
def _(
    BATCH,
    MIN_POINTS,
    V_READ,
    V_WINDOW_SIDE,
    calibration,
    hdf5_path,
    mo,
    plot_grid,
    plot_transfer_vread,
    plt,
    read_all_curves,
    window_bounds,
    window_widget,
):
    _curves = [
        c
        for c in read_all_curves(hdf5_path, calibration[0], direction="fwd")
        if len(c["v_gs"]) >= MIN_POINTS
    ]
    mo.stop(
        not _curves,
        mo.callout(
            mo.md("No hay curvas válidas para mostrar la ventana."),
            kind="warn",
        ),
    )
    _curve = max(_curves, key=lambda c: abs(float(c["v_ds"][0])))
    _lo, _hi = window_bounds(
        _curve["v_gs"], V_READ, window_widget.value, V_WINDOW_SIDE
    )

    def _plot_window(path, name, ax, direction="fwd"):
        plot_transfer_vread(path, name, V_READ, ax=ax, direction=direction)
        ax.axvline(_lo, color="0.35", ls="--", lw=0.9)
        ax.axvline(_hi, color="0.35", ls="--", lw=0.9)
        return ax

    _fig = plot_grid(
        hdf5_path,
        calibration,
        _plot_window,
        ncols=4,
        figsize_per=(4.0, 3.2),
        title_suffix=(
            f"{BATCH} — transfers con ventana de lectura "
            f"$w={window_widget.value:.2f}$ V"
        ),
    )
    _view = mo.as_html(_fig)
    plt.close(_fig)
    _view
    return


@app.cell(hide_code=True)
def _(
    MIN_POINTS,
    V_READ,
    V_WINDOW_SIDE,
    calibration,
    extract_reading,
    hdf5_path,
    i_ds_window_mean,
    mo,
    np,
    plt,
    read_all_curves,
    window_bounds,
    window_widget,
):
    _measurement = calibration[0]
    _curves = [
        c
        for c in read_all_curves(hdf5_path, _measurement, direction="fwd")
        if len(c["v_gs"]) >= MIN_POINTS
    ]
    mo.stop(
        not _curves,
        mo.callout(
            mo.md("No hay curvas válidas para mostrar la ventana."),
            kind="warn",
        ),
    )
    _curve = max(_curves, key=lambda c: abs(float(c["v_ds"][0])))
    _lo, _hi = window_bounds(
        _curve["v_gs"], V_READ, window_widget.value, V_WINDOW_SIDE
    )

    _fig, _ax = plt.subplots(figsize=(8.8, 4.3))
    for _k, _c in enumerate(_curves):
        _ax.plot(
            _c["v_gs"],
            _c["i_ds"] * 1e9,
            "o-",
            ms=2.5,
            lw=0.8,
            alpha=0.45,
            color=f"C{_k}",
            label=f"réplica {_k + 1}",
        )

    _means = [
        i_ds_window_mean(
            _c["v_gs"],
            _c["i_ds"],
            V_READ,
            window_widget.value,
            V_WINDOW_SIDE,
        )
        for _c in _curves
    ]
    _mean = float(np.nanmean(_means)) if _means else float("nan")
    _n_window = int(
        ((_curve["v_gs"] >= _lo) & (_curve["v_gs"] <= _hi)).sum()
    )

    _ax.axvline(_lo, color="0.35", ls="--", lw=1.0)
    _ax.axvline(
        _hi,
        color="0.35",
        ls="--",
        lw=1.0,
        label=f"ventana $w={window_widget.value:.2f}$ V",
    )
    _ax.axvline(
        V_READ,
        color="C3",
        ls="--",
        lw=1.4,
        label=f"$V_{{READ}}={V_READ:.2f}$ V",
    )
    if np.isfinite(_mean):
        _ax.hlines(
            _mean * 1e9,
            _lo,
            _hi,
            color="C2",
            ls="--",
            lw=1.6,
            label="media de la ventana",
        )
        _ax.plot(V_READ, _mean * 1e9, "D", color="C2", ms=5)

    _ax.set_xlabel(r"$V_{GS}$ (V)")
    _ax.set_ylabel(r"$I_{DS}$ (nA)")
    _ax.set_title(
        f"Ventana de lectura — {_measurement}", fontsize=11
    )
    _ax.grid(True, alpha=0.3)
    _ax.legend(fontsize=8)

    df_win = extract_reading(
        hdf5_path,
        calibration,
        V_READ,
        method="window",
        window=window_widget.value,
        side=V_WINDOW_SIDE,
    )

    mo.vstack(
        [
            window_widget,
            mo.as_html(_fig),
            mo.md(f"$N = {_n_window}$ puntos por réplica dentro de la ventana."),
        ],
        gap=1,
    )
    plt.close(_fig)
    return (df_win,)


@app.cell(hide_code=True)
def _(df_pts, df_win, exclude_widget, fit_calibration, mo, pd):
    df_fits, df_batch = fit_calibration(
        df_pts, df_win, exclude=exclude_widget.value
    )

    if df_batch.empty:
        _view = mo.callout(
            mo.md("No hay curva de batch con la selección actual."), kind="warn"
        )
    else:
        _pt = df_batch[df_batch["metodo"] == "Punto único"].sort_values("logC")
        _win = df_batch[df_batch["metodo"] == "Ventana"].sort_values("logC")
        _merged = _pt[
            ["condition", "conc", "n_devices", "R_mean", "R_sd"]
        ].merge(
            _win[["condition", "R_mean", "R_sd"]],
            on="condition",
            suffixes=("_pt", "_win"),
        )
        _compact = pd.DataFrame(
            {
                "Condición": _merged["condition"],
                "C (M)": _merged["conc"],
                "N disp.": _merged["n_devices"],
                "R punto": _merged["R_mean_pt"],
                "SD punto": _merged["R_sd_pt"],
                "R ventana": _merged["R_mean_win"],
                "SD ventana": _merged["R_sd_win"],
                "ΔR": _merged["R_mean_win"] - _merged["R_mean_pt"],
            }
        )
        _view = mo.vstack(
            [
                mo.md(
                    "### Comparación de métodos\n\n"
                    "Respuesta normalizada por condición: punto único vs "
                    "ventana. Las curvas completas se muestran al final."
                ),
                mo.ui.table(
                    _compact,
                    selection=None,
                    pagination=False,
                    show_download=False,
                    format_mapping={
                        "C (M)": "{:.1e}",
                        "R punto": "{:+.3f}",
                        "SD punto": "{:.3f}",
                        "R ventana": "{:+.3f}",
                        "SD ventana": "{:.3f}",
                        "ΔR": "{:+.3f}",
                    },
                    label="Respuesta normalizada por condición",
                ),
            ],
            gap=1,
        )
    _view
    return df_batch, df_fits


@app.cell(hide_code=True)
def _(
    BATCH,
    V_READ,
    calibration_frame,
    devices,
    df_batch,
    df_fits,
    df_pts,
    df_win,
    exclude_widget,
    missing_ref,
    mo,
    np,
    plt,
):
    _batch = df_fits[df_fits["nivel"] == "Batch"]

    def _fit_row(method):
        _row = _batch[_batch["metodo"] == method]
        return _row.iloc[0] if not _row.empty else None

    _pt = _fit_row("Punto único")
    _win = _fit_row("Ventana")
    _b_pt = f"{_pt['b']:+.4f}" if _pt is not None else "—"
    _r2_pt = f"{_pt['R2']:.3f}" if _pt is not None else "—"
    _b_win = f"{_win['b']:+.4f}" if _win is not None else "—"
    _r2_win = f"{_win['R2']:.3f}" if _win is not None else "—"

    _stats = mo.hstack(
        [
            mo.stat(BATCH, label="Batch", bordered=True),
            mo.stat(str(len(devices)), label="Dispositivos", bordered=True),
            mo.stat(f"{V_READ:.2f} V", label="V_READ", bordered=True),
            mo.stat(_b_pt, label="b punto único", bordered=True),
            mo.stat(_r2_pt, label="R² punto único", bordered=True),
            mo.stat(_b_win, label="b ventana", bordered=True),
            mo.stat(_r2_win, label="R² ventana", bordered=True),
        ],
        justify="start",
        wrap=True,
        gap=1,
    )

    _cal_pt = calibration_frame(df_pts, exclude_widget.value)
    _cal_win = calibration_frame(df_win, exclude_widget.value)

    if _cal_pt.empty and _cal_win.empty:
        _curves_view = mo.callout(
            mo.md("No hay dispositivos para graficar con la selección actual."),
            kind="warn",
        )
    else:
        _fig, _axes = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True)
        for _ax, (_method, _cal) in zip(
            _axes,
            [("Punto único", _cal_pt), ("Ventana", _cal_win)],
        ):
            for _k, (_device, _group) in enumerate(_cal.groupby("device")):
                _ax.plot(
                    _group["logC"],
                    _group["R"],
                    "o-",
                    ms=3,
                    lw=0.8,
                    alpha=0.35,
                    color=plt.cm.tab10(_k),
                    label=f"{_device} (dispositivo)",
                )

            _batch_method = df_batch[df_batch["metodo"] == _method]
            if not _batch_method.empty:
                _ax.errorbar(
                    _batch_method["logC"],
                    _batch_method["R_mean"],
                    yerr=_batch_method["R_sd"],
                    fmt="s",
                    ms=7,
                    color="k",
                    capsize=4,
                    zorder=4,
                    label="batch: media ± SD",
                )
                _coef = np.polyfit(
                    _batch_method["logC"], _batch_method["R_mean"], 1
                )
                _xs = np.linspace(
                    _batch_method["logC"].min(),
                    _batch_method["logC"].max(),
                    100,
                )
                _ax.plot(
                    _xs,
                    np.polyval(_coef, _xs),
                    "--",
                    color="C3",
                    lw=1.6,
                    label=f"ajuste batch: b={_coef[0]:+.3f}",
                )

            _ax.axhline(0, color="gray", ls=":", lw=0.8)
            _ax.set_xlabel(r"$\log_{10}(C\ /\mathrm{M})$")
            _ax.set_title(_method)
            _ax.grid(True, alpha=0.3)
            if _ax.get_legend_handles_labels()[0]:
                _ax.legend(fontsize=8)

        _axes[0].set_ylabel(r"$R = (I_{DS} - I_{DS,0}) / I_{DS,0}$")
        _fig.suptitle(
            "Curva de calibración — "
            f"$V_{{READ}}={V_READ:.2f}$ V"
        )
        _fig.tight_layout()
        _curves_view = mo.as_html(_fig)
        plt.close(_fig)

    if missing_ref:
        _warning = mo.callout(
            mo.md(
                f"Sin `Ref`: {', '.join(missing_ref)}. "
                "Esos dispositivos quedan fuera de la normalización."
            ),
            kind="warn",
        )
    else:
        _warning = mo.md("")

    mo.vstack(
        [
            mo.md("## 4. Resultados finales"),
            _stats,
            _curves_view,
            _warning,
        ],
        gap=1,
    )
    return


@app.cell(hide_code=True)
def _(
    BATCH,
    MIN_POINTS,
    Path,
    V_READ,
    V_WINDOW_SIDE,
    baseline,
    calibration,
    df_batch,
    df_fits,
    exclude_widget,
    file_widget,
    mo,
    window_widget,
):
    _parts = []
    _stem = Path(file_widget.value).stem
    if not df_fits.empty:
        _parts.append(
            mo.download(
                data=lambda: df_fits.to_csv(index=False),
                filename=f"calibration_fits_{_stem}.csv",
                mimetype="text/csv",
                label="Descargar ajustes (CSV)",
            )
        )
    if not df_batch.empty:
        _parts.append(
            mo.download(
                data=lambda: df_batch.to_csv(index=False),
                filename=f"calibration_batch_{_stem}.csv",
                mimetype="text/csv",
                label="Descargar curva del batch (CSV)",
            )
        )

    _excluded = ", ".join(exclude_widget.value) if exclude_widget.value else "ninguno"
    _config = mo.md(f"""
    ### Configuración de la corrida

    | Parámetro | Valor |
    |---|---|
    | Archivo | `{file_widget.value}` |
    | Batch | {BATCH} |
    | Mediciones de calibración | {len(calibration)} |
    | Mediciones fuera del patrón | {len(baseline)} |
    | Dispositivos excluidos | {_excluded} |
    | $V_{{READ}}$ | {V_READ:.2f} V |
    | Ventana | {window_widget.value:.2f} V ({V_WINDOW_SIDE}) |
    | Mínimo de puntos por curva | {MIN_POINTS} |
    """)

    if _parts:
        _downloads = mo.hstack(
            _parts, justify="start", wrap=True, gap=1
        )
    else:
        _downloads = mo.md("_No hay resultados para descargar._")

    mo.vstack([_config, _downloads], gap=1)
    return


if __name__ == "__main__":
    app.run()
