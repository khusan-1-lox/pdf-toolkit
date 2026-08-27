from fastapi import APIRouter, UploadFile, File, HTTPException, Request
import base64

from ..config import MAX_FILE_SIZE

router = APIRouter()

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

def thumb_b64(page):
    try:
        mat = page.get_pixmap(matrix=page.parent._get_matrix(0.4,0.4))  # nonsense
    except Exception:
        pass
    try:
        import pymupdf as fitz
        mat = fitz.Matrix(0.5, 0.5)
    except ImportError:
        try:
            import fitz as fitz2
            mat = fitz2.Matrix(0.5,0.5)
        except Exception:
            mat = None
    try:
        if mat is not None:
            pix = page.get_pixmap(matrix=mat, alpha=False)
        else:
            pix = page.get_pixmap(alpha=False)
    except Exception:
        pix = page.get_pixmap(alpha=False)
    try:
        jpg_bytes = pix.tobytes("jpg", jpg_quality=60)
        return "data:image/jpeg;base64," + base64.b64encode(jpg_bytes).decode()
    except Exception:
        try:
            png_bytes = pix.tobytes("png")
            return "data:image/png;base64," + base64.b64encode(png_bytes).decode()
        except Exception:
            return ""

@router.post("/api/compare")
async def compare_pdfs(
    request: Request,
    file1: UploadFile | None = File(default=None),
    file2: UploadFile | None = File(default=None),
    files: list[UploadFile] | None = File(default=None),
):
    # handle alternative: client sends two files as "files" with 2 entries, or as file1/file2
    # prioritize file1/file2, else use files
    f1 = file1
    f2 = file2
    if (f1 is None or f2 is None) and files is not None:
        # files may contain 2 entries
        if files and len(files) >= 2:
            if f1 is None:
                f1 = files[0]
            if f2 is None:
                # if files has 2, second is f2; if more, pick second where not same as first
                # handle case where f1 already set from file1 param, then files contains file2
                if file1 is not None and len(files) >=1:
                    f2 = files[0]
                else:
                    f2 = files[1]
        elif files and len(files)==1:
            # check if one of file1/file2 already set and files provides the other
            if f1 is None:
                f1 = files[0]
            elif f2 is None:
                f2 = files[0]

    # also handle reading form manually for file1/file2 if not parsed due to naming
    if f1 is None or f2 is None:
        try:
            form = await request.form()
            # form may contain UploadFile under keys file1, file2, files
            # need to inspect form values that are UploadFile
            # but request.form already parsed? We attempt fallback
            for key in ("file1","file2"):
                if key in form:
                    val = form[key]
                    # val may be starlette.datastructures.UploadFile
                    if hasattr(val, "read"):
                        if key=="file1" and f1 is None:
                            f1 = val  # type: ignore
                        if key=="file2" and f2 is None:
                            f2 = val  # type: ignore
            # also handle "files" list
            if "files" in form:
                # form.getlist ?
                try:
                    file_list = form.getlist("files")  # type: ignore
                    if file_list:
                        if f1 is None and len(file_list)>=1:
                            f1 = file_list[0]  # type: ignore
                        if f2 is None and len(file_list)>=2:
                            f2 = file_list[1]  # type: ignore
                        elif f2 is None and len(file_list)==1 and f1 is not None:
                            # need second file elsewhere? keep
                            pass
                except Exception:
                    pass
        except Exception:
            pass

    if f1 is None or f2 is None:
        raise HTTPException(status_code=400, detail="Two files required (file1 and file2)")

    # read both
    data1 = await f1.read()
    data2 = await f2.read()

    if len(data1) > MAX_FILE_SIZE or len(data2) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")
    if len(data1)==0 or len(data2)==0:
        raise HTTPException(status_code=400, detail="Empty file")

    fitz = get_fitz()
    if fitz is None:
        raise HTTPException(status_code=500, detail="PyMuPDF not available")

    try:
        doc1 = fitz.open(stream=data1, filetype="pdf")
    except Exception as e:
        msg = str(e).lower()
        if "password" in msg or "encrypt" in msg:
            raise HTTPException(status_code=400, detail="Encrypted PDF not supported")
        raise HTTPException(status_code=400, detail="Invalid PDF (file1)")
    try:
        doc2 = fitz.open(stream=data2, filetype="pdf")
    except Exception as e:
        msg = str(e).lower()
        try:
            doc1.close()
        except Exception:
            pass
        if "password" in msg or "encrypt" in msg:
            raise HTTPException(status_code=400, detail="Encrypted PDF not supported")
        raise HTTPException(status_code=400, detail="Invalid PDF (file2)")

    try:
        n1 = len(doc1)
        n2 = len(doc2)
        if n1==0 or n2==0:
            raise HTTPException(status_code=400, detail="PDF has no pages")
        n = max(n1, n2)
        # limit to 20 pages to avoid huge response
        max_pages = 20
        if n > max_pages:
            n = max_pages

        pages = []
        # prepare matrix once
        try:
            import pymupdf as fitz_mod
            mat = fitz_mod.Matrix(0.5, 0.5)
        except ImportError:
            try:
                import fitz as fitz_mod
                mat = fitz_mod.Matrix(0.5, 0.5)
            except Exception:
                mat = None

        for idx in range(n):
            left_text = ""
            right_text = ""
            left_thumb = ""
            right_thumb = ""
            diff = False

            if idx < n1:
                p1 = doc1.load_page(idx)
                try:
                    left_text = p1.get_text() or ""
                except Exception:
                    left_text = ""
                # thumb
                try:
                    if mat is not None:
                        pix = p1.get_pixmap(matrix=mat, alpha=False)
                    else:
                        pix = p1.get_pixmap(alpha=False)
                    try:
                        jpg = pix.tobytes("jpg", jpg_quality=55)
                        left_thumb = "data:image/jpeg;base64," + base64.b64encode(jpg).decode()
                    except Exception:
                        png = pix.tobytes("png")
                        left_thumb = "data:image/png;base64," + base64.b64encode(png).decode()
                except Exception:
                    left_thumb = ""
            else:
                left_text = ""
                left_thumb = ""
                diff = True

            if idx < n2:
                p2 = doc2.load_page(idx)
                try:
                    right_text = p2.get_text() or ""
                except Exception:
                    right_text = ""
                try:
                    if mat is not None:
                        pix = p2.get_pixmap(matrix=mat, alpha=False)
                    else:
                        pix = p2.get_pixmap(alpha=False)
                    try:
                        jpg = pix.tobytes("jpg", jpg_quality=55)
                        right_thumb = "data:image/jpeg;base64," + base64.b64encode(jpg).decode()
                    except Exception:
                        png = pix.tobytes("png")
                        right_thumb = "data:image/png;base64," + base64.b64encode(png).decode()
                except Exception:
                    right_thumb = ""
            else:
                right_text = ""
                right_thumb = ""
                diff = True

            if not diff:
                # compare texts stripped
                lt = left_text.strip()
                rt = right_text.strip()
                diff = lt != rt

            # trim texts for JSON size: limit 5000 chars per text
            if len(left_text) > 5000:
                left_text = left_text[:5000] + "…"
            if len(right_text) > 5000:
                right_text = right_text[:5000] + "…"

            pages.append({
                "index": idx,
                "diff": diff,
                "left_thumb": left_thumb,
                "right_thumb": right_thumb,
                "left_text": left_text,
                "right_text": right_text,
            })

        doc1.close()
        doc2.close()
        return {"pages": pages}
    except HTTPException:
        try:
            doc1.close()
        except Exception:
            pass
        try:
            doc2.close()
        except Exception:
            pass
        raise
    except Exception as e:
        try:
            doc1.close()
        except Exception:
            pass
        try:
            doc2.close()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=f"Compare failed: {e}")
