import numpy as np
import threading
import time
import os
import sys
import matplotlib.pyplot as plt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from scripts.exec_calibration_gqh import calculate_calibration
from modules.dynamic_curves.helper_calibration_gqh import GQHModelFormulation
from modules.dynamic_curves.helper_transformation_hh import GGmax_HH_model

from libs.config.config_variables import (
    STORAGE_DIR,
    STRAIN_RANGE,
)

CALIBRATION_DIR = STORAGE_DIR / "output" / "calibraciones_rule_4"
os.makedirs(CALIBRATION_DIR, exist_ok=True)


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

    ax.plot(STRAIN_RANGE, GGmax_GQH, label="GQH target", linewidth=2)
    ax.plot(STRAIN_RANGE, GG_fit, "r", label="HH fit", linewidth=2)

    ax.axhline(y=gg_ref, linestyle=":", linewidth=1.8)
    ax.axvline(x=gamma_ref, linestyle=":", linewidth=1.8)

    ax.set_xscale("log")
    ax.set_xlabel("Shear strain γ")
    ax.set_ylabel(r"$G/G_{max}$")

    ax.grid(alpha=0.3)
    ax.legend()

    gqh_params_text = "   ".join(
        f"{label} = {value:.3e}" for label, value in parametros_gqh.items()
    )

    best_params_text = "   ".join(
        f"{key} = {value:.3e}" for key, value in best_params.items()
    )

    fig.subplots_adjust(bottom=0.28)

    fig.text(0.5, 0.12, gqh_params_text, ha="center", fontsize=8)
    fig.text(0.5, 0.06, best_params_text, ha="center", fontsize=8)

    fig.savefig(CALIBRATION_DIR / f"Calibration_{set_number}_{n_sets}.png")

    plt.close(fig)


def run_set(
    set_number,
    gamma_ref_range,
    G_max_range,
    tau_max_range,
    parametros_gqh_ranges,
    n_sets,
):

    gamma_ref = np.random.uniform(*gamma_ref_range)
    G_max = np.random.uniform(*G_max_range)
    tau_max = np.random.uniform(*tau_max_range)

    parametros_gqh = {
        key: np.random.uniform(low, high)
        for key, (low, high) in parametros_gqh_ranges.items()
    }

    general_params = {
        "gamma_ref": gamma_ref,
        "G_max": G_max,
        "tau_max": tau_max,
    }

    modelo = "0"

    start_time = time.time()

    best_params = calculate_calibration(
        general_params,
        parametros_gqh,
        modelo,
    )
    
    elapsed = time.time() - start_time

    gg_ref = general_params["gg_ref"]
    print(
        f"(Set {set_number}) | gamma_ref={gamma_ref:.3e} | GGmax_ref={gg_ref:.3f} | G_max={G_max:.2e} | tau_max={tau_max:.2e}"
    )

    print(
        f"(Set {set_number}) | GQH: θ1={parametros_gqh['theta_1']:.2e} θ2={parametros_gqh['theta_2']:.2e} θ3={parametros_gqh['theta_3']:.2e} θ4={parametros_gqh['theta_4']:.2e} θ5={parametros_gqh['theta_5']:.2e}"
    )

    print(
        f"(Set {set_number}) | HH: s={best_params['s']:.2e} d={best_params['d']:.2e} mu={best_params['mu']:.2e} a={best_params['a']:.2e} beta={best_params['beta']:.2e}"
    )

    print(f"(Set {set_number}) | Tiempo: {elapsed:.2f} s")

    # Crear modelo para generar curvas
    model = GQHModelFormulation(parametros_gqh)

    GGmax_GQH = model.GGmax_model(gamma_ref)

    GG_fit = GGmax_HH_model(
        gg_ref,
        best_params["s"],
        best_params["d"],
        best_params["mu"],
        best_params["a"],
        G_max,
        gamma_ref,
        tau_max,
        model,
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


def main():

    n_sets = 1

    gamma_ref_range = (1e-3, 5e-3)
    G_max_range = (5e6, 1e7)
    tau_max_range = (1e5, 3e5)

    parametros_gqh_ranges = {
        "theta_1": (0.05, 0.2),
        "theta_2": (0.2, 0.5),
        "theta_3": (0.5, 2),
        "theta_4": (0.5, 2),
        "theta_5": (1, 3),
    }

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