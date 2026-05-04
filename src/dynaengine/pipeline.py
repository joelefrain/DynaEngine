"""High-level orchestration for DXF columns and optional file exports."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from dynaengine.calibration import CalibrationSettings
from dynaengine.columns import (
    DiscretizationSettings,
    MaterialLibrary,
    StratigraphicColumn,
    build_raw_column_table,
    calibrate_discretized_column,
    discretize_column,
)
from dynaengine.dxf import (
    FailurePositionInput,
    FailureTypeInput,
    MINIMUM_AREA_SCALE,
    UNIDENTIFIED_PREFIX,
    apply_material_aliases,
    extract_columns_from_dxf,
)

UnidentifiedMaterialActions = dict[str, Any]


@dataclass(frozen=True)
class ColumnProcessingResult:
    raw: pd.DataFrame
    discretized: pd.DataFrame
    calibrated: pd.DataFrame | None = None

    @property
    def result(self) -> pd.DataFrame:
        return self.calibrated if self.calibrated is not None else self.discretized


@dataclass(frozen=True)
class MaterialResolution:
    materials: list[dict[str, Any]]
    aliases: dict[str, str]
    unresolved: list[str]


def filter_columns(
    columns: dict[str, dict[str, Any]],
    selected_names: list[str] | None = None,
    excluded_names: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    selected = set(selected_names or columns.keys())
    excluded = set(excluded_names or [])
    return {
        name: column
        for name, column in columns.items()
        if name in selected and name not in excluded
    }


def resolve_unidentified_materials(
    materials: list[dict[str, Any]],
    unidentified_materials: list[str],
    actions: UnidentifiedMaterialActions | None = None,
    material_aliases: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Resolve DXF layers named ``Estrato no identificado ...``.

    Each unidentified stratum must be resolved in one of two ways:

    1. characterize it as a material, by providing either a material with the
       same name in ``materials`` or an action ``{"action": "characterize", ...}``;
    2. assign it to a material that is already characterized, by using
       ``material_aliases`` or an action such as ``{"action": "assign", "material": "CL"}``.

    Characterization actions may optionally include ``name``/``material_name`` to
    rename the stratum while adding its properties.
    """

    resolution = resolve_unidentified_materials_detailed(
        materials,
        unidentified_materials,
        actions=actions,
        material_aliases=material_aliases,
    )
    if resolution.unresolved:
        raise ValueError(
            "Estratos no identificados sin resolver: "
            + ", ".join(resolution.unresolved)
            + ". Para cada uno, caracterice sus propiedades como material nuevo "
            + "(opcionalmente con nombre nuevo) o asignelo a un material ya caracterizado."
        )

    return resolution.materials, resolution.aliases


def resolve_unidentified_materials_detailed(
    materials: list[dict[str, Any]],
    unidentified_materials: list[str],
    actions: UnidentifiedMaterialActions | None = None,
    material_aliases: dict[str, str] | None = None,
) -> MaterialResolution:
    """Resolve unidentified strata without forcing unresolved ones to be used."""

    actions = actions or {}
    incoming_aliases = material_aliases or {}
    resolved_aliases: dict[str, str] = {}
    resolved_materials = [dict(material) for material in materials]
    material_names = {
        str(material.get("material_name"))
        for material in resolved_materials
        if material.get("material_name") is not None
    }

    unresolved = []
    for unidentified in unidentified_materials:
        if unidentified in material_names:
            continue

        if unidentified in incoming_aliases:
            target = str(incoming_aliases[unidentified])
            if target not in material_names:
                raise ValueError(
                    f"El alias de '{unidentified}' apunta a un material no caracterizado: {target}"
                )
            resolved_aliases[unidentified] = target
            continue

        action = actions.get(unidentified)
        if action is None:
            unresolved.append(unidentified)
            continue

        alias, material = _resolve_unidentified_action(
            unidentified, action, material_names
        )
        if material is not None:
            resolved_materials.append(material)
            material_names.add(str(material["material_name"]))
        if alias is not None:
            source, target = alias
            resolved_aliases[source] = target

    return MaterialResolution(
        materials=resolved_materials,
        aliases=resolved_aliases,
        unresolved=unresolved,
    )


def filter_columns_with_unresolved_materials(
    columns: dict[str, dict[str, Any]],
    unresolved_materials: list[str],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Omit columns crossing unresolved unidentified strata."""

    unresolved = set(unresolved_materials)
    if not unresolved:
        return columns, []

    filtered: dict[str, dict[str, Any]] = {}
    omitted: list[dict[str, Any]] = []
    for column_name, column in columns.items():
        column_unresolved = sorted(
            {
                str(layer["material"])
                for layer in column.get("layers", [])
                if str(layer.get("material")) in unresolved
            }
        )
        if column_unresolved:
            omitted.append(
                {
                    "column_name": column_name,
                    "x_position": column.get("x_position"),
                    "failure_surface": column.get("failure_surface"),
                    "unresolved_materials": column_unresolved,
                }
            )
            continue
        filtered[column_name] = column

    return filtered, omitted


def _resolve_unidentified_action(
    unidentified: str,
    action: Any,
    material_names: set[str],
) -> tuple[tuple[str, str] | None, dict[str, Any] | None]:
    if isinstance(action, str):
        if action not in material_names:
            raise ValueError(
                f"'{unidentified}' se asigno a un material no caracterizado: {action}"
            )
        return (unidentified, action), None

    if not isinstance(action, dict):
        raise ValueError(
            f"La accion para '{unidentified}' debe ser texto o diccionario"
        )

    action_type = str(action.get("action", "assign")).strip().lower()
    if action_type in {"assign", "assign_existing", "asignar", "alias"}:
        target = (
            action.get("material")
            or action.get("material_name")
            or action.get("assign_to")
        )
        if target is None:
            raise ValueError(
                f"La accion de asignacion para '{unidentified}' requiere material"
            )
        target = str(target)
        if target not in material_names:
            raise ValueError(
                f"'{unidentified}' se asigno a un material no caracterizado: {target}"
            )
        return (unidentified, target), None

    if action_type in {"characterize", "caracterizar", "define", "new_material"}:
        material_data = action.get("properties") or action.get("material")
        if material_data is None:
            material_data = {
                key: value
                for key, value in action.items()
                if key not in {"action", "name", "assign_to"}
            }
        if not isinstance(material_data, dict):
            raise ValueError(
                f"La caracterizacion de '{unidentified}' debe contener propiedades de material"
            )
        target_name = (
            action.get("name")
            or action.get("material_name")
            or material_data.get("material_name")
            or unidentified
        )
        material = {**material_data, "material_name": str(target_name)}
        alias = (
            None
            if str(target_name) == unidentified
            else (unidentified, str(target_name))
        )
        return alias, material

    raise ValueError(
        f"Accion no soportada para '{unidentified}': {action_type}. Use assign o characterize."
    )


def prepare_column_configs(
    columns: dict[str, dict[str, Any]],
    materials: list[dict[str, Any]],
    target_frequency_hz: float,
) -> dict[str, dict[str, Any]]:
    return {
        name: {
            "materials": materials,
            "column": {**column, "name": name},
            "discretization": {"target_frequency_hz": target_frequency_hz},
        }
        for name, column in columns.items()
    }


def process_column_config(
    config: dict[str, Any],
    calibrate: bool = False,
    calibration_settings: CalibrationSettings | None = None,
    output_csv: str | Path | None = None,
) -> ColumnProcessingResult:
    materials = MaterialLibrary.from_mappings(config["materials"])
    column = StratigraphicColumn.from_mapping(config["column"])
    settings = DiscretizationSettings.from_mapping(config.get("discretization"))

    raw = build_raw_column_table(column, materials)
    discretized = discretize_column(column, materials, settings)
    calibrated = None
    if calibrate:
        calibrated = calibrate_discretized_column(
            discretized, materials, settings=calibration_settings
        )

    result = ColumnProcessingResult(
        raw=raw, discretized=discretized, calibrated=calibrated
    )
    if output_csv is not None:
        export_dataframe(result.result, output_csv)
    return result


def process_dxf_folder(
    section_folder: str | Path,
    x_positions_by_file: dict[str, FailurePositionInput],
    materials: list[dict[str, Any]],
    target_frequency_hz: float,
    calibrate: bool = False,
    calibration_settings: CalibrationSettings | None = None,
    failure_types_by_file: dict[str, FailureTypeInput] | None = None,
    material_aliases_by_file: dict[str, dict[str, str]] | dict[str, str] | None = None,
    unidentified_material_actions_by_file: dict[str, Any] | None = None,
    small_area_scale: float = MINIMUM_AREA_SCALE,
    selected_columns: list[str] | None = None,
    excluded_columns: list[str] | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, ColumnProcessingResult]:
    section_folder = Path(section_folder)
    if not section_folder.exists():
        raise FileNotFoundError(f"No existe la carpeta DXF: {section_folder}")

    output_path = Path(output_dir) if output_dir is not None else None
    if output_path is not None:
        output_path.mkdir(parents=True, exist_ok=True)

    results = {}
    for dxf_path in sorted(section_folder.glob("*.dxf")):
        positions = _positions_for_file(dxf_path, x_positions_by_file)
        failure_types = _value_for_file(dxf_path, failure_types_by_file)
        material_aliases = _material_aliases_for_file(
            dxf_path, material_aliases_by_file
        )
        unidentified_actions = _unidentified_actions_for_file(
            dxf_path, unidentified_material_actions_by_file
        )
        extraction = extract_columns_from_dxf(
            dxf_path,
            positions,
            material_aliases=material_aliases,
            failure_types=failure_types,
            small_area_scale=small_area_scale,
        )
        resolution = resolve_unidentified_materials_detailed(
            materials,
            extraction.unidentified_materials,
            actions=unidentified_actions,
            material_aliases=material_aliases,
        )
        all_aliases = {**(material_aliases or {}), **resolution.aliases}
        columns = apply_material_aliases(extraction.columns, all_aliases)
        columns, omitted = filter_columns_with_unresolved_materials(
            columns, resolution.unresolved
        )
        if omitted:
            warnings.warn(
                f"Se omitieron {len(omitted)} columnas de {dxf_path.name} "
                "porque cruzan estratos no identificados sin resolver: "
                + ", ".join(item["column_name"] for item in omitted),
                RuntimeWarning,
                stacklevel=2,
            )
        columns = filter_columns(columns, selected_columns, excluded_columns)
        configs = prepare_column_configs(
            columns, resolution.materials, target_frequency_hz
        )
        for name, config in configs.items():
            csv_path = None if output_path is None else output_path / f"{name}.csv"
            results[name] = process_column_config(
                config,
                calibrate=calibrate,
                calibration_settings=calibration_settings,
                output_csv=csv_path,
            )
    return results


def export_dataframe(frame: pd.DataFrame, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    export = frame.reset_index(drop=True).copy()
    if "id" not in export.columns:
        export.insert(0, "id", range(1, len(export) + 1))
    export.to_csv(output_path, index=False)
    return output_path


def _positions_for_file(
    dxf_path: Path, x_positions_by_file: dict[str, FailurePositionInput]
) -> FailurePositionInput:
    for key in (dxf_path.name, dxf_path.stem, str(dxf_path)):
        if key in x_positions_by_file:
            return x_positions_by_file[key]
    raise ValueError(f"No se definieron x_positions para {dxf_path.name}")


def _value_for_file(dxf_path: Path, values_by_file: dict[str, Any] | None) -> Any:
    if not values_by_file:
        return None
    for key in (dxf_path.name, dxf_path.stem, str(dxf_path)):
        if key in values_by_file:
            return values_by_file[key]
    return None


def _material_aliases_for_file(
    dxf_path: Path,
    material_aliases_by_file: dict[str, dict[str, str]] | dict[str, str] | None,
) -> dict[str, str] | None:
    if not material_aliases_by_file:
        return None
    value = _value_for_file(dxf_path, material_aliases_by_file)
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items()}
    if value is None and all(
        isinstance(key, str) and not key.lower().endswith(".dxf")
        for key in material_aliases_by_file
    ):
        return {str(k): str(v) for k, v in material_aliases_by_file.items()}  # type: ignore[union-attr]
    return None


def _unidentified_actions_for_file(
    dxf_path: Path,
    actions_by_file: dict[str, Any] | None,
) -> UnidentifiedMaterialActions | None:
    if not actions_by_file:
        return None
    value = _value_for_file(dxf_path, actions_by_file)
    if isinstance(value, dict):
        return value
    if any(str(key).startswith(UNIDENTIFIED_PREFIX) for key in actions_by_file):
        return actions_by_file
    return None
