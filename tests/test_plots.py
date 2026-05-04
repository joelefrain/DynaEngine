#!/usr/bin/env python
"""Validate plotting helpers against the section_01 DXF example."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dynaengine import (  # noqa: E402
    extract_columns_from_dxf,
    plot_column_discretized_detailed,
    plot_discretized_column,
    plot_dxf_extraction,
    plot_raw_column,
    prepare_column_configs,
    process_column_config,
)
from dynaengine.dxf import _generate_clean_polygons, _read_dxf_layers  # noqa: E402


def _load_materials() -> list[dict]:
    path = ROOT / "examples" / "data" / "section_01_materials.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_plots() -> None:
    dxf_path = ROOT / "examples" / "data" / "section_01.dxf"
    x_positions_by_failure = {f"failure_{index}": [250, 480] for index in range(1, 8)}
    extraction = extract_columns_from_dxf(
        dxf_path,
        x_positions=x_positions_by_failure,
        failure_types={name: "tipo_de_falla" for name in x_positions_by_failure},
    )

    external, _freatic, material, _failure, text = _read_dxf_layers(dxf_path)
    clean_polygons, _total_area = _generate_clean_polygons(external, material, text)

    fig, _ax = plot_dxf_extraction(clean_polygons, x_positions=[250, 480])
    plt.close(fig)

    configs = prepare_column_configs(
        extraction.columns,
        _load_materials(),
        target_frequency_hz=25,
    )
    first_name = next(iter(configs))
    result = process_column_config(configs[first_name], calibrate=False)

    assert "natural_frequency_hz" in result.discretized.columns

    fig, _ax = plot_raw_column(result.raw)
    plt.close(fig)

    fig, _ax = plot_discretized_column(result.discretized)
    plt.close(fig)

    fig, _axes = plot_column_discretized_detailed(result.discretized)
    plt.close(fig)
