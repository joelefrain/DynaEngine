from __future__ import annotations

from pathlib import Path

import ezdxf


def build_demo_dxf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = ezdxf.new()
    for layer in ("EXTERNAL", "MATERIAL", "FREATIC", "SUP_FALLA", "TEXTO"):
        if layer not in doc.layers:
            doc.layers.add(layer)

    modelspace = doc.modelspace()
    modelspace.add_lwpolyline(
        [(0, 0), (100, 0), (100, 30), (0, 30), (0, 0)],
        dxfattribs={"layer": "EXTERNAL"},
    )
    modelspace.add_lwpolyline([(0, 18), (100, 18)], dxfattribs={"layer": "MATERIAL"})
    modelspace.add_lwpolyline([(0, 25), (100, 25)], dxfattribs={"layer": "FREATIC"})
    modelspace.add_lwpolyline([(0, 12), (100, 12)], dxfattribs={"layer": "SUP_FALLA"})
    modelspace.add_text(
        "Arena", dxfattribs={"layer": "TEXTO", "height": 1.5}
    ).set_placement((10, 24))
    modelspace.add_text(
        "Grava", dxfattribs={"layer": "TEXTO", "height": 1.5}
    ).set_placement((10, 8))
    doc.saveas(path)
