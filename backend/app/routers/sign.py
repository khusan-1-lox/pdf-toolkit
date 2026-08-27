from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import uuid
import os
import shutil
import time
import io

from ..config import TMP_ROOT, MAX_FILE_SIZE, RETENTION_SECONDS

router = APIRouter()

ALLOWED_POSITIONS = {"center","top-left","top-right","bottom-left","bottom-right","bottom-center","top-center"}

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

def parse_pages(pages_str: str, total: int):
    s = str(pages_str).strip().lower()
    if s == "" or s == "all":
        return set(range(1, total+1))
    result = set()
    parts = s.split(",")
    for token in parts:
        token = token.strip()
        if not token:
            raise HTTPException(status_code=400, detail="Invalid pages format")
        if "-" in token:
            a,b = [x.strip() for x in token.split("-",1)]
            try:
                start = int(a); end=int(b)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid pages format")
            if start <1 or end<1 or start>total or end>total:
                bad = start if (start<1 or start>total) else end
                raise HTTPException(status_code=400, detail=f"Page {bad} out of range (file has {total} pages)")
            if start>end:
                raise HTTPException(status_code=400, detail="Invalid page range")
            for p in range(start,end+1):
                result.add(p)
        else:
            try:
                num=int(token)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid pages format")
            if num<1 or num>total:
                raise HTTPException(status_code=400, detail=f"Page {num} out of range (file has {total} pages)")
            result.add(num)
    return result

@router.post("/api/sign")
async def sign_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    image: UploadFile = File(...),
    position: str = Form(default="bottom-right"),
    page: str = Form(default="all"),
    pages: str | None = Form(default=None),
    opacity: str = Form(default="1.0"),
    x: str | None = Form(default=None),
    y: str | None = Form(default=None),
    w: str | None = Form(default=None),
    h: str | None = Form(default=None),
    width: str | None = Form(default=None),
    height: str | None = Form(default=None),
):
    # handle alias: pages vs page
    pages_str = pages if pages is not None and str(pages).strip() != "" else page
    if pages_str is None or str(pages_str).strip() == "":
        pages_str = "all"

    try:
        op_str = str(opacity).strip().replace(",", ".")
        op_f = float(op_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid opacity")
    if not (0.1 <= op_f <= 1.0):
        raise HTTPException(status_code=400, detail="Invalid opacity, must be 0.1-1.0")

    # validate position
    pos_norm = str(position).strip().lower().replace("_","-") if position else "bottom-right"
    if pos_norm not in ALLOWED_POSITIONS:
        # if explicit x,y,w,h given, allow any position as fallback -> treat as bottom-right if invalid?
        # but we enforce if no explicit rect, position must be valid
        # check if explicit rect provided, then position can be ignored
        has_rect = any(v is not None and str(v).strip() != "" for v in [x,y,w,h,width,height])
        if not has_rect:
            raise HTTPException(status_code=400, detail=f"Invalid position, must be one of {', '.join(sorted(ALLOWED_POSITIONS))}")

    # read pdf
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    # read image
    try:
        img_data = await image.read()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image")
    if not img_data or len(img_data) == 0:
        raise HTTPException(status_code=400, detail="Empty image")
    if len(img_data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Image too large")

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
    try:
        target_pages = parse_pages(pages_str, total)
    except HTTPException:
        try:
            doc.close()
        except Exception:
            pass
        raise

    # prepare image with opacity
    # normalize w/h aliases
    w_raw = w if w is not None else width
    h_raw = h if h is not None else height
    has_explicit_rect = False
    try:
        has_explicit_rect = all(v is not None and str(v).strip() != "" for v in [x,y,w_raw,h_raw])
        # also need numeric check
        if has_explicit_rect:
            xv = float(str(x).replace(",","."))
            yv = float(str(y).replace(",","."))
            wv = float(str(w_raw).replace(",","."))
            hv = float(str(h_raw).replace(",","."))
            if wv <= 0 or hv <= 0:
                raise HTTPException(status_code=400, detail="Invalid w/h, must be >0")
            # validate within range later per page
        else:
            has_explicit_rect = False
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid x,y,w,h")

    # process image opacity via Pillow
    image_png_bytes = None
    img_w = 0
    img_h = 0
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(img_data))
        img = img.convert("RGBA")
        img_w, img_h = img.size
        if op_f < 1.0:
            r,g,b,a = img.split()
            a = a.point(lambda p: int(p * op_f))
            img = Image.merge("RGBA", (r,g,b,a))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_png_bytes = buf.getvalue()
        img_w, img_h = img.size
    except HTTPException:
        raise
    except Exception as e:
        try:
            doc.close()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")

    # if not explicit rect, determine wv/hv for preset: use provided w/h if given else default 120x60 or proportional
    if not has_explicit_rect:
        # Use provided w_raw/h_raw as desired size else default
        try:
            if w_raw is not None and str(w_raw).strip() != "":
                wv = float(str(w_raw).replace(",","."))
            else:
                wv = min(150, img_w * 0.5) if img_w else 120
                # but ensure at least 80
                if wv < 40:
                    wv = 120
            if h_raw is not None and str(h_raw).strip() != "":
                hv = float(str(h_raw).replace(",","."))
            else:
                # keep aspect
                if img_w and img_h:
                    hv = wv * (img_h / img_w)
                else:
                    hv = 60
            if wv <=0 or hv <=0:
                raise HTTPException(status_code=400, detail="Invalid w/h")
        except HTTPException:
            raise
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid w/h")

    # For each target page, place image
    try:
        for idx, page_obj in enumerate(doc):
            pg_num = idx+1
            if pg_num not in target_pages:
                continue
            rect = page_obj.rect
            pw = rect.width
            ph = rect.height
            margin = 10
            if has_explicit_rect:
                xv = float(str(x).replace(",","."))
                yv = float(str(y).replace(",","."))
                wv2 = float(str(w_raw).replace(",","."))
                hv2 = float(str(h_raw).replace(",","."))
                # validate within page
                if xv < 0 or yv < 0 or xv+wv2 > pw+1 or yv+hv2 > ph+1:
                    # We allow but clamp? For spec we should error if out of bounds
                    # raise 400 if grossly out of bounds
                    if xv+wv2 > pw+5 or yv+hv2 > ph+5 or xv< -5 or yv< -5:
                        raise HTTPException(status_code=400, detail=f"Sign rect out of bounds for page {pg_num}")
                x0 = rect.x0 + xv
                y0 = rect.y0 + yv
                # y in fitz origin top-left? Rect y0 top. Use direct.
                # Use as provided: x,y from top-left
                rect_img = fitz.Rect(x0, y0, x0+wv2, y0+hv2)
            else:
                # preset positioning
                # scale to fit if wv/hv > page*0.5
                max_w = pw * 0.4
                max_h = ph * 0.2
                scale = 1.0
                if wv > max_w or hv > max_h:
                    scale = min(max_w/wv, max_h/hv)
                nw = wv * scale
                nh = hv * scale
                if pos_norm == "center":
                    x0 = rect.x0 + (pw - nw)/2
                    y0 = rect.y0 + (ph - nh)/2
                elif pos_norm == "top-left":
                    x0 = rect.x0 + margin
                    y0 = rect.y0 + margin
                elif pos_norm == "top-right":
                    x0 = rect.x1 - nw - margin
                    y0 = rect.y0 + margin
                elif pos_norm == "top-center":
                    x0 = rect.x0 + (pw - nw)/2
                    y0 = rect.y0 + margin
                elif pos_norm == "bottom-left":
                    x0 = rect.x0 + margin
                    y0 = rect.y1 - nh - margin
                elif pos_norm == "bottom-center":
                    x0 = rect.x0 + (pw - nw)/2
                    y0 = rect.y1 - nh - margin
                elif pos_norm == "bottom-right":
                    x0 = rect.x1 - nw - margin
                    y0 = rect.y1 - nh - margin
                else:
                    x0 = rect.x1 - nw - margin
                    y0 = rect.y1 - nh - margin
                rect_img = fitz.Rect(x0, y0, x0+nw, y0+nh)

            # also use new_shape as per watermark spec
            try:
                _shape = page_obj.new_shape()
                _shape.draw_rect(rect_img)
                _shape.finish(fill_opacity=op_f, stroke_opacity=op_f)
                _shape.commit(overlay=True)
            except Exception:
                pass
            try:
                page_obj.insert_image(rect_img, stream=image_png_bytes, overlay=True, keep_proportion=True)
            except Exception as e:
                try:
                    pix = fitz.Pixmap(image_png_bytes)
                    page_obj.insert_image(rect_img, pixmap=pix, overlay=True, keep_proportion=True)
                except Exception:
                    raise HTTPException(status_code=400, detail=f"Failed to insert signature: {e}")

        uid = str(uuid.uuid4())
        d = os.path.join(TMP_ROOT, uid)
        os.makedirs(d, exist_ok=True)
        out_path = os.path.join(d, "result.pdf")
        doc.save(out_path, garbage=4, deflate=True, clean=True)
        doc.close()
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
        raise HTTPException(status_code=400, detail=f"Sign failed: {e}")

    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Sign produced empty file")

    background_tasks.add_task(schedule_delete, out_path)
    return FileResponse(out_path, filename="signed.pdf", media_type="application/pdf")
