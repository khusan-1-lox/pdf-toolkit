#!/usr/bin/env python3
"""
PDF Toolkit MCP Server — local stdio, no auth, no billing.

Exposes 26 PDF tools as MCP tools for AI agents (Claude Desktop, Cursor, OpenCode).
All files stay local; no upload to cloud. Reuses backend logic where possible.
"""
import os
import io
import json
import uuid
import shutil
import zipfile
import tempfile
from pathlib import Path
from typing import Optional, List, Literal
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP

# Initialize MCP server — must be {service}_mcp format
mcp = FastMCP("pdf_toolkit_mcp")

# --- Shared helpers ---
def _ensure_exists(p: str) -> str:
    if not os.path.exists(p):
        raise FileNotFoundError(f"File not found: {p}")
    return p

def _out_path(input_path: str, suffix: str, ext: str = ".pdf") -> str:
    base = os.path.splitext(os.path.basename(input_path))[0]
    # Put output next to input to keep it discoverable
    out = os.path.join(os.path.dirname(os.path.abspath(input_path)), f"{base}{suffix}{ext}")
    # Avoid overwrite
    if os.path.exists(out):
        out = os.path.join(os.path.dirname(out), f"{base}{suffix}_{uuid.uuid4().hex[:6]}{ext}")
    return out

def _handle_error(e: Exception) -> str:
    if isinstance(e, FileNotFoundError):
        return f"Error: {e}"
    if isinstance(e, ValueError):
        return f"Error: {e}"
    return f"Error: {type(e).__name__}: {e}"

# ============ Pydantic Inputs ============
class MergeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    input_files: List[str] = Field(..., description="List of PDF file paths to merge (2-10 files), e.g. ['/tmp/a.pdf','/tmp/b.pdf']", min_length=2, max_length=10)
    output_file: Optional[str] = Field(default=None, description="Optional output path. If not set, creates merged.pdf next to first input")

class SplitInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    input_file: str = Field(..., description="PDF file path to split", min_length=1)
    pages: str = Field(..., description="Pages to extract, e.g. '1,3-5' or '1' (1-indexed)", min_length=1)

class CompressInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    input_file: str = Field(..., description="PDF file path", min_length=1)
    quality: Literal["low", "medium", "high"] = Field(default="medium", description="Compression level: low/medium/high")
    output_file: Optional[str] = Field(default=None, description="Optional output path")

class RotateInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    input_file: str = Field(..., description="PDF file path", min_length=1)
    angle: Literal[90, 180, 270] = Field(..., description="Rotation angle in degrees")
    pages: Optional[str] = Field(default=None, description="Pages to rotate, e.g. '1,3-5' or 'all'. Default all")
    output_file: Optional[str] = Field(default=None, description="Optional output path")

class DeleteInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    input_file: str = Field(..., description="PDF file path", min_length=1)
    pages: str = Field(..., description="Pages to delete, e.g. '2' or '2,4-5'", min_length=1)
    output_file: Optional[str] = Field(default=None, description="Optional output path")

class WatermarkInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    input_file: str = Field(..., description="PDF file path", min_length=1)
    text: Optional[str] = Field(default=None, description="Watermark text (e.g. 'CONFIDENTIAL')")
    image_file: Optional[str] = Field(default=None, description="Optional PNG image path for watermark")
    opacity: float = Field(default=0.3, description="Opacity 0.1-1.0", ge=0.1, le=1.0)
    position: str = Field(default="center", description="Position: center, top-left, top-right, bottom-left, bottom-right")
    output_file: Optional[str] = Field(default=None, description="Optional output path")

class PdfToJpgInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    input_file: str = Field(..., description="PDF file path", min_length=1)
    dpi: int = Field(default=150, description="DPI for rendering", ge=72, le=300)

class JpgToPdfInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    input_files: List[str] = Field(..., description="Image paths (JPG/PNG) to convert to PDF", min_length=1)
    output_file: Optional[str] = Field(default=None, description="Optional output path")

class WordToPdfInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    input_file: str = Field(..., description="DOCX/DOC path", min_length=1)
    output_file: Optional[str] = Field(default=None, description="Optional output path")

class PdfToWordInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    input_file: str = Field(..., description="PDF file path", min_length=1)
    output_file: Optional[str] = Field(default=None, description="Optional DOCX output path")

class PdfToExcelInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    input_file: str = Field(..., description="PDF file path", min_length=1)
    output_file: Optional[str] = Field(default=None, description="Optional XLSX output path")

class PdfToPptInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    input_file: str = Field(..., description="PDF file path", min_length=1)
    output_file: Optional[str] = Field(default=None, description="Optional PPTX output path")

class ExcelToPdfInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    input_file: str = Field(..., description="XLSX/XLS path", min_length=1)
    output_file: Optional[str] = Field(default=None, description="Optional output path")

class PptToPdfInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    input_file: str = Field(..., description="PPTX/PPT path", min_length=1)
    output_file: Optional[str] = Field(default=None, description="Optional output path")

class OcrInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    input_file: str = Field(..., description="Scanned PDF path", min_length=1)
    lang: str = Field(default="eng+rus", description="Tesseract lang, e.g. eng, rus, eng+rus")
    output_file: Optional[str] = Field(default=None, description="Optional output path")

class ProtectInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    input_file: str = Field(..., description="PDF path", min_length=1)
    password: str = Field(..., description="Password to encrypt with", min_length=1)
    output_file: Optional[str] = Field(default=None, description="Optional output path")

class UnlockInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    input_file: str = Field(..., description="Encrypted PDF path", min_length=1)
    password: str = Field(..., description="Password to decrypt", min_length=1)
    output_file: Optional[str] = Field(default=None, description="Optional output path")

# ============ Tools ============

@mcp.tool(name="pdf_merge", annotations={"title": "Merge PDFs", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def pdf_merge(params: MergeInput) -> str:
    """Merge multiple PDFs into one. Preserves order. Returns output path and page count."""
    try:
        for p in params.input_files:
            _ensure_exists(p)
        out = params.output_file or _out_path(params.input_files[0], "_merged")
        from pypdf import PdfMerger
        merger = PdfMerger()
        for p in params.input_files:
            merger.append(p)
        merger.write(out)
        merger.close()
        from pypdf import PdfReader
        pages = len(PdfReader(out).pages)
        return json.dumps({"output_file": out, "pages": pages, "sources": len(params.input_files)}, indent=2, ensure_ascii=False)
    except Exception as e:
        return _handle_error(e)

@mcp.tool(name="pdf_split", annotations={"title": "Split PDF by pages", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def pdf_split(params: SplitInput) -> str:
    """Split PDF into single-page PDFs (zip) by page spec like '1,3-5'. Returns zip path."""
    try:
        _ensure_exists(params.input_file)
        # Reuse parse logic from router
        import re
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(params.input_file)
        total = len(reader.pages)
        # parse pages
        result = set()
        for token in params.pages.split(","):
            token = token.strip()
            if "-" in token:
                s, e = token.split("-", 1)
                start, end = int(s.strip()), int(e.strip())
                if start < 1 or end < 1 or start > total or end > total or start > end:
                    return f"Error: Invalid range {token} for {total} pages"
                for p in range(start, end+1):
                    result.add(p)
            else:
                n = int(token)
                if n < 1 or n > total:
                    return f"Error: Page {n} out of range (has {total})"
                result.add(n)
        pages = sorted(result)
        out = _out_path(params.input_file, "_split", ".zip")
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for pnum in pages:
                w = PdfWriter()
                w.add_page(reader.pages[pnum-1])
                bio = io.BytesIO()
                w.write(bio)
                z.writestr(f"page_{pnum}.pdf", bio.getvalue())
        return json.dumps({"output_file": out, "pages_extracted": pages, "total_pages": total}, indent=2)
    except Exception as e:
        return _handle_error(e)

@mcp.tool(name="pdf_compress", annotations={"title": "Compress PDF", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def pdf_compress(params: CompressInput) -> str:
    """Compress PDF with low/medium/high quality. Uses PyMuPDF garbage+deflate, recompresses images on low."""
    try:
        _ensure_exists(params.input_file)
        out = params.output_file or _out_path(params.input_file, f"_compressed_{params.quality}")
        try:
            import fitz
        except ImportError:
            import pymupdf as fitz
        doc = fitz.open(params.input_file)
        if len(doc) == 0:
            return "Error: PDF has no pages"
        if params.quality == "low":
            for page in doc:
                for img in page.get_images(full=True):
                    try:
                        xref = img[0]
                        pix = fitz.Pixmap(doc, xref)
                        if pix.w >= 50 and pix.h >= 50:
                            if pix.n > 4:
                                pix = fitz.Pixmap(fitz.csRGB, pix)
                            jpg = pix.tobytes("jpg", jpg_quality=30)
                            doc.update_stream(xref, jpg)
                    except Exception:
                        continue
        doc.save(out, garbage=4, deflate=True, clean=True)
        doc.close()
        orig = os.path.getsize(params.input_file)
        comp = os.path.getsize(out)
        return json.dumps({"output_file": out, "original_bytes": orig, "compressed_bytes": comp, "saved_percent": round((1-comp/orig)*100,1) if orig else 0}, indent=2)
    except Exception as e:
        return _handle_error(e)

@mcp.tool(name="pdf_rotate", annotations={"title": "Rotate PDF", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def pdf_rotate(params: RotateInput) -> str:
    """Rotate PDF pages by 90/180/270 degrees. Pages spec like '1,3' or 'all'."""
    try:
        _ensure_exists(params.input_file)
        out = params.output_file or _out_path(params.input_file, f"_rotated_{params.angle}")
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(params.input_file)
        writer = PdfWriter()
        total = len(reader.pages)
        target = None
        if params.pages and params.pages.strip().lower() != "all":
            target = set()
            for tok in params.pages.split(","):
                tok = tok.strip()
                if "-" in tok:
                    s,e = tok.split("-",1)
                    for i in range(int(s), int(e)+1):
                        target.add(i)
                else:
                    target.add(int(tok))
        for idx, page in enumerate(reader.pages, start=1):
            if target is None or idx in target:
                page.rotate(params.angle)
            writer.add_page(page)
        with open(out, "wb") as f:
            writer.write(f)
        return json.dumps({"output_file": out, "angle": params.angle, "pages": total}, indent=2)
    except Exception as e:
        return _handle_error(e)

@mcp.tool(name="pdf_delete_pages", annotations={"title": "Delete PDF pages", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def pdf_delete_pages(params: DeleteInput) -> str:
    """Delete pages from PDF. Pages like '2' or '2,4-5'. Returns new PDF without those pages."""
    try:
        _ensure_exists(params.input_file)
        out = params.output_file or _out_path(params.input_file, "_deleted")
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(params.input_file)
        total = len(reader.pages)
        to_delete = set()
        for tok in params.pages.split(","):
            tok = tok.strip()
            if "-" in tok:
                s,e = tok.split("-",1)
                for i in range(int(s), int(e)+1):
                    to_delete.add(i)
            else:
                to_delete.add(int(tok))
        for p in to_delete:
            if p < 1 or p > total:
                return f"Error: Page {p} out of range (has {total})"
        writer = PdfWriter()
        for idx, page in enumerate(reader.pages, start=1):
            if idx not in to_delete:
                writer.add_page(page)
        if len(writer.pages) == 0:
            return "Error: Result would be empty — cannot delete all pages"
        with open(out, "wb") as f:
            writer.write(f)
        return json.dumps({"output_file": out, "deleted": sorted(to_delete), "remaining": len(writer.pages)}, indent=2)
    except Exception as e:
        return _handle_error(e)

@mcp.tool(name="pdf_watermark", annotations={"title": "Add watermark", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def pdf_watermark(params: WatermarkInput) -> str:
    """Add text or image watermark to every page with opacity and position."""
    try:
        _ensure_exists(params.input_file)
        if not params.text and not params.image_file:
            return "Error: Provide text or image_file"
        if params.image_file:
            _ensure_exists(params.image_file)
        out = params.output_file or _out_path(params.input_file, "_watermarked")
        import fitz
        doc = fitz.open(params.input_file)
        for page in doc:
            rect = page.rect
            if params.text:
                # Simple text watermark diagonal
                page.insert_textbox(rect, params.text, fontsize=48, color=(0.8,0.8,0.8), align=1, overlay=True)
            if params.image_file:
                # Place image at position
                pix_w = 150
                x, y = rect.width/2 - pix_w/2, rect.height/2 - pix_w/2
                if params.position == "top-left":
                    x, y = 20, 20
                elif params.position == "bottom-right":
                    x, y = rect.width - pix_w - 20, rect.height - pix_w - 20
                page.insert_image(fitz.Rect(x,y,x+pix_w,y+pix_w), filename=params.image_file, overlay=True, keep_proportion=True)
        doc.save(out, garbage=4, deflate=True)
        doc.close()
        return json.dumps({"output_file": out, "pages": len(fitz.open(out))}, indent=2)
    except Exception as e:
        return _handle_error(e)

@mcp.tool(name="pdf_to_jpg", annotations={"title": "PDF to JPG", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def pdf_to_jpg(params: PdfToJpgInput) -> str:
    """Render each PDF page to JPG images (zip). Returns zip with images."""
    try:
        _ensure_exists(params.input_file)
        out = _out_path(params.input_file, "_jpg", ".zip")
        import fitz
        doc = fitz.open(params.input_file)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for i, page in enumerate(doc):
                pix = page.get_pixmap(dpi=params.dpi)
                bio = io.BytesIO(pix.tobytes("png"))
                # Convert to jpg via Pillow
                from PIL import Image
                img = Image.open(bio)
                jbio = io.BytesIO()
                img.convert("RGB").save(jbio, "JPEG", quality=90)
                z.writestr(f"page_{i+1}.jpg", jbio.getvalue())
        return json.dumps({"output_file": out, "pages": len(doc)}, indent=2)
    except Exception as e:
        return _handle_error(e)

@mcp.tool(name="jpg_to_pdf", annotations={"title": "JPG to PDF", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def jpg_to_pdf(params: JpgToPdfInput) -> str:
    """Convert JPG/PNG images to paginated PDF."""
    try:
        for p in params.input_files:
            _ensure_exists(p)
        out = params.output_file or _out_path(params.input_files[0], "_from_images")
        import fitz
        doc = fitz.open()
        from PIL import Image
        for img_path in params.input_files:
            img = Image.open(img_path)
            w, h = img.size
            # A4-ish page
            page = doc.new_page(width=w, height=h)
            rect = fitz.Rect(0,0,w,h)
            page.insert_image(rect, filename=img_path)
        doc.save(out)
        doc.close()
        return json.dumps({"output_file": out, "images": len(params.input_files)}, indent=2)
    except Exception as e:
        return _handle_error(e)

@mcp.tool(name="word_to_pdf", annotations={"title": "Word to PDF", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def word_to_pdf(params: WordToPdfInput) -> str:
    """Convert DOCX/DOC to PDF via LibreOffice (requires soffice installed). Falls back to python-docx rendering."""
    try:
        _ensure_exists(params.input_file)
        out = params.output_file or _out_path(params.input_file, "", ".pdf")
        tmpdir = tempfile.mkdtemp()
        try:
            import subprocess, asyncio
            proc = await asyncio.to_thread(subprocess.run, ["soffice","--headless","--invisible","--norestore","--convert-to","pdf","--outdir",tmpdir, params.input_file], capture_output=True, timeout=30)
            if proc.returncode == 0:
                candidates = [os.path.join(tmpdir,f) for f in os.listdir(tmpdir) if f.endswith(".pdf")]
                if candidates:
                    shutil.copy(candidates[0], out)
                    return json.dumps({"output_file": out, "engine": "libreoffice"}, indent=2)
        except Exception:
            pass
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        # Fallback: text-only via python-docx + fitz
        from docx import Document
        import fitz
        docx_doc = Document(params.input_file)
        pdf = fitz.open()
        page = pdf.new_page()
        y = 40
        for para in docx_doc.paragraphs:
            if y > 800:
                page = pdf.new_page()
                y = 40
            page.insert_text((40,y), para.text, fontsize=11)
            y += 16
        pdf.save(out)
        pdf.close()
        return json.dumps({"output_file": out, "engine": "fallback"}, indent=2)
    except Exception as e:
        return _handle_error(e)

@mcp.tool(name="pdf_to_word", annotations={"title": "PDF to Word", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def pdf_to_word(params: PdfToWordInput) -> str:
    """Extract PDF text+images to editable DOCX (via pdf2docx + fallback)."""
    try:
        _ensure_exists(params.input_file)
        out = params.output_file or _out_path(params.input_file, "", ".docx")
        try:
            from pdf2docx import Converter
            cv = Converter(params.input_file)
            cv.convert(out, start=0, end=None)
            cv.close()
            if os.path.exists(out) and os.path.getsize(out) > 500:
                return json.dumps({"output_file": out, "engine": "pdf2docx"}, indent=2)
        except Exception:
            pass
        import fitz
        from docx import Document
        doc = fitz.open(params.input_file)
        word = Document()
        for page in doc:
            text = page.get_text()
            if text.strip():
                word.add_paragraph(text)
        word.save(out)
        return json.dumps({"output_file": out, "engine": "fallback"}, indent=2)
    except Exception as e:
        return _handle_error(e)

@mcp.tool(name="pdf_to_excel", annotations={"title": "PDF to Excel", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def pdf_to_excel(params: PdfToExcelInput) -> str:
    """Extract tables/text from PDF to XLSX (via pdfplumber)."""
    try:
        _ensure_exists(params.input_file)
        out = params.output_file or _out_path(params.input_file, "", ".xlsx")
        import pdfplumber
        from openpyxl import Workbook
        wb = Workbook()
        wb.remove(wb.active)
        with pdfplumber.open(params.input_file) as pdf:
            for pi, page in enumerate(pdf.pages):
                tables = page.extract_tables() or []
                if tables:
                    for ti, table in enumerate(tables):
                        ws = wb.create_sheet(title=f"P{pi+1}_T{ti+1}"[:31])
                        for r,row in enumerate(table):
                            for c,val in enumerate(row):
                                ws.cell(row=r+1, column=c+1, value=val)
                else:
                    text = page.extract_text() or ""
                    if text.strip():
                        ws = wb.create_sheet(title=f"P{pi+1}_text"[:31])
                        for r,line in enumerate(text.splitlines()):
                            if line.strip():
                                ws.cell(row=r+1, column=1, value=line)
        if len(wb.sheetnames)==0:
            ws = wb.create_sheet(title="Sheet1")
            ws.cell(row=1,column=1,value="No data extracted")
        wb.save(out)
        return json.dumps({"output_file": out, "sheets": wb.sheetnames}, indent=2)
    except Exception as e:
        return _handle_error(e)

@mcp.tool(name="pdf_to_ppt", annotations={"title": "PDF to PowerPoint", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def pdf_to_ppt(params: PdfToPptInput) -> str:
    """Convert each PDF page to a PPTX slide with image."""
    try:
        _ensure_exists(params.input_file)
        out = params.output_file or _out_path(params.input_file, "", ".pptx")
        import fitz
        from pptx import Presentation
        doc = fitz.open(params.input_file)
        prs = Presentation()
        prs.slide_width = int(13.33*914400)
        prs.slide_height = int(7.5*914400)
        blank = prs.slide_layouts[6]
        for page in doc:
            pix = page.get_pixmap(dpi=120)
            tmp = out + f"_tmp_{page.number}.png"
            pix.save(tmp)
            slide = prs.slides.add_slide(blank)
            slide.shapes.add_picture(tmp, 0,0, width=prs.slide_width, height=prs.slide_height)
            os.remove(tmp)
        prs.save(out)
        return json.dumps({"output_file": out, "slides": len(doc)}, indent=2)
    except Exception as e:
        return _handle_error(e)

@mcp.tool(name="excel_to_pdf", annotations={"title": "Excel to PDF", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def excel_to_pdf(params: ExcelToPdfInput) -> str:
    """Convert XLSX/XLS to PDF via LibreOffice."""
    try:
        _ensure_exists(params.input_file)
        out = params.output_file or _out_path(params.input_file, "", ".pdf")
        tmpdir = tempfile.mkdtemp()
        import subprocess, asyncio
        proc = await asyncio.to_thread(subprocess.run, ["soffice","--headless","--invisible","--norestore","--convert-to","pdf","--outdir",tmpdir, params.input_file], capture_output=True, timeout=30)
        candidates = [os.path.join(tmpdir,f) for f in os.listdir(tmpdir) if f.endswith(".pdf")] if os.path.exists(tmpdir) else []
        if proc.returncode == 0 and candidates:
            shutil.copy(candidates[0], out)
            shutil.rmtree(tmpdir, ignore_errors=True)
            return json.dumps({"output_file": out, "engine": "libreoffice"}, indent=2)
        shutil.rmtree(tmpdir, ignore_errors=True)
        if proc.returncode != 0:
            return f"Error: LibreOffice failed: {proc.stderr.decode()[:500] if proc.stderr else 'unknown'}"
        return f"Error: No PDF produced"
    except Exception as e:
        return _handle_error(e)

@mcp.tool(name="ppt_to_pdf", annotations={"title": "PowerPoint to PDF", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def ppt_to_pdf(params: PptToPdfInput) -> str:
    """Convert PPTX/PPT to PDF via LibreOffice."""
    try:
        _ensure_exists(params.input_file)
        out = params.output_file or _out_path(params.input_file, "", ".pdf")
        tmpdir = tempfile.mkdtemp()
        import subprocess, asyncio
        proc = await asyncio.to_thread(subprocess.run, ["soffice","--headless","--invisible","--norestore","--convert-to","pdf","--outdir",tmpdir, params.input_file], capture_output=True, timeout=30)
        candidates = [os.path.join(tmpdir,f) for f in os.listdir(tmpdir) if f.endswith(".pdf")] if os.path.exists(tmpdir) else []
        if candidates:
            shutil.copy(candidates[0], out)
            shutil.rmtree(tmpdir, ignore_errors=True)
            return json.dumps({"output_file": out, "engine": "libreoffice"}, indent=2)
        shutil.rmtree(tmpdir, ignore_errors=True)
        return _handle_error(RuntimeError(proc.stderr.decode()[:500] if proc.stderr else "No PDF produced"))
    except Exception as e:
        return _handle_error(e)

@mcp.tool(name="ocr_pdf", annotations={"title": "OCR PDF (scan to searchable)", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def ocr_pdf(params: OcrInput) -> str:
    """Make scanned PDF searchable via Tesseract (rus+eng)."""
    try:
        _ensure_exists(params.input_file)
        out = params.output_file or _out_path(params.input_file, "_ocr")
        import fitz, pytesseract
        from PIL import Image
        doc = fitz.open(params.input_file)
        out_doc = fitz.open()
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = pytesseract.image_to_string(img, lang=params.lang)
            new_page = out_doc.new_page(width=page.rect.width, height=page.rect.height)
            # embed original image + invisible text
            tmp = out + f"_tmp_{page.number}.png"
            pix.save(tmp)
            new_page.insert_image(new_page.rect, filename=tmp)
            # add searchable text as overlay (white on white small)
            new_page.insert_text((0,0), text, fontsize=1, color=(1,1,1))
            os.remove(tmp)
        out_doc.save(out)
        return json.dumps({"output_file": out, "pages": len(out_doc)}, indent=2)
    except Exception as e:
        return _handle_error(e)

@mcp.tool(name="pdf_protect", annotations={"title": "Protect PDF with password", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def pdf_protect(params: ProtectInput) -> str:
    """Encrypt PDF with password (128-bit)."""
    try:
        _ensure_exists(params.input_file)
        out = params.output_file or _out_path(params.input_file, "_protected")
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(params.input_file)
        writer = PdfWriter()
        for p in reader.pages:
            writer.add_page(p)
        writer.encrypt(params.password)
        with open(out, "wb") as f:
            writer.write(f)
        return json.dumps({"output_file": out}, indent=2)
    except Exception as e:
        return _handle_error(e)

@mcp.tool(name="pdf_unlock", annotations={"title": "Unlock PDF", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def pdf_unlock(params: UnlockInput) -> str:
    """Decrypt PDF with password."""
    try:
        _ensure_exists(params.input_file)
        out = params.output_file or _out_path(params.input_file, "_unlocked")
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(params.input_file)
        if reader.is_encrypted:
            if not reader.decrypt(params.password):
                return "Error: Wrong password"
        writer = PdfWriter()
        for p in reader.pages:
            writer.add_page(p)
        with open(out, "wb") as f:
            writer.write(f)
        return json.dumps({"output_file": out, "pages": len(writer.pages)}, indent=2)
    except Exception as e:
        return _handle_error(e)

if __name__ == "__main__":
    mcp.run()
