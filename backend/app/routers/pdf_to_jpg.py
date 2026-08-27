from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import uuid
import os
import shutil
import time
import io
import zipfile
import tempfile

from ..config import TMP_ROOT, MAX_FILE_SIZE, RETENTION_SECONDS

router = APIRouter()


def schedule_delete(path: str):
    """Delete temp dir after RETENTION_SECONDS (300s = 5 min). Non-blocking."""
    import threading

    def _del():
        time.sleep(RETENTION_SECONDS)
        dir_path = os.path.dirname(path)
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path, ignore_errors=True)

    threading.Thread(target=_del, daemon=True).start()


@router.post("/api/pdf-to-jpg")
async def pdf_to_jpg(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    uid = str(uuid.uuid4())
    d = os.path.join(TMP_ROOT, uid)
    os.makedirs(d, exist_ok=True)

    in_path = os.path.join(d, "input.pdf")
    zip_path = os.path.join(d, "result.zip")

    try:
        with open(in_path, "wb") as f:
            f.write(data)
    except Exception as e:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Failed to save input: {e}")

    images = None
    # Try pdf2image first
    pdf2image_error = None
    try:
        from pdf2image import convert_from_path

        # pdf2image requires poppler; try with 150 dpi
        images = convert_from_path(in_path, dpi=150)
        if not images:
            raise ValueError("pdf2image produced no images")
    except Exception as e:
        pdf2image_error = e
        images = None

    # Fallback to PyMuPDF if pdf2image failed or not available
    if images is None:
        try:
            import fitz  # PyMuPDF alias
        except ImportError:
            try:
                import pymupdf as fitz
            except ImportError:
                fitz = None

        if fitz is None:
            shutil.rmtree(d, ignore_errors=True)
            raise HTTPException(
                status_code=500,
                detail=f"PDF rendering unavailable (poppler not found): {pdf2image_error}",
            )

        try:
            doc = fitz.open(in_path)
            if len(doc) == 0:
                doc.close()
                raise HTTPException(status_code=400, detail="PDF has no pages")
            # Render each page to PIL Image via pixmap
            from PIL import Image

            images = []
            for page in doc:
                # Use 2x matrix ~144 dpi (72*2)
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                # Convert pixmap to PIL Image
                if pix.n >= 4:
                    # Handle CMYK or RGBA - convert to RGB
                    # pix.samples is bytes, pix.n is components per pixel
                    mode = "RGBA" if pix.alpha else "RGB"
                    # For CMYK (n==4 without alpha) -> convert via fitz
                    if pix.n == 4 and not pix.alpha:
                        # Convert CMYK pixmap to RGB
                        rgb_pix = fitz.Pixmap(fitz.csRGB, pix)
                        img = Image.frombytes("RGB", [rgb_pix.width, rgb_pix.height], rgb_pix.samples)
                        rgb_pix = None
                    else:
                        img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
                        if mode == "RGBA":
                            # Flatten alpha onto white
                            bg = Image.new("RGB", img.size, (255, 255, 255))
                            bg.paste(img, mask=img.split()[3])
                            img = bg
                else:
                    # n==1 (gray) or 3 (RGB)
                    mode = "RGB" if pix.n == 3 else "L"
                    img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
                    if mode == "L":
                        img = img.convert("RGB")
                images.append(img)
            doc.close()
            if not images:
                raise HTTPException(status_code=400, detail="PDF has no pages")
        except HTTPException:
            shutil.rmtree(d, ignore_errors=True)
            raise
        except Exception as e:
            shutil.rmtree(d, ignore_errors=True)
            msg = str(e).lower()
            if "password" in msg or "encrypt" in msg:
                raise HTTPException(status_code=400, detail="Encrypted PDF not supported")
            # If fitz also fails, likely invalid PDF
            raise HTTPException(status_code=400, detail=f"Invalid PDF: {e}")

    # At this point images is list of PIL Images
    try:
        from PIL import Image

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for idx, img in enumerate(images, start=1):
                # Ensure RGB for JPEG
                if img.mode != "RGB":
                    # Handle RGBA/LA/P
                    if img.mode == "RGBA":
                        bg = Image.new("RGB", img.size, (255, 255, 255))
                        bg.paste(img, mask=img.split()[3])
                        img = bg
                    elif img.mode == "LA":
                        bg = Image.new("RGB", img.size, (255, 255, 255))
                        # LA: split L and A
                        l, a = img.split()
                        rgb = Image.merge("RGB", [l, l, l])
                        bg.paste(rgb, mask=a)
                        img = bg
                    else:
                        img = img.convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=95)
                buf.seek(0)
                z.writestr(f"page_{idx}.jpg", buf.read())
    except HTTPException:
        shutil.rmtree(d, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"PDF to JPG failed: {e}")

    if not os.path.exists(zip_path) or os.path.getsize(zip_path) == 0:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Failed to create ZIP")

    background_tasks.add_task(schedule_delete, zip_path)
    return FileResponse(zip_path, filename="pdf_to_jpg.zip", media_type="application/zip")
