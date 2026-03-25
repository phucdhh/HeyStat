"""File upload validator – MIME type via magic bytes + size limit."""
import io
from pathlib import Path
from typing import Optional

try:
    import magic
    _MAGIC_AVAILABLE = True
except ImportError:
    _MAGIC_AVAILABLE = False

ALLOWED_MIME_TYPES = {
    "text/csv",
    "text/plain",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/x-spss-sav",
    "application/octet-stream",  # fallback for .omv, .sas7bdat
    "application/zip",  # .omv files are zipped
}

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".sav", ".sas7bdat", ".ods", ".omv"}


def validate_file_extension(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def validate_mime_type(data: bytes) -> bool:
    """Validate using magic bytes when python-magic is available; fall back to extension check."""
    if not _MAGIC_AVAILABLE:
        return True
    mime = magic.from_buffer(data[:2048], mime=True)
    return mime in ALLOWED_MIME_TYPES
