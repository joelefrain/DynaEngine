import numpy as np
import pandas as pd

from pathlib import Path
from dataclasses import dataclass

from libs.config.config_variables import SEP_FORMAT


def read_df_on_time_from_csv(
    path: Path,
    set_index: bool = False,
    auto_convert: bool = False,
    num_decimals: int = 3,
) -> pd.DataFrame:
    """Lee un DataFrame desde un archivo CSV y configura la columna de tiempo."""

    # Leer CSV desde una ruta
    df = read_df_from_csv(path)

    # Convertir la columna time a datetime preservando milisegundos
    df = config_time_df(df, set_index)

    # Conversión automática de tipos de datos
    if auto_convert:
        # Convertir columnas
        df = df.convert_dtypes()

        # Reemplazar pd.NA con np.nan para evitar errores en gráficos
        df = df.apply(
            lambda col: col.astype(float) if col.dtype.name == "Float64" else col
        )

        # Redondear columnas de tipo float a num_decimals
        float_cols = df.select_dtypes(include=["floating"]).columns
        df[float_cols] = df[float_cols].round(num_decimals)

    return df


def read_df_from_csv(path: Path) -> pd.DataFrame:
    # Leer CSV desde una ruta
    df = pd.read_csv(path, sep=SEP_FORMAT)
    return df


def config_time_df(
    df: pd.DataFrame, set_index: bool = True, format_time: str = None
) -> pd.DataFrame:
    # Convertir la columna time a datetime y establecer como índice
    df["time"] = pd.to_datetime(df["time"], errors="raise", format=format_time)
    if set_index:
        df = df.set_index("time")
    return df


def save_df_to_csv(df: pd.DataFrame, file_path: str) -> None:
    """Guarda un DataFrame en un archivo CSV.

    Args:
        df: DataFrame a guardar
        file_path: Ruta donde guardar el archivo CSV
    """
    df.to_csv(file_path, index=False, sep=SEP_FORMAT)


def append_params_as_column(df, **kwargs):
    """Asigna parámetros adicionales al DataFrame.

    Args:
        df: DataFrame al que se le asignarán los parámetros
        **kwargs: Parámetros a asignar como columnas en el DataFrame

    Returns:
        pd.DataFrame: DataFrame con los parámetros asignados
    """
    for key, value in kwargs.items():
        df[key] = value
    return df


def append_params_as_row(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """Agrega un nuevo registro al DataFrame con valores de kwargs.

    Si alguna clave no existe como columna, se crea y se rellena con NaN
    en las filas existentes. Las columnas que existen pero no están en kwargs
    se asignan como NaN en la nueva fila.

    Args:
        df: DataFrame existente
        **kwargs: Valores del nuevo registro

    Returns:
        pd.DataFrame con el nuevo registro agregado
    """
    # Asegurarse de que todas las columnas de kwargs estén en el DataFrame
    for col in kwargs:
        if col not in df.columns:
            df[col] = np.nan  # Agrega la columna con NaN para todas las filas

    # Crear una nueva fila con las mismas columnas que el DataFrame
    new_row = {col: kwargs.get(col, np.nan) for col in df.columns}

    # Agregar la fila al DataFrame
    return pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)


@dataclass
class DfMerger:
    df1: pd.DataFrame
    df2: pd.DataFrame

    def merge(self, match_columns=["time"], match_type="all") -> pd.DataFrame:
        match_columns = (
            [match_columns] if isinstance(match_columns, str) else match_columns
        )
        common_cols = [
            col
            for col in match_columns
            if col in self.df1.columns and col in self.df2.columns
        ]

        if not common_cols:
            raise ValueError(
                "No hay columnas comunes entre df1 y df2 en match_columns."
            )

        if match_type == "all":
            return self._merge_all(common_cols)
        elif match_type == "any":
            return self._merge_any(common_cols)
        else:
            raise ValueError("match_type debe ser 'all' o 'any'.")

    def _merge_all(self, keys):
        merged = pd.merge(
            self.df1, self.df2, on=keys, how="outer", suffixes=("", "_df2")
        )
        return self._resolve_conflicts(merged)

    def _merge_any(self, keys):
        frames = []
        for key in keys:
            m = pd.merge(self.df1, self.df2, on=key, how="outer", suffixes=("", "_df2"))
            frames.append(self._resolve_conflicts(m))
        result = pd.concat(frames, ignore_index=True)
        return result.drop_duplicates()

    def _resolve_conflicts(self, df):
        for col in self.df2.columns:
            if col not in self.df1.columns:
                continue
            alt_col = f"{col}_df2"
            if alt_col in df.columns:
                df[col] = df[col].combine_first(df.pop(alt_col))
        # Agregar columnas únicas de df2 que no están en df1
        for col in self.df2.columns:
            if col not in df.columns:
                df[col] = self.df2[col]
        return df
