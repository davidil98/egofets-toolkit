# /// script
# [tool.marimo.opengraph]
# title = "Calibration curve"
# description = "Interactive calibration curve built from batch measurements."
# ///

import marimo

__generated_with = "0.23.5"
app = marimo.App(width="full", app_title="EGOFET — Calibration curve")


@app.cell(hide_code=True)
def _():
    import os
    import re
    import sys
    from pathlib import Path

    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    from scipy.stats import linregress

    return Path, linregress, mo, np, os, pd, plt, re, sys


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

    from src.readers.keithley_dean import list_measurements, read_all_curves
    from src.plotting import plot_grid, plot_transfer

    data_folder = _PROJECT_ROOT / "data" / "raw"
    hdf5_files = sorted(p.name for p in data_folder.glob("*.hdf5"))

    # Archivo que abre por defecto (si esta disponible).
    default_file = "calibration_curve_example.hdf5"
    if default_file not in hdf5_files:
        default_file = hdf5_files[0] if hdf5_files else None
    return (
        data_folder,
        default_file,
        hdf5_files,
        list_measurements,
        plot_grid,
        plot_transfer,
        read_all_curves,
    )


@app.cell(hide_code=True)
def _(linregress, np, pd, re):
    # --- Parametros de analisis (viven en codigo) ---
    MIN_POINTS = 5
    V_WINDOW_SIDE = "inward"

    def get_batch_name(measurement_name):
        """'D1B2_E-12_00' -> 'B2'."""
        match = re.match(r"^D\d+(B\d+)_", measurement_name)
        return match.group(1) if match else "?"

    def parse_measurement_name(measurement_name):
        """Separa DnBm[_etapa]_<condicion>_<sufijo>."""
        parts = measurement_name.split("_")
        device = parts[0]
        stage = parts[1] if len(parts) >= 4 else None
        cond = parts[2] if stage else parts[1]
        suffix = parts[-1]
        device_key = f"{device}_{stage}" if stage else device
        return device_key, stage, cond, suffix

    def cond_conc(cond):
        """'E-12' -> 1e-12 M; 'Ref' -> None."""
        return None if cond == "Ref" else 10.0 ** (-int(cond.split("-")[1]))

    def clean_forward_branch(v_gs, i_ds, rel_tol=0.25):
        """Ordena V_GS y descarta el punto de retorno duplicado."""
        v = np.asarray(v_gs, dtype=float)
        i = np.asarray(i_ds, dtype=float)
        order = np.argsort(v)
        v, i = v[order], i[order]
        if v.size < 3:
            return v, i
        step = float(np.median(np.abs(np.diff(v))))
        keep = np.concatenate(([True], np.abs(np.diff(v)) > rel_tol * step))
        return v[keep], i[keep]

    def forward_gm(v_gs, i_ds):
        """Devuelve (V_GS, I_DS, g_m) de la rama forward limpia."""
        v, i = clean_forward_branch(v_gs, i_ds)
        if v.size < 2:
            return v, i, np.array([])
        return v, i, np.gradient(i, v)

    def i_ds_at(v_gs, i_ds, v_read):
        """I_DS interpolado linealmente en v_read."""
        v = np.asarray(v_gs, dtype=float)
        i = np.asarray(i_ds, dtype=float)
        order = np.argsort(v)
        return float(np.interp(v_read, v[order], i[order]))

    def window_bounds(v_gs, v_center, half_width, side="inward"):
        """Extremos de la ventana de lectura."""
        v = np.asarray(v_gs, dtype=float)
        at_low_edge = abs(v_center - v.min()) <= abs(v_center - v.max())
        if side == "both":
            return v_center - half_width, v_center + half_width
        if side == "inward":
            return (
                (v_center, v_center + half_width)
                if at_low_edge
                else (v_center - half_width, v_center)
            )
        if side == "outward":
            return (
                (v_center - half_width, v_center)
                if at_low_edge
                else (v_center, v_center + half_width)
            )
        raise ValueError(f"V_WINDOW_SIDE='{side}' no soportado")

    def window_mask(v_gs, v_center, half_width, side="inward"):
        lo, hi = window_bounds(v_gs, v_center, half_width, side)
        v = np.asarray(v_gs, dtype=float)
        return (v >= lo) & (v <= hi)

    def i_ds_window_mean(v_gs, i_ds, v_center, half_width, side="inward"):
        """Media de I_DS en la ventana de lectura."""
        mask = window_mask(v_gs, v_center, half_width, side)
        if not mask.any():
            return float("nan")
        return float(np.mean(np.asarray(i_ds)[mask]))

    def _pooled_sd(values):
        values = np.asarray(values, dtype=float)
        return float(np.sqrt(np.nanmean(values**2))) if values.size else float("nan")

    def collapse_conditions(df_raw):
        """Una fila por dispositivo+condicion a partir de una fila por medicion."""
        if df_raw.empty:
            return df_raw
        return (
            df_raw.groupby(["device", "condition"], as_index=False)
            .agg(
                measurement=("measurement", "first"),
                conc=("conc", "first"),
                n_measurements=("measurement", "count"),
                n_replicas=("n_replicas", "sum"),
                mean=("mean", "mean"),
                sd=("sd", _pooled_sd),
            )
        )

    def add_response(df):
        """Agrega R y R_sd normalizando contra la Ref del mismo dispositivo."""
        out = df.copy()
        out["R"] = np.nan
        out["R_sd"] = np.nan
        for _, _group in out.groupby("device"):
            _ref = _group[_group["condition"] == "Ref"]
            if _ref.empty:
                continue
            _i_ref = float(_ref["mean"].iloc[0])
            out.loc[_group.index, "R"] = (_group["mean"] - _i_ref) / _i_ref
            out.loc[_group.index, "R_sd"] = _group["sd"] / abs(_i_ref)
        return out

    def excluded_mask(devices, exclude=()):
        """True para dispositivos que coinciden exacta o por prefijo (D2)."""
        exclude = set(exclude)
        return devices.apply(
            lambda d: d in exclude or str(d).split("B")[0] in exclude
        )

    def calibration_frame(df, exclude=()):
        """Datos de calibracion (sin Ref) listos para el ajuste."""
        cal = df[
            (df["condition"] != "Ref")
            & (~excluded_mask(df["device"], exclude))
        ].copy()
        cal["logC"] = np.log10(cal["conc"])
        return cal.dropna(subset=["R", "logC"]).sort_values("logC")

    def batch_curve(df_device, exclude=()):
        """Una fila por concentracion con la media y la SD entre dispositivos."""
        data = calibration_frame(df_device, exclude)
        rows = []
        for conc, group in data.groupby("conc"):
            values = group["R"].to_numpy(dtype=float)
            n = values.size
            sd = float(np.std(values, ddof=1)) if n > 1 else float("nan")
            rows.append(
                {
                    "condition": group["condition"].iloc[0],
                    "conc": float(conc),
                    "logC": float(np.log10(conc)),
                    "n_devices": int(n),
                    "R_mean": float(np.mean(values)),
                    "R_sd": sd,
                    "R_sem": sd / np.sqrt(n) if n > 1 else float("nan"),
                    "devices": ", ".join(sorted(group["device"])),
                }
            )

        columns = [
            "condition",
            "conc",
            "logC",
            "n_devices",
            "R_mean",
            "R_sd",
            "R_sem",
            "devices",
        ]
        if not rows:
            return pd.DataFrame(columns=columns)
        return pd.DataFrame(rows, columns=columns).sort_values("logC").reset_index(drop=True)

    def fit_summary(level, x, y):
        """Ajuste y = a + b x y resumen de metricas."""
        res = linregress(np.asarray(x, dtype=float), np.asarray(y, dtype=float))
        return {
            "nivel": level,
            "b": res.slope,
            "se_b": res.stderr,
            "R2": res.rvalue**2,
            "n": int(len(x)),
        }

    return (
        MIN_POINTS,
        V_WINDOW_SIDE,
        add_response,
        batch_curve,
        calibration_frame,
        collapse_conditions,
        cond_conc,
        fit_summary,
        forward_gm,
        get_batch_name,
        i_ds_at,
        i_ds_window_mean,
        parse_measurement_name,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Curva de calibración — EGOFET

    Reporte condensado de la calibración a partir de un archivo HDF5:
    $V_{READ}$ por transconductancia, respuesta normalizada $R$ y ajuste
    lineal-log por dispositivo y por batch.

    Selecciona el archivo y, si hace falta, excluir dispositivos o cambia el ancho
    de la ventana. Los resultados se descargan como CSV.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.accordion(
        {
            "Método": mo.md(r"""
    - **$V_{READ}$**: mediana de $V_{GS}$ donde $|g_m|$ es máxima, sobre la
      rama forward de todas las réplicas del batch.
    - **Respuesta**: $R = (I_{DS} - I_{DS,0})/I_{DS,0}$, con $I_{DS,0}$ la
      lectura de la `Ref` del mismo dispositivo a $V_{READ}$.
    - **Métodos**: punto único (interpolación en $V_{READ}$) y ventana
      (media de $I_{DS}$ en $[V_{READ}, V_{READ}+w]$).
    - **Ajuste**: $R = a + b\log_{10}C$; $b$ es la sensibilidad. El batch
      promedia las medias por dispositivo y usa la SD entre dispositivos.
    """)
        }
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


@app.cell(hide_code=True)
def _(
    data_folder,
    file_widget,
    get_batch_name,
    hdf5_files,
    list_measurements,
    mo,
    parse_measurement_name,
    re,
):
    mo.stop(
        not hdf5_files,
        mo.callout(
            mo.md(f"No se encontraron archivos `.hdf5` en `{data_folder}`"),
            kind="warn",
        ),
    )

    hdf5_path = data_folder / file_widget.value
    measurements = list_measurements(hdf5_path)

    # Una medicion de calibracion tiene la forma
    #   DnBm[_etapa]_<condicion>_<sufijo>   con condicion = Ref | E-XX
    _calibration_re = re.compile(
        r"^D\d+B\d+(?:_[A-Za-z]+)?_(?:Ref|E-\d+)_\d+$"
    )
    transfer_names = [
        m["name"] for m in measurements if m["mode"] == "transfer"
    ]
    calibration = [m for m in transfer_names if _calibration_re.match(m)]
    baseline = [m for m in transfer_names if not _calibration_re.match(m)]
    batches = sorted({get_batch_name(m) for m in calibration})
    devices = sorted({parse_measurement_name(m)[0] for m in calibration})

    _issues = []
    if not transfer_names:
        _issues.append("El archivo no tiene mediciones de transfer.")
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

    mo.stop(
        bool(_issues),
        mo.callout(mo.md("  \n".join(_issues)), kind="warn"),
    )

    BATCH = batches[0]
    return BATCH, baseline, calibration, devices, hdf5_path


@app.cell
def _(devices, mo):
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


@app.cell(hide_code=True)
def _(
    MIN_POINTS,
    calibration,
    forward_gm,
    get_batch_name,
    hdf5_path,
    mo,
    np,
    pd,
    read_all_curves,
):
    _rows = []
    for _measurement in calibration:
        for _replica, _curve in enumerate(
            read_all_curves(hdf5_path, _measurement, direction="fwd"), start=1
        ):
            if len(_curve["v_gs"]) < MIN_POINTS:
                continue
            _v, _i, _gm = forward_gm(_curve["v_gs"], _curve["i_ds"])
            if _gm.size == 0:
                continue
            _idx = int(np.argmax(np.abs(_gm)))
            _rows.append(
                {
                    "batch": get_batch_name(_measurement),
                    "measurement": _measurement,
                    "replica": _replica,
                    "v_read": float(_v[_idx]),
                    "gm_max": float(abs(_gm[_idx])),
                }
            )

    _df_gm = pd.DataFrame(
        _rows, columns=["batch", "measurement", "replica", "v_read", "gm_max"]
    )
    df_gm_summary = (
        _df_gm.groupby(["batch", "measurement"])
        .agg(
            v_read=("v_read", "median"),
            gm_max=("gm_max", "median"),
            n_replicas=("replica", "count"),
        )
        .reset_index()
    )

    _valid_vread = _df_gm.dropna(subset=["v_read"])
    V_READ = (
        float(round(_valid_vread["v_read"].median(), 2))
        if not _valid_vread.empty
        else float("nan")
    )

    mo.stop(
        not np.isfinite(V_READ),
        mo.callout(
            mo.md(
                "No se pudo determinar $V_{READ}$: no hay curvas con "
                f"al menos {MIN_POINTS} puntos."
            ),
            kind="warn",
        ),
    )
    return V_READ, df_gm_summary


@app.cell(hide_code=True)
def _(
    MIN_POINTS,
    V_READ,
    V_WINDOW_SIDE,
    add_response,
    calibration,
    collapse_conditions,
    cond_conc,
    hdf5_path,
    i_ds_at,
    i_ds_window_mean,
    np,
    parse_measurement_name,
    pd,
    read_all_curves,
    window_widget,
):
    _point_rows = []
    _window_rows = []
    for _measurement in calibration:
        _curves = [
            _curve
            for _curve in read_all_curves(hdf5_path, _measurement, direction="fwd")
            if len(_curve["v_gs"]) >= MIN_POINTS
        ]
        if not _curves:
            continue

        _device, _stage, _condition, _suffix = parse_measurement_name(_measurement)
        _points = np.array(
            [i_ds_at(c["v_gs"], c["i_ds"], V_READ) for c in _curves],
            dtype=float,
        )
        _window = np.array(
            [
                i_ds_window_mean(
                    c["v_gs"], c["i_ds"], V_READ, window_widget.value, V_WINDOW_SIDE
                )
                for c in _curves
            ],
            dtype=float,
        )

        _base = {
            "measurement": _measurement,
            "device": _device,
            "condition": _condition,
            "conc": cond_conc(_condition),
        }
        _point_rows.append(
            {
                **_base,
                "n_replicas": int(_points.size),
                "mean": float(np.mean(_points)),
                "sd": (
                    float(np.std(_points, ddof=1))
                    if _points.size > 1
                    else 0.0
                ),
            }
        )

        _window = _window[np.isfinite(_window)]
        _window_rows.append(
            {
                **_base,
                "n_replicas": int(_window.size),
                "mean": (
                    float(np.mean(_window)) if _window.size else float("nan")
                ),
                "sd": (
                    float(np.std(_window, ddof=1))
                    if _window.size > 1
                    else 0.0
                ),
            }
        )

    _columns = [
        "measurement",
        "device",
        "condition",
        "conc",
        "n_replicas",
        "mean",
        "sd",
    ]
    _point_raw = pd.DataFrame(_point_rows, columns=_columns)
    _window_raw = pd.DataFrame(_window_rows, columns=_columns)

    df_pts = add_response(collapse_conditions(_point_raw))
    df_win = add_response(collapse_conditions(_window_raw))
    return df_pts, df_win


@app.cell(hide_code=True)
def _(
    batch_curve,
    calibration_frame,
    df_pts,
    df_win,
    exclude_widget,
    fit_summary,
    pd,
):
    _fit_rows = []
    _batch_parts = []

    for _method, _frame in [("Punto único", df_pts), ("Ventana", df_win)]:
        _cal = calibration_frame(_frame, exclude_widget.value)
        if _cal.empty:
            continue

        for _device, _group in _cal.groupby("device"):
            _group = _group.sort_values("logC")
            _fit_rows.append(
                {
                    "metodo": _method,
                    **fit_summary(_device, _group["logC"], _group["R"]),
                }
            )

        _batch = batch_curve(_frame, exclude_widget.value)
        if not _batch.empty:
            _fit_rows.append(
                {
                    "metodo": _method,
                    **fit_summary("Batch", _batch["logC"], _batch["R_mean"]),
                }
            )
            _batch.insert(0, "metodo", _method)
            _batch_parts.append(_batch)

    _fit_columns = ["metodo", "nivel", "b", "se_b", "R2", "n"]
    df_fits = pd.DataFrame(_fit_rows, columns=_fit_columns)

    _batch_columns = [
        "metodo",
        "condition",
        "conc",
        "logC",
        "n_devices",
        "R_mean",
        "R_sd",
        "R_sem",
        "devices",
    ]
    df_batch = (
        pd.concat(_batch_parts, ignore_index=True)
        if _batch_parts
        else pd.DataFrame(columns=_batch_columns)
    )
    return df_batch, df_fits


@app.cell
def _(df_pts, exclude_widget, mo):
    _missing = sorted(
        set(df_pts["device"])
        - set(df_pts.loc[df_pts["condition"] == "Ref", "device"])
    )
    _messages = []
    if _missing:
        _messages.append(
            f"Sin `Ref`: {', '.join(_missing)}. "
            "Esos dispositivos quedan fuera de la normalización."
        )
    if exclude_widget.value:
        _messages.append(
            f"Dispositivos excluidos: {', '.join(exclude_widget.value)}."
        )
    if _messages:
        _view = mo.callout(mo.md("  \n".join(_messages)), kind="warn")
    else:
        _view = mo.md("")
    _view
    return


@app.cell
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
            mo.stat(_b, label="Sensibilidad b (ventana)", bordered=True),
            mo.stat(_r2, label="R² batch (ventana)", bordered=True),
        ],
        justify="start",
        wrap=True,
        gap=1,
    )
    return


@app.cell
def _(
    calibration_frame,
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
        _view = mo.callout(
            mo.md("No hay dispositivos para graficar con la selección actual."),
            kind="warn",
        )
    else:
        _fig, _axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
        for _ax, (_label, _cal) in zip(
            _axes,
            [("Punto único (3.1)", _cal_pt), ("Ventana (3.2)", _cal_win)],
        ):
            for _k, (_device, _group) in enumerate(_cal.groupby("device")):
                _color = plt.cm.tab10(_k)
                _ax.errorbar(
                    _group["logC"],
                    _group["R"],
                    yerr=_group["R_sd"],
                    ls="none",
                    marker="o",
                    ms=5,
                    capsize=3,
                    color=_color,
                    label=_device,
                )
                _xs = np.linspace(
                    _group["logC"].min(), _group["logC"].max(), 50
                )
                _res = linregress(_group["logC"], _group["R"])
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

        _axes[0].set_ylabel(r"$R = (I_{DS} - I_{DS,0}) / I_{DS,0}$")
        if _axes[0].get_legend_handles_labels()[0]:
            _axes[0].legend(title="dispositivo", fontsize=8)
        _fig.suptitle("Curva de calibración — respuesta normalizada")
        _fig.tight_layout()

        _view = mo.as_html(_fig)
        plt.close(_fig)
    _view
    return


@app.cell
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


@app.cell
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


@app.cell
def _(df_gm_summary, mo):
    if df_gm_summary.empty:
        gm_table = mo.md("_Sin mediciones válidas para el punto de lectura._")
    else:
        gm_table = mo.ui.table(
            df_gm_summary,
            selection=None,
            pagination=False,
            show_download=False,
            format_mapping={"v_read": "{:.3f}", "gm_max": "{:.2e}"},
            label="Punto de lectura por medición",
        )
    return (gm_table,)


@app.cell
def _(
    MIN_POINTS,
    V_READ,
    calibration,
    hdf5_path,
    i_ds_at,
    mo,
    parse_measurement_name,
    plt,
    read_all_curves,
):
    _devices = sorted({parse_measurement_name(m)[0] for m in calibration})
    _fig, _axes = plt.subplots(
        1, len(_devices), figsize=(5 * len(_devices), 4.2), squeeze=False
    )
    for _ax, _device in zip(_axes.ravel(), _devices):
        for _measurement in calibration:
            if parse_measurement_name(_measurement)[0] != _device:
                continue
            for _curve in read_all_curves(
                hdf5_path, _measurement, direction="fwd"
            ):
                if len(_curve["v_gs"]) < MIN_POINTS:
                    continue
                _ax.plot(
                    _curve["v_gs"],
                    _curve["i_ds"],
                    "-",
                    lw=0.6,
                    color="gray",
                    alpha=0.45,
                )
                _ax.plot(
                    V_READ,
                    i_ds_at(_curve["v_gs"], _curve["i_ds"], V_READ),
                    "r*",
                    ms=7,
                    zorder=5,
                )
        _ax.axvline(V_READ, color="gray", ls="--", lw=0.8)
        _ax.set_title(_device)
        _ax.set_xlabel(r"$V_{GS}$ (V)")
        _ax.set_ylabel(r"$I_{DS}$ (A)")
        _ax.grid(True, alpha=0.3)

    _fig.suptitle(f"Curvas y punto de lectura en $V_{{GS}}={V_READ}$ V")
    _fig.tight_layout()

    devices_view = mo.as_html(_fig)
    plt.close(_fig)
    return (devices_view,)


@app.cell(hide_code=True)
def _(MIN_POINTS, V_READ, i_ds_at, plot_transfer, read_all_curves):
    def plot_transfer_vread(hdf5_path, measurement_name, ax=None, direction="fwd"):
        """Transfer forward + punto interpolado en V_READ.

        Firma compatible con plot_grid, que la llama como:
            plot_func(hdf5_path, m_name, ax=ax, direction='fwd')
        """
        plot_transfer(
            hdf5_path, measurement_name, direction=direction, ax=ax
        )

        for _curve in read_all_curves(
            hdf5_path, measurement_name, direction=direction
        ):
            if len(_curve["v_gs"]) < MIN_POINTS:
                continue
            ax.plot(
                V_READ,
                i_ds_at(_curve["v_gs"], _curve["i_ds"], V_READ),
                "r*",
                ms=8,
                zorder=5,
            )

        ax.axvline(V_READ, color="gray", ls="--", lw=0.8)
        ax.set_title(measurement_name, fontsize=9)

        # Las réplicas comparten V_DS: una leyenda por panel no aporta.
        _legend = ax.get_legend()
        if _legend is not None:
            _legend.remove()

        return ax

    return (plot_transfer_vread,)


@app.cell
def _(
    BATCH,
    V_READ,
    calibration,
    exclude_widget,
    hdf5_path,
    mo,
    parse_measurement_name,
    plot_grid,
    plot_transfer_vread,
    plt,
):
    _excluded = set(exclude_widget.value)

    def _is_excluded(measurement):
        _device = parse_measurement_name(measurement)[0]
        return _device in _excluded or _device.split("B")[0] in _excluded

    _measurements = [m for m in calibration if not _is_excluded(m)]

    if not _measurements:
        transfers_grid_view = mo.callout(
            mo.md("No hay transfers para graficar con la selección actual."),
            kind="warn",
        )
    else:
        _fig = plot_grid(
            hdf5_path,
            _measurements,
            plot_transfer_vread,
            ncols=4,
            figsize_per=(4.2, 3.4),
            title_suffix=(
                f"{BATCH} — transfers con $V_{{READ}}={V_READ:.2f}$ V"
            ),
        )
        transfers_grid_view = mo.as_html(_fig)
        plt.close(_fig)
    return (transfers_grid_view,)


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
        batch_fit_view = mo.callout(
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
                _res = linregress(_batch["logC"], _batch["R_mean"])
                _xs = np.linspace(
                    _batch["logC"].min(), _batch["logC"].max(), 100
                )
                _ax.plot(
                    _xs,
                    _res.intercept + _res.slope * _xs,
                    "--",
                    color="C3",
                    lw=1.6,
                    label=f"ajuste batch: b={_res.slope:+.3f}",
                )

            _ax.axhline(0, color="gray", ls=":", lw=0.8)
            _ax.set_xlabel(r"$\log_{10}(C\ /\mathrm{M})$")
            _ax.set_title(_method)
            _ax.grid(True, alpha=0.3)
            if _ax.get_legend_handles_labels()[0]:
                _ax.legend(fontsize=8)

        _axes[0].set_ylabel(r"$R = (I_{DS} - I_{DS,0}) / I_{DS,0}$")
        _fig.suptitle("Curva del batch — media ± SD entre dispositivos")
        _fig.tight_layout()

        batch_fit_view = mo.as_html(_fig)
        plt.close(_fig)
    return (batch_fit_view,)


@app.cell(hide_code=True)
def _(batch_fit_view, devices_view, gm_table, mo, transfers_grid_view):
    mo.accordion(
        {
            "Punto de lectura por medición": gm_table,
            "Curvas por dispositivo y V_READ": devices_view,
            "Transfers y V_READ (grilla)": transfers_grid_view,
            "Ajuste del batch": batch_fit_view,
            "Transconductancia": mo.md(
                r"$$g_m = \left.\frac{\partial I_{DS}}"
                r"{\partial V_{GS}}\right|_{V_{DS}}$$"
            ),
        }
    )
    return


@app.cell
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


@app.cell
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
    _excluded = (
        ", ".join(exclude_widget.value) if exclude_widget.value else "ninguno"
    )
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
