from abc import ABC, abstractmethod


class SoilParameters(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def validate(self):
        """Validaciones específicas del modelo"""
        pass


class DarendeliParameters_2001(SoilParameters):
    def __str__(self):
        return f"DarendeliParameters2001(IP={self.IP}, OCR={self.OCR})"

    def __init__(
        self,
        IP: float,
        OCR: float,
        k0: float,
        frequency: float,
        N: float,
    ):

        self.IP = IP
        self.OCR = OCR
        self.k0 = k0
        self.frequency = frequency
        self.N = N

        self.validate()

    def validate(self):

        if not (0 <= self.IP <= 100):
            raise ValueError("IP fuera de rango")

        if self.OCR < 1:
            raise ValueError("OCR debe ser ≥ 1")

        if self.frequency <= 0:
            raise ValueError("frequency debe ser positiva")

        if self.N <= 0:
            raise ValueError("N debe ser positivo")


class MenqParameters_2003(SoilParameters):
    def __str__(self):
        return f"MenqParameters2003(Cu={self.Cu}, D50={self.D50}, k0={self.k0}, N={self.N})"

    def __init__(
        self,
        Cu: float,
        D50: float,
        k0: float,
        N: float,
    ):

        self.Cu = Cu
        self.D50 = D50
        self.k0 = k0
        self.N = N

        self.validate()

    def validate(self):
        params = {
            "Cu": self.Cu,
            "D50": self.D50,
            "k0": self.k0,
            "N": self.N,
        }

        for name, value in params.items():
            if value <= 0:
                raise ValueError(f"{name} debe ser mayor a 0")


class RollinsParameters_2020(SoilParameters):
    def __str__(self):
        return f"RollinsParameters2020(Cu={self.Cu}, k0={self.k0})"

    def __init__(
        self,
        Cu,
        k0,
    ):
        self.Cu = Cu
        self.k0 = k0

        self.validate()

    def validate(self):

        if not (1.33 <= self.Cu <= 83.3):
            print("El valor de Cu esta fuera del rango ensayado por Rollins (2020)")
        if self.Cu <= 0:
            raise ValueError("Cu debe ser mayor a 0")
        if self.k0 <= 0:
            raise ValueError("k0 debe ser mayor a 0")


class IshibashiParameters_1993(SoilParameters):
    def __str__(self):
        return f"IshibashiParameters1993(IP={self.IP}, k0={self.k0})"

    def __init__(self, IP, k0):
        self.IP = IP
        self.k0 = k0

        self.validate()

    def validate(self):
        if self.IP <= 0:
            raise ValueError("Cu debe ser mayor a 0")


class WangStokoeParameters_2021(SoilParameters):
    REQUIRED_PARAMS = {
        "Clean sand and gravel group": ["e", "Cu", "CF", "D50", "wc"],
        "Nonplastic silty sand group": ["e", "CF"],
        "Clayey soil group": ["e", "CF", "OCR", "IP"],
    }

    def __str__(self):
        return f"WangStokoeParameters2021(soil_group={self.soil_group}, k0={self.k0})"

    def __init__(
        self,
        soil_group: str,
        e: float = None,
        D50: float = None,
        Cu: float = None,
        CF: float = None,
        IP: float = None,
        OCR: float = None,
        wc: float = None,
        k0: float = None,
    ):
        self.soil_group = soil_group

        self.e = e
        self.D50 = D50
        self.Cu = Cu
        self.OCR = OCR
        self.k0 = k0
        self.CF = CF / 100 if CF is not None else None
        self.IP = IP / 100 if IP is not None else None
        self.wc = wc / 100 if wc is not None else None

        self.validate()

    def validate(self):

        if self.soil_group not in self.REQUIRED_PARAMS:
            raise ValueError("soil_group no válido")

        required = self.REQUIRED_PARAMS[self.soil_group]

        for param in required:
            value = getattr(self, param)

            if value is None:
                raise ValueError(f"{param} es requerido para {self.soil_group}")

            if value <= 0:
                raise ValueError(f"{param} debe ser mayor a 0")


class RojasParameters_2019(SoilParameters):
    def __str__(self):
        return f"RojasParameters2019(k0={self.k0})"

    def __init__(
        self,
        k0,
    ):
        self.k0 = k0

    def validate(self):
        if self.k0 < 0:
            return


class SeedIdrissParameters_1970(SoilParameters):
    def __str__(self):
        return f"SeedIdrissParameters1970(band={self.band})"

    def __init__(self, band):
        self.band = band

    def validate(self):
        pass


class UserDefinedParameters(SoilParameters):
    def __str__(self):
        return f"UserDefinedParameters(k0={self.k0})"

    def __init__(self, k0):
        self.k0 = k0

        self.validate()

    def validate(self):
        if self.k0 <= 0:
            raise ValueError("k0 debe ser mayor a 0")
