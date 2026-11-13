# /// script
# [tool.marimo.opengraph]
# title = "Calibration curve"
# description = "Calibration curve report: response vs concentration and batch fit."
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="full", app_title="EGOFET — Calibration curve")


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
        parse_measurement_name,
        pick_v_read,
    )
    from src.readers.keithley_dean import list_measurements
    from src.plotting import plot_grid, plot_transfer_vread

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
        list_measurements,
        parse_measurement_name,
        pick_v_read,
        plot_grid,
        plot_transfer_vread,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Curva de calibración — EGOFET

    Reporte de la calibración de un archivo HDF5: $V_{READ}$ por
    transconductancia, respuesta normalizada $R$ y ajuste lineal-log por
    dispositivo y por batch.

    Elegí el archivo y, si hace falta, excluí dispositivos desde **Opciones**.
    Las tablas se descargan como CSV.
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
def _(calibration, devices, mo):
    exclude_widget = mo.ui.multiselect(
        options=devices,
        value=[],
        label="Dispositivos excluidos",
        full_width=True,
    )
    window_widget = mo.ui.slider(
        start=0.01,
        stop=0.20,
        step=0.01,
        value=0.05,
        label="Ancho de ventana (V)",
        show_value=True,
    )
    ncols_widget = mo.ui.slider(
        start=1,
        stop=4,
        step=1,
        value=4,
        label="Columnas de la grilla",
        show_value=True,
    )
    detail_widget = mo.ui.switch(value=False, label="Mostrar detalles de diagnóstico")

    mo.accordion(
        {
            "Opciones": mo.vstack(
                [
                    mo.hstack(
                        [exclude_widget, window_widget],
                        justify="start",
                        align="end",
                        gap=1,
                        wrap=True,
                    ),
                    mo.hstack(
                        [ncols_widget, detail_widget],
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
    mo.stop(
        len(calibration) < 1,
        mo.callout(mo.md("No hay mediciones de calibración."), kind="warn"),
    )
    return detail_widget, exclude_widget, ncols_widget, window_widget


@app.cell(hide_code=True)
def _(gm_summary, gm_table, hdf5_path, calibration, mo, pick_v_read):
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
    return V_READ, df_gm, df_gm_summary


@app.cell(hide_code=True)
def _(
    V_READ,
    V_WINDOW_SIDE,
    calibration,
    extract_reading,
    hdf5_path,
    window_widget,
):
    df_pts = extract_reading(hdf5_path, calibration, V_READ, method="point")
    df_win = extract_reading(
        hdf5_path,
        calibration,
        V_READ,
        method="window",
        window=window_widget.value,
        side=V_WINDOW_SIDE,
    )
    return df_pts, df_win


@app.cell(hide_code=True)
def _(df_pts, df_win, exclude_widget, fit_calibration):
    df_fits, df_batch = fit_calibration(
        df_pts, df_win, exclude=exclude_widget.value
    )
    return df_batch, df_fits


@app.cell(hide_code=True)
def _(df_pts, exclude_widget, mo):
    _missing = sorted(
        set(df_pts["device"]) - set(df_pts.loc[df_pts["condition"] == "Ref", "device"])
    )
    _messages = []
    if _missing:
        _messages.append(
            f"Sin `Ref`: {', '.join(_missing)}. "
            "Esos dispositivos quedan fuera de la normalización."
        )
    if exclude_widget.value:
        _messages.append(f"Dispositivos excluidos: {', '.join(exclude_widget.value)}.")
    if _messages:
        _view = mo.callout(mo.md("  \n".join(_messages)), kind="warn")
    else:
        _view = mo.md("")
    _view
    return


@app.cell(hide_code=True)
def _(BATCH, V_READ, devices, df_fits, mo):
    _batch = df_fits[df_fits["nivel"] == "Batch"]
    _window = _batch[_batch["metodo"] == "Ventana"]
    _row = (
        _window.iloc[0]
        if not _window.empty
        else (_batch.iloc[0] if not _batch.empty else None)
    )
    _b = f"{_row['b']:+.4f}" if _row is not None else "—"
    _r2 = f"{_row['R2']:.3f}" if _row is not None else "—"

    mo.hstack(
        [
            mo.stat(BATCH, label="Batch", bordered=True),
            mo.stat(str(len(devices)), label="Dispositivos", bordered=True),
            mo.stat(f"{V_READ:.2f} V", label="V_READ", bordered=True),
            mo.stat(_b, label="Sensibilidad b", bordered=True),
            mo.stat(_r2, label="R² batch", bordered=True),
        ],
        justify="start",
        wrap=True,
        gap=1,
    )
    return


@app.cell(hide_code=True)
def _(
    V_READ,
    calibration,
    df_batch,
    df_pts,
    df_win,
    exclude_widget,
    mo,
    np,
    plt,
    calibration_frame,
):
    _cal_pt = calibration_frame(df_pts, exclude_widget.value)
    _cal_win = calibration_frame(df_win, exclude_widget.value)

    if _cal_pt.empty and _cal_win.empty:
        _view = mo.callout(
            mo.md("No hay dispositivos para graficar con la selección actual."),
            kind="warn",
        )
    else:
        _fig, _axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
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

            _batch = df_batch[df_batch["metodo"] == _method]
            if not _batch.empty:
                _ax.errorbar(
                    _batch["logC"],
                    _batch["R_mean"],
                    yerr=_batch["R_sd"],
                    fmt="s",
                    ms=7,
                    color="k",
                    capsize=4,
                    zorder=4,
                    label="batch: media ± SD",
                )
                _coef = np.polyfit(_batch["logC"], _batch["R_mean"], 1)
                _xs = np.linspace(_batch["logC"].min(), _batch["logC"].max(), 100)
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

        _view = mo.as_html(_fig)
        plt.close(_fig)
    _view
    return


@app.cell(hide_code=True)
def _(df_fits, mo):
    if df_fits.empty:
        _view = mo.callout(
            mo.md("No se pudieron calcular ajustes con la selección actual."),
            kind="warn",
        )
    else:
        _view = mo.ui.table(
            df_fits,
            selection=None,
            pagination=False,
            show_download=False,
            format_mapping={
                "b": "{:+.4f}",
                "se_b": "{:.4f}",
                "R2": "{:.3f}",
            },
            label="Ajuste lineal-log: R = a + b·log10(C)",
        )
    _view
    return


@app.cell(hide_code=True)
def _(df_batch, mo):
    if df_batch.empty:
        _view = mo.callout(
            mo.md("No hay curva de batch con la selección actual."),
            kind="warn",
        )
    else:
        _view = mo.ui.table(
            df_batch.drop(columns=["logC"]),
            selection=None,
            pagination=False,
            show_download=False,
            format_mapping={
                "R_mean": "{:+.4f}",
                "R_sd": "{:.4f}",
                "R_sem": "{:.4f}",
            },
            label="Curva del batch — media ± SD entre dispositivos",
        )
    _view
    return


@app.cell(hide_code=True)
def _(
    BATCH,
    V_READ,
    calibration,
    detail_widget,
    df_gm_summary,
    exclude_widget,
    hdf5_path,
    mo,
    ncols_widget,
    parse_measurement_name,
    plot_grid,
    plot_transfer_vread,
    plt,
):
    mo.stop(not detail_widget.value)
    _excluded = set(exclude_widget.value)

    def _is_excluded(measurement):
        if parse_measurement_name(measurement)[0] in _excluded:
            return True
        return parse_measurement_name(measurement)[0].split("B")[0] in _excluded

    _measurements = [m for m in calibration if not _is_excluded(m)]
    if not _measurements:
        _grid = mo.callout(
            mo.md("No hay transfers para graficar con la selección actual."),
            kind="warn",
        )
    else:
        _fig = plot_grid(
            hdf5_path,
            _measurements,
            lambda path, name, ax, direction="fwd": plot_transfer_vread(
                path, name, V_READ, ax=ax, direction=direction
            ),
            ncols=ncols_widget.value,
            figsize_per=(4.2, 3.4),
            title_suffix=f"{BATCH} — transfers con $V_{{READ}}={V_READ:.2f}$ V",
        )
        _grid = mo.as_html(_fig)
        plt.close(_fig)

    _gm_table = (
        mo.md("_Sin mediciones válidas para el punto de lectura._")
        if df_gm_summary.empty
        else mo.ui.table(
            df_gm_summary,
            selection=None,
            pagination=False,
            show_download=False,
            format_mapping={"v_read": "{:.3f}", "gm_max": "{:.2e}"},
            label="Punto de lectura por medición",
        )
    )
    mo.accordion({"Diagnóstico": mo.vstack([_grid, _gm_table], gap=1)})
    return


@app.cell(hide_code=True)
def _(Path, df_batch, df_fits, file_widget, mo):
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
    if _parts:
        _view = mo.hstack(_parts, justify="start", wrap=True, gap=1)
    else:
        _view = mo.md("_No hay resultados para descargar._")
    _view
    return


@app.cell(hide_code=True)
def _(
    BATCH,
    MIN_POINTS,
    V_READ,
    V_WINDOW_SIDE,
    baseline,
    calibration,
    exclude_widget,
    file_widget,
    mo,
    window_widget,
):
    _excluded = ", ".join(exclude_widget.value) if exclude_widget.value else "ninguno"
    mo.md(f"""
    ---

    **Configuración de la corrida**

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
    return


if __name__ == "__main__":
    app.run()
