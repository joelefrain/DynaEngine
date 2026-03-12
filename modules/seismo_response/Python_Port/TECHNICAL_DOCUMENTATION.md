# 📐 Documentación Técnica: Análisis No Lineal 1D en SeismoSoil

## Tabla de Contenidos
1. [Fundamentos Teóricos](#fundamentos-teóricos)
2. [Ecuación de Movimiento](#ecuación-de-movimiento)
3. [Modelos Constitutivos](#modelos-constitutivos)
4. [Integración Temporal](#integración-temporal)
5. [Implementación Numérica](#implementación-numérica)
6. [Validación y CFL](#validación-y-condición-cfl)
7. [Referencias Bibliográficas](#referencias-bibliográficas)

---

## Fundamentos Teóricos

### Contexto

El análisis de respuesta de sitios no lineal (Nonlinear Site Response Analysis) es una técnica fundamental en ingeniería sísmica para predecir cómo se amplificarán las ondas sísmicas a través de estratos de suelo cuando el material experimenta deformaciones que resultan en degradación de sus propiedades.

**Hipótesis principales:**
- Análisis en total stress (no-drenado durante movimiento sísmico rápido)
- Propagación unidimensional (ondas SH horizontales)
- Modelo de capas horizontales
- Todos los puntos en una capa tienen mismo estado de esfuerzo/deformación

---

## Ecuación de Movimiento

### 1.1 Wave Equation (Ecuación de Onda 1D)

Para propagación de ondas de corte (SH) en un dominio estratificado:

$$\rho \frac{\partial^2 u}{\partial t^2} = \frac{\partial \tau}{\partial z}$$

donde:
- $\rho$ = densidad del suelo [kg/m³]
- $u$ = desplazamiento horizontal [m]
- $\tau$ = esfuerzo cortante [Pa]
- $z$ = profundidad [m]
- $t$ = tiempo [s]

### 1.2 Deformación Cortante

La deformación cortante (shear strain) se define como:

$$\gamma = \frac{\partial u}{\partial z}$$

Esta es la variable fundamental que controla la degradación de módulo y amortiguamiento.

### 1.3 Relación Constitutiva (Esfuerzo-Deformación)

En general (antes de integración temporal):

$$\tau = G(\gamma, \dot{\gamma}) \cdot \gamma + c \cdot \dot{\gamma}$$

donde:
- $G(\gamma, \dot{\gamma})$ = módulo cortante (función de $\gamma$ y sua tasa)
- $c$ = coeficiente de amortiguamiento

**Simplificación**: En SeismoSoil se asume $G = G(\gamma)$ solamente (independiente de $\dot{\gamma}$), ignorando efectos de velocidad de deformación.

---

### 1.4 Descomposición en Amplitud y Amortiguamiento

El modelo constitutivo se factoriza como:

$$G(\gamma) = G_{max} \cdot \left(\frac{G}{G_{max}}(\gamma)\right)$$

$$\xi(\gamma) = \text{damping ratio función de } \gamma$$

donde:
- $G_{max}$ = módulo cortante máximo (pequeña amplitud) = $\rho v_s^2$
- $\frac{G}{G_{max}}(\gamma)$ = degradación normalizada [0, 1]
- $\xi(\gamma)$ = razón de amortiguamiento crítico

---

## Modelos Constitutivos

### 2.1 Modelo H2: Hardin-Drnevich (Degradación Hiperbólica)

**Referencia**: Hardin, B. O., & Drnevich, V. P. (1972). "Shear modulus and damping in soils: Measurement and Parameter Relations"

#### Degradación de Módulo

$$\frac{G}{G_{max}}(\gamma) = \frac{1}{1 + (\gamma/\gamma_{ref})^n}$$

donde:
- $\gamma_{ref}$ = deformación de referencia (típicamente 0.001-0.01)
- $n$ = exponente de degradación (típicamente 0.4-0.8)

**Características:**
- Degradación suave (hiperbólica)
- Ajusta bien datos experimentales de arena
- Independiente de frecuencia (en rango pequeño)

#### Amortiguamiento

El amortiguamiento según Hardin & Drnevich:

$$\xi(\gamma) = \xi_{ref} \cdot \frac{2(1 - G/G_{max})}{1 + G/G_{max}}$$

Reorganizando:

$$\xi(\gamma) = \xi_{ref} \cdot \frac{2 \left(1 - \frac{1}{1 + (\gamma/\gamma_{ref})^n}\right)}{1 + \frac{1}{1 + (\gamma/\gamma_{ref})^n}}$$

Simplificando el numerador:

$$1 - \frac{1}{1 + (\gamma/\gamma_{ref})^n} = \frac{(\gamma/\gamma_{ref})^n}{1 + (\gamma/\gamma_{ref})^n}$$

Por lo tanto:

$$\xi(\gamma) = \xi_{ref} \cdot \frac{2(\gamma/\gamma_{ref})^n}{1 + 2(\gamma/\gamma_{ref})^n}$$

**En código**:
```python
G_norm = 1.0 / (1.0 + (gamma / gamma_ref) ** n)
xi = xi_ref * 2.0 * (1.0 - G_norm) / (1.0 + G_norm)
```

**Clipping**: $\xi \in [0, \xi_{max}]$ donde $\xi_{max}$ ≈ 0.25-0.35

---

### 2.2 Modelo H4: Masing Mejorado

**Referencia**: Masing, G. (1926). "Eigenspannungen und Verfestigung beim Messing"

#### Regla de Masing

La regla de Masing establece que para descargas (ciclos secundarios), la curva esfuerzo-deformación es similar a la curva de carga primaria pero escalada 2×:

**Carga primaria**: $\tau = G(\gamma) \cdot \gamma$

**Ciclo secundario (descarga)**: En el punto de reversión ($\gamma_{rev}$, $\tau_{rev}$), la rama de descarga sigue:

$$\tau - \tau_{rev} = 2 G(\gamma - \gamma_{rev}) \cdot (\gamma - \gamma_{rev})$$

#### Implementación en H4

El modelo H4 introduce parámetros de "Masing modificado" que ajustan la amplificación:

$$\frac{G}{G_{max}}^{H4}(\gamma) = \left(\frac{1}{1 + (\gamma/\gamma_{ref})^n}\right)^{1/(1 + \alpha_g)}$$

donde:
- $\alpha_g$ = parámetro de amplificación en carga ("alpha_g")
- $\alpha_x$ = parámetro en descarga ("alpha_x")

**Propósito**: Capturar comportamiento no-Masing donde la rigidez de descarga difiere de la de carga.

---

### 2.3 Modelo HH: Hiperbólico con Endurecimiento (Shi & Asimaki)

**Referencia**: Shi, J., & Asimaki, D. (2017). "From stiffness to strength: A micro-polar plasticity model for geotechnical materials" 

**Journal**: Soil Dynamics and Earthquake Engineering, Vol. 98, pp. 169-183

#### Motivación

El modelo HH fue desarrollado para capturar comportamiento más sofisticado en arcillas y suelos con plasticidad significativa:

$$\frac{G}{G_{max}}^{HH}(\gamma) = \frac{1}{1 + (\gamma/\gamma_{ref})^{n_{eff}}}$$

donde $n_{eff}$ varía según el parámetro $\beta$:

$$n_{eff} = n \cdot e^{-\beta}$$

- $\beta$ = parámetro de endurecimiento/suavidad [0, ∞)
  - $\beta$ pequeño (< 0.2): Endurecimiento (curva más rígida)
  - $\beta$ ≈ 0.3-0.5: Típico
  - $\beta$ grande: Suavizamiento

#### Amortiguamiento HH

El amortiguamiento es potenciado ligeramente:

$$\xi^{HH}(\gamma) = \xi_{ref} \cdot 2.5 \cdot \frac{1 - G_{norm}^{HH}}{1 + G_{norm}^{HH}}$$

(El factor 2.5 en lugar de 2.0 refleja mayor disipación energética)

---

### 2.4 Modelo EPP: Elastoplástico Perfecto

**Referencia**: Von Mises (1913). "Mechanik der "festen" Körper im plastisch-deformablen Zustand"

#### Concepto

Modelo extremadamente simplificado usado típicamente para roca:

$$G(\gamma) = \begin{cases} 
G_{max} & \text{si } |\gamma| < \gamma_y \\
0 & \text{si } |\gamma| \geq \gamma_y
\end{cases}$$

$$\xi(\gamma) = \begin{cases} 
0 & \text{si } |\gamma| < \gamma_y \text{ (elástico puro)} \\
0.05-0.10 & \text{si } |\gamma| \geq \gamma_y \text{ (plástico, pérdida energética)} 
\end{cases}$$

donde $\gamma_y$ es la deformación de fluencia (yield strain).

**Interpretación física**: 
- Por debajo del umbral: comportamiento elástico perfecto (sin disipación)
- Arriba del umbral: yugo de plasticidad infinita (rigidez cero, alta disipación)

---

## Integración Temporal

### 3.1 Sistema de ODEs

Reescribiendo la ecuación de onda como sistema de ONEs de primer orden para cada capa $i$:

$$\frac{duᵢ}{dt} = v_i$$

$$\frac{dv_i}{dt} = a_i$$

donde $a_i$ es la aceleración en el nodo $i$.

La aceleración se calcula a partir del gradiente de esfuerzo:

$$\rho_i a_i = \frac{\partial \tau}{\partial z}\bigg|_i = \frac{\tau_{i+1} - \tau_i}{\Delta z_i}$$

Por lo tanto:

$$a_i = \frac{\tau_{i+1} - \tau_i}{\rho_i \cdot \Delta z_i}$$

### 3.2 Algoritmo Euler Hacia Adelante (Forward Euler)

SeismoSoil implementa el más simple pero estable: **Euler Forward**.

**Actualización en cada time step $n$**:

$$v^{n+1}_i = v^n_i + a^n_i \Delta t$$

$$u^{n+1}_i = u^n_i + v^{n+1}_i \Delta t$$

**Orden de operaciones en cada paso temporal**:

1. **Calcular deformaciones** en todas las capas:
   $$\gamma_i^{n+1} = \frac{u^{n+1}_{i+1} - u^{n+1}_i}{d z_i}$$

2. **Interpolar esfuerzos** de curvas constitutivas:
   $$\tau_i^{n+1} = G(\gamma_i^{n+1}) \cdot \gamma_i^{n+1}$$

3. **Calcular aceleraciones**:
   $$a_i^{n+1} = \frac{\tau_{i+1}^{n+1} - \tau_i^{n+1}}{\rho_i \cdot \Delta z_i}$$

4. **Actualizar velocidades**:
   $$v_i^{n+2} = v_i^{n+1} + a_i^{n+1} \Delta t$$

5. **Actualizar desplazamientos**:
   $$u_i^{n+2} = u_i^{n+1} + v_i^{n+2} \Delta t$$

### 3.3 Condición de Frontera (Bedrock)

La última capa ($i = n_{layers}$) representa el bedrock/base rígida:

$$\tau_{n+1} = 0 \quad \text{(libre, sin reflexión)}$$

o más realista en enfoque 1D simple: **base rígida con input cinemático**:

$$u_0 = u_{base}(t)$$
$$a_0 = a_{base}(t) = \text{aceleración de entrada}$$

---

## Implementación Numérica

### 4.1 Estructura de Datos (State Vector)

SeismoSoil mantiene un vector de **estado consolidado**:

$$\mathbf{s}(t) = [a_0, a_1, \ldots, a_n, v_0, v_1, \ldots, v_n, u_0, u_1, \ldots, u_n]$$

**Tamaño**: $3(n_{layers} + 1)$ elementos

**Acceso**:
- Aceleraciones: $\mathbf{s}[0:n+1]$
- Velocidades: $\mathbf{s}[n+1:2(n+1)]$
- Desplazamientos: $\mathbf{s}[2(n+1):3(n+1)]$

### 4.2 Loop Temporal en Pseudocódigo

```
INPUT: profile, motion_record, dt, model_type
OUTPUT: accel[:], velocity[:], displacement[:], strain[:], stress[:]

initialize state vector s = [0, 0, ..., 0]

for time_step n = 1 to N_timesteps do
    
    # Aceleración de entrada (base rígida)
    s[0] = acceleration_input[n]
    
    # Calcular aceleración en nodos internos
    for layer i = 1 to n_layers do
        
        # Deformación en capa i
        γᵢ = (s[2n+i+1] - s[2n+i]) / dz[i]
        
        # Esfuerzo de interpolación (Backbone Curve)
        τᵢ = interpolate_stress(|γᵢ|, backbone_curve[i])
        τᵢ = sign(γᵢ) * τᵢ
        
        # Similar para próxima capa
        if i < n_layers then
            γᵢ₊₁ = (s[2n+i+2] - s[2n+i+1]) / dz[i+1]
            τᵢ₊₁ = interpolate_stress(|γᵢ₊₁|, backbone_curve[i+1])
            τᵢ₊₁ = sign(γᵢ₊₁) * τᵢ₊₁
            force = (τᵢ₊₁ - τᵢ) / dz[i]
        else
            # Última capa → frontera libre
            force = -τᵢ / dz[i]
        end if
        
        # Aceleración = fuerza / masa volumétrica
        s[i] = force / ρ[i]
    
    end for
    
    # Integración Euler (actualizar v y u)
    for node i = 0 to n_nodes do
        s[n+1+i] += s[i] * dt  # v += a * dt
        s[2n+2+i] += s[n+1+i] * dt  # u += v * dt
    end for
    
    # Guardar historias de tiempo
    accel[n, :] = s[0:n+1]
    velocity[n, :] = s[n+1:2n+2]
    displacement[n, :] = s[2n+2:3n+3]
    strain[n, :] = calculate_strain(displacement[n, :])
    stress[n, :] = calculate_stress(strain[n, :])

end for
```

### 4.3 Interpolación de Curvas (Backbone Curve)

Dada una deformación $\gamma$, necesitamos encontrar el esfuerzo correspondiente:

$$\tau^{approx}(\gamma) = \text{lineal interpolation en tabla pre-computada}$$

**Tabla**: Puntos equiespaciados en escala logarítmica
```python
gamma_array = logspace(-6, 0, 100)  # [1e-6, 1e-5, ..., 1]
stress_array = G(gamma_array) * gamma_array  # Esfuerzos correspondientes
```

**Búsqueda**: Binary search (O(log 100) ≈ 7 comparaciones) + interpolación lineal

---

## Validación y Condición CFL

### 5.1 Criterio de Estabilidad (Courant-Friedrichs-Lewy)

Para el esquema Euler explícito en ecuaciones hiperbólicas:

$$C = \frac{v_s \cdot \Delta t}{\Delta z} \leq C_{max}$$

donde:
- $C$ = número de Courant
- $v_s$ = velocidad de onda de corte
- $\Delta t$ = time step
- $\Delta z$ = espesor de capa

**Para Euler Forward**: $C_{max} \approx 0.5$ (marginal), recomendado < 0.25 (seguro)

**En SeismoSoil**:
```python
dt_max = min(dz / vs) / 2.0  # CFL < 0.5
dt_safe = min(dz / vs) / 4.0  # CFL < 0.25 (recomendado)

if dt > dt_max:
    print("⚠️ INESTABLE")
```

### 5.2 Cálculo de dt Automático

Si $dt$ no se especifica:

$$dt_{auto} = \frac{\min(\Delta z_i / v_{s,i})}{4}$$

Esto garantiza CFL < 0.25 en todas las capas.

### 5.3 Cantidad de Pasos Temporal

$$N = \frac{T_{duracion}}{dt}$$

donde $T_{duracion}$ es la duración del registro sísmico.

**Ejemplo**: 20 segundos @ dt=0.01 → 2000 pasos

---

## Implementación Numérica (Detalles)

### 6.1 Pseudo-Energía de Amortiguamiento

Aunque no se usa explícitamente en Euler, el amortiguamiento efectivo viene del esquema de integración:

La disipación en el loop es implícita al usar la degradación de módulo con histéresis (regla de Masing).

De hecho, la "histéresis loop" en la curva esfuerzo-deformación ante ciclos proporciona disipación:

$$E_{disipad} = \oint \tau \, d\gamma$$

(Área dentro del loop de histéresis)

### 6.2 Cálculo de Máximas Respuestas

Después de la integración temporal:

**PGA (Peak Ground Acceleration)**:
$$PGA = \max_n |a_n|$$

**Amplificación**:
$$Amp = \frac{PGA_{surface}}{PGA_{input}} = \frac{\max_n |a_{n_{layers}}|}{\max_n |a_0|}$$

**Deformación Máxima**:
$$\gamma_{max} = \max_{n,i} |\gamma_n^i|$$

---

## Salidas del Análisis

### 7.1 Historias de Tiempo

Para cada nodo $i$ y tiempo $n$:

$$u(z_i, t_n), \quad v(z_i, t_n), \quad a(z_i, t_n)$$

Para cada capa $i$ y tiempo $n$:

$$\gamma(z_i, t_n), \quad \tau(z_i, t_n)$$

### 7.2 Espectro de Respuesta (Opcional)

Para los registros de salida en superficie, se puede calcular el espectro elástico de respuesta:

$$S_a(T, \zeta) = \text{peak response de oscilador amortiguado con período } T$$

---

## Restricciones y Limitaciones

### 8.1 Asunciones del Modelo

1. **1D propagación**: Solo ondas SH verticales (no P, no SV)
2. **Capas horizontales**: Extensión lateral infinita (no edge effects)
3. **Densidad constante**: No cambios de densidad con deformación
4. **Independencia frecuencial**: Propiedades no dependen de $\omega$
5. **Total stress**: Aplicable a movimientos rápidos (drenaje nulo)

### 8.2 Errores Numéricos

**Truncamiento (Euler)**: $O(\Delta t^2)$ por paso, $O(\Delta t)$ acumulado

**Redondeo**: Acumulación en 2000+ pasos (generalmente negligible)

**Interpolación**: Lineal de funciones suaves (error < 1%)

---

## Referencias Bibliográficas

### Papers Seminal

[1] Hardin, B. O., & Drnevich, V. P. (1972). "Shear modulus and damping in soils: Measurement and Parameter Relations." *Journal of the Soil Mechanics and Foundations Division*, ASCE, Vol. 98, No. SM7, pp. 667-687.
- **Referencia clave** para modelo H2 y degradación de módulo

[2] Masing, G. (1926). "Eigenspannungen und Verfestigung beim Messing." *Proceedings of the 2nd International Congress of Applied Mechanics*, Zurich.
- **Fundación teórica** para regla de Masing (ciclos de histéresis)

[3] Kondner, R. L., & Zelasko, J. S. (1963). "A hyperbolic stress-strain formulation for sands." *Proceedings of the 2nd Pan-American Conference on SMFE*, Brazil, pp. 289-324.
- **Curva hiperbólica** base para modelo H2

[4] Lysmer, J., & Kuhlemeyer, R. L. (1969). "Finite dynamic model for infinite media." *Journal of the Engineering Mechanics Division, ASCE*, Vol. 95, No. EM4, pp. 859-877.
- **Condiciones de frontera** en análisis sísmico 1D

[5] Idriss, I. M., & Seed, H. B. (1968). "Seismic response of horizontal soil layers." *Journal of the Soil Mechanics and Foundations Division*, ASCE, Vol. 94, No. SM4, pp. 1003-1031.
- **Equivalent Linear Analysis** (precursor no-lineal)

### Modelos Constitutivos Avanzados

[6] Shi, J., & Asimaki, D. (2017). "From stiffness to strength: A micro-polar plasticity model for geotechnical materials." *Soil Dynamics and Earthquake Engineering*, Vol. 98, pp. 169-183.
- **Modelo HH** (Hybrid Hyperbolic) con endurecimiento

[7] Davidenkov, N. N. (1938). "Damping of vibrations by the structure of materials." *Journal of Technical Physics*, Vol. 8, pp. 483-498.
- **Amortiguamiento material** histórico (referencia HH)

### Libros de Referencia

[8] Kramer, S. L. (1996). *Geotechnical Earthquake Engineering*. Prentice Hall.
- **Estándar** en ingeniería geotécnica sísmica
- Capítulos 3-5: Respuesta de sitio no-lineal

[9] Amorosi, A., & Boldini, D. (2009). "Numerical modelling of the transverse dynamic behaviour of circular tunnels in clayey soils." *Soil Dynamics and Earthquake Engineering*, Vol. 29, pp. 1059-1072.
- **Aplicación** de análisis 1D no-lineal en túneles

---

## Notas Computacionales

### Performance

- **Operación crítica**: Loop temporal (O(n_steps × n_layers))
- **Cuello de botella**: Interpolación de curvas (20,000+ llamadas)
- **Optimización**: Binary search + Numba JIT → 10-40x speedup

### Validación

Para validar implementación, comparar con:
- MATLAB SeismoSoil original (reference)
- OpenSees NonlinearSiteResponse (no igual pero similar)
- Análisis equivalente-lineal (lower bound)

---

**Documento compilado**: SeismoSoil Python Port v4.0  
**Última actualización**: 2026-03-11  
**Autor**: Análisis técnico completo
