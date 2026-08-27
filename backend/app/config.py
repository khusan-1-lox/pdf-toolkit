import os
import tempfile

MAX_FILE_SIZE = 50 * 1024 * 1024
MAX_FILES = 10
RETENTION_SECONDS = 300
TMP_ROOT = os.getenv("TMP_ROOT", tempfile.gettempdir() + "/pdf-toolkit")
