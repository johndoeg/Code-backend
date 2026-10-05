import requests

from urllib.parse import urlencode
from flask import Blueprint, request, send_file, jsonify, redirect, current_app, session, Response, stream_with_context
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import text

from app import db
from app.auth.decorators import login_required
from app.utils.helpers.aws_helpers import _aws_presign
import mimetypes, os
from urllib.parse import urlparse

import mimetypes
from urllib.parse import quote

STREAM_CHUNK = 64 * 1024
UPSTREAM_TIMEOUT = 30

view_prechecking_bp = Blueprint("view_prechecking", __name__, url_prefix="/Prechecking/View")

def _clean_db_value(value):
    if isinstance(value, str) and value.strip().upper() == "NULL":
        return None
    return value

def _clean_row(mapping) -> dict:
    return {k: _clean_db_value(v) for k, v in dict(mapping).items()}

def _truthy_bit(value) -> bool:
    return value not in (None, "", 0, "0", False)

def _tf(val):
    if val is None:
        return ""
    try:
        return "True" if int(val) == 1 else "False"
    except (TypeError, ValueError):
        return ""

_LESSEE_TYPE_LABELS = {
    "CO": "Koperasi",
    "CV": "CV",
    "FD": "Yayasan",
    "PT": "Perusahaan Terbatas",
}

_PENGURUS_MARITAL_LABELS = {
    "M": "MARRIED",
    "S": "SINGLE",
    "D": "DIVORCE",
    "O": "MARRIED WITHOUT CERTIFICATE",
}

_OCR_SELECT = """
    Id, Citizen, Id_Type, NIK, Nama, Tempat_Lahir,
    FORMAT(Tgl_Lahir,'dd-MM-yyyy') AS Tgl_Lahir,
    Jenis_Kelamin, Golongan_Darah, Alamat, RT, RW,
    Kelurahan, Kecamatan, Kota, Provinsi, Agama, Pekerjaan,
    Status_Perkawinan, Kewarnegaraan, Foto, Tanda_Tangan
"""

@view_prechecking_bp.route("/document-url", methods=["GET"])
@login_required
def document_url():
    doc_id = (request.args.get("customer_document_id") or "").strip()

    if not doc_id:
        return jsonify({"error": "customer_document_id required"}), 400

    try:
        row = db.session.execute(text("""
            SELECT AWSKey, DocumentName
            FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
            WHERE CustomerDocumentId = :id
        """), {"id": doc_id}).fetchone()

        if not row or not row.AWSKey:
            return jsonify({"error": "Document not found"}), 404

        return jsonify({
            "url": _aws_presign(row.AWSKey, row.DocumentName),
            "file_name": row.DocumentName,
        })
    except (BotoCoreError, ClientError) as exc:
        current_app.logger.exception("document_url presign error")
        return jsonify({"error": str(exc)}), 500
    except Exception:
        current_app.logger.exception("document_url error")
        return jsonify({"error": "Server error"}), 500

@view_prechecking_bp.route("/aws-download", methods=["GET"])
@login_required
def aws_download():
    aws_key   = request.args.get("aws_key",   "").strip()
    file_name = request.args.get("file_name", "download").strip()

    if not aws_key:
        return jsonify({"error": "aws_key required"}), 400

    try:
        row = db.session.execute(text("""
            SELECT TOP 1 DocumentName
            FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
            WHERE AWSKey = :key
        """), {"key": aws_key}).fetchone()

        if not row:
            return jsonify({"error": "Document not found"}), 404

        name = row.DocumentName or file_name
        url = _aws_presign(aws_key, name)
        return jsonify({"url": url, "file_name": name})
    except (BotoCoreError, ClientError) as exc:
        current_app.logger.exception(exc)
        return jsonify({"error": str(exc)}), 500

@view_prechecking_bp.route("/get-data", methods=["GET"])
@login_required
def get_view():
    apless         = request.args.get("apless", "")
    prechecking_id = request.args.get("prechecking_id", "")

    try:
        raw_row = db.session.execute(text("""
            SELECT Apless, CustomerType, LesseeType, LesseeName, IdCardNo, NPWP,
                   MaritalStatus, WorkAddress, Check_For, Repeat_Order, Notes, Carro
            FROM TEMP_CAFLESS WITH(NOLOCK)
            WHERE Apless = :apless AND Prechecking_Id = :pid
        """), {"apless": apless, "pid": prechecking_id}).fetchone()

        if not raw_row:
            return jsonify({"error": "Not found"}), 404

        row = _clean_row(raw_row._mapping)

        check_for     = row.get("Check_For") or ""
        customer_type = row.get("CustomerType") or ""
        is_individu   = check_for == "C" and customer_type == "PR"
        is_guarn_pr   = check_for == "G" and customer_type == "PR"
        is_corporate  = check_for == "C" and customer_type == "PT"
        is_guarn_pt   = check_for == "G" and customer_type == "PT"

        new_ro = "1" if _truthy_bit(row.get("Repeat_Order")) else "0"

        lc_row = db.session.execute(text("""
            SELECT MAX(sik.CreatedDate) AS LastCheckingDate
            FROM TEMP_SIK_CHECKING_DOCUMENT sik WITH(NOLOCK)
                INNER JOIN TEMP_CAFLESS tc WITH(NOLOCK) ON tc.Prechecking_Id = sik.Prechecking_Id
            WHERE tc.FINAL_APLESS = :apless OR tc.Apless = :apless
        """), {"apless": apless}).fetchone()
        last_checking_date = (
            lc_row.LastCheckingDate.strftime("%d-%m-%Y %H:%M:%S")
            if lc_row and lc_row.LastCheckingDate else ""
        )

        outstanding = 0
        for sql in [
            """SELECT SUM(b.OUTS_PRINC) AS v FROM V_DataKredit a WITH(NOLOCK)
                    LEFT JOIN CLFPAY b WITH(NOLOCK) ON a.LEASE_NO=b.LEASE_NO
                    AND b.PERIOD=(SELECT ISNULL(MAX(period),0)
                                 FROM CLFPAY
                                 WHERE DATE_PAY IS NOT NULL
                                    AND LEASE_NO=a.LEASE_NO)
               WHERE a.APLESS=:apless AND a.UPD_STAT='Y' AND a.EXECUTION IS NOT NULL""",
            """SELECT SUM(v) AS v FROM (
                    SELECT SUM(d.Net_Finance) AS v FROM CLFCONT_DATA a WITH(NOLOCK)
                        INNER JOIN MCMOCAMCOMPLETELIST b WITH(NOLOCK) ON a.APPL_NO=b.APPL_NO
                        INNER JOIN CAFLESS c WITH(NOLOCK) ON a.LESSEE_NO=c.lessee_no
                        INNER JOIN V_NetFinance d ON a.LEASE_NO=d.LEASE_NO
                    WHERE EXECUTION IS NULL AND b.AdmSts=1 AND apless=:apless
                 
                 UNION ALL
                 
                    SELECT SUM(d.Net_Finance) AS v FROM MCMOCAMCOMPLETELIST a WITH(NOLOCK)
                        INNER JOIN cafcont b WITH(NOLOCK) ON a.APPL_NO=b.APPL_NO
                        INNER JOIN V_NetFinance d ON a.APPL_NO=d.APPL_NO
                    WHERE b.DateTrans IS NULL AND a.AdmSts=1 AND apless=:apless
               ) x"""
        ]:
            try:
                r = db.session.execute(text(sql), {"apless": apless}).fetchone()
                if r and r.v:
                    outstanding += float(r.v)
            except Exception:
                current_app.logger.exception("outstanding query failed for apless=%s", apless)

        def _ocr_fields(ocr_row: dict, rate_row, duc_row) -> dict:
            def f(col, has_duc=True):
                val = ocr_row.get(col)
                cr_val = rate_row.get(col) if rate_row else None
                duc_val = duc_row.get(col) if (duc_row and has_duc) else None
                return {
                    "value":      val or "",
                    "confidence": str(cr_val or ""),
                    "verified":   _tf(duc_val),
                }

            citizen = ocr_row.get("Citizen") or ""
            id_type = ocr_row.get("Id_Type") or ("KITAS" if citizen == "WNA" else "KTP")

            return {
                "citizen":     citizen,
                "idType":      id_type,
                "idCardNo":    f("NIK"),
                "name":        f("Nama"),
                "pob":         f("Tempat_Lahir"),
                "dob":         f("Tgl_Lahir"),
                "gender":      f("Jenis_Kelamin"),
                "bloodType":   f("Golongan_Darah", has_duc=False),
                "address":     f("Alamat"),
                "rt":          f("RT"),
                "rw":          f("RW"),
                "subdistrict": f("Kelurahan"),
                "district":    f("Kecamatan"),
                "city":        f("Kota"),
                "province":    f("Provinsi"),
                "religion":    f("Agama", has_duc=False),
                "job":         f("Pekerjaan"),
                "maritalStatus": ocr_row.get("Status_Perkawinan") or "",
                "photo":       ocr_row.get("Foto") or "",
                "signature":   ocr_row.get("Tanda_Tangan") or "",
            }

        def _load_ocr_row(raw_ocr) -> dict:
            ocr_row = _clean_row(raw_ocr._mapping)

            raw_rate = db.session.execute(text("""
                SELECT NIK, Nama, Tempat_Lahir, Tgl_Lahir, Jenis_Kelamin,
                       Golongan_Darah, Alamat, RT, RW, Kelurahan, Kecamatan,
                       Kota, Provinsi, Agama, Pekerjaan, Kewarnegaraan
                FROM TEMP_CAFLESS_OCR_Rate WITH(NOLOCK)
                WHERE Id=:id
            """), {"id": ocr_row.get("Id")}).fetchone()
            rate_row = _clean_row(raw_rate._mapping) if raw_rate else None

            raw_duc = db.session.execute(text("""
                SELECT NIK, Nama, Tempat_Lahir, Tgl_Lahir, Jenis_Kelamin,
                       Alamat, RT, RW, Kelurahan, Kecamatan, Kota, Provinsi, Pekerjaan
                FROM TEMP_CAFLESS_OCR_Dukcapil WITH(NOLOCK)
                WHERE Id=:id
            """), {"id": ocr_row.get("Id")}).fetchone()
            duc_row = _clean_row(raw_duc._mapping) if raw_duc else None

            return _ocr_fields(ocr_row, rate_row, duc_row)

        def load_ocr(ocr_for: str):
            raw_ocr = db.session.execute(text(f"""
                SELECT TOP 1 {_OCR_SELECT}
                FROM TEMP_CAFLESS_OCR WITH(NOLOCK)
                WHERE Prechecking_Id=:pid AND OCR_For=:ocr_for
                ORDER BY Id DESC
            """), {"pid": prechecking_id, "ocr_for": ocr_for}).fetchone()
            if not raw_ocr:
                return None
            return _load_ocr_row(raw_ocr)

        def load_ocr_list(ocr_for: str):
            raw_ocr_rows = db.session.execute(text(f"""
                SELECT {_OCR_SELECT}
                FROM TEMP_CAFLESS_OCR WITH(NOLOCK)
                WHERE Prechecking_Id=:pid AND OCR_For=:ocr_for AND Citizen='WNI'
                ORDER BY Id
            """), {"pid": prechecking_id, "ocr_for": ocr_for}).fetchall()
            officers = []
            for raw_ocr in raw_ocr_rows:
                officer = _load_ocr_row(raw_ocr)
                officer["maritalStatus"] = _PENGURUS_MARITAL_LABELS.get(
                    officer["maritalStatus"], officer["maritalStatus"]
                )
                officers.append(officer)
            return officers

        def load_wna_board(ocr_for: str):
            raw_rows = db.session.execute(text("""
                SELECT NIK, Nama, Id_Type FROM TEMP_CAFLESS_OCR WITH(NOLOCK)
                WHERE Prechecking_Id=:pid AND OCR_For=:ocr_for AND Citizen='WNA'
                ORDER BY Id
            """), {"pid": prechecking_id, "ocr_for": ocr_for}).fetchall()
            board = []
            for raw_r in raw_rows:
                r = _clean_row(raw_r._mapping)
                board.append({
                    "name": r.get("Nama") or "",
                    "idCardNo": r.get("NIK") or "",
                    "idType": r.get("Id_Type") or "KITAS",
                })
            return board

        def load_shareholders():
            raw_rows = db.session.execute(text("""
                SELECT NIK, Nama, Id_Type FROM TEMP_CAFLESS_OCR WITH(NOLOCK)
                WHERE Prechecking_Id=:pid AND OCR_For='H'
                ORDER BY Id
            """), {"pid": prechecking_id}).fetchall()
            out = []
            for raw_r in raw_rows:
                r = _clean_row(raw_r._mapping)
                out.append({
                    "name": r.get("Nama") or "",
                    "npwpNo": r.get("NIK") or "",
                    "idType": r.get("Id_Type") or "NPWP",
                })
            return out

        customer_ocr = None
        spouse_ocr   = None
        wna_name     = ""
        wna_idcard   = ""
        wna_id_type  = ""
        corporate_officers = []
        wna_board = []
        shareholders = []
        corp_name = ""
        corp_npwp = ""
        corp_address = ""
        corp_type_label = ""

        if is_individu or is_guarn_pr:
            ocr_for      = "C" if is_individu else check_for
            customer_ocr = load_ocr(ocr_for)
            spouse_ocr   = load_ocr("S")

            if customer_ocr and customer_ocr["citizen"] == "WNA":
                wna_name    = row.get("LesseeName") or ""
                wna_idcard  = row.get("IdCardNo") or ""
                wna_id_type = customer_ocr.get("idType") or "KITAS"

        if customer_type == "PT":
            corp_name = row.get("LesseeName") or ""
            corp_npwp = row.get("NPWP") or ""
            corp_address = row.get("WorkAddress") or ""
            lessee_type_code = row.get("LesseeType") or ""
            corp_type_label = _LESSEE_TYPE_LABELS.get(lessee_type_code, lessee_type_code)

            if is_corporate or is_guarn_pt:
                pengurus_ocr_for = "P" if is_corporate else "G"
                corporate_officers = load_ocr_list(pengurus_ocr_for)
                wna_board = load_wna_board(pengurus_ocr_for)
                shareholders = load_shareholders()

        marital_code  = row.get("MaritalStatus") or ""
        marital_label = marital_code
        if marital_code:
            mrow = db.session.execute(
                text("SELECT name FROM MSTMARITAL WITH(NOLOCK) WHERE Marital = :m"),
                {"m": marital_code},
            ).fetchone()
            if mrow and mrow.name:
                marital_label = mrow.name

        sik_rows = db.session.execute(text("""
            SELECT Subject, CreditBureau, Status, Score, Grade
            FROM TEMP_SIK_CHECKING_DOCUMENT WITH(NOLOCK)
            WHERE Prechecking_Id=:pid
        """), {"pid": prechecking_id}).fetchall()

        sik = []
        for raw_s in sik_rows:
            s = _clean_row(raw_s._mapping)
            credit_bureau = s.get("CreditBureau") or ""
            score = str(s.get("Score") or "")
            if credit_bureau == "APPI":
                score = ""
            elif credit_bureau == "SLIK":
                score = f"Col {score}"
            subj = s.get("Subject")

            subject = "Customer" if subj == "C" else ("Guarantor" if subj == "G" else "Pengurus")
            sik.append({
                "subject": subject,
                "credit_bureau": credit_bureau,
                "status": s.get("Status") or "",
                "score": score,
                "grade": (
                    "Whitelist"
                    if credit_bureau == "APPI" and s.get("Grade") == "W"
                    else "Blacklist"
                    if credit_bureau == "APPI"
                    else s.get("Grade") or ""
                ),
            })

        doc_rows = db.session.execute(text("""
            SELECT CustomerDocumentId, DocumentName, DocumentType, AWSKey
            FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
            WHERE Prechecking_Id=:pid
            ORDER BY DocumentType, CreatedDate
        """), {"pid": prechecking_id}).fetchall()

        documents: dict = {}
        for raw_d in doc_rows:
            d = _clean_row(raw_d._mapping)
            name = d.get("DocumentName")
            if not name:
                continue
            dt = d.get("DocumentType") or "other"
            query = urlencode({"aws_key": d.get("AWSKey") or "", "file_name": name})
            documents.setdefault(dt, []).append({
                "id":      d.get("CustomerDocumentId"),
                "name":    name,
                "type":    dt,
                "viewUrl": f"/Prechecking/View/aws-download?{query}",
            })

        return jsonify({
            "prechecking_id":    prechecking_id,
            "apless":            apless,
            "check_for":         check_for,
            "customer_type":     customer_type,
            "lessee_type":       row.get("LesseeType") or "",
            "new_ro":            new_ro,
            "nationality":       customer_ocr["citizen"] if customer_ocr else "WNI",
            "marital":           marital_label,
            "is_carro":          "1" if _truthy_bit(row.get("Carro")) else "0",
            "note":              row.get("Notes") or "",
            "last_checking_date":last_checking_date,
            "outstanding":       outstanding,
            "customer":          customer_ocr,
            "spouse":            spouse_ocr,
            "wna_name":          wna_name,
            "wna_idcard":        wna_idcard,
            "wna_id_type":       wna_id_type,
            "is_corporate":      is_corporate,
            "is_guarantor_pt":   is_guarn_pt,
            "corp_name":         corp_name,
            "corp_npwp":         corp_npwp,
            "corp_address":      corp_address,
            "corp_type_label":   corp_type_label,
            "corporate":         corporate_officers,
            "wna_board":         wna_board,
            "shareholders":      shareholders,
            "sik":               sik,
            "documents":         documents,
        })

    except Exception:
        current_app.logger.exception("get_view error")
        return jsonify({"error": "Server error"}), 500

@view_prechecking_bp.route("/approval-history", methods=["GET"])
@login_required
def get_approval_history():
    prechecking_id = request.args.get("prechecking_id", "")

    try:
        rows = db.session.execute(text("""
            SELECT
                FORMAT(h.CreatedDate,'dd-MM-yyyy HH:mm:ss') AS date,
                h.ApprovalActionCode                         AS action,
                h.CreatedBy                                  AS [by],
                h.Remarks                                    AS remarks
            FROM DocumentApprovalHistory h WITH(NOLOCK)
                INNER JOIN DocumentApproval a WITH(NOLOCK) ON h.DocumentApprovalId = a.Id
            WHERE a.DocumentNumber = :pid
            ORDER BY h.CreatedDate DESC
        """), {"pid": prechecking_id}).fetchall()

        return jsonify([
            {
                "date": r.date,
                "action": r.action,
                "by": _clean_db_value(r.by) or "",
                "remarks": _clean_db_value(r.remarks) or "",
            }
            for r in rows
        ])

    except Exception:
        current_app.logger.exception("get_approval_history error")
        return jsonify([])

def _document_aws_key(doc_id: int):
    row = db.session.execute(
        text("""
            SELECT AWSKey, DocumentName
            FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
            WHERE CustomerDocumentId = :id
        """),
        {"id": doc_id},
    ).fetchone()

    if not row or not row.AWSKey:
        return None, None
    return row.AWSKey.strip(), (row.DocumentName or f"document-{doc_id}").strip()

def _content_disposition(DocumentName: str) -> str:
    ascii_name = DocumentName.encode("ascii", "ignore").decode() or "download"
    return (
        f'attachment; filename="{ascii_name}"; '
        f"filename*=UTF-8''{quote(DocumentName)}"
    )

@view_prechecking_bp.route('/document-file')
@login_required
def download_document_file():
    doc_id = request.args.get('customer_document_id', type=int)
    if not doc_id:
        return jsonify({'error': 'customer_document_id is required'}), 400

    try:
        AWSKey, DocumentName = _document_aws_key(doc_id)
    except Exception:
        current_app.logger.exception('Document lookup error')
        return jsonify({'error': 'Gagal membaca data dokumen.'}), 500

    if not AWSKey:
        return jsonify({'error': 'Dokumen tidak ditemukan.'}), 404

    try:
        url = _aws_presign(AWSKey, DocumentName)
        upstream = requests.get(url, stream=True, timeout=UPSTREAM_TIMEOUT)
    except Exception:
        current_app.logger.exception('S3 fetch error for document %s', doc_id)
        return jsonify({'error': 'Gagal mengambil file dari storage.'}), 502

    if upstream.status_code != 200:
        upstream.close()
        return jsonify({'error': 'Gagal mengambil file dari storage.'}), 502

    mime = (
        upstream.headers.get('Content-Type')
        or mimetypes.guess_type(DocumentName)[0]
        or 'application/octet-stream'
    )

    headers = {'Content-Disposition': _content_disposition(DocumentName)}
    length = upstream.headers.get('Content-Length')
    if length:
        headers['Content-Length'] = length

    def generate():
        try:
            for chunk in upstream.iter_content(chunk_size=STREAM_CHUNK):
                if chunk:
                    yield chunk
        finally:
            upstream.close()

    return Response(stream_with_context(generate()), mimetype=mime, headers=headers)