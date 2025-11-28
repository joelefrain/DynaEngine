import time
import sqlite3

from libs.helpers.text_helpers import read_lines
from libs.helpers.storage_helpers import validate_file, validate_folder

from libs.config.config_variables import (
    DATABASE_PATH,
    SCHEMA_SQL_PATH,
    STORAGE_DIR,
)

from libs.config.config_logger import get_logger

logger = get_logger()

# Configuración de rutas base usando Path
LOGO_PATH = STORAGE_DIR / "logos"
DOCUMENTATION_PATH = STORAGE_DIR / "documentation"
CONFIG_PATH = STORAGE_DIR / "config"
GEOMETRIES_PATH = STORAGE_DIR / "geometries"
OUTPUTS_PATH = STORAGE_DIR / "outputs"
RAW_DATA_PATH = STORAGE_DIR / "raw_data"
TEMP_PATH = STORAGE_DIR / "temp"


def create_directories():
    """
    Crea los directorios necesarios para la aplicación.
    """
    logger.info("Creando directorios necesarios...")
    # Crear directorios base
    for path in [
        LOGO_PATH,
        DOCUMENTATION_PATH,
        CONFIG_PATH,
        GEOMETRIES_PATH,
        OUTPUTS_PATH,
        RAW_DATA_PATH,
        TEMP_PATH,
    ]:
        validate_folder(path, create_if_missing=True)
        logger.info(f"Directorio creado: {path}")
    logger.info("Todos los directorios necesarios han sido creados.")


def create_database():
    database_path = DATABASE_PATH
    schema_sql_path = SCHEMA_SQL_PATH

    logger.info(f"Inicio de creación de base de datos: {database_path}")
    start_time = time.time()

    try:
        schema_sql_path = validate_file(schema_sql_path, create_parents=False)
    except FileNotFoundError as e:
        logger.error(f"Archivo de esquema no encontrado: {schema_sql_path} | {e}")
        raise
    except FileExistsError as e:
        logger.error(f"La ruta existe pero no es un archivo: {schema_sql_path} | {e}")
        raise

    # Leer el esquema SQL
    try:
        schema_sql = read_lines(schema_sql_path, as_string=True)
        logger.info(f"Esquema SQL leído correctamente desde: {schema_sql_path}")
    except Exception as e:
        logger.error(f"Error al leer el archivo de esquema: {e}")
        raise

    # Crear nueva base de datos y ejecutar esquema
    try:
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()
        cursor.executescript(schema_sql)
        conn.commit()
        logger.info("Esquema SQL ejecutado correctamente.")
    except Exception as e:
        logger.error(f"Error al ejecutar el esquema SQL: {e}")
        raise
    finally:
        conn.close()

    # Mostrar todas las tablas creadas
    try:
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        conn.close()

        logger.info(f"Base de datos creada exitosamente: {database_path}")
        logger.info(f"Se crearon {len(tables)} tabla(s):")
        for table in tables:
            logger.info(f"  - {table[0]}")

    except Exception as e:
        logger.warning(f"No se pudieron listar las tablas creadas: {e}")

    elapsed = time.time() - start_time
    logger.info(f"Proceso completado en {elapsed:.2f} segundos.")
