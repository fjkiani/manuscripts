"""
Reference resolution engine — matches inline citations to bibliography records
and reformats them to the target journal style.
Supports: numbered [N], author-date (Smith, 2024), superscript ¹
"""

import re
import httpx
from typing import Optional
import structlog

log = structlog.get_logger()

CROSSREF_API = "https://api.crossref.org/works"
CROSSREF_TIMEOUT = 5.0  # seconds


def resolve_references(
    items: list,
    ris_data: Optional[list],
    target_style: str,
) -> list:
    """
    Main entry point: resolve and reformat all references in items list.
    Returns updated items with reformatted reference entries.
    """
    # Extract reference items
    ref_items = [i for i, item in enumerate(items) if item["type"] == "reference"]
    if not ref_items:
        return items

    # Build lookup from RIS data
    ris_lookup = _build_ris_lookup(ris_data or [])

    # Determine citation style of input
    input_style = _detect_citation_style(items)

    # Reformat each reference
    for idx in ref_items:
        item = items[idx]
        text = item["text"]

        # Try to match against RIS data
        matched_record = _match_reference(text, ris_lookup)

        if matched_record:
            formatted = _format_reference(matched_record, target_style, idx - ref_items[0] + 1)
        else:
            # Try CrossRef lookup
            doi = _extract_doi(text)
            if doi:
                record = _crossref_lookup_doi(doi)
                if record:
                    formatted = _format_reference(record, target_style, idx - ref_items[0] + 1)
                else:
                    formatted = _reformat_existing(text, target_style, idx - ref_items[0] + 1)
            else:
                formatted = _reformat_existing(text, target_style, idx - ref_items[0] + 1)

        items[idx] = {
            "type": "reference",
            "text": formatted,
            "runs": [{"text": formatted, "bold": False, "italic": False,
                      "superscript": False, "subscript": False}],
        }

    return items


def _detect_citation_style(items: list) -> str:
    """Detect whether manuscript uses numbered [N] or author-date citations."""
    text = " ".join(item["text"] for item in items if item["type"] == "paragraph")
    numbered = len(re.findall(r"\[\d+\]", text))
    author_date = len(re.findall(r"\([A-Z][a-z]+,?\s+\d{4}\)", text))
    return "numbered" if numbered >= author_date else "author_date"


def _build_ris_lookup(ris_data: list) -> dict:
    """Build lookup dict from RIS records keyed by DOI, title fragment, and author+year."""
    lookup = {}
    for record in ris_data:
        doi = record.get("DO", "").lower().strip()
        if doi:
            lookup[f"doi:{doi}"] = record

        title = record.get("TI", "").lower()[:40]
        if title:
            lookup[f"title:{title}"] = record

        authors = record.get("AU", "")
        year = record.get("PY", record.get("Y1", ""))[:4] if record.get("PY", record.get("Y1", "")) else ""
        if authors and year:
            first_author = (authors[0] if isinstance(authors, list) else authors).split(",")[0].lower()
            lookup[f"authoryear:{first_author}:{year}"] = record

    return lookup


def _match_reference(text: str, ris_lookup: dict) -> Optional[dict]:
    """Try to match a reference text against RIS lookup."""
    # Try DOI match
    doi = _extract_doi(text)
    if doi and f"doi:{doi.lower()}" in ris_lookup:
        return ris_lookup[f"doi:{doi.lower()}"]

    # Try title fragment match
    words = re.findall(r"\b[A-Z][a-z]{3,}\b", text)
    if len(words) >= 3:
        fragment = " ".join(words[:4]).lower()
        for key, record in ris_lookup.items():
            if key.startswith("title:") and fragment[:20] in key:
                return record

    # Try author+year match
    year_match = re.search(r"\b(19|20)\d{2}\b", text)
    author_match = re.match(r"^\[?\d+\]?\s*([A-Z][a-z]+)", text)
    if year_match and author_match:
        year = year_match.group(0)
        author = author_match.group(1).lower()
        key = f"authoryear:{author}:{year}"
        if key in ris_lookup:
            return ris_lookup[key]

    return None


def _extract_doi(text: str) -> Optional[str]:
    """Extract DOI from reference text."""
    match = re.search(r"10\.\d{4,}/\S+", text)
    return match.group(0).rstrip(".,;)") if match else None


def _crossref_lookup_doi(doi: str) -> Optional[dict]:
    """Look up a DOI via CrossRef API."""
    try:
        with httpx.Client(timeout=CROSSREF_TIMEOUT) as client:
            resp = client.get(f"{CROSSREF_API}/{doi}")
            if resp.status_code == 200:
                data = resp.json().get("message", {})
                return _crossref_to_ris(data)
    except Exception as e:
        log.debug("crossref_lookup_failed", doi=doi, error=str(e))
    return None


def _crossref_to_ris(data: dict) -> dict:
    """Convert CrossRef API response to RIS-like record."""
    authors = []
    for author in data.get("author", []):
        family = author.get("family", "")
        given = author.get("given", "")
        if family:
            authors.append(f"{family}, {given[:1]}." if given else family)

    year = ""
    date_parts = data.get("published", {}).get("date-parts", [[]])
    if date_parts and date_parts[0]:
        year = str(date_parts[0][0])

    return {
        "TY": "JOUR",
        "AU": authors,
        "TI": data.get("title", [""])[0] if data.get("title") else "",
        "JO": data.get("container-title", [""])[0] if data.get("container-title") else "",
        "PY": year,
        "VL": data.get("volume", ""),
        "IS": data.get("issue", ""),
        "SP": data.get("page", "").split("-")[0] if data.get("page") else "",
        "EP": data.get("page", "").split("-")[-1] if data.get("page") else "",
        "DO": data.get("DOI", ""),
    }


def _format_reference(record: dict, style: str, number: int) -> str:
    """Format a RIS record into the target journal citation style."""
    authors = record.get("AU", [])
    if isinstance(authors, str):
        authors = [authors]

    title = record.get("TI", "")
    journal = record.get("JO", record.get("T2", ""))
    year = record.get("PY", record.get("Y1", ""))[:4] if record.get("PY", record.get("Y1", "")) else ""
    volume = record.get("VL", "")
    issue = record.get("IS", "")
    start_page = record.get("SP", "")
    end_page = record.get("EP", "")
    doi = record.get("DO", "")

    pages = f"{start_page}–{end_page}" if start_page and end_page else start_page

    if style in ("ieee",):
        # IEEE: [N] A. Author, "Title," Journal, vol. V, no. I, pp. P, Year.
        author_str = _format_authors_ieee(authors)
        ref = f"[{number}] {author_str}, \"{title},\" {journal}"
        if volume: ref += f", vol. {volume}"
        if issue: ref += f", no. {issue}"
        if pages: ref += f", pp. {pages}"
        if year: ref += f", {year}"
        if doi: ref += f". doi: {doi}"
        return ref + "."

    elif style in ("elsevier", "springer", "generic"):
        # Numbered: [N] Author(s). Title. Journal. Year;Vol(Issue):Pages.
        author_str = _format_authors_vancouver(authors)
        ref = f"[{number}] {author_str}. {title}. {journal}."
        if year: ref += f" {year}"
        if volume: ref += f";{volume}"
        if issue: ref += f"({issue})"
        if pages: ref += f":{pages}"
        if doi: ref += f". https://doi.org/{doi}"
        return ref + "."

    elif style == "apa":
        # APA 7: Author, A. A., & Author, B. B. (Year). Title. Journal, Vol(Issue), Pages. DOI
        author_str = _format_authors_apa(authors)
        ref = f"{author_str} ({year}). {title}. {journal}"
        if volume: ref += f", {volume}"
        if issue: ref += f"({issue})"
        if pages: ref += f", {pages}"
        if doi: ref += f". https://doi.org/{doi}"
        return ref + "."

    elif style == "ama":
        # AMA: Author AA, Author BB. Title. Journal. Year;Vol(Issue):Pages. doi:DOI
        author_str = _format_authors_ama(authors)
        ref = f"{number}. {author_str}. {title}. {journal}."
        if year: ref += f" {year}"
        if volume: ref += f";{volume}"
        if issue: ref += f"({issue})"
        if pages: ref += f":{pages}"
        if doi: ref += f". doi:{doi}"
        return ref + "."

    return f"[{number}] {record}"


def _format_authors_ieee(authors: list) -> str:
    if not authors: return ""
    formatted = []
    for a in authors[:6]:
        parts = a.split(",")
        if len(parts) >= 2:
            last = parts[0].strip()
            first = parts[1].strip()
            initials = ". ".join(c + "." for c in first.replace(".", " ").split() if c)
            formatted.append(f"{initials} {last}")
        else:
            formatted.append(a)
    result = ", ".join(formatted[:-1])
    if len(formatted) > 1:
        result += f", and {formatted[-1]}"
    else:
        result = formatted[0] if formatted else ""
    if len(authors) > 6:
        result += " et al."
    return result


def _format_authors_apa(authors: list) -> str:
    if not authors: return ""
    formatted = []
    for a in authors[:20]:
        parts = a.split(",")
        if len(parts) >= 2:
            last = parts[0].strip()
            first = parts[1].strip()
            initials = ". ".join(c[0] + "." for c in first.split() if c) if first else ""
            formatted.append(f"{last}, {initials}")
        else:
            formatted.append(a)
    if len(formatted) == 1:
        return formatted[0]
    elif len(formatted) <= 20:
        return ", ".join(formatted[:-1]) + f", & {formatted[-1]}"
    else:
        return ", ".join(formatted[:19]) + ", . . . " + formatted[-1]


def _format_authors_ama(authors: list) -> str:
    if not authors: return ""
    formatted = []
    for a in authors[:6]:
        parts = a.split(",")
        if len(parts) >= 2:
            last = parts[0].strip()
            first = parts[1].strip()
            initials = "".join(c[0].upper() for c in first.split() if c)
            formatted.append(f"{last} {initials}")
        else:
            formatted.append(a)
    result = ", ".join(formatted)
    if len(authors) > 6:
        result += ", et al"
    return result


def _format_authors_vancouver(authors: list) -> str:
    return _format_authors_ama(authors)


def _reformat_existing(text: str, style: str, number: int) -> str:
    """Reformat an existing reference text when no metadata is available."""
    # Strip existing numbering
    text = re.sub(r"^\[?\d+\]?\.?\s*", "", text).strip()

    if style in ("ieee",):
        return f"[{number}] {text}"
    elif style == "apa":
        return text  # Keep as-is, can't reformat without metadata
    elif style == "ama":
        return f"{number}. {text}"
    else:
        return f"[{number}] {text}"
