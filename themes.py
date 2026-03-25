"""
Style themes for the SVG renderer.

A Theme defines all visual parameters used by the renderer.
The default theme preserves Visio colors. Other themes override everything.
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Theme:
    name: str

    # Page
    page_bg: str = "#ffffff"
    html_bg: str = "#f0f2f5"

    # Header
    header_bg: str = "#1e3a5f"
    header_text: str = "#ffffff"

    # Shapes
    node_fills: list[str] = field(default_factory=lambda: ["#dae8fc"])
    node_stroke: str = "#6c8ebf"
    node_text: str = "#222222"
    node_font: str = "system-ui, sans-serif"
    node_font_size: int = 11
    node_radius: int = 4
    node_shadow: bool = False

    # Connectors
    edge_color: str = "#666666"
    edge_width: float = 1.5

    # When True, theme colors override Visio colors
    override_visio_colors: bool = False


# ── Themes ────────────────────────────────────────────────────────────────────

THEMES: dict[str, Theme] = {}


def register(theme: Theme) -> Theme:
    THEMES[theme.name] = theme
    return theme


# Default — preserves Visio colors
register(Theme(name="default"))


# Corporate — professional dark tones with subtle shadows
register(Theme(
    name="corporate",
    page_bg="#ffffff",
    html_bg="#e8eaed",
    header_bg="#1a2332",
    header_text="#ffffff",
    node_fills=["#1a2332", "#2c3e50", "#34495e", "#1e3a5f", "#2d4a6b"],
    node_stroke="#0d1520",
    node_text="#ffffff",
    node_font="'Segoe UI', system-ui, sans-serif",
    node_font_size=11,
    node_radius=6,
    node_shadow=True,
    edge_color="#444444",
    edge_width=2.0,
    override_visio_colors=True,
))


# Modern — minimalist pastels with rounded corners
register(Theme(
    name="modern",
    page_bg="#ffffff",
    html_bg="#fafafa",
    header_bg="#6c63ff",
    header_text="#ffffff",
    node_fills=["#e8f4fd", "#fef9e7", "#eafaf1", "#fdf2f8", "#fef5e4"],
    node_stroke="#d0d0d0",
    node_text="#333333",
    node_font="'Inter', system-ui, sans-serif",
    node_font_size=11,
    node_radius=10,
    node_shadow=True,
    edge_color="#aaaaaa",
    edge_width=1.5,
    override_visio_colors=True,
))


def get(name: str) -> Theme:
    """Returns the theme with the given name. Raises ValueError for unknown names."""
    if name not in THEMES:
        available = ", ".join(THEMES.keys())
        raise ValueError(f"Unknown theme '{name}'. Available: {available}")
    return THEMES[name]
