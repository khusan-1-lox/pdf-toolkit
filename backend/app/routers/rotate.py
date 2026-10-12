from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import uuid
import os
import shutil
import time
import io
import zipfile

from pypdf import PdfReader, PdfWriter

from ..config import TMP_ROOT, MAX_FILE_SIZE, MAX_FILES, RETENTION_SECONDS

router = APIRouter()

ALLOWED_ANGLES = {90, 180, 270}


def schedule_delete(path: str):
    """Delete temp dir after RETENTION_SECONDS (300s = 5 min). Non-blocking."""
    import threading

    def _del():
        time.sleep(RETENTION_SECONDS)
        dir_path = os.path.dirname(path)
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path, ignore_errors=True)

    threading.Thread(target=_del, daemon=True).start()


def _rotate_reader(reader: PdfReader, angle_int: int) -> PdfWriter:
    writer = PdfWriter()
    for page in reader.pages:
        try:
            rotated = page.rotate(angle_int)
            target = rotated if rotated is not None else page
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid angle: must be 90, 180, or 270")
        writer.add_page(target)
    return writer


@router.post("/api/rotate")
async def rotate_pdf(
    background_tasks: BackgroundTasks,
    angle: str = Form(...),
    file: UploadFile | None = File(default=None),
    files: list[UploadFile] = File(default=[]),
):
    # validate angle
    try:
        angle_int = int(str(angle).strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid angle: must be 90, 180, or 270")
    if angle_int not in ALLOWED_ANGLES:
        raise HTTPException(status_code=400, detail="Invalid angle: must be 90, 180, or 270")

    # Determine mode: multiple files via "files" field, or single via "file" field
    # Backward compat: single file uses "file"; multi uses "files" -> zip
    has_files = files is not None and len(files) > 0
    has_file = file is not None

    # If both provided, prefer multi if files has >0 entries
    if has_files and len(files) > 1:
        # --- MULTI-FILE MODE -> ZIP ---
        if len(files) > MAX_FILES:
            raise HTTPException(status_code=413, detail="Too many files")
        uid = str(uuid.uuid4())
        d = os.path.join(TMP_ROOT, uid)
        os.makedirs(d, exist_ok=True)
        zip_path = os.path.join(d, "rotate.zip")
        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
                for idx, f in enumerate(files):
                    data = await f.read()
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
                    writer = _rotate_reader(reader, angle_int)
                    pdf_bytes = io.BytesIO()
                    writer.write(pdf_bytes)
                    pdf_bytes.seek(0)
                    orig_name = os.path.basename(f.filename) if f.filename else f"file_{idx+1}.pdf"
                    # ensure .pdf extension
                    base, ext = os.path.splitext(orig_name)
                    if not ext.lower() == ".pdf":
                        orig_name = f"{base}.pdf" if base else f"file_{idx+1}.pdf"
                    # avoid duplicate names inside zip
                    entry_name = orig_name
                    if entry_name in z.namelist():
                        entry_name = f"{base}_{uuid.uuid4().hex[:6]}.pdf"
                    z.writestr(entry_name, pdf_bytes.read())
        except HTTPException:
            shutil.rmtree(d, ignore_errors=True)
            raise
        except Exception as e:
            shutil.rmtree(d, ignore_errors=True)
            raise HTTPException(status_code=400, detail=f"Rotate failed: {e}")

        background_tasks.add_task(schedule_delete, zip_path)
        return FileResponse(zip_path, filename="rotate.zip", media_type="application/zip")

    elif has_files and len(files) == 1 and not has_file:
        # Single file sent via "files" field (len 1) -> treat as single for compat, return pdf
        file = files[0]
        has_file = True
        # fall through to single-file handling
        has_files = False

    if has_file:
        # --- SINGLE-FILE MODE -> PDF (backward compat) ---
        assert file is not None
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

        uid = str(uuid.uuid4())
        d = os.path.join(TMP_ROOT, uid)
        os.makedirs(d, exist_ok=True)

        out_path = os.path.join(d, "result.pdf")
        try:
            writer = _rotate_reader(reader, angle_int)
            with open(out_path, "wb") as f:
                writer.write(f)
        except HTTPException:
            shutil.rmtree(d, ignore_errors=True)
            raise
        except Exception as e:
            shutil.rmtree(d, ignore_errors=True)
            raise HTTPException(status_code=400, detail=f"Rotate failed: {e}")

        background_tasks.add_task(schedule_delete, out_path)
        return FileResponse(out_path, filename="rotated.pdf", media_type="application/pdf")

    # No file provided at all
    raise HTTPException(status_code=400, detail="No file provided")
