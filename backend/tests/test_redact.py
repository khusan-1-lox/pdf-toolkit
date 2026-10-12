import io

def make_pdf_with_text(text="Hello secret world"):
    import fitz as pymupdf
    doc = pymupdf.open()
    page = doc.new_page(width=200, height=200)
    page.insert_text((20, 50), text)
    b = doc.tobytes()
    doc.close()
    return io.BytesIO(b)

def make_pdf_with_image():
    import fitz as pymupdf
    from PIL import Image
    doc = pymupdf.open()
    page = doc.new_page(width=200, height=200)
    img = Image.new("RGB", (50, 50), color=(255,0,0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    # insert image via pixmap
    page.insert_image(pymupdf.Rect(20, 20, 70, 70), stream=buf.getvalue())
    b = doc.tobytes()
    doc.close()
    return io.BytesIO(b)

def test_redact_texts(client):
    pdf = make_pdf_with_text("Hello secret world")
    r = client.post("/api/redact", files=[("file", ("a.pdf", pdf, "application/pdf"))], data={"texts": "secret"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    # verify text removed
    import fitz as pymupdf
    doc = pymupdf.open(stream=r.content, filetype="pdf")
    txt = doc[0].get_text()
    doc.close()
    assert "secret" not in txt

def test_redact_multiple_texts(client):
    pdf = make_pdf_with_text("Hello secret world, hide this")
    r = client.post("/api/redact", files=[("file", ("a.pdf", pdf, "application/pdf"))], data={"texts": "secret, hide"})
    assert r.status_code == 200

def test_redact_hide_images(client):
    pdf = make_pdf_with_image()
    r = client.post("/api/redact", files=[("file", ("a.pdf", pdf, "application/pdf"))], data={"hide_images": "true"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"

def test_redact_hide_images_alt_param(client):
    pdf = make_pdf_with_image()
    r = client.post("/api/redact", files=[("file", ("a.pdf", pdf, "application/pdf"))], data={"redact_images": "true"})
    assert r.status_code == 200

def test_redact_no_params_400(client):
    pdf = make_pdf_with_text()
    r = client.post("/api/redact", files=[("file", ("a.pdf", pdf, "application/pdf"))], data={})
    assert r.status_code == 400

def test_redact_invalid_pdf_400(client):
    r = client.post("/api/redact", files=[("file", ("a.pdf", io.BytesIO(b"not pdf"), "application/pdf"))], data={"texts": "hello"})
    assert r.status_code == 400
