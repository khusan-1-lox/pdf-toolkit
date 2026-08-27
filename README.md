# PDF Toolkit — 25 tools + Free MCP Server

Privacy-first PDF toolkit. All files stay local, auto-delete in 5 min. Self-host on 2GB VPS or use as local MCP for AI agents.

[![MCP](https://img.shields.io/badge/MCP-1.29-blue)](mcp/) [![Python](https://img.shields.io/badge/python-3.12-blue)](backend/) [![Next.js](https://img.shields.io/badge/Next.js-14-black)](frontend/) [![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

## Why

- **iLovePDF clone, private**: no cloud upload, no training on your files
- **MCP for agents**: give Claude/Cursor 17 PDF tools via stdio (no API key)
- **Heavy local**: LibreOffice on-demand, PyMuPDF, pypdf — no paid APIs

## Tools (25)

| Category | Tools |
|---|---|
| **Organize** | merge, split, delete, rotate, crop, compare, organize-pdf |
| **Optimize** | compress (low/medium/high) |
| **Convert** | pdf→jpg, jpg→pdf, word↔pdf, excel↔pdf, ppt↔pdf, pdf→excel, pdf→ppt, html→pdf, pdf/a |
| **Edit** | watermark, page-numbers, sign, redact, ocr (rus+eng), repair |
| **Security** | protect (128-bit), unlock |

MCP exposes 17 most-used tools (see `mcp/server.py:607`). All return `output_file` path.

## Quick Start — Web

```bash
docker compose up --build
# web: http://localhost:3000  api: http://localhost:8000
```

Limits: 50 MB/file, 2–10 files for merge, 5 min retention (`TMP_ROOT` + `RETENTION_SECONDS`).

## Quick Start — MCP (free, local, no billing)

```bash
pip install mcp==1.29.1 pydantic pypdf PyMuPDF Pillow python-docx openpyxl python-pptx pdf2docx pdfplumber
python mcp/server.py  # stdio, waits for MCP client
```

Claude Desktop `claude_desktop_config.json`:

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

Test with Inspector:

```bash
npx @modelcontextprotocol/inspector python mcp/server.py
```

Tools: `pdf_merge`, `pdf_split`, `pdf_compress`, `pdf_rotate`, `pdf_delete_pages`, `pdf_watermark`, `pdf_to_jpg`, `jpg_to_pdf`, `word_to_pdf`, `pdf_to_word`, `pdf_to_excel`, `pdf_to_ppt`, `excel_to_pdf`, `ppt_to_pdf`, `ocr_pdf`, `pdf_protect`, `pdf_unlock`

Prompt example: `Склей /tmp/a.pdf и /tmp/b.pdf через pdf_merge`

Docker for MCP (with LibreOffice):

```bash
docker build -f mcp/Dockerfile -t pdf-toolkit-mcp .
```

Smithery 1-click: add `mcp/smithery.yaml` (stdio).

## Project Structure

```
pdf-toolkit/
  backend/   # FastAPI + 26 routers (app/main.py:145)
  frontend/  # Next.js 14 (app/page.tsx:104)
  mcp/       # FastMCP server (server.py, pyproject.toml, Dockerfile)
  docker-compose.yml
  nginx.conf
```

## Security

- No secrets in git: `.env*` ignored (`.env.example` kept as template), `frontend/.env.local` removed from history
- Telegram token now via `{env:TELEGRAM_BOT_TOKEN}` in `opencode.jsonc:42`
- If a token leaked, rotate via @BotFather `/revoke` immediately

