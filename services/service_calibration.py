from pathlib import Path

from modules.section_proccessing.generate_columns import (
    read_dxf_columns,
    generate_clean_polygons,
    generate_polygons,
    assign_polygons,
)
from libs.helpers.json_helpers import export_dict_to_json
from modules.section_proccessing.helper_graphics_section import (
    plot_section_with_columns,
)
from scripts.exec_make_input import (
    create_session_folder,
    execute_column_process,
    get_column_processing_preview,
)
from libs.config.config_logger import get_logger, log_execution_time

logger = get_logger()


@log_execution_time
def exec_column_process(
    section_folder, materials, x_position_map, f_target, id, output_root=None
):
    return execute_column_process(
        section_folder, materials, x_position_map, f_target, id, output_root=output_root
    )


@log_execution_time
def send_metadata_from_sections(id, sections_path):

    base_output_dir = create_session_folder(id)

    sections_path = Path(sections_path)
    section_names_list, section_path_list = get_dxf_names_and_paths(sections_path)

    figure_path = base_output_dir / "section_figures"
    figure_path.mkdir(parents=True, exist_ok=True)

    all_text_data = []
    all_figure_paths = []
    for i, section_path in enumerate(section_path_list, start=1):
        external_pline, freatic_pline, material_pline, failure_pline, text_data = (
            read_dxf_columns(section_path)
        )
        clean_polygons = generate_clean_polygons(
            external_pline, material_pline, text_data
        )

        polygons = generate_polygons(external_pline, material_pline)
        _, empty_polygons = assign_polygons(text_data, polygons)

        warning_polygon_without_id(text_data, clean_polygons, empty_polygons)

        fig = plot_section_with_columns(
            clean_polygons, external_pline, material_pline, failure_pline, freatic_pline
        )

        filepath = figure_path / f"section_{i}.png"
        fig.savefig(filepath)

        all_figure_paths.append(str(filepath))
        all_text_data.extend(text_data)

    materials = get_unique_materials(all_text_data)

    # =================================================
    # EXPORTACIÓN
    # =================================================
    exportation_dict = {
        "section_names": section_names_list,
        "material_names": materials,
        "figure_paths": all_figure_paths,
    }

    output_file = Path(base_output_dir) / "metadata.json"
    export_dict_to_json(output_file, exportation_dict)

    logger.info(section_names_list)


def warning_polygon_without_id(text_data, clean_polygons, empty_polygons):
    # logger.info(len(text_data))
    # logger.info(len(clean_polygons))
    logger.info(len(empty_polygons))

    if len(text_data) == len(clean_polygons):
        logger.info("El número de etiquetas coincide con el número de polígonos")
    else:
        logger.warning("El número de etiquetas NO coincide con el número de polígonos")

    for poly_dict in empty_polygons:
        area_poly = poly_dict["geometry"].area

        if area_poly < 100:
            logger.warning(
                f"Polígono con área muy pequeña detectado | ID: {poly_dict['id']} | Área: {area_poly}"
            )


def get_dxf_names_and_paths(folder_path):
    path = Path(folder_path)
    validate_path(path)

    names_list = []
    paths_list = []

    for file in path.rglob("*.dxf"):
        names_list.append(file.name)
        paths_list.append(str(file))

    return names_list, paths_list


def validate_path(folder_path):
    if not folder_path.exists():
        raise ValueError(f"La ruta no existe: {folder_path}")
    if not folder_path.is_dir():
        raise ValueError(f"No es una carpeta válida: {folder_path}")


def get_unique_materials(text_data):
    seen = set()
    unique_materials = []

    for material_name, _ in text_data:
        if material_name not in seen:
            seen.add(material_name)
            unique_materials.append(material_name)

    return unique_materials


def get_number_of_columns(data_columns: dict):
    result = {}
    total = 0

    for label, data in data_columns.items():
        count = len(data)
        result[label] = count
        total += count

    result["total"] = total

    return result


# ================================================================================
# API DE INSPECCIÓN DE COLUMNA
# ================================================================================


def inspect_column_before_discretization(
    section_file,
    materials,
    x_position_map,
    f_target,
    section_code,
    failure_surface_code,
    column_code,
):
    return get_column_processing_preview(
        section_file,
        materials,
        x_position_map,
        f_target,
        section_code,
        failure_surface_code,
        column_code,
    )
