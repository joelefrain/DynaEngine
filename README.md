# DynaEngine

DynaEngine queda reorganizado como un paquete de calculo local para una aplicacion de escritorio. Las entradas publicas no usan rutas globales y no escriben archivos salvo que se entregue una ruta explicita.

## Capacidades

- Curvas dinamicas por autor: Darendeli, Menq, Rollins, Ishibashi & Zhang, Wang & Stokoe, Rojas, Seed & Idriss y curvas definidas por el usuario.
- Calibracion GQH y MRDF desde curvas dinamicas.
- Lectura DXF de secciones, columnas no discretizadas, analisis de superficies de falla y discretizacion por frecuencia objetivo.

## Estructura

- `src/dynaengine/data/`: catalogo de modelos y curvas discretas requeridas por los autores.
- `examples/`: scripts ejecutables y pequenos.
- `notebooks/`: notebooks limpios que ejecutan el nucleo nuevo.

## Regla de guardado

Las funciones devuelven objetos Python o `DataFrame`. Para guardar resultados se debe pasar una ruta explicita:

```python
from dynaengine import export_dataframe

export_dataframe(frame, "salidas/columna.csv")
```

## Materiales

No hay valores geotecnicos predefinidos. Cada material debe traer nombre, peso unitario, perfil Vs, resistencia al corte y modelo dinamico. `sigma_vertical` no es obligatorio en el material: durante el flujo de columnas se recalcula como esfuerzo efectivo vertical del segmento antes de evaluar la curva dinamica.

Para evaluar una curva dinamica de forma aislada, fuera de columnas/discretizacion, los modelos dependientes de confinamiento usan `sigma_vertical=100 kPa` por defecto si no se entrega el valor. La funcion emite una advertencia en ese caso; para calibraciones o comparaciones directas conviene pasar `sigma_vertical` explicitamente.

Si el DXF genera un `Estrato no identificado`, el usuario puede asociarlo a un material existente o crear un material nuevo antes de discretizar/calibrar. Si un estrato no identificado queda sin resolver, deben omitirse las columnas que lo cruzan; `filter_columns_with_unresolved_materials` devuelve la lista de columnas omitidas para notificar al usuario.

El ejemplo `section_01.dxf` lee sus materiales desde:

```python
examples/data/section_01_materials.json
```

## Fallas en DXF

`extract_columns_from_dxf` calcula `failure_height` para cada polilinea `SUP_FALLA` como la separacion vertical maxima con la curva superior de `EXTERNAL`. El tipo de falla lo entrega el usuario:

```python
extraction = extract_columns_from_dxf(
    "examples/data/section_01.dxf",
    x_positions={
        "failure_1": [190, 225],
        "failure_2": [250],
    },
    failure_types={"failure_1": "rotacional", "failure_2": "planar"},
)
```

Los campos `failure_id`, `failure_surface`, `failure_type`, `failure_height`, `x_position` y `depth_failure_surface` viajan en cada columna extraida. En las tablas raw/discretizadas/calibradas se conservan como `failure_surface_id`, `failure_surface_name` y `x_position_m`.

`polygon_area_summary` y `area_notifications` reportan `polygon_id`, `area_ratio_to_total`, `bounds`, `representative_point` y `geometry_wkt`. Las areas pequenas se marcan como `small_area_omitted`; se omiten al cortar la columna y las capas superior e inferior se extienden hasta el centro del intervalo pequeno.

## Calibracion

La calibracion GQ/H + MRDF se ejecuta por estrato discretizado. Depende de la curva dinamica del material evaluada con el esfuerzo efectivo vertical del segmento, de `Gmax` calculado con peso unitario y Vs, y de `tau_max` calculado con resistencia al corte, `k0` y esfuerzo efectivo. `CalibrationSettings` usa por defecto `optimizer="scipy"` para una calibracion local multistart mas rapida; `optimizer="bayesian"` también está disponible, aunque es más costosa.
