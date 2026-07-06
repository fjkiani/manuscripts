"""
Output renderer — converts formatted DOCX to PDF (Pandoc+XeLaTeX), LaTeX, and HTML.
Also provides a fast HTML preview for the live editor.
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import structlog

log = structlog.get_logger()

# Journal-specific Pandoc LaTeX templates
STYLE_LATEX_SETTINGS = {
    "ieee": {
        "documentclass": "IEEEtran",
        "classoption": "conference",
        "fontsize": "10pt",
        "geometry": "margin=0.75in",
        "bibstyle": "IEEEtran",
        "columns": "twocolumn",
    },
    "elsevier": {
        "documentclass": "elsarticle",
        "classoption": "preprint,12pt",
        "fontsize": "12pt",
        "geometry": "margin=2.5cm",
        "bibstyle": "elsarticle-num",
        "columns": "onecolumn",
    },
    "springer": {
        "documentclass": "llncs",
        "classoption": "",
        "fontsize": "10pt",
        "geometry": "margin=2cm",
        "bibstyle": "splncs04",
        "columns": "onecolumn",
    },
    "apa": {
        "documentclass": "apa7",
        "classoption": "man",
        "fontsize": "12pt",
        "geometry": "margin=1in",
        "bibstyle": "apa",
        "columns": "onecolumn",
    },
    "ama": {
        "documentclass": "article",
        "classoption": "",
        "fontsize": "12pt",
        "geometry": "margin=1in",
        "bibstyle": "vancouver",
        "columns": "onecolumn",
    },
    "generic": {
        "documentclass": "article",
        "classoption": "",
        "fontsize": "11pt",
        "geometry": "margin=1in",
        "bibstyle": "plain",
        "columns": "onecolumn",
    },
}

STYLE_CSS = {
    "ieee": """
        body { font-family: 'Times New Roman', serif; font-size: 10pt; column-count: 2; column-gap: 0.5cm; }
        h1 { font-size: 12pt; text-align: center; text-transform: uppercase; }
        h2 { font-size: 10pt; font-variant: small-caps; }
        .abstract { font-size: 9pt; font-style: italic; }
    """,
    "elsevier": """
        body { font-family: 'Times New Roman', serif; font-size: 12pt; line-height: 1.5; margin: 2.5cm; }
        h1 { font-size: 14pt; font-weight: bold; }
        h2 { font-size: 12pt; font-weight: bold; }
        .abstract { font-size: 11pt; }
    """,
    "springer": """
        body { font-family: 'Times New Roman', serif; font-size: 10pt; margin: 2cm; }
        h1 { font-size: 12pt; font-weight: bold; }
        h2 { font-size: 11pt; font-weight: bold; }
    """,
    "apa": """
        body { font-family: 'Times New Roman', serif; font-size: 12pt; line-height: 2; margin: 1in; }
        h1 { text-align: center; font-weight: bold; }
        h2 { text-align: left; font-weight: bold; font-style: italic; }
        .abstract { margin: 0 0.5in; }
    """,
    "ama": """
        body { font-family: 'Times New Roman', serif; font-size: 12pt; line-height: 1.5; margin: 1in; }
        h1 { font-size: 14pt; font-weight: bold; }
        sup { font-size: 8pt; }
    """,
    "generic": """
        body { font-family: 'Times New Roman', serif; font-size: 11pt; line-height: 1.5; margin: 1in; }
        h1 { font-size: 14pt; font-weight: bold; }
        h2 { font-size: 12pt; font-weight: bold; }
    """,
}


def render_outputs(
    formatted_docx_path: str,
    output_dir: str,
    outputs: list,
    style: str,
) -> dict:
    """
    Render all requested output formats from the formatted DOCX.
    Returns dict mapping format name to output file path.
    """
    output_files = {}
    output_path = Path(output_dir)
    settings = STYLE_LATEX_SETTINGS.get(style, STYLE_LATEX_SETTINGS["generic"])

    for fmt in outputs:
        try:
            if fmt == "docx":
                # DOCX is already the formatted_docx — just copy
                import shutil
                dest = output_path / "manuscript.docx"
                shutil.copy2(formatted_docx_path, dest)
                output_files["docx"] = str(dest)

            elif fmt == "pdf":
                pdf_path = _render_pdf(formatted_docx_path, output_dir, style, settings)
                if pdf_path:
                    output_files["pdf"] = pdf_path

            elif fmt == "latex":
                tex_path = _render_latex(formatted_docx_path, output_dir, settings)
                if tex_path:
                    output_files["latex"] = tex_path

            elif fmt == "html":
                html_path = _render_html(formatted_docx_path, output_dir, style)
                if html_path:
                    output_files["html"] = html_path

        except Exception as e:
            log.error("render_failed", format=fmt, error=str(e))

    return output_files


def _render_pdf(docx_path: str, output_dir: str, style: str, settings: dict) -> Optional[str]:
    """Convert DOCX → PDF via Pandoc + XeLaTeX."""
    output_path = Path(output_dir) / "manuscript.pdf"

    # Build Pandoc command
    cmd = [
        "pandoc",
        docx_path,
        "-o", str(output_path),
        "--pdf-engine=xelatex",
        f"--variable=documentclass:{settings['documentclass']}",
        f"--variable=fontsize:{settings['fontsize']}",
        "--variable=mainfont:Times New Roman",
        "--variable=sansfont:Arial",
        "--variable=monofont:Courier New",
        "--variable=geometry:" + settings["geometry"],
        "--standalone",
        "--toc=false",
    ]

    if settings.get("classoption"):
        cmd.append(f"--variable=classoption:{settings['classoption']}")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=90,
            cwd=output_dir
        )
        if result.returncode == 0 and output_path.exists():
            log.info("pdf_rendered", path=str(output_path))
            return str(output_path)
        else:
            log.warning("pdf_pandoc_failed", stderr=result.stderr[:500])
            # Fallback: try with article class
            return _render_pdf_fallback(docx_path, output_dir)
    except subprocess.TimeoutExpired:
        log.error("pdf_render_timeout")
        return None
    except FileNotFoundError:
        log.error("pandoc_not_found")
        return _render_pdf_fallback(docx_path, output_dir)


def _render_pdf_fallback(docx_path: str, output_dir: str) -> Optional[str]:
    """Fallback PDF render with minimal settings."""
    output_path = Path(output_dir) / "manuscript.pdf"
    cmd = [
        "pandoc", docx_path,
        "-o", str(output_path),
        "--pdf-engine=xelatex",
        "--standalone",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and output_path.exists():
            return str(output_path)
    except Exception:
        pass
    return None


def _render_latex(docx_path: str, output_dir: str, settings: dict) -> Optional[str]:
    """Convert DOCX → LaTeX source via Pandoc."""
    output_path = Path(output_dir) / "manuscript.tex"
    cmd = [
        "pandoc", docx_path,
        "-o", str(output_path),
        f"--variable=documentclass:{settings['documentclass']}",
        "--standalone",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and output_path.exists():
            return str(output_path)
        log.warning("latex_render_failed", stderr=result.stderr[:300])
    except Exception as e:
        log.error("latex_render_error", error=str(e))
    return None


def _render_html(docx_path: str, output_dir: str, style: str) -> Optional[str]:
    """Convert DOCX → HTML via Pandoc with journal CSS."""
    output_path = Path(output_dir) / "manuscript.html"
    css = STYLE_CSS.get(style, STYLE_CSS["generic"])

    # Write CSS to temp file
    css_path = Path(output_dir) / "style.css"
    css_path.write_text(css)

    cmd = [
        "pandoc", docx_path,
        "-o", str(output_path),
        "--standalone",
        f"--css={css_path}",
        "--metadata", f"title=Manuscript",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and output_path.exists():
            return str(output_path)
        log.warning("html_render_failed", stderr=result.stderr[:300])
    except Exception as e:
        log.error("html_render_error", error=str(e))
    return None


def render_preview_html(content: str, style: str) -> str:
    """
    Fast HTML preview for the live editor.
    Converts Markdown content to styled HTML without Pandoc (for speed).
    """
    css = STYLE_CSS.get(style, STYLE_CSS["generic"])

    # Simple Markdown → HTML conversion for preview
    html_content = _markdown_to_html_simple(content)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  {css}
  body {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
  table {{ border-collapse: collapse; width: 100%; }}
  td, th {{ border: 1px solid #ccc; padding: 4px 8px; }}
  th {{ background: #f5f5f5; font-weight: bold; }}
  .reference-list {{ font-size: 0.9em; }}
  .abstract-section {{ background: #f9f9f9; padding: 10px; border-left: 3px solid #ccc; }}
</style>
</head>
<body>
{html_content}
</body>
</html>"""


def _markdown_to_html_simple(text: str) -> str:
    """Minimal Markdown → HTML for preview (no external deps)."""
    lines = text.split("\n")
    html_lines = []
    in_para = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_para:
                html_lines.append("</p>")
                in_para = False
            continue

        if stripped.startswith("# "):
            if in_para: html_lines.append("</p>"); in_para = False
            html_lines.append(f"<h1>{_inline_md(stripped[2:])}</h1>")
        elif stripped.startswith("## "):
            if in_para: html_lines.append("</p>"); in_para = False
            html_lines.append(f"<h2>{_inline_md(stripped[3:])}</h2>")
        elif stripped.startswith("### "):
            if in_para: html_lines.append("</p>"); in_para = False
            html_lines.append(f"<h3>{_inline_md(stripped[4:])}</h3>")
        else:
            if not in_para:
                html_lines.append("<p>")
                in_para = True
            html_lines.append(_inline_md(stripped) + " ")

    if in_para:
        html_lines.append("</p>")

    return "\n".join(html_lines)


def _inline_md(text: str) -> str:
    """Convert inline Markdown to HTML."""
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text
