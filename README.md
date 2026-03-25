# VSDX → HTML Converter

Konverterer Microsoft Visio-filer (`.vsdx`) til interaktiv, standalone HTML – uten Visio-lisens og uten internettilgang.

## Installasjon

```bash
pip3 install -e .
```

## Bruk

```bash
convert diagram.vsdx                        # → diagram.html (samme mappe)
convert diagram.vsdx -o output.html         # valgfri utdatasti
convert diagram.vsdx --theme corporate      # med tema
```

### Tilgjengelige temaer

| Tema | Beskrivelse |
|---|---|
| `default` | Bevarer Visio-farger |
| `corporate` | Profesjonell, mørke toner, subtile skygger |
| `modern` | Minimalistisk, pasteller, runde hjørner |

## Arkitektur

```
.vsdx → parser → JSON-graf → renderer → .html
```

| Lag | Fil | Ansvar |
|---|---|---|
| Parser | `parser/vsdx_parser.py` | Leser .vsdx (ZIP+XML), ekstraherer shapes, koblinger, sider |
| Intermediate | JSON-dict | Provider-uavhengig grafformat (nodes + edges per side) |
| Renderer | `renderer/svg.py` | Genererer inline SVG i standalone HTML |
| Temaer | `themes.py` | Styling-maler som overstyrer Visio-farger |

## Kjente svakheter

- **Stilarv fra master shapes** – kompleks stilarv fra Visio master pages kan gi avvik fra Visio-visning
- **Ingen klikk-navigasjon** – lenker mellom koblede diagrammer støttes ikke ut av boksen
- **Zoom/pan** – enklere enn dedikerte diagram-viewere (draw.io o.l.)

## Testing

Generer test-filer:

```bash
python3 tests/create_test_vsdx.py
python3 convert.py tests/enkel.vsdx
python3 convert.py tests/flersider.vsdx
```
