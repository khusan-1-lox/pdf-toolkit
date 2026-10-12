import io
import json

import fitz
import pytest
from PIL import Image


def pdf(*labels):
    with fitz.open() as doc:
        for label in labels or ("Original",):
            page = doc.new_page(width=400, height=500)
            page.insert_text((30, 40), label)
        return doc.tobytes()


def upload(data=None):
    return {"file": ("source.pdf", data or pdf(), "application/pdf")}


def test_organize_reorders_across_files_and_rotates(client):
    response = client.post("/api/organize-pdf", files=[
        ("files", ("a.pdf", pdf("A1", "A2"), "application/pdf")),
        ("files", ("b.pdf", pdf("B1"), "application/pdf")),
    ], data={"order": json.dumps([{"file": 1, "page": 1, "rotation": 90}, {"file": 0, "page": 2}, {"file": 1, "page": 1}])})
    assert response.status_code == 200, response.text
    with fitz.open(stream=response.content, filetype="pdf") as doc:
        assert [p.get_text().strip() for p in doc] == ["B1", "A2", "B1"]
        assert [p.rotation for p in doc] == [90, 0, 0]


@pytest.mark.parametrize("order", [[], [{"file": 2, "page": 1}], [{"file": 0, "page": 0}], [{"file": 0, "page": 1, "rotation": 45}], [{"file": True, "page": 1}]])
def test_organize_rejects_invalid_order(client, order):
    response = client.post("/api/organize-pdf", files={"files": ("a.pdf", pdf(), "application/pdf")}, data={"order": json.dumps(order)})
    assert response.status_code == 400


def test_extract_pages_returns_combined_pdf(client):
    response = client.post("/api/extract-pages", files=upload(pdf("First", "Second", "Third")), data={"pages": "1,3"})
    assert response.status_code == 200
    with fitz.open(stream=response.content, filetype="pdf") as doc:
        assert [p.get_text().strip() for p in doc] == ["First", "Third"]


def test_edit_text_shapes_and_image_persist(client):
    image = io.BytesIO()
    Image.new("RGB", (12, 12), "red").save(image, format="PNG")
    ops = [
        {"type": "text", "page": 1, "x": .1, "y": .2, "unit": "normalized", "text": "Added text", "fontSize": 18},
        {"type": "rectangle", "page": 1, "x": 50, "y": 120, "width": 100, "height": 40, "fill": "#FF0000"},
        {"type": "freehand", "page": 1, "points": [[20, 200], [50, 240], [90, 210]], "color": "#008800"},
        {"type": "image", "page": 1, "x": 200, "y": 200, "width": 50, "height": 50},
    ]
    response = client.post("/api/edit-pdf", files={**upload(), "image": ("red.png", image.getvalue(), "image/png")}, data={"operations": json.dumps(ops)})
    assert response.status_code == 200, response.text
    with fitz.open(stream=response.content, filetype="pdf") as doc:
        assert "Original" in doc[0].get_text()
        assert "Added text" in doc[0].get_text()
        assert len(doc[0].get_drawings()) == 2
        assert len(doc[0].get_images()) == 1


def test_edit_cyrillic_text_is_searchable(client):
    response = client.post("/api/edit-pdf", files=upload(), data={"operations": json.dumps([{"type": "text", "page": 1, "x": 30, "y": 100, "text": "Привет мир"}])})
    assert response.status_code == 200, response.text
    with fitz.open(stream=response.content, filetype="pdf") as doc:
        assert "Привет мир" in doc[0].get_text()


@pytest.mark.parametrize("operation", [
    {"type": "unknown", "page": 1},
    {"type": "text", "page": 1, "x": float("nan"), "y": 40, "text": "bad"},
    {"type": "rectangle", "page": 1, "x": 390, "y": 490, "width": 20, "height": 20},
    {"type": "image", "page": 1, "x": 30, "y": 30, "width": 20, "height": 20},
    {"type": "text", "page": 99, "x": 30, "y": 30, "text": "bad"},
])
def test_edit_rejects_invalid_operations(client, operation):
    response = client.post("/api/edit-pdf", files=upload(), data={"operations": json.dumps([operation])})
    assert response.status_code == 400


def test_form_creation_inspection_and_fill_roundtrip(client):
    fields = [
        {"type": "text", "name": "name", "page": 1, "x": 30, "y": 90, "width": 200, "height": 30},
        {"type": "checkbox", "name": "agree", "page": 1, "x": 30, "y": 140, "width": 20, "height": 20},
        {"type": "choice", "name": "city", "page": 1, "x": 30, "y": 180, "width": 200, "height": 30, "choices": ["Tashkent", "Samarkand"]},
    ]
    created = client.post("/api/pdf-forms", files=upload(), data={"fields": json.dumps(fields)})
    assert created.status_code == 200, created.text
    inspection = client.post("/api/pdf-forms/inspect", files=upload(created.content))
    assert inspection.status_code == 200
    assert [f["name"] for f in inspection.json()["fields"]] == ["name", "agree", "city"]
    filled = client.post("/api/pdf-forms", files=upload(created.content), data={"values": json.dumps({"name": "Alex", "agree": True, "city": "Tashkent"})})
    assert filled.status_code == 200, filled.text
    with fitz.open(stream=filled.content, filetype="pdf") as doc:
        values = {w.field_name: w.field_value for w in doc[0].widgets()}
        assert values == {"name": "Alex", "agree": "Yes", "city": "Tashkent"}
    unchecked = client.post("/api/pdf-forms", files=upload(filled.content), data={"values": '{"agree": false}'})
    assert unchecked.status_code == 200
    final = client.post("/api/pdf-forms/inspect", files=upload(unchecked.content)).json()
    assert next(field for field in final["fields"] if field["name"] == "agree")["checked"] is False


def test_form_unknown_names_and_invalid_choice_are_errors(client):
    assert client.post("/api/pdf-forms", files=upload(), data={"values": '{"missing":"x"}'}).status_code == 400
    field = {"type": "choice", "name": "city", "page": 1, "x": 30, "y": 90, "width": 200, "height": 30, "choices": ["Tashkent"], "value": "wrong"}
    assert client.post("/api/pdf-forms", files=upload(), data={"fields": json.dumps([field])}).status_code == 400


def test_form_normalized_rectangles_and_initial_values(client):
    fields = [
        {"type": "text", "name": "name", "page": 1, "x": .1, "y": .2, "width": .5, "height": .08, "unit": "normalized", "value": "Initial"},
        {"type": "checkbox", "name": "agree", "page": 1, "x": .1, "y": .4, "width": .05, "height": .04, "unit": "normalized", "value": True},
    ]
    response = client.post("/api/pdf-forms", files=upload(), data={"fields": json.dumps(fields)})
    assert response.status_code == 200, response.text
    with fitz.open(stream=response.content, filetype="pdf") as doc:
        widgets = list(doc[0].widgets())
        assert list(widgets[0].rect) == [40, 100, 240, 140]
        assert widgets[0].field_value == "Initial"
        assert widgets[1].field_value == "Yes"


def test_form_readonly_value_is_rejected(client):
    with fitz.open(stream=pdf(), filetype="pdf") as doc:
        page = doc[0]
        widget = fitz.Widget()
        widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        widget.field_name = "fixed"
        widget.field_flags = 1
        widget.field_value = "Original"
        widget.rect = fitz.Rect(30, 80, 200, 110)
        page.add_widget(widget)
        data = doc.tobytes()
    response = client.post("/api/pdf-forms", files=upload(data), data={"values": '{"fixed":"overwrite"}'})
    assert response.status_code == 400
    assert "read-only" in response.json()["detail"]


def test_markdown_extracts_heading_and_body(client):
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((40, 60), "Report heading", fontsize=24)
        for n in range(4):
            page.insert_text((40, 100 + n * 20), f"Paragraph {n} contains useful content.", fontsize=11)
        data = doc.tobytes()
    response = client.post("/api/pdf-to-markdown", files=upload(data))
    assert response.status_code == 200, response.text
    assert "# Report heading" in response.text
    assert "Paragraph 3 contains useful content." in response.text
    assert 'filename="document.md"' in response.headers["content-disposition"]


def test_markdown_extracts_table(client):
    with fitz.open() as doc:
        page = doc.new_page()
        for y in [100, 140, 180]:
            page.draw_line((40, y), (340, y))
        for x in [40, 190, 340]:
            page.draw_line((x, 100), (x, 180))
        for point, text in [((50, 125), "Name"), ((200, 125), "Count"), ((50, 165), "Apples"), ((200, 165), "3")]:
            page.insert_text(point, text)
        data = doc.tobytes()
    response = client.post("/api/pdf-to-markdown", files=upload(data))
    assert response.status_code == 200, response.text
    assert "| Name | Count |" in response.text
    assert "| Apples | 3 |" in response.text


def test_markdown_empty_pdf_requires_ocr(client):
    with fitz.open() as doc:
        doc.new_page()
        data = doc.tobytes()
    response = client.post("/api/pdf-to-markdown", files=upload(data))
    assert response.status_code == 400
    assert "OCR" in response.json()["detail"]
