"""
DynaEngine is a Python package designed for processing and analyzing stratigraphic column data.
"""

from .calibration import (
    CalibrationResult,
    CalibrationSettings,
    calibrate_dynamic_curve,
)
from .columns import (
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
from .dxf import (
    DxfColumnExtraction,
    apply_material_aliases,
    extract_columns_from_dxf,
    summarize_polygon_areas,
)
from .dynamic_curves import (
    DynamicCurveResult,
    DynamicModelSpec,
    evaluate_dynamic_curve,
)
from .pipeline import (
    ColumnProcessingResult,
    MaterialResolution,
    export_dataframe,
    filter_columns_with_unresolved_materials,
    filter_columns,
    prepare_column_configs,
    process_column_config,
    process_dxf_folder,
    resolve_unidentified_materials,
    resolve_unidentified_materials_detailed,
)
from .plots import (
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
    "MaterialResolution",
    "ShearVelocityProfile",
    "StratigraphicColumn",
    "build_raw_column_table",
    "calibrate_discretized_column",
    "calibrate_dynamic_curve",
    "discretize_column",
    "evaluate_dynamic_curve",
    "export_dataframe",
    "extract_columns_from_dxf",
    "apply_material_aliases",
    "filter_columns_with_unresolved_materials",
    "filter_columns",
    "summarize_polygon_areas",
    "plot_dxf_extraction",
    "plot_raw_column",
    "plot_discretized_column",
    "plot_column_discretized_detailed",
    "plot_dynamic_curve",
    "plot_shear_velocity_profile",
    "prepare_column_configs",
    "process_column_config",
    "process_dxf_folder",
    "resolve_unidentified_materials",
    "resolve_unidentified_materials_detailed",
]
