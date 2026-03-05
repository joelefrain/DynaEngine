import uuid

from scripts.exec_calibration_gqh import calculate_calibration
from scripts.exec_seismo_response import execute_response_analysis

def test_calculate_calibration():
    general_params = {"gamma_ref": 1.0e-3, "G_max": 5.0e6, "tau_max": 1.0e5}

    base_params_gqh = {
        "theta_1": 0.05,
        "theta_2": 0.23,
        "theta_3": 0.62,
        "theta_4": 0.71,
        "theta_5": 1.00,
    }
    
    modelo = "0" # 0 gqh: 0 y mkz: 1

    calibrate_params_hh = calculate_calibration(general_params, base_params_gqh, modelo)

    # =========================================================================
    print(
        f"Parámetros generales: | gamma_ref={general_params['gamma_ref']:.3e} | GGmax_ref={general_params['gg_ref']} | G_max={general_params['G_max']:.2e} | tau_max={general_params['tau_max']:.2e}"
    )
    print(
        f"base_params ingresados GQH: | θ_1={base_params_gqh['theta_1']:.2e} | θ_2={base_params_gqh['theta_2']:.2e} | θ_3={base_params_gqh['theta_3']:.2e} | θ_4={base_params_gqh['theta_4']:.2e} | θ_5={base_params_gqh['theta_5']:.2e}"
    )
    print(
        f"Parámetros óptimos HH: | s = {calibrate_params_hh['s']:.2e} | d = {calibrate_params_hh['d']:.2e} | mu = {calibrate_params_hh['mu']:.2e} | a = {calibrate_params_hh['a']:.2e} | beta = {calibrate_params_hh['beta']:.2e}"
    )
    # =========================================================================

def test_seismo_response():
    base_session = "sesion_20260304_140400_ew"

    short_id = uuid.uuid4().hex[:4]
    session_name = f"{base_session}_{short_id}"

    simulation = ["1", "2"]  # 0: Lineal, 1: Lineal equivalente y 2: No lineal.
    boundary = "0"  # 0: Elastico y 1: Rigido.
    execute_response_analysis(base_session, session_name, simulation, boundary)