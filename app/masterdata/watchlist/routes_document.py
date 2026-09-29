from __future__ import annotations

import mimetypes
import os

from flask import Blueprint, abort, current_app, send_file
from app.auth.decorators import login_required

attachment_files_bp = Blueprint('attachment_files', __name__, url_prefix='/MasterData')

_DOWNLOAD_EXTENSIONS = {'.doc', '.docx', '.xls', '.xlsx'}
_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tif', '.tiff'}

def _safe_filename(filename: str) -> str:
    base = os.path.basename(filename)
    if not base or base != filename or '..' in filename:
        abort(400, description='Invalid filename')
    return base

@attachment_files_bp.route('/files/ppatk/<path:filename>')
@login_required
def serve_ppatk_file(filename: str):
    safe_name = _safe_filename(filename)

    upload_dir = current_app.config.get('PPATK_UPLOAD_DIR')
    if not upload_dir:
        abort(500, description='PPATK_UPLOAD_DIR is not configured')

    full_path = os.path.join(upload_dir, safe_name)

    if not os.path.abspath(full_path).startswith(os.path.abspath(upload_dir)):
        abort(400, description='Invalid filename')

    if not os.path.isfile(full_path):
        abort(404)

    ext = os.path.splitext(safe_name)[1].lower()

    if ext == '.pdf':
        return send_file(full_path, mimetype='application/pdf')

    if ext in _DOWNLOAD_EXTENSIONS:
        return send_file(full_path, as_attachment=True, download_name=safe_name)

    if ext in _IMAGE_EXTENSIONS:
        mime, _ = mimetypes.guess_type(safe_name)
        return send_file(full_path, mimetype=mime or 'application/octet-stream')

    return send_file(full_path, as_attachment=True, download_name=safe_name)