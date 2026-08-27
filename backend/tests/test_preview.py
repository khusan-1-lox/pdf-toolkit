import io
from pypdf import PdfWriter


def make_pdf(pages=1):
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(100, 100)
    b = io.BytesIO()
    w.write(b)
    b.seek(0)
    return b


def test_preview_single(client):
    pdf = make_pdf(1)
    r = client.post("/api/preview", files={"file": ("a.pdf", pdf, "application/pdf")})
    assert r.status_code == 200
    j = r.json()
    assert j["numPages"] == 1
    assert len(j["pages"]) == 1
    assert j["pages"][0]["page"] == 0
    assert j["pages"][0]["thumb"].startswith("data:image/")


def test_preview_multi(client):
    pdf = make_pdf(3)
    r = client.post("/api/preview", files={"file": ("a.pdf", pdf, "application/pdf")})
    assert r.status_code == 200
    j = r.json()
    assert j["numPages"] == 3
    assert len(j["pages"]) == 3
    for p in j["pages"]:
        assert p["thumb"].startswith("data:image/")


def test_preview_invalid(client):
    r = client.post("/api/preview", files={"file": ("bad.pdf", io.BytesIO(b"not pdf"), "application/pdf")})
    assert r.status_code == 400


def test_preview_empty(client):
    r = client.post("/api/preview", files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")})
    assert r.status_code == 400
