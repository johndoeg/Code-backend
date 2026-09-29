import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text

from app import db
from models.customer_document import CustomerDocument
from app.utils.helpers.aws_helpers import build_key, upload_fileobj, delete_object, _validate_file, _aws_presign

S3_KEY_NAMESPACE = "customer-documents"

DOC_TYPE_NON = "non"

_DIRECTOR_KTP_RE = re.compile(r"^corp-ocr-ktp_(\d+)$")
_WNA_BOARD_RE = re.compile(r"^wna-corp-board_(\d+)$")

def get_lessee_category(apless: str) -> Optional[str]:
   
    row = db.session.execute(
        text("SELECT Lessee_Cat FROM CAFLESS WITH (NOLOCK) WHERE APLESS = :apless"),
        {"apless": apless},
    ).first()
    return row.Lessee_Cat if row else None

def _record_upload_audit_log(username: str, applno: str, apless: str, document_type: str, file_name: str) -> None:
    pass

def upload_customer_document(
    file_storage,
    document_type: str,
    prefix: str,
    applno: str,
    apless: str,
    organization_type: str,
    subfolder: str,
    username: str = "",
    grnid: str = "",
    max_file_size_mb: float = 2,
) -> tuple[str, Optional[dict]]:
   
    if file_storage is None or not file_storage.filename:
        return "No file selected.", None

    data = file_storage.read()
    error = _validate_file(data, file_storage.filename, int(max_file_size_mb) if max_file_size_mb else 0)
    if error:
        return error, None

    key = build_key(prefix=S3_KEY_NAMESPACE, applno=applno, sub_type=subfolder, filename=file_storage.filename)

    file_storage.stream.seek(0)
    if not upload_fileobj(key, file_storage.stream):
        return "Upload failed.", None

    doc = CustomerDocument(
        appl_no=applno,
        apless=apless,
        file_document=file_storage.filename,
        organization_type=organization_type,
        doc_no=1,
        doc_type=DOC_TYPE_NON,
        document_type=document_type,
        upload_dt=datetime.now(timezone.utc),
        aws_key=key,
        grnid=grnid or None,
    )
    db.session.add(doc)
    db.session.commit()

    _record_upload_audit_log(username, applno, apless, document_type, file_storage.filename)

    return "", doc.to_dict()

def delete_customer_document(id_customer_document: int) -> bool:
    doc = db.session.get(CustomerDocument, id_customer_document)
    if not doc:
        return False
    if doc.aws_key:
        delete_object(doc.aws_key)
    db.session.delete(doc)
    db.session.commit()
    return True

def get_document_view_url(id_customer_document: int) -> Optional[str]:
    
    doc = db.session.get(CustomerDocument, id_customer_document)
    if not doc or not doc.aws_key:
        return None
    return _aws_presign(doc.aws_key, doc.file_document)

def list_customer_documents(applno: str, apless: str, organization_type: str) -> dict:
   
    docs = (
        CustomerDocument.query
        .filter(
            CustomerDocument.organization_type == organization_type,
            CustomerDocument.doc_type == DOC_TYPE_NON,
            CustomerDocument.appl_no == applno,
            CustomerDocument.apless == apless,
            CustomerDocument.apless.isnot(None),
        )
        .order_by(CustomerDocument.document_type, CustomerDocument.upload_dt.desc())
        .all()
    )

    grouped: dict[str, list[dict]] = {}
    director_docs: list[dict] = []
    board_docs: list[dict] = []

    for doc in docs:
        if not doc.file_document or doc.file_document == "-":
            continue

        dtype = doc.document_type or ""
        director_match = _DIRECTOR_KTP_RE.match(dtype)
        board_match = _WNA_BOARD_RE.match(dtype)

        if director_match:
            director_docs.append({**doc.to_dict(), "index": int(director_match.group(1))})
        elif board_match:
            board_docs.append({**doc.to_dict(), "index": int(board_match.group(1))})
        else:
            grouped.setdefault(dtype, []).append(doc.to_dict())

    director_docs.sort(key=lambda d: d["index"])
    board_docs.sort(key=lambda d: d["index"])

    return {
        "documents": grouped,
        "directorDocuments": director_docs,
        "boardDocuments": board_docs,
        "nextDirectorIndex": max((d["index"] for d in director_docs), default=-1) + 1,
        "nextBoardIndex": max((d["index"] for d in board_docs), default=-1) + 1,
        "hasAnyDocument": bool(docs),
    }