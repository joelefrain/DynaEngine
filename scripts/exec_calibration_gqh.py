import numpy as np

import matplotlib

from bayes_opt import BayesianOptimization

from modules.dynamic_curves.class_cost_function import GGmaxCalibrationCost
from modules.dynamic_curves.helper_calibration_gqh import GQHModelFormulation
from modules.dynamic_curves.helper_transformation_hh import GGmax_HH_model

matplotlib.use("Agg")

def calculate_calibration(
    general_params: dict, base_params_gqh: dict, modelo: str
) -> dict:
    match modelo:
        case "0":
            model = GQHModelFormulation(base_params_gqh)
            error_rule = GGmaxCalibrationCost(model=model.model_type)
        case "1":
            pass
        case _:
            raise ValueError("El modelo proporcionado no existe")

    gamma_ref = general_params["gamma_ref"]
    G_max = general_params["G_max"]
    tau_max = general_params["tau_max"]
    gg_ref = model.calculate_gg_ref()
    GGmax_GQH = model.GGmax_model(gamma_ref)

    def objective(s, d, mu, a):

        GG_model = GGmax_HH_model(gg_ref, s, d, mu, a, G_max, gamma_ref, tau_max, model)

        if np.any(np.isnan(GG_model)) or np.any(GG_model <= 0):
            return -1e10

        error = error_rule.compute(GGmax_GQH, GG_model)

        return -error

    pbounds = {
        "s": (0.1, 2.5),
        "d": (0.1, 3),
        "mu": (1, 1e5),
        "a": (0.1, 4),
    }

    optimizer = BayesianOptimization(
        f=objective, pbounds=pbounds, random_state=42, verbose=0
    )
    optimizer.maximize(init_points=8, n_iter=100)

    best_params = optimizer.max["params"]
    beta = model._calcular_beta_ref(
        gg_ref,
        best_params["d"],
        best_params["a"],
        best_params["mu"],
        gamma_ref,
        tau_max,
        G_max,
    )

    best_params["beta"] = beta
    general_params["gg_ref"] = gg_ref

    return best_params