from __future__ import annotations

from common import MATERIALS, ROOT
from dxf_demo import build_demo_dxf
from dynaengine import (
    extract_columns_from_dxf,
    prepare_column_configs,
    process_column_config,
)


REAL_DXF = ROOT / "examples" / "data" / "section_01.dxf"

REAL_DXF_ALIASES = {
    "Grava arcillosa": "Arena",
    "Grava arenosa": "Grava",
    "Grava pobremente gradada": "Grava",
    "Material de poza": "Curva usuario",
    "Material dique": "Arena",
}

REAL_DXF_FAILURE_TYPES = [
    "rotacional",
    "rotacional",
    "planar",
    "compuesta",
    "compuesta",
    "bloque",
    "bloque",
]


def main() -> None:
    if REAL_DXF.exists():
        dxf_path = REAL_DXF
        x_positions = [190, 225, 250, 290, 320, 350, 400]
        aliases = REAL_DXF_ALIASES
        failure_types = REAL_DXF_FAILURE_TYPES
        materials = MATERIALS
    else:
        dxf_path = ROOT / "examples" / "_generated" / "simple_section.dxf"
        build_demo_dxf(dxf_path)
        x_positions = [25, 75]
        aliases = None
        failure_types = "demo"
        materials = MATERIALS[:2]

    extraction = extract_columns_from_dxf(
        dxf_path,
        x_positions=x_positions,
        material_aliases=aliases,
        failure_types=failure_types,
    )
    configs = prepare_column_configs(
        extraction.columns, materials, target_frequency_hz=25
    )

    print("Materiales detectados:", extraction.material_names)
    print("Superficies de falla:")
    for name, data in extraction.failure_surfaces.items():
        print(name, "tipo=", data["failure_type"], "altura=", data["failure_height"])
    for name, config in configs.items():
        result = process_column_config(config, calibrate=False)
        print(name, "capas=", len(result.raw), "segmentos=", len(result.discretized))


if __name__ == "__main__":
    main()
