# ⚡ SeismoSoil Advanced - Quick Start (5 minutos)

**Guía rápida sin leer documentación completa**

---

## 🚀 Paso 1: Tu Primer Análisis (2 min)

```python
from seismosoil_advanced import (
    create_example_profile,
    create_example_motion,
    NonlinearSiteResponseAdvanced
)

# Crear datos de ejemplo
profile = create_example_profile()           # 4 capas
motion = create_example_motion(duration=10)  # 10 segundos

# Crear análisis con modelo H2
analysis = NonlinearSiteResponseAdvanced(
    profile,
    model_type='H2',
    gamma_ref=0.005,    # Cambiar esto para sensibilidad
    n=0.5,
    damping_ref=0.05
)

# Ejecutar análisis
results = analysis.compute_response(motion)

# Ver resultados
print(f"PGA entrada:   {results['pga_input']:.3f} m/s²")
print(f"PGA salida:    {results['pga_output']:.3f} m/s²")
print(f"Amplificación: {results['amplification']:.2f}×")
print(f"Máxima deformación: {results['max_shear_strain']:.5f}")
```

**Output esperado:**
```
PGA entrada:   2.000 m/s²
PGA salida:    3.200 m/s²
Amplificación: 1.60×
Máxima deformación: 0.00234
```

---

## 🔄 Paso 2: Comparar Modelos (1 min)

```python
from seismosoil_advanced import (
    create_example_profile,
    create_example_motion,
    NonlinearSiteResponseAdvanced
)

profile = create_example_profile()
motion = create_example_motion()

# Probar H2, H4, HH
for model in ['H2', 'H4', 'HH']:
    analysis = NonlinearSiteResponseAdvanced(profile, model_type=model)
    results = analysis.compute_response(motion)
    print(f"{model}: Amplificación = {results['amplification']:.2f}×, "
          f"Deformación = {results['max_shear_strain']:.5f}")
```

---

## 📁 Paso 3: Guardar y Cargar Perfil (1 min)

```python
from seismosoil_advanced import (
    SoilLayer, VsProfile,
    write_profile, read_profile,
    NonlinearSiteResponseAdvanced,
    create_example_motion
)

# CREAR Y GUARDAR
layers = [
    SoilLayer(thickness=5.0, vs=150, density=1800),
    SoilLayer(thickness=10.0, vs=250, density=1900),
    SoilLayer(thickness=20.0, vs=350, density=2000),
    SoilLayer(thickness=0, vs=500, density=2100),  # bedrock
]

profile = VsProfile(layers=layers)
write_profile(profile, 'my_profile.txt')  # Guardar

# CARGAR Y ANALIZAR
profile = read_profile('my_profile.txt')  # Cargar
analysis = NonlinearSiteResponseAdvanced(profile, model_type='H2')
results = analysis.compute_response(create_example_motion())
print(f"Amplificación: {results['amplification']:.2f}×")
```

Archivo `my_profile.txt` creado:
```
# Espesor(m)  Vs(m/s)  Densidad(kg/m³)
5.0           150      1800
10.0          250      1900
20.0          350      2000
0             500      2100
```

---

## 🎚️ Paso 4: Estudio de Sensibilidad (1 min)

```python
from seismosoil_advanced import (
    create_example_profile,
    create_example_motion,
    NonlinearSiteResponseAdvanced
)

profile = create_example_profile()
motion = create_example_motion()

print("Sensibilidad a gamma_ref (deformación de referencia):")
print("gamma_ref\tAmplificación")
print("-" * 30)

for gamma in [0.001, 0.005, 0.010, 0.020]:
    analysis = NonlinearSiteResponseAdvanced(
        profile,
        model_type='H2',
        gamma_ref=gamma
    )
    results = analysis.compute_response(motion)
    print(f"{gamma:.4f}\t\t{results['amplification']:.3f}×")
```

---

## 💡 Parámetros Tipicos (Copiar)

**Sitio muy blando** (Vs30 < 200 m/s):
```python
gamma_ref=0.010, n=0.70, damping_ref=0.08
```

**Sitio blando** (Vs30 200-400 m/s):
```python
gamma_ref=0.005, n=0.50, damping_ref=0.05
```

**Sitio firme** (Vs30 400-800 m/s):
```python
gamma_ref=0.003, n=0.40, damping_ref=0.03
```

**Roca** (Vs30 > 800 m/s):
```python
gamma_ref=0.001, n=0.30, damping_ref=0.02
```

---

## 🆘 Troubleshooting

| Problema | Solución |
|----------|----------|
| `ModuleNotFoundError: No module named 'seismosoil_advanced'` | Correr desde `Python_Port/` |
| `FileNotFoundError` | Verificar ruta archivo .txt |
| Resultados extraños | Verificar unidades: m, m/s, kg/m³ |
| ImportError: numpy | `pip install numpy scipy` |

---

## 📖 Próximos Pasos

1. **Ver ejemplos completos**: `python examples_advanced.py`
2. **Entender cambios**: `CLEANUP_SESSION_4.md`
3. **Detalles técnicos**: `STRATIFIED_PROFILES_GUIDE.md`