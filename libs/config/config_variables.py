# Este archivo contiene variables de configuración para la aplicación.
# ---------------------------------------------------------------
import os
import numpy as np
from pathlib import Path

# Rutas a carpetas destacadas
# ---------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent.parent

LOG_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

STORAGE_DIR = BASE_DIR / "var"

OUTPUT_DIR = Path(os.environ.get("PRISMO_OUTPUT_DIR", r"C:\Prismo"))

# Constantes
# ---------------------------------------------------------------
CONVERT_MS2_TO_G = 9.81
MIN_FLOAT = 1e-12
MAX_FLOAT = 1e12
EXP_LIMIT = 500
ROUND_DECIMALS = 5

# Pesos de ajuste a modelo HH
# ---------------------------------------------------------------

WEIGHTED_GGMAX_MKZ = {
    "curve_weight_1": 0.07,
    "curve_weight_2": 0.63,
    "area_weight": 0.3,
}

WEIGHTED_GGMAX_GQH = {
    "sesgo": 0.05,
    "curve_weight_super": 0.25,  # sesgo
    "curve_weight_inf": 0.25,  # 60% para urv superior
    "area_weight": 0.45,
}

WEIGHTED_DAMPING_MRDF = {
    "area_weight": 0.4,
    "boundary_weight": 0.3,
    "monotonic_weight": 0.1,
    "smooth_weight": 0.1,
    "oscillation_weight": 0.1,
    "slope_weight": 0.05,
    "spike_weight": 0.05,
}

GAMMA_50_WEIGHT = 30.0

LIMIT_CALIBRATED_HH = {
    "gamma_t": (1e-5, 1e-1),
    "s": (0.3, 5),
    "d": (0.1, 6),
    "mu": (1, 1e5),
    "a": (0.01, 1),
}

LIMIT_CALIBRATED_GQH = {
    "theta_1": (-2.0, 2.0),
    "theta_2": (-3.0, 2.0),
    "theta_3": (0.01, 8.0),
    "theta_5": (0.0, 1.0),
}

LIMIT_CALIBRATED_MRDF = {
    "P1": (0.0, 1.0),
    "P2": (0.05, 1.0),
    "P3": (0.5, 30.0),
    "Dmin": (0.0, 1.0),
}

# Curvas dinámicas
# ---------------------------------------------------------------

SHEAR_STRAIN = np.logspace(-6, -1, 100)
SHEAR_STRAIN_SEED = np.logspace(-6, -2, 100)
STRAIN_RANGE = [
    0.000001,
    0.000003,
    0.00001,
    0.00003,
    0.0001,
    0.0003,
    0.001,
    0.003,
    0.007,
    0.01,
    0.03,
    0.07,
    0.1,
]

ATM_CONVERT = 101.3

EXP1_CONVERT = 1e1
PERCENT_TO_NUMBER = 1e2
KPA_TO_PA = 1e3
MPA_TO_PA = 1e6

# Coeficientes de transfomación Massing-Darendeli
# ---------------------------------------------------------------
MASING_COEFFS = {
    "c1": np.array([-1.1143, 1.8618, 0.2523]),
    "c2": np.array([0.0805, -0.0710, -0.0095]),
    "c3": np.array([-0.0005, 0.0002, 0.0003]),
}
# Parámetros de Darendeli
# ---------------------------------------------------------------
DAR_PARAMS = {
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

# Parámetros propiedades de columna estratificada
# ---------------------------------------------------------------
K0_DEFAULD = 0.7
PHI_CONSTANT = {"min_val": 1.1, "max_val": 1.4}

# Propiedades geométricas de columna estratigráfica
# ---------------------------------------------------------------
MINIMUM_THICKNESS = 0.01  # En metros (1 cm)
