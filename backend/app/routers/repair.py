from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import uuid
import os
import shutil
import time

from ..config import TMP_ROOT, MAX_FILE_SIZE, RETENTION_SECONDS

router = APIRouter()

# optional pikepdf
try:
    import pikepdf  # type: ignore
    HAS_PIKEPDF = True
except Exception:
    pikepdf = None  # type: ignore
    HAS_PIKEPDF = False

try:
    import fitz  # PyMuPDF
except ImportError:
    try:
        import pymupdf as fitz  # type: ignore
    except ImportError:
        fitz = None  # type: ignore


def schedule_delete(path: str):
    """Delete temp dir after RETENTION_SECONDS (300s = 5 min). Non-blocking."""
    import threading

    def _del():
        time.sleep(RETENTION_SECONDS)
        dir_path = os.path.dirname(path)
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path, ignore_errors=True)

    threading.Thread(target=_del, daemon=True).start()


def _repair_sync(in_path: str, out_path: str):
    """Try fitz rebuild, fallback to pikepdf."""
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) not available")

    # First attempt: fitz open + save garbage=4 deflate clean
    try:
        doc = fitz.open(in_path)
        if len(doc) == 0:
            doc.close()
            raise ValueError("PDF has no pages")
        doc.save(out_path, garbage=4, deflate=True, clean=True)
        doc.close()
        return
    except Exception as e1:
        # fitz failed - try pikepdf if available
        if HAS_PIKEPDF and pikepdf is not None:
            try:
                with pikepdf.open(in_path) as pdf:
                    pdf.save(out_path)
                # Second pass: re-save with fitz to deflate/clean if possible (best-effort)
                try:
                    doc2 = fitz.open(out_path)
                    tmp2 = out_path + ".fitz.tmp"
                    doc2.save(tmp2, garbage=4, deflate=True, clean=True)
                    doc2.close()
                    shutil.move(tmp2, out_path)
                except Exception:
                    # pikepdf output is still valid even if fitz second pass fails
                    pass
                return
            except Exception as e2:
                # Both fitz and pikepdf failed -> raise 422 with details
                msg1 = str(e1).lower()
                if "password" in msg1 or "encrypt" in msg1:
                    raise ValueError(f"Encrypted PDF not supported: {e1}") from e1
                raise ValueError(f"Repair failed (fitz: {e1}; pikepdf: {e2})") from e2
        else:
            msg = str(e1).lower()
            if "password" in msg or "encrypt" in msg:
                raise ValueError(f"Encrypted PDF not supported: {e1}") from e1
            raise ValueError(f"Repair failed: {e1}") from e1


async def _handle_repair(file: UploadFile, background_tasks: BackgroundTasks):
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
    out_path = os.path.join(d, "repaired.pdf")

    try:
        with open(in_path, "wb") as f:
            f.write(data)
    except Exception as e:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Failed to save input: {e}")

    # Repair
    try:
        # run sync repair in thread to avoid blocking event loop for large files
        import asyncio
        await asyncio.to_thread(_repair_sync, in_path, out_path)
    except ValueError as ve:
        shutil.rmtree(d, ignore_errors=True)
        msg = str(ve).lower()
        if "encrypted" in msg:
            raise HTTPException(status_code=400, detail=str(ve))
        raise HTTPException(status_code=422, detail=str(ve))
    except HTTPException:
        shutil.rmtree(d, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=422, detail=f"Repair failed: {e}")

    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=422, detail="Repair produced empty file")

    background_tasks.add_task(schedule_delete, out_path)
    return FileResponse(out_path, filename="repaired.pdf", media_type="application/pdf")


@router.post("/api/repair-pdf")
@router.post("/api/repair")
async def repair_pdf(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    return await _handle_repair(file, background_tasks)
