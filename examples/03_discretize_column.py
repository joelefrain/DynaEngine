from __future__ import annotations

from common import COLUMN, MATERIALS
from dynaengine import process_column_config


def main() -> None:
    config = {
        "materials": MATERIALS,
        "column": COLUMN,
        "discretization": {"target_frequency_hz": 25},
    }
    result = process_column_config(config, calibrate=False)

    print("Columna sin discretizar")
    print(result.raw[["material_name", "thickness_m", "shear_velocity_m_s", "passes_failure_surface"]])
    print("\nColumna discretizada")
    print(result.discretized[["segment_id", "material_name", "thickness_m", "natural_frequency_hz"]].head())


if __name__ == "__main__":
    main()
