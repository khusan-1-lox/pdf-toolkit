import asyncio
import base64

import fitz
from fastapi import APIRouter, UploadFile, File, HTTPException

from ..config import MAX_FILE_SIZE

router = APIRouter()
MAX_COMPARE_PAGES = 100


def render_page(page):
    scale = min(1.0, 1600 / max(page.rect.width, page.rect.height))
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False, colorspace=fitz.csRGB)
    thumb = "data:image/jpeg;base64," + base64.b64encode(
        pix.tobytes("jpg", jpg_quality=60)
    ).decode()
    return page.get_text(), thumb, (pix.width, pix.height, pix.samples)


def compare_documents(data1, data2):
    try:
        with fitz.open(stream=data1, filetype="pdf") as left, fitz.open(stream=data2, filetype="pdf") as right:
            if left.needs_pass or right.needs_pass:
                raise HTTPException(400, "Encrypted PDF not supported")
            n1, n2 = len(left), len(right)
            if not n1 or not n2:
                raise HTTPException(400, "PDF has no pages")
            count = max(n1, n2)
            if count > MAX_COMPARE_PAGES:
                raise HTTPException(422, f"Compare supports up to {MAX_COMPARE_PAGES} pages per PDF. Split the document first.")
            pages = []
            for index in range(count):
                lt, lthumb, lpix = render_page(left[index]) if index < n1 else ("", "", None)
                rt, rthumb, rpix = render_page(right[index]) if index < n2 else ("", "", None)
                text_diff = lt.strip() != rt.strip()
                visual_diff = lpix != rpix
                size_diff = index < n1 and index < n2 and left[index].rect != right[index].rect
                pages.append({
                    "index": index, "diff": text_diff or visual_diff or size_diff,
                    "text_diff": text_diff, "visual_diff": visual_diff or size_diff,
                    "left_thumb": lthumb, "right_thumb": rthumb,
                    "left_text": lt[:5000] + ("…" if len(lt) > 5000 else ""),
                    "right_text": rt[:5000] + ("…" if len(rt) > 5000 else ""),
                    "text_truncated": len(lt) > 5000 or len(rt) > 5000,
                })
            return {"pages": pages, "leftPageCount": n1, "rightPageCount": n2,
                    "comparedPages": count, "visualComparison": "rendered-at-up-to-72dpi"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, f"Compare failed: {exc}") from exc


@router.post("/api/compare")
async def compare_pdfs(
    file1: UploadFile | None = File(default=None),
    file2: UploadFile | None = File(default=None),
    files: list[UploadFile] = File(default=[]),
):
    remaining = list(files or [])
    if file1 is None and remaining:
        file1 = remaining.pop(0)
    if file2 is None and remaining:
        file2 = remaining.pop(0)
    if file1 is None or file2 is None:
        raise HTTPException(400, "Two files required (file1 and file2)")
    data1, data2 = await file1.read(), await file2.read()
    if len(data1) > MAX_FILE_SIZE or len(data2) > MAX_FILE_SIZE:
        raise HTTPException(413, "File too large")
    if not data1 or not data2:
        raise HTTPException(400, "Empty file")
    return await asyncio.to_thread(compare_documents, data1, data2)
