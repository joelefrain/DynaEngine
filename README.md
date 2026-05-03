# DynaEngine

DynaEngine queda reorganizado como un paquete de calculo local para una aplicacion de escritorio. Las entradas publicas no usan rutas globales y no escriben archivos salvo que se entregue una ruta explicita.

## Capacidades

- Curvas dinamicas por autor: Darendeli, Menq, Rollins, Ishibashi & Zhang, Wang & Stokoe, Rojas, Seed & Idriss y curvas definidas por el usuario.
- Calibracion GQH y MRDF desde curvas dinamicas.
- Lectura DXF de secciones, columnas no discretizadas y discretizacion por frecuencia objetivo.

## Estructura

- `dynaengine/`: nucleo estable que debe consumir el frontend.
- `dynaengine/data/`: catalogo de modelos y curvas discretas requeridas por los autores.
- `examples/`: scripts ejecutables y pequenos.
- `notebooks/`: notebooks limpios que ejecutan el nucleo nuevo.

## Uso rapido

```powershell
python main.py curves
python main.py calibration
python main.py column
python main.py dxf
```

## Regla de guardado

Las funciones devuelven objetos Python o `DataFrame`. Para guardar resultados se debe pasar una ruta explicita:

```python
from dynaengine import export_dataframe

export_dataframe(frame, "salidas/columna.csv")
```

## Materiales

No hay valores geotecnicos predefinidos. Cada material debe traer nombre, peso unitario, perfil Vs, resistencia al corte y modelo dinamico completo. Si el DXF genera un `Estrato no identificado`, el frontend puede asociarlo a un material existente o crear un material nuevo antes de discretizar/calibrar.
