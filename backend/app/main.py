from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import os
import time
import shutil
import threading
import logging
import json

from .config import TMP_ROOT, RETENTION_SECONDS
from .routers.merge import router as merge_router
from .routers.split import router as split_router
from .routers.delete import router as delete_router
from .routers.rotate import router as rotate_router
from .routers.compress import router as compress_router
from .routers.pdf_to_jpg import router as pdf_to_jpg_router
from .routers.jpg_to_pdf import router as jpg_to_pdf_router
from .routers.preview import router as preview_router
from .routers.watermark import router as watermark_router
from .routers.page_numbers import router as page_numbers_router
from .routers.crop import router as crop_router
from .routers.protect import router as protect_router
from .routers.unlock import router as unlock_router
from .routers.redact import router as redact_router
from .routers.sign import router as sign_router
from .routers.compare import router as compare_router
from .routers.word_to_pdf import router as word_to_pdf_router
from .routers.excel_to_pdf import router as excel_to_pdf_router
from .routers.ppt_to_pdf import router as ppt_to_pdf_router
from .routers.pdf_to_word import router as pdf_to_word_router
from .routers.pdf_to_excel import router as pdf_to_excel_router
from .routers.pdf_to_ppt import router as pdf_to_ppt_router
from .routers.ocr import router as ocr_router
from .routers.pdfa import router as pdfa_router
from .routers.html_to_pdf import router as html_to_pdf_router
from .routers.repair import router as repair_router
from .routers.advanced import router as advanced_router

# Security: mask passwords in logs
class PasswordMaskingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = record.msg.replace(record.msg, self._mask_passwords(record.msg))
        if hasattr(record, 'args') and record.args:
            record.args = tuple(
                self._mask_passwords(str(arg)) if isinstance(arg, str) else arg
                for arg in record.args
            )
        return True

    def _mask_passwords(self, text: str) -> str:
        import re
        # Mask password=... in URLs and form data
        text = re.sub(r'(password=)[^&\s]+', r'\1***MASKED***', text, flags=re.IGNORECASE)
        text = re.sub(r'(pwd=)[^&\s]+', r'\1***MASKED***', text, flags=re.IGNORECASE)
        return text

# Apply filter to uvicorn access logger
logging.getLogger("uvicorn.access").addFilter(PasswordMaskingFilter())

app = FastAPI(title="PDF Toolkit API")

# Security middleware
allowed_hosts = ["your-domain.com", "*.your-domain.com", "localhost", "127.0.0.1", "testserver"]
if os.getenv("PYTEST_CURRENT_TEST") and "testserver" not in allowed_hosts:
    allowed_hosts.append("testserver")

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=allowed_hosts
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-domain.com", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

os.makedirs(TMP_ROOT, exist_ok=True)
app.include_router(merge_router)
app.include_router(split_router)
app.include_router(delete_router)
app.include_router(rotate_router)
app.include_router(compress_router)
app.include_router(pdf_to_jpg_router)
app.include_router(jpg_to_pdf_router)
app.include_router(preview_router)
app.include_router(watermark_router)
app.include_router(page_numbers_router)
app.include_router(crop_router)
app.include_router(protect_router)
app.include_router(unlock_router)
app.include_router(redact_router)
app.include_router(sign_router)
app.include_router(compare_router)
app.include_router(word_to_pdf_router)
app.include_router(excel_to_pdf_router)
app.include_router(ppt_to_pdf_router)
app.include_router(pdf_to_word_router)
app.include_router(pdf_to_excel_router)
app.include_router(pdf_to_ppt_router)
app.include_router(ocr_router)
app.include_router(pdfa_router)
app.include_router(html_to_pdf_router)
app.include_router(repair_router)
app.include_router(advanced_router)


@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok"}


# --- Fallback cleaner: every 600s delete folders older than 300s ---
# Each router already schedules per-file deletion via schedule_delete (threading.Timer 300s).
# This fallback handles edge cases: server restart, lost thread, download not triggered, etc.
def _fallback_cleaner():
    while True:
        time.sleep(600)
        try:
            if not os.path.exists(TMP_ROOT):
                continue
            now = time.time()
            for entry in os.listdir(TMP_ROOT):
                p = os.path.join(TMP_ROOT, entry)
                # Only handle directories (each request is a UUID dir)
                if not os.path.isdir(p):
                    continue
                try:
                    mtime = os.path.getmtime(p)
                except OSError:
                    continue
                age = now - mtime
                if age > RETENTION_SECONDS:
                    shutil.rmtree(p, ignore_errors=True)
        except Exception:
            # Never crash the daemon thread
            continue


threading.Thread(target=_fallback_cleaner, daemon=True).start()
