"""
Ejemplos de uso de SeismoSoil Advanced

Demuestra análisis no lineal 1D con un modelo constitutivo único
"""

import numpy as np
from seismosoil_advanced import (
    NonlinearSiteResponseAdvanced,
    VsProfile, SoilLayer, MotionRecord,
    create_example_profile, create_example_motion,
    read_profile, write_profile
)


def example_1_simple_analysis():
    """Ejemplo 1: Crear perfil y ejecutar análisis"""
    print("\n" + "="*80)
    print("EJEMPLO 1: Análisis Simple con Modelo H2")
    print("="*80)
    
    # Crear perfil
    profile = create_example_profile()
    profile.print_stratigraphy()
    
    # Crear movimiento
    motion = create_example_motion(duration=10.0)
    
    # Análisis con H2
    analysis = NonlinearSiteResponseAdvanced(
        profile, 
        model_type='H2',
        gamma_ref=0.005,
        n=0.5,
        damping_ref=0.05
    )
    results = analysis.compute_response(motion)
    
    # Imprimir resultados
    print(f"\nResultados:")
    print(f"  Input PGA:    {results['pga_input']:.3f} m/s²")
    print(f"  Surface PGA:  {results['pga_surface']:.3f} m/s²")
    print(f"  Amplificación: {results['amplification']:.2f}×")
    print(f"  Max strain:   {results['max_strain']:.2e}")
    print(f"  Model used:   {results['model']}")


def example_2_compare_models():
    """Ejemplo 2: Comparar diferentes modelos constitutivos"""
    print("\n" + "="*80)
    print("EJEMPLO 2: Comparación de Modelos (H2, H4, HH)")
    print("="*80)
    
    profile = create_example_profile()
    motion = create_example_motion(duration=10.0)
    
    models = [
        ('H2', {}),
        ('H4', {'alpha_g': 0.45, 'alpha_x': 0.55}),
        ('HH', {'alpha_g': 0.5, 'alpha_x': 0.5, 'beta': 0.3})
    ]
    
    print("\nComparando modelos constitutivos:")
    print(f"{'Modelo':<10} {'PGA Input':<12} {'PGA Out':<12} {'Amplificación':<15} {'Max Strain':<12}")
    print("-" * 70)
    
    for model_name, params in models:
        analysis = NonlinearSiteResponseAdvanced(
            profile,
            model_type=model_name,
            gamma_ref=0.005,
            n=0.5,
            damping_ref=0.05,
            **params
        )
        results = analysis.compute_response(motion)
        
        print(f"{model_name:<10} {results['pga_input']:<12.3f} "
              f"{results['pga_surface']:<12.3f} {results['amplification']:<15.2f} "
              f"{results['max_strain']:<12.2e}")


def example_3_custom_profile():
    """Ejemplo 3: Crear perfil personalizado"""
    print("\n" + "="*80)
    print("EJEMPLO 3: Perfil Personalizado")
    print("="*80)
    
    # Definir capas manually
    layers = [
        SoilLayer(thickness=3.0, vs=200, density=1700),
        SoilLayer(thickness=4.0, vs=250, density=1750),
        SoilLayer(thickness=6.0, vs=300, density=1800),
        SoilLayer(thickness=10.0, vs=400, density=1900),
        SoilLayer(thickness=20.0, vs=500, density=2000)
    ]
    
    profile = VsProfile(layers=layers)
    profile.print_stratigraphy()
    
    # Guardar a archivo .txt
    write_profile(profile, "custom_profile.txt")
    print("✓ Perfil guardado a: custom_profile.txt")
    
    # Cargar de vuelta
    loaded = read_profile("custom_profile.txt")
    print(f"✓ Perfil cargado: {loaded.num_layers} capas")
    
    # Análisis
    motion = create_example_motion(duration=8.0)
    analysis = NonlinearSiteResponseAdvanced(loaded, model_type='HH')
    results = analysis.compute_response(motion)
    
    print(f"\nAnálisis con modelo HH:")
    print(f"  Amplificación: {results['amplification']:.2f}×")
    print(f"  Max strain: {results['max_strain']:.2e}")


def example_4_parameter_study():
    """Ejemplo 4: Estudio de sensibilidad de parámetros"""
    print("\n" + "="*80)
    print("EJEMPLO 4: Estudio de Sensibilidad (gamma_ref)")
    print("="*80)
    
    profile = create_example_profile()
    motion = create_example_motion(duration=10.0)
    
    gamma_refs = [0.001, 0.005, 0.010, 0.020]
    
    print("\nVariando gamma_ref (parámetro de degradación):")
    print(f"{'gamma_ref':<12} {'PGA Out':<12} {'Amplificación':<15} {'Max Strain':<12}")
    print("-" * 60)
    
    for gamma_ref in gamma_refs:
        analysis = NonlinearSiteResponseAdvanced(
            profile,
            model_type='H2',
            gamma_ref=gamma_ref,
            n=0.5,
            damping_ref=0.05
        )
        results = analysis.compute_response(motion)
        
        print(f"{gamma_ref:<12.4f} {results['pga_surface']:<12.3f} "
              f"{results['amplification']:<15.2f} {results['max_strain']:<12.2e}")


def main():
    """Ejecutar todos los ejemplos"""
    print("\n" + "╔" + "═"*78 + "╗")
    print("║" + " "*20 + "SEISMOSOIL ADVANCED - EJEMPLOS" + " "*30 + "║")
    print("╚" + "═"*78 + "╝")
    
    example_1_simple_analysis()
    example_2_compare_models()
    example_3_custom_profile()
    example_4_parameter_study()
    
    print("\n" + "="*80)
    print("✓ Todos los ejemplos completados exitosamente")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
