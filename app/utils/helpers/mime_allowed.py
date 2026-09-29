from __future__ import annotations

import mimetypes

_ALLOWED_MIME = {
    "image/jpeg", "image/pjpeg", "image/x-png", "image/png",
    "image/gif", "image/bmp", "image/heic", "image/heif",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/download",
}
_MAX_MB = 2

def _validate_file(file_bytes: bytes, filename: str, max_mb: int = _MAX_MB) -> str:
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    if mime not in _ALLOWED_MIME:
        return "Invalid file format. Allowed: PNG, JPG, PDF, TIFF, BMP, GIF, HEIC, XLSX, DOCX."
    if mime != "application/pdf" and len(file_bytes) > max_mb * 1024 * 1024:
        return f"File size exceeds {max_mb} MB limit."
    return ""