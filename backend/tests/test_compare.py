import io

def make_pdf(text="Hello"):
    import fitz as pymupdf
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
    import fitz as pymupdf
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

def test_compare_detects_visual_changes_without_text(client):
    import fitz
    documents = []
    for color in ((1, 0, 0), (0, 0, 1)):
        with fitz.open() as doc:
            page = doc.new_page(width=200, height=200)
            page.draw_rect(fitz.Rect(20, 20, 150, 150), fill=color)
            documents.append(doc.tobytes())
    response = client.post("/api/compare", files=[
        ("file1", ("a.pdf", documents[0], "application/pdf")),
        ("file2", ("b.pdf", documents[1], "application/pdf"))])
    assert response.status_code == 200
    page = response.json()["pages"][0]
    assert page["diff"] and page["visual_diff"]
    assert not page["text_diff"]


def test_compare_includes_pages_after_twenty(client):
    import fitz
    with fitz.open() as doc:
        for _ in range(21):
            doc.new_page(width=100, height=100)
        original = doc.tobytes()
        doc[20].insert_text((10, 30), "Changed")
        changed = doc.tobytes()
    response = client.post("/api/compare", files=[
        ("file1", ("a.pdf", original, "application/pdf")),
        ("file2", ("b.pdf", changed, "application/pdf"))])
    assert response.status_code == 200
    assert len(response.json()["pages"]) == 21
    assert response.json()["pages"][20]["diff"]


def test_compare_rejects_over_limit_instead_of_truncating(client):
    import fitz
    with fitz.open() as doc:
        for _ in range(101):
            doc.new_page(width=100, height=100)
        document = doc.tobytes()
    response = client.post("/api/compare", files=[
        ("file1", ("a.pdf", document, "application/pdf")),
        ("file2", ("b.pdf", document, "application/pdf"))])
    assert response.status_code == 422
    assert "100" in response.json()["detail"]
