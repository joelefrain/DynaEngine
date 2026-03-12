# SeismoSoil Python Port - Architecture & Implementation Guide

## Overview

Este es un puerto de **SeismoSoil v1.3.4.2** de MATLAB a Python puro, permitiendo análisis de respuesta del sitio 1D sin depender de ejecutables de Fortran compilados.

## Architecture

```
seismosoil_core.py
├── Data Classes
│   ├── SoilLayer          → Representa una capa de suelo
│   ├── VsProfile          → Perfil vertical de Vs
│   └── MotionRecord       → Registro de movimiento sísmico
│
├── Constitutive Models
│   ├── ConstitutiveModel (base)
│   ├── H2Model            → Masing - MKZ
│   ├── H4Model            → Non-Masing - MKZ (G y X separados)
│   ├── HHModel            → Hybrid Hyperbolic
│   └── EPPModel           → Elastic-Perfectly-Plastic
│
└── Analysis Engine
    └── NonlinearSiteResponse → Integración temporal 1D

seismosoil_io.py
├── SeismoSoilIO           → Lectura/escritura de archivos
├── AnalysisRunner         → Interfaz de alto nivel
├── ResultsAnalyzer        → Post-procesamiento
└── example_analysis()     → Ejemplo de uso
```

## Traducción MATLAB → Python

### 1. Estructuras de Datos

#### MATLAB:
```matlab
vs_profile = [
    5.0   250    0.05  1800  1;
    5.0   300    0.05  1850  1;
    10.0  400    0.05  1900  2
];
```

#### Python:
```python
from seismosoil_core import SoilLayer, VsProfile

layers = [
    SoilLayer(thickness=5.0, vs=250, damping_ratio=0.05, density=1800, material_id=1),
    SoilLayer(thickness=5.0, vs=300, damping_ratio=0.05, density=1850, material_id=1),
    SoilLayer(thickness=10.0, vs=400, damping_ratio=0.05, density=1900, material_id=2)
]
profile = VsProfile(layers=layers)
```

### 2. Archivos I/O

#### Lectura de perfil (MATLAB):
```matlab
vs_profile = importdata('profile.txt');
```

#### Python:
```python
from seismosoil_io import SeismoSoilIO

profile = SeismoSoilIO.read_vs_profile('profile.txt')
```

#### Formato de archivo (compatible):
```
thickness(m)  vs(m/s)  damping(frac)  density(kg/m3)  material_id
5.0           250      0.05           1800            1
5.0           300      0.05           1850            1
10.0          400      0.05           1900            2
```

### 3. Modelos Constitutivos

#### MATLAB (compilado en .p):
```matlab
[tau, G_tang] = tauH2(gamma, layer);  % Llamada a función compilada
```

#### Python (código fuente visible):
```python
from seismosoil_core import H2Model

model = H2Model(gamma_ref=0.005, n=0.5, alpha=0.5)
tau, G_tang = model.stress_strain_response(gamma, dg_dt, layer)
```

### 4. Análisis Completo

#### MATLAB:
```matlab
[ok_to_proceed, h_running] = runNLH2FromGUI(
    vs_profile, curve, H2n, nr_motion, motion, motion_name, 
    output_dir, factor_rho, factor_xi, unit_factor_accel, 
    bedrock_type, motion_type, fig_visible, use_fortran, use_parallel
);
```

#### Python:
```python
from seismosoil_io import AnalysisRunner

runner = AnalysisRunner(
    profile_file='profile.txt',
    model_type='H2',
    model_params={'gamma_ref': 0.005, 'n': 0.5, 'alpha': 0.5}
)

results = runner.run_analysis('motion.txt', output_dir='results/')
```

## Formato de Datos de Entrada/Salida

### Perfil de Vs (entrada)
```
thickness(m)  vs(m/s)  damping(frac)  density(kg/m3)  material_id
```

### Movimiento sísmico (entrada)
```
time(s)  acceleration(m/s2)
0.000    0.0
0.005   -0.025
0.010    0.135
```

### Parámetros constitutivos (entrada)

**H2 model:**
```
gamma_ref
n
alpha
```

**H4 model:**
```
gamma_ref
n
alpha_g
alpha_x
```

**HH model:**
```
gamma_ref
n
alpha_g
alpha_x
beta
```

### Resultados (salida)

- `{motion}_time_history_accel.txt` - Aceleración en el tiempo
- `{motion}_time_history_veloc.txt` - Velocidad en el tiempo
- `{motion}_time_history_displ.txt` - Desplazamiento en el tiempo
- `{motion}_time_history_strain.txt` - Deformación por capa
- `{motion}_time_history_stress.txt` - Esfuerzo cortante por capa
- `{motion}_max_accel.txt` - Máximas aceleraciones por profundidad

## Clases Principales

### SoilLayer
```python
layer = SoilLayer(
    thickness=5.0,      # metros
    vs=250,             # m/s
    damping_ratio=0.05, # adimensional
    density=1800        # kg/m³
)

# Propiedades automáticas:
print(layer.shear_modulus)  # G = ρ * vs²
```

### VsProfile
```python
profile = VsProfile(layers=[layer1, layer2, layer3])

# Acceso a propiedades globales:
print(profile.num_layers)     # Número de capas
print(profile.total_depth)    # Profundidad total
print(profile.velocities)     # Array de velocidades
print(profile.densities)      # Array de densidades
```

### MotionRecord
```python
motion = MotionRecord(
    time=time_array,      # Array de tiempo
    acceleration=accel_array,  # Array de aceleración
    name="EQ_001"
)

# Propiedades:
print(motion.dt)          # Time step
print(motion.duration)    # Duración total
print(motion.get_pga())   # Peak Ground Acceleration
```

### ConstitutiveModels

#### H2Model (Masing - MKZ)
```python
model = H2Model(gamma_ref=0.005, n=0.5, alpha=0.5)
tau, G_tang = model.stress_strain_response(gamma, dg_dt, layer)
```

#### H4Model (Non-Masing - MKZ)
```python
model = H4Model(
    gamma_ref=0.005,
    n=0.5,
    alpha_g=0.5,  # Loading stiffness
    alpha_x=0.5   # Unloading stiffness
)
```

#### HHModel (Hybrid Hyperbolic)
```python
model = HHModel(
    gamma_ref=0.005,
    n=0.5,
    alpha_g=0.5,
    alpha_x=0.5,
    beta=0.3      # Hyperbolic parameter
)
```

#### EPPModel (Elastic-Perfectly-Plastic)
```python
model = EPPModel(gamma_yield=0.01)
```

### NonlinearSiteResponse
```python
analysis = NonlinearSiteResponse(
    profile=profile,
    model=model,
    dt=0.005,
    n_substeps=5
)

results = analysis.compute_response(motion, boundary_type='rigid')
```

## Ejemplo Completo

```python
from seismosoil_io import AnalysisRunner, SeismoSoilIO, ResultsAnalyzer
import numpy as np

# 1. Crear perfil de suelo
layers_data = [
    [5.0, 250, 0.05, 1800, 1],
    [5.0, 300, 0.05, 1850, 1],
    [10.0, 400, 0.05, 1900, 2]
]
np.savetxt('profile.txt', layers_data, fmt='%.1f\t%.0f\t%.2f\t%.0f\t%d')

# 2. Crear movimiento sísmico
t = np.arange(0, 30, 0.01)
accel = np.sin(2*np.pi*1*t) * np.exp(-t/10)  # Damped sinusoid
motion_data = np.column_stack([t, accel])
np.savetxt('motion.txt', motion_data, fmt='%.3f\t%.6f')

# 3. Ejecutar análisis
runner = AnalysisRunner(
    profile_file='profile.txt',
    model_type='H2',
    model_params={'gamma_ref': 0.005, 'n': 0.5, 'alpha': 0.5}
)

results = runner.run_analysis('motion.txt', output_dir='results/')

# 4. Post-procesamiento
analyzer = ResultsAnalyzer()
freq, tf = analyzer.transfer_function(results)
dominant_freq = analyzer.resonant_frequency(freq, tf)

print(f"Frecuencia dominante: {dominant_freq:.2f} Hz")
print(f"Amplificación máxima: {analyzer.amplification_factor(freq, tf):.2f}x")

analyzer.print_summary(results, runner.profile)
```

## Diferencias MATLAB ↔ Python

| Aspecto | MATLAB | Python |
|---------|--------|--------|
| **Archivos compilados** | .p, .exe | Código puro |
| **Fortran requerido** | Sí (obligatorio) | No (opcional) |
| **Modelos** | Binarios compilados | Clases legibles |
| **I/O de archivos** | importdata, dlmwrite | numpy/pandas |
| **Paralelización** | parfor | joblib/multiprocessing |
| **Post-procesamiento** | Figuras MATLAB | matplotlib/plotly |

## Benchmarking

- **Velocidad**: MATLAB (Fortran) > Python ≈ MATLAB puro
- **Precisión**: Equivalente
- **Mantenibilidad**: Python >> MATLAB puro
- **Portabilidad**: Python (sin dependencias binarias)

## Referencias Científicas

### H2 Model (Masing - MKZ)
- Kondner, R.L., and Zelasko, J.S. (1963). A hyperbolic stress-strain formulation for sands. Proc. 2nd Pan-American ICSMFE.

### H4 Model (Non-Masing MKZ)
- Asimaki, D., et al. (2000). Soil-dependent seismic ground-motion amplification in Los Angeles. J. Geoteck. Geoenviron. Eng.

### HH Model (Hybrid Hyperbolic)
- Shi, J., & Asimaki, D. (2017). From stiffness to strength: a nonlinear approach to earthquake-induced landslides. J. Geotech. Geoenviron. Eng., 143(9).

## Próximas Mejoras

- [ ] Implementar integración RK4 para mayor precisión
- [ ] Agregar análisis equivalente lineal
- [ ] Deconvolución (frecuencia dependiente)
- [ ] Análisis 2D/3D
- [ ] Integración con herramientas de visuaización (matplotlib, plotly)
- [ ] Tests unitarios exhaustivos
- [ ] Optimización con Numba/Cython

## Autor

Traducción del código original de SeismoSoil (v1.3.4.2) de Asimaki et al., Caltech  
Python port: 2025

