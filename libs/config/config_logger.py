import time
import logging
import inspect
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler

from .config_variables import LOG_DIR

from libs.helpers.storage_helpers import validate_folder


def _resolve_module_name(module_name=None):
    """Obtiene el nombre del módulo o archivo llamador."""
    if module_name:
        return module_name

    frame = inspect.stack()[2]  # [2] para saltar función auxiliar
    module = inspect.getmodule(frame[0])
    if module and module.__name__ != "__main__":
        return module.__name__
    return Path(frame.filename).stem


def _format_time(seconds: float) -> str:
    """Convierte segundos a un string legible."""
    if seconds < 60:
        return f"{seconds:.2f} seconds"
    elif seconds < 3600:
        return f"{seconds / 60:.2f} minutes"
    elif seconds < 86400:
        return f"{seconds / 3600:.2f} hours"
    return f"{seconds / 86400:.2f} days"


def get_logger(module_name=None):
    module_name = _resolve_module_name(module_name)
    logger = logging.getLogger(module_name)
    logger.setLevel(logging.INFO)

    today_date = datetime.now().strftime("%Y-%m-%d")
    log_dir = LOG_DIR / today_date
    validate_folder(log_dir, create_if_missing=True)
    log_file = log_dir / f"{module_name}.log"

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


def log_execution_time(func=None, *, module=None):
    if func is None:
        return lambda f: log_execution_time(f, module=module)

    logger = get_logger(_resolve_module_name(module))

    def wrapper(*args, **kwargs):
        start_time = time.time()
        func_name = (
            f"{args[0].__class__.__name__}.{func.__name__}"
            if args and hasattr(args[0], "__class__")
            else func.__name__
        )

        logger.info(f"Starting execution of {func_name}")
        result = func(*args, **kwargs)
        elapsed_time = _format_time(time.time() - start_time)
        logger.info(f"Finished execution of {func_name} in {elapsed_time}")

        return result

    return wrapper
