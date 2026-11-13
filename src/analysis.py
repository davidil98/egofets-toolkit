"""Modulo para extraer parametros de mediciones EGOFET."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import linregress

from .readers.keithley_dean import read_all_curves


# ---------------------------------------------------------------------------
# Utilidades de señal
# ---------------------------------------------------------------------------
def clean_forward_branch(v_gs, i_ds, rel_tol: float = 0.25):
    """Ordena ``V_GS`` ascendente y descarta el punto de retorno duplicado.

    ``read_curve(..., direction='fwd')`` conserva el punto de giro del barrido,
    que repite el ``V_GS`` del borde con una diferencia de ~1e-5 V. Ese punto
    haría que ``np.gradient`` dividiera por un paso casi nulo y generara un
    pico artificial de ``g_m``.
    """
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
    """Devuelve ``(V_GS, I_DS, g_m)`` de la rama forward ya limpia."""
    v, i = clean_forward_branch(v_gs, i_ds)
    if v.size < 2:
        return v, i, np.array([])
    return v, i, np.gradient(i, v)


def _saturation_curve(curves: list[dict]) -> dict | None:
    """Curva con ``|V_DS|`` máximo (la más cercana a saturación)."""
    if not curves:
        return None
    return max(curves, key=lambda curve: abs(float(curve["v_ds"][0])))


def _best_fit_window(
    v_gs,
    y,
    v_min_range: tuple[float, float],
    v_max_range: tuple[float, float],
    step: float,
    min_points: int,
):
    """Busca la ventana ``(v_min, v_max)`` que maximiza ``R^2``.

    Returns
    -------
    tuple or None
        ``(v_min, v_max, slope, intercept, r2, n_points)``.
    """
    best_r2 = -np.inf
    best = None
    for v_min in np.arange(v_min_range[0], v_min_range[1], step):
        for v_max in np.arange(v_max_range[0], v_max_range[1], step):
            if v_max <= v_min:
                continue
            mask = (v_gs >= v_min) & (v_gs <= v_max)
            if mask.sum() < min_points:
                continue
            slope, intercept, r_value, _, _ = linregress(v_gs[mask], y[mask])
            r2 = r_value**2
            if r2 > best_r2:
                best_r2 = r2
                best = (v_min, v_max, slope, intercept, r2, int(mask.sum()))
    return best


def _subthreshold_swing(v_gs, i_ds) -> float:
    """``SS = min |dV_GS / d log10|I_DS||`` en V/dec."""
    v = np.asarray(v_gs, dtype=float)
    abs_i = np.abs(np.asarray(i_ds, dtype=float))
    if v.size < 3 or not np.any(abs_i > 0):
        return float("nan")

    floor = abs_i.max() * 1e-9
    log_i = np.log10(np.clip(abs_i, floor, None))
    dv = np.diff(v)
    dlog = np.diff(log_i)
    valid = np.isfinite(dlog) & (np.abs(dlog) > 1e-12) & (abs_i[1:] > floor)
    if not np.any(valid):
        return float("nan")
    return float(np.min(np.abs(dv[valid] / dlog[valid])))


def extract_vth_for_transfers(
    hdf5_path,
    measurements,
    v_min_range=(-0.40, -0.20),
    v_max_range=(-0.15, -0.05),
    step=0.01,
    min_points=5,
):
    """Extrae V_th de multiples mediciones transfer con busqueda 2D de ventana.

    Para cada medicion:
      - Toma la curva con |V_DS| maximo (saturacion).
      - Calcula sqrt(|I_DS|) en el forward sweep.
      - Busca la mejor combinacion (v_min, v_max) dentro del rectangulo
        definido que maximice R^2.
      - Calcula V_th = -intercept/slope de la regresion lineal en esa ventana.

    Parameters
    ----------
    hdf5_path : str o Path
    measurements : list[str]
        Nombres de mediciones de tipo transfer.
    v_min_range, v_max_range : tuple
        (min, max) del extremo izquierdo/derecho de la ventana, en V.
    step : float
        Resolucion de la busqueda en V.
    min_points : int
        Minimo de puntos para aceptar un fit.

    Returns
    -------
    pd.DataFrame
        Columnas: measurement, V_DS (V), V_th (V), v_min (V), v_max (V),
        R^2, n_points.
    """
    results = []
    for m_name in measurements:
        try:
            curves = read_all_curves(hdf5_path, m_name, direction="fwd")
            curve = _saturation_curve(curves)
            if curve is None:
                continue

            v_gs_fwd, i_ds_fwd = curve["v_gs"], curve["i_ds"]
            sqrt_ids = np.sqrt(np.abs(i_ds_fwd))
            best = _best_fit_window(
                v_gs_fwd, sqrt_ids, v_min_range, v_max_range, step, min_points
            )
            if best is None:
                print(f"{m_name}: ninguna ventana valida en el rectangulo")
                continue

            v_min, v_max, slope, intercept, best_r2, n_pts = best
            v_th = -intercept / slope

            results.append(
                {
                    "measurement": m_name,
                    "V_DS (V)": float(curve["v_ds"][0]),
                    "V_th (V)": v_th,
                    "v_min (V)": v_min,
                    "v_max (V)": v_max,
                    "R^2": best_r2,
                    "n_points": n_pts,
                }
            )
        except Exception as exc:
            print(f"{m_name}: {exc}")
            continue

    return pd.DataFrame(results)


def extract_transfer_metrics(
    hdf5_path,
    measurements,
    v_min_range=(-0.40, -0.20),
    v_max_range=(-0.15, -0.05),
    step=0.01,
    min_points=5,
):
    """Resume las metricas de transfer de cada medicion.

    Combina la extraccion de ``V_th`` (ventana que maximiza ``R^2`` en
    ``sqrt(|I_DS|)``) con metricas de conmutacion calculadas sobre la misma
    rama forward y la curva de mayor ``|V_DS|``:

    - ``SS (V/dec)``: subthreshold swing mínimo.
    - ``I_on`` / ``I_off``: máximo y mínimo de ``|I_DS|`` en el barrido.
    - ``I_on/I_off``: relación de conmutación.
    - ``gm_max`` y ``V_GS@gm_max``: transconductancia máxima.

    Returns
    -------
    pd.DataFrame
        Columnas: measurement, V_DS (V), V_th (V), R^2, v_min (V),
        v_max (V), n_points, SS (V/dec), I_on (A), I_off (A),
        I_on/I_off, gm_max (A/V), V_GS_gm (V).
    """
    rows = []
    for m_name in measurements:
        try:
            curves = read_all_curves(hdf5_path, m_name, direction="fwd")
            curve = _saturation_curve(curves)
            if curve is None:
                continue

            v_gs, i_ds = curve["v_gs"], curve["i_ds"]
            if len(v_gs) < min_points:
                continue

            sqrt_ids = np.sqrt(np.abs(i_ds))
            best = _best_fit_window(
                v_gs, sqrt_ids, v_min_range, v_max_range, step, min_points
            )
            if best is None:
                continue

            v_min, v_max, slope, intercept, r2, n_pts = best
            v_th = -intercept / slope

            v_clean, i_clean, gm = forward_gm(v_gs, i_ds)
            abs_i = np.abs(i_clean)
            positive = abs_i[abs_i > 0]
            i_on = float(abs_i.max()) if abs_i.size else float("nan")
            i_off = float(positive.min()) if positive.size else float("nan")
            ratio = i_on / i_off if i_off else float("nan")

            if gm.size:
                gm_index = int(np.argmax(np.abs(gm)))
                gm_max = float(abs(gm[gm_index]))
                v_gs_gm = float(v_clean[gm_index])
            else:
                gm_max = float("nan")
                v_gs_gm = float("nan")

            rows.append(
                {
                    "measurement": m_name,
                    "V_DS (V)": float(curve["v_ds"][0]),
                    "V_th (V)": float(v_th),
                    "R^2": float(r2),
                    "v_min (V)": float(v_min),
                    "v_max (V)": float(v_max),
                    "n_points": int(n_pts),
                    "SS (V/dec)": _subthreshold_swing(v_clean, i_clean),
                    "I_on (A)": i_on,
                    "I_off (A)": i_off,
                    "I_on/I_off": float(ratio),
                    "gm_max (A/V)": gm_max,
                    "V_GS_gm (V)": v_gs_gm,
                }
            )
        except Exception as exc:
            print(f"{m_name}: {exc}")
            continue

    return pd.DataFrame(rows)


def output_branch(v_ds, i_ds):
    """Rama de ida de un barrido output (desde el inicio hasta ``V_DS`` mínimo)."""
    v = np.asarray(v_ds, dtype=float)
    i = np.asarray(i_ds, dtype=float)
    if v.size == 0:
        return v, i
    stop = int(np.argmin(v))
    return v[: stop + 1], i[: stop + 1]


def extract_output_metrics(
    hdf5_path,
    measurements,
    linear_limit: float = 0.1,
    min_points: int = 5,
):
    """Metricas data-driven de curvas output.

    Para cada curva (un ``V_GS``) se toma la rama de ida y se calcula:

    - ``g_lin`` / ``R_on``: pendiente de ``I_DS`` vs ``V_DS`` en
      ``|V_DS| <= linear_limit`` y su inversa.
    - ``I_sat``: ``|I_DS|`` al final del barrido (``V_DS`` mínimo).

    Con ``I_sat`` de todas las curvas se calcula la transconductancia
    ``g_m = dI_sat/dV_GS`` de la medición.

    Returns
    -------
    df_curves : pandas.DataFrame
        Una fila por curva: measurement, V_GS (V), I_sat (A), g_lin (S),
        R_on (ohm), R^2_lin.
    df_summary : pandas.DataFrame
        Una fila por medición: n_curves, V_GS_min/max, I_sat_max, g_lin_max,
        R_on_min, gm_max (A/V), V_GS_gm (V).
    """
    curve_rows = []
    summary_rows = []

    for m_name in measurements:
        curves = [
            curve
            for curve in read_all_curves(hdf5_path, m_name)
            if len(curve["v_ds"]) >= min_points
        ]
        if not curves:
            continue

        per_curve = []
        for curve in curves:
            v_ds, i_ds = output_branch(curve["v_ds"], curve["i_ds"])
            if v_ds.size < 3:
                continue

            v_gs = float(curve["v_gs"][0])
            linear = np.abs(v_ds) <= linear_limit
            if linear.sum() >= 3:
                slope, _, r_value, _, _ = linregress(v_ds[linear], i_ds[linear])
                g_lin = float(abs(slope))
                r2_lin = float(r_value**2)
            else:
                g_lin = float("nan")
                r2_lin = float("nan")

            i_sat = float(abs(i_ds[int(np.argmin(v_ds))]))
            row = {
                "measurement": m_name,
                "V_GS (V)": v_gs,
                "I_sat (A)": i_sat,
                "g_lin (S)": g_lin,
                "R_on (ohm)": 1.0 / g_lin if g_lin and np.isfinite(g_lin) else float("nan"),
                "R^2_lin": r2_lin,
            }
            per_curve.append(row)
            curve_rows.append(row)

        if not per_curve:
            continue

        dfc = pd.DataFrame(per_curve).sort_values("V_GS (V)")
        gm_max = float("nan")
        v_gs_gm = float("nan")
        if len(dfc) >= 3:
            gm = np.gradient(
                dfc["I_sat (A)"].to_numpy(dtype=float),
                dfc["V_GS (V)"].to_numpy(dtype=float),
            )
            index = int(np.argmax(np.abs(gm)))
            gm_max = float(abs(gm[index]))
            v_gs_gm = float(dfc["V_GS (V)"].iloc[index])

        g_lin_max = float(dfc["g_lin (S)"].max())
        summary_rows.append(
            {
                "measurement": m_name,
                "n_curves": int(len(dfc)),
                "V_GS_min (V)": float(dfc["V_GS (V)"].min()),
                "V_GS_max (V)": float(dfc["V_GS (V)"].max()),
                "I_sat_max (A)": float(dfc["I_sat (A)"].max()),
                "g_lin_max (S)": g_lin_max,
                "R_on_min (ohm)": 1.0 / g_lin_max if g_lin_max else float("nan"),
                "gm_max (A/V)": gm_max,
                "V_GS_gm (V)": v_gs_gm,
            }
        )

    curve_columns = [
        "measurement",
        "V_GS (V)",
        "I_sat (A)",
        "g_lin (S)",
        "R_on (ohm)",
        "R^2_lin",
    ]
    summary_columns = [
        "measurement",
        "n_curves",
        "V_GS_min (V)",
        "V_GS_max (V)",
        "I_sat_max (A)",
        "g_lin_max (S)",
        "R_on_min (ohm)",
        "gm_max (A/V)",
        "V_GS_gm (V)",
    ]
    return (
        pd.DataFrame(curve_rows, columns=curve_columns),
        pd.DataFrame(summary_rows, columns=summary_columns),
    )
