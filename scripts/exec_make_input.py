from pathlib import Path
import matplotlib.pyplot as plt

from modules.section_proccessing.generate_columns import execute_generate_columns
from scripts.exec_discretized_column import execute_processing
from libs.config.config_variables import OUTPUT_DIR
from libs.config.config_logger import get_logger

from libs.helpers.json_helpers import export_dict_to_json

logger = get_logger()


def generate_exportation(section_path, materials, x_position, f_target, id=0):
    """
    Realiza la reestructuración de data de entrada a un formato de lectura para
    las calibraciones de cada layer / columna.
    """
    logger.info(f"\n[EXPORTACIÓN] Generando columnas para: {section_path}")

    columns, material_labels, section_fig = execute_generate_columns(
        section_path, x_position
    )

    logger.info(f"- Columnas generadas: {len(columns)}")
    logger.info(f"- Labels: {list(columns.keys())}")

    formar_json_export = {}

    if id != 0:
        for label, df in columns.items():
            formar_json_export[label] = {
                "materials": materials,
                "column": df,
                "discretization": {"f_target": f_target},
            }
        # Agregar input un ID, vacio y si tiene valor genera JSON si no nada.
        # Que el codigo reciba un ID no generarlo automaticamente.
        # La web me va a dar el ID.

    return formar_json_export, material_labels, section_fig


# ============================================================
# CALIBRACIÓN
# ============================================================
def generate_calibration(columns, base_output_dir):
    """
    Genera la calibración para toda la data de entrada exportando la información
    de cada layer calibrado (Modelo GQH).
    """
    logger.info(f"\n[CALIBRACIÓN] Base dir: {base_output_dir.resolve()}")

    result_dict = {}

    for label_column, data_column in columns.items():
        safe_label = Path(label_column).name

        directory = base_output_dir / safe_label
        directory.mkdir(parents=True, exist_ok=True)

        filename = f"{safe_label}.csv"

        logger.info(f"\nCreando carpeta: {directory.resolve()}")
        logger.info(f"Archivo: {filename}")

        result_dict[safe_label] = {
            safe_label: execute_processing(data_column, directory, filename)
        }

        logger.info(f"Procesado: {safe_label}")

    return result_dict


def create_session_folder(id, output_root=None):
    """
    Crea una sesión con un código único para el output de información.

    output_root debe venir de la ruta elegida por el usuario. Si no se entrega,
    se usa el valor por defecto configurable: C:\Prismo.
    """

    root = Path(output_root).expanduser() if output_root else OUTPUT_DIR
    base_output_dir = root / "make_calibration" / f"sesion_{id}"
    base_output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Carpeta sesión: {base_output_dir.resolve()}")

    return base_output_dir


def get_input_files(section_folder):
    """ """
    if not section_folder.exists():
        raise FileNotFoundError(f"No existe la carpeta: {section_folder}")

    logger.info(f"Inputs desde: {section_folder.resolve()}")

    files = list(section_folder.glob("*.dxf"))
    logger.info(f"Archivos encontrados: {[f.name for f in files]}\n")

    return files


def _section_keys(file_path):
    path = Path(file_path)
    return [path.name, path.stem, str(path)]


def validate_x_position(file_path, x_position_map):
    """
    Obtiene las coordenadas X para una sección.

    Formato recomendado:
    {
        "section_01": {
            "failure_1": [180, 230],
            "failure_2": [210, 260]
        }
    }

    También acepta claves por nombre de archivo (section_01.dxf) o ruta completa.
    """
    if not isinstance(x_position_map, dict):
        raise TypeError("x_position_map debe ser un diccionario por sección")

    selected_key = None
    for key in _section_keys(file_path):
        if key in x_position_map:
            selected_key = key
            break

    if selected_key is None:
        expected = ", ".join(_section_keys(file_path))
        raise ValueError(
            f"No definiste x_position para la sección. Claves aceptadas: {expected}"
        )

    x_position = x_position_map[selected_key]
    logger.info(f"x_position[{selected_key}]: {x_position}")
    return x_position


def rename_columns(columns):
    """ """
    renamed_columns = {}

    for key, val in columns.items():
        clean_key = key.replace(".dxf", "")

        safe_key = Path(clean_key).name
        renamed_columns[safe_key] = val

    return renamed_columns


def get_data_single_file(
    file_path, materials, x_position_map, f_target, base_output_dir, id=0
):
    """ """
    section_name = file_path.stem  # Obtengo el nombre del file a partir de URL
    section_file = str(file_path)  # Conviertes la URL a string.

    logger.info("\n========================================")
    logger.info(f"Procesando: {file_path.name}")
    logger.info(f"Ruta: {file_path.resolve()}")
    logger.info(f"Section: {section_name}")
    logger.info("\n========================================")

    x_position = validate_x_position(file_path, x_position_map)
    columns, material_labels, section_fig = generate_exportation(
        section_file, materials, x_position, f_target, id
    )

    renamed_columns = rename_columns(columns)
    result = generate_calibration(renamed_columns, base_output_dir)
    logger.info("Tipo de resultado:")
    logger.info(type(result))

    logger.info("\n========================================")
    logger.info(f"Ejecutando calibración para: {section_name}")
    logger.info(f"Sección finalizada: {section_name}")
    logger.info("\n========================================")

    return material_labels, section_fig, section_name, result


def execute_column_process(
    section_folder, materials, x_position_map, f_target, id, output_root=None
):
    """ """
    base_output_dir = create_session_folder(id, output_root=output_root)
    file_paths = get_input_files(Path(section_folder).expanduser())

    sections_plots_dir = base_output_dir / "section_figures"
    sections_plots_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    all_section_names = []
    material_labels_all = set()

    for file_path in file_paths:
        material_labels, section_fig, section_name, result = get_data_single_file(
            file_path, materials, x_position_map, f_target, base_output_dir, id
        )
        material_labels_all.update(material_labels)
        all_section_names.append(section_name)
        results[section_name] = result

        plot_path = sections_plots_dir / f"{section_name}.png"
        section_fig.savefig(plot_path, dpi=300, bbox_inches="tight")
        plt.close(section_fig)

        logger.info(f"Plot guardado en: {plot_path}")

    logger.info("\n==========================================")
    logger.info(f"Resultados generados: {len(results)} secciones")
    logger.info(f"Guardado en: {base_output_dir.resolve()}")
    logger.info("============================================\n")

    # CONSTRUCCIÓN DE EXPORTACIÓN
    # ================================================================
    output_json_path = base_output_dir / "columns_metadata.json"

    all_labels_dict = {
        "materials": sorted(material_labels_all),
        "section_names": all_section_names,
    }

    export_dict_to_json(output_json_path, all_labels_dict)
    logger.info(f"Material labels guardados en: {output_json_path.resolve()}")

    return results


def get_column_config(
    section_file,
    materials,
    x_position_map,
    f_target,
    section_code,
    failure_surface_code,
    column_code,
):
    """
    Devuelve el objeto de entrada compatible con execute_processing para una
    columna específica: materials, column y discretization.
    """
    file_path = Path(section_file).expanduser()
    x_position = validate_x_position(file_path, x_position_map)
    columns, material_labels, _ = generate_exportation(
        str(file_path), materials, x_position, f_target, id=1
    )

    section_code = Path(str(section_code)).stem
    wanted_key = f"{section_code}-{column_code}-{failure_surface_code}"
    if wanted_key not in columns:
        available = sorted(columns.keys())
        raise KeyError(
            f"No existe la columna solicitada: {wanted_key}. Disponibles: {available}"
        )

    return {
        "materials": materials,
        "column": columns[wanted_key],
        "discretization": {"f_target": f_target},
        "metadata": {
            "section": section_code,
            "failure_surface": failure_surface_code,
            "column_code": column_code,
            "column_key": wanted_key,
            "material_labels_in_section": sorted(set(material_labels)),
        },
    }


def get_column_processing_preview(
    section_file,
    materials,
    x_position_map,
    f_target,
    section_code,
    failure_surface_code,
    column_code,
):
    """
    Inspecciona una columna antes de discretizarla.

    Retorna los materiales encontrados en orden de profundidad, sus espesores y
    las propiedades asignadas desde la lista de materiales. El objeto incluye
    column_input, que es compatible con execute_processing.
    """
    from scripts.exec_discretized_column import describe_column_before_discretization

    column_input = get_column_config(
        section_file,
        materials,
        x_position_map,
        f_target,
        section_code,
        failure_surface_code,
        column_code,
    )
    preview = describe_column_before_discretization(column_input)
    preview["column_input"] = column_input
    return preview


# ESCRIBIR EN EL LOOP LOS JSON
# Nombre con materiales -> Todo hecho
# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    section_folder = "pozas_simp"

    materials = [
        {
            "material_name": "Material de poza",
            "unit_weight_kn_m3": 19,
            "shear_velocity": {"depth": [0, 5, 10, 15], "vs": [300, 350, 440, 550]},
            "shear_properties": {"c": 0, "phi": 34},
            "dynamic_model": {
                "model_type": "darendeli_2001",
                "sigma_vertical": 100,
                "soil_parameters": {
                    "IP": 0.0,
                    "OCR": 1.0,
                    "k0": 0.7,
                    "frequency": 1.0,
                    "N": 10,
                },
            },
        },
        {
            "material_name": "Material del dique",
            "unit_weight_kn_m3": 20,
            "shear_velocity": {"depth": [0, 8, 15, 20], "vs": [320, 380, 420, 550]},
            "shear_properties": {"c": 0, "phi": 34},
            "dynamic_model": {
                "model_type": "menq_2003",
                "sigma_vertical": 100,
                "soil_parameters": {"Cu": 18.0, "D50": 8.0, "k0": 0.7, "N": 10},
            },
        },
        {
            "material_name": "Grava arcillosa",
            "unit_weight_kn_m3": 19,
            "shear_velocity": {"depth": [0, 10, 20, 25], "vs": [200, 330, 540, 600]},
            "shear_properties": {"c": 0, "phi": 34},
            "dynamic_model": {
                "model_type": "wang_2021",
                "sigma_vertical": 100,
                "soil_parameters": {
                    "soil_group": "Nonplastic silty sand group",
                    "Cu": 2.0,
                    "CF": 50.0,
                    "e": 0.7,
                    "D50": 1.0,
                    "wc": 1.0,
                    "k0": 0.7,
                },
            },
        },
        {
            "material_name": "Grava arenosa",
            "unit_weight_kn_m3": 19,
            "shear_velocity": {"depth": [0, 24, 30, 40], "vs": [230, 300, 440, 700]},
            "shear_properties": {"c": 0, "phi": 34},
            "dynamic_model": {
                "model_type": "rollins_2020",
                "sigma_vertical": 100,
                "soil_parameters": {"Cu": 1.0, "k0": 1.0},
            },
        },
        {
            "material_name": "Grava pobremente gradada",
            "unit_weight_kn_m3": 19.0,
            "shear_velocity": {"depth": [0, 24, 30, 35], "vs": [230, 300, 440, 500]},
            "shear_properties": {"c": 0, "phi": 34},
            "dynamic_model": {
                "model_type": "ishibashi_1993",
                "sigma_vertical": 100,
                "soil_parameters": {"IP": 50.0, "k0": 0.5},
            },
        },
        {
            "material_name": "Estrato no identificado 1",
            "unit_weight_kn_m3": 19.0,
            "shear_velocity": {"depth": [0, 24, 30, 35], "vs": [230, 300, 440, 550]},
            "shear_properties": {"c": 0, "phi": 34},
            "dynamic_model": {
                "model_type": "rojas_2019",
                "sigma_vertical": 100,
                "soil_parameters": {"k0": 1.0},
            },
        },
    ]

    x_position_map = {
        "section_01.dxf": [250],
        #    "section_02.dxf": [300, 350],
    }

    f_target = 25

    id = "i6e2"

    result = execute_column_process(
        section_folder, materials, x_position_map, f_target, id
    )
