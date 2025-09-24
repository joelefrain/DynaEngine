import os

from PyPDF2 import PdfMerger

from libs.helpers.storage_helpers import validate_folder


def find_pdf_files(input_dir: str) -> list:
    """Busca recursivamente archivos PDF en el directorio de entrada.

    Args:
        input_dir (str): Ruta del directorio de entrada

    Returns:
        list: Lista de rutas de archivos PDF encontrados
    """
    pdf_files = []
    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.lower().endswith(".pdf"):
                pdf_files.append(os.path.join(root, file))
    return sorted(pdf_files, key=lambda x: os.path.basename(x))


def merge_pdfs(pdf_files: list, output_path: str) -> None:
    """Fusiona los archivos PDF en un único archivo.

    Args:
        pdf_files (list): Lista de rutas de archivos PDF a fusionar
        output_path (str): Ruta del archivo PDF de salida
    """
    merger = PdfMerger()

    for pdf_file in pdf_files:
        merger.append(pdf_file)

    # Asegurarse que el directorio de salida existe
    output_dir = os.path.dirname(output_path)
    if output_dir:
        validate_folder(output_dir, create_if_missing=True)

    # Guardar el PDF fusionado
    merger.write(output_path)
    merger.close()
