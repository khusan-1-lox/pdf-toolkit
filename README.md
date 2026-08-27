<p align="center">
  <img src="https://img.shields.io/badge/PDF_Toolkit-BETA-amber?style=for-the-badge&labelColor=black" alt="BETA"/>
</p>

<h1 align="center">PDF Toolkit</h1>
<p align="center"><b>25 инструментов · Локально · Приватно · Бесплатный MCP для AI-агентов</b></p>

<p align="center">
  <a href="https://github.com/khusan-1-lox/pdf-toolkit/releases/tag/v1.0.0-beta.1"><img src="https://img.shields.io/github/v/release/khusan-1-lox/pdf-toolkit?label=beta&color=amber" alt="beta"/></a>
  <a href="mcp/"><img src="https://img.shields.io/badge/MCP-1.29-blue?logo=anthropic" alt="MCP"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT"/></a>
  <img src="https://img.shields.io/badge/Next.js-14-black?logo=next.js" alt="Next.js"/>
  <img src="https://img.shields.io/badge/FastAPI-0.110-009688?logo=fastapi" alt="FastAPI"/>
</p>

<p align="center">
  <img src="mcp/banner.png" alt="PDF Toolkit banner" width="860" onerror="this.style.display='none'"/>
</p>

<p align="center">
  <b>Merge · Split · Compress · Convert · OCR · Protect</b> — всё на вашем сервере. Файлы удаляются через 5 минут. Никакого облака.
</p>

---

### ✨ Что внутри

| | Инструменты |
|---|---|
| **📂 Организовать** | Объединить, Разделить, Удалить страницы, Поворот, Обрезка, Сравнение, Сортировка |
| **⚡ Оптимизировать** | Сжать PDF (low / medium / high) |
| **🔄 Конвертировать** | PDF ↔ JPG, Word ↔ PDF, Excel ↔ PDF, PowerPoint ↔ PDF, PDF → Excel/PPT, HTML → PDF, PDF/A |
| **✏️ Редактировать** | Водяной знак, Нумерация, Подпись, Скрытие, OCR (рус+англ), Починка |
| **🔒 Безопасность** | Защита паролем (128-bit), Снятие пароля |

> **BETA** — тестируем с друзьями. Скачайте установщик в [Releases](https://github.com/khusan-1-lox/pdf-toolkit/releases).

---

### 🖥️ Софт

**Web** — `docker compose up --build` → http://localhost:3000  
**Desktop** — `PDF Toolkit BETA` (Electron, Windows) — офлайн, 25 инструментов без браузера. Скачать: [Release v1.0.0-beta.1](https://github.com/khusan-1-lox/pdf-toolkit/releases/tag/v1.0.0-beta.1)

<p align="center">
  <img src="docs/screenshot-dashboard.png" alt="dashboard" width="860" onerror="this.style.display='none'"/>
</p>

---

### 🤖 MCP — дайте AI-агенту PDF-суперсилы

Бесплатно, локально, без API-ключа. Агент сам вызывает тулы.

**Шаг 1 — Установка**

```bash
pip install mcp==1.29.1 pydantic pypdf PyMuPDF Pillow python-docx openpyxl python-pptx pdf2docx pdfplumber
```

**Шаг 2 — Подключение**

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

Cursor / OpenCode / VS Code + Cline — тот же `mcp.json`.

**Шаг 3 — Промпты**

```
Склей /tmp/a.pdf и /tmp/b.pdf через pdf_merge
Сожми /tmp/big.pdf с качеством low через pdf_compress
Сделай из /tmp/scan.pdf searchable PDF с русским языком через ocr_pdf
```

<details>
<summary>Все 17 MCP-тулов</summary>

`pdf_merge` · `pdf_split` · `pdf_compress` · `pdf_rotate` · `pdf_delete_pages` · `pdf_watermark` · `pdf_to_jpg` · `jpg_to_pdf` · `word_to_pdf` · `pdf_to_word` · `pdf_to_excel` · `pdf_to_ppt` · `excel_to_pdf` · `ppt_to_pdf` · `ocr_pdf` · `pdf_protect` · `pdf_unlock`

</details>

Проверка: `npx @modelcontextprotocol/inspector python mcp/server.py` · Docker: `docker build -f mcp/Dockerfile -t pdf-toolkit-mcp .`

<p align="center">
  <img src="docs/screenshot-mcp.png" alt="MCP inspector" width="860" onerror="this.style.display='none'"/>
</p>

---

### 🚀 Быстрый старт

```bash
git clone https://github.com/khusan-1-lox/pdf-toolkit
cd pdf-toolkit
docker compose up --build
```

### 📁 Структура

```
pdf-toolkit/
  backend/   # FastAPI, 26 роутов
  frontend/  # Next.js 14
  mcp/       # MCP сервер (stdio)
  desktop-electron/ # Electron BETA
```

### 📜 Лицензия

MIT — делай что хочешь, приватность по умолчанию.
