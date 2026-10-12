import asyncio
import base64

import fitz
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..config import MAX_FILE_SIZE

router = APIRouter()


def render_preview(data: bytes, offset: int, limit: int):
    try:
        with fitz.open(stream=data, filetype="pdf") as doc:
            if doc.needs_pass:
                raise HTTPException(400, "Encrypted PDF not supported")
            count = len(doc)
            if not count:
                raise HTTPException(400, "PDF has no pages")
            pages = []
            for index in range(offset, min(offset + limit, count)):
                page = doc[index]
                scale = min(0.4, 500 / max(page.rect.width, page.rect.height))
                pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                encoded = base64.b64encode(pix.tobytes("jpg", jpg_quality=65)).decode()
                pages.append({"page": index, "thumb": "data:image/jpeg;base64," + encoded,
                              "width": page.rect.width, "height": page.rect.height})
            return {"pages": pages, "numPages": count, "offset": offset,
                    "hasMore": offset + len(pages) < count}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, f"Invalid PDF: {exc}") from exc


@router.post("/api/preview")
async def preview(
    file: UploadFile = File(...),
    offset: int = Form(default=0, ge=0),
    limit: int = Form(default=50, ge=1, le=50),
):
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(413, "File too large")
    if not data:
        raise HTTPException(400, "Empty file")
    return await asyncio.to_thread(render_preview, data, offset, limit)
