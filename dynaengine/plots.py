"""Matplotlib helpers used by examples and notebooks."""

from __future__ import annotations

import matplotlib.pyplot as plt

from dynaengine.columns import ShearVelocityProfile
from dynaengine.dynamic_curves import DynamicCurveResult


def plot_dynamic_curve(result: DynamicCurveResult):
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    axes[0].semilogx(result.strain, result.ggmax)
    axes[0].set_title("Reduccion de modulo")
    axes[0].set_xlabel("Deformacion cortante, gamma")
    axes[0].set_ylabel("G/Gmax")

    axes[1].semilogx(result.strain, result.damping_percent)
    axes[1].set_title("Amortiguamiento")
    axes[1].set_xlabel("Deformacion cortante, gamma")
    axes[1].set_ylabel("Damping (%)")

    axes[2].semilogx(result.strain, result.shear_stress_kpa)
    axes[2].set_title("Esfuerzo-deformacion")
    axes[2].set_xlabel("Deformacion cortante, gamma")
    axes[2].set_ylabel("Tau (kPa)")

    for axis in axes:
        axis.grid(True, which="both", alpha=0.25)
        axis.tick_params(axis="both", which="both", labelsize=8)
    fig.tight_layout()
    return fig, axes


def plot_shear_velocity_profile(profile: ShearVelocityProfile):
    fig, axis = plt.subplots(figsize=(4, 6))
    velocity = list(profile.velocity_m_s)
    depth = list(profile.depth_m)

    x_values = []
    y_values = []
    for index in range(len(depth) - 1):
        x_values.extend([velocity[index], velocity[index]])
        y_values.extend([depth[index], depth[index + 1]])
    x_values.append(velocity[-1])
    y_values.append(depth[-1])

    axis.step(x_values, y_values, where="post")
    axis.invert_yaxis()
    axis.set_title("Perfil Vs")
    axis.set_xlabel("Vs (m/s)")
    axis.set_ylabel("Profundidad (m)")
    axis.grid(True, which="both", alpha=0.25)
    axis.tick_params(axis="both", which="both", labelsize=8)
    fig.tight_layout()
    return fig, axis
