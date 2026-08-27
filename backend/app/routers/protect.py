from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Request
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

def to_bool(v):
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("true","1","yes","on"):
        return True
    if s in ("false","0","no","off"):
        return False
    return None

@router.post("/api/protect")
async def protect_pdf(
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
    user_password: str | None = Form(default=None),
    owner_password: str | None = Form(default=None),
):
    # validate password
    if user_password is None or str(user_password).strip() == "":
        raise HTTPException(status_code=400, detail="user_password required")
    user_pwd = str(user_password)
    owner_pwd = str(owner_password) if owner_password is not None and str(owner_password).strip() != "" else None

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    # collect permission booleans from form (flexible names)
    try:
        form = await request.form()
    except Exception:
        form = {}

    # permission keys mapping to UserAccessPermissions bits
    # support both allow_* and direct names
    perm_map = {
        "print": "print",
        "print_high": "print_high",
        "modify": "modify",
        "copy": "copy",
        "annotate": "annotate",
        "fill_forms": "fill_forms",
        "fill-forms": "fill_forms",
        "extract": "extract",
        "assemble": "assemble",
        "allow_print": "print",
        "allow_copy": "copy",
        "allow_modify": "modify",
        "allow_annotate": "annotate",
        "allow_fill": "fill_forms",
        "allow_fill_forms": "fill_forms",
        "allow_extract": "extract",
        "allow_assemble": "assemble",
        "permissions_print": "print",
        "permissions_copy": "copy",
    }

    # default = True for all
    perms = {
        "print": True,
        "modify": True,
        "copy": True,
        "annotate": True,
        "fill_forms": True,
        "extract": True,
        "assemble": True,
    }

    # also handle generic "permissions" json field
    # if provided as JSON string like {"print": false}
    if "permissions" in form:
        try:
            import json
            raw = form["permissions"]
            if isinstance(raw, (bytes,)):
                raw = raw.decode()
            parsed = json.loads(str(raw))
            if isinstance(parsed, dict):
                for k,v in parsed.items():
                    kk = str(k).lower()
                    if kk in ("print","copy","modify","annotate","extract","assemble","fill_forms","fill-forms"):
                        nk = "fill_forms" if kk in ("fill-forms",) else kk
                        # direct mapping
                        b = to_bool(v)
                        if b is not None:
                            if nk == "copy":
                                perms["copy"] = b
                                perms["extract"] = b
                            else:
                                perms[nk] = b
        except Exception:
            pass

    for key, raw_val in form.items():
        lk = str(key).lower()
        if lk in perm_map:
            b = to_bool(raw_val)
            if b is not None:
                target = perm_map[lk]
                if target == "copy":
                    perms["copy"] = b
                    perms["extract"] = b
                else:
                    perms[target] = b
        # also handle keys like "permissions[print]" variant?
        # search for print etc inside
        # if key starts with "permission"
        if lk.startswith("permission"):
            # e.g. permissions_print
            continue

    # build permissions_flag
    try:
        from pypdf.constants import UserAccessPermissions
        from pypdf._writer import ALL_DOCUMENT_PERMISSIONS
    except ImportError:
        from pypdf.generic import UserAccessPermissions  # type: ignore
        ALL_DOCUMENT_PERMISSIONS = UserAccessPermissions.PRINT | UserAccessPermissions.MODIFY | UserAccessPermissions.EXTRACT | UserAccessPermissions.ADD_OR_MODIFY | UserAccessPermissions.FILL_FORM_FIELDS | UserAccessPermissions.EXTRACT_TEXT_AND_GRAPHICS | UserAccessPermissions.ASSEMBLE_DOC | UserAccessPermissions.PRINT_TO_REPRESENTATION  # fallback

    # start with ALL, then clear bits if false
    permissions_flag = ALL_DOCUMENT_PERMISSIONS
    # We need to clear bits where perm false
    # Map perm name -> bits
    # print -> PRINT (4) + PRINT_TO_REPRESENTATION (2048)
    # modify -> MODIFY (8)
    # copy -> EXTRACT (16) + EXTRACT_TEXT_AND_GRAPHICS (512)
    # annotate -> ADD_OR_MODIFY (32)
    # fill_forms -> FILL_FORM_FIELDS (256)
    # extract -> EXTRACT_TEXT_AND_GRAPHICS (512)
    # assemble -> ASSEMBLE_DOC (1024)
    bit_map = {
        "print": [UserAccessPermissions.PRINT, UserAccessPermissions.PRINT_TO_REPRESENTATION],
        "modify": [UserAccessPermissions.MODIFY],
        "copy": [UserAccessPermissions.EXTRACT, UserAccessPermissions.EXTRACT_TEXT_AND_GRAPHICS],
        "annotate": [UserAccessPermissions.ADD_OR_MODIFY],
        "fill_forms": [UserAccessPermissions.FILL_FORM_FIELDS],
        "extract": [UserAccessPermissions.EXTRACT_TEXT_AND_GRAPHICS],
        "assemble": [UserAccessPermissions.ASSEMBLE_DOC],
    }
    for perm_name, allowed in perms.items():
        if not allowed:
            bits = bit_map.get(perm_name, [])
            for b in bits:
                try:
                    permissions_flag = permissions_flag & ~b
                except Exception:
                    permissions_flag = int(permissions_flag) & ~int(b)

    # validate PDF via pypdf and fitz
    # check encrypted?
    # Try pypdf reader first to validate
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        raise HTTPException(status_code=500, detail="pypdf not available")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise HTTPException(status_code=400, detail="Encrypted PDF not supported")
        if len(reader.pages) == 0:
            raise HTTPException(status_code=400, detail="PDF has no pages")
    except HTTPException:
        raise
    except Exception as e:
        msg = str(e).lower()
        if "password" in msg or "encrypt" in msg:
            raise HTTPException(status_code=400, detail="Encrypted PDF not supported")
        raise HTTPException(status_code=400, detail="Invalid PDF")

    # Create writer and encrypt
    try:
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        # keep metadata if any
        if reader.metadata:
            try:
                writer.add_metadata({k: v for k, v in reader.metadata.items() if v is not None})
            except Exception:
                pass
        # encrypt signature: encrypt(user_pwd, owner_pwd, use_128bit=True, permissions_flag=...)
        if owner_pwd is not None:
            writer.encrypt(user_pwd, owner_pwd, use_128bit=True, permissions_flag=permissions_flag)
        else:
            writer.encrypt(user_pwd, use_128bit=True, permissions_flag=permissions_flag)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Encrypt failed: {e}")

    uid = str(uuid.uuid4())
    d = os.path.join(TMP_ROOT, uid)
    os.makedirs(d, exist_ok=True)
    out_path = os.path.join(d, "result.pdf")
    try:
        with open(out_path, "wb") as f:
            writer.write(f)
    except Exception as e:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Write failed: {e}")

    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Protect produced empty file")

    background_tasks.add_task(schedule_delete, out_path)
    return FileResponse(out_path, filename="protected.pdf", media_type="application/pdf")
