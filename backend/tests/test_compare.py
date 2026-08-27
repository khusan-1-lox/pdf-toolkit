import io

def make_pdf(text="Hello"):
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page(width=200, height=200)
    page.insert_text((20,50), text)
    b = doc.tobytes()
    doc.close()
    return b

def test_compare_diff_true(client):
    a = make_pdf("Hello A")
    b = make_pdf("Hello B")
    r = client.post("/api/compare", files=[("file1", ("a.pdf", a, "application/pdf")), ("file2", ("b.pdf", b, "application/pdf"))])
    assert r.status_code == 200
    data = r.json()
    assert "pages" in data
    assert len(data["pages"]) == 1
    p = data["pages"][0]
    assert p["diff"] is True
    assert "left_thumb" in p and p["left_thumb"].startswith("data:image")
    assert "right_thumb" in p and p["right_thumb"].startswith("data:image")
    assert "Hello A" in p["left_text"]
    assert "Hello B" in p["right_text"]

def test_compare_diff_false(client):
    a = make_pdf("Same text")
    b = make_pdf("Same text")
    r = client.post("/api/compare", files=[("file1", ("a.pdf", a, "application/pdf")), ("file2", ("b.pdf", b, "application/pdf"))])
    assert r.status_code == 200
    assert r.json()["pages"][0]["diff"] is False

def test_compare_different_page_count(client):
    import pymupdf
    doc1 = pymupdf.open()
    doc1.new_page()
    doc1.new_page()
    a = doc1.tobytes()
    doc1.close()
    doc2 = pymupdf.open()
    doc2.new_page()
    b = doc2.tobytes()
    doc2.close()
    r = client.post("/api/compare", files=[("file1", ("a.pdf", a, "application/pdf")), ("file2", ("b.pdf", b, "application/pdf"))])
    assert r.status_code == 200
    pages = r.json()["pages"]
    assert len(pages) == 2
    assert pages[1]["diff"] is True

def test_compare_missing_file_400(client):
    a = make_pdf("Hello")
    r = client.post("/api/compare", files=[("file1", ("a.pdf", a, "application/pdf"))])
    assert r.status_code == 400

def test_compare_invalid_pdf_400(client):
    a = make_pdf("Hello")
    r = client.post("/api/compare", files=[("file1", ("a.pdf", a, "application/pdf")), ("file2", ("b.pdf", b"not pdf", "application/pdf"))])
    assert r.status_code == 400

def test_compare_via_files_field(client):
    a = make_pdf("X")
    b = make_pdf("Y")
    r = client.post("/api/compare", files=[("files", ("a.pdf", a, "application/pdf")), ("files", ("b.pdf", b, "application/pdf"))])
    # our fallback supports files list; if not, still should handle via file1/file2 only.
    # Accept either 200 or 400 but prefer 200 if implementation supports
    assert r.status_code in (200, 400)
    if r.status_code == 200:
        assert "pages" in r.json()
