import numpy as np
from pathlib import Path


class ParameterLoader:

    def __init__(self, parameter_file):
        self.parameter_file = Path(parameter_file)
        self.data = self._load_data()

    def _load_data(self):

        data = np.loadtxt(self.parameter_file)

        # Soporte para una sola columna
        if data.ndim == 1:
            data = data.reshape(-1, 1)

        if data.shape[0] != 8:
            raise ValueError(
                "El archivo debe contener exactamente 8 filas de parámetros."
            )

        return data

    @staticmethod
    def _build_param_dict(column):

        general_params = {
            "gamma_ref": column[0],
            "G_max": column[1],
            "tau_max": column[2],
        }

        base_params_gqh = {
            "theta_1": column[3],
            "theta_2": column[4],
            "theta_3": column[5],
            "theta_4": column[6],
            "theta_5": column[7],
        }

        return general_params, base_params_gqh

    def get_all_sets(self):

        sets = []

        n_sets = self.data.shape[1]

        for i in range(n_sets):
            column = self.data[:, i]
            general_params, base_params_gqh = self._build_param_dict(column)

            sets.append(
                {
                    "set_number": i + 1,
                    "general_params": general_params,
                    "base_params_gqh": base_params_gqh,
                }
            )

        return sets