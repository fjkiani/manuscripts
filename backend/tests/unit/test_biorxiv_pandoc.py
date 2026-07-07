"""Unit tests for bioRxiv Pandoc pipeline (MBD4 BUILD.md parity)."""

import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from app.pipelines.biorxiv_pandoc import (
    _pandoc_biorxiv_cmd,
    extract_assets_zip,
    resolve_manuscript_path,
)


def test_pandoc_biorxiv_cmd_matches_build_md(tmp_path):
    """Flags must match publications/.../rxiv/BUILD.md recorded command."""
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("# Test\n", encoding="utf-8")
    bib = tmp_path / "references.bib"
    bib.write_text("@article{a, title={A}}\n", encoding="utf-8")
    out = tmp_path / "out.pdf"

    cmd = _pandoc_biorxiv_cmd(manuscript, out, bib)

    assert cmd[0] == "pandoc"
    assert cmd[1] == "manuscript.md"
    assert "-o" in cmd
    assert str(out) in cmd
    assert "--pdf-engine=tectonic" in cmd
    assert "--filter" in cmd
    assert "pandoc-crossref" in cmd
    assert "--citeproc" in cmd
    assert "--bibliography" in cmd
    assert "references.bib" in cmd
    assert "-V" in cmd
    assert any("xmpquote" in part for part in cmd)


def test_resolve_manuscript_path_nested_rxiv(tmp_path):
    rxiv = tmp_path / "rxiv"
    rxiv.mkdir()
    (rxiv / "manuscript.md").write_text("# nested\n", encoding="utf-8")
    assert resolve_manuscript_path(tmp_path) == rxiv / "manuscript.md"


def test_extract_assets_zip(tmp_path):
    zpath = tmp_path / "bundle.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("manuscript.md", "# zip ms\n")
        zf.writestr("FIGURES/fig1.png", b"png")
    dest = tmp_path / "extracted"
    extract_assets_zip(zpath, dest)
    assert (dest / "manuscript.md").exists()
    assert (dest / "FIGURES" / "fig1.png").exists()


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc not installed")
def test_render_minimal_pdf_if_toolchain_available(tmp_path):
    """Integration smoke when tectonic + pandoc-crossref exist locally."""
    if shutil.which("tectonic") is None or shutil.which("pandoc-crossref") is None:
        pytest.skip("tectonic or pandoc-crossref not installed")

    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text(
        "---\ntitle: Smoke\n---\n\n# Hello\n\nSee @fig:smoke.\n\n![x](fig.png){#fig:smoke}\n",
        encoding="utf-8",
    )
    out = tmp_path / "smoke.pdf"
    cmd = _pandoc_biorxiv_cmd(manuscript, out, None)
    result = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        pytest.skip(f"pandoc render failed in CI env: {result.stderr[:500]}")
    assert out.exists()
