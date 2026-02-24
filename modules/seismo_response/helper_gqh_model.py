from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from modules.seismo_response import helper_generic as hlp
from modules.seismo_response import helper_site_response as sr

# Modificar las funciones:
# - tau_MKZ (no estoy considerando influencia del agua aún puede generarse después)
# - damping_misfit (revisar informacion de como ajusta las curvas - NO AFECTA)
# - serialize_params_to_array (OK)
# - deserialize_array_to_params (OK)

def tau_GQH(
        gamma: np.ndarray,
        *,
        gamma_ref: float,
        theta_1: float,
        theta_2: float,
        theta_3: float = 1,
        theta_4: float = 1,
        theta_5: float,
        Gmax: float,
) -> np.ndarray:
    """
    Calculate the GQ/H shear stress. The GQ/H model is proposed in Groholski et al.
    (2016), and has the following form::

                                                              2 * Gmax * gamma
        T(gamma) = ---------------------------------------------------------------------------------------------------
                      1 + (gamma / gamma_ref) + ([1 + (gamma / gamma_ref)]^2 - 4 * theta_T (gamma / gamma_ref))^0.5

    where:
        + T         = shear stress
        + gamma     = shear strain
        + Gmax      = initial shear modulus
        + theta_tau      = a shape parameter of the MKZ model
        + gamma_ref = reference strain, another shape parameter of the MKZ model

                                                    theta_4 * (gamma / gamma_ref)^(theta_5)
        theta_T = theta_1 + theta_2 * ----------------------------------------------------------------
                                            theta_3^(theta_5) + theta_4 * (gamma / gamma_ref)^(theta_5)

    where:
        + theta_1   = shape parameter
        + theta_2   = shape parameter
        + theta_3   = shape parameter (set: 1)
        + theta_4   = shape parameter (set: 1)
        + theta_5   = shape parameter

    Parameters
    ----------
    gamma : np.ndarray
        The shear strain array. Must be a 1D array. Its unit should be '1',
        rather than '%'.
    gamma_ref : float
        Reference shear strain, a shape parameter of the MKZ model. Unit: 1.
    theta_1 : float
        A shape parameter of the GQ/H model.
    theta_2 : float
        A shape parameter of the GQ/H model.
    theta_3 : float
        A shape parameter of the GQ/H model.
    theta_4 : float
        A shape parameter of the GQ/H model.
    theta_5 : float
        A shape parameter of the GQ/H model.
    Gmax : float
        Initial shear modulus. Its unit can be arbitrary, but we recommend Pa.

    Returns
    -------
    T_GQH : np.ndarray
        The shear stress determined by the formula above. Same shape as ``x``,
        and same unit as ``Gmax``.
    """
    hlp.assert_1D_numpy_array(gamma, name='`gamma`')
    
    frac_upper = theta_4 * (gamma / gamma_ref)**theta_5
    frac_lower = theta_3**theta_5 + theta_4*(gamma / gamma_ref)**theta_5
    theta_T = theta_1 + theta_2 * (frac_upper / frac_lower)

    sqrt_argument = (1 + gamma/gamma_ref)**2 - 4 * theta_T * (gamma / gamma_ref)
    T_GQH = 2 * Gmax * gamma / [1 + (gamma / gamma_ref) + sqrt_argument **0.5]

    return T_GQH


def fit_H4_x_single_layer(
        damping_data_in_pct: np.ndarray,
        *,
        use_scipy: bool = True,
        pop_size: int = 800,
        n_gen: int = 100,
        lower_bound_power: float = -4,
        upper_bound_power: float = 6,
        eta: float = 0.1,
        seed: int = 0,
        show_fig: bool = False,
        verbose: bool = False,
        suppress_warnings: bool = True,
        parallel: bool = False,
        n_cores: int | None = None,
) -> dict[str, float]:
    """
    Perform H4_x curve fitting for one damping curve using the genetic
    algorithm.

    Parameters
    ----------
    damping_data_in_pct : np.ndarray
        Damping data. Needs to have 2 columns (strain and damping ratio). Both
        columns need to use % as unit.
    use_scipy : bool
        Whether to use the "differential_evolution" algorithm in scipy
        (https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.differential_evolution.html)
        to perform the optimization. If ``False``, use the algorithm in the
        DEAP package.
    pop_size : int
        The number of individuals in a generation. A larger number leads to
        potentially better curve-fitting, but a longer computing time.
    n_gen : int
        Number of generations that the evolution lasts. A larger number leads
        to potentially better curve-fitting, but a longer computing time.
    lower_bound_power : float
        The 10-based power of the lower bound of all the 9 parameters. For
        example, if your desired lower bound is 0.26, then set this parameter
        to be numpy.log10(0.26).
    upper_bound_power : float
        The 10-based power of the upper bound of all the 9 parameters.
    eta : float
        Crowding degree of the mutation or crossover. A high ``eta`` will produce
        children resembling to their parents, while a low ``eta`` will produce
        solutions much more different.
    seed : int
        Seed value for the random number generator.
    show_fig : bool
        Whether to show the curve fitting results as a figure.
    verbose : bool
        Whether to display information (statistics of the loss in each
        generation) on the console.
    suppress_warnings : bool
        Whether to suppress warning messages. For this particular task,
        overflow warnings are likely to occur.
    parallel : bool
        Whether to use multiple processors in the calculation. All CPU cores
        will be used if set to ``True``.
    n_cores : int | None
        The number of CPU cores to use in the curve fitting

    Return
    ------
    best_param : dict[str, float]
        The best parameters found in the optimization.
    """
    hlp.check_two_column_format(damping_data_in_pct, ensure_non_negative=True)

    init_damping = damping_data_in_pct[0, 1]  # small-strain damping
    damping_data_in_pct[:, 1] -= init_damping  # offset all dampings
    damping_data_in_unit_1 = damping_data_in_pct / 100  # unit: percent --> 1

    n_param = 6  # number of GQH model parameters; do not change this
    N = 122  # denser strain array for more accurate damping calculation
    strain_dense = np.logspace(-6, -1, N)
    damping_dense = np.interp(
        strain_dense,
        damping_data_in_unit_1[:, 0],
        damping_data_in_unit_1[:, 1],
    )

    damping_data_ = np.column_stack((strain_dense, damping_dense))

    crossover_prob = 0.8  # hard-coded, because not much useful to tune them
    mutation_prob = 0.8

    result = sr.ga_optimization(
        n_param,
        lower_bound_power,
        upper_bound_power,
        damping_misfit,
        damping_data_,
        use_scipy=use_scipy,
        pop_size=pop_size,
        n_gen=n_gen,
        eta=eta,
        seed=seed,
        crossover_prob=crossover_prob,
        mutation_prob=mutation_prob,
        suppress_warnings=suppress_warnings,
        verbose=verbose,
        parallel=parallel,
        n_cores=n_cores,
    )

    best_param = {}
    best_param['gamma_ref'] = 10 ** result[0]
    best_param['theta_1'] = 10 ** result[1]
    best_param['theta_2'] = 10 ** result[2]
    best_param['theta_3'] = 10 ** result[3]
    best_param['theta_4'] = 10 ** result[4]
    best_param['theta_5'] = 10 ** result[5]
    best_param['Gmax'] = 1.0

    if show_fig:
        sr._plot_damping_curve_fit(damping_data_in_pct, best_param, tau_GQH)

    return best_param

# Estoy utilizando parámetros diferentes al MKZ (¿El código seguirá funcionando?)
def damping_misfit(
        param_without_Gmax: tuple[float, float, float, float, float, float],
        damping_data: np.ndarray,
) -> float:
    """
    Calculate the misfit given a set of GQH parameters. Note that the values
    in `param` are actually the 10-based power of the actual GQH parameters.
    Using the powers in the genetic algorithm searching turns out to work
    much better for this particular problem.

    Parameters
    ----------
    param_without_Gmax : tuple[float, float, float, float, float, float]
        GQH model parameters, in the order specified below:
            gamma_ref, theta_1, theta_2, theta_3, theta_4, theta_5
    damping_data : np.ndarray
        2D numpy array with two columns (strain and damping value). Both
        columns need to use "1" as the unit, not percent.

    Returns
    -------
    error : float
        The mean absolute error between the true damping values and the
        predicted damping values at each strain level.
    """
    gamma_ref_, theta_1_, theta_2_, theta_3_, theta_4_, theta_5_ = param_without_Gmax

    gamma_ref = 10**gamma_ref_
    theta_1 = 10**theta_1_
    theta_2 = 10**theta_2_
    theta_3 = 10**theta_3_
    theta_4 = 10**theta_4_
    theta_5 = 10**theta_5_

    Gmax = 1.0  # does not affect damping, because it gets cancels out

    strain = damping_data[:, 0]
    damping_true = damping_data[:, 1]

    Tau_MKZ = tau_GQH(strain, 
                      gamma_ref=gamma_ref, 
                      theta_1=theta_1, 
                      theta_2=theta_2, 
                      theta_3=theta_3, 
                      theta_4=theta_4, 
                      theta_5=theta_5, 
                      Gmax=Gmax
                      )
    damping_pred = sr.calc_damping_from_stress_strain(strain, Tau_MKZ, Gmax)
    error = hlp.mean_absolute_error(damping_true, damping_pred)

    return error


def serialize_params_to_array(
        param: dict[str, float],
        to_files: bool = False,
) -> np.ndarray:
    """
    Convert the GQH parameters from a dictionary to an array, according to this
    order:
        gamma_ref, theta_1, theta_2, theta_3, theta_4, theta_5, Gmax

    Parameters
    ----------
    param : dict[str, float]
        A dictionary containing the parameters of the GQH model.
    to_files : bool (REVISAR)
        Whether the result is for writing to files. If so, the last parameter,
        Gmax, is removed, and a dummy parameter, b, which is always 0, is
        inserted between gamma_ref and s. This is for historical reasons: the
        text files recognizable by MATLAB and Fortran functions have the
        convention of "gamma_ref, 0.0, s, beta".

    Returns
    -------
    param_array : np.ndarray
        A numpy array of shape (9,) containing the parameters of the GQH model
        in the order specified above.
    """
    assert len(param) == 7
    order = ['gamma_ref', 'theta_1', 'theta_2', 'theta_3', 'theta_4', 'theta_5', 'Gmax']
    param_array = []
    for key in order:
        param_array.append(param[key])

    if to_files:
        param_array = [param_array[0], 0.0, param_array[1], param_array[2], param_array[3], param_array[4], param_array[5]]

    return np.array(param_array)


def deserialize_array_to_params(
        array: np.ndarray,
        from_files: bool = False,
) -> dict[str, float]:
    """
    Reconstruct a GQH model parameter dictionary from an array of values.

    The users need to ensure the order of values in ``array`` are in this order:
        gamma_ref, theta_1, theta_2, theta_3, theta_4, theta_5, Gmax (if ``from_files`` is ``False``)
    or:
        gamma_ref, b, theta_1, theta_2, theta_3, theta_4, theta_5 (if ``from_files`` is ``True``)
    (b is always 0, for historical reasons)

    Parameters
    ----------
    array : np.ndarray
        A 1D numpy array of GQH parameter values in this order:
            gamma_ref, theta_1, theta_2, theta_3, theta_4, theta_5, Gmax
    from_files : bool
        Whether the array was directly imported from a "H4_x_SITE_NAME.txt"
        file. If so, the 1st (0-based indexing) element, "b", which is always
        0, is neglected, and a dummy Gmax value (1.0) is padded at the end. The
        presence of "b" is due to historical reasons.

    Returns
    -------
    param : dict[str, float]
        The dictionary with parameter name as keys and values as values.
    """
    hlp.assert_1D_numpy_array(array)
    assert len(array) == 7

    if from_files:
        param = {}
        param['gamma_ref'] = array[0]
        param['theta_1'] = array[2]
        param['theta_2'] = array[3]
        param['theta_3'] = array[4]
        param['theta_4'] = array[5]
        param['theta_5'] = array[6]

        param['Gmax'] = 1.0  # "H4_G_SITE_NAME.txt" files don't have Gmax info
    else:
        param = {}
        param['gamma_ref'] = array[0]
        param['theta_1'] = array[1]
        param['theta_2'] = array[2]
        param['theta_3'] = array[3]
        param['theta_4'] = array[4]
        param['theta_5'] = array[5]
        param['Gmax'] = array[6]

    return param


def fit_MKZ(
        curve_data: np.ndarray,
        show_fig: bool = False,
        verbose: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Fit GQH model to G/Gmax curves.

    Parameters
    ----------
    curve_data : np.ndarray
        A 2D numpy array that represents G/Gmax and damping curves of each
        layer, in the following format:
         +------------+--------+------------+-------------+-------------+--------+-----+
         | strain [%] | G/Gmax | strain [%] | damping [%] |  strain [%] | G/Gmax | ... |
         +============+========+============+=============+=============+========+=====+
         |    ...     |  ...   |    ...     |    ...      |    ...      |  ...   | ... |
         +------------+--------+------------+-------------+-------------+--------+-----+

        The damping information is neglected in this function, so users can
        supply some dummy values.
    show_fig : bool
        Whether to show curve-fitting results.
    verbose : bool
        Whether to show messages about the calculation progress on the console.

    Returns
    -------
    param : np.ndarray
        The fitted MKZ parameters. Shape: (n_mat, 4), where ``n_mat`` is
        the number of materials implied in ``curve_data``.
    fitted_curves : np.ndarray
        The fitted curves. Shape: (nr, 4 * n_mat), where ``nr`` is the length
        of the strain array. Currently hard-coded as 109.
    """
    from scipy.optimize import curve_fit

    hlp.assert_2D_numpy_array(curve_data, name='`curve_data`')

    nr = 109
    fitted_curves = np.zeros((nr, curve_data.shape[1]))

    n_ma = int(curve_data.shape[1] / 4.0)  # number of materials
    length = curve_data.shape[0]  # length of strain array

    ref_strain = np.zeros(n_ma)
    theta_1 = np.zeros(n_ma)
    theta_2 = np.zeros(n_ma)
    theta_3 = np.zeros(n_ma)
    theta_4 = np.zeros(n_ma)
    theta_5 = np.zeros(n_ma)

    gamma = np.zeros((length, n_ma))
    GGmax = np.zeros((length, n_ma))
    for k in range(n_ma):
        gamma[:, k] = curve_data[:, k * 4 + 0] / 100.0  # percent --> 1
        GGmax[:, k] = curve_data[:, k * 4 + 1]

    gamma_ = np.geomspace(1e-6, 0.1, num=nr)  # unit: 1
    GGmax_ = np.zeros((nr, n_ma))
    damping_ = np.zeros((nr, n_ma))

    # -------------- Curve-fitting, layer by layer -----------------------------
    def func(x, gamma_ref, theta_1, theta_2, theta_3, theta_4, theta_5):

        frac_upper = theta_4 * (x / gamma_ref)**theta_5
        frac_lower = theta_3**theta_5 + theta_4*(x / gamma_ref)**theta_5
        theta_T = theta_1 + theta_2 * (frac_upper / frac_lower)

        sqrt_argument = (1 + x/gamma_ref)**2 - 4 * theta_T * (x / gamma_ref)

        return 2 / [1 + (x / gamma_ref) + sqrt_argument **0.5]

    if verbose:
        print('Fitting GQH model to G/Gmax data. Total: %d layers.' % n_ma)

    for j in range(n_ma):
        if verbose:
            print('  Layer #%d' % j)

        x_data = gamma[:, j]
        y_data = GGmax[:, j]
        popt, _ = curve_fit(
            func,
            x_data,
            y_data,
            p0=[1, 0.005, 0.8],
            bounds=([0.2, 0, 0.6], [1.8, 0.1, 0.999]),
        )
        ref_strain[j] = popt[0]
        theta_1[j] = popt[1]
        theta_2[j] = popt[2]
        theta_3[j] = popt[3]
        theta_4[j] = popt[4]
        theta_5[j] = popt[5]

    param = np.column_stack((ref_strain, np.zeros(n_ma), theta_1, theta_2, theta_3, theta_4, theta_5))

    # ------------ Calculate the fitted curve ----------------------------------
    for k in range(n_ma):
        param_k = param[k, :]
        T_GQH = tau_GQH(
            gamma_,
            gamma_ref=param_k[0],
            theta_1=param_k[2],
            theta_2=param_k[3],
            theta_3=param_k[4],
            theta_4=param_k[5],
            theta_5=param_k[6],
            Gmax=1.0,
        )
        GGmax_k = sr.calc_GGmax_from_stress_strain(gamma_, T_GQH, Gmax=1.0)
        GGmax_[:, k] = GGmax_k

    # ------------ Plotting ----------------------------------------------------
    if show_fig:
        ncol = 4
        nrow = int(np.ceil(n_ma / ncol))
        plt.figure(figsize=(ncol * 3.5, nrow * 3))
        for k in range(n_ma):
            plt.subplot(nrow, ncol, k + 1)
            plt.semilogx(
                gamma[:, k] * 100,
                GGmax[:, k],
                ls='-',
                marker='o',
                lw=1.5,
                alpha=0.8,
                label='Data points',
            )
            plt.semilogx(
                gamma_ * 100,
                GGmax_[:, k],
                lw=1.5,
                label='Curve fit',
            )
            plt.xlabel('Shear strain [%]')
            plt.ylabel('G/Gmax')
            plt.legend(loc='lower left')
            plt.grid(ls=':', lw=0.5)
            plt.title(
                r'$\gamma_{\mathrm{ref}}$ = %.3g, theta_1 = %.3g, theta_2 = %.3g, theta_3 = %.3g, theta_4 = %.3g, theta_5 = %.3g'
                % (ref_strain[k], theta_1[k], theta_2[k], theta_3[k], theta_4[k], theta_5[k]),
            )
        # END FOR
        plt.tight_layout(pad=0.5, h_pad=0.5, w_pad=0.5)

    # ---------- Produce fitting curves ----------------------------------------
    for k in range(n_ma):
        fitted_curves[:, k * 4 + 0] = gamma_ * 100
        fitted_curves[:, k * 4 + 1] = GGmax_[:, k]
        fitted_curves[:, k * 4 + 2] = gamma_ * 100
        fitted_curves[:, k * 4 + 3] = damping_[:, k] * 100

    return param, fitted_curves
