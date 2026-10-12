<p align="center">
  <img src="https://img.shields.io/badge/PDF_Toolkit-v1.1.0-amber?style=for-the-badge&labelColor=black" alt="v1.1.0"/>
</p>

<h1 align="center">PDF Toolkit</h1>
<p align="center"><b>31+ Tools · Visual Editor · Windows Desktop App (Auto-Update) · Web · Free MCP for AI Agents</b></p>
<p align="center">🌐 Languages: <a href="frontend/messages/en.json">EN</a> | <a href="frontend/messages/ru.json">RU</a> — Web & Desktop served in <code>/ru</code> and <code>/en</code></p>

<p align="center">
  <a href="https://github.com/khusan-1-lox/pdf-toolkit/releases/tag/v1.1.0"><img src="https://img.shields.io/github/v/release/khusan-1-lox/pdf-toolkit?include_prereleases&label=release&color=amber" alt="release"/></a>
  <a href="mcp/"><img src="https://img.shields.io/badge/MCP-1.29-blue?logo=anthropic" alt="MCP"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT"/></a>
  <img src="https://img.shields.io/badge/Next.js-14-black?logo=next.js" alt="Next.js"/>
  <img src="https://img.shields.io/badge/FastAPI-0.110-009688?logo=fastapi" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/Electron-Windows_x64-47848F?logo=electron" alt="Electron"/>
</p>

<p align="center">
  <img src="mcp/banner.png" alt="PDF Toolkit banner" width="860"/>
</p>

<p align="center">
  <b>Merge · Split · Compress · Edit PDF · Forms · Convert · OCR · Redact · Protect</b> — 100% local & private. Auto-deleted in 5 minutes. No cloud.
</p>

---

### 🚀 Что нового в v1.1.0 / What's New in v1.1.0

- **🖥️ Установщик Windows (`.exe`) с автообновлением из GitHub** — полноценный Setup-инсталлятор (`PDF-Toolkit-Setup-1.1.0-x64.exe`) и Portable-версия. Программа автоматически проверяет новые релизы и коммиты в GitHub (`khusan-1-lox/pdf-toolkit`) и обновляется сама, а если на ПК нет Python — автоматически скачивает портативный Python 3.12 при первом запуске.
- **🎨 Новый интерактивный редактор документов (`ToolWorkspace` & `DocumentEditor`)** — визуальное рабочее пространство с предпросмотром страниц, drag-and-drop сортировкой, рисованием на страницах, размещением текста, фигур, изображений, подписей, водяных знаков, областей обрезки (`Crop`) и цензуры (`Redact`).
- **🆕 31+ инструмент + Цепочки действий (`Workflows`)** — добавлены **Редактор PDF (`Edit PDF`)**, **PDF-формы (`PDF Forms / AcroForms`)**, **PDF в Markdown (`PDF to Markdown`)**, **Извлечь страницы (`Extract Pages`)**, **Сканировать в PDF (`Scan to PDF`)** и **Цепочки действий (`Workflows`)**.
- **🔒 Усиленная безопасность и качество PDF** — защита `HTML to PDF` от SSRF/LFI с проверкой IP, точное физическое удаление скрытых данных в `Redact PDF`, поддержка кириллицы и улучшенное сжатие.

---

### ✨ Все инструменты / All Tools (31 + Workflows)

| Категория / Category | Инструменты / Tools |
|---|---|
| **📂 Страницы / Organize** | **Merge PDF** (Объединить), **Split PDF** (Разделить), **Organize PDF** (Организовать: порядок, поворот, вставка пустых страниц), **Extract Pages** (Извлечь страницы), **Remove Pages** (Удалить страницы), **Rotate PDF** (Повернуть), **Scan to PDF** (Сканировать в PDF), **Workflows** (Цепочки действий) |
| **⚡ Оптимизация / Optimize** | **Compress PDF** (Сжать PDF: low / medium / high), **OCR PDF** (Распознать текст: `eng` + `rus`), **Repair PDF** (Восстановить повреждённый PDF) |
| **🔄 Конвертация / Convert** | **PDF ↔ JPG/PNG**, **Word ↔ PDF**, **Excel ↔ PDF**, **PowerPoint ↔ PDF**, **HTML → PDF** (файл, код или URL), **PDF → Markdown**, **PDF → PDF/A** |
| **✏️ Редактирование / Edit** | **Edit PDF** (текст, картинки, фигуры, рисование), **PDF Forms** (заполнение и создание полей AcroForms), **Watermark** (водяной знак), **Page Numbers** (нумерация страниц), **Crop PDF** (обрезка полей), **Compare PDF** (сравнение двух PDF бок о бок) |
| **🔒 Защита / Security** | **Sign PDF** (нарисовать или загрузить подпись), **Protect PDF** (пароль AES/128-bit), **Unlock PDF** (снятие пароля), **Redact PDF** (безвозвратное удаление текста и областей) |

---

### 🖥️ Скачать и запустить / Download & Run

1. **Windows Desktop (`.exe` Installer & Portable)** — работает локально без браузера, с автообновлением с GitHub:
   - 📦 Скачать из [GitHub Releases (v1.1.0)](https://github.com/khusan-1-lox/pdf-toolkit/releases/tag/v1.1.0):
     - `PDF-Toolkit-Setup-1.1.0-x64.exe` — стандартный установщик Windows (ярлыки на Рабочем столе и в меню «Пуск»).
     - `PDF-Toolkit-Portable-1.1.0-x64.exe` — портативная версия в одном файле.
2. **Web (Docker)** — `docker compose up --build` → `http://localhost:3000/ru` (или `/en`).

<p align="center">
  <img src="docs/screenshot-dashboard.png" alt="dashboard" width="860"/>
</p>

---

### 🤖 MCP — Give Your AI Agent PDF Superpowers

Free, local, no API key. Connect Claude Desktop, Cursor, Cline, or any MCP client:

```bash
pip install mcp==1.29.1 pydantic pypdf PyMuPDF Pillow python-docx openpyxl python-pptx pdf2docx pdfplumber
```

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

<details>
<summary>All 17 MCP tools</summary>

`pdf_merge` · `pdf_split` · `pdf_compress` · `pdf_rotate` · `pdf_delete_pages` · `pdf_watermark` · `pdf_to_jpg` · `jpg_to_pdf` · `word_to_pdf` · `pdf_to_word` · `pdf_to_excel` · `pdf_to_ppt` · `excel_to_pdf` · `ppt_to_pdf` · `ocr_pdf` · `pdf_protect` · `pdf_unlock`

</details>

<p align="center">
  <img src="docs/screenshot-mcp.png" alt="MCP inspector" width="860"/>
</p>

---

### 🛠️ Сборка `.exe` из исходников / Build Desktop `.exe` from Source

```bash
cd frontend && npm ci && npm run build
cd ../desktop-electron && npm install && npm run build
```

Готовые файлы появятся в `desktop-electron/dist/`.

### 📁 Структура проекта / Structure

```
pdf-toolkit/
  backend/           # FastAPI, 30+ PDF routes & quality tests
  frontend/          # Next.js 14 (RU/EN), interactive PDF workspace
  mcp/               # MCP server (stdio) for AI agents
  desktop-electron/  # Windows Electron app + GitHub auto-updater
```

### 📜 License

MIT — do what you want, privacy by default.
