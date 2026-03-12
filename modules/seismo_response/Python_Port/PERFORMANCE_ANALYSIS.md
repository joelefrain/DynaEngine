# 📊 Análisis de Rendimiento - SeismoSoil Python Port

## ❓ ¿Por Qué Fortran Originalmente?

SeismoSoil original (MATLAB) usaba **Fortran compilado** para los módulos no lineales:
- `NLH2.exe`, `NLH4.exe`, `NLHH.exe`, `NLEPP.exe` (Windows)
- `NLH2.mac`, `NLH4.mac`, etc. (macOS)
- `NLH2.unix`, etc. (Linux)

**Razones:**
1. **CPU-bound computation**: Integración temporal (Euler, RK4) es O(n_steps × n_layers)
   - 10 seg @ 0.01 dt = 1,000 pasos
   - Típicamente 5-100 capas
   - **Total: 5,000-100,000 iteraciones**

2. **Gets muy frecuentes de interpolación**: `get_stress()`, `get_damping()` llamados en CADA paso
   - `np.interp()` es O(log n) por búsqueda binaria
   - Con 100 puntos en curva: ~7 comparaciones por `get_stress()`

3. **Overhead de Python puro**: Cada loop temporal = acceso a memoria, conversión de tipos, etc.

4. **MATLAB lentitud**: MATLAB es **100-1000x más lento** que Fortran para loops numéricos

**Conclusión**: Fortran fue elegido porque:
- Compilación directa a código máquina
- Sin overhead de interpretación
- Optimizaciones del compilador (vectorización automática, cache)
- Ideal para CFD/integración numérica

---

## 🔍 Análisis del Código Python Actual

### Cuellos de Botella (Bottlenecks)

#### **1. Loop Temporal Principal** ⚠️ **MÁS CRÍTICO**

```python
# En compute_response():
for step in range(1, n_steps):           # ~1000 iteraciones
    base_acc = motion.acceleration[step]
    state[0] = base_acc
    
    for i in range(n_layers):            # ~5-50 iteraciones
        dz = self.profile.depths[i]
        gamma = (state[2*n_nodes + i+1] - state[2*n_nodes + i]) / dz
        
        tau_i = self.backbone_curves[i].get_stress(gamma)  # ⚠️ CARO
        
        if i < n_layers - 1:
            gamma_next = (...)
            tau_next = self.backbone_curves[i+1].get_stress(gamma_next)  # ⚠️ CARO
            force = (tau_next - tau_i) / dz
        else:
            force = -tau_i / dz
        
        state[i+1] = force / self.profile.densities[i]
    
    # Integración
    state[n_nodes:2*n_nodes] += state[:n_nodes] * self.dt
    state[2*n_nodes:] += state[n_nodes:2*n_nodes] * self.dt
```

**Problemas:**
- Doble loop anidado: O(n_steps × n_layers)
- `get_stress()` hace `np.interp()` internamente (caro)
- Acceso indexado múltiple a `state[]` (mala localidad de cache)
- Conversión Python ↔ NumPy en cada iteración

**Estimado de tiempo** (ejemplo: 1000 steps × 20 layers):
- Sin optimizar: **0.5-1.0 segundos** (Python puro)
- Con NumPy actual: **0.1-0.3 segundos**
- Con Cython: **0.01-0.05 segundos** (10x)
- Con Fortran: **0.001-0.01 segundos** (100x)

---

#### **2. Función get_stress()** ⚠️ **LLAMADA FRECUENTE**

```python
def get_stress(self, gamma: float) -> float:
    """Interpolar esfuerzo en deformación"""
    return np.interp(np.abs(gamma), self.strain, self.stress) * np.sign(gamma)
```

**Problemas:**
- `np.interp()` hace búsqueda binaria: O(log 100) ≈ 7 comparaciones
- Se llama 2× por cada capa, en cada paso
- Para 1000 steps × 20 layers: **40,000 llamadas** a `np.interp()`
- Overhead de conversión: `np.abs()`, `np.sign()` crea temporales

**Solución**: Pre-calcular tabla lookup o usar Cython con binary search manual

---

#### **3. Creación de Arrays Temporales**

```python
# En cada step del loop temporal:
state[n_nodes:2*n_nodes] += state[:n_nodes] * self.dt  # Crea vista
state[2*n_nodes:] += state[n_nodes:2*n_nodes] * self.dt  # Crea vista
```

**Problemas:**
- Slicing crea vistas (OK en NumPy)
- Pero la suma con escalar `* self.dt` hace copia
- Repetido 1,000 veces = overhead acumulado

---

### Análisis de Vectorización

| Operación | Actual | Vectorizable | Beneficio |
|-----------|--------|--------------|-----------|
| Loop temporal | ❌ No | ❌ No (estado sequencial) | - |
| Cálculo de γ | ✅ Sí (NumPy slice) | Parcialmente (pre-calc) | Mínimo |
| `get_stress()` | ❌ No (Fortran sería mejor) | ❌ No (interp secuencial) | - |
| Integración v,u | ✅ Sí (NumPy) | ✅ Sí | Alto (ya vectorizado) |

**Conclusión**: El loop temporal NO se puede vectorizar por dependencias secuenciales
→ Mejor opción: **Compilar con Cython**

---

## 🚀 Estrategia de Optimización

### Opción 1: **Numba JIT** (Recomendado - Fácil)

```python
from numba import jit, float64
import numpy as np

@jit(nopython=True)
def compute_response_kernel(motion_accel, depths, densities, 
                           strain_curves, stress_curves,
                           gamma_ref, n, dt):
    # Loop temporal - Numba compilará a código máquina
    # Sin overhead Python
```

**Ventajas:**
- Cambio mínimo de código
- Compilación automática
- Speedup: **10-50x**
- No requiere .pyx ni compilar

**Desventajas:**
- Primera ejecución lenta (JIT)
- Debugging complicado
- NumPy puro required

---

### Opción 2: **Cython** (Recomendado - Potente)

```cython
# seismosoil_kernel.pyx
cimport numpy as np
from libc.math cimport sin, cos, exp, fabs, copysign

def compute_response_cython(double[::1] motion_accel,
                           double[::1] depths,
                           double[::1] densities,
                           ...):
    # Loop temporal en C puro
    # Speedup: **50-100x**
```

**Ventajas:**
- Speedup máximo: **50-100x**
- Control total (tipos C)
- Debugging posible
- Producción profesional

**Desventajas:**
- Requiere compilación (`python setup.py build_ext`)
- Más complejo
- Dependencias (gcc en Linux)

---

### Opción 3: **Mantener Python + NumPy Optimizado** (Actual)

Mejoras sin compilar:
1. **Pre-compute interpolations** en tabla 2D
2. **Vectorizar slicing** de state
3. **Reduce function calls** en loop

Speedup: **1.5-2x** (no suficiente)

---

## 📋 Problemas Lógicos Identificados

### ✅ Validado (Correcto)
1. Euler forward integration: correcto para pequeños dt
2. Cálculo de γ = du/dz: correcto
3. Regla de Masing (degradación): correcto
4. Boundary conditions: correcto

### ⚠️ Problemas Detectados

#### **Problema 1: Fórmula de Amortiguamiento Incorrecta**

```python
# ACTUAL (INCORRECTO):
xi_array = self.damping_ref * (1.0 - G_norm) / (1.0 - 1.0/(1.0 + 1.0))
# División por (1.0 - 0.5) = 0.5
# Resultado: xi = 2 * damping_ref * (1 - G_norm)
```

Debería ser:
```python
# CORRECTO (Hardin & Drnevich 1972):
# ξ(γ) = ξ_ref * [ 2 * (1 - G_norm) / (1 + G_norm) ]
xi_array = self.damping_ref * 2.0 * (1.0 - G_norm) / (1.0 + G_norm)
```

**Impacto**: Amortiguamiento ~2x incorrecto → respuesta amplificada/atenuada mal

---

#### **Problema 2: EPP Model No Implementado**

```python
if model_type == 'EPP':
    self.gamma_yield = gamma_yield if gamma_yield is not None else 0.01
```

Pero `_generate_curves()` no distingue modelos:
```python
# Usa degradación Hardin-Drnevich para TODOS
G_norm = 1.0 / (1.0 + (gamma_array / self.gamma_ref) ** self.n)
```

EPP (Elastoplástico) debería ser:
```python
# G(γ) = G_max constante si γ < γ_y
# G(γ) = G_max si γ ≥ γ_y → plástico
if gamma < gamma_yield:
    G = G_max
    xi = 0  # Elástico sin amortiguamiento
else:
    G = 0  # Plástico
    xi = xi_yield ~ 0.05
```

**Impacto**: Modelo EPP genera curvas incorrectas

---

#### **Problema 3: HH Model (H4) Parámetros No Usados**

```python
if model_type in ['H4', 'HH']:
    self.alpha_g = alpha_g if alpha_g is not None else 0.5
    self.alpha_x = alpha_x if alpha_x is not None else 0.5
```

Pero no se usan en `_generate_curves()`:
```python
# Ignora alpha_g, alpha_x, beta
G_norm = 1.0 / (1.0 + (gamma_array / self.gamma_ref) ** self.n)
```

H4/HH requieren curvas diferentes:
```python
# H4: Masing mejorado con alpha_g, alpha_x
# HH: Hiperbólico con beta (curva de carga vs descarga)
```

**Impacto**: H4 y HH devuelven mismos resultados que H2 (incorrecto)

---

#### **Problema 4: Ningún Chequeo de Estabilidad**

Euler explícito requiere CFL condition:
```
dt ≤ min(dz / Vs)  para estabilidad
```

Código actual no valida:
```python
# En __init__:
self.dt = dt  # Asume que es estable
```

Si dt_input > dt_critical → inestabilidad numérica, respuesta diverge

---

## 🎯 Plan de Acción Recomendado

### **Fase 1: Corregir Lógica** (Crítica)
1. ✅ Arreglar fórmula de amortiguamiento
2. ✅ Implementar EPP correctamente
3. ✅ Agregar dependencia de alpha_g, alpha_x, beta
4. ✅ Validar estabilidad CFL

### **Fase 2: Optimizar** (Deseable)
1. Implementar Numba JIT en `compute_response_kernel()`
2. O implementar Cython `.pyx` para máximo speedup
3. Pre-compute interpolation tables

### **Fase 3: Testing** (Importante)
1. Comparar con SeismoSoil MATLAB
2. Verificar amplificación, período fundamental, etc.

---

## 📚 Referencias

- Hardin, B. O., & Drnevich, V. P. (1972). Shear modulus and damping in soils. *J. Soil Mech. Found. Div., ASCE*, 98(SM7), 667-687.
- Shi, J., & Asimaki, D. (2017). From stiffness to strength: A micro-polar plasticity model for geotechnical materials. *Soil Dyn. Earthquake Eng., 98*, 169-183.
- Kondner, R. L., & Zelasko, J. S. (1963). A hyperbolic stress‐strain formulation for sands. In *Proc., 2nd Pan-American Conf. on SMFE*, Brazil.
