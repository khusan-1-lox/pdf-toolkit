from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import uuid
import os
import shutil
import time
import io
import re

from ..config import TMP_ROOT, MAX_FILE_SIZE, RETENTION_SECONDS

router = APIRouter()

ALLOWED_POSITIONS = {"center", "top-left", "top-right", "bottom-left", "bottom-right"}
DEFAULT_POSITION = "center"
DEFAULT_OPACITY = 0.3
DEFAULT_FONTSIZE = 36
DEFAULT_COLOR = "#C8C8C8"
DEFAULT_ROTATION = 45


def schedule_delete(path: str):
    """Delete temp dir after RETENTION_SECONDS (300s = 5 min). Non-blocking."""
    import threading

    def _del():
        time.sleep(RETENTION_SECONDS)
        dir_path = os.path.dirname(path)
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path, ignore_errors=True)

    threading.Thread(target=_del, daemon=True).start()


def parse_color(hex_str: str):
    s = hex_str.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6 or not re.fullmatch(r"[0-9a-fA-F]{6}", s):
        raise HTTPException(status_code=400, detail="Invalid color hex, use #RRGGBB")
    r = int(s[0:2], 16) / 255.0
    g = int(s[2:4], 16) / 255.0
    b = int(s[4:6], 16) / 255.0
    return (r, g, b)


def get_fitz():
    try:
        import fitz  # PyMuPDF provides fitz alias (deprecated but still works)
        return fitz
    except ImportError:
        pass
    try:
        import pymupdf as fitz
        return fitz
    except ImportError:
        return None


def get_text_length(text: str, fontsize: int, fontname: str = "helv"):
    fitz = get_fitz()
    if fitz is not None:
        try:
            # fitz.get_text_length is available at module level
            return fitz.get_text_length(text, fontsize=fontsize, fontname=fontname)
        except Exception:
            pass
    # fallback approximation: ~0.5*fontsize per char
    return len(text) * fontsize * 0.5


@router.post("/api/watermark")
async def watermark(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    text: str | None = Form(default=None),
    image: UploadFile | None = File(default=None),
    position: str = Form(default="center"),
    opacity: str = Form(default="0.3"),
    fontSize: str = Form(default="36"),
    color: str = Form(default="#C8C8C8"),
    rotation: str = Form(default="45"),
):
    # Normalize and validate text / image presence
    has_text = text is not None and text.strip() != ""
    has_image = image is not None and image.filename not in (None, "")

    # image may be provided but empty filename still counts as no image if no bytes?
    # We'll also check later after reading
    # If has_image but file size 0, treat as no image
    image_data: bytes | None = None
    if has_image:
        try:
            image_data = await image.read()
        except Exception:
            image_data = None
        if not image_data or len(image_data) == 0:
            has_image = False
            image_data = None
        elif len(image_data) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="Image too large")

    if not has_text and not has_image:
        raise HTTPException(status_code=400, detail="At least text or image required")

    # validate position
    pos = (position or "center").strip().lower()
    if pos not in ALLOWED_POSITIONS:
        raise HTTPException(status_code=400, detail=f"Invalid position, must be one of {', '.join(sorted(ALLOWED_POSITIONS))}")

    # validate opacity
    try:
        opacity_f = float(str(opacity).strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid opacity, must be 0.1-1.0")
    if not (0.1 <= opacity_f <= 1.0):
        raise HTTPException(status_code=400, detail="Invalid opacity, must be 0.1-1.0")

    # validate fontSize
    try:
        fontsize_i = int(str(fontSize).strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid fontSize")
    if not (8 <= fontsize_i <= 200):
        raise HTTPException(status_code=400, detail="Invalid fontSize, must be 8-200")

    # validate color
    color_str = (color or DEFAULT_COLOR).strip()
    if not color_str:
        color_str = DEFAULT_COLOR
    color_rgb = parse_color(color_str)

    # validate rotation
    try:
        rotation_i = int(str(rotation).strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rotation")
    # allow 0-360 or -360..360
    if not (-360 <= rotation_i <= 360):
        raise HTTPException(status_code=400, detail="Invalid rotation, must be -360..360")

    # read pdf file
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    fitz = get_fitz()
    if fitz is None:
        raise HTTPException(status_code=500, detail="PyMuPDF not available")

    # open doc to validate
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:
        msg = str(e).lower()
        if "password" in msg or "encrypt" in msg:
            raise HTTPException(status_code=400, detail="Encrypted PDF not supported")
        raise HTTPException(status_code=400, detail="Invalid PDF")

    if doc.needs_pass:
        doc.close()
        raise HTTPException(400, "Encrypted PDF not supported")

    if len(doc) == 0:
        doc.close()
        raise HTTPException(status_code=400, detail="PDF has no pages")

    # Prepare image pixmap if needed (with opacity applied via Pillow)
    image_png_bytes: bytes | None = None
    image_w: int = 0
    image_h: int = 0
    if has_image and image_data is not None:
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(image_data))
            # ensure RGBA
            img = img.convert("RGBA")
            image_w, image_h = img.size
            if opacity_f < 1.0:
                r, g, b, a = img.split()
                # multiply alpha channel by opacity
                a = a.point(lambda p: int(p * opacity_f))
                img = Image.merge("RGBA", (r, g, b, a))
            if rotation_i % 360:
                img = img.rotate(rotation_i, expand=True, resample=Image.Resampling.BICUBIC)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            image_png_bytes = buf.getvalue()
            image_w, image_h = img.size
        except HTTPException:
            raise
        except Exception as e:
            doc.close()
            raise HTTPException(status_code=400, detail=f"Invalid image: {e}")

    uid = str(uuid.uuid4())
    d = os.path.join(TMP_ROOT, uid)
    os.makedirs(d, exist_ok=True)
    out_path = os.path.join(d, "result.pdf")

    try:
        for page in doc:
            rect = page.rect
            w = rect.width
            h = rect.height
            margin = 20

            if has_text:
                t = text.strip()
                # MuPDF's bundled Unicode font works offline, including Cyrillic.
                font = fitz.Font("cjk")
                if any(not font.has_glyph(ord(char)) for char in t if not char.isspace()):
                    raise HTTPException(400, "Watermark contains characters unsupported by the embedded font")
                page.insert_font(fontname="watermark_unicode", fontbuffer=font.buffer)
                matrix = fitz.Matrix(rotation_i)
                # Text morphs use PDF's y-up coordinates; page rectangles use y-down.
                bounds_matrix = fitz.Matrix(-rotation_i)
                size = float(fontsize_i)
                bounds = fitz.Rect(0, -font.ascender * size,
                                   font.text_length(t, fontsize=size), -font.descender * size) * bounds_matrix
                # Keep the whole rotated mark inside the selected page region.
                factor = min(1.0, max(1, w - 2 * margin) / max(1, bounds.width),
                             max(1, h - 2 * margin) / max(1, bounds.height))
                size *= factor
                bounds = fitz.Rect(0, -font.ascender * size,
                                   font.text_length(t, fontsize=size), -font.descender * size) * bounds_matrix
                left = (w - bounds.width) / 2 if pos == "center" else (
                    margin if "left" in pos else w - margin - bounds.width)
                top = (h - bounds.height) / 2 if pos == "center" else (
                    margin if "top" in pos else h - margin - bounds.height)
                origin = fitz.Point(left - bounds.x0, top - bounds.y0)
                page.insert_text(
                    origin, t, fontsize=size, fontname="watermark_unicode",
                    color=color_rgb, morph=(origin, matrix),
                    stroke_opacity=opacity_f, fill_opacity=opacity_f, overlay=True,
                )

            # Image watermark via page.new_shape drawImage (spec) - we use page.insert_image with overlay and alpha pre-baked
            if has_image and image_png_bytes is not None:
                # scale image to max 30% of page
                iw = image_w
                ih = image_h
                max_w = w * 0.3
                max_h = h * 0.3
                scale = 1.0
                if iw > max_w or ih > max_h:
                    scale = min(max_w / iw, max_h / ih)
                nw = iw * scale
                nh = ih * scale

                if pos == "center":
                    x0 = (w - nw) / 2
                    y0 = (h - nh) / 2
                elif pos == "top-left":
                    x0 = margin
                    y0 = margin
                elif pos == "top-right":
                    x0 = w - nw - margin
                    y0 = margin
                elif pos == "bottom-left":
                    x0 = margin
                    y0 = h - nh - margin
                elif pos == "bottom-right":
                    x0 = w - nw - margin
                    y0 = h - nh - margin
                else:
                    x0 = (w - nw) / 2
                    y0 = (h - nh) / 2

                rect_img = fitz.Rect(x0, y0, x0 + nw, y0 + nh)

                # actual image insertion with pre-baked opacity
                try:
                    page.insert_image(rect_img, stream=image_png_bytes, overlay=True, keep_proportion=True)
                except Exception as e:
                    # fallback try pixmap
                    try:
                        pix = fitz.Pixmap(image_png_bytes)
                        page.insert_image(rect_img, pixmap=pix, overlay=True, keep_proportion=True)
                    except Exception:
                        raise HTTPException(status_code=400, detail=f"Failed to insert image watermark: {e}")

        doc.subset_fonts()
        doc.save(out_path, garbage=4, deflate=True, clean=True)
        doc.close()
    except HTTPException:
        shutil.rmtree(d, ignore_errors=True)
        try:
            doc.close()
        except Exception:
            pass
        raise
    except Exception as e:
        shutil.rmtree(d, ignore_errors=True)
        try:
            doc.close()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=f"Watermark failed: {e}")

    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Watermark produced empty file")

    background_tasks.add_task(schedule_delete, out_path)
    return FileResponse(out_path, filename="watermarked.pdf", media_type="application/pdf")
