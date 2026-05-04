"""DXF section parsing for stratigraphic columns."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import ezdxf
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
)
from shapely.ops import polygonize, unary_union
from shapely.validation import make_valid

from dynaengine.constants import MAX_FLOAT, MINIMUM_THICKNESS_M, ROUND_DECIMALS

CLOSED_POLY_TOLERANCE = 0.0001
MINIMUM_AREA_SCALE = 0.01
MINIMUM_AREA = 1.0
UNIDENTIFIED_PREFIX = "Estrato no identificado"
FailureTypeInput = dict[str | int, str] | list[str] | tuple[str, ...] | str


@dataclass(frozen=True)
class DxfColumnExtraction:
    columns: dict[str, dict[str, Any]]
    material_names: list[str]
    unidentified_materials: list[str]
    failure_surfaces: dict[str, dict[str, Any]] = field(default_factory=dict)


def extract_columns_from_dxf(
    section_path: str | Path,
    x_positions: list[float],
    material_aliases: dict[str, str] | None = None,
    failure_types: FailureTypeInput | None = None,
) -> DxfColumnExtraction:
    """Extract non-discretized columns from a DXF section.

    The function never reads from a global input folder. The caller must pass an
    explicit DXF path.
    """

    path = Path(section_path)
    if not path.exists():
        raise FileNotFoundError(f"No existe el DXF: {path}")
    if not x_positions:
        raise ValueError("x_positions no puede estar vacio")

    external, freatic, material, failure, text = _read_dxf_layers(path)
    failure_type_map = _normalize_failure_types(failure_types, len(failure))
    columns, _clean_polygons, failure_surfaces = _construct_columns(
        external,
        freatic,
        material,
        failure,
        text,
        x_positions,
        failure_type_map,
    )
    flat_columns = _flatten_columns_by_failure(columns, path.stem, failure_surfaces)

    aliases = material_aliases or {}
    if aliases:
        flat_columns = _apply_material_aliases(flat_columns, aliases)

    material_names = sorted(
        {
            layer["material"]
            for column in flat_columns.values()
            for layer in column["layers"]
        }
    )
    unidentified = [
        name for name in material_names if name.startswith(UNIDENTIFIED_PREFIX)
    ]
    return DxfColumnExtraction(
        columns=flat_columns,
        material_names=material_names,
        unidentified_materials=unidentified,
        failure_surfaces=failure_surfaces,
    )


def _read_dxf_layers(path: Path) -> tuple[list, list, list, list, list]:
    dxf_file = ezdxf.readfile(path)
    return (
        _read_dxf_pline(dxf_file, "EXTERNAL"),
        _read_dxf_pline(dxf_file, "FREATIC"),
        _read_dxf_pline(dxf_file, "MATERIAL"),
        _read_dxf_pline(dxf_file, "SUP_FALLA"),
        _read_dxf_text(dxf_file, "TEXTO"),
    )


def _read_dxf_pline(dxf_file, layer_name: str) -> list[list[tuple[float, float]]]:
    modelspace = dxf_file.modelspace()
    polylines = []
    for pline in modelspace.query(f'LWPOLYLINE[layer=="{layer_name}"]'):
        polylines.append(
            [(float(point[0]), float(point[1])) for point in pline.get_points()]
        )
    if not polylines and layer_name in {"EXTERNAL", "FREATIC", "SUP_FALLA"}:
        raise ValueError(f"No se encontraron polilineas en la capa '{layer_name}'")
    return polylines


def _read_dxf_text(dxf_file, layer_name: str) -> list[tuple[str, tuple[float, float]]]:
    modelspace = dxf_file.modelspace()
    text_data = []
    for text in modelspace.query("TEXT"):
        if text.dxf.layer == layer_name:
            insert = text.dxf.insert
            text_data.append((str(text.dxf.text), (float(insert.x), float(insert.y))))
    if not text_data:
        raise ValueError(f"No se encontraron textos en la capa '{layer_name}'")
    return text_data


def _generate_polygons(
    external_pline: list, material_pline: list
) -> list[dict[str, Any]]:
    lines = []
    for polyline in external_pline + material_pline:
        coords = [(float(x), float(y)) for x, y in polyline]
        if len(coords) >= 2:
            lines.append(LineString(coords))

    union = unary_union(lines).buffer(CLOSED_POLY_TOLERANCE)
    polygons = []
    for polygon in polygonize(union):
        polygon = make_valid(polygon)
        if (
            polygon.is_valid
            and polygon.area >= MINIMUM_AREA
            and not any(polygon.equals(item) for item in polygons)
        ):
            polygons.append(polygon)

    return [
        {"id": index + 1, "geometry": polygon} for index, polygon in enumerate(polygons)
    ]


def _assign_polygons(
    text_data: list[tuple[str, tuple[float, float]]],
    polygons: list[dict[str, Any]],
) -> tuple[list[tuple[str, dict[str, Any]]], list[dict[str, Any]]]:
    polygons_with_text = []
    polygon_ids_with_text = set()

    for text, (x, y) in text_data:
        point = Point(x, y)
        found = [
            polygon
            for polygon in polygons
            if polygon["geometry"].buffer(CLOSED_POLY_TOLERANCE).contains(point)
        ]
        for polygon in found:
            polygons_with_text.append((text, polygon))
            polygon_ids_with_text.add(polygon["id"])

    polygons_without_text = [
        polygon for polygon in polygons if polygon["id"] not in polygon_ids_with_text
    ]
    return polygons_with_text, polygons_without_text


def _reassign_unlabeled_polygons(
    layer_polygons: list[tuple[str, dict[str, Any]]],
    empty_polygons: list[dict[str, Any]],
    external_pline: list,
) -> list[tuple[str, dict[str, Any]]]:
    if not external_pline:
        return layer_polygons

    reference_area = _largest_polygon_area(
        [polygon for _, polygon in layer_polygons] + empty_polygons
    )
    new_polygons = []
    unidentified_index = 1

    for polygon in empty_polygons:
        geometry = polygon["geometry"]
        if reference_area > 0 and geometry.area >= MINIMUM_AREA_SCALE * reference_area:
            new_polygons.append(
                (f"{UNIDENTIFIED_PREFIX} {unidentified_index}", polygon)
            )
            unidentified_index += 1
            continue

        closest_name = None
        closest_distance = float("inf")
        for name, reference in layer_polygons:
            distance = geometry.distance(reference["geometry"])
            if distance < closest_distance:
                closest_distance = distance
                closest_name = name
        if closest_name is not None:
            new_polygons.append((closest_name, polygon))

    return [*layer_polygons, *new_polygons]


def _merge_polygons_by_label(
    layer_polygons: list[tuple[str, dict[str, Any]]],
) -> list[tuple[str, dict[str, Any]]]:
    grouped = defaultdict(list)
    for name, polygon in layer_polygons:
        grouped[name].append(polygon["geometry"])

    result = []
    new_id = 1
    for name, geometries in grouped.items():
        union = unary_union(
            [geometry.buffer(CLOSED_POLY_TOLERANCE) for geometry in geometries]
        )
        union = union.buffer(-CLOSED_POLY_TOLERANCE)
        if isinstance(union, MultiPolygon):
            for geometry in union.geoms:
                result.append((name, {"id": new_id, "geometry": geometry}))
                new_id += 1
        else:
            result.append((name, {"id": new_id, "geometry": union}))
            new_id += 1
    return result


def _generate_clean_polygons(
    external_pline: list, material_pline: list, text_data: list
) -> list:
    polygons = _generate_polygons(external_pline, material_pline)
    layer_polygons, empty_polygons = _assign_polygons(text_data, polygons)
    layer_polygons = _reassign_unlabeled_polygons(
        layer_polygons, empty_polygons, external_pline
    )
    return _merge_polygons_by_label(layer_polygons)


def summarize_polygon_areas(
    layer_polygons: list[tuple[str, dict[str, Any]]],
    small_area_scale: float = MINIMUM_AREA_SCALE,
) -> list[dict[str, Any]]:
    """Summarize polygon areas and flag areas small relative to the largest area.

    ``area_ratio_to_largest`` is computed as polygon area divided by the largest
    polygon area in the supplied collection. A polygon is flagged as small when
    that ratio is lower than ``small_area_scale``.
    """

    if small_area_scale < 0:
        raise ValueError("small_area_scale debe ser mayor o igual a 0")

    largest_area = _largest_polygon_area([polygon for _, polygon in layer_polygons])
    if largest_area <= 0:
        return []

    summary = []
    for material_name, polygon in layer_polygons:
        geometry = polygon["geometry"]
        area = float(geometry.area)
        ratio = area / largest_area
        summary.append(
            {
                "material_name": material_name,
                "polygon_id": polygon.get("id"),
                "area_m2": round(area, ROUND_DECIMALS),
                "largest_area_m2": round(largest_area, ROUND_DECIMALS),
                "area_ratio_to_largest": round(ratio, ROUND_DECIMALS),
                "small_area_scale": small_area_scale,
                "is_small_area": bool(ratio < small_area_scale),
            }
        )
    return sorted(summary, key=lambda item: item["area_m2"], reverse=True)


def _largest_polygon_area(polygons: list[dict[str, Any]]) -> float:
    areas = [float(polygon["geometry"].area) for polygon in polygons]
    return max(areas) if areas else 0.0


def _construct_columns(
    external_pline: list,
    freatic_pline: list,
    material_pline: list,
    failure_pline: list,
    text_data: list,
    x_positions: list[float],
    failure_types: dict[str, str],
) -> tuple[dict[str, Any], list, dict[str, dict[str, Any]]]:
    clean_polygons = _generate_clean_polygons(external_pline, material_pline, text_data)
    external_elevation = _external_elevation_at_positions(external_pline, x_positions)
    freatic_elevation = _intersection_pline_to_vline(freatic_pline[0], x_positions)
    failure_surface_elevation = _intersection_failure_surface(
        failure_pline, x_positions
    )
    failure_surfaces = _describe_failure_surfaces(
        external_pline, failure_pline, failure_types
    )
    columns = _generate_columns(
        x_positions,
        clean_polygons,
        external_elevation,
        freatic_elevation,
        failure_surface_elevation,
    )
    return columns, clean_polygons, failure_surfaces


def _intersection_pline_to_vline(pline: list, x_positions: list[float]) -> list[float]:
    result = []
    for x in x_positions:
        y_values = _y_values_at_x([pline], x)
        result.append(float(max(y_values)) if y_values else float("nan"))
    return result


def _external_elevation_at_positions(
    external_pline: list, x_positions: list[float]
) -> list[float]:
    result = []
    for x in x_positions:
        external_y = _top_y_at_x(external_pline, x)
        result.append(float(external_y) if external_y is not None else float("nan"))
    return result


def _intersection_failure_surface(
    failure_pline: list, x_positions: list[float]
) -> dict[str, list[float]]:
    return {
        f"failure_{index + 1}": _intersection_pline_to_vline(polyline, x_positions)
        for index, polyline in enumerate(failure_pline)
    }


def _describe_failure_surfaces(
    external_pline: list,
    failure_pline: list,
    failure_types: dict[str, str],
) -> dict[str, dict[str, Any]]:
    result = {}
    for index, polyline in enumerate(failure_pline):
        name = f"failure_{index + 1}"
        result[name] = {
            "failure_surface": name,
            "failure_type": failure_types.get(name),
            "failure_height": _compute_failure_height(external_pline, polyline),
        }
    return result


def _normalize_failure_types(
    failure_types: FailureTypeInput | None,
    failure_count: int,
) -> dict[str, str]:
    names = [f"failure_{index + 1}" for index in range(failure_count)]
    if failure_types is None:
        return {}
    if isinstance(failure_types, str):
        return {name: failure_types for name in names}
    if isinstance(failure_types, (list, tuple)):
        return {
            names[index]: str(value)
            for index, value in enumerate(failure_types[:failure_count])
            if value is not None
        }

    normalized = {}
    for key, value in failure_types.items():
        if value is None:
            continue
        key_text = str(key)
        if key_text in names:
            normalized[key_text] = str(value)
            continue
        if key_text.isdigit():
            index = int(key_text) - 1
            if 0 <= index < failure_count:
                normalized[names[index]] = str(value)
    return normalized


def _compute_failure_height(
    external_pline: list, failure_polyline: list
) -> float | None:
    if not external_pline or not failure_polyline:
        return None

    external_bounds = _x_bounds(external_pline)
    failure_bounds = _x_bounds([failure_polyline])
    if external_bounds is None or failure_bounds is None:
        return None

    min_x = max(external_bounds[0], failure_bounds[0])
    max_x = min(external_bounds[1], failure_bounds[1])
    if min_x > max_x:
        return None

    candidate_x = {min_x, max_x}
    candidate_x.update(_x_vertices_within(external_pline, min_x, max_x))
    candidate_x.update(_x_vertices_within([failure_polyline], min_x, max_x))

    heights = []
    for x in sorted(candidate_x):
        external_y = _top_y_at_x(external_pline, x)
        failure_y = _bottom_y_at_x([failure_polyline], x)
        if external_y is None or failure_y is None:
            continue
        heights.append(external_y - failure_y)

    if not heights:
        return None
    return round(max(heights), ROUND_DECIMALS)


def _x_bounds(polylines: list) -> tuple[float, float] | None:
    x_values = [float(x) for polyline in polylines for x, _ in polyline]
    if not x_values:
        return None
    return min(x_values), max(x_values)


def _x_vertices_within(polylines: list, min_x: float, max_x: float) -> list[float]:
    return [
        float(x)
        for polyline in polylines
        for x, _ in polyline
        if min_x <= float(x) <= max_x
    ]


def _top_y_at_x(polylines: list, x: float) -> float | None:
    y_values = _y_values_at_x(polylines, x)
    return None if not y_values else max(y_values)


def _bottom_y_at_x(polylines: list, x: float) -> float | None:
    y_values = _y_values_at_x(polylines, x)
    return None if not y_values else min(y_values)


def _y_values_at_x(polylines: list, x: float) -> list[float]:
    vertical = LineString([(x, -MAX_FLOAT), (x, MAX_FLOAT)])
    values = []
    for polyline in polylines:
        if len(polyline) < 2:
            continue
        line = LineString([(float(px), float(py)) for px, py in polyline])
        values.extend(_extract_y_values(line.intersection(vertical)))
    return values


def _extract_y_values(geometry) -> list[float]:
    if geometry.is_empty:
        return []
    if isinstance(geometry, Point):
        return [float(geometry.y)]
    if isinstance(geometry, MultiPoint):
        return [float(point.y) for point in geometry.geoms]
    if isinstance(geometry, LineString):
        return [float(point[1]) for point in geometry.coords]
    if isinstance(geometry, MultiLineString):
        return [float(point[1]) for line in geometry.geoms for point in line.coords]
    if isinstance(geometry, GeometryCollection):
        return [value for item in geometry.geoms for value in _extract_y_values(item)]
    return []


def _generate_columns(
    x_positions: list[float],
    layer_polygons: list[tuple[str, dict[str, Any]]],
    external_elevation: list[float],
    freatic_elevation: list[float],
    failure_surface_elevation: dict[str, list[float]],
) -> dict[str, Any]:
    result = {}
    min_y = min(polygon["geometry"].bounds[1] for _, polygon in layer_polygons)
    max_y = max(polygon["geometry"].bounds[3] for _, polygon in layer_polygons)

    for index, x in enumerate(x_positions):
        line = LineString([(x, min_y), (x, max_y)])
        layers = _intersect_column_with_layers(line, layer_polygons)
        layers = _clean_and_deduplicate_layers(layers)
        freatic, failure_depth = _compute_column_metrics(
            layers,
            external_elevation[index],
            freatic_elevation[index],
            failure_surface_elevation,
            index,
        )
        for layer in layers:
            del layer["top"]
        result[f"column_{index + 1}"] = {
            "layers": layers,
            "external_elevation": _round_optional_elevation(external_elevation[index]),
            "freatic": freatic,
            "depth_failure_surface": failure_depth,
        }
    return result


def _intersect_column_with_layers(
    line: LineString,
    layer_polygons: list[tuple[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    layers = []
    for material, polygon in layer_polygons:
        intersection = line.intersection(polygon["geometry"])
        if intersection.is_empty:
            continue
        segments = []
        if intersection.geom_type == "LineString":
            segments.append(intersection)
        elif intersection.geom_type == "MultiLineString":
            segments.extend(intersection.geoms)
        for segment in segments:
            y_values = [point[1] for point in segment.coords]
            y_top = max(y_values)
            y_bottom = min(y_values)
            thickness = y_top - y_bottom
            if thickness >= MINIMUM_THICKNESS_M:
                layers.append(
                    {
                        "material": material,
                        "thickness": round(thickness, ROUND_DECIMALS),
                        "top": round(y_top, ROUND_DECIMALS),
                    }
                )
    return layers


def _clean_and_deduplicate_layers(layers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    layers.sort(key=lambda layer: layer["top"], reverse=True)
    seen = set()
    clean_layers = []
    for layer in layers:
        key = (layer["material"], layer["top"], layer["thickness"])
        if key not in seen:
            clean_layers.append(layer)
            seen.add(key)
    return clean_layers


def _compute_column_metrics(
    layers: list[dict[str, Any]],
    external_elevation_at_x: float,
    freatic_elevation_at_x: float,
    failure_surface_elevation: dict[str, list[float]],
    column_index: int,
) -> tuple[float | None, dict[str, float | None]]:
    if not layers or _is_missing_elevation(external_elevation_at_x):
        return None, {name: None for name in failure_surface_elevation}

    freatic = _depth_from_external_elevation(
        external_elevation_at_x, freatic_elevation_at_x
    )
    failure_depth = {}
    for name, values in failure_surface_elevation.items():
        y_value = values[column_index]
        failure_depth[name] = _depth_from_external_elevation(
            external_elevation_at_x, y_value
        )
    return freatic, failure_depth


def _depth_from_external_elevation(
    external_elevation_at_x: float, target_elevation_at_x: float | None
) -> float | None:
    if _is_missing_elevation(target_elevation_at_x):
        return None
    return round(
        float(external_elevation_at_x) - float(target_elevation_at_x),
        ROUND_DECIMALS,
    )


def _round_optional_elevation(value: float | None) -> float | None:
    if _is_missing_elevation(value):
        return None
    return round(float(value), ROUND_DECIMALS)


def _is_missing_elevation(value: float | None) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def _flatten_columns_by_failure(
    columns: dict[str, Any],
    section_name: str,
    failure_surfaces: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    result = {}
    for column_name, data in columns.items():
        for failure_name, depth in data.get("depth_failure_surface", {}).items():
            if depth is None or (isinstance(depth, float) and math.isnan(depth)):
                continue
            failure_data = failure_surfaces.get(failure_name, {})
            result[f"{section_name}-{column_name}-{failure_name}"] = {
                "layers": data["layers"],
                "external_elevation": data.get("external_elevation"),
                "freatic": data["freatic"],
                "failure_surface": failure_name,
                "failure_type": failure_data.get("failure_type"),
                "failure_height": failure_data.get("failure_height"),
                "depth_failure_surface": depth,
            }
    return result


def _apply_material_aliases(
    columns: dict[str, dict[str, Any]],
    aliases: dict[str, str],
) -> dict[str, dict[str, Any]]:
    aliased = {}
    for column_name, column in columns.items():
        layers = []
        for layer in column["layers"]:
            layers.append(
                {**layer, "material": aliases.get(layer["material"], layer["material"])}
            )
        aliased[column_name] = {**column, "layers": layers}
    return aliased
