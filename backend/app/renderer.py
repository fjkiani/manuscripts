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
    "crispro": {
        "documentclass": "article",
        "classoption": "",
        "fontsize": "11pt",
        "geometry": "a4paper,margin=2.5cm",
        "bibstyle": "plain",
        "columns": "onecolumn",
        "extra_packages": "booktabs,graphicx,hyperref,fancyhdr,setspace",
        "footer": "For Research Use Only",
    },
    "preprint": {
        "documentclass": "article",
        "classoption": "",
        "fontsize": "11pt",
        "geometry": "a4paper,margin=2.5cm",
        "bibstyle": "plain",
        "columns": "onecolumn",
        "extra_packages": "booktabs,graphicx,hyperref,setspace",
        "footer": "",
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
    "crispro": """
        body { font-family: Georgia, 'Times New Roman', serif; font-size: 11pt; line-height: 1.4;
               max-width: 750px; margin: 2.5cm auto; padding: 0 1em; text-align: justify; }
        h1 { font-size: 20pt; font-weight: normal; text-align: center; margin-bottom: 0.3em; }
        h2 { font-size: 12pt; font-weight: bold; margin-top: 1.2em; margin-bottom: 0.3em; }
        h3 { font-size: 11pt; font-weight: bold; font-style: italic; margin-top: 1em; margin-bottom: 0.2em; }
        .abstract { margin: 1em 0; }
        .abstract-label { font-weight: bold; }
        figure { text-align: center; margin: 1.5em 0; page-break-inside: avoid; }
        figcaption { font-size: 0.9em; font-style: italic; margin-top: 0.4em; }
        figcaption strong { font-style: normal; }
        table { border-collapse: collapse; width: 100%; margin: 1em 0; }
        th { border-top: 2px solid #000; border-bottom: 1px solid #000; padding: 4px 8px; font-weight: bold; }
        td { padding: 4px 8px; border: none; }
        tr:last-child td { border-bottom: 2px solid #000; }
        .references p { padding-left: 1.5em; text-indent: -1.5em; font-size: 0.9em; }
        footer { font-style: italic; font-size: 0.85em; text-align: center; margin-top: 2em;
                 border-top: 1px solid #ccc; padding-top: 0.5em; color: #555; }
    """,
    "preprint": """
        body { font-family: Georgia, 'Times New Roman', serif; font-size: 11pt; line-height: 1.4;
               max-width: 750px; margin: 2.5cm auto; padding: 0 1em; text-align: justify; }
        h1 { font-size: 20pt; font-weight: normal; text-align: center; margin-bottom: 0.3em; }
        h2 { font-size: 12pt; font-weight: bold; margin-top: 1.2em; margin-bottom: 0.3em; }
        h3 { font-size: 11pt; font-weight: bold; font-style: italic; margin-top: 1em; margin-bottom: 0.2em; }
        .abstract { margin: 1em 0; }
        figure { text-align: center; margin: 1.5em 0; page-break-inside: avoid; }
        figcaption { font-size: 0.9em; font-style: italic; margin-top: 0.4em; }
        table { border-collapse: collapse; width: 100%; margin: 1em 0; }
        th { border-top: 2px solid #000; border-bottom: 1px solid #000; padding: 4px 8px; font-weight: bold; }
        td { padding: 4px 8px; border: none; }
        tr:last-child td { border-bottom: 2px solid #000; }
        .references p { padding-left: 1.5em; text-indent: -1.5em; font-size: 0.9em; }
    """,
}


def render_outputs(
    formatted_docx_path: str,
    output_dir: str,
    outputs: list,
    style: str,
    figures_dir: Optional[str] = None,
) -> dict:
    """
    Render all requested output formats from the formatted DOCX.
    Returns dict mapping format name to output file path.

    figures_dir: path to directory containing figure files; passed to Pandoc
                 as --resource-path so images are resolved correctly.
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
                pdf_path = _render_pdf(formatted_docx_path, output_dir, style, settings, figures_dir)
                if pdf_path:
                    output_files["pdf"] = pdf_path

            elif fmt == "latex":
                tex_path = _render_latex(formatted_docx_path, output_dir, settings, figures_dir)
                if tex_path:
                    output_files["latex"] = tex_path

            elif fmt == "html":
                html_path = _render_html(formatted_docx_path, output_dir, style, figures_dir)
                if html_path:
                    output_files["html"] = html_path

        except Exception as e:
            log.error("render_failed", format=fmt, error=str(e))

    return output_files


def _write_latex_header(output_dir: str, settings: dict) -> Optional[str]:
    """Write a custom LaTeX header file for styles that need extra packages/formatting.

    Returns the path to the header file, or None if no header is needed.
    """
    extra_packages = settings.get("extra_packages", "")
    footer_text = settings.get("footer", "")

    if not extra_packages and not footer_text:
        return None

    tex_lines = []

    # Extra packages
    if extra_packages:
        for pkg in extra_packages.split(","):
            pkg = pkg.strip()
            if pkg:
                tex_lines.append("\\usepackage{" + pkg + "}")

    # Line spacing
    if "setspace" in extra_packages:
        tex_lines.append("\\setstretch{1.2}")

    # Footer setup
    if footer_text and "fancyhdr" in extra_packages:
        tex_lines += [
            "\\pagestyle{fancy}",
            "\\fancyhf{}",
            "\\fancyfoot[C]{\\small\\textit{" + footer_text + "}}",
            "\\fancyfoot[R]{\\thepage}",
            "\\renewcommand{\\headrulewidth}{0pt}",
        ]
    elif "fancyhdr" in extra_packages:
        tex_lines += [
            "\\pagestyle{fancy}",
            "\\fancyhf{}",
            "\\fancyfoot[C]{\\thepage}",
            "\\renewcommand{\\headrulewidth}{0pt}",
        ]

    if not tex_lines:
        return None

    header_path = str(Path(output_dir) / "latex_header.tex")
    Path(header_path).write_text("\n".join(tex_lines) + "\n", encoding="utf-8")
    return header_path


def _render_pdf(docx_path: str, output_dir: str, style: str, settings: dict,
                figures_dir: Optional[str] = None) -> Optional[str]:
    """Convert DOCX → PDF via Pandoc + XeLaTeX."""
    output_path = Path(output_dir) / "manuscript.pdf"

    # Write custom LaTeX header for styles that need it (crispro, preprint)
    header_path = _write_latex_header(output_dir, settings)

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

    if header_path:
        cmd.extend(["--include-in-header", header_path])

    # Add resource path for figures
    resource_paths = [output_dir]
    if figures_dir and Path(figures_dir).exists():
        resource_paths.append(figures_dir)
    cmd.append("--resource-path=" + ":".join(resource_paths))

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
            return _render_pdf_fallback(docx_path, output_dir, figures_dir)
    except subprocess.TimeoutExpired:
        log.error("pdf_render_timeout")
        return None
    except FileNotFoundError:
        log.error("pandoc_not_found")
        return _render_pdf_fallback(docx_path, output_dir, figures_dir)


def _render_pdf_fallback(docx_path: str, output_dir: str,
                         figures_dir: Optional[str] = None) -> Optional[str]:
    """Fallback PDF render with minimal settings."""
    output_path = Path(output_dir) / "manuscript.pdf"
    cmd = [
        "pandoc", docx_path,
        "-o", str(output_path),
        "--pdf-engine=xelatex",
        "--standalone",
    ]
    if figures_dir and Path(figures_dir).exists():
        cmd.append(f"--resource-path={output_dir}:{figures_dir}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and output_path.exists():
            return str(output_path)
    except Exception:
        pass
    return None


def _render_latex(docx_path: str, output_dir: str, settings: dict,
                  figures_dir: Optional[str] = None) -> Optional[str]:
    """Convert DOCX → LaTeX source via Pandoc."""
    output_path = Path(output_dir) / "manuscript.tex"
    header_path = _write_latex_header(output_dir, settings)
    cmd = [
        "pandoc", docx_path,
        "-o", str(output_path),
        f"--variable=documentclass:{settings['documentclass']}",
        "--standalone",
    ]
    if header_path:
        cmd.extend(["--include-in-header", header_path])
    if figures_dir and Path(figures_dir).exists():
        cmd.append(f"--resource-path={output_dir}:{figures_dir}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and output_path.exists():
            return str(output_path)
        log.warning("latex_render_failed", stderr=result.stderr[:300])
    except Exception as e:
        log.error("latex_render_error", error=str(e))
    return None


def _render_html(docx_path: str, output_dir: str, style: str,
                 figures_dir: Optional[str] = None) -> Optional[str]:
    """Convert DOCX → HTML via Pandoc with journal CSS."""
    import shutil
    output_path = Path(output_dir) / "manuscript.html"
    css = STYLE_CSS.get(style, STYLE_CSS["generic"])

    # Write CSS to temp file
    css_path = Path(output_dir) / "style.css"
    css_path.write_text(css)

    # Copy figures into output dir so HTML <img src> resolves correctly
    if figures_dir:
        figs = Path(figures_dir)
        if figs.exists():
            for img_file in figs.iterdir():
                if img_file.is_file():
                    dest = Path(output_dir) / img_file.name
                    if not dest.exists():
                        shutil.copy2(img_file, dest)

    cmd = [
        "pandoc", docx_path,
        "-o", str(output_path),
        "--standalone",
        f"--css={css_path}",
        "--metadata", f"title=Manuscript",
        "--extract-media=.",
    ]
    if figures_dir and Path(figures_dir).exists():
        cmd.append(f"--resource-path={output_dir}:{figures_dir}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                                cwd=output_dir)
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
