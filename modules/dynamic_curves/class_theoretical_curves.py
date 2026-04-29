import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from abc import ABC, abstractmethod
from matplotlib.ticker import FuncFormatter
from modules.dynamic_curves.class_soil_parameters import (
    DarendeliParameters_2001,
    MenqParameters_2003,
    RollinsParameters_2020,
    IshibashiParameters_1993,
    WangStokoeParameters_2021,
    RojasParameters_2019,
    SeedIdrissParameters_1970,
    UserDefinedParameters,
)

from libs.config.config_variables import (
    SHEAR_STRAIN,
    SHEAR_STRAIN_SEED,
    MASING_COEFFS,
    DAR_PARAMS,
    ATM_CONVERT,
    MPA_TO_PA,
    KPA_TO_PA,
    PERCENT_TO_NUMBER,
    DATA_DIR,
)

from libs.config.config_logger import get_logger

logger = get_logger()

theoretical_curves_path = DATA_DIR / "theoretical_curves" / "curves.json"


def load_discrete_curves(path):
    with open(path) as f:
        return json.load(f)


raw_discrete_curves = load_discrete_curves(theoretical_curves_path)

discrete_curves = {
    "gamma": np.array(raw_discrete_curves["gamma"]),
    "rojas": {
        "G_Gmax": {
            float(k): np.array(v)
            for k, v in raw_discrete_curves["rojas"]["G_Gmax"].items()
        },
        "D": {
            float(k): np.array(v) for k, v in raw_discrete_curves["rojas"]["D"].items()
        },
    },
    "seed": {
        "G_Gmax": {
            k: np.array(v) for k, v in raw_discrete_curves["seed"]["G_Gmax"].items()
        },
        "D": {k: np.array(v) for k, v in raw_discrete_curves["seed"]["D"].items()},
    },
}


class DynamicCurveModel(ABC):
    def __str__(self):
        params = ", ".join(
            f"{k}={v:.3g}" if isinstance(v, float) else f"{k}={v}"
            for k, v in vars(self).items()
        )
        return f"{self.__class__.__name__}({params})"

    def curves(self):
        return {
            "gamma": SHEAR_STRAIN,
            "ggmax": self.gg_max(),
            "damping": self.damping(),
            "tau": self.shear_strength(),
        }

    def export_to_excel(self, filename="dynamic_curves"):
        curves = self.curves()
        filename = filename + ".xlsx"
        df = pd.DataFrame(
            {
                "gamma (strain)": curves["gamma"],
                "G/Gmax": curves["ggmax"],
                "damping (%)": curves["damping"],
                "tau (kPa)": curves["tau"],
            }
        )

        df.to_excel(filename, index=False)

        logger.info(f"Archivo exportado correctamente: {filename}")

    def plot(self):
        curves = self.curves()

        gamma = curves["gamma"]
        ggmax = curves["ggmax"]
        damping = curves["damping"]
        tau = curves["tau"]

        fig, ax = plt.subplots(1, 3, figsize=(12, 4))

        ax[0].semilogx(gamma, ggmax)
        ax[0].set_xlabel("Shear strain γ")
        ax[0].set_ylabel("Normalized shear modulus, G/Gmax")
        ax[0].set_title("Modulus reduction")

        ax[1].semilogx(gamma, damping)
        ax[1].set_xlabel("Shear strain γ")
        ax[1].set_ylabel("Damping, D (%)")
        ax[1].set_title("Damping curve")

        ax[2].semilogx(gamma, tau)
        ax[2].set_xlabel("Shear strain, γ")
        ax[2].set_ylabel("Shear stress, τ (kPa)")
        ax[2].set_title("Stress-strain")

        plt.tight_layout()
        plt.show()

    @staticmethod
    def _transform_sigma(k0, se):
        sigma_m = 0.5 * (1 + k0) * se
        return sigma_m / ATM_CONVERT

    @staticmethod
    def _interp_log(values):
        gamma = discrete_curves["gamma"]

        log_gamma = np.log10(gamma)
        log_strain = np.log10(SHEAR_STRAIN)

        return np.interp(log_strain, log_gamma, values)

    @staticmethod
    def _interp_log_seed(values):
        gamma = discrete_curves["gamma"]

        log_gamma = np.log10(gamma)
        log_strain = np.log10(SHEAR_STRAIN_SEED)

        return np.interp(log_strain, log_gamma, values)

    @abstractmethod
    def shear_strength(self):
        pass

    @abstractmethod
    def gg_max(self):
        pass

    @abstractmethod
    def damping(self):
        pass


class DarendeliModel_2001(DynamicCurveModel):
    def __init__(
        self,
        soil_parameters: DarendeliParameters_2001,
        sigma_ve: float,
        G_max: float = 10,
        p_parameter: float = 0.1,
    ) -> None:

        self.soil = soil_parameters
        self.p = p_parameter

        self.G_max = G_max * MPA_TO_PA
        self.se = sigma_ve

        self.gamma_ref, self.a, self.b, self.d_min = self._transform_parameters(
            soil_parameters
        )

    def _transform_parameters(self, soil: DarendeliParameters_2001):

        phi = DAR_PARAMS

        sigma_m = self._transform_sigma(soil.k0, self.se)

        gamma_ref = (
            (phi["phi1"] + phi["phi2"] * soil.IP * soil.OCR ** phi["phi3"])
            * sigma_m ** phi["phi4"]
            / PERCENT_TO_NUMBER
        )

        a = phi["phi5"]

        d_min = (
            (phi["phi6"] + phi["phi7"] * soil.IP * soil.OCR ** phi["phi8"])
            * sigma_m ** phi["phi9"]
            * (1 + phi["phi10"] * np.log(soil.frequency))
        )

        b = phi["phi11"] + phi["phi12"] * np.log(soil.N)

        return gamma_ref, a, b, d_min

    def shear_strength(self):
        tau = self.G_max * SHEAR_STRAIN * self.gg_max()
        return tau / KPA_TO_PA

    def gg_max(self):
        gamma_ratio = SHEAR_STRAIN / self.gamma_ref
        ggmax = 1 / (1 + gamma_ratio**self.a)
        ggmax = np.minimum(ggmax, 1)
        return ggmax

    def damping_masing(self):
        upper = SHEAR_STRAIN - self.gamma_ref * np.log(
            (SHEAR_STRAIN + self.gamma_ref) / self.gamma_ref
        )
        bottom = SHEAR_STRAIN**2 / (SHEAR_STRAIN + self.gamma_ref)

        damping_mass = (100 / np.pi) * (4 * upper / bottom - 2)

        c1 = np.polyval(MASING_COEFFS["c1"], self.a)
        c2 = np.polyval(MASING_COEFFS["c2"], self.a)
        c3 = np.polyval(MASING_COEFFS["c3"], self.a)

        damping_massing = (
            c1 * damping_mass + c2 * damping_mass**2 + c3 * damping_mass**3
        )

        return damping_massing

    def damping(self):
        gg_max = self.gg_max()
        damping_massing = self.damping_masing()
        damping = self.b * (gg_max**self.p) * damping_massing + self.d_min

        return damping


class MenqModel_2003(DynamicCurveModel):
    def __init__(
        self,
        soil_parameters: MenqParameters_2003,
        sigma_ve: float,
        G_max: float = 10,
        p_parameter: float = 0.1,
    ) -> None:

        self.soil = soil_parameters

        self.G_max = G_max * MPA_TO_PA
        self.p = p_parameter
        self.se = sigma_ve
        self.gamma_ref, self.a, self.b, self.d_min = self._transform_parameters(
            soil_parameters
        )

    def _transform_parameters(self, soil: MenqParameters_2003):

        sigma_m = self._transform_sigma(soil.k0, self.se)

        sigma_norm = sigma_m

        gamma_ref = (
            0.12
            * soil.Cu**-0.6
            * sigma_norm ** (0.5 * soil.Cu**-0.15)
            / PERCENT_TO_NUMBER
        )
        a = 0.86 + 0.1 * np.log10(sigma_norm)
        d_min = 0.55 * soil.Cu**0.1 * soil.D50**-0.3 * sigma_norm**-0.08
        b = 0.6329 - 0.0057 * np.log(soil.N)

        return gamma_ref, a, b, d_min

    def shear_strength(self):
        tau = self.G_max * SHEAR_STRAIN * self.gg_max()
        return tau / KPA_TO_PA

    def gg_max(self):
        gamma_ratio = SHEAR_STRAIN / self.gamma_ref
        ggmax = 1 / (1 + gamma_ratio**self.a)
        ggmax = np.minimum(ggmax, 1)
        return ggmax

    def damping_masing(self):
        upper = SHEAR_STRAIN - self.gamma_ref * np.log(
            (SHEAR_STRAIN + self.gamma_ref) / self.gamma_ref
        )
        bottom = SHEAR_STRAIN**2 / (SHEAR_STRAIN + self.gamma_ref)

        damping_mass = (100 / np.pi) * (4 * upper / bottom - 2)

        c1 = np.polyval(MASING_COEFFS["c1"], self.a)
        c2 = np.polyval(MASING_COEFFS["c2"], self.a)
        c3 = np.polyval(MASING_COEFFS["c3"], self.a)

        return c1 * damping_mass + c2 * damping_mass**2 + c3 * damping_mass**3

    def damping(self):
        gg_max = self.gg_max()
        damping_massing = self.damping_masing()
        return self.b * (gg_max**self.p) * damping_massing + self.d_min


class RollinsModel_2020(DynamicCurveModel):
    def __init__(
        self,
        soil_parameters: RollinsParameters_2020,
        sigma_ve: float,
        G_max: float = 10,
    ) -> None:

        self.soil = soil_parameters
        self.Cu = soil_parameters.Cu
        self.se = sigma_ve
        self.G_max = G_max * MPA_TO_PA

    def gg_max(self):

        sigma_m = self._transform_sigma(self.soil.k0, self.se) * ATM_CONVERT

        gamma_percent = SHEAR_STRAIN * 100

        temp = 0.0046 * self.Cu ** (-0.197) * sigma_m**0.52  # / PERCENT_TO_NUMBER
        gg_max = 1 / (1 + (gamma_percent / temp) ** 0.84)
        gg_max = np.minimum(gg_max, 1)

        return gg_max

    def damping(self):

        sigma_m = self._transform_sigma(self.soil.k0, self.se) * ATM_CONVERT

        gamma_percent = SHEAR_STRAIN  # * 100

        gamma_norm = 100 * gamma_percent / (1 + 100 * gamma_percent)
        damping = 26.05 * gamma_norm**0.375 * self.Cu**0.08 * sigma_m ** (-0.07)

        return damping

    def shear_strength(self):

        tau = self.gg_max() * self.G_max * SHEAR_STRAIN

        return tau / KPA_TO_PA


class IshibashiModel_1993(DynamicCurveModel):
    def __init__(
        self,
        soil_parameters: IshibashiParameters_1993,
        sigma_ve: float,
        G_max: float = 10,
    ) -> None:

        self.soil = soil_parameters
        self.IP = soil_parameters.IP

        self.G_max = G_max * MPA_TO_PA
        self.se = sigma_ve

    def _compute_nip(self):
        if self.IP < 0:
            return 0
        elif self.IP <= 15:
            return 3.37 * 10 ** (-6) * self.IP**1.404
        elif self.IP <= 70:
            return 7.0 * 10 ** (-7) * self.IP**1.976
        elif self.IP > 70:
            return 2.7 * 10 ** (-5) * self.IP**1.115
        else:
            raise ValueError("IP fuera del rango")

    def _compute_k(self):
        strain_ratio = (0.000102 + self._compute_nip()) / SHEAR_STRAIN

        if np.any(strain_ratio <= 0):
            raise ValueError("Se ha generado un logaritmo de un número negativo.")

        log_term = 0.492 * np.log(strain_ratio)
        return 0.5 * (1 + np.tanh(log_term))

    def _compute_exp(self):
        return -0.0145 * self.IP**1.3

    def _compute_m_mo(self):
        strain_ratio = 0.000556 / SHEAR_STRAIN

        if np.any(strain_ratio <= 0):
            raise ValueError("Se ha generado un logaritmo de un número negativo.")

        log_term = 0.4 * np.log(strain_ratio)
        return 0.272 * (1 - np.tanh(log_term)) * np.exp(self._compute_exp())

    def gg_max(self):
        gg_max = self._compute_k() * self.se ** self._compute_m_mo()
        value = np.max(gg_max)
        gg_max = gg_max / value
        return gg_max

    def shear_strength(self):
        tau = self.gg_max() * self.G_max * SHEAR_STRAIN
        return tau / KPA_TO_PA

    def damping(self):
        ggmax = self.gg_max()
        coeff = 0.5 * (1 + np.exp(self._compute_exp()))
        damping = 0.333 * coeff * (0.586 * ggmax**2 - 1.547 * ggmax + 1)
        return 100 * damping


class WangStokoeModel_2021(DynamicCurveModel):
    def __init__(
        self,
        soil_parameters: WangStokoeParameters_2021,
        sigma_ve: float,
        G_max: float = 10,
    ) -> None:

        self.soil = soil_parameters

        self.G_max = G_max * MPA_TO_PA
        self.se = sigma_ve

    def _gg_max_parameters(self):

        param = self.soil

        sigma_nor = self.se / ATM_CONVERT  # Mpdificar

        match param.soil_group:
            case "Clean sand and gravel group":
                b = 0.844 - 1.897 * param.CF
                a = param.CF + 0.834

                coeff = 0.048 * np.exp(0.089 * param.Cu) + 0.008
                gamma_mr = coeff * sigma_nor**0.4

            case "Nonplastic silty sand group":
                b = 0.486 - 0.006 * sigma_nor
                a = (1.495 * param.e + 3.079 * param.CF) ** 0.121

                coeff = 0.031 * param.e - 0.003
                exponent = 0.405 - 0.193 * param.CF
                gamma_mr = coeff * sigma_nor**exponent

            case "Clayey soil group":
                b = 0.586 - 0.098 * param.e - 0.135 * param.CF
                a = 0.896 + 0.412 * param.CF + 0.534 * param.IP

                coeff = 0.02 * param.e + 0.004 * param.CF
                exponent = 0.447 - 0.27 * param.IP
                base_term = sigma_nor + 0.42 * param.OCR
                gamma_mr = coeff * base_term**exponent

            case _:
                raise ValueError("El grupo ingresado no existe")

        return a, b, gamma_mr

    def _dmin_parameters(self):

        param = self.soil

        sigma_nor = self.se / ATM_CONVERT

        match param.soil_group:
            case "Clean sand and gravel group":
                Cd = 0.6
                F_sigma = sigma_nor ** (-0.14)
                delta = 0

                coeff = 1 + 21.17 * param.CF
                exponent = 7.45 - 15.23 * param.e + 4.29 * param.D50
                base_term = 0.99 + param.wc
                Fd = coeff * base_term**exponent

            case "Nonplastic silty sand group":
                Cd = 52.16
                F_sigma = sigma_nor ** (-0.19)
                delta = 0

                coeff = 1 + 5.35 * param.CF
                exponent = 0.81 * param.CF + 5.2 * param.e
                base_term = 0.41 * param.e
                Fd = coeff * base_term**exponent

            case "Clayey soil group":
                Cd = 4.86
                F_sigma = sigma_nor ** (-0.19)
                delta = (0.46 * param.IP) ** (1.73 - 1.34 * param.e)

                coeff = 1 + 106.75 * param.IP**1.64
                exponent = -1.91 * param.e - 6.5 * param.CF
                base_term = 1.99 + param.CF
                Fd = coeff * base_term**exponent

        return Cd, Fd, F_sigma, delta

    def damping_parameters(self):

        param = self.soil

        sigma_nor = self.se / ATM_CONVERT

        match param.soil_group:
            case "Clean sand and gravel group":
                d = 18.13
                c = 0.93 * param.e ** (0.34 - 0.8 * param.e)

                coeff = 0.13 * param.Cu ** (-0.31)
                exponent = 0.47 - param.CF
                base_term = sigma_nor + 22.04 * param.CF
                gamma_d = coeff * base_term**exponent

            case "Nonplastic silty sand group":
                d = 12.13
                c = 1.39 * param.e**0.27

                coeff = 0.0025
                exponent = 1.47 - 0.52 * param.CF
                base_term = sigma_nor + 5.73 * param.e + 9.17 * param.CF
                gamma_d = coeff * base_term**exponent

            case "Clayey soil group":
                d = 21.7
                c = (1.91 * param.CF) ** (1.62 * param.IP)

                coeff = 0.11
                exponent = 1.45 - param.IP + param.wc - 1.09 * param.CF
                base_term = 0.12 * sigma_nor + 5.29 * param.wc - param.CF
                gamma_d = coeff * base_term**exponent

        return d, c, gamma_d

    def gg_max(self):
        a, b, gamma_mr = self._gg_max_parameters()
        gamma_mr = gamma_mr / PERCENT_TO_NUMBER
        gg_max = 1 / (1 + (SHEAR_STRAIN / gamma_mr) ** a) ** b
        gg_max = np.minimum(gg_max, 1)
        return gg_max

    def _compute_dmin(self):
        Cd, Fd, F_sigma, delta = self._dmin_parameters()
        return Cd * Fd * F_sigma + delta

    def damping(self):
        dmin = self._compute_dmin()
        d, c, gamma_d = self.damping_parameters()
        gamma_d = gamma_d / PERCENT_TO_NUMBER

        upper_term = d * (SHEAR_STRAIN / gamma_d) ** c + dmin
        bottom_term = (SHEAR_STRAIN / gamma_d) ** c + 1
        damping = upper_term / bottom_term

        return damping

    def shear_strength(self):
        tau = self.G_max * self.gg_max() * SHEAR_STRAIN
        return tau / KPA_TO_PA


class RojasModel_2019(DynamicCurveModel):
    def __init__(
        self, soil_parameters: RojasParameters_2019, sigma_ve: float, G_max: float = 10
    ) -> None:

        self.soil = soil_parameters

        self.G_max = G_max * MPA_TO_PA
        self.se = sigma_ve

        self.sm = self._transform_sigma(self.soil.k0, self.se) * ATM_CONVERT
        self._sigma_ref = self._select_confinement()

    def _select_confinement(self):
        available = np.array([k for k in discrete_curves["rojas"]["G_Gmax"].keys()])

        if self.sm < available.min():
            raise ValueError("Confinamiento fuera del rango")

        return max(available[available <= self.sm])

    def gg_max(self):
        values = discrete_curves["rojas"]["G_Gmax"][self._sigma_ref]
        return self._interp_log(values)

    def damping(self):
        values = discrete_curves["rojas"]["D"][self._sigma_ref]
        return self._interp_log(values)

    def shear_strength(self):
        tau = self.gg_max() * self.G_max * SHEAR_STRAIN
        return tau / KPA_TO_PA


class SeedIdrissModel_1970(DynamicCurveModel):
    def __init__(self, soil_parameters: SeedIdrissParameters_1970, G_max: float = 10):

        self.soil = soil_parameters

        self.G_max = G_max * MPA_TO_PA

    def gg_max(self):
        band = self.soil.band
        values = discrete_curves["seed"]["G_Gmax"][band]
        return self._interp_log_seed(values)

    def damping(self):
        band = self.soil.band
        values = discrete_curves["seed"]["D"][band]
        return self._interp_log_seed(values)

    def shear_strength(self):
        tau = self.gg_max() * self.G_max * SHEAR_STRAIN_SEED
        return tau / KPA_TO_PA


class UserDefined(DynamicCurveModel):
    def __init__(
        self,
        soil_parameters: UserDefinedParameters,
        curve_data: dict,
        sigma_vertical: float,
        G_max: float = 10,
    ):
        self.soil = soil_parameters
        self.sigma_vertical = sigma_vertical
        self.curve_data = curve_data

        strain = np.asarray(curve_data["strain"], dtype=float)
        ggmax = np.asarray(curve_data["ggmax"], dtype=float)
        damp = 100 * np.asarray(curve_data["damp"], dtype=float)

        mask = np.isfinite(strain) & np.isfinite(ggmax) & np.isfinite(damp)

        strain = strain[mask]
        ggmax = ggmax[mask]
        damp = damp[mask]

        strain = np.maximum(strain, 1e-12)
        ggmax = np.maximum(ggmax, 1e-12)
        damp = np.maximum(damp, 1e-12)

        idx = np.argsort(strain)
        self.strain_input = strain[idx]
        self.ggmax_input = ggmax[idx]
        self.damp_input = damp[idx]

        self.G_max = G_max * MPA_TO_PA

    def _interp_user(self, values):
        log_input = np.log10(self.strain_input)
        log_target = np.log10(SHEAR_STRAIN)

        return np.interp(
            log_target, log_input, values, left=values[0], right=values[-1]
        )

    def gg_max(self):
        return self._interp_user(self.ggmax_input)

    def damping(self):
        return self._interp_user(self.damp_input)

    def shear_strength(self):
        tau = self.gg_max() * self.G_max * SHEAR_STRAIN
        return tau / KPA_TO_PA


# ================================================================
# GRÁFICOS DE LA CLASE
# ================================================================


def percent_formatter(x, pos):
    return f"{x * 100:g}"


class CurveVisualizer:
    def __init__(self, model):

        self.model = model
        self.gamma = SHEAR_STRAIN

        curves = self.model.curves()

        tau = curves["tau"]
        ggmax = curves["ggmax"]
        damping = curves["damping"]

        self.create_figure(tau, ggmax, damping)

        plt.show()

    def create_figure(self, tau, ggmax, damping):

        self.fig, self.ax = plt.subplots(1, 3, figsize=(16, 5))
        plt.subplots_adjust(bottom=0.35)

        colors = ["tab:blue", "tab:green", "tab:red"]

        (self.line_tau,) = self.ax[0].plot(self.gamma, tau, lw=2, color=colors[0])
        (self.line_gg,) = self.ax[1].plot(self.gamma, ggmax, lw=2, color=colors[1])
        (self.line_damp,) = self.ax[2].plot(self.gamma, damping, lw=2, color=colors[2])

        titles = [
            "Stress–Strain",
            "Shear Modulus Reduction",
            "Damping Curve",
        ]

        ylabels = [
            r"$\tau$ (kPa)",
            r"$G/G_{max}$",
            r"$D$ (%)",
        ]

        for i in range(3):
            self.ax[i].set_xscale("log")
            self.ax[i].xaxis.set_major_formatter(FuncFormatter(percent_formatter))

            self.ax[i].set_xlabel(r"$\gamma$ (%)")
            self.ax[i].set_title(titles[i])
            self.ax[i].set_ylabel(ylabels[i])

            self.ax[i].grid(True, which="major", ls="-", alpha=0.5)
            self.ax[i].grid(True, which="minor", ls="--", alpha=0.2)

        self.ax[1].set_ylim(0, 1)

    def update_curves(self):

        curves = self.model.curves()

        tau = curves["tau"]
        gg = curves["ggmax"]
        damp = curves["damping"]

        self.line_tau.set_ydata(tau)
        self.line_gg.set_ydata(gg)
        self.line_damp.set_ydata(damp)

        self.fig.canvas.draw_idle()
