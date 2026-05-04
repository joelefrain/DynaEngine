#!/usr/bin/env python
"""Validate unidentified-stratum resolution examples."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynaengine import resolve_unidentified_materials_detailed  # noqa: E402


def test_explicit_alias_overrides_same_name_material() -> None:
    resolution = resolve_unidentified_materials_detailed(
        [
            {"material_name": "Estrato no identificado 1"},
            {"material_name": "Grava pobremente gradada"},
        ],
        ["Estrato no identificado 1"],
        material_aliases={
            "Estrato no identificado 1": "Grava pobremente gradada",
        },
    )

    assert resolution.aliases == {
        "Estrato no identificado 1": "Grava pobremente gradada",
    }
    assert resolution.unresolved == []


def test_explicit_characterization_can_rename_same_name_material() -> None:
    resolution = resolve_unidentified_materials_detailed(
        [
            {"material_name": "Estrato no identificado 1"},
            {"material_name": "Grava pobremente gradada"},
        ],
        ["Estrato no identificado 1"],
        actions={
            "Estrato no identificado 1": {
                "action": "characterize",
                "name": "Grava pobremente gradada caracterizada",
                "properties": {
                    "unit_weight_kn_m3": 19.0,
                },
            }
        },
    )

    assert resolution.aliases == {
        "Estrato no identificado 1": "Grava pobremente gradada caracterizada",
    }
    assert resolution.unresolved == []
    assert any(
        material["material_name"] == "Grava pobremente gradada caracterizada"
        for material in resolution.materials
    )
