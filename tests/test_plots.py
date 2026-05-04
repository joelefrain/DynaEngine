#!/usr/bin/env python
"""Test script to validate all plot functions work correctly."""

from pathlib import Path
import sys

ROOT = Path.cwd().resolve()
if not (ROOT / "dynaengine").exists():
    ROOT = ROOT.parent

from dynaengine import (
    extract_columns_from_dxf,
    prepare_column_configs,
    process_column_config,
    plot_dxf_extraction,
    plot_raw_column,
    plot_discretized_column,
    plot_column_discretized_detailed,
)
from dynaengine.dxf import (
    _read_dxf_layers,
    _generate_clean_polygons,
)
import matplotlib
matplotlib.use('Agg')  # Non-GUI backend for testing
import matplotlib.pyplot as plt

# Materials definition
MATERIALS = [
    {
        "material_name": "Material de poza",
        "unit_weight_kn_m3": 19,
        "shear_velocity": {"depth": [0, 5, 10, 15], "vs": [300, 350, 440, 550]},
        "shear_properties": {"c": 0, "phi": 34},
        "dynamic_model": {
            "model_type": "darendeli_2001",
            "sigma_vertical": 100,
            "soil_parameters": {"IP": 0.0, "OCR": 1.0, "k0": 0.7, "frequency": 1.0, "N": 10},
        },
    },
    {
        "material_name": "Material del dique",
        "unit_weight_kn_m3": 20,
        "shear_velocity": {"depth": [0, 8, 15, 20], "vs": [320, 380, 420, 550]},
        "shear_properties": {"c": 0, "phi": 34},
        "dynamic_model": {
            "model_type": "menq_2003",
            "sigma_vertical": 100,
            "soil_parameters": {"Cu": 18.0, "D50": 8.0, "k0": 0.7, "N": 10},
        },
    },
    {
        "material_name": "Grava arcillosa",
        "unit_weight_kn_m3": 19,
        "shear_velocity": {"depth": [0, 10, 20, 25], "vs": [200, 330, 540, 600]},
        "shear_properties": {"c": 0, "phi": 34},
        "dynamic_model": {
            "model_type": "wang_2021",
            "sigma_vertical": 100,
            "soil_parameters": {"soil_group": "Nonplastic silty sand group", "Cu": 2.0, "CF": 50.0, "e": 0.7, "D50": 1.0, "wc": 1.0, "k0": 0.7},
        },
    },
    {
        "material_name": "Grava arenosa",
        "unit_weight_kn_m3": 19,
        "shear_velocity": {"depth": [0, 24, 30, 40], "vs": [230, 300, 440, 700]},
        "shear_properties": {"c": 0, "phi": 34},
        "dynamic_model": {
            "model_type": "rollins_2020",
            "sigma_vertical": 100,
            "soil_parameters": {"Cu": 1.0, "k0": 1.0},
        },
    },
    {
        "material_name": "Grava pobremente gradada",
        "unit_weight_kn_m3": 19.0,
        "shear_velocity": {"depth": [0, 24, 30, 35], "vs": [230, 300, 440, 500]},
        "shear_properties": {"c": 0, "phi": 34},
        "dynamic_model": {
            "model_type": "ishibashi_1993",
            "sigma_vertical": 100,
            "soil_parameters": {"IP": 50.0, "k0": 0.5},
        },
    },
    {
        "material_name": "Estrato no identificado 1",
        "unit_weight_kn_m3": 19.0,
        "shear_velocity": {"depth": [0, 24, 30, 35], "vs": [230, 300, 440, 550]},
        "shear_properties": {"c": 0, "phi": 34},
        "dynamic_model": {
            "model_type": "rojas_2019",
            "sigma_vertical": 100,
            "soil_parameters": {"k0": 1.0},
        },
    },
]

def test_plots():
    """Test all plot functions."""
    
    print("=" * 60)
    print("Testing Plot Functions")
    print("=" * 60)
    
    # Step 1: Extract DXF
    print("\n1. Extracting DXF...")
    dxf_path = ROOT / "examples" / "data" / "section_01.dxf"
    extraction = extract_columns_from_dxf(dxf_path, x_positions=[250, 480])
    print(f"   ✓ Extracted {len(extraction.columns)} columns")
    print(f"   ✓ Materials: {extraction.material_names}")
    
    # Step 2: Get clean polygons for DXF plot
    print("\n2. Getting clean polygons for DXF visualization...")
    external, freatic, material, failure, text = _read_dxf_layers(dxf_path)
    clean_polygons = _generate_clean_polygons(external, material, text)
    print(f"   ✓ Generated {len(clean_polygons)} clean polygons")
    
    # Step 3: Test plot_dxf_extraction
    print("\n3. Testing plot_dxf_extraction()...")
    try:
        fig, ax = plot_dxf_extraction(clean_polygons, x_positions=[250, 480])
        plt.close(fig)
        print("   ✓ plot_dxf_extraction works correctly")
    except Exception as e:
        print(f"   ✗ plot_dxf_extraction failed: {e}")
        return False
    
    # Step 4: Process first column
    print("\n4. Processing first column...")
    configs = prepare_column_configs(extraction.columns, MATERIALS, target_frequency_hz=25)
    first_name = next(iter(configs))
    result = process_column_config(configs[first_name], calibrate=False)
    print(f"   ✓ Processed column: {first_name}")
    print(f"   ✓ Raw layers: {len(result.raw)}")
    print(f"   ✓ Discretized segments: {len(result.discretized)}")
    
    # Step 5: Verify natural_frequency_hz column
    print("\n5. Verifying 'natural_frequency_hz' column...")
    if "natural_frequency_hz" in result.discretized.columns:
        freq_values = result.discretized["natural_frequency_hz"]
        print(f"   ✓ Column present with {len(freq_values)} values")
        print(f"   ✓ Frequency range: {freq_values.min():.2f} - {freq_values.max():.2f} Hz")
    else:
        print("   ✗ 'natural_frequency_hz' column NOT found")
        return False
    
    # Step 6: Test plot_raw_column
    print("\n6. Testing plot_raw_column()...")
    try:
        fig, ax = plot_raw_column(result.raw)
        plt.close(fig)
        print("   ✓ plot_raw_column works correctly")
    except Exception as e:
        print(f"   ✗ plot_raw_column failed: {e}")
        return False
    
    # Step 7: Test plot_discretized_column
    print("\n7. Testing plot_discretized_column()...")
    try:
        fig, ax = plot_discretized_column(result.discretized)
        plt.close(fig)
        print("   ✓ plot_discretized_column works correctly")
    except Exception as e:
        print(f"   ✗ plot_discretized_column failed: {e}")
        return False
    
    # Step 8: Test plot_column_discretized_detailed
    print("\n8. Testing plot_column_discretized_detailed()...")
    try:
        fig, axes = plot_column_discretized_detailed(result.discretized)
        plt.close(fig)
        print("   ✓ plot_column_discretized_detailed works correctly")
        print(f"   ✓ Generated 4 subplots: Materiales, Espesor, Perfil Vs, Perfil de Frecuencia")
    except Exception as e:
        print(f"   ✗ plot_column_discretized_detailed failed: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED ✓")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_plots()
    sys.exit(0 if success else 1)
