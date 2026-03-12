"""
SeismoSoil Advanced - Nonlinear 1D Site Response Analysis

Análisis simplificado con un modelo constitutivo único para todo el perfil.

REFERENCIAS CLAVE:
- Kondner & Zelasko (1963) - Modelo hiperbólico base
- Hardin & Drnevich (1972) - Degradación de módulo y amortiguamiento
- Masing (1926) - Regla de histéresis
- Kramer (1996) - Geotechnical Earthquake Engineering
"""

import numpy as np
from dataclasses import dataclass
from typing import Tuple, List, Dict, Optional


# ═════════════════════════════════════════════════════════════════════════════
# CLASES BASE
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class BackboneCurve:
    """Curva de degradación τ-γ"""
    strain: np.ndarray
    stress: np.ndarray
    modulus: np.ndarray
    modulus_norm: np.ndarray
    
    def get_stress(self, gamma: float) -> float:
        """Interpolar esfuerzo en deformación"""
        return np.interp(np.abs(gamma), self.strain, self.stress) * np.sign(gamma)
    
    def get_modulus(self, gamma: float) -> float:
        """Interpolar módulo tangente"""
        return np.interp(np.abs(gamma), self.strain, self.modulus)


@dataclass
class DampingCurve:
    """Curva de amortiguamiento ξ(γ)"""
    strain: np.ndarray
    damping: np.ndarray
    
    def get_damping(self, gamma: float) -> float:
        """Interpolar amortiguamiento"""
        return np.interp(np.abs(gamma), self.strain, self.damping)


@dataclass
class SoilLayer:
    """Capa de suelo (solo propiedades geométricas)"""
    thickness: float
    vs: float
    density: float
    
    @property
    def shear_modulus(self) -> float:
        """G = ρ * vs²"""
        return self.density * self.vs ** 2


@dataclass
class VsProfile:
    """Perfil vertical (todas las capas usan el mismo modelo)"""
    layers: List[SoilLayer]
    
    @property
    def num_layers(self) -> int:
        return len(self.layers)
    
    @property
    def depths(self) -> np.ndarray:
        return np.array([layer.thickness for layer in self.layers])
    
    @property
    def velocities(self) -> np.ndarray:
        return np.array([layer.vs for layer in self.layers])
    
    @property
    def densities(self) -> np.ndarray:
        return np.array([layer.density for layer in self.layers])
    
    @property
    def total_depth(self) -> float:
        return np.sum(self.depths)
    
    def print_stratigraphy(self):
        """Imprimir perfil"""
        print("\n" + "═"*80)
        print(f"PERFIL ({self.num_layers} capas, profundidad: {self.total_depth:.1f} m)")
        print("═"*80)
        depth = 0
        for i, layer in enumerate(self.layers):
            print(f"Capa {i+1:2d}: {depth:6.2f}-{depth+layer.thickness:6.2f} m | "
                  f"Vs={layer.vs:5.0f} m/s | ρ={layer.density:5.0f} kg/m³")
            depth += layer.thickness
        print("═"*80 + "\n")


@dataclass
class MotionRecord:
    """Registro sísmico de entrada"""
    time: np.ndarray
    acceleration: np.ndarray
    name: str = "Unknown"
    
    @property
    def dt(self) -> float:
        return self.time[1] - self.time[0] if len(self.time) > 1 else 0.0
    
    @property
    def duration(self) -> float:
        return self.time[-1] - self.time[0]
    
    @property
    def num_points(self) -> int:
        return len(self.time)
    
    def get_pga(self) -> float:
        """Peak Ground Acceleration"""
        return np.max(np.abs(self.acceleration))


# ═════════════════════════════════════════════════════════════════════════════
# MOTOR DE ANÁLISIS NO LINEAL
# ═════════════════════════════════════════════════════════════════════════════

class NonlinearSiteResponseAdvanced:
    """
    Análisis no lineal 1D con modelo constitutivo único para todo el perfil.
    
    El tipo de curva (H2, H4, HH, EPP) se especifica en __init__ y aplica
    a TODAS las capas del perfil.
    """
    
    def __init__(self, profile: VsProfile, 
                 model_type: str = 'H2',
                 G_max: Optional[float] = None,
                 gamma_ref: float = 0.005,
                 n: float = 0.5,
                 damping_ref: float = 0.05,
                 alpha_g: Optional[float] = None,
                 alpha_x: Optional[float] = None,
                 beta: Optional[float] = None,
                 gamma_yield: Optional[float] = None,
                 dt: float = 0.005):
        """
        Inicializar análisis no lineal
        
        Parameters:
        -----------
        profile : VsProfile con capas
        model_type : 'H2', 'H4', 'HH', o 'EPP' (aplica a TODO el perfil)
        G_max : Módulo máximo. Si None, usa G = ρ*vs² de cada capa
        gamma_ref : Deformación de referencia (típicamente 0.005)
        n : Exponente de degradación (típicamente 0.5)
        damping_ref : Amortiguamiento a gamma_ref
        alpha_g, alpha_x : Parámetros para H4/HH (rigidez carga/descarga)
        beta : Parámetro de flexibilidad para HH
        gamma_yield : Deformación de fluencia para EPP
        dt : Time step
        """
        self.profile = profile
        self.model_type = model_type
        self.gamma_ref = gamma_ref
        self.n = n
        self.damping_ref = damping_ref
        self.dt = dt
        
        # Parámetros opcionales por modelo
        if model_type in ['H4', 'HH']:
            self.alpha_g = alpha_g if alpha_g is not None else 0.5
            self.alpha_x = alpha_x if alpha_x is not None else 0.5
        
        if model_type == 'HH':
            self.beta = beta if beta is not None else 0.3
        
        if model_type == 'EPP':
            self.gamma_yield = gamma_yield if gamma_yield is not None else 0.01
        
        # Generar curvas para cada capa
        self.backbone_curves = []
        self.damping_curves = []
        
        for layer in profile.layers:
            G_max_layer = G_max if G_max is not None else layer.shear_modulus
            bb, dc = self._generate_curves(G_max_layer)
            self.backbone_curves.append(bb)
            self.damping_curves.append(dc)
        
        self.results = None
    
    def _generate_curves(self, G_max: float) -> Tuple[BackboneCurve, DampingCurve]:
        """Generar curvas de degradación para una capa con G_max dado"""
        
        gamma_array = np.logspace(-6, 0, 100)
        
        # G(γ) = G_max / [1 + (γ/γ_r)^n]
        G_norm = 1.0 / (1.0 + (gamma_array / self.gamma_ref) ** self.n)
        G_array = G_max * G_norm
        
        # Amortiguamiento
        xi_array = self.damping_ref * (1.0 - G_norm) / (1.0 - 1.0/(1.0 + 1.0))
        xi_array = np.clip(xi_array, 0.0, 0.3)
        
        # Esfuerzo
        tau_array = gamma_array * G_array
        
        backbone = BackboneCurve(
            strain=gamma_array,
            stress=tau_array,
            modulus=G_array,
            modulus_norm=G_norm
        )
        
        damping = DampingCurve(
            strain=gamma_array,
            damping=xi_array
        )
        
        return backbone, damping
    
    def compute_response(self, motion: MotionRecord) -> Dict:
        """
        Computar respuesta no lineal 1D
        
        Parameters:
        -----------
        motion : Registro sísmico
        
        Returns:
        --------
        Dictionary con historias de tiempo y máximos
        """
        n_layers = self.profile.num_layers
        n_nodes = n_layers + 1
        n_steps = motion.num_points
        
        # Arrays de salida
        accel = np.zeros((n_steps, n_nodes))
        velocity = np.zeros((n_steps, n_nodes))
        displacement = np.zeros((n_steps, n_nodes))
        strain = np.zeros((n_steps, n_layers))
        stress = np.zeros((n_steps, n_layers))
        
        # Aceleración en base
        accel[:, 0] = motion.acceleration
        
        # Estado: [a_1, ..., a_n, v_1, ..., v_n, u_1, ..., u_n]
        state = np.zeros(3 * n_nodes)
        
        # Integración temporal (Euler simple)
        for step in range(1, n_steps):
            base_acc = motion.acceleration[step]
            state[0] = base_acc
            
            # Aceleración en otros nodos
            for i in range(n_layers):
                dz = self.profile.depths[i]
                gamma = (state[2*n_nodes + i+1] - state[2*n_nodes + i]) / dz
                
                tau_i = self.backbone_curves[i].get_stress(gamma)
                
                if i < n_layers - 1:
                    dz_next = self.profile.depths[i+1]
                    gamma_next = (state[2*n_nodes + i+2] - state[2*n_nodes + i+1]) / dz_next
                    tau_next = self.backbone_curves[i+1].get_stress(gamma_next)
                    force = (tau_next - tau_i) / dz
                else:
                    force = -tau_i / dz
                
                state[i+1] = force / self.profile.densities[i]
            
            # Integración: v y u
            state[n_nodes:2*n_nodes] += state[:n_nodes] * self.dt
            state[2*n_nodes:] += state[n_nodes:2*n_nodes] * self.dt
            
            # Guardar
            accel[step, :] = state[:n_nodes]
            velocity[step, :] = state[n_nodes:2*n_nodes]
            displacement[step, :] = state[2*n_nodes:]
        
        # Calcular deformaciones y esfuerzos
        for step in range(n_steps):
            for i in range(n_layers):
                dz = self.profile.depths[i]
                gamma = (displacement[step, i+1] - displacement[step, i]) / dz
                strain[step, i] = gamma
                stress[step, i] = self.backbone_curves[i].get_stress(gamma)
        
        # Empaquetar resultados
        depths_nodes = np.cumsum(np.concatenate([[0], self.profile.depths]))
        
        pga_surf = np.max(np.abs(accel[:, -1]))
        pga_input = motion.get_pga()
        
        self.results = {
            'time': motion.time,
            'acceleration': accel,
            'velocity': velocity,
            'displacement': displacement,
            'strain': strain,
            'stress': stress,
            'depth_nodes': depths_nodes,
            'pga_input': pga_input,
            'pga_surface': pga_surf,
            'pga_output': pga_surf,  # Alias
            'amplification': pga_surf / pga_input if pga_input > 0 else 1.0,
            'max_strain': np.max(np.abs(strain)) if strain.size > 0 else 0.0,
            'max_shear_strain': np.max(np.abs(strain)) if strain.size > 0 else 0.0,  # Alias
            'model': self.model_type
        }
        
        return self.results


# ═════════════════════════════════════════════════════════════════════════════
# I/O
# ═════════════════════════════════════════════════════════════════════════════

def read_profile(filepath: str) -> VsProfile:
    """
    Leer perfil de archivo .txt
    
    Formato:
    ─────────────────────────────────────
    thickness(m)  vs(m/s)  density(kg/m³)
    5.0           250      1800
    5.0           300      1850
    10.0          400      1900
    ─────────────────────────────────────
    """
    data = np.genfromtxt(filepath, skip_header=0)
    
    if data.ndim == 1:
        data = data.reshape(1, -1)
    
    layers = []
    for row in data:
        layer = SoilLayer(
            thickness=float(row[0]),
            vs=float(row[1]),
            density=float(row[2])
        )
        layers.append(layer)
    
    return VsProfile(layers=layers)


def write_profile(profile: VsProfile, filepath: str):
    """Escribir perfil a archivo .txt"""
    with open(filepath, 'w') as f:
        f.write("thickness(m)\tvs(m/s)\tdensity(kg/m³)\n")
        for layer in profile.layers:
            f.write(f"{layer.thickness:.1f}\t{layer.vs:.0f}\t{layer.density:.0f}\n")


# ═════════════════════════════════════════════════════════════════════════════
# UTILIDADES
# ═════════════════════════════════════════════════════════════════════════════

def create_example_profile() -> VsProfile:
    """Crear perfil de ejemplo simple"""
    layers = [
        SoilLayer(thickness=5.0, vs=250, density=1800),
        SoilLayer(thickness=5.0, vs=300, density=1850),
        SoilLayer(thickness=10.0, vs=400, density=1900),
        SoilLayer(thickness=15.0, vs=500, density=2000)
    ]
    return VsProfile(layers=layers)


def create_example_motion(duration: float = 10.0, dt: float = 0.01) -> MotionRecord:
    """Crear movimiento sísmico de ejemplo"""
    time = np.arange(0, duration, dt)
    pga = 0.3
    freq = 2.0
    damping_exp = 0.3
    accel = pga * np.sin(2*np.pi*freq*time) * np.exp(-damping_exp*time)
    
    return MotionRecord(time=time, acceleration=accel, name="Synthetic Pulse")


if __name__ == "__main__":
    # Ejemplo quick
    profile = create_example_profile()
    profile.print_stratigraphy()
    
    motion = create_example_motion()
    
    # Análisis con modelo H2
    analysis = NonlinearSiteResponseAdvanced(profile, model_type='H2')
    results = analysis.compute_response(motion)
    
    print(f"✓ Input PGA: {results['pga_input']:.3f} m/s²")
    print(f"✓ Surface PGA: {results['pga_surface']:.3f} m/s²")
    print(f"✓ Amplification: {results['amplification']:.2f}×")
    print(f"✓ Max strain: {results['max_strain']:.2e}")
    print(f"✓ Model: {results['model']}")
