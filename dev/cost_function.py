import numpy as np

from libs.config.config_variables import (
    WEIGHTED_FUNCTION,
    STRAIN_RANGE_PCT,
)

def curvature_weight(GGmax_GQH):
    log_gamma = np.log10(STRAIN_RANGE_PCT)
    d1 = np.gradient(GGmax_GQH, log_gamma)
    d2 = np.gradient(d1, log_gamma)
    curvatura = np.abs(d2)

    weights = curvatura / np.max(curvatura)
    weights = WEIGHTED_FUNCTION[0] + WEIGHTED_FUNCTION[1] * weights
    return weights

def error_area_between_curves(GGmax_GQH, GG_model):

    log_gamma = np.log10(STRAIN_RANGE_PCT)

    diff = np.abs(GGmax_GQH - GG_model)

    area = np.trapz(diff, log_gamma)
    error_area = area / (
    np.trapz(np.abs(GGmax_GQH), np.log10(STRAIN_RANGE_PCT))
    )
    return error_area

def cost_function_curvature(GGmax_GQH, GG_model):
    weights = curvature_weight(GGmax_GQH)
    return np.mean(weights * (GGmax_GQH - GG_model) ** 2)

def cost_function_total(GGmax_GQH, GG_model,
                        alpha_curv=0.7,
                        alpha_area=0.3):

    error_curv = cost_function_curvature(GGmax_GQH, GG_model)
    error_area = error_area_between_curves(GGmax_GQH, GG_model)

    return alpha_curv * error_curv + alpha_area * error_area

# Clase funciones de costo GQH - HH (Input: Hiperparametros)
# Cambiar nombres (independiente del modelo)