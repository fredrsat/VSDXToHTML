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


def _page_bounds_from_shapes(shapes: list[dict]) -> tuple[float, float]:
    """
    Calculates page width and height in inches from the bounding box of all shapes.
    Used as a fallback when page.width/height is unavailable.
    Adds 1 inch of padding around all shapes.
    """
    if not shapes:
        return 11.0, 8.5  # A4 landscape default
    padding_px = 96  # 1 inch
    max_x = max(n["x"] + n["w"] for n in shapes) + padding_px
    max_y = max(n["y"] + n["h"] for n in shapes) + padding_px
    return max_x / 96, max_y / 96  # back to inches for consistency


# ── Conversion ────────────────────────────────────────────────────────────────


def _is_edge(shape: vsdx.Shape) -> bool:
    """Returns True if the shape is a connector/edge."""
    return str(shape.shape_type).lower() in ("edge", "connector")


def _parse_shape(
    shape: vsdx.Shape,
    page_height_in: float,
    parent_x_in: float = 0.0,
    parent_y_in: float = 0.0,
) -> dict | None:
    """
    Converts a single Visio shape to a node object in the JSON graph.

    For shapes inside a group, parent_x_in and parent_y_in provide the
    group's absolute position so child coordinates can be made absolute.
    """
    if _is_edge(shape):
        return None

    x_in = _safe_float(shape.x) + parent_x_in
    y_in = _safe_float(shape.y) + parent_y_in
    w_in = _safe_float(shape.width)
    h_in = _safe_float(shape.height)

    # Skip shapes with no meaningful size
    if w_in == 0 and h_in == 0:
        return None

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

    # Skip connectors with missing endpoints
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
    nodes: list[dict] = []
    edges: list[dict] = []

    def walk(
        shapes: list[vsdx.Shape],
        parent_x_in: float = 0.0,
        parent_y_in: float = 0.0,
    ) -> None:
        for shape in shapes:
            node = _parse_shape(shape, page_h_in, parent_x_in, parent_y_in)
            if node:
                nodes.append(node)
            edge = _parse_connector(shape)
            if edge:
                edges.append(edge)
            # Recurse into grouped shapes, passing this shape's absolute position
            subs = shape.child_shapes
            if subs:
                abs_x = _safe_float(shape.x) + parent_x_in
                abs_y = _safe_float(shape.y) + parent_y_in
                walk(subs, abs_x, abs_y)

    # page.width/height is buggy in this vsdx version — use try/except
    try:
        page_w_in = _safe_float(page.width, default=11.0)
        page_h_in = _safe_float(page.height, default=8.5)
        if page_w_in == 0:
            raise ValueError("zero width")
    except Exception:
        page_w_in = 11.0
        page_h_in = 8.5

    walk(page.child_shapes)

    # If page dimensions were unavailable, derive from shape bounding box
    if page_w_in == 11.0 and page_h_in == 8.5 and nodes:
        page_w_in, page_h_in = _page_bounds_from_shapes(nodes)

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

    Raises:
        ValueError: If the file cannot be parsed as a valid .vsdx file.
    """
    path = Path(path)

    if path.suffix.lower() == ".vsd":
        raise ValueError(
            f"'{path.name}' is a legacy binary .vsd file. "
            "Only the modern .vsdx format is supported. "
            "Open the file in Visio and save as .vsdx to convert it."
        )

    try:
        with vsdx.VisioFile(str(path)) as vis:
            # vsdx does not expose document_properties — use filename as title
            meta = {
                "title": path.stem,
                "author": "",
                "modified": "",
            }
            pages = [_parse_page(p) for p in vis.pages]
    except Exception as exc:
        raise ValueError(f"Could not parse '{path.name}': {exc}") from exc

    return {"meta": meta, "pages": pages}
