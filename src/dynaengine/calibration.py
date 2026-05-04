"""Calibration of GQH and MRDF parameters from dynamic curves."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.interpolate import interp1d
from scipy.optimize import minimize

from dynaengine.constants import (
    DAMPING_CALIBRATION_WEIGHTS,
    DEFAULT_THETA_4,
    GQH_PARAMETER_BOUNDS,
    GGMAX_CALIBRATION_WEIGHTS,
    MAX_FLOAT,
    MIN_FLOAT,
    MRDF_PARAMETER_BOUNDS,
)

try:
    from bayes_opt import BayesianOptimization
except ImportError as exc:  # pragma: no cover - exercised only with missing dependency
    BayesianOptimization = None
    _BAYES_OPT_IMPORT_ERROR = exc
else:
    _BAYES_OPT_IMPORT_ERROR = None


@dataclass(frozen=True)
class CalibrationSettings:
    gqh_init_points: int = 15
    gqh_iterations: int = 100
    mrdf_init_points: int = 15
    mrdf_iterations: int = 100
    random_state: int = 1
    optimizer: str = "scipy"
    scipy_starts: int = 8
    scipy_maxiter: int = 120
    cache_precision: int = 4

    def __post_init__(self) -> None:
        if self.optimizer not in {"scipy", "bayesian"}:
            raise ValueError("optimizer debe ser 'scipy' o 'bayesian'")
        if self.scipy_starts <= 0:
            raise ValueError("scipy_starts debe ser mayor a 0")
        if self.scipy_maxiter <= 0:
            raise ValueError("scipy_maxiter debe ser mayor a 0")


@dataclass(frozen=True)
class CalibrationResult:
    theta: dict[str, float]
    mrdf: dict[str, float]
    dmin: float
    gamma_ref: float
    strain: np.ndarray
    target_ggmax: np.ndarray
    calibrated_ggmax: np.ndarray
    target_damping_percent: np.ndarray
    calibrated_damping_percent: np.ndarray
    gqh_score: float
    mrdf_score: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "theta": self.theta,
            "mrdf": self.mrdf,
            "dmin": self.dmin,
            "gamma_ref": self.gamma_ref,
            "strain": self.strain.tolist(),
            "target_ggmax": self.target_ggmax.tolist(),
            "calibrated_ggmax": self.calibrated_ggmax.tolist(),
            "target_damping_percent": self.target_damping_percent.tolist(),
            "calibrated_damping_percent": self.calibrated_damping_percent.tolist(),
            "gqh_score": self.gqh_score,
            "mrdf_score": self.mrdf_score,
        }


def calibrate_dynamic_curve(
    curve_data: dict[str, Any],
    gmax_pa: float,
    tau_max_pa: float,
    b: float = 1.0,
    settings: CalibrationSettings | None = None,
) -> CalibrationResult:
    """Fit GQH and MRDF parameters to a target dynamic curve."""

    settings = settings or CalibrationSettings()
    strain, ggmax, damping = _normalize_curve_data(curve_data)

    if gmax_pa <= 0:
        raise ValueError("gmax_pa debe ser mayor a 0")
    if tau_max_pa <= 0:
        raise ValueError("tau_max_pa debe ser mayor a 0")

    calibrator = _CurveCalibrator(
        strain=strain,
        ggmax=ggmax,
        damping=damping,
        gmax_pa=float(gmax_pa),
        tau_max_pa=float(tau_max_pa),
        b=float(b),
        settings=settings,
    )

    gqh_result = calibrator.calibrate_gqh()
    theta = {key: float(value) for key, value in gqh_result["params"].items()}
    mrdf_result = calibrator.calibrate_mrdf(theta)
    mrdf = {key: float(value) for key, value in mrdf_result["params"].items()}

    return CalibrationResult(
        theta={**theta, "theta_4": DEFAULT_THETA_4},
        mrdf=mrdf,
        dmin=mrdf["Dmin"],
        gamma_ref=calibrator.gamma_ref,
        strain=strain,
        target_ggmax=ggmax,
        calibrated_ggmax=calibrator.compute_gqh_curve(theta),
        target_damping_percent=damping,
        calibrated_damping_percent=calibrator.compute_mrdf_curve(theta, mrdf),
        gqh_score=float(gqh_result["target"]),
        mrdf_score=float(mrdf_result["target"]),
    )


def _normalize_curve_data(
    curve_data: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    damping_key = "damp" if "damp" in curve_data else "damping"
    required = ("strain", "ggmax", damping_key)
    missing = [key for key in required if key not in curve_data]
    if missing:
        raise KeyError(f"Faltan llaves de curva: {missing}")

    strain = np.asarray(curve_data["strain"], dtype=float)
    ggmax = np.asarray(curve_data["ggmax"], dtype=float)
    damping = np.asarray(curve_data[damping_key], dtype=float)
    if not (strain.shape == ggmax.shape == damping.shape):
        raise ValueError("strain, ggmax y damping deben tener la misma dimension")

    mask = np.isfinite(strain) & np.isfinite(ggmax) & np.isfinite(damping)
    strain = strain[mask]
    ggmax = ggmax[mask]
    damping = damping[mask]
    if strain.size < 3:
        raise ValueError("La calibracion requiere al menos tres puntos validos")
    if np.any(strain <= 0):
        raise ValueError("strain debe ser positivo")
    if np.any((ggmax <= 0) | (ggmax > 1.2)):
        raise ValueError("ggmax debe estar entre 0 y 1.2")

    order = np.argsort(strain)
    damping = damping[order]
    if damping.max() <= 1.5:
        damping = 100 * damping

    return strain[order], ggmax[order], damping


class _CurveCalibrator:
    def __init__(
        self,
        strain: np.ndarray,
        ggmax: np.ndarray,
        damping: np.ndarray,
        gmax_pa: float,
        tau_max_pa: float,
        b: float,
        settings: CalibrationSettings,
    ) -> None:
        self.strain = strain
        self.ggmax = ggmax
        self.damping = damping
        self.gmax_pa = gmax_pa
        self.tau_max_pa = tau_max_pa
        self.b = b
        self.settings = settings

        # GQ/H defines gamma_ref from strength, not from the target gamma_50.
        # The target gamma_50 is still used inside the objective as a fit metric.
        self.gamma_ref = self.tau_max_pa / self.gmax_pa
        if self.gamma_ref <= 0:
            raise ValueError("gamma_ref=tau_max_pa/gmax_pa debe ser mayor a 0")
        self.ggmax_cost = _GGmaxCalibrationCost(self.strain, b)
        self.damping_cost = _DampingCalibrationCost()

    def calibrate_gqh(self) -> dict[str, Any]:
        def objective(
            theta_1: float, theta_2: float, theta_3: float, theta_5: float
        ) -> float:
            if theta_1 + theta_2 > 1:
                return -MAX_FLOAT
            params = {
                "theta_1": theta_1,
                "theta_2": theta_2,
                "theta_3": theta_3,
                "theta_4": DEFAULT_THETA_4,
                "theta_5": theta_5,
            }
            try:
                model = GQHModelFormulation(params)
                model_curve = model.ggmax_model(self.strain, self.gamma_ref)
                return -self.ggmax_cost.compute(self.ggmax, model_curve)
            except Exception:
                return -MAX_FLOAT

        if self.settings.optimizer == "scipy":
            return _maximize_with_scipy(
                objective,
                GQH_PARAMETER_BOUNDS,
                random_state=self.settings.random_state,
                starts=self.settings.scipy_starts,
                maxiter=self.settings.scipy_maxiter,
            )

        if BayesianOptimization is None:
            raise ImportError(
                "bayesian-optimization es requerido para calibrar con optimizer='bayesian'"
            ) from _BAYES_OPT_IMPORT_ERROR

        optimizer = BayesianOptimization(
            f=objective,
            pbounds=GQH_PARAMETER_BOUNDS,
            random_state=self.settings.random_state,
            verbose=0,
        )
        optimizer.maximize(
            init_points=self.settings.gqh_init_points,
            n_iter=self.settings.gqh_iterations,
        )
        return optimizer.max

    def calibrate_mrdf(self, theta: dict[str, float]) -> dict[str, Any]:
        gqh_model = GQHModelFormulation({**theta, "theta_4": DEFAULT_THETA_4})
        backbone = BackboneWrapper(gqh_model, self.gmax_pa, self.tau_max_pa)

        def objective(P1: float, P2: float, P3: float, Dmin: float) -> float:
            params = {"P1": P1, "P2": P2, "P3": P3, "Dmin": Dmin}
            model = MRDFNoMasingRules(backbone, params)
            damping_curve = model.compute_damping_vectorized(self.strain)
            if np.any(damping_curve <= 0):
                return -MAX_FLOAT
            error = self.damping_cost.compute(self.damping, damping_curve, self.strain)
            return -error

        if self.settings.optimizer == "scipy":
            return _maximize_with_scipy(
                objective,
                MRDF_PARAMETER_BOUNDS,
                random_state=self.settings.random_state + 101,
                starts=self.settings.scipy_starts,
                maxiter=self.settings.scipy_maxiter,
            )

        if BayesianOptimization is None:
            raise ImportError(
                "bayesian-optimization es requerido para calibrar con optimizer='bayesian'"
            ) from _BAYES_OPT_IMPORT_ERROR

        optimizer = BayesianOptimization(
            f=objective,
            pbounds=MRDF_PARAMETER_BOUNDS,
            random_state=self.settings.random_state,
            verbose=0,
        )
        optimizer.maximize(
            init_points=self.settings.mrdf_init_points,
            n_iter=self.settings.mrdf_iterations,
        )
        return optimizer.max

    def compute_gqh_curve(self, theta: dict[str, float]) -> np.ndarray:
        model = GQHModelFormulation({**theta, "theta_4": DEFAULT_THETA_4})
        return model.ggmax_model(self.strain, self.gamma_ref)

    def compute_mrdf_curve(
        self, theta: dict[str, float], mrdf: dict[str, float]
    ) -> np.ndarray:
        model = GQHModelFormulation({**theta, "theta_4": DEFAULT_THETA_4})
        backbone = BackboneWrapper(model, self.gmax_pa, self.tau_max_pa)
        return MRDFNoMasingRules(backbone, mrdf).compute_damping_vectorized(self.strain)


class GQHModelFormulation:
    def __init__(self, parameters: dict[str, float]) -> None:
        for key in ("theta_1", "theta_2", "theta_3", "theta_4", "theta_5"):
            if key not in parameters:
                raise ValueError(f"Falta el parametro {key}")
        self.theta_1 = parameters["theta_1"]
        self.theta_2 = parameters["theta_2"]
        self.theta_3 = parameters["theta_3"]
        self.theta_4 = parameters["theta_4"]
        self.theta_5 = parameters["theta_5"]

    def compute_theta_tau(self, strain: np.ndarray, x: np.ndarray) -> np.ndarray:
        strain = np.asarray(strain, dtype=float)
        x = np.asarray(x, dtype=float)
        rad = self.theta_4 * x**self.theta_5
        theta_r = self.theta_1 + self.theta_2 * rad / (self.theta_3**self.theta_5 + rad)
        return np.minimum(theta_r, 1.0)

    def ggmax_model(self, strain: np.ndarray, gamma_ref: float) -> np.ndarray:
        x = strain / gamma_ref
        theta_r = self.compute_theta_tau(strain, x)
        inside = (1 + x) ** 2 - 4 * theta_r * x
        if np.any(inside < 0):
            raise ValueError("Raiz negativa en GQH")
        return np.minimum(2 / (1 + x + np.sqrt(inside)), 1.0)


class BackboneWrapper:
    def __init__(
        self, gqh_model: GQHModelFormulation, gmax_pa: float, tau_max_pa: float
    ) -> None:
        self.model = gqh_model
        self.gmax_pa = gmax_pa
        self.tau_max_pa = tau_max_pa
        self.gamma_ref = tau_max_pa / gmax_pa

    def compute_theta_tau(
        self, gamma: np.ndarray, gamma_norm: np.ndarray
    ) -> np.ndarray:
        return self.model.compute_theta_tau(gamma, gamma_norm)


class MRDFNoMasingRules:
    def __init__(
        self, backbone_model: BackboneWrapper, parameters: dict[str, float]
    ) -> None:
        self.backbone_model = backbone_model
        self.p1 = parameters["P1"]
        self.p2 = parameters["P2"]
        self.p3 = parameters["P3"]
        self.d_min = parameters["Dmin"]
        self.gmax_pa = backbone_model.gmax_pa
        self.tau_max_pa = backbone_model.tau_max_pa
        self.gamma_ref = backbone_model.gamma_ref

    def _compute_mrdf(self, ggmax: float) -> float:
        return self.p1 - self.p2 * (1 - ggmax) ** self.p3

    def _compute_tau_backbone(self, gamma: np.ndarray) -> np.ndarray:
        gamma = np.atleast_1d(gamma).astype(float)
        sign = np.sign(gamma)
        x = np.abs(gamma) / self.gamma_ref
        theta_tau = self.backbone_model.compute_theta_tau(np.abs(gamma), x)
        radicand = (1 + x) ** 2 - 4 * theta_tau * x
        if np.any(radicand < 0):
            raise ValueError("Raiz negativa en backbone GQ/H")
        normalized_tau = 2 * x / (1 + x + np.sqrt(radicand))
        return sign * self.tau_max_pa * normalized_tau

    def compute_damping(self, gamma: float, n_points: int = 100) -> float:
        if gamma < 1e-8:
            return self.d_min
        tau_y = self._compute_tau_backbone(np.array([gamma]))[0]
        g_gamma = tau_y / gamma
        ggmax = g_gamma / self.gmax_pa
        factor = self._compute_mrdf(ggmax)
        if factor <= 0:
            return -MAX_FLOAT
        yc = np.linspace(-gamma, gamma, n_points)
        gamma_mid = (yc + gamma) / 2
        tau_backbone = self._compute_tau_backbone(gamma_mid)
        tc = (
            factor * (2 * tau_backbone - g_gamma * (yc + gamma))
            + g_gamma * (yc + gamma)
            - tau_y
        )
        loop_area = abs(
            np.trapz(np.concatenate((tc, -tc[::-1])), np.concatenate((yc, yc[::-1])))
        )
        elastic_energy = tau_y * gamma / 2
        if elastic_energy < MIN_FLOAT:
            return self.d_min
        return 100 * loop_area / (4 * np.pi * elastic_energy) + self.d_min

    def compute_damping_vectorized(self, gamma_array: np.ndarray) -> np.ndarray:
        gamma_array = np.asarray(gamma_array, dtype=float)
        result = np.full_like(gamma_array, self.d_min, dtype=float)
        active = gamma_array >= 1e-8
        if not np.any(active):
            return result

        gamma = gamma_array[active]
        tau_y = self._compute_tau_backbone(gamma)
        g_gamma = tau_y / gamma
        ggmax = g_gamma / self.gmax_pa
        factor = self._compute_mrdf(ggmax)

        valid = factor > 0
        active_result = np.full_like(gamma, -MAX_FLOAT, dtype=float)
        if np.any(valid):
            gamma_valid = gamma[valid]
            tau_y_valid = tau_y[valid]
            g_gamma_valid = g_gamma[valid]
            factor_valid = factor[valid]

            normalized = np.linspace(-1.0, 1.0, 100)
            yc = gamma_valid[:, None] * normalized[None, :]
            gamma_mid = (yc + gamma_valid[:, None]) / 2
            tau_backbone = self._compute_tau_backbone(gamma_mid)
            tc = (
                factor_valid[:, None]
                * (
                    2 * tau_backbone
                    - g_gamma_valid[:, None] * (yc + gamma_valid[:, None])
                )
                + g_gamma_valid[:, None] * (yc + gamma_valid[:, None])
                - tau_y_valid[:, None]
            )
            y_plot = np.concatenate((yc, yc[:, ::-1]), axis=1)
            t_plot = np.concatenate((tc, -tc[:, ::-1]), axis=1)
            loop_area = np.abs(np.trapz(t_plot, y_plot, axis=1))
            elastic_energy = tau_y_valid * gamma_valid / 2

            damping = np.full_like(gamma_valid, self.d_min, dtype=float)
            energy_valid = elastic_energy >= MIN_FLOAT
            damping[energy_valid] = (
                100
                * loop_area[energy_valid]
                / (4 * np.pi * elastic_energy[energy_valid])
                + self.d_min
            )
            active_result[valid] = damping

        result[active] = active_result
        return result


def _maximize_with_scipy(
    objective,
    bounds: dict[str, tuple[float, float]],
    random_state: int,
    starts: int,
    maxiter: int,
) -> dict[str, Any]:
    names = list(bounds)
    bound_values = [bounds[name] for name in names]
    rng = np.random.default_rng(random_state)
    initial_points = [_bounds_midpoint(bound_values)]
    initial_points.extend(_random_points(bound_values, rng, max(0, starts - 1)))

    best_value = MAX_FLOAT
    best_x = initial_points[0]

    def loss(x: np.ndarray) -> float:
        params = {name: float(value) for name, value in zip(names, x)}
        try:
            score = float(objective(**params))
        except Exception:
            return MAX_FLOAT
        if not np.isfinite(score):
            return MAX_FLOAT
        return -score

    for point in initial_points:
        result = minimize(
            loss,
            point,
            method="Powell",
            bounds=bound_values,
            options={"maxiter": maxiter, "disp": False},
        )
        value = float(result.fun) if np.isfinite(result.fun) else MAX_FLOAT
        if value < best_value:
            best_value = value
            best_x = np.asarray(result.x, dtype=float)

    best_params = {name: float(value) for name, value in zip(names, best_x)}
    return {"target": -best_value, "params": best_params}


def _bounds_midpoint(bounds: list[tuple[float, float]]) -> np.ndarray:
    return np.asarray([(low + high) / 2 for low, high in bounds], dtype=float)


def _random_points(
    bounds: list[tuple[float, float]], rng: np.random.Generator, count: int
) -> list[np.ndarray]:
    points = []
    for _ in range(count):
        values = [rng.uniform(low, high) for low, high in bounds]
        points.append(np.asarray(values, dtype=float))
    return points


class _GGmaxCalibrationCost:
    def __init__(self, strain: np.ndarray, b: float = 1.0) -> None:
        self.strain = strain
        self.log_gamma = np.log10(strain)
        self.b = b

    def compute(self, reference_curve: np.ndarray, model_curve: np.ndarray) -> float:
        reference_curve = np.asarray(reference_curve)
        model_curve = np.asarray(model_curve)
        if reference_curve.shape != model_curve.shape:
            raise ValueError("Las curvas deben tener la misma dimension")
        if reference_curve.size < 3:
            return float(np.mean((reference_curve - model_curve) ** 2))

        gamma_ref = self._compute_gamma_ref(reference_curve)
        error_before = self._curvature_cost(
            reference_curve, model_curve, gamma_ref, before=True
        )
        error_after = self._curvature_cost(
            reference_curve, model_curve, gamma_ref, before=False
        )
        area_error = self._area_error(reference_curve, model_curve)
        gamma50_error = self._gamma50_error(gamma_ref, model_curve)
        weights = GGMAX_CALIBRATION_WEIGHTS
        return (
            error_before
            + error_after
            + weights["area"] * area_error
            + weights["gamma_50"] * gamma50_error
        )

    def _compute_gamma_ref(self, reference_curve: np.ndarray) -> float:
        target = 0.5**self.b
        order = np.argsort(reference_curve)
        gg_sorted = reference_curve[order]
        log_gamma_sorted = self.log_gamma[order]
        unique_gg, unique_idx = np.unique(gg_sorted, return_index=True)
        if len(unique_gg) < 2:
            return float(self.strain[np.argmin(np.abs(reference_curve - target))])
        try:
            interpolator = interp1d(
                unique_gg,
                log_gamma_sorted[unique_idx],
                bounds_error=False,
                fill_value="extrapolate",
            )
            return float(10 ** interpolator(target))
        except Exception:
            return float(self.strain[np.argmin(np.abs(reference_curve - target))])

    def _gamma50_error(self, gamma_ref: float, model_curve: np.ndarray) -> float:
        target = 0.5**self.b
        value = np.interp(np.log10(gamma_ref), self.log_gamma, model_curve)
        return float((value - target) ** 2)

    def _curvature_cost(
        self,
        reference_curve: np.ndarray,
        model_curve: np.ndarray,
        gamma_ref: float,
        before: bool,
    ) -> float:
        mask = self.strain <= gamma_ref if before else self.strain > gamma_ref
        ref = reference_curve[mask]
        mod = model_curve[mask]
        log_gamma = self.log_gamma[mask]
        if ref.size < 3:
            return float(np.mean((ref - mod) ** 2)) if ref.size else 0.0
        curvature_weight = self._safe_curvature(ref, log_gamma)
        weights = GGMAX_CALIBRATION_WEIGHTS
        curvature_factor = (
            weights["upper_curvature"] if before else weights["lower_curvature"]
        )
        sample_weights = weights["bias"] + curvature_factor * curvature_weight
        return float(np.sum(sample_weights * (ref - mod) ** 2) / np.sum(sample_weights))

    @staticmethod
    def _safe_curvature(curve: np.ndarray, log_gamma: np.ndarray) -> np.ndarray:
        d1 = np.gradient(curve, log_gamma)
        d2 = np.gradient(d1, log_gamma)
        curvature = np.nan_to_num(np.abs(d2))
        max_curvature = np.max(curvature)
        if max_curvature == 0:
            return np.ones_like(curvature)
        return curvature / max_curvature

    def _area_error(
        self, reference_curve: np.ndarray, model_curve: np.ndarray
    ) -> float:
        diff = np.abs(reference_curve - model_curve)
        area = np.trapz(diff, self.log_gamma)
        total_area = np.trapz(np.abs(reference_curve), self.log_gamma)
        if total_area == 0:
            return 0.0
        return float(area / total_area)


class _DampingCalibrationCost:
    def compute(
        self, reference_curve: np.ndarray, model_curve: np.ndarray, strain: np.ndarray
    ) -> float:
        reference_curve = np.nan_to_num(reference_curve, nan=0.0)
        model_curve = np.nan_to_num(model_curve, nan=0.0)
        log_gamma = np.log10(np.nan_to_num(strain, nan=MIN_FLOAT) + MIN_FLOAT)
        ref_normalized, mod_normalized = self._normalize(reference_curve, model_curve)
        weights = DAMPING_CALIBRATION_WEIGHTS
        total_error = (
            weights["area"]
            * self._area_error(ref_normalized, mod_normalized, log_gamma)
            + weights["boundary"] * self._extreme_error(reference_curve, model_curve)
            + weights["monotonic"] * self._monotonicity_error(mod_normalized)
            + weights["smooth"] * self._smoothness_error(mod_normalized, log_gamma)
            + weights["oscillation"]
            * self._oscillation_penalty(mod_normalized, log_gamma)
            + weights["slope"] * self._slope_penalty(mod_normalized, log_gamma)
            + weights["spike"] * self._spike_penalty(mod_normalized, log_gamma)
        )
        if not np.isfinite(total_error):
            return MAX_FLOAT
        return float(total_error)

    @staticmethod
    def _normalize(
        reference_curve: np.ndarray, model_curve: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        max_reference = max(float(np.max(reference_curve)), MIN_FLOAT)
        return reference_curve / max_reference, model_curve / max_reference

    @staticmethod
    def _area_error(
        reference_curve: np.ndarray, model_curve: np.ndarray, log_gamma: np.ndarray
    ) -> float:
        diff = np.abs(reference_curve - model_curve)
        spread = np.std(log_gamma)
        if spread <= MIN_FLOAT:
            weights = np.ones_like(log_gamma)
        else:
            weights = np.exp(-((log_gamma - np.mean(log_gamma)) ** 2) / (2 * spread**2))
            weights = weights / np.max(weights)
        area = np.trapz(diff * weights, log_gamma)
        total = np.trapz(np.abs(reference_curve) * weights, log_gamma)
        if total <= MIN_FLOAT:
            return 1.0
        return float(np.clip(area / total, 0, 1))

    @staticmethod
    def _extreme_error(reference_curve: np.ndarray, model_curve: np.ndarray) -> float:
        error = (
            abs(reference_curve[0] - model_curve[0]) ** 2
            + 1.5 * abs(reference_curve[-1] - model_curve[-1]) ** 2
        )
        return float(np.clip(error, 0, 1))

    @staticmethod
    def _safe_gradient(values: np.ndarray, x: np.ndarray) -> np.ndarray:
        if len(values) < 3 or np.any(np.diff(x) <= 0):
            return np.zeros_like(values)
        return np.nan_to_num(np.gradient(values, x))

    def _monotonicity_error(self, model_curve: np.ndarray) -> float:
        negative = np.abs(np.diff(model_curve)[np.diff(model_curve) < 0])
        return (
            0.0
            if len(negative) == 0
            else float(np.clip(np.sum(negative) / len(model_curve), 0, 1))
        )

    def _smoothness_error(
        self, model_curve: np.ndarray, log_gamma: np.ndarray
    ) -> float:
        d1 = self._safe_gradient(model_curve, log_gamma)
        d2 = self._safe_gradient(d1, log_gamma)
        return float(np.clip(np.mean(np.abs(d2)), 0, 1))

    def _oscillation_penalty(
        self, model_curve: np.ndarray, log_gamma: np.ndarray
    ) -> float:
        d1 = self._safe_gradient(model_curve, log_gamma)
        return float(np.sum(np.diff(np.sign(d1)) != 0) / len(model_curve))

    def _slope_penalty(self, model_curve: np.ndarray, log_gamma: np.ndarray) -> float:
        d1 = self._safe_gradient(model_curve, log_gamma)
        negative = np.abs(d1[d1 < 0])
        return (
            0.0
            if len(negative) == 0
            else float(np.clip(np.sum(negative) / len(model_curve), 0, 1))
        )

    def _spike_penalty(self, model_curve: np.ndarray, log_gamma: np.ndarray) -> float:
        d1 = self._safe_gradient(model_curve, log_gamma)
        return float(np.clip(np.max(np.abs(np.diff(d1))), 0, 1))
