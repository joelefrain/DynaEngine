from __future__ import annotations

from common import USER_DEFINED_CURVE
from dynaengine import CalibrationSettings, calibrate_dynamic_curve


def main() -> None:
    result = calibrate_dynamic_curve(
        USER_DEFINED_CURVE,
        gmax_pa=70_000_000,
        tau_max_pa=120_000,
        settings=CalibrationSettings(
            gqh_init_points=2,
            gqh_iterations=3,
            mrdf_init_points=2,
            mrdf_iterations=3,
        ),
    )

    print("Theta GQH:", {key: round(value, 4) for key, value in result.theta.items()})
    print("MRDF:", {key: round(value, 4) for key, value in result.mrdf.items()})


if __name__ == "__main__":
    main()
