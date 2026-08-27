from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import uuid
import os
import shutil
import time
import re

from ..config import TMP_ROOT, MAX_FILE_SIZE, RETENTION_SECONDS

router = APIRouter()

ALLOWED_MODES = {"margins", "rect"}
MM_TO_PT = 2.83464567


def schedule_delete(path: str):
    import threading

    def _del():
        time.sleep(RETENTION_SECONDS)
        dir_path = os.path.dirname(path)
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path, ignore_errors=True)

    threading.Thread(target=_del, daemon=True).start()


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


def parse_pages(pages_str: str, total: int) -> set[int]:
    s = pages_str.strip().lower()
    if s == "" or s == "all":
        return set(range(1, total + 1))
    if not s:
        raise HTTPException(status_code=400, detail="pages parameter required")
    result: set[int] = set()
    parts = s.split(",")
    for token in parts:
        token = token.strip()
        if not token:
            raise HTTPException(status_code=400, detail="Invalid pages format")
        if "-" in token:
            range_parts = token.split("-")
            if len(range_parts) != 2:
                raise HTTPException(status_code=400, detail="Invalid pages format")
            a, b = range_parts[0].strip(), range_parts[1].strip()
            if not a or not b:
                raise HTTPException(status_code=400, detail="Invalid pages format")
            try:
                start = int(a)
                end = int(b)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid pages format")
            if start < 1 or end < 1 or start > total or end > total:
                bad = start if (start < 1 or start > total) else end
                raise HTTPException(status_code=400, detail=f"Page {bad} out of range (file has {total} pages)")
            if start > end:
                raise HTTPException(status_code=400, detail="Invalid page range")
            for p in range(start, end + 1):
                result.add(p)
        else:
            try:
                num = int(token)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid pages format")
            if num < 1 or num > total:
                raise HTTPException(status_code=400, detail=f"Page {num} out of range (file has {total} pages)")
            result.add(num)
    if not result:
        raise HTTPException(status_code=400, detail="No valid pages")
    return result


def parse_float_field(raw: str | None, name: str, allow_zero=True, min_val=None, max_val=None) -> float:
    if raw is None or raw == "":
        return 0.0
    s = str(raw).strip()
    if s == "":
        return 0.0
    # allow comma as decimal separator
    s = s.replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid {name}: must be a number")
    if not allow_zero and v == 0:
        raise HTTPException(status_code=400, detail=f"Invalid {name}: must be > 0")
    if min_val is not None and v < min_val:
        raise HTTPException(status_code=400, detail=f"Invalid {name}: must be >= {min_val}")
    if max_val is not None and v > max_val:
        raise HTTPException(status_code=400, detail=f"Invalid {name}: must be <= {max_val}")
    return v


@router.post("/api/crop")
async def crop_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    mode: str = Form(default="margins"),
    pages: str = Form(default="all"),
    top: str = Form(default="0"),
    bottom: str = Form(default="0"),
    left: str = Form(default="0"),
    right: str = Form(default="0"),
    x: str = Form(default="0"),
    y: str = Form(default="0"),
    w: str = Form(default="0"),
    h: str = Form(default="0"),
    unit: str = Form(default="pt"),
):
    # normalize mode
    m = (mode or "margins").strip().lower()
    if m not in ALLOWED_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid mode, must be one of {', '.join(sorted(ALLOWED_MODES))}")

    unit_norm = (unit or "pt").strip().lower()
    if unit_norm not in {"pt", "mm", "points", "millimeters"}:
        raise HTTPException(status_code=400, detail="Invalid unit, must be pt or mm")
    is_mm = unit_norm in {"mm", "millimeters"}

    # read file
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
        try:
            doc.close()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail="PDF has no pages")

    total = len(doc)

    # parse pages
    try:
        target_pages = parse_pages(pages, total)
    except HTTPException:
        try:
            doc.close()
        except Exception:
            pass
        raise

    # parse params per mode
    if m == "margins":
        top_v = parse_float_field(top, "top", min_val=0, max_val=1000)
        bottom_v = parse_float_field(bottom, "bottom", min_val=0, max_val=1000)
        left_v = parse_float_field(left, "left", min_val=0, max_val=1000)
        right_v = parse_float_field(right, "right", min_val=0, max_val=1000)

        if is_mm:
            top_v *= MM_TO_PT
            bottom_v *= MM_TO_PT
            left_v *= MM_TO_PT
            right_v *= MM_TO_PT

        if top_v == 0 and bottom_v == 0 and left_v == 0 and right_v == 0:
            try:
                doc.close()
            except Exception:
                pass
            raise HTTPException(status_code=400, detail="No crop margins provided")

        # validate each page will remain at least 1pt
        # we check before mutating
        for pg_num in target_pages:
            page = doc.load_page(pg_num - 1)
            rect = page.rect
            pw = rect.width
            ph = rect.height
            remaining_w = pw - left_v - right_v
            remaining_h = ph - top_v - bottom_v
            if remaining_w <= 1 or remaining_h <= 1:
                try:
                    doc.close()
                except Exception:
                    pass
                raise HTTPException(status_code=400, detail="Crop margins too large for page size")

        # apply
        try:
            for pg_num in target_pages:
                page = doc.load_page(pg_num - 1)
                rect = page.rect
                new_rect = fitz.Rect(rect.x0 + left_v, rect.y0 + top_v, rect.x1 - right_v, rect.y1 - bottom_v)
                # ensure non-empty
                if new_rect.width <= 1 or new_rect.height <= 1 or new_rect.x0 >= new_rect.x1 or new_rect.y0 >= new_rect.y1:
                    raise HTTPException(status_code=400, detail="Crop margins too large for page size")
                page.set_cropbox(new_rect)
        except HTTPException:
            try:
                doc.close()
            except Exception:
                pass
            raise
        except Exception as e:
            try:
                doc.close()
            except Exception:
                pass
            raise HTTPException(status_code=400, detail=f"Crop failed: {e}")

    else:  # rect mode
        x_v = parse_float_field(x, "x", min_val=0, max_val=10000)
        y_v = parse_float_field(y, "y", min_val=0, max_val=10000)
        w_v = parse_float_field(w, "w", min_val=0.1, max_val=10000)
        h_v = parse_float_field(h, "h", min_val=0.1, max_val=10000)

        # w/h must be >0 already validated; also check x,y+w/h within page
        # rect unit is always points per spec, ignore mm for rect
        # validate before apply
        for pg_num in target_pages:
            page = doc.load_page(pg_num - 1)
            rect = page.rect
            pw = rect.width
            ph = rect.height
            # need x,y within page + w/h
            # treat x,y as offsets from rect.x0, rect.y0
            abs_x0 = rect.x0 + x_v
            abs_y0 = rect.y0 + y_v
            abs_x1 = abs_x0 + w_v
            abs_y1 = abs_y0 + h_v
            if abs_x0 < rect.x0 - 0.001 or abs_y0 < rect.y0 - 0.001 or abs_x1 > rect.x1 + 0.001 or abs_y1 > rect.y1 + 0.001:
                try:
                    doc.close()
                except Exception:
                    pass
                raise HTTPException(status_code=400, detail=f"Crop rect out of bounds for page {pg_num} (page size {pw:.1f}x{ph:.1f} pt)")
            if w_v <= 1 or h_v <= 1:
                try:
                    doc.close()
                except Exception:
                    pass
                raise HTTPException(status_code=400, detail="Crop rect too small")

        try:
            for pg_num in target_pages:
                page = doc.load_page(pg_num - 1)
                rect = page.rect
                new_rect = fitz.Rect(rect.x0 + x_v, rect.y0 + y_v, rect.x0 + x_v + w_v, rect.y0 + y_v + h_v)
                page.set_cropbox(new_rect)
        except HTTPException:
            try:
                doc.close()
            except Exception:
                pass
            raise
        except Exception as e:
            try:
                doc.close()
            except Exception:
                pass
            raise HTTPException(status_code=400, detail=f"Crop failed: {e}")

    uid = str(uuid.uuid4())
    d = os.path.join(TMP_ROOT, uid)
    os.makedirs(d, exist_ok=True)
    out_path = os.path.join(d, "result.pdf")

    try:
        doc.save(out_path, garbage=4, deflate=True, clean=True)
        doc.close()
    except Exception as e:
        shutil.rmtree(d, ignore_errors=True)
        try:
            doc.close()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=f"Crop save failed: {e}")

    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Crop produced empty file")

    background_tasks.add_task(schedule_delete, out_path)
    return FileResponse(out_path, filename="cropped.pdf", media_type="application/pdf")
