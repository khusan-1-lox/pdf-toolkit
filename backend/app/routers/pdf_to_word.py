from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import uuid
import os
import shutil
import time
import asyncio
from ..config import TMP_ROOT, MAX_FILE_SIZE, RETENTION_SECONDS
from ..services.office_convert import convert_pdf_to_docx

router = APIRouter()


def schedule_delete(path: str):
    import threading

    def _del():
        time.sleep(RETENTION_SECONDS)
        d = os.path.dirname(path)
        if os.path.exists(d):
            shutil.rmtree(d, ignore_errors=True)

    threading.Thread(target=_del, daemon=True).start()


@router.post("/api/pdf-to-word")
async def pdf_to_word(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
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
    with open(in_path, "wb") as out:
        out.write(data)
    out_path = os.path.join(d, "converted.docx")
    try:
        await asyncio.to_thread(convert_pdf_to_docx, in_path, out_path)
    except Exception as e:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=422, detail=f"Conversion failed: {e}")
    background_tasks.add_task(schedule_delete, out_path)
    return FileResponse(
        out_path,
        filename="converted.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
