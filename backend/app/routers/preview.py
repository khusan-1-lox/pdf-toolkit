from fastapi import APIRouter, UploadFile, File, HTTPException
import base64

from ..config import MAX_FILE_SIZE

router = APIRouter()


@router.post("/api/preview")
async def preview(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    # basic PDF magic check - allow but will fail gracefully
    # If not PDF, return 400
    # Use PyMuPDF to render thumbnails
    try:
        import pymupdf as fitz  # type: ignore
    except ImportError:
        try:
            import fitz  # type: ignore  # PyMuPDF alias (deprecated)
        except ImportError:
            fitz = None  # type: ignore

    if fitz is None:
        # fallback: no renderer available -> return empty pages (frontend will show placeholders)
        return {"pages": [], "numPages": 0}

    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:
        msg = str(e).lower()
        if "password" in msg or "encrypt" in msg:
            raise HTTPException(status_code=400, detail="Encrypted PDF not supported")
        raise HTTPException(status_code=400, detail=f"Invalid PDF: {e}")

    try:
        n = len(doc)
        if n == 0:
            doc.close()
            raise HTTPException(status_code=400, detail="PDF has no pages")
        # limit pages to avoid DoS - max 50 pages for preview
        max_preview = 50
        if n > max_preview:
            # still return first 50; frontend handles pagination if needed
            n_render = max_preview
        else:
            n_render = n

        pages = []
        mat = fitz.Matrix(0.4, 0.4)
        for i in range(n_render):
            page = doc.load_page(i)
            try:
                pix = page.get_pixmap(matrix=mat, alpha=False)
            except Exception:
                # fallback try without matrix
                pix = page.get_pixmap(alpha=False)
            # try JPEG first (smaller), fallback to PNG
            thumb_b64 = None
            try:
                # tobytes("jpg", jpg_quality=60) is valid for recent pymupdf
                jpg_bytes = pix.tobytes("jpg", jpg_quality=60)
                thumb_b64 = "data:image/jpeg;base64," + base64.b64encode(jpg_bytes).decode()
            except Exception:
                try:
                    png_bytes = pix.tobytes("png")
                    thumb_b64 = "data:image/png;base64," + base64.b64encode(png_bytes).decode()
                except Exception:
                    # last resort: use samples -> PNG via Pillow if available
                    thumb_b64 = None
            if thumb_b64:
                pages.append({"page": i, "thumb": thumb_b64})
            else:
                pages.append({"page": i, "thumb": ""})

        doc.close()
        return {"pages": pages, "numPages": n}
    except HTTPException:
        raise
    except Exception as e:
        try:
            doc.close()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=f"Preview failed: {e}")
