import numpy as np
import os
import sys
import pandas as pd
import matplotlib.pyplot as plt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from scripts.exec_calibration_gqh import calculate_calibration
from modules.dynamic_curves.helper_calibration_gqh import GQHModelFormulation
from modules.dynamic_curves.helper_transformation_hh import GGmax_HH_model

from libs.config.config_variables import STORAGE_DIR, STRAIN_RANGE


CALIBRATION_DIR = STORAGE_DIR / "output" / "calibraciones_columna_05"
os.makedirs(CALIBRATION_DIR, exist_ok=True)

INPUT_FILE = STORAGE_DIR / "raw_data" /"input_parameters.xlsx"


def grafica_prueba(
    GGmax_GQH,
    GG_fit,
    gg_ref,
    parametros_gqh,
    best_params,
    gamma_ref,
    set_number
):

    fig, ax = plt.subplots(figsize=(7, 5))

    ax.set_title(rf"Calibration Set {set_number}")

    ax.plot(STRAIN_RANGE, GGmax_GQH, label="GQH target", linewidth=2)
    ax.plot(STRAIN_RANGE, GG_fit, "r", label="HH fit", linewidth=2)

    ax.axhline(y=gg_ref, linestyle=":", linewidth=1.8)
    ax.axvline(x=gamma_ref, linestyle=":", linewidth=1.8)

    ax.set_xscale("log")
    ax.set_xlabel("Shear strain γ")
    ax.set_ylabel(r"$G/G_{max}$")

    ax.grid(alpha=0.3)
    ax.legend()

    fig.savefig(CALIBRATION_DIR / f"Calibration_{set_number:02d}.png")
    plt.close()


def run_set(set_number, params):

    G_max = params["Gmax"]
    tau_max = params["Tmax"]

    parametros_gqh = {
        "theta_1": params["theta_1"],
        "theta_2": params["theta_2"],
        "theta_3": params["theta_3"],
        "theta_4": params["theta_4"],
        "theta_5": params["theta_5"],
    }

    general_params = {
        "G_max": G_max,
        "tau_max": tau_max,
    }

    modelo = "0"

    best_params = calculate_calibration(
        general_params,
        parametros_gqh,
        modelo,
    )

    gg_ref = general_params["gg_ref"]
    gamma_ref = general_params["gamma_ref"]

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
        parametros_gqh,
        best_params,
        gamma_ref,
        set_number,
    )

    result = {
        "set": set_number,
        "Gmax": G_max,
        "Tmax": tau_max,
        "gamma_ref": gamma_ref,
        "GGmax_ref": gg_ref,
        **parametros_gqh,
        **best_params,
    }

    return result


def main():

    df = pd.read_excel(INPUT_FILE, index_col=0)

    results = []

    for i, column in enumerate(df.columns):

        params = df[column].to_dict()

        print(f"Running set {i+1}")

        result = run_set(i + 1, params)

        results.append(result)

    results_df = pd.DataFrame(results)

    output_excel = CALIBRATION_DIR / "calibration_results.xlsx"
    results_df.to_excel(output_excel, index=False)

    print("Resultados guardados en:", output_excel)


if __name__ == "__main__":
    main()