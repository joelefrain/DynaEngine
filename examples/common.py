from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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
    {
        "material_name": "Curva usuario",
        "unit_weight_kn_m3": 19.0,
        "shear_velocity": {"depth": [0, 10, 25, 40], "vs": [250, 330, 430, 560]},
        "shear_properties": {"c": 5, "phi": 32},
        "dynamic_model": {
            "model_type": "user_defined",
            "sigma_vertical": 100,
            "soil_parameters": {"k0": 0.7},
            "data": USER_DEFINED_CURVE,
        },
    },
]


COLUMN = {
    "name": "columna_demo",
    "layers": [
        {"material": "Arena", "thickness": 8.0},
        {"material": "Grava", "thickness": 12.0},
        {"material": "Curva usuario", "thickness": 10.0},
    ],
    "freatic": 6.0,
    "depth_failure_surface": 18.0,
}
