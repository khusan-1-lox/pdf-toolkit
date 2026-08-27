FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libreoffice-writer libreoffice-calc libreoffice-impress tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md ./
COPY server.py ./
RUN pip install --no-cache-dir mcp==1.29.1 pydantic pypdf PyMuPDF Pillow python-docx openpyxl python-pptx pdf2docx pdfplumber pikepdf WeasyPrint pytesseract
ENTRYPOINT ["python", "server.py"]
