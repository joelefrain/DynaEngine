import numpy as np
from libs.config.config_logger import get_logger

logger = get_logger()


class ShearVelocity:
    """
    Recibe una dos listas (profundidad y vs_array) para definirse.
    """

    def __init__(self, depth: list, shear_velocity: list) -> None:
        if not len(depth) == len(shear_velocity):
            raise ValueError("Profundidad y vs deben tener el mismo tamaño")

        self.depth = depth
        self.shear_velocity = shear_velocity


def compute_layer_vs(
    prof_mat_depth: list, vs_mat_depth: list, z_top: float, z_bottom: float
):
    """
    Calcula los vs como un promedio armonico
    """
    vs_list_validator(prof_mat_depth, vs_mat_depth, z_top, z_bottom)

    depth_array = np.array(prof_mat_depth)
    vs_array = np.array(vs_mat_depth)

    cut_depths = [z_top]

    for p in depth_array:
        if z_top < p < z_bottom:
            cut_depths.append(p)

    cut_depths.append(z_bottom)
    cut_depths = np.array(cut_depths)

    vs_cut = np.array([_get_vs(z, depth_array, vs_array) for z in cut_depths])

    layer_thickness = cut_depths[1:] - cut_depths[:-1]

    vs_target = (z_bottom - z_top) / np.sum(layer_thickness / vs_cut[:-1])

    if vs_target > np.max(vs_array):
        logger.warning(
            f"vs_target={vs_target:.2f} excede el máximo vs del perfil={np.max(vs_array):.2f}."
        )
    elif vs_target < np.min(vs_array):
        logger.warning(
            f"vs_target={vs_target:.2f} es menor que el mínimo vs del perfil={np.min(vs_array):.2f}."
        )

    return vs_target


def _get_vs(z: float, depth_array: np.array, vs_array: np.array):
    for i in range(len(depth_array) - 1):
        if depth_array[i] <= z < depth_array[i + 1]:
            return vs_array[i]
    return vs_array[-1]


def vs_list_validator(
    prof_mat_depth: list, vs_mat_depth: list, z_top: float, z_bottom: float
):
    if not len(prof_mat_depth) == len(vs_mat_depth):
        raise ValueError("La lista de vs_array y depth_array deben ser iguales")
    if not z_top < z_bottom:
        raise ValueError("Error en el orden de profundidades")
    if not all(
        prof_mat_depth[i] < prof_mat_depth[i + 1]
        for i in range(len(prof_mat_depth) - 1)
    ):
        raise ValueError("prof_mat_depth debe estar en orden creciente")
