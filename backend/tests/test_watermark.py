import io
from pypdf import PdfWriter, PdfReader
from PIL import Image


def make_pdf(pages=1):
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(200, 200)
    b = io.BytesIO()
    w.write(b)
    b.seek(0)
    return b


def make_image(w=80, h=40, color=(255, 0, 0, 255)):
    img = Image.new("RGBA", (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def test_watermark_text_center(client):
    pdf = make_pdf(1)
    r = client.post(
        "/api/watermark",
        files=[("file", ("a.pdf", pdf, "application/pdf"))],
        data={"text": "Test", "position": "center", "opacity": "0.5", "fontSize": "36", "color": "#FF0000", "rotation": "45"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    reader = PdfReader(io.BytesIO(r.content))
    assert len(reader.pages) == 1


def test_watermark_all_positions(client):
    for pos in ["center", "top-left", "top-right", "bottom-left", "bottom-right"]:
        pdf = make_pdf(1)
        r = client.post(
            "/api/watermark",
            files=[("file", ("a.pdf", pdf, "application/pdf"))],
            data={"text": "pos", "position": pos, "opacity": "0.3"},
        )
        assert r.status_code == 200, f"failed pos {pos}"


def test_watermark_image(client):
    pdf = make_pdf(1)
    img = make_image()
    r = client.post(
        "/api/watermark",
        files=[("file", ("a.pdf", pdf, "application/pdf")), ("image", ("wm.png", img, "image/png"))],
        data={"position": "bottom-right", "opacity": "0.4"},
    )
    assert r.status_code == 200
    reader = PdfReader(io.BytesIO(r.content))
    assert len(reader.pages) == 1


def test_watermark_both(client):
    pdf = make_pdf(2)
    img = make_image(60, 60, (0, 255, 0, 180))
    r = client.post(
        "/api/watermark",
        files=[("file", ("a.pdf", pdf, "application/pdf")), ("image", ("wm.png", img, "image/png"))],
        data={"text": "Both", "position": "center", "opacity": "0.5", "fontSize": "24", "color": "#0000FF", "rotation": "30"},
    )
    assert r.status_code == 200
    reader = PdfReader(io.BytesIO(r.content))
    assert len(reader.pages) == 2


def test_watermark_no_text_or_image_400(client):
    pdf = make_pdf(1)
    r = client.post(
        "/api/watermark",
        files=[("file", ("a.pdf", pdf, "application/pdf"))],
        data={"position": "center"},
    )
    assert r.status_code == 400


def test_watermark_invalid_opacity(client):
    pdf = make_pdf(1)
    r = client.post(
        "/api/watermark",
        files=[("file", ("a.pdf", pdf, "application/pdf"))],
        data={"text": "hi", "opacity": "5"},
    )
    assert r.status_code == 400


def test_watermark_invalid_position(client):
    pdf = make_pdf(1)
    r = client.post(
        "/api/watermark",
        files=[("file", ("a.pdf", pdf, "application/pdf"))],
        data={"text": "hi", "position": "invalid"},
    )
    assert r.status_code == 400
