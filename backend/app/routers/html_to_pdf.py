from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import os
import uuid
import shutil
import time
import asyncio
from typing import Optional

from ..config import TMP_ROOT, MAX_FILE_SIZE, RETENTION_SECONDS

router = APIRouter()

try:
    from weasyprint import HTML  # type: ignore
    HAS_WP = True
except Exception:
    HAS_WP = False
    HTML = None  # type: ignore

def schedule_delete(path: str):
    import threading
    def _del():
        time.sleep(RETENTION_SECONDS)
        d = os.path.dirname(path)
        if os.path.exists(d):
            shutil.rmtree(d, ignore_errors=True)
    threading.Thread(target=_del, daemon=True).start()

async def convert_html(html_str: str, out_path: str, base_url: Optional[str] = None):
    def _sync():
        if HAS_WP:
            HTML(string=html_str, base_url=base_url).write_pdf(out_path)  # type: ignore
        else:
            import fitz
            doc = fitz.open()
            page = doc.new_page()
            # Simple fallback: insert text, wrap manually via textbox?
            text = html_str[:3000] if html_str else ""
            try:
                page.insert_text((72, 72), text)
            except Exception:
                # fallback if insert_text fails, try textbox
                try:
                    rect = fitz.Rect(72, 72, 540, 770)
                    page.insert_textbox(rect, text, fontsize=9)
                except Exception:
                    pass
            doc.save(out_path)
            doc.close()
    await asyncio.to_thread(_sync)

@router.post("/api/html-to-pdf")
async def html_to_pdf(
    background_tasks: BackgroundTasks,
    html: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
    url: Optional[str] = Form(default=None),
):
    has_html = html is not None and html.strip() != ""
    has_file = file is not None
    has_url = url is not None and url.strip() != ""

    if not has_html and not has_file and not has_url:
        raise HTTPException(status_code=400, detail="Must provide one of html, file, or url")

    html_str: Optional[str] = None
    base_url: Optional[str] = None

    if has_url:
        # fetch via httpx 10s timeout
        import httpx
        target_url = url.strip()  # type: ignore
        base_url = target_url
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(target_url, follow_redirects=True)
                resp.raise_for_status()
                # Try to get text with detected encoding
                html_str = resp.text
                if html_str is None:
                    html_str = resp.content.decode("utf-8", errors="ignore")
                if len(html_str.encode("utf-8")) > MAX_FILE_SIZE:
                    raise HTTPException(status_code=413, detail="Fetched HTML too large")
                if not html_str or not html_str.strip():
                    raise HTTPException(status_code=400, detail="Fetched HTML is empty")
        except HTTPException:
            raise
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=422, detail=f"Failed to fetch URL: {e}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=422, detail=f"Failed to fetch URL: {e}")
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Failed to fetch URL: {e}")
    elif has_file:
        assert file is not None
        data = await file.read()
        if len(data) == 0:
            raise HTTPException(status_code=400, detail="Empty file")
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File too large")
        try:
            html_str = data.decode("utf-8")
        except UnicodeDecodeError:
            html_str = data.decode("utf-8", errors="ignore")
        if not html_str or not html_str.strip():
            raise HTTPException(status_code=400, detail="Empty HTML")
    else:
        # html string form field
        assert html is not None
        if len(html.encode("utf-8")) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="HTML too large")
        html_str = html
        if not html_str or not html_str.strip():
            raise HTTPException(status_code=400, detail="Empty HTML")

    # At this point html_str is set
    assert html_str is not None

    uid = str(uuid.uuid4())
    d = os.path.join(TMP_ROOT, uid)
    os.makedirs(d, exist_ok=True)
    out_path = os.path.join(d, "output.pdf")

    try:
        await convert_html(html_str, out_path, base_url=base_url)
    except HTTPException:
        shutil.rmtree(d, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=422, detail=f"HTML to PDF conversion failed: {e}")

    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=422, detail="Conversion produced empty file")

    background_tasks.add_task(schedule_delete, out_path)
    return FileResponse(out_path, filename="output.pdf", media_type="application/pdf")
