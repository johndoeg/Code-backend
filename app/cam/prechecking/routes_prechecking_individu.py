from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import text
from datetime import datetime, date
import base64, os, mimetypes, re, calendar

from botocore.exceptions import BotoCoreError, ClientError

from app import db
from app.auth.decorators import login_required
from app.utils.helpers.aws_helpers import (
    _aws_upload, _aws_delete, _aws_presign, _validate_file, copy_object
)

from app.utils.helpers.base_format import (
    _username, _branch, _emp_id, _to_bit, _strip_non_digit,
    fmt_date, parse_date, as_of_date, can_edit, format_threshold, get_combo,
)

prechecking_individu_bp = Blueprint("prechecking_individu", __name__, url_prefix="/CAM/Prechecking")

_OCR_DOC_TYPES = {"cust-ktp", "cust-spouse-ktp", "cust-wna-spouse-ktp"}
_WNA_ID_TYPES = ("KITAS", "KITAP")

def _is_ocr_doc_type(document_type: str) -> bool:
    return (document_type or "") in _OCR_DOC_TYPES

def _norm_id_type(value: str, nationality: str) -> str:
    if (nationality or "").strip().upper() != "WNA":
        return "KTP"
    v = (value or "").strip().upper()
    return v if v in _WNA_ID_TYPES else "KITAS"

def _sql_date(value: str):
    v = (value or "").strip()
    if not v:
        return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(v, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None

def _apless_for_prechecking(prechecking_id: str) -> str:
    if not prechecking_id:
        return ""
    row = db.session.execute(
        text("""
            SELECT TOP 1 Apless FROM TEMP_CAFLESS WITH(NOLOCK)
            WHERE Prechecking_Id = :pid AND ISNULL(Apless, '') <> ''
            ORDER BY CreatedDate DESC
        """),
        {"pid": prechecking_id},
    ).fetchone()
    return (row.Apless or "") if row else ""

def _carried_source_filename(source_name: str) -> str:
    stripped = re.sub(r"^[^-]*-[A-Z0-9_]+-", "", source_name or "", count=1)
    return stripped or (source_name or "document")

def _carry_over_documents(prechecking_id: str, apless: str, username: str, items) -> list:
    failed = []

    if not isinstance(items, list) or not prechecking_id:
        return failed

    for item in items:
        if not isinstance(item, dict):
            continue

        doc_id = item.get("customer_document_id")
        target_type = (item.get("document_type") or "").strip()
        if not doc_id or not target_type:
            continue

        src = db.session.execute(
            text("""
                SELECT CustomerDocumentId, DocumentName, DocumentType, AWSKey,
                       OrganizationType, Prechecking_Id
                FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
                WHERE CustomerDocumentId = :id
            """),
            {"id": doc_id},
        ).fetchone()

        if not src or not src.AWSKey:
            failed.append(target_type)
            continue

        if (src.Prechecking_Id or "") == prechecking_id:
            continue

        exists = db.session.execute(
            text("""
                SELECT COUNT(1) AS cnt
                FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
                WHERE Prechecking_Id = :pid AND DocumentType = :dtype
            """),
            {"pid": prechecking_id, "dtype": target_type},
        ).fetchone()
        if exists and exists.cnt > 0:
            continue

        name_prefix, doc_subfolder = _DOC_META.get(
            target_type, (f"-{target_type.upper().replace('-', '_')}-", target_type)
        )

        org_type = src.OrganizationType or "PR"
        doc_name = f"{prechecking_id}{name_prefix}{_carried_source_filename(src.DocumentName)}"
        aws_prefix = "upload_doc/guarantor" if org_type in ("GUARNPR", "GUARNPT") else "upload_doc"
        aws_key = f"{aws_prefix}/{apless}/{prechecking_id}/{doc_subfolder}/{doc_name}"

        try:
            copied = copy_object(src.AWSKey, aws_key)
        except (BotoCoreError, ClientError):
            current_app.logger.exception("carry_over_documents copy failed for %s", src.AWSKey)
            copied = False

        if not copied:
            failed.append(target_type)
            continue

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
                "org_type": org_type,
                "numb_doc": "1",
                "dtype":    target_type,
                "user":     username,
                "aws_key":  aws_key,
                "pid":      prechecking_id,
            },
        )

    return failed

def _cleanup_ocr_for_nik(prechecking_id: str, nik: str) -> None:
   
    if not nik:
        return

    ocr_row = db.session.execute(
        text("""
            SELECT Id FROM TEMP_CAFLESS_OCR WITH(NOLOCK)
            WHERE Prechecking_Id = :pid AND NIK = :nik
        """),
        {"pid": prechecking_id, "nik": nik},
    ).fetchone()
    if not ocr_row:
        return

    ocr_id = ocr_row.Id
    db.session.execute(
        text("DELETE FROM TEMP_CAFLESS_OCR_Rate WHERE Id = :id"),
        {"id": ocr_id},
    )
    db.session.execute(
        text("DELETE FROM TEMP_CAFLESS_OCR_Dukcapil WHERE Id = :id"),
        {"id": ocr_id},
    )
    db.session.execute(
        text("DELETE FROM TEMP_CAFLESS_OCR WHERE Id = :id"),
        {"id": ocr_id},
    )

@prechecking_individu_bp.route("/generate-apless", methods=["POST"])
@login_required
def generate_temp_apless():
   
    data         = request.get_json(force=True) or {}
    customer_type = (data.get("customer_type") or "PR").strip()
    username      = _username()

    try:
        row = db.session.execute(
            text("""
                SELECT TOP 1
                    RIGHT([Year], 2)      AS YearPart,
                    NextRunningNumber
                FROM TEMP_APLESS WITH(NOLOCK)
                WHERE [Year] = YEAR(GETDATE())
                    AND CustomerType = :ct
            """),
            {"ct": customer_type},
        ).fetchone()

        if row:
            next_num  = row.NextRunningNumber
            year_part = row.YearPart
        else:
            db.session.execute(
                text("""
                    INSERT INTO TEMP_APLESS
                        (CustomerType, [Year], NextRunningNumber, CreatedBy, CreatedDate)
                    VALUES (:ct, YEAR(GETDATE()), 1, 'system', GETDATE())
                """),
                {"ct": customer_type},
            )
            db.session.commit()
            next_num  = 1
            year_part = datetime.now().strftime("%y")

        prefix_map = {"PR": "C", "G": "G"}
        prefix = prefix_map.get(customer_type, "P")

        apless = f"{prefix}{year_part}{str(next_num).zfill(4)}"

        db.session.execute(
            text("""
                UPDATE TEMP_APLESS
                SET NextRunningNumber = NextRunningNumber + 1,
                    UpdatedBy = :user, UpdatedDate = GETDATE()
                WHERE [Year] = YEAR(GETDATE()) AND CustomerType = :ct
            """),
            {"user": username, "ct": customer_type},
        )
        db.session.commit()

        return jsonify(apless)

    except Exception:
        current_app.logger.exception("generate_temp_apless error")
        return jsonify({"error": "Failed to generate APLESS"}), 500

@prechecking_individu_bp.route("/generate-prechecking-id", methods=["POST"])
@login_required
def generate_prechecking_id():
  
    username = _username()
    today    = date.today()

    try:
        row = db.session.execute(
            text("""
                SELECT TOP 1
                    RIGHT([Year], 2) AS YearPart,
                    [Month]          AS MonthPart,
                    [Date]           AS DayPart,
                    NextRunningNumber
                FROM TEMP_PRECHECKING_ID WITH(NOLOCK)
                WHERE [Year]  = YEAR(GETDATE())
                    AND [Month] = MONTH(GETDATE())
                    AND [Date]  = DAY(GETDATE())
            """),
        ).fetchone()

        if row:
            next_num  = row.NextRunningNumber
            year_part = row.YearPart
            mon_part  = row.MonthPart
            day_part  = row.DayPart
        else:
            db.session.execute(
                text("""
                    INSERT INTO TEMP_PRECHECKING_ID
                        ([Year],[Month],[Date],NextRunningNumber,CreatedBy,CreatedDate)
                    VALUES (YEAR(GETDATE()),MONTH(GETDATE()),DAY(GETDATE()),1,'system',GETDATE())
                """),
            )
            db.session.commit()
            next_num  = 1
            year_part = today.strftime("%y")
            mon_part  = today.month
            day_part  = today.day

        prechecking_id = (
            f"{year_part}"
            f"{str(mon_part).zfill(2)}"
            f"{str(day_part).zfill(2)}"
            f"{str(next_num).zfill(4)}"
        )

        db.session.execute(
            text("""
                UPDATE TEMP_PRECHECKING_ID
                SET NextRunningNumber = NextRunningNumber + 1,
                    UpdatedBy = :user, UpdatedDate = GETDATE()
                WHERE [Year]=YEAR(GETDATE())
                  AND [Month]=MONTH(GETDATE())
                  AND [Date]=DAY(GETDATE())
            """),
            {"user": username},
        )
        db.session.commit()

        return jsonify(prechecking_id)

    except Exception:
        current_app.logger.exception("generate_prechecking_id error")
        return jsonify({"error": "Failed to generate Prechecking ID"}), 500

@prechecking_individu_bp.route("/check-customer-history", methods=["POST"])
@login_required
def check_customer_history():
   
    if request.method != "POST":
        return jsonify({"error": "Method not allowed"}), 405

    body         = request.get_json(force=True) or {}
    id_no        = (body.get("idNo")         or "").strip()
    lessee_type  = (body.get("lesseeType")   or "").strip()
    checking_for = (body.get("checking_for") or "C").strip()

    try:
        result = _check_history(id_no, lessee_type, checking_for)
        return jsonify(result)
    except Exception:
        current_app.logger.exception("check_customer_history error")
        return jsonify(["", "", "", ""]), 500

def _check_history(id_no: str, lessee_type: str, checking_for: str):
    message       = ""
    apless        = ""
    types         = ""
    prechecking_id= ""

    if checking_for == "C":
        row_cafless = db.session.execute(
            text("""
                SELECT
                    a.APLESS                             AS final_apless,
                    ISNULL(a.APLESS, b.APLESS)           AS temp_apless,
                    IIF(a.APLESS <> '', '1', '0')        AS Repeat_Order
                FROM CAFLESS a
                    LEFT JOIN TEMP_CAFLESS b
                        ON (a.Id_Card = b.idcardno OR a.NPWP = b.NPWP)
                    AND a.Lessee_TP = b.CustomerType
                WHERE (a.id_card = :id OR a.NPWP = :id)
                  AND a.Lessee_TP = :lt
            """),
            {"id": id_no, "lt": lessee_type},
        ).fetchone()
    else:  # Guarantor
        row_cafless = db.session.execute(
            text("""
                SELECT TOP 1
                    ISNULL(FINAL_APLESS, '') AS final_apless,
                    ISNULL(Apless, '')       AS temp_apless,
                    Repeat_Order
                FROM TEMP_CAFLESS
                WHERE (IdCardNo = :id OR NPWP = :id)
                    AND Check_For  = :cf
                    AND CustomerType = :lt
                ORDER BY Prechecking_Id DESC
            """),
            {"id": id_no, "cf": checking_for, "lt": lessee_type},
        ).fetchone()

    final_apless = (row_cafless.final_apless or "") if row_cafless else ""
    temp_apless  = (row_cafless.temp_apless  or "") if row_cafless else ""
    repeat_order = str(row_cafless.Repeat_Order or "0") if row_cafless else "0"

    apless = final_apless

    row_expired = db.session.execute(
        text("""
            SELECT TOP 1
                CASE
                    WHEN DATEDIFF(DAY, LastActionDate, GETDATE()) <= 30
                    THEN 'TRUE' ELSE 'FALSE'
                END                     AS IsWithin30Days,
                b.Prechecking_Id,
                a.LastApprovalActionCode,
                b.CreatedBy,
                c.Remarks,
                a.LastActionBy,
                a.LastActionDate
            FROM documentApproval a WITH(NOLOCK)
                INNER JOIN TEMP_CAFLESS b WITH(NOLOCK)
                    ON a.DocumentNumber = b.Prechecking_Id
                LEFT JOIN documentApprovalHistory c WITH(NOLOCK)
                    ON a.Id = c.DocumentApprovalId
                AND c.ApprovalActionCode = 'reject'
                AND c.Id = (
                        SELECT MAX(Id) FROM documentApprovalHistory WITH(NOLOCK)
                        WHERE DocumentApprovalId = a.Id
                    )
            WHERE (b.IdCardNo = :id OR b.NPWP = :id)
                AND b.Check_For   = :cf
                AND b.CustomerType = :lt
            ORDER BY LastActionDate DESC
        """),
        {"id": id_no, "cf": checking_for, "lt": lessee_type},
    ).fetchone()

    cust_type_label = "Guarantor" if checking_for == "G" else "Customer"

    if row_expired:
        prechecking_id  = row_expired.Prechecking_Id or ""
        action_code     = (row_expired.LastApprovalActionCode or "").lower()
        is_within_30    = row_expired.IsWithin30Days == "TRUE"
        last_action_by  = row_expired.LastActionBy or ""
        last_action_date= (
            row_expired.LastActionDate.strftime("%Y-%m-%d %H:%M:%S")
            if row_expired.LastActionDate else ""
        )
        remarks         = row_expired.Remarks or ""
        created_by      = row_expired.CreatedBy or ""

        if action_code in ("approve", "draft", "withdraw"):
            if is_within_30:
                message = f"Notification : Prechecking status for this {cust_type_label} is still valid"
                types   = "valid"
                if repeat_order == "1" and not final_apless:
                    apless   = temp_apless
                    message  = "EXPIRED"
                    types    = "expired"
                elif repeat_order == "1" and final_apless:
                    message  = f"Notification : Prechecking status for this {cust_type_label} is still valid"
                    types    = "valid"
            else:
                if not final_apless:
                    message = ""
                    apless  = ""
                else:
                    message = "EXPIRED"
                    types   = "expired"

        elif action_code == "reject":
            message = (
                f"Notification: This {cust_type_label} has been rejected by: "
                f"{last_action_by} on {last_action_date}. "
                f"Reason: {remarks} by CMO : {created_by}"
            )
            types = "reject"

        elif action_code == "submit":
            message = (
                f"Notification : Prechecking status for this {cust_type_label} "
                f"is currently in progress by CMO : {created_by}"
            )
            types = "inprogress"

        else:
            message = ""
            apless  = ""
    else:
        if final_apless and temp_apless and repeat_order == "1":
            message = "EXPIRED"
            types   = "expired"
        else:
            message = ""
            apless  = ""

    return [message, apless, types, prechecking_id]

@prechecking_individu_bp.route("/submit", methods=["POST"])
@login_required
def submit_prechecking():

    username = _username()
    branch   = _branch()
    emp_id   = _emp_id()

    body = request.form.to_dict() if request.form else (request.get_json(force=True) or {})

    def g(key, default=""):
        return (body.get(key) or default).strip() if isinstance(body.get(key), str) else (body.get(key) or default)

    prechecking_id  = g("prechecking_id")
    apless          = g("apless")
    cust_type       = g("cust_type", "PR")
    lessee_type     = g("lessee_type", "PR")
    check_for       = g("check_for", "C")
    cust_new_ro     = 0 if g("cust_new_ro", "New") == "New" else 1
    existing_apless = g("existing_apless")
    nationality     = g("cust_nationality_type", "WNI")
    marital         = g("marital_status")
    wna_marital     = g("wna_marital_status")
    is_carro        = int(g("is_carro_type", "1"))
    note_pr         = g("note_prechecking_pr")
    note_pt         = g("note_prechecking_pt")

    if not prechecking_id:
        return jsonify({"success": False, "message": "prechecking_id is required"}), 400

    errors = {}
    required_cust = [
        ("cust_id_card_no", "NIK"),
        ("cust_name",       "Nama"),
        ("cust_pob",        "Tempat Lahir"),
        ("cust_dob",        "Tanggal Lahir"),
        ("cust_gender",     "Jenis Kelamin"),
        ("cust_address",    "Alamat"),
        ("cust_rt",         "RT"),
        ("cust_rw",         "RW"),
        ("cust_subdistrict","Kelurahan/Desa"),
        ("cust_district",   "Kecamatan"),
        ("cust_city",       "Kota/Kabupaten"),
        ("cust_province",   "Provinsi"),
        ("cust_religion",   "Agama"),
        ("cust_job",        "Pekerjaan"),
    ]
    if nationality == "WNI":
        for key, label in required_cust:
            if not g(key):
                errors[f"{key}_error"] = f"{label} is required"
    if errors:
        return jsonify({"success": False, "errors": errors}), 422

    _marital_map = {
        "BELUM KAWIN": "S", "KAWIN": "M", "KAWIN TERCATAT": "M",
        "KAWIN BELUM TERCATAT": "O", "PERJANJIAN PRANIKAH": "P",
        "CERAI HIDUP": "D", "CERAI MATI": "D",
    }
    
    def nm(val):
        return _marital_map.get((val or "").strip().upper(), val)

    marital     = nm(marital)
    wna_marital = nm(wna_marital)

    nik          = g("cust_id_card_no")
    cust_name    = g("cust_name")
    cust_dob     = g("cust_dob")
    cust_citizen = g("cust_citizen", "WNI") if nationality == "WNI" else "WNA"

    sp_nik       = g("cust_spouse_id_card_no")

    wna_name     = g("wna_name")
    wna_idcard   = g("wna_idcard_no")
    wna_sp_name  = g("wna_spouse_name")
    wna_sp_id    = g("wna_spouse_idcard_no")

    wna_sp_nik   = g("cust_wna_spouse_id_card_no")

    sp_nationality     = (g("cust_spouse_nationality_type") or g("cust_spouse_citizen") or "WNI").strip().upper()
    wna_sp_nationality = (g("wna_spouse_nationality_type") or g("cust_wna_spouse_citizen") or "WNI").strip().upper()

    sp_citizen     = "WNA" if sp_nationality == "WNA" else "WNI"
    wna_sp_citizen = "WNA" if wna_sp_nationality == "WNA" else "WNI"

    cust_id_type   = _norm_id_type(g("cust_id_type"), nationality)
    sp_id_type     = _norm_id_type(g("cust_spouse_id_type"), sp_nationality)
    wna_sp_id_type = _norm_id_type(g("cust_spouse_id_type"), wna_sp_nationality)

    is_married     = marital in ("M", "O")
    is_wna_married = wna_marital in ("M", "O")

    try:
        count_row = db.session.execute(
            text("""
                SELECT COUNT(1) AS cnt
                FROM TEMP_CAFLESS WITH(NOLOCK)
                WHERE Apless = :apless AND Prechecking_Id = :pid
            """),
            {"apless": apless, "pid": prechecking_id},
        ).fetchone()
        already_exists = (count_row.cnt > 0) if count_row else False

        approval_form_row = db.session.execute(
            text("SELECT Id FROM mstApprovalForm WHERE ApprovalFormKey = 'cam-request'"),
        ).fetchone()
        if not approval_form_row:
            return jsonify({"success": False, "message": "Approval Form Master is not completed. Please contact your administrator."}), 500
        approval_form_id = approval_form_row.Id

        if not already_exists:

            if nationality == "WNI":
               
                db.session.execute(text("""
                    INSERT INTO TEMP_CAFLESS
                        (Apless, CustomerType, LesseeType, LesseeName, IdCardNo, NPWP,
                         MaritalStatus, CreatedBy, CreatedDate,
                         Prechecking_Id, Check_For, Repeat_Order, Notes, Carro)
                    VALUES
                        (:apless, :cust_type, :lessee_type, :cust_name, :nik, '',
                         :marital, :username, GETDATE(),
                         :pid, :check_for, :new_ro, :note_pr, :is_carro)
                """), {
                    "apless": apless, "cust_type": cust_type, "lessee_type": lessee_type,
                    "cust_name": cust_name, "nik": nik, "marital": marital,
                    "username": username, "pid": prechecking_id, "check_for": check_for,
                    "new_ro": cust_new_ro, "note_pr": note_pr, "is_carro": is_carro,
                })

               
                db.session.execute(text("""
                    INSERT INTO TEMP_CAFLESS_OCR
                        (Prechecking_Id, OCR_For, Citizen, Id_Type, NIK, Nama, Tempat_Lahir,
                         Tgl_Lahir, Jenis_Kelamin, Golongan_Darah, Alamat, RT, RW,
                         Kelurahan, Kecamatan, Kota, Provinsi, Agama, Pekerjaan,
                         Status_Perkawinan, Kewarnegaraan, Foto, Tanda_Tangan)
                    VALUES
                        (:pid, :check_for, :citizen, :id_type, :nik, :nama, :pob,
                         :dob, :gender, :blood, :addr, :rt, :rw,
                         :subdistrict, :district, :city, :province, :religion, :job,
                         :marital, :citizen2, :photo, :sign)
                """), {
                    "pid": prechecking_id, "check_for": check_for,
                    "citizen": cust_citizen, "id_type": cust_id_type, "nik": nik,
                    "nama": cust_name, "pob": g("cust_pob"),
                    "dob": _sql_date(g("cust_dob")),
                    "gender": g("cust_gender"),
                    "blood": g("cust_blood_type"), "addr": g("cust_address"),
                    "rt": g("cust_rt"), "rw": g("cust_rw"),
                    "subdistrict": g("cust_subdistrict"), "district": g("cust_district"),
                    "city": g("cust_city"), "province": g("cust_province"),
                    "religion": g("cust_religion"), "job": g("cust_job"),
                    "marital": marital, "citizen2": cust_citizen,
                    "photo": g("cust_photo_hidden"), "sign": g("cust_signature_hidden"),
                })

                cust_ocr_row = db.session.execute(
                    text("SELECT Id FROM TEMP_CAFLESS_OCR WITH(NOLOCK) WHERE Prechecking_Id = :pid AND NIK = :nik"),
                    {"pid": prechecking_id, "nik": nik},
                ).fetchone()
                cust_id = cust_ocr_row.Id if cust_ocr_row else 0

                db.session.execute(text("""
                    INSERT INTO TEMP_CAFLESS_OCR_Rate
                        (Id, NIK, Nama, Tempat_Lahir, Tgl_Lahir, Jenis_Kelamin,
                         Golongan_Darah, Alamat, RT, RW, Kelurahan, Kecamatan,
                         Kota, Provinsi, Agama, Pekerjaan, Kewarnegaraan)
                    VALUES
                        (:id, :nik, :nama, :pob, :dob, :gender,
                         :blood, :addr, :rt, :rw, :subdistrict, :district,
                         :city, :province, :religion, :job, :citizen)
                """), {
                    "id": cust_id,
                    "nik":        _strip_non_digit(g("val_cust_id_card_no")),
                    "nama":       _strip_non_digit(g("val_cust_name")),
                    "pob":        _strip_non_digit(g("val_cust_pob")),
                    "dob":        _strip_non_digit(g("val_cust_dob")),
                    "gender":     _strip_non_digit(g("val_cust_gender")),
                    "blood":      _strip_non_digit(g("val_cust_blood_type")),
                    "addr":       _strip_non_digit(g("val_cust_address")),
                    "rt":         _strip_non_digit(g("val_cust_rt")),
                    "rw":         _strip_non_digit(g("val_cust_rw")),
                    "subdistrict":_strip_non_digit(g("val_cust_subdistrict")),
                    "district":   _strip_non_digit(g("val_cust_district")),
                    "city":       _strip_non_digit(g("val_cust_city")),
                    "province":   _strip_non_digit(g("val_cust_province")),
                    "religion":   _strip_non_digit(g("val_cust_religion")),
                    "job":        _strip_non_digit(g("val_cust_job")),
                    "citizen":    _strip_non_digit(g("val_cust_citizen")),
                })

                db.session.execute(text("""
                    INSERT INTO TEMP_CAFLESS_OCR_Dukcapil
                        (Id, NIK, Nama, Tempat_Lahir, Tgl_Lahir, Jenis_Kelamin,
                         Alamat, RT, RW, Kelurahan, Kecamatan, Kota, Provinsi, Pekerjaan)
                    VALUES
                        (:id, :nik, :nama, :pob, :dob, :gender, :addr,
                         :rt, :rw, :subdistrict, :district, :city, :province, :job)
                """), {
                    "id":         cust_id,
                    "nik":        _to_bit(g("ver_cust_id_card_no")),
                    "nama":       _to_bit(g("ver_cust_name")),
                    "pob":        _to_bit(g("ver_cust_pob")),
                    "dob":        _to_bit(g("ver_cust_dob")),
                    "gender":     _to_bit(g("ver_cust_gender")),
                    "addr":       _to_bit(g("ver_cust_address")),
                    "rt":         _to_bit(g("ver_cust_rt")),
                    "rw":         _to_bit(g("ver_cust_rw")),
                    "subdistrict":_to_bit(g("ver_cust_subdistrict")),
                    "district":   _to_bit(g("ver_cust_district")),
                    "city":       _to_bit(g("ver_cust_city")),
                    "province":   _to_bit(g("ver_cust_province")),
                    "job":        _to_bit(g("ver_cust_job")),
                })

                if is_married:
                    if sp_citizen == "WNI":
                        sp_exists = db.session.execute(
                            text("SELECT COUNT(1) AS cnt FROM TEMP_CAFLESS_OCR WHERE Prechecking_Id = :pid AND OCR_For = 'S'"),
                            {"pid": prechecking_id},
                        ).fetchone()

                        if sp_exists and sp_exists.cnt > 0:
                            db.session.execute(text("""
                                UPDATE TEMP_CAFLESS_OCR SET
                                    OCR_For='S', Citizen=:citizen, Id_Type=:id_type, NIK=:nik, Nama=:nama,
                                    Tempat_Lahir=:pob, Tgl_Lahir=:dob, Jenis_Kelamin=:gender,
                                    Golongan_Darah=:blood, Alamat=:addr, RT=:rt, RW=:rw,
                                    Kelurahan=:subdistrict, Kecamatan=:district, Kota=:city,
                                    Provinsi=:province, Agama=:religion, Pekerjaan=:job,
                                    Status_Perkawinan=:marital, Kewarnegaraan=:citizen2,
                                    Foto=:photo, Tanda_Tangan=:sign, UpdatedDate=GETDATE()
                                WHERE Prechecking_Id=:pid AND OCR_For='S'
                            """), {
                                "pid": prechecking_id, "citizen": sp_citizen, "id_type": sp_id_type,
                                "nik": sp_nik, "nama": g("cust_spouse_name"),
                                "pob": g("cust_spouse_pob"),
                                "dob": _sql_date(g("cust_spouse_dob")),
                                "gender": g("cust_spouse_gender"), "blood": g("cust_spouse_blood_type"),
                                "addr": g("cust_spouse_address"), "rt": g("cust_spouse_rt"),
                                "rw": g("cust_spouse_rw"), "subdistrict": g("cust_spouse_subdistrict"),
                                "district": g("cust_spouse_district"), "city": g("cust_spouse_city"),
                                "province": g("cust_spouse_province"), "religion": g("cust_spouse_religion"),
                                "job": g("cust_spouse_job"), "marital": marital,
                                "citizen2": sp_citizen,
                                "photo": g("cust_spouse_photo_hidden"), "sign": g("cust_spouse_signature_hidden"),
                            })

                            sp_ocr_row = db.session.execute(
                                text("SELECT Id FROM TEMP_CAFLESS_OCR WITH(NOLOCK) WHERE Prechecking_Id=:pid AND OCR_For='S'"),
                                {"pid": prechecking_id},
                            ).fetchone()
                            sp_id = sp_ocr_row.Id if sp_ocr_row else 0

                            db.session.execute(text("""
                                UPDATE TEMP_CAFLESS_OCR_Rate SET
                                    NIK=:nik, Nama=:nama, Tempat_Lahir=:pob, Tgl_Lahir=:dob,
                                    Jenis_Kelamin=:gender, Golongan_Darah=:blood, Alamat=:addr,
                                    RT=:rt, RW=:rw, Kelurahan=:subdistrict, Kecamatan=:district,
                                    Kota=:city, Provinsi=:province, Agama=:religion,
                                    Pekerjaan=:job, Kewarnegaraan=:citizen
                                WHERE Id=:id
                            """), {
                                "id": sp_id,
                                "nik":        _strip_non_digit(g("val_cust_spouse_id_card_no")),
                                "nama":       _strip_non_digit(g("val_cust_spouse_name")),
                                "pob":        _strip_non_digit(g("val_cust_spouse_pob")),
                                "dob":        _strip_non_digit(g("val_cust_spouse_dob")),
                                "gender":     _strip_non_digit(g("val_cust_spouse_gender")),
                                "blood":      _strip_non_digit(g("val_cust_spouse_blood_type")),
                                "addr":       _strip_non_digit(g("val_cust_spouse_address")),
                                "rt":         _strip_non_digit(g("val_cust_spouse_rt")),
                                "rw":         _strip_non_digit(g("val_cust_spouse_rw")),
                                "subdistrict":_strip_non_digit(g("val_cust_spouse_subdistrict")),
                                "district":   _strip_non_digit(g("val_cust_spouse_district")),
                                "city":       _strip_non_digit(g("val_cust_spouse_city")),
                                "province":   _strip_non_digit(g("val_cust_spouse_province")),
                                "religion":   _strip_non_digit(g("val_cust_spouse_religion")),
                                "job":        _strip_non_digit(g("val_cust_spouse_job")),
                                "citizen":    _strip_non_digit(g("val_cust_spouse_citizen")),
                            })

                            db.session.execute(text("""
                                UPDATE TEMP_CAFLESS_OCR_Dukcapil SET
                                    NIK=:nik, Nama=:nama,
                                    Tempat_Lahir=:pob, Tgl_Lahir=:dob,
                                    Jenis_Kelamin=:gender, Alamat=:addr,
                                    RT=:rt, RW=:rw,
                                    Kelurahan=:subdistrict, Kecamatan=:district,
                                    Kota=:city, Provinsi=:province,
                                    Pekerjaan=:job
                                WHERE Id=:id
                            """), {
                                "id": sp_id,
                                "nik": _to_bit(g("ver_cust_spouse_id_card_no")), "nama": _to_bit(g("ver_cust_spouse_name")),
                                "pob": _to_bit(g("ver_cust_spouse_pob")), "dob": _to_bit(g("ver_cust_spouse_dob")),
                                "gender": _to_bit(g("ver_cust_spouse_gender")), "addr": _to_bit(g("ver_cust_spouse_address")),
                                "rt": _to_bit(g("ver_cust_spouse_rt")), "rw": _to_bit(g("ver_cust_spouse_rw")),
                                "subdistrict": _to_bit(g("ver_cust_spouse_subdistrict")),
                                "district": _to_bit(g("ver_cust_spouse_district")),
                                "city": _to_bit(g("ver_cust_spouse_city")),
                                "province": _to_bit(g("ver_cust_spouse_province")),
                                "job": _to_bit(g("ver_cust_spouse_job")),
                            })

                        else:
                            db.session.execute(text("""
                                INSERT INTO TEMP_CAFLESS_OCR
                                    (Prechecking_Id, OCR_For, Citizen, Id_Type, NIK, Nama, Tempat_Lahir,
                                     Tgl_Lahir, Jenis_Kelamin, Golongan_Darah, Alamat, RT, RW,
                                     Kelurahan, Kecamatan, Kota, Provinsi, Agama, Pekerjaan,
                                     Status_Perkawinan, Kewarnegaraan, Foto, Tanda_Tangan)
                                VALUES
                                    (:pid,'S',:citizen,:id_type,:nik,:nama,:pob,
                                     :dob,:gender,:blood,:addr,:rt,:rw,
                                     :subdistrict,:district,:city,:province,:religion,:job,
                                     :marital,:citizen2,:photo,:sign)
                            """), {
                                "pid": prechecking_id, "citizen": sp_citizen, "id_type": sp_id_type,
                                "nik": sp_nik, "nama": g("cust_spouse_name"),
                                "pob": g("cust_spouse_pob"),
                                "dob": _sql_date(g("cust_spouse_dob")),
                                "gender": g("cust_spouse_gender"), "blood": g("cust_spouse_blood_type"),
                                "addr": g("cust_spouse_address"), "rt": g("cust_spouse_rt"),
                                "rw": g("cust_spouse_rw"), "subdistrict": g("cust_spouse_subdistrict"),
                                "district": g("cust_spouse_district"), "city": g("cust_spouse_city"),
                                "province": g("cust_spouse_province"), "religion": g("cust_spouse_religion"),
                                "job": g("cust_spouse_job"), "marital": marital,
                                "citizen2": sp_citizen,
                                "photo": g("cust_spouse_photo_hidden"), "sign": g("cust_spouse_signature_hidden"),
                            })

                            sp_ocr_row = db.session.execute(
                                text("SELECT Id FROM TEMP_CAFLESS_OCR WITH(NOLOCK) WHERE Prechecking_Id=:pid AND OCR_For='S'"),
                                {"pid": prechecking_id},
                            ).fetchone()
                            sp_id = sp_ocr_row.Id if sp_ocr_row else 0

                            db.session.execute(text("""
                                INSERT INTO TEMP_CAFLESS_OCR_Rate
                                    (Id, NIK, Nama, Tempat_Lahir, Tgl_Lahir, Jenis_Kelamin,
                                     Golongan_Darah, Alamat, RT, RW, Kelurahan, Kecamatan,
                                     Kota, Provinsi, Agama, Pekerjaan, Kewarnegaraan)
                                VALUES
                                    (:id,:nik,:nama,:pob,:dob,:gender,
                                     :blood,:addr,:rt,:rw,:subdistrict,:district,
                                     :city,:province,:religion,:job,:citizen)
                            """), {
                                "id": sp_id,
                                "nik":        _strip_non_digit(g("val_cust_spouse_id_card_no")),
                                "nama":       _strip_non_digit(g("val_cust_spouse_name")),
                                "pob":        _strip_non_digit(g("val_cust_spouse_pob")),
                                "dob":        _strip_non_digit(g("val_cust_spouse_dob")),
                                "gender":     _strip_non_digit(g("val_cust_spouse_gender")),
                                "blood":      _strip_non_digit(g("val_cust_spouse_blood_type")),
                                "addr":       _strip_non_digit(g("val_cust_spouse_address")),
                                "rt":         _strip_non_digit(g("val_cust_spouse_rt")),
                                "rw":         _strip_non_digit(g("val_cust_spouse_rw")),
                                "subdistrict":_strip_non_digit(g("val_cust_spouse_subdistrict")),
                                "district":   _strip_non_digit(g("val_cust_spouse_district")),
                                "city":       _strip_non_digit(g("val_cust_spouse_city")),
                                "province":   _strip_non_digit(g("val_cust_spouse_province")),
                                "religion":   _strip_non_digit(g("val_cust_spouse_religion")),
                                "job":        _strip_non_digit(g("val_cust_spouse_job")),
                                "citizen":    _strip_non_digit(g("val_cust_spouse_citizen")),
                            })

                            db.session.execute(text("""
                                INSERT INTO TEMP_CAFLESS_OCR_Dukcapil
                                    (Id, NIK, Nama, Tempat_Lahir, Tgl_Lahir, Jenis_Kelamin,
                                     Alamat, RT, RW, Kelurahan, Kecamatan, Kota, Provinsi, Pekerjaan)
                                VALUES
                                    (:id, :nik, :nama, :pob, :dob, :gender, :addr,
                                     :rt, :rw, :subdistrict, :district, :city, :province, :job)
                            """), {
                                "id": sp_id,
                                "nik": _to_bit(g("ver_cust_spouse_id_card_no")), "nama": _to_bit(g("ver_cust_spouse_name")),
                                "pob": _to_bit(g("ver_cust_spouse_pob")), "dob": _to_bit(g("ver_cust_spouse_dob")),
                                "gender": _to_bit(g("ver_cust_spouse_gender")), "addr": _to_bit(g("ver_cust_spouse_address")),
                                "rt": _to_bit(g("ver_cust_spouse_rt")), "rw": _to_bit(g("ver_cust_spouse_rw")),
                                "subdistrict": _to_bit(g("ver_cust_spouse_subdistrict")),
                                "district": _to_bit(g("ver_cust_spouse_district")),
                                "city": _to_bit(g("ver_cust_spouse_city")),
                                "province": _to_bit(g("ver_cust_spouse_province")),
                                "job": _to_bit(g("ver_cust_spouse_job")),
                            })

                    else:
                        db.session.execute(text("""
                            INSERT INTO TEMP_CAFLESS_OCR
                                (Prechecking_Id, OCR_For, Citizen, Id_Type, NIK, Nama, Kewarnegaraan, UpdatedDate)
                            VALUES (:pid,'S','WNA',:id_type,:nik,:nama,'WNA',GETDATE())
                        """), {
                            "pid": prechecking_id, "id_type": sp_id_type,
                            "nik": wna_sp_id, "nama": wna_sp_name,
                        })

            else:
                db.session.execute(text("""
                    INSERT INTO TEMP_CAFLESS
                        (Apless, CustomerType, LesseeType, LesseeName, IdCardNo, NPWP,
                         MaritalStatus, CreatedBy, CreatedDate,
                         Prechecking_Id, Check_For, Repeat_Order, Notes, Carro)
                    VALUES
                        (:apless,:cust_type,:lessee_type,:wna_name,:wna_idcard,'',
                         :wna_marital,:username,GETDATE(),
                         :pid,:check_for,:new_ro,:note_pr,:is_carro)
                """), {
                    "apless": apless, "cust_type": cust_type, "lessee_type": lessee_type,
                    "wna_name": wna_name, "wna_idcard": wna_idcard,
                    "wna_marital": wna_marital, "username": username,
                    "pid": prechecking_id, "check_for": check_for,
                    "new_ro": cust_new_ro, "note_pr": note_pr, "is_carro": is_carro,
                })

                db.session.execute(text("""
                    INSERT INTO TEMP_CAFLESS_OCR
                        (Prechecking_Id, OCR_For, Citizen, Id_Type, NIK, Nama,
                         Status_Perkawinan, Kewarnegaraan)
                    VALUES (:pid,:check_for,'WNA',:id_type,:nik,:nama,:wna_marital,'WNA')
                """), {
                    "pid": prechecking_id, "check_for": check_for, "id_type": cust_id_type,
                    "nik": wna_idcard, "nama": wna_name, "wna_marital": wna_marital,
                })

                if is_wna_married:
                    if wna_sp_citizen == "WNI":
                        sp_exists = db.session.execute(
                            text("SELECT COUNT(1) AS cnt FROM TEMP_CAFLESS_OCR WHERE Prechecking_Id=:pid AND OCR_For='S'"),
                            {"pid": prechecking_id},
                        ).fetchone()

                        if sp_exists and sp_exists.cnt > 0:
                            db.session.execute(text("""
                                UPDATE TEMP_CAFLESS_OCR SET
                                    OCR_For='S', Citizen=:citizen, Id_Type=:id_type, NIK=:nik, Nama=:nama,
                                    Tempat_Lahir=:pob, Tgl_Lahir=:dob, Jenis_Kelamin=:gender,
                                    Golongan_Darah=:blood, Alamat=:addr, RT=:rt, RW=:rw,
                                    Kelurahan=:subdistrict, Kecamatan=:district, Kota=:city,
                                    Provinsi=:province, Agama=:religion, Pekerjaan=:job,
                                    Status_Perkawinan=:marital, Kewarnegaraan=:citizen2,
                                    Foto=:photo, Tanda_Tangan=:sign, UpdatedDate=GETDATE()
                                WHERE Prechecking_Id=:pid AND OCR_For='S'
                            """), {
                                "pid": prechecking_id, "citizen": wna_sp_citizen, "id_type": wna_sp_id_type,
                                "nik": wna_sp_nik, "nama": g("cust_wna_spouse_name"),
                                "pob": g("cust_wna_spouse_pob"),
                                "dob": _sql_date(g("cust_wna_spouse_dob")),
                                "gender": g("cust_wna_spouse_gender"), "blood": g("cust_wna_spouse_blood_type"),
                                "addr": g("cust_wna_spouse_address"), "rt": g("cust_wna_spouse_rt"),
                                "rw": g("cust_wna_spouse_rw"), "subdistrict": g("cust_wna_spouse_subdistrict"),
                                "district": g("cust_wna_spouse_district"), "city": g("cust_wna_spouse_city"),
                                "province": g("cust_wna_spouse_province"), "religion": g("cust_wna_spouse_religion"),
                                "job": g("cust_wna_spouse_job"), "marital": wna_marital,
                                "citizen2": wna_sp_citizen,
                                "photo": g("cust_wna_spouse_photo_hidden"), "sign": g("cust_wna_spouse_signature_hidden"),
                            })

                            wna_sp_ocr = db.session.execute(
                                text("SELECT Id FROM TEMP_CAFLESS_OCR WITH(NOLOCK) WHERE Prechecking_Id=:pid AND OCR_For='S'"),
                                {"pid": prechecking_id},
                            ).fetchone()
                            wna_sp_ocr_id = wna_sp_ocr.Id if wna_sp_ocr else 0

                            db.session.execute(text("""
                                UPDATE TEMP_CAFLESS_OCR_Rate SET
                                    NIK=:nik, Nama=:nama, Tempat_Lahir=:pob, Tgl_Lahir=:dob,
                                    Jenis_Kelamin=:gender, Golongan_Darah=:blood, Alamat=:addr,
                                    RT=:rt, RW=:rw, Kelurahan=:subdistrict, Kecamatan=:district,
                                    Kota=:city, Provinsi=:province, Agama=:religion,
                                    Pekerjaan=:job, Kewarnegaraan=:citizen
                                WHERE Id=:id
                            """), {
                                "id": wna_sp_ocr_id,
                                "nik":        _strip_non_digit(g("val_cust_wna_spouse_id_card_no")),
                                "nama":       _strip_non_digit(g("val_cust_wna_spouse_name")),
                                "pob":        _strip_non_digit(g("val_cust_wna_spouse_pob")),
                                "dob":        _strip_non_digit(g("val_cust_wna_spouse_dob")),
                                "gender":     _strip_non_digit(g("val_cust_wna_spouse_gender")),
                                "blood":      _strip_non_digit(g("val_cust_wna_spouse_blood_type")),
                                "addr":       _strip_non_digit(g("val_cust_wna_spouse_address")),
                                "rt":         _strip_non_digit(g("val_cust_wna_spouse_rt")),
                                "rw":         _strip_non_digit(g("val_cust_wna_spouse_rw")),
                                "subdistrict":_strip_non_digit(g("val_cust_wna_spouse_subdistrict")),
                                "district":   _strip_non_digit(g("val_cust_wna_spouse_district")),
                                "city":       _strip_non_digit(g("val_cust_wna_spouse_city")),
                                "province":   _strip_non_digit(g("val_cust_wna_spouse_province")),
                                "religion":   _strip_non_digit(g("val_cust_wna_spouse_religion")),
                                "job":        _strip_non_digit(g("val_cust_wna_spouse_job")),
                                "citizen":    _strip_non_digit(g("val_cust_wna_spouse_citizen")),
                            })

                            db.session.execute(text("""
                                UPDATE TEMP_CAFLESS_OCR_Dukcapil SET
                                    NIK=:nik, Nama=:nama,
                                    Tempat_Lahir=:pob, Tgl_Lahir=:dob,
                                    Jenis_Kelamin=:gender, Alamat=:addr,
                                    RT=:rt, RW=:rw,
                                    Kelurahan=:subdistrict, Kecamatan=:district,
                                    Kota=:city, Provinsi=:province,
                                    Pekerjaan=:job
                                WHERE Id=:id
                            """), {
                                "id": wna_sp_ocr_id,
                                "nik": _to_bit(g("ver_cust_wna_spouse_id_card_no")), "nama": _to_bit(g("ver_cust_wna_spouse_name")),
                                "pob": _to_bit(g("ver_cust_wna_spouse_pob")), "dob": _to_bit(g("ver_cust_wna_spouse_dob")),
                                "gender": _to_bit(g("ver_cust_wna_spouse_gender")), "addr": _to_bit(g("ver_cust_wna_spouse_address")),
                                "rt": _to_bit(g("ver_cust_wna_spouse_rt")), "rw": _to_bit(g("ver_cust_wna_spouse_rw")),
                                "subdistrict": _to_bit(g("ver_cust_wna_spouse_subdistrict")),
                                "district": _to_bit(g("ver_cust_wna_spouse_district")),
                                "city": _to_bit(g("ver_cust_wna_spouse_city")),
                                "province": _to_bit(g("ver_cust_wna_spouse_province")),
                                "job": _to_bit(g("ver_cust_wna_spouse_job")),
                            })

                        else:
                            db.session.execute(text("""
                                INSERT INTO TEMP_CAFLESS_OCR
                                    (Prechecking_Id, OCR_For, Citizen, Id_Type, NIK, Nama, Tempat_Lahir,
                                     Tgl_Lahir, Jenis_Kelamin, Golongan_Darah, Alamat, RT, RW,
                                     Kelurahan, Kecamatan, Kota, Provinsi, Agama, Pekerjaan,
                                     Status_Perkawinan, Kewarnegaraan, Foto, Tanda_Tangan)
                                VALUES
                                    (:pid,'S',:citizen,:id_type,:nik,:nama,:pob,
                                     :dob,:gender,:blood,:addr,:rt,:rw,
                                     :subdistrict,:district,:city,:province,:religion,:job,
                                     :marital,:citizen2,:photo,:sign)
                            """), {
                                "pid": prechecking_id, "citizen": wna_sp_citizen, "id_type": wna_sp_id_type,
                                "nik": wna_sp_nik, "nama": g("cust_wna_spouse_name"),
                                "pob": g("cust_wna_spouse_pob"),
                                "dob": _sql_date(g("cust_wna_spouse_dob")),
                                "gender": g("cust_wna_spouse_gender"), "blood": g("cust_wna_spouse_blood_type"),
                                "addr": g("cust_wna_spouse_address"), "rt": g("cust_wna_spouse_rt"),
                                "rw": g("cust_wna_spouse_rw"), "subdistrict": g("cust_wna_spouse_subdistrict"),
                                "district": g("cust_wna_spouse_district"), "city": g("cust_wna_spouse_city"),
                                "province": g("cust_wna_spouse_province"), "religion": g("cust_wna_spouse_religion"),
                                "job": g("cust_wna_spouse_job"), "marital": wna_marital,
                                "citizen2": wna_sp_citizen,
                                "photo": g("cust_wna_spouse_photo_hidden"), "sign": g("cust_wna_spouse_signature_hidden"),
                            })

                            wna_sp_ocr = db.session.execute(
                                text("SELECT Id FROM TEMP_CAFLESS_OCR WITH(NOLOCK) WHERE Prechecking_Id=:pid AND NIK=:nik"),
                                {"pid": prechecking_id, "nik": wna_sp_nik},
                            ).fetchone()
                            wna_sp_ocr_id = wna_sp_ocr.Id if wna_sp_ocr else 0

                            db.session.execute(text("""
                                INSERT INTO TEMP_CAFLESS_OCR_Rate
                                    (Id, NIK, Nama, Tempat_Lahir, Tgl_Lahir, Jenis_Kelamin,
                                     Golongan_Darah, Alamat, RT, RW, Kelurahan, Kecamatan,
                                     Kota, Provinsi, Agama, Pekerjaan, Kewarnegaraan)
                                VALUES
                                    (:id,:nik,:nama,:pob,:dob,:gender,
                                     :blood,:addr,:rt,:rw,:subdistrict,:district,
                                     :city,:province,:religion,:job,:citizen)
                            """), {
                                "id": wna_sp_ocr_id,
                                "nik":        _strip_non_digit(g("val_cust_wna_spouse_id_card_no")),
                                "nama":       _strip_non_digit(g("val_cust_wna_spouse_name")),
                                "pob":        _strip_non_digit(g("val_cust_wna_spouse_pob")),
                                "dob":        _strip_non_digit(g("val_cust_wna_spouse_dob")),
                                "gender":     _strip_non_digit(g("val_cust_wna_spouse_gender")),
                                "blood":      _strip_non_digit(g("val_cust_wna_spouse_blood_type")),
                                "addr":       _strip_non_digit(g("val_cust_wna_spouse_address")),
                                "rt":         _strip_non_digit(g("val_cust_wna_spouse_rt")),
                                "rw":         _strip_non_digit(g("val_cust_wna_spouse_rw")),
                                "subdistrict":_strip_non_digit(g("val_cust_wna_spouse_subdistrict")),
                                "district":   _strip_non_digit(g("val_cust_wna_spouse_district")),
                                "city":       _strip_non_digit(g("val_cust_wna_spouse_city")),
                                "province":   _strip_non_digit(g("val_cust_wna_spouse_province")),
                                "religion":   _strip_non_digit(g("val_cust_wna_spouse_religion")),
                                "job":        _strip_non_digit(g("val_cust_wna_spouse_job")),
                                "citizen":    _strip_non_digit(g("val_cust_wna_spouse_citizen")),
                            })

                            db.session.execute(text("""
                                INSERT INTO TEMP_CAFLESS_OCR_Dukcapil
                                    (Id, NIK, Nama, Tempat_Lahir, Tgl_Lahir, Jenis_Kelamin,
                                     Alamat, RT, RW, Kelurahan, Kecamatan, Kota, Provinsi, Pekerjaan)
                                VALUES
                                    (:id, :nik, :nama, :pob, :dob, :gender, :addr,
                                     :rt, :rw, :subdistrict, :district, :city, :province, :job)
                            """), {
                                "id": wna_sp_ocr_id,
                                "nik": _to_bit(g("ver_cust_wna_spouse_id_card_no")), "nama": _to_bit(g("ver_cust_wna_spouse_name")),
                                "pob": _to_bit(g("ver_cust_wna_spouse_pob")), "dob": _to_bit(g("ver_cust_wna_spouse_dob")),
                                "gender": _to_bit(g("ver_cust_wna_spouse_gender")), "addr": _to_bit(g("ver_cust_wna_spouse_address")),
                                "rt": _to_bit(g("ver_cust_wna_spouse_rt")), "rw": _to_bit(g("ver_cust_wna_spouse_rw")),
                                "subdistrict": _to_bit(g("ver_cust_wna_spouse_subdistrict")),
                                "district": _to_bit(g("ver_cust_wna_spouse_district")),
                                "city": _to_bit(g("ver_cust_wna_spouse_city")),
                                "province": _to_bit(g("ver_cust_wna_spouse_province")),
                                "job": _to_bit(g("ver_cust_wna_spouse_job")),
                            })

                    else:
                        db.session.execute(text("""
                            INSERT INTO TEMP_CAFLESS_OCR
                                (Prechecking_Id, OCR_For, Citizen, Id_Type, NIK, Nama, Kewarnegaraan)
                            VALUES (:pid,'S','WNA',:id_type,:nik,:nama,'WNA')
                        """), {
                            "pid": prechecking_id, "id_type": wna_sp_id_type,
                            "nik": wna_sp_id, "nama": wna_sp_name,
                        })

        else:

            if nationality == "WNI":
                db.session.execute(text("""
                    UPDATE TEMP_CAFLESS SET
                        Apless=:apless, CustomerType=:cust_type, LesseeType=:lessee_type,
                        LesseeName=:cust_name, NPWP='', MaritalStatus=:marital,
                        CreatedBy=:username, CreatedDate=GETDATE(),
                        Check_For=:check_for, Repeat_Order=:new_ro,
                        Notes=:note_pr, Carro=:is_carro
                    WHERE IdCardNo=:nik AND Prechecking_Id=:pid
                """), {
                    "apless": apless, "cust_type": cust_type, "lessee_type": lessee_type,
                    "cust_name": cust_name, "marital": marital, "username": username,
                    "check_for": check_for, "new_ro": cust_new_ro, "note_pr": note_pr,
                    "is_carro": is_carro, "nik": nik, "pid": prechecking_id,
                })

                db.session.execute(text("""
                    UPDATE TEMP_CAFLESS_OCR SET
                        OCR_For=:check_for, Citizen=:citizen, Id_Type=:id_type, Nama=:nama,
                        Tempat_Lahir=:pob, Tgl_Lahir=:dob, Jenis_Kelamin=:gender,
                        Golongan_Darah=:blood, Alamat=:addr, RT=:rt, RW=:rw,
                        Kelurahan=:subdistrict, Kecamatan=:district, Kota=:city,
                        Provinsi=:province, Agama=:religion, Pekerjaan=:job,
                        Status_Perkawinan=:marital, Kewarnegaraan=:citizen2,
                        Foto=:photo, Tanda_Tangan=:sign, UpdatedDate=GETDATE()
                    WHERE Prechecking_Id=:pid AND NIK=:nik
                """), {
                    "pid": prechecking_id, "check_for": check_for,
                    "citizen": cust_citizen, "id_type": cust_id_type, "nik": nik,
                    "nama": cust_name, "pob": g("cust_pob"), "dob": _sql_date(g("cust_dob")),
                    "gender": g("cust_gender"), "blood": g("cust_blood_type"),
                    "addr": g("cust_address"), "rt": g("cust_rt"), "rw": g("cust_rw"),
                    "subdistrict": g("cust_subdistrict"), "district": g("cust_district"),
                    "city": g("cust_city"), "province": g("cust_province"),
                    "religion": g("cust_religion"), "job": g("cust_job"),
                    "marital": marital, "citizen2": cust_citizen,
                    "photo": g("cust_photo_hidden"), "sign": g("cust_signature_hidden"),
                })

                cust_ocr_row = db.session.execute(
                    text("SELECT Id FROM TEMP_CAFLESS_OCR WITH(NOLOCK) WHERE Prechecking_Id=:pid AND NIK=:nik"),
                    {"pid": prechecking_id, "nik": nik},
                ).fetchone()
                cust_id = cust_ocr_row.Id if cust_ocr_row else 0

                db.session.execute(text("""
                    UPDATE TEMP_CAFLESS_OCR_Rate SET
                        NIK=:nik, Nama=:nama, Tempat_Lahir=:pob, Tgl_Lahir=:dob,
                        Jenis_Kelamin=:gender, Golongan_Darah=:blood, Alamat=:addr,
                        RT=:rt, RW=:rw, Kelurahan=:subdistrict, Kecamatan=:district,
                        Kota=:city, Provinsi=:province, Agama=:religion,
                        Pekerjaan=:job, Kewarnegaraan=:citizen
                    WHERE Id=:id
                """), {
                    "id": cust_id,
                    "nik":        _strip_non_digit(g("val_cust_id_card_no")),
                    "nama":       _strip_non_digit(g("val_cust_name")),
                    "pob":        _strip_non_digit(g("val_cust_pob")),
                    "dob":        _strip_non_digit(g("val_cust_dob")),
                    "gender":     _strip_non_digit(g("val_cust_gender")),
                    "blood":      _strip_non_digit(g("val_cust_blood_type")),
                    "addr":       _strip_non_digit(g("val_cust_address")),
                    "rt":         _strip_non_digit(g("val_cust_rt")),
                    "rw":         _strip_non_digit(g("val_cust_rw")),
                    "subdistrict":_strip_non_digit(g("val_cust_subdistrict")),
                    "district":   _strip_non_digit(g("val_cust_district")),
                    "city":       _strip_non_digit(g("val_cust_city")),
                    "province":   _strip_non_digit(g("val_cust_province")),
                    "religion":   _strip_non_digit(g("val_cust_religion")),
                    "job":        _strip_non_digit(g("val_cust_job")),
                    "citizen":    _strip_non_digit(g("val_cust_citizen")),
                })

                db.session.execute(text("""
                    UPDATE TEMP_CAFLESS_OCR_Dukcapil SET
                        NIK=:nik, Nama=:nama,
                        Tempat_Lahir=:pob, Tgl_Lahir=:dob,
                        Jenis_Kelamin=:gender, Alamat=:addr,
                        RT=:rt, RW=:rw,
                        Kelurahan=:subdistrict, Kecamatan=:district,
                        Kota=:city, Provinsi=:province,
                        Pekerjaan=:job
                    WHERE Id=:id
                """), {
                    "id": cust_id,
                    "nik": _to_bit(g("ver_cust_id_card_no")), "nama": _to_bit(g("ver_cust_name")),
                    "pob": _to_bit(g("ver_cust_pob")), "dob": _to_bit(g("ver_cust_dob")),
                    "gender": _to_bit(g("ver_cust_gender")), "addr": _to_bit(g("ver_cust_address")),
                    "rt": _to_bit(g("ver_cust_rt")), "rw": _to_bit(g("ver_cust_rw")),
                    "subdistrict": _to_bit(g("ver_cust_subdistrict")), "district": _to_bit(g("ver_cust_district")),
                    "city": _to_bit(g("ver_cust_city")), "province": _to_bit(g("ver_cust_province")),
                    "job": _to_bit(g("ver_cust_job")),
                })

                if is_married:
                    if sp_citizen == "WNI":
                        db.session.execute(text("""
                            UPDATE TEMP_CAFLESS_OCR SET
                                OCR_For='S', Citizen=:citizen, Id_Type=:id_type, Nama=:nama,
                                Tempat_Lahir=:pob, Tgl_Lahir=:dob, Jenis_Kelamin=:gender,
                                Golongan_Darah=:blood, Alamat=:addr, RT=:rt, RW=:rw,
                                Kelurahan=:subdistrict, Kecamatan=:district, Kota=:city,
                                Provinsi=:province, Agama=:religion, Pekerjaan=:job,
                                Status_Perkawinan=:marital, Kewarnegaraan=:citizen2,
                                Foto=:photo, Tanda_Tangan=:sign, UpdatedDate=GETDATE()
                            WHERE Prechecking_Id=:pid AND NIK=:nik
                        """), {
                            "pid": prechecking_id, "citizen": sp_citizen, "id_type": sp_id_type, "nik": sp_nik,
                            "nama": g("cust_spouse_name"), "pob": g("cust_spouse_pob"),
                            "dob": _sql_date(g("cust_spouse_dob")),
                            "gender": g("cust_spouse_gender"),
                            "blood": g("cust_spouse_blood_type"), "addr": g("cust_spouse_address"),
                            "rt": g("cust_spouse_rt"), "rw": g("cust_spouse_rw"),
                            "subdistrict": g("cust_spouse_subdistrict"), "district": g("cust_spouse_district"),
                            "city": g("cust_spouse_city"), "province": g("cust_spouse_province"),
                            "religion": g("cust_spouse_religion"), "job": g("cust_spouse_job"),
                            "marital": marital, "citizen2": sp_citizen,
                            "photo": g("cust_spouse_photo_hidden"), "sign": g("cust_spouse_signature_hidden"),
                        })

                        sp_ocr_row = db.session.execute(
                            text("SELECT Id FROM TEMP_CAFLESS_OCR WITH(NOLOCK) WHERE Prechecking_Id=:pid AND NIK=:nik"),
                            {"pid": prechecking_id, "nik": sp_nik},
                        ).fetchone()
                        sp_id = sp_ocr_row.Id if sp_ocr_row else 0

                        db.session.execute(text("""
                            UPDATE TEMP_CAFLESS_OCR_Rate SET
                                NIK=:nik, Nama=:nama, Tempat_Lahir=:pob, Tgl_Lahir=:dob,
                                Jenis_Kelamin=:gender, Golongan_Darah=:blood, Alamat=:addr,
                                RT=:rt, RW=:rw, Kelurahan=:subdistrict, Kecamatan=:district,
                                Kota=:city, Provinsi=:province, Agama=:religion,
                                Pekerjaan=:job, Kewarnegaraan=:citizen
                            WHERE Id=:id
                        """), {
                            "id": sp_id,
                            "nik":        _strip_non_digit(g("val_cust_spouse_id_card_no")),
                            "nama":       _strip_non_digit(g("val_cust_spouse_name")),
                            "pob":        _strip_non_digit(g("val_cust_spouse_pob")),
                            "dob":        _strip_non_digit(g("val_cust_spouse_dob")),
                            "gender":     _strip_non_digit(g("val_cust_spouse_gender")),
                            "blood":      _strip_non_digit(g("val_cust_spouse_blood_type")),
                            "addr":       _strip_non_digit(g("val_cust_spouse_address")),
                            "rt":         _strip_non_digit(g("val_cust_spouse_rt")),
                            "rw":         _strip_non_digit(g("val_cust_spouse_rw")),
                            "subdistrict":_strip_non_digit(g("val_cust_spouse_subdistrict")),
                            "district":   _strip_non_digit(g("val_cust_spouse_district")),
                            "city":       _strip_non_digit(g("val_cust_spouse_city")),
                            "province":   _strip_non_digit(g("val_cust_spouse_province")),
                            "religion":   _strip_non_digit(g("val_cust_spouse_religion")),
                            "job":        _strip_non_digit(g("val_cust_spouse_job")),
                            "citizen":    _strip_non_digit(g("val_cust_spouse_citizen")),
                        })

                        db.session.execute(text("""
                            UPDATE TEMP_CAFLESS_OCR_Dukcapil SET
                                NIK=:nik, Nama=:nama,
                                Tempat_Lahir=:pob, Tgl_Lahir=:dob,
                                Jenis_Kelamin=:gender, Alamat=:addr,
                                RT=:rt, RW=:rw,
                                Kelurahan=:subdistrict, Kecamatan=:district,
                                Kota=:city, Provinsi=:province,
                                Pekerjaan=:job
                            WHERE Id=:id
                        """), {
                            "id": sp_id,
                            "nik": _to_bit(g("ver_cust_spouse_id_card_no")), "nama": _to_bit(g("ver_cust_spouse_name")),
                            "pob": _to_bit(g("ver_cust_spouse_pob")), "dob": _to_bit(g("ver_cust_spouse_dob")),
                            "gender": _to_bit(g("ver_cust_spouse_gender")), "addr": _to_bit(g("ver_cust_spouse_address")),
                            "rt": _to_bit(g("ver_cust_spouse_rt")), "rw": _to_bit(g("ver_cust_spouse_rw")),
                            "subdistrict": _to_bit(g("ver_cust_spouse_subdistrict")),
                            "district": _to_bit(g("ver_cust_spouse_district")),
                            "city": _to_bit(g("ver_cust_spouse_city")),
                            "province": _to_bit(g("ver_cust_spouse_province")),
                            "job": _to_bit(g("ver_cust_spouse_job")),
                        })

                    else:
                        db.session.execute(text("""
                            INSERT INTO TEMP_CAFLESS_OCR
                                (Prechecking_Id, OCR_For, Citizen, Id_Type, NIK, Nama, Kewarnegaraan, UpdatedDate)
                            VALUES (:pid,'S','WNA',:id_type,:nik,:nama,'WNA',GETDATE())
                        """), {
                            "pid": prechecking_id, "id_type": sp_id_type,
                            "nik": wna_sp_id, "nama": wna_sp_name,
                        })

                else:
                    db.session.execute(text("""
                        DELETE TEMP_CAFLESS_OCR_Dukcapil
                        WHERE Id = (SELECT Id FROM TEMP_CAFLESS_OCR WHERE Prechecking_Id=:pid AND OCR_For='S')
                    """), {"pid": prechecking_id})
                    db.session.execute(text("""
                        DELETE TEMP_CAFLESS_OCR_Rate
                        WHERE Id = (SELECT Id FROM TEMP_CAFLESS_OCR WHERE Prechecking_Id=:pid AND OCR_For='S')
                    """), {"pid": prechecking_id})
                    db.session.execute(text("""
                        DELETE TEMP_CAFLESS_OCR WHERE Prechecking_Id=:pid AND OCR_For='S'
                    """), {"pid": prechecking_id})

            else:
                db.session.execute(text("""
                    UPDATE TEMP_CAFLESS SET
                        CustomerType=:cust_type, LesseeType=:lessee_type,
                        LesseeName=:wna_name, IdCardNo=:wna_idcard,
                        MaritalStatus=:wna_marital, CreatedBy=:username,
                        CreatedDate=GETDATE(), Check_For=:check_for,
                        Repeat_Order=:new_ro, Notes=:note_pr, Carro=:is_carro
                    WHERE Apless=:apless AND Prechecking_Id=:pid
                """), {
                    "cust_type": cust_type, "lessee_type": lessee_type,
                    "wna_name": wna_name, "wna_idcard": wna_idcard,
                    "wna_marital": wna_marital, "username": username,
                    "check_for": check_for, "new_ro": cust_new_ro,
                    "note_pr": note_pr, "is_carro": is_carro,
                    "apless": apless, "pid": prechecking_id,
                })

                db.session.execute(text("""
                    UPDATE TEMP_CAFLESS_OCR SET
                        Citizen='WNA', Id_Type=:id_type, NIK=:nik, Nama=:nama,
                        Status_Perkawinan=:wna_marital, Kewarnegaraan='WNA', UpdatedDate=GETDATE()
                    WHERE Prechecking_Id=:pid AND OCR_For=:check_for
                """), {
                    "check_for": check_for, "id_type": cust_id_type,
                    "nik": wna_idcard, "nama": wna_name,
                    "wna_marital": wna_marital, "pid": prechecking_id,
                })

                if is_wna_married:
                    if wna_sp_citizen == "WNI":
                        db.session.execute(text("""
                            UPDATE TEMP_CAFLESS_OCR SET
                                OCR_For='S', Citizen=:citizen, Id_Type=:id_type, Nama=:nama,
                                Tempat_Lahir=:pob, Tgl_Lahir=:dob, Jenis_Kelamin=:gender,
                                Golongan_Darah=:blood, Alamat=:addr, RT=:rt, RW=:rw,
                                Kelurahan=:subdistrict, Kecamatan=:district, Kota=:city,
                                Provinsi=:province, Agama=:religion, Pekerjaan=:job,
                                Status_Perkawinan=:marital, Kewarnegaraan=:citizen2,
                                Foto=:photo, Tanda_Tangan=:sign, UpdatedDate=GETDATE()
                            WHERE Prechecking_Id=:pid AND NIK=:nik
                        """), {
                            "pid": prechecking_id, "citizen": wna_sp_citizen, "id_type": wna_sp_id_type,
                            "nik": wna_sp_nik,
                            "nama": g("cust_wna_spouse_name"), "pob": g("cust_wna_spouse_pob"),
                            "dob": _sql_date(g("cust_wna_spouse_dob")),
                            "gender": g("cust_wna_spouse_gender"),
                            "blood": g("cust_wna_spouse_blood_type"), "addr": g("cust_wna_spouse_address"),
                            "rt": g("cust_wna_spouse_rt"), "rw": g("cust_wna_spouse_rw"),
                            "subdistrict": g("cust_wna_spouse_subdistrict"),
                            "district": g("cust_wna_spouse_district"), "city": g("cust_wna_spouse_city"),
                            "province": g("cust_wna_spouse_province"), "religion": g("cust_wna_spouse_religion"),
                            "job": g("cust_wna_spouse_job"), "marital": wna_marital,
                            "citizen2": wna_sp_citizen,
                            "photo": g("cust_wna_spouse_photo_hidden"), "sign": g("cust_wna_spouse_signature_hidden"),
                        })

                        wna_sp_ocr = db.session.execute(
                            text("SELECT Id FROM TEMP_CAFLESS_OCR WITH(NOLOCK) WHERE Prechecking_Id=:pid AND NIK=:nik"),
                            {"pid": prechecking_id, "nik": wna_sp_nik},
                        ).fetchone()
                        wna_sp_ocr_id = wna_sp_ocr.Id if wna_sp_ocr else 0

                        db.session.execute(text("""
                            UPDATE TEMP_CAFLESS_OCR_Rate SET
                                NIK=:nik, Nama=:nama, Tempat_Lahir=:pob, Tgl_Lahir=:dob,
                                Jenis_Kelamin=:gender, Golongan_Darah=:blood, Alamat=:addr,
                                RT=:rt, RW=:rw, Kelurahan=:subdistrict, Kecamatan=:district,
                                Kota=:city, Provinsi=:province, Agama=:religion,
                                Pekerjaan=:job, Kewarnegaraan=:citizen
                            WHERE Id=:id
                        """), {
                            "id": wna_sp_ocr_id,
                            "nik":        _strip_non_digit(g("val_cust_wna_spouse_id_card_no")),
                            "nama":       _strip_non_digit(g("val_cust_wna_spouse_name")),
                            "pob":        _strip_non_digit(g("val_cust_wna_spouse_pob")),
                            "dob":        _strip_non_digit(g("val_cust_wna_spouse_dob")),
                            "gender":     _strip_non_digit(g("val_cust_wna_spouse_gender")),
                            "blood":      _strip_non_digit(g("val_cust_wna_spouse_blood_type")),
                            "addr":       _strip_non_digit(g("val_cust_wna_spouse_address")),
                            "rt":         _strip_non_digit(g("val_cust_wna_spouse_rt")),
                            "rw":         _strip_non_digit(g("val_cust_wna_spouse_rw")),
                            "subdistrict":_strip_non_digit(g("val_cust_wna_spouse_subdistrict")),
                            "district":   _strip_non_digit(g("val_cust_wna_spouse_district")),
                            "city":       _strip_non_digit(g("val_cust_wna_spouse_city")),
                            "province":   _strip_non_digit(g("val_cust_wna_spouse_province")),
                            "religion":   _strip_non_digit(g("val_cust_wna_spouse_religion")),
                            "job":        _strip_non_digit(g("val_cust_wna_spouse_job")),
                            "citizen":    _strip_non_digit(g("val_cust_wna_spouse_citizen")),
                        })

                        db.session.execute(text("""
                            UPDATE TEMP_CAFLESS_OCR_Dukcapil SET
                                NIK=:nik, Nama=:nama,
                                Tempat_Lahir=:pob, Tgl_Lahir=:dob,
                                Jenis_Kelamin=:gender, Alamat=:addr,
                                RT=:rt, RW=:rw,
                                Kelurahan=:subdistrict, Kecamatan=:district,
                                Kota=:city, Provinsi=:province,
                                Pekerjaan=:job
                            WHERE Id=:id
                        """), {
                            "id": wna_sp_ocr_id,
                            "nik": _to_bit(g("ver_cust_wna_spouse_id_card_no")), "nama": _to_bit(g("ver_cust_wna_spouse_name")),
                            "pob": _to_bit(g("ver_cust_wna_spouse_pob")), "dob": _to_bit(g("ver_cust_wna_spouse_dob")),
                            "gender": _to_bit(g("ver_cust_wna_spouse_gender")), "addr": _to_bit(g("ver_cust_wna_spouse_address")),
                            "rt": _to_bit(g("ver_cust_wna_spouse_rt")), "rw": _to_bit(g("ver_cust_wna_spouse_rw")),
                            "subdistrict": _to_bit(g("ver_cust_wna_spouse_subdistrict")),
                            "district": _to_bit(g("ver_cust_wna_spouse_district")),
                            "city": _to_bit(g("ver_cust_wna_spouse_city")),
                            "province": _to_bit(g("ver_cust_wna_spouse_province")),
                            "job": _to_bit(g("ver_cust_wna_spouse_job")),
                        })

                    else:
                        db.session.execute(text("""
                            INSERT INTO TEMP_CAFLESS_OCR
                                (Prechecking_Id, OCR_For, Citizen, Id_Type, NIK, Nama, Kewarnegaraan)
                            VALUES (:pid,'S','WNA',:id_type,:nik,:nama,'WNA')
                        """), {
                            "pid": prechecking_id, "id_type": wna_sp_id_type,
                            "nik": wna_sp_id, "nama": wna_sp_name,
                        })

        db.session.execute(text("""
            INSERT INTO DocumentApproval
                (ApprovalFormId, DocumentNumber, Title, Progress,
                 LastApprovalActionCode, LastActionBy, LastActionDate,
                 CurrentApprover, DocumentStatusCode, CreatedBy, CreatedDate)
            VALUES
                (:form_id, :pid, :title, 50,
                 'draft', :username, GETDATE(),
                 :approver, 'draft', :username, GETDATE())
        """), {
            "form_id":  approval_form_id,
            "pid":      prechecking_id,
            "title":    f"CAM Request - {prechecking_id}",
            "username": username,
            "approver": f"({username})",
        })

        doc_appr_row = db.session.execute(
            text("SELECT Id FROM DocumentApproval WITH(NOLOCK) WHERE DocumentNumber=:pid"),
            {"pid": prechecking_id},
        ).fetchone()
        doc_appr_id = doc_appr_row.Id if doc_appr_row else 0

        db.session.execute(text("""
            INSERT INTO DocumentApprovalHistory
                (DocumentApprovalId, ApprovalActionCode, Remarks, CreatedBy, CreatedDate)
            VALUES
                (:appr_id, 'draft', :remarks, :username, GETDATE())
        """), {
            "appr_id":  doc_appr_id,
            "remarks":  f"CMO {username} submitted Prechecking Request No. {prechecking_id}",
            "username": username,
        })

        db.session.execute(
            text("""
                UPDATE TEMP_CUSTOMER_DOCUMENT SET Apless = :apless
                WHERE Prechecking_Id = :pid AND ISNULL(LTRIM(RTRIM(Apless)), '') = ''
            """),
            {"apless": apless, "pid": prechecking_id},
        )

        carried_failed = _carry_over_documents(
            prechecking_id, apless, username, body.get("carried_documents")
        )

        required_doc_types = []
        if nationality == "WNI":
            required_doc_types.append("cust-ktp")
            if is_married and sp_citizen == "WNI":
                required_doc_types.append("cust-spouse-ktp")
        elif is_wna_married and wna_sp_citizen == "WNI":
            required_doc_types.append("cust-wna-spouse-ktp")

        documents_missing = []
        for dtype in required_doc_types:
            found = db.session.execute(
                text("""
                    SELECT COUNT(1) AS cnt FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
                    WHERE Prechecking_Id = :pid AND DocumentType = :dtype
                """),
                {"pid": prechecking_id, "dtype": dtype},
            ).fetchone()
            if not found or found.cnt == 0:
                documents_missing.append(dtype)

        db.session.commit()
        return jsonify({
            "success": True,
            "prechecking_id": prechecking_id,
            "apless": apless,
            "documents_failed": carried_failed,
            "documents_missing": documents_missing,
        })

    except Exception:
        db.session.rollback()
        current_app.logger.exception("submit_prechecking error")
        return jsonify({"success": False, "message": "Database error"}), 500

@prechecking_individu_bp.route("/cancel", methods=["POST"])
@login_required
def cancel_prechecking():
   
    body           = request.get_json(force=True) or {}
    prechecking_id = (body.get("prechecking_id") or "").strip()

    if not prechecking_id:
        return jsonify({"success": False, "message": "prechecking_id required"}), 400

    try:
        for tbl in (
            "TEMP_CAFLESS_OCR_Rate",
            "TEMP_CAFLESS_OCR",
            "TEMP_CUSTOMER_DOCUMENT",
            "TEMP_CAFLESS",
        ):
            if tbl == "TEMP_CAFLESS_OCR_Rate":
                db.session.execute(
                    text(f"""
                        DELETE r FROM {tbl} r
                        INNER JOIN TEMP_CAFLESS_OCR o ON r.Id = o.Id
                        WHERE o.Prechecking_Id = :pid
                    """),
                    {"pid": prechecking_id},
                )
            else:
                db.session.execute(
                    text(f"DELETE FROM {tbl} WHERE Prechecking_Id = :pid"),
                    {"pid": prechecking_id},
                )
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("cancel_prechecking error")
        return jsonify({"success": False, "message": "Database error"}), 500

@prechecking_individu_bp.route("/marital-statuses", methods=["GET"])
@login_required
def get_marital_statuses():
    try:
        rows = db.session.execute(
            text("SELECT Marital, name FROM MSTMARITAL ORDER BY name")
        ).fetchall()
        return jsonify([{"value": r.Marital, "label": r.name} for r in rows])
    except Exception:
        current_app.logger.exception("get_marital_statuses error")
        return jsonify([
            {"value": "S", "label": "Belum Kawin"},
            {"value": "M", "label": "Kawin Tercatat"},
            {"value": "O", "label": "Kawin Belum Tercatat"},
            {"value": "P", "label": "Perjanjian Pranikah"},
            {"value": "D", "label": "Cerai"},
        ])

_DOC_META: dict[str, tuple[str, str]] = {
    "cust-ktp":                        ("-CUST_KTP-",                       "DATA_DIRI/KTP"),
    "cust-spouse-ktp":                 ("-CUST_SPOUSE_KTP-",                "DATA_DIRI/KTP"),
    "cust-kk":                         ("-CUST_KK-",                        "DATA_DIRI/KK"),
    "cust-npwp":                       ("-CUST_NPWP-",                      "DATA_DIRI/NPWP"),
    "cust-marriage-or-death-statement":("-CUST-MARRIAGE_OR_DEATH_STATEMENT-","DATA_DIRI/AKTA_CERAI_MATI"),
    "cust-kitas":                      ("-CUST_KITAS-",                     "DATA_DIRI/KITAS"),
    "cust-kitap":                      ("-CUST_KITAP-",                     "DATA_DIRI/KITAP"),
    "cust-spouse-kitas":               ("-CUST_SPOUSE_KITAS-",              "DATA_DIRI/KITAS_PASANGAN"),
    "cust-spouse-kitap":               ("-CUST_SPOUSE_KITAP-",              "DATA_DIRI/KITAP_PASANGAN"),
    "cust-wna-spouse-ktp":             ("-CUST_WNA_SPOUSE_KTP-",            "DATA_DIRI/KTP_PASANGAN"),
}

_DOC_TYPE_SIBLINGS: dict[str, tuple[str, ...]] = {
    "cust-kitas":        ("cust-kitas", "cust-kitap"),
    "cust-kitap":        ("cust-kitas", "cust-kitap"),
    "cust-spouse-kitas": ("cust-spouse-kitas", "cust-spouse-kitap"),
    "cust-spouse-kitap": ("cust-spouse-kitas", "cust-spouse-kitap"),
}

@prechecking_individu_bp.route("/upload-document", methods=["POST"])
@login_required
def upload_document():
    
    username          = _username()
    apless            = request.form.get("apless", "")
    prechecking_id    = request.form.get("prechecking_id", "")
    document_type     = request.form.get("document_type", "")
    cust_type         = request.form.get("cust_type", "PR")
    organization_type = request.form.get("organization_type", "PR")

    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file provided"}), 400

    if not prechecking_id:
        return jsonify({"success": False, "message": "prechecking_id is required"}), 400

    if not apless:
        apless = _apless_for_prechecking(prechecking_id)

    if not apless:
        return jsonify({
            "success": False,
            "message": "Temp. Customer No. (apless) is required before uploading a document.",
        }), 400

    f          = request.files["file"]
    original   = f.filename or "upload"
    file_bytes = f.read()

    err = _validate_file(file_bytes, original)
    if err:
        return jsonify({"success": False, "message": err}), 400

    name_prefix, doc_subfolder = _DOC_META.get(
        document_type, (f"-{document_type.upper().replace('-', '_')}-", document_type)
    )

    doc_name  = f"{prechecking_id}{name_prefix}{original}"

    is_guarantor = organization_type in ("GUARNPR", "GUARNPT")
    aws_prefix   = "upload_doc/guarantor" if is_guarantor else "upload_doc"
    aws_key      = f"{aws_prefix}/{apless}/{prechecking_id}/{doc_subfolder}/{doc_name}"

    content_type = mimetypes.guess_type(original)[0] or "application/octet-stream"

    replaced_types = _DOC_TYPE_SIBLINGS.get(document_type, (document_type,))

    try:
        placeholders = ", ".join(f":dtype_{i}" for i in range(len(replaced_types)))
        params = {"pid": prechecking_id}
        params.update({f"dtype_{i}": t for i, t in enumerate(replaced_types)})

        existing_rows = db.session.execute(
            text(f"""
                SELECT CustomerDocumentId, AWSKey, DocumentName
                FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
                WHERE Prechecking_Id = :pid
                    AND DocumentType IN ({placeholders})
                    AND Apless IS NOT NULL
            """),
            params,
        ).fetchall()

        for existing in existing_rows:
            if existing.AWSKey:
                _aws_delete(existing.AWSKey)

            db.session.execute(
                text("""
                    DELETE FROM TEMP_CUSTOMER_DOCUMENT
                    WHERE CustomerDocumentId = :doc_id
                """),
                {"doc_id": existing.CustomerDocumentId},
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
                "apless":    apless,
                "name":      doc_name,
                "org_type":  organization_type,
                "numb_doc":  "1",
                "dtype":     document_type,
                "user":      username,
                "aws_key":   aws_key,
                "pid":       prechecking_id,
            },
        )
        db.session.commit()

        b64_data = base64.b64encode(file_bytes).decode()
        orig_ext = os.path.splitext(original)[1].lower()
        return jsonify({
            "success":       True,
            "document_name": doc_name,
            "document_type": document_type,
            "aws_key":       aws_key,
            "b64": b64_data if orig_ext in (".png", ".jpg", ".jpeg") else None,
        })

    except (BotoCoreError, ClientError) as exc:
        db.session.rollback()
        current_app.logger.exception("upload_document S3 error")
        return jsonify({"success": False, "message": f"S3 upload failed: {exc}"}), 500
    except Exception:
        db.session.rollback()
        current_app.logger.exception("upload_document error")
        return jsonify({"success": False, "message": "Database error"}), 500

@prechecking_individu_bp.route("/documents", methods=["GET"])
@login_required
def get_documents():

    apless                  = request.args.get("apless", "")
    prechecking_id          = request.args.get("prechecking_id", "")
    previous_prechecking_id = request.args.get("previous_prechecking_id", "")

    prechecking_ids = [pid for pid in {prechecking_id, previous_prechecking_id} if pid]

    if not prechecking_ids:
        return jsonify([])

    try:
        placeholders = ", ".join(f":pid_{i}" for i in range(len(prechecking_ids)))
        params = {"apless": apless}
        params.update({f"pid_{i}": pid for i, pid in enumerate(prechecking_ids)})

        rows = db.session.execute(
            text(f"""
                SELECT CustomerDocumentId, DocumentName, DocumentType, AWSKey
                FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
                WHERE Prechecking_Id IN ({placeholders})
                    AND (:apless = '' OR ISNULL(Apless, '') IN (:apless, ''))
                ORDER BY DocumentType, CreatedDate
            """),
            params,
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

@prechecking_individu_bp.route("/view-document", methods=["GET"])
@login_required
def view_document():
   
    doc_id = request.args.get("customer_document_id")
    if not doc_id:
        return jsonify({"success": False, "message": "document id required"}), 400

    try:
        row = db.session.execute(
            text("""
                SELECT AWSKey, DocumentName
                FROM TEMP_CUSTOMER_DOCUMENT
                WHERE CustomerDocumentId = :id
            """),
            {"id": doc_id},
        ).fetchone()

        if not row or not row.AWSKey:
            return jsonify({"success": False, "message": "Document not found"}), 404

        url = _aws_presign(row.AWSKey, row.DocumentName)
        return jsonify({"success": True, "view_url": url})
    except Exception:
        current_app.logger.exception("view_document error")
        return jsonify({"success": False, "message": "Could not generate view link"}), 500

@prechecking_individu_bp.route("/delete-document", methods=["POST"])
@login_required
def delete_document():
  
    body   = request.get_json(force=True) or {}
    doc_id = body.get("customer_document_id")
    pid    = (body.get("prechecking_id") or "").strip()
    nik    = (body.get("nik") or "").strip()

    if not doc_id:
        return jsonify({"success": False, "message": "document id required"}), 400

    try:
        row = db.session.execute(
            text("""
                SELECT AWSKey, DocumentType FROM TEMP_CUSTOMER_DOCUMENT
                WHERE CustomerDocumentId = :id
            """),
            {"id": doc_id},
        ).fetchone()

        if row and row.AWSKey:
            _aws_delete(row.AWSKey)

        db.session.execute(
            text("DELETE FROM TEMP_CUSTOMER_DOCUMENT WHERE CustomerDocumentId = :id"),
            {"id": doc_id},
        )

        if row and pid and nik and _is_ocr_doc_type(row.DocumentType):
            _cleanup_ocr_for_nik(pid, nik)

        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("delete_document error")
        return jsonify({"success": False, "message": "Database error"}), 500