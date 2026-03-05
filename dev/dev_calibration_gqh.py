import os
import sys

import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
import matplotlib

matplotlib.use("Agg")
from bayes_opt import BayesianOptimization

from dev.class_cost_function import GGmaxCalibrationCost
from dev.helper_calibration_gqh import GQHModelFormulation
from dev.helper_transformation_hh import GGmax_HH_model


def calculate_calibration(
    general_params: dict, error_rule: object, model: object
) -> dict:

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


def main():
    general_params = {"gamma_ref": 1.0e-3, "G_max": 5.0e6, "tau_max": 1.0e5}

    base_params_gqh = {
        "theta_1": 0.05,
        "theta_2": 0.23,
        "theta_3": 0.62,
        "theta_4": 0.71,
        "theta_5": 1.00,
    }

    model = GQHModelFormulation(base_params_gqh)
    error_rule = GGmaxCalibrationCost(model=model.model_type)

    calibrate_params_hh = calculate_calibration(general_params, error_rule, model)

    # =========================================================================
    print(
        f"Parámetros generales: | gamma_ref={general_params['gamma_ref']:.3e} | GGmax_ref={general_params['gg_ref']} | G_max={general_params['G_max']:.2e} | tau_max={general_params['tau_max']:.2e}"
    )
    print(
        f"base_params ingresados GQH: | θ_1={base_params_gqh['theta_1']:.2e} | θ_2={base_params_gqh['theta_2']:.2e} | θ_3={base_params_gqh['theta_3']:.2e} | θ_4={base_params_gqh['theta_4']:.2e} | θ_5={base_params_gqh['theta_5']:.2e}"
    )
    print(
        f"Parámetros óptimos HH: | s = {calibrate_params_hh['s']:.2e} | d = {calibrate_params_hh['d']:.2e} | mu = {calibrate_params_hh['mu']:.2e} | a = {calibrate_params_hh['a']:.2e} | beta = {calibrate_params_hh['beta']:.2e}"
    )
    # =========================================================================


if __name__ == "__main__":
    main()
