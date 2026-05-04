"""Dynamic-curve model catalog and input validation."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from dynaengine.constants import SEED_IDRISS_BANDS, WANG_GROUP_ALIASES

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_CATALOG_PATH = PACKAGE_DIR / "data" / "dynamic_curve_models.json"

MODEL_ALIASES = {
    "seedidriss_1970": "seed_1970",
    "seed_idriss_1970": "seed_1970",
    "seed_1970": "seed_1970",
}

CATALOG_MODEL_ALIASES = {
    "seed_1970": "seedidriss_1970",
}

PARAMETER_ALIASES = {
    "FC": "CF",
    "fc": "CF",
}


def normalize_model_type(model_type: str) -> str:
    key = str(model_type).strip().lower()
    return MODEL_ALIASES.get(key, key)


def normalize_wang_group(group: str) -> str:
    key = str(group).strip().lower()
    if key not in WANG_GROUP_ALIASES:
        raise ValueError(f"Grupo Wang & Stokoe no soportado: {group}")
    return WANG_GROUP_ALIASES[key]


@lru_cache(maxsize=1)
def load_dynamic_curve_catalog(path: str | Path | None = None) -> dict[str, Any]:
    catalog_path = Path(path) if path else DEFAULT_CATALOG_PATH
    with catalog_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def dynamic_curve_catalog_for_frontend() -> dict[str, Any]:
    catalog = load_dynamic_curve_catalog()
    result = dict(catalog)
    if "seedidriss_1970" in result:
        result["seed_1970"] = result["seedidriss_1970"]
    return result


def normalize_soil_parameters(
    model_type: str, parameters: dict[str, Any]
) -> dict[str, Any]:
    model_type = normalize_model_type(model_type)
    normalized = {}

    for key, value in parameters.items():
        normalized[PARAMETER_ALIASES.get(key, key)] = value

    if model_type == "wang_2021" and "soil_group" in normalized:
        normalized["soil_group"] = normalize_wang_group(normalized["soil_group"])

    return normalized


def validate_dynamic_model_definition(
    model_type: str,
    soil_parameters: dict[str, Any],
    curve_data: dict[str, Any] | None = None,
) -> None:
    model_type = normalize_model_type(model_type)
    catalog = load_dynamic_curve_catalog()
    catalog_key = CATALOG_MODEL_ALIASES.get(model_type, model_type)

    if catalog_key not in catalog:
        raise ValueError(f"Modelo dinamico no soportado: {model_type}")

    if model_type == "seed_1970":
        band = soil_parameters.get("band")
        if band not in SEED_IDRISS_BANDS:
            raise ValueError(
                "La banda de Seed & Idriss debe ser una de: "
                + ", ".join(SEED_IDRISS_BANDS)
            )
        return

    model_metadata = catalog[catalog_key]
    model_parameters = model_metadata["model_parameters"]

    if model_type == "wang_2021":
        group = normalize_wang_group(soil_parameters.get("soil_group", ""))
        reverse_group_alias = {
            "Clean sand and gravel group": "clean_sand_and_gravel_group",
            "Nonplastic silty sand group": "nonplastic_silty_sand_group",
            "Clayey soil group": "clayed_soil_group",
        }
        group_key = reverse_group_alias[group]
        model_parameters = model_parameters[group_key]

    for name, metadata in model_parameters.items():
        internal_name = PARAMETER_ALIASES.get(name, name)
        if (
            internal_name not in soil_parameters
            or soil_parameters[internal_name] is None
        ):
            raise ValueError(
                f"Falta el parametro requerido '{internal_name}' para {model_type}"
            )

        if metadata.get("type") != "float":
            continue

        value = float(soil_parameters[internal_name])
        min_value = metadata.get("min_value")
        max_value = metadata.get("max_value")
        if min_value is not None and value < float(min_value):
            raise ValueError(f"{internal_name} debe ser >= {min_value}")
        if max_value is not None and value > float(max_value):
            raise ValueError(f"{internal_name} debe ser <= {max_value}")

    if model_type == "user_defined":
        validate_user_curve_data(curve_data)


def validate_user_curve_data(curve_data: dict[str, Any] | None) -> None:
    if not curve_data:
        raise ValueError("El modelo definido por el usuario requiere datos de curva")

    damping_key = "damp" if "damp" in curve_data else "damping"
    required = ("strain", "ggmax", damping_key)
    for key in required:
        if key not in curve_data:
            raise ValueError(
                f"Falta el campo '{key}' en la curva definida por el usuario"
            )

    lengths = {len(curve_data[key]) for key in required}
    if len(lengths) != 1:
        raise ValueError(
            "strain, ggmax y damping deben tener la misma cantidad de puntos"
        )

    if not lengths or next(iter(lengths)) < 2:
        raise ValueError(
            "La curva definida por el usuario necesita al menos dos puntos"
        )
