#!/usr/bin/env python
"""Validate dynamic-curve sigma defaults."""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynaengine import (  # noqa: E402
    DEFAULT_SIGMA_VERTICAL_KPA,
    DynamicModelSpec,
    Material,
    evaluate_dynamic_curve,
)


def _darendeli_without_sigma() -> dict:
    return {
        "model_type": "darendeli_2001",
        "soil_parameters": {
            "IP": 0.0,
            "OCR": 1.0,
            "k0": 0.7,
            "frequency": 1.0,
            "N": 10,
        },
    }


def test_dynamic_model_defaults_sigma_vertical() -> None:
    spec = DynamicModelSpec.from_mapping(_darendeli_without_sigma())

    assert spec.sigma_vertical_kpa == DEFAULT_SIGMA_VERTICAL_KPA
    assert spec.sigma_vertical_assumed is True


def test_evaluate_dynamic_curve_warns_when_sigma_is_assumed() -> None:
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        curve = evaluate_dynamic_curve(_darendeli_without_sigma())

    assert len(curve.strain) > 0
    assert any(
        "sigma_vertical=100 kPa por defecto" in str(item.message)
        for item in captured
    )


def test_column_material_can_omit_sigma_vertical() -> None:
    material = Material.from_mapping(
        {
            "material_name": "Arena",
            "unit_weight_kn_m3": 19.0,
            "shear_velocity": {"depth": [0, 10], "vs": [250, 300]},
            "shear_properties": {"c": 0, "phi": 34},
            "dynamic_model": _darendeli_without_sigma(),
        }
    )

    segment_model = material.model_at_sigma(42.0)

    assert segment_model.sigma_vertical_kpa == 42.0
    assert segment_model.sigma_vertical_assumed is False
