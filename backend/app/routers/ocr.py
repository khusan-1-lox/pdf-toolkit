import asyncio
import io
import os
import re
import shutil
import time
import uuid

import fitz
from PIL import Image
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

from ..config import TMP_ROOT, MAX_FILE_SIZE, RETENTION_SECONDS

router = APIRouter()

try:
    import pytesseract
    HAS_TESS = True
except ImportError:
    pytesseract = None
    HAS_TESS = False


def schedule_delete(path: str):
    import threading

    def delete():
        time.sleep(RETENTION_SECONDS)
        shutil.rmtree(os.path.dirname(path), ignore_errors=True)

    threading.Thread(target=delete, daemon=True).start()


def check_ocr_engine(lang: str):
    if not HAS_TESS:
        raise HTTPException(503, "OCR requires pytesseract and the Tesseract OCR application on the server")
    try:
        pytesseract.get_tesseract_version()
        available = set(pytesseract.get_languages(config=""))
    except Exception as exc:
        raise HTTPException(503, "Install Tesseract OCR on the server and add it to PATH") from exc
    missing = set(lang.split("+")) - available
    if missing:
        raise HTTPException(503, "Install Tesseract language data: " + ", ".join(sorted(missing)))


async def do_ocr(in_path: str, out_path: str, lang: str = "rus+eng"):
    def convert():
        with fitz.open(in_path) as source:
            if source.needs_pass:
                raise HTTPException(400, "Encrypted PDF not supported")
            if not len(source):
                raise HTTPException(400, "PDF has no pages")
            check_ocr_engine(lang)
            with fitz.open() as result:
                for page in source:
                    # Limit raster allocation for oversized engineering drawings.
                    scale = min(200 / 72, (16_000_000 / (page.rect.width * page.rect.height)) ** 0.5)
                    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                    with Image.open(io.BytesIO(pix.tobytes("png"))) as image:
                        # Tesseract's PDF renderer embeds accurately positioned,
                        # invisible Unicode text with the full page image.
                        pdf_bytes = pytesseract.image_to_pdf_or_hocr(
                            image, extension="pdf", lang=lang,
                            config=f"--dpi {max(1, round(scale * 72))}", timeout=120,
                        )
                    with fitz.open(stream=pdf_bytes, filetype="pdf") as recognized:
                        target = result.new_page(width=page.rect.width, height=page.rect.height)
                        target.show_pdf_page(target.rect, recognized, 0)
                result.set_metadata(source.metadata)
                result.save(out_path, garbage=4, deflate=True)

    await asyncio.to_thread(convert)


@router.post("/api/ocr-pdf")
async def ocr_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    lang: str = Form(default="rus+eng"),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only .pdf allowed")
    if not re.fullmatch(r"[a-zA-Z_]+(?:\+[a-zA-Z_]+)*", lang):
        raise HTTPException(400, "Invalid OCR language")
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file")
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(413, "File too large")
    directory = os.path.join(TMP_ROOT, str(uuid.uuid4()))
    os.makedirs(directory, exist_ok=True)
    in_path, out_path = os.path.join(directory, "in.pdf"), os.path.join(directory, "ocr.pdf")
    with open(in_path, "wb") as output:
        output.write(data)
    try:
        await do_ocr(in_path, out_path, lang)
        if not os.path.exists(out_path) or not os.path.getsize(out_path):
            raise ValueError("OCR produced an empty file")
    except HTTPException:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(directory, ignore_errors=True)
        raise HTTPException(422, f"OCR failed: {exc}") from exc
    background_tasks.add_task(schedule_delete, out_path)
    return FileResponse(out_path, filename="ocr.pdf", media_type="application/pdf")
