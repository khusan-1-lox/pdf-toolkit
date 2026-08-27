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

def test_protect_basic(client):
    pdf = make_pdf(1)
    r = client.post("/api/protect", files=[("file", ("a.pdf", pdf, "application/pdf"))], data={"user_password": "secret123"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    reader = PdfReader(io.BytesIO(r.content))
    assert reader.is_encrypted
    # decrypt should work
    assert reader.decrypt("secret123") != 0
    assert len(reader.pages) == 1

def test_protect_with_owner_and_permissions(client):
    pdf = make_pdf(2)
    r = client.post("/api/protect", files=[("file", ("a.pdf", pdf, "application/pdf"))], data={"user_password": "user123", "owner_password": "owner123", "allow_print": "false", "allow_copy": "true"})
    assert r.status_code == 200
    reader = PdfReader(io.BytesIO(r.content))
    assert reader.is_encrypted
    # owner password should also work
    reader2 = PdfReader(io.BytesIO(r.content))
    assert reader2.decrypt("owner123") != 0

def test_protect_missing_password_400(client):
    pdf = make_pdf(1)
    r = client.post("/api/protect", files=[("file", ("a.pdf", pdf, "application/pdf"))], data={})
    assert r.status_code == 400

def test_protect_empty_password_400(client):
    pdf = make_pdf(1)
    r = client.post("/api/protect", files=[("file", ("a.pdf", pdf, "application/pdf"))], data={"user_password": ""})
    assert r.status_code == 400

def test_protect_invalid_pdf_400(client):
    r = client.post("/api/protect", files=[("file", ("a.pdf", io.BytesIO(b"not a pdf"), "application/pdf"))], data={"user_password": "secret"})
    assert r.status_code == 400

def test_protect_empty_file_400(client):
    r = client.post("/api/protect", files=[("file", ("a.pdf", io.BytesIO(b""), "application/pdf"))], data={"user_password": "secret"})
    assert r.status_code == 400
