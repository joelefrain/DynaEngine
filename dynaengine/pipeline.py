"""High-level orchestration for DXF columns and optional file exports."""

from __future__ import annotations

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
from dynaengine.dxf import extract_columns_from_dxf

FailureTypeInput = dict[str | int, str] | list[str] | tuple[str, ...] | str


@dataclass(frozen=True)
class ColumnProcessingResult:
    raw: pd.DataFrame
    discretized: pd.DataFrame
    calibrated: pd.DataFrame | None = None

    @property
    def result(self) -> pd.DataFrame:
        return self.calibrated if self.calibrated is not None else self.discretized


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
    x_positions_by_file: dict[str, list[float]],
    materials: list[dict[str, Any]],
    target_frequency_hz: float,
    calibrate: bool = False,
    failure_types_by_file: dict[str, FailureTypeInput] | None = None,
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
        failure_types = _failure_types_for_file(dxf_path, failure_types_by_file)
        extraction = extract_columns_from_dxf(
            dxf_path, positions, failure_types=failure_types
        )
        columns = filter_columns(extraction.columns, selected_columns, excluded_columns)
        configs = prepare_column_configs(columns, materials, target_frequency_hz)
        for name, config in configs.items():
            csv_path = None if output_path is None else output_path / f"{name}.csv"
            results[name] = process_column_config(
                config, calibrate=calibrate, output_csv=csv_path
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
    dxf_path: Path, x_positions_by_file: dict[str, list[float]]
) -> list[float]:
    for key in (dxf_path.name, dxf_path.stem, str(dxf_path)):
        if key in x_positions_by_file:
            return x_positions_by_file[key]
    raise ValueError(f"No se definieron x_positions para {dxf_path.name}")


def _failure_types_for_file(
    dxf_path: Path,
    failure_types_by_file: dict[str, FailureTypeInput] | None,
) -> FailureTypeInput | None:
    if not failure_types_by_file:
        return None
    for key in (dxf_path.name, dxf_path.stem, str(dxf_path)):
        if key in failure_types_by_file:
            return failure_types_by_file[key]
    return None
