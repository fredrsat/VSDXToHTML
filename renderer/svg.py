"""
Renderer-strategi: SVG (inline i HTML)

Pipeline: JSON-graf → inline SVG → standalone HTML-fil

Designvalg:
  - Null eksterne avhengigheter. Filen fungerer offline ved å åpne den i en browser.
  - Visio-filer inneholder eksakte koordinater (x, y, w, h) – ingen layout-motor trengs.
  - Zoom og pan håndteres med ~20 linjer vanilla JS via CSS transform-manipulasjon.
  - Flersidig navigasjon via HTML-tabs med ren CSS/JS, ingen rammeverk.
  - Tema-støtte: Theme-objektet overstyrer farger og stil når override_visio_colors=True.

Kjente svakheter (dokumenter i README):
  - Kompleks stilarv fra Visio master shapes kan avvike fra Visio-visning.
  - Klikk-navigasjon mellom koblede diagrammer støttes ikke ut av boksen.
  - Zoom/pan er enklere enn draw.io sin innebygde viewer.
"""

from __future__ import annotations

import html
import json
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from themes import Theme


# ── Fargehåndtering ──────────────────────────────────────────────────────────


def _normalize_color(value: Any, default: str) -> str:
    """
    Normaliserer Visio-fargeverdier til #rrggbb CSS-format.

    Visio kan returnere farger som hex-streng (#rrggbb) eller som et
    desimalt heltall der RGB er pakket som 0xBBGGRR (liten-endian).
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


# ── SVG-primitiver ───────────────────────────────────────────────────────────


def _render_node(node: dict, theme: "Theme", node_index: int) -> str:
    """
    Rendrer én node (shape) som et SVG-element.

    Består av:
      - <rect> for bakgrunn og ramme, med valgfri skygge fra temaet
      - <text> med <tspan>-linjer for innholdet
      - <title> for tooltip (brukes av browser og screen readers)

    Når theme.override_visio_colors=True brukes tema-farger i stedet for
    Visio-farger. Tema-fyllfarger sykles gjennom node_fills-listen slik
    at naboshapes får ulike farger automatisk.
    """
    x = node["x"]
    y = node["y"]
    w = node["w"]
    h = node["h"]
    text = node.get("text", "")
    tooltip = node.get("tooltip", "")
    style = node.get("style", {})

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

    # Enkel tekstbryting: del på whitespace, legg én linje per tspan
    words = text.split()
    lines: list[str] = []
    current = ""
    chars_per_line = max(1, int(w / (font_size * 0.6)))
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

    return (
        f'<g class="node" data-id="{html.escape(node["id"])}">'
        f"{title_el}"
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
        f'rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="1.5" {shadow}/>'
        f'<text x="{x + w / 2:.1f}" y="{text_y_start:.1f}" '
        f'font-size="{font_size}" text-anchor="middle" '
        f'fill="{text_color}" font-family="{font_family}">'
        f"{tspans}</text>"
        f"</g>"
    )


def _render_edge(edge: dict, node_map: dict[str, dict], theme: "Theme") -> str:
    """
    Rendrer én kant (connector) som en SVG-linje mellom to nodes.

    Tegner en rett linje fra senter av kilde-node til senter av mål-node,
    med en pilspiss på mål-enden og valgfri label midtveis.

    Kanter der kilde eller mål ikke finnes i node_map hoppes over stille.
    """
    src = node_map.get(edge["from"])
    tgt = node_map.get(edge["to"])
    if not src or not tgt:
        return ""

    x1 = src["x"] + src["w"] / 2
    y1 = src["y"] + src["h"] / 2
    x2 = tgt["x"] + tgt["w"] / 2
    y2 = tgt["y"] + tgt["h"] / 2
    label = edge.get("label", "")
    color = theme.edge_color

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
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{color}" stroke-width="{theme.edge_width}" marker-end="url(#arrowhead)"/>'
        f"{label_el}"
        f"</g>"
    )


def _render_page_svg(page: dict, theme: "Theme") -> str:
    """
    Bygger et komplett <svg>-element for én side.

    Rekkefølge: kanter tegnes under nodes slik at piler ikke
    overlapper shape-boksene. SVG-definisjoner inkluderer pil-markør
    og valgfri skygge-filter for temaet.
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

    return (
        f'<svg class="diagram-svg" viewBox="0 0 {w:.0f} {h:.0f}" '
        f'width="{w:.0f}" height="{h:.0f}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f"{defs}"
        f'<rect width="100%" height="100%" fill="{theme.page_bg}"/>'
        f"{edge_svgs}"
        f"{node_svgs}"
        f"</svg>"
    )


# ── HTML-wrapper ─────────────────────────────────────────────────────────────


def render_html(graph: dict, theme: "Theme | None" = None) -> str:
    """
    Konverterer en intermediate JSON-graf til en komplett, standalone HTML-fil.

    Filen har null eksterne avhengigheter og fungerer offline.
    Inkluderer:
      - Inline SVG per side med tema-styling
      - Fane-navigasjon for flersidige diagrammer
      - Zoom og pan via mushjul og dra (vanilla JS)
      - Alt-tekst og diagram-beskrivelse fra AI-berikelse hvis tilgjengelig

    Args:
        graph: Intermediate JSON-graf fra parseren (evt. beriket av AI-laget).
        theme: Tema-objekt. Bruker default-tema hvis None.

    Returns:
        Komplett HTML som streng, klar til å skrives til fil.
    """
    from themes import get as get_theme
    if theme is None:
        theme = get_theme("default")

    pages = graph.get("pages", [])
    meta = graph.get("meta", {})
    title = html.escape(meta.get("title", "Diagram"))
    description = html.escape(meta.get("description", ""))

    page_svgs = [_render_page_svg(p, theme) for p in pages]

    # Fane-knapper (bare synlige ved mer enn én side)
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
<html lang="no">
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
      max-width: 100%; max-height: 100%;
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
    <button class="zoom-btn" onclick="zoom(0.2)" title="Zoom inn">+</button>
    <button class="zoom-btn" onclick="zoom(-0.2)" title="Zoom ut">−</button>
    <button class="zoom-btn" onclick="resetZoom()" title="Tilbakestill">⊙</button>
  </div>

  <script>
    var PAGES = {pages_data};
    var currentPage = 0;
    var scale = 1;
    var offsetX = 0, offsetY = 0;
    var isDragging = false;
    var dragStart = {{ x: 0, y: 0 }};

    function showPage(index) {{
      currentPage = index;
      scale = 1; offsetX = 0; offsetY = 0;
      document.querySelectorAll('.tab-btn').forEach(function(b, i) {{
        b.classList.toggle('active', i === index);
      }});
      var container = document.getElementById('svg-container');
      container.innerHTML = PAGES[index].svg;
      var svg = container.querySelector('svg');
      if (svg && PAGES[index].alt_text) {{
        svg.setAttribute('aria-label', PAGES[index].alt_text);
        svg.setAttribute('role', 'img');
      }}
      applyTransform();
    }}

    function getSvg() {{ return document.querySelector('#svg-container svg'); }}

    function applyTransform() {{
      var svg = getSvg();
      if (svg) {{
        svg.style.transform =
          'translate(' + offsetX + 'px, ' + offsetY + 'px) scale(' + scale + ')';
      }}
    }}

    function zoom(delta) {{
      scale = Math.min(5, Math.max(0.1, scale + delta));
      applyTransform();
    }}

    function resetZoom() {{
      scale = 1; offsetX = 0; offsetY = 0;
      applyTransform();
    }}

    document.getElementById('viewport').addEventListener('wheel', function(e) {{
      e.preventDefault();
      zoom(e.deltaY < 0 ? 0.1 : -0.1);
    }}, {{ passive: false }});

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

    if (PAGES.length > 0) showPage(0);
  </script>
</body>
</html>"""
