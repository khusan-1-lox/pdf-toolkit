"""Conversion contracts must not depend on system binaries being installed."""
import asyncio
from types import SimpleNamespace

import fitz
import pytest
from PIL import Image
from fastapi import HTTPException

from app.routers import html_to_pdf, ocr, pdfa


def sample_pdf():
    with fitz.open() as doc:
        page = doc.new_page(width=300, height=400)
        page.insert_text((72, 72), "Hello conversion")
        return doc.tobytes()


def test_ocr_requires_engine(client, monkeypatch):
    monkeypatch.setattr(ocr, "HAS_TESS", False)
    response = client.post("/api/ocr-pdf", files={"file": ("test.pdf", sample_pdf(), "application/pdf")})
    assert response.status_code == 503
    assert "Tesseract" in response.json()["detail"]


def test_ocr_preserves_position_and_hidden_text(client, monkeypatch):
    def recognize(image, *, extension, lang, config, timeout):
        assert extension == "pdf"
        assert lang == "eng"
        with fitz.open() as doc:
            page = doc.new_page(width=300, height=400)
            # Simulate the Tesseract PDF contract: image plus positioned invisible text.
            page.draw_rect(page.rect, color=None, fill=(1, 1, 1))
            page.insert_text((100, 240), "Recognized words", fontsize=12, render_mode=3)
            return doc.tobytes()

    monkeypatch.setattr(ocr, "HAS_TESS", True)
    monkeypatch.setattr(ocr, "pytesseract", SimpleNamespace(
        get_tesseract_version=lambda: "5",
        get_languages=lambda config: ["eng"],
        image_to_pdf_or_hocr=recognize,
    ))
    response = client.post("/api/ocr-pdf",
                           files={"file": ("test.pdf", sample_pdf(), "application/pdf")},
                           data={"lang": "eng"})
    assert response.status_code == 200, response.text
    with fitz.open(stream=response.content, filetype="pdf") as doc:
        assert doc[0].rect == fitz.Rect(0, 0, 300, 400)
        words = doc[0].get_text("words")
        assert words[0][4] == "Recognized"
        assert words[0][0] == pytest.approx(100, abs=1)
        assert words[0][1] > 220
        assert all(span["type"] == 3 for span in doc[0].get_texttrace())
        rendered = doc[0].get_pixmap()
        assert min(rendered.samples) == 255


def test_ocr_missing_language(client, monkeypatch):
    monkeypatch.setattr(ocr, "HAS_TESS", True)
    monkeypatch.setattr(ocr, "pytesseract", SimpleNamespace(
        get_tesseract_version=lambda: "5", get_languages=lambda config: ["eng"],
    ))
    response = client.post("/api/ocr-pdf",
                           files={"file": ("test.pdf", sample_pdf(), "application/pdf")},
                           data={"lang": "rus"})
    assert response.status_code == 503
    assert "rus" in response.json()["detail"]


@pytest.mark.parametrize("filename,data", [("test.txt", b"hello"), ("test.pdf", b"")])
def test_ocr_invalid_input(client, filename, data):
    response = client.post("/api/ocr-pdf", files={"file": (filename, data, "application/pdf")})
    assert response.status_code == 400


def test_pdfa_requires_ghostscript(client, monkeypatch):
    monkeypatch.setattr(pdfa.shutil, "which", lambda name: None)
    for route in ("/api/pdf-to-pdfa", "/api/pdfa"):
        response = client.post(route, files={"file": ("test.pdf", sample_pdf(), "application/pdf")})
        assert response.status_code == 503
        assert "Ghostscript" in response.json()["detail"]
        assert "x-pdf-a" not in response.headers


def test_pdfa_rejects_ordinary_pdf(tmp_path):
    ordinary = tmp_path / "ordinary.pdf"
    ordinary.write_bytes(sample_pdf())
    with pytest.raises((ValueError, pdfa.ET.ParseError)):
        pdfa.validate_pdfa_metadata(str(ordinary))


def test_pdfa_strict_command_with_real_icc_profile(tmp_path, monkeypatch):
    source, result = tmp_path / "source.pdf", tmp_path / "result.pdf"
    source.write_bytes(sample_pdf())
    monkeypatch.setattr(pdfa.shutil, "which", lambda name: "ghostscript")
    checked = []

    def run(command, **kwargs):
        assert "-dSAFER" in command
        assert "-dPDFA=2" in command
        assert "-dPDFACompatibilityPolicy=2" in command
        assert kwargs["timeout"] == 120
        profile = (tmp_path / "srgb.icc").read_bytes()
        assert profile[36:40] == b"acsp"
        definition = (tmp_path / "pdfa.ps").read_text()
        assert "/DestOutputProfile {icc_PDFA}" in definition
        assert "/OutputIntents" in definition
        # Producing a plain PDF must still fail the post-conversion structural check.
        result.write_bytes(sample_pdf())
        checked.append(True)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(pdfa.subprocess, "run", run)
    with pytest.raises((ValueError, pdfa.ET.ParseError)):
        asyncio.run(pdfa.convert_to_pdfa(str(source), str(result)))
    assert checked == [True]


def test_html_requires_renderer(client, monkeypatch):
    monkeypatch.setattr(html_to_pdf, "HAS_WP", False)
    response = client.post("/api/html-to-pdf", data={"html": "<h1>Hello</h1>"})
    assert response.status_code == 503
    assert "WeasyPrint" in response.json()["detail"]


def test_html_from_url_preserves_final_base(client, monkeypatch):
    monkeypatch.setattr(html_to_pdf, "fetch_public_resource", lambda url: {
        "string": b"<h1>Downloaded</h1>", "mime_type": "text/html", "encoding": "utf-8",
        "redirected_url": "https://example.com/final/page",
    })

    async def convert(html, path, base):
        assert html == "<h1>Downloaded</h1>"
        assert base == "https://example.com/final/page"
        with open(path, "wb") as output:
            output.write(sample_pdf())

    monkeypatch.setattr(html_to_pdf, "convert_html", convert)
    response = client.post("/api/html-to-pdf", data={"url": "https://example.com"})
    assert response.status_code == 200


@pytest.mark.parametrize("data", [{}, {"html": "<p>x</p>", "url": "https://example.com"}])
def test_html_requires_exactly_one_source(client, data):
    response = client.post("/api/html-to-pdf", data=data)
    assert response.status_code == 400


def test_html_does_not_hide_blocked_resource_errors(client, monkeypatch):
    class FakeRenderer:
        def __init__(self, **kwargs):
            self.fetch = kwargs["url_fetcher"]

        def write_pdf(self, path):
            # WeasyPrint swallows fetch errors. Conversion must still report blocking.
            try:
                self.fetch("file:///etc/passwd")
            except HTTPException:
                pass
            with open(path, "wb") as output:
                output.write(sample_pdf())

    monkeypatch.setattr(html_to_pdf, "HAS_WP", True)
    monkeypatch.setattr(html_to_pdf, "HTML", FakeRenderer)
    response = client.post("/api/html-to-pdf", data={"html": "<img src='file:///etc/passwd'>"})
    assert response.status_code == 400
