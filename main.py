import uuid
import numpy as np

from scripts.exec_calibration_gqh import calculate_calibration
from scripts.exec_seismo_response import execute_response_analysis
from dev.dev_seismo_response import execute_modified_response_analysis

# def test_calculate_calibration():
#     general_params = {"G_max": 5.0e6, "tau_max": 1.0e5}

#     base_params_gqh = {
#         "theta_1": 0.05,
#         "theta_2": 0.23,
#         "theta_3": 0.62,
#         "theta_4": 0.71,
#         "theta_5": 1.00,
#     }
    
#     modelo = "0" # 0 gqh: 0 y mkz: 1

#     calibrate_params_hh = calculate_calibration(general_params, base_params_gqh, modelo)

#     # =========================================================================
#     print(
#         f"gamma_t={general_params['gamma_ref']:.3e} \n a = {calibrate_params_hh['a']:.2e} \n gamma_ref={general_params['gamma_ref']:.3e}"
#     )
#     print(
#         f"beta = {calibrate_params_hh['beta']:.2e} \n s = {calibrate_params_hh['s']:.2e} \n G_max={general_params['G_max']:.2e}"
#     )
#     print(
#         f"mu = {calibrate_params_hh['mu']:.2e} \n tau_max={general_params['tau_max']:.2e} \n d = {calibrate_params_hh['d']:.2e}"
#     )
#     # =========================================================================

# ==================================================

def test_seismo_response():
    base_session = "sesion_20250309_C4_tarapaca_ns"

    short_id = uuid.uuid4().hex[:4]
    session_name = f"{base_session}_{short_id}"

    simulation = ["2"]  # 0: Lineal, 1: Lineal equivalente y 2: No lineal.
    boundary = "0"  # 0: Elastico y 1: Rigido.
    execute_response_analysis(base_session, session_name, simulation, boundary)

# ==================================================

# def test_modified_seismo_response():
#     base_session = "sesion_20260304_140400_ew"

#     short_id = uuid.uuid4().hex[:4]
#     session_name = f"{base_session}_{short_id}"

#     vs_profile = {
#         "thickness": [5, 5, 0],
#         "vs": [250, 350, 760],
#         "damping": [0.02, 0.01, 0.005],
#         "density": [1834, 1936, 2446],
#         "material": [1,2,0]
#     }
#     dynamic_curves = np.array([
#         [0.0001, 1.00, 0.0001, 0.5,  0.0001, 1.00, 0.0001, 0.6],
#         [0.001 , 0.95, 0.001 , 1.0,  0.001 , 0.96, 0.001 , 1.2],
#         [0.01  , 0.80, 0.01  , 2.5,  0.01  , 0.82, 0.01  , 2.8],
#         [0.1   , 0.50, 0.1   , 5.0,  0.1   , 0.52, 0.1   , 5.5],
#     ])
#     #dynamic_parameters = 

#     simulation = ["1", "2"]  # 0: Lineal, 1: Lineal equivalente y 2: No lineal.
#     boundary = "0"  # 0: Elastico y 1: Rigido.
#     execute_modified_response_analysis(base_session, session_name, simulation, vs_profile, dynamic_curves, boundary)


if __name__ == "__main__":
    test_seismo_response()
