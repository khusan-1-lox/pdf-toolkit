from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import uuid
import os
import shutil
import time
import json
try:
    from pypdf import PdfMerger
except ImportError:
    from pypdf import PdfWriter as PdfMerger  # pypdf 6.x fallback

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    PdfReader = None  # type: ignore
    PdfWriter = None  # type: ignore

from ..config import TMP_ROOT, MAX_FILE_SIZE, MAX_FILES, RETENTION_SECONDS

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


@router.post("/api/merge")
async def merge(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(default=[]),
    order: str | None = Form(default=None),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files")
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=413, detail="Too many files")

    # Parse order if provided
    order_parsed = None
    if order is not None and order.strip() != "":
        try:
            order_parsed = json.loads(order)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid order JSON")
        if not isinstance(order_parsed, list):
            raise HTTPException(status_code=400, detail="order must be a list")
        if len(order_parsed) == 0:
            raise HTTPException(status_code=400, detail="order must not be empty")
        for idx, entry in enumerate(order_parsed):
            if not isinstance(entry, dict):
                raise HTTPException(status_code=400, detail=f"order[{idx}] must be an object")
            if "file" not in entry or "page" not in entry:
                raise HTTPException(status_code=400, detail=f"order[{idx}] missing file/page")
            f_idx = entry["file"]
            p_idx = entry["page"]
            if not isinstance(f_idx, int) or not isinstance(p_idx, int):
                raise HTTPException(status_code=400, detail=f"order[{idx}].file/page must be integers")
            if f_idx < 0 or f_idx >= len(files):
                raise HTTPException(status_code=400, detail=f"order[{idx}].file out of range")
            if p_idx < 0:
                raise HTTPException(status_code=400, detail=f"order[{idx}].page out of range")

    uid = str(uuid.uuid4())
    d = os.path.join(TMP_ROOT, uid)
    os.makedirs(d, exist_ok=True)

    saved_paths: list[str] = []

    # Save files and validate size
    try:
        for f in files:
            data = await f.read()
            if len(data) > MAX_FILE_SIZE:
                raise HTTPException(status_code=413, detail="File too large")
            safe_name = os.path.basename(f.filename) if f.filename else "in.pdf"
            p = os.path.join(d, safe_name)
            if os.path.exists(p):
                base, ext = os.path.splitext(safe_name)
                p = os.path.join(d, f"{base}_{uuid.uuid4().hex[:6]}{ext}")
            with open(p, "wb") as out_f:
                out_f.write(data)
            saved_paths.append(p)
    except HTTPException:
        shutil.rmtree(d, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Invalid PDF: {e}")

    # Validate PDFs are readable via PdfReader for order validation early
    # and also perform merge
    out = os.path.join(d, "result.pdf")

    if order_parsed is not None:
        # Ordered merge via PdfReader/PdfWriter page-by-page
        if PdfReader is None or PdfWriter is None:
            shutil.rmtree(d, ignore_errors=True)
            raise HTTPException(status_code=500, detail="PDF library not available")
        try:
            readers: list = []
            for p in saved_paths:
                try:
                    readers.append(PdfReader(p))
                except Exception:
                    raise HTTPException(status_code=400, detail="Invalid PDF")

            # Validate page indices against actual reader lengths
            for idx, entry in enumerate(order_parsed):
                f_idx = entry["file"]
                p_idx = entry["page"]
                reader = readers[f_idx]
                num = len(reader.pages)
                if p_idx >= num:
                    raise HTTPException(
                        status_code=400,
                        detail=f"order[{idx}].page out of range (file {f_idx} has {num} pages)",
                    )

            writer = PdfWriter()
            for entry in order_parsed:
                f_idx = entry["file"]
                p_idx = entry["page"]
                writer.add_page(readers[f_idx].pages[p_idx])

            # Handle pypdf 6 write API
            with open(out, "wb") as out_f:
                writer.write(out_f)

        except HTTPException:
            shutil.rmtree(d, ignore_errors=True)
            raise
        except Exception as e:
            shutil.rmtree(d, ignore_errors=True)
            raise HTTPException(status_code=400, detail=f"Invalid PDF: {e}")
    else:
        # Backward compat: append whole files via PdfMerger
        merger = PdfMerger()
        try:
            for p in saved_paths:
                try:
                    merger.append(p)
                except Exception:
                    merger.close()
                    raise HTTPException(status_code=400, detail="Invalid PDF")
            merger.write(out)
            merger.close()
        except HTTPException:
            try:
                merger.close()
            except Exception:
                pass
            shutil.rmtree(d, ignore_errors=True)
            raise
        except Exception as e:
            try:
                merger.close()
            except Exception:
                pass
            shutil.rmtree(d, ignore_errors=True)
            raise HTTPException(status_code=400, detail=f"Invalid PDF: {e}")

    background_tasks.add_task(schedule_delete, out)
    return FileResponse(out, filename="merged.pdf", media_type="application/pdf")
