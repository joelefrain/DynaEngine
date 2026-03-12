import numpy as np
from numpy.typing import NDArray
from libs.config.config_variables import STRAIN_RANGE, MIN_FLOAT, MAX_FLOAT, EXP_LIMIT

MIN_A = 1e-6

Array1D = NDArray[np.float64]


def GGmax_HH_model(
    gg_ref: float,
    s: float,
    d: float,
    mu: float,
    a: float,
    G_max: float,
    gamma_ref: float,
    gamma_t: float,  # Agregado
    tau_max: float,
    model: object,
) -> Array1D:
    """
    Calcula la curva de degradación del módulo de corte normalizado (G/Gmax)
    utilizando el modelo Hiperbólico Híbrido (HH).

    El modelo HH combina las formulaciones MKZ y FKZ mediante una
    función logística de transición ω(γ), permitiendo una interpolación
    suave entre ambos comportamientos constitutivos en función de la
    deformación cortante.

    Parámetros
    ----------
    gg_ref : float
        Valor de referencia de G/Gmax utilizado para la calibración
        del parámetro β.
    s : float
        Parámetro de curvatura del modelo MKZ.
    d : float
        Exponente del modelo FKZ.
    mu : float
        Parámetro de rigidez del modelo FKZ.
    a : float
        Parámetro que controla la pendiente de la transición logística.
    G_max : float
        Módulo de corte máximo del suelo.
    gamma_ref : float
        Deformación cortante de referencia.
    tau_max : float
        Esfuerzo cortante máximo.
    model : object
        Instancia que contiene el método de calibración del parámetro β.

    Retorna
    -------
    Array1D
        Curva de degradación del módulo G/Gmax evaluada en el rango
        de deformaciones definido por STRAIN_RANGE.
    """
    a = np.clip(a, MIN_A, None)

    beta = model._calcular_beta_ref(
        gg_ref, d, a, mu, gamma_ref, gamma_t, tau_max, G_max
    )

    tau_mkz = _calcular_tau_mkz(gamma_ref, beta, s, G_max)
    tau_fkz = _calcular_tau_fkz(mu, d, tau_max, G_max)

    omega = _calcular_omega_hh(gamma_t, a)

    tau_hh = omega * tau_mkz + (1 - omega) * tau_fkz

    gg_model = tau_hh / (STRAIN_RANGE * G_max)
    gg_model = np.clip(gg_model, MIN_FLOAT, 1.0)

    return gg_model


def _calcular_tau_mkz(gamma_ref: float, beta: float, s: float, G_max: float) -> Array1D:

    x = STRAIN_RANGE / gamma_ref
    x = np.clip(x, MIN_FLOAT, MAX_FLOAT)

    mkz_den = 1 + beta * np.power(x, s)
    mkz_den = np.clip(mkz_den, MIN_FLOAT, MAX_FLOAT)

    tau_mkz = (G_max * STRAIN_RANGE) / mkz_den

    return tau_mkz


def _calcular_tau_fkz(mu: float, d: float, tau_max: float, G_max: float) -> Array1D:

    gamma_d = np.power(STRAIN_RANGE, d)
    num = gamma_d * mu
    den = (1 / G_max) + (num / tau_max)
    den = np.clip(den, MIN_FLOAT, MAX_FLOAT)

    tau_fkz = num / den

    return tau_fkz


def _calcular_omega_hh(gamma_ref: float, a: float) -> Array1D:

    ratio = np.clip(STRAIN_RANGE / gamma_ref, MIN_FLOAT, MAX_FLOAT)
    log_ratio = np.log10(ratio)

    shift = 4.039 * np.power(a, -1.036)
    exp_term = -a * (log_ratio - shift)

    z = exp_term * np.log(10)

    z = np.clip(z, -EXP_LIMIT, EXP_LIMIT)

    omega = 1 / (1 + np.exp(-z))
    return omega
