"""PDF composition, editing, AcroForms and local Markdown extraction.

All page numbers are one-based; organize file indexes are zero-based.
Editing/form rectangles use unrotated PDF page coordinates in points. Pass
unit="normalized" for coordinates and dimensions in [0, 1]. Text x/y is its
baseline; rectangle/image x/y is its top-left. Colors are #RRGGBB.
"""

import json
import io
import math
import re
from contextlib import ExitStack, contextmanager
from statistics import median

import fitz
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError

from ..config import MAX_FILE_SIZE, MAX_FILES
from .split import parse_pages

router = APIRouter()
MAX_PAGES = 100_000
MAX_ITEMS = 100_000
MAX_JSON = 100 * 1024 * 1024


def _bad(message):
    raise HTTPException(400, message)


async def _read(upload, limit=MAX_FILE_SIZE):
    data = await upload.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, "File too large")
    if not data:
        _bad("Empty file")
    return data


async def _open(upload):
    data = await _read(upload)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception:
        _bad("Invalid PDF")
    if not doc.is_pdf or doc.needs_pass or not 0 < len(doc) <= MAX_PAGES:
        doc.close()
        _bad(f"PDF must be unlocked and contain 1–{MAX_PAGES} pages")
    return doc


@contextmanager
def _guard():
    try:
        yield
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, "Cannot process these PDF operations") from exc


def _json(value, expected, name):
    if len(value) > MAX_JSON:
        raise HTTPException(413, f"{name} is too large")
    try:
        parsed = json.loads(value)
    except (ValueError, RecursionError):
        _bad(f"Invalid {name} JSON")
    if not isinstance(parsed, expected) or len(parsed) > MAX_ITEMS:
        _bad(f"{name} must be a {expected.__name__} with at most {MAX_ITEMS} items")
    return parsed


def _number(value, name, minimum=0, maximum=100000):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        _bad(f"{name} must be a number")
    if not math.isfinite(value) or not minimum <= value <= maximum:
        _bad(f"{name} must be between {minimum} and {maximum}")
    return value


def _integer(value, name, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        _bad(f"{name} must be an integer between {minimum} and {maximum}")
    return value


def _item(value):
    if not isinstance(value, dict):
        _bad("Each operation must be an object")
    return value


def _color(value):
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        _bad("Colors must use #RRGGBB")
    return tuple(int(value[i:i + 2], 16) / 255 for i in (1, 3, 5))


def _page(doc, op):
    return doc[_integer(op.get("page"), "page", 1, len(doc)) - 1]


def _dimensions(page):
    # Page.rect includes /Rotate; insertion APIs expect the unrotated page.
    return page.cropbox.width, page.cropbox.height


def _point(page, op, x, y):
    width, height = _dimensions(page)
    unit = op.get("unit", "pt")
    if unit not in ("pt", "normalized"):
        _bad("unit must be pt or normalized")
    px = _number(x, "x", 0, 1 if unit == "normalized" else width)
    py = _number(y, "y", 0, 1 if unit == "normalized" else height)
    return fitz.Point(px * width, py * height) if unit == "normalized" else fitz.Point(px, py)


def _rect(page, op):
    point = _point(page, op, op.get("x"), op.get("y"))
    size = _point(page, op, op.get("width"), op.get("height"))
    width, height = _dimensions(page)
    if size.x <= 0 or size.y <= 0 or point.x + size.x > width + .01 or point.y + size.y > height + .01:
        _bad("Rectangle must have positive size and fit inside the page")
    return fitz.Rect(point.x, point.y, point.x + size.x, point.y + size.y)


def _download(doc, name):
    data = doc.tobytes(garbage=3, deflate=True)
    if len(data) > MAX_FILE_SIZE * 4:
        raise HTTPException(413, "Result is too large")
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'})


@router.post("/api/organize-pdf")
async def organize_pdf(files: list[UploadFile] = File(...), order: str = Form(...)):
    """Select, duplicate, omit and reorder source pages; rotation is relative."""
    if not 1 <= len(files) <= MAX_FILES:
        _bad(f"Upload between 1 and {MAX_FILES} PDFs")
    sequence = _json(order, list, "order")
    if not sequence:
        _bad("Select at least one page")
    with _guard(), ExitStack() as stack:
        docs = []
        total_size = 0
        for upload in files:
            doc = stack.enter_context(await _open(upload))
            docs.append(doc)
            total_size += upload.size or 0
            if total_size > MAX_FILE_SIZE * 2:
                raise HTTPException(413, "Combined files are too large")
        output = stack.enter_context(fitz.open())
        for selection in sequence:
            op = _item(selection)
            source = docs[_integer(op.get("file"), "file", 0, len(docs) - 1)]
            page = _integer(op.get("page"), "page", 1, len(source)) - 1
            rotation = _integer(op.get("rotation", 0), "rotation", -360, 360)
            if rotation % 90:
                _bad("rotation must be a multiple of 90")
            output.insert_pdf(source, from_page=page, to_page=page)
            output[-1].set_rotation((source[page].rotation + rotation) % 360)
        return _download(output, "organized")


@router.post("/api/extract-pages")
async def extract_pages(file: UploadFile = File(...), pages: str = Form(...)):
    with _guard(), await _open(file) as source, fitz.open() as output:
        for number in parse_pages(pages, len(source)):
            output.insert_pdf(source, from_page=number - 1, to_page=number - 1)
        return _download(output, "extracted")


@router.post("/api/edit-pdf")
async def edit_pdf(file: UploadFile = File(...), operations: str = Form(...), image: UploadFile | None = File(None)):
    ops = _json(operations, list, "operations")
    if not ops:
        _bad("Add at least one edit")
    image_data = await _read(image, 10 * 1024 * 1024) if image else None
    if image_data:
        try:
            with Image.open(io.BytesIO(image_data)) as source:
                if source.width * source.height > 40_000_000:
                    _bad("Image must contain at most 40 million pixels")
                source.verify()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            _bad("Invalid or oversized image")
    with _guard(), await _open(file) as doc:
        for value in ops:
            op = _item(value)
            page = _page(doc, op)
            kind = op.get("type")
            color = _color(op.get("color", "#20263A"))
            if kind == "text":
                text = op.get("text")
                if not isinstance(text, str) or not text.strip() or len(text) > 10000:
                    _bad("Text must contain 1–10000 characters")
                point = _point(page, op, op.get("x"), op.get("y"))
                font_size = _number(op.get("fontSize", 18), "fontSize", 4, 200)
                font_name = "helv"
                font = fitz.Font("helv")
                if any(ord(c) > 255 for c in text):
                    font = fitz.Font("cjk")
                    page.insert_font(fontname="unicode", fontbuffer=font.buffer)
                    font_name = "unicode"
                width, height = _dimensions(page)
                lines = text.splitlines()
                if (point.y - font.ascender * font_size < 0
                        or point.y + (len(lines) - 1) * font_size * 1.2 - font.descender * font_size > height
                        or any(point.x + font.text_length(line, fontsize=font_size) > width for line in lines)):
                    _bad("Text does not fit inside the page; move it or reduce its font size")
                page.insert_text(point, text, fontsize=font_size, fontname=font_name, color=color)
            elif kind == "rectangle":
                fill = _color(op["fill"]) if op.get("fill") is not None else None
                page.draw_rect(_rect(page, op), color=color, fill=fill, width=_number(op.get("lineWidth", 2), "lineWidth", .1, 50))
            elif kind == "freehand":
                points = op.get("points")
                if not isinstance(points, list) or not 2 <= len(points) <= 10000:
                    _bad("A freehand path needs 2–10000 points")
                path = []
                for point in points:
                    if not isinstance(point, list) or len(point) != 2:
                        _bad("Each point must be [x,y]")
                    path.append(_point(page, op, *point))
                page.draw_polyline(path, color=color, width=_number(op.get("lineWidth", 2), "lineWidth", .1, 50))
            elif kind == "image":
                if not image_data:
                    _bad("Upload an image for image operations")
                page.insert_image(_rect(page, op), stream=image_data, keep_proportion=True)
            else:
                _bad("Unknown edit type; use text, rectangle, freehand or image")
        return _download(doc, "edited")


def _field_info(page_number, widget):
    info = {"page": page_number, "name": widget.field_name, "type": widget.field_type_string,
            "value": widget.field_value, "rect": list(widget.rect), "readonly": bool(widget.field_flags & 1)}
    if widget.field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX:
        info["checked"] = widget.field_value not in (None, "", "Off", False)
    if widget.choice_values:
        info["choices"] = widget.choice_values
    return info


@router.post("/api/pdf-forms/inspect")
async def inspect_forms(file: UploadFile = File(...)):
    with _guard(), await _open(file) as doc:
        return {"pageCount": len(doc), "fields": [_field_info(i + 1, widget) for i, page in enumerate(doc) for widget in page.widgets() or []]}


def _set_value(widget, value):
    if widget.field_flags & 1:
        _bad(f"Field {widget.field_name} is read-only")
    if widget.field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX:
        if type(value) is not bool:
            _bad(f"Checkbox {widget.field_name} requires true or false")
        on_state = widget.on_state() or "Yes"
        widget.field_value = on_state if value else "Off"
    elif widget.field_type in (fitz.PDF_WIDGET_TYPE_TEXT, fitz.PDF_WIDGET_TYPE_COMBOBOX, fitz.PDF_WIDGET_TYPE_LISTBOX):
        if not isinstance(value, str) or len(value) > 10000:
            _bad(f"Field {widget.field_name} requires a string of at most 10000 characters")
        if widget.field_type != fitz.PDF_WIDGET_TYPE_TEXT:
            choices = widget.choice_values or []
            allowed = [c[0] if isinstance(c, (tuple, list)) else c for c in choices]
            if value not in allowed:
                _bad(f"Invalid choice for {widget.field_name}")
        if widget.text_maxlen and len(value) > widget.text_maxlen:
            _bad(f"Value exceeds maximum length for {widget.field_name}")
        widget.field_value = value
    else:
        _bad(f"Unsupported field type for {widget.field_name}")
    widget.update()


@router.post("/api/pdf-forms")
async def pdf_forms(file: UploadFile = File(...), values: str = Form("{}"), fields: str = Form("[]")):
    """Fill name->value map and/or create fields (text, checkbox, choice).

    New fields require name, type, page, x, y, width, height; choice also
    requires choices: [str, ...]. Optional value sets the initial value.
    """
    assignments = _json(values, dict, "values")
    additions = _json(fields, list, "fields")
    if not assignments and not additions:
        _bad("Provide field values or new fields")
    with _guard(), await _open(file) as doc:
        names = {widget.field_name for page in doc for widget in page.widgets() or []}
        for value in additions:
            op = _item(value)
            name = op.get("name")
            if not isinstance(name, str) or not name.strip() or len(name) > 200 or name in names:
                _bad("New fields require a unique name of 1–200 characters")
            types = {"text": fitz.PDF_WIDGET_TYPE_TEXT, "checkbox": fitz.PDF_WIDGET_TYPE_CHECKBOX, "choice": fitz.PDF_WIDGET_TYPE_COMBOBOX}
            if op.get("type") not in types:
                _bad("New field type must be text, checkbox or choice")
            page = _page(doc, op)
            widget = fitz.Widget()
            widget.field_name = name
            widget.field_type = types[op["type"]]
            widget.rect = _rect(page, op)
            widget.border_width = 1
            widget.border_color = (.45, .5, .6)
            widget.fill_color = (.97, .98, 1)
            widget.text_fontsize = _number(op.get("fontSize", 12), "fontSize", 4, 100)
            if op["type"] == "choice":
                choices = op.get("choices")
                if not isinstance(choices, list) or not 1 <= len(choices) <= 100 or any(not isinstance(c, str) or not c or len(c) > 200 for c in choices):
                    _bad("Choice fields require 1–100 nonempty choices")
                widget.choice_values = choices
            annotation = page.add_widget(widget)
            created = page.load_widget(annotation.xref)
            if "value" in op:
                _set_value(created, op["value"])
            names.add(name)
        missing = set(assignments) - names
        if missing:
            _bad("Unknown form fields: " + ", ".join(sorted(missing)))
        for page in doc:
            for widget in page.widgets() or []:
                if widget.field_name in assignments:
                    _set_value(widget, assignments[widget.field_name])
        return _download(doc, "form")


def _md_escape(text):
    return re.sub(r"([\\`*_\[\]<>])", r"\\\1", text)


@router.post("/api/pdf-to-markdown")
async def pdf_to_markdown(file: UploadFile = File(...)):
    """Extract local text, heading hierarchy and tables; scanned PDFs need OCR."""
    with _guard(), await _open(file) as doc:
        parts = []
        extracted = False
        for index, page in enumerate(doc):
            blocks = page.get_text("dict", sort=True, flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES)["blocks"]
            sizes = [s["size"] for b in blocks if b.get("type") == 0 for line in b["lines"] for s in line["spans"] if s["text"].strip()]
            body_size = median(sizes) if sizes else 12
            table_areas = []
            table_blocks = []
            if hasattr(page, "find_tables"):
                for table in page.find_tables().tables:
                    rows = table.extract()
                    if len(rows) < 2 or not rows[0]:
                        continue
                    width = max(map(len, rows))
                    formatted = []
                    for row in rows:
                        cells = [_md_escape(str(cell or "")).replace("|", r"\|").replace("\n", "<br>") for cell in row]
                        formatted.append("| " + " | ".join(cells + [""] * (width - len(cells))) + " |")
                    formatted.insert(1, "| " + " | ".join(["---"] * width) + " |")
                    table_blocks.append((table.bbox[1], "\n".join(formatted)))
                    table_areas.append(fitz.Rect(table.bbox))
            content = list(table_blocks)
            for block in blocks:
                if block.get("type") != 0:
                    continue
                lines = []
                block_sizes = []
                for line in block["lines"]:
                    center = (fitz.Rect(line["bbox"]).tl + fitz.Rect(line["bbox"]).br) / 2
                    if any(area.contains(center) for area in table_areas):
                        continue
                    text = "".join(span["text"] for span in line["spans"]).strip()
                    if text:
                        lines.append(_md_escape(text))
                        block_sizes.extend(span["size"] for span in line["spans"])
                if lines:
                    size = max(block_sizes)
                    prefix = "# " if size >= body_size * 1.6 else "## " if size >= body_size * 1.25 else ""
                    content.append((block["bbox"][1], prefix + " ".join(lines)))
            if content:
                extracted = True
                parts.append(f"<!-- Page {index + 1} -->\n\n" + "\n\n".join(text for _, text in sorted(content, key=lambda entry: entry[0])))
        if not extracted:
            _bad("No text found. Run OCR on scanned pages before converting to Markdown.")
        return Response("\n\n---\n\n".join(parts) + "\n", media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="document.md"'})
