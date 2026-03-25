"""
Renderer strategy: SVG (inline in HTML)

Pipeline: JSON graph → inline SVG → standalone HTML file

Design decisions:
  - Zero external dependencies. The output file works offline by opening it in a browser.
  - Visio files contain exact coordinates (x, y, w, h) — no layout engine needed.
  - Zoom and pan handled with vanilla JS via CSS transform manipulation.
  - Auto-fit on load: SVG scales to fill the viewport on first render.
  - Multi-page navigation via HTML tabs, no framework required.
  - Theme support: Theme object overrides colors and style when override_visio_colors=True.

Known limitations (document in README):
  - Complex style inheritance from Visio master shapes may differ from original Visio rendering.
  - Click-navigation between linked diagrams is not supported out of the box.
  - Zoom/pan is simpler than dedicated diagram viewers such as draw.io.
"""

from __future__ import annotations

import html
import json
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from themes import Theme


# ── Color handling ───────────────────────────────────────────────────────────


def _normalize_color(value: Any, default: str) -> str:
    """
    Normalizes Visio color values to #rrggbb CSS format.

    Visio may return colors as a hex string (#rrggbb) or as a decimal
    integer where RGB is packed as 0xBBGGRR (little-endian).
    """
    if not value:
        return default
    s = str(value).strip()
    if s.startswith("#") and len(s) in (4, 7):
        return s
    try:
        v = int(s)
        r = v & 0xFF
        g = (v >> 8) & 0xFF
        b = (v >> 16) & 0xFF
        return f"#{r:02x}{g:02x}{b:02x}"
    except ValueError:
        return default


# ── SVG primitives ───────────────────────────────────────────────────────────


def _render_node(node: dict, theme: "Theme", node_index: int) -> str:
    """
    Renders a single node (shape) as an SVG element.

    Consists of:
      - <clipPath> to prevent text from overflowing the shape bounds
      - <rect> for background and border, with optional shadow from the theme
      - <text> with <tspan> lines for the content, clipped to shape bounds
      - <title> for tooltip (used by browser and screen readers)

    When theme.override_visio_colors=True, theme colors are used instead of
    Visio colors. Theme fill colors cycle through node_fills so adjacent
    shapes get different colors automatically.
    """
    x = node["x"]
    y = node["y"]
    w = node["w"]
    h = node["h"]
    text = node.get("text", "")
    tooltip = node.get("tooltip", "")
    style = node.get("style", {})
    node_id = node["id"]

    if theme.override_visio_colors:
        fill = theme.node_fills[node_index % len(theme.node_fills)]
        stroke = theme.node_stroke
        font_size = theme.node_font_size
        text_color = theme.node_text
        font_family = theme.node_font
        radius = theme.node_radius
    else:
        fill = _normalize_color(style.get("fill"), "#dae8fc")
        stroke = _normalize_color(style.get("stroke"), "#6c8ebf")
        font_size = style.get("font_size", 11)
        text_color = "#222222"
        font_family = "system-ui, sans-serif"
        radius = 4

    # Simple word wrap: split on whitespace, one line per tspan
    words = text.split()
    lines: list[str] = []
    current = ""
    padding = font_size * 0.8
    chars_per_line = max(1, int((w - padding * 2) / (font_size * 0.6)))
    for word in words:
        if len(current) + len(word) + 1 <= chars_per_line:
            current = (current + " " + word).strip()
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    if not lines:
        lines = [""]

    line_height = font_size * 1.3
    total_text_h = len(lines) * line_height
    text_y_start = y + h / 2 - total_text_h / 2 + font_size

    tspans = "".join(
        f'<tspan x="{x + w / 2:.1f}" dy="{0 if i == 0 else line_height:.1f}">'
        f"{html.escape(line)}</tspan>"
        for i, line in enumerate(lines)
    )

    title_el = f"<title>{html.escape(tooltip or text)}</title>" if (tooltip or text) else ""
    shadow = 'filter="url(#shadow)"' if theme.node_shadow else ""
    clip_id = f"clip_{html.escape(node_id)}"

    return (
        f'<clipPath id="{clip_id}">'
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}"/>'
        f"</clipPath>"
        f'<g class="node" data-id="{html.escape(node_id)}">'
        f"{title_el}"
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
        f'rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="1.5" {shadow}/>'
        f'<text x="{x + w / 2:.1f}" y="{text_y_start:.1f}" '
        f'font-size="{font_size}" text-anchor="middle" '
        f'fill="{text_color}" font-family="{font_family}" '
        f'clip-path="url(#{clip_id})">'
        f"{tspans}</text>"
        f"</g>"
    )


def _orthogonal_path(x1: float, y1: float, x2: float, y2: float) -> str:
    """
    Returns an SVG path string for an orthogonal (L-shaped) connector.

    Routes horizontally from the source midpoint, then vertically to the
    target midpoint. This avoids diagonal lines crossing over shapes.
    """
    mx = (x1 + x2) / 2
    return f"M {x1:.1f} {y1:.1f} L {mx:.1f} {y1:.1f} L {mx:.1f} {y2:.1f} L {x2:.1f} {y2:.1f}"


def _render_edge(edge: dict, node_map: dict[str, dict], theme: "Theme") -> str:
    """
    Renders a single connector as an orthogonal SVG path between two nodes.

    Routes from the right edge of the source to the left edge of the target
    when the target is to the right; otherwise falls back to center-to-center
    routing. Includes an arrowhead at the target end and an optional label.

    Edges where source or target are not found in node_map are skipped silently.
    """
    src = node_map.get(edge["from"])
    tgt = node_map.get(edge["to"])
    if not src or not tgt:
        return ""

    # Connect from the closest horizontal edges for cleaner routing
    if tgt["x"] >= src["x"]:
        x1 = src["x"] + src["w"]
        x2 = tgt["x"]
    else:
        x1 = src["x"]
        x2 = tgt["x"] + tgt["w"]

    y1 = src["y"] + src["h"] / 2
    y2 = tgt["y"] + tgt["h"] / 2
    label = edge.get("label", "")
    color = theme.edge_color
    path = _orthogonal_path(x1, y1, x2, y2)

    label_el = ""
    if label:
        mx = (x1 + x2) / 2
        my = (y1 + y2) / 2 - 6
        label_el = (
            f'<text x="{mx:.1f}" y="{my:.1f}" font-size="10" '
            f'text-anchor="middle" fill="{color}" font-family="{theme.node_font}">'
            f"{html.escape(label)}</text>"
        )

    return (
        f'<g class="edge">'
        f'<path d="{path}" stroke="{color}" stroke-width="{theme.edge_width}" '
        f'fill="none" marker-end="url(#arrowhead)"/>'
        f"{label_el}"
        f"</g>"
    )


def _render_page_svg(page: dict, theme: "Theme") -> str:
    """
    Builds a complete <svg> element for a single page.

    Edges are drawn before nodes so arrowheads do not overlap shape boxes.
    SVG defs include the arrowhead marker and an optional drop-shadow filter.
    """
    w = page["width"]
    h = page["height"]
    nodes = page.get("nodes", [])
    edges = page.get("edges", [])

    node_map = {n["id"]: n for n in nodes}

    shadow_filter = """
  <filter id="shadow" x="-10%" y="-10%" width="120%" height="130%">
    <feDropShadow dx="2" dy="3" stdDeviation="3" flood-color="rgba(0,0,0,0.18)"/>
  </filter>""" if theme.node_shadow else ""

    defs = f"""<defs>{shadow_filter}
  <marker id="arrowhead" markerWidth="8" markerHeight="6"
          refX="8" refY="3" orient="auto">
    <polygon points="0 0, 8 3, 0 6" fill="{theme.edge_color}"/>
  </marker>
</defs>"""

    edge_svgs = "".join(_render_edge(e, node_map, theme) for e in edges)
    node_svgs = "".join(_render_node(n, theme, i) for i, n in enumerate(nodes))

    empty_msg = ""
    if not nodes:
        empty_msg = (
            f'<text x="{w/2:.0f}" y="{h/2:.0f}" text-anchor="middle" '
            f'font-size="14" fill="#aaa" font-family="system-ui, sans-serif">'
            f"No shapes on this page</text>"
        )

    return (
        f'<svg class="diagram-svg" viewBox="0 0 {w:.0f} {h:.0f}" '
        f'data-width="{w:.0f}" data-height="{h:.0f}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f"{defs}"
        f'<rect width="100%" height="100%" fill="{theme.page_bg}"/>'
        f"{edge_svgs}"
        f"{node_svgs}"
        f"{empty_msg}"
        f"</svg>"
    )


# ── HTML wrapper ─────────────────────────────────────────────────────────────


def render_html(graph: dict, theme: "Theme | None" = None) -> str:
    """
    Converts an intermediate JSON graph to a complete, standalone HTML file.

    The output has zero external dependencies and works offline.
    Includes:
      - Inline SVG per page with theme styling and text clipping
      - Orthogonal connectors for cleaner routing
      - Auto-fit on load: SVG scales to fill the viewport
      - Tab navigation for multi-page diagrams
      - Zoom and pan via mouse wheel and drag (vanilla JS)
      - Alt text and diagram description from AI enrichment if available

    Args:
        graph: Intermediate JSON graph from the parser (optionally AI-enriched).
        theme: Theme object. Uses default theme if None.

    Returns:
        Complete HTML string, ready to write to a file.
    """
    from themes import get as get_theme
    if theme is None:
        theme = get_theme("default")

    pages = graph.get("pages", [])
    meta = graph.get("meta", {})
    title = html.escape(meta.get("title", "Diagram"))
    description = html.escape(meta.get("description", ""))

    page_svgs = [_render_page_svg(p, theme) for p in pages]

    # Tab buttons — only visible when there is more than one page
    tab_display = "flex" if len(pages) > 1 else "none"
    tab_buttons = "".join(
        f'<button class="tab-btn{" active" if i == 0 else ""}" '
        f'onclick="showPage({i})">{html.escape(p["name"])}</button>'
        for i, p in enumerate(pages)
    )

    pages_data = json.dumps(
        [
            {
                "name": p["name"],
                "svg": svg,
                "alt_text": p.get("alt_text", ""),
            }
            for p, svg in zip(pages, page_svgs)
        ],
        ensure_ascii=False,
    )

    description_block = (
        f'<p class="description">{description}</p>' if description else ""
    )

    has_tabs = len(pages) > 1
    viewport_offset = "90px" if (description or has_tabs) else "56px"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: {theme.node_font}; background: {theme.html_bg}; }}

    header {{
      background: {theme.header_bg}; color: {theme.header_text};
      padding: 12px 20px;
    }}
    header h1 {{ font-size: 1rem; font-weight: 600; }}
    .description {{ font-size: .82rem; opacity: 0.75; margin-top: 4px; }}

    .tab-bar {{
      display: {tab_display};
      gap: 4px; padding: 8px 12px;
      background: #fff; border-bottom: 1px solid #ddd;
    }}
    .tab-btn {{
      padding: 5px 14px; border: 1px solid #ccc; border-radius: 4px;
      background: #f0f0f0; cursor: pointer; font-size: .83rem;
    }}
    .tab-btn.active {{
      background: {theme.header_bg}; color: {theme.header_text};
      border-color: {theme.header_bg};
    }}

    #viewport {{
      width: 100%;
      height: calc(100vh - {viewport_offset});
      overflow: hidden; cursor: grab; background: {theme.html_bg};
      display: flex; align-items: center; justify-content: center;
    }}
    #viewport:active {{ cursor: grabbing; }}

    .diagram-svg {{
      transform-origin: center center;
    }}

    .zoom-controls {{
      position: fixed; bottom: 20px; right: 20px;
      display: flex; flex-direction: column; gap: 4px;
    }}
    .zoom-btn {{
      width: 32px; height: 32px; border: 1px solid #ccc;
      border-radius: 4px; background: #fff; cursor: pointer;
      font-size: 1.1rem; display: flex; align-items: center;
      justify-content: center; box-shadow: 0 1px 4px rgba(0,0,0,.1);
    }}
    .zoom-btn:hover {{ background: #f0f0f0; }}
  </style>
</head>
<body>
  <header>
    <h1>{title}</h1>
    {description_block}
  </header>

  <div class="tab-bar">{tab_buttons}</div>

  <div id="viewport">
    <div id="svg-container"></div>
  </div>

  <div class="zoom-controls">
    <button class="zoom-btn" onclick="zoom(0.2)" title="Zoom in">+</button>
    <button class="zoom-btn" onclick="zoom(-0.2)" title="Zoom out">−</button>
    <button class="zoom-btn" onclick="fitToViewport()" title="Fit to window">⊙</button>
  </div>

  <script>
    var PAGES = {pages_data};
    var currentPage = 0;
    var scale = 1;
    var offsetX = 0, offsetY = 0;
    var isDragging = false;
    var dragStart = {{ x: 0, y: 0 }};

    function getSvg() {{ return document.querySelector('#svg-container svg'); }}

    function applyTransform() {{
      var svg = getSvg();
      if (svg) {{
        svg.style.transform =
          'translate(' + offsetX + 'px, ' + offsetY + 'px) scale(' + scale + ')';
      }}
    }}

    /** Scales the SVG to fill 90% of the viewport while preserving aspect ratio. */
    function fitToViewport() {{
      var svg = getSvg();
      if (!svg) return;
      var vp = document.getElementById('viewport');
      var svgW = parseFloat(svg.getAttribute('data-width'));
      var svgH = parseFloat(svg.getAttribute('data-height'));
      scale = Math.min(vp.clientWidth / svgW, vp.clientHeight / svgH) * 0.9;
      offsetX = 0;
      offsetY = 0;
      applyTransform();
    }}

    function showPage(index) {{
      currentPage = index;
      document.querySelectorAll('.tab-btn').forEach(function(b, i) {{
        b.classList.toggle('active', i === index);
      }});
      var container = document.getElementById('svg-container');
      container.innerHTML = PAGES[index].svg;
      var svg = getSvg();
      if (svg && PAGES[index].alt_text) {{
        svg.setAttribute('aria-label', PAGES[index].alt_text);
        svg.setAttribute('role', 'img');
      }}
      fitToViewport();
    }}

    function zoom(delta) {{
      scale = Math.min(5, Math.max(0.1, scale + delta));
      applyTransform();
    }}

    // Mouse wheel zoom
    document.getElementById('viewport').addEventListener('wheel', function(e) {{
      e.preventDefault();
      zoom(e.deltaY < 0 ? 0.1 : -0.1);
    }}, {{ passive: false }});

    // Drag to pan
    var vp = document.getElementById('viewport');
    vp.addEventListener('mousedown', function(e) {{
      isDragging = true;
      dragStart = {{ x: e.clientX - offsetX, y: e.clientY - offsetY }};
    }});
    window.addEventListener('mousemove', function(e) {{
      if (!isDragging) return;
      offsetX = e.clientX - dragStart.x;
      offsetY = e.clientY - dragStart.y;
      applyTransform();
    }});
    window.addEventListener('mouseup', function() {{ isDragging = false; }});

    // Init: show first page, auto-fit after layout is complete
    if (PAGES.length > 0) {{
      document.getElementById('svg-container').innerHTML = PAGES[0].svg;
      var initSvg = getSvg();
      if (initSvg && PAGES[0].alt_text) {{
        initSvg.setAttribute('aria-label', PAGES[0].alt_text);
        initSvg.setAttribute('role', 'img');
      }}
      window.addEventListener('load', fitToViewport);
    }}
  </script>
</body>
</html>"""
