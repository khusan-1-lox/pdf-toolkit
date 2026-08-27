import io
from pypdf import PdfWriter, PdfReader


def make_pdf(pages=1):
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(200, 200)
    b = io.BytesIO()
    w.write(b)
    b.seek(0)
    return b


def test_page_numbers_basic(client):
    pdf = make_pdf(2)
    r = client.post(
        "/api/page-numbers",
        files=[("file", ("a.pdf", pdf, "application/pdf"))],
        data={"position": "bottom-center", "format": "1", "fontSize": "12", "color": "#000000", "margin": "20", "startNumber": "1"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    reader = PdfReader(io.BytesIO(r.content))
    assert len(reader.pages) == 2


def test_page_numbers_all_positions(client):
    for pos in ["bottom-center", "bottom-right", "bottom-left", "top-center", "top-left", "top-right", "center"]:
        pdf = make_pdf(1)
        r = client.post(
            "/api/page-numbers",
            files=[("file", ("a.pdf", pdf, "application/pdf"))],
            data={"position": pos, "format": "1"},
        )
        assert r.status_code == 200, f"failed pos {pos}"


def test_page_numbers_all_formats(client):
    for fmt in ["1", "1 / N", "Page 1", "Page 1 of N"]:
        pdf = make_pdf(2)
        r = client.post(
            "/api/page-numbers",
            files=[("file", ("a.pdf", pdf, "application/pdf"))],
            data={"format": fmt, "position": "bottom-center"},
        )
        assert r.status_code == 200, f"failed fmt {fmt}"


def test_page_numbers_start_number(client):
    pdf = make_pdf(3)
    r = client.post(
        "/api/page-numbers",
        files=[("file", ("a.pdf", pdf, "application/pdf"))],
        data={"startNumber": "5", "format": "Page 1 of N"},
    )
    assert r.status_code == 200
    reader = PdfReader(io.BytesIO(r.content))
    assert len(reader.pages) == 3


def test_page_numbers_invalid_position(client):
    pdf = make_pdf(1)
    r = client.post(
        "/api/page-numbers",
        files=[("file", ("a.pdf", pdf, "application/pdf"))],
        data={"position": "invalid"},
    )
    assert r.status_code == 400


def test_page_numbers_invalid_format(client):
    pdf = make_pdf(1)
    r = client.post(
        "/api/page-numbers",
        files=[("file", ("a.pdf", pdf, "application/pdf"))],
        data={"format": "bad"},
    )
    assert r.status_code == 400


def test_page_numbers_invalid_pdf(client):
    r = client.post(
        "/api/page-numbers",
        files=[("file", ("bad.pdf", io.BytesIO(b"not pdf"), "application/pdf"))],
    )
    assert r.status_code == 400


def test_page_numbers_empty(client):
    r = client.post(
        "/api/page-numbers",
        files=[("file", ("empty.pdf", io.BytesIO(b""), "application/pdf"))],
    )
    assert r.status_code == 400
