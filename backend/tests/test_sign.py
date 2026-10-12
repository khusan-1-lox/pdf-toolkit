import io
from PIL import Image

def make_pdf(pages=1):
    import fitz as pymupdf
    doc = pymupdf.open()
    for _ in range(pages):
        doc.new_page(width=595, height=842)
    b = doc.tobytes()
    doc.close()
    return io.BytesIO(b)

def make_image(w=80, h=40, color=(255,0,0,255)):
    img = Image.new("RGBA", (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def test_sign_position_bottom_right(client):
    pdf = make_pdf(1)
    img = make_image()
    r = client.post("/api/sign", files=[("file", ("a.pdf", pdf, "application/pdf")), ("image", ("sig.png", img, "image/png"))], data={"position": "bottom-right", "opacity": "0.8", "page": "all"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(r.content))
    assert len(reader.pages) == 1

def test_sign_xywh(client):
    pdf = make_pdf(1)
    img = make_image(60, 60, (0,255,0,255))
    r = client.post("/api/sign", files=[("file", ("a.pdf", pdf, "application/pdf")), ("image", ("sig.png", img, "image/png"))], data={"x": "10", "y": "20", "w": "100", "h": "50", "opacity": "0.5", "page": "1"})
    assert r.status_code == 200

def test_sign_center_opacity_percent(client):
    pdf = make_pdf(2)
    img = make_image()
    r = client.post("/api/sign", files=[("file", ("a.pdf", pdf, "application/pdf")), ("image", ("sig.png", img, "image/png"))], data={"position": "center", "opacity": "0.8", "page": "all"})
    assert r.status_code == 200

def test_sign_missing_image_400(client):
    pdf = make_pdf(1)
    r = client.post("/api/sign", files=[("file", ("a.pdf", pdf, "application/pdf"))], data={"position": "bottom-right"})
    assert r.status_code == 422 or r.status_code == 400

def test_sign_invalid_opacity_400(client):
    pdf = make_pdf(1)
    img = make_image()
    r = client.post("/api/sign", files=[("file", ("a.pdf", pdf, "application/pdf")), ("image", ("sig.png", img, "image/png"))], data={"opacity": "5"})
    assert r.status_code == 400

def test_sign_invalid_position_400(client):
    pdf = make_pdf(1)
    img = make_image()
    r = client.post("/api/sign", files=[("file", ("a.pdf", pdf, "application/pdf")), ("image", ("sig.png", img, "image/png"))], data={"position": "invalid-pos"})
    assert r.status_code == 400
