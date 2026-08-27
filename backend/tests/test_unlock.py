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

def encrypt_pdf(data: bytes, pwd: str):
    reader = PdfReader(io.BytesIO(data))
    writer = PdfWriter()
    for p in reader.pages:
        writer.add_page(p)
    writer.encrypt(pwd, use_128bit=True)
    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out.read()

def test_unlock_success(client):
    pdf = make_pdf(1)
    enc = encrypt_pdf(pdf.getvalue(), "secret123")
    r = client.post("/api/unlock", files=[("file", ("enc.pdf", io.BytesIO(enc), "application/pdf"))], data={"password": "secret123"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    reader = PdfReader(io.BytesIO(r.content))
    assert not reader.is_encrypted
    assert len(reader.pages) == 1

def test_unlock_wrong_password_400(client):
    pdf = make_pdf(1)
    enc = encrypt_pdf(pdf.getvalue(), "rightpwd")
    r = client.post("/api/unlock", files=[("file", ("enc.pdf", io.BytesIO(enc), "application/pdf"))], data={"password": "wrong"})
    assert r.status_code == 400

def test_unlock_missing_password_400(client):
    pdf = make_pdf(1)
    enc = encrypt_pdf(pdf.getvalue(), "secret")
    r = client.post("/api/unlock", files=[("file", ("enc.pdf", io.BytesIO(enc), "application/pdf"))], data={})
    assert r.status_code == 400

def test_unlock_not_encrypted_passthrough(client):
    pdf = make_pdf(1)
    r = client.post("/api/unlock", files=[("file", ("a.pdf", pdf, "application/pdf"))], data={"password": "any"})
    # should succeed and return pdf without encryption
    assert r.status_code == 200
    reader = PdfReader(io.BytesIO(r.content))
    assert not reader.is_encrypted

def test_unlock_invalid_pdf_400(client):
    r = client.post("/api/unlock", files=[("file", ("a.pdf", io.BytesIO(b"not pdf"), "application/pdf"))], data={"password": "secret"})
    assert r.status_code == 400
