import io
import zipfile
from pypdf import PdfWriter, PdfReader
from PIL import Image


def make_pdf(pages=1):
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(100, 100)
    b = io.BytesIO()
    w.write(b)
    b.seek(0)
    return b


def make_jpeg(color="red", size=(100, 100), fmt="JPEG"):
    im = Image.new("RGB", size, color)
    b = io.BytesIO()
    im.save(b, fmt)
    b.seek(0)
    return b


def make_png(color="blue", size=(100, 100)):
    return make_jpeg(color=color, size=size, fmt="PNG")


# --- pdf -> jpg ---

def test_pdf_to_jpg(client):
    pdf = make_pdf(2)
    r = client.post("/api/pdf-to-jpg", files=[("file", ("a.pdf", pdf, "application/pdf"))])
    assert r.status_code == 200, r.text
    assert "zip" in r.headers["content-type"]
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = z.namelist()
    assert len(names) == 2
    for name in names:
        assert name.endswith(".jpg")
        data = z.read(name)
        # verify it is a valid JPEG via Pillow
        img = Image.open(io.BytesIO(data))
        assert img.format == "JPEG"


def test_pdf_to_jpg_single_page(client):
    pdf = make_pdf(1)
    r = client.post("/api/pdf-to-jpg", files=[("file", ("single.pdf", pdf, "application/pdf"))])
    assert r.status_code == 200
    assert "zip" in r.headers["content-type"]
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert len(z.namelist()) == 1
    data = z.read(z.namelist()[0])
    img = Image.open(io.BytesIO(data))
    assert img.format == "JPEG"


def test_pdf_to_jpg_invalid_file(client):
    fake = io.BytesIO(b"not a pdf content")
    r = client.post("/api/pdf-to-jpg", files=[("file", ("a.pdf", fake, "application/pdf"))])
    assert r.status_code == 400


def test_pdf_to_jpg_empty_file(client):
    empty = io.BytesIO(b"")
    r = client.post("/api/pdf-to-jpg", files=[("file", ("a.pdf", empty, "application/pdf"))])
    assert r.status_code == 400


def test_pdf_to_jpg_no_file(client):
    r = client.post("/api/pdf-to-jpg")
    assert r.status_code == 422


def test_pdf_to_jpg_oversize(client, monkeypatch):
    import app.routers.pdf_to_jpg as mod

    monkeypatch.setattr(mod, "MAX_FILE_SIZE", 10)
    pdf = make_pdf(1)
    r = client.post("/api/pdf-to-jpg", files=[("file", ("a.pdf", pdf, "application/pdf"))])
    assert r.status_code == 413


# --- jpg -> pdf ---

def test_jpg_to_pdf(client):
    jpg = make_jpeg("red")
    r = client.post("/api/jpg-to-pdf", files=[("files", ("a.jpg", jpg, "image/jpeg"))])
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    reader = PdfReader(io.BytesIO(r.content))
    assert len(reader.pages) == 1


def test_jpg_to_pdf_multiple(client):
    jpg1 = make_jpeg("red")
    jpg2 = make_jpeg("blue")
    png = make_png("green")
    r = client.post(
        "/api/jpg-to-pdf",
        files=[
            ("files", ("a.jpg", jpg1, "image/jpeg")),
            ("files", ("b.jpg", jpg2, "image/jpeg")),
            ("files", ("c.png", png, "image/png")),
        ],
    )
    assert r.status_code == 200
    reader = PdfReader(io.BytesIO(r.content))
    assert len(reader.pages) == 3


def test_jpg_to_pdf_png_input(client):
    png = make_png("green")
    r = client.post("/api/jpg-to-pdf", files=[("files", ("a.png", png, "image/png"))])
    assert r.status_code == 200
    reader = PdfReader(io.BytesIO(r.content))
    assert len(reader.pages) == 1


def test_jpg_to_pdf_invalid_file(client):
    fake = io.BytesIO(b"not an image")
    r = client.post("/api/jpg-to-pdf", files=[("files", ("a.jpg", fake, "image/jpeg"))])
    assert r.status_code == 400


def test_jpg_to_pdf_empty_file(client):
    empty = io.BytesIO(b"")
    r = client.post("/api/jpg-to-pdf", files=[("files", ("a.jpg", empty, "image/jpeg"))])
    assert r.status_code == 400


def test_jpg_to_pdf_no_file(client):
    r = client.post("/api/jpg-to-pdf")
    # FastAPI returns 422 for missing required files
    assert r.status_code in (400, 422)


def test_jpg_to_pdf_oversize(client, monkeypatch):
    import app.routers.jpg_to_pdf as mod

    monkeypatch.setattr(mod, "MAX_FILE_SIZE", 10)
    jpg = make_jpeg("red")
    r = client.post("/api/jpg-to-pdf", files=[("files", ("a.jpg", jpg, "image/jpeg"))])
    assert r.status_code == 413


def test_jpg_to_pdf_too_many_files(client):
    files = [("files", (f"{i}.jpg", make_jpeg("red"), "image/jpeg")) for i in range(11)]
    r = client.post("/api/jpg-to-pdf", files=files)
    assert r.status_code == 413


def test_jpg_to_pdf_rgba_png(client):
    # PNG with transparency should be flattened
    im = Image.new("RGBA", (100, 100), (255, 0, 0, 128))
    b = io.BytesIO()
    im.save(b, "PNG")
    b.seek(0)
    r = client.post("/api/jpg-to-pdf", files=[("files", ("a.png", b, "image/png"))])
    assert r.status_code == 200
    reader = PdfReader(io.BytesIO(r.content))
    assert len(reader.pages) == 1
