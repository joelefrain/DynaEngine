import os
import sys

import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import threading
import time
from bayes_opt import BayesianOptimization
from dev.cost_function import (
#    cost_function_curvature, 
    cost_function_total
)
from libs.config.config_variables import (
    STORAGE_DIR,
    STRAIN_RANGE_PCT,
)

CALIBRATION_DIR = STORAGE_DIR / "output" / "calibraciones_rule_3"

# Modificar parametro a diccionario.

def GGmax_GQH_model(gamma_ref, parametro: list) -> list:

    x = STRAIN_RANGE_PCT / gamma_ref

    theta_r = parametro[0] + parametro[1] * (parametro[3] * x ** parametro[4]) / (
        parametro[2] ** parametro[4] + parametro[3] * x ** parametro[4]
    )

    theta_r = np.minimum(theta_r, 1.0)

    GG = 2 / (1 + x + np.sqrt((1 + x) ** 2 - 4 * theta_r * x))

    return GG

# Depende del modelo
def calcular_beta_ref(gg_ref, d, a, mu, gamma_ref, tau_max, G_max):
    omega = 1 - 1 / (1 + 10 ** (4.039 * a**-0.036))
    ref = gg_ref - (1 - omega) * mu * gamma_ref ** (d - 1) / (
        1 + (mu * G_max * gamma_ref**d) / tau_max
    )
    ref = np.clip(ref, 1e-12, None)
    return -1 + omega / ref


def calcular_tau_mkz(gamma_ref, beta, s, G_max):
    x = STRAIN_RANGE_PCT / gamma_ref
    x = np.clip(x, 1e-12, 1e12)

    mkz_den = 1 + beta * np.power(x, s)
    mkz_den = np.clip(mkz_den, 1e-12, 1e12)

    tau_mkz = (G_max * STRAIN_RANGE_PCT) / mkz_den

    return tau_mkz


def calcular_tau_fkz(mu, d, tau_max, G_max):
    gamma_d = np.power(STRAIN_RANGE_PCT, d)
    num = gamma_d * mu
    den = (1 / G_max) + (num / tau_max)
    den = np.clip(den, 1e-12, 1e12)

    tau_fkz = num / den

    return tau_fkz


def calcular_omega_hh(gamma_ref, a):
    log_ratio = np.log10(STRAIN_RANGE_PCT / gamma_ref)

    shift = 4.039 * np.power(a, -1.036)
    exp_term = -a * (log_ratio - shift)

    z = exp_term * np.log(10)

    z = np.clip(z, -500, 500)

    w = 1 / (1 + np.exp(-z))
    return w


def GGmax_HH_model(gg_ref, s, d, mu, a, G_max, gamma_ref, tau_max):

    a = max(a, 1e-6)

    beta = calcular_beta_ref(gg_ref, d, a, mu, gamma_ref, tau_max, G_max)

    tau_mkz = calcular_tau_mkz(gamma_ref, beta, s, G_max)
    tau_fkz = calcular_tau_fkz(mu, d, tau_max, G_max)

    w = calcular_omega_hh(gamma_ref, a)

    tau_hh = w * tau_mkz + (1 - w) * tau_fkz

    GG = tau_hh / (STRAIN_RANGE_PCT * G_max)
    GG = np.clip(GG, 1e-12, 2.0)

    return GG

#helper transformar hh (funciones independientes)

#swv_calbration_hh
def grafica_prueba(
    GGmax_GQH,
    GG_fit,
    gg_ref,
    set_number,
    n_sets,
    parametros_gqh,
    best_params,
    gamma_ref,
):

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.set_title(r"Bayesian Calibration of $G/G_\mathrm{max}$", fontsize=12)

    ax.plot(STRAIN_RANGE_PCT, GGmax_GQH, label="Datos", linewidth=2)
    ax.plot(STRAIN_RANGE_PCT, GG_fit, "r", label="Ajuste HH", linewidth=2)

    ax.axhline(y=gg_ref, color="r", linestyle=":", linewidth=1.8)
    ax.axvline(x=gamma_ref, color="r", linestyle=":", linewidth=1.8)

    ax.text(
        STRAIN_RANGE_PCT.max(),
        gg_ref,
        f"{gg_ref:.3f}",
        va="bottom",
        ha="right",
        fontsize=9,
    )

    ax.text(
        gamma_ref,
        ax.get_ylim()[0] + 0.03,
        f"{gamma_ref:.2e}",
        va="bottom",
        ha="right",
        rotation=90,
        fontsize=9,
    )

    ax.set_xscale("log")
    ax.set_xlabel("Shear strain, γ (%)")
    ax.set_ylabel(r"Normalized shear modulus, $G/G_\mathrm{max}$")

    ax.grid(alpha=0.3)
    ax.legend()

    theta_labels = [
        r"$\theta_1$",
        r"$\theta_2$",
        r"$\theta_3$",
        r"$\theta_4$",
        r"$\theta_5$",
    ]

    gqh_params_text = "   ".join(
        f"{label} = {value:.3e}" for label, value in zip(theta_labels, parametros_gqh)
    )

    best_params_text = "   ".join(
        f"{key} = {value:.3e}" for key, value in best_params.items()
    )

    fig.subplots_adjust(bottom=0.28)

    fig.text(0.5, 0.12, gqh_params_text, ha="center", fontsize=9)
    fig.text(0.5, 0.06, best_params_text, ha="center", fontsize=9)

    fig.savefig(CALIBRATION_DIR / f"Calibration - {set_number}_{n_sets}.png")

    plt.close(fig)

# Dic...
def calculate_gg_ref(parametros_gqh):
    x = parametros_gqh[0] + (parametros_gqh[1] * parametros_gqh[3]) / (
        parametros_gqh[2] ** parametros_gqh[4] + parametros_gqh[3]
    )
    gg_ref = 1 / (1 + np.sqrt(1 - x))
    return gg_ref


def calculate_calibration(
    gamma_ref, G_max, tau_max, parametros_gqh, set_number=1, n_sets=20
):

    # Cálculo de G / G máx de referencia
    gg_ref = calculate_gg_ref(parametros_gqh)
    GGmax_GQH = GGmax_GQH_model(gamma_ref, parametros_gqh)

    def objective(s, d, mu, a):

        GG_model = GGmax_HH_model(gg_ref, s, d, mu, a, G_max, gamma_ref, tau_max)

        if np.any(np.isnan(GG_model)) or np.any(GG_model <= 0):
            return -1e10

        error = cost_function_total(GGmax_GQH, GG_model)
#helpers transformation hh
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
    optimizer.maximize(init_points=8, n_iter=80)

    best_params = optimizer.max["params"]
    beta = calcular_beta_ref(
        gg_ref,
        best_params["d"],
        best_params["a"],
        best_params["mu"],
        gamma_ref,
        tau_max,
        G_max,
    )
    best_params["beta"] = beta

    GG_fit = GGmax_HH_model(
        gg_ref,
        best_params["s"],
        best_params["d"],
        best_params["mu"],
        best_params["a"],
        G_max,
        gamma_ref,
        tau_max,
    )
    grafica_prueba(
        GGmax_GQH,
        GG_fit,
        gg_ref,
        set_number,
        n_sets,
        parametros_gqh,
        best_params,
        gamma_ref,
    )
    return best_params, gg_ref

# Dev_transformation hh
def run_set(
    set_number,
    gamma_ref_range,
    G_max_range,
    tau_max_range,
    parametros_gqh_ranges,
    n_sets,
):
    # Generar valores aleatorios
    gamma_ref = np.random.uniform(*gamma_ref_range)
    G_max = np.random.uniform(*G_max_range)
    tau_max = np.random.uniform(*tau_max_range)
    parametros_gqh = [
        np.random.uniform(low, high) for (low, high) in parametros_gqh_ranges
    ]
    start_time = time.time()
    best_params, gg_ref = calculate_calibration(
        gamma_ref, G_max, tau_max, parametros_gqh, set_number=set_number, n_sets=n_sets
    )
    elapsed = time.time() - start_time

    # =========================================================================
    print(
        f"(Set {set_number}) | Parámetros generales: | gamma_ref={gamma_ref:.3e} | GGmax_ref={gg_ref} | G_max={G_max:.2e} | tau_max={tau_max:.2e}"
    )
    print(
        f"(Set {set_number}) | Parametros ingresados GQH: | θ_1={parametros_gqh[0]:.2e} | θ_2={parametros_gqh[1]:.2e} | θ_3={parametros_gqh[2]:.2e} | θ_4={parametros_gqh[3]:.2e} | θ_5={parametros_gqh[4]:.2e}"
    )
    print(
        f"(Set {set_number}) | Parámetros óptimos HH: | s = {best_params['s']:.2e} | d = {best_params['d']:.2e} | mu = {best_params['mu']:.2e} | a = {best_params['a']:.2e} | beta = {best_params['beta']:.2e}"
    )
    print(f"(Set {set_number}) | Duración de ejecución : {elapsed:.2f} segundos")
    # =========================================================================


def main():
    n_sets = 1  # Número de sets aleatorios
    gamma_ref_range = (1e-3, 5e-3)
    G_max_range = (5e6, 1e7)
    tau_max_range = (1e5, 3e5)
    parametros_gqh_ranges = [(0.05, 0.2), (0.2, 0.5), (0.5, 2), (0.5, 2), (1, 3)]

    threads = []
    for i in range(n_sets):
        t = threading.Thread(
            target=run_set,
            args=(
                i + 1,
                gamma_ref_range,
                G_max_range,
                tau_max_range,
                parametros_gqh_ranges,
                n_sets,
            ),
        )
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

if __name__ == "__main__":
    main()
