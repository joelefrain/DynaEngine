from bayes_opt import BayesianOptimization
import numpy as np

from modules.dynamic_curves.helper_calibration_gqh import (
    GQHModelFormulation,
    BackboneWrapper,
)
from modules.dynamic_curves.class_cost_function import (
    GGmaxCalibrationCost,
    DampingCalibrationCost,
)
from modules.calibration_curves.class_nomasing_mrdf_rules import MRDFNoMasingRules

from libs.config.config_variables import (
    LIMIT_CALIBRATED_GQH,
    LIMIT_CALIBRATED_MRDF,
    MAX_FLOAT,
)

from libs.config.config_logger import get_logger
from libs.config.config_logger import log_execution_time

CURVE_KEYS = ["strain", "ggmax", "damp"]

logger = get_logger()


class CalibrationCurve:
    """
    Módulo util para la calibración de curvas dinámicas utilizando el modelo GQH.

    El módulo proporciona herramientas para calibrar los parámetros del modelo GQH
    (Generalized Quadratic Hyperbolic) utilizando la optimización bayesiana,
    permitiendo ajustar las curvas de módulo de corte normalizado.

    Parameters
    ----------
    curve_data : dict[str : List]
        Información de las curvas de degradación de módulo de corte y amortiguamiento
        en formato de diccionario que se utilizará como patrón para calibrar los
        parámetros del modelo GQH.

        Ejemplo:
            curve_data = {
                'strain': [0.001, 0.01, ... , 0.1, 1.0],  # shape: (n,1)
                'ggmax': [0.99, 0.95, ... ,0.80, 0.50],   # shape: (n,1)
                'damp': [0.5, 1.0, ... ,3.0, 8.0]         # shape: (n,1)
            }

    ggmax_calibration : bool | True
        Variable que permite conocer si se realizará la calibración en la curva
        dinámica normalizada de degradación de módulo de corte.
    damping_calibration : bool | False
        Variable que permite conocer si se realizará la calibración en la curva
        dinámica de amortiguamiento.

    Attributes
    ----------
    strain: np.ndarray
        Valores de deformación cortante.
        Array 1D.
    ggmax: np.ndarray
        Valores de degradación de módulo de corte.
        Array 1D con valores entre 0 y 1.
    damping: np.ndarray
        Valores de amortiguamiento.
        Array 1D.
    ggmax_calibration
        Similar al parámetro input.
    damping_calibration
        Similar al parámetro input.
    cost_function_ggmax
        ###

    Raises
    ------
    TypeError
        Cuando los inputs tienen un tipo no valido.
    KeyERROR
        Cuando en los inputs no existen la llaves necesarias para el procesamiento.
    ValueError
        Cuando los inputs tienen valores en dimensiones no válidas.

    """

    def __init__(
        self,
        curve_data: dict,
        gmax_pa: float,
        tau_max_pa: float,
        b: float,
        ggmax_calibration: bool = True,
        damping_calibration: bool = False,
    ) -> None:

        if not isinstance(curve_data, dict):
            raise TypeError("El input curve_data no es del tipo diccionario.")

        if not all(k in curve_data for k in CURVE_KEYS):
            raise KeyError(
                f"Faltan llaves: {[k for k in CURVE_KEYS if k not in curve_data]}"
            )

        if np.any(curve_data[CURVE_KEYS[1]] > 1):
            raise ValueError("Existen valores de ggmax mayores a 1")

        self.b = b

        self.strain = np.asarray(curve_data[CURVE_KEYS[0]], dtype=float)
        self.ggmax = np.asarray(curve_data[CURVE_KEYS[1]], dtype=float)
        self.damping = np.asarray(curve_data[CURVE_KEYS[2]], dtype=float)

        self.ggmax_calibration = ggmax_calibration
        self.damping_calibration = damping_calibration

        self.tau_max_pa = tau_max_pa
        self.gmax_pa = gmax_pa
        idxs = np.where(self.ggmax <= 0.5)[0]
        if len(idxs) > 0:
            self.gamma_ref = self.strain[idxs[0]]
        else:
            self.gamma_ref = np.median(self.strain)

        self.cost_function_ggmax = GGmaxCalibrationCost(0, b)
        self.cost_function_damp = DampingCalibrationCost()

    def gqh_calibration(self):

        logger.info("Calibración QGH inicializada")

        def objective(theta_1, theta_2, theta_3, theta_5):

            if theta_1 + theta_2 > 1:
                return -MAX_FLOAT

            params = {
                "theta_1": theta_1,
                "theta_2": theta_2,
                "theta_3": theta_3,
                "theta_4": 1.0,
                "theta_5": theta_5,
            }

            try:
                model = GQHModelFormulation(params)

                GG_model = model.GGmax_model(self.strain, self.gamma_ref)

                error = self.cost_function_ggmax.compute(self.ggmax, GG_model)

                return -error

            except Exception as e:
                logger.warning(f"Error de cálculo en la calibración bayesiana; \n {e}")
                return -MAX_FLOAT

        optimizer = BayesianOptimization(
            f=objective, pbounds=LIMIT_CALIBRATED_GQH, random_state=1, verbose=0
        )

        optimizer.maximize(init_points=15, n_iter=100)

        return optimizer.max

    def compute_gqh_curve(self, params):
        parametros = {
            "theta_1": params["theta_1"],
            "theta_2": params["theta_2"],
            "theta_3": params["theta_3"],
            "theta_4": 1.0,
            "theta_5": params["theta_5"],
        }

        model = GQHModelFormulation(parametros)

        GG_model = model.GGmax_model(self.strain, self.gamma_ref)

        return GG_model

    def mrdf_calibration(self, best_gqh_params):
        logger.info("Calibración MRDF inicializada")

        gqh_model = GQHModelFormulation(
            {
                "theta_1": best_gqh_params["theta_1"],
                "theta_2": best_gqh_params["theta_2"],
                "theta_3": best_gqh_params["theta_3"],
                "theta_4": 1.0,
                "theta_5": best_gqh_params["theta_5"],
            }
        )

        def objective(P1, P2, P3, Dmin):
            params = {
                "P1": P1,
                "P2": P2,
                "P3": P3,
                "Dmin": Dmin,
            }

            backbone = BackboneWrapper(gqh_model, self.gmax_pa, self.tau_max_pa)

            model = MRDFNoMasingRules(backbone, params)

            damp_mrdf = model._compute_damping_vectorized(self.strain)

            real = self.damping
            model_d = damp_mrdf

            if np.any(model_d <= 0):
                return -MAX_FLOAT

            error = self.cost_function_damp.compute(real, model_d, self.strain)

            return -error

        optimizer = BayesianOptimization(
            f=objective, pbounds=LIMIT_CALIBRATED_MRDF, random_state=1, verbose=0
        )

        optimizer.maximize(init_points=15, n_iter=100)

        return optimizer.max

    def compute_mrdf_curve(self, best_gqh_params, mrdf_params):

        gqh_model = GQHModelFormulation(
            {
                "theta_1": best_gqh_params["theta_1"],
                "theta_2": best_gqh_params["theta_2"],
                "theta_3": best_gqh_params["theta_3"],
                "theta_4": 1.0,
                "theta_5": best_gqh_params["theta_5"],
            }
        )

        backbone = BackboneWrapper(gqh_model, self.gmax_pa, self.tau_max_pa)

        model = MRDFNoMasingRules(backbone, mrdf_params)

        damping_curve = np.array(
            [model.compute_damping(gamma) for gamma in self.strain]
        )

        return damping_curve


@log_execution_time
def execute_calibration(dynamic_data, Gmax_pa, tau_max_pa, b: float = 1):
    """
    Funcion útil para realizar una calibración hacia una curva dinámica objetivo.
    Se reutiliza muchas veces en el archivo multicalibration.

    """

    calibration = CalibrationCurve(dynamic_data, Gmax_pa, tau_max_pa, b)
    gqh_params = calibration.gqh_calibration()

    best_gqh_params = gqh_params["params"]

    print("Parámetros GQH calibrados:")
    print(best_gqh_params)

    # La idea es que MRDF me genere los mejores parámetros en una función
    mrdf_params = calibration.mrdf_calibration(best_gqh_params)
    best_mrdf_params = mrdf_params["params"]

    print("Parámetros MRDF calibrados:")
    print(best_mrdf_params)

    GG_model = calibration.compute_gqh_curve(best_gqh_params)
    GG_exp = np.array(dynamic_data["ggmax"])

    D_model = calibration.compute_mrdf_curve(best_gqh_params, best_mrdf_params)
    D_exp = np.array(dynamic_data["damp"])

    data_calibration = {
        "GG_exp": GG_exp,
        "GG_model": GG_model,
        "D_exp": D_exp,
        "D_model": D_model,
        "theta": best_gqh_params,
        "p": best_mrdf_params,
        "dmin": best_mrdf_params["Dmin"],
    }

    return data_calibration
