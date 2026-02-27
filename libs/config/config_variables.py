# Este archivo contiene variables de configuración para la aplicación.
# ---------------------------------------------------------------
import os
from pathlib import Path


# Formatos de visualización
# ---------------------------------------------------------------
SEP_NAME_FORMAT = "_"
SEP_TABLE_FORMAT = ";"
VIZ_TABLE_FORMAT = "pretty"

# Fuente predeterminada para reportes
DEFAULT_FONT = "Arial"

# Formatos numéricos
DECIMAL_CHAR = ","
THOUSAND_CHAR = " "
DATE_FORMAT = "%d-%m-%y"

# Configuración de idioma
LANG_DEFAULT = "es"  # Default language for the application

# Formatos de reporte
# ---------------------------------------------------------------
DOC_TITLE = "SIG-AND"
THEME_COLOR = "#0069AA"
THEME_COLOR_FONT = "white"

# Rutas a carpetas destacadas
# ---------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent.parent

LOG_DIR = BASE_DIR / "logs"
STORAGE_DIR = BASE_DIR / "var"
TEMP_DATA_DIR = STORAGE_DIR / "temp"
ENV_FILE_PATH = BASE_DIR / "config" / ".env"

# Rutas a archivos de base de datos
# ---------------------------------------------------------------
SCHEMA_SQL_PATH = BASE_DIR / "data" / "database" / "schema.sql"
DATABASE_PATH = BASE_DIR / "data" / "database" / "prismo.db"
ACCEL_RECORD_STORE = BASE_DIR / "data" / "accel_records"

# Rutas a archivos destacados
# ---------------------------------------------------------------
LOGO_SVG = BASE_DIR / "data" / "logo" / "logo_main_109x50.svg"
LOGO_PDF = BASE_DIR / "data" / "logo" / "logo_main_109x50.pdf"
DATA_CONFIG = BASE_DIR / "data" / "config"
DXF_COLORS_PATH = BASE_DIR / "data" / "styles" / "dxf_colors.json"
DXF_LINETYPES_PATH = BASE_DIR / "data" / "styles" / "dxf_linetypes.json"
DATETIME_FORMATS_PATH = BASE_DIR / "data" / "styles" / "datetime_formats.json"

# Rutas a carpetas destacadas de módulos del sistema
# ---------------------------------------------------------------
REPORT_CONFIG_DIR = BASE_DIR / "modules" / "reporter" / "data" / "reports"
CHART_CONFIG_DIR = BASE_DIR / "modules" / "reporter" / "data" / "charts"
NOTE_CONFIG_DIR = BASE_DIR / "modules" / "reporter" / "data" / "notes"
TABLE_CONFIG_DIR = BASE_DIR / "modules" / "reporter" / "data" / "tables"

CATALOG_CSV_DIR = BASE_DIR / "data" / "catalog"

# Caracteres permitidos en archivos para ser parseados
# ---------------------------------------------------------------
DEFAULT_SEP_CHARS = (",", ";", "\t", "|")
DEFAULT_CHARS_IN_TEXTS = r"[^\w\s:/\-.+]"

# Máximo número de workers
# ---------------------------------------------------------------
MAX_WORKERS = min(40, (os.cpu_count() or 1) * 5)

# Límite de datos
MAX_TOTAL_SIZE = 2.5 * 1024**3  # 2.5 GB
MAX_FILE_SIZE = 800 * 1024**2  # 800 MB
BATCH_SIZE_SQL_VAR = 5000
TIMEOUT_API_REQUEST = 30

# Estilos para matplotlib
# ---------------------------------------------------------------
UNIQUE_MARKERS = ("o", "s", "D", "v", "^", "<", ">", "p", "h")

# Extensiones permitidas en parsers
# ---------------------------------------------------------------
TEXT_EXTENSIONS = [".csv", ".txt", ".dat", ".gkn"]
EXCEL_EXTENSIONS = [".xlsx", ".xls", ".xlsm", ".xlsb", ".odf", ".ods", ".odt"]

# Formatos de parseo de fechas
# ---------------------------------------------------------------
TIMESTAMP_ALLOWABLE_DECIMALS = 6  # hasta microsegundos
DATETIME_ALLOWABLE_PATTERN = r"[^\w\s:/\-.,]"
TIMESTAMP_ALLOWABLE_PATTERN = r"(\d{2}:\d{2}:\d{2})\.(\d{7,})"

# Periodos de retorno para estudio de peligro sísmico
# ---------------------------------------------------------------
N_PERIOD_RETURN = 50  # años
RETURN_PRD_LST = [100, 475, 1000, 2475, 5000, 10000]  # años

# Constantes
# ---------------------------------------------------------------
UNIT_GROUND_MOTION = "g"
STRAIN_RANGE_PCT = [0.0001, 0.0003, 0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 0.7, 1, 3, 7, 10]