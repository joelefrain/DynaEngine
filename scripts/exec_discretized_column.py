import json

from pathlib import Path

from modules.make_columns.class_columns import Columns
from modules.make_columns.class_layers import Layers
from modules.make_columns.class_shear_velocity import ShearVelocity
from libs.config.config_logger import get_logger, log_execution_time

from modules.dynamic_curves.class_theoretical_curves import (
    DarendeliModel_2001,
    MenqModel_2003,
    RollinsModel_2020,
    WangStokoeModel_2021,
    IshibashiModel_1993,
    SeedIdrissModel_1970,
    RojasModel_2019,
    UserDefined,
)
from modules.dynamic_curves.class_soil_parameters import (
    DarendeliParameters_2001,
    MenqParameters_2003,
    RollinsParameters_2020,
    WangStokoeParameters_2021,
    IshibashiParameters_1993,
    SeedIdrissParameters_1970,
    RojasParameters_2019,
    UserDefinedParameters,
)

logger = get_logger()

MODEL_REGISTRY = {
    "darendeli_2001": (DarendeliModel_2001, DarendeliParameters_2001),
    "menq_2003": (MenqModel_2003, MenqParameters_2003),
    "rollins_2020": (RollinsModel_2020, RollinsParameters_2020),
    "ishibashi_1993": (IshibashiModel_1993, IshibashiParameters_1993),
    "wang_2021": (WangStokoeModel_2021, WangStokoeParameters_2021),
    "rojas_2019": (RojasModel_2019, RojasParameters_2019),
    "seed_1970": (SeedIdrissModel_1970, SeedIdrissParameters_1970),
    "user_defined": (UserDefined, UserDefinedParameters),
}


def create_shear_velocity(mat: dict) -> ShearVelocity:
    return ShearVelocity(
        depth=mat["shear_velocity"]["depth"],
        shear_velocity=mat["shear_velocity"]["vs"],
    )


def create_dynamic_model(model_data):
    model_type = model_data["model_type"]

    if model_type not in MODEL_REGISTRY:
        raise ValueError(f"Modelo no soportado: {model_type}")

    ModelClass, ParamsClass = MODEL_REGISTRY[model_type]
    params = ParamsClass(**model_data["soil_parameters"])

    if model_type == "user_defined":
        return ModelClass(
            params,
            model_data["data"],
            model_data[
                "sigma_vertical"
            ],  # Revisar porque calibración en definido por el usuario no va bien.
        )

    return ModelClass(params, model_data["sigma_vertical"])




def _dynamic_model_summary(model_data):
    summary = {
        "model_type": model_data.get("model_type"),
        "sigma_vertical": model_data.get("sigma_vertical"),
        "soil_parameters": model_data.get("soil_parameters", {}),
    }
    if model_data.get("model_type") == "user_defined":
        summary["data"] = model_data.get("data")
    return summary


def describe_column_before_discretization(config: dict) -> dict:
    """
    Describe una columna en el mismo orden en que será procesada por la
    discretización, sin calibrarla ni subdividirla.

    Entrada compatible con execute_processing:
    {"materials": [...], "column": {"layers": [...]}, "discretization": {...}}
    """
    materials_by_name = {m["material_name"]: m for m in config["materials"]}
    layers = config["column"].get("layers", [])

    ordered_layers = []
    z_top = 0.0
    for idx, layer in enumerate(layers, start=1):
        name = layer["material"]
        if name not in materials_by_name:
            raise KeyError(f"La columna usa el material '{name}', pero no está definido en materials")

        mat = materials_by_name[name]
        thickness = float(layer["thickness"])
        z_bottom = z_top + thickness

        ordered_layers.append({
            "order": idx,
            "material_name": name,
            "depth_top": round(z_top, 5),
            "depth_bottom": round(z_bottom, 5),
            "thickness": thickness,
            "unit_weight_kn_m3": mat.get("unit_weight_kn_m3"),
            "shear_velocity": mat.get("shear_velocity"),
            "shear_properties": mat.get("shear_properties"),
            "dynamic_model": _dynamic_model_summary(mat.get("dynamic_model", {})),
        })
        z_top = z_bottom

    return {
        "metadata": config.get("metadata", {}),
        "freatic": config["column"].get("freatic"),
        "depth_failure_surface": config["column"].get("depth_failure_surface"),
        "discretization": config.get("discretization", {}),
        "materials_found_ordered": ordered_layers,
        "column": config["column"],
    }


def build_layers(materials_json: dict) -> Layers:
    logger.info(f"Construyendo {len(materials_json)} materiales")

    material_names = []
    vs_list = []
    unit_weights = []
    dynamic_curve = []
    shear_properties = []

    for mat in materials_json:
        logger.debug(f"Procesando material: {mat['material_name']}")

        material_names.append(mat["material_name"])
        vs_list.append(create_shear_velocity(mat))
        dynamic_curve.append(create_dynamic_model(mat["dynamic_model"]))
        unit_weights.append(mat["unit_weight_kn_m3"])
        shear_properties.append(mat["shear_properties"])

    return Layers(
        material_name=material_names,
        shear_velocity=vs_list,
        unit_weight_kn_m3=unit_weights,
        dynamic_curve=dynamic_curve,
        shear_properties=shear_properties,
    )


def build_column(column_json, layers):
    logger.info("Inicio de construcción de columna estratigráfica")
    material_names = []
    thickness = []

    for layer in column_json["layers"]:
        material_names.append(layer["material"])
        thickness.append(layer["thickness"])

    freatic = column_json["freatic"]
    return Columns(
        layers=layers,
        material_name=material_names,
        thickness=thickness,
        freatic=freatic,
    )


def export_data(output_subdir: Path, result_filename, df_final):

    output_dir = Path(output_subdir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df_final = df_final.reset_index(drop=True)
    df_final.insert(0, "id", range(1, len(df_final) + 1))

    file_path = output_dir / result_filename
    df_final.to_csv(file_path, index=False)


# TEMPORAL SI ES NECESARIO LEER JSON
# ================================================================
@log_execution_time
def execute_processing_from_json(
    input_dir, input_filename, output_subdir, output_filename
):

    # PROPROCESAMIENTO / ENTRADA DE DATOS
    # ================================================================
    config_path = input_dir / input_filename

    if not config_path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {config_path}")

    with open(config_path, "r") as f:
        config = json.load(f)

    # PROCESAMIENTO
    # ================================================================

    layer = build_layers(config["materials"])
    columna = build_column(config["column"], layer)

    column_final = columna.run(f_target=config["discretization"]["f_target"])

    #  TESTEO
    # ================================================================
    # fila = column_final.iloc[0]
    # modelo = fila["model"]

    # gg = modelo.gg_max()
    # damp = modelo.damping()

    # print("Tipo:", type(modelo))
    # print("GG:", gg[:5])
    # print("Damping:", damp[:5])

    export_data(output_subdir, output_filename, column_final)


# ================================================================


@log_execution_time
def execute_processing(config: dict, output_subdir, output_filename):

    # PROCESAMIENTO
    # ==============================

    layer = build_layers(config["materials"])
    columna = build_column(config["column"], layer)

    fig_dir = Path(output_subdir)

    column_final = columna.run(fig_dir, f_target=config["discretization"]["f_target"])

    #  TESTEO
    # ================================================================
    # fila = column_final.iloc[0]
    # modelo = fila["model"]

    # gg = modelo.gg_max()
    # damp = modelo.damping()

    # print("Tipo:", type(modelo))
    # print("GG:", gg[:5])
    # print("Damping:", damp[:5])

    export_data(output_subdir, output_filename, column_final)

    return column_final


if __name__ == "__main__":
    input_filename = "input_data.json"
    input_dir = "input_columns"
    output_subdir = "Calibraciones_de_prueba"
    output_filename = "resultados.csv"
    execute_processing_from_json(
        input_dir, input_filename, output_subdir, output_filename
    )
