from __future__ import annotations

from common import USER_DEFINED_CURVE
from dynaengine import DynamicModelSpec, evaluate_dynamic_curve


def main() -> None:
    specs = [
        {
            "model_type": "darendeli_2001",
            "sigma_vertical": 100,
            "soil_parameters": {"IP": 5, "OCR": 1, "k0": 0.7, "frequency": 1, "N": 10},
        },
        {
            "model_type": "seed_1970",
            "soil_parameters": {"band": "mean"},
        },
        {
            "model_type": "user_defined",
            "sigma_vertical": 100,
            "soil_parameters": {"k0": 0.7},
            "data": USER_DEFINED_CURVE,
        },
    ]

    for item in specs:
        curve = evaluate_dynamic_curve(DynamicModelSpec.from_mapping(item))
        print(
            f"{curve.model_type}: {len(curve.strain)} puntos, "
            f"G/Gmax inicial={curve.ggmax[0]:.3f}, damping final={curve.damping_percent[-1]:.2f}%"
        )


if __name__ == "__main__":
    main()
