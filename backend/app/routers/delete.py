from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import uuid
import os
import shutil
import time
import io

from pypdf import PdfReader, PdfWriter

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


def parse_pages(pages_str: str, total: int) -> set[int]:
    if not pages_str or not pages_str.strip():
        raise HTTPException(status_code=400, detail="pages parameter required")
    result: set[int] = set()
    parts = pages_str.split(",")
    for token in parts:
        token = token.strip()
        if not token:
            raise HTTPException(status_code=400, detail="Invalid pages format")
        if "-" in token:
            range_parts = token.split("-")
            if len(range_parts) != 2:
                raise HTTPException(status_code=400, detail="Invalid pages format")
            s, e = range_parts[0].strip(), range_parts[1].strip()
            if not s or not e:
                raise HTTPException(status_code=400, detail="Invalid pages format")
            try:
                start = int(s)
                end = int(e)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid pages format")
            if start < 1 or end < 1 or start > total or end > total:
                bad = start if (start < 1 or start > total) else end
                raise HTTPException(status_code=400, detail=f"Page {bad} out of range (file has {total} pages)")
            if start > end:
                raise HTTPException(status_code=400, detail="Invalid page range")
            for p in range(start, end + 1):
                result.add(p)
        else:
            try:
                num = int(token)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid pages format")
            if num < 1 or num > total:
                raise HTTPException(status_code=400, detail=f"Page {num} out of range (file has {total} pages)")
            result.add(num)
    if not result:
        raise HTTPException(status_code=400, detail="No valid pages")
    return result


@router.post("/api/delete")
async def delete_pages(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    pages: str = Form(...),
):
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        reader = PdfReader(io.BytesIO(data))
        total = len(reader.pages)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid PDF")

    if total == 0:
        raise HTTPException(status_code=400, detail="PDF has no pages")

    to_delete = parse_pages(pages, total)

    if len(to_delete) >= total:
        raise HTTPException(status_code=400, detail="Cannot delete all pages")

    uid = str(uuid.uuid4())
    d = os.path.join(TMP_ROOT, uid)
    os.makedirs(d, exist_ok=True)

    out_path = os.path.join(d, "result.pdf")
    try:
        writer = PdfWriter()
        for idx, page in enumerate(reader.pages):
            if (idx + 1) not in to_delete:
                writer.add_page(page)
        with open(out_path, "wb") as f:
            writer.write(f)
    except HTTPException:
        shutil.rmtree(d, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Delete failed: {e}")

    background_tasks.add_task(schedule_delete, out_path)
    return FileResponse(out_path, filename="deleted.pdf", media_type="application/pdf")
