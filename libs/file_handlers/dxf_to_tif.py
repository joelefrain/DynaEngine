import os
import io
import time
import json
import ezdxf
import folium
import rasterio

import numpy as np
import geopandas as gpd

from PIL import Image

from shapely.geometry import LineString
from rasterio.transform import from_bounds

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from libs.config.config_logger import get_logger

logger = get_logger()


def extract_bounds_latlon(dxf_path, utm_epsg=32718, scale=1.0):
    """Extrae el bounding box del DXF, lo convierte a lat/lon (EPSG:4326) y aplica escalado desde el centro."""
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    geometries = []

    for e in msp:
        if e.dxftype() == "LINE":
            geometries.append(LineString([e.dxf.start[:2], e.dxf.end[:2]]))
        elif e.dxftype() in {"POLYLINE", "LWPOLYLINE"}:
            try:
                points = [tuple(p[:2]) for p in e.get_points()]
                geometries.append(LineString(points))
            except Exception:
                continue

    gdf = gpd.GeoDataFrame(geometry=geometries, crs=f"EPSG:{utm_epsg}")
    gdf_latlon = gdf.to_crs(epsg=4326)
    minlon, minlat, maxlon, maxlat = gdf_latlon.total_bounds

    # Escalar desde el centro
    if scale != 1.0:
        center_lon = (minlon + maxlon) / 2
        center_lat = (minlat + maxlat) / 2
        half_width = (maxlon - minlon) * scale / 2
        half_height = (maxlat - minlat) * scale / 2
        minlon = center_lon - half_width
        maxlon = center_lon + half_width
        minlat = center_lat - half_height
        maxlat = center_lat + half_height

    return np.array([minlon, minlat, maxlon, maxlat])


def create_folium_map_for_cropping(bounds, output_html):
    """Genera un mapa optimizado para captura y recorte preciso."""
    minlon, minlat, maxlon, maxlat = bounds
    center = [(minlat + maxlat) / 2, (minlon + maxlon) / 2]

    m = folium.Map(
        location=center,
        zoom_start=17,
        tiles="Esri.WorldImagery",
        control_scale=False,
        zoom_control=False,
        attribution_control=False,
    )

    folium.Rectangle(
        bounds=[[minlat, minlon], [maxlat, maxlon]],
        color=None,
        weight=2,
        fill=False,
        opacity=1.0,
    ).add_to(m)

    m.fit_bounds([[minlat, minlon], [maxlat, maxlon]], padding=0)

    bounds_list = bounds.tolist()
    bounds_js = f"""
    <script>
    window.mapBounds = {json.dumps(bounds_list)};
    window.addEventListener('load', function() {{
        setTimeout(function() {{
            var map = window[Object.keys(window).find(key => key.startsWith('map_'))];
            if (map) {{
                var bounds = L.latLngBounds([{minlat}, {minlon}], [{maxlat}, {maxlon}]);
                var topLeft = map.latLngToContainerPoint(bounds.getNorthWest());
                var bottomRight = map.latLngToContainerPoint(bounds.getSouthEast());

                window.rectanglePixelBounds = {{
                    left: Math.round(topLeft.x),
                    top: Math.round(topLeft.y),
                    right: Math.round(bottomRight.x),
                    bottom: Math.round(bottomRight.y)
                }};

                console.log('Rectangle pixel bounds:', window.rectanglePixelBounds);
            }}
        }}, 1000);
    }});
    </script>
    """

    m.get_root().html.add_child(folium.Element(bounds_js))
    m.save(output_html)
    logger.info(f"Mapa HTML generado: {output_html}")


def capture_and_crop_satellite_image(
    html_path, bounds, output_png, width=1024, height=768, delay=5
):
    """Captura la imagen y recorta exactamente el área del rectángulo."""
    minlon, minlat, maxlon, maxlat = bounds

    options = Options()
    options.headless = True
    options.add_argument(f"--window-size={width},{height}")
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-features=VizDisplayCompositor")

    driver = webdriver.Chrome(options=options)

    try:
        driver.get("file://" + os.path.abspath(html_path))
        time.sleep(delay)

        pixel_bounds = driver.execute_script("""
            return window.rectanglePixelBounds || null;
        """)

        if pixel_bounds is None:
            logger.info(
                "No se pudieron obtener las coordenadas pixel, usando método alternativo..."
            )
            margin = 50
            pixel_bounds = {
                "left": margin,
                "top": margin,
                "right": width - margin,
                "bottom": height - margin,
            }

        screenshot = driver.get_screenshot_as_png()
        full_image = Image.open(io.BytesIO(screenshot))

        left = max(0, pixel_bounds["left"])
        top = max(0, pixel_bounds["top"])
        right = min(full_image.width, pixel_bounds["right"])
        bottom = min(full_image.height, pixel_bounds["bottom"])

        cropped_image = full_image.crop((left, top, right, bottom))
        cropped_image.save(output_png, "PNG")

        logger.info(f"Imagen recortada guardada: {output_png}")
        logger.info(f"Dimensiones originales: {full_image.width}x{full_image.height}")
        logger.info(
            f"Dimensiones recortadas: {cropped_image.width}x{cropped_image.height}"
        )
        logger.info(
            f"Área recortada: left={left}, top={top}, right={right}, bottom={bottom}"
        )

        return cropped_image.width, cropped_image.height

    except Exception as e:
        logger.exception(f"Error en captura: {e}")
        return None, None
    finally:
        driver.quit()


def png_to_geotiff_precise(
    png_path, bounds, output_tif, img_width=None, img_height=None
):
    """Convierte la imagen PNG recortada a GeoTIFF con georreferenciación precisa."""
    img = Image.open(png_path).convert("RGB")
    img_np = np.array(img)
    height, width = img_np.shape[0], img_np.shape[1]
    minlon, minlat, maxlon, maxlat = bounds

    transform = from_bounds(minlon, minlat, maxlon, maxlat, width, height)

    with rasterio.open(
        output_tif,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=3,
        dtype=img_np.dtype,
        crs="EPSG:4326",
        transform=transform,
        compress="lzw",
    ) as dst:
        for i in range(3):
            dst.write(img_np[:, :, i], i + 1)

    logger.info(f"GeoTIFF georreferenciado generado: {output_tif}")
    with rasterio.open(output_tif) as src:
        logger.info(f"CRS: {src.crs}")
        logger.info(f"Transform: {src.transform}")
        logger.info(f"Bounds verificados: {src.bounds}")


def dxf_to_satellite_geotiff_precise(
    dxf_path, output_basename, utm_zone=18, capture_size=(1024, 768), scale=1.0
):
    """Pipeline completo con recorte preciso y escalado desde el centro del rectángulo."""
    utm_epsg = 32700 + utm_zone
    bounds = extract_bounds_latlon(dxf_path, utm_epsg=utm_epsg, scale=scale)
    logger.info(f"Bounds extraídos y escalados: {bounds}")

    html_path = output_basename + ".html"
    png_path = output_basename + ".png"
    tif_path = output_basename + ".tif"

    create_folium_map_for_cropping(bounds, html_path)

    img_width, img_height = capture_and_crop_satellite_image(
        html_path, bounds, png_path, width=capture_size[0], height=capture_size[1]
    )

    if img_width and img_height:
        png_to_geotiff_precise(png_path, bounds, tif_path, img_width, img_height)
        logger.info(f"Proceso completado exitosamente. Archivo final: {tif_path}")
    else:
        logger.error("Error en el proceso de captura y recorte")


# --- USO ---
if __name__ == "__main__":
    structure = "PAD_2B_2C"
    client = "sample_client"
    project = "sample_project"
    dxf_input = f"data/config/{client}/{project}/dxf/{structure}.dxf"
    output_base = f"data/config/{client}/{project}/tif/{structure}"

    # Escalado desde el centro (por ejemplo 1.3 = 30% más grande)
    dxf_to_satellite_geotiff_precise(
        dxf_input, output_base, utm_zone=17, capture_size=(2048, 1536), scale=1.0
    )
