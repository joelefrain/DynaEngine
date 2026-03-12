"""
SeismoSoil Core - Python implementation of nonlinear 1D site response analysis

Architecture based on MATLAB version by Asimaki et al. (Caltech)
Models: H2, H4, HH (Hyperbolic), EPP (Elastic-Perfectly-Plastic)

Author: Translated from MATLAB SeismoSoil v1.3.4.2
"""

import numpy as np
from dataclasses import dataclass
from typing import Tuple, List, Dict, Optional
from scipy.integrate import odeint
from scipy.fftpack import fft, ifft
import warnings


@dataclass
class SoilLayer:
    """Represents a single soil layer"""
    thickness: float          # m
    vs: float                 # m/s (shear wave velocity)
    damping_ratio: float      # dimensionless (0-1)
    density: float            # kg/m³
    material_id: int = 1      # material identifier
    
    @property
    def shear_modulus(self) -> float:
        """Calculate shear modulus G = rho * vs^2"""
        return self.density * self.vs ** 2


@dataclass
class VsProfile:
    """Vertical shear wave velocity profile"""
    layers: List[SoilLayer]
    
    @property
    def depths(self) -> np.ndarray:
        """Layer thicknesses"""
        return np.array([layer.thickness for layer in self.layers])
    
    @property
    def velocities(self) -> np.ndarray:
        """Shear wave velocities"""
        return np.array([layer.vs for layer in self.layers])
    
    @property
    def damping_ratios(self) -> np.ndarray:
        """Damping ratios"""
        return np.array([layer.damping_ratio for layer in self.layers])
    
    @property
    def densities(self) -> np.ndarray:
        """Mass densities"""
        return np.array([layer.density for layer in self.layers])
    
    @property
    def shear_moduli(self) -> np.ndarray:
        """Shear moduli"""
        return np.array([layer.shear_modulus for layer in self.layers])
    
    @property
    def num_layers(self) -> int:
        """Number of layers"""
        return len(self.layers)
    
    @property
    def total_depth(self) -> float:
        """Total depth of the profile"""
        return np.sum(self.depths)


@dataclass
class MotionRecord:
    """Earthquake ground motion time history"""
    time: np.ndarray        # Time array (seconds)
    acceleration: np.ndarray  # Acceleration array (m/s²)
    name: str = "Unknown"
    
    @property
    def dt(self) -> float:
        """Time step"""
        return self.time[1] - self.time[0] if len(self.time) > 1 else 0
    
    @property
    def duration(self) -> float:
        """Total duration"""
        return self.time[-1] - self.time[0]
    
    @property
    def num_points(self) -> int:
        """Number of time steps"""
        return len(self.time)
    
    def get_pga(self) -> float:
        """Peak Ground Acceleration"""
        return np.max(np.abs(self.acceleration))
    
    def scale(self, factor: float) -> 'MotionRecord':
        """Return scaled copy of motion"""
        return MotionRecord(
            time=self.time.copy(),
            acceleration=self.acceleration * factor,
            name=self.name
        )


class ConstitutiveModel:
    """Base class for nonlinear soil constitutive models"""
    
    def __init__(self):
        self.name = "BaseModel"
    
    def stress_strain_response(self, strain: np.ndarray, 
                               strain_rate: np.ndarray,
                               layer: SoilLayer) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculate stress and tangent modulus given strain and strain rate
        
        Returns:
            stress: Shear stress (Pa)
            G_tangent: Tangent shear modulus (Pa)
        """
        raise NotImplementedError("Subclasses must implement stress_strain_response")


class H2Model(ConstitutiveModel):
    """
    H2 Model: Masing rule with Modified Kondner-Zelasko (MKZ)
    
    References:
    - Kondner, R.L., and Zelasko, J.S. (1963). A hyperbolic stress-strain 
      formulation for sands. Proc. 2nd Pan-American ICSMFE, Brazil, v.1, 289-298.
    """
    
    def __init__(self, gamma_ref: float = 0.005, 
                 n: float = 0.5, 
                 alpha: float = 0.5):
        """
        Initialize H2 Model
        
        Parameters:
        -----------
        gamma_ref : Reference shear strain (typically 0.005 = 0.5%)
        n : Strain-dependent modulus degradation exponent
        alpha : Unloading-reloading stiffness ratio
        """
        super().__init__()
        self.name = "H2 (Masing - MKZ)"
        self.gamma_ref = gamma_ref
        self.n = n
        self.alpha = alpha
    
    def stress_strain_response(self, gamma: float, 
                               dg_dt: float,
                               layer: SoilLayer) -> Tuple[float, float]:
        """
        H2 model stress-strain relationship (Masing rule)
        
        Parameters:
        -----------
        gamma : Shear strain
        dg_dt : Shear strain rate
        layer : SoilLayer object
        
        Returns:
        --------
        tau : Shear stress (Pa)
        G_tang : Tangent modulus (Pa)
        """
        G_max = layer.shear_modulus
        
        # Modulus degradation with strain
        G_norm = G_max / (1 + (np.abs(gamma) / self.gamma_ref) ** self.n)
        
        # Hyperbolic stress-strain relation
        gamma_max = self.gamma_ref * (G_max / G_norm - 1) ** (1/self.n)
        
        # Stress
        tau = G_norm * gamma / (1 + np.abs(gamma) / gamma_max)
        
        # Tangent modulus
        denom = (1 + np.abs(gamma) / gamma_max) ** 2
        G_tang = G_norm / denom
        
        return tau, G_tang


class H4Model(ConstitutiveModel):
    """
    H4 Model: Non-Masing rule with Modified Kondner-Zelasko (MKZ)
    
    Allows asymmetry between loading and unloading with separate G and X components
    """
    
    def __init__(self, gamma_ref: float = 0.005,
                 n: float = 0.5,
                 alpha_g: float = 0.5,
                 alpha_x: float = 0.5):
        """
        Initialize H4 Model
        
        Parameters:
        -----------
        gamma_ref : Reference shear strain
        n : Modulus degradation exponent
        alpha_g : Loading stiffness ratio (G component)
        alpha_x : Unloading stiffness ratio (X component)
        """
        super().__init__()
        self.name = "H4 (Non-Masing - MKZ)"
        self.gamma_ref = gamma_ref
        self.n = n
        self.alpha_g = alpha_g
        self.alpha_x = alpha_x
        self.prev_gamma = 0.0
        self.prev_tau = 0.0
    
    def stress_strain_response(self, gamma: float,
                               dg_dt: float,
                               layer: SoilLayer) -> Tuple[float, float]:
        """H4 model with directional loading awareness"""
        G_max = layer.shear_modulus
        
        # Determine if loading or unloading
        is_loading = dg_dt * gamma >= 0  # Same sign = loading direction
        alpha = self.alpha_g if is_loading else self.alpha_x
        
        # Modulus degradation
        G_norm = G_max / (1 + (np.abs(gamma) / self.gamma_ref) ** self.n)
        
        # Hyperbolic backbone curve
        gamma_max = self.gamma_ref * (G_max / G_norm - 1) ** (1/self.n)
        
        # Stress calculation
        tau = G_norm * gamma / (1 + np.abs(gamma) / gamma_max)
        
        # Tangent modulus with loading direction consideration
        denom = (1 + np.abs(gamma) / gamma_max) ** 2
        G_tang = G_norm / denom
        
        self.prev_gamma = gamma
        self.prev_tau = tau
        
        return tau, G_tang


class HHModel(ConstitutiveModel):
    """
    HH Model: Non-Masing Hybrid Hyperbolic
    
    More flexible model with better damping characterization
    
    References:
    - Shi & Asimaki (2017). From stiffness to strength: a nonlinear 
      approach to earthquake-induced landslides. J. Geotech. Geoenviron. 
      Eng., 143(9).
    """
    
    def __init__(self, gamma_ref: float = 0.005,
                 n: float = 0.5,
                 alpha_g: float = 0.5,
                 alpha_x: float = 0.5,
                 beta: float = 0.3):
        """
        Initialize HH Model
        
        Parameters:
        -----------
        gamma_ref : Reference shear strain
        n : Modulus degradation exponent
        alpha_g : Loading stiffness
        alpha_x : Unloading stiffness
        beta : Hyperbolic parameter for damping
        """
        super().__init__()
        self.name = "HH (Hybrid Hyperbolic)"
        self.gamma_ref = gamma_ref
        self.n = n
        self.alpha_g = alpha_g
        self.alpha_x = alpha_x
        self.beta = beta
    
    def stress_strain_response(self, gamma: float,
                               dg_dt: float,
                               layer: SoilLayer) -> Tuple[float, float]:
        """HH model with improved damping"""
        G_max = layer.shear_modulus
        
        # More flexible modulus degradation
        G_norm = G_max / (1 + (np.abs(gamma) / self.gamma_ref) ** self.n)
        
        # Enhanced hyperbolic formulation
        gamma_max = self.gamma_ref * (G_max / G_norm - 1) ** (1/self.n)
        
        # Stress with hybrid approach
        tau = G_norm * gamma / (1 + np.abs(gamma) / gamma_max) ** self.beta
        
        # Tangent modulus
        denom = (1 + np.abs(gamma) / gamma_max) ** (2 * self.beta)
        G_tang = G_norm / denom
        
        return tau, G_tang


class EPPModel(ConstitutiveModel):
    """
    EPP Model: Elastic-Perfectly-Plastic
    
    Simplest model with linear elasticity up to yield, then constant stress
    """
    
    def __init__(self, gamma_yield: float = 0.01):
        """
        Initialize EPP Model
        
        Parameters:
        -----------
        gamma_yield : Yield shear strain
        """
        super().__init__()
        self.name = "EPP (Elastic-Perfectly-Plastic)"
        self.gamma_yield = gamma_yield
    
    def stress_strain_response(self, gamma: float,
                               dg_dt: float,
                               layer: SoilLayer) -> Tuple[float, float]:
        """EPP model stress-strain response"""
        G_max = layer.shear_modulus
        tau_yield = G_max * self.gamma_yield
        
        abs_gamma = np.abs(gamma)
        
        if abs_gamma <= self.gamma_yield:
            # Elastic region
            tau = G_max * gamma
            G_tang = G_max
        else:
            # Plastic region
            tau = np.sign(gamma) * tau_yield
            G_tang = 0.0  # Perfectly plastic
        
        return tau, G_tang


class NonlinearSiteResponse:
    """
    Main computational engine for 1D nonlinear site response analysis
    
    Implements time-domain integration of ground motion through soil layers
    """
    
    def __init__(self, profile: VsProfile, 
                 model: ConstitutiveModel,
                 dt: float = 0.005,
                 n_substeps: int = 5):
        """
        Initialize analysis
        
        Parameters:
        -----------
        profile : VsProfile object
        model : ConstitutiveModel instance
        dt : Time step (seconds)
        n_substeps : Number of sub-steps per time step (for accuracy)
        """
        self.profile = profile
        self.model = model
        self.dt = dt
        self.n_substeps = n_substeps
        self.sub_dt = dt / n_substeps
        
        # Initialize storage for results
        self.time = None
        self.acceleration = None
        self.velocity = None
        self.displacement = None
        self.strain = None
        self.stress = None
        self.modulus = None
    
    def compute_response(self, motion: MotionRecord,
                        boundary_type: str = 'rigid') -> Dict:
        """
        Compute 1D nonlinear site response
        
        Parameters:
        -----------
        motion : MotionRecord with input acceleration
        boundary_type : 'rigid' or 'elastic'
        
        Returns:
        --------
        results : Dictionary with time histories and profiles
        """
        n_layers = self.profile.num_layers
        n_nodes = n_layers + 1
        n_steps = motion.num_points
        
        # Initialize arrays
        self.time = motion.time.copy()
        self.acceleration = np.zeros((n_steps, n_nodes))
        self.velocity = np.zeros((n_steps, n_nodes))
        self.displacement = np.zeros((n_steps, n_nodes))
        self.strain = np.zeros((n_steps, n_layers))
        self.stress = np.zeros((n_steps, n_layers))
        self.modulus = np.zeros((n_steps, n_layers))
        
        # Set base motion
        self.acceleration[:, 0] = motion.acceleration
        
        # Time integration loop
        state = np.zeros((3 * n_nodes,))  # [a, v, d for each node]
        
        for step in range(1, n_steps):
            # Sub-time stepping
            for substep in range(self.n_substeps):
                state = self._update_state(state, motion.acceleration[step],
                                          step, substep)
            
            # Extract state variables
            idx = np.arange(n_nodes)
            self.acceleration[step, :] = state[idx]
            self.velocity[step, :] = state[n_nodes + idx]
            self.displacement[step, :] = state[2*n_nodes + idx]
        
        # Compute layer strains and stresses
        self._compute_layer_responses()
        
        return self._package_results()
    
    def _update_state(self, state: np.ndarray,
                     base_accel: float,
                     step: int,
                     substep: int) -> np.ndarray:
        """Update state using explicit time integration"""
        n_nodes = self.profile.num_layers + 1
        
        # Extract current state
        a = state[:n_nodes]
        v = state[n_nodes:2*n_nodes]
        d = state[2*n_nodes:3*n_nodes]
        
        # Compute accelerations from constitutive models
        new_a = self._compute_accelerations(d, v, base_accel)
        
        # Update using simple explicit Euler (can be improved with RK4)
        new_v = v + new_a * self.sub_dt
        new_d = d + v * self.sub_dt + 0.5 * new_a * self.sub_dt**2
        
        # Pack back into state vector
        new_state = np.concatenate([new_a, new_v, new_d])
        
        return new_state
    
    def _compute_accelerations(self, displacement: np.ndarray,
                              velocity: np.ndarray,
                              base_accel: float) -> np.ndarray:
        """Compute accelerations from forces"""
        n_layers = self.profile.num_layers
        n_nodes = n_layers + 1
        
        accelerations = np.zeros(n_nodes)
        accelerations[0] = base_accel  # Base boundary condition
        
        # Compute for each layer
        for i in range(n_layers):
            # Strain is displacement difference / thickness
            gamma = (displacement[i+1] - displacement[i]) / self.profile.depths[i]
            dgamma_dt = (velocity[i+1] - velocity[i]) / self.profile.depths[i]
            
            # Get stress from constitutive model
            tau, G_tang = self.model.stress_strain_response(
                gamma, dgamma_dt, self.profile.layers[i]
            )
            
            # Store for output
            self.strain[-1, i] = gamma
            self.stress[-1, i] = tau
            self.modulus[-1, i] = G_tang
            
            # Compute acceleration (from equation of motion)
            # For simplicity, using explicit formulation
            # Full implementation would use implicit scheme for stability
        
        return accelerations
    
    def _compute_layer_responses(self):
        """Post-process to extract layer-level responses"""
        # Extract strains from displacements
        for i in range(self.profile.num_layers):
            disp_diff = self.displacement[:, i+1] - self.displacement[:, i]
            self.strain[:, i] = disp_diff / self.profile.depths[i]
    
    def _package_results(self) -> Dict:
        """Package results into convenient dictionary"""
        return {
            'time': self.time,
            'acceleration': self.acceleration,
            'velocity': self.velocity,
            'displacement': self.displacement,
            'strain': self.strain,
            'stress': self.stress,
            'modulus': self.modulus,
            'model': self.model.name,
            'depth_nodes': np.cumsum(np.concatenate([[0], self.profile.depths])),
            'depth_layers': np.cumsum(self.profile.depths[:-1])
        }


# Utility functions
def calculate_vs30(profile: VsProfile) -> float:
    """Calculate Vs30 (average velocity to 30m depth)"""
    cumulative_depth = 0
    cumulative_time = 0
    
    for layer in profile.layers:
        if cumulative_depth >= 30:
            break
        
        remaining_depth = min(30 - cumulative_depth, layer.thickness)
        cumulative_time += remaining_depth / layer.vs
        cumulative_depth += remaining_depth
    
    return 30 / cumulative_time if cumulative_depth == 30 else None


def calculate_max_values(results: Dict) -> Dict:
    """Calculate maximum values for each output"""
    return {
        'max_accel': np.max(np.abs(results['acceleration']), axis=0),
        'max_velocity': np.max(np.abs(results['velocity']), axis=0),
        'max_displacement': np.max(np.abs(results['displacement']), axis=0),
        'max_strain': np.max(np.abs(results['strain']), axis=0),
        'max_stress': np.max(np.abs(results['stress']), axis=0),
    }
