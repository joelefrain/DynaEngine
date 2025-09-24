import json

import numpy as np
import pandas as pd

from typing import Any
from datetime import datetime, date


def flatten(nested_list):
    flat_list = []
    for item in nested_list:
        if isinstance(item, list):
            flat_list.extend(flatten(item))  # Desciende un nivel
        else:
            flat_list.append(item)  # Elemento final
    return flat_list


def get_field_from_dict(fields: str | list[str], dictionary: dict):
    """
    Verifica si una clave (o ruta de claves anidadas) está definida en un diccionario,
    e informa en qué punto exacto ocurre un fallo si lo hay.

    Parameters
    ----------
    fields : str | list[str]
        Clave o lista de claves que representan un acceso anidado al diccionario.
    dictionary : dict
        Diccionario sobre el cual se realiza la validación.

    Returns
    -------
    value
        Valor extraído del diccionario si se encuentra correctamente.

    Raises
    ------
    ValueError
        Si alguna de las claves no está definida en el diccionario.
    """
    if isinstance(fields, str):
        fields = [fields]

    value = dictionary
    path_traversed = []

    for key in fields:
        path_traversed.append(key)
        if not isinstance(value, dict):
            raise ValueError(
                f"Esperado un diccionario en la ruta {' -> '.join(path_traversed[:-1])}, "
                f"pero se encontró {type(value).__name__}."
            )
        if key not in value:
            raise ValueError(
                f"Clave '{key}' no definida en la ruta {' -> '.join(path_traversed[:-1])} "
                f"dentro del diccionario."
            )
        value = value[key]

    if value is None:
        raise ValueError(
            f"Valor en la ruta {' -> '.join(path_traversed)} está definido como None."
        )

    return value


def make_serializable(obj: Any):
    if isinstance(obj, (datetime, date, pd.Timestamp, np.datetime64)):
        return str(obj)
    elif isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple, set)):
        return [make_serializable(v) for v in obj]
    try:
        json.dumps(obj)
        return obj
    except (TypeError, OverflowError):
        return str(obj)
