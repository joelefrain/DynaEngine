import re
import json
import pickle

from datetime import datetime, timedelta

from .variables_helpers import make_serializable

from libs.config.config_variables import DEFAULT_SEP_CHARS, DATETIME_FORMATS_PATH


def to_sentence_format(text: str, mode: str = "lower") -> str:
    """
    Formatea un nombre de serie aplicando un tipo de conversión a la parte antes del paréntesis
    y conservando intacto el contenido entre paréntesis.

    Parámetros:
        text (str): El texto original.
        mode (str): Tipo de conversión aplicado a la parte antes del paréntesis. Opciones:
            - 'lower':        convierte todo a minúsculas (ej. "TURBIDEZ (NTU)" → "turbidez (NTU)")
            - 'sentence':     primera letra en minúscula, el resto igual (ej. "Presión (kPa)" → "presión (kPa)")
            - 'capitalize':   primera letra en mayúscula, el resto en minúsculas (ej. "Presión (kPa)" → "Presión (kPa)")
            - 'title':        tipo título (mayúscula inicial de cada palabra) (ej. "oxígeno disuelto (mg/L)" → "Oxígeno Disuelto (mg/L)")
            - 'original':     mantiene el texto tal como está (ej. "Presión (kPa)" → "Presión (kPa)")
            - 'decapitalize': convierte solo la primera letra a minúscula, dejando el resto intacto.

    Retorna:
        str: El texto formateado.

    Ejemplos:
        >>> to_sentence_format("Presión (kPa)", mode="lower")
        'presión (kPa)'

        >>> to_sentence_format("TURBIDEZ (NTU)", mode="sentence")
        'turbidez (NTU)'

        >>> to_sentence_format("oxígeno disuelto (mg/L)", mode="capitalize")
        'Oxígeno disuelto (mg/L)'

        >>> to_sentence_format("oxígeno disuelto (mg/L)", mode="title")
        'Oxígeno Disuelto (mg/L)'

        >>> to_sentence_format("pH in-situ (mg/L)", mode="original")
        'pH in-situ (mg/L)'

        >>> to_sentence_format("PH in-situ (mg/L)", mode="decapitalize")
        'pH in-situ (mg/L)'"""
    text = text.strip()

    if "(" in text:
        main = text.split("(")[0].strip()
        suffix = text[text.find("(") :]
    else:
        main = text
        suffix = ""

    if mode == "lower":
        main = main.lower()
    elif mode == "sentence":
        main = main.lower()
    elif mode == "capitalize":
        main = main.capitalize()
    elif mode == "title":
        main = main.title()
    elif mode == "original":
        pass
    elif mode == "decapitalize":
        main = main[0].lower() + main[1:] if main else ""
    else:
        raise ValueError(f"Modo de conversión no válido: {mode}")

    return f"{main} {suffix}".strip()


def clean_str(s, allowable_chars=r"[^\w\s:/\-.]", remove_space=False):
    """Devuelve un string según un patrón definido"""
    cleaned = re.sub(allowable_chars, "", s)
    if remove_space:
        cleaned = cleaned.replace(" ", "")
    return cleaned.strip()


def parse_number(text):
    """
    Intenta convertir un texto desordenado a un número (int o float).
    Maneja diferentes convenciones de separación decimal/millar.
    """
    if not isinstance(text, str):
        text = str(text)

    # Eliminar caracteres que no sean números, punto, coma o signo
    cleaned = clean_str(text, allowable_chars=r"[^\d,.\-+]", remove_space=True)

    # Caso 1: Formato europeo (coma decimal, punto millar)
    if cleaned.count(",") == 1 and cleaned.count(".") > 0:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    # Caso 2: Formato americano (punto decimal, coma millar)
    elif cleaned.count(".") == 1 and cleaned.count(",") > 0:
        cleaned = cleaned.replace(",", "")
    # Caso 3: Solo una coma -> puede ser decimal
    elif cleaned.count(",") == 1 and cleaned.count(".") == 0:
        cleaned = cleaned.replace(",", ".")
    # Caso 4: Solo puntos -> nada que hacer
    else:
        cleaned = cleaned

    try:
        number = float(cleaned)
        if number.is_integer():
            return int(number)
        return number
    except ValueError:
        raise ValueError(
            f"No se pudo convertir el texto a número: '{text}' (limpio: '{cleaned}')"
        )


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def parse_excel_date(value: str) -> datetime:
    """Convierte un número de fecha Excel a datetime, validando rango razonable (1970 a hoy)."""
    try:
        numeric_value = float(value)
    except ValueError:
        raise ValueError(f"No es un valor numérico de Excel válido: '{value}'")

    base_date = datetime(1899, 12, 30)
    result = base_date + timedelta(days=numeric_value)

    if not (datetime(1970, 1, 1) <= result <= datetime.now()):
        raise ValueError(f"Fecha Excel fuera de rango razonable: {result}")

    return result


def try_parse_with_specific_fmt(text, formats, tried_formats):
    """
    Intenta convertir 'text' usando una lista de formatos strptime.
    Devuelve datetime si tiene éxito, None si falla.
    """
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            tried_formats.append(fmt)
    return None


def try_parse_excel_date(text):
    """Intenta interpretar 'text' como fecha Excel si es numérico."""
    if is_number(text):
        try:
            return parse_excel_date(text)
        except Exception:
            return None
    return None


def handle_fmt_priority(text, priorities, number_formats, tried_formats):
    """
    Aplica los formatos de prioridad en orden:
      - excel
      - number
      - strptime directo
    """
    for fmt in priorities:
        if fmt == "excel":
            result = try_parse_excel_date(text)
            if result:
                return result

        elif fmt == "number":
            result = try_parse_with_specific_fmt(text, number_formats, tried_formats)
            if result:
                return result

        else:  # asume que es un formato strptime explícito
            result = try_parse_with_specific_fmt(text, [fmt], tried_formats)
            if result:
                return result
    return None


def parse_datetime(text, format_priority=None):
    """
    Intenta convertir un texto a datetime.

    format_priority puede contener:
        - "excel": fuerza interpretación como fecha Excel
        - "number": intenta formatos numéricos sin separadores
        - formatos strptime tradicionales ("%d-%m-%Y", etc.)

    Devuelve:
        datetime.datetime
    """
    if not isinstance(text, str):
        text = str(text)

    cleaned = clean_str(text, allowable_chars=r"[^\w\s:/\-.,]", remove_space=False)

    # Formatos numéricos sin separadores
    number_formats = ["%Y%m%d", "%d%m%Y", "%y%m%d"]

    # Formatos convencionales
    datetime_formats = read_json(DATETIME_FORMATS_PATH)
    default_formats = list(datetime_formats.keys())

    # Normalizar prioridades en lista
    priorities = (
        format_priority
        if isinstance(format_priority, list)
        else [format_priority]
        if format_priority
        else []
    )

    tried_formats = []

    # 1. Intentar con prioridades definidas
    result = handle_fmt_priority(cleaned, priorities, number_formats, tried_formats)
    if result:
        return result

    # 2. Excel implícito
    result = try_parse_excel_date(cleaned)
    if result:
        return result

    # 3. Formatos numéricos
    result = try_parse_with_specific_fmt(cleaned, number_formats, tried_formats)
    if result:
        return result

    # 4. Formatos convencionales
    result = try_parse_with_specific_fmt(cleaned, default_formats, tried_formats)
    if result:
        return result

    # Si nada funcionó
    raise ValueError(
        f"No se pudo parsear '{text}' como fecha. Formatos probados: {tried_formats}"
    )


def detect_separator(lines, priority_separators=DEFAULT_SEP_CHARS):
    """
    Detecta automáticamente el separador más probable en las líneas de texto.

    Parameters
    ----------
    lines : list of str
        Líneas de texto a analizar.
    priority_separators : list or str, optional
        Lista de separadores a probar. Por defecto: [",", ";", "\t", "|"]

    Returns
    -------
    str
        Separador más probable detectado.
    """

    # Filtrar líneas que parezcan contener datos
    data_lines = [
        line for line in lines if line.strip() and not line.strip().startswith("#")
    ]

    if not data_lines:
        return priority_separators[0]  # Retorna el separador por defecto

    separator_counts = {}

    for sep in priority_separators:
        count = sum(line.count(sep) for line in data_lines[:10])  # primeras 10 líneas
        separator_counts[sep] = count

    # Retornar el separador con mayor ocurrencia
    best_separator = max(separator_counts, key=separator_counts.get)

    return best_separator


def read_lines(filepath, encoding="utf-8", as_string=True):
    with open(file=filepath, mode="r", encoding=encoding) as file:
        return file.read() if as_string else file.readlines()


def read_json(filepath, encoding="utf-8"):
    with open(file=filepath, mode="r", encoding=encoding) as file:
        return json.load(file)


def read_pickle(filepath):
    with filepath.open("rb") as file:
        return pickle.load(file)


def write_lines(list_to_write, filepath, encoding="utf-8"):
    with open(file=filepath, mode="w", encoding=encoding) as f:
        for element in list_to_write:
            f.write(f"{element}\n")


def write_json(dict_to_write, filepath, encoding="utf-8"):
    serializable_dict = make_serializable(dict_to_write)
    with (filepath).open("w", encoding=encoding) as file:
        json.dump(serializable_dict, file, ensure_ascii=False, indent=4)


def write_pickle(obj_to_write, filepath):
    with filepath.open("wb") as file:
        pickle.dump(obj_to_write, file)
