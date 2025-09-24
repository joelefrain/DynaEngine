import numpy as np

from typing import Tuple
from babel import Locale
from babel.dates import format_date

from libs.config.config_variables import DECIMAL_CHAR


def round_decimal(value: float, decimals: int, decimal_char: str = DECIMAL_CHAR) -> str:
    """
    Rounds a float to a specified number of decimal places and replaces the decimal point with the specified character.

    Parameters
    ----------
    value : float
        The float value to round.
    decimals : int
        The number of decimal places.
    decimal_char : str
        The character to use as the decimal point ('.' or ',').

    Returns
    -------
    str
        The rounded value as a string with the specified decimal character.
    """
    rounded_value = round(value, decimals)
    formatted_value = f"{rounded_value:.{decimals}f}"
    return formatted_value.replace(".", decimal_char)


def round_lower(value):
    return int(value // 1)


def round_upper(value):
    return int(-(-value // 1))


def format_date_long(date, lang="es"):
    """Convert date to 'mmmm yyyy' format in the specified language."""
    locale = Locale(lang)
    return format_date(date, "MMMM yyyy", locale=locale).lower()


def format_date_short(date):
    """Convert date to 'dd-mm-yy' format."""
    return date.strftime("%d-%m-%y")


def get_percentile_value(data: list, percentile: float = 90.0) -> float:
    """
    Calculate the value at a specified percentile from a list of numbers.

    Parameters
    ----------
    data : list
        List of numeric values.
    percentile : float, optional
        Percentile to calculate (0-100), by default 90.0

    Returns
    -------
    float
        Value at the specified percentile.
    """
    data_arr = np.asarray(data)
    return float(np.nanpercentile(data_arr, percentile))


def get_limit(
    data: list, percentile: float = 90.0, scale: float = 1.5, abs_mode: bool = True
) -> float:
    """
    Calculate the limit based on a specified percentile.

    Parameters
    ----------
    data : list
        List of numeric values.
    percentile : float, optional
        Percentile to calculate (0-100), by default 90.0
    scale : float, optional
        Scale factor to apply to the percentile value, by default 1.5
    abs_mode : bool, optional
        If True, returns the absolute value of the limit, by default True.

    Returns
    -------
    float
        Limit value at the specified percentile.
    """

    value = get_percentile_value(data, percentile)
    limit = abs(value * scale) if abs_mode else value * scale

    return limit


def get_typical_range(
    data: list, percentile: float = 90.0, scale: float = 1.5
) -> float:
    """
    Calculate the typical range based on a specified percentile and scale.
    Parameters
    ----------
    data : list
        List of numeric values.
    percentile : float, optional
        Percentile to calculate (0-100), by default 90.0
    scale : float, optional
        Scale factor to apply to the percentile value, by default 1.5

    Returns
    -------
    Tuple[float, float]
        Upper and lower limits of the typical range.
    """

    upper_limit = get_limit(data, percentile, scale, abs_mode=False)
    if upper_limit < 0:
        upper_limit = get_limit(data, percentile, 1 / scale, abs_mode=False)
    else:
        upper_limit = get_limit(data, percentile, scale, abs_mode=True)
    upper_limit = round_upper(upper_limit)

    lower_limit = get_limit(data, 100 - percentile, 1 / scale, abs_mode=False)
    if lower_limit < 0:
        lower_limit = get_limit(data, 100 - percentile, scale, abs_mode=False)
    else:
        lower_limit = get_limit(data, 100 - percentile, 1 / scale, abs_mode=True)
    lower_limit = round_lower(lower_limit)

    return lower_limit, upper_limit


def get_symetric_range(
    data: list, percentile: float = 90.0, scale: float = 1.5
) -> Tuple[float, float]:
    """
    Calculate symmetric limits based on a specified percentile and scale.

    Parameters
    ----------
    data : list
        List of numeric values.
    percentile : float, optional
        Percentile to calculate (0-100), by default 90.0
    scale : float, optional
        Scale factor to apply to the percentile value, by default 1.5

    Returns
    -------
    Tuple[float, float]
        Lower and upper symmetric limits.
    """

    upper_limit = get_limit(data, percentile, scale, abs_mode=True)
    upper_limit = round_upper(upper_limit)
    lower_limit = -upper_limit

    return lower_limit, upper_limit


def get_iqr_limits(data: list, margin_factor: float = 1.5) -> Tuple[float, float]:
    """
    Calculate plot limits using the Interquartile Range (IQR) method.

    Parameters
    ----------
    data : list
        List of numeric values.
    margin_factor : float, optional
        Factor to multiply IQR for margin calculation, by default 1.5.

    Returns
    -------
    Tuple[float, float]
        Lower and upper limits (y_min, y_max).
    """
    data_arr = np.asarray(data)
    q1, q3 = np.nanquantile(data_arr, [0.25, 0.75])
    margin = (q3 - q1) * margin_factor
    return q1 - margin, q3 + margin


def calc_epsg_from_utm(utm_zone: int, northern_hemisphere: bool = True) -> int:
    """
    Calculate the EPSG code for a given UTM zone.

    Parameters
    ----------
    utm_zone : int
        UTM zone number (1-60).
    northern_hemisphere : bool, optional
        True if the zone is in the Northern Hemisphere, False if in the Southern Hemisphere, by default True.

    Returns
    -------
    int
        EPSG code for the specified UTM zone.
    """
    if not 1 <= utm_zone <= 60:
        raise ValueError(f"UTM zone must be between 1 and 60, got {utm_zone}.")

    return 32600 + utm_zone if northern_hemisphere else 32700 + utm_zone
