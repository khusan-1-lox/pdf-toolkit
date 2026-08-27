from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import uuid
import os
import shutil
import time
import asyncio

from ..config import TMP_ROOT, MAX_FILE_SIZE, RETENTION_SECONDS

router = APIRouter()

try:
    import pytesseract
    from PIL import Image
    import io

    HAS_TESS = True
except Exception:
    HAS_TESS = False
    io = None  # type: ignore
    Image = None  # type: ignore

import fitz


def schedule_delete(path: str):
    import threading

    def _del():
        time.sleep(RETENTION_SECONDS)
        d = os.path.dirname(path)
        if os.path.exists(d):
            shutil.rmtree(d, ignore_errors=True)

    threading.Thread(target=_del, daemon=True).start()


async def do_ocr(in_path: str, out_path: str, lang: str = "rus+eng"):
    def _sync():
        doc = fitz.open(in_path)
        if len(doc) == 0:
            doc.close()
            raise ValueError("PDF has no pages")
        new_doc = fitz.open()
        for page in doc:
            pix = page.get_pixmap(dpi=150)
            img_data = pix.tobytes("png")
            if HAS_TESS:
                try:
                    # need io and PIL
                    import io as _io
                    from PIL import Image as _Image

                    img = _Image.open(_io.BytesIO(img_data))
                    text = pytesseract.image_to_string(img, lang=lang)
                except Exception:
                    try:
                        text = page.get_text()
                    except Exception:
                        text = ""
            else:
                try:
                    text = page.get_text()
                except Exception:
                    text = ""
            # create new page with image + hidden text
            new_page = new_doc.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(page.rect, stream=img_data)
            if text and text.strip():
                # hidden-ish white text
                try:
                    new_page.insert_text((10, 20), text[:2000], fontsize=10, color=(1, 1, 1))
                except Exception:
                    pass
        new_doc.save(out_path, garbage=4)
        new_doc.close()
        doc.close()

    await asyncio.to_thread(_sync)


@router.post("/api/ocr-pdf")
async def ocr_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    lang: str = Form(default="rus+eng"),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only .pdf allowed")
    data = await file.read()
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")

    uid = str(uuid.uuid4())
    d = os.path.join(TMP_ROOT, uid)
    os.makedirs(d, exist_ok=True)
    in_path = os.path.join(d, "in.pdf")
    out_path = os.path.join(d, "ocr.pdf")

    with open(in_path, "wb") as out:
        out.write(data)

    try:
        await do_ocr(in_path, out_path, lang=lang or "rus+eng")
    except HTTPException:
        shutil.rmtree(d, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(d, ignore_errors=True)
        # distinguish invalid pdf vs ocr failure - spec says 422
        raise HTTPException(status_code=422, detail=f"OCR failed: {e}")

    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=422, detail="OCR produced empty file")

    background_tasks.add_task(schedule_delete, out_path)
    return FileResponse(out_path, filename="ocr.pdf", media_type="application/pdf")
