import marimo

__generated_with = "0.25.2"
app = marimo.App(width="full", app_title="EGOFET — Calibration analysis")


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

    from src.calibration import (
        MIN_POINTS,
        V_WINDOW_SIDE,
        add_response,
        batch_curve,
        calibration_frame,
        calibration_measurements,
        collapse_conditions,
        cond_conc,
        extract_reading,
        fit_calibration,
        fit_summary,
        forward_gm,
        get_batch_name,
        gm_summary,
        gm_table,
        i_ds_at,
        i_ds_window_mean,
        parse_measurement_name,
        pick_v_read,
        window_bounds,
    )
    from src.readers.keithley_dean import (
        list_measurements,
        read_all_curves,
        view_measurements,
    )
    from src.plotting import plot_grid, plot_transfer, plot_transfer_vread

    data_folder = _PROJECT_ROOT / "data" / "raw"
    hdf5_files = sorted(p.name for p in data_folder.glob("*.hdf5"))

    default_file = "calibration_curve_example.hdf5"
    if default_file not in hdf5_files:
        default_file = hdf5_files[0] if hdf5_files else None
    return (
        MIN_POINTS,
        V_WINDOW_SIDE,
        add_response,
        batch_curve,
        calibration_frame,
        calibration_measurements,
        collapse_conditions,
        cond_conc,
        data_folder,
        default_file,
        extract_reading,
        fit_calibration,
        fit_summary,
        forward_gm,
        get_batch_name,
        gm_summary,
        gm_table,
        hdf5_files,
        i_ds_at,
        i_ds_window_mean,
        list_measurements,
        parse_measurement_name,
        pick_v_read,
        plot_grid,
        plot_transfer,
        plot_transfer_vread,
        read_all_curves,
        view_measurements,
        window_bounds,
    )


@app.cell
def _(mo):
    mo.md(r"""
    # Análisis de la curva de calibración — EGOFET

    Versión paso a paso de la construcción de una curva de calibración a partir
    de mediciones `transfer`. El recorrido sigue el notebook
    `01_calibration_analysis.ipynb`:

    1. Carga y parseo de nombres.
    2. Transconductancia y elección de $V_{READ}$.
    3. Lectura en un punto y en una ventana.
    4. Respuesta normalizada $R$.
    5. Ajuste lineal-log por dispositivo y por batch.

    Esta app es para desarrollo: se abre con `marimo edit` y muestra el código
    de cada paso. La versión condensada para consumidores es
    `03_calibration_report.py`.
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
def _(
    calibration_measurements,
    cond_conc,
    data_folder,
    file_widget,
    get_batch_name,
    list_measurements,
    parse_measurement_name,
    pd,
):
    hdf5_path = data_folder / file_widget.value
    measurements = list_measurements(hdf5_path)
    calibration, baseline = calibration_measurements(measurements)
    batches = sorted({get_batch_name(m) for m in calibration})
    devices = sorted({parse_measurement_name(m)[0] for m in calibration})
    BATCH = batches[0] if batches else "—"

    _rows = []
    for _name in calibration:
        _device, _stage, _condition, _suffix = parse_measurement_name(_name)
        _rows.append(
            {
                "measurement": _name,
                "batch": get_batch_name(_name),
                "device": _device,
                "stage": _stage,
                "condition": _condition,
                "conc (M)": cond_conc(_condition),
                "suffix": _suffix,
            }
        )
    df_measurements = pd.DataFrame(_rows)
    return (
        BATCH,
        baseline,
        batches,
        calibration,
        devices,
        df_measurements,
        hdf5_path,
        measurements,
    )


@app.cell
def _(df_measurements, file_widget, mo):
    mo.vstack(
        [
            mo.md(
                f"**Archivo:** `{file_widget.value}`  \n"
                f"**Mediciones de calibración:** {len(df_measurements)}"
            ),
            mo.ui.table(
                df_measurements[["measurement", "batch", "device", "condition", "conc (M)"]],
                selection=None,
                pagination=True,
                page_size=10,
                show_download=False,
                label="Mediciones parseadas",
            ),
        ],
        gap=1,
    )
    return


@app.cell
def _(baseline, mo):
    if baseline:
        _view = mo.callout(
            mo.md(
                "Mediciones fuera del patrón de calibración "
                f"(no se usan): {', '.join(f'`{m}`' for m in baseline)}."
            ),
            kind="info",
        )
    else:
        _view = mo.md("")
    _view
    return


@app.cell
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
    mo.hstack(
        [exclude_widget, window_widget],
        justify="start",
        align="end",
        gap=1,
        wrap=True,
    )
    return exclude_widget, window_widget


@app.cell
def _(BATCH, calibration, mo, parse_measurement_name):
    _by_device = {}
    for _name in calibration:
        _device = parse_measurement_name(_name)[0]
        _by_device.setdefault(_device, 0)
        _by_device[_device] += 1
    _lines = "  \n".join(
        f"- **{_device}**: {_count} mediciones"
        for _device, _count in sorted(_by_device.items())
    )
    mo.md(f"""
    ## 1. Carga de datos

    Batch **{BATCH}**, {len(calibration)} mediciones de calibración repartidas
    en {len(_by_device)} dispositivos:

    {_lines}
    """)
    return


@app.cell
def _(
    calibration,
    hdf5_path,
    mo,
    plot_grid,
    plot_transfer,
    plt,
):
    _fig = plot_grid(
        hdf5_path,
        calibration,
        plot_transfer,
        ncols=4,
        figsize_per=(4.0, 3.2),
        title_suffix="Transfers de calibración (forward)",
    )
    _view = mo.as_html(_fig)
    plt.close(_fig)
    _view
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## 2. Transconductancia y $V_{READ}$

    La transconductancia es la derivada de la corriente respecto de la tensión
    de gate:

    $$g_m = \left.\frac{\partial I_{DS}}{\partial V_{GS}}\right|_{V_{DS}}$$

    Se calcula sobre la rama de ida de cada réplica. El punto de lectura
    $V_{READ}$ es la **mediana** del $V_{GS}$ donde $|g_m|$ es máxima, redondeada
    a 0.01 V. Usar un único $V_{READ}$ por batch hace comparables todas las
    mediciones de la calibración.
    """)
    return


@app.cell
def _(
    calibration,
    df_measurements,
    forward_gm,
    gm_summary,
    gm_table,
    hdf5_path,
    mo,
    pick_v_read,
    plt,
    read_all_curves,
):
    df_gm = gm_table(hdf5_path, calibration)
    df_gm_summary = gm_summary(df_gm)
    V_READ = pick_v_read(df_gm)

    _first = df_measurements["measurement"].iloc[0] if not df_measurements.empty else None
    if _first is None:
        _view = mo.md("_No hay mediciones para analizar._")
    else:
        _fig, _ax = plt.subplots(figsize=(8, 4.2))
        for _curve in read_all_curves(hdf5_path, _first, direction="fwd"):
            _v, _i, _gm = forward_gm(_curve["v_gs"], _curve["i_ds"])
            if _gm.size:
                _ax.plot(_v, _gm, lw=1.2, label=f"réplica {_curve['curve_name']}")
        _ax.axvline(V_READ, color="C3", ls="--", lw=1.2, label=f"V_READ={V_READ:.2f} V")
        _ax.set_xlabel(r"$V_{GS}$ (V)")
        _ax.set_ylabel(r"$g_m$ (A/V)")
        _ax.set_title(f"Transconductancia — {_first}")
        _ax.grid(True, alpha=0.3)
        _ax.legend(fontsize=8)
        _fig.tight_layout()
        _view = mo.as_html(_fig)
        plt.close(_fig)
    return V_READ, df_gm, df_gm_summary, _view


@app.cell
def _(df_gm, mo, np):
    _per_batch = (
        df_gm.groupby("batch")
        .agg(
            v_read=("v_read", "median"),
            gm_max=("gm_max", "median"),
            n_replicas=("replica", "count"),
        )
        .reset_index()
    )
    _per_batch["v_read"] = _per_batch["v_read"].round(2)
    mo.ui.table(
        _per_batch,
        selection=None,
        pagination=False,
        show_download=False,
        format_mapping={"v_read": "{:.3f}", "gm_max": "{:.2e}"},
        label="V_READ por batch",
    )
    return


@app.cell
def _(
    BATCH,
    V_READ,
    calibration,
    df_gm_summary,
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
        title_suffix=f"{BATCH} — transfers con $V_{{READ}}={V_READ:.2f}$ V",
    )
    mo.vstack(
        [
            mo.as_html(_fig),
            mo.ui.table(
                df_gm_summary,
                selection=None,
                pagination=False,
                show_download=False,
                format_mapping={"v_read": "{:.3f}", "gm_max": "{:.2e}"},
                label="$V_{GS}$ y $g_m$ máximos por medición",
            ),
        ],
        gap=1,
    )
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## 3. Lectura de $I_{DS}$ y respuesta normalizada

    ### 3.1 Punto único

    Para cada réplica se interpola $I_{DS}$ en $V_{READ}$, se promedian las
    réplicas de cada medición y se normaliza contra la medición `Ref` del
    **mismo dispositivo**:

    $$R = \frac{I_{DS} - I_{DS,0}}{I_{DS,0}}$$

    Así se elimina la escala propia de cada dispositivo y queda una respuesta
    relativa comparable entre dispositivos.
    """)
    return


@app.cell
def _(
    V_READ,
    calibration,
    exclude_widget,
    extract_reading,
    hdf5_path,
    mo,
    pd,
):
    df_pts = extract_reading(
        hdf5_path,
        calibration,
        V_READ,
        method="point",
    )
    mo.ui.table(
        df_pts[
            ["device", "condition", "n_replicas", "mean", "sd", "R", "R_sd"]
        ],
        selection=None,
        pagination=True,
        page_size=12,
        show_download=False,
        format_mapping={
            "mean": "{:.3e}",
            "sd": "{:.3e}",
            "R": "{:+.4f}",
            "R_sd": "{:.4f}",
        },
        label=f"Lectura en un punto — V_READ = {V_READ:.2f} V",
    )
    return (df_pts,)


@app.cell
def _(df_pts, exclude_widget, calibration_frame, mo, plt, np):
    _cal = calibration_frame(df_pts, exclude_widget.value)
    if _cal.empty:
        _view = mo.md("_No hay datos para graficar._")
    else:
        _fig, _ax = plt.subplots(figsize=(8, 4.5))
        for _k, (_device, _group) in enumerate(_cal.groupby("device")):
            _ax.errorbar(
                _group["logC"],
                _group["R"],
                yerr=_group["R_sd"],
                fmt="o-",
                ms=4,
                lw=0.8,
                capsize=3,
                color=plt.cm.tab10(_k),
                label=_device,
            )
        _ax.axhline(0, color="gray", ls=":", lw=0.8)
        _ax.set_xlabel(r"$\log_{10}(C\ /\mathrm{M})$")
        _ax.set_ylabel(r"$R$")
        _ax.set_title("Respuesta normalizada — punto único")
        _ax.grid(True, alpha=0.3)
        _ax.legend(fontsize=8)
        _fig.tight_layout()
        _view = mo.as_html(_fig)
        plt.close(_fig)
    _view
    return


@app.cell
def _(mo):
    mo.md(r"""
    ### 3.2 Ventana de puntos

    En lugar de un único punto, se promedia $I_{DS}$ sobre una ventana de ancho
    $w$ que arranca en $V_{READ}$ y avanza hacia el interior del barrido:

    $$\bar I_{DS} = \frac{1}{N}\sum_{V_{GS}\in[V_{READ},\,V_{READ}+w]} I_{DS}$$

    La ventana reduce la sensibilidad al ruido de un punto aislado. El ancho es
    un compromiso: una ventana muy grande suaviza la curva pero mezcla
    condiciones de operación.
    """)
    return


@app.cell
def _(
    MIN_POINTS,
    V_WINDOW_SIDE,
    V_READ,
    calibration,
    hdf5_path,
    i_ds_window_mean,
    mo,
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
    if not _curves:
        _view = mo.md("_No hay curvas válidas para la ventana._")
    else:
        _curve = max(_curves, key=lambda c: abs(float(c["v_ds"][0])))
        _lo, _hi = window_bounds(
            _curve["v_gs"], V_READ, window_widget.value, V_WINDOW_SIDE
        )
        _fig, _ax = plt.subplots(figsize=(8, 4.2))
        _ax.plot(_curve["v_gs"], _curve["i_ds"], "o-", ms=3, label="forward")
        _ax.axvspan(_lo, _hi, color="C1", alpha=0.25, label="ventana de lectura")
        _ax.axvline(V_READ, color="C3", ls="--", lw=1, label=f"V_READ={V_READ:.2f} V")
        _ax.set_xlabel(r"$V_{GS}$ (V)")
        _ax.set_ylabel(r"$I_{DS}$ (A)")
        _ax.set_title(f"Ventana sobre {calibration[0]}")
        _ax.grid(True, alpha=0.3)
        _ax.legend(fontsize=8)
        _fig.tight_layout()
        _view = mo.as_html(_fig)
        plt.close(_fig)
        _mean = i_ds_window_mean(
            _curve["v_gs"],
            _curve["i_ds"],
            V_READ,
            window_widget.value,
            V_WINDOW_SIDE,
        )
        _view = mo.vstack([_view, mo.md(f"Media en la ventana: `{_mean:.3e} A`")])
    _view
    return


@app.cell
def _(
    V_READ,
    V_WINDOW_SIDE,
    calibration,
    extract_reading,
    hdf5_path,
    window_widget,
):
    df_win = extract_reading(
        hdf5_path,
        calibration,
        V_READ,
        method="window",
        window=window_widget.value,
        side=V_WINDOW_SIDE,
    )
    return (df_win,)


@app.cell
def _(
    calibration_frame,
    df_pts,
    df_win,
    exclude_widget,
    mo,
    plt,
    window_widget,
):
    _cal_pt = calibration_frame(df_pts, exclude_widget.value)
    _cal_win = calibration_frame(df_win, exclude_widget.value)
    if _cal_pt.empty and _cal_win.empty:
        _view = mo.md("_No hay datos para comparar._")
    else:
        _fig, _axes = plt.subplots(1, 2, figsize=(12, 4.2), sharey=True)
        for _ax, (_label, _cal) in zip(
            _axes,
            [("Punto único", _cal_pt), (f"Ventana ({window_widget.value:.2f} V)", _cal_win)],
        ):
            for _k, (_device, _group) in enumerate(_cal.groupby("device")):
                _ax.errorbar(
                    _group["logC"],
                    _group["R"],
                    yerr=_group["R_sd"],
                    fmt="o-",
                    ms=4,
                    lw=0.8,
                    capsize=3,
                    color=plt.cm.tab10(_k),
                    label=_device,
                )
            _ax.axhline(0, color="gray", ls=":", lw=0.8)
            _ax.set_xlabel(r"$\log_{10}(C\ /\mathrm{M})$")
            _ax.set_title(_label)
            _ax.grid(True, alpha=0.3)
        _axes[0].set_ylabel(r"$R$")
        _axes[0].legend(fontsize=8)
        _fig.suptitle("Punto único vs ventana")
        _fig.tight_layout()
        _view = mo.as_html(_fig)
        plt.close(_fig)
    _view
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## 4. Ajuste lineal-log y sensibilidad

    La curva de calibración se modela como

    $$R = a + b\,\log_{10} C$$

    donde la pendiente $b$ es la **sensibilidad** (cambio de $R$ por década de
    concentración) y $R^2$ indica cuánto explica el modelo lineal. Se ajusta por
    dispositivo y también sobre la curva media del batch.
    """)
    return


@app.cell
def _(df_pts, df_win, exclude_widget, fit_calibration, mo):
    df_fits, df_batch = fit_calibration(
        df_pts, df_win, exclude=exclude_widget.value
    )
    mo.ui.table(
        df_fits,
        selection=None,
        pagination=False,
        show_download=False,
        format_mapping={
            "b": "{:+.4f}",
            "se_b": "{:.4f}",
            "R2": "{:.3f}",
        },
        label="Ajuste por dispositivo y batch",
    )
    return df_batch, df_fits


@app.cell
def _(
    calibration_frame,
    df_fits,
    df_pts,
    df_win,
    exclude_widget,
    linregress,
    mo,
    np,
    plt,
):
    _cal_pt = calibration_frame(df_pts, exclude_widget.value)
    _cal_win = calibration_frame(df_win, exclude_widget.value)
    if _cal_pt.empty and _cal_win.empty:
        _view = mo.md("_No hay datos para graficar._")
    else:
        _fig, _axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
        for _ax, (_label, _cal) in zip(
            _axes,
            [("Punto único", _cal_pt), ("Ventana", _cal_win)],
        ):
            for _k, (_device, _group) in enumerate(_cal.groupby("device")):
                _color = plt.cm.tab10(_k)
                _group = _group.sort_values("logC")
                _ax.errorbar(
                    _group["logC"],
                    _group["R"],
                    yerr=_group["R_sd"],
                    fmt="o",
                    ms=5,
                    capsize=3,
                    color=_color,
                    label=_device,
                )
                _res = linregress(_group["logC"], _group["R"])
                _xs = np.linspace(_group["logC"].min(), _group["logC"].max(), 50)
                _ax.plot(
                    _xs,
                    _res.intercept + _res.slope * _xs,
                    "--",
                    lw=1,
                    color=_color,
                    alpha=0.6,
                )
            _ax.axhline(0, color="gray", ls=":", lw=0.8)
            _ax.set_xlabel(r"$\log_{10}(C\ /\mathrm{M})$")
            _ax.set_title(_label)
            _ax.grid(True, alpha=0.3)
        _axes[0].set_ylabel(r"$R$")
        _axes[0].legend(fontsize=8)
        _fig.suptitle("Ajustes por dispositivo")
        _fig.tight_layout()
        _view = mo.as_html(_fig)
        plt.close(_fig)
    _view
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## 5. Curva del batch y reproducibilidad

    La curva del batch promedia las **medias por dispositivo** (no todas las
    réplicas) y usa la desviación estándar entre dispositivos como medida de
    reproducibilidad. La `Ref` se excluye porque por definición $R=0$ en todos
    los dispositivos.
    """)
    return


@app.cell
def _(df_batch, mo):
    if df_batch.empty:
        _view = mo.callout(
            mo.md("No hay curva de batch con la selección actual."), kind="warn"
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


@app.cell
def _(
    calibration_frame,
    df_batch,
    df_pts,
    df_win,
    exclude_widget,
    linregress,
    mo,
    np,
    plt,
):
    _cal_pt = calibration_frame(df_pts, exclude_widget.value)
    _cal_win = calibration_frame(df_win, exclude_widget.value)
    if _cal_pt.empty and _cal_win.empty:
        _view = mo.md("_No hay datos para graficar._")
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
                _res = linregress(_batch["logC"], _batch["R_mean"])
                _xs = np.linspace(_batch["logC"].min(), _batch["logC"].max(), 100)
                _ax.plot(
                    _xs,
                    _res.intercept + _res.slope * _xs,
                    "--",
                    color="C3",
                    lw=1.6,
                    label=f"ajuste batch: b={_res.slope:+.3f}, R²={_res.rvalue**2:.3f}",
                )
            _ax.axhline(0, color="gray", ls=":", lw=0.8)
            _ax.set_xlabel(r"$\log_{10}(C\ /\mathrm{M})$")
            _ax.set_title(_method)
            _ax.grid(True, alpha=0.3)
            _ax.legend(fontsize=8)
        _axes[0].set_ylabel(r"$R$")
        _fig.suptitle("Curva del batch — media ± SD entre dispositivos")
        _fig.tight_layout()
        _view = mo.as_html(_fig)
        plt.close(_fig)
    _view
    return


@app.cell
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
        _view = mo.md("_Sin advertencias: todos los dispositivos tienen `Ref`._")
    _view
    return


@app.cell
def _(Path, df_batch, df_fits, file_widget, mo):
    _parts = []
    _stem = Path(file_widget.value).stem
    for _label, _frame, _name in [
        ("Descargar ajustes (CSV)", df_fits, f"calibration_fits_{_stem}.csv"),
        ("Descargar curva del batch (CSV)", df_batch, f"calibration_batch_{_stem}.csv"),
    ]:
        if not _frame.empty:
            _parts.append(
                mo.download(
                    data=lambda frame=_frame: frame.to_csv(index=False),
                    filename=_name,
                    mimetype="text/csv",
                    label=_label,
                )
            )
    if _parts:
        _view = mo.hstack(_parts, justify="start", wrap=True, gap=1)
    else:
        _view = mo.md("_No hay resultados para descargar._")
    _view
    return


@app.cell
def _(
    BATCH,
    MIN_POINTS,
    V_READ,
    V_WINDOW_SIDE,
    baseline,
    calibration,
    devices,
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
    | Dispositivos | {len(devices)} |
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
