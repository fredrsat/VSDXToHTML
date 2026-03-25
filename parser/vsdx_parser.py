"""
Phase 1 – Parser
.vsdx → intermediate JSON graph

Uses python-vsdx (MIT) to abstract over ZIP/XML complexity.
Coordinate system: Visio uses inches with origin at bottom-left (y increases upward).
Converts to SVG/HTML convention: origin at top-left (y increases downward).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import vsdx


# ── Helpers ──────────────────────────────────────────────────────────────────


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _inches_to_px(inches: float, dpi: int = 96) -> float:
    """Converts Visio inches to CSS pixels at 96 dpi."""
    return round(inches * dpi, 2)


def _clean_text(text: str | None) -> str:
    if not text:
        return ""
    # Strip XML tags and whitespace
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def _shape_style(shape: vsdx.Shape) -> dict:
    """Extracts fill color, stroke color, and font size where available."""
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


# ── Conversion ────────────────────────────────────────────────────────────────


def _is_edge(shape: vsdx.Shape) -> bool:
    """Returns True if the shape is a connector/edge."""
    return str(shape.shape_type).lower() in ("edge", "connector")


def _parse_shape(shape: vsdx.Shape, page_height_in: float) -> dict | None:
    """Converts a single Visio shape to a node object in the JSON graph."""
    if _is_edge(shape):
        return None

    x_in = _safe_float(shape.x)
    y_in = _safe_float(shape.y)
    w_in = _safe_float(shape.width)
    h_in = _safe_float(shape.height)

    # Visio: PinX/PinY is the center of the shape, y increases upward.
    # HTML: origin is top-left, y increases downward.
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
    """Converts a single Visio connector to an edge object in the JSON graph."""
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
    """Converts a single Visio page to a page object in the JSON graph."""
    # page.width/height is buggy in this vsdx version — fall back to A4 landscape
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
            # Recurse into grouped shapes
            if shape.sub_shapes():
                walk(shape.sub_shapes())

    walk(page.child_shapes)

    return {
        "id": str(page.index_num),
        "name": page.name or f"Page {page.index_num + 1}",
        "width": _inches_to_px(page_w_in),
        "height": _inches_to_px(page_h_in),
        "nodes": nodes,
        "edges": edges,
    }


def parse_vsdx(path: str | Path) -> dict:
    """
    Reads a .vsdx file and returns an intermediate JSON graph.

    Args:
        path: Path to the .vsdx file.

    Returns:
        Dict with keys 'meta' and 'pages' according to the JSON schema.
    """
    path = Path(path)
    with vsdx.VisioFile(str(path)) as vis:
        # vsdx does not expose document_properties — use filename as title
        meta = {
            "title": path.stem,
            "author": "",
            "modified": "",
        }

        pages = [_parse_page(p) for p in vis.pages]

    return {"meta": meta, "pages": pages}
