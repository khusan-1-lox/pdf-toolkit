from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import uuid
import os
import shutil
import time
import io

from PIL import Image

from ..config import TMP_ROOT, MAX_FILE_SIZE, MAX_FILES, RETENTION_SECONDS

router = APIRouter()

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/bmp",
    "image/tiff",
    "image/gif",
}


def schedule_delete(path: str):
    """Delete temp dir after RETENTION_SECONDS (300s = 5 min). Non-blocking."""
    import threading

    def _del():
        time.sleep(RETENTION_SECONDS)
        dir_path = os.path.dirname(path)
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path, ignore_errors=True)

    threading.Thread(target=_del, daemon=True).start()


@router.post("/api/jpg-to-pdf")
async def jpg_to_pdf(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files")
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=413, detail="Too many files")

    uid = str(uuid.uuid4())
    d = os.path.join(TMP_ROOT, uid)
    os.makedirs(d, exist_ok=True)

    out_path = os.path.join(d, "result.pdf")

    pil_images: list[Image.Image] = []

    try:
        for f in files:
            data = await f.read()
            if len(data) > MAX_FILE_SIZE:
                raise HTTPException(status_code=413, detail="File too large")
            if len(data) == 0:
                raise HTTPException(status_code=400, detail="Empty file")

            # Optional mime check: allow any but rely on PIL; reject clearly non-image by PIL failure
            # Also reject if content_type is explicitly non-image and PIL also fails - we handle via 400
            try:
                img = Image.open(io.BytesIO(data))
                # Force load to detect truncated/corrupt
                img.load()
                # Verify it's an image by checking format
                # Image.open may succeed for PDFs (which Pillow can also open as PDF) but we treat as invalid
                # Only allow common raster formats
                if img.format not in ("JPEG", "JPG", "PNG", "WEBP", "BMP", "TIFF", "GIF", "PPM", "WEBP"):
                    # Pillow may return None for format if unknown; still try to process if load succeeded
                    # but reject if it's PDF
                    if img.format == "PDF":
                        raise HTTPException(status_code=400, detail="Invalid image: PDF not allowed")
                # Convert to RGB for PDF saving (PDF doesn't support RGBA/LA/P directly)
                if img.mode == "RGBA":
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    bg.paste(img, mask=img.split()[3])
                    img = bg
                elif img.mode == "LA":
                    # Convert LA to RGB
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    l, a = img.split()
                    rgb = Image.merge("RGB", [l, l, l])
                    bg.paste(rgb, mask=a)
                    img = bg
                elif img.mode == "P":
                    # Palette -> convert via RGBA then flatten
                    if "transparency" in img.info:
                        img = img.convert("RGBA")
                        bg = Image.new("RGB", img.size, (255, 255, 255))
                        bg.paste(img, mask=img.split()[3])
                        img = bg
                    else:
                        img = img.convert("RGB")
                elif img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                elif img.mode == "L":
                    img = img.convert("RGB")
                pil_images.append(img)
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid image: {e}")

        if not pil_images:
            raise HTTPException(status_code=400, detail="No valid images")

        # Save to PDF using Pillow save_all
        first, rest = pil_images[0], pil_images[1:]
        # Ensure output dir exists
        # Pillow can save with save_all; first.save(out_path, "PDF", save_all=True, append_images=rest)
        try:
            if rest:
                first.save(out_path, "PDF", resolution=100.0, save_all=True, append_images=rest)
            else:
                first.save(out_path, "PDF", resolution=100.0)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to create PDF: {e}")

    except HTTPException:
        shutil.rmtree(d, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"JPG to PDF failed: {e}")

    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Failed to create PDF")

    background_tasks.add_task(schedule_delete, out_path)
    return FileResponse(out_path, filename="images.pdf", media_type="application/pdf")
