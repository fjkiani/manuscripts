"""Unit tests for the citation reference engine."""

import pytest
from app.citations.reference_engine import (
    _detect_citation_style,
    _build_ris_lookup,
    _match_reference,
    _extract_doi,
    _format_reference,
    _format_authors_ieee,
    _format_authors_apa,
    _format_authors_ama,
    _reformat_existing,
)

SAMPLE_RIS_RECORDS = [
    {
        "TY": "JOUR",
        "AU": ["Smith, John", "Doe, Jane"],
        "TI": "A Test Article on Machine Learning",
        "JO": "Nature",
        "PY": "2024",
        "VL": "600",
        "IS": "1",
        "SP": "100",
        "EP": "110",
        "DO": "10.1038/test.2024.001",
    },
    {
        "TY": "JOUR",
        "AU": "Johnson, Alice",
        "TI": "Deep Learning Applications",
        "JO": "Science",
        "PY": "2023",
        "VL": "380",
        "SP": "200",
        "EP": "210",
        "DO": "10.1126/science.2023.002",
    },
]


class TestCitationStyleDetection:
    def test_detects_numbered_style(self):
        items = [
            {"type": "paragraph", "text": "As shown in [1] and [2], the results are clear.", "runs": []},
            {"type": "paragraph", "text": "Further evidence [3] supports this.", "runs": []},
        ]
        style = _detect_citation_style(items)
        assert style == "numbered"

    def test_detects_author_date_style(self):
        items = [
            {"type": "paragraph", "text": "As shown by (Smith, 2024) and (Doe, 2023).", "runs": []},
        ]
        style = _detect_citation_style(items)
        assert style == "author_date"

    def test_empty_items(self):
        style = _detect_citation_style([])
        assert style in ("numbered", "author_date")


class TestRISLookup:
    def test_builds_doi_lookup(self):
        lookup = _build_ris_lookup(SAMPLE_RIS_RECORDS)
        assert "doi:10.1038/test.2024.001" in lookup

    def test_builds_authoryear_lookup(self):
        lookup = _build_ris_lookup(SAMPLE_RIS_RECORDS)
        assert "authoryear:smith:2024" in lookup

    def test_empty_records(self):
        lookup = _build_ris_lookup([])
        assert lookup == {}


class TestReferenceMatching:
    def test_matches_by_doi(self):
        lookup = _build_ris_lookup(SAMPLE_RIS_RECORDS)
        text = "Smith J, Doe J. A Test Article. Nature. 2024. https://doi.org/10.1038/test.2024.001"
        match = _match_reference(text, lookup)
        assert match is not None
        assert match["TI"] == "A Test Article on Machine Learning"

    def test_no_match_returns_none(self):
        lookup = _build_ris_lookup(SAMPLE_RIS_RECORDS)
        text = "Unknown Author. Unknown Title. Unknown Journal. 1999."
        match = _match_reference(text, lookup)
        assert match is None


class TestDOIExtraction:
    def test_extracts_doi(self):
        text = "Smith J. Title. Journal. 2024. https://doi.org/10.1038/test.2024.001"
        doi = _extract_doi(text)
        assert doi == "10.1038/test.2024.001"

    def test_extracts_bare_doi(self):
        text = "doi: 10.1126/science.abc1234"
        doi = _extract_doi(text)
        assert doi == "10.1126/science.abc1234"

    def test_no_doi_returns_none(self):
        text = "Smith J. Title. Journal. 2024."
        doi = _extract_doi(text)
        assert doi is None


class TestReferenceFormatting:
    def test_ieee_format(self):
        record = SAMPLE_RIS_RECORDS[0]
        formatted = _format_reference(record, "ieee", 1)
        assert "[1]" in formatted
        assert "Nature" in formatted
        assert "2024" in formatted

    def test_apa_format(self):
        record = SAMPLE_RIS_RECORDS[0]
        formatted = _format_reference(record, "apa", 1)
        assert "2024" in formatted
        assert "Nature" in formatted
        assert "Smith" in formatted

    def test_ama_format(self):
        record = SAMPLE_RIS_RECORDS[0]
        formatted = _format_reference(record, "ama", 1)
        assert "1." in formatted
        assert "Nature" in formatted

    def test_elsevier_format(self):
        record = SAMPLE_RIS_RECORDS[0]
        formatted = _format_reference(record, "elsevier", 1)
        assert "[1]" in formatted

    def test_generic_format(self):
        record = SAMPLE_RIS_RECORDS[0]
        formatted = _format_reference(record, "generic", 1)
        assert "[1]" in formatted


class TestAuthorFormatting:
    def test_ieee_single_author(self):
        result = _format_authors_ieee(["Smith, John"])
        assert "Smith" in result

    def test_ieee_two_authors(self):
        result = _format_authors_ieee(["Smith, John", "Doe, Jane"])
        assert "and" in result

    def test_apa_single_author(self):
        result = _format_authors_apa(["Smith, John"])
        assert "Smith" in result

    def test_apa_two_authors(self):
        result = _format_authors_apa(["Smith, John", "Doe, Jane"])
        assert "&" in result

    def test_ama_format(self):
        result = _format_authors_ama(["Smith, John"])
        assert "Smith" in result

    def test_empty_authors(self):
        assert _format_authors_ieee([]) == ""
        assert _format_authors_apa([]) == ""
        assert _format_authors_ama([]) == ""


class TestReformatExisting:
    def test_ieee_adds_brackets(self):
        result = _reformat_existing("Smith J. Title. Journal. 2024.", "ieee", 1)
        assert "[1]" in result

    def test_ama_adds_number(self):
        result = _reformat_existing("Smith J. Title. Journal. 2024.", "ama", 1)
        assert "1." in result

    def test_strips_existing_numbering(self):
        result = _reformat_existing("[3] Smith J. Title.", "ieee", 1)
        assert "[1]" in result
        assert "[3]" not in result
