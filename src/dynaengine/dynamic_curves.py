"""Dynamic curve calculations by published authors and user-defined curves."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from dynaengine.catalog import (
    normalize_model_type,
    normalize_soil_parameters,
    validate_dynamic_model_definition,
)
from dynaengine.constants import (
    ATM_PRESSURE_KPA,
    DARENDELI_PARAMETERS,
    DEFAULT_SHEAR_STRAIN,
    KPA_TO_PA,
    MASING_COEFFICIENTS,
    MPA_TO_PA,
    PERCENT_TO_NUMBER,
    SEED_IDRISS_SHEAR_STRAIN,
)

DATA_DIR = Path(__file__).resolve().parent / "data"
THEORETICAL_CURVES_PATH = DATA_DIR / "theoretical_curves.json"


@dataclass(frozen=True)
class DynamicModelSpec:
    model_type: str
    sigma_vertical_kpa: float | None
    soil_parameters: dict[str, Any]
    curve_data: dict[str, Any] | None = None
    gmax_mpa: float = 10.0

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "DynamicModelSpec":
        source = data.get("dynamic_model", data)
        model_type = normalize_model_type(source["model_type"])
        soil_parameters = normalize_soil_parameters(
            model_type, dict(source.get("soil_parameters", {}))
        )
        curve_data = source.get("data") or source.get("curve_data")
        validate_dynamic_model_definition(model_type, soil_parameters, curve_data)

        sigma_vertical = source.get("sigma_vertical", source.get("sigma_vertical_kpa"))
        if model_type != "seed_1970" and sigma_vertical is None:
            raise ValueError(f"{model_type} requiere sigma_vertical en kPa")

        return cls(
            model_type=model_type,
            sigma_vertical_kpa=None
            if sigma_vertical is None
            else float(sigma_vertical),
            soil_parameters=soil_parameters,
            curve_data=curve_data,
            gmax_mpa=float(source.get("gmax_mpa", 10.0)),
        )

    def with_sigma_vertical(self, sigma_vertical_kpa: float) -> "DynamicModelSpec":
        return DynamicModelSpec(
            model_type=self.model_type,
            sigma_vertical_kpa=float(sigma_vertical_kpa),
            soil_parameters=dict(self.soil_parameters),
            curve_data=self.curve_data,
            gmax_mpa=self.gmax_mpa,
        )


@dataclass(frozen=True)
class DynamicCurveResult:
    strain: np.ndarray
    ggmax: np.ndarray
    damping_percent: np.ndarray
    shear_stress_kpa: np.ndarray
    model_type: str

    def as_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "strain": self.strain,
                "ggmax": self.ggmax,
                "damping_percent": self.damping_percent,
                "shear_stress_kpa": self.shear_stress_kpa,
            }
        )

    def calibration_data(self) -> dict[str, np.ndarray]:
        return {
            "strain": self.strain,
            "ggmax": self.ggmax,
            "damp": self.damping_percent,
        }


def evaluate_dynamic_curve(
    spec: DynamicModelSpec | dict[str, Any],
) -> DynamicCurveResult:
    model_spec = (
        spec
        if isinstance(spec, DynamicModelSpec)
        else DynamicModelSpec.from_mapping(spec)
    )

    model_type = model_spec.model_type
    p = model_spec.soil_parameters
    sigma = model_spec.sigma_vertical_kpa
    gmax_pa = model_spec.gmax_mpa * MPA_TO_PA

    if model_type == "darendeli_2001":
        strain, ggmax, damping = _darendeli_2001(p, sigma)
    elif model_type == "calibrated_darendeli":
        strain, ggmax, damping = _calibrated_darendeli(p, sigma)
    elif model_type == "menq_2003":
        strain, ggmax, damping = _menq_2003(p, sigma)
    elif model_type == "rollins_2020":
        strain, ggmax, damping = _rollins_2020(p, sigma)
    elif model_type == "ishibashi_1993":
        strain, ggmax, damping = _ishibashi_1993(p, sigma)
    elif model_type == "wang_2021":
        strain, ggmax, damping = _wang_2021(p, sigma)
    elif model_type == "rojas_2019":
        strain, ggmax, damping = _rojas_2019(p, sigma)
    elif model_type == "seed_1970":
        strain, ggmax, damping = _seed_idriss_1970(p)
    elif model_type == "user_defined":
        strain, ggmax, damping = _user_defined(model_spec.curve_data)
    else:
        raise ValueError(f"Modelo dinamico no soportado: {model_type}")

    shear_stress_kpa = gmax_pa * strain * ggmax / KPA_TO_PA
    return DynamicCurveResult(
        strain=strain,
        ggmax=ggmax,
        damping_percent=damping,
        shear_stress_kpa=shear_stress_kpa,
        model_type=model_type,
    )


def _load_theoretical_curves() -> dict[str, Any]:
    with THEORETICAL_CURVES_PATH.open("r", encoding="utf-8") as file:
        raw = json.load(file)

    return {
        "gamma": np.asarray(raw["gamma"], dtype=float),
        "rojas": {
            "G_Gmax": {
                float(k): np.asarray(v, dtype=float)
                for k, v in raw["rojas"]["G_Gmax"].items()
            },
            "D": {
                float(k): np.asarray(v, dtype=float)
                for k, v in raw["rojas"]["D"].items()
            },
        },
        "seed": {
            "G_Gmax": {
                k: np.asarray(v, dtype=float) for k, v in raw["seed"]["G_Gmax"].items()
            },
            "D": {k: np.asarray(v, dtype=float) for k, v in raw["seed"]["D"].items()},
        },
    }


_DISCRETE_CURVES: dict[str, Any] | None = None


def _discrete_curves() -> dict[str, Any]:
    global _DISCRETE_CURVES
    if _DISCRETE_CURVES is None:
        if not THEORETICAL_CURVES_PATH.exists():
            raise FileNotFoundError(
                f"No existe el archivo de curvas teoricas: {THEORETICAL_CURVES_PATH}"
            )
        _DISCRETE_CURVES = _load_theoretical_curves()
    return _DISCRETE_CURVES


def _mean_effective_stress_atm(k0: float, sigma_vertical_kpa: float) -> float:
    sigma_m = 0.5 * (1 + float(k0)) * float(sigma_vertical_kpa)
    return sigma_m / ATM_PRESSURE_KPA


def _interp_log(
    source_strain: np.ndarray, target_strain: np.ndarray, values: np.ndarray
) -> np.ndarray:
    return np.interp(np.log10(target_strain), np.log10(source_strain), values)


def _darendeli_2001(
    p: dict[str, Any], sigma_vertical_kpa: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    strain = DEFAULT_SHEAR_STRAIN
    phi = DARENDELI_PARAMETERS
    sigma_m = _mean_effective_stress_atm(p["k0"], sigma_vertical_kpa)

    gamma_ref = (
        (phi["phi1"] + phi["phi2"] * p["IP"] * p["OCR"] ** phi["phi3"])
        * sigma_m ** phi["phi4"]
        / PERCENT_TO_NUMBER
    )
    a = phi["phi5"]
    d_min = (
        (phi["phi6"] + phi["phi7"] * p["IP"] * p["OCR"] ** phi["phi8"])
        * sigma_m ** phi["phi9"]
        * (1 + phi["phi10"] * np.log(p["frequency"]))
    )
    b = phi["phi11"] + phi["phi12"] * np.log(p["N"])

    ggmax = np.minimum(1 / (1 + (strain / gamma_ref) ** a), 1)
    damping = b * (ggmax**0.1) * _damping_masing(strain, gamma_ref, a) + d_min
    return strain, ggmax, damping


def _calibrated_darendeli(
    p: dict[str, Any], sigma_vertical_kpa: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Parameterized Darendeli-style curve preserved from old_calibration."""

    strain = DEFAULT_SHEAR_STRAIN
    confinement = sigma_vertical_kpa * (1 + float(p["k0"])) / 2
    a = float(p["a1"]) + float(p["a2"]) * confinement
    gamma_ref = float(p["y1"]) + float(p["y2"]) * confinement
    if a <= 0:
        raise ValueError("calibrated_darendeli requiere a1 + a2 * confinamiento > 0")
    if gamma_ref <= 0:
        raise ValueError("calibrated_darendeli requiere y1 + y2 * confinamiento > 0")

    ggmax = np.minimum(1 / (1 + (strain / gamma_ref) ** a), 1)
    damping = (
        float(p["D1"]) * ggmax**2
        + float(p["D2"]) * ggmax
        + float(p["D3"])
        + float(p["Dmin"])
    )
    return strain, ggmax, damping


def _menq_2003(
    p: dict[str, Any], sigma_vertical_kpa: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    strain = DEFAULT_SHEAR_STRAIN
    sigma_norm = _mean_effective_stress_atm(p["k0"], sigma_vertical_kpa)
    gamma_ref = (
        0.12
        * p["Cu"] ** -0.6
        * sigma_norm ** (0.5 * p["Cu"] ** -0.15)
        / PERCENT_TO_NUMBER
    )
    a = 0.86 + 0.1 * np.log10(sigma_norm)
    d_min = 0.55 * p["Cu"] ** 0.1 * p["D50"] ** -0.3 * sigma_norm**-0.08
    b = 0.6329 - 0.0057 * np.log(p["N"])
    ggmax = np.minimum(1 / (1 + (strain / gamma_ref) ** a), 1)
    damping = b * (ggmax**0.1) * _damping_masing(strain, gamma_ref, a) + d_min
    return strain, ggmax, damping


def _damping_masing(strain: np.ndarray, gamma_ref: float, a: float) -> np.ndarray:
    upper = strain - gamma_ref * np.log((strain + gamma_ref) / gamma_ref)
    bottom = strain**2 / (strain + gamma_ref)
    damping_mass = (100 / np.pi) * (4 * upper / bottom - 2)
    c1 = np.polyval(MASING_COEFFICIENTS["c1"], a)
    c2 = np.polyval(MASING_COEFFICIENTS["c2"], a)
    c3 = np.polyval(MASING_COEFFICIENTS["c3"], a)
    return c1 * damping_mass + c2 * damping_mass**2 + c3 * damping_mass**3


def _rollins_2020(
    p: dict[str, Any], sigma_vertical_kpa: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    strain = DEFAULT_SHEAR_STRAIN
    sigma_m_kpa = (
        _mean_effective_stress_atm(p["k0"], sigma_vertical_kpa) * ATM_PRESSURE_KPA
    )
    gamma_percent = strain * 100
    temp = 0.0046 * p["Cu"] ** (-0.197) * sigma_m_kpa**0.52
    ggmax = np.minimum(1 / (1 + (gamma_percent / temp) ** 0.84), 1)
    gamma_norm = 100 * strain / (1 + 100 * strain)
    damping = 26.05 * gamma_norm**0.375 * p["Cu"] ** 0.08 * sigma_m_kpa ** (-0.07)
    return strain, ggmax, damping


def _ishibashi_1993(
    p: dict[str, Any], sigma_vertical_kpa: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    strain = DEFAULT_SHEAR_STRAIN
    ip = p["IP"]
    if ip <= 15:
        nip = 3.37e-6 * ip**1.404
    elif ip <= 70:
        nip = 7.0e-7 * ip**1.976
    else:
        nip = 2.7e-5 * ip**1.115

    k = 0.5 * (1 + np.tanh(0.492 * np.log((0.000102 + nip) / strain)))
    exponent = -0.0145 * ip**1.3
    m_mo = 0.272 * (1 - np.tanh(0.4 * np.log(0.000556 / strain))) * np.exp(exponent)
    ggmax = k * sigma_vertical_kpa**m_mo
    ggmax = ggmax / np.max(ggmax)
    damping = (
        100
        * 0.333
        * 0.5
        * (1 + np.exp(exponent))
        * (0.586 * ggmax**2 - 1.547 * ggmax + 1)
    )
    return strain, ggmax, damping


def _wang_2021(
    p: dict[str, Any], sigma_vertical_kpa: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    strain = DEFAULT_SHEAR_STRAIN
    sigma_norm = sigma_vertical_kpa / ATM_PRESSURE_KPA
    cf = _as_fraction(p.get("CF"))
    ip = _as_fraction(p.get("IP"))
    wc = _as_fraction(p.get("wc"))
    group = p["soil_group"]

    if group == "Clean sand and gravel group":
        _require_wang_params(p, "e", "Cu", "D50")
        if cf is None or wc is None:
            raise ValueError(
                "Wang & Stokoe requiere CF y wc para Clean sand and gravel group"
            )
        a = cf + 0.834
        b = 0.844 - 1.897 * cf
        gamma_mr = (0.048 * np.exp(0.089 * p["Cu"]) + 0.008) * sigma_norm**0.4
        cd = 0.6
        f_sigma = sigma_norm ** (-0.14)
        delta = 0
        fd = (1 + 21.17 * cf) * (0.99 + wc) ** (7.45 - 15.23 * p["e"] + 4.29 * p["D50"])
        d = 18.13
        c = 0.93 * p["e"] ** (0.34 - 0.8 * p["e"])
        gamma_d = 0.13 * p["Cu"] ** (-0.31) * (sigma_norm + 22.04 * cf) ** (0.47 - cf)
    elif group == "Nonplastic silty sand group":
        _require_wang_params(p, "e")
        if cf is None:
            raise ValueError(
                "Wang & Stokoe requiere CF para Nonplastic silty sand group"
            )
        a = (1.495 * p["e"] + 3.079 * cf) ** 0.121
        b = 0.486 - 0.006 * sigma_norm
        gamma_mr = (0.031 * p["e"] - 0.003) * sigma_norm ** (0.405 - 0.193 * cf)
        cd = 52.16
        f_sigma = sigma_norm ** (-0.19)
        delta = 0
        fd = (1 + 5.35 * cf) * (0.41 * p["e"]) ** (0.81 * cf + 5.2 * p["e"])
        d = 12.13
        c = 1.39 * p["e"] ** 0.27
        gamma_d = 0.0025 * (sigma_norm + 5.73 * p["e"] + 9.17 * cf) ** (
            1.47 - 0.52 * cf
        )
    elif group == "Clayey soil group":
        _require_wang_params(p, "e", "OCR")
        if cf is None or ip is None or wc is None:
            raise ValueError(
                "Wang & Stokoe requiere CF, IP y wc para Clayey soil group"
            )
        a = 0.896 + 0.412 * cf + 0.534 * ip
        b = 0.586 - 0.098 * p["e"] - 0.135 * cf
        gamma_mr = (0.02 * p["e"] + 0.004 * cf) * (sigma_norm + 0.42 * p["OCR"]) ** (
            0.447 - 0.27 * ip
        )
        cd = 4.86
        f_sigma = sigma_norm ** (-0.19)
        delta = (0.46 * ip) ** (1.73 - 1.34 * p["e"])
        fd = (1 + 106.75 * ip**1.64) * (1.99 + cf) ** (-1.91 * p["e"] - 6.5 * cf)
        d = 21.7
        c = (1.91 * cf) ** (1.62 * ip)
        gamma_d = 0.11 * (0.12 * sigma_norm + 5.29 * wc - cf) ** (
            1.45 - ip + wc - 1.09 * cf
        )
    else:
        raise ValueError(f"Grupo Wang & Stokoe no soportado: {group}")

    gamma_mr = gamma_mr / PERCENT_TO_NUMBER
    gamma_d = gamma_d / PERCENT_TO_NUMBER
    ggmax = np.minimum(1 / (1 + (strain / gamma_mr) ** a) ** b, 1)
    d_min = cd * fd * f_sigma + delta
    damping = (d * (strain / gamma_d) ** c + d_min) / ((strain / gamma_d) ** c + 1)
    return strain, ggmax, damping


def _as_fraction(value: Any) -> float | None:
    if value is None:
        return None
    value = float(value)
    return value / 100 if value > 1 else value


def _require_wang_params(parameters: dict[str, Any], *names: str) -> None:
    missing = [name for name in names if parameters.get(name) is None]
    if missing:
        raise ValueError(f"Faltan parametros Wang & Stokoe: {missing}")


def _rojas_2019(
    p: dict[str, Any], sigma_vertical_kpa: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    strain = DEFAULT_SHEAR_STRAIN
    sigma_m_kpa = (
        _mean_effective_stress_atm(p["k0"], sigma_vertical_kpa) * ATM_PRESSURE_KPA
    )
    available = np.array(
        list(_discrete_curves()["rojas"]["G_Gmax"].keys()), dtype=float
    )
    if sigma_m_kpa < available.min():
        raise ValueError("Confinamiento fuera del rango disponible para Rojas (2019)")
    sigma_ref = max(available[available <= sigma_m_kpa])
    source_strain = _discrete_curves()["gamma"]
    ggmax = _interp_log(
        source_strain, strain, _discrete_curves()["rojas"]["G_Gmax"][sigma_ref]
    )
    damping = _interp_log(
        source_strain, strain, _discrete_curves()["rojas"]["D"][sigma_ref]
    )
    return strain, ggmax, damping


def _seed_idriss_1970(p: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    strain = SEED_IDRISS_SHEAR_STRAIN
    source_strain = _discrete_curves()["gamma"]
    band = p["band"]
    ggmax = _interp_log(
        source_strain, strain, _discrete_curves()["seed"]["G_Gmax"][band]
    )
    damping = _interp_log(source_strain, strain, _discrete_curves()["seed"]["D"][band])
    return strain, ggmax, damping


def _user_defined(
    curve_data: dict[str, Any] | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if curve_data is None:
        raise ValueError("El modelo definido por el usuario requiere datos de curva")

    damping_key = "damp" if "damp" in curve_data else "damping"
    source_strain = np.asarray(curve_data["strain"], dtype=float)
    source_ggmax = np.asarray(curve_data["ggmax"], dtype=float)
    source_damping = np.asarray(curve_data[damping_key], dtype=float)

    mask = (
        np.isfinite(source_strain)
        & np.isfinite(source_ggmax)
        & np.isfinite(source_damping)
    )
    source_strain = np.maximum(source_strain[mask], 1e-12)
    source_ggmax = np.maximum(source_ggmax[mask], 1e-12)
    source_damping = np.maximum(source_damping[mask], 1e-12)
    if source_damping.max() <= 1.5:
        source_damping = 100 * source_damping

    order = np.argsort(source_strain)
    source_strain = source_strain[order]
    source_ggmax = source_ggmax[order]
    source_damping = source_damping[order]
    strain = DEFAULT_SHEAR_STRAIN
    ggmax = np.interp(
        np.log10(strain),
        np.log10(source_strain),
        source_ggmax,
        left=source_ggmax[0],
        right=source_ggmax[-1],
    )
    damping = np.interp(
        np.log10(strain),
        np.log10(source_strain),
        source_damping,
        left=source_damping[0],
        right=source_damping[-1],
    )
    return strain, ggmax, damping
