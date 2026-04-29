import numpy as np
import matplotlib.pyplot as plt


class MasingRules:
    """ """

    def __init__(self, gamma: list, ggmax: list, Gmax: float = 1.0):

        self.gamma = np.array(gamma)
        self.ggmax = np.array(ggmax)
        self.Gmax = Gmax

    def build_tau(self):

        G = self.Gmax * self.ggmax
        tau = np.zeros_like(self.gamma)

        for i in range(1, len(self.gamma)):
            dgamma = self.gamma[i] - self.gamma[i - 1]
            tau[i] = tau[i - 1] + 0.5 * (G[i] + G[i - 1]) * dgamma

        return tau

    def damping_masing_clean(self):

        idx = np.argsort(self.gamma)
        gamma = self.gamma[idx]
        ggmax = self.ggmax[idx]

        gamma = np.maximum(gamma, 1e-12)

        damping = []

        for i in range(1, len(gamma)):
            g = gamma[i]

            # integral numérica estable
            g_int = np.linspace(0, g, 200)
            gg_int = np.interp(g_int, gamma, ggmax)

            integrand = gg_int * g_int
            integral = np.trapz(integrand, g_int)

            D = (2 / np.pi) * (integral / (g * ggmax[i]))

            damping.append(D)

        return 1000 * np.array(damping)


if __name__ == "__main__":
    gamma = 0.01 * np.array(
        [0.0001, 0.0003, 0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 0.7, 1, 3, 7, 10]
    )

    ggmax = np.array(
        [
            0.994112945419293,
            0.984006818208231,
            0.953158843,
            0.881153032,
            0.710321011911523,
            0.471859501691469,
            0.228089225,
            0.09719768,
            0.047091629,
            0.034382908,
            0.012807521,
            0.005919894,
            0.00427246176914836,
        ]
    )

    masingmodel = MasingRules(gamma, ggmax, Gmax=1.0)
    D = masingmodel.damping_masing_clean()

    gamma_plot = gamma[1:]

    plt.semilogx(gamma_plot, D)
    plt.xlabel("Shear strain γ")
    plt.ylabel("Damping (Masing)")
    plt.title("Masing damping from G/Gmax")
    plt.grid()
    plt.show()
