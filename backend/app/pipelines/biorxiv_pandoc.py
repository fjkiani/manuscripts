"""
bioRxiv / preprint PDF pipeline — matches CrisPRO MBD4 BUILD.md exactly.

Recorded command (publications/00-mbd4-manuscript/mbd4_parp_response/rxiv/BUILD.md):

    pandoc manuscript.md \\
      -o mbd4_parp_response_biorxiv_submission.pdf \\
      --pdf-engine=tectonic \\
      --filter pandoc-crossref \\
      --citeproc
"""

from __future__ import annotations

import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Optional

import structlog

log = structlog.get_logger()

BIORXIV_PDF_ENGINE = os.getenv("BIORXIV_PDF_ENGINE", "tectonic")
CROSSREF_FILTER = os.getenv("PANDOC_CROSSREF_FILTER", "pandoc-crossref")

# BUILD.md: required for tectonic when Pandoc emits \\xmpquote in pdfkeywords
DEFAULT_HEADER_INCLUDES = r"""\providecommand{\xmpquote}[1]{#1}
"""


def extract_assets_zip(zip_path: str | Path, dest_dir: str | Path) -> Path:
    """Extract optional bundle zip (manuscript.md, FIGURES/, references.bib)."""
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest)
    log.info("biorxiv_assets_extracted", dest=str(dest), members=len(zipfile.ZipFile(zip_path).namelist()))
    return dest


def resolve_manuscript_path(work_dir: Path, preferred_name: str = "manuscript.md") -> Path:
    """Locate manuscript markdown inside a job directory."""
    direct = work_dir / preferred_name
    if direct.exists():
        return direct
    nested = work_dir / "rxiv" / preferred_name
    if nested.exists():
        return nested
    for candidate in sorted(work_dir.rglob("*.md")):
        if candidate.name in (preferred_name, "input.md"):
            return candidate
    raise FileNotFoundError(f"No manuscript markdown found under {work_dir}")


def _ensure_bibliography(work_dir: Path, bibliography_path: Optional[str]) -> Optional[Path]:
    if not bibliography_path:
        local = work_dir / "references.bib"
        return local if local.exists() else None
    src = Path(bibliography_path)
    if not src.exists():
        return None
    dest = work_dir / "references.bib"
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    return dest


def _pandoc_biorxiv_cmd(
    manuscript: Path,
    output_pdf: Path,
    bibliography: Optional[Path],
    *,
    inject_tectonic_header: bool = True,
) -> list[str]:
    cmd = [
        "pandoc",
        manuscript.name,
        "-o",
        str(output_pdf),
        f"--pdf-engine={BIORXIV_PDF_ENGINE}",
        "--filter",
        CROSSREF_FILTER,
        "--citeproc",
    ]
    if bibliography and bibliography.exists():
        cmd.extend(["--bibliography", bibliography.name])
    # BUILD.md: tectonic fails on \\xmpquote unless defined (YAML may omit header-includes).
    if inject_tectonic_header:
        cmd.extend(["-V", f"header-includes:{DEFAULT_HEADER_INCLUDES.strip()}"])
    return cmd


def render_biorxiv_pdf(
    manuscript_path: str | Path,
    output_pdf: str | Path,
    bibliography_path: Optional[str | Path] = None,
    timeout_sec: int = 300,
) -> str:
    """
    Render PDF from Pandoc markdown using the MBD4-recorded toolchain.
    Runs with cwd=manuscript parent so relative FIGURES/ paths resolve.
    """
    manuscript = Path(manuscript_path).resolve()
    work_dir = manuscript.parent
    output_pdf = Path(output_pdf).resolve()
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    bib = _ensure_bibliography(work_dir, str(bibliography_path) if bibliography_path else None)

    cmd = _pandoc_biorxiv_cmd(manuscript, output_pdf, bib)
    log.info("biorxiv_pandoc_start", cmd=cmd, cwd=str(work_dir))

    result = subprocess.run(
        cmd,
        cwd=str(work_dir),
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    if result.returncode != 0 or not output_pdf.exists():
        raise RuntimeError(
            f"biorxiv pandoc failed (exit {result.returncode}): {result.stderr[-2000:]}"
        )

    log.info("biorxiv_pdf_rendered", path=str(output_pdf), size=output_pdf.stat().st_size)
    return str(output_pdf)


def render_biorxiv_html(
    manuscript_path: str | Path,
    output_html: str | Path,
    bibliography_path: Optional[str | Path] = None,
    timeout_sec: int = 120,
) -> str:
    """HTML export with crossrefs + citeproc (no tectonic)."""
    manuscript = Path(manuscript_path).resolve()
    work_dir = manuscript.parent
    output_html = Path(output_html).resolve()
    bib = _ensure_bibliography(work_dir, str(bibliography_path) if bibliography_path else None)

    cmd = [
        "pandoc",
        manuscript.name,
        "-o",
        str(output_html),
        "--standalone",
        "--filter",
        CROSSREF_FILTER,
        "--citeproc",
    ]
    if bib and bib.exists():
        cmd.extend(["--bibliography", bib.name])

    result = subprocess.run(cmd, cwd=str(work_dir), capture_output=True, text=True, timeout=timeout_sec)
    if result.returncode != 0 or not output_html.exists():
        raise RuntimeError(f"biorxiv html pandoc failed: {result.stderr[-1500:]}")
    return str(output_html)


def render_biorxiv_outputs(
    work_dir: str | Path,
    output_dir: str | Path,
    outputs: list[str],
    bibliography_path: Optional[str] = None,
    manuscript_filename: str = "manuscript.md",
) -> dict[str, str]:
    """
    Render requested outputs from a bioRxiv bundle directory.
    Expects work_dir to contain manuscript.md (or rxiv/manuscript.md) and optional FIGURES/.
    """
    work = Path(work_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    manuscript = resolve_manuscript_path(work, manuscript_filename)
    output_files: dict[str, str] = {}

    if "pdf" in outputs:
        pdf_path = out / "manuscript.pdf"
        output_files["pdf"] = render_biorxiv_pdf(manuscript, pdf_path, bibliography_path)

    if "html" in outputs:
        html_path = out / "manuscript.html"
        output_files["html"] = render_biorxiv_html(manuscript, html_path, bibliography_path)

    if "latex" in outputs:
        tex_path = out / "manuscript.tex"
        bib = _ensure_bibliography(work, bibliography_path)
        cmd = [
            "pandoc",
            manuscript.name,
            "-o",
            str(tex_path),
            "--standalone",
            "--filter",
            CROSSREF_FILTER,
        ]
        if bib and bib.exists():
            cmd.extend(["--bibliography", bib.name])
        result = subprocess.run(cmd, cwd=str(work), capture_output=True, text=True, timeout=120)
        if result.returncode == 0 and tex_path.exists():
            output_files["latex"] = str(tex_path)

    # bioRxiv path is Pandoc-native; no DOCX formatter step
    if "docx" in outputs:
        docx_path = out / "manuscript.docx"
        bib = _ensure_bibliography(work, bibliography_path)
        cmd = ["pandoc", manuscript.name, "-o", str(docx_path), "--filter", CROSSREF_FILTER, "--citeproc"]
        if bib and bib.exists():
            cmd.extend(["--bibliography", bib.name])
        result = subprocess.run(cmd, cwd=str(work), capture_output=True, text=True, timeout=120)
        if result.returncode == 0 and docx_path.exists():
            output_files["docx"] = str(docx_path)

    return output_files


def verify_pdf_text_layer(pdf_path: str | Path) -> dict[str, bool]:
    """Optional checks from MBD4 BUILD.md (requires PyPDF2)."""
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        return {"skipped": True}

    reader = PdfReader(str(pdf_path))
    text = "".join((page.extract_text() or "") for page in reader.pages)
    return {
        "no_raw_citation_keys": "[@" not in text,
        "no_raw_figure_keys": "@fig:" not in text,
        "has_references": "References" in text,
        "has_author": "Kiani" in text,
    }
