from __future__ import annotations

from common import MATERIALS, ROOT
from dxf_demo import build_demo_dxf
from dynaengine import extract_columns_from_dxf, prepare_column_configs, process_column_config


def main() -> None:
    dxf_path = ROOT / "examples" / "_generated" / "simple_section.dxf"
    build_demo_dxf(dxf_path)

    extraction = extract_columns_from_dxf(dxf_path, x_positions=[25, 75])
    configs = prepare_column_configs(extraction.columns, MATERIALS[:2], target_frequency_hz=25)

    print("Materiales detectados:", extraction.material_names)
    for name, config in configs.items():
        result = process_column_config(config, calibrate=False)
        print(name, "capas=", len(result.raw), "segmentos=", len(result.discretized))


if __name__ == "__main__":
    main()
