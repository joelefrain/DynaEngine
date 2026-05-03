from __future__ import annotations

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

import ezdxf

from dynaengine import (
    CalibrationSettings,
    calibrate_dynamic_curve,
    evaluate_dynamic_curve,
    extract_columns_from_dxf,
    prepare_column_configs,
    process_column_config,
)


USER_DEFINED_CURVE = {
    "strain": [1e-6, 3e-6, 1e-5, 3e-5, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1],
    "ggmax": [0.995, 0.985, 0.955, 0.89, 0.72, 0.49, 0.25, 0.11, 0.04, 0.015, 0.006],
    "damp": [0.010, 0.011, 0.014, 0.023, 0.050, 0.090, 0.150, 0.190, 0.210, 0.205, 0.190],
}

MATERIALS = [
    {
        "material_name": "Arena",
        "unit_weight_kn_m3": 18.5,
        "shear_velocity": {"depth": [0, 5, 15, 30], "vs": [220, 280, 360, 460]},
        "shear_properties": {"c": 0, "phi": 34},
        "dynamic_model": {
            "model_type": "darendeli_2001",
            "sigma_vertical": 100,
            "soil_parameters": {"IP": 5, "OCR": 1, "k0": 0.7, "frequency": 1, "N": 10},
        },
    },
    {
        "material_name": "Grava",
        "unit_weight_kn_m3": 20.0,
        "shear_velocity": {"depth": [0, 5, 20, 40], "vs": [300, 360, 460, 620]},
        "shear_properties": {"c": 0, "phi": 38},
        "dynamic_model": {
            "model_type": "menq_2003",
            "sigma_vertical": 100,
            "soil_parameters": {"Cu": 15, "D50": 8, "k0": 0.7, "N": 10},
        },
    },
]

COLUMN = {
    "name": "columna_demo",
    "layers": [
        {"material": "Arena", "thickness": 8.0},
        {"material": "Grava", "thickness": 12.0},
    ],
    "freatic": 6.0,
    "depth_failure_surface": 18.0,
}


def run_curves() -> None:
    specs = [
        {
            "model_type": "darendeli_2001",
            "sigma_vertical": 100,
            "soil_parameters": {"IP": 5, "OCR": 1, "k0": 0.7, "frequency": 1, "N": 10},
        },
        {"model_type": "seed_1970", "soil_parameters": {"band": "mean"}},
        {
            "model_type": "user_defined",
            "sigma_vertical": 100,
            "soil_parameters": {"k0": 0.7},
            "data": USER_DEFINED_CURVE,
        },
    ]
    for spec in specs:
        curve = evaluate_dynamic_curve(spec)
        print(
            f"{curve.model_type}: {len(curve.strain)} puntos, "
            f"G/Gmax inicial={curve.ggmax[0]:.3f}, damping final={curve.damping_percent[-1]:.2f}%"
        )


def run_calibration() -> None:
    result = calibrate_dynamic_curve(
        USER_DEFINED_CURVE,
        gmax_pa=70_000_000,
        tau_max_pa=120_000,
        settings=CalibrationSettings(gqh_init_points=2, gqh_iterations=3, mrdf_init_points=2, mrdf_iterations=3),
    )
    print("Theta GQH:", {key: round(value, 4) for key, value in result.theta.items()})
    print("MRDF:", {key: round(value, 4) for key, value in result.mrdf.items()})


def run_column() -> None:
    result = process_column_config(
        {"materials": MATERIALS, "column": COLUMN, "discretization": {"target_frequency_hz": 25}},
        calibrate=False,
    )
    print("Capas sin discretizar:", len(result.raw))
    print("Segmentos discretizados:", len(result.discretized))
    print(result.discretized[["segment_id", "material_name", "thickness_m", "natural_frequency_hz"]].head())


def run_dxf() -> None:
    with TemporaryDirectory() as tmp:
        dxf_path = Path(tmp) / "simple_section.dxf"
        _build_demo_dxf(dxf_path)
        extraction = extract_columns_from_dxf(dxf_path, x_positions=[25, 75])
        configs = prepare_column_configs(extraction.columns, MATERIALS, target_frequency_hz=25)
        print("Materiales detectados:", extraction.material_names)
        for name, config in configs.items():
            result = process_column_config(config, calibrate=False)
            print(name, "capas=", len(result.raw), "segmentos=", len(result.discretized))


def _build_demo_dxf(path: Path) -> None:
    doc = ezdxf.new()
    for layer in ("EXTERNAL", "MATERIAL", "FREATIC", "SUP_FALLA", "TEXTO"):
        if layer not in doc.layers:
            doc.layers.add(layer)

    modelspace = doc.modelspace()
    modelspace.add_lwpolyline(
        [(0, 0), (100, 0), (100, 30), (0, 30), (0, 0)],
        dxfattribs={"layer": "EXTERNAL"},
    )
    modelspace.add_lwpolyline([(0, 18), (100, 18)], dxfattribs={"layer": "MATERIAL"})
    modelspace.add_lwpolyline([(0, 25), (100, 25)], dxfattribs={"layer": "FREATIC"})
    modelspace.add_lwpolyline([(0, 12), (100, 12)], dxfattribs={"layer": "SUP_FALLA"})
    modelspace.add_text("Arena", dxfattribs={"layer": "TEXTO", "height": 1.5}).set_placement((10, 24))
    modelspace.add_text("Grava", dxfattribs={"layer": "TEXTO", "height": 1.5}).set_placement((10, 8))
    doc.saveas(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="DynaEngine core runner")
    parser.add_argument(
        "example",
        nargs="?",
        choices=("curves", "calibration", "column", "dxf"),
        default="column",
        help="Example to execute",
    )
    args = parser.parse_args()
    runners = {
        "curves": run_curves,
        "calibration": run_calibration,
        "column": run_column,
        "dxf": run_dxf,
    }
    runners[args.example]()


if __name__ == "__main__":
    main()
