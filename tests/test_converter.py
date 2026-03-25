"""
Automated tests for the VSDX → HTML converter.

Run:
    python3 -m pytest tests/test_converter.py -v

Requires test .vsdx files to be generated first:
    python3 tests/create_test_vsdx.py
"""

import sys
from pathlib import Path

import pytest

# Add project root to path so imports work without pip install
sys.path.insert(0, str(Path(__file__).parent.parent))

from parser.vsdx_parser import parse_vsdx
from renderer.svg import render_html
from themes import get as get_theme, THEMES


TESTS_DIR = Path(__file__).parent


# ── Parser tests ──────────────────────────────────────────────────────────────

class TestParser:

    def test_simple_returns_meta_and_pages(self):
        graph = parse_vsdx(TESTS_DIR / "simple.vsdx")
        assert "meta" in graph
        assert "pages" in graph
        assert graph["meta"]["title"] == "simple"

    def test_simple_has_one_page(self):
        graph = parse_vsdx(TESTS_DIR / "simple.vsdx")
        assert len(graph["pages"]) == 1

    def test_simple_has_three_nodes(self):
        graph = parse_vsdx(TESTS_DIR / "simple.vsdx")
        nodes = graph["pages"][0]["nodes"]
        assert len(nodes) == 3

    def test_simple_has_two_edges(self):
        graph = parse_vsdx(TESTS_DIR / "simple.vsdx")
        edges = graph["pages"][0]["edges"]
        assert len(edges) == 2

    def test_node_fields_present(self):
        graph = parse_vsdx(TESTS_DIR / "simple.vsdx")
        node = graph["pages"][0]["nodes"][0]
        for field in ("id", "text", "type", "x", "y", "w", "h", "style"):
            assert field in node, f"Missing field: {field}"

    def test_node_coordinates_are_positive(self):
        graph = parse_vsdx(TESTS_DIR / "simple.vsdx")
        for node in graph["pages"][0]["nodes"]:
            assert node["x"] >= 0, f"Negative x for node {node['id']}"
            assert node["y"] >= 0, f"Negative y for node {node['id']}"
            assert node["w"] > 0, f"Zero width for node {node['id']}"
            assert node["h"] > 0, f"Zero height for node {node['id']}"

    def test_node_text_extracted(self):
        graph = parse_vsdx(TESTS_DIR / "simple.vsdx")
        texts = [n["text"] for n in graph["pages"][0]["nodes"]]
        assert "Registration" in texts
        assert "Triage" in texts
        assert "Treatment" in texts

    def test_edge_references_valid_nodes(self):
        graph = parse_vsdx(TESTS_DIR / "simple.vsdx")
        page = graph["pages"][0]
        node_ids = {n["id"] for n in page["nodes"]}
        for edge in page["edges"]:
            assert edge["from"] in node_ids, f"Edge from unknown node: {edge['from']}"
            assert edge["to"] in node_ids, f"Edge to unknown node: {edge['to']}"

    def test_multipage_has_two_pages(self):
        graph = parse_vsdx(TESTS_DIR / "multipage.vsdx")
        assert len(graph["pages"]) == 2

    def test_multipage_page_names(self):
        graph = parse_vsdx(TESTS_DIR / "multipage.vsdx")
        names = [p["name"] for p in graph["pages"]]
        assert "Components" in names
        assert "Data Flow" in names

    def test_empty_page_has_no_nodes(self):
        graph = parse_vsdx(TESTS_DIR / "empty_page.vsdx")
        assert graph["pages"][0]["nodes"] == []
        assert graph["pages"][0]["edges"] == []

    def test_no_text_shapes_have_empty_text(self):
        graph = parse_vsdx(TESTS_DIR / "no_text.vsdx")
        for node in graph["pages"][0]["nodes"]:
            assert node["text"] == ""

    def test_labeled_edges_have_labels(self):
        graph = parse_vsdx(TESTS_DIR / "labeled_edges.vsdx")
        labels = [e["label"] for e in graph["pages"][0]["edges"]]
        assert "yes" in labels
        assert "no" in labels

    def test_large_diagram_has_twenty_nodes(self):
        graph = parse_vsdx(TESTS_DIR / "large.vsdx")
        assert len(graph["pages"][0]["nodes"]) == 20

    def test_vsd_raises_value_error(self, tmp_path):
        fake_vsd = tmp_path / "test.vsd"
        fake_vsd.write_bytes(b"fake")
        with pytest.raises(ValueError, match=".vsd"):
            parse_vsdx(fake_vsd)

    def test_corrupt_file_raises_value_error(self, tmp_path):
        bad = tmp_path / "bad.vsdx"
        bad.write_bytes(b"not a zip file")
        with pytest.raises(ValueError):
            parse_vsdx(bad)


# ── Renderer tests ────────────────────────────────────────────────────────────

class TestRenderer:

    def test_output_is_valid_html(self):
        graph = parse_vsdx(TESTS_DIR / "simple.vsdx")
        output = render_html(graph)
        assert output.startswith("<!DOCTYPE html>")
        assert "</html>" in output

    def test_output_contains_title(self):
        graph = parse_vsdx(TESTS_DIR / "simple.vsdx")
        output = render_html(graph)
        assert "simple" in output

    def test_output_contains_shape_text(self):
        graph = parse_vsdx(TESTS_DIR / "simple.vsdx")
        output = render_html(graph)
        assert "Registration" in output
        assert "Triage" in output
        assert "Treatment" in output

    def test_output_contains_svg(self):
        graph = parse_vsdx(TESTS_DIR / "simple.vsdx")
        output = render_html(graph)
        assert "<svg" in output

    def test_empty_page_renders_without_error(self):
        graph = parse_vsdx(TESTS_DIR / "empty_page.vsdx")
        output = render_html(graph)
        assert "No shapes on this page" in output

    def test_multipage_output_contains_tab_buttons(self):
        graph = parse_vsdx(TESTS_DIR / "multipage.vsdx")
        output = render_html(graph)
        assert "Components" in output
        assert "Data Flow" in output
        assert "tab-btn" in output

    def test_default_theme_does_not_override_visio_colors(self):
        graph = parse_vsdx(TESTS_DIR / "simple.vsdx")
        theme = get_theme("default")
        assert not theme.override_visio_colors

    def test_corporate_theme_applied(self):
        graph = parse_vsdx(TESTS_DIR / "simple.vsdx")
        theme = get_theme("corporate")
        output = render_html(graph, theme=theme)
        assert theme.header_bg in output

    def test_modern_theme_applied(self):
        graph = parse_vsdx(TESTS_DIR / "simple.vsdx")
        theme = get_theme("modern")
        output = render_html(graph, theme=theme)
        assert theme.header_bg in output

    def test_output_contains_fit_to_viewport_js(self):
        graph = parse_vsdx(TESTS_DIR / "simple.vsdx")
        output = render_html(graph)
        assert "fitToViewport" in output

    def test_output_contains_orthogonal_path(self):
        graph = parse_vsdx(TESTS_DIR / "simple.vsdx")
        output = render_html(graph)
        # SVGs are JSON-encoded in the PAGES variable, so " is escaped as \"
        # Orthogonal connectors use <path> not <line>
        assert '<path d=\\"M' in output


# ── Theme tests ───────────────────────────────────────────────────────────────

class TestThemes:

    def test_all_expected_themes_exist(self):
        for name in ("default", "corporate", "modern"):
            assert name in THEMES

    def test_unknown_theme_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown theme"):
            get_theme("nonexistent")

    def test_default_theme_preserves_visio_colors(self):
        assert not get_theme("default").override_visio_colors

    def test_corporate_theme_overrides_colors(self):
        assert get_theme("corporate").override_visio_colors

    def test_modern_theme_overrides_colors(self):
        assert get_theme("modern").override_visio_colors

    def test_all_themes_have_required_fields(self):
        required = ("name", "page_bg", "html_bg", "header_bg", "header_text",
                    "node_fills", "node_stroke", "node_text", "edge_color")
        for name, theme in THEMES.items():
            for field in required:
                assert hasattr(theme, field), f"Theme '{name}' missing field: {field}"
