# VSDX → HTML Converter

Convert Microsoft Visio files (`.vsdx`) to interactive, standalone HTML — no Visio license or internet connection required.

## Installation

```bash
pip3 install -e .
```

## Usage

```bash
convert diagram.vsdx                    # → diagram.html (same directory)
convert diagram.vsdx -o output.html     # custom output path
convert diagram.vsdx --theme corporate  # with theme
```

### Available themes

| Theme | Description |
|---|---|
| `default` | Preserves Visio colors |
| `corporate` | Professional dark tones with subtle shadows |
| `modern` | Minimalist pastels with rounded corners |

## Architecture

```
.vsdx → parser → JSON graph → renderer → .html
```

| Layer | File | Responsibility |
|---|---|---|
| Parser | `parser/vsdx_parser.py` | Reads .vsdx (ZIP+XML), extracts shapes, connectors, and pages |
| Intermediate | JSON dict | Provider-agnostic graph format (nodes + edges per page) |
| Renderer | `renderer/svg.py` | Generates inline SVG in a standalone HTML file |
| Themes | `themes.py` | Style presets that override Visio colors |

## Known limitations

- **Master shape style inheritance** — complex style inheritance from Visio master pages may differ from the original Visio rendering
- **No cross-diagram navigation** — links between connected diagrams are not supported out of the box
- **Zoom/pan** — simpler than dedicated diagram viewers such as draw.io

## Testing

Generate test files and run a conversion:

```bash
python3 tests/create_test_vsdx.py
python3 convert.py tests/enkel.vsdx
python3 convert.py tests/flersider.vsdx
```
