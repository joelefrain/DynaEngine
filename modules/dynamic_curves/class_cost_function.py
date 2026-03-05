from typing import Literal
from numpy.typing import NDArray
import numpy as np

from libs.config.config_variables import (
    WEIGHTED_FUNCTION_GQH,
    WEIGHTED_FUNCTION_MKZ,
    STRAIN_RANGE,
)

Array1D = NDArray[np.float64]


class GGmaxCalibrationCost:
    """
    Clase para el cálculo de la función de costo en la calibración
    de curvas normalizadas de módulo cortante (G/Gmax).

    La función de costo puede considerar:

    - Error cuadrático medio ponderado por curvatura.
    - Diferencia normalizada del área entre curvas.

    Parámetros
    ----------
    model : int, opcional
        Identificador del modelo:
        0 → GQH
        1 → MKZ

    Atributos
    ---------
    base_weight : float
        Peso base aplicado al error por curvatura.

    curvature_weight_factor : float
        Factor de ponderación asociado a la curvatura.

    area_weight_factor : float
        Factor de ponderación asociado al error de área.
    """

    def __init__(self, model: Literal[0, 1] = 0) -> None:
        match model:
            case 0:
                self.base_weight = WEIGHTED_FUNCTION_GQH["curve_weight_1"]
                self.curvature_weight_factor = WEIGHTED_FUNCTION_GQH["curve_weight_2"]
                self.area_weight_factor = WEIGHTED_FUNCTION_GQH["area_weight"]
            case 1:
                self.base_weight = WEIGHTED_FUNCTION_MKZ["curve_weight_1"]
                self.curvature_weight_factor = WEIGHTED_FUNCTION_MKZ["curve_weight_2"]
                self.area_weight_factor = WEIGHTED_FUNCTION_MKZ["area_weight"]
            case _:
                raise ValueError(
                    f"Modelo no válido: {model}. Utilizar 0(GQH) o 1 (MKZ)"
                )
        self._log_gamma = np.log10(STRAIN_RANGE)

    def compute(self, reference_curve: Array1D, model_curve: Array1D) -> float:
        """
        Calcula el error total entre la curva de referencia y la curva modelo.

        Parámetros
        ----------
        reference_curve : ndarray
            Curva de referencia normalizada (G/Gmax).

        model_curve : ndarray
            Curva modelo normalizada (G/Gmax).

        Retorna
        -------
        float
            Valor escalar del error total ponderado.
        """

        if not isinstance(reference_curve, np.ndarray) or not isinstance(
            model_curve, np.ndarray
        ):
            raise TypeError("Las curvas deben ser numpy arrays")

        if np.any((reference_curve < 0) | (reference_curve > 1)) or np.any(
            (model_curve < 0) | (model_curve > 1)
        ):
            raise ValueError("G/Gmax debe estar en el rango [0 - 1]")

        if reference_curve.shape != model_curve.shape:
            raise ValueError("Las curvas deben tener la misma dimensión")

        if not np.isfinite(reference_curve).all() or not np.isfinite(model_curve).all():
            raise ValueError("Las curvas contienen valores inválidos")

        error_curv = self._cost_function_curvature(reference_curve, model_curve)

        if self.area_weight_factor == 0:
            return error_curv

        error_area = self._area_error(reference_curve, model_curve)

        return error_curv + self.area_weight_factor * error_area

    def _cost_function_curvature(
        self, reference_curve: Array1D, model_curve: Array1D
    ) -> float:

        diff2 = (reference_curve - model_curve) ** 2

        if self.curvature_weight_factor == 0:
            return self.base_weight * np.mean(diff2)

        weights = self._curvature_weight(reference_curve)
        return np.mean(weights * diff2)

    def _curvature_weight(self, reference_curve: Array1D) -> Array1D:

        d1 = np.gradient(reference_curve, self._log_gamma)
        d2 = np.gradient(d1, self._log_gamma)

        curvatura = np.abs(d2)

        max_curvature = np.max(curvatura)

        if max_curvature == 0:
            weights = np.ones_like(curvatura)
        else:
            weights = curvatura / max_curvature

        weights = self.base_weight + self.curvature_weight_factor * weights

        return weights

    def _area_error(self, reference_curve: Array1D, model_curve: Array1D) -> float:

        diff = np.abs(reference_curve - model_curve)

        area = np.trapz(diff, self._log_gamma)
        total_area = np.trapz(np.abs(reference_curve), self._log_gamma)

        error_area = area / total_area

        return error_area
