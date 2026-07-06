"""Unit tests for the input converter module."""

import os
import tempfile
import pytest
from app.converter import (
    _parse_markdown_simple,
    _parse_ris,
    _parse_bibtex,
    _extract_metadata,
    _parse_inline_markdown,
)


class TestMarkdownParser:
    def test_title_detection(self):
        text = "# My Paper Title\n\n## Abstract\n\nThis is the abstract."
        items = _parse_markdown_simple(text)
        assert items[0]["type"] == "heading1"
        assert items[0]["text"] == "My Paper Title"

    def test_abstract_detection(self):
        text = "# Title\n\n## Abstract\n\nThis is abstract text."
        items = _parse_markdown_simple(text)
        abstract_items = [i for i in items if i["type"] == "abstract"]
        assert len(abstract_items) > 0

    def test_heading_levels(self):
        text = "# H1\n## H2\n### H3\nParagraph"
        items = _parse_markdown_simple(text)
        types = [i["type"] for i in items]
        assert "heading1" in types
        assert "heading2" in types
        assert "heading3" in types

    def test_reference_detection(self):
        text = "Some paragraph.\n\n[1] Smith, J. (2024). Title. Journal, 1(1), 1-10."
        items = _parse_markdown_simple(text)
        ref_items = [i for i in items if i["type"] == "reference"]
        assert len(ref_items) == 1

    def test_keywords_detection(self):
        text = "# Title\n\nKeywords: machine learning, AI, deep learning"
        items = _parse_markdown_simple(text)
        kw_items = [i for i in items if i["type"] == "keywords"]
        assert len(kw_items) == 1

    def test_empty_lines_skipped(self):
        text = "# Title\n\n\n\nParagraph"
        items = _parse_markdown_simple(text)
        assert all(item["text"].strip() for item in items)

    def test_runs_structure(self):
        text = "# Title\nParagraph with **bold** and *italic* text."
        items = _parse_markdown_simple(text)
        para = next(i for i in items if i["type"] == "paragraph")
        assert isinstance(para["runs"], list)
        assert all("text" in r for r in para["runs"])


class TestInlineMarkdown:
    def test_bold(self):
        runs = _parse_inline_markdown("Hello **world** text")
        bold_runs = [r for r in runs if r["bold"]]
        assert len(bold_runs) == 1
        assert bold_runs[0]["text"] == "world"

    def test_italic(self):
        runs = _parse_inline_markdown("Hello *world* text")
        italic_runs = [r for r in runs if r["italic"]]
        assert len(italic_runs) == 1

    def test_plain_text(self):
        runs = _parse_inline_markdown("Plain text only")
        assert len(runs) >= 1
        assert runs[0]["text"] == "Plain text only"


class TestRISParser:
    def test_parse_basic_ris(self):
        ris_content = """TY  - JOUR
AU  - Smith, John
TI  - Test Article
JO  - Test Journal
PY  - 2024
VL  - 1
SP  - 1
EP  - 10
DO  - 10.1234/test
ER  -
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ris', delete=False) as f:
            f.write(ris_content)
            f.flush()
            records = _parse_ris(f.name)
        os.unlink(f.name)

        assert len(records) == 1
        assert records[0]["TI"] == "Test Article"
        assert records[0]["AU"] == "Smith, John"
        assert records[0]["PY"] == "2024"

    def test_parse_multiple_authors(self):
        ris_content = """TY  - JOUR
AU  - Smith, John
AU  - Doe, Jane
TI  - Multi-author Paper
ER  -
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ris', delete=False) as f:
            f.write(ris_content)
            f.flush()
            records = _parse_ris(f.name)
        os.unlink(f.name)

        assert len(records) == 1
        assert isinstance(records[0]["AU"], list)
        assert len(records[0]["AU"]) == 2


class TestBibTeXParser:
    def test_parse_basic_bibtex(self):
        bib_content = """@article{smith2024,
  author = {Smith, John},
  title = {Test Article},
  journal = {Test Journal},
  year = {2024},
  volume = {1},
  pages = {1-10},
  doi = {10.1234/test}
}
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.bib', delete=False) as f:
            f.write(bib_content)
            f.flush()
            records = _parse_bibtex(f.name)
        os.unlink(f.name)

        assert len(records) == 1
        assert records[0]["TI"] == "Test Article"
        assert records[0]["ID"] == "smith2024"


class TestMetadataExtraction:
    def test_extract_title(self):
        items = [
            {"type": "title", "text": "My Paper Title", "runs": []},
            {"type": "paragraph", "text": "Some text", "runs": []},
        ]
        meta = _extract_metadata(items)
        assert meta["title"] == "My Paper Title"

    def test_extract_abstract(self):
        items = [
            {"type": "title", "text": "Title", "runs": []},
            {"type": "abstract", "text": "This is the abstract.", "runs": []},
        ]
        meta = _extract_metadata(items)
        assert meta["abstract"] == "This is the abstract."
