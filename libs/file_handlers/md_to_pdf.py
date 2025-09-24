import markdown

from weasyprint import HTML


def convert_md_to_pdf(input_md: str, output_pdf: str):
    """
    Convierte un archivo Markdown a PDF.

    Args:
        input_md (str): Ruta del archivo Markdown de entrada.
        output_pdf (str): Ruta del archivo PDF de salida.
    """
    # Leer el archivo markdown
    with open(input_md, "r", encoding="utf-8") as f:
        md_text = f.read()

    # Convertir markdown a HTML
    html_text = markdown.markdown(md_text, extensions=["fenced_code", "tables"])

    # Añadir estilo básico para el PDF
    html_template = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 0.5cm;
                line-height: 1.6;
            }}
            h1, h2, h3 {{
                color: #1a237e;
            }}
            pre {{
                background-color: #f4f4f4;
                padding: 10px;
                border-radius: 5px;
                overflow-x: auto;
            }}
            code {{
                font-family: Consolas, monospace;
                background-color: #eeeeee;
                padding: 2px 4px;
                border-radius: 4px;
            }}
            hr {{
                border: none;
                border-top: 1px solid #ccc;
                margin: 6px 0;
            }}
        </style>
    </head>
    <body>
    {html_text}
    </body>
    </html>
    """

    # Generar el PDF
    HTML(string=html_template).write_pdf(output_pdf)


# --- USO ---
if __name__ == "__main__":
    output_pdf = "README.pdf"
    convert_md_to_pdf("README.md", "README.pdf")
    print(f"PDF generado: {output_pdf}")
