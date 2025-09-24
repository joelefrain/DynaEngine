import os
import ezdxf


def get_bounding_box(dxf_path):
    if not os.path.isfile(dxf_path):
        raise FileNotFoundError(f"File not found: {dxf_path}")

    doc = ezdxf.readfile(dxf_path)
    modelspace = doc.modelspace()

    min_x, min_y = float("inf"), float("inf")
    max_x, max_y = float("-inf"), float("-inf")

    found_valid = (
        False  # Bandera para verificar si encontramos al menos una entidad válida
    )

    for entity in modelspace:
        entity_type = entity.dxftype()
        try:
            # Intentar usar el bounding box nativo
            if hasattr(entity, "bbox"):
                bbox = entity.bbox()
                if bbox:
                    min_corner, max_corner = bbox.extmin, bbox.extmax
                    min_x = min(min_x, min_corner.x)
                    min_y = min(min_y, min_corner.y)
                    max_x = max(max_x, max_corner.x)
                    max_y = max(max_y, max_corner.y)
                    found_valid = True
                    continue

            # Intentar con atributos comunes
            if hasattr(entity, "dxf"):
                for attr in ["start", "end", "center", "insert"]:
                    if hasattr(entity.dxf, attr):
                        point = getattr(entity.dxf, attr)
                        min_x = min(min_x, point.x)
                        min_y = min(min_y, point.y)
                        max_x = max(max_x, point.x)
                        max_y = max(max_y, point.y)
                        found_valid = True

            # Casos especiales: LWPOLYLINE, POLYLINE
            if entity_type in ["LWPOLYLINE", "POLYLINE"]:
                for point in entity.get_points():
                    x, y = point[0], point[1]
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)
                    found_valid = True

        except Exception as e:
            print(f"Error processing entity {entity_type}: {e}")

    if not found_valid:
        raise ValueError("No valid coordinate entities found in modelspace.")

    return (min_x, min_y), (max_x, max_y)


if __name__ == "__main__":
    dxf_file = "./data/config/sample_client/sample_project/dxf/DME_CHO.dxf"
    try:
        lower_left, upper_right = get_bounding_box(dxf_file)
        print("Bounding box:")
        print(f" - Lower left corner: {lower_left}")
        print(f" - Upper right corner: {upper_right}")
    except Exception as e:
        print(f"Error: {e}")
