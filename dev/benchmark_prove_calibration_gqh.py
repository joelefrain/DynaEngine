import numpy as np
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

CALIBRATION_DIR = STORAGE_DIR / "output" / "calibraciones_rule_6"
os.makedirs(CALIBRATION_DIR, exist_ok=True)


def grafica_prueba(
    GGmax_GQH,
    GG_fit,
    gg_ref,
    parametros_gqh,
    best_params,
    gamma_ref,
):

    fig, ax = plt.subplots(figsize=(7, 5))

    ax.set_title(r"Bayesian Calibration of $G/G_\mathrm{max}$")

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

    fig.savefig(CALIBRATION_DIR / "Calibration.png")


def main():

    # ---------------------------
    # PARÁMETROS DEFINIDOS POR TI
    # ---------------------------

    G_max = 8.41e8
    tau_max = 6.70e5

    parametros_gqh = {
        "theta_1": -0.18,
        "theta_2": 0.96,
        "theta_3": 0.70794578,
        "theta_4": 1.0,
        "theta_5": 0.5,
    }

    general_params = {
        "G_max": G_max,
        "tau_max": tau_max,
    }

    modelo = "0"

    # ---------------------------
    # CALIBRACIÓN
    # ---------------------------

    best_params = calculate_calibration(
        general_params,
        parametros_gqh,
        modelo,
    )

    gg_ref = general_params["gg_ref"]
    gamma_ref = general_params["gamma_ref"]

    # ---------------------------
    # MODELO GQH
    # ---------------------------

    model = GQHModelFormulation(parametros_gqh)

    GGmax_GQH = model.GGmax_model(gamma_ref)

    # ---------------------------
    # MODELO HH
    # ---------------------------

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

    # ---------------------------
    # GRAFICAR
    # ---------------------------

    grafica_prueba(
        GGmax_GQH,
        GG_fit,
        gg_ref,
        parametros_gqh,
        best_params,
        gamma_ref,
    )


if __name__ == "__main__":
    main()