#!/usr/bin/env python
"""
Benchmark: Comparar versiones optimized vs original

Uso:
    python benchmark.py

Output: Tabla de tiempos y speedups
"""

import numpy as np
import time
import sys
from pathlib import Path

# Add current dir to path
sys.path.insert(0, str(Path(__file__).parent))

from seismosoil_advanced import (
    NonlinearSiteResponseAdvanced as NonlinearOrig,
    create_example_profile,
    create_example_motion
)

try:
    from seismosoil_optimized import (
        NonlinearSiteResponseAdvanced as NonlinearOptimized
    )
    OPTIMIZED_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  seismosoil_optimized no disponible: {e}")
    OPTIMIZED_AVAILABLE = False


def benchmark_version(name, analysis_class, profile, motion, num_runs=3, dt=0.01):
    """
    Ejecutar benchmark de una versión.
    Pasar dt explícitamente para comparación justa.
    """
    times = []
    
    print(f"\n  {name}...")
    
    for i in range(num_runs):
        # Crear análisis fresh con dt fijo
        try:
            analysis = analysis_class(profile, model_type='H2', dt=dt, validate_cfl=False)
        except TypeError:
            # Fallback si validate_cfl no existe
            analysis = analysis_class(profile, model_type='H2', dt=dt)
        
        # Time
        start = time.perf_counter()
        results = analysis.compute_response(motion)
        end = time.perf_counter()
        
        t = end - start
        times.append(t)
        
        if i == 0:
            print(f"    (Primera ejecución - JIT si aplica: {t:.3f}s)")
        else:
            print(f"    Run {i+1}: {t:.4f}s")
    
    # Usar promedio de últimas 2 ejecuciones (sin JIT)
    avg_time = np.mean(times[-2:]) if len(times) > 1 else times[0]
    
    # Validar resultados
    pga = results.get('pga_output') or results.get('pga_surface') or 0
    amplification = results.get('amplification', 0)
    max_strain = results.get('max_strain') or results.get('max_shear_strain') or 0
    
    return {
        'name': name,
        'time': avg_time,
        'pga': pga,
        'amplification': amplification,
        'max_strain': max_strain
    }


def print_results(results_list):
    """Imprimir tabla de resultados"""
    
    print("\n" + "="*100)
    print("BENCHMARK RESULTS")
    print("="*100)
    
    # Tabla de times
    print("\nTiempos de ejecución:")
    print("─"*100)
    print(f"{'Versión':<30} {'Tiempo':<15} {'Speedup':<15} {'PGA Out':<15}")
    print("─"*100)
    
    baseline_time = results_list[0]['time']
    
    for res in results_list:
        speedup = baseline_time / res['time']
        print(f"{res['name']:<30} {res['time']:>7.4f} s      "
              f"{speedup:>6.1f}x         {res['pga']:>8.4f} m/s²")
    
    print("─"*100)
    
    # Tabla de validación
    print("\nValidación de resultados (idénticos):")
    print("─"*100)
    print(f"{'Versión':<30} {'PGA Out':<15} {'Amplification':<15} {'Max Strain':<15}")
    print("─"*100)
    
    for res in results_list:
        print(f"{res['name']:<30} {res['pga']:>8.4f} m/s²  "
              f"{res['amplification']:>8.3f}x      {res['max_strain']:>10.2e}")
    
    print("─"*100)
    
    # Validar que todos dan MISMO resultado
    baseline_pga = results_list[0]['pga']
    all_same = all(np.isclose(res['pga'], baseline_pga, rtol=1e-6) for res in results_list)
    
    if all_same:
        print("\n✅ Todos los resultados son idénticos (< 1e-6 error)")
    else:
        print("\n⚠️  Advertencia: Resultados difieren")
        for res in results_list[1:]:
            diff = abs(res['pga'] - baseline_pga)
            print(f"   {res['name']}: Δ = {diff:.2e}")


def main():
    print("\n" + "="*100)
    print("SEISMOSOIL ADVANCED - BENCHMARK")
    print("="*100)
    
    # Create test data
    print("\nPreparando datos de test...")
    profile = create_example_profile()
    motion = create_example_motion(duration=10, dt=0.01)  # 1000 steps
    
    print(f"  Profile: {profile.num_layers} capas, {profile.total_depth:.0f} m")
    print(f"  Motion: {motion.num_points} puntos de tiempo, {motion.duration:.1f} s @ {motion.dt:.3f} s")
    
    results_list = []
    
    # Test 1: Original (sin optimización)
    print("\n[BENCHMARK] Ejecutando versión ORIGINAL (NumPy)...")
    res_orig = benchmark_version("Original (NumPy)", NonlinearOrig, profile, motion, dt=0.01)
    results_list.append(res_orig)
    
    # Test 2: Optimized (Numba/Cython)
    if OPTIMIZED_AVAILABLE:
        print("\n[BENCHMARK] Ejecutando versión OPTIMIZADA (Numba/Cython)...")
        try:
            res_opt = benchmark_version("Optimized (Numba/Cython)", NonlinearOptimized, profile, motion, dt=0.01)
            results_list.append(res_opt)
        except Exception as e:
            print(f"⚠️  Error en versión optimizada: {e}")
    
    # Print results
    print_results(results_list)
    
    # Summary
    if len(results_list) > 1:
        speedup = results_list[0]['time'] / results_list[1]['time']
        print(f"\n🚀 SPEEDUP: {speedup:.1f}x faster")
        if speedup > 10:
            print("   Excelente - Usar versión optimizada")
        elif speedup > 2:
            print("   Bueno - Diferencia notable")
        else:
            print("   Mínimo - Mejora pequeña")
    
    print("\n" + "="*100)


if __name__ == '__main__':
    main()
