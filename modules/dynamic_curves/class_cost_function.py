from typing import Literal
from numpy.typing import NDArray
from scipy.interpolate import interp1d
import numpy as np

from libs.config.config_variables import (
    WEIGHTED_GGMAX_GQH,
    WEIGHTED_GGMAX_MKZ,
    WEIGHTED_DAMPING_MRDF,
    SHEAR_STRAIN,
    MIN_FLOAT,
    MAX_FLOAT,
    GAMMA_50_WEIGHT,
)

from libs.config.config_logger import get_logger

Array1D = NDArray[np.float64]

logger = get_logger()


class GGmaxCalibrationCost:
    """
    Función de costo considerando la mínima área entre curvas, coincidencia de máximas curvaturas
    superiores e inferiores.

    """

    def __init__(self, model: Literal[0, 1] = 0, b: float = 1) -> None:

        match model:
            case 0:
                self.base_weight = WEIGHTED_GGMAX_GQH["sesgo"]
                self.super_curvature_weight_factor = WEIGHTED_GGMAX_GQH[
                    "curve_weight_super"
                ]
                self.inf_curvature_weight_factor = WEIGHTED_GGMAX_GQH[
                    "curve_weight_inf"
                ]
                self.area_weight_factor = WEIGHTED_GGMAX_GQH["area_weight"]

            case 1:
                self.base_weight = WEIGHTED_GGMAX_MKZ["curve_weight_1"]
                self.curvature_weight_factor = WEIGHTED_GGMAX_MKZ["curve_weight_2"]
                self.area_weight_factor = WEIGHTED_GGMAX_MKZ["area_weight"]

            case _:
                raise ValueError(
                    f"Modelo no válido: {model}. Utilizar 0(GQH) o 1 (MKZ)"
                )

        self._log_gamma = np.log10(SHEAR_STRAIN)
        self.b = b
        self.gamma_50_weight = GAMMA_50_WEIGHT

    def compute(self, reference_curve: Array1D, model_curve: Array1D) -> float:

        reference_curve = np.asarray(reference_curve)
        model_curve = np.asarray(model_curve)

        if reference_curve.shape != model_curve.shape:
            raise ValueError("Las curvas deben tener la misma dimensión")

        if reference_curve.size < 3:
            return np.mean((reference_curve - model_curve) ** 2)

        reference_curve = np.nan_to_num(reference_curve)
        model_curve = np.nan_to_num(model_curve)

        gamma_ref = self._compute_gamma_ref(reference_curve)

        error_before = self._cost_function_before_gamma_ref(
            reference_curve, model_curve, gamma_ref
        )

        error_after = self._cost_function_after_gamma_ref(
            reference_curve, model_curve, gamma_ref
        )

        error_curv = error_before + error_after

        if self.area_weight_factor == 0:
            return error_curv

        error_area = self._area_error(reference_curve, model_curve)

        error_gamma50 = self._calibration_gamma_50(gamma_ref, model_curve)

        return (
            error_curv
            + self.area_weight_factor * error_area
            + self.gamma_50_weight * error_gamma50
        )

    def _calibration_gamma_50(self, gamma_ref, model_curve):
        target = 0.5**self.b

        # interpolar modelo en gamma_ref
        GG_model_at_gamma_ref = np.interp(
            np.log10(gamma_ref), self._log_gamma, model_curve
        )

        error_gamma50 = (GG_model_at_gamma_ref - target) ** 2
        return error_gamma50

    def _compute_gamma_ref(self, reference_curve):

        gg = np.asarray(reference_curve)
        log_gamma = self._log_gamma

        target = 0.5**self.b

        idx = np.argsort(gg)
        gg_sorted = gg[idx]
        log_gamma_sorted = log_gamma[idx]

        unique_gg, unique_idx = np.unique(gg_sorted, return_index=True)
        log_gamma_unique = log_gamma_sorted[unique_idx]

        if len(unique_gg) < 2:
            logger.warning("No hay suficientes puntos únicos para interpolar")
            return 10 ** log_gamma[np.argmin(np.abs(gg - target))]

        try:
            f = interp1d(
                unique_gg,
                log_gamma_unique,
                bounds_error=False,
                fill_value="extrapolate",
            )

            gamma_val = 10 ** f(target)

        except Exception as e:
            logger.warning(f"Fallo en interpolación: {e}")
            gamma_val = 10 ** log_gamma[np.argmin(np.abs(gg - target))]

        return gamma_val

    def _safe_curvature(self, curve: Array1D, log_gamma: Array1D):

        if curve.size < 3:
            return np.ones_like(curve)

        d1 = np.gradient(curve, log_gamma)
        d2 = np.gradient(d1, log_gamma)

        curvature = np.abs(d2)
        curvature = np.nan_to_num(curvature)

        max_curv = np.max(curvature)

        if max_curv == 0:
            return np.ones_like(curvature)

        return curvature / max_curv

    def _cost_function_before_gamma_ref(self, reference_curve, model_curve, gamma_ref):

        mask = SHEAR_STRAIN <= gamma_ref

        if len(SHEAR_STRAIN) != len(reference_curve):
            raise ValueError("SHEAR_STRAIN y curvas no tienen la misma longitud")

        reference_curve = reference_curve[mask]
        model_curve = model_curve[mask]
        log_gamma = self._log_gamma[mask]

        if reference_curve.size < 3:
            return np.mean((reference_curve - model_curve) ** 2)

        diff2 = (reference_curve - model_curve) ** 2

        curvature_weight = self._safe_curvature(reference_curve, log_gamma)

        weights = (
            self.base_weight + self.super_curvature_weight_factor * curvature_weight
        )

        w_sum = np.sum(weights)

        if w_sum == 0:
            return np.mean(diff2)

        return np.sum(weights * diff2) / w_sum

    def _cost_function_after_gamma_ref(self, reference_curve, model_curve, gamma_ref):

        mask = SHEAR_STRAIN > gamma_ref

        reference_curve = reference_curve[mask]
        model_curve = model_curve[mask]
        log_gamma = self._log_gamma[mask]

        if reference_curve.size < 3:
            return np.mean((reference_curve - model_curve) ** 2)

        diff2 = (reference_curve - model_curve) ** 2

        curvature_weight = self._safe_curvature(reference_curve, log_gamma)

        weights = self.base_weight + self.inf_curvature_weight_factor * curvature_weight

        w_sum = np.sum(weights)

        if w_sum == 0:
            return np.mean(diff2)

        return np.sum(weights * diff2) / w_sum

    def _area_error(self, reference_curve: Array1D, model_curve: Array1D) -> float:

        diff = np.abs(reference_curve - model_curve)

        area = np.trapz(diff, self._log_gamma)
        total_area = np.trapz(np.abs(reference_curve), self._log_gamma)

        if total_area == 0:
            return 0

        return area / total_area


class DampingCalibrationCost:
    def __init__(self, b: float = 1):
        self.b = b

    def compute(self, reference_curve, model_curve, strain):

        reference_curve = np.nan_to_num(reference_curve, nan=0.0)
        model_curve = np.nan_to_num(model_curve, nan=0.0)
        strain = np.nan_to_num(strain, nan=MIN_FLOAT)

        self._log_gamma = np.log10(strain + MIN_FLOAT)

        ref_raw = reference_curve.copy()
        mod_raw = model_curve.copy()

        reference_curve, model_curve = self._normalize_curves(
            reference_curve, model_curve
        )

        error_area = self._area_error(reference_curve, model_curve)
        error_extreme = self._extreme_error(ref_raw, mod_raw)

        penalty_monotonic = self._monotonicity_error(model_curve)
        penalty_smooth = self._smoothness_error(model_curve)

        penalty_oscillation = self._oscillation_penalty(model_curve)
        penalty_slope = self._slope_penalty(model_curve)
        penalty_spike = self._spike_penalty(model_curve)

        total_error = (
            WEIGHTED_DAMPING_MRDF["area_weight"] * error_area
            + WEIGHTED_DAMPING_MRDF["boundary_weight"] * error_extreme
            + WEIGHTED_DAMPING_MRDF["monotonic_weight"] * penalty_monotonic
            + WEIGHTED_DAMPING_MRDF["smooth_weight"] * penalty_smooth
            + WEIGHTED_DAMPING_MRDF["oscillation_weight"] * penalty_oscillation
            + WEIGHTED_DAMPING_MRDF["slope_weight"] * penalty_slope
            + WEIGHTED_DAMPING_MRDF["spike_weight"] * penalty_spike
        )

        if not np.isfinite(total_error):
            return MAX_FLOAT

        return total_error

    def _normalize_curves(self, theoretical_curve, calibrated_curve):

        max_theoretical_value = max(np.max(theoretical_curve), MIN_FLOAT)

        normalized_theoretical = theoretical_curve / max_theoretical_value
        normalized_calibrated = calibrated_curve / max_theoretical_value

        return normalized_theoretical, normalized_calibrated

    def _area_error(self, reference_curve, model_curve):

        log_gamma = self._log_gamma
        diff = np.abs(reference_curve - model_curve)
        weights = self._strain_weight()
        area = np.trapz(diff * weights, log_gamma)
        total_area = np.trapz(np.abs(reference_curve) * weights, log_gamma)

        if total_area <= MIN_FLOAT:
            return 1.0

        return np.clip(area / total_area, 0, 1)

    def _strain_weight(self):

        mean_strain = np.mean(self._log_gamma)
        spread_strain = np.std(self._log_gamma)
        weights = np.exp(
            -((self._log_gamma - mean_strain) ** 2) / (2 * spread_strain**2)
        )

        return weights / np.max(weights)

    def _extreme_error(self, reference_curve, model_curve):

        error_start = np.abs(reference_curve[0] - model_curve[0])
        error_end = np.abs(reference_curve[-1] - model_curve[-1])
        error = error_start**2 + 1.5 * error_end**2

        return np.clip(error, 0, 1)

    def _monotonicity_error(self, model_curve):

        d_diff = np.diff(model_curve)
        negative = np.abs(d_diff[d_diff < 0])

        if len(negative) == 0:
            return 0.0

        penalty = np.sum(negative)
        return np.clip(penalty / len(model_curve), 0, 1)

    def _smoothness_error(self, model_curve):

        d1 = self._safe_gradient(model_curve, self._log_gamma)
        d2 = self._safe_gradient(d1, self._log_gamma)

        penalty = np.mean(np.abs(d2))

        return np.clip(penalty, 0, 1)

    def _safe_gradient(self, y, x):

        if len(y) < 3:
            return np.zeros_like(y)

        dx = np.diff(x)

        if np.any(dx <= 0):
            return np.zeros_like(y)

        grad = np.gradient(y, x)
        return np.nan_to_num(grad)

    def _oscillation_penalty(self, model_curve):

        d1 = self._safe_gradient(model_curve, self._log_gamma)
        sign_changes = np.sum(np.diff(np.sign(d1)) != 0)
        return sign_changes / len(model_curve)

    def _slope_penalty(self, model_curve):

        d1 = self._safe_gradient(model_curve, self._log_gamma)
        negative = np.abs(d1[d1 < 0])
        if len(negative) == 0:
            return 0.0

        return np.clip(np.sum(negative) / len(model_curve), 0, 1)

    def _spike_penalty(self, model_curve):

        d1 = self._safe_gradient(model_curve, self._log_gamma)
        spike = np.max(np.abs(np.diff(d1)))
        return np.clip(spike, 0, 1)
