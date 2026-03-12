"""
SeismoSoil Python - Complete Examples

Demonstrates how to use the Python port for various analyses
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

from seismosoil_core import (
    SoilLayer, VsProfile, MotionRecord,
    H2Model, H4Model, HHModel, EPPModel,
    NonlinearSiteResponse, calculate_vs30, calculate_max_values
)
from seismosoil_io import (
    SeismoSoilIO, AnalysisRunner, ResultsAnalyzer
)


# ==============================================================================
# EXAMPLE 1: Basic H2 Model Analysis with Simple Profile
# ==============================================================================

def example_1_basic_h2_analysis():
    """
    Most basic example: 3-layer profile with H2 model
    """
    print("\n" + "="*70)
    print("EXAMPLE 1: Basic H2 Model Analysis")
    print("="*70)
    
    # 1. Create soil profile
    layers = [
        SoilLayer(thickness=5.0, vs=250, damping_ratio=0.05, density=1800),
        SoilLayer(thickness=5.0, vs=300, damping_ratio=0.05, density=1850),
        SoilLayer(thickness=10.0, vs=400, damping_ratio=0.05, density=1900),
    ]
    profile = VsProfile(layers=layers)
    
    print(f"\nProfile created:")
    print(f"  Total depth: {profile.total_depth:.1f} m")
    print(f"  Vs30: {calculate_vs30(profile):.1f} m/s")
    print(f"  Layers: {profile.num_layers}")
    
    # 2. Create ground motion
    dt = 0.01
    duration = 10.0
    t = np.arange(0, duration, dt)
    
    # Damped sinusoid: A*sin(2πft)*exp(-t/τ)
    freq = 1.0  # 1 Hz
    A = 1.0     # 1 m/s²
    tau = 5.0   # Decay time
    accel = A * np.sin(2*np.pi*freq*t) * np.exp(-t/tau)
    
    motion = MotionRecord(time=t, acceleration=accel, name="Example1_Motion")
    
    print(f"\nMotion created:")
    print(f"  Duration: {motion.duration:.1f} s")
    print(f"  Samples: {motion.num_points}")
    print(f"  PGA: {motion.get_pga():.3f} m/s²")
    
    # 3. Create H2 model
    model = H2Model(gamma_ref=0.005, n=0.5, alpha=0.5)
    print(f"\nModel: {model.name}")
    
    # 4. Run analysis
    analysis = NonlinearSiteResponse(
        profile=profile,
        model=model,
        dt=motion.dt,
        n_substeps=10
    )
    
    print("\nRunning analysis...")
    results = analysis.compute_response(motion, boundary_type='rigid')
    
    # 5. Post-process
    analyzer = ResultsAnalyzer()
    analyzer.print_summary(results, profile)
    
    # 6. Compute transfer function
    freq, tf = analyzer.transfer_function(results, max_freq=5.0)
    dominant_freq = analyzer.resonant_frequency(freq, tf)
    amplification = analyzer.amplification_factor(freq, tf)
    
    print(f"\nTransfer Function Analysis:")
    print(f"  Dominant frequency: {dominant_freq:.2f} Hz")
    print(f"  Peak amplification: {amplification:.2f}x")
    
    # 7. Plot results
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle('H2 Model Analysis - Example 1', fontsize=14, fontweight='bold')
    
    # Time series
    ax = axes[0, 0]
    ax.plot(results['time'], results['acceleration'][:, 0], label='Base', linewidth=1.5)
    ax.plot(results['time'], results['acceleration'][:, -1], label='Surface', linewidth=1.5)
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Acceleration (m/s²)')
    ax.set_title('Input and Output Accelerations')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Transfer function
    ax = axes[0, 1]
    ax.semilogy(freq, tf)
    ax.set_xlabel('Frequency (Hz)')
    ax.set_ylabel('Amplitude')
    ax.set_title('Transfer Function')
    ax.grid(True, alpha=0.3)
    ax.axvline(dominant_freq, color='r', linestyle='--', alpha=0.5, label=f'{dominant_freq:.2f} Hz')
    ax.legend()
    
    # Strain vs depth
    ax = axes[1, 0]
    max_vals = calculate_max_values(results)
    depths = results['depth_layers']
    ax.plot(max_vals['max_strain']*100, depths, 'o-', linewidth=2, markersize=6)
    ax.set_xlabel('Max Strain (%)')
    ax.set_ylabel('Depth (m)')
    ax.set_title('Max Strain by Depth')
    ax.invert_yaxis()
    ax.grid(True, alpha=0.3)
    
    # Stress vs depth
    ax = axes[1, 1]
    ax.plot(max_vals['max_stress']/1000, depths, 's-', linewidth=2, markersize=6)
    ax.set_xlabel('Max Stress (kPa)')
    ax.set_ylabel('Depth (m)')
    ax.set_title('Max Stress by Depth')
    ax.invert_yaxis()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('example1_h2_analysis.png', dpi=150, bbox_inches='tight')
    print(f"\n✓ Plot saved as 'example1_h2_analysis.png'")
    
    return results, profile


# ==============================================================================
# EXAMPLE 2: Comparing Different Models (H2 vs H4 vs HH)
# ==============================================================================

def example_2_model_comparison():
    """
    Compare H2, H4, and HH models with same profile and motion
    """
    print("\n" + "="*70)
    print("EXAMPLE 2: Model Comparison (H2 vs H4 vs HH)")
    print("="*70)
    
    # Create same profile and motion as Example 1
    layers = [
        SoilLayer(thickness=5.0, vs=250, damping_ratio=0.05, density=1800),
        SoilLayer(thickness=5.0, vs=300, damping_ratio=0.05, density=1850),
        SoilLayer(thickness=10.0, vs=400, damping_ratio=0.05, density=1900),
    ]
    profile = VsProfile(layers=layers)
    
    dt = 0.01
    t = np.arange(0, 10, dt)
    accel = 1.0 * np.sin(2*np.pi*1*t) * np.exp(-t/5)
    motion = MotionRecord(time=t, acceleration=accel, name="Comparison")
    
    # Common model parameters
    params = {
        'gamma_ref': 0.005,
        'n': 0.5,
    }
    
    models = {
        'H2': H2Model(alpha=0.5, **params),
        'H4': H4Model(alpha_g=0.5, alpha_x=0.5, **params),
        'HH': HHModel(alpha_g=0.5, alpha_x=0.5, beta=0.3, **params),
    }
    
    results_dict = {}
    max_vals_dict = {}
    
    print(f"\nRunning analyses...")
    for model_name, model in models.items():
        print(f"  {model_name}... ", end='', flush=True)
        
        analysis = NonlinearSiteResponse(profile=profile, model=model, dt=dt)
        results = analysis.compute_response(motion)
        results_dict[model_name] = results
        max_vals_dict[model_name] = calculate_max_values(results)
        
        print("✓")
    
    # Compare results
    print(f"\nResults Comparison:")
    print(f"{'Model':<8} {'PGA_in':<12} {'PGA_out':<12} {'Amplif.':<10} {'Max_Strain':<12}")
    print("-" * 60)
    
    max_vals = calculate_max_values(results_dict['H2'])
    
    for model_name in models.keys():
        max_v = max_vals_dict[model_name]
        pga_in = max_v['max_accel'][0]
        pga_out = max_v['max_accel'][-1]
        amplif = pga_out / (pga_in + 1e-10)
        max_strain = np.max(max_v['max_strain'])
        
        print(f"{model_name:<8} {pga_in:<12.4f} {pga_out:<12.4f} {amplif:<10.2f} {max_strain:<12.2e}")
    
    # Plot comparison
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    fig.suptitle('Model Comparison (H2 vs H4 vs HH)', fontsize=14, fontweight='bold')
    
    colors = {'H2': 'blue', 'H4': 'red', 'HH': 'green'}
    
    # Surface acceleration
    ax = axes[0, 0]
    for model_name, results in results_dict.items():
        ax.plot(results['time'], results['acceleration'][:, -1], 
               label=model_name, linewidth=1.5, color=colors[model_name], alpha=0.7)
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Acceleration (m/s²)')
    ax.set_title('Surface Acceleration')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Transfer functions
    ax = axes[0, 1]
    analyzer = ResultsAnalyzer()
    for model_name, results in results_dict.items():
        freq, tf = analyzer.transfer_function(results, max_freq=5.0)
        ax.semilogy(freq, tf, label=model_name, linewidth=2, color=colors[model_name])
    ax.set_xlabel('Frequency (Hz)')
    ax.set_ylabel('Amplitude')
    ax.set_title('Transfer Functions')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Max strain profiles
    ax = axes[1, 0]
    depths = results_dict['H2']['depth_layers']
    for model_name in models.keys():
        max_strain = max_vals_dict[model_name]['max_strain'] * 100
        ax.plot(max_strain, depths, 'o-', label=model_name, 
               linewidth=2, markersize=5, color=colors[model_name])
    ax.set_xlabel('Max Strain (%)')
    ax.set_ylabel('Depth (m)')
    ax.set_title('Max Strain Profiles')
    ax.invert_yaxis()
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Max stress profiles
    ax = axes[1, 1]
    for model_name in models.keys():
        max_stress = max_vals_dict[model_name]['max_stress'] / 1000
        ax.plot(max_stress, depths, 's-', label=model_name, 
               linewidth=2, markersize=5, color=colors[model_name])
    ax.set_xlabel('Max Stress (kPa)')
    ax.set_ylabel('Depth (m)')
    ax.set_title('Max Stress Profiles')
    ax.invert_yaxis()
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('example2_model_comparison.png', dpi=150, bbox_inches='tight')
    print(f"\n✓ Plot saved as 'example2_model_comparison.png'")
    
    return results_dict, profile


# ==============================================================================
# EXAMPLE 3: Parametric Study - Effect of Model Parameters
# ==============================================================================

def example_3_parameter_study():
    """
    Study effect of gamma_ref parameter on H2 model
    """
    print("\n" + "="*70)
    print("EXAMPLE 3: Parametric Study (H2 - gamma_ref effect)")
    print("="*70)
    
    # Same profile and motion
    layers = [
        SoilLayer(thickness=5.0, vs=250, damping_ratio=0.05, density=1800),
        SoilLayer(thickness=5.0, vs=300, damping_ratio=0.05, density=1850),
        SoilLayer(thickness=10.0, vs=400, damping_ratio=0.05, density=1900),
    ]
    profile = VsProfile(layers=layers)
    
    dt = 0.01
    t = np.arange(0, 10, dt)
    accel = 2.0 * np.sin(2*np.pi*1*t) * np.exp(-t/5)  # Larger amplitude
    motion = MotionRecord(time=t, acceleration=accel)
    
    # Parameter sweep
    gamma_refs = [0.001, 0.005, 0.01, 0.02, 0.05]
    results_dict = {}
    max_vals_dict = {}
    
    print(f"\nParametrically varying gamma_ref...")
    for gamma_ref in gamma_refs:
        print(f"  gamma_ref={gamma_ref:.3f}... ", end='', flush=True)
        
        model = H2Model(gamma_ref=gamma_ref, n=0.5, alpha=0.5)
        analysis = NonlinearSiteResponse(profile=profile, model=model, dt=dt)
        results = analysis.compute_response(motion)
        
        results_dict[gamma_ref] = results
        max_vals_dict[gamma_ref] = calculate_max_values(results)
        
        print("✓")
    
    # Analysis
    print(f"\nParameter Effects:")
    print(f"{'gamma_ref':<12} {'PGA_out':<12} {'Max_Strain':<12} {'Max_Stress':<12}")
    print("-" * 50)
    
    for gamma_ref in gamma_refs:
        max_v = max_vals_dict[gamma_ref]
        print(f"{gamma_ref:<12.4f} {max_v['max_accel'][-1]:<12.4f} "
              f"{np.max(max_v['max_strain']):<12.2e} {np.max(max_v['max_stress']):<12.0f}")
    
    # Plot parametric results
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    fig.suptitle('Parameter Study: Effect of gamma_ref', fontsize=14, fontweight='bold')
    
    # Surface acceleration
    ax = axes[0]
    for gamma_ref in gamma_refs[::2]:  # Plot every other for clarity
        results = results_dict[gamma_ref]
        ax.plot(results['time'], results['acceleration'][:, -1], 
               label=f'γ_ref={gamma_ref:.3f}', linewidth=1.5, alpha=0.7)
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Acceleration (m/s²)')
    ax.set_title('Surface Acceleration')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Effect on amplification
    ax = axes[1]
    amplifications = []
    for gamma_ref in gamma_refs:
        max_v = max_vals_dict[gamma_ref]
        pga_in = max_v['max_accel'][0]
        pga_out = max_v['max_accel'][-1]
        amplifications.append(pga_out / (pga_in + 1e-10))
    
    ax.plot(gamma_refs, amplifications, 'o-', linewidth=2, markersize=8)
    ax.set_xlabel('Reference Strain (γ_ref)')
    ax.set_ylabel('Amplification Factor')
    ax.set_title('Effect on Amplification')
    ax.set_xscale('log')
    ax.grid(True, alpha=0.3)
    
    # Effect on max strain
    ax = axes[2]
    max_strains = []
    for gamma_ref in gamma_refs:
        max_v = max_vals_dict[gamma_ref]
        max_strains.append(np.max(max_v['max_strain']))
    
    ax.semilogy(gamma_refs, max_strains, 's-', linewidth=2, markersize=8)
    ax.set_xlabel('Reference Strain (γ_ref)')
    ax.set_ylabel('Maximum Strain')
    ax.set_title('Effect on Max Strain')
    ax.set_xscale('log')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('example3_parameter_study.png', dpi=150, bbox_inches='tight')
    print(f"\n✓ Plot saved as 'example3_parameter_study.png'")
    
    return results_dict, profile


# ==============================================================================
# EXAMPLE 4: Using File I/O (MATLAB-compatible format)
# ==============================================================================

def example_4_file_io():
    """
    Demonstrate saving/loading with MATLAB-compatible format
    """
    print("\n" + "="*70)
    print("EXAMPLE 4: File I/O (MATLAB-compatible format)")
    print("="*70)
    
    # Create output directory
    output_dir = Path('example4_results')
    output_dir.mkdir(exist_ok=True)
    
    # 1. Create and save profile
    print("\n1. Creating and saving profile...")
    layers = [
        SoilLayer(thickness=3.0, vs=200, damping_ratio=0.05, density=1750),
        SoilLayer(thickness=4.0, vs=280, damping_ratio=0.05, density=1800),
        SoilLayer(thickness=5.0, vs=350, damping_ratio=0.055, density=1900),
        SoilLayer(thickness=8.0, vs=450, damping_ratio=0.05, density=2000),
    ]
    profile = VsProfile(layers=layers)
    
    profile_file = output_dir / 'profile.txt'
    SeismoSoilIO.write_vs_profile(profile, str(profile_file))
    print(f"  ✓ Profile saved to {profile_file}")
    
    # 2. Create and save motion
    print("2. Creating and saving ground motion...")
    dt = 0.01
    t = np.arange(0, 15, dt)
    accel = 1.5 * np.sin(2*np.pi*0.8*t) * np.exp(-t/7)
    motion = MotionRecord(time=t, acceleration=accel, name="TestMotion")
    
    motion_file = output_dir / 'motion.txt'
    SeismoSoilIO.write_motion(motion, str(motion_file))
    print(f"  ✓ Motion saved to {motion_file}")
    
    # 3. Read back and verify
    print("3. Reading back from files...")
    loaded_profile = SeismoSoilIO.read_vs_profile(str(profile_file))
    loaded_motion = SeismoSoilIO.read_motion(str(motion_file))
    
    print(f"  ✓ Profile loaded: {loaded_profile.num_layers} layers, {loaded_profile.total_depth:.1f}m")
    print(f"  ✓ Motion loaded: {loaded_motion.num_points} samples, PGA={loaded_motion.get_pga():.3f} m/s²")
    
    # 4. Run analysis
    print("4. Running analysis...")
    model = H2Model(gamma_ref=0.005, n=0.5, alpha=0.5)
    analysis = NonlinearSiteResponse(profile=loaded_profile, model=model, dt=loaded_motion.dt)
    results = analysis.compute_response(loaded_motion)
    
    # 5. Save results
    print("5. Saving analysis results...")
    SeismoSoilIO.write_results(results, str(output_dir), 'TestMotion')
    print(f"  ✓ Results saved to {output_dir}/TestMotion/")
    
    # List saved files
    results_subdir = output_dir / 'TestMotion'
    saved_files = list(results_subdir.glob('*.txt'))
    for f in saved_files:
        print(f"    - {f.name}")
    
    return loaded_profile, loaded_motion, results


# ==============================================================================
# Main Execution
# ==============================================================================

if __name__ == "__main__":
    print("\n" + "╔" + "="*68 + "╗")
    print("║" + " "*15 + "SEISMOSOIL PYTHON - EXAMPLES" + " "*25 + "║")
    print("╚" + "="*68 + "╝")
    
    # Run examples
    try:
        results1, profile1 = example_1_basic_h2_analysis()
    except Exception as e:
        print(f"\n✗ Example 1 failed: {e}")
    
    try:
        results2, profile2 = example_2_model_comparison()
    except Exception as e:
        print(f"\n✗ Example 2 failed: {e}")
    
    try:
        results3, profile3 = example_3_parameter_study()
    except Exception as e:
        print(f"\n✗ Example 3 failed: {e}")
    
    try:
        profile4, motion4, results4 = example_4_file_io()
    except Exception as e:
        print(f"\n✗ Example 4 failed: {e}")
    
    print("\n" + "="*70)
    print("All examples completed!")
    print("="*70 + "\n")
    
    # Try to display plots
    try:
        plt.show()
    except:
        print("Note: Interactive plots not available (headless mode)")
