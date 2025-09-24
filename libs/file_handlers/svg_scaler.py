import cairosvg

from pathlib import Path
from xml.etree import ElementTree as ET


def svg_to_pdf(svg_path, pdf_path):
    cairosvg.svg2pdf(url=svg_path, write_to=pdf_path)


def get_output_path(input_path: str, actual_width: int, actual_height: int) -> str:
    """Generate output path with actual dimensions suffix."""
    p = Path(input_path)
    return str(p.parent / f"{p.stem}_{actual_width}x{actual_height}{p.suffix}")


def scale_svg(
    svg_content: str,
    target_width: int,
    target_height: int,
    output_path: str = None,
    keep_aspect_ratio: bool = True,
) -> str:
    """
    Escala un SVG al mejor ajuste dentro de target_width x target_height y opcionalmente lo guarda.

    Args:
        svg_content: Contenido del SVG a escalar
        target_width: Ancho objetivo
        target_height: Alto objetivo
        output_path: Ruta del archivo original (para generar la ruta de salida)
        keep_aspect_ratio: Mantener proporción de aspecto

    Returns:
        str: SVG escalado
    """
    tree = ET.ElementTree(ET.fromstring(svg_content))
    root = tree.getroot()

    # Obtener dimensiones originales
    width = root.get("width")
    height = root.get("height")
    viewBox = root.get("viewBox")

    if viewBox:
        _, _, orig_w, orig_h = map(float, viewBox.split())
    elif width and height:
        orig_w = float(width.replace("px", ""))
        orig_h = float(height.replace("px", ""))
    else:
        raise ValueError("SVG debe tener width/height o viewBox definidos.")

    if keep_aspect_ratio:
        scale = min(target_width / orig_w, target_height / orig_h)
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)
    else:
        new_w = target_width
        new_h = target_height

    root.set("width", f"{new_w}px")
    root.set("height", f"{new_h}px")
    if not viewBox:
        root.set("viewBox", f"0 0 {orig_w} {orig_h}")

    scaled_svg = ET.tostring(root, encoding="unicode")

    # Si se proporciona ruta, guardar archivo
    if output_path:
        save_path = get_output_path(output_path, new_w, new_h)
        Path(save_path).write_text(scaled_svg)

    return save_path


# --- USO ---
if __name__ == "__main__":
    # Leer archivo SVG de entrada
    input_file = Path("data/logo/logo_main.svg")
    try:
        svg_content = input_file.read_text()
        save_path = scale_svg(
            svg_content, target_width=142, target_height=50, output_path=str(input_file)
        )
        print(f"SVG escalado y guardado en: {save_path}")
        svg_to_pdf(save_path, save_path.replace(".svg", ".pdf"))
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo {input_file}")
    except Exception as e:
        print(f"Error: {e}")
