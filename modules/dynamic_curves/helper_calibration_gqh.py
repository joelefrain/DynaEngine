import numpy as np
from numpy.typing import NDArray
from libs.config.config_variables import STRAIN_RANGE

Array1D = NDArray[np.float64]


class GQHModelFormulation:
    """
    Implementación del modelo GQH (Generalized Quadratic Hyperbolic)
    para el cálculo de la curva de reducción del módulo cortante normalizado (G/Gmax).

    El modelo describe el comportamiento no lineal del suelo bajo deformaciones
    cortantes crecientes mediante cinco parámetros calibrables (theta_1 a theta_5).

    Parámetros
    ----------
    parametros_gqh : dict
        Diccionario con los parámetros del modelo:
        - theta_1 : float
        - theta_2 : float
        - theta_3 : float
        - theta_4 : float
        - theta_5 : float

    Notas
    -----
    - El modelo asume deformaciones positivas.
    - La formulación garantiza G/Gmax <= 1.
    - Puede presentar inestabilidades numéricas si los parámetros no son físicamente consistentes.
    """

    def __init__(self, parametros_gqh: dict) -> None:

        if not isinstance(parametros_gqh, dict):
            raise TypeError("parametros_gqh debe ser un diccionario")

        for key in ["theta_1", "theta_2", "theta_3", "theta_4", "theta_5"]:
            if key not in parametros_gqh:
                raise ValueError(f"Falta el parámetro {key}")

        self.theta_1 = parametros_gqh["theta_1"]
        self.theta_2 = parametros_gqh["theta_2"]
        self.theta_3 = parametros_gqh["theta_3"]
        self.theta_4 = parametros_gqh["theta_4"]
        self.theta_5 = parametros_gqh["theta_5"]
        self.model_type = 0

    def GGmax_model(self, gamma_ref: float) -> Array1D:
        """
        Calcula la curva de reducción del módulo cortante normalizado (G/Gmax)
        para un valor dado de deformación de referencia.

        Parámetros
        ----------
        gamma_ref : float
            Deformación cortante de referencia.

        Retorna
        -------
        np.ndarray
            Valores de G/Gmax evaluados sobre STRAIN_RANGE.
        """
        x = STRAIN_RANGE / gamma_ref

        theta_r = self.theta_1 + self.theta_2 * (self.theta_4 * x**self.theta_5) / (
            self.theta_3**self.theta_5 + self.theta_4 * x**self.theta_5
        )

        theta_r = np.minimum(theta_r, 1.0)

        inside = (1 + x) ** 2 - 4 * theta_r * x
        if inside.any() < 0:
            raise ("Se estan generando problemas de cálculo. Raiz compleja")
        GG = 2 / (1 + x + np.sqrt(inside))

        return GG

    def calculate_gg_ref(self) -> float:
        """
        Calcula el valor de referencia G/Gmax asociado a gamma = gamma_ref = 1
        según la formulación interna del modelo GQH.

        Retorna
        -------
        float
            Valor escalar de G/Gmax de referencia.
        """
        x = self.theta_1 + (self.theta_2 * self.theta_4) / (
            self.theta_3**self.theta_5 + self.theta_4
        )
        gg_ref = 1 / (1 + np.sqrt(1 - x))
        return gg_ref

    @staticmethod
    def _calcular_beta_ref(
        gg_ref: float,
        d: float,
        a: float,
        mu: float,
        gamma_ref: float,
        gamma_t: float,
        tau_max: float,
        G_max: float,
    ) -> float:
        """
        Calcula el parámetro beta de transición para el modelo híbrido HH
        a partir del valor de referencia G/Gmax.

        Parámetros
        ----------
        gg_ref : float
            Valor de referencia G/Gmax.
        d : float
            Exponente del modelo FKZ.
        a : float
            Parámetro de transición logística.
        mu : float
            Parámetro de rigidez FKZ.
        gamma_ref : float
            Deformación de referencia.
        tau_max : float
            Esfuerzo cortante máximo.
        G_max : float
            Módulo cortante máximo.

        Retorna
        -------
        float
            Valor calibrado de beta.
        """
        omega = 1 - 1 / (
            1 + 10 ** (-a * (np.log10(gamma_ref / gamma_t) - 4.039 * a**-1.036))
        )

        ref = gg_ref - (1 - omega) * mu * gamma_ref ** (d - 1) / (
            1 + (mu * G_max * gamma_ref**d) / tau_max
        )
        ref = np.clip(ref, 1e-12, None)

        return -1 + omega / ref
