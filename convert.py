"""
VSDX → HTML converter

Bruk:
    python3 convert.py diagram.vsdx
    python3 convert.py diagram.vsdx --theme hso
    python3 convert.py diagram.vsdx --theme corporate -o output.html

Tilgjengelige temaer: default, corporate, hso, modern
"""

import argparse
import sys
from pathlib import Path

from parser.vsdx_parser import parse_vsdx
from renderer.svg import render_html
from themes import get as get_theme, THEMES


def main() -> None:
    p = argparse.ArgumentParser(
        description="Konverter .vsdx til standalone HTML.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Tilgjengelige temaer: {', '.join(THEMES.keys())}",
    )
    p.add_argument("input", help=".vsdx-fil som skal konverteres")
    p.add_argument("-o", "--output", help="Utdatafil (standard: samme navn som input med .html)")
    p.add_argument(
        "--theme",
        default="default",
        metavar="NAVN",
        help="Styling-tema (standard: default)",
    )
    args = p.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Feil: finner ikke {input_path}", file=sys.stderr)
        sys.exit(1)
    if input_path.suffix.lower() != ".vsdx":
        print("Feil: filen må være en .vsdx-fil.", file=sys.stderr)
        sys.exit(1)

    try:
        theme = get_theme(args.theme)
    except ValueError as e:
        print(f"Feil: {e}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output) if args.output else input_path.with_suffix(".html")

    print(f"Parser {input_path} …")
    graph = parse_vsdx(input_path)

    print(f"Rendrer SVG (tema: {theme.name}) …")
    output = render_html(graph, theme=theme)

    output_path.write_text(output, encoding="utf-8")
    print(f"Ferdig: {output_path}")


if __name__ == "__main__":
    main()
