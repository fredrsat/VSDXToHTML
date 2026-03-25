# VSDX → HTML Converter

Convert Microsoft Visio files (`.vsdx`) to interactive, standalone HTML — no Visio license or internet connection required.

## Getting started after clone

```bash
# 1. Install the vsdx library (not on PyPI — install from GitHub)
pip3 install git+https://github.com/dave-howard/vsdx.git

# 2. Install the converter as a local editable package
pip3 install -e .

# 3. Convert a file
convert diagram.vsdx
```

## Usage

```bash
convert diagram.vsdx                    # → diagram.html (same directory)
convert diagram.vsdx -o output.html     # custom output path
convert diagram.vsdx --theme corporate  # with theme
convert *.vsdx                          # batch conversion
convert --list-themes                   # show available themes
convert --version                       # show version
```

### Available themes

| Theme | Description |
|---|---|
| `default` | Preserves Visio colors |
| `corporate` | Professional dark tones with subtle shadows |
| `modern` | Minimalist pastels with rounded corners |

## Testing

Generate test files and run the test suite:

```bash
python3 tests/create_test_vsdx.py      # generate test .vsdx files (run once)
python3 -m pytest tests/test_converter.py -v
```

The test files are excluded from version control (`.gitignore`), so `create_test_vsdx.py` must be run after each fresh clone.

### Test coverage

| Class | What is tested |
|---|---|
| `TestParser` | Parsing nodes, edges, coordinates, text, multi-page, empty pages, error handling |
| `TestRenderer` | HTML output, SVG content, themes, tab navigation, auto-fit JS, orthogonal paths |
| `TestThemes` | Theme lookup, required fields, color override flags |

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

- **Legacy `.vsd` format** — binary `.vsd` files are not supported; open in Visio and save as `.vsdx` first
- **Master shape style inheritance** — complex style inheritance from Visio master pages may differ from the original Visio rendering
- **No cross-diagram navigation** — links between connected diagrams are not supported out of the box
- **Zoom/pan** — simpler than dedicated diagram viewers such as draw.io
