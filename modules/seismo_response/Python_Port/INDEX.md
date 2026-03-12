# SeismoSoil Advanced - Índice de Archivos

## 🎯 RESUMEN

**Análisis no lineal 1D con modelo constitutivo único + formato .txt**

- **Formato**: .txt simple (thickness, vs, density)
- **Modelo**: Especificado en análisis (H2, H4, HH, EPP)
- **Engine**: `seismosoil_advanced.py` (300 líneas, limpio)
- **Ejemplos**: `examples_advanced.py` (4 casos listos para usar)

---

## 📚 Documentación

- **`CLEANUP_SESSION_4.md`** ⭐ **[LEER PRIMERO - CAMBIOS RECIENTES]**
  - Resumen de simplificación: JSON → .txt
  - Arquitectura nueva: modelo único + .txt
  - Cómo usar el sistema simplificado

- **`QUICKSTART_5MIN.md`** (Guía rápida)
  - Primer análisis en 5 minutos
  - Ejemplos copypaste
  - Parámetros típicos

- **`STRATIFIED_PROFILES_GUIDE.md`** (Legacy - .txt reference)
  - Formato .txt original
  - Detalles de modelos constitutivos
  - Tablas de parámetros

---

## 💻 Código Principal

### Motor de Análisis
- **`seismosoil_advanced.py`** ⭐ **[USAR ESTE]** (300 líneas)
  - `NonlinearSiteResponseAdvanced`: análisis no lineal 1D
  - **Clases simples**: VsProfile, SoilLayer, MotionRecord, BackboneCurve, DampingCurve
  - **Modelos**: H2, H4, HH, EPP (especificar en análisis)
  - **I/O**: `read_profile()`, `write_profile()` (formato .txt)
  - **Utilidades**: `create_example_profile()`, `create_example_motion()`
  - **Referencias**: Kondner, Hardin, Masing, Kramer

### Ejemplos (Listos para Usar)
- **`examples_advanced.py`** ⭐ **[EMPEZAR AQUÍ]** (4 ejemplos)
  1. Análisis simple con H2
  2. Comparar modelos (H2 vs H4 vs HH)
  3. Crear perfil personalizado, guardar/cargar .txt
  4. Estudio de sensibilidad de parámetros

### Legacy (Backup)
- `seismosoil_advanced_full.py` - Código anterior (con parámetros per-estrato)
- `seismosoil_core.py` - Versión primitiva
- `seismosoil_io.py` - I/O legacy

---

## 🎯 Cómo Elegir Qué Archivo Leer/Usar

| Objetivo | Archivo |
|----------|---------|
| **Entender cambios recientes** | `CLEANUP_SESSION_4.md` |
| **Empezar inmediatamente (5 min)** | `QUICKSTART_5MIN.md` o `examples_advanced.py` |
| **Ejecutar primer análisis** | `examples_advanced.py` ejemplo 1 |
| **Crear perfil personalizado** | `examples_advanced.py` ejemplo 3 |
| **Comparar modelos (H2 vs H4 vs HH)** | `examples_advanced.py` ejemplo 2 |
| **Estudio de sensibilidad** | `examples_advanced.py` ejemplo 4 |
| **Entender parámetros constitutivos** | `STRATIFIED_PROFILES_GUIDE.md` + `seismosoil_advanced.py` docstrings |
| **Detalles de integración temporal** | `seismosoil_advanced.py` comentarios |
| **Todas las referencias bibliográficas** | `seismosoil_advanced.py` header + `STRATIFIED_PROFILES_GUIDE.md` |
| **Formato .txt** | Primeras líneas de `seismosoil_advanced.py` (read_profile) |

---

## 📋 Dependencias

**Requeridas**:
- numpy
- scipy

**Instalación**:
```bash
pip install numpy scipy
```

---

## 📂 Estructura de Directorios

```
C:\Users\joel.alarcon\Desktop\_code\SeismoSoil\Python_Port\

✅ CÓDIGO:
   seismosoil_advanced.py              [Motor 300 líneas]
   examples_advanced.py                [4 ejemplos listos]
   seismosoil_advanced_full.py         [Backup - código antiguo]
   seismosoil_core.py                  [Legacy]
   seismosoil_io.py                    [Legacy]

📚 DOCUMENTACIÓN:
   CLEANUP_SESSION_4.md                [Cambios recientes ⭐]
   QUICKSTART_5MIN.md                  [Guía 5 min]
   STRATIFIED_PROFILES_GUIDE.md        [.txt y modelos]
   INDEX.md                            [Este archivo]
   README.md                           [Proyecto]

📊 DATOS (Legacy):
   stratified_profiles/
     ├── profile_*.txt                 [Ejemplos .txt]
```

---

## ✨ Características

✅ Análisis no lineal 1D  
✅ Degradación de módulo desde parámetros  
✅ Amortiguamiento dependiente de amplitud  
✅ Múltiples modelos: H2, H4, HH, EPP  
✅ Integración temporal (Euler)  
✅ Formato .txt simple  
✅ 4 ejemplos ejecutables  
✅ Documentación completa  

⏳ Futuros:
- [ ] Integración RK4
- [ ] Profundidad efectiva viscosa
- [ ] Soporte para movimientos reales (PEER)
- [ ] Visualización de resultados
```

---

## 🚀 Cómo Empezar

### Opción 1: Ejecutar Ejemplos (Recomendado)
```bash
cd Python_Port/
python examples_advanced.py
```

**Output esperado:**
- Ejemplo 1: Análisis H2 simple
- Ejemplo 2: Tabla comparativa (H2 vs H4 vs HH)
- Ejemplo 3: Crear, guardar y cargar perfil .txt
- Ejemplo 4: Sensibilidad a parámetros

### Opción 2: Script Personalizado Mínimo
```python
from seismosoil_advanced import (
    NonlinearSiteResponseAdvanced,
    create_example_profile,
    create_example_motion
)

# Cargar datos
profile = create_example_profile()
motion = create_example_motion(duration=10, dt=0.01)

# Análisis
analysis = NonlinearSiteResponseAdvanced(
    profile,
    model_type='H2',
    gamma_ref=0.005,
    n=0.5,
    damping_ref=0.05
)
results = analysis.compute_response(motion)

# Resultados
print(f"Amplificación: {results['amplification']:.2f}×")
print(f"Deformación máxima: {results['max_shear_strain']:.4f}")
```

### Opción 3: Cargar Perfil Existente
```python
from seismosoil_advanced import read_profile, NonlinearSiteResponseAdvanced

# Cargar .txt con 3 columnas (espesor, vs, densidad)
profile = read_profile('stratified_profiles/profile_1_H2_homogeneous.txt')

# Análisis
analysis = NonlinearSiteResponseAdvanced(profile, model_type='H2')
```

---

## 📖 Guía de Archivos

| Necesito... | Leer... | Tiempo |
|---|---|---|
| Empezar ahora | `examples_advanced.py` | 2 min |
| Entender cambios Session 4 | `CLEANUP_SESSION_4.md` | 5 min |
| Guía rápida 5 min | `QUICKSTART_5MIN.md` | 5 min |
| Detalles técnicos | `STRATIFIED_PROFILES_GUIDE.md` | 15 min |
| Arquitectura del código | `seismosoil_advanced.py` (docstrings) | 10 min |

---

## 🔧 Parámetros Típicos

| Parámetro | Rango Típico | Descripción |
|-----------|---|---|
| `gamma_ref` | 0.001–0.02 | Deformación de referencia (adimensional) |
| `n` | 0.3–0.8 | Exponente de degradación |
| `damping_ref` | 0.02–0.08 | Amortiguamiento a γ_ref |
| `damping_max` | 0.15–0.35 | Amortiguamiento máximo |

**Iniciales recomendadas**:
```python
gamma_ref = 0.005    # Valor central
n = 0.5              # Típico
damping_ref = 0.05   # Típico
damping_max = 0.25   # Típico
```

---

## 📝 Formato .txt

Archivo de 3 columnas (espacios):

```
# Espesor(m)  Vs(m/s)  Densidad(kg/m³)
5.0           150      1800
10.0          250      1900
20.0          350      2000
0            500      2100
```

**Notas:**
- Última capa: espesor = 0 (bedrock → infinito)
- Densidad: típicamente 1800–2100 kg/m³
- Vs: desde 50 m/s (muy blando) hasta 1000+ m/s (roca)
| `seismosoil_advanced.py` | código, clases, ecuaciones, implementación |
| `profile_utilities.py` | generador, análisis, validación, conversión de formatos |
| `examples_advanced.py` | demo, ejecutable, creador de perfiles, comparación modelos |
| `SUMMARY_SESSION_2.md` | arquitectura, estado proyecto, próximos pasos |

---

## ✅ Checklist: ¿Qué Debo Haber Leído?

- [ ] `QUICKSTART_5MIN.md` (obligatorio)
- [ ] Ejecutado `examples_advanced.py` (obligatorio)
- [ ] `STRATIFIED_PROFILES_GUIDE.md` si necesito crear .txt (recomendado)
- [ ] `profile_utilities.py` si quiero generar perfiles (recomendado)
- [ ] `SUMMARY_SESSION_2.md` para entender arquitectura (opcional)
- [ ] Docstrings en `seismosoil_advanced.py` para detalles (según necesidad)

---

## 🎓 Niveles de Uso

### Nivel 1: Usuario Principiante (Usar perfiles existentes)
```
QUICKSTART_5MIN.md → examples_advanced.py → profile_1/2/3/4.txt → Análisis
```

### Nivel 2: Usuario Intermedio (Modificar/crear perfiles)
```
STRATIFIED_PROFILES_GUIDE.md → crear profile_mio.txt → Análisis
```

### Nivel 3: Usuario Avanzado (Generar, validar, analizar)
```
profile_utilities.py (ProfileGenerator) → ProfileAnalyzer → ProfileValidator → Análisis
```

### Nivel 4: Desarrollador (Extender, modificar motor)
```
seismosoil_advanced.py → Modificar BackboneCurve/NonlinearSiteResponseAdvanced
```

---

## 📞 Duda Frecuente

**P: ¿Por qué hay `seismosoil_core.py` y `seismosoil_advanced.py`?**
A: `core` es la versión simple original (conservada para referencia). `advanced` es la versión nueva con estratificación y generación de curvas. **Usa `advanced`**.

**P: ¿Necesito Excel/JSON?**
A: No, todo funciona con archivos .txt. JSON/Excel son opcionales con `profile_utilities.py`.

**P: ¿Cuál es el formato .txt correcto?**
A: Ver `STRATIFIED_PROFILES_GUIDE.md` o copiar uno de los perfiles existentes en `stratified_profiles/`.

**P: ¿Cómo valido mi perfil?**
A: ```python
from profile_utilities import ProfileValidator
is_valid, warnings = ProfileValidator.validate_parameters(profile)
```

---

## 🎯 Próximos Pasos después de Completar Básico

1. **Equivalent Linear Analysis**: Módulo para análisis lineal equivalente
2. **RK4 Integration**: Integración de orden superior
3. **Elastic Boundaries**: Condiciones de contorno elásticas
4. **2D/3D Extension**: Análisis bidimensional y tridimensional
5. **Performance**: Optimización con Numba/Cython

---

**¡Comienza con `QUICKSTART_5MIN.md`!** 🚀

