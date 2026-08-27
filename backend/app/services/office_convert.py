import asyncio
import subprocess
import os
import shutil
import fitz  # PyMuPDF
from docx import Document
from openpyxl import Workbook
from pptx import Presentation

SEMAPHORE = asyncio.Semaphore(3)
TIMEOUT = 30


async def convert_office_to_pdf(input_path: str, out_dir: str, timeout: int = TIMEOUT) -> str:
    async with SEMAPHORE:
        # LibreOffice: soffice --headless --convert-to pdf --outdir out_dir input_path
        proc = await asyncio.to_thread(
            subprocess.run,
            ["soffice", "--headless", "--invisible", "--norestore", "--convert-to", "pdf", "--outdir", out_dir, input_path],
            capture_output=True, timeout=timeout
        )
        if proc.returncode != 0:
            raise RuntimeError(f"LibreOffice failed: {proc.stderr.decode()[:500]}")
        base = os.path.splitext(os.path.basename(input_path))[0] + ".pdf"
        out = os.path.join(out_dir, base)
        if not os.path.exists(out):
            # LibreOffice sometimes keeps original name
            candidates = [os.path.join(out_dir, f) for f in os.listdir(out_dir) if f.endswith(".pdf")]
            if not candidates:
                raise RuntimeError("Conversion produced no PDF")
            out = candidates[0]
        return out


def convert_pdf_to_docx(pdf_path: str, out_path: str) -> None:
    # Try pdf2docx for high-fidelity layout preservation (tables, columns, fonts)
    try:
        from pdf2docx import Converter

        cv = Converter(pdf_path)
        cv.convert(out_path, start=0, end=None)
        cv.close()
        # pdf2docx succeeded — verify output has content
        if os.path.exists(out_path) and os.path.getsize(out_path) > 500:
            return
    except Exception:
        pass
    # Fallback: simple text+images via PyMuPDF + python-docx
    doc = fitz.open(pdf_path)
    word = Document()
    for page in doc:
        text = page.get_text()
        if text.strip():
            word.add_paragraph(text)
        for img in page.get_images(full=True):
            try:
                pix = fitz.Pixmap(doc, img[0])
                if pix.n > 4:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                img_path = out_path + f"_tmp_{img[0]}.png"
                pix.save(img_path)
                word.add_picture(img_path, width=pix.w * 0.5)
                os.remove(img_path)
            except Exception:
                continue
    word.save(out_path)


def convert_pdf_to_xlsx(pdf_path: str, out_path: str) -> None:
    # Try pdfplumber table extraction for real tables
    try:
        import pdfplumber

        wb = Workbook()
        wb.remove(wb.active)
        found_table = False
        with pdfplumber.open(pdf_path) as pdf:
            for pi, page in enumerate(pdf.pages):
                tables = page.extract_tables() or []
                if tables:
                    for ti, table in enumerate(tables):
                        ws = wb.create_sheet(title=f"P{pi+1}_T{ti+1}"[:31])
                        for r, row in enumerate(table):
                            for c, val in enumerate(row):
                                ws.cell(row=r + 1, column=c + 1, value=val)
                        found_table = True
                else:
                    # No table on this page — fallback to text lines
                    text = page.extract_text() or ""
                    if text.strip():
                        ws = wb.create_sheet(title=f"P{pi+1}_text"[:31]) if not found_table or len(wb.sheetnames) == 0 else wb.create_sheet(title=f"P{pi+1}_text"[:31])
                        # Ensure at least one sheet
                        if len(wb.sheetnames) == 1 and wb.active is None:
                            ws = wb.create_sheet(title="Sheet1")
                        for r, line in enumerate(text.splitlines()):
                            if line.strip():
                                ws.cell(row=r + 1, column=1, value=line)
                        found_table = True
        if len(wb.sheetnames) == 0:
            raise ValueError("No data extracted")
        # Remove default empty sheet if we created others
        if "Sheet" in wb.sheetnames and len(wb.sheetnames) > 1:
            try:
                wb.remove(wb["Sheet"])
            except Exception:
                pass
        wb.save(out_path)
        return
    except Exception:
        pass
    # Fallback: simple text dump via fitz
    doc = fitz.open(pdf_path)
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    for i, page in enumerate(doc):
        text = page.get_text()
        for r, line in enumerate(text.splitlines()):
            if line.strip():
                ws.cell(row=i * 100 + r + 1, column=1, value=line)
    wb.save(out_path)


def convert_pdf_to_pptx(pdf_path: str, out_path: str) -> None:
    doc = fitz.open(pdf_path)
    prs = Presentation()
    prs.slide_width = int(13.33 * 914400)
    prs.slide_height = int(7.5 * 914400)
    blank = prs.slide_layouts[6]
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        img_path = out_path + f"_tmp_{page.number}.png"
        pix.save(img_path)
        slide = prs.slides.add_slide(blank)
        slide.shapes.add_picture(img_path, 0, 0, width=prs.slide_width, height=prs.slide_height)
        os.remove(img_path)
    prs.save(out_path)
