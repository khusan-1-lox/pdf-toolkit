import asyncio
import io
import os
import shutil
import time
import uuid

import fitz
from PIL import Image
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..config import MAX_FILE_SIZE, RETENTION_SECONDS, TMP_ROOT

router = APIRouter()
ALLOWED_QUALITIES = {"low", "medium", "high"}
# Low image quality gives the strongest compression.
IMAGE_SETTINGS = {"low": (45, 1200), "medium": (70, 1800), "high": (90, 2600)}


def schedule_delete(path: str):
    import threading

    def delete():
        time.sleep(RETENTION_SECONDS)
        shutil.rmtree(os.path.dirname(path), ignore_errors=True)

    threading.Thread(target=delete, daemon=True).start()


def compress_document(data: bytes, out_path: str, quality: str):
    with fitz.open(stream=data, filetype="pdf") as doc:
        if doc.needs_pass:
            raise HTTPException(400, "Encrypted PDF not supported")
        if not len(doc):
            raise HTTPException(400, "PDF has no pages")
        jpeg_quality, max_dimension = IMAGE_SETTINGS[quality]
        visited = set()
        for page in doc:
            for image in page.get_images(full=True):
                xref, smask, width, height = image[:4]
                if xref in visited:
                    continue
                visited.add(xref)
                # Preserve transparency, masks, line art and small logos losslessly.
                if smask or min(width, height) < 128 or image[4] != 8:
                    continue
                if doc.xref_get_key(xref, "Mask")[0] != "null":
                    continue
                try:
                    original = doc.extract_image(xref)
                    with Image.open(io.BytesIO(original["image"])) as source:
                        if source.mode not in ("RGB", "L"):
                            continue
                        replacement = source.copy()
                    replacement.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
                    buffer = io.BytesIO()
                    replacement.save(buffer, "JPEG", quality=jpeg_quality, optimize=True)
                    replacement.close()
                    encoded = buffer.getvalue()
                    if len(encoded) < len(original["image"]):
                        # Replace dictionary and stream together; stream-only updates
                        # leave stale filters and can corrupt the image.
                        page.replace_image(xref, stream=encoded)
                except (ValueError, OSError):
                    continue
        doc.save(out_path, garbage=4, deflate=True)
    if os.path.getsize(out_path) >= len(data):
        with open(out_path, "wb") as output:
            output.write(data)


@router.post("/api/compress")
async def compress_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    quality: str = Form(default="medium"),
):
    quality = quality.strip().lower()
    if quality not in ALLOWED_QUALITIES:
        raise HTTPException(400, "Invalid quality: must be low, medium or high")
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(413, "File too large")
    if not data:
        raise HTTPException(400, "Empty file")
    directory = os.path.join(TMP_ROOT, str(uuid.uuid4()))
    os.makedirs(directory, exist_ok=True)
    out_path = os.path.join(directory, "result.pdf")
    try:
        await asyncio.to_thread(compress_document, data, out_path, quality)
    except HTTPException:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(directory, ignore_errors=True)
        raise HTTPException(400, f"Could not compress PDF: {exc}") from exc
    background_tasks.add_task(schedule_delete, out_path)
    return FileResponse(
        out_path, filename="compressed.pdf", media_type="application/pdf",
        headers={"X-Original-Size": str(len(data)),
                 "X-Compressed-Size": str(os.path.getsize(out_path))},
    )
