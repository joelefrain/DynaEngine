import numpy as np


class MRDFNoMasingRules:
    """
    Modelo MRDF sin reglas de Masing (formulación cerrada tipo Groholski 2016).
    Compatible con calibración.
    """

    def __init__(self, backbone_model: object, mrdf_parameters: dict) -> None:

        self.backbone_model = backbone_model

        self.p1 = mrdf_parameters["P1"]
        self.p2 = mrdf_parameters["P2"]
        self.p3 = mrdf_parameters["P3"]
        self.D_min = mrdf_parameters["Dmin"]

        self.Gmax = backbone_model.gmax
        self.tau_max = backbone_model.tau_max
        self.gamma_ref = backbone_model.gamma_ref

    def _compute_mrdf(self, ggmax: float) -> float:

        return self.p1 - self.p2 * (1 - ggmax) ** self.p3

    def _compute_tau_backbone(self, gamma: np.ndarray) -> np.ndarray:

        gamma = np.atleast_1d(gamma)

        theta_tau = self.backbone_model.compute_theta_tau(
            np.abs(gamma), np.abs(gamma) / self.gamma_ref
        )

        tau = (self.tau_max * 2 * gamma / self.gamma_ref) / (
            1
            + gamma / self.gamma_ref
            + np.sqrt(
                (1 + gamma / self.gamma_ref) ** 2
                - 4 * theta_tau * gamma / self.gamma_ref
            )
        )

        return tau

    def compute_damping(self, gamma: float, n_points: int = 100) -> float:

        if gamma < 1e-8:
            return self.D_min

        tau_y = self._compute_tau_backbone(np.array([gamma]))[0]
        G_gamma = tau_y / gamma

        ggmax = G_gamma / self.Gmax

        F = self._compute_mrdf(ggmax)

        yc = np.linspace(-gamma, gamma, n_points)

        gamma_mid = (yc + gamma) / 2

        tau_backbone = self._compute_tau_backbone(gamma_mid)

        tc = (
            F * (2 * tau_backbone - G_gamma * (yc + gamma))
            + G_gamma * (yc + gamma)
            - tau_y
        )

        y_plot = np.concatenate((yc, yc[::-1]))
        t_plot = np.concatenate((tc, -tc))

        loop_area = np.trapz(t_plot, y_plot)
        loop_area = abs(loop_area)

        E_elastic = tau_y * gamma / 2

        if E_elastic < 1e-12:
            return self.D_min

        damping = loop_area / (4 * np.pi * E_elastic)

        return 100 * damping + self.D_min

    def _compute_damping_vectorized(self, gamma_array):
        return np.array([self.compute_damping(g) for g in gamma_array])
