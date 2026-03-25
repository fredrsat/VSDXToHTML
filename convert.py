"""
VSDX → HTML converter

Usage:
    python3 convert.py diagram.vsdx
    python3 convert.py diagram.vsdx --theme corporate
    python3 convert.py diagram.vsdx --theme modern -o output.html

Available themes: default, corporate, modern
"""

import argparse
import sys
from pathlib import Path

from parser.vsdx_parser import parse_vsdx
from renderer.svg import render_html
from themes import get as get_theme, THEMES


def main() -> None:
    p = argparse.ArgumentParser(
        description="Convert a .vsdx file to standalone HTML.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Available themes: {', '.join(THEMES.keys())}",
    )
    p.add_argument("input", help=".vsdx file to convert")
    p.add_argument("-o", "--output", help="Output file (default: same name as input with .html)")
    p.add_argument(
        "--theme",
        default="default",
        metavar="NAME",
        help="Style theme (default: default)",
    )
    args = p.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)
    if input_path.suffix.lower() != ".vsdx":
        print("Error: input file must be a .vsdx file.", file=sys.stderr)
        sys.exit(1)

    try:
        theme = get_theme(args.theme)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output) if args.output else input_path.with_suffix(".html")

    print(f"Parsing {input_path} ...")
    graph = parse_vsdx(input_path)

    print(f"Rendering SVG (theme: {theme.name}) ...")
    output = render_html(graph, theme=theme)

    output_path.write_text(output, encoding="utf-8")
    print(f"Done: {output_path}")


if __name__ == "__main__":
    main()
