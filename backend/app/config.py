import os
import tempfile

MAX_FILE_SIZE = 100 * 1024 * 1024 * 1024  # 100 GB (no artificial 50 MB limit)
MAX_FILES = 100_000                       # No artificial 10-file limit
RETENTION_SECONDS = 300
TMP_ROOT = os.getenv("TMP_ROOT") or os.getenv("PDF_TOOLKIT_TMP_DIR") or os.path.join(tempfile.gettempdir(), "pdf-toolkit")
