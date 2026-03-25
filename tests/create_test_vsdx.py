"""
Genererer test-.vsdx-filer for utvikling og testing.

Siden python-vsdx kun støtter lesing, bygger vi .vsdx-filer manuelt
som ZIP-arkiver med OOXML-struktur.

Kjør:
    python tests/create_test_vsdx.py
    → tests/enkel.vsdx        (3 shapes, 2 koblinger, én side)
    → tests/flersider.vsdx    (2 sider med ulike shapes)
"""

import zipfile
import textwrap
from pathlib import Path


# ── XML-maler ────────────────────────────────────────────────────────────────

CONTENT_TYPES = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/visio/document.xml"
    ContentType="application/vnd.ms-visio.drawing.main+xml"/>
  <Override PartName="/visio/pages/pages.xml"
    ContentType="application/vnd.ms-visio.pages+xml"/>
  {page_overrides}
</Types>"""

RELS = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.microsoft.com/visio/2010/relationships/document"
    Target="visio/document.xml"/>
</Relationships>"""

DOCUMENT_XML = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<VisioDocument xmlns="http://schemas.microsoft.com/office/visio/2012/main">
  <DocumentProperties>
    <Creator>Test</Creator>
    <Title>{title}</Title>
  </DocumentProperties>
</VisioDocument>"""

DOCUMENT_RELS = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.microsoft.com/visio/2010/relationships/pages"
    Target="pages/pages.xml"/>
</Relationships>"""

PAGES_XML = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Pages xmlns="http://schemas.microsoft.com/office/visio/2012/main"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  {page_elements}
</Pages>"""

PAGES_RELS = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  {relationships}
</Relationships>"""

PAGE_XML = """\
<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<PageContents xmlns="http://schemas.microsoft.com/office/visio/2012/main"
              xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
              xml:space="preserve">
  <Shapes>
    {shapes}
  </Shapes>
  <Connects>
    {connects}
  </Connects>
</PageContents>"""


# ── Hjelpefunksjoner ─────────────────────────────────────────────────────────

def shape(id: int, text: str, pin_x: float, pin_y: float,
          width: float = 1.5, height: float = 0.6,
          fill: str = "#dae8fc", stroke: str = "#6c8ebf") -> str:
    """Lager XML for én rektangulær shape med Cell-basert format (vsdx-standard)."""
    return textwrap.dedent(f"""\
        <Shape ID="{id}" Type="Shape">
          <Cell N="PinX" V="{pin_x}"/>
          <Cell N="PinY" V="{pin_y}"/>
          <Cell N="Width" V="{width}"/>
          <Cell N="Height" V="{height}"/>
          <Cell N="FillForegnd" V="{fill}"/>
          <Cell N="LineColor" V="{stroke}"/>
          <Text>{text}</Text>
        </Shape>""")


def connector(id: int, from_id: int, to_id: int) -> tuple[str, str]:
    """Lager XML for én connector. Returnerer (shape_xml, connect_xml)."""
    shape_xml = textwrap.dedent(f"""\
        <Shape ID="{id}" Type="Edge">
          <Cell N="PinX" V="0"/>
          <Cell N="PinY" V="0"/>
          <Cell N="Width" V="0"/>
          <Cell N="Height" V="0"/>
        </Shape>""")
    connect_xml = textwrap.dedent(f"""\
        <Connect FromSheet="{id}" FromCell="BeginX" ToSheet="{from_id}" ToCell="PinX"/>
        <Connect FromSheet="{id}" FromCell="EndX" ToSheet="{to_id}" ToCell="PinX"/>""")
    return shape_xml, connect_xml


def build_vsdx(output_path: Path, title: str, pages: list[dict]) -> None:
    """
    Bygger en .vsdx-fil fra en liste av side-definisjoner.

    Args:
        output_path: Utdatasti for .vsdx-filen.
        title:       Dokumenttittel.
        pages:       Liste av dicts med nøklene 'name', 'shapes', 'connects'.
    """
    page_overrides = "\n  ".join(
        f'<Override PartName="/visio/pages/page{i+1}.xml" '
        f'ContentType="application/vnd.ms-visio.page+xml"/>'
        for i in range(len(pages))
    )
    page_elements = "\n  ".join(
        f'<Page ID="{i}" Name="{p["name"]}" IsCustomName="1">'
        f'<Rel r:id="rId{i+1}"/></Page>'
        for i, p in enumerate(pages)
    )
    relationships = "\n  ".join(
        f'<Relationship Id="rId{i+1}" '
        f'Type="http://schemas.microsoft.com/visio/2010/relationships/page" '
        f'Target="page{i+1}.xml"/>'
        for i in range(len(pages))
    )

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml",
                    CONTENT_TYPES.format(page_overrides=page_overrides))
        zf.writestr("_rels/.rels", RELS)
        zf.writestr("visio/document.xml", DOCUMENT_XML.format(title=title))
        zf.writestr("visio/_rels/document.xml.rels", DOCUMENT_RELS)
        zf.writestr("visio/pages/pages.xml",
                    PAGES_XML.format(page_elements=page_elements))
        zf.writestr("visio/pages/_rels/pages.xml.rels",
                    PAGES_RELS.format(relationships=relationships))

        for i, page in enumerate(pages):
            zf.writestr(
                f"visio/pages/page{i+1}.xml",
                PAGE_XML.format(
                    shapes="\n    ".join(page["shapes"]),
                    connects="\n    ".join(page["connects"]),
                ),
            )

    print(f"Lagret: {output_path}")


# ── Test 1: Enkel prosessflyt ────────────────────────────────────────────────

def create_enkel(out_dir: Path) -> None:
    """
    Enkel én-sides prosessflyt:
    Pasientregistrering → Triagering → Behandling
    """
    s1 = shape(1, "Pasientregistrering", pin_x=1.5, pin_y=7.0,
               fill="#dae8fc", stroke="#6c8ebf")
    s2 = shape(2, "Triagering",          pin_x=4.5, pin_y=7.0,
               fill="#d5e8d4", stroke="#82b366")
    s3 = shape(3, "Behandling",          pin_x=7.5, pin_y=7.0,
               fill="#fff2cc", stroke="#d6b656")

    c1_shape, c1_conn = connector(4, from_id=1, to_id=2)
    c2_shape, c2_conn = connector(5, from_id=2, to_id=3)

    build_vsdx(
        out_dir / "enkel.vsdx",
        title="Enkel prosessflyt",
        pages=[{
            "name": "Pasientflyt",
            "shapes": [s1, s2, s3, c1_shape, c2_shape],
            "connects": [c1_conn, c2_conn],
        }],
    )


# ── Test 2: Flersiders arkitekturdiagram ─────────────────────────────────────

def create_flersider(out_dir: Path) -> None:
    """
    To-siders diagram:
      Side 1 – Systemkomponenter
      Side 2 – Dataflyt
    """
    # Side 1: Systemkomponenter
    s1 = shape(1, "Nettleser",    pin_x=2.0, pin_y=7.5, fill="#f8cecc", stroke="#b85450")
    s2 = shape(2, "API Gateway",  pin_x=5.0, pin_y=7.5, fill="#dae8fc", stroke="#6c8ebf")
    s3 = shape(3, "Database",     pin_x=8.0, pin_y=7.5, fill="#d5e8d4", stroke="#82b366")
    s4 = shape(4, "Auth Service", pin_x=5.0, pin_y=5.5, fill="#e1d5e7", stroke="#9673a6")
    c1_s, c1_c = connector(5, from_id=1, to_id=2)
    c2_s, c2_c = connector(6, from_id=2, to_id=3)
    c3_s, c3_c = connector(7, from_id=2, to_id=4)

    # Side 2: Dataflyt
    s10 = shape(10, "Klient sender forespørsel", pin_x=2.0, pin_y=8.0,
                fill="#dae8fc", stroke="#6c8ebf")
    s11 = shape(11, "Autentisering",             pin_x=5.0, pin_y=8.0,
                fill="#fff2cc", stroke="#d6b656")
    s12 = shape(12, "Hent data fra DB",          pin_x=8.0, pin_y=8.0,
                fill="#d5e8d4", stroke="#82b366")
    s13 = shape(13, "Returner respons",          pin_x=5.0, pin_y=6.0,
                fill="#f8cecc", stroke="#b85450")
    c10_s, c10_c = connector(14, from_id=10, to_id=11)
    c11_s, c11_c = connector(15, from_id=11, to_id=12)
    c12_s, c12_c = connector(16, from_id=12, to_id=13)

    build_vsdx(
        out_dir / "flersider.vsdx",
        title="Systemarkitektur",
        pages=[
            {
                "name": "Komponenter",
                "shapes": [s1, s2, s3, s4, c1_s, c2_s, c3_s],
                "connects": [c1_c, c2_c, c3_c],
            },
            {
                "name": "Dataflyt",
                "shapes": [s10, s11, s12, s13, c10_s, c11_s, c12_s],
                "connects": [c10_c, c11_c, c12_c],
            },
        ],
    )


# ── Hovedprogram ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    out_dir = Path(__file__).parent
    create_enkel(out_dir)
    create_flersider(out_dir)
    print("Ferdig. Kjør: convert tests/enkel.vsdx")
