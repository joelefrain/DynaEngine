"""
Public functions in this package are pure Python entry points for the future
desktop frontend. They do not write files unless an explicit output path is
provided by the caller.
"""

from dynaengine.calibration import CalibrationResult, CalibrationSettings, calibrate_dynamic_curve
from dynaengine.columns import (
    ColumnLayer,
    DiscretizationSettings,
    Material,
    MaterialLibrary,
    ShearVelocityProfile,
    StratigraphicColumn,
    build_raw_column_table,
    calibrate_discretized_column,
    discretize_column,
)
from dynaengine.dxf import DxfColumnExtraction, extract_columns_from_dxf
from dynaengine.dynamic_curves import DynamicCurveResult, DynamicModelSpec, evaluate_dynamic_curve
from dynaengine.pipeline import (
    ColumnProcessingResult,
    export_dataframe,
    filter_columns,
    prepare_column_configs,
    process_column_config,
    process_dxf_folder,
)
from dynaengine.plots import (
    plot_column_discretized_detailed,
    plot_dxf_extraction,
    plot_raw_column,
    plot_discretized_column,
    plot_dynamic_curve,
    plot_shear_velocity_profile,
)

__all__ = [
    "CalibrationResult",
    "CalibrationSettings",
    "ColumnLayer",
    "ColumnProcessingResult",
    "DiscretizationSettings",
    "DxfColumnExtraction",
    "DynamicCurveResult",
    "DynamicModelSpec",
    "Material",
    "MaterialLibrary",
    "ShearVelocityProfile",
    "StratigraphicColumn",
    "build_raw_column_table",
    "calibrate_discretized_column",
    "calibrate_dynamic_curve",
    "discretize_column",
    "evaluate_dynamic_curve",
    "export_dataframe",
    "extract_columns_from_dxf",
    "filter_columns",
    "plot_dxf_extraction",
    "plot_raw_column",
    "plot_discretized_column",
    "plot_column_discretized_detailed",
    "plot_dynamic_curve",
    "plot_shear_velocity_profile",
    "prepare_column_configs",
    "process_column_config",
    "process_dxf_folder",
]
