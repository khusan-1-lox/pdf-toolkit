from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import uuid
import os
import shutil
import time

from ..config import TMP_ROOT, MAX_FILE_SIZE, RETENTION_SECONDS

router = APIRouter()

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

def to_bool(v):
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in ("true","1","yes","on")

@router.post("/api/redact")
async def redact_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    texts: str | None = Form(default=None),
    redact_images: str | None = Form(default=None),
    hide_images: str | None = Form(default=None),
):
    # texts is comma-separated phrases
    # redact_images / hide_images bool
    hide_images_flag = to_bool(redact_images) or to_bool(hide_images)
    # also handle if texts contains flag-like? no

    # Also support texts param named "text" fallback via reading via? we have texts
    # If texts provided as empty and hide_images false => error
    texts_list = []
    if texts is not None and str(texts).strip() != "":
        # split by comma
        raw = str(texts)
        # allow comma separated; also handle if single phrase with spaces
        parts = [p.strip() for p in raw.split(",")]
        texts_list = [p for p in parts if p != ""]

    # also handle form field "text" alias? fastapi will have texts only, but client might send "texts" correctly
    # If no texts and no hide_images => 400
    if len(texts_list) == 0 and not hide_images_flag:
        raise HTTPException(status_code=400, detail="No texts or hide_images provided")

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

    try:
        for page in doc:
            # redact texts
            for phrase in texts_list:
                try:
                    rects = page.search_for(phrase)
                except Exception:
                    rects = []
                for rect in rects:
                    try:
                        # fill black
                        page.add_redact_annot(rect, fill=(0,0,0))
                    except Exception:
                        continue
            # redact images
            if hide_images_flag:
                try:
                    images = page.get_images(full=True)
                except Exception:
                    images = []
                for img in images:
                    try:
                        xref = img[0]
                        # get rects for this image xref
                        try:
                            rects = page.get_image_rects(xref)
                        except Exception:
                            # fallback: try get_image_bbox
                            try:
                                rects = page.get_image_bbox(img)  # type: ignore
                                rects = [rects] if rects else []
                            except Exception:
                                rects = []
                        for r in rects:
                            try:
                                page.add_redact_annot(r, fill=(0,0,0))
                            except Exception:
                                continue
                    except Exception:
                        continue
            # apply redactions for this page
            try:
                # default args redact correctly (text=0 means redact). No args is safest.
                page.apply_redactions()
            except Exception:
                try:
                    page.apply_redactions(images=2, graphics=1, text=0)
                except Exception:
                    pass

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
        raise HTTPException(status_code=400, detail=f"Redact failed: {e}")

    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Redact produced empty file")

    background_tasks.add_task(schedule_delete, out_path)
    return FileResponse(out_path, filename="redacted.pdf", media_type="application/pdf")
