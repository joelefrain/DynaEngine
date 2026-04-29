import math
import ezdxf
from shapely.geometry import Point, Polygon, LineString, MultiPolygon
from shapely.ops import polygonize, unary_union
from shapely.validation import make_valid
from collections import defaultdict
from pathlib import Path

from modules.section_proccessing.helper_graphics_section import (
    plot_section_with_columns,
)
from libs.config.config_variables import (
    ROUND_DECIMALS,
    MAX_FLOAT,
    MINIMUM_THICKNESS,
)

CLOSED_POLY_TOLERANCE = 0.0001  # Distancia mínima para considerar un polígono cerrado
MINIMUM_AREA_SCALE = 1 / 300  # Escala para no considerar áreas sin etiquetas.
MINIMUM_AREA = 1  # Área mínima de poligonos para considerarlo en la lectura.


def read_dxf_pline(dxf_file, layer_name):
    """
    Lee las polilíneas del archivo dxf.
    """
    mps = dxf_file.modelspace()

    layer_pline = []
    layer_query = 'LWPOLYLINE[layer=="' + layer_name + '"]'

    for pline in mps.query(layer_query):
        points = [(p[0], p[1]) for p in pline.get_points()]
        layer_pline.append(points)

    return layer_pline


def read_dxf_text(dxf_file, layer_name):
    """
    Lee los textos del archivo dxf.
    """
    mps = dxf_file.modelspace()

    text_data = []

    for text in mps.query("TEXT"):
        if text.dxf.layer == layer_name:
            contenido = text.dxf.text
            posicion = text.dxf.insert

            data = (contenido, (float(posicion.x), float(posicion.y)))
            text_data.append(data)

    if not text_data:
        raise ValueError(f"No se encontraron textos en la capa '{layer_name}'")

    return text_data


def generate_polygons(external_pline, material_pline):
    """
    Genera los polígonos en función a las polilíneas external y material.
    """
    all_plines = external_pline + material_pline

    lineas = []
    for pline in all_plines:
        coords = [(float(x), float(y)) for x, y in pline]
        if len(coords) >= 2:
            lineas.append(LineString(coords))

    union = unary_union(lineas)
    union = union.buffer(CLOSED_POLY_TOLERANCE)

    poligonos = list(polygonize(union))

    unique_polygons = []
    for p in poligonos:
        p = make_valid(p)

        if not p.is_valid:
            continue

        if p.area < MINIMUM_AREA:
            continue

        if not any(p.equals(q) for q in unique_polygons):
            unique_polygons.append(p)

    polygons_with_id = [
        {"id": i + 1, "geometry": poly} for i, poly in enumerate(unique_polygons)
    ]

    return polygons_with_id


def assign_polygons(text_data, polygons):
    """
    Asigna etiquetas a los polígonos en función a la geometría de la sección.
    """
    polygons_with_text = []
    poligonos_with_text = set()

    for texto, (x, y) in text_data:
        punto = Point(x, y)

        encontrados = []

        for poly_dict in polygons:
            poly = poly_dict["geometry"]

            if poly.buffer(CLOSED_POLY_TOLERANCE).contains(punto):
                encontrados.append(poly_dict)

        if not encontrados:
            print(f"No se encontró polígono para: {texto}")

        for poly_dict in encontrados:
            polygons_with_text.append((texto, poly_dict))
            poligonos_with_text.add(poly_dict["id"])

    polygons_without_text = [
        poly_dict
        for poly_dict in polygons
        if poly_dict["id"] not in poligonos_with_text
    ]

    return polygons_with_text, polygons_without_text


def intersect_column_with_layers(linea, layer_polygons):
    """
    Calcula la intersección geométrica de una línea vertical con los polígonos de capas.
    """
    capas = []

    for material, poly_dict in layer_polygons:
        poly = poly_dict["geometry"]
        inter = linea.intersection(poly)

        if inter.is_empty:
            continue

        segmentos = []

        if inter.geom_type == "LineString":
            segmentos.append(inter)
        elif inter.geom_type == "MultiLineString":
            segmentos.extend(inter)

        for seg in segmentos:
            y_vals = [pt[1] for pt in seg.coords]

            y_top = max(y_vals)
            y_bot = min(y_vals)
            thickness = y_top - y_bot

            if thickness < MINIMUM_THICKNESS:
                continue

            capas.append(
                {
                    "material": material,
                    "thickness": round(thickness, ROUND_DECIMALS),
                    "top": round(y_top, ROUND_DECIMALS),
                }
            )

    return capas


def clean_and_deduplicate_layers(capas):
    """
    Ordena y elimina capas duplicadas según material, top y thickness.
    """
    capas.sort(key=lambda c: c["top"], reverse=True)

    seen = set()
    clean_layers = []

    for c in capas:
        key = (c["material"], c["top"], c["thickness"])
        if key not in seen:
            clean_layers.append(c)
            seen.add(key)

    return clean_layers


def compute_column_metrics(capas, freatic_depth_i, failure_surface_depth, col_index):
    """
    Calcula el nivel freático y las profundidades de superficie de falla para una columna.
    """
    freatic = (
        round(capas[0]["top"] - freatic_depth_i, ROUND_DECIMALS) if capas else None
    )

    failure_depth_col = {}

    if capas and failure_surface_depth:
        top_surface = capas[0]["top"]

        for key, values in failure_surface_depth.items():
            y_val = values[col_index]

            if y_val is None or math.isnan(y_val):
                depth = None
            else:
                depth = round(top_surface - y_val, ROUND_DECIMALS)

            failure_depth_col[key] = depth

    return freatic, failure_depth_col


def generate_columns(x_positions, layer_polygons, freatic_depth, failure_surface_depth):
    """
    Orquesta la generación de columnas geotécnicas a partir de posiciones y capas.

    Conserva el formato histórico: una lista de coordenadas X y un diccionario
    de superficies de falla evaluadas en esas mismas coordenadas.
    """
    resultado = {}

    min_y = min(poly_dict["geometry"].bounds[1] for _, poly_dict in layer_polygons)
    max_y = max(poly_dict["geometry"].bounds[3] for _, poly_dict in layer_polygons)

    for i, x in enumerate(x_positions):
        name_col = f"column_{i + 1}"

        linea = LineString([(x, min_y), (x, max_y)])

        capas = intersect_column_with_layers(linea, layer_polygons)
        capas = clean_and_deduplicate_layers(capas)
        freatic, failure_depth_col = compute_column_metrics(
            capas, freatic_depth[i], failure_surface_depth, i
        )

        for c in capas:
            del c["top"]

        resultado[name_col] = {
            "layers": capas,
            "freatic": freatic,
            "depth_failure_surface": failure_depth_col,
        }

    return resultado


def generate_columns_for_failure(x_positions, layer_polygons, freatic_depth, failure_depth, failure_name):
    """
    Genera columnas para una única superficie de falla con coordenadas X propias.

    El resultado es compatible con scripts.exec_discretized_column porque cada
    columna contiene layers, freatic y depth_failure_surface escalar.
    """
    resultado = {}

    min_y = min(poly_dict["geometry"].bounds[1] for _, poly_dict in layer_polygons)
    max_y = max(poly_dict["geometry"].bounds[3] for _, poly_dict in layer_polygons)

    for i, x in enumerate(x_positions):
        name_col = f"column_{i + 1}"
        linea = LineString([(x, min_y), (x, max_y)])
        capas = clean_and_deduplicate_layers(intersect_column_with_layers(linea, layer_polygons))

        freatic = round(capas[0]["top"] - freatic_depth[i], ROUND_DECIMALS) if capas else None
        y_failure = failure_depth[i] if i < len(failure_depth) else None
        if capas and y_failure is not None and not (isinstance(y_failure, float) and math.isnan(y_failure)):
            depth_failure = round(capas[0]["top"] - y_failure, ROUND_DECIMALS)
        else:
            depth_failure = None

        layers = []
        for c in capas:
            item = dict(c)
            item.pop("top", None)
            layers.append(item)

        resultado[name_col] = {
            "layers": layers,
            "freatic": freatic,
            "depth_failure_surface": depth_failure,
            "failure_surface": failure_name,
            "x_position": float(x),
        }

    return resultado


def _intersection_pline_to_vline(pline, x_position):
    """
    Obtiene y del freático intersectando líneas verticales con la polilínea.
    """

    pts = pline

    freatic_line = LineString([(float(x), float(y)) for x, y in pts])

    result = []

    for x in x_position:
        vertical_line = LineString([(x, -MAX_FLOAT), (x, MAX_FLOAT)])

        inter = freatic_line.intersection(vertical_line)

        if inter.is_empty:
            result.append(float("nan"))

        elif inter.geom_type == "Point":
            result.append(inter.y)

        elif inter.geom_type == "MultiPoint":
            result.append(max(p.y for p in inter))

        else:
            result.append(float("nan"))

    return result


def intersection_failure_surface(failure_pline, x_position):
    """
    Calcula la intersección entre una polilínea con una línea vertical.
    """
    dict_failure = {}

    for i, pline in enumerate(failure_pline):
        result = _intersection_pline_to_vline(pline, x_position)

        dict_failure[f"failure_{i + 1}"] = result

    return dict_failure


def reasigned_polygon(layer_polygons, empty_polygons, external_pline):
    """
    Reasigna polígonos sin etiqueta, si es grande como polígono sin etiqueta y
    si es pequeño como el polígono más cercano.
    """
    if not external_pline:
        return layer_polygons

    external_polygon = Polygon(external_pline[0])
    external_area = external_polygon.area

    nuevos = []
    i = 1

    for poly_dict in empty_polygons:
        poly = poly_dict["geometry"]

        if poly.area >= MINIMUM_AREA_SCALE * external_area:
            tag_unidentified_layer = "Estrato no identificado " + str(i)
            nuevos.append((tag_unidentified_layer, poly_dict))
            i = +1
            continue

        # Reasignación de etiquetas por cercanía.
        min_dist = float("inf")
        closest_name = None

        for nombre, ref_poly_dict in layer_polygons:
            ref_poly = ref_poly_dict["geometry"]

            dist = poly.distance(ref_poly)

            if dist < min_dist:
                min_dist = dist
                closest_name = nombre

        if closest_name is not None:
            nuevos.append((closest_name, poly_dict))

    layer_polygons.extend(nuevos)

    return layer_polygons


def merge_polygons_by_label(layer_polygons):
    """
    Une polígonos que tienen la misma etiqueta.
    Corrige gaps pequeños usando buffer.
    """

    agrupados = defaultdict(list)

    for nombre, poly_dict in layer_polygons:
        agrupados[nombre].append(poly_dict["geometry"])

    result = []
    new_id = 1

    for nombre, geoms in agrupados.items():
        geoms_buffered = [g.buffer(CLOSED_POLY_TOLERANCE) for g in geoms]

        union = unary_union(geoms_buffered)
        union = union.buffer(-CLOSED_POLY_TOLERANCE)

        if isinstance(union, MultiPolygon):
            for geom in union.geoms:
                result.append((nombre, {"id": new_id, "geometry": geom}))
                new_id += 1
        else:
            result.append((nombre, {"id": new_id, "geometry": union}))
            new_id += 1

    return result


def flatten_columns_by_failure(columns_dict, section, failure_name=None):
    """Convierte columnas a claves section-column-failure para el ARS."""
    result = {}
    section = Path(str(section)).stem

    for col_name, data in columns_dict.items():
        if failure_name is not None:
            depth = data.get("depth_failure_surface")
            if depth is None or (isinstance(depth, float) and math.isnan(depth)):
                continue
            result[f"{section}-{col_name}-{failure_name}"] = data
            continue

        failures = data.get("depth_failure_surface", {})
        for fname, depth in failures.items():
            if depth is None or (isinstance(depth, float) and math.isnan(depth)):
                continue
            result[f"{section}-{col_name}-{fname}"] = {
                "layers": data["layers"],
                "freatic": data["freatic"],
                "depth_failure_surface": depth,
            }

    return result


def normalize_x_position_spec(x_position_spec, failure_count):
    """
    Acepta el formato nuevo {failure_1: [x,...]} y el formato legado [x,...].
    El formato legado se replica para todas las superficies solo por compatibilidad.
    """
    if isinstance(x_position_spec, dict):
        normalized = {}
        for key, values in x_position_spec.items():
            if not isinstance(values, (list, tuple)) or not values:
                raise ValueError(f"La superficie {key} no tiene coordenadas X válidas")
            normalized[str(key)] = [float(v) for v in values]
        return normalized

    if isinstance(x_position_spec, (list, tuple)):
        values = [float(v) for v in x_position_spec]
        if not values:
            raise ValueError("La lista de coordenadas X no puede estar vacía")
        return {f"failure_{i + 1}": list(values) for i in range(failure_count)}

    raise TypeError("x_position debe ser un dict por superficie de falla o una lista legado")


def read_dxf_columns(section):
    """
    Realiza la ejecución del código (Orquestador).
    """

    input_section = Path(section).expanduser()

    if not input_section.exists():
        raise FileNotFoundError(f"No existe el DXF indicado por el usuario: {input_section}")
    if not input_section.is_file():
        raise ValueError(f"La ruta indicada no es un archivo DXF: {input_section}")

    # LECTURA DE ARCHIVOS
    # ================================================================

    dxf_file = ezdxf.readfile(input_section)

    # PROCESAMIENTO
    # ================================================================

    external_pline = read_dxf_pline(dxf_file, "EXTERNAL")
    freatic_pline = read_dxf_pline(dxf_file, "FREATIC")
    material_pline = read_dxf_pline(dxf_file, "MATERIAL")
    failure_pline = read_dxf_pline(dxf_file, "SUP_FALLA")
    text_data = read_dxf_text(dxf_file, "TEXTO")

    return external_pline, freatic_pline, material_pline, failure_pline, text_data


def generate_clean_polygons(external_pline, material_pline, text_data):
    polygons = generate_polygons(external_pline, material_pline)
    layer_polygons, empty_polygons = assign_polygons(text_data, polygons)
    reasigned_polygons = reasigned_polygon(
        layer_polygons, empty_polygons, external_pline
    )
    clean_polygons = merge_polygons_by_label(reasigned_polygons)

    return clean_polygons


def construct_columns(
    external_pline, freatic_pline, material_pline, failure_pline, text_data, x_position
):
    clean_polygons = generate_clean_polygons(external_pline, material_pline, text_data)

    if not freatic_pline:
        raise ValueError("La sección no contiene polilínea FREATIC")
    if not failure_pline:
        raise ValueError("La sección no contiene superficies SUP_FALLA")

    x_by_failure = normalize_x_position_spec(x_position, len(failure_pline))
    columns_by_failure = {}

    for failure_name, x_positions in x_by_failure.items():
        failure_idx = int(str(failure_name).split("_")[-1]) - 1 if str(failure_name).startswith("failure_") else None
        if failure_idx is None or failure_idx < 0 or failure_idx >= len(failure_pline):
            raise ValueError(f"Superficie de falla no válida para esta sección: {failure_name}")

        freatic_depth = _intersection_pline_to_vline(freatic_pline[0], x_positions)
        failure_depth = _intersection_pline_to_vline(failure_pline[failure_idx], x_positions)
        columns_by_failure[failure_name] = generate_columns_for_failure(
            x_positions, clean_polygons, freatic_depth, failure_depth, failure_name
        )

    return columns_by_failure, clean_polygons


def execute_generate_columns(section, x_position):
    external_pline, freatic_pline, material_pline, failure_pline, text_data = (
        read_dxf_columns(section)
    )

    columns_by_failure, clean_polygons = construct_columns(
        external_pline,
        freatic_pline,
        material_pline,
        failure_pline,
        text_data,
        x_position,
    )

    columns_export = {}
    for failure_name, columns in columns_by_failure.items():
        columns_export.update(flatten_columns_by_failure(columns, section, failure_name))

    material_labels = list(material for material, _ in text_data)

    #  TESTEO
    # ================================================================
    # print("Tipo: ", type(freatic_pline[0]), "\n", freatic_pline[0])
    # print("Tipo: ", type(failure_pline[0]), "\n", failure_pline[0])
    # print (failure_surface_depth)
    # print("Tipo: ", type(text_data), "\n", text_data)
    # print("Cantidad de etiquetas:", len(text_data))
    # print("Tipo: ", type(polygons), "\n", polygons[0]['geometry'])
    # print("Cantidad de polígonos leídos:", len(polygons))
    # print(layer_polygons)
    # print("Cantidad de poligonos con etiqueta en preprocesamiento:", len(layer_polygons))
    # print(empty_polygons)
    # print("Cantidad de poligonos sin etiqueta:", len(empty_polygons))
    # print(columns)
    # print("Cantidad de poligonos finales:", len(reasigned_polygons))
    # print(columns)
    # print("Cantidad de columnas gráficas:", len(columns))
    # print(freatic_depth)
    # print("Cantidad de secciones de falla:", len(failure_pline))
    # print(columns_export)
    # print("Cantidad de columnas para el ARS:", len(columns_export))
    # print(material_labels)

    section_fig = plot_section_with_columns(
        clean_polygons,
        external_pline,
        material_pline,
        failure_pline,
        freatic_pline,
        columns_by_failure,
        x_position,
    )  # Muestra temporal de las zonas generadas.

    #  EXPORTACIÓN
    # ================================================================
    # with open(output_file, "w", encoding="utf-8") as f:
    #    json.dump(columns_export, f, indent=4, ensure_ascii=False)

    return columns_export, material_labels, section_fig


if __name__ == "__main__":
    section_filename = "section_01.dxf"
    # output_directory = "output_sections"
    # output_filename = "columns.json"

    x_position = [180, 230, 290, 310, 370, 430, 450]

    columns = execute_generate_columns(section_filename, x_position)
    # print(columns)


# ===========================================
# FALTA AÑADIR
# ===========================================

# 1. Revisar y documentar código.
# 4. Documentar funciones utilizadas.
# 5. Revisar posible código duplicado.
# 6. Colocar logs pertinentes.


# ===========================================
# POSIBLES PROBLEMAS
# ===========================================

# 1. Cuando una linea inicia en el punto medio de otra podria no considerarla como poligono cerrado. (Problemas del Shapely)
# 2. Revisar que se generen el número correcto de superficies de falla.
