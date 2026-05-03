"""Numerical constants used by DynaEngine core calculations."""

from __future__ import annotations

import numpy as np

DEFAULT_SHEAR_STRAIN = np.logspace(-6, -1, 100)
SEED_IDRISS_SHEAR_STRAIN = np.logspace(-6, -2, 100)

GRAVITY = 9.81
ATM_PRESSURE_KPA = 101.3
KPA_TO_PA = 1_000.0
MPA_TO_PA = 1_000_000.0
PERCENT_TO_NUMBER = 100.0

MIN_FLOAT = 1e-12
MAX_FLOAT = 1e12
ROUND_DECIMALS = 5
MINIMUM_THICKNESS_M = 0.01

DEFAULT_K0 = 0.7
DEFAULT_THETA_4 = 1.0
PHI_FACTOR_RANGE = (1.1, 1.4)

MASING_COEFFICIENTS = {
    "c1": np.array([-1.1143, 1.8618, 0.2523]),
    "c2": np.array([0.0805, -0.0710, -0.0095]),
    "c3": np.array([-0.0005, 0.0002, 0.0003]),
}

DARENDELI_PARAMETERS = {
    "phi1": 0.0352,
    "phi2": 0.0010,
    "phi3": 0.3246,
    "phi4": 0.3483,
    "phi5": 0.9190,
    "phi6": 0.8005,
    "phi7": 0.0129,
    "phi8": -0.1069,
    "phi9": -0.2889,
    "phi10": 0.2919,
    "phi11": 0.6329,
    "phi12": -0.0057,
}

GQH_PARAMETER_BOUNDS = {
    "theta_1": (-2.0, 2.0),
    "theta_2": (-3.0, 2.0),
    "theta_3": (0.01, 8.0),
    "theta_5": (0.0, 1.0),
}

MRDF_PARAMETER_BOUNDS = {
    "P1": (0.0, 1.0),
    "P2": (0.05, 1.0),
    "P3": (0.5, 30.0),
    "Dmin": (0.0, 1.0),
}

GGMAX_CALIBRATION_WEIGHTS = {
    "bias": 0.05,
    "upper_curvature": 0.25,
    "lower_curvature": 0.25,
    "area": 0.45,
    "gamma_50": 30.0,
}

DAMPING_CALIBRATION_WEIGHTS = {
    "area": 0.4,
    "boundary": 0.3,
    "monotonic": 0.1,
    "smooth": 0.1,
    "oscillation": 0.1,
    "slope": 0.05,
    "spike": 0.05,
}

SEED_IDRISS_BANDS = ("upper", "lower", "mean")

WANG_GROUP_ALIASES = {
    "clean_sand_and_gravel_group": "Clean sand and gravel group",
    "clean sand and gravel group": "Clean sand and gravel group",
    "nonplastic_silty_sand_group": "Nonplastic silty sand group",
    "nonplastic silty sand group": "Nonplastic silty sand group",
    "clayed_soil_group": "Clayey soil group",
    "clayey_soil_group": "Clayey soil group",
    "clayey soil group": "Clayey soil group",
}
