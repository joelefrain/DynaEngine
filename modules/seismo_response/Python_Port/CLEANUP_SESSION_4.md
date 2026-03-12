# Simplificación de Arquitectura - Session 4

## ¿Qué Cambió?

### Revertir de JSON a .txt
- **Antes**: Intentamos soportar parámetros independientes por estrato usando JSON
- **Problema identificado**: Si todos los estratos usan el MISMO modelo, JSON es innecesario y aumenta complejidad
- **Solución**: Volver a .txt simple + un modelo único para todo el perfil

### Arquitectura Simplificada

```
Antes:
- Cada capa con parámetros independientes
- JSON con estructura compleja
- ~600 líneas de código en profile_utilities.py
- Documentación extensiva para JSON

Después:
- Un modelo constitutivo para TODO el perfil
- .txt simple (3 columnas: thickness, vs, density)
- ~300 líneas de código limpio en seismosoil_advanced.py
- Especificar modelo (H2/H4/HH/EPP) SOLO en el análisis
```

## Cambios en Código

### seismosoil_advanced.py (Simplicado)
- ❌ Eliminar: `ConstitutiveParameters` (parámetros per-estrato)
- ❌ Eliminar: `SoilLayer.generate_curves()` y parámetros constitutivos
- ✅ Mantener: Clases simples: `BackboneCurve`, `DampingCurve`, `SoilLayer`, `VsProfile`
- ✅ Mantener: `NonlinearSiteResponseAdvanced` con modelo único
- ✅ Mejorar: Especificar modelo en `__init__()`:

```python
# Antes
layer = SoilLayer(thickness=5, vs=250, density=1800, constitutive_params=...)

# Después (en análisis)
analysis = NonlinearSiteResponseAdvanced(
    profile,
    model_type='H2',        # ← Modelo especificado AQUÍ
    gamma_ref=0.005,
    n=0.5,
    damping_ref=0.05
)
```

### examples_advanced.py (Simplificado)
- ❌ Eliminar: Lógica de carga/creación de JSON
- ✅ Nuevo: 4 ejemplos claros:
  1. Análisis simple con H2
  2. Comparar modelos (H2 vs H4 vs HH)
  3. Crear perfil personalizado, guardar/cargar .txt
  4. Estudio de sensibilidad de parámetros

### Archivos Eliminados
- ❌ `profile_utilities.py` (600+ líneas - innecesario)
- ❌ `profiles/` directorio (4 archivos JSON)
- ❌ `JSON_FORMAT_GUIDE.md` (600+ líneas)
- ❌ `REFACTOR_TO_JSON_SUMMARY.md`
- ❌ `REFACTOR_CHECKLIST.md`
- ❌ `SESSION_3_SUMMARY.md`

### Archivos Creados
- ✅ `seismosoil_advanced_full.py` (backup del código anterior)

## Formato .txt Recomendado

```
thickness(m)  vs(m/s)  density(kg/m³)
5.0           250      1800
5.0           300      1850
10.0          400      1900
15.0          500      2000
```

Usar con:
```python
profile = read_profile('mi_perfil.txt')
analysis = NonlinearSiteResponseAdvanced(profile, model_type='H2')
results = analysis.compute_response(motion)
```

## ¿Por Qué Este Cambio?

1. **Simplicidad**: Un modelo para todo el perfil es común en práctica
2. **Menos código**: De 600+ líneas a ~300 líneas
3. **Menos confusión**: Parámetros del modelo en lugar de per-capa
4. **.txt suficiente**: Para geometría, JSON no añade valor
5. **Faster prototyping**: Menos abstracciones, fácil de modificar

## Modelos Soportados

Todos en `NonlinearSiteResponseAdvanced.__init__()`:

| Modelo | Referencias | Parámetros Principales |
|--------|------------|------------------------|
| **H2** | Masing (1926), Kondner-Zelasko (1963) | gamma_ref, n, damping_ref |
| **H4** | Asimaki et al. (2005) | + alpha_g, alpha_x (asimetría) |
| **HH** | Shi & Asimaki (2017) | + beta (flexibilidad) |
| **EPP** | Borja (1991) | gamma_yield |

## Cómo Usar

### 1. Crear perfil
```python
from seismosoil_advanced import SoilLayer, VsProfile, MotionRecord
from seismosoil_advanced import NonlinearSiteResponseAdvanced

# Opción A: Manualmente
layers = [
    SoilLayer(thickness=5.0, vs=250, density=1800),
    SoilLayer(thickness=10.0, vs=300, density=1850),
]
profile = VsProfile(layers=layers)

# Opción B: Desde archivo .txt
from seismosoil_advanced import read_profile
profile = read_profile('perfil.txt')
```

### 2. Especificar modelo EN EL ANÁLISIS
```python
analysis = NonlinearSiteResponseAdvanced(
    profile,
    model_type='H2',           # ← Especificar aquí
    gamma_ref=0.005,
    n=0.5,
    damping_ref=0.05
)
```

### 3. Ejecutar
```python
results = analysis.compute_response(motion)

print(f"Amplificación: {results['amplification']:.2f}×")
print(f"PGA salida: {results['pga_surface']:.3f} m/s²")
```

## Próximos Pasos (Opcionales)

- [ ] Agregar más ejemplos de perfiles .txt
- [ ] Mejorar visualización de resultados
- [ ] Optimizar integración temporal (RK4 en lugar de Euler)
- [ ] Soporte para movimientos reales (PEER database)
- [ ] Exportar resultados a Excel

## Backward Compatibility

- ❌ Código anterior con `ConstitutiveParameters` por capa: **NO compatible**
- ✅ Archivos .txt: pueden ser reciclados
- ✅ Lógica de análisis: mantenida, solo reorganizada

## Estado Actual

```
C:\Users\joel.alarcon\Desktop\_code\SeismoSoil\Python_Port\

📄 seismosoil_advanced.py          [NEW - 300 líneas, simplificado]
📄 examples_advanced.py             [NEW - 4 ejemplos listos]
📄 seismosoil_advanced_full.py      [BACKUP - código antiguo]

📚 Documentación:
   - STRATIFIED_PROFILES_GUIDE.md   [.txt legacy]
   - QUICKSTART_5MIN.md             [válido]
   - INDEX.md                       [actualizar]
   - README.md                      [actualizar]
```

---

**Resultado**: Arquitectura más limpia, código más simple, más fácil de mantener ✅
