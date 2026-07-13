"""
Generic Preprint format plugin.

Same visual layout as CrisPRO Preprint (Computer Modern / Times New Roman,
single-column, bold headings, justified body, booktabs tables, hanging-indent
references) but without CrisPRO-specific branding:
- No "For Research Use Only" footer
- No CrisPRO affiliation formatting
- Suitable for any preprint server (bioRxiv, arXiv, medRxiv, etc.)
"""

from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from typing import Optional

from app.citations.reference_engine import resolve_references
from app.formats._image_helper import add_image_to_doc
# Reuse all item-level rendering from crispro — only footer/branding differs
from app.formats.crispro import (
    _add_item as _crispro_add_item,
    _set_line_spacing,
    _BODY_FONT,
    _BODY_SIZE,
    _LINE_SPACING,
)

FORMAT_NAME = "Generic Preprint"
FORMAT_SUFFIX = "_preprint"


def build(
    items: list,
    output_path: str,
    ris_data: Optional[list] = None,
    zotero_enabled: bool = False,
) -> str:
    """Build a generic preprint DOCX from items list (no branding)."""
    items = resolve_references(items, ris_data, "generic")

    doc = Document()

    # Page setup: A4, 2.5 cm margins
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)

    # Default body style
    normal = doc.styles["Normal"]
    normal.font.name = _BODY_FONT
    normal.font.size = _BODY_SIZE
    _set_line_spacing(normal.paragraph_format, _LINE_SPACING)

    for item in items:
        _crispro_add_item(doc, item)

    doc.save(output_path)
    return output_path
