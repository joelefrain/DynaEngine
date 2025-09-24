import shutil

from pathlib import Path

from libs.config.config_variables import MAX_FILE_SIZE, MAX_TOTAL_SIZE


def copy_folder_content(source_path, destination_path):
    """
    Copia el contenido de source_path a destination_path respetando límites de tamaño.
    No interrumpe el proceso: devuelve un reporte con archivos copiados, omitidos y errores.

    Retorna:
        dict: {
            "copied": [Path, ...],
            "skipped": [(Path, str), ...],  # (ruta, motivo)
            "errors": [(Path, str), ...]    # (ruta, error)
        }
    """

    source = Path(source_path)
    destination = Path(destination_path)
    destination.mkdir(parents=True, exist_ok=True)

    total_copied = 0
    report = {"copied": [], "skipped": [], "errors": []}

    for item in source.iterdir():
        if total_copied >= MAX_TOTAL_SIZE:
            report["skipped"].append((item, "Se alcanzó el límite total"))
            continue

        dest_item = destination / item.name

        try:
            if item.is_dir():
                dir_files = [
                    f
                    for f in item.rglob("*")
                    if f.is_file() and f.stat().st_size <= MAX_FILE_SIZE
                ]
                dir_size = sum(f.stat().st_size for f in dir_files)

                if total_copied + dir_size > MAX_TOTAL_SIZE:
                    report["skipped"].append((item, "Excede límite total"))
                    continue

                shutil.copytree(item, dest_item, dirs_exist_ok=True)
                total_copied += dir_size
                report["copied"].append(item)

            else:
                file_size = item.stat().st_size
                if file_size > MAX_FILE_SIZE:
                    report["skipped"].append((item, "Excede límite por archivo"))
                    continue
                if total_copied + file_size > MAX_TOTAL_SIZE:
                    report["skipped"].append((item, "Excede límite total"))
                    continue

                shutil.copy2(item, dest_item)
                total_copied += file_size
                report["copied"].append(item)

        except Exception as e:
            report["errors"].append((item, str(e)))
            continue

    return report


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


def validate_file(path: str | Path, create_parents: bool = True) -> Path:
    """
    Valida si un archivo existe y opcionalmente crea las carpetas padre.

    Args:
        path (str | Path): Ruta del archivo.
        create_parents (bool, opcional): Si True, crea las carpetas padre si no existen. Por defecto False.

    Retorna:
        Path: ruta validada.

    Lanza:
        FileExistsError: si la ruta existe pero no es un archivo.
        FileNotFoundError: si el archivo no existe.
    """
    path = Path(path)

    if create_parents:
        path.parent.mkdir(parents=True, exist_ok=True)
        return False

    else:
        if path.is_file():
            return path
        elif path.exists():
            raise FileExistsError(f"La ruta existe pero no es un archivo: {path}")
        else:
            raise FileNotFoundError(f"El archivo no existe: {path}")
