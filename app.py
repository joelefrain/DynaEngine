# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import json
import logging
import os
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import webview
except Exception:  # pragma: no cover
    webview = None

APP_NAME = "Prismo"
APP_VERSION = "1.0.3"
ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"

for candidate in (ROOT_DIR, BACKEND_DIR):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from services.service_calibration import (  # noqa: E402
    exec_column_process,
    inspect_column_before_discretization,
    send_metadata_from_sections,
)
from modules.section_proccessing.generate_columns import (  # noqa: E402
    assign_polygons,
    generate_clean_polygons,
    generate_polygons,
    read_dxf_columns,
)
from scripts.exec_make_input import create_session_folder  # noqa: E402


class MemoryLogHandler(logging.Handler):
    def __init__(self, sink: list[dict[str, Any]]):
        super().__init__(level=logging.INFO)
        self.sink = sink
        self.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.sink.append(
                {
                    "ts": datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                }
            )
        except Exception:
            pass


class PrismoAPI:
    def __init__(self):
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.sections_dir = ""
        self.output_root = str(Path(os.environ.get("PRISMO_OUTPUT_DIR", ROOT_DIR / "_outputs")).expanduser())
        os.environ.setdefault("PRISMO_OUTPUT_DIR", self.output_root)
        self.current_view = "geometria"
        self.processing = False
        self.progress_pct = 0
        self.metadata_ready = False
        self.metadata_error = ""
        self.metadata_status = "Selecciona una carpeta DXF para ejecutar send_metadata_from_sections."
        self.metadata_needs_confirmation = False
        self.section_names: list[str] = []
        self.section_paths: dict[str, str] = {}
        self.section_previews: dict[str, dict[str, Any]] = {}
        self.material_names: list[str] = []
        self.materials: list[dict[str, Any]] = []
        self.x_position_map: dict[str, dict[str, list[float]]] = {}
        self.warnings: list[str] = []
        self.warning_area_ids: list[str] = []
        self.warning_area_map: dict[str, list[str]] = {}
        self.warning_section_messages: dict[str, list[str]] = {}
        self.error_section_messages: dict[str, list[str]] = {}
        self.logs: list[dict[str, Any]] = []
        self.results: dict[str, Any] = {}
        self.f_target = 25.0
        self.dynamic_curve_config = self._load_dynamic_curve_config()
        self._install_memory_logger()

    def _install_memory_logger(self) -> None:
        handler = MemoryLogHandler(self.logs)
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        if not any(isinstance(h, MemoryLogHandler) for h in root.handlers):
            root.addHandler(handler)

    def _log(self, level: str, message: str) -> None:
        self.logs.append({"ts": datetime.now().strftime("%H:%M:%S"), "level": level.upper(), "logger": "app", "message": message})

    def _load_dynamic_curve_config(self) -> dict[str, Any]:
        path = BACKEND_DIR / "data" / "dynamic_curves" / "curve_parameters.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["user_defined"] = {
                "model_name": "Definido por usuario",
                "model_type": "user_defined",
                "model_parameters": {},
            }
            return data
        except Exception as exc:
            self._log("ERROR", f"No se pudo leer curve_parameters.json: {exc}")
            return {"user_defined": {"model_name": "Definido por usuario", "model_type": "user_defined", "model_parameters": {}}}

    def _state(self) -> dict[str, Any]:
        total = 0
        by_section: dict[str, int] = {}
        for section, failures in self.x_position_map.items():
            subtotal = sum(len(v or []) for v in (failures or {}).values())
            by_section[section] = subtotal
            total += subtotal
        by_section["total"] = total
        return {
            "app_name": APP_NAME,
            "app_version": APP_VERSION,
            "session_id": self.session_id,
            "current_view": self.current_view,
            "sections_dir": self.sections_dir,
            "output_root": self.output_root,
            "processing": self.processing,
            "progress_pct": self.progress_pct,
            "metadata_ready": self.metadata_ready,
            "metadata_error": self.metadata_error,
            "metadata_status": self.metadata_status,
            "metadata_needs_confirmation": self.metadata_needs_confirmation,
            "section_names": self.section_names,
            "section_paths": self.section_paths,
            "section_previews": self.section_previews,
            "material_names": self.material_names,
            "materials": self.materials,
            "x_position_map": self.x_position_map,
            "number_of_columns": by_section,
            "warnings": self.warnings,
            "warning_area_ids": self.warning_area_ids,
            "warning_area_map": self.warning_area_map,
            "warning_section_messages": self.warning_section_messages,
            "error_section_messages": self.error_section_messages,
            "logs": self.logs[-500:],
            "results": self.results,
            "f_target": self.f_target,
            "dynamic_curve_config": self.dynamic_curve_config,
        }

    def get_state(self) -> dict[str, Any]:
        return self._state()

    def set_current_view(self, view: str) -> dict[str, Any]:
        self.current_view = str(view or "geometria")
        return self._state()

    def choose_sections_dir(self) -> dict[str, Any]:
        if webview and getattr(webview, "windows", None):
            result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
            if not result:
                return self._state()
            folder = result[0]
        else:
            raise RuntimeError("El selector de carpetas solo está disponible ejecutando app.py con pywebview.")
        return self.load_sections_dir(folder)

    def load_sections_dir(self, folder: str) -> dict[str, Any]:
        self.sections_dir = str(Path(folder).expanduser())
        self.metadata_error = ""
        self.metadata_ready = False
        self.metadata_needs_confirmation = False
        self.metadata_status = "Leyendo DXF con send_metadata_from_sections..."
        self.warnings = []
        self.warning_area_ids = []
        self.warning_area_map = {}
        self.warning_section_messages = {}
        self.error_section_messages = {}
        self.section_previews = {}
        self.section_paths = {}
        self.section_names = []
        self.material_names = []
        self.results = {}
        try:
            before = len(self.logs)
            # Paso obligatorio: usar el backend real para metadata, figuras y warnings por logger.
            send_metadata_from_sections(self.session_id, self.sections_dir)
            new_log_entries = self.logs[before:]
            backend_warnings = [entry["message"] for entry in new_log_entries if entry.get("level") == "WARNING"]

            base_output_dir = create_session_folder(self.session_id)
            metadata_path = base_output_dir / "metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}

            self.section_names = list(metadata.get("section_names") or [])
            self.material_names = list(metadata.get("material_names") or [])
            self.materials = [self._default_material(name) for name in self.material_names]
            self.section_paths = self._discover_section_paths(self.sections_dir)

            for name in self.section_names:
                path = self.section_paths.get(name)
                if not path:
                    continue
                try:
                    preview, section_warnings, area_ids = self._build_section_preview(path)
                    self.section_previews[name] = preview
                    if name not in self.x_position_map:
                        self.x_position_map[name] = {}
                    for failure in preview.get("failure_surfaces", []):
                        self.x_position_map[name].setdefault(failure["id"], [])
                    if section_warnings:
                        self.warning_section_messages[name] = section_warnings
                    if area_ids:
                        self.warning_area_map[name] = area_ids
                except Exception as exc:
                    self.error_section_messages.setdefault(name, []).append(str(exc))
                    self._log("ERROR", f"No se pudo construir preview DXF de {name}: {exc}")

            all_section_warnings = [f"{name}: {msg}" for name, msgs in self.warning_section_messages.items() for msg in msgs]
            self.warnings = list(dict.fromkeys(backend_warnings + all_section_warnings))
            self.warning_area_ids = sorted({aid for ids in self.warning_area_map.values() for aid in ids}, key=lambda x: (len(x), x))
            self.metadata_needs_confirmation = bool(self.warnings)
            self.metadata_ready = not self.metadata_needs_confirmation and not self.error_section_messages
            if self.error_section_messages:
                self.metadata_error = "Se leyeron los DXF, pero algunas secciones no pudieron graficarse. Revisa el modal de warnings/logs."
            elif self.metadata_needs_confirmation:
                self.metadata_status = "send_metadata_from_sections finalizó con warnings. Deben revisarse y aceptarse."
            else:
                self.metadata_status = "send_metadata_from_sections finalizó correctamente."
                self.metadata_ready = True
        except Exception as exc:
            self.metadata_error = str(exc)
            self.metadata_status = "Error ejecutando send_metadata_from_sections."
            self._log("ERROR", traceback.format_exc())
        return self._state()

    def confirm_metadata_warnings(self) -> dict[str, Any]:
        if not self.metadata_error:
            self.metadata_needs_confirmation = False
            self.metadata_ready = True
            self.metadata_status = "Warnings aceptados por el usuario. Metadata lista."
        return self._state()

    def _discover_section_paths(self, folder: str) -> dict[str, str]:
        out: dict[str, str] = {}
        for path in sorted(Path(folder).expanduser().rglob("*.dxf")):
            out[path.name] = str(path)
            out[path.stem] = str(path)
        return out

    def _default_material(self, name: str) -> dict[str, Any]:
        return {
            "material_name": name,
            "unit_weight_kn_m3": 19.0,
            "shear_properties": {"c": 0.0, "phi": 34.0},
            "shear_velocity": {"depth": [0, 5, 10, 15], "vs": [300, 350, 440, 550]},
            "dynamic_model": {"model_type": "", "sigma_vertical": 100.0, "soil_parameters": {}},
            "characterization_status": "Pendiente",
        }

    def _build_section_preview(self, section_path: str) -> tuple[dict[str, Any], list[str], list[str]]:
        external_pline, freatic_pline, material_pline, failure_pline, text_data = read_dxf_columns(section_path)
        clean_polygons = generate_clean_polygons(external_pline, material_pline, text_data)
        raw_polygons = generate_polygons(external_pline, material_pline)
        _, empty_polygons = assign_polygons(text_data, raw_polygons)

        warnings: list[str] = []
        area_ids: list[str] = []
        if len(text_data) != len(clean_polygons):
            warnings.append("El número de etiquetas no coincide con el número de polígonos limpios.")
        for poly_dict in empty_polygons:
            area = float(poly_dict["geometry"].area)
            if area < 100:
                pid = str(poly_dict["id"])
                warnings.append(f"Polígono con área muy pequeña detectado | ID: {pid} | Área: {area:.3f}")
                area_ids.append(pid)

        svg, bounds = self._section_svg(clean_polygons, external_pline, material_pline, failure_pline, freatic_pline, empty_polygons)
        failures = [
            {"id": f"failure_{i + 1}", "label": f"Superficie {i + 1}", "layer": "SUP_FALLA", "color": "#d3342f"}
            for i, _ in enumerate(failure_pline)
        ] or [{"id": "failure_1", "label": "Superficie 1", "layer": "SUP_FALLA", "color": "#d3342f"}]
        return {"svg": svg, "bounds": bounds, "failure_surfaces": failures}, warnings, area_ids

    def _section_svg(self, layer_polygons, external_pline, material_pline, failure_pline, freatic_pline, empty_polygons) -> tuple[str, dict[str, float]]:
        xs: list[float] = []
        ys: list[float] = []
        for _, poly_dict in layer_polygons:
            minx, miny, maxx, maxy = poly_dict["geometry"].bounds
            xs += [minx, maxx]
            ys += [miny, maxy]
        for group in (external_pline, material_pline, failure_pline, freatic_pline):
            for pl in group:
                for x, y in pl:
                    xs.append(float(x)); ys.append(float(y))
        min_x, max_x = (min(xs), max(xs)) if xs else (0.0, 1.0)
        min_y, max_y = (min(ys), max(ys)) if ys else (0.0, 1.0)
        pad_x = max((max_x - min_x) * 0.04, 1.0)
        pad_y = max((max_y - min_y) * 0.04, 1.0)
        min_x -= pad_x; max_x += pad_x; min_y -= pad_y; max_y += pad_y
        width = max_x - min_x
        height = max_y - min_y
        view_min_y = -max_y

        def pt(x, y):
            return f"{float(x):.4f},{-float(y):.4f}"

        palette = ["#dbeafe", "#dcfce7", "#fef3c7", "#fce7f3", "#e0e7ff", "#cffafe", "#ede9fe", "#f3f4f6"]
        parts = [f'<svg class="dxf-preview-svg" xmlns="http://www.w3.org/2000/svg" viewBox="{min_x:.4f} {view_min_y:.4f} {width:.4f} {height:.4f}" preserveAspectRatio="xMidYMid meet">']
        parts.append('<rect x="-100000000" y="-100000000" width="200000000" height="200000000" fill="#ffffff"/>')
        for i, (name, poly_dict) in enumerate(layer_polygons):
            poly = poly_dict["geometry"]
            coords = " ".join(pt(x, y) for x, y in poly.exterior.coords)
            pid = str(poly_dict.get("id", i + 1))
            color = palette[i % len(palette)]
            rp = poly.representative_point()
            parts.append(f'<polygon class="dxf-area" data-area-id="{pid}" points="{coords}" fill="{color}" stroke="#334155" stroke-width="1.15" vector-effect="non-scaling-stroke" opacity="0.72"/>')
            parts.append(f'<text x="{rp.x:.4f}" y="{-rp.y:.4f}" text-anchor="middle" dominant-baseline="middle" font-size="8" fill="#0f172a" paint-order="stroke" stroke="#ffffff" stroke-width="2" vector-effect="non-scaling-stroke">{self._xml_escape(str(name))}</text>')
        for poly_dict in empty_polygons:
            poly = poly_dict["geometry"]
            coords = " ".join(pt(x, y) for x, y in poly.exterior.coords)
            pid = str(poly_dict.get("id", ""))
            parts.append(f'<polygon class="dxf-area empty-area" data-area-id="{pid}" points="{coords}" fill="rgba(255,138,0,0.22)" stroke="#ff8a00" stroke-width="1.2" vector-effect="non-scaling-stroke" opacity="0.6"/>')
        for pl in external_pline:
            points = " ".join(pt(x, y) for x, y in pl)
            parts.append(f'<polyline points="{points}" fill="none" stroke="#111827" stroke-width="1.7" stroke-dasharray="6 4" vector-effect="non-scaling-stroke"/>')
        for pl in material_pline:
            points = " ".join(pt(x, y) for x, y in pl)
            parts.append(f'<polyline points="{points}" fill="none" stroke="#64748b" stroke-width="1.0" stroke-dasharray="3 3" vector-effect="non-scaling-stroke"/>')
        for i, pl in enumerate(failure_pline):
            points = " ".join(pt(x, y) for x, y in pl)
            parts.append(f'<polyline class="dxf-failure" data-failure="failure_{i + 1}" points="{points}" fill="none" stroke="#d3342f" stroke-width="2.1" vector-effect="non-scaling-stroke"/>')
        for pl in freatic_pline:
            points = " ".join(pt(x, y) for x, y in pl)
            parts.append(f'<polyline class="dxf-freatic" points="{points}" fill="none" stroke="#0069aa" stroke-width="1.8" vector-effect="non-scaling-stroke"/>')
        parts.append("</svg>")
        bounds = {"min_x": min_x, "max_x": max_x, "min_y": view_min_y, "max_y": view_min_y + height, "raw_min_y": min_y, "raw_max_y": max_y}
        return "".join(parts), bounds

    def _xml_escape(self, value: str) -> str:
        return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    def add_column(self, section: str, failure: str, x: float) -> dict[str, Any]:
        self.x_position_map.setdefault(section, {}).setdefault(failure, [])
        arr = self.x_position_map[section][failure]
        value = round(float(x), 4)
        if value not in arr:
            arr.append(value)
            arr.sort()
        return self._state()

    def set_columns(self, section: str, failure: str, values: list[Any]) -> dict[str, Any]:
        clean = sorted({round(float(v), 4) for v in values if self._is_number(v)})
        self.x_position_map.setdefault(section, {})[failure] = clean
        return self._state()

    def remove_column(self, section: str, failure: str, index: int) -> dict[str, Any]:
        arr = self.x_position_map.setdefault(section, {}).setdefault(failure, [])
        i = int(index)
        if 0 <= i < len(arr):
            arr.pop(i)
        return self._state()

    def clear_columns(self, section: str, failure: str) -> dict[str, Any]:
        self.x_position_map.setdefault(section, {})[failure] = []
        return self._state()

    def set_materials(self, materials: list[dict[str, Any]]) -> dict[str, Any]:
        self.materials = materials or []
        return self._state()

    def set_f_target(self, value: float) -> dict[str, Any]:
        self.f_target = float(value)
        return self._state()

    def start_column_process(self) -> dict[str, Any]:
        if self.processing:
            return self._state()
        thread = threading.Thread(target=self._run_column_process, daemon=True)
        thread.start()
        return self._state()

    def _run_column_process(self) -> None:
        try:
            self.processing = True
            self.progress_pct = 5
            self._log("INFO", "Iniciando exec_column_process con backend real.")
            specs = self._build_column_input_specs()
            self.progress_pct = 15
            raw_result = exec_column_process(self.sections_dir, self.materials, self.x_position_map, self.f_target, self.session_id, output_root=self.output_root)
            self.progress_pct = 85
            self.results = {
                "column_input_specs": specs,
                "raw_result_summary": raw_result,
                "session_dir": str(create_session_folder(self.session_id, output_root=self.output_root)),
            }
            self.progress_pct = 100
            self._log("INFO", "Procesamiento finalizado.")
        except Exception:
            self._log("ERROR", traceback.format_exc())
        finally:
            self.processing = False

    def _build_column_input_specs(self) -> list[dict[str, Any]]:
        specs: list[dict[str, Any]] = []
        for section, failures in self.x_position_map.items():
            section_file = self.section_paths.get(section) or self.section_paths.get(Path(section).stem)
            if not section_file:
                continue
            for failure, xs in failures.items():
                for i, x in enumerate(xs or [], start=1):
                    item = {"id": f"{Path(section).stem}-column_{i}-{failure}", "section": section, "failure": failure, "column": f"column_{i}", "x": x, "layers": []}
                    try:
                        preview = inspect_column_before_discretization(section_file, self.materials, self.x_position_map, self.f_target, Path(section).stem, failure, f"column_{i}")
                        item["materials_found_ordered"] = preview.get("materials_found_ordered", [])
                        col = preview.get("column_input", {}).get("column", {})
                        item["layers"] = col.get("layers", []) if isinstance(col, dict) else []
                        item["freatic"] = col.get("freatic") if isinstance(col, dict) else None
                        item["depth_failure_surface"] = col.get("depth_failure_surface") if isinstance(col, dict) else None
                    except Exception as exc:
                        item["preview_error"] = str(exc)
                    specs.append(item)
        return specs

    def save_results_as(self) -> dict[str, Any]:
        if not self.results:
            self._log("WARNING", "No hay resultados para guardar.")
            return self._state()
        if webview and getattr(webview, "windows", None):
            result = webview.windows[0].create_file_dialog(webview.SAVE_DIALOG, save_filename="prismo_resultados.json")
            if result:
                Path(result).write_text(json.dumps(self.results, ensure_ascii=False, indent=2), encoding="utf-8")
        return self._state()

    def _is_number(self, value: Any) -> bool:
        try:
            float(value)
            return True
        except Exception:
            return False


def main() -> None:
    if webview is None:
        raise RuntimeError("pywebview no está instalado. Ejecuta: pip install -r requirements.txt")
    api = PrismoAPI()
    index = FRONTEND_DIR / "index.html"
    window = webview.create_window(APP_NAME, str(index), js_api=api, width=1450, height=920, min_size=(1180, 760))
    webview.start(debug=False)


if __name__ == "__main__":
    main()
