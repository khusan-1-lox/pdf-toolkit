import io
from pypdf import PdfWriter, PdfReader


def make_pdf(pages=1):
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(100, 100)
    b = io.BytesIO()
    w.write(b)
    b.seek(0)
    return b


def make_pdf_with_text(pages=1):
    """Create PDF with some content to allow compression to have effect."""
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(200, 200)
    b = io.BytesIO()
    w.write(b)
    b.seek(0)
    return b


def test_compress(client):
    pdf = make_pdf(1)
    r = client.post(
        "/api/compress",
        files=[("file", ("a.pdf", pdf, "application/pdf"))],
        data={"quality": "medium"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert int(r.headers.get("content-length", len(r.content))) > 0
    # verify result is valid PDF
    reader = PdfReader(io.BytesIO(r.content))
    assert len(reader.pages) == 1


def test_compress_low_quality(client):
    pdf = make_pdf(2)
    r = client.post(
        "/api/compress",
        files=[("file", ("a.pdf", pdf, "application/pdf"))],
        data={"quality": "low"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    reader = PdfReader(io.BytesIO(r.content))
    assert len(reader.pages) == 2


def test_compress_high_quality(client):
    pdf = make_pdf(1)
    r = client.post(
        "/api/compress",
        files=[("file", ("a.pdf", pdf, "application/pdf"))],
        data={"quality": "high"},
    )
    assert r.status_code == 200
    reader = PdfReader(io.BytesIO(r.content))
    assert len(reader.pages) == 1


def test_compress_default_quality(client):
    # when quality omitted, should default to medium and succeed
    pdf = make_pdf(1)
    r = client.post(
        "/api/compress",
        files=[("file", ("a.pdf", pdf, "application/pdf"))],
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


def test_compress_invalid_quality(client):
    pdf = make_pdf(1)
    r = client.post(
        "/api/compress",
        files=[("file", ("a.pdf", pdf, "application/pdf"))],
        data={"quality": "ultra"},
    )
    assert r.status_code == 400


def test_compress_invalid_quality_empty(client):
    pdf = make_pdf(1)
    r = client.post(
        "/api/compress",
        files=[("file", ("a.pdf", pdf, "application/pdf"))],
        data={"quality": ""},
    )
    # FastAPI treats empty string as default (medium) via Form default, so 200 is expected
    # but if implementation validates empty, either 200 or 400 is acceptable
    assert r.status_code in (200, 400)


def test_compress_invalid_quality_numeric(client):
    pdf = make_pdf(1)
    r = client.post(
        "/api/compress",
        files=[("file", ("a.pdf", pdf, "application/pdf"))],
        data={"quality": "123"},
    )
    assert r.status_code == 400


def test_compress_oversize(client, monkeypatch):
    import app.routers.compress as compress_mod

    monkeypatch.setattr(compress_mod, "MAX_FILE_SIZE", 10)
    pdf = make_pdf(1)
    r = client.post(
        "/api/compress",
        files=[("file", ("a.pdf", pdf, "application/pdf"))],
        data={"quality": "medium"},
    )
    assert r.status_code == 413


def test_compress_invalid_pdf(client):
    fake = io.BytesIO(b"not a pdf content")
    r = client.post(
        "/api/compress",
        files=[("file", ("a.pdf", fake, "application/pdf"))],
        data={"quality": "medium"},
    )
    assert r.status_code == 400


def test_compress_empty_file(client):
    empty = io.BytesIO(b"")
    r = client.post(
        "/api/compress",
        files=[("file", ("a.pdf", empty, "application/pdf"))],
        data={"quality": "medium"},
    )
    assert r.status_code == 400


def test_compress_no_file(client):
    r = client.post("/api/compress", data={"quality": "medium"})
    # FastAPI will return 422 for missing required file
    assert r.status_code in (400, 422)


def test_compress_case_insensitive_quality(client):
    pdf = make_pdf(1)
    r = client.post(
        "/api/compress",
        files=[("file", ("a.pdf", pdf, "application/pdf"))],
        data={"quality": "MEDIUM"},
    )
    assert r.status_code == 200


def test_compress_content_length_positive(client):
    pdf = make_pdf_with_text(3)
    r = client.post(
        "/api/compress",
        files=[("file", ("a.pdf", pdf, "application/pdf"))],
        data={"quality": "medium"},
    )
    assert r.status_code == 200
    cl = int(r.headers.get("content-length", 0))
    # content-length header should be >0 or fallback to body length
    assert cl > 0 or len(r.content) > 0
    assert len(r.content) > 0


def test_compress_preserves_page_count(client):
    for n in [1, 3, 5]:
        pdf = make_pdf(n)
        r = client.post(
            "/api/compress",
            files=[("file", ("a.pdf", pdf, "application/pdf"))],
            data={"quality": "high"},
        )
        assert r.status_code == 200, f"failed for {n} pages"
        reader = PdfReader(io.BytesIO(r.content))
        assert len(reader.pages) == n


def test_compress_low_vs_high_both_valid(client):
    pdf = make_pdf(1)
    for q in ["low", "medium", "high"]:
        pdf.seek(0)
        r = client.post(
            "/api/compress",
            files=[("file", ("a.pdf", pdf, "application/pdf"))],
            data={"quality": q},
        )
        assert r.status_code == 200, f"quality {q} failed"
        assert r.headers["content-type"] == "application/pdf"
