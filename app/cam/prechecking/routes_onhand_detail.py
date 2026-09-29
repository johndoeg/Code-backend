from datetime import datetime

from flask import Blueprint, request, jsonify, current_app, session
from sqlalchemy import text

from app import db
from app.auth.decorators import login_required
from app.utils.helpers.prechecking_ocr import load_person_ocr

try:
    from app.utils.helpers.telegram_helpers import send_telegram  # type: ignore
except ImportError:
    def send_telegram(target_id: str, message: str) -> None:
        current_app.logger.warning(
            "send_telegram() stub called (no app.utils.helpers.telegram_helpers) — "
            "target=%s message=%s", target_id, message,
        )

onhand_detail_bp = Blueprint("cam_onhand_detail", __name__, url_prefix="/Prechecking/OnhandDetail")

MARITAL_LABELS = {
    "S": "Single",
    "M": "Married",
    "D": "Divorce",
    "O": "Married without Certificate",
    "P": "Married with Prenuptial Agreement",
}

def _session_str(key: str) -> str:
    return session.get(key, "") or ""

def _field(payload: dict, form, *keys):
    for k in keys:
        v = payload.get(k)
        if v not in (None, ""):
            return v
    for k in keys:
        v = form.get(k)
        if v not in (None, ""):
            return v
    return ""

def _normalize_score(raw_score, existing_grade: str):
    raw_score = str(raw_score or "").strip()
    grade = existing_grade or ""

    if raw_score.lstrip("-").isdigit():
        return int(raw_score), grade

    if raw_score and not grade:
        grade = raw_score
    return None, grade

def _fetch_combo(cat_value: str, value_filter: str = None, value_as_desc: bool = False):
    desc_col = "VALUE as DESC_VALUE" if value_as_desc else "DESC_VALUE"
    sql = f"SELECT VALUE, {desc_col} FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE = :cat"
    params = {"cat": cat_value}
    if value_filter:
        sql += " AND VALUE = :val"
        params["val"] = value_filter
    rows = db.session.execute(text(sql), params).fetchall()
    return [{"value": r.VALUE, "label": r.DESC_VALUE} for r in rows]

def _fetch_lookups():
    return {
        "subjects": _fetch_combo("SID1"),
        "relatedParties": _fetch_combo("SIDa2"),
        "types": _fetch_combo("SID_Type"),
        "boardTypes": _fetch_combo("SID_Type", value_filter="PR"),
        "creditBureaus": [c for c in _fetch_combo("SIDCB", value_as_desc=True) if c["value"] in ("PBK", "SLIK", "APPI")],
        "statuses": _fetch_combo("SIDST"),
        "slikScores": _fetch_combo("SLIK"),
        "appiScores": _fetch_combo("SIDAPPI"),
    }

def _current_approver(emp_id: str, username: str, apless: str):
    rows = db.session.execute(text(
        "EXEC USP_CAM_REQUEST_ONHANDBYAPLESS :emp_id, :username, '', :apless"
    ), {"emp_id": emp_id, "username": username, "apless": apless}).fetchall()
    current_approver = rows[0].CurrentApprover if rows else ""
    return current_approver, rows

def _load_sik_rows(prechecking_id: str):
    rows = db.session.execute(text("""
        SELECT Id, Subject, Description, CreditBureau, RelatedParty, [Status], [Type], Score, Grade
        FROM TEMP_SIK_CHECKING_DOCUMENT WITH(NOLOCK)
        WHERE Prechecking_Id = :pid
        ORDER BY Id
    """), {"pid": prechecking_id}).fetchall()
    return [{
        "id": r.Id,
        "subject": r.Subject or "",
        "keterangan": r.Description or "",
        "creditBureau": r.CreditBureau or "",
        "relatedParty": r.RelatedParty or "",
        "status": r.Status or "",
        "type": r.Type or "",
        "score": "" if r.Score is None else str(r.Score),
        "grade": r.Grade or "",
    } for r in rows]

def _load_documents(apless: str, prechecking_id: str):
    doc_rows = db.session.execute(text("""
        SELECT CustomerDocumentId, DocumentName, DocumentType, AWSKey
        FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
        WHERE Apless = :apless AND Prechecking_Id = :pid
        ORDER BY DocumentType, CreatedDate
    """), {"apless": apless, "pid": prechecking_id}).fetchall()
    documents: dict = {}
    for d in doc_rows:
        documents.setdefault(d.DocumentType or "other", []).append({
            "id": d.CustomerDocumentId,
            "name": d.DocumentName or "",
            "awsKey": d.AWSKey or "",
        })
    return documents

def _outstanding(apless: str) -> float:
    outstanding = 0.0
    for sql in [
        """SELECT SUM(b.OUTS_PRINC) AS v FROM V_DataKredit a WITH(NOLOCK)
               LEFT JOIN CLFPAY b WITH(NOLOCK) ON a.LEASE_NO = b.LEASE_NO
                   AND b.PERIOD = (SELECT ISNULL(MAX(period), 0) FROM CLFPAY
                                   WHERE DATE_PAY IS NOT NULL AND LEASE_NO = a.LEASE_NO)
           WHERE a.APLESS = :apless AND a.UPD_STAT = 'Y' AND a.EXECUTION IS NOT NULL""",
        """SELECT SUM(v) AS v FROM (
               SELECT SUM(d.Net_Finance) AS v FROM CLFCONT_DATA a WITH(NOLOCK)
                   INNER JOIN MCMOCAMCOMPLETELIST b WITH(NOLOCK) ON a.APPL_NO = b.APPL_NO
                   INNER JOIN CAFLESS c WITH(NOLOCK) ON a.LESSEE_NO = c.lessee_no
                   INNER JOIN V_NetFinance d ON a.LEASE_NO = d.LEASE_NO
               WHERE EXECUTION IS NULL AND b.AdmSts = 1 AND apless = :apless
               UNION ALL
               SELECT SUM(d.Net_Finance) AS v FROM MCMOCAMCOMPLETELIST a WITH(NOLOCK)
                   INNER JOIN cafcont b WITH(NOLOCK) ON a.APPL_NO = b.APPL_NO
                   INNER JOIN V_NetFinance d ON a.APPL_NO = d.APPL_NO
               WHERE b.DateTrans IS NULL AND a.AdmSts = 1 AND apless = :apless
           ) x""",
    ]:
        try:
            r = db.session.execute(text(sql), {"apless": apless}).fetchone()
            if r and r.v:
                outstanding += float(r.v)
        except Exception:
            current_app.logger.exception("outstanding calc failed")
    return outstanding

def _notify_telegram(prechecking_id: str, username: str, comment: str, approval_message: str) -> None:
    try:
        rows = db.session.execute(text("""
            SELECT DISTINCT cl.createdBy, d.TelegramID, cl.LesseeName, f.TelegramID as CMH_ID, e.FULLNAME
            FROM TEMP_CAFLESS cl
                LEFT JOIN APP_USRMST e ON cl.createdBy = e.username
                LEFT JOIN EMPLOYEE_DATA d ON e.employee_id = d.Employee_ID
                LEFT JOIN EMPLOYEE_DATA f ON e.SUPERIOR = f.Employee_ID
            WHERE Prechecking_Id = :pid
        """), {"pid": prechecking_id}).fetchall()

        for row in rows:
            lessee_name = row.LesseeName
            cmo_name = row.FULLNAME
            message = f"Prechecking of {lessee_name} has been {approval_message} by {username}. Note: {comment}"
            message_cmh = (
                f"Prechecking of {lessee_name} (CMO : {cmo_name}) has been "
                f"{approval_message} by {username}. Note: {comment}"
            )
            if row.TelegramID:
                send_telegram(row.TelegramID, message)
            if row.CMH_ID:
                send_telegram(row.CMH_ID, message_cmh)
    except Exception:
        current_app.logger.exception("Telegram notification failed")

@onhand_detail_bp.route("/get-data", methods=["GET"])
@login_required
def get_data():
    apless = request.args.get("apless", "")
    prechecking_id = request.args.get("prechecking_id", "")

    if not apless or not prechecking_id:
        return jsonify({"error": "apless and prechecking_id are required"}), 400

    row = db.session.execute(text("""
        SELECT Apless, CustomerType, Check_For, Repeat_Order, Notes, Carro, MaritalStatus, FINAL_APLESS
        FROM TEMP_CAFLESS WITH(NOLOCK)
        WHERE Apless = :apless AND Prechecking_Id = :pid
    """), {"apless": apless, "pid": prechecking_id}).fetchone()

    if not row:
        return jsonify({"error": "Not found"}), 404
    if (row.CustomerType or "") != "PR":
        return jsonify({"error": "This screen only supports individual (PR) prechecking records"}), 400

    check_for = row.Check_For or "C"
    customer = load_person_ocr(prechecking_id, check_for)
    if customer is None:
        return jsonify({"error": "OCR data not found for this prechecking"}), 404

    spouse = load_person_ocr(prechecking_id, "S")

    username = _session_str("username")
    emp_id = _session_str("emp_id")
    accesslevel = _session_str("accesslevel")
    current_approver, _cams = _current_approver(emp_id, username, apless)

    can_edit = accesslevel == "CR" and current_approver == f"({username})"

    last_checking_date = ""
    lc_row = db.session.execute(text("""
        SELECT MAX(sik.CreatedDate) AS LastCheckingDate
        FROM TEMP_SIK_CHECKING_DOCUMENT sik WITH(NOLOCK)
            INNER JOIN TEMP_CAFLESS tc WITH(NOLOCK) ON tc.Prechecking_Id = sik.Prechecking_Id
        WHERE tc.FINAL_APLESS = :apless
    """), {"apless": apless}).fetchone()
    if lc_row and lc_row.LastCheckingDate:
        last_checking_date = lc_row.LastCheckingDate.strftime("%d-%m-%Y %H:%M:%S")

    marital = row.MaritalStatus or ""

    return jsonify({
        "apless": apless,
        "prechecking_id": prechecking_id,
        "check_for": check_for,
        "customer_type": "PR",
        "repeat_order": "1" if str(row.Repeat_Order) == "1" else "0",
        "is_carro": str(row.Carro or "0"),
        "note": row.Notes or "",
        "last_checking_date": last_checking_date,
        "outstanding": _outstanding(apless),
        "maritalStatus": marital,
        "maritalStatusLabel": MARITAL_LABELS.get(marital, marital),
        "customer": customer,
        "spouse": spouse,
        "documents": _load_documents(apless, prechecking_id),
        "sik": _load_sik_rows(prechecking_id),
        "canEdit": can_edit,
        "accessLevel": accesslevel,
        "currentApprover": current_approver,
        "lookups": _fetch_lookups(),
    })

@onhand_detail_bp.route("/decide", methods=["POST"])
@login_required
def decide():
    payload = request.get_json(silent=True) or {}
    apless = payload.get("apless", "")
    prechecking_id = payload.get("prechecking_id", "")
    decision = payload.get("decision", "")
    comment = (payload.get("comment") or "").replace("'", "`")
    sik_rows = payload.get("sik") or []

    if not apless or not prechecking_id:
        return jsonify({"success": False, "message": "apless and prechecking_id are required"}), 400
    if decision not in ("approve", "reject"):
        return jsonify({"success": False, "message": "decision must be 'approve' or 'reject'"}), 400

    username = _session_str("username")
    emp_id = _session_str("emp_id")
    accesslevel = _session_str("accesslevel")

    current_approver, cams = _current_approver(emp_id, username, apless)
    if accesslevel != "CR" or current_approver != f"({username})":
        return jsonify({"success": False, "message": "You are not the current approver for this record."}), 403

    errors = {}
    if not comment:
        errors["comment"] = "Comment field is required"

    for i, sik in enumerate(sik_rows):
        prefix = f"sik.{i}"
        if not sik.get("subject"):
            errors[f"{prefix}.subject"] = f"Subject can't be empty (row {i + 1})"
        if not sik.get("creditBureau"):
            errors[f"{prefix}.creditBureau"] = f"Credit bureau can't be empty (row {i + 1})"
        if not sik.get("status"):
            errors[f"{prefix}.status"] = f"Status can't be empty (row {i + 1})"
        if sik.get("relatedParty") and not sik.get("type"):
            errors[f"{prefix}.type"] = f"Related party type can't be empty (row {i + 1})"

    if errors:
        return jsonify({"success": False, "errors": errors}), 422

    approval_status = "A" if decision == "approve" else "R"
    approval_message = "approved" if decision == "approve" else "rejected"

    try:
        db.session.execute(text(
            "DELETE FROM TEMP_SIK_CHECKING_DOCUMENT WHERE Prechecking_Id = :pid"
        ), {"pid": prechecking_id})

        for sik in sik_rows:
            score, grade = _normalize_score(sik.get("score"), sik.get("grade", ""))
            db.session.execute(text("""
                INSERT INTO TEMP_SIK_CHECKING_DOCUMENT
                    (ApplNo, Subject, Description, CreditBureau, RelatedParty, [Status], [Type],
                     Score, Grade, CreatedBy, CreatedDate, Prechecking_Id)
                VALUES
                    (:pid, :subject, :keterangan, :credit_bureau, :related_party, :status, :type,
                     :score, :grade, :by, :created, :pid)
            """), {
                "pid": prechecking_id,
                "subject": sik.get("subject", ""),
                "keterangan": sik.get("keterangan", ""),
                "credit_bureau": sik.get("creditBureau", ""),
                "related_party": sik.get("relatedParty", ""),
                "status": sik.get("status", ""),
                "type": sik.get("type", ""),
                "score": score,
                "grade": grade,
                "by": username,
                "created": datetime.utcnow(),
            })

        for cam in cams:
            db.session.execute(text(
                "EXEC USP_CAM_REQUEST_SENTBYPRECHECKINGID :pid, :username, :comment, :form_id, "
                ":accesslevel, :approval, :status"
            ), {
                "pid": prechecking_id, "username": username, "comment": comment,
                "form_id": "", "accesslevel": accesslevel, "approval": "Admin",
                "status": approval_status,
            })

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("decide failed")
        return jsonify({"success": False, "message": "Failed to save. Please try again."}), 500

    _notify_telegram(prechecking_id, username, comment, approval_message)

    return jsonify({"success": True})

@onhand_detail_bp.route("/upsert-sik", methods=["POST"])
@login_required
def upsert_sik():
    payload = request.get_json(force=True, silent=True) or {}
    form = request.form
    
    current_app.logger.warning(
        "upsert_sik content-type=%s json=%s form=%s",
        request.content_type, payload, form.to_dict()
    )

    apless = _field(payload, form, "apless")
    prechecking_id = _field(payload, form, "prechecking_id")
    subject = _field(payload, form, "subject", "sid_subject")
    related_party = _field(payload, form, "relatedParty", "sid_related_party")
    keterangan = _field(payload, form, "keterangan", "sid_keterangan")
    credit_bureau = _field(payload, form, "creditBureau", "credit_bureau")
    status = _field(payload, form, "status", "sid_status")
    grade_in = _field(payload, form, "grade", "sid_grade")
    type_ = _field(payload, form, "type", "sid_type")
    aws_key = _field(payload, form, "awsKey", "pefindo")
    row_id = _field(payload, form, "id")
    raw_score = _field(payload, form, "score", "sid_score")

    if not apless or not prechecking_id:
        return jsonify({"success": False, "message": "apless and prechecking_id are required"}), 400
    if not subject or not credit_bureau or not status:
        return jsonify({"success": False, "message": "subject, creditBureau and status are required"}), 422
    if related_party and not type_:
        return jsonify({"success": False, "message": "type is required when relatedParty is set"}), 422

    username = _session_str("username")
    emp_id = _session_str("emp_id")
    accesslevel = _session_str("accesslevel")

    current_approver, cams = _current_approver(emp_id, username, apless)
    if accesslevel != "CR" or current_approver != f"({username})":
        return jsonify({"success": False, "message": "You are not the current approver for this record."}), 403

    score, grade = _normalize_score(raw_score, grade_in)

    new_id = row_id or None
    try:
        for cam in cams:
            appl_no = cam.APPL_NO

            existing = db.session.execute(text("""
                SELECT Id FROM TEMP_SIK_CHECKING_DOCUMENT WITH(NOLOCK)
                WHERE ApplNo = :appl_no AND Prechecking_Id = :pid AND CreditBureau = :credit_bureau
                    AND Subject = :subject AND RelatedParty = :related_party
                    AND [Status] = :status AND [Type] = :type
            """), {
                "appl_no": appl_no, "pid": prechecking_id, "credit_bureau": credit_bureau,
                "subject": subject, "related_party": related_party, "status": status, "type": type_,
            }).fetchone()

            if existing:
                if row_id and str(existing.Id) == str(row_id):
                    db.session.execute(text("""
                        UPDATE TEMP_SIK_CHECKING_DOCUMENT
                        SET Subject = :subject, CreditBureau = :credit_bureau, RelatedParty = :related_party,
                            Description = :keterangan, [Status] = :status, Score = :score, Grade = :grade,
                            [Type] = :type, AWSKey = :aws_key, UpdatedBy = :username, UpdatedDate = :updated
                        WHERE Id = :id
                    """), {
                        "subject": subject, "credit_bureau": credit_bureau, "related_party": related_party,
                        "keterangan": keterangan, "status": status, "score": score, "grade": grade,
                        "type": type_, "aws_key": aws_key, "username": username,
                        "updated": datetime.utcnow(), "id": existing.Id,
                    })
                    new_id = existing.Id
                else:
                    db.session.rollback()
                    return jsonify({
                        "success": False,
                        "message": (
                            f"SIK Checking data with Subject: {subject}, Credit Bureau: {credit_bureau}, "
                            f"Related Party: {related_party}, Status: {status}, Type: {type_} already exists."
                        ),
                    }), 409
            else:
                result = db.session.execute(text("""
                    INSERT INTO TEMP_SIK_CHECKING_DOCUMENT
                        (ApplNo, Subject, Description, CreditBureau, RelatedParty, [Status], [Type],
                         Score, Grade, AWSKey, CreatedBy, CreatedDate, Prechecking_Id)
                    OUTPUT INSERTED.Id
                    VALUES
                        (:appl_no, :subject, :keterangan, :credit_bureau, :related_party, :status, :type,
                         :score, :grade, :aws_key, :username, :created, :pid)
                """), {
                    "appl_no": appl_no, "subject": subject, "keterangan": keterangan,
                    "credit_bureau": credit_bureau, "related_party": related_party, "status": status,
                    "type": type_, "score": score, "grade": grade, "aws_key": aws_key,
                    "username": username, "created": datetime.utcnow(), "pid": prechecking_id,
                }).fetchone()
                new_id = result.Id

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("upsert_sik failed")
        return jsonify({"success": False, "message": "Failed to save. Please try again."}), 500

    return jsonify({"success": True, "id": new_id})

@onhand_detail_bp.route("/delete-sik", methods=["POST"])
@login_required
def delete_sik():
    payload = request.get_json(silent=True) or {}
    form = request.form

    row_id = _field(payload, form, "id")
    apless = _field(payload, form, "apless")

    if not row_id:
        return jsonify({"success": False, "message": "id is required"}), 400
    if not apless:
        return jsonify({"success": False, "message": "apless is required"}), 400

    username = _session_str("username")
    emp_id = _session_str("emp_id")
    accesslevel = _session_str("accesslevel")

    current_approver, _cams = _current_approver(emp_id, username, apless)
    if accesslevel != "CR" or current_approver != f"({username})":
        return jsonify({"success": False, "message": "You are not the current approver for this record."}), 403

    try:
        db.session.execute(text(
            "DELETE FROM TEMP_SIK_CHECKING_DOCUMENT WHERE Id = :id"
        ), {"id": row_id})
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("delete_sik failed")
        return jsonify({"success": False, "message": "Failed to delete. Please try again."}), 500

    return jsonify({"success": True})