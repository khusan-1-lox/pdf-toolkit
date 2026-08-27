import io
import zipfile
from pypdf import PdfWriter, PdfReader


def make_pdf(pages=1):
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(100, 100)
    b = io.BytesIO()
    w.write(b)
    b.seek(0)
    return b


def test_split(client):
    pdf = make_pdf(3)
    r = client.post("/api/split", files=[("file", ("a.pdf", pdf, "application/pdf"))], data={"pages": "1-2"})
    assert r.status_code == 200
    assert "zip" in r.headers["content-type"]
    # verify zip contains 2 files, each 1 page
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert len(z.namelist()) == 2
    for name in z.namelist():
        data = z.read(name)
        reader = PdfReader(io.BytesIO(data))
        assert len(reader.pages) == 1


def test_split_comma_list(client):
    pdf = make_pdf(5)
    r = client.post("/api/split", files=[("file", ("a.pdf", pdf, "application/pdf"))], data={"pages": "1,3-5"})
    assert r.status_code == 200
    assert "zip" in r.headers["content-type"]
    z = zipfile.ZipFile(io.BytesIO(r.content))
    # 1,3,4,5 = 4 files
    assert len(z.namelist()) == 4


def test_delete(client):
    pdf = make_pdf(3)
    r = client.post("/api/delete", files=[("file", ("a.pdf", pdf, "application/pdf"))], data={"pages": "2"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    reader = PdfReader(io.BytesIO(r.content))
    assert len(reader.pages) == 2


def test_delete_multiple(client):
    pdf = make_pdf(4)
    r = client.post("/api/delete", files=[("file", ("a.pdf", pdf, "application/pdf"))], data={"pages": "2,4"})
    assert r.status_code == 200
    reader = PdfReader(io.BytesIO(r.content))
    assert len(reader.pages) == 2


def test_rotate(client):
    pdf = make_pdf(1)
    r = client.post("/api/rotate", files=[("file", ("a.pdf", pdf, "application/pdf"))], data={"angle": "90"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    reader = PdfReader(io.BytesIO(r.content))
    assert len(reader.pages) == 1
    # verify rotation applied (pypdf stores /Rotate entry)
    rot = reader.pages[0].get("/Rotate", 0)
    assert int(rot) % 360 == 90


def test_rotate_180(client):
    pdf = make_pdf(2)
    r = client.post("/api/rotate", files=[("file", ("a.pdf", pdf, "application/pdf"))], data={"angle": "180"})
    assert r.status_code == 200
    reader = PdfReader(io.BytesIO(r.content))
    assert len(reader.pages) == 2


def test_split_invalid_pages(client):
    pdf = make_pdf(3)
    r = client.post("/api/split", files=[("file", ("a.pdf", pdf, "application/pdf"))], data={"pages": "99"})
    assert r.status_code == 400


def test_split_invalid_format(client):
    pdf = make_pdf(3)
    r = client.post("/api/split", files=[("file", ("a.pdf", pdf, "application/pdf"))], data={"pages": "abc"})
    assert r.status_code == 400


def test_delete_out_of_range(client):
    pdf = make_pdf(3)
    r = client.post("/api/delete", files=[("file", ("a.pdf", pdf, "application/pdf"))], data={"pages": "99"})
    assert r.status_code == 400


def test_rotate_bad_angle(client):
    pdf = make_pdf(1)
    r = client.post("/api/rotate", files=[("file", ("a.pdf", pdf, "application/pdf"))], data={"angle": "45"})
    assert r.status_code == 400


def test_rotate_bad_angle_non_numeric(client):
    pdf = make_pdf(1)
    r = client.post("/api/rotate", files=[("file", ("a.pdf", pdf, "application/pdf"))], data={"angle": "foo"})
    assert r.status_code == 400
