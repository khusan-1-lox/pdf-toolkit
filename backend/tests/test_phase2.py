import tempfile
import os
import fitz


def test_ocr_route(client):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello OCR test")
    pdf_bytes = doc.tobytes()
    doc.close()

    resp = client.post(
        "/api/ocr-pdf",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"
    # check output pdf has pages
    tmp = tempfile.mktemp(suffix=".pdf")
    try:
        with open(tmp, "wb") as f:
            f.write(resp.content)
        d = fitz.open(tmp)
        assert len(d) >= 1
        d.close()
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def test_ocr_invalid_extension(client):
    resp = client.post(
        "/api/ocr-pdf",
        files={"file": ("test.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400


def test_ocr_empty(client):
    resp = client.post(
        "/api/ocr-pdf",
        files={"file": ("test.pdf", b"", "application/pdf")},
    )
    assert resp.status_code == 400


def test_ocr_with_lang_param(client):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello lang")
    pdf_bytes = doc.tobytes()
    doc.close()
    resp = client.post(
        "/api/ocr-pdf",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        data={"lang": "eng"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"


def test_pdfa_route(client):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello PDF/A test")
    pdf_bytes = doc.tobytes()
    doc.close()

    resp = client.post(
        "/api/pdf-to-pdfa",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"
    # verify header
    assert resp.headers.get("x-pdf-a") == "true" or resp.headers.get("X-PDF-A") == "true"
    tmp = tempfile.mktemp(suffix=".pdf")
    try:
        with open(tmp, "wb") as f:
            f.write(resp.content)
        d = fitz.open(tmp)
        assert len(d) >= 1
        d.close()
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def test_html_to_pdf_route(client):
    # via html string Form field
    resp = client.post(
        "/api/html-to-pdf",
        data={"html": "<h1>Hello</h1><p>test</p>"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"
    tmp = tempfile.mktemp(suffix=".pdf")
    try:
        with open(tmp, "wb") as f:
            f.write(resp.content)
        d = fitz.open(tmp)
        assert len(d) >= 1
        d.close()
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    # via html file upload
    html_bytes = b"<html><body><h1>Hello file</h1><p>test file</p></body></html>"
    resp2 = client.post(
        "/api/html-to-pdf",
        files={"file": ("test.html", html_bytes, "text/html")},
    )
    assert resp2.status_code == 200, resp2.text
    assert resp2.headers["content-type"] == "application/pdf"
    assert resp2.content[:4] == b"%PDF"


def test_html_to_pdf_from_url(client):
    from unittest.mock import patch, AsyncMock, MagicMock

    mock_resp = MagicMock()
    mock_resp.text = "<h1>Mocked URL</h1><p>hello world</p>"
    mock_resp.content = b"<h1>Mocked URL</h1><p>hello world</p>"
    mock_resp.raise_for_status = lambda: None
    mock_instance = AsyncMock()
    mock_instance.get = AsyncMock(return_value=mock_resp)
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    with patch("httpx.AsyncClient", return_value=mock_cm):
        resp = client.post(
            "/api/html-to-pdf",
            data={"url": "http://example.com"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:4] == b"%PDF"
        tmp = tempfile.mktemp(suffix=".pdf")
        try:
            with open(tmp, "wb") as f:
                f.write(resp.content)
            d = fitz.open(tmp)
            assert len(d) >= 1
            d.close()
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
