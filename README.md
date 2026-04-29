# Refactor backend Prismo

## Cambios principales

1. Las coordenadas `x_position` ahora se definen por sección y por superficie de falla.

Formato recomendado:

```python
x_position_map = {
    "section_01": {
        "failure_1": [180, 230, 290],
        "failure_2": [210, 260, 330]
    },
    "section_02.dxf": {
        "failure_1": [150, 200]
    }
}
```

Se aceptan claves de sección como `section_01`, `section_01.dxf` o la ruta completa del DXF. El formato legado `"section_01.dxf": [180, 230]` sigue funcionando, pero se replica para todas las superficies de falla solo por compatibilidad.

2. Las rutas de entrada ya no caen a carpetas internas por defecto. Todo DXF se lee desde la ruta entregada por el usuario. Si la ruta no existe o no es archivo, se lanza excepción.

3. Las rutas de salida reciben `output_root`. Si no se entrega, el backend usa `C:\Prismo` mediante `OUTPUT_DIR`, configurable también con la variable de entorno `PRISMO_OUTPUT_DIR`.

4. Se agregó inspección de columna previa a la discretización:

```python
from backend.services.service_calibration import inspect_column_before_discretization

preview = inspect_column_before_discretization(
    section_file=r"C:\ruta\section_01.dxf",
    materials=materials,
    x_position_map=x_position_map,
    f_target=25,
    section_code="section_01",
    failure_surface_code="failure_1",
    column_code="column_1",
)
```

El resultado incluye `materials_found_ordered`, con materiales ordenados por profundidad, espesores y propiedades asignadas, además de `column_input`, compatible con `execute_processing`.

5. La salida de generación mantiene compatibilidad con la discretización actual. Cada columna exportada conserva:

```python
{
    "layers": [...],
    "freatic": ...,
    "depth_failure_surface": ...
}
```

con metadatos adicionales no invasivos: `failure_surface` y `x_position`.
