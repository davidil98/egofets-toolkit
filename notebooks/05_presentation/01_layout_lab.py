import marimo

__generated_with = "0.25.2"
app = marimo.App(width="full", app_title="EGOFET Layout Lab")


@app.cell(hide_code=True)
def _():
    import os
    import sys
    from pathlib import Path

    import matplotlib.pyplot as plt
    import marimo as mo
    import pandas as pd

    return Path, mo, os, pd, plt, sys


@app.cell(hide_code=True)
def _(Path, os, sys):
    def find_project_root(marker="src"):
        cwd = Path(os.getcwd()).resolve()
        for parent in [cwd, *cwd.parents]:
            if (parent / marker).is_dir():
                return parent
        raise FileNotFoundError(f"No se encontro un directorio con '{marker}'")

    PROJECT_ROOT = find_project_root()
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from src.plotting import plot_output, plot_transfer
    from src.readers.keithley_dean import list_measurements

    data_folder = PROJECT_ROOT / "data" / "raw"
    hdf5_files = sorted(p.name for p in data_folder.glob("*.hdf5"))

    default_file = "transf-outp_example.hdf5"
    if default_file not in hdf5_files:
        default_file = hdf5_files[0] if hdf5_files else None
    return (
        data_folder,
        default_file,
        hdf5_files,
        list_measurements,
        plot_output,
        plot_transfer,
    )


@app.cell(hide_code=True)
def _(default_file, hdf5_files, mo):
    file_widget = mo.ui.dropdown(
        options=hdf5_files,
        value=default_file,
        label="Archivo HDF5",
        searchable=True,
        full_width=True,
    )
    pattern_widget = mo.ui.radio(
        options=["Documento", "Sidebar + tabs", "Tabs", "Master-detail"],
        value="Documento",
        label="Patrón de presentación",
    )
    ncols_widget = mo.ui.slider(
        start=1,
        stop=4,
        step=1,
        value=3,
        label="Columnas de la grilla",
        show_value=True,
    )
    max_widget = mo.ui.slider(
        start=1,
        stop=12,
        step=1,
        value=6,
        label="Mediciones en la grilla",
        show_value=True,
    )
    mode_badge = mo.md(f"Modo: `{mo.app_meta().mode}`")

    mo.vstack(
        [
            mo.md("## Controles del laboratorio"),
            mo.hstack([file_widget, pattern_widget], justify="start", gap=1, wrap=True),
            mo.hstack(
                [ncols_widget, max_widget, mode_badge],
                justify="start",
                gap=1,
                wrap=True,
                align="center",
            ),
        ],
        gap=1,
    )
    return file_widget, max_widget, ncols_widget, pattern_widget


@app.cell(hide_code=True)
def _(data_folder, file_widget, hdf5_files, list_measurements, mo):
    mo.stop(
        not hdf5_files,
        mo.callout(
            mo.md(f"No se encontraron archivos `.hdf5` en `{data_folder}`"),
            kind="warn",
        ),
    )
    hdf5_path = data_folder / file_widget.value
    measurements = list_measurements(hdf5_path)
    transfer = [m["name"] for m in measurements if m["mode"] == "transfer"]
    output = [m["name"] for m in measurements if m["mode"] == "output"]
    stability = [m["name"] for m in measurements if m["mode"] == "stability"]
    return hdf5_path, measurements, output, stability, transfer


@app.cell(hide_code=True)
def _(file_widget, hdf5_path, measurements, mo, output, stability, transfer):
    header = mo.vstack(
        [
            mo.md("# EGOFET — Laboratorio de layout"),
            mo.md(
                f"**{file_widget.value}** · {len(measurements)} mediciones · "
                f"`{hdf5_path.parent.name}/{hdf5_path.name}`"
            ),
        ],
        gap=0,
    )
    kpis = mo.hstack(
        [
            mo.stat(len(transfer), label="Transfer", bordered=True),
            mo.stat(len(output), label="Output", bordered=True),
            mo.stat(len(stability), label="Estabilidad", bordered=True),
            mo.stat(
                sum(m["n_curves"] for m in measurements),
                label="Curvas",
                bordered=True,
            ),
        ],
        justify="start",
        gap=1,
        wrap=True,
    )
    return header, kpis


@app.cell(hide_code=True)
def _(
    hdf5_path,
    max_widget,
    mo,
    ncols_widget,
    output,
    plot_output,
    plot_transfer,
    plt,
    transfer,
):
    def figure_html(name, mode):
        if mode == "transfer":
            fig, _ = plot_transfer(hdf5_path, name, direction="fwd")
        else:
            fig, _ = plot_output(hdf5_path, name)
        html = mo.as_html(fig)
        plt.close(fig)
        return html

    if transfer:
        names, _mode = transfer[: max_widget.value], "transfer"
    elif output:
        names, _mode = output[: max_widget.value], "output"
    else:
        names, _mode = [], None

    if names:
        ncols = ncols_widget.value
        rows = []
        for start in range(0, len(names), ncols):
            chunk = names[start : start + ncols]
            rows.append(
                mo.hstack(
                    [figure_html(name, _mode) for name in chunk],
                    justify="start",
                    gap=1,
                    widths="equal",
                )
            )
        grid = mo.vstack(rows, gap=1)
    else:
        grid = mo.callout(
            mo.md("Este archivo no tiene mediciones transfer ni output."),
            kind="warn",
        )
    return (grid,)


@app.cell(hide_code=True)
def _(measurements, mo, pd):
    table_df = pd.DataFrame(
        [
            {"medición": m["name"], "modo": m["mode"], "curvas": m["n_curves"]}
            for m in measurements
        ]
    )
    measurements_table = mo.ui.table(
        table_df,
        selection="single",
        label="Mediciones (seleccioná una para ver el detalle)",
        pagination=False,
        show_data_types=False,
        max_height=320,
    )
    return (measurements_table,)


@app.cell(hide_code=True)
def _(hdf5_path, measurements_table, mo, plot_output, plot_transfer, plt):
    selected = measurements_table.value
    if selected is None or len(selected) == 0:
        detail = mo.callout(
            mo.md("Seleccioná una medición en la tabla."), kind="info"
        )
    else:
        row = selected.iloc[0]
        name, mode = row["medición"], row["modo"]
        fig = None
        if mode == "transfer":
            fig, _ = plot_transfer(hdf5_path, name, direction="both")
        elif mode == "output":
            fig, _ = plot_output(hdf5_path, name)

        if fig is None:
            detail = mo.callout(
                mo.md(f"`{name}` no es transfer ni output; el lab no la grafica."),
                kind="warn",
            )
        else:
            detail = mo.vstack([mo.md(f"### {name}"), mo.as_html(fig)])
            plt.close(fig)
    return (detail,)


@app.cell
def _(grid, header, kpis, measurements_table, mo, pattern_widget):
    mo.stop(pattern_widget.value != "Documento")
    mo.vstack(
        [
            header,
            kpis,
            mo.md("## Curvas"),
            grid,
            mo.md("## Mediciones"),
            measurements_table,
        ],
        gap=1.5,
    )
    return


@app.cell
def _(detail, grid, header, kpis, measurements_table, mo, pattern_widget):
    mo.stop(pattern_widget.value != "Tabs")
    mo.vstack(
        [
            header,
            kpis,
            mo.ui.tabs(
                {
                    "Curvas": grid,
                    "Tabla": measurements_table,
                    "Detalle": detail,
                }
            ),
        ],
        gap=1.5,
    )
    return


@app.cell
def _(hdf5_path, measurements, mo, pattern_widget):
    mo.stop(pattern_widget.value != "Sidebar + tabs")
    mo.sidebar(
        [
            mo.md("# Panel"),
            mo.md(f"**Archivo**\n\n`{hdf5_path.name}`"),
            mo.md(f"**Mediciones**: {len(measurements)}"),
            mo.md(
                "Los parámetros de análisis viven en el código. "
                "Acá solo hay navegación y lectura."
            ),
        ]
    )
    return


@app.cell
def _(detail, grid, header, kpis, measurements_table, mo, pattern_widget):
    mo.stop(pattern_widget.value != "Sidebar + tabs")
    mo.vstack(
        [
            header,
            kpis,
            mo.ui.tabs(
                {
                    "Curvas": grid,
                    "Tabla": measurements_table,
                    "Detalle": detail,
                }
            ),
        ],
        gap=1.5,
    )
    return


@app.cell
def _(detail, header, kpis, measurements_table, mo, pattern_widget):
    mo.stop(pattern_widget.value != "Master-detail")
    mo.vstack(
        [
            header,
            kpis,
            mo.hstack(
                [measurements_table, detail],
                widths=[1, 2],
                justify="start",
                gap=1.5,
                align="start",
            ),
        ],
        gap=1.5,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ---
    **Laboratorio de layout.** Este notebook no analiza datos: prueba
    disposiciones para los reportes Marimo. Cambiar de patrón y compara el
    resultado con `marimo run notebooks/07_presentation/01_layout_lab.py`.
    """)
    return


if __name__ == "__main__":
    app.run()
