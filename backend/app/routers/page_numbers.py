from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import uuid
import os
import shutil
import time
import re

from ..config import TMP_ROOT, MAX_FILE_SIZE, RETENTION_SECONDS

router = APIRouter()

ALLOWED_POSITIONS = {
    "bottom-center",
    "bottom-right",
    "bottom-left",
    "top-center",
    "top-left",
    "top-right",
    "center",
}
DEFAULT_POSITION = "bottom-center"
ALLOWED_FORMATS = {"1", "1 / N", "Page 1", "Page 1 of N"}
DEFAULT_FORMAT = "1"
DEFAULT_FONTSIZE = 12
DEFAULT_COLOR = "#000000"
DEFAULT_MARGIN = 20
DEFAULT_START = 1


def schedule_delete(path: str):
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
        import fitz  # type: ignore
        return fitz
    except ImportError:
        pass
    try:
        import pymupdf as fitz  # type: ignore
        return fitz
    except ImportError:
        return None


def get_text_length(text: str, fontsize: int, fontname: str = "helv"):
    fitz = get_fitz()
    if fitz is not None:
        try:
            return fitz.get_text_length(text, fontsize=fontsize, fontname=fontname)
        except Exception:
            pass
    return len(text) * fontsize * 0.5


@router.post("/api/page-numbers")
async def page_numbers(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    position: str = Form(default="bottom-center"),
    format: str = Form(default="1"),  # noqa: A002 - shadow builtin but required by spec
    fontSize: str = Form(default="12"),
    color: str = Form(default="#000000"),
    margin: str = Form(default="20"),
    startNumber: str = Form(default="1"),
):
    # validate position
    pos = (position or DEFAULT_POSITION).strip().lower()
    # normalize: allow aliases with underscores
    pos = pos.replace("_", "-")
    if pos not in ALLOWED_POSITIONS:
        raise HTTPException(status_code=400, detail=f"Invalid position, must be one of {', '.join(sorted(ALLOWED_POSITIONS))}")

    # validate format
    fmt = (format or DEFAULT_FORMAT).strip()
    if fmt not in ALLOWED_FORMATS:
        raise HTTPException(status_code=400, detail=f"Invalid format, must be one of {', '.join(sorted(ALLOWED_FORMATS))}")

    # validate fontSize
    try:
        fontsize_i = int(str(fontSize).strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid fontSize")
    if not (6 <= fontsize_i <= 72):
        raise HTTPException(status_code=400, detail="Invalid fontSize, must be 6-72")

    # validate color
    color_str = (color or DEFAULT_COLOR).strip()
    if not color_str:
        color_str = DEFAULT_COLOR
    color_rgb = parse_color(color_str)

    # validate margin
    try:
        margin_i = int(str(margin).strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid margin")
    if not (0 <= margin_i <= 100):
        raise HTTPException(status_code=400, detail="Invalid margin, must be 0-100")

    # validate startNumber
    try:
        start_i = int(str(startNumber).strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid startNumber")
    if not (1 <= start_i <= 100000):
        raise HTTPException(status_code=400, detail="Invalid startNumber, must be 1-100000")

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    fitz = get_fitz()
    if fitz is None:
        raise HTTPException(status_code=500, detail="PyMuPDF not available")

    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:
        msg = str(e).lower()
        if "password" in msg or "encrypt" in msg:
            raise HTTPException(status_code=400, detail="Encrypted PDF not supported")
        raise HTTPException(status_code=400, detail="Invalid PDF")

    if len(doc) == 0:
        doc.close()
        raise HTTPException(status_code=400, detail="PDF has no pages")

    n = len(doc)

    uid = str(uuid.uuid4())
    d = os.path.join(TMP_ROOT, uid)
    os.makedirs(d, exist_ok=True)
    out_path = os.path.join(d, "result.pdf")

    try:
        for idx, page in enumerate(doc):
            rect = page.rect
            w = rect.width
            h = rect.height
            num = start_i + idx

            if fmt == "1":
                text = str(num)
            elif fmt == "1 / N":
                text = f"{num} / {n}"
            elif fmt == "Page 1":
                text = f"Page {num}"
            elif fmt == "Page 1 of N":
                text = f"Page {num} of {n}"
            else:
                text = str(num)

            txt_len = get_text_length(text, fontsize_i, "helv")
            txt_h = fontsize_i * 1.2

            # compute x,y baseline for insert_text
            if pos == "center":
                x = w / 2 - txt_len / 2
                y = h / 2 + txt_h / 4
            elif pos == "top-left":
                x = margin_i
                y = margin_i + fontsize_i
            elif pos == "top-right":
                x = w - txt_len - margin_i
                y = margin_i + fontsize_i
            elif pos == "top-center":
                x = w / 2 - txt_len / 2
                y = margin_i + fontsize_i
            elif pos == "bottom-left":
                x = margin_i
                y = h - margin_i
            elif pos == "bottom-right":
                x = w - txt_len - margin_i
                y = h - margin_i
            elif pos == "bottom-center":
                x = w / 2 - txt_len / 2
                y = h - margin_i
            else:
                x = w / 2 - txt_len / 2
                y = h - margin_i

            # clamp x to stay inside page
            if x < margin_i:
                x = margin_i
            if x + txt_len > w - margin_i:
                x = max(margin_i, w - txt_len - margin_i)

            shape = page.new_shape()
            try:
                shape.insert_text(
                    fitz.Point(x, y),
                    text,
                    fontsize=fontsize_i,
                    fontname="helv",
                    color=color_rgb,
                )
                shape.finish(color=color_rgb, fill=color_rgb)
                shape.commit(overlay=True)
            except Exception:
                # fallback direct insert
                try:
                    page.insert_text(
                        fitz.Point(x, y),
                        text,
                        fontsize=fontsize_i,
                        fontname="helv",
                        color=color_rgb,
                    )
                except Exception:
                    pass
                try:
                    shape.commit(overlay=True)
                except Exception:
                    pass

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
        raise HTTPException(status_code=400, detail=f"Page numbers failed: {e}")

    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Page numbers produced empty file")

    background_tasks.add_task(schedule_delete, out_path)
    return FileResponse(out_path, filename="paginated.pdf", media_type="application/pdf")
