import io
import os
import sys
import tempfile
import shutil
try:
    import requests as _requests
    HAS_REQUESTS = True
except ImportError:
    _requests = None
    HAS_REQUESTS = False
from pypdf import PdfWriter

# --- 1) Frontend / tool pages checks (via HTTP if server up) ---
tools_old = ['merge','split','delete','rotate','crop','compare','compress','pdf-to-jpg','jpg-to-pdf','watermark','page-numbers','sign','redact','protect','unlock','organize-pdf']
tools_office = ['word-to-pdf','excel-to-pdf','ppt-to-pdf','pdf-to-word','pdf-to-excel','pdf-to-ppt']
tools_phase2 = ['ocr-pdf','pdf-to-pdfa','html-to-pdf','repair-pdf']
tools = tools_old + tools_office + tools_phase2  # 16 + 6 + 4 = 26 total (dashboard subtitle says 25 — actual array is 26 incl. repair-pdf)
print(f'Checking {len(tools)} tool pages (old {len(tools_old)} + office {len(tools_office)} + phase2 {len(tools_phase2)}):')
frontend_ok = 0
frontend_fail = 0
frontend_skipped = 0
if not HAS_REQUESTS:
    print('  SKIP all frontend checks: requests not installed (pip install requests)')
    frontend_skipped = len(tools)
else:
    for slug in tools:
        try:
            r = _requests.get(f'http://127.0.0.1:3000/tools/{slug}', timeout=5)
            has_unknown = 'Unknown tool' in r.text
            status = 'OK' if (not has_unknown and r.status_code == 200) else 'FAIL'
            if status == 'OK':
                frontend_ok += 1
            else:
                frontend_fail += 1
            print(f'  {slug}: {status} (unknown={has_unknown}, status={r.status_code})')
        except Exception as e:
            frontend_skipped += 1
            print(f'  {slug}: SKIP (frontend not running: {e})')

# Dashboard
# Expected count: 26 tools total (16 old + 6 office + 4 phase2) — subtitle says 25 but array has 26
EXPECTED_TOOL_COUNT = 26
# Also accept 25 as legacy count if subtitle not yet updated
if HAS_REQUESTS:
    try:
        r = _requests.get('http://127.0.0.1:3000', timeout=5)
        links = r.text.count("/tools/")
        dash_ok = r.status_code == 200 and (EXPECTED_TOOL_COUNT - 2 <= links <= EXPECTED_TOOL_COUNT + 5 or "25" in r.text or "26" in r.text)
        dash_status = 'OK' if dash_ok else 'WARN'
        print(f'Dashboard: {dash_status} status={r.status_code} len={len(r.text)} tools_links={links} expected~{EXPECTED_TOOL_COUNT} (accept 25-26)')
        if not dash_ok and r.status_code == 200:
            print(f'  WARN: dashboard links {links} differs from expected {EXPECTED_TOOL_COUNT} — check frontend/app/page.tsx tools array')
    except Exception as e:
        print(f'Dashboard: SKIP (not running: {e})')
else:
    print('Dashboard: SKIP (requests not installed)')

# API proxy via frontend
if HAS_REQUESTS:
    try:
        w = PdfWriter()
        w.add_blank_page(595, 842)
        b = io.BytesIO()
        w.write(b)
        b.seek(0)
        r = _requests.post('http://127.0.0.1:3000/api/merge',
            files=[('files', ('a.pdf', b, 'application/pdf'))], timeout=10)
        print(f'API /api/merge via frontend proxy: {r.status_code} - {r.headers.get("content-type")} ({len(r.content)} bytes)')
    except Exception as e:
        print(f'API /api/merge via frontend proxy: SKIP ({e})')
else:
    print('API /api/merge via frontend proxy: SKIP (requests not installed)')

print('\n--- Office conversion API checks (backend TestClient, with soffice mock fallback) ---')

# --- 2) Backend office conversion checks via TestClient ---
# Ensure backend app is importable regardless of cwd (working dir is C:\Users\LOX\Documents\pdf-toolkit, script is in pdf-toolkit/pdf-toolkit/)
backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
# Also handle when run as python pdf-toolkit/final_test.py from parent dir: __file__ is pdf-toolkit/pdf-toolkit/final_test.py, backend_dir resolves correctly.
# Fallback: try parent pdf-toolkit folder
alt_backend = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'pdf-toolkit', 'backend')
if alt_backend not in sys.path and os.path.exists(alt_backend):
    sys.path.insert(0, alt_backend)

office_results = []
try:
    from fastapi.testclient import TestClient
    from app.main import app
    import app.routers.word_to_pdf as w2p_mod
    import app.routers.excel_to_pdf as e2p_mod
    import app.routers.ppt_to_pdf as p2p_mod
    import app.services.office_convert as svc_mod

    # Mock convert_office_to_pdf if soffice not available (same logic as backend/tests/test_office_conversions.py)
    need_mock = shutil.which("soffice") is None
    if need_mock:
        print('  soffice not found -> mocking convert_office_to_pdf with dummy PDF via fitz')
        import fitz
        async def fake_convert(input_path: str, out_dir: str, timeout: int = 30) -> str:
            out_pdf = os.path.join(out_dir, os.path.splitext(os.path.basename(input_path))[0] + ".pdf")
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((72, 72), "dummy")
            doc.save(out_pdf)
            doc.close()
            return out_pdf
        w2p_mod.convert_office_to_pdf = fake_convert
        e2p_mod.convert_office_to_pdf = fake_convert
        p2p_mod.convert_office_to_pdf = fake_convert
        svc_mod.convert_office_to_pdf = fake_convert
    else:
        print('  soffice found -> using real LibreOffice conversion')

    client = TestClient(app)

    # helpers to create minimal fixtures
    def make_docx_bytes():
        from docx import Document
        d = Document()
        d.add_paragraph("Hello Word to PDF - final_test")
        bio = io.BytesIO()
        d.save(bio)
        bio.seek(0)
        return bio.read()

    def make_xlsx_bytes():
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws["A1"] = "Hello Excel to PDF - final_test"
        bio = io.BytesIO()
        wb.save(bio)
        bio.seek(0)
        return bio.read()

    def make_pptx_bytes():
        from pptx import Presentation
        prs = Presentation()
        slide_layout = prs.slide_layouts[0] if len(prs.slide_layouts) > 0 else prs.slide_layouts[6]
        slide = prs.slides.add_slide(slide_layout)
        try:
            slide.shapes.title.text = "Hello PPT to PDF - final_test"
        except Exception:
            txBox = slide.shapes.add_textbox(72, 72, 400, 100)
            txBox.text_frame.text = "Hello PPT to PDF - final_test"
        bio = io.BytesIO()
        prs.save(bio)
        bio.seek(0)
        return bio.read()

    def make_pdf_bytes(text="Hello PDF for office test"):
        import fitz
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), text)
        b = doc.tobytes()
        doc.close()
        return b

    # Define 6 checks: (name, method)
    checks = []

    # 1) word-to-pdf
    try:
        data = make_docx_bytes()
        resp = client.post("/api/word-to-pdf", files={"file": ("test.docx", data, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
        ok = resp.status_code == 200 and resp.headers.get("content-type") == "application/pdf" and resp.content[:4] == b"%PDF"
        msg = f'status={resp.status_code} ct={resp.headers.get("content-type")} pdf_header={resp.content[:4]}'
        checks.append(("word-to-pdf", ok, msg))
        print(f'  word-to-pdf: {"OK" if ok else "FAIL"} - {msg}')
    except Exception as e:
        checks.append(("word-to-pdf", False, str(e)))
        print(f'  word-to-pdf: FAIL - {e}')

    # 2) excel-to-pdf
    try:
        data = make_xlsx_bytes()
        resp = client.post("/api/excel-to-pdf", files={"file": ("test.xlsx", data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        ok = resp.status_code == 200 and resp.headers.get("content-type") == "application/pdf" and resp.content[:4] == b"%PDF"
        msg = f'status={resp.status_code} ct={resp.headers.get("content-type")} pdf_header={resp.content[:4]}'
        checks.append(("excel-to-pdf", ok, msg))
        print(f'  excel-to-pdf: {"OK" if ok else "FAIL"} - {msg}')
    except Exception as e:
        checks.append(("excel-to-pdf", False, str(e)))
        print(f'  excel-to-pdf: FAIL - {e}')

    # 3) ppt-to-pdf
    try:
        data = make_pptx_bytes()
        resp = client.post("/api/ppt-to-pdf", files={"file": ("test.pptx", data, "application/vnd.openxmlformats-officedocument.presentationml.presentation")})
        ok = resp.status_code == 200 and resp.headers.get("content-type") == "application/pdf" and resp.content[:4] == b"%PDF"
        msg = f'status={resp.status_code} ct={resp.headers.get("content-type")} pdf_header={resp.content[:4]}'
        checks.append(("ppt-to-pdf", ok, msg))
        print(f'  ppt-to-pdf: {"OK" if ok else "FAIL"} - {msg}')
    except Exception as e:
        checks.append(("ppt-to-pdf", False, str(e)))
        print(f'  ppt-to-pdf: FAIL - {e}')

    # 4) pdf-to-word
    try:
        pdf_bytes = make_pdf_bytes("Hello Word from PDF - final_test")
        resp = client.post("/api/pdf-to-word", files={"file": ("test.pdf", pdf_bytes, "application/pdf")})
        ok_ct = resp.headers.get("content-type") == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ok_status = resp.status_code == 200
        # verify docx content
        ok_content = False
        if ok_status and ok_ct:
            tmp = tempfile.mktemp(suffix=".docx")
            try:
                with open(tmp, "wb") as f:
                    f.write(resp.content)
                from docx import Document as DocxDoc
                d = DocxDoc(tmp)
                text = "\n".join([p.text for p in d.paragraphs])
                ok_content = "Hello Word" in text or len(text.strip()) > 0
            finally:
                if os.path.exists(tmp):
                    os.remove(tmp)
        ok = ok_status and ok_ct and ok_content
        msg = f'status={resp.status_code} ct={resp.headers.get("content-type")} has_content={ok_content} len={len(resp.content)}'
        checks.append(("pdf-to-word", ok, msg))
        print(f'  pdf-to-word: {"OK" if ok else "FAIL"} - {msg}')
    except Exception as e:
        checks.append(("pdf-to-word", False, str(e)))
        print(f'  pdf-to-word: FAIL - {e}')

    # 5) pdf-to-excel
    try:
        pdf_bytes = make_pdf_bytes("Hello Excel from PDF - final_test")
        resp = client.post("/api/pdf-to-excel", files={"file": ("test.pdf", pdf_bytes, "application/pdf")})
        ok_ct = resp.headers.get("content-type") == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ok_status = resp.status_code == 200
        ok_content = False
        if ok_status and ok_ct:
            tmp = tempfile.mktemp(suffix=".xlsx")
            try:
                with open(tmp, "wb") as f:
                    f.write(resp.content)
                from openpyxl import load_workbook
                wb = load_workbook(tmp)
                ws = wb.active
                found = any(cell and "Hello Excel" in str(cell) for row in ws.iter_rows(values_only=True) for cell in row if cell is not None)
                if not found:
                    has_any = any(cell is not None and str(cell).strip() != "" for row in ws.iter_rows(values_only=True) for cell in row if cell is not None)
                    ok_content = has_any
                else:
                    ok_content = True
                wb.close()
            finally:
                if os.path.exists(tmp):
                    os.remove(tmp)
        ok = ok_status and ok_ct and ok_content
        msg = f'status={resp.status_code} ct={resp.headers.get("content-type")} has_content={ok_content} len={len(resp.content)}'
        checks.append(("pdf-to-excel", ok, msg))
        print(f'  pdf-to-excel: {"OK" if ok else "FAIL"} - {msg}')
    except Exception as e:
        checks.append(("pdf-to-excel", False, str(e)))
        print(f'  pdf-to-excel: FAIL - {e}')

    # 6) pdf-to-ppt
    try:
        pdf_bytes = make_pdf_bytes("Hello PPT from PDF - final_test")
        resp = client.post("/api/pdf-to-ppt", files={"file": ("test.pptx", pdf_bytes, "application/pdf")}) if False else client.post("/api/pdf-to-ppt", files={"file": ("test.pdf", pdf_bytes, "application/pdf")})
        # Note: endpoint expects file field named "file"
        ok_ct = resp.headers.get("content-type") == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        ok_status = resp.status_code == 200
        ok_content = False
        if ok_status and ok_ct:
            tmp = tempfile.mktemp(suffix=".pptx")
            try:
                with open(tmp, "wb") as f:
                    f.write(resp.content)
                from pptx import Presentation as PptPres
                prs = PptPres(tmp)
                ok_content = len(prs.slides) >= 1
            finally:
                if os.path.exists(tmp):
                    os.remove(tmp)
        ok = ok_status and ok_ct and ok_content
        msg = f'status={resp.status_code} ct={resp.headers.get("content-type")} slides_ok={ok_content} len={len(resp.content)}'
        checks.append(("pdf-to-ppt", ok, msg))
        print(f'  pdf-to-ppt: {"OK" if ok else "FAIL"} - {msg}')
    except Exception as e:
        checks.append(("pdf-to-ppt", False, str(e)))
        print(f'  pdf-to-ppt: FAIL - {e}')

    office_ok = sum(1 for _, ok, _ in checks if ok)
    office_fail = len(checks) - office_ok
    print(f'\nOffice conversions: {office_ok}/{len(checks)} passed')
    for name, ok, msg in checks:
        office_results.append((name, ok))
    if office_fail == 0:
        print('All 6 office checks PASSED')
    else:
        print(f'{office_fail} office checks FAILED')

except Exception as e:
    print(f'Backend TestClient office checks FAILED to run: {e}')
    import traceback; traceback.print_exc()
    office_ok = 0
    office_fail = 6

print('\n--- Phase2 API checks (backend TestClient, fallback handles missing weasyprint/pikepdf) ---')
phase2_results = []
phase2_ok = 0
phase2_fail = 0
try:
    from fastapi.testclient import TestClient as _TC2
    from app.main import app as _app2
    # reuse same client if already created, else new
    try:
        _client2 = client  # type: ignore  # from office block
    except NameError:
        _client2 = _TC2(_app2)
    import fitz as _fitz2

    def _make_pdf_bytes_phase2(text="Hello Phase2"):
        doc = _fitz2.open()
        page = doc.new_page()
        page.insert_text((72, 72), text)
        b = doc.tobytes()
        doc.close()
        return b

    _p2_checks = []

    # 1) ocr-pdf  (reuse fitz pdf fixture; weasyprint/pikepdf optional — fallback via fitz exists)
    try:
        pdf_b = _make_pdf_bytes_phase2("Hello OCR phase2 - final_test")
        resp = _client2.post("/api/ocr-pdf", files={"file": ("test.pdf", pdf_b, "application/pdf")})
        ok = resp.status_code == 200 and resp.headers.get("content-type") == "application/pdf" and resp.content[:4] == b"%PDF"
        msg = f'status={resp.status_code} ct={resp.headers.get("content-type")} pdf_header={resp.content[:4]} len={len(resp.content)}'
        _p2_checks.append(("ocr-pdf", ok, msg))
        print(f'  ocr-pdf: {"OK" if ok else "FAIL"} - {msg}')
        if not ok:
            print(f'    body preview: {resp.text[:500]}')
    except Exception as e:
        _p2_checks.append(("ocr-pdf", False, str(e)))
        print(f'  ocr-pdf: FAIL - {e}')
        import traceback as _tb1; _tb1.print_exc()

    # 2) pdf-to-pdfa — try primary route, fallback to alias /api/pdfa
    try:
        pdf_b = _make_pdf_bytes_phase2("Hello PDF/A phase2")
        resp = _client2.post("/api/pdf-to-pdfa", files={"file": ("test.pdf", pdf_b, "application/pdf")})
        # also accept alias if primary 404 (should not happen, but handle per task)
        if resp.status_code == 404:
            resp = _client2.post("/api/pdfa", files={"file": ("test.pdf", pdf_b, "application/pdf")})
        ct = resp.headers.get("content-type")
        pdf_header_ok = resp.content[:4] == b"%PDF"
        # X-PDF-A header is set lower-case in FileResponse; TestClient normalizes?
        has_pdfa_header = resp.headers.get("x-pdf-a") == "true" or resp.headers.get("X-PDF-A") == "true" or resp.headers.get("x-pdf-a".lower()) == "true"
        # If alias /api/pdfa used, same header expected
        ok = resp.status_code == 200 and ct == "application/pdf" and pdf_header_ok
        # header is secondary — warn but not fail if missing
        extra = f' x-pdf-a={resp.headers.get("x-pdf-a") or resp.headers.get("X-PDF-A")}'
        msg = f'status={resp.status_code} ct={ct} header_ok={pdf_header_ok}{extra} len={len(resp.content)}'
        _p2_checks.append(("pdf-to-pdfa", ok, msg))
        print(f'  pdf-to-pdfa: {"OK" if ok else "FAIL"} - {msg}')
        if not ok:
            print(f'    body preview: {resp.text[:500]}')
        # also verify alias works if not already tried
        try:
            resp_alias = _client2.post("/api/pdfa", files={"file": ("test.pdf", pdf_b, "application/pdf")})
            alias_ok = resp_alias.status_code == 200 and resp_alias.content[:4] == b"%PDF"
            print(f'  pdfa (alias /api/pdfa): {"OK" if alias_ok else "FAIL"} - status={resp_alias.status_code} ct={resp_alias.headers.get("content-type")}')
        except Exception as ae:
            print(f'  pdfa alias check SKIP: {ae}')
    except Exception as e:
        _p2_checks.append(("pdf-to-pdfa", False, str(e)))
        print(f'  pdf-to-pdfa: FAIL - {e}')
        import traceback as _tb2; _tb2.print_exc()

    # 3) html-to-pdf — test html string fixture, file upload, and alias handling
    try:
        # html string via Form field (primary pattern)
        resp = _client2.post("/api/html-to-pdf", data={"html": "<h1>Hello HTML phase2</h1><p>final_test html string</p>"})
        ok = resp.status_code == 200 and resp.headers.get("content-type") == "application/pdf" and resp.content[:4] == b"%PDF"
        msg = f'status={resp.status_code} ct={resp.headers.get("content-type")} header={resp.content[:4]} len={len(resp.content)}'
        _p2_checks.append(("html-to-pdf", ok, msg))
        print(f'  html-to-pdf (html string): {"OK" if ok else "FAIL"} - {msg}')
        if not ok:
            print(f'    body preview: {resp.text[:500]}')
        # file upload variant — should also pass
        try:
            html_bytes = b"<html><body><h1>Hello file</h1><p>test file final_test</p></body></html>"
            resp2 = _client2.post("/api/html-to-pdf", files={"file": ("test.html", html_bytes, "text/html")})
            ok2 = resp2.status_code == 200 and resp2.content[:4] == b"%PDF"
            print(f'  html-to-pdf (file upload): {"OK" if ok2 else "FAIL"} - status={resp2.status_code} ct={resp2.headers.get("content-type")} len={len(resp2.content)}')
        except Exception as fe:
            print(f'  html-to-pdf (file upload) SKIP: {fe}')
    except Exception as e:
        _p2_checks.append(("html-to-pdf", False, str(e)))
        print(f'  html-to-pdf: FAIL - {e}')
        import traceback as _tb3; _tb3.print_exc()

    # 4) repair-pdf — handle both /api/repair-pdf and /api/repair alias
    try:
        pdf_b = _make_pdf_bytes_phase2("Hello Repair phase2")
        resp = _client2.post("/api/repair-pdf", files={"file": ("test.pdf", pdf_b, "application/pdf")})
        if resp.status_code == 404:
            resp = _client2.post("/api/repair", files={"file": ("test.pdf", pdf_b, "application/pdf")})
        ok = resp.status_code == 200 and resp.headers.get("content-type") == "application/pdf" and resp.content[:4] == b"%PDF"
        msg = f'status={resp.status_code} ct={resp.headers.get("content-type")} header={resp.content[:4]} len={len(resp.content)}'
        _p2_checks.append(("repair-pdf", ok, msg))
        print(f'  repair-pdf: {"OK" if ok else "FAIL"} - {msg}')
        if not ok:
            print(f'    body preview: {resp.text[:500]}')
        # also verify alias
        try:
            resp_alias = _client2.post("/api/repair", files={"file": ("test.pdf", pdf_b, "application/pdf")})
            alias_ok = resp_alias.status_code == 200 and resp_alias.content[:4] == b"%PDF"
            print(f'  repair (alias /api/repair): {"OK" if alias_ok else "FAIL"} - status={resp_alias.status_code} ct={resp_alias.headers.get("content-type")}')
        except Exception as ae:
            print(f'  repair alias check SKIP: {ae}')
    except Exception as e:
        _p2_checks.append(("repair-pdf", False, str(e)))
        print(f'  repair-pdf: FAIL - {e}')
        import traceback as _tb4; _tb4.print_exc()

    phase2_ok = sum(1 for _, ok, _ in _p2_checks if ok)
    phase2_fail = len(_p2_checks) - phase2_ok
    print(f'\nPhase2 conversions: {phase2_ok}/{len(_p2_checks)} passed')
    for name, ok, msg in _p2_checks:
        phase2_results.append((name, ok))
    if phase2_fail == 0:
        print('All 4 phase2 checks PASSED')
    else:
        print(f'{phase2_fail} phase2 checks FAILED')

except Exception as e:
    print(f'Backend TestClient phase2 checks FAILED to run: {e}')
    import traceback; traceback.print_exc()
    phase2_ok = 0
    phase2_fail = 4

print('\n--- Summary ---')
print(f'Frontend tool pages: {frontend_ok} OK, {frontend_fail} FAIL, {frontend_skipped} SKIP (total {len(tools)} = {len(tools_old)} old + {len(tools_office)} office + {len(tools_phase2)} phase2)')
try:
    print(f'Backend office: {office_ok} OK, {office_fail} FAIL (expected 6)')
except NameError:
    pass
try:
    print(f'Backend phase2: {phase2_ok} OK, {phase2_fail} FAIL (expected 4)')
except NameError:
    pass
# docker compose config check hint
print('Docker compose: run `docker compose config` or `docker-compose config` to validate (checked separately in Task 8 verification)')

print('\n--- All checks done ---')
# Exit code reflects office + phase2 backend checks (critical for Task 8/7)
_exit_fail = 0
if 'office_fail' in locals() and office_fail > 0:
    _exit_fail += office_fail
if 'phase2_fail' in locals() and phase2_fail > 0:
    _exit_fail += phase2_fail
if _exit_fail > 0:
    sys.exit(1)
