"""DXF section parsing for stratigraphic columns."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import ezdxf
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.ops import polygonize, unary_union
from shapely.validation import make_valid

from dynaengine.constants import MAX_FLOAT, MINIMUM_THICKNESS_M, ROUND_DECIMALS

CLOSED_POLY_TOLERANCE = 0.0001
MINIMUM_AREA_SCALE = 0.01
MINIMUM_AREA = 1.0
UNIDENTIFIED_PREFIX = "Estrato no identificado"


@dataclass(frozen=True)
class DxfColumnExtraction:
    columns: dict[str, dict[str, Any]]
    material_names: list[str]
    unidentified_materials: list[str]


def extract_columns_from_dxf(
    section_path: str | Path,
    x_positions: list[float],
    material_aliases: dict[str, str] | None = None,
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
    columns, clean_polygons = _construct_columns(external, freatic, material, failure, text, x_positions)
    flat_columns = _flatten_columns_by_failure(columns, path.stem)

    aliases = material_aliases or {}
    if aliases:
        flat_columns = _apply_material_aliases(flat_columns, aliases)

    material_names = sorted({layer["material"] for column in flat_columns.values() for layer in column["layers"]})
    unidentified = [name for name in material_names if name.startswith(UNIDENTIFIED_PREFIX)]
    return DxfColumnExtraction(
        columns=flat_columns,
        material_names=material_names,
        unidentified_materials=unidentified,
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
        polylines.append([(float(point[0]), float(point[1])) for point in pline.get_points()])
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


def _generate_polygons(external_pline: list, material_pline: list) -> list[dict[str, Any]]:
    lines = []
    for polyline in external_pline + material_pline:
        coords = [(float(x), float(y)) for x, y in polyline]
        if len(coords) >= 2:
            lines.append(LineString(coords))

    union = unary_union(lines).buffer(CLOSED_POLY_TOLERANCE)
    polygons = []
    for polygon in polygonize(union):
        polygon = make_valid(polygon)
        if polygon.is_valid and polygon.area >= MINIMUM_AREA and not any(polygon.equals(item) for item in polygons):
            polygons.append(polygon)

    return [{"id": index + 1, "geometry": polygon} for index, polygon in enumerate(polygons)]


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

    polygons_without_text = [polygon for polygon in polygons if polygon["id"] not in polygon_ids_with_text]
    return polygons_with_text, polygons_without_text


def _reassign_unlabeled_polygons(
    layer_polygons: list[tuple[str, dict[str, Any]]],
    empty_polygons: list[dict[str, Any]],
    external_pline: list,
) -> list[tuple[str, dict[str, Any]]]:
    if not external_pline:
        return layer_polygons

    external_area = Polygon(external_pline[0]).area
    new_polygons = []
    unidentified_index = 1

    for polygon in empty_polygons:
        geometry = polygon["geometry"]
        if geometry.area >= MINIMUM_AREA_SCALE * external_area:
            new_polygons.append((f"{UNIDENTIFIED_PREFIX} {unidentified_index}", polygon))
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


def _merge_polygons_by_label(layer_polygons: list[tuple[str, dict[str, Any]]]) -> list[tuple[str, dict[str, Any]]]:
    grouped = defaultdict(list)
    for name, polygon in layer_polygons:
        grouped[name].append(polygon["geometry"])

    result = []
    new_id = 1
    for name, geometries in grouped.items():
        union = unary_union([geometry.buffer(CLOSED_POLY_TOLERANCE) for geometry in geometries])
        union = union.buffer(-CLOSED_POLY_TOLERANCE)
        if isinstance(union, MultiPolygon):
            for geometry in union.geoms:
                result.append((name, {"id": new_id, "geometry": geometry}))
                new_id += 1
        else:
            result.append((name, {"id": new_id, "geometry": union}))
            new_id += 1
    return result


def _generate_clean_polygons(external_pline: list, material_pline: list, text_data: list) -> list:
    polygons = _generate_polygons(external_pline, material_pline)
    layer_polygons, empty_polygons = _assign_polygons(text_data, polygons)
    layer_polygons = _reassign_unlabeled_polygons(layer_polygons, empty_polygons, external_pline)
    return _merge_polygons_by_label(layer_polygons)


def _construct_columns(
    external_pline: list,
    freatic_pline: list,
    material_pline: list,
    failure_pline: list,
    text_data: list,
    x_positions: list[float],
) -> tuple[dict[str, Any], list]:
    clean_polygons = _generate_clean_polygons(external_pline, material_pline, text_data)
    freatic_depth = _intersection_pline_to_vline(freatic_pline[0], x_positions)
    failure_surface_depth = _intersection_failure_surface(failure_pline, x_positions)
    columns = _generate_columns(x_positions, clean_polygons, freatic_depth, failure_surface_depth)
    return columns, clean_polygons


def _intersection_pline_to_vline(pline: list, x_positions: list[float]) -> list[float]:
    line = LineString([(float(x), float(y)) for x, y in pline])
    result = []
    for x in x_positions:
        vertical = LineString([(x, -MAX_FLOAT), (x, MAX_FLOAT)])
        intersection = line.intersection(vertical)
        if intersection.is_empty:
            result.append(float("nan"))
        elif intersection.geom_type == "Point":
            result.append(float(intersection.y))
        elif intersection.geom_type == "MultiPoint":
            result.append(float(max(point.y for point in intersection.geoms)))
        else:
            result.append(float("nan"))
    return result


def _intersection_failure_surface(failure_pline: list, x_positions: list[float]) -> dict[str, list[float]]:
    return {
        f"failure_{index + 1}": _intersection_pline_to_vline(polyline, x_positions)
        for index, polyline in enumerate(failure_pline)
    }


def _generate_columns(
    x_positions: list[float],
    layer_polygons: list[tuple[str, dict[str, Any]]],
    freatic_depth: list[float],
    failure_surface_depth: dict[str, list[float]],
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
            freatic_depth[index],
            failure_surface_depth,
            index,
        )
        for layer in layers:
            del layer["top"]
        result[f"column_{index + 1}"] = {
            "layers": layers,
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
    freatic_depth_at_x: float,
    failure_surface_depth: dict[str, list[float]],
    column_index: int,
) -> tuple[float | None, dict[str, float | None]]:
    freatic = round(layers[0]["top"] - freatic_depth_at_x, ROUND_DECIMALS) if layers else None
    failure_depth = {}
    if layers and failure_surface_depth:
        top_surface = layers[0]["top"]
        for name, values in failure_surface_depth.items():
            y_value = values[column_index]
            if y_value is None or math.isnan(y_value):
                failure_depth[name] = None
            else:
                failure_depth[name] = round(top_surface - y_value, ROUND_DECIMALS)
    return freatic, failure_depth


def _flatten_columns_by_failure(columns: dict[str, Any], section_name: str) -> dict[str, dict[str, Any]]:
    result = {}
    for column_name, data in columns.items():
        for failure_name, depth in data.get("depth_failure_surface", {}).items():
            if depth is None or (isinstance(depth, float) and math.isnan(depth)):
                continue
            result[f"{section_name}-{column_name}-{failure_name}"] = {
                "layers": data["layers"],
                "freatic": data["freatic"],
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
            layers.append({**layer, "material": aliases.get(layer["material"], layer["material"])})
        aliased[column_name] = {**column, "layers": layers}
    return aliased
