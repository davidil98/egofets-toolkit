"""Functions to plot EGOFET measurements."""

import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import linregress

from .readers.keithley_dean import list_measurements, read_all_curves, _select_direction


def plot_transfer(hdf5_path, measurement_name, direction: str='both', ax=None):
    """Grafica todas las curvas de una medicion transfer desde un HDF5.

    Cada V_DS se dibuja con un color distinto.
    
    Direction puede ser: 
    'fwd' (ida),
    'reverse' (vuelta)
    o 'both' (ambas). En el caso de 'both', la ida se dibuja con linea solida y la vuelta con linea discontinua.
    
    Para añadir más curvas a la misma figura, se recomienda como ejemplo:
    
    >>> fig, ax = plot_transfer(hdf5_path, measurement_name, direction='fwd')
    >>> ax.plot(v_gs, i_ds, 'o-', ms=3, color='red', label='otra curva')

    Parameters
    ----------
    hdf5_path : str o Path
        Ruta al archivo HDF5.
    measurement_name : str
        Nombre del grupo top-level dentro del HDF5.
    direction : str, opcional
        Direccion del barrido a graficar:
        'fwd' (ida), 'reverse' (vuelta) o 'both' (ambas). Default 'both'.
    ax : matplotlib.axes.Axes, opcional
        Ejes donde graficar. Si es None, se crea una figura nueva.

    Returns
    -------
    fig, ax
    """
    if direction not in ('fwd', 'reverse', 'both'):
        raise ValueError(
            f"direction '{direction}' no soportada. Usa 'fwd', 'reverse' o 'both'."
        )

    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 5))
    else:
        fig = ax.figure

    colors = plt.cm.tab10.colors
    curves = read_all_curves(hdf5_path, measurement_name)

    for i, c in enumerate(curves):
        v_gs = c['v_gs']
        i_ds = c['i_ds']
        v_ds = c['v_ds']
        curve_name = c['curve_name']
        curve_idx = curve_name.split('_')[-1]
        color = colors[i % len(colors)]
        label = f'{float(v_ds[0]):.2f} V (#{curve_idx})'

        v_fwd, i_fwd = _select_direction(v_gs, i_ds, 'fwd')
        v_rev, i_rev = _select_direction(v_gs, i_ds, 'reverse')

        if direction in ('fwd', 'both'):
            ax.plot(v_fwd, i_fwd, 'o-', ms=3, color=color, label=label)

        if direction in ('reverse', 'both'):
            ax.plot(v_rev, i_rev, 'o--', ms=3, color=color,
                    label=label if direction == 'reverse' else '_nolegend_')

    ax.set_xlabel(r"$V_{GS}$ (V)")
    ax.set_ylabel(r"$I_{DS}$ (A)")
    ax.set_title(f"Transfer — {measurement_name}")
    ax.legend(fontsize=8, title=r'$V_{DS}$')
    ax.grid(True, alpha=0.3)

    return fig, ax

def plot_output(hdf5_path, measurement_name, ax=None, direction: str = 'both'):
    """Grafica todas las curvas de una medicion output desde un HDF5.

    Cada V_GS se dibuja con un color distinto.

    Parameters
    ----------
    hdf5_path : str o Path
        Ruta al archivo HDF5.
    measurement_name : str
        Nombre del grupo top-level dentro del HDF5.
    ax : matplotlib.axes.Axes, opcional
        Ejes donde graficar. Si es None, se crea una figura nueva.
    direction : str, opcional
        Aceptado por compatibilidad con ``plot_grid``. En una medicion output
        V_GS es constante, asi que el barrido no se recorta.

    Returns
    -------
    fig, ax
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 5))
    else:
        fig = ax.figure

    colors = plt.cm.tab10.colors
    curves = read_all_curves(hdf5_path, measurement_name)

    for i, c in enumerate(curves):
        v_gs = c['v_gs']
        i_ds = c['i_ds']
        v_ds = c['v_ds']
        curve_name = c['curve_name']
        curve_idx = curve_name.split('_')[-1]
        color = colors[i % len(colors)]
        
        ax.plot(v_ds, i_ds, 'o-', ms=3, color=color,
                label=f'{float(v_gs[0]):.2f} V (#{curve_idx})') # Es el primer valor porque se repite para todas las mediciones.

    ax.set_xlabel(r"$V_{DS}$ (V)")
    ax.set_ylabel(r"$I_{DS}$ (A)")
    ax.set_title(f"Output — {measurement_name}")
    ax.legend(fontsize=8, title=r'$V_{GS}$')
    ax.grid(True, alpha=0.3)

    return fig, ax

def plot_transfer_vread(
    hdf5_path,
    measurement_name,
    v_read,
    ax=None,
    direction: str = 'fwd',
    min_points: int = 5,
):
    """Curvas forward de una medicion transfer + punto interpolado en V_READ.

    Ademas de dibujar la transfer con :func:`plot_transfer`, marca una estrella
    por replica en ``V_READ`` y una linea vertical en ese ``V_GS``.

    La firma es compatible con :func:`plot_grid`, que la llama como
    ``plot_func(hdf5_path, m_name, ax=ax, direction='fwd')``; en un notebook se
    puede pasar ``v_read`` con ``functools.partial`` o una lambda.
    """
    fig, ax = plot_transfer(
        hdf5_path, measurement_name, direction=direction, ax=ax
    )

    for curve in read_all_curves(hdf5_path, measurement_name, direction=direction):
        if len(curve['v_gs']) < min_points:
            continue
        v = np.asarray(curve['v_gs'], dtype=float)
        i = np.asarray(curve['i_ds'], dtype=float)
        order = np.argsort(v)
        i_read = float(np.interp(v_read, v[order], i[order]))
        ax.plot(v_read, i_read, 'r*', ms=9, zorder=5)

    ax.axvline(v_read, color='gray', ls='--', lw=0.8)
    return ax


def plot_transfer_linearized(
    hdf5_path,
    measurement_name,
    v_min=None,
    v_max=None,
    ax=None,
    direction: str = 'fwd',
):
    """Linealizacion ``sqrt(|I_DS|)`` de una transfer con la recta de ajuste.

    Usa la curva de mayor ``|V_DS|`` (la mas cercana a saturacion) y ajusta una
    recta en ``[v_min, v_max]``. Si ``v_min`` o ``v_max`` son ``None`` se usa
    todo el barrido. La firma es compatible con :func:`plot_grid`; para fijar la
    ventana se puede envolver con ``functools.partial`` o una lambda.

    Returns
    -------
    matplotlib.axes.Axes
        Eje con la linealizacion, la recta y una etiqueta con ``V_th``/``R^2``.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(5, 4))

    curves = read_all_curves(hdf5_path, measurement_name, direction=direction)
    if not curves:
        ax.text(0.5, 0.5, 'Sin curvas', transform=ax.transAxes,
                ha='center', va='center')
        return ax

    curve = max(curves, key=lambda c: abs(float(c['v_ds'][0])))
    v_gs = np.asarray(curve['v_gs'], dtype=float)
    i_ds = np.asarray(curve['i_ds'], dtype=float)
    sqrt_ids = np.sqrt(np.abs(i_ds))

    lo = float(np.min(v_gs)) if v_min is None else float(v_min)
    hi = float(np.max(v_gs)) if v_max is None else float(v_max)
    mask = (v_gs >= lo) & (v_gs <= hi)

    ax.plot(v_gs, sqrt_ids, 'o-', ms=3, color='C3',
            label=r'$\sqrt{|I_{DS}|}$')
    if mask.sum() >= 2:
        result = linregress(v_gs[mask], sqrt_ids[mask])
        x_fit = np.array([lo, hi])
        ax.plot(x_fit, result.intercept + result.slope * x_fit, '--',
                color='C2', lw=2,
                label=(f'$V_{{th}}$={-result.intercept / result.slope:.3f} V, '
                       f'$R^2$={result.rvalue ** 2:.3f}'))
        ax.axvline(lo, color='gray', ls=':', lw=0.8)
        ax.axvline(hi, color='gray', ls=':', lw=0.8)

    ax.set_xlabel(r"$V_{GS}$ (V)")
    ax.set_ylabel(r"$\sqrt{|I_{DS}|}$ ($\sqrt{A}$)")
    ax.set_title(f"Linealizacion — {measurement_name}", fontsize=9)
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)
    return ax


def plot_grid(hdf5_path, measurements: list, plot_func: callable, ncols: int = 3, figsize_per: tuple = (5, 4), title_suffix: str = None):
    """Crea una figura y grafica varias mediciones en una grilla de subplots usando la funcion plot_func a partir de un HDF5.
    
    Es posible asignar un sufijo al titulo de la figura.
    
    uso:
    >>> fig = plot_grid(hdf5_path, transfer_measurements, plot_transfer, ncols=3, title_suffix="Transfer curves")
    >>> plt.show()

    Args:
        hdf5_path : str o Path
            Ruta al archivo HDF5.
        measurements : list of str
            Lista de nombres de mediciones a graficar.
        plot_func : callable
            Función para graficar cada medición. Debe aceptar los argumentos (hdf5_path, measurement_name, ax).
        ncols : int, optional
            Número de columnas en la grilla. Defaults to 3.
        figsize_per : tuple, optional
            Tamaño de cada subplot. Defaults to (5, 4).
        title_suffix: str, optional
            Sufijo para el título de la figura. Defaults to None.

    Returns:
        fig : matplotlib.figure.Figure
            La figura creada con la grilla de subplots.
    """
    n = len(measurements)
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(figsize_per[0]*ncols, figsize_per[1]*nrows))
    axes_flat = np.array(axes).flatten() if n > 1 else np.array([axes])
    for ax, m_name in zip(axes_flat, measurements):
        plot_func(hdf5_path, m_name, ax=ax, direction='fwd') # Solo fordward para la calibración.
    for ax in axes_flat[len(measurements):]:
        ax.set_visible(False)
    if title_suffix:
        fig.suptitle(title_suffix, fontsize=14, fontweight="bold")
        fig.tight_layout(rect=[0, 0, 1, 0.98])
    else:
        fig.tight_layout()
    return fig

def plot_i_vs_time(hdf5_path, measurement_name, array_time: np.ndarray, ax=None):
    """Grafica Ids vs time para una medicion i-vs-t desde un HDF5."""