"""
SeismoSoil I/O and utility functions

Handles reading/writing of input/output files compatible with MATLAB SeismoSoil
"""

import numpy as np
from pathlib import Path
from typing import Tuple, Dict, List
import pandas as pd
from seismosoil_core import (
    SoilLayer, VsProfile, MotionRecord, 
    H2Model, H4Model, HHModel, EPPModel,
    NonlinearSiteResponse, calculate_vs30, calculate_max_values
)


class SeismoSoilIO:
    """File I/O utilities for SeismoSoil data formats"""
    
    @staticmethod
    def read_vs_profile(filepath: str) -> VsProfile:
        """
        Read Vs profile from text file
        
        Format (tab/space delimited):
        thickness(m)  vs(m/s)  damping(frac)  density(kg/m3)  material_id
        
        Example:
            5.0     250     0.05    1800    1
            5.0     300     0.05    1850    1
            10.0    400     0.05    1900    2
        """
        data = np.loadtxt(filepath)
        
        layers = []
        for row in data:
            thickness, vs, damping, density = row[:4]
            material_id = int(row[4]) if len(row) > 4 else 1
            
            layer = SoilLayer(
                thickness=float(thickness),
                vs=float(vs),
                damping_ratio=float(damping),
                density=float(density),
                material_id=material_id
            )
            layers.append(layer)
        
        return VsProfile(layers=layers)
    
    @staticmethod
    def write_vs_profile(profile: VsProfile, filepath: str):
        """Write Vs profile to file"""
        data = np.column_stack([
            profile.depths,
            profile.velocities,
            profile.damping_ratios,
            profile.densities,
            [layer.material_id for layer in profile.layers]
        ])
        np.savetxt(filepath, data, 
                   fmt='%.6f\t%.6f\t%.6f\t%.6f\t%d',
                   header='thickness(m)\tvs(m/s)\tdamping\tdensity(kg/m3)\tmaterial_id')
    
    @staticmethod
    def read_motion(filepath: str, name: str = None) -> MotionRecord:
        """
        Read ground motion from text file
        
        Format (tab/space delimited):
        time(s)  acceleration(m/s2)
        
        Example:
            0.000    0.0
            0.005   -0.025
            0.010    0.135
        """
        data = np.loadtxt(filepath)
        
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        
        time = data[:, 0]
        accel = data[:, 1]
        
        if name is None:
            name = Path(filepath).stem
        
        return MotionRecord(time=time, acceleration=accel, name=name)
    
    @staticmethod
    def write_motion(motion: MotionRecord, filepath: str):
        """Write ground motion to file"""
        data = np.column_stack([motion.time, motion.acceleration])
        np.savetxt(filepath, data,
                   fmt='%.6f\t%.6f',
                   header='time(s)\tacceleration(m/s2)')
    
    @staticmethod
    def read_constitutive_parameters(filepath: str, model_type: str) -> dict:
        """
        Read constitutive model parameters from file
        
        Formats depend on model type:
        - H2: gamma_ref, n, alpha
        - H4: gamma_ref, n, alpha_g, alpha_x
        - HH: gamma_ref, n, alpha_g, alpha_x, beta
        """
        data = np.loadtxt(filepath)
        
        if model_type.upper() == 'H2':
            return {
                'gamma_ref': data[0],
                'n': data[1],
                'alpha': data[2]
            }
        elif model_type.upper() == 'H4':
            return {
                'gamma_ref': data[0],
                'n': data[1],
                'alpha_g': data[2],
                'alpha_x': data[3]
            }
        elif model_type.upper() == 'HH':
            return {
                'gamma_ref': data[0],
                'n': data[1],
                'alpha_g': data[2],
                'alpha_x': data[3],
                'beta': data[4]
            }
        else:
            raise ValueError(f"Unknown model type: {model_type}")
    
    @staticmethod
    def write_results(results: Dict, output_dir: str, motion_name: str):
        """Write analysis results to directory"""
        output_path = Path(output_dir) / motion_name
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Write time histories
        np.savetxt(
            output_path / f'{motion_name}_time_history_accel.txt',
            results['acceleration'],
            fmt='%.6f',
            delimiter='\t'
        )
        np.savetxt(
            output_path / f'{motion_name}_time_history_veloc.txt',
            results['velocity'],
            fmt='%.6f',
            delimiter='\t'
        )
        np.savetxt(
            output_path / f'{motion_name}_time_history_displ.txt',
            results['displacement'],
            fmt='%.6f',
            delimiter='\t'
        )
        np.savetxt(
            output_path / f'{motion_name}_time_history_strain.txt',
            results['strain'],
            fmt='%.6e',
            delimiter='\t'
        )
        np.savetxt(
            output_path / f'{motion_name}_time_history_stress.txt',
            results['stress'],
            fmt='%.6e',
            delimiter='\t'
        )
        
        # Write maximum values
        max_vals = calculate_max_values(results)
        max_data = np.column_stack([
            results['depth_nodes'],
            max_vals['max_accel']
        ])
        np.savetxt(
            output_path / f'{motion_name}_max_accel.txt',
            max_data,
            fmt='%.6f',
            delimiter='\t'
        )


class AnalysisRunner:
    """High-level interface for running analyses"""
    
    def __init__(self, profile_file: str, model_type: str, 
                 model_params: dict = None):
        """
        Initialize analysis runner
        
        Parameters:
        -----------
        profile_file : Path to Vs profile file
        model_type : 'H2', 'H4', 'HH', or 'EPP'
        model_params : Dictionary of model parameters
        """
        self.profile = SeismoSoilIO.read_vs_profile(profile_file)
        self.model_type = model_type.upper()
        self.model = self._create_model(model_type, model_params)
        self.io = SeismoSoilIO()
    
    def _create_model(self, model_type: str, params: dict):
        """Create appropriate model instance"""
        if params is None:
            params = {}
        
        if model_type.upper() == 'H2':
            return H2Model(
                gamma_ref=params.get('gamma_ref', 0.005),
                n=params.get('n', 0.5),
                alpha=params.get('alpha', 0.5)
            )
        elif model_type.upper() == 'H4':
            return H4Model(
                gamma_ref=params.get('gamma_ref', 0.005),
                n=params.get('n', 0.5),
                alpha_g=params.get('alpha_g', 0.5),
                alpha_x=params.get('alpha_x', 0.5)
            )
        elif model_type.upper() == 'HH':
            return HHModel(
                gamma_ref=params.get('gamma_ref', 0.005),
                n=params.get('n', 0.5),
                alpha_g=params.get('alpha_g', 0.5),
                alpha_x=params.get('alpha_x', 0.5),
                beta=params.get('beta', 0.3)
            )
        elif model_type.upper() == 'EPP':
            return EPPModel(
                gamma_yield=params.get('gamma_yield', 0.01)
            )
        else:
            raise ValueError(f"Unknown model type: {model_type}")
    
    def run_analysis(self, motion_file: str, output_dir: str = None) -> Dict:
        """
        Run nonlinear site response analysis
        
        Parameters:
        -----------
        motion_file : Path to ground motion file
        output_dir : Directory to save results
        
        Returns:
        --------
        results : Dictionary with time histories and profiles
        """
        motion = SeismoSoilIO.read_motion(motion_file)
        
        # Create analysis engine
        analysis = NonlinearSiteResponse(
            profile=self.profile,
            model=self.model,
            dt=motion.dt,
            n_substeps=5
        )
        
        # Run analysis
        results = analysis.compute_response(motion, boundary_type='rigid')
        
        # Save results if output directory specified
        if output_dir:
            SeismoSoilIO.write_results(
                results, output_dir, motion.name
            )
        
        return results
    
    def batch_analysis(self, motion_files: List[str], 
                      output_dir: str) -> Dict[str, Dict]:
        """Run analysis for multiple motions"""
        results = {}
        
        for motion_file in motion_files:
            motion_name = Path(motion_file).stem
            print(f"Processing: {motion_name}...")
            
            try:
                result = self.run_analysis(motion_file, output_dir)
                results[motion_name] = result
                print(f"  ✓ Completed successfully")
            except Exception as e:
                print(f"  ✗ Error: {e}")
                results[motion_name] = None
        
        return results


class ResultsAnalyzer:
    """Post-processing and analysis of results"""
    
    @staticmethod
    def transfer_function(results: Dict, max_freq: float = 30.0) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute frequency-dependent transfer function
        
        Returns:
        --------
        freq : Frequency array (Hz)
        tf : Transfer function (surface / base)
        """
        from scipy.fftpack import fft
        
        time = results['time']
        dt = time[1] - time[0]
        
        # Get surface and base acceleration
        accel_surface = results['acceleration'][:, -1]
        accel_base = results['acceleration'][:, 0]
        
        # FFT
        n = len(accel_surface)
        freq = np.fft.fftfreq(n, dt)[:n//2]
        
        fft_surface = np.abs(fft(accel_surface))[:n//2]
        fft_base = np.abs(fft(accel_base))[:n//2]
        
        # Transfer function
        tf = fft_surface / (fft_base + 1e-10)  # Avoid division by zero
        
        # Filter to max frequency
        mask = freq <= max_freq
        freq = freq[mask]
        tf = tf[mask]
        
        return freq, tf
    
    @staticmethod
    def resonant_frequency(freq: np.ndarray, tf: np.ndarray) -> float:
        """Find dominant frequency from transfer function"""
        return freq[np.argmax(tf)]
    
    @staticmethod
    def amplification_factor(freq: np.ndarray, tf: np.ndarray, 
                            target_freq: float = None) -> float:
        """Get amplification at specific frequency (default: peak)"""
        if target_freq is None:
            return np.max(tf)
        
        idx = np.argmin(np.abs(freq - target_freq))
        return tf[idx]
    
    @staticmethod
    def print_summary(results: Dict, profile: VsProfile):
        """Print analysis summary"""
        max_vals = calculate_max_values(results)
        
        print("\n" + "="*60)
        print("NONLINEAR SITE RESPONSE ANALYSIS - SUMMARY")
        print("="*60)
        
        print(f"\nModel: {results['model']}")
        print(f"Profile depth: {profile.total_depth:.1f} m")
        print(f"Vs30: {calculate_vs30(profile):.1f} m/s")
        
        print(f"\nInput motion:")
        print(f"  Duration: {results['time'][-1]:.2f} s")
        print(f"  PGA (base): {max_vals['max_accel'][0]:.3f} m/s²")
        
        print(f"\nOutput motion:")
        print(f"  PGA (surface): {max_vals['max_accel'][-1]:.3f} m/s²")
        print(f"  Amplification: {max_vals['max_accel'][-1] / (max_vals['max_accel'][0] + 1e-10):.2f}x")
        
        print(f"\nMaximum responses:")
        print(f"  Max strain: {np.max(max_vals['max_strain']):.2e}")
        print(f"  Max stress: {np.max(max_vals['max_stress']):.2e} Pa")
        print(f"  Max displacement: {np.max(max_vals['max_displacement']):.4f} m")
        
        print("\n" + "="*60 + "\n")


# Example usage function
def example_analysis():
    """Example of how to use the Python port"""
    
    # Create a simple profile
    layers = [
        SoilLayer(thickness=5.0, vs=250, damping_ratio=0.05, density=1800),
        SoilLayer(thickness=5.0, vs=300, damping_ratio=0.05, density=1850),
        SoilLayer(thickness=10.0, vs=400, damping_ratio=0.05, density=1900),
    ]
    profile = VsProfile(layers=layers)
    
    # Create ground motion
    dt = 0.01
    t = np.arange(0, 10, dt)
    accel = np.sin(2*np.pi*1*t) * np.exp(-t/5)  # Damped sinusoid
    motion = MotionRecord(time=t, acceleration=accel, name="Example")
    
    # Run analysis with H2 model
    model = H2Model(gamma_ref=0.005, n=0.5, alpha=0.5)
    analysis = NonlinearSiteResponse(profile=profile, model=model, dt=dt)
    results = analysis.compute_response(motion)
    
    # Post-process
    analyzer = ResultsAnalyzer()
    freq, tf = analyzer.transfer_function(results)
    dominant_freq = analyzer.resonant_frequency(freq, tf)
    
    print(f"Dominant frequency: {dominant_freq:.2f} Hz")
    print(f"Peak amplification: {analyzer.amplification_factor(freq, tf):.2f}x")
    
    analyzer.print_summary(results, profile)
    
    return results


if __name__ == "__main__":
    # Run example
    results = example_analysis()
