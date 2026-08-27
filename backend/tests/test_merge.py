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


def test_merge_two_pdfs(client):
    p1, p2 = make_pdf(1), make_pdf(2)
    r = client.post(
        "/api/merge",
        files=[("files", ("a.pdf", p1, "application/pdf")), ("files", ("b.pdf", p2, "application/pdf"))],
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    # verify merged page count = 1+2 = 3
    reader = PdfReader(io.BytesIO(r.content))
    assert len(reader.pages) == 3


def test_merge_no_files(client):
    r = client.post("/api/merge", files=[])
    assert r.status_code == 400


def test_merge_too_many_files(client):
    files = [("files", (f"{i}.pdf", make_pdf(1), "application/pdf")) for i in range(11)]
    r = client.post("/api/merge", files=files)
    assert r.status_code == 413


def test_merge_file_too_large(client, monkeypatch):
    # monkeypatch MAX_FILE_SIZE to 10 bytes to force 413 without creating 50MB file
    import app.routers.merge as merge_mod
    monkeypatch.setattr(merge_mod, "MAX_FILE_SIZE", 10)
    # also need config patch for re-import? router uses imported MAX_FILE_SIZE variable, so patching module var works
    p1 = make_pdf(1)
    r = client.post("/api/merge", files=[("files", ("a.pdf", p1, "application/pdf"))])
    assert r.status_code == 413
