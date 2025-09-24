import ezdxf


def remove_non_multiple_polylines(
    input_path: str, output_path: str, elevation_multiple: float = 10
) -> None:
    """
    Remove polylines whose elevation is not a multiple of 'elevation_multiple' from a DXF file.

    Parameters:
    - input_path: ruta del archivo DXF de entrada
    - output_path: ruta del archivo DXF de salida (filtrado)
    - elevation_multiple: valor de múltiplo para la elevación (por defecto es 10)
    """
    # Carga el archivo DXF
    doc = ezdxf.readfile(input_path)
    msp = doc.modelspace()

    # Crea una lista con las entidades que se deben eliminar
    entities_to_remove = []

    for entity in msp:
        # Verifica si es una polilínea ligera (LWPOLYLINE)
        if entity.dxftype() == "LWPOLYLINE":
            elevation = entity.dxf.elevation  # obtiene la elevación (grupo 38)
            # Si la elevación no es múltiplo de 'elevation_multiple', la marca para eliminación
            if elevation % elevation_multiple != 0:
                entities_to_remove.append(entity)

    # Elimina las entidades marcadas
    for entity in entities_to_remove:
        msp.delete_entity(entity)

    # Guarda el nuevo archivo DXF
    doc.saveas(output_path)


# --- USO ---
if __name__ == "__main__":
    # Ruta de entrada y salida (puedes cambiar por argumentos de línea de comandos si lo deseas)
    input_dxf = "data/config/sample_client/sample_project/dxf/DME_CHO.dxf"
    output_dxf = "data/config/sample_client/sample_project/dxf/DME_CHO_temp.dxf"

    remove_non_multiple_polylines(input_dxf, output_dxf)
    print("DXF saved:", output_dxf)
