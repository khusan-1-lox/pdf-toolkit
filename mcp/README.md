# PDF Toolkit MCP — бесплатный локальный MCP-сервер (без сайта/биллинга)

26 инструментов PDF как MCP-тулы для AI-агентов. Файлы не уходят в облако.

## Быстрый старт (free, stdio)

```bash
cd pdf-toolkit/mcp
pip install -e .
# или: pip install mcp pydantic pypdf PyMuPDF Pillow python-docx openpyxl python-pptx pdf2docx pdfplumber pikepdf WeasyPrint pytesseract
```

### Claude Desktop
`claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "pdf-toolkit": {
      "command": "python",
      "args": ["-m", "server"],
      "cwd": "C:/Users/LOX/Documents/pdf-toolkit/pdf-toolkit/mcp"
    }
  }
}
```
Перезапусти Claude → появятся тулы `pdf_merge`, `pdf_split`, `pdf_compress`, `pdf_rotate`, `pdf_delete_pages`, `pdf_watermark`, `pdf_to_jpg`, `jpg_to_pdf`, `word_to_pdf`, `pdf_to_word`, `pdf_to_excel`, `pdf_to_ppt`, `excel_to_pdf`, `ppt_to_pdf`, `ocr_pdf`, `pdf_protect`, `pdf_unlock`.

### Cursor / OpenCode
Аналогично в `mcp.json`:
```json
{
  "mcpServers": {
    "pdf-toolkit": {
      "command": "python",
      "args": ["C:/Users/LOX/Documents/pdf-toolkit/pdf-toolkit/mcp/server.py"]
    }
  }
}
```

## Тулы (17 в v0.1)
- `pdf_merge` — склеить 2-10 PDF
- `pdf_split` — извлечь страницы в zip
- `pdf_compress` — сжать low/medium/high
- `pdf_rotate` — поворот 90/180/270
- `pdf_delete_pages` — удалить страницы
- `pdf_watermark` — текст/картинка
- `pdf_to_jpg` / `jpg_to_pdf`
- `word_to_pdf` / `pdf_to_word` / `pdf_to_excel` / `pdf_to_ppt` / `excel_to_pdf` / `ppt_to_pdf`
- `ocr_pdf` — скан → searchable
- `pdf_protect` / `pdf_unlock`

Примеры промптов агенту:
- "Склей все PDF в /tmp/pdfs в один"
- "Сожми /tmp/big.pdf c low качеством"
- "Сделай из /tmp/scan.pdf searchable с русским языком"

## Проверка
```bash
python -m py_compile server.py
npx @modelcontextprotocol/inspector python server.py
```

## Монетизация потом
Когда наберет звезды/юзеров — добавим хостед версию `https://your-domain.com/mcp` (Streamable HTTP + API-key $5/мес) без установки LibreOffice/Tesseract. Локальная останется бесплатной (open core).

## Публикация (free marketing)
- GitHub публичный репо с тэгом `mcp`
- mcp.so, Smithery, PulseMCP — листинг
- Пост на ProductHunt / Reddit r/ClaudeAI
