from pathlib import Path


def validate_folder(path: str | Path, create_if_missing: bool = False) -> Path:
    """
    Valida si una carpeta existe. Opcionalmente, la crea si no existe.

    Parámetros:
    ----------
    path : str | Path
        Ruta a validar.
    create_if_missing : bool
        Si es True, crea la carpeta si no existe.

    Retorna:
    -------
    Path
        Objeto Path de la ruta validada o creada.

    Lanza:
    -----
    FileNotFoundError si la ruta no existe y `create_if_missing` es False.
    """
    path = Path(path)

    if path.is_dir():
        return path

    if create_if_missing:
        path.mkdir(parents=True, exist_ok=True)
        return path
    else:
        raise FileNotFoundError(f"La ruta no existe: {path}")
