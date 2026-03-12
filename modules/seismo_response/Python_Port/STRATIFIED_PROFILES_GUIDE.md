# Guía Completa: Perfiles Estratificados en SeismoSoil Advanced

## Contenido
1. [Introducción](#introducción)
2. [Formato del Archivo .txt](#formato-del-archivo-txt)
3. [Modelos Constitutivos y Parámetros](#modelos-constitutivos-y-parámetros)
4. [Ejemplos de Perfiles](#ejemplos-de-perfiles)
5. [Uso en Python](#uso-en-python)
6. [Validación de Datos](#validación-de-datos)
7. [Troubleshooting](#troubleshooting)

---

## Introducción

La arquitectura avanzada de SeismoSoil permite definir **estratigrafías complejas** donde **cada estrato tiene sus propios parámetros constitutivos independientes**, lo que permite:

- ✅ Usar diferentes modelos constitutivos en diferentes capas
- ✅ Capturar comportamiento realista de sitios complejos
- ✅ Generar automáticamente curvas de degradación y amortiguamiento
- ✅ Ejecutar análisis paramétricos efficientes

### Arquitectura Conceptual

```
PERFIL ESTRATIFICADO (VsProfile)
    │
    ├── Estrato 1 (SoilLayer)
    │   ├── thickness: 5.0 m
    │   ├── vs: 200 m/s
    │   ├── rho: 1750 kg/m³
    │   └── constitutive_params: ConstitutiveParameters
    │       ├── model_type: "H2"
    │       ├── G_max: 7.0e7 Pa
    │       ├── gamma_ref: 0.004
    │       ├── n: 0.5
    │       └── damping_ref: 0.04
    │
    ├── Estrato 2 (SoilLayer)
    │   └── constitutive_params: ConstitutiveParameters (INDEPENDIENTE)
    │       ├── model_type: "H4"
    │       ├── alpha_g: 0.45
    │       └── alpha_x: 0.55
    │
    └── Estrato 3 (SoilLayer)
        └── constitutive_params: ConstitutiveParameters (INDEPENDIENTE)
            ├── model_type: "HH"
            ├── beta: 0.35
            └── ...

ANÁLISIS (NonlinearSiteResponseAdvanced)
    = Aplica modelo 1 en estrato 1
    + Aplica modelo 2 en estrato 2
    + Aplica modelo 3 en estrato 3
    = Respuesta integrada del sitio
```

---

## Formato del Archivo .txt

### Encabezado de Columnas (REQUERIDO)

```
# COMENTARIO DE DESCRIPCIÓN
# Línea 1: Descripción del perfil
# Línea 2: Referencias bibliográficas
# ...
#
# thickness(m)  vs(m/s)  rho(kg/m3)  model  G_max(Pa)  gamma_ref  n  xi_ref  alpha_g  alpha_x  beta  gamma_yield
```

### Especificación de Columnas

| Columna | Tipo | Unidad | Descripción | Rango Típico |
|---------|------|--------|-------------|--------------|
| `thickness` | float | m | Espesor del estrato | 1-50 m |
| `vs` | float | m/s | Velocidad de onda de corte | 100-700 m/s |
| `rho` | float | kg/m³ | Densidad del suelo | 1600-2200 kg/m³ |
| `model` | string | - | Tipo de modelo: H2, H4, HH, EPP | - |
| `G_max` | float | Pa | Módulo de rigidez máximo | 1e6 - 1e9 Pa |
| `gamma_ref` | float | - | Deformación de referencia | 0.0001 - 0.01 |
| `n` | float | - | Exponente de degradación (Hardin-Drnevich) | 0.4 - 1.0 |
| `xi_ref` | float | - | Amortiguamiento a γ_ref | 0.01 - 0.20 |
| `alpha_g` | float | - | Asimetría en carga (H4, HH) | 0.3 - 0.7 |
| `alpha_x` | float | - | Asimetría en descarga (H4, HH) | 0.3 - 0.7 |
| `beta` | float | - | Factor de amortiguamiento no lineal (HH) | 0.2 - 0.5 |
| `gamma_yield` | float | - | Deformación de fluencia (EPP) | 0.002 - 0.02 |

### Marcador de Valores Especiales

- **`-`** : Parámetro no aplicable para este modelo
  - Ejemplo: H2 no usa `alpha_g`, escribir `-`

### Rango de Aplicabilidad

```
γ_ref (Hardin & Drnevich 1972)
├── Arenas sueltas: 0.003 - 0.008
├── Arenas medias: 0.004 - 0.007
├── Arenas densas: 0.005 - 0.006
├── Arcillas blandas: 0.001 - 0.003
└── Arcillas firmes: 0.003 - 0.005

n (exponente de degradación, Hardin & Drnevich 1972)
├── Arenas: 0.4 - 0.6
├── Arcillas: 0.6 - 0.9
└── Gravas: 0.3 - 0.5

ξ_ref (amortiguamiento inicial, Kramer 1996)
├── Arenas: 0.02 - 0.07
├── Arcillas: 0.05 - 0.15
└── Gravas: 0.01 - 0.05
```

---

## Modelos Constitutivos y Parámetros

### 1. Modelo H2 - Masing Puro (Kondner-Zelasko - MKZ)

**Descripción**: Simétrico en carga/descarga, regla de Masing

**Ecuación Base** (Kondner & Zelasko 1963):
```
τ = γ × G(γ) / (1 + |γ|/γ_max)
G(γ) = G_max / [1 + (γ/γ_ref)^n]
```

**Parámetros Requeridos**:
- `model`: "H2"
- `G_max`: Módulo de rigidez máximo [Pa]
- `gamma_ref`: Deformación de referencia [-]
- `n`: Exponente de degradación [-]
- `xi_ref`: Amortiguamiento a γ_ref [-]

**Parámetros Ignorados** (usar `-`):
- `alpha_g`, `alpha_x`, `beta`, `gamma_yield`

**Aplicación Típica**:
- Arenas a bajos niveles de deformación
- Suelos con comportamiento simétrico
- Análisis de carga estática

**Ejemplo**:
```
5.0  250  1800  H2  1.125e8  0.005  0.5  0.05  -  -  -  -
```

---

### 2. Modelo H4 - No-Masing (Asimaki et al. 2005)

**Descripción**: Asimétrico en carga/descarga, regla de Masing modificada

**Innovación**: Parámetros independientes para carga (α_g) y descarga (α_x)

**Ecuación**:
```
En carga:    G(γ) = G_max / [1 + α_g × (γ/γ_ref)^n]
En descarga: G(γ) = G_max / [1 + α_x × (γ/γ_ref)^n]

Típicamente: α_g < 1.0 (más flexible) 
             α_x > 1.0 (más rígido)
```

**Parámetros Requeridos**:
- `model`: "H4"
- `G_max`, `gamma_ref`, `n`, `xi_ref`: igual que H2
- `alpha_g`: Coeficiente en carga [típicamente 0.40-0.55]
- `alpha_x`: Coeficiente en descarga [típicamente 0.45-0.65]

**Parámetros Ignorados** (usar `-`):
- `beta`, `gamma_yield`

**Aplicación Típica**:
- Arenas y gravas a medios niveles de deformación
- Suelos con comportamiento histerético complejo
- Análisis dinámico realista

**Rango de Parámetros** (Asimaki et al. 2005):
```
Para arenas: α_g = 0.40-0.50, α_x = 0.50-0.60
Para gravas: α_g = 0.35-0.45, α_x = 0.55-0.65
```

**Ejemplo**:
```
7.0  280  1850  H4  1.45e8  0.005  0.55  0.05  0.45  0.55  -  -
```

---

### 3. Modelo HH - Hybrid Hyperbolic (Shi & Asimaki 2017)

**Descripción**: Máxima flexibilidad, parámetros α y β independientes

**Innovación Principal**: Parámetro `beta` controla amortiguamiento no lineal

**Ecuación**:
```
τ_backbone = γ × G(γ) / (1 + |γ|/γ_max)
G(γ) = G_max / [1 + (γ/γ_ref)^n]

ξ(γ) = ξ_ref × [1 - G(γ)/G_max] × (1 + β × |γ|/γ_ref)^0.5
```

**Parámetros Requeridos**:
- `model`: "HH"
- `G_max`, `gamma_ref`, `n`, `xi_ref`: igual que H2
- `alpha_g`, `alpha_x`: asimetría (típicamente 0.5, simétrico)
- `beta`: Parámetro de amortiguamiento no lineal [0.2-0.5]

**Parámetros Ignorados** (usar `-`):
- `gamma_yield`

**Aplicación Típica**:
- Arcillas blandas a medias
- Sitios muy amplificadores
- Análisis con degradación severa

**Rango de Parámetros** (Shi & Asimaki 2017):
```
Para arcillas:
  β = 0.3-0.4 (amortiguamiento moderado)
  α_g = α_x = 0.5 (simétrico)
  n = 0.7-0.85 (degradación pronunciada)
```

**Ejemplo**:
```
10.0  150  1800  HH  4.05e7  0.001  0.85  0.12  0.50  0.50  0.35  -
```

---

### 4. Modelo EPP - Elastic Perfectly Plastic

**Descripción**: Comportamiento rígido hasta fluencia, luego plástico

**Ecuación**:
```
Si |γ| < γ_yield:
  τ = γ × G_max  (comportamiento elástico)

Si |γ| >= γ_yield:
  τ = ±τ_yield  (comportamiento plástico)
```

**Parámetros Requeridos**:
- `model`: "EPP"
- `G_max`: Módulo de rigidez [Pa]
- `gamma_yield`: Deformación de fluencia [-]
- (Los demás parámetros se ignoran - usar `-`)

**Parámetros Ignorados** (usar `-`):
- `gamma_ref`, `n`, `xi_ref`, `alpha_g`, `alpha_x`, `beta`

**Aplicación Típica**:
- Gravas compactas
- Bedrock
- Suelos con fluencia bien definida
- Análisis conservador de sitios rígidos

**Rango de Parámetros**:
```
γ_yield típico:
- Gravas: 0.003-0.008
- Arenas densas: 0.005-0.010
```

**Ejemplo**:
```
15.0  450  2000  EPP  4.05e8  -  -  -  -  -  -  0.008
```

---

## Ejemplos de Perfiles

### Ejemplo 1: Arena Homogénea Uniforme

**Escenario**: Sitio simple con una sola formación geológica

```txt
# EJEMPLO 1: ARENA HOMOGÉNEA
# Sitio de arena con incremento de Vs con profundidad
# Referencias: Hardin & Drnevich (1972), Kramer (1996)

# thickness(m)  vs(m/s)  rho(kg/m3)  model  G_max(Pa)     gamma_ref  n    xi_ref  alpha_g  alpha_x  beta  gamma_yield
3.0             200      1750        H2     7.0e7         0.004      0.5  0.04    -        -        -     -
3.0             220      1780        H2     8.64e7        0.004      0.5  0.04    -        -        -     -
4.0             240      1800        H2     1.036e8       0.005      0.5  0.05    -        -        -     -
5.0             260      1820        H2     1.23e8        0.005      0.5  0.05    -        -        -     -
10.0            300      1880        H2     1.69e8        0.005      0.5  0.05    -        -        -     -
```

---

### Ejemplo 2: Perfil Heterogéneo Estratificado

**Escenario**: Sitio complejo con depósito de arena sobre arcilla

```txt
# EJEMPLO 2: PERFIL ESTRATIFICADO HETEROGÉNEO
# Arena sobre arcilla
# Capa 1: Arena suelta (amplificación esperada)
# Capa 2: Arcilla firme (amortiguamiento)
# Referencias: Asimaki et al. (2005), Kramer (1996)

# thickness(m)  vs(m/s)  rho(kg/m3)  model  G_max(Pa)     gamma_ref  n    xi_ref  alpha_g  alpha_x  beta  gamma_yield
5.0             200      1750        H2     7.0e7         0.004      0.5  0.04    -        -        -     -
5.0             220      1800        H4     8.64e7        0.004      0.5  0.05    0.45     0.55     -     -
8.0             280      1850        H4     1.45e8        0.005      0.55 0.05    0.45     0.55     -     -
12.0            250      1850        HH     1.125e8       0.003      0.75 0.08    0.50     0.50     0.35  -
20.0            350      1950        HH     2.33e8        0.004      0.7  0.07    0.50     0.50     0.30  -
```

---

### Ejemplo 3: Sitio Blando (Mexico DF tipo)

**Escenario**: Arcillas muy blandas con degradación severa

```txt
# EJEMPLO 3: SITIO BLANDO - LAKEBED
# Zona de lago - Arcillas blandas estratificadas
# Amplificación esperada: 4-6x
# Referencias: Singh et al. (1988), Shi & Asimaki (2017)

# thickness(m)  vs(m/s)  rho(kg/m3)  model  G_max(Pa)     gamma_ref  n    xi_ref  alpha_g  alpha_x  beta  gamma_yield
5.0             100      1700        HH     1.7e7         0.002      0.8  0.12    0.50     0.50     0.40  -
10.0            120      1750        HH     2.52e7        0.0015     0.85 0.14    0.50     0.50     0.40  -
15.0            140      1800        HH     3.528e7       0.001      0.90 0.13    0.50     0.50     0.40  -
20.0            160      1850        HH     4.608e7       0.0012     0.85 0.12    0.50     0.50     0.35  -
```

---

### Ejemplo 4: Sitio Rocoso

**Escenario**: Roca competente, comportamiento predominantemente elástico

```txt
# EJEMPLO 4: SITIO ROCOSO
# Bedrock o suelos muy densos
# Amplificación esperada: 1-1.5x
# Referencias: Kramer (1996), Boore & Joyner (1997)

# thickness(m)  vs(m/s)  rho(kg/m3)  model  G_max(Pa)     gamma_ref  n    xi_ref  alpha_g  alpha_x  beta  gamma_yield
10.0            400      2000        H2     3.2e8         0.008      0.4  0.03    -        -        -     -
15.0            500      2050        H2     5.125e8       0.008      0.4  0.03    -        -        -     -
20.0            600      2100        H2     7.56e8        0.010      0.4  0.03    -        -        -     -
100.0           700      2150        EPP    1.0519e9      -          -    -       -        -        -     0.005
```

---

## Uso en Python

### 1. Cargar un perfil desde archivo .txt

```python
from seismosoil_advanced import read_stratified_profile, VsProfile

# Cargar perfil
profile = read_stratified_profile('path/to/profile.txt')

# Mostrar estratigrafía
profile.print_stratigraphy()

# Acceder a propiedades
for i, layer in enumerate(profile.layers):
    print(f"Capa {i+1}:")
    print(f"  Espesor: {layer.thickness} m")
    print(f"  Vs: {layer.vs} m/s")
    print(f"  Modelo: {layer.constitutive_params.model_type}")
    print(f"  G_max: {layer.constitutive_params.G_max} Pa")
```

### 2. Crear un perfil programáticamente

```python
from seismosoil_advanced import (
    ConstitutiveParameters, SoilLayer, VsProfile
)

profile = VsProfile(layers=[
    SoilLayer(
        thickness=5.0, vs=250, density=1800,
        constitutive_params=ConstitutiveParameters(
            model_type='H2', 
            G_max=1.125e8, 
            gamma_ref=0.005, 
            n=0.5, 
            damping_ref=0.05
        )
    ),
    SoilLayer(
        thickness=10.0, vs=350, density=1900,
        constitutive_params=ConstitutiveParameters(
            model_type='H4',
            G_max=2.33e8,
            gamma_ref=0.005,
            n=0.5,
            damping_ref=0.05,
            alpha_g=0.45,
            alpha_x=0.55
        )
    ),
])
```

### 3. Ejecutar análisis

```python
from seismosoil_advanced import NonlinearSiteResponseAdvanced, MotionRecord
import numpy as np

# Crear movimiento
dt = 0.01
t = np.arange(0, 20, dt)
accel = 2.0 * np.sin(2 * np.pi * 0.5 * t) * np.exp(-t/10)
motion = MotionRecord(time=t, acceleration=accel)

# Crear y ejecutar análisis
analysis = NonlinearSiteResponseAdvanced(
    profile=profile,
    dt=dt,
    integration_scheme='euler',
    n_substeps=10
)

results = analysis.compute_response(motion, boundary='rigid')

# Procesar resultados
accel_output = results['acceleration'][:, -1]  # Aceleración en superficie
strain_max = np.max(np.abs(results['strain']), axis=0)
stress_max = np.max(np.abs(results['stress']), axis=0)
```

### 4. Guardar perfil modificado

```python
from seismosoil_advanced import write_stratified_profile

# Modificar y guardar
write_stratified_profile(profile, 'path/to/modified_profile.txt')
```

---

## Validación de Datos

### Verificar Consistencia de Parámetros

```python
from seismosoil_advanced import ConstitutiveParameters

params = ConstitutiveParameters(
    model_type='H2',
    G_max=1.125e8,
    gamma_ref=0.005,
    n=0.5,
    damping_ref=0.05
)

# Validar automáticamente
try:
    params.validate()
    print("✓ Parámetros válidos")
except ValueError as e:
    print(f"✗ Error en parámetros: {e}")
```

### Verificación Automática (read_stratified_profile)

La función `read_stratified_profile()` valida automáticamente:

1. ✓ Número correcto de columnas
2. ✓ Tipos de datos (float para valores numéricos)
3. ✓ Modelos soportados (H2, H4, HH, EPP)
4. ✓ Rango de valores típicos (warning si fuera de rango)
5. ✓ Parámetros requeridos vs ignorados

---

## Troubleshooting

### Error 1: "Invalid model type"
```
✗ Error: Invalid model type 'H3' in layer 3
```
**Solución**: Los modelos soportados son: H2, H4, HH, EPP
- Verificar ortografía (mayúsculas)
- Usar solamente estos 4 modelos

### Error 2: "Missing required parameters"
```
✗ Error: Model 'H4' requires alpha_g and alpha_x (got '-')
```
**Solución**: 
- H4 requiere `alpha_g` y `alpha_x` (no pueden ser `-`)
- H2 no requiere estos (pueden ser `-`)
- HH requiere todos menos `gamma_yield`
- EPP requiere solo `G_max` y `gamma_yield`

### Error 3: "File format error"
```
✗ Error: Expected 12 columns, got 11
```
**Solución**:
- Verificar que el encabezado tenga exactamente 12 columnas
- Contar columnas: thickness, vs, rho, model, G_max, gamma_ref, n, xi_ref, alpha_g, alpha_x, beta, gamma_yield
- Usar espacios múltiples como separadores (no tabs)

### Error 4: "Valor de G_max fuera de rango"
```
⚠ Warning: G_max = 1.5e10 Pa (very high for sand)
```
**Solución**:
- Verificar unidades (debe ser Pa, no MPa o kPa)
- G_max típicos:
  - Arenas: 1e7 - 3e8 Pa
  - Arcillas: 1e6 - 5e8 Pa
  - Gravas: 2e8 - 2e9 Pa

### Error 5: "AttributeError: 'VsProfile' object has no attribute..."
```
✗ ValueError: gamma_ref must be > 0
```
**Solución**: 
- Valores positivos requeridos (γ_ref > 0)
- No usar cero o negativos

---

## Resumen de Referencias Bibliográficas

| Referencia | Tema | Ecuación |
|-----------|------|---------|
| Kondner & Zelasko (1963) | Hiperbólica base | τ = γG/(1+\|γ\|/γ_max) |
| Hardin & Drnevich (1972) | Degradación de G | G(γ) = G_max/[1+(γ/γ_ref)^n] |
| Masing (1926) | Regla de histéresis | Simetría carga/descarga |
| Asimaki et al. (2005) | Modelo H4 | α_g ≠ α_x (asimetría) |
| Shi & Asimaki (2017) | Modelo HH | β (amortiguamiento no lineal) |
| Kramer (1996) | Tablas de parámetros | Rangos por tipo suelo |
| Borja (1991) | Marco de plasticidad | Criterio de fluencia |
| Singh et al. (1988) | Arcillas de México | Comportamiento lakebed |

---

## Checklist antes de ejecutar análisis

- [ ] Archivo .txt existe y es legible
- [ ] Encabezado de columnas correcto (12 columnas)
- [ ] Modelos válidos (H2, H4, HH, EPP)
- [ ] Parámetros requeridos presentes
- [ ] Parámetros no usados marcados con `-`
- [ ] Valores dentro del rango esperado
- [ ] Sumatoria de espesores = profundidad total esperada
- [ ] Vs aumenta con profundidad (típicamente)
- [ ] Densidad aumenta con profundidad (típicamente)
- [ ] Archivo sin errores de formato

---

## Información de Contacto/Documentación

Para más información sobre los modelos constitutivos, consultar:

- **SeismoSoil Original**: https://asimaki.caltech.edu/seismosoil/
- **Documentación técnica**: Ver ARCHITECTURE.md
- **Ejemplos**: Ver examples_advanced.py

