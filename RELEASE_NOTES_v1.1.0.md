# 🚀 PDF Toolkit v1.1.0 — Большое обновление Desktop `.exe`, Визуального Редактора и 31+ инструмента

## 🇷🇺 Описание обновления (RU)

### 1. 🖥️ Полноценный установщик для ПК (Windows `.exe`) + Автообновление с GitHub
- **Установщик `PDF-Toolkit-Setup-1.1.0-x64.exe`**: устанавливается как стандартная программа Windows с выбором папки установки, созданием ярлыков на Рабочем столе и в меню «Пуск», а также штатным деинсталлятором.
- **Портативная версия `PDF-Toolkit-Portable-1.1.0-x64.exe`**: запуск из одного файла без установки.
- **Двойное автообновление с GitHub (`khusan-1-lox/pdf-toolkit`)**:
  - При выходе нового релиза на GitHub программа автоматически скачивает свежий установщик, тихо обновляется и перезапускается.
  - При пуше новых коммитов в ветку `main` программа автоматически подтягивает обновлённый бэкенд на лету (Hot-Update) без необходимости переустанавливать `.exe`.
- **Работа на чистых ПК без установленного Python**: если у пользователя на компьютере нет Python, при первом запуске приложение автоматически разворачивает изолированный портативный Python 3.12 и все необходимые PDF-библиотеки.

### 2. 🎨 Новый интерактивный редактор и рабочее пространство (`ToolWorkspace` & `DocumentEditor`)
- Живой предпросмотр всех страниц PDF с масштабированием.
- Интерактивное наложение элементов прямо поверх страницы (`PageOverlay`):
  - Перетаскивание текста, изображений, штампов, прямоугольников и рисование от руки.
  - Визуальное размещение собственной подписи (нарисованной мышкой/стилусом или загруженной из картинки).
  - Визуальное выделение рамки обрезки (`Crop`) и областей скрытия конфиденциальных данных (`Redact`).
  - Drag-and-drop сортировка страниц, поворот отдельных страниц и вставка пустых листов.

### 3. 🆕 Новые инструменты (всего 31+ инструмент)
- **Редактор PDF (`Edit PDF`)** — добавление текста (включая кириллицу), картинок, фигур и рисунков на любые страницы.
- **PDF-формы (`PDF Forms / AcroForms`)** — чтение, заполнение существующих интерактивных форм и создание новых текстовых полей и галочек.
- **PDF в Markdown (`PDF to Markdown`)** — конвертация PDF-документов в чистую разметку Markdown с автоматическим определением заголовков и списков.
- **Организовать PDF (`Organize PDF`)** и **Извлечь страницы (`Extract Pages`)** — гибкая сборка документа из нужных страниц.
- **Сканировать в PDF (`Scan to PDF`)** и **Цепочки действий (`Workflows`)** — выполнение нескольких операций над PDF за один шаг.

### 4. 🔒 Безопасность и качество обработки
- Защита конвертера `HTML в PDF` от SSRF/LFI и DNS-rebinding (разрешены только публичные HTTP/HTTPS ресурсы с проверкой IP).
- Настоящее физическое удаление текста и графики в `Redact PDF` (`apply_redactions`).
- Улучшенное сжатие `Compress PDF`, сравнение двух PDF бок о бок (`Compare PDF`) с подсветкой отличий и полная поддержка русского/английского интерфейса.

---

## 🇬🇧 Release Notes (EN)

- **Windows Desktop Installer (`PDF-Toolkit-Setup-1.1.0-x64.exe`) & Portable `.exe`** with built-in **GitHub Auto-Updater** (automatically pulls new GitHub Releases as well as hot-updates from the `main` branch) and automatic portable Python 3.12 setup on clean Windows machines.
- **Interactive Visual Workspace (`DocumentEditor`, `PageOverlay`, `ToolWorkspace`)** for WYSIWYG page editing, signing, cropping, redacting, and drag-and-drop page organization.
- **Expanded to 31+ PDF Tools + Workflows**: added **Edit PDF**, **PDF Forms (AcroForms)**, **PDF to Markdown**, **Organize PDF**, **Extract Pages**, **Scan to PDF**, and **Multi-step Workflows**.
- **Security & Quality Upgrades**: IP-pinned SSRF protection in `HTML to PDF`, true content stream removal in `Redact PDF`, Cyrillic font rendering in watermarks/editor, and comprehensive test coverage.
