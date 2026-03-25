"""
VSDX → HTML converter

Usage:
    convert diagram.vsdx
    convert diagram.vsdx --theme corporate
    convert diagram.vsdx --theme modern -o output.html
    convert *.vsdx                          # batch conversion
    convert --list-themes                   # show available themes
    convert --version                       # show version
"""

import argparse
import glob
import sys
from pathlib import Path

from parser.vsdx_parser import parse_vsdx
from renderer.svg import render_html
from themes import get as get_theme, THEMES

__version__ = "0.1.0"


def convert_file(input_path: Path, output_path: Path, theme_name: str) -> bool:
    """
    Converts a single .vsdx file to HTML.

    Returns True on success, False on failure (error is printed to stderr).
    """
    try:
        theme = get_theme(theme_name)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return False

    print(f"Parsing {input_path} ...")
    try:
        graph = parse_vsdx(input_path)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return False

    print(f"Rendering SVG (theme: {theme.name}) ...")
    output = render_html(graph, theme=theme)
    output_path.write_text(output, encoding="utf-8")
    print(f"Done: {output_path}")
    return True


def main() -> None:
    p = argparse.ArgumentParser(
        description="Convert .vsdx files to standalone HTML.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Available themes: {', '.join(THEMES.keys())}",
    )
    p.add_argument(
        "inputs",
        nargs="*",
        help=".vsdx file(s) to convert (supports glob patterns, e.g. *.vsdx)",
    )
    p.add_argument(
        "-o", "--output",
        help="Output file (only valid when converting a single file)",
    )
    p.add_argument(
        "--theme",
        default="default",
        metavar="NAME",
        help="Style theme (default: default)",
    )
    p.add_argument(
        "--list-themes",
        action="store_true",
        help="List available themes and exit",
    )
    p.add_argument(
        "--version",
        action="version",
        version=f"vsdx-to-html {__version__}",
    )
    args = p.parse_args()

    if args.list_themes:
        print("Available themes:")
        for name in THEMES:
            t = THEMES[name]
            override = "overrides Visio colors" if t.override_visio_colors else "preserves Visio colors"
            print(f"  {name:<12} {override}")
        return

    if not args.inputs:
        p.print_help()
        sys.exit(1)

    # Expand glob patterns (e.g. *.vsdx) and collect all input files
    files: list[Path] = []
    for pattern in args.inputs:
        matched = glob.glob(pattern)
        if matched:
            files.extend(Path(f) for f in matched)
        else:
            files.append(Path(pattern))

    if args.output and len(files) > 1:
        print("Error: --output can only be used when converting a single file.", file=sys.stderr)
        sys.exit(1)

    errors = 0
    for input_path in files:
        if not input_path.exists():
            print(f"Error: file not found: {input_path}", file=sys.stderr)
            errors += 1
            continue
        if input_path.suffix.lower() not in (".vsdx", ".vsd"):
            print(f"Error: '{input_path.name}' is not a .vsdx file — skipping.", file=sys.stderr)
            errors += 1
            continue

        output_path = Path(args.output) if args.output else input_path.with_suffix(".html")
        success = convert_file(input_path, output_path, args.theme)
        if not success:
            errors += 1

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
