from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import uuid, os, shutil, time
from ..config import TMP_ROOT, MAX_FILE_SIZE, RETENTION_SECONDS
from ..services.office_convert import convert_office_to_pdf

router = APIRouter()

def schedule_delete(path: str):
    import threading
    def _del():
        time.sleep(RETENTION_SECONDS)
        d = os.path.dirname(path)
        if os.path.exists(d):
            shutil.rmtree(d, ignore_errors=True)
    threading.Thread(target=_del, daemon=True).start()

@router.post("/api/excel-to-pdf")
async def excel_to_pdf(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith((".xlsx",".xls")):
        raise HTTPException(status_code=400, detail="Only .xlsx/.xls allowed")
    data = await file.read()
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")
    uid = str(uuid.uuid4())
    d = os.path.join(TMP_ROOT, uid)
    os.makedirs(d, exist_ok=True)
    in_path = os.path.join(d, os.path.basename(file.filename))
    with open(in_path, "wb") as out:
        out.write(data)
    try:
        out_pdf = await convert_office_to_pdf(in_path, d)
    except Exception as e:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=422, detail=f"Conversion failed: {e}")
    background_tasks.add_task(schedule_delete, out_pdf)
    return FileResponse(out_pdf, filename="converted.pdf", media_type="application/pdf")
