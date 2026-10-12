import asyncio
import io
import os
import shutil
import time
import uuid

import fitz
from PIL import Image, ImageOps
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

from ..config import TMP_ROOT, MAX_FILE_SIZE, MAX_FILES, RETENTION_SECONDS

router = APIRouter()
PAGE_SIZES = {"a4": (595.276, 841.89), "a3": (841.89, 1190.551), "letter": (612, 792)}
MARGINS = {"none": 0, "small": 14.173, "medium": 28.346, "large": 56.693}


def schedule_delete(path: str):
    import threading

    def delete():
        time.sleep(RETENTION_SECONDS)
        shutil.rmtree(os.path.dirname(path), ignore_errors=True)

    threading.Thread(target=delete, daemon=True).start()


def build_image_pdf(images, out_path, orientation, page_size, margin):
    padding = MARGINS[margin]
    with fitz.open() as doc:
        for data in images:
            with Image.open(io.BytesIO(data)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP", "BMP", "TIFF", "GIF", "PPM"}:
                    raise ValueError("Unsupported image format")
                source.load()
                image = ImageOps.exif_transpose(source).convert("RGBA")
                # Composite alpha over white, including palette PNG and LA images.
                background = Image.new("RGBA", image.size, "white")
                background.alpha_composite(image)
                rgb = background.convert("RGB")
                width, height = rgb.size
                if page_size == "fit":
                    # Preserve the image aspect ratio; orientation is not meaningful
                    # when the user explicitly chooses an image-sized page.
                    page_width, page_height = width * 0.72 + 2 * padding, height * 0.72 + 2 * padding
                else:
                    page_width, page_height = PAGE_SIZES[page_size]
                    if orientation == "landscape" or (orientation == "auto" and width > height):
                        page_width, page_height = page_height, page_width
                page = doc.new_page(width=page_width, height=page_height)
                content = fitz.Rect(padding, padding, page_width - padding, page_height - padding)
                image_bytes = io.BytesIO()
                rgb.save(image_bytes, "PNG")
                page.insert_image(content, stream=image_bytes.getvalue(), keep_proportion=True)
                rgb.close()
                background.close()
                image.close()
        doc.save(out_path, garbage=4, deflate=True)


@router.post("/api/scan-to-pdf")
@router.post("/api/jpg-to-pdf")
async def jpg_to_pdf(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    orientation: str = Form(default="portrait"),
    pageSize: str = Form(default="A4"),
    margin: str = Form(default="medium"),
):
    orientation, page_size, margin = orientation.lower(), pageSize.lower(), margin.lower()
    if orientation not in {"portrait", "landscape", "auto"}:
        raise HTTPException(400, "Invalid orientation")
    if page_size not in {*PAGE_SIZES, "fit"}:
        raise HTTPException(400, "Invalid pageSize: use A4, A3, Letter or fit")
    if margin not in MARGINS:
        raise HTTPException(400, "Invalid margin")
    if not files:
        raise HTTPException(400, "No files")
    if len(files) > MAX_FILES:
        raise HTTPException(413, "Too many files")
    images = []
    for file in files:
        data = await file.read()
        if not data:
            raise HTTPException(400, "Empty file")
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(413, "File too large")
        images.append(data)
    directory = os.path.join(TMP_ROOT, str(uuid.uuid4()))
    os.makedirs(directory, exist_ok=True)
    out_path = os.path.join(directory, "result.pdf")
    try:
        await asyncio.to_thread(build_image_pdf, images, out_path, orientation, page_size, margin)
    except Exception as exc:
        shutil.rmtree(directory, ignore_errors=True)
        raise HTTPException(400, f"Invalid image or PDF settings: {exc}") from exc
    background_tasks.add_task(schedule_delete, out_path)
    return FileResponse(out_path, filename="images.pdf", media_type="application/pdf")
