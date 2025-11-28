# This file contains configuration variables for the application.
# ---------------------------------------------------------------
from pathlib import Path


# Constants for formats
# ---------------------------------------------------------------
SEP_FORMAT = ";"

# Font for the report
DEFAULT_FONT = "Arial"

# Constants for number formats
DECIMAL_CHAR = ","
THOUSAND_CHAR = " "
DATE_FORMAT = "%d-%m-%y"

# Language settings
LANG_DEFAULT = "es"  # Default language for the application

# Defaults for the report
# ---------------------------------------------------------------
DOC_TITLE = "SIG-AND"
THEME_COLOR = "#0069AA"
THEME_COLOR_FONT = "white"

# Paths to data files
# ---------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent.parent

LOG_DIR = BASE_DIR / "logs"
STORAGE_DIR = BASE_DIR / "var"
ENV_FILE_PATH = BASE_DIR / "config" / ".env"

# Rutas a archivos de base de datos
# ---------------------------------------------------------------
SCHEMA_SQL_PATH = BASE_DIR / "data" / "database" / "schema.sql"
DATABASE_PATH = BASE_DIR / "data" / "database" / "prismo.db"
ACCEL_RECORD_STORE = BASE_DIR / "data" / "accel_records"
