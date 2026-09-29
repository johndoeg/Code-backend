import glob
import os
import re

from pathlib import Path
from sqlalchemy import text

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif'}
ATTACHMENT_EXTENSIONS = IMAGE_EXTENSIONS | {'.pdf', '.doc', '.docx'}
PPATK_EXTENSIONS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png'}

RESIZE_WIDTH = 1024
RESIZE_QUALITY = 70

def check_id_card_status(db, id_card):
    row = db.session.execute(
        text("""
            SELECT Flag_Type FROM MCMOWATCHLIST WITH(NOLOCK)
            WHERE FlagDel = 0 AND (Flag_Type = 'W' OR Flag_Type = 'B')
              AND ID_Card = :id_card AND ID_Card IS NOT NULL AND ID_Card <> ''
        """),
        {"id_card": id_card}
    ).fetchone()

    if row:
        if row.Flag_Type == 'W':
            return False, "ID Card is exist in Watchlist"
        if row.Flag_Type == 'B':
            return False, "ID Card is exist in Blacklist"
    return True, ""

def check_npwp_status(db, npwp):
    row = db.session.execute(
        text("""
            SELECT Flag_Type FROM MCMOWATCHLIST WITH(NOLOCK)
            WHERE FlagDel = 0 AND (Flag_Type = 'W' OR Flag_Type = 'B')
              AND NPWP = :npwp AND NPWP IS NOT NULL AND NPWP <> ''
        """),
        {"npwp": npwp}
    ).fetchone()

    if row:
        if row.Flag_Type == 'W':
            return False, "NPWP is exist in Watchlist"
        if row.Flag_Type == 'B':
            return False, "NPWP is exist in Blacklist"
    return True, ""

def save_blacklist_image(file, name_prefix, apless, upload_root):
    ext = os.path.splitext(file.filename)[1]
    safe_prefix = re.sub(r'[^a-zA-Z0-9_-]', '_', name_prefix)
    filename = f"{apless}{safe_prefix}{ext}"
    folder = os.path.join(upload_root, apless)
    os.makedirs(folder, exist_ok=True)
    file.save(os.path.join(folder, filename))
    
    return filename

def save_general_attachment(file, name_prefix, apless, upload_root):
    ext = os.path.splitext(file.filename)[1]
    filename = f"{name_prefix}{ext}"
    folder = os.path.join(upload_root, apless)
    os.makedirs(folder, exist_ok=True)
    file.save(os.path.join(folder, filename))
    
    return filename

def _split_extension(filename: str) -> tuple:
    stem, ext = os.path.splitext(os.path.basename(filename or ''))
    return stem, ext.lower()

def _safe_component(value: str) -> str:
    cleaned = re.sub(r'[^A-Za-z0-9._-]+', '_', (value or '').strip())
    cleaned = cleaned.strip('._-')
    return cleaned[:80]

def _resolve_folder(base_folder: str, subdir: str = None) -> Path:
    if not base_folder:
        raise ValueError("Upload folder is not configured")

    base = Path(base_folder).resolve()
    if not subdir:
        return base

    folder = (base / _safe_component(subdir)).resolve()
    if base not in folder.parents:
        raise ValueError("Resolved upload folder escapes the upload root")
    return folder

def _store(file, folder: Path, new_name: str) -> str:
    folder.mkdir(parents=True, exist_ok=True)
    file.save(str(folder / new_name))
    return new_name

def save_blacklist_image(file, suffix: str, apless: str, base_folder: str, resize: bool = False) -> str:
    _, ext = _split_extension(file.filename)
    if ext not in IMAGE_EXTENSIONS:
        raise ValueError(f"Unsupported image type: {ext or 'no extension'}")

    folder = _resolve_folder(base_folder)
    new_name = f"{_safe_component(apless)}{_safe_component(suffix)}{ext}"
    stored = _store(file, folder, new_name)

    if resize:
        resize_image(folder / stored)

    return stored

def save_general_attachment(file, prefix: str, apless: str, base_folder: str) -> str:
    _, ext = _split_extension(file.filename)
    if ext not in ATTACHMENT_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext or 'no extension'}")

    folder = _resolve_folder(base_folder, apless)
    new_name = f"{_safe_component(prefix)}{ext}"
    return _store(file, folder, new_name)

def delete_blacklist_file(filename: str, base_folder: str, subdir: str = None) -> bool:
   
    if not filename or not base_folder:
        return False

    try:
        folder = _resolve_folder(base_folder, subdir)
    except ValueError:
        return False

    stem, ext = _split_extension(filename)
    if not stem or not ext:
        return False

    deleted = 0

    for path in glob.glob(os.path.join(str(folder), glob.escape(stem) + ".*")):
        target = Path(path).resolve()
        if not target.is_file() or target.parent != folder:
            continue
        try:
            target.unlink()
            deleted += 1
        except FileNotFoundError:
            pass

    return deleted > 0

def resize_image(path, width: int = RESIZE_WIDTH, quality: int = RESIZE_QUALITY) -> None:
    from PIL import Image

    path = Path(path)
    with Image.open(path) as img:
        img.load()
        if img.width <= width:
            return

        height = round(img.height * width / img.width)
        resized = img.resize((width, height), Image.LANCZOS)

        if img.format == 'JPEG':
            resized.convert('RGB').save(path, 'JPEG', quality=quality)
        else:
            resized.save(path, img.format)
            
def save_ppatk_file(file, prefix: str, base_folder: str) -> str:
    _, ext = _split_extension(file.filename)
    if ext not in PPATK_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext or 'no extension'}")

    folder = _resolve_folder(base_folder)
    return _store(file, folder, f"{_safe_component(prefix)}{ext}")