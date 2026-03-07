from pathlib import Path

import numpy as np

from libs.config.config_variables import STORAGE_DIR, UNIT_GROUND_MOTION

from libs.config.config_logger import get_logger, log_execution_time
from modules.seismo_response.class_ground_motion import Ground_Motion
from modules.seismo_response.class_Vs_profile import Vs_Profile
from modules.seismo_response.class_curves import (
    Multiple_GGmax_Damping_Curves,
    HH_Param_Multi_Layer,
)

from modules.seismo_response.class_simulation import (
    Linear_Simulation,
    Equiv_Linear_Simulation,
    Nonlinear_Simulation,
)

BOUNDARY_TYPE = {"0": "elastic", "1": "rigid"}
SIMULATION_TYPE = {"0": "linear", "1": "linear_equivalent", "2": "no_linear"}
ACCEL_FNAME = "input_accel.txt"
VS_PROFILE_FNAME = "vs_profile.txt"
DINAMIC_CURVES_FNAME = "dynamic_curves.txt"
PARAMETERS_HH_FNAME = "curve_parameters_hh.txt"

logger = get_logger()


class InputData:
    def __init__(self, session_name, vs_profile, dynamic_curves):

        self.session = session_name

        self.raw_data_dir = STORAGE_DIR / "raw_data" / self.session

        self.perfil = vs_profile
        self.dynamic_curves = dynamic_curves

        self.seismic_path = self.raw_data_dir / ACCEL_FNAME
        self.parameters_hh_path = self.raw_data_dir / PARAMETERS_HH_FNAME

    def _check_file_exists(self, path):
        if not path.exists():
            raise FileNotFoundError(f"Los archivos ingresados no existen:\n{path}")

    def validate_all_inputs(self):
        self._check_file_exists(self.seismic_path)
        self._check_file_exists(self.parameters_hh_path)

    def input_ground_motion(self):
        logger.info("Inicio de lectura de sismos")

        InputValidator.validate_ground_motion(self.seismic_path)

        return Ground_Motion(data=str(self.seismic_path), unit=UNIT_GROUND_MOTION)

    def input_vs_profile(self):
        logger.info("Inicio lectura de perfil de velocidades")
        data = np.column_stack(list(self.perfil.values()))

        amount_vs_rows = data.shape[0]

        return Vs_Profile(data), amount_vs_rows

    def input_dynamic_curves(self, amount_vs_rows: int):
        logger.info("Inicio de lectura de curvas dinámicas")

        #InputValidator.validate_dynamic_curves(self.dynamic_curves, amount_vs_rows)

        return Multiple_GGmax_Damping_Curves(data=self.dynamic_curves)

    def input_parameters_hh(self):
        return str(self.parameters_hh_path)


class InputValidator:
    @staticmethod
    def load_file(path: Path) -> np.ndarray:
        try:
            return np.loadtxt(path)
        except ValueError:
            raise ValueError(f"El archivo '{path}' no tiene formato numérico válido")

    @staticmethod
    def _validate_2d(data: np.ndarray):
        if data.ndim != 2:
            raise ValueError("El archivo debe contener filas y columnas numéricas")

    @staticmethod
    def _validate_non_empty(data: np.ndarray):
        if data.shape[0] == 0:
            raise ValueError("No se encontraron filas válidas en el archivo")

    @staticmethod
    def _validate_no_nan(data: np.ndarray):
        if np.isnan(data).any():
            raise ValueError("Existen valores faltantes en el archivo")

    @staticmethod
    def _validate_columns(data: np.ndarray, expected: int):
        if data.shape[1] != expected:
            raise ValueError(
                f"El archivo debe tener exactamente {expected} columnas. "
                f"Se encontraron {data.shape[1]}"
            )

    @staticmethod
    def _validate_vs_last_row(data: np.ndarray):
        last_row = data[-1]

        if last_row[0] != 0:
            raise ValueError("La última fila debe tener 0 en la primera columna")

        if last_row[4] != 0:
            raise ValueError("La última fila debe tener 0 en la quinta columna")

    @staticmethod
    def validate_boundary_conditions(boundary_case):
        if len(boundary_case) > 1:
            logger.warning("Modificar, se permite una condición de borde")
            raise ValueError("No se puede continuar")

    @staticmethod
    def validate_ground_motion(path: Path) -> None:
        data = InputValidator.load_file(path)

        InputValidator._validate_2d(data)
        InputValidator._validate_non_empty(data)
        InputValidator._validate_no_nan(data)

        InputValidator._validate_columns(data, expected=2)

    @staticmethod
    def validate_vs_profile(data: np.ndarray) -> None:
        InputValidator._validate_2d(data)
        InputValidator._validate_non_empty(data)
        InputValidator._validate_no_nan(data)

        InputValidator._validate_columns(data, expected=5)
        InputValidator._validate_vs_last_row(data)

    @staticmethod
    def validate_dynamic_curves(path: Path, vs_rows: int) -> None:
        data = InputValidator.load_file(path)

        InputValidator._validate_2d(data)
        InputValidator._validate_non_empty(data)
        InputValidator._validate_no_nan(data)

        expected_cols = 4 * (vs_rows - 1)
        InputValidator._validate_columns(data, expected=expected_cols)


class SimulationExecuter:
    @staticmethod
    def execute_simulation(
        simulation_type,
        vs_profile,
        ground_motion,
        dynamic_curves=None,
        parameters_hh=None,
        boundary="elastic",
        base_session=None,
    ):

        match simulation_type:
            case "0":
                return Linear_Simulation(vs_profile, ground_motion, boundary=boundary)

            case "1":
                if dynamic_curves is None:
                    logger.warning("Es necesario colocar curvas dinámicas")
                    raise ValueError("No se puede continuar")
                return Equiv_Linear_Simulation(
                    vs_profile, ground_motion, dynamic_curves, boundary=boundary
                )

            case "2":
                hh_g_param = HH_Param_Multi_Layer(parameters_hh, sep="\t")
                return Nonlinear_Simulation(
                    vs_profile,
                    ground_motion,
                    G_param=hh_g_param,
                    xi_param=hh_g_param,
                    boundary=boundary,
                )

            case _:
                raise ValueError(f"Tipo de simulación no válido: {simulation_type}")


class ResultManager:
    def __init__(self, session_name, simulation_case: str, boundary_case: str):
        result_name = (
            f"{SIMULATION_TYPE[simulation_case]}_{BOUNDARY_TYPE[boundary_case]}"
        )

        self.output_path = STORAGE_DIR / "output" / session_name
        self.simulation_output_path = self.output_path / result_name

    def create_simulation_files(self):
        """
        Crea carpeta de sesión y carpeta de tipo de simulación.
        """
        self.simulation_output_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Estructura de salida creada:\n {self.simulation_output_path}")

    def save_results(self, response):
        self.create_simulation_files()
        response.to_txt(output_dir=self.simulation_output_path)

        logger.info("Resultados guardados correctamente.")


@log_execution_time
def execute_modified_response_analysis(
    base_session, session_name, simulation_case, vs_profile, dynamic_curves, boundary_case
):
    input_data = InputData(
        session_name = base_session,
        vs_profile = vs_profile,
        dynamic_curves = dynamic_curves
    )

    input_data.validate_all_inputs()

    ground_motion = input_data.input_ground_motion()
    vs_profile, vs_rows = input_data.input_vs_profile()
    parameters_hh = input_data.input_parameters_hh()
    dynamic_curves = input_data.input_dynamic_curves(vs_rows)

    InputValidator.validate_boundary_conditions(boundary_case)
    for sim_case in simulation_case:
        simulation = SimulationExecuter.execute_simulation(
            sim_case,
            vs_profile,
            ground_motion,
            dynamic_curves,
            parameters_hh,
            BOUNDARY_TYPE[boundary_case],
            base_session,
        )
        response = simulation.run()

        result_manager = ResultManager(
            session_name,
            sim_case,
            boundary_case,
        )
        result_manager.save_results(response)
