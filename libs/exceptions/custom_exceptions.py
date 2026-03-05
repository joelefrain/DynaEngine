

# ERRORES EN LA FUNCION DE COSTO

class ModelConfigurationError(Exception):
    """Error en configuración del modelo"""
    pass


class InvalidCurveError(Exception):
    """Error en curvas G/Gmax"""
    pass


class NumericalStabilityError(Exception):
    """Error numérico (división por cero, NaN, etc.)"""
    pass