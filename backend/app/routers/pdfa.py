import asyncio
import os
import shutil
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET

import fitz
from PIL import ImageCms
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

from ..config import TMP_ROOT, MAX_FILE_SIZE, RETENTION_SECONDS

router = APIRouter()


def schedule_delete(path: str):
    import threading

    def delete():
        time.sleep(RETENTION_SECONDS)
        shutil.rmtree(os.path.dirname(path), ignore_errors=True)

    threading.Thread(target=delete, daemon=True).start()


def validate_pdfa_metadata(out_path):
    # A structural check, not a replacement for an ISO validator such as veraPDF.
    with fitz.open(out_path) as doc:
        if not len(doc) or doc.needs_pass:
            raise ValueError("PDF/A output is empty or encrypted")
        root = ET.fromstring(doc.get_xml_metadata())
        namespace = "{http://www.aiim.org/pdfa/ns/id/}"
        values = {}
        for node in root.iter():
            values.update(node.attrib)
            if node.text:
                values[node.tag] = node.text.strip()
        if values.get(namespace + "part") != "2" or values.get(namespace + "conformance") != "B":
            raise ValueError("Converter did not produce PDF/A-2b identification")
        if doc.xref_get_key(doc.pdf_catalog(), "OutputIntents")[0] == "null":
            raise ValueError("PDF/A output is missing its ICC output intent")


async def convert_to_pdfa(in_path, out_path):
    def convert():
        with fitz.open(in_path) as source:
            if source.needs_pass:
                raise HTTPException(400, "Encrypted PDF not supported")
            if not len(source):
                raise HTTPException(400, "PDF has no pages")
        gs = shutil.which("gs") or shutil.which("gswin64c") or shutil.which("gswin32c")
        if not gs:
            raise HTTPException(503, "PDF/A conversion requires Ghostscript on the server (gs or gswin64c in PATH)")
        directory = os.path.dirname(out_path)
        profile_path = os.path.abspath(os.path.join(directory, "srgb.icc"))
        with open(profile_path, "wb") as profile:
            profile.write(ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes())
        # PostScript strings must escape parentheses and backslashes in paths.
        escaped_profile = profile_path.replace("\\", "/").replace("(", "\\(").replace(")", "\\)")
        definition = os.path.join(directory, "pdfa.ps")
        with open(definition, "w", encoding="ascii") as output:
            output.write(
                "%!PS-Adobe-3.0\n"
                "[/_objdef {icc_PDFA} /type /stream /OBJ pdfmark\n"
                "[{icc_PDFA} << /N 3 >> /PUT pdfmark\n"
                f"[{{icc_PDFA}} ({escaped_profile}) (r) file /PUT pdfmark\n"
                "[/_objdef {OutputIntent_PDFA} /type /dict /OBJ pdfmark\n"
                "[{OutputIntent_PDFA} << /Type /OutputIntent /S /GTS_PDFA1 "
                "/DestOutputProfile {icc_PDFA} /OutputConditionIdentifier (sRGB) "
                "/Info (sRGB IEC61966-2.1) >> /PUT pdfmark\n"
                "[{Catalog} << /OutputIntents [ {OutputIntent_PDFA} ] >> /PUT pdfmark\n"
            )
        completed = subprocess.run(
            [gs, "-dSAFER", "-dBATCH", "-dNOPAUSE", "-dPDFA=2",
             "-dPDFACompatibilityPolicy=2", "-sDEVICE=pdfwrite",
             "-sColorConversionStrategy=RGB", "-sProcessColorModel=DeviceRGB",
             "-dEmbedAllFonts=true",
             f"--permit-file-read={profile_path}",
             f"-sOutputFile={out_path}", definition, in_path],
            timeout=120, check=False, capture_output=True,
        )
        if completed.returncode:
            raise ValueError("Ghostscript could not create compliant PDF/A-2b from this document")
        validate_pdfa_metadata(out_path)

    await asyncio.to_thread(convert)


async def _handle_pdfa(file: UploadFile, background_tasks: BackgroundTasks):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only .pdf allowed")
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file")
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(413, "File too large")
    directory = os.path.join(TMP_ROOT, str(uuid.uuid4()))
    os.makedirs(directory, exist_ok=True)
    in_path, out_path = os.path.join(directory, "in.pdf"), os.path.join(directory, "pdfa.pdf")
    with open(in_path, "wb") as output:
        output.write(data)
    try:
        await convert_to_pdfa(in_path, out_path)
    except HTTPException:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(directory, ignore_errors=True)
        raise HTTPException(422, f"PDF/A conversion failed: {exc}") from exc
    background_tasks.add_task(schedule_delete, out_path)
    return FileResponse(
        out_path, filename="pdfa.pdf", media_type="application/pdf",
        headers={"X-PDF-A": "true", "X-PDF-A-Profile": "PDF/A-2b",
                 "X-PDF-A-Validation": "metadata-and-output-intent"},
    )


@router.post("/api/pdf-to-pdfa")
@router.post("/api/pdfa")
async def pdf_to_pdfa(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    return await _handle_pdfa(file, background_tasks)
