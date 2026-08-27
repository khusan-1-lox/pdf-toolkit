import io
from pypdf import PdfWriter, PdfReader

try:
    import fitz  # type: ignore
except ImportError:
    import pymupdf as fitz  # type: ignore


def make_pdf(pages=1, w=200, h=300):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=w, height=h)
    b = io.BytesIO()
    writer.write(b)
    b.seek(0)
    return b


def test_crop_margins_basic(client):
    pdf = make_pdf(2)
    r = client.post(
        "/api/crop",
        files=[("file", ("a.pdf", pdf, "application/pdf"))],
        data={"mode": "margins", "top": "10", "bottom": "10", "left": "10", "right": "10", "unit": "pt", "pages": "all"},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    reader = PdfReader(io.BytesIO(r.content))
    assert len(reader.pages) == 2
    # verify cropbox applied
    doc = fitz.open(stream=r.content, filetype="pdf")
    for page in doc:
        cb = page.cropbox
        # original 200x300, margins 10 each => 180x280 cropbox
        assert abs(cb.width - 180) < 0.5
        assert abs(cb.height - 280) < 0.5
    doc.close()


def test_crop_rect_basic(client):
    pdf = make_pdf(1, w=400, h=400)
    r = client.post(
        "/api/crop",
        files=[("file", ("a.pdf", pdf, "application/pdf"))],
        data={"mode": "rect", "x": "50", "y": "50", "w": "100", "h": "100", "pages": "all"},
    )
    assert r.status_code == 200, r.text
    doc = fitz.open(stream=r.content, filetype="pdf")
    page = doc.load_page(0)
    cb = page.cropbox
    assert abs(cb.width - 100) < 0.5
    assert abs(cb.height - 100) < 0.5
    doc.close()


def test_crop_margins_mm(client):
    pdf = make_pdf(1, w=595, h=842)  # A4
    r = client.post(
        "/api/crop",
        files=[("file", ("a.pdf", pdf, "application/pdf"))],
        data={"mode": "margins", "top": "10", "bottom": "10", "left": "10", "right": "10", "unit": "mm", "pages": "all"},
    )
    assert r.status_code == 200, r.text
    doc = fitz.open(stream=r.content, filetype="pdf")
    cb = doc.load_page(0).cropbox
    # 10mm ~ 28.34pt, so width ~ 595-56.69=538.3
    assert abs(cb.width - (595 - 56.69)) < 1.0
    doc.close()


def test_crop_pages_specific(client):
    pdf = make_pdf(3, w=200, h=200)
    r = client.post(
        "/api/crop",
        files=[("file", ("a.pdf", pdf, "application/pdf"))],
        data={"mode": "margins", "top": "20", "left": "20", "right": "20", "bottom": "20", "unit": "pt", "pages": "1,3"},
    )
    assert r.status_code == 200, r.text
    doc = fitz.open(stream=r.content, filetype="pdf")
    cb0 = doc.load_page(0).cropbox
    cb1 = doc.load_page(1).cropbox
    cb2 = doc.load_page(2).cropbox
    assert abs(cb0.width - 160) < 0.5
    assert abs(cb1.width - 200) < 0.5  # page 2 unchanged
    assert abs(cb2.width - 160) < 0.5
    doc.close()


def test_crop_margins_too_large(client):
    pdf = make_pdf(1, w=100, h=100)
    r = client.post(
        "/api/crop",
        files=[("file", ("a.pdf", pdf, "application/pdf"))],
        data={"mode": "margins", "top": "60", "bottom": "60", "left": "0", "right": "0", "unit": "pt", "pages": "all"},
    )
    assert r.status_code == 400


def test_crop_rect_out_of_bounds(client):
    pdf = make_pdf(1, w=200, h=200)
    r = client.post(
        "/api/crop",
        files=[("file", ("a.pdf", pdf, "application/pdf"))],
        data={"mode": "rect", "x": "150", "y": "150", "w": "100", "h": "100", "pages": "all"},
    )
    assert r.status_code == 400


def test_crop_invalid_mode(client):
    pdf = make_pdf(1)
    r = client.post(
        "/api/crop",
        files=[("file", ("a.pdf", pdf, "application/pdf"))],
        data={"mode": "bad"},
    )
    assert r.status_code == 400


def test_crop_invalid_pdf(client):
    r = client.post(
        "/api/crop",
        files=[("file", ("bad.pdf", io.BytesIO(b"not pdf"), "application/pdf"))],
        data={"mode": "margins", "top": "10", "left": "10"},
    )
    assert r.status_code == 400


def test_crop_empty(client):
    r = client.post(
        "/api/crop",
        files=[("file", ("empty.pdf", io.BytesIO(b""), "application/pdf"))],
        data={"mode": "margins", "top": "10"},
    )
    assert r.status_code == 400
