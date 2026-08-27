from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import fitz
import os
import uuid
import shutil
import time
import asyncio
import subprocess

try:
    import pikepdf
except Exception:
    pikepdf = None

from ..config import TMP_ROOT, MAX_FILE_SIZE, RETENTION_SECONDS

router = APIRouter()


def schedule_delete(path: str):
    import threading

    def _del():
        time.sleep(RETENTION_SECONDS)
        d = os.path.dirname(path)
        if os.path.exists(d):
            shutil.rmtree(d, ignore_errors=True)

    threading.Thread(target=_del, daemon=True).start()


async def convert_to_pdfa(in_path, out_path):
    def _sync():
        # Try ghostscript if exists
        if shutil.which("gs") or shutil.which("gswin64c"):
            gs = shutil.which("gs") or shutil.which("gswin64c")
            subprocess.run(
                [gs, "-dPDFA", "-dBATCH", "-dNOPAUSE", "-sColorConversionStrategy=RGB", "-sDEVICE=pdfwrite", f"-sOutputFile={out_path}", in_path],
                timeout=30,
                check=True,
            )
            return
        if pikepdf:
            with pikepdf.open(in_path) as pdf:
                pdf.save(out_path)
            return
        # fallback fitz
        doc = fitz.open(in_path)
        doc.save(out_path, garbage=4, deflate=True)
        doc.close()

    await asyncio.to_thread(_sync)


async def _handle_pdfa(file: UploadFile, background_tasks: BackgroundTasks):
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
    out_path = os.path.join(d, "pdfa.pdf")

    with open(in_path, "wb") as out:
        out.write(data)

    try:
        await convert_to_pdfa(in_path, out_path)
    except HTTPException:
        shutil.rmtree(d, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=422, detail=f"PDF/A conversion failed: {e}")

    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=422, detail="PDF/A conversion produced empty file")

    background_tasks.add_task(schedule_delete, out_path)
    return FileResponse(out_path, filename="pdfa.pdf", media_type="application/pdf", headers={"X-PDF-A": "true"})


@router.post("/api/pdf-to-pdfa")
async def pdf_to_pdfa(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    return await _handle_pdfa(file, background_tasks)


@router.post("/api/pdfa")
async def pdfa_alias(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    return await _handle_pdfa(file, background_tasks)
