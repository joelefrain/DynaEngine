import matplotlib.pyplot as plt
import random


def plot_section_with_columns(
    layer_polygons,
    external_pline,
    material_pline,
    failure_pline,
    freatic_pline,
    columns=None,
    x_positions=None,
    width=10,
):

    section_fig, ax = plt.subplots()

    # =========================
    # 1. DIBUJAR SECCIÓN
    # =========================
    for nombre, poly_dict in layer_polygons:
        poly = poly_dict["geometry"]
        pid = poly_dict["id"]

        x, y = poly.exterior.xy
        color = (random.random(), random.random(), random.random())

        ax.fill(x, y, facecolor=color, edgecolor="black", alpha=0.35, linewidth=1)

        centro = poly.representative_point()
        ax.text(
            centro.x,
            centro.y,
            f"{nombre}\nID:{pid}",
            ha="center",
            va="center",
            fontsize=9,
            fontweight="bold",
            color="black",
        )

    # Líneas externas
    for pl in external_pline:
        x = [p[0] for p in pl]
        y = [p[1] for p in pl]
        ax.plot(x, y, linestyle="--", color="black")

    # Líneas de material
    for pl in material_pline:
        x = [p[0] for p in pl]
        y = [p[1] for p in pl]
        ax.plot(x, y, linestyle=":", color="gray")

    # Superficie de falla
    for pl in failure_pline:
        x = [p[0] for p in pl]
        y = [p[1] for p in pl]
        ax.plot(x, y, color="red", linewidth=2)

    # Freático
    for pl in freatic_pline:
        x = [p[0] for p in pl]
        y = [p[1] for p in pl]
        ax.plot(x, y, color="blue", linewidth=2)

    # =========================
    # 2. COLUMNAS (OPCIONAL)
    # =========================
    if columns and x_positions:
        colores = [
            "gold",
            "orange",
            "green",
            "skyblue",
            "violet",
            "salmon",
            "lightgray",
        ]

        all_polys = [poly_dict["geometry"] for _, poly_dict in layer_polygons]
        if not all_polys:
            print("No hay polígonos para graficar columnas")
        else:
            y_base = min(poly.bounds[1] for poly in all_polys)

            plot_items = []
            if isinstance(columns, dict) and all(isinstance(v, dict) and any(k.startswith("column_") for k in v.keys()) for v in columns.values()):
                for failure_name, cols in columns.items():
                    xs = x_positions.get(failure_name, []) if isinstance(x_positions, dict) else []
                    for i, (col_name, col_data) in enumerate(cols.items()):
                        if i < len(xs):
                            plot_items.append((f"{col_name}-{failure_name}", col_data, xs[i]))
            else:
                xs = x_positions if isinstance(x_positions, (list, tuple)) else []
                for i, (col_name, col_data) in enumerate(columns.items()):
                    if i < len(xs):
                        plot_items.append((col_name, col_data, xs[i]))

            for col_name, col_data, x in plot_items:
                layers = list(reversed(col_data["layers"]))

                if not layers:
                    continue

                y_actual = y_base

                for j, layer in enumerate(layers):
                    thickness = layer["thickness"]
                    material = layer["material"]

                    color = colores[j % len(colores)]

                    rect = plt.Rectangle(
                        (x - width / 2, y_actual),
                        width,
                        thickness,
                        facecolor=color,
                        edgecolor="black",
                        alpha=0.6,
                    )

                    ax.add_patch(rect)

                    ax.text(
                        x,
                        y_actual + thickness / 2,
                        material,
                        ha="center",
                        va="center",
                        fontsize=7,
                    )

                    y_actual += thickness

                ax.text(
                    x,
                    y_base - 4,
                    col_name,
                    ha="center",
                    fontsize=9,
                    fontweight="bold",
                    color="brown",
                    alpha=0.7,
                )

    # =========================
    # 3. FORMATO
    # =========================
    ax.set_aspect("equal", adjustable="box")

    if columns and x_positions:
        ax.set_title("Sección con columnas")
    else:
        ax.set_title("Sección")

    ax.set_xlabel("X")
    ax.set_ylabel("Elevación")

    plt.grid(True, linestyle="--", alpha=0.3)

    return section_fig
