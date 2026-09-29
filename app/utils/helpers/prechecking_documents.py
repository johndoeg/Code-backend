from __future__ import annotations

import os
import tempfile
import uuid

from app import db
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from flask import current_app
from sqlalchemy import text
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

try:
    from app.utils.helpers.aws_helpers import aws_upload_file, aws_delete_file, _aws_presign
except ImportError:
    import boto3

    def _s3_client():
        return boto3.client("s3")

    def aws_upload_file(bucket: str, key: str, local_path: str) -> None:
        _s3_client().upload_file(local_path, bucket, key)

    def aws_delete_file(bucket: str, key: str) -> None:
        _s3_client().delete_object(Bucket=bucket, Key=key)

    def _aws_presign(aws_key: str, file_name: str, expires_in: int = 300) -> str:
        return _s3_client().generate_presigned_url(
            "get_object",
            Params={
                "Bucket": current_app.config["AWS_S3_BUCKET"],
                "Key": aws_key,
                "ResponseContentDisposition": f'attachment; filename="{file_name}"',
            },
            ExpiresIn=expires_in,
        )
class DocumentError(Exception):
    """"""

_GUARANTOR_ORGANIZATION_TYPES = {"GUARNPR", "GUARNPT"}

@dataclass(frozen=True)
class DocumentTypeConfig:
    prefix: str
    organization_type: str
    subfolder: str
    multiple: bool
    max_file_size_mb: Optional[int] = None

_DOC_META: dict[str, DocumentTypeConfig] = {
    "cust-ktp": DocumentTypeConfig(
        prefix="-CUST_KTP-", organization_type="PR", subfolder="DATA_DIRI/KTP", multiple=False,
    ),
    "cust-spouse-ktp": DocumentTypeConfig(
        prefix="-CUST_SPOUSE_KTP-", organization_type="PR", subfolder="DATA_DIRI/KTP", multiple=False,
    ),
    "cust-kk": DocumentTypeConfig(
        prefix="-CUST_KK-", organization_type="PR", subfolder="DATA_DIRI/KK", multiple=True,
    ),
    "cust-npwp": DocumentTypeConfig(
        prefix="-CUST_NPWP-", organization_type="PR", subfolder="DATA_DIRI/NPWP", multiple=True,
    ),
    "cust-marriage-or-death-statement": DocumentTypeConfig(
        prefix="-CUST-MARRIAGE_OR_DEATH_STATEMENT-", organization_type="PR",
        subfolder="DATA_DIRI/AKTA_CERAI_MATI", multiple=True,
    ),
    "cust-kitas": DocumentTypeConfig(
        prefix="-CUST_KITAS-", organization_type="PR", subfolder="DATA_DIRI/KITAS", multiple=False,
    ),
    "cust-spouse-kitas": DocumentTypeConfig(
        prefix="-CUST_SPOUSE_KITAS-", organization_type="PR", subfolder="DATA_DIRI/KITAS_PASANGAN", multiple=False,
    ),
    "cust-wna-spouse-ktp": DocumentTypeConfig(
        prefix="-CUST_WNA_SPOUSE_KTP-", organization_type="PR", subfolder="DATA_DIRI/KTP_PASANGAN", multiple=False,
    ),
    "guarantor-ktp": DocumentTypeConfig(
        prefix="-GUARANTOR_KTP-", organization_type="GUARNPR", subfolder="DATA_GUARANTOR/KTP", multiple=False,
    ),
    "guarantor-spouse-ktp": DocumentTypeConfig(
        prefix="-GUARANTOR_SPOUSE_KTP-", organization_type="GUARNPR", subfolder="DATA_GUARANTOR/KTP", multiple=False,
    ),
    "guarantor-kk": DocumentTypeConfig(
        prefix="-GUARANTOR_KK-", organization_type="GUARNPR", subfolder="DATA_GUARANTOR/KK", multiple=True,
    ),
    "guarantor-npwp": DocumentTypeConfig(
        prefix="-GUARANTOR_NPWP-", organization_type="GUARNPR", subfolder="DATA_GUARANTOR/NPWP", multiple=True,
    ),
    "guarantor-marriage-or-death-statement": DocumentTypeConfig(
        prefix="-GUARNTOR-MARRIAGE_OR_DEATH_STATEMENT-", organization_type="GUARNPR",
        subfolder="DATA_GUARANTOR/AKTA_CERAI_MATI", multiple=True,
    ),
    "guarantor-kitas": DocumentTypeConfig(
        prefix="-GUARANTOR_KITAS-", organization_type="GUARNPR", subfolder="DATA_GUARANTOR/KITAS", multiple=False,
    ),
    "guarantor-spouse-kitas": DocumentTypeConfig(
        prefix="-GUARANTOR_SPOUSE_KITAS-", organization_type="GUARNPR",
        subfolder="DATA_GUARANTOR/KITAS_PASANGAN", multiple=False,
    ),
    "guarantor-wna-spouse-ktp": DocumentTypeConfig(
        prefix="-GUARANTOR_WNA_SPOUSE_KTP-", organization_type="GUARNPR",
        subfolder="DATA_GUARANTOR/KTP_PASANGAN", multiple=False,
    ),
}

ALLOWED_DOCUMENT_TYPES = frozenset(_DOC_META.keys())

_SPECIAL_CHAR_MAP: dict[str, str] = {
    "&": "", "$": "", "@": "", "=": "", ";": "", ":": "", "/": "", "+": "", ",": "", "?": "", "%": "",
    " ": "_",
    "\u00A0": "_",  # non-breaking space
    "\u2002": "_",  # en space
    "\u2003": "_",  # em space
    "\u2009": "_",  # thin space
    "\u200B": "_",  # zero-width space
    "\u2007": "_",  # figure space
    "\u3000": "_",  # ideographic space
}

def sanitize_filename(original_filename: str) -> str:
    result = original_filename
    for old, new in _SPECIAL_CHAR_MAP.items():
        result = result.replace(old, new)
    return result

_ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/pjpeg", "image/x-png", "image/png", "image/gif",
    "image/bmp", "image/heic", "image/heif", "application/download",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

def validate_document_file(
    mimetype: str,
    size_bytes: int,
    max_file_size_mb: Optional[int] = None,
) -> Optional[str]:
    if mimetype not in _ALLOWED_MIME_TYPES:
        return "Invalid uploaded file format."
    if mimetype == "application/pdf":
        return None

    if max_file_size_mb is None:
        max_file_size_mb = current_app.config["DEFAULT_MAX_FILE_SIZE_MB"]

    if max_file_size_mb != 0 and size_bytes > max_file_size_mb * 1024 * 1024:
        return f"File size exceeded maximum allowed file size ({max_file_size_mb}MB)."
    return None

def build_stored_filename(prechecking_id: str, prefix: str, original_filename: str) -> str:
    return f"{prechecking_id}{prefix}{sanitize_filename(original_filename)}"

def build_aws_key(apless: str, prechecking_id: str, subfolder: str, stored_filename: str, organization_type: str) -> str:
    base = f"{apless}/{prechecking_id}/{subfolder}/{stored_filename}"
    if organization_type in _GUARANTOR_ORGANIZATION_TYPES:
        return f"upload_doc/guarantor/{base}"
    return f"upload_doc/{base}"

def _file_size(file: FileStorage) -> int:
    stream = file.stream
    pos = stream.tell()
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(pos)

    return size

def save_prechecking_document(
    file: Optional[FileStorage],
    apless: str,
    prechecking_id: str,
    document_type: str,
    username: str,
) -> dict:

    if document_type not in _DOC_META:
        raise DocumentError(f"Unknown document type: {document_type}")
    if not file or not file.filename:
        raise DocumentError("No file provided")

    config = _DOC_META[document_type]

    max_file_size_mb = config.max_file_size_mb
    if max_file_size_mb is None:
        max_file_size_mb = current_app.config["DEFAULT_MAX_FILE_SIZE_MB"]

    validation_error = validate_document_file(file.mimetype or "", _file_size(file), max_file_size_mb)
    if validation_error:
        raise DocumentError(validation_error)

    stored_filename = build_stored_filename(prechecking_id, config.prefix, file.filename)
    aws_key = build_aws_key(apless, prechecking_id, config.subfolder, stored_filename, config.organization_type)
    bucket = current_app.config["AWS_S3_BUCKET"]

    tmp_name = f"{uuid.uuid4().hex}_{secure_filename(file.filename) or 'upload'}"
    tmp_path = os.path.join(tempfile.gettempdir(), tmp_name)
    file.save(tmp_path)
    try:
        aws_upload_file(bucket, aws_key, tmp_path)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    if not config.multiple:
        _replace_existing_document(prechecking_id, document_type, bucket)

    result = db.session.execute(text("""
        INSERT INTO TEMP_CUSTOMER_DOCUMENT
            (Apless, Prechecking_Id, DocumentName, OrganizationType, DocumentType, NumberOfDocuments, CreatedBy, CreatedDate, AWSKey)
        OUTPUT INSERTED.CustomerDocumentId
        VALUES (:apless, :pid, :name, :org_type, :dt, 1, :by, :created, :aws_key)
    """), {
        "apless": apless,
        "pid": prechecking_id,
        "name": stored_filename,
        "org_type": config.organization_type,
        "dt": document_type,
        "by": username,
        "created": datetime.utcnow(),
        "aws_key": aws_key,
    }).fetchone()
    db.session.commit()

    return {"id": result.CustomerDocumentId, "name": stored_filename, "awsKey": aws_key}

def _replace_existing_document(prechecking_id: str, document_type: str, bucket: str) -> None:
    existing_rows = db.session.execute(text("""
        SELECT CustomerDocumentId, AWSKey FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
        WHERE Prechecking_Id = :pid AND DocumentType = :dt
    """), {"pid": prechecking_id, "dt": document_type}).fetchall()

    if not existing_rows:
        return

    for row in existing_rows:
        try:
            aws_delete_file(bucket, row.AWSKey)
        except Exception:
            current_app.logger.exception("Failed removing old S3 object %s", row.AWSKey)

    db.session.execute(text("""
        DELETE FROM TEMP_CUSTOMER_DOCUMENT WHERE Prechecking_Id = :pid AND DocumentType = :dt
    """), {"pid": prechecking_id, "dt": document_type})

def remove_prechecking_document(
    prechecking_id: str,
    document_type: str,
    customer_document_id: Optional[int] = None,
) -> None:

    params = {"pid": prechecking_id, "dt": document_type}
    where = "Prechecking_Id = :pid AND DocumentType = :dt"
    if customer_document_id is not None:
        params["doc_id"] = customer_document_id
        where += " AND CustomerDocumentId = :doc_id"

    rows = db.session.execute(text(f"""
        SELECT CustomerDocumentId, AWSKey FROM
        TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
        WHERE {where}
    """), params).fetchall()

    if not rows:
        raise DocumentError("Document not found")

    bucket = current_app.config["AWS_S3_BUCKET"]
    for row in rows:
        try:
            aws_delete_file(bucket, row.AWSKey)
        except Exception:
            current_app.logger.exception("Failed removing S3 object %s", row.AWSKey)

    db.session.execute(text(f"DELETE FROM TEMP_CUSTOMER_DOCUMENT WHERE {where}"), params)
    db.session.commit()