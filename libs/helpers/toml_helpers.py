import os
import tomli

from typing import Dict, Any

from libs.config.config_variables import INSTRUMENTS_TOML_PATHS


def load_toml(toml_name: str, data_dir: str = None) -> Dict[str, Any]:
    """
    Load a TOML configuration file from a specific directory.

    Args:
        data_dir (str): Base directory path where TOML files are stored
        toml_name (str): Name of the TOML file (with or without extension)

    Returns:
        Dict[str, Any]: Parsed TOML content as a dictionary

    Raises:
        FileNotFoundError: If the TOML file doesn't exist
        tomli.TOMLDecodeError: If the TOML file is invalid
    """
    # Build full path
    if data_dir is None:
        toml_path = toml_name
    else:
        # Ensure toml_name has .toml extension
        if not toml_name.endswith(".toml"):
            toml_name += ".toml"
        toml_path = os.path.join(data_dir, toml_name)

    try:
        with open(toml_path, "rb") as f:
            return tomli.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found: {toml_path}")
    except tomli.TOMLDecodeError as e:
        raise tomli.TOMLDecodeError(f"Invalid TOML file {toml_path}: {str(e)}")


def processor_config_loader(instrument_type: str) -> Dict:
    """Carga y valida la configuración desde archivo TOML"""

    if instrument_type not in INSTRUMENTS_TOML_PATHS:
        raise ValueError(f"Tipo de instrumento desconocido: {instrument_type}")

    instrument_type_toml_path = INSTRUMENTS_TOML_PATHS[instrument_type]
    config = load_toml(instrument_type_toml_path)

    # Validar estructura básica del config
    required_sections = ["schema", "calculations", "analysis_config"]
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Sección requerida '{section}' no encontrada en config")

    return config
