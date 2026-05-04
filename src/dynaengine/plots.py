"""Matplotlib helpers used by examples and notebooks."""

from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

from dynaengine.columns import ShearVelocityProfile
from dynaengine.dxf import MINIMUM_AREA_SCALE, summarize_polygon_areas
from dynaengine.dynamic_curves import DynamicCurveResult


def plot_dynamic_curve(result: DynamicCurveResult):
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    axes[0].semilogx(result.strain, result.ggmax)
    axes[0].set_title("Reduccion de modulo")
    axes[0].set_xlabel("Deformacion cortante, gamma")
    axes[0].set_ylabel("G/Gmax")

    axes[1].semilogx(result.strain, result.damping_percent)
    axes[1].set_title("Amortiguamiento")
    axes[1].set_xlabel("Deformacion cortante, gamma")
    axes[1].set_ylabel("Damping (%)")

    axes[2].semilogx(result.strain, result.shear_stress_kpa)
    axes[2].set_title("Esfuerzo-deformacion")
    axes[2].set_xlabel("Deformacion cortante, gamma")
    axes[2].set_ylabel("Tau (kPa)")

    for axis in axes:
        axis.grid(True, which="both", alpha=0.25)
        axis.tick_params(axis="both", which="both", labelsize=8)
    fig.tight_layout()
    return fig, axes


def plot_shear_velocity_profile(profile: ShearVelocityProfile):
    fig, axis = plt.subplots(figsize=(4, 6))
    velocity = list(profile.velocity_m_s)
    depth = list(profile.depth_m)

    x_values = []
    y_values = []
    for index in range(len(depth) - 1):
        x_values.extend([velocity[index], velocity[index]])
        y_values.extend([depth[index], depth[index + 1]])
    x_values.append(velocity[-1])
    y_values.append(depth[-1])

    axis.step(x_values, y_values, where="post")
    axis.invert_yaxis()
    axis.set_title("Perfil Vs")
    axis.set_xlabel("Vs (m/s)")
    axis.set_ylabel("Profundidad (m)")
    axis.grid(True, which="both", alpha=0.25)
    axis.tick_params(axis="both", which="both", labelsize=8)
    fig.tight_layout()
    return fig, axis


def plot_dxf_extraction(
    clean_polygons: list[tuple[str, dict]],
    x_positions: list[float] | None = None,
    figsize: tuple[float, float] = (12, 8),
    highlight_small_areas: bool = False,
    small_area_scale: float = MINIMUM_AREA_SCALE,
    annotate_areas: bool = False,
    failure_polylines: dict[str, list[tuple[float, float]]] | list | None = None,
    failure_surfaces: dict[str, dict] | None = None,
    annotate_failures: bool = True,
    annotate_x_positions: bool = False,
) -> tuple:
    """Plot DXF extraction with material areas colored differently.

    Args:
        clean_polygons: List of (material_name, polygon_dict) tuples
        x_positions: Optional list of x positions where columns are extracted
        figsize: Figure size
        highlight_small_areas: If True, mark polygons whose area is small
            relative to the total DXF section area.
        small_area_scale: Small-area threshold as area/total_area.
        annotate_areas: If True, annotate each polygon with its area ratio.
        failure_polylines: Optional failure-surface polylines, either as a
            dict keyed by failure name or a list ordered as failure_1, failure_2, ...
        failure_surfaces: Optional failure-surface metadata used in labels.
        annotate_failures: If True, place failure names on their polylines.
        annotate_x_positions: If True, label extracted x-position guide lines.

    Returns:
        Tuple of (fig, axis)
    """
    fig, axis = plt.subplots(figsize=figsize)

    material_names = sorted({name for name, _ in clean_polygons})
    color_map = {name: plt.cm.tab20(i % 20) for i, name in enumerate(material_names)}
    area_summary = {
        row["polygon_id"]: row
        for row in summarize_polygon_areas(clean_polygons, small_area_scale)
    }

    for material_name, polygon_dict in clean_polygons:
        geometry = polygon_dict["geometry"]
        if hasattr(geometry, "exterior"):
            small_area = area_summary.get(polygon_dict.get("id"), {}).get(
                "is_small_area", False
            )
            edgecolor = "crimson" if highlight_small_areas and small_area else "black"
            linewidth = 2.0 if highlight_small_areas and small_area else 0.5
            hatch = "///" if highlight_small_areas and small_area else None
            x_coords, y_coords = geometry.exterior.xy
            axis.fill(
                x_coords,
                y_coords,
                alpha=0.6,
                color=color_map[material_name],
                edgecolor=edgecolor,
                linewidth=linewidth,
                hatch=hatch,
                label=material_name if material_name else "Unknown",
            )
            axis.plot(x_coords, y_coords, color=edgecolor, linewidth=max(linewidth, 1))

            if annotate_areas:
                centroid = geometry.representative_point()
                ratio = area_summary.get(polygon_dict.get("id"), {}).get(
                    "area_ratio_to_total"
                )
                if ratio is not None:
                    axis.text(
                        centroid.x,
                        centroid.y,
                        f"A/Atotal={ratio:.3f}",
                        ha="center",
                        va="center",
                        fontsize=7,
                        bbox={
                            "boxstyle": "round,pad=0.2",
                            "fc": "white",
                            "alpha": 0.65,
                        },
                    )

    if failure_polylines:
        for index, (failure_name, polyline) in enumerate(
            _iter_named_polylines(failure_polylines), start=1
        ):
            if len(polyline) < 2:
                continue

            x_coords = [float(point[0]) for point in polyline]
            y_coords = [float(point[1]) for point in polyline]
            color = plt.cm.tab10((index - 1) % 10)
            axis.plot(
                x_coords,
                y_coords,
                color=color,
                linestyle="-",
                linewidth=2.0,
                label=_failure_label(failure_name, failure_surfaces),
                zorder=5,
            )

            if annotate_failures:
                middle = len(x_coords) // 2
                axis.text(
                    x_coords[middle],
                    y_coords[middle],
                    failure_name,
                    color=color,
                    fontsize=8,
                    weight="bold",
                    ha="center",
                    va="bottom",
                    bbox={
                        "boxstyle": "round,pad=0.2",
                        "fc": "white",
                        "alpha": 0.75,
                    },
                    zorder=6,
                )

    if x_positions:
        for x in x_positions:
            axis.axvline(x=x, color="red", linestyle="--", linewidth=1.5, alpha=0.7)
            if annotate_x_positions:
                _, y_top = axis.get_ylim()
                axis.text(
                    x,
                    y_top,
                    f"x={x:g}",
                    color="red",
                    fontsize=8,
                    rotation=90,
                    ha="right",
                    va="top",
                )

    axis.set_xlabel("X (m)")
    axis.set_ylabel("Elevacion Y (m)")
    axis.set_title("Secciones del DXF - Materiales por Color")
    axis.grid(True, alpha=0.25)

    handles, labels = axis.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    axis.legend(by_label.values(), by_label.keys(), loc="upper right", fontsize=8)

    fig.tight_layout()
    return fig, axis


def _iter_named_polylines(
    polylines: dict[str, list[tuple[float, float]]] | list,
) -> list[tuple[str, list[tuple[float, float]]]]:
    if isinstance(polylines, dict):
        return list(polylines.items())
    return [
        (f"failure_{index + 1}", polyline) for index, polyline in enumerate(polylines)
    ]


def _failure_label(
    failure_name: str,
    failure_surfaces: dict[str, dict] | None,
) -> str:
    metadata = (failure_surfaces or {}).get(failure_name, {})
    height = metadata.get("failure_height")
    if height is None:
        return failure_name
    return f"{failure_name} H={float(height):.2f} m"


def plot_raw_column(
    raw_column: pd.DataFrame,
    figsize: tuple[float, float] = (6, 10),
) -> tuple:
    """Plot non-discretized column with material layers.

    Args:
        raw_column: DataFrame from build_raw_column_table()
        figsize: Figure size

    Returns:
        Tuple of (fig, axis)
    """
    fig, axis = plt.subplots(figsize=figsize)

    material_names = sorted(raw_column["material_name"].unique())
    color_map = {name: plt.cm.tab20(i % 20) for i, name in enumerate(material_names)}

    for _, row in raw_column.iterrows():
        top = row["top_m"]
        bottom = row["bottom_m"]
        material = row["material_name"]

        rect = mpatches.Rectangle(
            (0, top),
            1,
            bottom - top,
            linewidth=1,
            edgecolor="black",
            facecolor=color_map[material],
            alpha=0.7,
        )
        axis.add_patch(rect)

        axis.text(
            0.5,
            (top + bottom) / 2,
            material,
            ha="center",
            va="center",
            fontsize=8,
            weight="bold",
        )

    axis.set_ylim(raw_column["bottom_m"].max(), raw_column["top_m"].min())
    axis.set_xlim(0, 1)
    axis.set_ylabel("Profundidad (m)")
    axis.set_title("Columna No Discretizada")
    axis.grid(True, axis="y", alpha=0.25)
    axis.set_xticks([])

    fig.tight_layout()
    return fig, axis


def plot_discretized_column(
    discretized_column: pd.DataFrame,
    figsize: tuple[float, float] = (6, 10),
) -> tuple:
    """Plot discretized column with material segments colored.

    Args:
        discretized_column: DataFrame from discretize_column()
        figsize: Figure size

    Returns:
        Tuple of (fig, axis)
    """
    fig, axis = plt.subplots(figsize=figsize)

    material_names = sorted(discretized_column["material_name"].unique())
    color_map = {name: plt.cm.tab20(i % 20) for i, name in enumerate(material_names)}

    for _, row in discretized_column.iterrows():
        top = row["top_m"]
        bottom = row["bottom_m"]
        material = row["material_name"]

        rect = mpatches.Rectangle(
            (0, top),
            1,
            bottom - top,
            linewidth=0.5,
            edgecolor="black",
            facecolor=color_map[material],
            alpha=0.7,
        )
        axis.add_patch(rect)

    axis.set_ylim(
        discretized_column["bottom_m"].max(), discretized_column["top_m"].min()
    )
    axis.set_xlim(0, 1)
    axis.set_ylabel("Profundidad (m)")
    axis.set_title("Columna Discretizada")
    axis.grid(True, axis="y", alpha=0.25)
    axis.set_xticks([])

    fig.tight_layout()
    return fig, axis


def plot_column_discretized_detailed(
    discretized_column: pd.DataFrame,
    figsize: tuple[float, float] = (16, 10),
) -> tuple:
    """Plot discretized column with thickness, Vs profile, and frequency profile.

    Args:
        discretized_column: DataFrame from discretize_column()
        figsize: Figure size

    Returns:
        Tuple of (fig, axes)
    """
    fig, axes = plt.subplots(1, 4, figsize=figsize, sharey=True)

    material_names = sorted(discretized_column["material_name"].unique())
    color_map = {name: plt.cm.tab20(i % 20) for i, name in enumerate(material_names)}

    max_depth = discretized_column["bottom_m"].max()
    max_vs = discretized_column["shear_velocity_m_s"].max()
    max_freq = discretized_column["natural_frequency_hz"].max()

    # Plot 1: Materiales discretizados
    ax = axes[0]
    for _, row in discretized_column.iterrows():
        top = row["top_m"]
        bottom = row["bottom_m"]
        material = row["material_name"]

        rect = mpatches.Rectangle(
            (0, top),
            1,
            bottom - top,
            linewidth=0.5,
            edgecolor="black",
            facecolor=color_map[material],
            alpha=0.7,
        )
        ax.add_patch(rect)

    ax.set_xlim(0, 1)
    ax.set_ylim(max_depth, 0)
    ax.set_title("Materiales", weight="bold")
    ax.set_xticks([])
    ax.grid(True, axis="y", alpha=0.25)

    # Plot 2: Thickness
    ax = axes[1]
    thickness_values = discretized_column["thickness_m"].values
    depths = (discretized_column["top_m"] + discretized_column["bottom_m"]).values / 2
    ax.barh(
        depths,
        thickness_values,
        height=discretized_column["thickness_m"].values,
        left=0,
        color="steelblue",
        alpha=0.7,
        edgecolor="black",
        linewidth=0.5,
    )
    ax.set_xlim(0, discretized_column["thickness_m"].max() * 1.1)
    ax.set_xlabel("Thickness (m)")
    ax.set_title("Espesor de Estrato", weight="bold")
    ax.grid(True, axis="x", alpha=0.25)

    # Plot 3: Shear Velocity Profile
    ax = axes[2]
    vs_x, vs_y = _segment_profile_xy(discretized_column, "shear_velocity_m_s")
    ax.plot(vs_x, vs_y, color="steelblue", linewidth=2)

    ax.set_xlim(0, max_vs * 1.1)
    ax.set_xlabel("Vs (m/s)")
    ax.set_title("Perfil Vs", weight="bold")
    ax.grid(True, axis="x", alpha=0.25)

    # Plot 4: Natural Frequency Profile
    ax = axes[3]
    freq_x, freq_y = _segment_profile_xy(discretized_column, "natural_frequency_hz")
    ax.plot(freq_x, freq_y, color="darkgreen", linewidth=2)

    ax.set_xlim(0, max_freq * 1.1)
    ax.set_xlabel("Frecuencia Natural (Hz)")
    ax.set_title("Perfil de Frecuencia", weight="bold")
    ax.grid(True, axis="x", alpha=0.25)

    # Set y-label only on first axis
    axes[0].set_ylabel("Profundidad (m)")

    fig.suptitle("Columna Discretizada - Vista Detallada", fontsize=14, weight="bold")
    fig.tight_layout()
    return fig, axes


def _segment_profile_xy(
    frame: pd.DataFrame, value_column: str
) -> tuple[list[float], list[float]]:
    """Build step-profile x/y coordinates without area fills."""

    x_values: list[float] = []
    y_values: list[float] = []
    previous_value: float | None = None

    for row in frame.itertuples(index=False):
        top = float(getattr(row, "top_m"))
        bottom = float(getattr(row, "bottom_m"))
        value = float(getattr(row, value_column))

        if previous_value is not None:
            x_values.extend([previous_value, value])
            y_values.extend([top, top])

        x_values.extend([value, value])
        y_values.extend([top, bottom])
        previous_value = value

    return x_values, y_values
