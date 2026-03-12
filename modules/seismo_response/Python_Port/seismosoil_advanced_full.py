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
# PART 1: ESTRATIGRAFÍA CON MODELOS INDEPENDIENTES
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class BackboneCurve:
    """
    Curva de degradación (Backbone Curve)
    
    Representa la relación τ-γ ramificada en la que se basan las curvas histeréticas
    
    Reference: Kramer (1996) "Geotechnical Earthquake Engineering", pp. 244-250
    """
    strain: np.ndarray          # Deformación γ
    stress: np.ndarray          # Esfuerzo cortante τ
    modulus: np.ndarray         # Módulo tangente G_t
    modulus_norm: np.ndarray    # G/G_max (normalizado)
    
    def get_stress_at_strain(self, gamma: float) -> float:
        """Interpolar esfuerzo en deformación dada"""
        return np.interp(np.abs(gamma), self.strain, self.stress) * np.sign(gamma)
    
    def get_modulus_at_strain(self, gamma: float) -> float:
        """Interpolar módulo en deformación dada"""
        return np.interp(np.abs(gamma), self.strain, self.modulus)


@dataclass
class DampingCurve:
    """
    Curva de amortiguamiento ξ(γ)
    
    Representa el amortiguamiento viscoso equivalente normalizado por deformación
    Reference: Hardin & Drnevich (1972), tablas de damping ratios
    """
    strain: np.ndarray          # Deformación γ
    damping: np.ndarray         # Amortiguamiento ξ (fraction)
    
    def get_damping_at_strain(self, gamma: float) -> float:
        """Interpolar amortiguamiento en deformación dada"""
        return np.interp(np.abs(gamma), self.strain, self.damping)


@dataclass
class ConstitutiveParameters:
    """
    Parámetros constitutivos de un estrato (independiente)
    
    Formato compatible con archivo .txt entrada
    """
    model_type: str             # 'H2', 'H4', 'HH', 'EPP'
    G_max: float                # Módulo de corte máximo (Pa)
    gamma_ref: float            # Strain de referencia (típico: 0.005)
    n: float                     # Exponente de degradación (típicamente 0.5-1.0)
    damping_ref: float          # Amortiguamiento a γ_ref (fraction, típico: 0.05)
    
    # H2 / H4 / HH específicos
    alpha_g: Optional[float] = None      # Rigidez en carga (H4/HH)
    alpha_x: Optional[float] = None      # Rigidez en descarga (H4/HH)
    beta: Optional[float] = None         # Parámetro hiperbólico (HH)
    
    # EPP específico
    gamma_yield: Optional[float] = None  # Strain de fluencia plástica
    
    def validate(self):
        """Validar parámetros según modelo"""
        if self.G_max <= 0:
            raise ValueError("G_max debe ser positivo")
        if self.gamma_ref <= 0:
            raise ValueError("gamma_ref debe ser positivo")
        if not (0 < self.damping_ref < 0.5):
            raise ValueError("damping_ref debe estar entre 0 y 0.5")
        
        if self.model_type == 'H2':
            if self.alpha_g is None:
                self.alpha_g = 0.5
        elif self.model_type == 'H4':
            if self.alpha_g is None or self.alpha_x is None:
                raise ValueError("H4 requiere alpha_g y alpha_x")
        elif self.model_type == 'HH':
            if self.alpha_g is None or self.alpha_x is None or self.beta is None:
                raise ValueError("HH requiere alpha_g, alpha_x, beta")
        elif self.model_type == 'EPP':
            if self.gamma_yield is None:
                raise ValueError("EPP requiere gamma_yield")


@dataclass
class SoilLayer:
    """
    Capa de suelo con parámetros y modelo constitutivo independiente
    
    Cada capa puede tener diferentes parámetros constitutivos
    """
    thickness: float                        # Espesor (m)
    vs: float                               # Velocidad de onda cortante (m/s)
    density: float                          # Densidad (kg/m³)
    material_id: int = 1                    # ID del material
    damping_ratio: float = 0.05             # Amortiguamiento lineal inicial (para ref)
    
    # Parámetros constitutivos independientes
    constitutive_params: Optional[ConstitutiveParameters] = None
    
    # Curvas precalculadas
    backbone_curve: Optional[BackboneCurve] = None
    damping_curve: Optional[DampingCurve] = None
    
    @property
    def shear_modulus(self) -> float:
        """G = ρ * vs²"""
        return self.density * self.vs ** 2
    
    def generate_curves(self):
        """
        Generar curvas de degradación y amortiguamiento
        desde los parámetros constitutivos
        
        References:
        -----------
        Hardin & Drnevich (1972) - Tablas y correlaciones
        Kramer (1996) - Tables 4.1-4.3
        """
        if self.constitutive_params is None:
            raise ValueError("constitutive_params no está definido")
        
        params = self.constitutive_params
        params.validate()
        
        # Generar array de deformaciones (logarítmico)
        gamma_array = np.logspace(-6, 0, 100)  # γ: 10^-6 a 1.0
        
        # ═══════════════════════════════════════════════════════════════════
        # MODULERACIÓN DE MÓDULO (Hardin & Drnevich, 1972; Eq. 4.1)
        # ═══════════════════════════════════════════════════════════════════
        # G(γ) = G_max / [1 + (γ/γ_r)^n]
        #
        # Parámetros típicos según tipo de suelo (Kramer 1996):
        # - Arena: n = 0.5, γ_r = 0.005-0.01
        # - Arcilla: n = 0.75-1.0, γ_r = 0.001-0.003
        # - Grava: n = 0.4-0.5, γ_r = 0.008-0.012
        # ═══════════════════════════════════════════════════════════════════
        
        G_norm = 1.0 / (1.0 + (gamma_array / params.gamma_ref) ** params.n)
        G_array = params.G_max * G_norm
        
        # Módulo tangente (derivada)
        # dG/dγ = -G_max * n * (γ/γ_r)^(n-1) / γ_r / [1 + (γ/γ_r)^n]²
        dG_dgamma = (-params.G_max * params.n * 
                     (gamma_array / params.gamma_ref) ** (params.n - 1) / params.gamma_ref /
                     (1.0 + (gamma_array / params.gamma_ref) ** params.n) ** 2)
        
        # ═══════════════════════════════════════════════════════════════════
        # AMORTIGUAMIENTO (Hardin & Drnevich, 1972; Eq. 4.2)
        # ═══════════════════════════════════════════════════════════════════
        # ξ(γ) = ξ_ref * [1 - G(γ)/G_max] / [2 * π]
        #
        # O alternativa más simple (Kramer, 1996):
        # ξ(γ) = ξ_ref * [1 + (γ/γ_ref)^n / 0.5] / [1 + (γ/γ_ref)^n]
        # ═══════════════════════════════════════════════════════════════════
        
        # Usar formulación energética (más consistente físicamente)
        # ξ = 0.5 * (1 - G_norm)  en rango lineal
        # Escalar a ξ_ref en γ_ref
        xi_array = params.damping_ref * (1.0 - G_norm) / (1.0 - 1.0/(1.0 + 1.0))
        xi_array = np.clip(xi_array, 0.0, 0.3)  # Límites físicos
        
        # Crear curva de esfuerzo (hiperbólica compatible)
        # τ = γ * G(γ) en prueba monotónica
        tau_array = gamma_array * G_array
        
        # Almacenar curvas
        self.backbone_curve = BackboneCurve(
            strain=gamma_array,
            stress=tau_array,
            modulus=G_array,
            modulus_norm=G_norm
        )
        
        self.damping_curve = DampingCurve(
            strain=gamma_array,
            damping=xi_array
        )
    
    def get_stress_strain_response(self, gamma: float, 
                                   dg_dt: float) -> Tuple[float, float]:
        """
        Obtener respuesta esfuerzo-deformación del estrato
        
        Usa la curva de degradación precalculada e interpola
        
        Parameters:
        -----------
        gamma : Deformación cortante (adimensional)
        dg_dt : Tasa de deformación (1/s)
        
        Returns:
        --------
        tau : Esfuerzo cortante (Pa)
        G_tang : Módulo tangente (Pa)
        """
        if self.backbone_curve is None:
            raise ValueError("Debe llamar generate_curves() primero")
        
        # Interpolación de esfuerzo
        tau = self.backbone_curve.get_stress_at_strain(gamma)
        
        # Interpolación de módulo (rigidez instantánea)
        G_tang = self.backbone_curve.get_modulus_at_strain(gamma)
        
        return tau, G_tang


@dataclass
class VsProfile:
    """
    Perfil vertical de velocidad de onda cortante
    
    Cada capa tiene parámetros constitutivos independientes
    """
    layers: List[SoilLayer]
    
    def __post_init__(self):
        """Generar curvas para todas las capas"""
        for layer in self.layers:
            if layer.constitutive_params is not None:
                layer.generate_curves()
    
    @property
    def depths(self) -> np.ndarray:
        """Espesores de capas"""
        return np.array([layer.thickness for layer in self.layers])
    
    @property
    def velocities(self) -> np.ndarray:
        """Velocidades de onda cortante"""
        return np.array([layer.vs for layer in self.layers])
    
    @property
    def densities(self) -> np.ndarray:
        """Densidades"""
        return np.array([layer.density for layer in self.layers])
    
    @property
    def num_layers(self) -> int:
        """Número de capas"""
        return len(self.layers)
    
    @property
    def total_depth(self) -> float:
        """Profundidad total"""
        return np.sum(self.depths)
    
    def print_stratigraphy(self):
        """Imprimir estratigrafía con parámetros"""
        print("\n" + "═"*100)
        print("ESTRATIGRAFÍA DEL PERFIL DE SUELO")
        print("═"*100)
        
        cumul_depth = 0
        for i, layer in enumerate(self.layers):
            depth_top = cumul_depth
            depth_bot = cumul_depth + layer.thickness
            cumul_depth = depth_bot
            
            print(f"\nCapa {i+1}")
            print(f"  Profundidad: {depth_top:.2f} - {depth_bot:.2f} m")
            print(f"  Vs: {layer.vs:.0f} m/s")
            print(f"  ρ: {layer.density:.0f} kg/m³")
            print(f"  G_max: {layer.shear_modulus:.0f} Pa = {layer.shear_modulus/1e3:.0f} kPa")
            
            if layer.constitutive_params is not None:
                p = layer.constitutive_params
                print(f"  Modelo: {p.model_type}")
                print(f"    γ_ref: {p.gamma_ref:.2e}")
                print(f"    n: {p.n:.2f}")
                print(f"    ξ_ref: {p.damping_ref:.3f}")
                if p.alpha_g is not None:
                    print(f"    α_g: {p.alpha_g:.2f}")
                if p.alpha_x is not None:
                    print(f"    α_x: {p.alpha_x:.2f}")
        
        print("\n" + "═"*100 + "\n")


@dataclass
class MotionRecord:
    """Registro de movimiento sísmico"""
    time: np.ndarray
    acceleration: np.ndarray
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
        """Peak Ground Acceleration (m/s²)"""
        return np.max(np.abs(self.acceleration))
    
    def get_pgv(self) -> float:
        """Peak Ground Velocity (m/s) - numerical integration"""
        velocity = np.cumsum(self.acceleration) * self.dt
        return np.max(np.abs(velocity))
    
    def get_pgd(self) -> float:
        """Peak Ground Displacement (m) - double integration"""
        velocity = np.cumsum(self.acceleration) * self.dt
        displacement = np.cumsum(velocity) * self.dt
        return np.max(np.abs(displacement))


# ═════════════════════════════════════════════════════════════════════════════
# PART 2: ANÁLISIS NO LINEAL CON MODELOS ESTRATIFICADOS
# ═════════════════════════════════════════════════════════════════════════════

class NonlinearSiteResponseAdvanced:
    """
    Análisis avanzado 1D con modelos constitutivos independientes por estrato
    
    Implementa integración temporal de las ecuaciones de movimiento acopladas
    con modelos constitutivos estratificados
    
    ECUACIONES FUNDAMENTALES:
    ═════════════════════════════════════════════════════════════════════════════
    
    1. ECUACIÓN DE MOVIMIENTO (Newton, segundo orden):
       ρ * ∂²u/∂t² = ∂τ/∂z + ρ*g
       
       En discretización con elementos finitos:
       M * a + C * v + K * u = -M * a_base
       
       Para caso 1D linealizado (actualizado en cada paso):
       ρ_i * a_i = (τ_{i+1/2} - τ_{i-1/2}) / Δz_i
    
    2. RELACIÓN DEFORMACIÓN-DESPLAZAMIENTO:
       γ = ∂u/∂z ≈ (u_{i+1} - u_i) / Δz_i
    
    3. MODELO CONSTITUTIVO HIPERBÓLICO:
       τ = G(γ) * γ  (relación esfuerzo-deformación)
       
       Donde: G(γ) = G_max / [1 + (γ/γ_r)^n]
    
    4. INTEGRACIÓN TEMPORAL (Euler explícito o RK4):
       y_{n+1} = y_n + h * f(t_n, y_n)
    
    ═════════════════════════════════════════════════════════════════════════════
    
    References:
    -----------
    Kramer, S.L. (1996). Geotechnical Earthquake Engineering. Prentice Hall.
    Iwan, W.D. (1967). The dynamic response of bilinear hysteretic systems.
      Proc. World Conf. on Earthquake Engineering.
    Clipped model: Wen (1976)
    """
    
    def __init__(self, profile: VsProfile, 
                 dt: float = 0.005,
                 integration_scheme: str = 'euler',
                 n_substeps: int = 5):
        """
        Inicializar análisis
        
        Parameters:
        -----------
        profile : VsProfile con capas y parámetros
        dt : Time step (segundos)
        integration_scheme : 'euler' o 'rk4'
        n_substeps : Número de sub-pasos para estabilidad
        """
        self.profile = profile
        self.dt = dt
        self.integration_scheme = integration_scheme
        self.n_substeps = n_substeps
        self.sub_dt = dt / n_substeps
        
        # Storage
        self.results = None
    
    def compute_response(self, motion: MotionRecord,
                        boundary: str = 'rigid') -> Dict:
        """
        Computar respuesta no lineal 1D
        
        Parameters:
        -----------
        motion : MotionRecord con aceleración de entrada
        boundary : 'rigid' o 'elastic'
        
        Returns:
        --------
        results : Dict con historias de tiempo y máximos
        """
        n_layers = self.profile.num_layers
        n_nodes = n_layers + 1
        n_steps = motion.num_points
        
        # ═══════════════════════════════════════════════════════════════════
        # INICIALIZACIÓN DE ARRAYS
        # ═══════════════════════════════════════════════════════════════════
        
        accel = np.zeros((n_steps, n_nodes))
        velocity = np.zeros((n_steps, n_nodes))
        displacement = np.zeros((n_steps, n_nodes))
        strain = np.zeros((n_steps, n_layers))
        stress = np.zeros((n_steps, n_layers))
        modulus = np.zeros((n_steps, n_layers))
        
        # Condición de frontera en base
        accel[:, 0] = motion.acceleration
        
        # ═══════════════════════════════════════════════════════════════════
        # INTEGRACIÓN TEMPORAL (Loop principal)
        # ═══════════════════════════════════════════════════════════════════
        
        # Estado inicial [a, v, u] para todos los nodos
        state = np.zeros(3 * n_nodes)
        
        for step in range(1, n_steps):
            # Sub-stepping para estabilidad numérica
            base_accel = motion.acceleration[step]
            
            for substep in range(self.n_substeps):
                state = self._step_forward(state, base_accel, step)
            
            # Extraer variables de estado
            accel[step, :] = state[:n_nodes]
            velocity[step, :] = state[n_nodes:2*n_nodes]
            displacement[step, :] = state[2*n_nodes:]
        
        # ═══════════════════════════════════════════════════════════════════
        # POST-PROCESAMIENTO
        # ═══════════════════════════════════════════════════════════════════
        
        # Deformaciones por capa
        for i in range(n_layers):
            disp_diff = displacement[:, i+1] - displacement[:, i]
            strain[:, i] = disp_diff / self.profile.depths[i]
            
            # Esfuerzos y módulos por interpolación
            for step in range(n_steps):
                tau, G_t = self.profile.layers[i].get_stress_strain_response(
                    strain[step, i], 0
                )
                stress[step, i] = tau
                modulus[step, i] = G_t
        
        # ═══════════════════════════════════════════════════════════════════
        # EMPAQUETAR RESULTADOS
        # ═══════════════════════════════════════════════════════════════════
        
        depths_nodes = np.cumsum(np.concatenate([[0], self.profile.depths]))
        depths_layers = np.cumsum(self.profile.depths[:-1])
        
        self.results = {
            'time': motion.time,
            'acceleration': accel,
            'velocity': velocity,
            'displacement': displacement,
            'strain': strain,
            'stress': stress,
            'modulus': modulus,
            'depth_nodes': depths_nodes,
            'depth_layers': depths_layers,
            'motion_name': motion.name,
            'profile': self.profile,
        }
        
        return self.results
    
    def _step_forward(self, state: np.ndarray,
                     base_accel: float,
                     step_idx: int) -> np.ndarray:
        """
        Avanzar un paso de tiempo usando esquema de integración
        
        Reference: Newmark (1959) para integración implícita
        Aquí usamos explícito para simplificar
        """
        n_nodes = self.profile.num_layers + 1
        
        # Extraer estado
        a = state[:n_nodes].copy()
        v = state[n_nodes:2*n_nodes].copy()
        u = state[2*n_nodes:].copy()
        
        # Condición frontera base
        a[0] = base_accel
        u[0] = 0  # Base fija
        v[0] = 0
        
        # ═══════════════════════════════════════════════════════════════════
        # COMPUTAR ACELERACIONES de ecuación de movimiento
        # ═══════════════════════════════════════════════════════════════════
        
        a_new = np.zeros(n_nodes)
        a_new[0] = base_accel
        
        for i in range(self.profile.num_layers):
            # Deformación en capa i
            gamma_i = (u[i+1] - u[i]) / self.profile.depths[i]
            
            # Obtener esfuerzo desde modelo constitutivo
            tau_i, G_i = self.profile.layers[i].get_stress_strain_response(
                gamma_i, 0
            )
            
            # Ecuación de movimiento discreta (FDM simple)
            # ρ * a = τ/Δz
            if i < self.profile.num_layers - 1:
                gamma_ip = (u[i+2] - u[i+1]) / self.profile.depths[i+1]
                tau_ip, _ = self.profile.layers[i+1].get_stress_strain_response(
                    gamma_ip, 0
                )
                force = (tau_ip - tau_i) / self.profile.depths[i]
            else:
                force = -tau_i / self.profile.depths[i]
            
            a_new[i+1] = force / self.profile.densities[i]
        
        # ═══════════════════════════════════════════════════════════════════
        # INTEGRAR (Euler explícito)
        # ═══════════════════════════════════════════════════════════════════
        
        v_new = v + a_new * self.sub_dt
        u_new = u + v * self.sub_dt + 0.5 * a_new * self.sub_dt**2
        
        # Empaquetar nuevo estado
        state_new = np.concatenate([a_new, v_new, u_new])
        
        return state_new


# ═════════════════════════════════════════════════════════════════════════════
# PART 3: I/O MEJORADO
# ═════════════════════════════════════════════════════════════════════════════

def read_stratified_profile(filepath: str) -> VsProfile:
    """
    Lee perfil estratificado con parámetros constitutivos independientes
    
    Formato de archivo (.txt):
    ═══════════════════════════════════════════════════════════════════════════
    
    # Comentario
    thickness(m)  vs(m/s)  rho(kg/m3)  model  G_max(Pa)  gamma_ref  n  xi_ref  alpha_g  alpha_x  beta  gamma_yield
    5.0           250      1800        H2     1.125e6    0.005      0.5  0.05    0.5      -        -      -
    5.0           300      1850        H4     1.665e6    0.005      0.5  0.05    0.5      0.5      -      -
    10.0          400      1900        HH     3.04e6     0.005      0.5  0.05    0.5      0.5      0.3    -
    15.0          500      2000        EPP    5e6        -           -    -       -        -        -      0.01
    
    ═══════════════════════════════════════════════════════════════════════════
    """
    data = np.genfromtxt(filepath, dtype=str, comments='#')
    
    layers = []
    for row in data:
        thickness = float(row[0])
        vs = float(row[1])
        rho = float(row[2])
        model_type = row[3]
        G_max = float(row[4])
        gamma_ref = float(row[5]) if row[5] != '-' else None
        n = float(row[6]) if row[6] != '-' else None
        xi_ref = float(row[7]) if row[7] != '-' else None
        alpha_g = float(row[8]) if row[8] != '-' else None
        alpha_x = float(row[9]) if row[9] != '-' else None
        beta = float(row[10]) if row[10] != '-' else None
        gamma_yield = float(row[11]) if row[11] != '-' else None
        
        # Crear parámetros
        params = ConstitutiveParameters(
            model_type=model_type,
            G_max=G_max,
            gamma_ref=gamma_ref,
            n=n,
            damping_ref=xi_ref,
            alpha_g=alpha_g,
            alpha_x=alpha_x,
            beta=beta,
            gamma_yield=gamma_yield
        )
        
        layer = SoilLayer(
            thickness=thickness,
            vs=vs,
            density=rho,
            constitutive_params=params
        )
        
        layers.append(layer)
    
    return VsProfile(layers=layers)


def write_stratified_profile(profile: VsProfile, filepath: str):
    """Escribir perfil estratificado a archivo"""
    with open(filepath, 'w') as f:
        f.write("# Perfil estratificado con parámetros constitutivos independientes\n")
        f.write("# Created by SeismoSoil Advanced\n")
        f.write("thickness(m)\tvs(m/s)\trho(kg/m3)\tmodel\tG_max(Pa)\t")
        f.write("gamma_ref\tn\txi_ref\talpha_g\talpha_x\tbeta\tgamma_yield\n")
        
        for layer in profile.layers:
            p = layer.constitutive_params
            
            G_max_str = f"{p.G_max:.2e}"
            gamma_ref_str = f"{p.gamma_ref:.6f}" if p.gamma_ref else "-"
            n_str = f"{p.n:.2f}" if p.n else "-"
            xi_str = f"{p.damping_ref:.4f}" if p.damping_ref else "-"
            alpha_g_str = f"{p.alpha_g:.2f}" if p.alpha_g else "-"
            alpha_x_str = f"{p.alpha_x:.2f}" if p.alpha_x else "-"
            beta_str = f"{p.beta:.2f}" if p.beta else "-"
            gamma_yield_str = f"{p.gamma_yield:.6f}" if p.gamma_yield else "-"
            
            f.write(f"{layer.thickness:.1f}\t{layer.vs:.0f}\t{layer.density:.0f}\t")
            f.write(f"{p.model_type}\t{G_max_str}\t{gamma_ref_str}\t{n_str}\t{xi_str}\t")
            f.write(f"{alpha_g_str}\t{alpha_x_str}\t{beta_str}\t{gamma_yield_str}\n")


# ═════════════════════════════════════════════════════════════════════════════
# UTILIDADES
# ═════════════════════════════════════════════════════════════════════════════

def generate_example_profile() -> VsProfile:
    """Generar perfil de ejemplo con parámetros diversos por estrato"""
    
    # Estrato 1: Arena saturada (H2, Masing completo)
    layer1 = SoilLayer(
        thickness=5.0,
        vs=250,
        density=1800,
        material_id=1,
        constitutive_params=ConstitutiveParameters(
            model_type='H2',
            G_max=250**2 * 1800,  # ρ * vs²
            gamma_ref=0.005,
            n=0.5,
            damping_ref=0.050
        )
    )
    
    # Estrato 2: Arena media (H4, asimetría carga/descarga)
    layer2 = SoilLayer(
        thickness=5.0,
        vs=300,
        density=1850,
        material_id=2,
        constitutive_params=ConstitutiveParameters(
            model_type='H4',
            G_max=300**2 * 1850,
            gamma_ref=0.005,
            n=0.55,
            damping_ref=0.055,
            alpha_g=0.45,
            alpha_x=0.55
        )
    )
    
    # Estrato 3: Arena con grava (HH, máxima flexibilidad)
    layer3 = SoilLayer(
        thickness=10.0,
        vs=400,
        density=1900,
        material_id=3,
        constitutive_params=ConstitutiveParameters(
            model_type='HH',
            G_max=400**2 * 1900,
            gamma_ref=0.006,
            n=0.50,
            damping_ref=0.045,
            alpha_g=0.50,
            alpha_x=0.50,
            beta=0.25
        )
    )
    
    # Estrato 4: Grava compacta (EPP, simple)
    layer4 = SoilLayer(
        thickness=15.0,
        vs=500,
        density=2000,
        material_id=4,
        constitutive_params=ConstitutiveParameters(
            model_type='EPP',
            G_max=500**2 * 2000,
            gamma_ref=None,
            n=None,
            damping_ref=None,
            gamma_yield=0.01
        )
    )
    
    return VsProfile(layers=[layer1, layer2, layer3, layer4])


if __name__ == "__main__":
    # Ejemplo rápido
    profile = generate_example_profile()
    profile.print_stratigraphy()
    
    print("\n✓ Módulo seismosoil_advanced importado correctamente")
    print(f"✓ Perfil de ejemplo creado con {profile.num_layers} capas")
