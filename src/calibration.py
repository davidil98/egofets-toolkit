"""Pipeline de curvas de calibración para EGOFET.

El módulo reúne las funciones puras que construyen una curva de calibración a
partir de mediciones ``transfer``:

1. Parseo de los nombres ``DnBm[_etapa]_<condición>_<sufijo>``.
2. Elección de ``V_READ`` a partir de la transconductancia.
3. Lectura de ``I_DS`` en un punto o en una ventana.
4. Normalización contra la ``Ref`` de cada dispositivo (respuesta ``R``).
5. Ajuste lineal-log por dispositivo y curva media del batch.

Las apps Marimo ``02_*`` (análisis) y ``03_*`` (reporte) importan estas
funciones, de modo que ambas muestran exactamente los mismos números.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
from scipy.stats import linregress

from .analysis import clean_forward_branch, forward_gm
from .readers.keithley_dean import read_all_curves

#: Medición de calibración: ``DnBm[_etapa]_<Ref|E-XX>_<sufijo>``.
CALIBRATION_PATTERN = re.compile(r"^D\d+B\d+(?:_[A-Za-z]+)?_(?:Ref|E-\d+)_\d+$")

#: Curvas con menos puntos que este umbral se consideran adquisiciones fallidas.
MIN_POINTS = 5

#: La ventana de lectura va hacia el interior del barrido (V_READ cae en el borde).
V_WINDOW_SIDE = "inward"


# ---------------------------------------------------------------------------
# Nombres de medición
# ---------------------------------------------------------------------------
def get_batch_name(measurement_name: str) -> str:
    """Extrae el batch del nombre: ``'D1B2_E-12_00' -> 'B2'``."""
    match = re.match(r"^D\d+(B\d+)_", measurement_name)
    return match.group(1) if match else "?"


def parse_measurement_name(measurement_name: str) -> tuple[str, str | None, str, str]:
    """Separa ``DnBm[_etapa]_<condición>_<sufijo>``.

    ``'D1B2_E-12_00'``     -> ``('D1B2', None, 'E-12', '00')``
    ``'D1B3_TAE_E-12_00'`` -> ``('D1B3', 'TAE', 'E-12', '00')``
    """
    parts = measurement_name.split("_")
    device = parts[0]
    stage = parts[1] if len(parts) >= 4 else None
    cond = parts[2] if stage else parts[1]
    suffix = parts[-1]
    device_key = f"{device}_{stage}" if stage else device
    return device_key, stage, cond, suffix


def cond_conc(cond: str) -> float | None:
    """``'E-12' -> 1e-12 M``; ``'Ref' -> None``."""
    return None if cond == "Ref" else 10.0 ** (-int(cond.split("-")[1]))


def calibration_measurements(measurements: list[dict]) -> tuple[list[str], list[str]]:
    """Separa mediciones de calibración y líneas base.

    Parameters
    ----------
    measurements : list of dict
        Salida de :func:`src.readers.keithley_dean.list_measurements`.

    Returns
    -------
    calibration, baseline : list of str
        Nombres que siguen el patrón de calibración y los que no (p. ej. TBE).
    """
    transfer = [m["name"] for m in measurements if m["mode"] == "transfer"]
    calibration = [name for name in transfer if CALIBRATION_PATTERN.match(name)]
    baseline = [name for name in transfer if not CALIBRATION_PATTERN.match(name)]
    return calibration, baseline


# ---------------------------------------------------------------------------
# Transconductancia y V_READ
# ---------------------------------------------------------------------------
def gm_table(
    hdf5_path, measurements: list[str], min_points: int = MIN_POINTS
) -> pd.DataFrame:
    """Una fila por réplica con ``V_GS`` de ``|g_m|`` máxima.

    Columnas: ``batch``, ``measurement``, ``replica``, ``v_read``, ``gm_max``.
    """
    rows = []
    for measurement in measurements:
        for replica, curve in enumerate(
            read_all_curves(hdf5_path, measurement, direction="fwd"), start=1
        ):
            if len(curve["v_gs"]) < min_points:
                continue
            v, _, gm = forward_gm(curve["v_gs"], curve["i_ds"])
            if gm.size == 0:
                continue
            index = int(np.argmax(np.abs(gm)))
            rows.append(
                {
                    "batch": get_batch_name(measurement),
                    "measurement": measurement,
                    "replica": replica,
                    "v_read": float(v[index]),
                    "gm_max": float(abs(gm[index])),
                }
            )
    return pd.DataFrame(
        rows, columns=["batch", "measurement", "replica", "v_read", "gm_max"]
    )


def gm_summary(df_gm: pd.DataFrame) -> pd.DataFrame:
    """Resume :func:`gm_table` por medición: mediana de ``v_read`` y ``gm_max``."""
    if df_gm.empty:
        return pd.DataFrame(
            columns=["batch", "measurement", "v_read", "gm_max", "n_replicas"]
        )
    return (
        df_gm.groupby(["batch", "measurement"])
        .agg(
            v_read=("v_read", "median"),
            gm_max=("gm_max", "median"),
            n_replicas=("replica", "count"),
        )
        .reset_index()
    )


def pick_v_read(df_gm: pd.DataFrame) -> float:
    """``V_READ`` del batch: mediana de ``v_read`` redondeada a 0.01 V."""
    valid = df_gm.dropna(subset=["v_read"])
    if valid.empty:
        return float("nan")
    return float(round(valid["v_read"].median(), 2))


# ---------------------------------------------------------------------------
# Lectura de I_DS
# ---------------------------------------------------------------------------
def i_ds_at(v_gs, i_ds, v_read: float) -> float:
    """``I_DS`` interpolado linealmente en ``v_read``."""
    v = np.asarray(v_gs, dtype=float)
    i = np.asarray(i_ds, dtype=float)
    order = np.argsort(v)
    return float(np.interp(v_read, v[order], i[order]))


def window_bounds(v_gs, v_center: float, half_width: float, side: str = V_WINDOW_SIDE):
    """Extremos de la ventana de lectura."""
    v = np.asarray(v_gs, dtype=float)
    at_low_edge = abs(v_center - v.min()) <= abs(v_center - v.max())
    if side == "both":
        return v_center - half_width, v_center + half_width
    if side == "inward":
        return (v_center, v_center + half_width) if at_low_edge else (
            v_center - half_width,
            v_center,
        )
    if side == "outward":
        return (v_center - half_width, v_center) if at_low_edge else (
            v_center,
            v_center + half_width,
        )
    raise ValueError(f"V_WINDOW_SIDE='{side}' no soportado")


def window_mask(v_gs, v_center: float, half_width: float, side: str = V_WINDOW_SIDE):
    """Máscara booleana de los puntos dentro de la ventana de lectura."""
    lo, hi = window_bounds(v_gs, v_center, half_width, side)
    v = np.asarray(v_gs, dtype=float)
    return (v >= lo) & (v <= hi)


def i_ds_window_mean(
    v_gs, i_ds, v_center: float, half_width: float, side: str = V_WINDOW_SIDE
) -> float:
    """Media de ``I_DS`` en la ventana de lectura (``nan`` si queda vacía)."""
    mask = window_mask(v_gs, v_center, half_width, side)
    if not mask.any():
        return float("nan")
    return float(np.mean(np.asarray(i_ds)[mask]))


# ---------------------------------------------------------------------------
# Agrupación, normalización y ajustes
# ---------------------------------------------------------------------------
def pooled_sd(values) -> float:
    """Combina SD de varias mediciones: ``sqrt(media de varianzas)``."""
    values = np.asarray(values, dtype=float)
    return float(np.sqrt(np.nanmean(values**2))) if values.size else float("nan")


def collapse_conditions(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Una fila por dispositivo+condición a partir de una fila por medición."""
    if df_raw.empty:
        return df_raw
    return df_raw.groupby(["device", "condition"], as_index=False).agg(
        measurement=("measurement", "first"),
        conc=("conc", "first"),
        n_measurements=("measurement", "count"),
        n_replicas=("n_replicas", "sum"),
        mean=("mean", "mean"),
        sd=("sd", pooled_sd),
    )


def add_response(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega ``R`` y ``R_sd`` normalizando contra la ``Ref`` del dispositivo."""
    out = df.copy()
    out["R"] = np.nan
    out["R_sd"] = np.nan
    for _, group in out.groupby("device"):
        ref = group[group["condition"] == "Ref"]
        if ref.empty:
            continue
        i_ref = float(ref["mean"].iloc[0])
        out.loc[group.index, "R"] = (group["mean"] - i_ref) / i_ref
        out.loc[group.index, "R_sd"] = group["sd"] / abs(i_ref)
    return out


def extract_reading(
    hdf5_path,
    measurements: list[str],
    v_read: float,
    method: str = "point",
    window: float = 0.05,
    side: str = V_WINDOW_SIDE,
    min_points: int = MIN_POINTS,
) -> pd.DataFrame:
    """Extrae ``I_DS`` por medición y normaliza contra la ``Ref``.

    Parameters
    ----------
    method : {'point', 'window'}
        ``point`` interpola en ``V_READ``; ``window`` promedia ``I_DS`` en
        ``[V_READ, V_READ + window]`` (hacia el interior del barrido).
    """
    if method not in ("point", "window"):
        raise ValueError("method debe ser 'point' o 'window'")

    rows = []
    for measurement in measurements:
        curves = [
            curve
            for curve in read_all_curves(hdf5_path, measurement, direction="fwd")
            if len(curve["v_gs"]) >= min_points
        ]
        if not curves:
            continue

        if method == "point":
            values = np.array(
                [i_ds_at(c["v_gs"], c["i_ds"], v_read) for c in curves], dtype=float
            )
            values = values[np.isfinite(values)]
            if values.size == 0:
                continue
        else:
            values = np.array(
                [
                    i_ds_window_mean(c["v_gs"], c["i_ds"], v_read, window, side)
                    for c in curves
                ],
                dtype=float,
            )
            values = values[np.isfinite(values)]
            if values.size == 0:
                continue

        device, stage, condition, _ = parse_measurement_name(measurement)
        rows.append(
            {
                "measurement": measurement,
                "device": device,
                "stage": stage,
                "condition": condition,
                "conc": cond_conc(condition),
                "n_replicas": int(values.size),
                "mean": float(np.mean(values)),
                "sd": float(np.std(values, ddof=1)) if values.size > 1 else 0.0,
            }
        )

    columns = [
        "measurement",
        "device",
        "stage",
        "condition",
        "conc",
        "n_replicas",
        "mean",
        "sd",
    ]
    raw = pd.DataFrame(rows, columns=columns)
    return add_response(collapse_conditions(raw))


def excluded_mask(devices: pd.Series, exclude=()) -> pd.Series:
    """``True`` para dispositivos que coinciden exacta o por prefijo (``D2``)."""
    exclude = set(exclude)
    return devices.apply(
        lambda device: device in exclude or str(device).split("B")[0] in exclude
    )


def calibration_frame(df: pd.DataFrame, exclude=()) -> pd.DataFrame:
    """Datos de calibración (sin ``Ref``) con ``logC`` listos para el ajuste."""
    cal = df[
        (df["condition"] != "Ref") & (~excluded_mask(df["device"], exclude))
    ].copy()
    cal["logC"] = np.log10(cal["conc"])
    return cal.dropna(subset=["R", "logC"]).sort_values("logC")


def batch_curve(df_device: pd.DataFrame, exclude=()) -> pd.DataFrame:
    """Una fila por concentración con media y SD entre dispositivos."""
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
    return (
        pd.DataFrame(rows, columns=columns)
        .sort_values("logC")
        .reset_index(drop=True)
    )


def fit_summary(level: str, x, y) -> dict:
    """Ajuste ``y = a + b x`` y resumen de métricas."""
    result = linregress(np.asarray(x, dtype=float), np.asarray(y, dtype=float))
    return {
        "nivel": level,
        "b": result.slope,
        "se_b": result.stderr,
        "R2": result.rvalue**2,
        "n": int(len(x)),
    }


def fit_calibration(
    df_point: pd.DataFrame, df_window: pd.DataFrame, exclude=()
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ajustes por dispositivo y batch para ambos métodos.

    Returns
    -------
    df_fits : pandas.DataFrame
        Columnas ``metodo``, ``nivel``, ``b``, ``se_b``, ``R2``, ``n``.
    df_batch : pandas.DataFrame
        Curva del batch de ambos métodos, con la columna ``metodo``.
    """
    fit_rows = []
    batch_parts = []

    for method, frame in [("Punto único", df_point), ("Ventana", df_window)]:
        cal = calibration_frame(frame, exclude)
        if cal.empty:
            continue

        for device, group in cal.groupby("device"):
            group = group.sort_values("logC")
            fit_rows.append(
                {
                    "metodo": method,
                    **fit_summary(device, group["logC"], group["R"]),
                }
            )

        batch = batch_curve(frame, exclude)
        if not batch.empty:
            fit_rows.append(
                {
                    "metodo": method,
                    **fit_summary("Batch", batch["logC"], batch["R_mean"]),
                }
            )
            batch.insert(0, "metodo", method)
            batch_parts.append(batch)

    fit_columns = ["metodo", "nivel", "b", "se_b", "R2", "n"]
    df_fits = pd.DataFrame(fit_rows, columns=fit_columns)

    batch_columns = [
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
        pd.concat(batch_parts, ignore_index=True)
        if batch_parts
        else pd.DataFrame(columns=batch_columns)
    )
    return df_fits, df_batch
