from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import uuid
import os
import shutil
import time
import io

from ..config import TMP_ROOT, MAX_FILE_SIZE, RETENTION_SECONDS

router = APIRouter()

def schedule_delete(path: str):
    import threading
    def _del():
        time.sleep(RETENTION_SECONDS)
        dir_path = os.path.dirname(path)
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path, ignore_errors=True)
    threading.Thread(target=_del, daemon=True).start()

def get_fitz():
    try:
        import fitz  # type: ignore
        return fitz
    except ImportError:
        pass
    try:
        import pymupdf as fitz  # type: ignore
        return fitz
    except ImportError:
        return None

@router.post("/api/unlock")
async def unlock_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    password: str | None = Form(default=None),
):
    if password is None or str(password).strip() == "":
        raise HTTPException(status_code=400, detail="password required")
    pwd = str(password)

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    # try fitz first
    fitz = get_fitz()
    decrypted_via_fitz = False
    out_data = None

    if fitz is not None:
        try:
            doc = fitz.open(stream=data, filetype="pdf")
            if doc.is_encrypted:
                # try authenticate
                auth = False
                try:
                    auth = doc.authenticate(pwd)
                except Exception:
                    auth = False
                if not auth:
                    try:
                        doc.close()
                    except Exception:
                        pass
                    raise HTTPException(status_code=400, detail="Invalid password")
                # authenticated, now save without encryption
                uid = str(uuid.uuid4())
                d = os.path.join(TMP_ROOT, uid)
                os.makedirs(d, exist_ok=True)
                out_path = os.path.join(d, "result.pdf")
                try:
                    # save with no encryption; garbage clean
                    doc.save(out_path, garbage=4, deflate=True, clean=True)
                    doc.close()
                except Exception as e:
                    shutil.rmtree(d, ignore_errors=True)
                    try:
                        doc.close()
                    except Exception:
                        pass
                    raise HTTPException(status_code=400, detail=f"Unlock failed: {e}")
                if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
                    shutil.rmtree(d, ignore_errors=True)
                    raise HTTPException(status_code=500, detail="Unlock produced empty file")
                background_tasks.add_task(schedule_delete, out_path)
                return FileResponse(out_path, filename="unlocked.pdf", media_type="application/pdf")
            else:
                # not encrypted - just return decrypted (no-op) via pypdf or fitz
                # we will fall through to pypdf handling which will just copy
                try:
                    doc.close()
                except Exception:
                    pass
                # not encrypted: still try pypdf path to ensure no encryption
                decrypted_via_fitz = False
        except HTTPException:
            raise
        except Exception as e:
            msg = str(e).lower()
            if "password" in msg or "encrypt" in msg:
                # try pypdf fallback
                pass
            else:
                # if fitz failed to open (invalid pdf), raise 400
                if "invalid" in msg or "cannot" in msg:
                    raise HTTPException(status_code=400, detail="Invalid PDF")
                # otherwise fallback
                pass

    # pypdf fallback / primary for encrypted
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        raise HTTPException(status_code=500, detail="pypdf not available")

    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as e:
        msg = str(e).lower()
        if "password" in msg or "encrypt" in msg:
            raise HTTPException(status_code=400, detail="Invalid password")
        raise HTTPException(status_code=400, detail="Invalid PDF")

    if not reader.is_encrypted:
        # Not encrypted - just copy without encryption
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        uid = str(uuid.uuid4())
        d = os.path.join(TMP_ROOT, uid)
        os.makedirs(d, exist_ok=True)
        out_path = os.path.join(d, "result.pdf")
        try:
            with open(out_path, "wb") as f:
                writer.write(f)
        except Exception as e:
            shutil.rmtree(d, ignore_errors=True)
            raise HTTPException(status_code=400, detail=f"Unlock failed: {e}")
        background_tasks.add_task(schedule_delete, out_path)
        return FileResponse(out_path, filename="unlocked.pdf", media_type="application/pdf")

    # is encrypted, try decrypt
    try:
        res = reader.decrypt(pwd)
        # pypdf decrypt returns 0 if failed, 1 or 2 if success (depending on user/owner)
        if res == 0:
            raise HTTPException(status_code=400, detail="Invalid password")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid password")

    # check still encrypted? Try to access pages
    try:
        num = len(reader.pages)
        if num == 0:
            raise HTTPException(status_code=400, detail="PDF has no pages")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid password")

    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    # preserve metadata if any
    if reader.metadata:
        try:
            writer.add_metadata({k: v for k, v in reader.metadata.items() if v is not None})
        except Exception:
            pass

    uid = str(uuid.uuid4())
    d = os.path.join(TMP_ROOT, uid)
    os.makedirs(d, exist_ok=True)
    out_path = os.path.join(d, "result.pdf")
    try:
        with open(out_path, "wb") as f:
            writer.write(f)
    except Exception as e:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Unlock failed: {e}")

    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Unlock produced empty file")

    background_tasks.add_task(schedule_delete, out_path)
    return FileResponse(out_path, filename="unlocked.pdf", media_type="application/pdf")
