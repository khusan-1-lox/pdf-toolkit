from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import uuid
import os
import shutil
import time
import io

from ..config import TMP_ROOT, MAX_FILE_SIZE, RETENTION_SECONDS

router = APIRouter()

ALLOWED_QUALITIES = {"low", "medium", "high"}


def schedule_delete(path: str):
    """Delete temp dir after RETENTION_SECONDS (300s = 5 min). Non-blocking."""
    import threading

    def _del():
        time.sleep(RETENTION_SECONDS)
        dir_path = os.path.dirname(path)
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path, ignore_errors=True)

    threading.Thread(target=_del, daemon=True).start()


@router.post("/api/compress")
async def compress_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    quality: str = Form(default="medium"),
):
    # validate quality
    q = str(quality).strip().lower() if quality is not None else "medium"
    if q not in ALLOWED_QUALITIES:
        raise HTTPException(status_code=400, detail=f"Invalid quality: must be one of {', '.join(sorted(ALLOWED_QUALITIES))}")

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    uid = str(uuid.uuid4())
    d = os.path.join(TMP_ROOT, uid)
    os.makedirs(d, exist_ok=True)

    in_path = os.path.join(d, "input.pdf")
    out_path = os.path.join(d, "result.pdf")

    try:
        with open(in_path, "wb") as f:
            f.write(data)
    except Exception as e:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Failed to save input: {e}")

    # Try PyMuPDF first
    try:
        import fitz  # PyMuPDF provides fitz alias
    except ImportError:
        try:
            import pymupdf as fitz
        except ImportError:
            fitz = None

    if fitz is not None:
        try:
            doc = fitz.open(in_path)
            if len(doc) == 0:
                doc.close()
                raise HTTPException(status_code=400, detail="PDF has no pages")
            # For low quality, try to recompress images by lowering pixmap quality
            # Approach: iterate images and re-encode with lower quality where possible
            if q == "low":
                try:
                    for page in doc:
                        pix = None
                        # Try to clean up images via recompression is best-effort
                        # We attempt to set image quality via save options; fallback is garbage/deflate alone
                        # More aggressive image recompression:
                        images = page.get_images(full=True)
                        for img in images:
                            xref = img[0]
                            try:
                                base_pix = fitz.Pixmap(doc, xref)
                                # Only recompress if image is large
                                if base_pix.w >= 50 and base_pix.h >= 50:
                                    # Convert to RGB if CMYK/alpha
                                    if base_pix.n > 4:
                                        rgb = fitz.Pixmap(fitz.csRGB, base_pix)
                                        base_pix = rgb
                                    # Re-encode as JPEG with lower quality (pix.tobytes with jpg)
                                    # Write back via update - replace image stream
                                    # Use tobytes JPG then set as new image via doc.update_stream
                                    jpg_bytes = base_pix.tobytes("jpg", jpg_quality=30)
                                    # Update the xref stream with recompressed JPEG
                                    doc.update_stream(xref, jpg_bytes)
                                base_pix = None
                            except Exception:
                                continue
                except Exception:
                    # Image recompression is best-effort, ignore failures
                    pass

            # Save with compression: garbage=4, deflate, clean
            # garbage=4 = max garbage collection, deflate compresses streams, clean sanitizes
            doc.save(out_path, garbage=4, deflate=True, clean=True)
            doc.close()
        except HTTPException:
            shutil.rmtree(d, ignore_errors=True)
            raise
        except Exception as e:
            # fitz can raise on encrypted/corrupt PDFs
            shutil.rmtree(d, ignore_errors=True)
            # Detect if it's an invalid PDF vs other error
            msg = str(e).lower()
            if "password" in msg or "encrypt" in msg:
                raise HTTPException(status_code=400, detail="Encrypted PDF not supported")
            raise HTTPException(status_code=400, detail=f"Invalid PDF: {e}")
    else:
        # Fallback to pypdf if fitz not available
        try:
            from pypdf import PdfReader, PdfWriter

            reader = PdfReader(in_path)
            if len(reader.pages) == 0:
                raise HTTPException(status_code=400, detail="PDF has no pages")
            writer = PdfWriter()
            for page in reader.pages:
                try:
                    page.compress_content_streams()
                except Exception:
                    pass
                writer.add_page(page)
            # pypdf writer compresses via deflate when writing
            with open(out_path, "wb") as out_f:
                writer.write(out_f)
        except HTTPException:
            shutil.rmtree(d, ignore_errors=True)
            raise
        except Exception as e:
            shutil.rmtree(d, ignore_errors=True)
            raise HTTPException(status_code=400, detail=f"Compress failed: {e}")

    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Compression produced empty file")

    background_tasks.add_task(schedule_delete, out_path)
    return FileResponse(out_path, filename="compressed.pdf", media_type="application/pdf")
