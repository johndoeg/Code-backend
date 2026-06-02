from flask import Blueprint, request, jsonify, current_app, session
from sqlalchemy import text
from datetime import datetime, date
import base64, os, uuid

from app import db

prechecking_individu_bp = Blueprint("prechecking_individu", __name__, url_prefix="/CAM/Prechecking")

def _username():
    return session.get("username", "")

def _branch():
    return session.get("branchcode", "")

def _emp_id():
    return session.get("emp_id", "")


@prechecking_individu_bp.route("/generate-apless", methods=["POST"])
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
def submit_prechecking():
   
    username = _username()
    branch   = _branch()
    emp_id   = _emp_id()

    body = request.form.to_dict() if request.form else (request.get_json(force=True) or {})

    def g(key, default=""):
        return (body.get(key) or default).strip() if isinstance(body.get(key), str) else (body.get(key) or default)

    prechecking_id = g("prechecking_id")
    apless         = g("apless")
    cust_type      = g("cust_type", "PR")
    lessee_type    = g("lessee_type", "PR")
    check_for      = g("check_for", "C")
    cust_new_ro    = g("cust_new_ro", "New")
    existing_apless= g("existing_apless")
    nationality    = g("cust_nationality_type", "WNI")
    marital        = g("marital_status")
    wna_marital    = g("wna_marital_status")
    is_carro       = int(g("is_carro_type", "1"))
    note_pr        = g("note_prechecking_pr")
    note_pt        = g("note_prechecking_pt")

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
        "BELUM KAWIN": "S",
        "KAWIN": "M",
        "KAWIN TERCATAT": "M",
        "KAWIN BELUM TERCATAT": "O",
        "PERJANJIAN PRANIKAH": "P",
        "CERAI HIDUP": "D",
        "CERAI MATI": "D",
    }
    def normalise_marital(val):
        return _marital_map.get((val or "").strip().upper(), val)

    marital     = normalise_marital(marital)
    wna_marital = normalise_marital(wna_marital)

    try:
        exists = db.session.execute(
            text("SELECT 1 FROM TEMP_CAFLESS WHERE Prechecking_Id = :pid"),
            {"pid": prechecking_id},
        ).fetchone()

        params = {
            "pid":           prechecking_id,
            "apless":        apless,
            "branch":        branch,
            "lessee_type":   lessee_type,
            "cust_type":     cust_type,
            "check_for":     check_for,
            "nationality":   nationality,
            "marital":       marital,
            "wna_marital":   wna_marital,
            "new_ro":        0 if cust_new_ro == "New" else 1,
            "existing":      existing_apless,
            "is_carro":      is_carro,
            "note_pr":       note_pr,
            "note_pt":       note_pt,
            "username":      username,
            "emp_id":        emp_id,
            # Customer WNI
            "nik":           g("cust_id_card_no"),
            "nama":          g("cust_name"),
            "pob":           g("cust_pob"),
            "dob":           g("cust_dob"),
            "gender":        g("cust_gender"),
            "blood":         g("cust_blood_type"),
            "addr":          g("cust_address"),
            "rt":            g("cust_rt"),
            "rw":            g("cust_rw"),
            "subdistrict":   g("cust_subdistrict"),
            "district":      g("cust_district"),
            "city":          g("cust_city"),
            "province":      g("cust_province"),
            "religion":      g("cust_religion"),
            "job":           g("cust_job"),
            "citizen":       g("cust_citizen"),
            "photo":         g("cust_photo_hidden"),
            "sign":          g("cust_signature_hidden"),
            # OCR confidence (val_*)
            "val_nik":       _strip_non_digit(g("val_cust_id_card_no")),
            "val_nama":      _strip_non_digit(g("val_cust_name")),
            "val_pob":       _strip_non_digit(g("val_cust_pob")),
            "val_dob":       _strip_non_digit(g("val_cust_dob")),
            "val_gender":    _strip_non_digit(g("val_cust_gender")),
            "val_blood":     _strip_non_digit(g("val_cust_blood_type")),
            "val_addr":      _strip_non_digit(g("val_cust_address")),
            "val_rt":        _strip_non_digit(g("val_cust_rt")),
            "val_rw":        _strip_non_digit(g("val_cust_rw")),
            "val_subdistrict": _strip_non_digit(g("val_cust_subdistrict")),
            "val_district":  _strip_non_digit(g("val_cust_district")),
            "val_city":      _strip_non_digit(g("val_cust_city")),
            "val_province":  _strip_non_digit(g("val_cust_province")),
            "val_religion":  _strip_non_digit(g("val_cust_religion")),
            "val_job":       _strip_non_digit(g("val_cust_job")),
            "val_citizen":   _strip_non_digit(g("val_cust_citizen")),
            # Verification (ver_*)
            "ver_nik":       g("ver_cust_id_card_no"),
            "ver_nama":      g("ver_cust_name"),
            "ver_pob":       g("ver_cust_pob"),
            "ver_dob":       g("ver_cust_dob"),
            "ver_gender":    g("ver_cust_gender"),
            "ver_addr":      g("ver_cust_address"),
            "ver_rt":        g("ver_cust_rt"),
            "ver_subdistrict": g("ver_cust_subdistrict"),
            "ver_district":  g("ver_cust_district"),
            "ver_city":      g("ver_cust_city"),
            "ver_province":  g("ver_cust_province"),
            "ver_job":       g("ver_cust_job"),
            # Spouse
            "sp_nik":        g("cust_spouse_id_card_no"),
            "sp_nama":       g("cust_spouse_name"),
            "sp_pob":        g("cust_spouse_pob"),
            "sp_dob":        g("cust_spouse_dob"),
            "sp_gender":     g("cust_spouse_gender"),
            "sp_blood":      g("cust_spouse_blood_type"),
            "sp_addr":       g("cust_spouse_address"),
            "sp_rt":         g("cust_spouse_rt"),
            "sp_rw":         g("cust_spouse_rw"),
            "sp_subdistrict":g("cust_spouse_subdistrict"),
            "sp_district":   g("cust_spouse_district"),
            "sp_city":       g("cust_spouse_city"),
            "sp_province":   g("cust_spouse_province"),
            "sp_religion":   g("cust_spouse_religion"),
            "sp_job":        g("cust_spouse_job"),
            "sp_citizen":    g("cust_spouse_citizen"),
            "sp_photo":      g("cust_spouse_photo_hidden"),
            "sp_sign":       g("cust_spouse_signature_hidden"),
            # WNA
            "wna_name":      g("wna_name"),
            "wna_idcard":    g("wna_idcard_no"),
            "wna_sp_name":   g("wna_spouse_name"),
            "wna_sp_idcard": g("wna_spouse_idcard_no"),
        }

        if exists:
            db.session.execute(
                text("""
                    UPDATE TEMP_CAFLESS SET
                        Apless=:apless, BranchCd=:branch, Lessee_TP=:lessee_type,
                        CustomerType=:cust_type, Check_For=:check_for,
                        NationalityType=:nationality, MaritalStatus=:marital,
                        WnaMaritalStatus=:wna_marital, NewRO=:new_ro,
                        ExistingApless=:existing, IsCarroType=:is_carro,
                        NotePrecheckingPR=:note_pr, NotePrecheckingPT=:note_pt,
                        IdCardNo=:nik, LesseeName=:nama, PlaceOfBirth=:pob,
                        DateOfBirth=:dob, Gender=:gender, BloodType=:blood,
                        Address=:addr, RT=:rt, RW=:rw,
                        Subdistrict=:subdistrict, District=:district,
                        City=:city, Province=:province,
                        Religion=:religion, Job=:job, Citizen=:citizen,
                        Photo=:photo, Signature=:sign,
                        ValIdCardNo=:val_nik, ValName=:val_nama,
                        ValPOB=:val_pob, ValDOB=:val_dob,
                        ValGender=:val_gender, ValBloodType=:val_blood,
                        ValAddress=:val_addr, ValRT=:val_rt, ValRW=:val_rw,
                        ValSubdistrict=:val_subdistrict, ValDistrict=:val_district,
                        ValCity=:val_city, ValProvince=:val_province,
                        ValReligion=:val_religion, ValJob=:val_job,
                        ValCitizen=:val_citizen,
                        VerIdCardNo=:ver_nik, VerName=:ver_nama,
                        VerPOB=:ver_pob, VerDOB=:ver_dob,
                        VerGender=:ver_gender, VerAddress=:ver_addr,
                        VerRT=:ver_rt, VerSubdistrict=:ver_subdistrict,
                        VerDistrict=:ver_district, VerCity=:ver_city,
                        VerProvince=:ver_province, VerJob=:ver_job,
                        SpouseIdCardNo=:sp_nik, SpouseName=:sp_nama,
                        SpousePOB=:sp_pob, SpouseDOB=:sp_dob,
                        SpouseGender=:sp_gender, SpouseBloodType=:sp_blood,
                        SpouseAddress=:sp_addr, SpouseRT=:sp_rt, SpouseRW=:sp_rw,
                        SpouseSubdistrict=:sp_subdistrict, SpouseDistrict=:sp_district,
                        SpouseCity=:sp_city, SpouseProvince=:sp_province,
                        SpouseReligion=:sp_religion, SpouseJob=:sp_job,
                        SpouseCitizen=:sp_citizen, SpousePhoto=:sp_photo,
                        SpouseSignature=:sp_sign,
                        WnaName=:wna_name, WnaIdCardNo=:wna_idcard,
                        WnaSpouseName=:wna_sp_name, WnaSpouseIdCardNo=:wna_sp_idcard,
                        UpdatedBy=:username, UpdatedDate=GETDATE()
                    WHERE Prechecking_Id=:pid
                """),
                params,
            )
        else:
            db.session.execute(
                text("""
                    INSERT INTO TEMP_CAFLESS (
                        Prechecking_Id, Apless, BranchCd, Lessee_TP,
                        CustomerType, Check_For, NationalityType,
                        MaritalStatus, WnaMaritalStatus, NewRO, ExistingApless,
                        IsCarroType, NotePrecheckingPR, NotePrecheckingPT,
                        IdCardNo, LesseeName, PlaceOfBirth, DateOfBirth,
                        Gender, BloodType, Address, RT, RW,
                        Subdistrict, District, City, Province,
                        Religion, Job, Citizen, Photo, Signature,
                        ValIdCardNo, ValName, ValPOB, ValDOB,
                        ValGender, ValBloodType, ValAddress, ValRT, ValRW,
                        ValSubdistrict, ValDistrict, ValCity, ValProvince,
                        ValReligion, ValJob, ValCitizen,
                        VerIdCardNo, VerName, VerPOB, VerDOB,
                        VerGender, VerAddress, VerRT, VerSubdistrict,
                        VerDistrict, VerCity, VerProvince, VerJob,
                        SpouseIdCardNo, SpouseName, SpousePOB, SpouseDOB,
                        SpouseGender, SpouseBloodType, SpouseAddress,
                        SpouseRT, SpouseRW, SpouseSubdistrict, SpouseDistrict,
                        SpouseCity, SpouseProvince, SpouseReligion, SpouseJob,
                        SpouseCitizen, SpousePhoto, SpouseSignature,
                        WnaName, WnaIdCardNo, WnaSpouseName, WnaSpouseIdCardNo,
                        EmpId, CreatedBy, CreatedDate
                    ) VALUES (
                        :pid, :apless, :branch, :lessee_type,
                        :cust_type, :check_for, :nationality,
                        :marital, :wna_marital, :new_ro, :existing,
                        :is_carro, :note_pr, :note_pt,
                        :nik, :nama, :pob, :dob,
                        :gender, :blood, :addr, :rt, :rw,
                        :subdistrict, :district, :city, :province,
                        :religion, :job, :citizen, :photo, :sign,
                        :val_nik, :val_nama, :val_pob, :val_dob,
                        :val_gender, :val_blood, :val_addr, :val_rt, :val_rw,
                        :val_subdistrict, :val_district, :val_city, :val_province,
                        :val_religion, :val_job, :val_citizen,
                        :ver_nik, :ver_nama, :ver_pob, :ver_dob,
                        :ver_gender, :ver_addr, :ver_rt, :ver_subdistrict,
                        :ver_district, :ver_city, :ver_province, :ver_job,
                        :sp_nik, :sp_nama, :sp_pob, :sp_dob,
                        :sp_gender, :sp_blood, :sp_addr,
                        :sp_rt, :sp_rw, :sp_subdistrict, :sp_district,
                        :sp_city, :sp_province, :sp_religion, :sp_job,
                        :sp_citizen, :sp_photo, :sp_sign,
                        :wna_name, :wna_idcard, :wna_sp_name, :wna_sp_idcard,
                        :emp_id, :username, GETDATE()
                    )
                """),
                params,
            )

        db.session.commit()
        return jsonify({"success": True, "prechecking_id": prechecking_id, "apless": apless})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("submit_prechecking error")
        return jsonify({"success": False, "message": "Database error"}), 500

@prechecking_individu_bp.route("/cancel", methods=["POST"])
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

@prechecking_individu_bp.route("/upload-document", methods=["POST"])
def upload_document():
   
    username       = _username()
    apless         = request.form.get("apless", "")
    prechecking_id = request.form.get("prechecking_id", "")
    document_type  = request.form.get("document_type", "")
    cust_type      = request.form.get("cust_type", "PR")
    organization_type = request.form.get("organization_type", "PR")

    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file provided"}), 400

    f        = request.files["file"]
    original = f.filename or "upload"
    ext      = os.path.splitext(original)[1].lower()

    file_bytes = f.read()
    b64_data   = base64.b64encode(file_bytes).decode()
    doc_name   = f"{prechecking_id}-{document_type}-{uuid.uuid4().hex[:8]}{ext}"

    try:
        db.session.execute(
            text("""
                INSERT INTO TEMP_CUSTOMER_DOCUMENT (Apless, DocumentName, OrganizationType, NumberOfDocuments, DocumentType, CreatedBy, CreatedDate, AWSKey, Prechecking_Id)
                VALUES (:apless, :name, :org_type, :numb_doc, :dtype, :user, GETDATE(), :aws_key, :pid)
                """),
            {
                "apless": apless,
                "name":   doc_name,
                "org_type": organization_type,
                "numb_doc": "1",
                "dtype":   document_type,
                "aws_key": f"{prechecking_id}/{document_type}/{doc_name}",
                "user":    username,
                "pid":     prechecking_id,
            },
        )
        db.session.commit()
        return jsonify({
            "success": True,
            "document_name": doc_name,
            "document_type": document_type,
            "b64": b64_data if ext in (".png", ".jpg", ".jpeg") else None,
        })
    except Exception:
        db.session.rollback()
        current_app.logger.exception("upload_document error")
        return jsonify({"success": False, "message": "Database error"}), 500


@prechecking_individu_bp.route("/documents", methods=["GET"])
def get_documents():
   
    apless         = request.args.get("apless", "")
    prechecking_id = request.args.get("prechecking_id", "")

    try:
        rows = db.session.execute(
            text("""
                SELECT CustomerDocumentId, DocumentName, DocumentType, AWSKey
                FROM TEMP_CUSTOMER_DOCUMENT WITH(NOLOCK)
                WHERE Apless = :apless
                  AND Prechecking_Id = :pid
                  AND Apless IS NOT NULL
                ORDER BY DocumentType, CreatedDate
            """),
            {"apless": apless, "pid": prechecking_id},
        ).fetchall()

        docs = [
            {
                "id":   r.CustomerDocumentId,
                "name": r.DocumentName,
                "type": r.DocumentType,
                "key":  r.AWSKey,
            }
            for r in rows
        ]
        return jsonify(docs)
    except Exception:
        current_app.logger.exception("get_documents error")
        return jsonify([])


@prechecking_individu_bp.route("/delete-document", methods=["POST"])
def delete_document():
   
    body     = request.get_json(force=True) or {}
    doc_id   = body.get("customer_document_id")
    pid      = body.get("prechecking_id", "")

    if not doc_id:
        return jsonify({"success": False, "message": "document id required"}), 400

    try:
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

def _strip_non_digit(value: str) -> str:
    import re
    return re.sub(r"\D", "", value or "")
