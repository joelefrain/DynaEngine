"""Column construction, non-discretized tables, discretization and calibration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np
import pandas as pd

from dynaengine.calibration import CalibrationSettings, calibrate_dynamic_curve
from dynaengine.constants import (
    DEFAULT_K0,
    GRAVITY,
    KPA_TO_PA,
    MIN_FLOAT,
    PHI_FACTOR_RANGE,
)
from dynaengine.dynamic_curves import DynamicModelSpec, evaluate_dynamic_curve


@dataclass(frozen=True)
class ShearVelocityProfile:
    depth_m: tuple[float, ...]
    velocity_m_s: tuple[float, ...]

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "ShearVelocityProfile":
        depth = data.get("depth", data.get("depth_m"))
        velocity = data.get("vs", data.get("velocity_m_s"))
        if depth is None or velocity is None:
            raise ValueError("shear_velocity requiere depth y vs")
        return cls(tuple(float(v) for v in depth), tuple(float(v) for v in velocity))

    def __post_init__(self) -> None:
        if len(self.depth_m) != len(self.velocity_m_s):
            raise ValueError("depth y vs deben tener la misma longitud")
        if len(self.depth_m) < 2:
            raise ValueError("El perfil Vs requiere al menos dos puntos")
        if any(value <= 0 for value in self.velocity_m_s):
            raise ValueError("Vs debe ser mayor a 0")
        if any(
            self.depth_m[i] >= self.depth_m[i + 1] for i in range(len(self.depth_m) - 1)
        ):
            raise ValueError(
                "Las profundidades del perfil Vs deben estar en orden creciente"
            )

    def average_between(self, top_m: float, bottom_m: float) -> float:
        if top_m >= bottom_m:
            raise ValueError("top_m debe ser menor a bottom_m")

        depths = np.asarray(self.depth_m, dtype=float)
        velocities = np.asarray(self.velocity_m_s, dtype=float)
        cut_depths = [top_m]
        cut_depths.extend(float(depth) for depth in depths if top_m < depth < bottom_m)
        cut_depths.append(bottom_m)
        cut_depths = np.asarray(cut_depths, dtype=float)
        segment_thickness = cut_depths[1:] - cut_depths[:-1]
        segment_velocity = np.asarray(
            [self.velocity_at(depth) for depth in cut_depths[:-1]]
        )
        return float((bottom_m - top_m) / np.sum(segment_thickness / segment_velocity))

    def velocity_at(self, depth_m: float) -> float:
        depths = np.asarray(self.depth_m, dtype=float)
        velocities = np.asarray(self.velocity_m_s, dtype=float)
        index = np.searchsorted(depths, depth_m, side="right") - 1
        index = max(0, min(index, len(velocities) - 1))
        return float(velocities[index])


@dataclass(frozen=True)
class Material:
    name: str
    unit_weight_kn_m3: float
    shear_velocity: ShearVelocityProfile
    cohesion_kpa: float
    friction_angle_deg: float
    dynamic_model: DynamicModelSpec

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "Material":
        required = (
            "material_name",
            "unit_weight_kn_m3",
            "shear_velocity",
            "shear_properties",
            "dynamic_model",
        )
        missing = [key for key in required if key not in data or data[key] is None]
        if missing:
            raise ValueError(f"Material incompleto. Faltan: {missing}")

        shear_properties = data["shear_properties"]
        for key in ("c", "phi"):
            if key not in shear_properties or shear_properties[key] is None:
                raise ValueError(f"shear_properties requiere '{key}'")

        return cls(
            name=str(data["material_name"]),
            unit_weight_kn_m3=float(data["unit_weight_kn_m3"]),
            shear_velocity=ShearVelocityProfile.from_mapping(data["shear_velocity"]),
            cohesion_kpa=float(shear_properties["c"]),
            friction_angle_deg=float(shear_properties["phi"]),
            dynamic_model=DynamicModelSpec.from_mapping(data["dynamic_model"]),
        )

    @property
    def k0(self) -> float:
        return float(self.dynamic_model.soil_parameters.get("k0", DEFAULT_K0))

    def model_at_sigma(self, sigma_vertical_kpa: float) -> DynamicModelSpec:
        if self.dynamic_model.model_type == "seed_1970":
            return self.dynamic_model
        return self.dynamic_model.with_sigma_vertical(sigma_vertical_kpa)


@dataclass(frozen=True)
class MaterialLibrary:
    materials: dict[str, Material]

    @classmethod
    def from_mappings(
        cls, material_data: Iterable[dict[str, Any]]
    ) -> "MaterialLibrary":
        materials = [Material.from_mapping(item) for item in material_data]
        names = [material.name for material in materials]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"Materiales duplicados: {duplicates}")
        return cls({material.name: material for material in materials})

    def require(self, name: str) -> Material:
        if name not in self.materials:
            raise KeyError(f"Material no caracterizado: {name}")
        return self.materials[name]


@dataclass(frozen=True)
class ColumnLayer:
    material: str
    thickness_m: float

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "ColumnLayer":
        material = data.get("material", data.get("material_name"))
        thickness = data.get("thickness", data.get("thickness_m"))
        if not material:
            raise ValueError("La capa de columna requiere material")
        if thickness is None or float(thickness) <= 0:
            raise ValueError("La capa de columna requiere thickness mayor a 0")
        return cls(material=str(material), thickness_m=float(thickness))


@dataclass(frozen=True)
class StratigraphicColumn:
    layers: tuple[ColumnLayer, ...]
    water_table_depth_m: float | None = None
    failure_surface_depth_m: float | None = None
    failure_surface_name: str | None = None
    failure_type: str | None = None
    failure_height_m: float | None = None
    name: str | None = None

    @classmethod
    def from_mapping(
        cls, data: dict[str, Any], name: str | None = None
    ) -> "StratigraphicColumn":
        if "layers" not in data or not data["layers"]:
            raise ValueError("La columna requiere layers")
        failure_height = data.get("failure_height", data.get("failure_height_m"))
        failure_surface_name = data.get(
            "failure_surface", data.get("failure_surface_name")
        )
        failure_type = data.get("failure_type")
        return cls(
            layers=tuple(ColumnLayer.from_mapping(layer) for layer in data["layers"]),
            water_table_depth_m=None
            if data.get("freatic") is None
            else float(data["freatic"]),
            failure_surface_depth_m=None
            if data.get("depth_failure_surface") is None
            else float(data["depth_failure_surface"]),
            failure_surface_name=None
            if failure_surface_name is None
            else str(failure_surface_name),
            failure_type=None if failure_type is None else str(failure_type),
            failure_height_m=None if failure_height is None else float(failure_height),
            name=name or data.get("name"),
        )


@dataclass(frozen=True)
class DiscretizationSettings:
    target_frequency_hz: float = 25.0
    max_segments_per_layer: int = 10_000

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "DiscretizationSettings":
        data = data or {}
        target = data.get("f_target", data.get("target_frequency_hz", 25.0))
        return cls(
            target_frequency_hz=float(target),
            max_segments_per_layer=int(data.get("max_segments_per_layer", 10_000)),
        )

    def __post_init__(self) -> None:
        if self.target_frequency_hz <= 0:
            raise ValueError("target_frequency_hz debe ser mayor a 0")
        if self.max_segments_per_layer <= 0:
            raise ValueError("max_segments_per_layer debe ser mayor a 0")


def build_raw_column_table(
    column: StratigraphicColumn, materials: MaterialLibrary
) -> pd.DataFrame:
    rows = []
    top = 0.0
    for index, layer in enumerate(column.layers, start=1):
        material = materials.require(layer.material)
        bottom = top + layer.thickness_m
        center = 0.5 * (top + bottom)
        vs = material.shear_velocity.average_between(top, bottom)
        sigma_v = _vertical_effective_stress_at_depth(column, materials, center)
        gmax_kpa = material.unit_weight_kn_m3 * vs**2 / GRAVITY
        tau_kpa = _average_shear_strength(material, sigma_v)
        rows.append(
            {
                "layer_id": index,
                "column_name": column.name,
                "material_name": material.name,
                "top_m": top,
                "bottom_m": bottom,
                "center_depth_m": center,
                "thickness_m": layer.thickness_m,
                "unit_weight_kn_m3": material.unit_weight_kn_m3,
                "shear_velocity_m_s": vs,
                "sigma_v_center_kpa": sigma_v,
                "gmax_kpa": gmax_kpa,
                "tau_kpa": tau_kpa,
                "k0": material.k0,
                "failure_surface_name": column.failure_surface_name,
                "failure_type": column.failure_type,
                "failure_height_m": column.failure_height_m,
                "failure_surface_depth_m": column.failure_surface_depth_m,
                "passes_failure_surface": _passes_failure_surface(column, top, bottom),
            }
        )
        top = bottom
    return pd.DataFrame(rows)


def discretize_column(
    column: StratigraphicColumn,
    materials: MaterialLibrary,
    settings: DiscretizationSettings | None = None,
) -> pd.DataFrame:
    settings = settings or DiscretizationSettings()
    raw = build_raw_column_table(column, materials)
    rows = []

    for raw_layer in raw.itertuples(index=False):
        material = materials.require(raw_layer.material_name)
        segment_count = _segment_count_for_frequency(
            thickness_m=raw_layer.thickness_m,
            top_m=raw_layer.top_m,
            material=material,
            settings=settings,
        )
        segment_thickness = raw_layer.thickness_m / segment_count

        for segment_index in range(segment_count):
            top = raw_layer.top_m + segment_index * segment_thickness
            bottom = top + segment_thickness
            center = 0.5 * (top + bottom)
            vs = material.shear_velocity.average_between(top, bottom)
            sigma_v = _vertical_effective_stress_at_depth(column, materials, center)
            gmax_kpa = material.unit_weight_kn_m3 * vs**2 / GRAVITY
            tau_kpa = _average_shear_strength(material, sigma_v)
            rows.append(
                {
                    "source_layer_id": raw_layer.layer_id,
                    "column_name": column.name,
                    "material_name": material.name,
                    "top_m": top,
                    "bottom_m": bottom,
                    "center_depth_m": center,
                    "thickness_m": segment_thickness,
                    "unit_weight_kn_m3": material.unit_weight_kn_m3,
                    "shear_velocity_m_s": vs,
                    "natural_frequency_hz": vs / (4 * segment_thickness),
                    "sigma_v_center_kpa": sigma_v,
                    "gmax_kpa": gmax_kpa,
                    "tau_kpa": tau_kpa,
                    "k0": material.k0,
                    "failure_surface_name": column.failure_surface_name,
                    "failure_type": column.failure_type,
                    "failure_height_m": column.failure_height_m,
                    "failure_surface_depth_m": column.failure_surface_depth_m,
                    "passes_failure_surface": _passes_failure_surface(
                        column, top, bottom
                    ),
                }
            )

    frame = pd.DataFrame(rows)
    frame.insert(0, "segment_id", range(1, len(frame) + 1))
    return frame


def calibrate_discretized_column(
    discretized_column: pd.DataFrame,
    materials: MaterialLibrary,
    settings: CalibrationSettings | None = None,
) -> pd.DataFrame:
    calibrated = discretized_column.copy()
    theta_1 = []
    theta_2 = []
    theta_3 = []
    theta_4 = []
    theta_5 = []
    p1 = []
    p2 = []
    p3 = []
    dmin = []

    for row in calibrated.itertuples(index=False):
        material = materials.require(row.material_name)
        curve = evaluate_dynamic_curve(material.model_at_sigma(row.sigma_v_center_kpa))
        result = calibrate_dynamic_curve(
            curve.calibration_data(),
            gmax_pa=row.gmax_kpa * KPA_TO_PA,
            tau_max_pa=max(row.tau_kpa * KPA_TO_PA, MIN_FLOAT),
            settings=settings,
        )
        theta_1.append(result.theta["theta_1"])
        theta_2.append(result.theta["theta_2"])
        theta_3.append(result.theta["theta_3"])
        theta_4.append(result.theta["theta_4"])
        theta_5.append(result.theta["theta_5"])
        p1.append(result.mrdf["P1"])
        p2.append(result.mrdf["P2"])
        p3.append(result.mrdf["P3"])
        dmin.append(result.dmin)

    calibrated["theta_1"] = theta_1
    calibrated["theta_2"] = theta_2
    calibrated["theta_3"] = theta_3
    calibrated["theta_4"] = theta_4
    calibrated["theta_5"] = theta_5
    calibrated["P1"] = p1
    calibrated["P2"] = p2
    calibrated["P3"] = p3
    calibrated["dmin"] = dmin
    return calibrated


def _segment_count_for_frequency(
    thickness_m: float,
    top_m: float,
    material: Material,
    settings: DiscretizationSettings,
) -> int:
    count = 1
    while True:
        segment_thickness = thickness_m / count
        vs = material.shear_velocity.average_between(top_m, top_m + segment_thickness)
        if vs / (4 * segment_thickness) >= settings.target_frequency_hz:
            return count
        count += 1
        if count > settings.max_segments_per_layer:
            raise ValueError(
                f"No se logro discretizar {material.name} con f_target={settings.target_frequency_hz}"
            )


def _vertical_effective_stress_at_depth(
    column: StratigraphicColumn,
    materials: MaterialLibrary,
    depth_m: float,
) -> float:
    total_stress = 0.0
    top = 0.0
    for layer in column.layers:
        material = materials.require(layer.material)
        bottom = top + layer.thickness_m
        if depth_m <= top:
            break
        contributing_thickness = min(depth_m, bottom) - top
        if contributing_thickness > 0:
            total_stress += material.unit_weight_kn_m3 * contributing_thickness
        top = bottom

    pore_pressure = 0.0
    if column.water_table_depth_m is not None and depth_m > column.water_table_depth_m:
        pore_pressure = GRAVITY * (depth_m - column.water_table_depth_m)
    return max(total_stress - pore_pressure, MIN_FLOAT)


def _average_shear_strength(material: Material, sigma_v_kpa: float) -> float:
    phi_min, phi_max = (
        PHI_FACTOR_RANGE[0] * material.friction_angle_deg,
        PHI_FACTOR_RANGE[1] * material.friction_angle_deg,
    )
    sigma_m = 0.5 * (1 + material.k0) * sigma_v_kpa
    tau_min = material.cohesion_kpa + sigma_m * np.tan(np.deg2rad(phi_min))
    tau_max = material.cohesion_kpa + sigma_m * np.tan(np.deg2rad(phi_max))
    return float(0.5 * (tau_min + tau_max))


def _passes_failure_surface(
    column: StratigraphicColumn, top_m: float, bottom_m: float
) -> bool:
    if column.failure_surface_depth_m is None:
        return False
    return top_m <= column.failure_surface_depth_m <= bottom_m
