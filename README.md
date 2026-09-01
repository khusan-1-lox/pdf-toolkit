<p align="center">
  <img src="https://img.shields.io/badge/PDF_Toolkit-BETA-amber?style=for-the-badge&labelColor=black" alt="BETA"/>
</p>

<h1 align="center">PDF Toolkit</h1>
<p align="center"><b>25 Tools · Local · Private · Free MCP for AI Agents</b></p>
<p align="center">🌐 Languages: <a href="frontend/messages/en.json">EN</a> | <a href="frontend/messages/ru.json">RU</a> — Web served at <code>/en</code> and <code>/ru</code> (default <code>en</code>, auto-detect)</p>

<p align="center">
  <a href="https://github.com/khusan-1-lox/pdf-toolkit/releases/tag/v1.0.0-beta.1"><img src="https://img.shields.io/github/v/release/khusan-1-lox/pdf-toolkit?label=beta&color=amber" alt="beta"/></a>
  <a href="mcp/"><img src="https://img.shields.io/badge/MCP-1.29-blue?logo=anthropic" alt="MCP"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT"/></a>
  <img src="https://img.shields.io/badge/Next.js-14-black?logo=next.js" alt="Next.js"/>
  <img src="https://img.shields.io/badge/FastAPI-0.110-009688?logo=fastapi" alt="FastAPI"/>
</p>

<p align="center">
  <img src="mcp/banner.png" alt="PDF Toolkit banner" width="860"/>
</p>

<p align="center">
  <b>Merge · Split · Compress · Convert · OCR · Protect</b> — stays on your server. Auto-deleted in 5 minutes. No cloud.
</p>

---

### ✨ What's inside

| | Tools |
|---|---|
| **📂 Organize** | Merge, Split, Delete Pages, Rotate, Crop, Compare, Organize |
| **⚡ Optimize** | Compress PDF (low / medium / high) |
| **🔄 Convert** | PDF ↔ JPG, Word ↔ PDF, Excel ↔ PDF, PowerPoint ↔ PDF, PDF → Excel/PPT, HTML → PDF, PDF/A |
| **✏️ Edit** | Watermark, Page Numbers, Sign, Redact, OCR (eng+rus), Repair |
| **🔒 Security** | Protect with password (128-bit), Unlock |

> **BETA** — testing with friends. Download installer in [Releases](https://github.com/khusan-1-lox/pdf-toolkit/releases).

---

### 🖥️ Software

**Web** — `docker compose up --build` → http://localhost:3000/en (or /ru, auto-redirect)  
**Desktop** — `PDF Toolkit BETA` (Electron, Windows) — offline, 25 tools without browser. Download: [Release v1.0.0-beta.1](https://github.com/khusan-1-lox/pdf-toolkit/releases/tag/v1.0.0-beta.1)

<p align="center">
  <img src="docs/screenshot-dashboard.png" alt="dashboard" width="860"/>
</p>

---

### 🤖 MCP — Give Your AI Agent PDF Superpowers

Free, local, no API key. The agent calls tools itself.

**Step 1 — Install**

```bash
pip install mcp==1.29.1 pydantic pypdf PyMuPDF Pillow python-docx openpyxl python-pptx pdf2docx pdfplumber
```

**Step 2 — Connect**

Claude Desktop (`%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "pdf-toolkit": {
      "command": "python",
      "args": ["C:/path/to/pdf-toolkit/mcp/server.py"]
    }
  }
}
```

Cursor / OpenCode / VS Code + Cline — same `mcp.json`.

**Step 3 — Prompts**

```
Merge /tmp/a.pdf and /tmp/b.pdf via pdf_merge
Compress /tmp/big.pdf with low quality via pdf_compress
Make /tmp/scan.pdf searchable with Russian language via ocr_pdf
```

<details>
<summary>All 17 MCP tools</summary>

`pdf_merge` · `pdf_split` · `pdf_compress` · `pdf_rotate` · `pdf_delete_pages` · `pdf_watermark` · `pdf_to_jpg` · `jpg_to_pdf` · `word_to_pdf` · `pdf_to_word` · `pdf_to_excel` · `pdf_to_ppt` · `excel_to_pdf` · `ppt_to_pdf` · `ocr_pdf` · `pdf_protect` · `pdf_unlock`

</details>

Verify: `npx @modelcontextprotocol/inspector python mcp/server.py` · Docker: `docker build -f mcp/Dockerfile -t pdf-toolkit-mcp .`

<p align="center">
  <img src="docs/screenshot-mcp.png" alt="MCP inspector" width="860"/>
</p>

---

### 🚀 Quick Start

```bash
git clone https://github.com/khusan-1-lox/pdf-toolkit
cd pdf-toolkit
docker compose up --build
```

### 📁 Structure

```
pdf-toolkit/
  backend/   # FastAPI, 26 routes
  frontend/  # Next.js 14
  mcp/       # MCP server (stdio)
  desktop-electron/ # Electron BETA
```

### 📜 License

MIT — do what you want, privacy by default.
