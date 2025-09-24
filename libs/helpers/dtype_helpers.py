import pandas as pd

from typing import Any, Callable
from abc import ABC

from .text_helpers import parse_datetime, parse_number

from libs.config.config_logger import get_logger

logger = get_logger()


class TypeConverter(ABC):
    """Conversor genérico de valores individuales."""

    def __init__(self, format_priority: dict[str, Any] = None):
        self.format_priority = format_priority or {}
        self._converters: dict[str, Callable[[Any], Any]] = {
            "numeric": self._to_numeric,
            "datetime": self._to_datetime,
            "time": self._to_time,
            "string": self._to_string,
            "float": self._to_float,
            "int": self._to_int,
            "bool": self._to_bool,
        }

    def convert(self, value: Any, data_type: str) -> Any:
        try:
            return self._converters.get(data_type, self._identity)(value)
        except Exception:
            return None

    # ---- Métodos internos de conversión ----
    def _to_numeric(self, value: Any) -> Any:
        return float(parse_number(value))

    def _to_datetime(self, value: Any) -> Any:
        fmt = self.format_priority.get("datetime", [])
        return parse_datetime(value, fmt)

    def _to_time(self, value: Any) -> Any:
        fmt = self.format_priority.get("time", [])
        dt = parse_datetime(value, fmt)
        return dt.time() if pd.notnull(dt) else None

    def _to_string(self, value: Any) -> str:
        return str(value)

    def _to_float(self, value: Any) -> float:
        return float(value)

    def _to_int(self, value: Any) -> int:
        return int(float(value))

    def _to_bool(self, value: Any) -> bool | None:
        if str(value).strip().lower() in ("true", "1"):
            return True
        elif str(value).strip().lower() in ("false", "0"):
            return False
        return None

    def _identity(self, value: Any) -> Any:
        return value


class DfTypeConverter(TypeConverter):
    """Conversor aplicado a DataFrames, con políticas de fallback."""

    def _apply_and_handle_invalids(
        self,
        df: pd.DataFrame,
        col: str,
        dtype: str,
        fallback: Any,
        drop_invalid: bool = False,
    ) -> pd.DataFrame:
        df[col] = df[col].apply(lambda x: self.convert(x, dtype))

        if df[col].isna().any():
            invalid = df.loc[df[col].isna(), ["time", col]]
            if drop_invalid:
                logger.warning(
                    f"[{col}] Se eliminaron {len(invalid)} registros inválidos:\n{invalid}"
                )
                df = df.drop(invalid.index)
            else:
                logger.warning(
                    f"[{col}] {len(invalid)} registros inválidos, completados con {fallback}."
                )
                df[col] = df[col].fillna(fallback)

        return df

    def to_datetime(self, df: pd.DataFrame, col: str) -> pd.DataFrame:
        return self._apply_and_handle_invalids(
            df, col, "datetime", None, drop_invalid=True
        )

    def to_numeric(self, df: pd.DataFrame, col: str) -> pd.DataFrame:
        return self._apply_and_handle_invalids(df, col, "numeric", 0)

    def to_boolean(self, df: pd.DataFrame, col: str) -> pd.DataFrame:
        return self._apply_and_handle_invalids(df, col, "bool", False)
