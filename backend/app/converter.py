"""
Input converter — normalizes DOCX, Markdown, LaTeX, and plain text
into the internal document representation used by format plugins.
"""

import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import structlog
from docx import Document as DocxDocument

log = structlog.get_logger()


def convert_input(input_path: str, bib_path: Optional[str] = None) -> dict:
    """
    Convert any supported input format to internal document representation.
    Returns: { "items": [...], "ris_data": [...] | None, "metadata": {...} }
    """
    path = Path(input_path)
    suffix = path.suffix.lower()

    if suffix == ".docx":
        items = _read_docx(input_path)
    elif suffix in (".md", ".markdown"):
        items = _read_markdown(input_path)
    elif suffix == ".tex":
        items = _read_latex(input_path)
    elif suffix == ".txt":
        items = _read_plaintext(input_path)
    else:
        raise ValueError(f"Unsupported input format: {suffix}")

    # Parse bibliography if provided
    ris_data = None
    if bib_path:
        bib_path_obj = Path(bib_path)
        if bib_path_obj.exists():
            if bib_path_obj.suffix.lower() == ".ris":
                ris_data = _parse_ris(bib_path)
            elif bib_path_obj.suffix.lower() == ".bib":
                ris_data = _parse_bibtex(bib_path)

    return {"items": items, "ris_data": ris_data, "metadata": _extract_metadata(items)}


def _read_docx(path: str) -> list:
    """Read DOCX and classify each element into the internal item schema."""
    doc = DocxDocument(path)
    items = []
    found_abstract = False
    found_keywords = False

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        style_name = para.style.name if para.style else ""
        runs = _extract_runs(para)

        # Classify by style and content
        if style_name == "Title" or (not items and not any(
            s in style_name for s in ["Heading", "Normal"]
        )):
            item_type = "title"
        elif "Heading 1" in style_name:
            item_type = "heading1"
        elif "Heading 2" in style_name:
            item_type = "heading2"
        elif "Heading 3" in style_name:
            item_type = "heading3"
        elif text.lower().startswith("abstract"):
            item_type = "abstract_heading"
            found_abstract = True
        elif found_abstract and not found_keywords and not any(
            h in style_name for h in ["Heading"]
        ):
            item_type = "abstract"
        elif text.lower().startswith("keywords"):
            item_type = "keywords"
            found_keywords = True
        elif re.match(r"^\[?\d+\]?\s+\w", text) and len(text) > 30:
            item_type = "reference"
        elif re.match(r"^(Table|Figure)\s+\d+", text, re.IGNORECASE):
            item_type = "table_caption" if text.lower().startswith("table") else "figure_caption"
        else:
            item_type = "paragraph"

        items.append({"type": item_type, "text": text, "runs": runs})

    # Extract tables
    for table in doc.tables:
        rows = []
        for row in table.rows:
            cells = []
            for cell in row.cells:
                cells.append({
                    "text": cell.text.strip(),
                    "gridspan": 1,
                    "runs": [{"text": cell.text.strip(), "bold": False, "italic": False,
                               "superscript": False, "subscript": False}],
                    "vmerge_continue": False,
                })
            rows.append(cells)
        items.append({"type": "table", "text": "", "runs": [], "rows": rows})

    return items


def _read_markdown(path: str) -> list:
    """Convert Markdown to internal items via Pandoc JSON AST."""
    try:
        result = subprocess.run(
            ["pandoc", path, "-t", "json"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return _pandoc_json_to_items(result.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Fallback: simple regex-based Markdown parser
    return _parse_markdown_simple(Path(path).read_text(encoding="utf-8"))


def _read_latex(path: str) -> list:
    """Convert LaTeX to internal items via Pandoc."""
    try:
        result = subprocess.run(
            ["pandoc", path, "-f", "latex", "-t", "json"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return _pandoc_json_to_items(result.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Fallback: convert LaTeX to Markdown first, then parse
    return _parse_markdown_simple(Path(path).read_text(encoding="utf-8"))


def _read_plaintext(path: str) -> list:
    """Parse plain text into items using heuristics."""
    text = Path(path).read_text(encoding="utf-8")
    return _parse_markdown_simple(text)


def _parse_markdown_simple(text: str) -> list:
    """Simple Markdown/plain text parser — fallback when Pandoc unavailable."""
    items = []
    lines = text.split("\n")
    i = 0
    in_abstract = False

    while i < len(lines):
        line = lines[i].strip()

        if not line:
            i += 1
            continue

        # ATX headings
        if line.startswith("# "):
            items.append({"type": "heading1", "text": line[2:].strip(),
                          "runs": [{"text": line[2:].strip(), "bold": True, "italic": False,
                                    "superscript": False, "subscript": False}]})
        elif line.startswith("## "):
            heading_text = line[3:].strip()
            # Reclassify "Abstract" heading
            if heading_text.lower() in ("abstract",):
                items.append({"type": "abstract_heading", "text": heading_text,
                              "runs": [{"text": heading_text, "bold": True, "italic": False,
                                        "superscript": False, "subscript": False}]})
                in_abstract = True
            else:
                items.append({"type": "heading2", "text": heading_text,
                              "runs": [{"text": heading_text, "bold": True, "italic": False,
                                        "superscript": False, "subscript": False}]})
        elif line.startswith("### "):
            items.append({"type": "heading3", "text": line[4:].strip(),
                          "runs": [{"text": line[4:].strip(), "bold": True, "italic": False,
                                    "superscript": False, "subscript": False}]})
        elif line.lower().startswith("abstract"):
            in_abstract = True
            items.append({"type": "abstract_heading", "text": line,
                          "runs": [{"text": line, "bold": True, "italic": False,
                                    "superscript": False, "subscript": False}]})
        elif line.lower().startswith("keywords"):
            in_abstract = False
            items.append({"type": "keywords", "text": line,
                          "runs": [{"text": line, "bold": False, "italic": False,
                                    "superscript": False, "subscript": False}]})
        elif re.match(r"^\[?\d+\]?\s+\w", line) and len(line) > 30:
            items.append({"type": "reference", "text": line,
                          "runs": [{"text": line, "bold": False, "italic": False,
                                    "superscript": False, "subscript": False}]})
        elif re.match(r"^(Table|Figure)\s+\d+", line, re.IGNORECASE):
            t = "table_caption" if line.lower().startswith("table") else "figure_caption"
            items.append({"type": t, "text": line,
                          "runs": [{"text": line, "bold": False, "italic": True,
                                    "superscript": False, "subscript": False}]})
        else:
            item_type = "abstract" if in_abstract else "paragraph"
            # Check if this looks like a title (first non-empty item, short, no period)
            if not items and len(line) < 150 and not line.endswith("."):
                item_type = "title"
                in_abstract = False
            runs = _parse_inline_markdown(line)
            items.append({"type": item_type, "text": line, "runs": runs})

        i += 1

    return items


def _parse_inline_markdown(text: str) -> list:
    """Parse inline Markdown formatting into runs."""
    runs = []
    # Simple bold/italic detection
    pattern = re.compile(r"(\*\*(.+?)\*\*|\*(.+?)\*|(.+?)(?=\*|$))")
    pos = 0
    while pos < len(text):
        bold_match = re.match(r"\*\*(.+?)\*\*", text[pos:])
        italic_match = re.match(r"\*(.+?)\*", text[pos:])
        if bold_match:
            runs.append({"text": bold_match.group(1), "bold": True, "italic": False,
                         "superscript": False, "subscript": False})
            pos += len(bold_match.group(0))
        elif italic_match:
            runs.append({"text": italic_match.group(1), "bold": False, "italic": True,
                         "superscript": False, "subscript": False})
            pos += len(italic_match.group(0))
        else:
            # Find next markdown marker
            next_marker = len(text)
            for marker in ["**", "*"]:
                idx = text.find(marker, pos)
                if idx != -1 and idx < next_marker:
                    next_marker = idx
            chunk = text[pos:next_marker]
            if chunk:
                runs.append({"text": chunk, "bold": False, "italic": False,
                             "superscript": False, "subscript": False})
            pos = next_marker

    if not runs:
        runs = [{"text": text, "bold": False, "italic": False,
                 "superscript": False, "subscript": False}]
    return runs


def _pandoc_json_to_items(json_str: str) -> list:
    """Convert Pandoc JSON AST to internal item format."""
    import json
    try:
        ast = json.loads(json_str)
        raw_items = []
        blocks = ast.get("blocks", [])
        for block in blocks:
            t = block.get("t", "")
            c = block.get("c", [])
            if t == "Header":
                level = c[0] if c else 1
                text = _pandoc_inlines_to_text(c[2] if len(c) > 2 else [])
                type_map = {1: "heading1", 2: "heading2", 3: "heading3"}
                raw_items.append({"type": type_map.get(level, "heading1"), "text": text,
                              "runs": [{"text": text, "bold": True, "italic": False,
                                        "superscript": False, "subscript": False}]})
            elif t == "Para":
                text = _pandoc_inlines_to_text(c)
                raw_items.append({"type": "paragraph", "text": text,
                              "runs": _pandoc_inlines_to_runs(c)})
            elif t == "Table":
                raw_items.append({"type": "table", "text": "", "runs": [], "rows": []})
        return _post_classify_items(raw_items)
    except Exception:
        return []


def _post_classify_items(items: list) -> list:
    """Post-process raw items to detect abstract, keywords, and references."""
    result = []
    in_abstract = False
    in_references = False

    for item in items:
        text = item["text"].strip()
        itype = item["type"]

        # Detect section transitions via headings
        if itype in ("heading1", "heading2", "heading3"):
            tl = text.lower().rstrip(".")
            if tl == "abstract":
                item = dict(item, type="abstract_heading")
                in_abstract = True
                in_references = False
            elif tl in ("references", "bibliography", "works cited"):
                in_abstract = False
                in_references = True
            else:
                in_abstract = False
            result.append(item)
            continue

        # Classify paragraphs based on context
        if in_abstract:
            if text.lower().startswith("keyword"):
                item = dict(item, type="keywords")
                in_abstract = False
            else:
                item = dict(item, type="abstract")
        elif in_references:
            # Reference lines: [N] Author... or numbered list
            if re.match(r"^\[?\d+\]?\.?\s+\w", text) and len(text) > 20:
                item = dict(item, type="reference")
            elif re.match(r"^\d+\.\s+\w", text) and len(text) > 20:
                item = dict(item, type="reference")
        elif not result and itype == "paragraph" and len(text) < 150 and not text.endswith("."):
            item = dict(item, type="title")

        result.append(item)

    return result


def _pandoc_inlines_to_text(inlines: list) -> str:
    parts = []
    for inline in inlines:
        t = inline.get("t", "")
        c = inline.get("c", "")
        if t == "Str":
            parts.append(c)
        elif t == "Space":
            parts.append(" ")
        elif t in ("Emph", "Strong"):
            parts.append(_pandoc_inlines_to_text(c))
    return "".join(parts)


def _pandoc_inlines_to_runs(inlines: list) -> list:
    runs = []
    for inline in inlines:
        t = inline.get("t", "")
        c = inline.get("c", "")
        if t == "Str":
            runs.append({"text": c, "bold": False, "italic": False,
                         "superscript": False, "subscript": False})
        elif t == "Space":
            runs.append({"text": " ", "bold": False, "italic": False,
                         "superscript": False, "subscript": False})
        elif t == "Strong":
            for r in _pandoc_inlines_to_runs(c):
                r["bold"] = True
                runs.append(r)
        elif t == "Emph":
            for r in _pandoc_inlines_to_runs(c):
                r["italic"] = True
                runs.append(r)
    return runs or [{"text": "", "bold": False, "italic": False,
                     "superscript": False, "subscript": False}]


def _extract_runs(para) -> list:
    """Extract formatted runs from a python-docx paragraph."""
    runs = []
    for run in para.runs:
        if run.text:
            runs.append({
                "text": run.text,
                "bold": bool(run.bold),
                "italic": bool(run.italic),
                "superscript": bool(run.font.superscript) if run.font else False,
                "subscript": bool(run.font.subscript) if run.font else False,
            })
    if not runs and para.text:
        runs = [{"text": para.text, "bold": False, "italic": False,
                 "superscript": False, "subscript": False}]
    return runs


def _parse_ris(path: str) -> list:
    """Parse RIS bibliography file into list of records."""
    records = []
    current = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip()
            if line.startswith("ER  -"):
                if current:
                    records.append(current)
                    current = {}
            elif "  - " in line:
                tag, _, value = line.partition("  - ")
                tag = tag.strip()
                value = value.strip()
                if tag in current:
                    if isinstance(current[tag], list):
                        current[tag].append(value)
                    else:
                        current[tag] = [current[tag], value]
                else:
                    current[tag] = value
    return records


def _parse_bibtex(path: str) -> list:
    """Parse BibTeX file into list of records (simplified)."""
    records = []
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    entries = re.findall(r"@\w+\{([^,]+),([^@]+)\}", text, re.DOTALL)
    for key, body in entries:
        record = {"TY": "JOUR", "ID": key.strip()}
        fields = re.findall(r"(\w+)\s*=\s*\{([^}]+)\}", body)
        field_map = {
            "author": "AU", "title": "TI", "journal": "JO",
            "year": "PY", "volume": "VL", "pages": "SP",
            "doi": "DO", "abstract": "AB", "booktitle": "BT",
        }
        for field, value in fields:
            ris_key = field_map.get(field.lower(), field.upper()[:2])
            record[ris_key] = value.strip()
        records.append(record)
    return records


def _extract_metadata(items: list) -> dict:
    """Extract title, authors, abstract from items list."""
    metadata = {"title": "", "abstract": "", "keywords": ""}
    for item in items:
        if item["type"] == "title" and not metadata["title"]:
            metadata["title"] = item["text"]
        elif item["type"] == "abstract" and not metadata["abstract"]:
            metadata["abstract"] = item["text"]
        elif item["type"] == "keywords" and not metadata["keywords"]:
            metadata["keywords"] = item["text"]
    return metadata
