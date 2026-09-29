import json as _json
import base64
import mimetypes
import os
import requests
from flask import Blueprint, current_app, jsonify, request, session

from botocore.exceptions import BotoCoreError, ClientError

from app import db
from app.auth.decorators import login_required
from sqlalchemy import text

from app.utils.helpers.aws_helpers import (
    _aws_upload, _aws_delete, _aws_presign, _validate_file,
)

ocr_bp = Blueprint("prechecking_ocr", __name__, url_prefix="/Prechecking/OCR")

def _username() -> str:
    return session.get("username", "system")

def _glair_headers() -> dict:
    cfg = current_app.config
    token = base64.b64encode(
        f"{cfg['GLAIR_USERNAME']}:{cfg['GLAIR_PASSWORD']}".encode()
    ).decode()
    return {
        "x-api-key": cfg["GLAIR_API_KEY"],
        "Authorization": f"Basic {token}",
    }

_DOC_META: dict[str, tuple[str, str]] = {
    "cust-ktp":                         ("-CUST_KTP-",                        "DATA_DIRI/KTP"),
    "cust-spouse-ktp":                  ("-CUST_SPOUSE_KTP-",                 "DATA_DIRI/KTP"),
    "cust-kk":                          ("-CUST_KK-",                         "DATA_DIRI/KK"),
    "cust-npwp":                        ("-CUST_NPWP-",                       "DATA_DIRI/NPWP"),
    "cust-marriage-or-death-statement": ("-CUST-MARRIAGE_OR_DEATH_STATEMENT-", "DATA_DIRI/AKTA_CERAI_MATI"),
    "cust-kitas":                       ("-CUST_KITAS-",                      "DATA_DIRI/KITAS"),
    "cust-spouse-kitas":                ("-CUST_SPOUSE_KITAS-",               "DATA_DIRI/KITAS_PASANGAN"),
    "cust-wna-spouse-ktp":              ("-CUST_WNA_SPOUSE_KTP-",             "DATA_DIRI/KTP_PASANGAN"),
}

def _log_ocr(
    prechecking_id: str,
    username: str,
    request_type: str,
    request_body: str,
    response_body: str,
    status_code: int,
    request_id: str | None,
) -> None:
    try:
        db.session.execute(
            text("""
                INSERT INTO [DataLog].[dbo].[Log_OCR]
                    (Prechecking_Id, Username, RequestType, RequestDt,
                     RequestBody, ResponseBody, Status_Code, RequestID)
                VALUES (:pid, :user, :rtype, GETDATE(), :req, :res, :code, :rid)
            """),
            {
                "pid":   prechecking_id,
                "user":  username,
                "rtype": request_type,
                "req":   request_body,
                "res":   response_body,
                "code":  status_code,
                "rid":   request_id,
            },
        )
        db.session.commit()
    except Exception:
        current_app.logger.exception("OCR log insert failed")
        db.session.rollback()

@ocr_bp.route("/scanOCRCustomer", methods=["POST"])
@login_required
def scan_ocr_customer():
   
    param          = request.form.get("param", "")
    prechecking_id = request.form.get("prechecking_id", "")
    username       = _username()

    if param == "check_qualities":
        return _check_qualities(prechecking_id, username)

    if param == "ocr_customer":
        return _ocr_customer(prechecking_id, username)

    if param == "check_data_duckapil":
        return _check_data_dukcapil(prechecking_id, username)

    return jsonify({"status": "ERROR", "reason": "Unknown param"}), 400

def _check_qualities(prechecking_id: str, username: str):
    
    cfg = current_app.config
    glair_qualities = cfg["GLAIR_ENDPOINT_QUALITIES"]
    
    if "image" not in request.files:
        return jsonify({"status": "ERROR", "reason": "No image uploaded"}), 400

    f          = request.files["image"]
    file_bytes = f.read()
    filename   = f.filename or "upload.jpg"

    err = _validate_file(file_bytes, filename)
    if err:
        return jsonify({"status": "ERROR", "reason": err}), 400

    resp = requests.post(
        glair_qualities,
        headers=_glair_headers(),
        files={"image": (filename, file_bytes, f.mimetype)},
        timeout=30,
    )
    request_id    = resp.headers.get("request-id")
    response_body = resp.text

    _log_ocr(
        prechecking_id, username, "Qualities",
        f"data:image/{os.path.splitext(filename)[1].lstrip('.')};base64,"
        + base64.b64encode(file_bytes).decode(),
        response_body,
        resp.status_code,
        request_id,
    )

    return (response_body, resp.status_code, {"Content-Type": "application/json"})

def _ocr_customer(prechecking_id: str, username: str):
    if "image" not in request.files:
        return jsonify({"status": "ERROR", "reason": "No image uploaded"}), 400

    f          = request.files["image"]
    file_bytes = f.read()
    filename   = f.filename or "upload.jpg"

    err = _validate_file(file_bytes, filename)
    if err:
        return jsonify({"status": "ERROR", "reason": err}), 400

    cfg = current_app.config
    resp = requests.post(
        cfg["GLAIR_ENDPOINT_OCR"],
        headers=_glair_headers(),
        files={"image": (filename, file_bytes, f.mimetype)},
        timeout=30,
    )
    request_id = resp.headers.get("request-id")

    body_dict = resp.json() if resp.ok else {}
    
    log_copy          = {k: v for k, v in body_dict.items() if k != "images"}
    response_body_log = _json.dumps(log_copy, ensure_ascii=False)

    _log_ocr(
        prechecking_id, username, "OCR",
        f"data:image/{os.path.splitext(filename)[1].lstrip('.')};base64,"
        + base64.b64encode(file_bytes).decode(),
        response_body_log,
        resp.status_code,
        request_id,
    )

    return (resp.text, resp.status_code, {"Content-Type": "application/json"})

def _check_data_dukcapil(prechecking_id: str, username: str):
    fields = [
        "nik", "name", "place_of_birth", "date_of_birth",
        "gender", "address", "rt", "rw", "subdistrict",
        "district", "city", "province", "job_type", "marital_status",
    ]

    payload = {f: (request.form.get(f, "") or "null") for f in fields}

    cfg = current_app.config
    resp = requests.post(
        cfg["GLAIR_ENDPOINT_DUKCAPIL"],
        headers=_glair_headers(),
        files={k: (None, v) for k, v in payload.items()},
        timeout=30,
    )
    request_id = resp.headers.get("request-id")

    _log_ocr(
        prechecking_id, username, "Dukcapil",
        _json.dumps(payload, ensure_ascii=False),
        resp.text,
        resp.status_code,
        request_id,
    )

    try:
        data = resp.json()
        if (
            not data.get("verification_status")
            and "Something wrong in Dukcapil server" in (data.get("reason") or "")
        ):
            _notify_dukcapil_error()
    except Exception:
        pass

    return (resp.text, 200, {"Content-Type": "application/json"})

def _notify_dukcapil_error() -> None:
    try:
        rows = db.session.execute(
            text("SELECT TelegramID FROM EMPLOYEE_DATA WHERE Employee_ID IN ('2402104','2405111')")
        ).fetchall()
        for row in rows:
            tid = row.TelegramID
            if tid:
                _send_telegram(tid, "Something wrong in Dukcapil server!")
    except Exception:
        current_app.logger.exception("Telegram notify error")

def _send_telegram(chat_id: str, message: str) -> None:
    token = current_app.config.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message},
            timeout=5,
        )
    except Exception:
        pass

@ocr_bp.route("/upload-document", methods=["POST"])
@login_required
def upload_document():
   
    username          = _username()
    apless            = request.form.get("apless", "")
    prechecking_id    = request.form.get("prechecking_id", "")
    document_type     = request.form.get("document_type", "")
    cust_type         = request.form.get("cust_type", "PR")
    organization_type = request.form.get("organization_type", "PR")
    lessee_type       = request.form.get("lessee_type", "")

    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file provided"}), 400

    f          = request.files["file"]
    original   = f.filename or "upload"
    file_bytes = f.read()

    err = _validate_file(file_bytes, original)
    if err:
        return jsonify({"success": False, "message": err}), 400

    name_prefix, doc_subfolder = _DOC_META.get(
        document_type,
        (f"-{document_type.upper().replace('-', '_')}-", document_type),
    )
    doc_name     = f"{prechecking_id}{name_prefix}{original}"
    is_guarantor = organization_type in ("GUARNPR", "GUARNPT")
    aws_prefix   = "upload_doc/guarantor" if is_guarantor else "upload_doc"
    aws_key      = f"{aws_prefix}/{apless}/{prechecking_id}/{doc_subfolder}/{doc_name}"
    content_type = mimetypes.guess_type(original)[0] or "application/octet-stream"

    try:
        existing = db.session.execute(
            text("""
                SELECT CustomerDocumentId, AWSKey
                FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
                WHERE Prechecking_Id = :pid
                    AND DocumentType   = :dtype
                    AND Apless IS NOT NULL
            """),
            {"pid": prechecking_id, "dtype": document_type},
        ).fetchone()

        if existing:
            _aws_delete(existing.AWSKey)
            db.session.execute(
                text("DELETE FROM TEMP_CUSTOMER_DOCUMENT WHERE CustomerDocumentId = :id"),
                {"id": existing.CustomerDocumentId},
            )

        _aws_upload(file_bytes, aws_key, content_type)

        db.session.execute(
            text("""
                INSERT INTO TEMP_CUSTOMER_DOCUMENT
                    (Apless, DocumentName, OrganizationType, NumberOfDocuments,
                     DocumentType, CreatedBy, CreatedDate, AWSKey, Prechecking_Id)
                VALUES
                    (:apless, :name, :org_type, :numb_doc,
                     :dtype, :user, GETDATE(), :aws_key, :pid)
            """),
            {
                "apless":   apless,
                "name":     doc_name,
                "org_type": organization_type,
                "numb_doc": "1",
                "dtype":    document_type,
                "user":     username,
                "aws_key":  aws_key,
                "pid":      prechecking_id,
            },
        )
        db.session.commit()

        orig_ext    = os.path.splitext(original)[1].lower()
        preview_b64 = (
            base64.b64encode(file_bytes).decode()
            if orig_ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp",
                            ".heic", ".heif", ".tiff", ".tif", ".webp")
            else None
        )

        return jsonify({
            "success":       True,
            "document_name": doc_name,
            "document_type": document_type,
            "aws_key":       aws_key,
            "preview_b64":   preview_b64,
            "content_type":  content_type,
        })

    except (BotoCoreError, ClientError) as exc:
        db.session.rollback()
        current_app.logger.exception("S3 upload error")
        return jsonify({"success": False, "message": f"S3 upload failed: {exc}"}), 500
    except Exception:
        db.session.rollback()
        current_app.logger.exception("upload_document error")
        return jsonify({"success": False, "message": "Database error"}), 500

@ocr_bp.route("/documents", methods=["GET"])
@login_required
def get_documents():
    apless = request.args.get("apless", "")

    if not apless:
        return jsonify([])

    try:
        rows = db.session.execute(
            text("""
                ;WITH PrecheckIds AS (
                    SELECT Prechecking_Id
                    FROM CAFLESS WITH(NOLOCK)
                    WHERE Apless = :apless
                ),
                AllDocs AS (
                    SELECT
                        CAST(id_customer_document AS bigint) AS CustomerDocumentId,
                        file_document                        AS DocumentName,
                        doc_type                             AS DocumentType,
                        AWSKey,
                        APLESS                                AS Apless,
                        CAST(NULL AS varchar(50))            AS Prechecking_Id,
                        Upload_Dt                            AS SourceDate,
                        'CUSTOMER_DOCUMENT'                  AS SourceTable
                    FROM CUSTOMER_DOCUMENT WITH(NOLOCK)
                    WHERE APLESS = :apless

                    UNION ALL

                    SELECT
                        CustomerDocumentId,
                        DocumentName,
                        DocumentType,
                        AWSKey,
                        Apless,
                        Prechecking_Id,
                        CreatedDate AS SourceDate,
                        'TEMP_CUSTOMER_DOCUMENT'
                    FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
                    WHERE Prechecking_Id IN (SELECT Prechecking_Id FROM PrecheckIds)
                )
                SELECT *
                FROM AllDocs
                ORDER BY DocumentType, SourceDate DESC;
            """),
            {"apless": apless},
        ).fetchall()

        docs = [
            {
                "id":       r.CustomerDocumentId,
                "name":     r.DocumentName,
                "type":     r.DocumentType,
                "key":      r.AWSKey,
                "view_url": _aws_presign(r.AWSKey, r.DocumentName) if r.AWSKey else None,
            }
            for r in rows
        ]
        return jsonify(docs)
    except Exception:
        current_app.logger.exception("get_documents error")
        return jsonify([])

@ocr_bp.route("/view-document", methods=["GET"])
@login_required
def view_document():
    doc_id = request.args.get("customer_document_id", "")
    if not doc_id:
        return jsonify({"success": False, "message": "customer_document_id required"}), 400

    try:
        row = db.session.execute(
            text("""
                SELECT AWSKey, DocumentName FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
                WHERE CustomerDocumentId = :id
            """),
            {"id": doc_id},
        ).fetchone()

        if not row or not row.AWSKey:
            return jsonify({"success": False, "message": "Document not found"}), 404

        view_url = _aws_presign(row.AWSKey, row.DocumentName)
        return jsonify({"success": True, "view_url": view_url})

    except (BotoCoreError, ClientError):
        current_app.logger.exception("S3 presign error")
        return jsonify({"success": False, "message": "Failed to generate preview URL"}), 500
    except Exception:
        current_app.logger.exception("view_document error")
        return jsonify({"success": False, "message": "Database error"}), 500

@ocr_bp.route("/delete-document", methods=["POST"])
@login_required
def delete_document():
   
    body   = request.get_json(force=True) or {}
    doc_id = body.get("customer_document_id")

    if not doc_id:
        return jsonify({"success": False, "message": "customer_document_id required"}), 400

    try:
        row = db.session.execute(
            text("SELECT AWSKey FROM TEMP_CUSTOMER_DOCUMENT WHERE CustomerDocumentId = :id"),
            {"id": doc_id},
        ).fetchone()

        if row and row.AWSKey:
            _aws_delete(row.AWSKey)

        db.session.execute(
            text("DELETE FROM TEMP_CUSTOMER_DOCUMENT WHERE CustomerDocumentId = :id"),
            {"id": doc_id},
        )
        db.session.commit()
        return jsonify({"success": True})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("delete_document error")
        return jsonify({"success": False, "message": "Database error"}), 500