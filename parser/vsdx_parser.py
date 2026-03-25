"""
Phase 1 – Parser
.vsdx → intermediate JSON graph

Bruker python-vsdx (MIT) for å abstrahere over ZIP/XML-kompleksiteten.
Koordinatsystem: Visio bruker inches med origo nede til venstre (y opp).
Konverterer til SVG/HTML-konvensjon: origo øverst til venstre (y ned).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import vsdx


# ── Hjelpefunksjoner ────────────────────────────────────────────────────────


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _inches_to_px(inches: float, dpi: int = 96) -> float:
    """Visio-koordinater er i inches; konverterer til CSS px (96 dpi)."""
    return round(inches * dpi, 2)


def _clean_text(text: str | None) -> str:
    if not text:
        return ""
    # Fjern XML-entiteter og whitespace
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def _shape_style(shape: vsdx.Shape) -> dict:
    """Henter ut fill- og stroke-farge og font-størrelse der det er tilgjengelig."""
    style: dict = {}
    try:
        fill = shape.cell_value("FillForegnd")
        if fill:
            style["fill"] = fill
    except Exception:
        pass
    try:
        stroke = shape.cell_value("LineColor")
        if stroke:
            style["stroke"] = stroke
    except Exception:
        pass
    try:
        font_size = shape.cell_value("Char.Size")
        if font_size:
            style["font_size"] = int(_safe_float(font_size) * 72)  # pt
    except Exception:
        pass
    return style


# ── Hoved-konvertering ───────────────────────────────────────────────────────


def _is_edge(shape: vsdx.Shape) -> bool:
    """Returnerer True hvis shape er en connector/edge."""
    return str(shape.shape_type).lower() in ("edge", "connector")


def _parse_shape(shape: vsdx.Shape, page_height_in: float) -> dict | None:
    """Konverterer én Visio-shape til et node-objekt i JSON-grafen."""
    if _is_edge(shape):
        return None

    x_in = _safe_float(shape.x)
    y_in = _safe_float(shape.y)
    w_in = _safe_float(shape.width)
    h_in = _safe_float(shape.height)

    # Visio: PinX/PinY er sentrum av shape, y opp.
    # HTML: top-left, y ned.
    x_px = _inches_to_px(x_in - w_in / 2)
    y_px = _inches_to_px(page_height_in - y_in - h_in / 2)

    return {
        "id": str(shape.ID),
        "text": _clean_text(shape.text),
        "type": str(shape.shape_type) if shape.shape_type else "Shape",
        "x": x_px,
        "y": y_px,
        "w": _inches_to_px(w_in),
        "h": _inches_to_px(h_in),
        "style": _shape_style(shape),
    }


def _parse_connector(shape: vsdx.Shape) -> dict | None:
    """Konverterer én Visio-connector til et edge-objekt i JSON-grafen."""
    if not _is_edge(shape):
        return None

    connects = shape.connects
    from_id = to_id = None
    for c in connects:
        if c.from_rel == "BeginX":
            from_id = str(c.shape_id)
        elif c.from_rel == "EndX":
            to_id = str(c.shape_id)

    if not from_id or not to_id:
        return None

    return {
        "id": str(shape.ID),
        "from": from_id,
        "to": to_id,
        "label": _clean_text(shape.text),
    }


def _parse_page(page: vsdx.Page) -> dict:
    """Konverterer én Visio-side til et page-objekt i JSON-grafen."""
    # Sidemål – page.width/height er buggy i denne vsdx-versjonen, bruker A4 landskapsformat
    try:
        page_w_in = _safe_float(page.width, default=11.0)
        page_h_in = _safe_float(page.height, default=8.5)
    except Exception:
        page_w_in = 11.0
        page_h_in = 8.5

    nodes: list[dict] = []
    edges: list[dict] = []

    def walk(shapes: list[vsdx.Shape]) -> None:
        for shape in shapes:
            node = _parse_shape(shape, page_h_in)
            if node:
                nodes.append(node)
            edge = _parse_connector(shape)
            if edge:
                edges.append(edge)
            # Rekursivt for grupperte shapes
            if shape.sub_shapes():
                walk(shape.sub_shapes())

    walk(page.child_shapes)

    return {
        "id": str(page.index_num),
        "name": page.name or f"Side {page.index_num + 1}",
        "width": _inches_to_px(page_w_in),
        "height": _inches_to_px(page_h_in),
        "nodes": nodes,
        "edges": edges,
    }


def parse_vsdx(path: str | Path) -> dict:
    """
    Hovedfunksjon: leser en .vsdx-fil og returnerer intermediate JSON-graf.

    Args:
        path: Filsti til .vsdx-filen.

    Returns:
        Dict med nøklene 'meta' og 'pages' i henhold til JSON-skjemaet.
    """
    path = Path(path)
    with vsdx.VisioFile(str(path)) as vis:
        # Metadata – vsdx har ikke document_properties, bruker filnavn som tittel
        meta = {
            "title": path.stem,
            "author": "",
            "modified": "",
        }

        pages = [_parse_page(p) for p in vis.pages]

    return {"meta": meta, "pages": pages}
