import os
import pandas as pd
import numpy as np

from concurrent.futures import ProcessPoolExecutor
from libs.config.config_variables import (
    SHEAR_STRAIN,
    SHEAR_STRAIN_SEED,
    CONVERT_MS2_TO_G,
    KPA_TO_PA,
    K0_DEFAULD,
    PHI_CONSTANT,
    MPA_TO_PA,
)

import matplotlib.pyplot as plt
from pathlib import Path

from modules.calibration_curves.class_model_calibration import execute_calibration
from modules.make_columns.class_shear_velocity import compute_layer_vs
from modules.calibration_curves.class_masing_rules import MasingRules
from modules.dynamic_curves.class_theoretical_curves import (
    SeedIdrissModel_1970,
    UserDefined,
)


class Columns:
    """
    Crea columnas.
    """

    def __init__(
        self, layers: object, material_name: list, thickness: list, freatic: float = 0
    ) -> None:
        self.layers = layers
        self.material_name = material_name
        self.thickness = thickness
        self.freatic = freatic

        self.processor = SoilProcessing(layers)
        self.post = Postprocessing(layers)

    def run(self, fig_directory, f_target=25):

        gamma = self.processor.compute_unit_weight(self.material_name)
        vs = self.processor.compute_vs_profile(self.material_name, self.thickness)
        sigma_ve = SoilProcessing.compute_sigma_eff(self.freatic, self.thickness, gamma)

        column = pd.DataFrame(
            {
                "material_name": self.material_name,
                "thickness": self.thickness,
                "unit_weight_kn_m3": gamma,
                "shear_velocity": vs,
                "sigma_v_center_kPa": sigma_ve,
            }
        )

        column_disc = self.processor.discretize(column, f_target)
        column_disc = self.post.add_sigma_v(column_disc)
        column_disc = self.post.add_k0(column_disc)
        column_disc = self.post.add_gmax(column_disc)
        column_disc = self.post.add_tau(column_disc)
        column_disc = self.post.add_model(column_disc)

        column_calibrate = run_parallel(column_disc, fig_directory)

        return column_calibrate


class SoilProcessing:
    """
    Calcula las propiedades geotécnicas de los layers y columnas.
    """

    def __init__(self, layers: object) -> None:
        self.layers = layers

    def compute_unit_weight(self, material_name: list):
        return [self.layers.map[name]["gamma"] for name in material_name]

    def compute_vs_profile(self, material_name: list, thickness: list):
        z_top = 0
        vs_list = []

        for i, h in enumerate(thickness):
            z_bottom = z_top + h

            mat = self.layers.map[material_name[i]]
            vs_model = mat["vs"]

            vs = compute_layer_vs(
                vs_model.depth, vs_model.shear_velocity, z_top, z_bottom
            )

            vs_list.append(vs)
            z_top = z_bottom

        return vs_list

    @staticmethod
    def compute_sigma_eff(freatic: float, thickness: list, unit_weight: list):
        sigma_v = []
        acumulado = 0.0

        for gamma, h in zip(unit_weight, thickness):
            sigma_centro = acumulado + gamma * (h / 2)
            if h > freatic:
                u = 9.81 * (h - freatic)
                sigma_centro = sigma_centro - u
            else:
                pass
            sigma_v.append(sigma_centro)
            acumulado += gamma * h

        return sigma_v

    def discretize(self, column: pd.DataFrame, f_target: float):
        rows = []
        z_global = 0

        for row in column.itertuples():
            thickness = row.thickness
            material = row.material_name
            gamma = row.unit_weight_kn_m3

            mat = self.layers.map[material]
            vs_model = mat["vs"]

            k = 1

            while True:
                sub_h = thickness / k

                vs_test = compute_layer_vs(
                    vs_model.depth, vs_model.shear_velocity, z_global, z_global + sub_h
                )

                if vs_test / (4 * sub_h) >= f_target:
                    break

                k += 1

            for j in range(k):
                z_top = z_global + j * sub_h
                z_bottom = z_top + sub_h

                vs_sub = compute_layer_vs(
                    vs_model.depth, vs_model.shear_velocity, z_top, z_bottom
                )

                rows.append(
                    {
                        "material_name": material,
                        "thickness": sub_h,
                        "unit_weight_kn_m3": gamma,
                        "shear_velocity": vs_sub,
                        "frec": vs_sub / (4 * sub_h),
                    }
                )

            z_global += thickness

        column_disc = pd.DataFrame(rows)
        column_disc["depth"] = column_disc["thickness"].cumsum()

        return column_disc


class Postprocessing:
    """
    Postprocessing
    """

    def __init__(self, layers: object) -> None:
        self.layers = layers

    def add_sigma_v(self, column: pd.DataFrame):
        sigma_v = []
        acumulado = 0

        for row in column.itertuples():
            gamma = self.layers.map[row.material_name]["gamma"]
            h = row.thickness

            sigma_centro = acumulado + gamma * (h / 2)
            sigma_v.append(sigma_centro)

            acumulado += gamma * h

        column["sigma_v_center_kPa"] = sigma_v
        return column

    def add_k0(self, column: pd.DataFrame):
        column["k0"] = column.apply(
            lambda row: getattr(
                self.layers.map[row["material_name"]]["model"].soil, "k0", K0_DEFAULD
            ),
            axis=1,
        )
        return column

    @staticmethod
    def add_gmax(column: pd.DataFrame):
        column["gmax_kpa"] = (
            column["unit_weight_kn_m3"] * column["shear_velocity"] ** 2
        ) / CONVERT_MS2_TO_G
        return column

    def add_tau(self, column: pd.DataFrame):
        def compute_tau(row):
            props = self.layers.map[row["material_name"]]["shear_properties"]
            c = props["c"]
            phi = props["phi"]

            phi_min, phi_max = (
                PHI_CONSTANT["min_val"] * phi,
                PHI_CONSTANT["max_val"] * phi,
            )
            sigma_m = 0.5 * (1 + row["k0"]) * row["sigma_v_center_kPa"]
            esf_min = c + sigma_m * np.tan(np.deg2rad(phi_min))
            esf_max = c + sigma_m * np.tan(np.deg2rad(phi_max))
            return 0.5 * (esf_min + esf_max)

        column["tau_kpa"] = column.apply(compute_tau, axis=1)
        return column

    def add_model(self, column: pd.DataFrame):
        def build(row):
            mat = self.layers.map[row["material_name"]]
            base = mat["model"]

            if isinstance(base, UserDefined):
                return UserDefined(base.soil, base.curve_data, base.G_max / MPA_TO_PA)

            return type(base)(base.soil, row["sigma_v_center_kPa"])

        column["model"] = column.apply(build, axis=1)
        return column


def calibration_model(idx, row, fig_directory):
    if isinstance(row["model"], SeedIdrissModel_1970):
        strain = SHEAR_STRAIN_SEED
    else:
        strain = SHEAR_STRAIN

    dynamic_data = {
        "strain": strain,
        "ggmax": row["model"].gg_max(),
        "damp": row["model"].damping(),
    }

    Gmax = row["gmax_kpa"] * KPA_TO_PA
    tau_max = row["tau_kpa"] * KPA_TO_PA

    result = execute_calibration(dynamic_data, Gmax, tau_max)

    GG_exp = result["GG_exp"]
    GG_model = result["GG_model"]
    D_exp = result["D_exp"]
    D_model = result["D_model"]

    mas_exp = MasingRules(strain, GG_exp)
    Dmas_exp = mas_exp.damping_masing_clean()
    mas_model = MasingRules(strain, GG_model)
    Dmas_model = mas_model.damping_masing_clean()

    save_results(
        idx,
        strain,
        GG_exp,
        GG_model,
        Dmas_exp,
        Dmas_model,
        D_exp,
        D_model,
        fig_directory,
    )

    return {
        "theta": result["theta"],
        "p": result["p"],
        "dmin": result["dmin"],
    }


def save_results(
    idx,
    strain,
    GG_exp,
    GG_model,
    Dmas_exp,
    Dmas_model,
    D_exp,
    D_model,
    fig_directory,
):

    base_dir = Path(fig_directory)

    # Carpetas separadas
    figures_dir = base_dir / "calibration_figures"
    data_dir = base_dir / "calibration_data"

    figures_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    # Rutas de salida
    fig_path = figures_dir / f"calibration_{idx}.png"
    excel_path = data_dir / f"calibration_{idx}.xlsx"

    make_double_figure(
        fig_path,
        excel_path,
        strain,
        GG_exp,
        GG_model,
        Dmas_exp,
        Dmas_model,
        D_exp,
        D_model,
    )


def run_parallel(column: dict, fig_directory: str) -> dict:
    column = column.reset_index()
    rows = column.to_dict("records")

    with ProcessPoolExecutor(max_workers=os.cpu_count() // 2) as executor:
        futures = [
            executor.submit(calibration_model, i, row, fig_directory)
            for i, row in enumerate(rows, start=1)
        ]
        results = [future.result() for future in futures]

    column["theta_1"] = [r["theta"]["theta_1"] for r in results]
    column["theta_2"] = [r["theta"]["theta_2"] for r in results]
    column["theta_3"] = [r["theta"]["theta_3"] for r in results]
    column["theta_4"] = 1
    column["theta_5"] = [r["theta"]["theta_5"] for r in results]

    column["P1"] = [r["p"]["P1"] for r in results]
    column["P2"] = [r["p"]["P2"] for r in results]
    column["P3"] = [r["p"]["P3"] for r in results]

    column["dmin"] = [r["dmin"] for r in results]

    return column


def make_double_figure(
    fig_path,
    excel_path,
    strain,
    GG_exp,
    GG_model,
    Dmas_exp,
    Dmas_model,
    D_exp,
    D_model,
):

    fig, axes = plt.subplots(1, 3, figsize=(12, 8))

    ax1, ax2, ax3 = axes

    ax1.semilogx(strain, GG_exp)
    ax1.semilogx(strain, GG_model)
    ax1.set_title("G/Gmax")

    ax2.semilogx(strain[1:], Dmas_exp)
    ax2.semilogx(strain[1:], Dmas_model)
    ax2.set_title("Damping Masing")

    ax3.semilogx(strain, D_exp)
    ax3.semilogx(strain, D_model)
    ax3.set_title("Damping")

    fig.tight_layout()

    # Guardar figura
    fig.savefig(fig_path, dpi=120)
    plt.close(fig)

    # Guardar data
    save_curves_to_excel(
        excel_path,
        strain,
        GG_exp,
        GG_model,
        Dmas_exp,
        Dmas_model,
        D_exp,
        D_model,
    )


def save_curves_to_excel(
    excel_path,
    strain,
    GG_exp,
    GG_model,
    Dmas_exp,
    Dmas_model,
    D_exp,
    D_model,
):

    df_gg = pd.DataFrame(
        {
            "strain": strain,
            "GG_exp": GG_exp,
            "GG_model": GG_model,
        }
    )

    df_dmas = pd.DataFrame(
        {
            "strain": strain[1:],
            "Dmas_exp": Dmas_exp,
            "Dmas_model": Dmas_model,
        }
    )

    df_d = pd.DataFrame(
        {
            "strain": strain,
            "D_exp": D_exp,
            "D_model": D_model,
        }
    )

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        df_gg.to_excel(writer, sheet_name="GGmax", index=False)
        df_dmas.to_excel(writer, sheet_name="Damping_Masing", index=False)
        df_d.to_excel(writer, sheet_name="Damping", index=False)
