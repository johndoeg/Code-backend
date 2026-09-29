import re

from app import db
from app.auth.decorators import login_required
from datetime import datetime, date

from flask import Blueprint, request, jsonify, current_app, session
from sqlalchemy import text

cam_customer_bp = Blueprint("cam_customer", __name__, url_prefix="/CAM/Customer")

def _session_str(key: str) -> str:
    return session.get(key, "") or ""

def _fetch_combo(cat_value: str):
    rows = db.session.execute(text(
        "SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE = :cat"
    ), {"cat": cat_value}).fetchall()
    return [{"value": r.VALUE, "label": r.DESC_VALUE} for r in rows]

def _normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    digits = "".join(c for c in phone if c.isdigit() or c in "xX")
    if digits.startswith("62"):
        digits = digits[2:]
    if digits.startswith("0"):
        digits = digits[1:]
    return digits

def _format_phone_db(phone: str):
    if not phone:
        return None
    digits = "".join(c for c in phone if c.isdigit() or c in "xX")
    if digits.startswith("62"):
        return digits
    if digits.startswith("0"):
        digits = digits[1:]
    return f"62{digits}"

def _check_watchlist_blacklist(name, address, id_card, mother, dob, ind_cor, apless, npwp):
    row = db.session.execute(text("""
        EXEC USP_CAM_CHECKWATCHLIST :name, :address, :id_card, :mother, :dob, :ind_cor, :apless, :npwp
    """), {
        "name": name, "address": address, "id_card": id_card, "mother": mother,
        "dob": dob, "ind_cor": ind_cor, "apless": apless, "npwp": npwp,
    }).mappings().first()

    if not row:
        return {"status": "not_found"}

    counter = row.get("Counters") or 0
    reason2 = row.get("Reason2") or ""
    flag_tp = row.get("Flag_type") or ""
    other = row.get("Other") or ""
    cate = row.get("caterory")
    id_watch = row.get("id_watchlist") or ""

    desc_value = ""
    if cate is not None:
        combo_row = db.session.execute(text(
            "SELECT DESC_VALUE FROM MSTCOMBO WITH (NOLOCK) WHERE VALUE = :v AND CAT_VALUE = 'BLACKLIST_CATEGORY'"
        ), {"v": cate}).mappings().first()
        desc_value = (combo_row or {}).get("DESC_VALUE") or ""

    if counter != 1:
        return {"status": "no_match"}

    if counter == 1 and flag_tp == "W":
        return {
            "status": "watchlist",
            "message": f"This name is on watchlist ({id_watch}).\nReason : {desc_value}",
        }
    elif counter == 1 and flag_tp == "B" and cate != 5 and cate != 1:
        return {
            "status": "blacklist",
            "message": f"This name is on Blacklist ({id_watch}).\nReason : {reason2}",
            "redirect": "../index.php?sumber=module_cam/cam_onhand.php",
        }
    elif counter == 1 and flag_tp == "B" and cate == 5:
        return {
            "status": "blacklist",
            "message": f"This name is on Blacklist ({id_watch}).\nReason : {other}",
            "redirect": "../index.php?sumber=module_cam/cam_onhand.php",
        }
    elif counter == 1 and flag_tp == "B" and cate == 1:
        return {
            "status": "blacklist",
            "message": f"This name is on Blacklist ({id_watch}).\nReason : {reason2}",
            "redirect": "../index.php?sumber=module_cam/cam_onhand.php",
        }

    return {"status": "unknown"}

def _next_number(prop_group_name: str):
    row = db.session.execute(text(
        "SELECT NextNumber FROM TANUMBER WITH(NOLOCK) WHERE PropertyGroupName = :p"
    ), {"p": prop_group_name}).fetchone()
    return row.NextNumber if row else None

def _generate_apless():
    next_num = _next_number("APLESS")
    if next_num is None:
        return None
    apless = str(next_num).zfill(6)
    db.session.execute(text(
        "UPDATE TANUMBER SET NextNumber = :n, LastUpdate = GETDATE() WHERE PropertyGroupName = 'APLESS'"
    ), {"n": next_num + 1})
    return apless

def _generate_applno(emp_id: str):
    prop = f"APPL_NO{emp_id}"
    row = db.session.execute(text("""
        SELECT NextNumber, CONVERT(varchar(7), [LastUpdate], 126) AS LastUpdate
        FROM TANUMBER WITH(NOLOCK) WHERE PropertyGroupName = :p
    """), {"p": prop}).fetchone()
    if not row:
        return None
    this_month = datetime.utcnow().strftime("%Y-%m")
    seq = row.NextNumber if row.LastUpdate == this_month else 1
    applno = f"{emp_id}{datetime.utcnow().strftime('%y%m')}{str(seq).zfill(3)}"
    db.session.execute(text(
        "UPDATE TANUMBER SET NextNumber = :n, LastUpdate = GETDATE() WHERE PropertyGroupName = :p"
    ), {"n": seq + 1, "p": prop})
    return applno

def _next_cafequip_id():
    row = db.session.execute(text(
        "SELECT NextNumber FROM TANUMBER WITH(NOLOCK) WHERE PropertyGroupName = 'CAFEQUIP_ID'"
    )).fetchone()
    if not row:
        return None
    cafequip_id = row.NextNumber
    db.session.execute(text(
        "UPDATE TANUMBER SET NextNumber = :n, LastUpdate = GETDATE() WHERE PropertyGroupName = 'CAFEQUIP_ID'"
    ), {"n": cafequip_id + 1})
    return cafequip_id

def _seed_new_application(applno, apless, branch_cd, emp_id, cons_leas, has_guarantor, purpoffinc, cont_type, new_car):
    db.session.execute(text("""
        INSERT INTO CAFCONT (APPL_NO, APLESS, CREATE_DATE, Disc_Cust, CURR_CODE, Cons_Leas, BRANCH_CD, CMO,
            HAS_GUARANTOR, purpoffinc, Cont_type)
        VALUES (:applno, :apless, GETDATE(), '0', 'IDR', :cons_leas, :branch_cd, :emp_id, :hg, :p, :ct)
    """), {
        "applno": applno, "apless": apless, "cons_leas": cons_leas, "branch_cd": branch_cd,
        "emp_id": emp_id, "hg": has_guarantor, "p": purpoffinc, "ct": cont_type,
    })
    condition, tahun = ("USED", None) if new_car == "1" else ("NEW", str(datetime.utcnow().year))
    cafequip_id = _next_cafequip_id()
    db.session.execute(text(
        "INSERT INTO CAFEQUIP (CAFEQUIP_ID, APPL_NO, CONDITION, TAHUN) VALUES (:id, :applno, :c, :t)"
    ), {"id": cafequip_id, "applno": applno, "c": condition, "t": tahun})

def _parse_ddmmyyyy(value: str):
    try:
        return datetime.strptime(value, "%d-%m-%Y").date()
    except (ValueError, TypeError):
        return None

def _apply_age_deviation(applno: str, dob: date):
    age = (date.today() - dob).days // 365
    if age < 21:
        code = "1206"
    elif age > 55:
        code = "1207"
    else:
        db.session.execute(text(
            "DELETE FROM CAFDEV WHERE APPL_NO = :applno AND DEVIATION_CD IN ('1206', '1207')"
        ), {"applno": applno})
        return

    existing = db.session.execute(text(
        "SELECT REASON FROM CAFDEV WHERE APPL_NO = :applno AND DEVIATION_CD = :code"
    ), {"applno": applno, "code": code}).fetchone()
    if not existing:
        std = db.session.execute(text("""
            SELECT DEVIATION_CD, DEVIATION_DESC, STANDARD_DESC FROM MSTDEVIATION WITH(NOLOCK)
            WHERE DEVIATION_CD = :code
        """), {"code": code}).fetchone()
        if std:
            db.session.execute(text("""
                INSERT INTO CAFDEV (APPL_NO, DEVIATION_CD, REASON, DEVIATION_DESC, STANDARD_DESC, INPUT_DT)
                VALUES (:applno, :cd, '', :dd, :sd, GETDATE())
            """), {"applno": applno, "cd": std.DEVIATION_CD, "dd": std.DEVIATION_DESC, "sd": std.STANDARD_DESC})

@cam_customer_bp.route("/detail", methods=["GET"])
@login_required
def get_detail():
    apless = request.args.get("apless", "")

    data = {
        "lesseeNm": "", "lesseeCat": "", "address1": "", "city1": "", "zipcode1": "",
        "phone2": "", "mobilePhone1": "", "mobilePhone2": "", "mobilePhone3": "",
        "otherPhone1": "", "otherPhone2": "", "otherPhoneNotes1": "", "otherPhoneNotes2": "",
        "email1": "", "email2": "", "npwp": "", "areaCd": "", "fax1": "",
        "spouse": "", "spouseWt": "", "mother": "", "grpcode": "", "placebirth": "",
        "tglbirth": "", "gender": "", "marital": "", "religion": "", "citizen1": "",
        "nationality": "", "custType": "", "idCard": "", "idCardValid": "", "famCard": "",
        "aliasName": "", "kecamatan1": "", "kelurahan1": "", "rt1": "", "rw1": "",
        "emergencyName": "", "emergencyAddress": "", "emergencyPhone": "", "emergencyRelation": "",
        "addrNpwp": "", "areaCdNpwp": "", "kecamatanNpwp": "", "kelurahanNpwp": "", "zipcode2Npwp": "",
        "grnSpouseAdd": "", "areaCdz": "", "city1z": "", "kecamatan1z": "", "kelurahan1z": "",
        "rt1z": "", "rw1z": "", "zipcode1z": "", "yearLive": "", "spouseMobilePhone": "",
        "spouseEmail": "", "ocuType": "", "idCardName": "", "lEdu": "", "career": "",
        "placebirth2": "", "tglbirth2": "", "citizen2": "", "nationality2": "", "idCard2": "",
        "idCardValid2": "", "sPass": "", "mAgree": "", "dependent": "", "relMlci": "e3", "passNo": "",
    }

    if apless:
        row = db.session.execute(text("""
            SELECT cld.PASSPORTNO, ca.LESSEE_NM, ca.Lessee_Cat, ca.ADDRESS1, cda.KECAMATAN, cda.KELURAHAN,
                cda.RT, cda.RW, cda.EMERGENCY_NAME, cda.EMERGENCY_ADDRESS, cda.EMERGENCY_PHONE,
                cda.EMERGENCY_RELATION, ca.CITY1, ca.ZipCode1, ca.PHONE2, ca.Mobile_phone1,
                ca.Mobile_phone2, ca.Mobile_phone3, ca.EMAIL1, ca.EMAIL2, ca.NPWP, ca.Area_CD, ca.Fax1,
                ca.Spouse, ca.Mother, ca.GrpCode, ca.PLACEBIRTH, ca.TGLBIRTH, ca.GENDER, ca.MARITAL,
                ca.RELIGION, ca.Citizen, ca.Nationality, ca.Cust_Type, ca.ID_CARD, ca.Id_Card_Valid,
                ca.FAM_CARD, ca.INDUS_CODE, ca.OTHER_PHONE1, ca.OTHER_PHONE2, ca.OTHER_PHONENOTES1,
                ca.OTHER_PHONENOTES2, ca.ALIAS_NAME, cld.BUSINESS_TYPE, cld.Fullname_Without_Title,
                cld.LAST_EDUCATION, cld.CAREER_FIELD, cld.SPOUSE_PLACEBIRTH, cld.SPOUSE_TGLBIRTH,
                cld.SPOUSE_CITIZEN, cld.SPOUSE_NATIONALITY, cld.SPOUSE_ID_CARD, cld.SPOUSE_Id_CARD_VALID,
                cld.SPOUSE_PASSPORTNO, cld.SPOUSE_MARRIAGE, cld.SPOUSE_DEPENDENT,
                ISNULL(cld.RELATIONSHIP, 'e3') AS RELATIONSHIP, cld.SPOUSE_Fullname_Without_Title,
                cda.Address_NPWP, cda.Area_CD_NPWP, cda.Kecamatan_NPWP, cda.Kelurahan_NPWP,
                cda.zipcode_NPWP, cda.Spouse_Address, cda.Spouse_Area_CD, cda.Spouse_City,
                cda.Spouse_Kecamatan, cda.Spouse_Kelurahan, cda.Spouse_RT, cda.Spouse_RW,
                cda.Spouse_Zipcode, cld.Live_since, cld.SPOUSE_MobilePhone, cld.SPOUSE_Email
            FROM CAFLESS ca WITH(NOLOCK)
                LEFT JOIN CAFLESS_DETAIL_ADDRESS cda WITH(NOLOCK) ON ca.APLESS = cda.APLESS
                LEFT JOIN CAFLESS_DETAIL cld WITH(NOLOCK) ON ca.APLESS = cld.APLESS
            WHERE ca.APLESS = :apless
        """), {"apless": apless}).fetchone()

        if row:
            data.update({
                "lesseeNm": row.LESSEE_NM or "", "lesseeCat": row.Lessee_Cat or "",
                "address1": row.ADDRESS1 or "", "kecamatan1": row.KECAMATAN or "",
                "kelurahan1": row.KELURAHAN or "", "rt1": row.RT or "", "rw1": row.RW or "",
                "city1": row.CITY1 or "", "emergencyName": row.EMERGENCY_NAME or "",
                "emergencyAddress": row.EMERGENCY_ADDRESS or "",
                "emergencyPhone": _normalize_phone(row.EMERGENCY_PHONE),
                "emergencyRelation": row.EMERGENCY_RELATION or "", "aliasName": row.ALIAS_NAME or "",
                "zipcode1": row.ZipCode1 or "", "addrNpwp": row.Address_NPWP or "",
                "areaCdNpwp": row.Area_CD_NPWP or "", "kecamatanNpwp": row.Kecamatan_NPWP or "",
                "kelurahanNpwp": row.Kelurahan_NPWP or "", "zipcode2Npwp": row.zipcode_NPWP or "",
                "grnSpouseAdd": row.Spouse_Address or "", "areaCdz": row.Spouse_Area_CD or "",
                "city1z": row.Spouse_City or "", "kecamatan1z": row.Spouse_Kecamatan or "",
                "kelurahan1z": row.Spouse_Kelurahan or "", "rt1z": row.Spouse_RT or "",
                "rw1z": row.Spouse_RW or "", "zipcode1z": row.Spouse_Zipcode or "",
                "yearLive": row.Live_since or "", "spouseMobilePhone": _normalize_phone(row.SPOUSE_MobilePhone),
                "spouseEmail": row.SPOUSE_Email or "", "phone2": _normalize_phone(row.PHONE2),
                "mobilePhone1": _normalize_phone(row.Mobile_phone1),
                "mobilePhone2": _normalize_phone(row.Mobile_phone2),
                "mobilePhone3": _normalize_phone(row.Mobile_phone3),
                "otherPhone1": _normalize_phone(row.OTHER_PHONE1),
                "otherPhone2": _normalize_phone(row.OTHER_PHONE2),
                "otherPhoneNotes1": row.OTHER_PHONENOTES1 or "", "otherPhoneNotes2": row.OTHER_PHONENOTES2 or "",
                "email1": row.EMAIL1 or "", "email2": row.EMAIL2 or "", "npwp": row.NPWP or "",
                "areaCd": row.Area_CD or "", "fax1": row.Fax1 or "", "spouse": row.Spouse or "",
                "spouseWt": row.SPOUSE_Fullname_Without_Title or "", "mother": row.Mother or "",
                "grpcode": row.GrpCode or "", "placebirth": row.PLACEBIRTH or "",
                "tglbirth": row.TGLBIRTH.strftime("%d-%m-%Y") if row.TGLBIRTH else "",
                "gender": row.GENDER or "", "marital": row.MARITAL or "", "religion": row.RELIGION or "",
                "citizen1": row.Citizen or "", "nationality": row.Nationality or "",
                "custType": row.Cust_Type or "", "idCard": row.ID_CARD or "",
                "idCardValid": row.Id_Card_Valid.strftime("%d-%m-%Y") if row.Id_Card_Valid else "",
                "famCard": row.FAM_CARD or "", "ocuType": row.BUSINESS_TYPE or "",
                "idCardName": row.Fullname_Without_Title or "", "lEdu": row.LAST_EDUCATION or "",
                "career": row.CAREER_FIELD or "", "placebirth2": row.SPOUSE_PLACEBIRTH or "",
                "tglbirth2": row.SPOUSE_TGLBIRTH.strftime("%d-%m-%Y") if row.SPOUSE_TGLBIRTH else "",
                "citizen2": row.SPOUSE_CITIZEN or "", "nationality2": row.SPOUSE_NATIONALITY or "",
                "idCard2": row.SPOUSE_ID_CARD or "",
                "idCardValid2": row.SPOUSE_Id_CARD_VALID.strftime("%d-%m-%Y") if row.SPOUSE_Id_CARD_VALID else "",
                "sPass": row.SPOUSE_PASSPORTNO or "", "mAgree": row.SPOUSE_MARRIAGE or "",
                "dependent": row.SPOUSE_DEPENDENT or "", "relMlci": row.RELATIONSHIP or "e3",
                "passNo": row.PASSPORTNO or "",
            })

    return jsonify({
        "data": data,
        "lookups": {
            "customerProfiles": [
                {"value": r.CUST_TYPE, "label": r.NAME} for r in db.session.execute(text(
                    "SELECT CUST_TYPE, NAME FROM MSTLESSEETYPE WITH(NOLOCK) WHERE LESSEE_TP = 'PR'"
                )).fetchall()
            ],
            "religions": [{"value": r.Religion, "label": r.name} for r in db.session.execute(text(
                "SELECT Religion, name FROM MSTRELIGION WITH(NOLOCK)"
            )).fetchall()],
            "maritalStatuses": [{"value": r.Marital, "label": r.name} for r in db.session.execute(text(
                "SELECT Marital, name FROM MSTMARITAL WITH(NOLOCK)"
            )).fetchall()],
            "countries": [{"value": r.ID2digit, "label": r.Name} for r in db.session.execute(text(
                "SELECT ID2digit, Name FROM Mst_Country WITH(NOLOCK) ORDER BY Name"
            )).fetchall()],
            "groups": [{"value": r.GrpCode, "label": r.GrpName} for r in db.session.execute(text("""
                SELECT GrpCode, GrpName FROM CLFGROUP WITH(NOLOCK) WHERE GrpCode IN ('001', '002') AND FLGDEL = '0'
                UNION SELECT GrpCode, GrpName FROM CLFGROUP WITH(NOLOCK) WHERE GrpCode NOT IN ('001', '002') AND FLGDEL = '0'
            """)).fetchall()],
            "biCustomerTypes": [{"value": r.OJK_Code, "label": r.MLCI_Desc} for r in db.session.execute(text(
                "SELECT OJK_Code, MLCI_Desc FROM UMFBITYP_LBPP WITH(NOLOCK) WHERE OJK_Code IS NOT NULL ORDER BY MLCI_Desc"
            )).fetchall()],
            "relationshipWithCompany": [{"value": r.VALUE, "label": r.DESC_VALUE} for r in db.session.execute(text(
                "SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE = 'RELATIONSHIP_MLCI' ORDER BY DESC_VALUE"
            )).fetchall()],
            "lastEducation": _fetch_combo("LAST_EDU"),
            "careerField": _fetch_combo("CAREER_FIELD"),
            "dependent": _fetch_combo("DEPENDENT"),
            "marriageAgreement": _fetch_combo("YES_NO"),
        },
    })

REQUIRED_FIELDS_MESSAGES = [
    ("idCardName", "ID Card Name must not empty"),
    ("lesseeNm", "Customer Name must not empty"),
    ("lesseeCat", "Customer Type must not empty"),
    ("address1", "ID Address must not empty"),
    ("city1", "City must not empty"),
    ("areaCd", "Area must not empty"),
    ("phone2", "Phone must not empty"),
    ("mobilePhone1", "Mobile 1 must not empty"),
    ("mother", "Mother's Maiden Name must not empty"),
    ("placebirth", "Place of Birth must not empty"),
    ("gender", "Gender must not empty"),
    ("marital", "Marital Status must not empty"),
    ("religion", "Religion must not empty"),
    ("citizen1", "Citizenship must not empty"),
    ("idCard", "ID Card No. must not empty"),
    ("famCard", "Family Card No. must not empty"),
    ("lEdu", "Last Education must not empty"),
    ("career", "Career Field must not empty"),
]

PHONE_FIELDS = ["phone2", "mobilePhone1", "mobilePhone2", "mobilePhone3", "otherPhone1", "otherPhone2"]

@cam_customer_bp.route("/detail", methods=["POST"])
@login_required
def save_detail():
    payload = request.get_json(silent=True) or {}
    editable = payload.get("editable")
    if editable != 1:
        return jsonify({
            "success": False,
            "message": "editable must be 1 — the editable=0 seed-only path from prev_next() wasn't ported (see module docstring).",
        }), 400

    apless = payload.get("apless", "")
    applno = payload.get("applno", "")
    fin_type = payload.get("finType", "")
    guarantor = payload.get("guarantor", "")
    new_car = payload.get("newCar", "")
    purpoffinc = payload.get("purpoffinc", "")
    cont_type = payload.get("contType", "")
    r_change = payload.get("restructuringChange", "")

    d = {k: (payload.get(k) or "").strip() if isinstance(payload.get(k), str) else payload.get(k) for k in payload}

    errors = {}
    for field, message in REQUIRED_FIELDS_MESSAGES:
        if not d.get(field):
            errors[field] = message

    if d.get("zipcode1") and len(d["zipcode1"]) != 5:
        errors["zipcode1"] = "Post Code must not empty or must be 5 digits"
    elif not d.get("zipcode1"):
        errors["zipcode1"] = "Post Code must not empty or must be 5 digits"

    if d.get("nationality") in (None, "") and d.get("citizen1") != "WNI":
        errors["nationality"] = "Nationality must not empty"

    dob = _parse_ddmmyyyy(d.get("tglbirth", ""))
    if not dob or dob >= date.today():
        errors["tglbirth"] = "Date of Birth not valid"

    for f in PHONE_FIELDS:
        v = d.get(f) or ""
        if len(v) > 18:
            errors[f] = f"{f} max 18 digit"

    npwp_digits = "".join(c for c in (d.get("npwp") or "") if c.isalnum())
    if len(npwp_digits) < 15:
        errors["npwp"] = "NPWP must 15 digit"

    year_live = d.get("yearLive") or ""
    if not year_live:
        errors["yearLive"] = "Live here since (year) must not empty"
    elif len(year_live) < 4:
        errors["yearLive"] = "Live here since (year) must 4 digit year"

    if errors:
        return jsonify({"success": False, "errors": errors}), 422

    username = _session_str("username")
    emp_id = _session_str("emp_id")
    branch_cd = _session_str("branchcode")

    watchlist_result = _check_watchlist_blacklist(
        d.get("lesseeNm"), d.get("address1"), d.get("idCard"), d.get("mother"), d.get("tglbirth"),
        "PR", apless, d.get("npwp"),
    )
    if watchlist_result["status"] == "blacklist":
        return jsonify({"success": False, "message": watchlist_result.get("message", "Blacklisted"), "blocked": True}), 403

    try:
        is_new = not apless
        if is_new:
            apless = _generate_apless()
            if not apless:
                db.session.rollback()
                return jsonify({"success": False, "message": "Cannot create CAM, please call helpdesk"}), 500

        phone2 = _format_phone_db(d.get("phone2"))
        mobile1 = _format_phone_db(d.get("mobilePhone1"))
        mobile2 = _format_phone_db(d.get("mobilePhone2"))
        mobile3 = _format_phone_db(d.get("mobilePhone3"))
        other1 = _format_phone_db(d.get("otherPhone1"))
        other2 = _format_phone_db(d.get("otherPhone2"))
        emergency_phone = _format_phone_db(d.get("emergencyPhone"))
        spouse_mobile = _format_phone_db(d.get("spouseMobilePhone"))
        id_card_valid1 = _parse_ddmmyyyy(d.get("idCardValid", ""))
        tglbirth2 = _parse_ddmmyyyy(d.get("tglbirth2", ""))
        id_card_valid2 = _parse_ddmmyyyy(d.get("idCardValid2", ""))

        if d.get("cekbokSame") == "1":
            area_cdz = d.get("areaCd")
            kecamatan1z = d.get("kecamatan1")
            kelurahan1z = d.get("kelurahan1")
            rt1z = d.get("rt1")
            rw1z = d.get("rw1")
            zipcode1z = d.get("zipcode1")
        else:
            area_cdz = d.get("areaCdz")
            kecamatan1z = d.get("kecamatan1z")
            kelurahan1z = d.get("kelurahan1z")
            rt1z = d.get("rt1z")
            rw1z = d.get("rw1z")
            zipcode1z = d.get("zipcode1z")

        if is_new:
            db.session.execute(text("""
                INSERT INTO CAFLESS (APLESS, LESSEE_NM, LESSEE_TP, ADDRESS1, CITY1, ZipCode1, PHONE2,
                    Mobile_phone1, Mobile_phone2, Mobile_phone3, EMAIL1, EMAIL2, NPWP, Area_CD, Fax1,
                    Send_SMS, Spouse, Mother, GrpCode, PLACEBIRTH, TGLBIRTH, GENDER, MARITAL, RELIGION,
                    Citizen, Nationality, Cust_Type, ID_CARD, Id_Card_Valid, FAM_CARD, INDUS_CODE,
                    Lessee_Cat, RELATION, OTHER_PHONE1, OTHER_PHONE2, OTHER_PHONENOTES1, OTHER_PHONENOTES2, ALIAS_NAME)
                VALUES (:apless, :lessee_nm, 'PR', :address1, :city1, :zipcode1, :phone2, :m1, :m2, :m3,
                    :email1, :email2, :npwp, :area_cd, :fax1, '1', :spouse, :mother, :grpcode, :placebirth,
                    :tglbirth, :gender, :marital, :religion, :citizen1, :nationality, :cust_type, :id_card,
                    :id_card_valid, :fam_card, :indus_code, :lessee_cat, '2', :other1, :other2, :opn1, :opn2, :alias)
            """), {
                "apless": apless, "lessee_nm": d.get("lesseeNm"), "address1": d.get("address1"),
                "city1": d.get("city1"), "zipcode1": d.get("zipcode1"), "phone2": phone2, "m1": mobile1,
                "m2": mobile2, "m3": mobile3, "email1": d.get("email1"), "email2": d.get("email2"),
                "npwp": npwp_digits, "area_cd": d.get("areaCd"), "fax1": d.get("fax1"),
                "spouse": d.get("spouse"), "mother": d.get("mother"), "grpcode": d.get("grpcode"),
                "placebirth": d.get("placebirth"), "tglbirth": dob, "gender": d.get("gender"),
                "marital": d.get("marital"), "religion": d.get("religion"), "citizen1": d.get("citizen1"),
                "nationality": d.get("nationality"), "cust_type": d.get("custType"),
                "id_card": d.get("idCard"), "id_card_valid": id_card_valid1, "fam_card": d.get("famCard"),
                "indus_code": d.get("indCode5") or d.get("indusCode"), "lessee_cat": d.get("lesseeCat"),
                "other1": other1, "other2": other2, "opn1": d.get("otherPhoneNotes1"),
                "opn2": d.get("otherPhoneNotes2"), "alias": d.get("aliasName"),
            })
            db.session.execute(text("""
                INSERT INTO CAFLESS_DETAIL_ADDRESS (APLESS, KECAMATAN, KELURAHAN, RT, RW, EMERGENCY_NAME,
                    EMERGENCY_ADDRESS, EMERGENCY_PHONE, EMERGENCY_RELATION, Address_NPWP, Area_CD_NPWP,
                    Kecamatan_NPWP, Kelurahan_NPWP, Zipcode_NPWP, Spouse_Address, Spouse_Area_CD, Spouse_City,
                    Spouse_Kecamatan, Spouse_Kelurahan, Spouse_RT, Spouse_RW, Spouse_Zipcode)
                VALUES (:apless, :kec, :kel, :rt, :rw, :en, :ea, :ep, :er, :an, :acn, :kn, :keln, :zn,
                    :gsa, :acz, :cz, :kz, :kelz, :rtz, :rwz, :zz)
            """), {
                "apless": apless, "kec": d.get("kecamatan1"), "kel": d.get("kelurahan1"),
                "rt": d.get("rt1"), "rw": d.get("rw1"), "en": d.get("emergencyName"),
                "ea": d.get("emergencyAddress"), "ep": emergency_phone, "er": d.get("emergencyRelation"),
                "an": d.get("addrNpwp"), "acn": d.get("areaCdNpwp"), "kn": d.get("kecamatanNpwp"),
                "keln": d.get("kelurahanNpwp"), "zn": d.get("zipcode2Npwp"), "gsa": d.get("grnSpouseAdd"),
                "acz": area_cdz, "cz": d.get("city1z"), "kz": kecamatan1z, "kelz": kelurahan1z,
                "rtz": rt1z, "rwz": rw1z, "zz": zipcode1z,
            })
        else:
            db.session.execute(text("""
                UPDATE CAFLESS SET LESSEE_NM = :lessee_nm, Lessee_Cat = :lessee_cat, ADDRESS1 = :address1,
                    CITY1 = :city1, ZipCode1 = :zipcode1, PHONE2 = :phone2, Mobile_phone1 = :m1,
                    Mobile_phone2 = :m2, Mobile_phone3 = :m3, EMAIL1 = :email1, EMAIL2 = :email2,
                    NPWP = :npwp, Area_CD = :area_cd, Fax1 = :fax1, Send_SMS = '1', Spouse = :spouse,
                    Mother = :mother, GrpCode = :grpcode, PLACEBIRTH = :placebirth, TGLBIRTH = :tglbirth,
                    GENDER = :gender, MARITAL = :marital, RELIGION = :religion, Citizen = :citizen1,
                    Nationality = :nationality, Cust_Type = :cust_type, ID_CARD = :id_card,
                    Id_Card_Valid = :id_card_valid, FAM_CARD = :fam_card, INDUS_CODE = :indus_code,
                    OTHER_PHONE1 = :other1, OTHER_PHONE2 = :other2, OTHER_PHONENOTES1 = :opn1,
                    OTHER_PHONENOTES2 = :opn2, LESSEE_TP = 'PR', ALIAS_NAME = :alias
                WHERE APLESS = :apless
            """), {
                "lessee_nm": d.get("lesseeNm"), "lessee_cat": d.get("lesseeCat"), "address1": d.get("address1"),
                "city1": d.get("city1"), "zipcode1": d.get("zipcode1"), "phone2": phone2, "m1": mobile1,
                "m2": mobile2, "m3": mobile3, "email1": d.get("email1"), "email2": d.get("email2"),
                "npwp": npwp_digits, "area_cd": d.get("areaCd"), "fax1": d.get("fax1"),
                "spouse": d.get("spouse"), "mother": d.get("mother"), "grpcode": d.get("grpcode"),
                "placebirth": d.get("placebirth"), "tglbirth": dob, "gender": d.get("gender"),
                "marital": d.get("marital"), "religion": d.get("religion"), "citizen1": d.get("citizen1"),
                "nationality": d.get("nationality"), "cust_type": d.get("custType"),
                "id_card": d.get("idCard"), "id_card_valid": None, "fam_card": d.get("famCard"),
                "indus_code": d.get("indCode5") or d.get("indusCode"), "other1": other1, "other2": other2,
                "opn1": d.get("otherPhoneNotes1"), "opn2": d.get("otherPhoneNotes2"), "alias": d.get("aliasName"),
                "apless": apless,
            })

            exists_addr = db.session.execute(text(
                "SELECT 1 FROM CAFLESS_DETAIL_ADDRESS WITH(NOLOCK) WHERE APLESS = :apless"
            ), {"apless": apless}).fetchone()
            addr_params = {
                "en": d.get("emergencyName"), "ea": d.get("emergencyAddress"), "ep": emergency_phone,
                "er": d.get("emergencyRelation"), "kec": d.get("kecamatan1"), "kel": d.get("kelurahan1"),
                "rt": d.get("rt1"), "rw": d.get("rw1"), "an": d.get("addrNpwp"), "acn": d.get("areaCdNpwp"),
                "kn": d.get("kecamatanNpwp"), "keln": d.get("kelurahanNpwp"), "zn": d.get("zipcode2Npwp"),
                "gsa": d.get("grnSpouseAdd"), "acz": area_cdz, "cz": d.get("city1z"), "kz": kecamatan1z,
                "kelz": kelurahan1z, "rtz": rt1z, "rwz": rw1z, "zz": zipcode1z, "apless": apless,
            }
            if exists_addr:
                db.session.execute(text("""
                    UPDATE CAFLESS_DETAIL_ADDRESS SET EMERGENCY_NAME = :en, EMERGENCY_ADDRESS = :ea,
                        EMERGENCY_PHONE = :ep, EMERGENCY_RELATION = :er, KECAMATAN = :kec, KELURAHAN = :kel,
                        RT = :rt, RW = :rw, Address_NPWP = :an, Area_CD_NPWP = :acn, Kecamatan_NPWP = :kn,
                        Kelurahan_NPWP = :keln, Zipcode_NPWP = :zn, Spouse_Address = :gsa,
                        Spouse_Area_CD = :acz, Spouse_City = :cz, Spouse_Kecamatan = :kz,
                        Spouse_Kelurahan = :kelz, Spouse_RT = :rtz, Spouse_RW = :rwz, Spouse_Zipcode = :zz
                    WHERE APLESS = :apless
                """), addr_params)
            else:
                db.session.execute(text("""
                    INSERT INTO CAFLESS_DETAIL_ADDRESS (APLESS, KECAMATAN, KELURAHAN, RT, RW, EMERGENCY_NAME,
                        EMERGENCY_ADDRESS, EMERGENCY_PHONE, EMERGENCY_RELATION, Address_NPWP, Area_CD_NPWP,
                        Kecamatan_NPWP, Kelurahan_NPWP, Zipcode_NPWP, Spouse_Address, Spouse_Area_CD,
                        Spouse_City, Spouse_Kecamatan, Spouse_Kelurahan, Spouse_RT, Spouse_RW, Spouse_Zipcode)
                    VALUES (:apless, :kec, :kel, :rt, :rw, :en, :ea, :ep, :er, :an, :acn, :kn, :keln, :zn,
                        :gsa, :acz, :cz, :kz, :kelz, :rtz, :rwz, :zz)
                """), addr_params)

        detail_params = {
            "apless": apless, "ocu_type": d.get("ocuType"), "id_card_name": d.get("idCardName"),
            "l_edu": d.get("lEdu"), "career": d.get("career"), "placebirth2": d.get("placebirth2"),
            "tglbirth2": tglbirth2, "citizen2": d.get("citizen2"), "nationality2": d.get("nationality2"),
            "id_card2": d.get("idCard2"), "id_card_valid2": id_card_valid2, "s_pass": d.get("sPass"),
            "m_agree": d.get("mAgree"), "dependent": d.get("dependent") or "0", "rel_mlci": d.get("relMlci"),
            "pass_no": d.get("passNo"), "spouse_wt": d.get("spouseWt"), "year_live": d.get("yearLive"),
            "spouse_mobile": spouse_mobile, "spouse_email": d.get("spouseEmail"),
        }
        exists_detail = db.session.execute(text(
            "SELECT 1 FROM CAFLESS_DETAIL WITH(NOLOCK) WHERE APLESS = :apless"
        ), {"apless": apless}).fetchone()
        if exists_detail:
            db.session.execute(text("""
                UPDATE CAFLESS_DETAIL SET BUSINESS_TYPE = :ocu_type, Fullname_Without_Title = :id_card_name,
                    LAST_EDUCATION = :l_edu, CAREER_FIELD = :career, SPOUSE_PLACEBIRTH = :placebirth2,
                    SPOUSE_TGLBIRTH = :tglbirth2, SPOUSE_CITIZEN = :citizen2, SPOUSE_NATIONALITY = :nationality2,
                    SPOUSE_ID_CARD = :id_card2, SPOUSE_Id_CARD_VALID = :id_card_valid2, SPOUSE_PASSPORTNO = :s_pass,
                    SPOUSE_MARRIAGE = :m_agree, SPOUSE_DEPENDENT = :dependent, RELATIONSHIP = :rel_mlci,
                    PASSPORTNO = :pass_no, SPOUSE_Fullname_Without_Title = :spouse_wt, Live_since = :year_live,
                    SPOUSE_MobilePhone = :spouse_mobile, SPOUSE_Email = :spouse_email
                WHERE APLESS = :apless
            """), detail_params)
        else:
            db.session.execute(text("""
                INSERT INTO CAFLESS_DETAIL (APLESS, BUSINESS_TYPE, Fullname_Without_Title, LAST_EDUCATION,
                    CAREER_FIELD, SPOUSE_PLACEBIRTH, SPOUSE_TGLBIRTH, SPOUSE_CITIZEN, SPOUSE_NATIONALITY,
                    SPOUSE_ID_CARD, SPOUSE_Id_CARD_VALID, SPOUSE_PASSPORTNO, SPOUSE_MARRIAGE, SPOUSE_DEPENDENT,
                    RELATIONSHIP, PASSPORTNO, SPOUSE_Fullname_Without_Title, Live_since, SPOUSE_MobilePhone, SPOUSE_Email)
                VALUES (:apless, :ocu_type, :id_card_name, :l_edu, :career, :placebirth2, :tglbirth2, :citizen2,
                    :nationality2, :id_card2, :id_card_valid2, :s_pass, :m_agree, :dependent, :rel_mlci, :pass_no,
                    :spouse_wt, :year_live, :spouse_mobile, :spouse_email)
            """), detail_params)

        if d.get("marital") in ("D", "S"):
            has_ffs = db.session.execute(text(
                "SELECT 1 FROM CAFFS WITH(NOLOCK) WHERE APLESS = :apless AND ITEM_CODE = '310103'"
            ), {"apless": apless}).fetchone()
            if has_ffs:
                db.session.execute(text(
                    "UPDATE CAFFS SET AMOUNT = '0' WHERE APLESS = :apless AND ITEM_CODE = '310103'"
                ), {"apless": apless})

        if applno:
            if cont_type in ("RS1", "RS0"):
                exists_restr = db.session.execute(text(
                    "SELECT 1 FROM CAFCONT_RESTRUCTURING WITH(NOLOCK) WHERE APPL_NO = :applno"
                ), {"applno": applno}).fetchone()
                if exists_restr:
                    db.session.execute(text(
                        "UPDATE CAFCONT_RESTRUCTURING SET RESTRUCTURING_CHANGE = :rc WHERE APPL_NO = :applno"
                    ), {"rc": r_change, "applno": applno})
                else:
                    db.session.execute(text(
                        "INSERT INTO CAFCONT_RESTRUCTURING (APPL_NO, RESTRUCTURING_CHANGE) VALUES (:applno, :rc)"
                    ), {"applno": applno, "rc": r_change})
            else:
                db.session.execute(text(
                    "DELETE FROM CAFCONT_RESTRUCTURING WHERE APPL_NO = :applno"
                ), {"applno": applno})
        else:
            has_guarantor = 0 if guarantor == "1" else (1 if guarantor == "2" else None)
            applno = _generate_applno(emp_id)
            if not applno:
                db.session.rollback()
                return jsonify({"success": False, "message": "Cannot create CAM, please call helpdesk"}), 500
            _seed_new_application(applno, apless, branch_cd, emp_id, fin_type, has_guarantor, purpoffinc, cont_type, new_car)

        if dob:
            _apply_age_deviation(applno, dob)

        business_type = d.get("ocuType") or ""
        if len(business_type) >= 4 and business_type[3:4] != "H":
            db.session.execute(text(
                "UPDATE Kuisioner_EDD SET EDD_Customer = NULL WHERE APPL_NO = :applno"
            ), {"applno": applno})

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("cust_detail save failed")
        return jsonify({"success": False, "message": "Failed"}), 500

    response = {"success": True, "message": "Successful", "apless": apless, "applno": applno}
    if watchlist_result["status"] == "watchlist":
        response["watchlistWarning"] = watchlist_result.get("message")
    return jsonify(response)

CORPORATE_REQUIRED_FIELDS_MESSAGES = [
    ("lesseeNm", "Customer Name must not empty"),
    ("lesseeCat", "Customer Type must not empty"),
    ("address2", "Address must not empty"),
    ("city2", "City must not empty"),
    ("addressStatus", "Office Status must not empty"),
    ("areaCd", "Area must not empty"),
    ("phone1", "Phone must not empty"),
    ("mobilePhone1", "Mobile 1 must not empty"),
    ("contact", "Contact Person must not empty"),
    ("occupation", "Position must not empty"),
    ("businessEntity", "Form of Business Entity must not empty"),
]

CORPORATE_PHONE_FIELDS = ["phone1", "mobilePhone1", "mobilePhone2", "mobilePhone3", "otherPhone1", "otherPhone2"]

def _strip_special(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "", value or "")

@cam_customer_bp.route("/corporate-detail", methods=["GET"])
@login_required
def get_corporate_detail():
    apless = request.args.get("apless", "")

    data = {
        "lesseeNm": "", "lesseeCat": "", "idCardName": "", "address1": "", "address2": "", "city1": "",
        "city2": "", "addressStatus": "", "zipcode2": "", "phone1": "", "mobilePhone1": "", "mobilePhone2": "",
        "mobilePhone3": "", "otherPhone1": "", "otherPhone2": "", "otherPhoneNotes1": "", "otherPhoneNotes2": "",
        "email1": "", "npwp": "", "areaCd": "", "fax1": "", "grpcode": "", "placebirth": "", "tglbirth": "",
        "custType": "", "indusCode": "", "lob": "", "contact": "", "occupation": "", "kecamatan1": "",
        "kelurahan1": "", "rt1": "", "rw1": "", "emergencyName": "", "emergencyAddress": "", "emergencyPhone": "",
        "emergencyRelation": "", "siup": "", "domicile": "", "addrNpwp": "", "areaCdNpwp": "", "kecamatanNpwp": "",
        "kelurahanNpwp": "", "zipcode2Npwp": "", "businessEntity": "", "relMlci": "e3", "employeeNumber": "",
    }

    if apless:
        row = db.session.execute(text("""
            SELECT ca.LESSEE_NM, ca.Lessee_Cat, ca.ADDRESS1, ca.ADDRESS2, ca.CITY2, ca.Address_Status,
                ca.ZipCode2, ca.PHONE1, ca.Mobile_phone1, ca.Mobile_phone2, ca.Mobile_phone3, ca.EMAIL1,
                ca.NPWP, ca.Occupation, ca.Area_CD, ca.Fax1, ca.Contact, ca.GrpCode, ca.PLACEBIRTH, ca.TGLBIRTH,
                ca.Cust_Type, ca.INDUS_CODE, ca.LOB, ca.OTHER_PHONE1, ca.OTHER_PHONE2, ca.OTHER_PHONENOTES1,
                ca.OTHER_PHONENOTES2, cda.KECAMATAN, cda.KELURAHAN, cda.RT, cda.RW, cda.EMERGENCY_NAME,
                cda.EMERGENCY_ADDRESS, cda.EMERGENCY_PHONE, cda.EMERGENCY_RELATION, cda.SIUP_NO, cda.DOMICILE_NO,
                cda.Address_NPWP, cda.Area_CD_NPWP, cda.Kecamatan_NPWP, cda.Kelurahan_NPWP, cda.zipcode_NPWP,
                cld.BUSINESS_TYPE, cld.Fullname_Without_Title, cld.RELATIONSHIP, cld.BUSINESS_ENTITY,
                cld.NumberOfEmployee
            FROM CAFLESS ca WITH (NOLOCK)
                LEFT JOIN CAFLESS_DETAIL_ADDRESS cda WITH (NOLOCK) ON ca.APLESS = cda.APLESS
                LEFT JOIN CAFLESS_DETAIL cld WITH (NOLOCK) ON ca.APLESS = cld.APLESS
            WHERE ca.APLESS = :apless
        """), {"apless": apless}).fetchone()

        if row:
            data.update({
                "lesseeNm": row.LESSEE_NM or "", "lesseeCat": row.Lessee_Cat or "",
                "idCardName": row.Fullname_Without_Title or "", "address1": row.ADDRESS1 or "",
                "address2": row.ADDRESS2 or "", "city2": row.CITY2 or "", "addressStatus": row.Address_Status or "",
                "zipcode2": row.ZipCode2 or "", "phone1": _normalize_phone(row.PHONE1),
                "mobilePhone1": _normalize_phone(row.Mobile_phone1), "mobilePhone2": _normalize_phone(row.Mobile_phone2),
                "mobilePhone3": _normalize_phone(row.Mobile_phone3), "otherPhone1": _normalize_phone(row.OTHER_PHONE1),
                "otherPhone2": _normalize_phone(row.OTHER_PHONE2), "otherPhoneNotes1": row.OTHER_PHONENOTES1 or "",
                "otherPhoneNotes2": row.OTHER_PHONENOTES2 or "", "email1": row.EMAIL1 or "", "npwp": row.NPWP or "",
                "areaCd": row.Area_CD or "", "fax1": row.Fax1 or "", "grpcode": row.GrpCode or "",
                "placebirth": row.PLACEBIRTH or "",
                "tglbirth": row.TGLBIRTH.strftime("%d-%m-%Y") if row.TGLBIRTH else "",
                "custType": row.Cust_Type or "", "indusCode": (row.INDUS_CODE or "").strip(),
                "lob": row.LOB or "", "contact": row.Contact or "", "occupation": row.Occupation or "",
                "kecamatan1": row.KECAMATAN or "", "kelurahan1": row.KELURAHAN or "", "rt1": row.RT or "",
                "rw1": row.RW or "", "emergencyName": row.EMERGENCY_NAME or "",
                "emergencyAddress": row.EMERGENCY_ADDRESS or "", "emergencyPhone": _normalize_phone(row.EMERGENCY_PHONE),
                "emergencyRelation": row.EMERGENCY_RELATION or "", "siup": row.SIUP_NO or "",
                "domicile": row.DOMICILE_NO or "", "addrNpwp": row.Address_NPWP or "",
                "areaCdNpwp": row.Area_CD_NPWP or "", "kecamatanNpwp": row.Kecamatan_NPWP or "",
                "kelurahanNpwp": row.Kelurahan_NPWP or "", "zipcode2Npwp": row.zipcode_NPWP or "",
                "businessEntity": row.BUSINESS_ENTITY or "", "relMlci": row.RELATIONSHIP or "e3",
                "employeeNumber": row.NumberOfEmployee or "",
            })

    return jsonify({
        "data": data,
        "lookups": {
            "customerProfiles": [
                {"value": r.CUST_TYPE, "label": r.NAME} for r in db.session.execute(text(
                    "SELECT CUST_TYPE, NAME FROM MSTLESSEETYPE WITH(NOLOCK) WHERE LESSEE_TP = 'PT'"
                )).fetchall()
            ],
            "officeStatuses": [{"value": r.AddressStatus, "label": r.name} for r in db.session.execute(text("""
                SELECT AddressStatus, name FROM MSTADDRESSSTATUS WITH (NOLOCK) ORDER BY CASE
                    WHEN AddressStatus = 'PV' THEN 1 WHEN AddressStatus = 'FM' THEN 2
                    WHEN AddressStatus = 'CP' THEN 3 WHEN AddressStatus = 'RN' THEN 4
                    WHEN AddressStatus = 'OT' THEN 5 ELSE 6 END
            """)).fetchall()],
            "groups": [{"value": r.GrpCode, "label": r.GrpName} for r in db.session.execute(text("""
                SELECT GrpCode, GrpName FROM CLFGROUP WITH(NOLOCK) WHERE GrpCode IN ('001', '002') AND FLGDEL = '0'
                UNION SELECT GrpCode, GrpName FROM CLFGROUP WITH(NOLOCK) WHERE GrpCode NOT IN ('001', '002') AND FLGDEL = '0'
            """)).fetchall()],
            "relationshipWithCompany": [{"value": r.VALUE, "label": r.DESC_VALUE} for r in db.session.execute(text(
                "SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE = 'RELATIONSHIP_MLCI' ORDER BY DESC_VALUE"
            )).fetchall()],
            "businessEntities": _fetch_combo("BUSINESS_ENTITY"),
        },
    })

@cam_customer_bp.route("/corporate-detail", methods=["POST"])
@login_required
def save_corporate_detail():
    payload = request.get_json(silent=True) or {}
    editable = payload.get("editable")
    if editable != 1:
        return jsonify({
            "success": False,
            "message": "editable must be 1 — the editable=0 seed-only path from prev_next() wasn't ported (see module docstring).",
        }), 400

    apless = payload.get("apless", "")
    applno = payload.get("applno", "")
    fin_type = payload.get("finType", "")
    guarantor = payload.get("guarantor", "")
    new_car = payload.get("newCar", "")
    purpoffinc = payload.get("purpoffinc", "")
    cont_type = payload.get("contType", "")
    r_change = payload.get("restructuringChange", "")
    go_public = payload.get("goPublic", "")
    is_new = not apless

    d = {k: (payload.get(k) or "").strip() if isinstance(payload.get(k), str) else payload.get(k) for k in payload}

    errors = {}
    for field, message in CORPORATE_REQUIRED_FIELDS_MESSAGES:
        if not d.get(field):
            errors[field] = message

    if d.get("zipcode2") and len(d["zipcode2"]) != 5:
        errors["zipcode2"] = "Post Code must not empty or must be 5 digits"
    elif not d.get("zipcode2"):
        errors["zipcode2"] = "Post Code must not empty or must be 5 digits"

    tglbirth1 = _parse_ddmmyyyy(d.get("tglbirth", ""))
    if not tglbirth1 or tglbirth1 >= date.today():
        errors["tglbirth"] = "Establishment Date not valid"

    for f in CORPORATE_PHONE_FIELDS:
        v = d.get(f) or ""
        if len(v) > 18:
            errors[f] = f"{f} max 18 digit"

    npwp_digits = _strip_special(d.get("npwp") or "")
    if len(npwp_digits) < 15:
        errors["npwp"] = "NPWP must 15 digit"

    lessee_nm = d.get("lesseeNm") or ""
    address2 = d.get("address2") or ""
    lessee_nm_norm = _strip_special(lessee_nm)
    address2_norm = _strip_special(address2)

    if is_new:
        dup_name_address = db.session.execute(text("""
            SELECT 1 FROM CAFLESS WITH (NOLOCK)
            WHERE dbo.FuncRemovedSpecial(LESSEE_NM) = :n AND dbo.FuncRemovedSpecial(ADDRESS2) = :a
                AND LESSEE_TP = 'PT' AND APLESS <> :apless
        """), {"n": lessee_nm_norm, "a": address2_norm, "apless": apless}).fetchone()
        if dup_name_address:
            errors["lesseeNm"] = "Data Already exist"

        dup_name_dob = db.session.execute(text("""
            SELECT 1 FROM CAFLESS WITH (NOLOCK)
            WHERE dbo.FuncRemovedSpecial(LESSEE_NM) = :n AND TGLBIRTH = :dob AND APLESS <> :apless
        """), {"n": lessee_nm_norm, "dob": tglbirth1, "apless": apless}).fetchone()
        if dup_name_dob:
            errors["lesseeNm"] = "Data Already exist"

        dup_npwp = db.session.execute(text("""
            SELECT 1 FROM CAFLESS WITH (NOLOCK)
            WHERE dbo.FuncRemovedSpecial(ISNULL(NPWP, '')) = :npwp AND APLESS <> :apless
        """), {"npwp": npwp_digits, "apless": apless}).fetchone()
        if dup_npwp:
            errors["npwp"] = "Data Already exist"

    if errors:
        return jsonify({"success": False, "errors": errors}), 422

    watchlist_result = _check_watchlist_blacklist(
        lessee_nm, address2_norm, "", "", "", "PT", apless, npwp_digits,
    )
    if watchlist_result["status"] == "blacklist":
        return jsonify({"success": False, "message": watchlist_result.get("message", "Blacklisted"), "blocked": True}), 403

    try:
        if is_new:
            apless = _generate_apless()
            if not apless:
                db.session.rollback()
                return jsonify({"success": False, "message": "Cannot create CAM, please call helpdesk"}), 500

        phone1 = _format_phone_db(d.get("phone1"))
        mobile1 = _format_phone_db(d.get("mobilePhone1"))
        mobile2 = _format_phone_db(d.get("mobilePhone2"))
        mobile3 = _format_phone_db(d.get("mobilePhone3"))
        other1 = _format_phone_db(d.get("otherPhone1"))
        other2 = _format_phone_db(d.get("otherPhone2"))
        emergency_phone = _format_phone_db(d.get("emergencyPhone"))
        ocu_type = None if d.get("lesseeCat") == "FD" else (d.get("occupation") or None)

        if is_new:
            db.session.execute(text("""
                INSERT INTO CAFLESS (APLESS, LESSEE_NM, LESSEE_TP, ADDRESS1, ADDRESS2, CITY2, Address_Status,
                    ZipCode2, PHONE1, Mobile_phone1, Mobile_phone2, Mobile_phone3, EMAIL1, NPWP, Occupation,
                    Area_CD, Fax1, Send_SMS, Contact, GrpCode, PLACEBIRTH, TGLBIRTH, Cust_Type, INDUS_CODE,
                    Lessee_Cat, LOB, OTHER_PHONE1, OTHER_PHONE2, OTHER_PHONENOTES1, OTHER_PHONENOTES2)
                VALUES (:apless, :lessee_nm, 'PT', :address1, :address2, :city2, :address_status, :zipcode2,
                    :phone1, :m1, :m2, :m3, :email1, :npwp, :occupation, :area_cd, :fax1, '1', :contact,
                    :grpcode, :placebirth, :tglbirth, :cust_type, :indus_code, :lessee_cat, :lob, :other1,
                    :other2, :opn1, :opn2)
            """), {
                "apless": apless, "lessee_nm": lessee_nm, "address1": d.get("address1"), "address2": address2,
                "city2": d.get("city2"), "address_status": d.get("addressStatus"), "zipcode2": d.get("zipcode2"),
                "phone1": phone1, "m1": mobile1, "m2": mobile2, "m3": mobile3, "email1": d.get("email1"),
                "npwp": npwp_digits, "occupation": d.get("occupation"), "area_cd": d.get("areaCd"),
                "fax1": d.get("fax1"), "contact": d.get("contact"), "grpcode": d.get("grpcode"),
                "placebirth": d.get("placebirth"), "tglbirth": tglbirth1, "cust_type": d.get("custType"),
                "indus_code": d.get("indusCode"), "lessee_cat": d.get("lesseeCat"), "lob": d.get("lob"),
                "other1": other1, "other2": other2, "opn1": d.get("otherPhoneNotes1"),
                "opn2": d.get("otherPhoneNotes2"),
            })
            db.session.execute(text("""
                INSERT INTO CAFLESS_DETAIL_ADDRESS (APLESS, KECAMATAN, KELURAHAN, RT, RW, EMERGENCY_NAME,
                    EMERGENCY_ADDRESS, EMERGENCY_PHONE, EMERGENCY_RELATION, SIUP_NO, DOMICILE_NO, Address_NPWP,
                    Area_CD_NPWP, Kecamatan_NPWP, Kelurahan_NPWP, Zipcode_NPWP)
                VALUES (:apless, :kec, :kel, :rt, :rw, :en, :ea, :ep, :er, :siup, :domicile, :an, :acn, :kn,
                    :keln, :zn)
            """), {
                "apless": apless, "kec": d.get("kecamatan1"), "kel": d.get("kelurahan1"), "rt": d.get("rt1"),
                "rw": d.get("rw1"), "en": d.get("emergencyName"), "ea": d.get("emergencyAddress"),
                "ep": emergency_phone, "er": d.get("emergencyRelation"), "siup": d.get("siup"),
                "domicile": d.get("domicile"), "an": d.get("addrNpwp"), "acn": d.get("areaCdNpwp"),
                "kn": d.get("kecamatanNpwp"), "keln": d.get("kelurahanNpwp"), "zn": d.get("zipcode2Npwp"),
            })
            db.session.execute(text("""
                INSERT INTO CAFLESS_DETAIL (APLESS, BUSINESS_TYPE, RELATIONSHIP, Fullname_Without_Title,
                    GO_PUBLIC, BUSINESS_ENTITY, NumberOfEmployee)
                VALUES (:apless, :ocu_type, 'e3', :id_card_name, :go_public, :b_entity, :employee_number)
            """), {
                "apless": apless, "ocu_type": ocu_type, "id_card_name": d.get("idCardName"),
                "go_public": go_public, "b_entity": d.get("businessEntity"),
                "employee_number": d.get("employeeNumber"),
            })
        else:
            bpkb_row = db.session.execute(text(
                "SELECT BPKB_AN FROM CAFEQUIP WITH (NOLOCK) WHERE APPL_NO = :applno"
            ), {"applno": applno}).fetchone()
            if bpkb_row and bpkb_row.BPKB_AN:
                old_name_row = db.session.execute(text(
                    "SELECT LESSEE_NM FROM CAFLESS WITH (NOLOCK) WHERE APLESS = :apless"
                ), {"apless": apless}).fetchone()
                if old_name_row and old_name_row.LESSEE_NM != lessee_nm:
                    db.session.execute(text(
                        "UPDATE CAFEQUIP SET BPKB_AN = :lessee_nm WHERE APPL_NO = :applno"
                    ), {"lessee_nm": lessee_nm, "applno": applno})

            db.session.execute(text("""
                UPDATE CAFLESS SET LESSEE_NM = :lessee_nm, Lessee_Cat = :lessee_cat, ADDRESS1 = :address1,
                    ADDRESS2 = :address2, CITY2 = :city2, Address_Status = :address_status,
                    ZipCode2 = :zipcode2, PHONE1 = :phone1, Mobile_phone1 = :m1, Mobile_phone2 = :m2,
                    Mobile_phone3 = :m3, EMAIL1 = :email1, NPWP = :npwp, Occupation = :occupation,
                    Area_CD = :area_cd, Fax1 = :fax1, Send_SMS = '1', Contact = :contact, GrpCode = :grpcode,
                    TGLBIRTH = :tglbirth, Cust_Type = :cust_type, INDUS_CODE = :indus_code, LOB = :lob,
                    OTHER_PHONE1 = :other1, OTHER_PHONE2 = :other2, OTHER_PHONENOTES1 = :opn1,
                    OTHER_PHONENOTES2 = :opn2, LESSEE_TP = 'PT', PLACEBIRTH = :placebirth
                WHERE APLESS = :apless
            """), {
                "lessee_nm": lessee_nm, "lessee_cat": d.get("lesseeCat"), "address1": d.get("address1"),
                "address2": address2, "city2": d.get("city2"), "address_status": d.get("addressStatus"),
                "zipcode2": d.get("zipcode2"), "phone1": phone1, "m1": mobile1, "m2": mobile2, "m3": mobile3,
                "email1": d.get("email1"), "npwp": npwp_digits, "occupation": d.get("occupation"),
                "area_cd": d.get("areaCd"), "fax1": d.get("fax1"), "contact": d.get("contact"),
                "grpcode": d.get("grpcode"), "tglbirth": tglbirth1, "cust_type": d.get("custType"),
                "indus_code": d.get("indusCode"), "lob": d.get("lob"), "other1": other1, "other2": other2,
                "opn1": d.get("otherPhoneNotes1"), "opn2": d.get("otherPhoneNotes2"),
                "placebirth": d.get("placebirth"), "apless": apless,
            })

            exists_addr = db.session.execute(text(
                "SELECT 1 FROM CAFLESS_DETAIL_ADDRESS WITH(NOLOCK) WHERE APLESS = :apless"
            ), {"apless": apless}).fetchone()
            addr_params = {
                "en": d.get("emergencyName"), "ea": d.get("emergencyAddress"), "ep": emergency_phone,
                "er": d.get("emergencyRelation"), "kec": d.get("kecamatan1"), "kel": d.get("kelurahan1"),
                "rt": d.get("rt1"), "rw": d.get("rw1"), "siup": d.get("siup"), "domicile": d.get("domicile"),
                "an": d.get("addrNpwp"), "acn": d.get("areaCdNpwp"), "kn": d.get("kecamatanNpwp"),
                "keln": d.get("kelurahanNpwp"), "zn": d.get("zipcode2Npwp"), "apless": apless,
            }
            if exists_addr:
                db.session.execute(text("""
                    UPDATE CAFLESS_DETAIL_ADDRESS SET EMERGENCY_NAME = :en, EMERGENCY_ADDRESS = :ea,
                        EMERGENCY_PHONE = :ep, EMERGENCY_RELATION = :er, KECAMATAN = :kec, KELURAHAN = :kel,
                        RT = :rt, RW = :rw, SIUP_NO = :siup, DOMICILE_NO = :domicile, Address_NPWP = :an,
                        Area_CD_NPWP = :acn, Kecamatan_NPWP = :kn, Kelurahan_NPWP = :keln, Zipcode_NPWP = :zn
                    WHERE APLESS = :apless
                """), addr_params)
            else:
                db.session.execute(text("""
                    INSERT INTO CAFLESS_DETAIL_ADDRESS (APLESS, KECAMATAN, KELURAHAN, RT, RW, EMERGENCY_NAME,
                        EMERGENCY_ADDRESS, EMERGENCY_PHONE, EMERGENCY_RELATION, SIUP_NO, DOMICILE_NO,
                        Address_NPWP, Area_CD_NPWP, Kecamatan_NPWP, Kelurahan_NPWP, Zipcode_NPWP)
                    VALUES (:apless, :kec, :kel, :rt, :rw, :en, :ea, :ep, :er, :siup, :domicile, :an, :acn,
                        :kn, :keln, :zn)
                """), addr_params)

            exists_detail = db.session.execute(text(
                "SELECT 1 FROM CAFLESS_DETAIL WITH(NOLOCK) WHERE APLESS = :apless"
            ), {"apless": apless}).fetchone()
            detail_params = {
                "apless": apless, "ocu_type": ocu_type, "id_card_name": d.get("idCardName"),
                "go_public": go_public, "b_entity": d.get("businessEntity"),
                "employee_number": d.get("employeeNumber"),
            }
            if exists_detail:
                db.session.execute(text("""
                    UPDATE CAFLESS_DETAIL SET BUSINESS_TYPE = :ocu_type, RELATIONSHIP = 'e3',
                        Fullname_Without_Title = :id_card_name, GO_PUBLIC = :go_public,
                        BUSINESS_ENTITY = :b_entity, NumberOfEmployee = :employee_number
                    WHERE APLESS = :apless
                """), detail_params)
            else:
                db.session.execute(text("""
                    INSERT INTO CAFLESS_DETAIL (APLESS, BUSINESS_TYPE, Fullname_Without_Title, RELATIONSHIP,
                        GO_PUBLIC, BUSINESS_ENTITY, NumberOfEmployee)
                    VALUES (:apless, :ocu_type, :id_card_name, 'e3', :go_public, :b_entity, :employee_number)
                """), detail_params)

        if not applno:
            has_guarantor = 0 if guarantor == "1" else (1 if guarantor == "2" else None)
            applno = _generate_applno(emp_id=_session_str("emp_id"))
            if not applno:
                db.session.rollback()
                return jsonify({"success": False, "message": "Cannot create CAM, please call helpdesk"}), 500
            _seed_new_application(
                applno, apless, _session_str("branchcode"), _session_str("emp_id"), fin_type,
                has_guarantor, purpoffinc, cont_type, new_car,
            )

        if cont_type == "RS1":
            exists_restr = db.session.execute(text(
                "SELECT 1 FROM CAFCONT_RESTRUCTURING WITH(NOLOCK) WHERE APPL_NO = :applno"
            ), {"applno": applno}).fetchone()
            if exists_restr:
                db.session.execute(text(
                    "UPDATE CAFCONT_RESTRUCTURING SET RESTRUCTURING_CHANGE = :rc WHERE APPL_NO = :applno"
                ), {"rc": r_change, "applno": applno})
            else:
                db.session.execute(text(
                    "INSERT INTO CAFCONT_RESTRUCTURING (APPL_NO, RESTRUCTURING_CHANGE) VALUES (:applno, :rc)"
                ), {"applno": applno, "rc": r_change})
        else:
            db.session.execute(text(
                "DELETE FROM CAFCONT_RESTRUCTURING WHERE APPL_NO = :applno"
            ), {"applno": applno})

        business_type = ocu_type or ""
        if len(business_type) >= 4 and business_type[3:4] != "H":
            db.session.execute(text(
                "UPDATE Kuisioner_EDD SET EDD_Customer = NULL WHERE APPL_NO = :applno"
            ), {"applno": applno})

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("corp_detail save failed")
        return jsonify({"success": False, "message": "Failed"}), 500

    response = {"success": True, "message": "Successful", "apless": apless, "applno": applno}
    if watchlist_result["status"] == "watchlist":
        response["watchlistWarning"] = watchlist_result.get("message")
    return jsonify(response)

def _fetch_address(apless: str) -> dict:
    row = db.session.execute(text("""
        SELECT ADDRESS4, CITY4, PHONE4, ZipCode4, Fax4,
               ADDRESS3, CITY3, PHONE3, ZipCode3, Fax3,
               ADDRESS5, CITY5, PHONE5, ZipCode5, Fax5,
               ADDRESS1, CITY1, PHONE2, ZipCode1, Fax1
        FROM CAFLESS WITH (NOLOCK)
        WHERE APLESS = :apless
    """), {"apless": apless}).fetchone()

    if row is None:
        return {}

    return {
        "address4": row.ADDRESS4 or "",
        "city4": row.CITY4 or "",
        "phone4": row.PHONE4 or "",
        "zipcode4": row.ZipCode4 or "",
        "fax4": row.Fax4 or "",
        "address3": row.ADDRESS3 or "",
        "city3": row.CITY3 or "",
        "phone3": row.PHONE3 or "",
        "zipcode3": row.ZipCode3 or "",
        "fax3": row.Fax3 or "",
        "address5": row.ADDRESS5 or "",
        "city5": row.CITY5 or "",
        "phone5": row.PHONE5 or "",
        "zipcode5": row.ZipCode5 or "",
        "fax5": row.Fax5 or "",
        "address1": row.ADDRESS1 or "",
        "city1": row.CITY1 or "",
        "phone2": row.PHONE2 or "",
        "zipcode1": row.ZipCode1 or "",
        "fax1": row.Fax1 or "",
    }

@cam_customer_bp.route("/address", methods=["GET"])
@login_required
def get_address():
    apless = request.args.get("apless", "")
    if not apless:
        return jsonify({"message": "apless is required"}), 400

    data = _fetch_address(apless)
    return jsonify(data)

@cam_customer_bp.route("/address", methods=["POST"])
@login_required
def save_address():
    body = request.get_json(silent=True) or {}
    apless = body.get("apless", "")
    applno = body.get("applno", "")

    if not apless:
        return jsonify({"message": "apless is required"}), 400

    errors = {}
    for field, message in (
        ("zipcode3", "Post Code Correspondence not valid"),
        ("zipcode4", "Post Code additional 1 not valid"),
        ("zipcode5", "Post Code additional 2 not valid"),
    ):
        value = (body.get(field) or "").strip()
        if value and len(value) != 5:
            errors[field] = message

    if errors:
        return jsonify({"success": False, "errors": errors}), 200

    def clean_text(value):
        return (value or "").replace("'", "`")

    def clean_digits(value):
        return "".join(ch for ch in (value or "") if ch.isdigit())

    params = {
        "address4": clean_text(body.get("address4")), "city4": clean_text(body.get("city4")),
        "phone4": clean_digits(body.get("phone4")), "zipcode4": clean_digits(body.get("zipcode4")),
        "fax4": clean_digits(body.get("fax4")),
        "address3": clean_text(body.get("address3")), "city3": clean_text(body.get("city3")),
        "phone3": clean_digits(body.get("phone3")), "zipcode3": clean_digits(body.get("zipcode3")),
        "fax3": clean_digits(body.get("fax3")),
        "address5": clean_text(body.get("address5")), "city5": clean_text(body.get("city5")),
        "phone5": clean_digits(body.get("phone5")), "zipcode5": clean_digits(body.get("zipcode5")),
        "fax5": clean_digits(body.get("fax5")),
        "apless": apless,
    }

    try:
        db.session.execute(text("""
            UPDATE CAFLESS
            SET ADDRESS4 = :address4, CITY4 = :city4, PHONE4 = :phone4, ZipCode4 = :zipcode4, Fax4 = :fax4,
                ADDRESS3 = :address3, CITY3 = :city3, PHONE3 = :phone3, ZipCode3 = :zipcode3, Fax3 = :fax3,
                ADDRESS5 = :address5, CITY5 = :city5, PHONE5 = :phone5, ZipCode5 = :zipcode5, Fax5 = :fax5
            WHERE APLESS = :apless
        """), params)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("cust_address save failed")
        return jsonify({"success": False, "message": "Failed"}), 500

    return jsonify({"success": True, "apless": apless, "applno": applno})

def _currencies():
    rows = db.session.execute(text("SELECT CURR_CODE, DESCRIP FROM UMFCURR WITH(NOLOCK)")).fetchall()
    return [{"value": r.CURR_CODE, "label": r.DESCRIP} for r in rows]

def _cam_create_year(apless: str, applno: str) -> str:
    row = db.session.execute(text("""
        SELECT CONVERT(varchar(4), YEAR(CREATE_DATE)) AS y
        FROM CAFCONT WITH (NOLOCK) WHERE APLESS = :apless AND APPL_NO = :applno
    """), {"apless": apless, "applno": applno}).fetchone()
    return row.y if row and row.y else str(datetime.utcnow().year)

@cam_customer_bp.route("/individual", methods=["GET"])
@login_required
def get_individual():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")

    cafless = db.session.execute(text(
        "SELECT MARITAL, FS_Curr FROM CAFLESS WITH (NOLOCK) WHERE APLESS = :apless"
    ), {"apless": apless}).fetchone()
    marital = (cafless.MARITAL if cafless else "") or ""
    currency = (cafless.FS_Curr if cafless else "") or "IDR"

    create_year = _cam_create_year(apless, applno)
    period_rows = db.session.execute(text("""
        SELECT PERIOD FROM CAFFS WITH (NOLOCK)
        WHERE APLESS = :apless AND FS_CODE = 'I' AND PERIOD <= :year
        GROUP BY PERIOD ORDER BY PERIOD DESC
    """), {"apless": apless, "year": create_year}).fetchall()
    period_options = [r.PERIOD for r in period_rows]
    selected_period = period_options[0] if period_options else ""

    def fs_items(like_pattern: str, exclude_abc: bool = False):
        sql = "SELECT FS_CODE, FS_DESC FROM MSTFS WITH (NOLOCK) WHERE FS_CODE LIKE :p"
        if exclude_abc:
            sql += " AND FS_CODE NOT LIKE '%A%' AND FS_CODE NOT LIKE '%B%' AND FS_CODE NOT LIKE '%C%'"
        sql += " ORDER BY FS_CODE"
        rows = db.session.execute(text(sql), {"p": like_pattern}).fetchall()
        return [{"code": r.FS_CODE, "label": r.FS_DESC} for r in rows]

    income_main = fs_items("3101%", exclude_abc=True)
    income_deduction = fs_items("3102%")
    income_other = fs_items("%5001%")

    income_values = {}
    if selected_period:
        rows = db.session.execute(text("""
            SELECT ITEM_CODE, AMOUNT FROM CAFFS WITH (NOLOCK)
            WHERE APLESS = :apless AND FS_CODE = 'I' AND PERIOD = :period
        """), {"apless": apless, "period": selected_period}).fetchall()
        income_values = {r.ITEM_CODE: str(r.AMOUNT) for r in rows}

    def cafla_rows(la_code: str):
        if not selected_period:
            return []
        rows = db.session.execute(text("""
            SELECT ID_CAFLA, [DESC], NOTES, AMOUNT FROM CAFLA WITH (NOLOCK)
            WHERE APLESS = :apless AND PERIOD = :period AND LA_CODE = :la_code
        """), {"apless": apless, "period": selected_period, "la_code": la_code}).fetchall()
        return rows

    liabilities = [
        {"id": r.ID_CAFLA, "category": r.NOTES or "", "description": r.DESC or "", "amount": str(r.AMOUNT)}
        for r in cafla_rows("L")
    ]
    assets = [
        {"id": r.ID_CAFLA, "description": r.DESC or "", "amount": str(r.AMOUNT), "notes": r.NOTES or ""}
        for r in cafla_rows("A")
    ]

    return jsonify({
        "currency": currency,
        "maritalStatus": marital,
        "currencies": _currencies(),
        "periodOptions": period_options,
        "selectedPeriod": selected_period,
        "incomeMain": income_main,
        "incomeDeduction": income_deduction,
        "incomeOther": income_other,
        "incomeValues": income_values,
        "liabilities": liabilities,
        "assets": assets,
    })

@cam_customer_bp.route("/individual", methods=["POST"])
@login_required
def save_individual():
    body = request.get_json(silent=True) or {}
    apless = body.get("apless", "")
    applno = body.get("applno", "")
    period = (body.get("period") or "").strip()
    is_new = bool(body.get("isNewPeriod"))
    currency = body.get("currency") or "IDR"
    income_values = body.get("incomeValues") or {}
    liabilities = body.get("liabilities") or []
    assets = body.get("assets") or []

    if not period or len(period) != 4 or not period.isdigit():
        return jsonify({"success": False, "message": "Period 1 not valid"}), 200
    if int(period) > datetime.utcnow().year:
        return jsonify({"success": False, "message": "Period 1 not valid"}), 200

    now = datetime.utcnow()

    try:
        db.session.execute(text(
            "UPDATE CAFLESS SET FS_Curr = :curr WHERE APLESS = :apless"
        ), {"curr": currency, "apless": apless})

        if is_new:
            existing = db.session.execute(text("""
                SELECT 1 FROM CAFFS WITH (NOLOCK) WHERE APLESS = :apless AND PERIOD = :period AND FS_CODE = 'I'
            """), {"apless": apless, "period": period}).fetchone()
            if existing:
                return jsonify({"success": False, "message": "Data (Period 1) exist"}), 200

            for code, amount in income_values.items():
                db.session.execute(text("""
                    INSERT INTO CAFFS (FS_CODE, PERIOD, ITEM_CODE, AMOUNT, APLESS, INPUT_DT)
                    VALUES ('I', :period, :code, :amount, :apless, :now)
                """), {"period": period, "code": code, "amount": amount or 0, "apless": apless, "now": now})

            for row in liabilities:
                if not (row.get("category") or row.get("description") or row.get("amount")):
                    continue
                db.session.execute(text("""
                    INSERT INTO CAFLA (LA_CODE, PERIOD, [DESC], NOTES, AMOUNT, APLESS, INPUT_DT)
                    VALUES ('L', :period, :desc, :notes, :amount, :apless, :now)
                """), {"period": period, "desc": row.get("description", ""), "notes": row.get("category", ""),
                       "amount": row.get("amount") or 0, "apless": apless, "now": now})

            for row in assets:
                if not (row.get("description") or row.get("amount") or row.get("notes")):
                    continue
                db.session.execute(text("""
                    INSERT INTO CAFLA (LA_CODE, PERIOD, [DESC], NOTES, AMOUNT, APLESS, INPUT_DT)
                    VALUES ('A', :period, :desc, :notes, :amount, :apless, :now)
                """), {"period": period, "desc": row.get("description", ""), "notes": row.get("notes", ""),
                       "amount": row.get("amount") or 0, "apless": apless, "now": now})
        else:
            db.session.execute(text(
                "DELETE FROM CAFFS WHERE FS_CODE = 'I' AND APLESS = :apless AND PERIOD = :period"
            ), {"apless": apless, "period": period})
            for code, amount in income_values.items():
                db.session.execute(text("""
                    INSERT INTO CAFFS (FS_CODE, PERIOD, ITEM_CODE, AMOUNT, APLESS, INPUT_DT)
                    VALUES ('I', :period, :code, :amount, :apless, :now)
                """), {"period": period, "code": code, "amount": amount or 0, "apless": apless, "now": now})

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("individual financial info save failed")
        return jsonify({"success": False, "message": "Failed"}), 500

    return jsonify({"success": True, "apless": apless, "applno": applno})

@cam_customer_bp.route("/individual", methods=["DELETE"])
@login_required
def delete_individual():
    apless = request.args.get("apless", "")
    period = request.args.get("period", "")
    if not apless or not period:
        return jsonify({"message": "apless and period are required"}), 400

    try:
        db.session.execute(text(
            "DELETE FROM CAFFS WHERE PERIOD = :period AND APLESS = :apless AND FS_CODE = 'I'"
        ), {"period": period, "apless": apless})
        db.session.execute(text(
            "DELETE FROM CAFLA WHERE PERIOD = :period AND APLESS = :apless"
        ), {"period": period, "apless": apless})
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("individual financial info delete failed")
        return jsonify({"success": False, "message": "Failed"}), 500

    return jsonify({"success": True})

def _balance_sheet_groups():
    def build(where_clause: str, params: dict, section: str):
        prefixes = db.session.execute(text(f"""
            SELECT SUBSTRING(FS_CODE, 1, 4) AS prefix FROM MSTFS WITH (NOLOCK)
            WHERE {where_clause} GROUP BY SUBSTRING(FS_CODE, 1, 4)
        """), params).fetchall()

        groups = []
        for p in prefixes:
            prefix = p.prefix
            rows = db.session.execute(text(f"""
                SELECT FS_CODE, FS_DESC FROM MSTFS WITH (NOLOCK)
                WHERE {where_clause} AND FS_CODE LIKE :prefix_like ORDER BY FS_CODE
            """), {**params, "prefix_like": f"{prefix}%"}).fetchall()

            header = None
            items = []
            for r in rows:
                if r.FS_CODE[4:6] == "00":
                    header = r.FS_DESC
                else:
                    items.append({
                        "code": r.FS_CODE,
                        "label": r.FS_DESC,
                        "allowNegative": r.FS_CODE == "110206",
                    })
            if items:
                groups.append({"section": section, "header": header or prefix, "items": items})
        return groups

    asset_groups = build("FS_CODE < '120000'", {}, "asset")
    liability_groups = build("FS_CODE >= '12000' AND FS_CODE < '21000'", {}, "liability_equity")
    return asset_groups + liability_groups

@cam_customer_bp.route("/corporate", methods=["GET"])
@login_required
def get_corporate():
    apless = request.args.get("apless", "")

    cafless = db.session.execute(text(
        "SELECT FS_Curr FROM CAFLESS WITH (NOLOCK) WHERE APLESS = :apless"
    ), {"apless": apless}).fetchone()
    currency = (cafless.FS_Curr if cafless else "") or "IDR"

    period_rows = db.session.execute(text("""
        SELECT TOP 2 PERIOD FROM CAFFS WITH (NOLOCK)
        WHERE APLESS = :apless AND FS_CODE = 'B'
        GROUP BY PERIOD ORDER BY PERIOD DESC
    """), {"apless": apless}).fetchall()
    period_options = [r.PERIOD for r in period_rows]
    period1 = period_options[0] if len(period_options) > 0 else ""
    period2 = period_options[1] if len(period_options) > 1 else ""

    groups = _balance_sheet_groups()

    def values_for(period: str):
        if not period:
            return {}
        rows = db.session.execute(text("""
            SELECT ITEM_CODE, AMOUNT FROM CAFFS WITH (NOLOCK)
            WHERE APLESS = :apless AND FS_CODE = 'B' AND PERIOD = :period
        """), {"apless": apless, "period": period}).fetchall()
        return {r.ITEM_CODE: str(r.AMOUNT) for r in rows}

    return jsonify({
        "currency": currency,
        "currencies": _currencies(),
        "periodOptions": period_options,
        "period1": period1,
        "period2": period2,
        "groups": groups,
        "values": {"period1": values_for(period1), "period2": values_for(period2)},
    })

@cam_customer_bp.route("/corporate", methods=["POST"])
@login_required
def save_corporate():
    body = request.get_json(silent=True) or {}
    apless = body.get("apless", "")
    applno = body.get("applno", "")
    currency = body.get("currency") or "IDR"
    p1 = body.get("period1") or {}
    p2 = body.get("period2") or {}

    def validate(p, label):
        period = (p.get("period") or "").strip()
        if not period or len(period) != 4 or not period.isdigit():
            return f"{label} not valid"
        if int(period) > datetime.utcnow().year:
            return f"{label} not valid"
        return None

    err1 = validate(p1, "Period 1 (Balance Sheet)")
    err2 = validate(p2, "Period 2 (Balance Sheet)")
    if err1:
        return jsonify({"success": False, "message": err1}), 200
    if err2:
        return jsonify({"success": False, "message": err2}), 200
    if p1.get("period") == p2.get("period"):
        return jsonify({"success": False, "message": "Data Period 1 and 2 must not be the same"}), 200

    now = datetime.utcnow()

    def upsert_period(p):
        period = p.get("period")
        values = p.get("values") or {}
        is_new = bool(p.get("isNew"))

        if is_new:
            existing = db.session.execute(text("""
                SELECT 1 FROM CAFFS WITH (NOLOCK) WHERE APLESS = :apless AND PERIOD = :period AND FS_CODE = 'B'
            """), {"apless": apless, "period": period}).fetchone()
            if existing:
                return f"Data Period {period} Exist"
            for code, amount in values.items():
                db.session.execute(text("""
                    INSERT INTO CAFFS (FS_CODE, PERIOD, ITEM_CODE, AMOUNT, APLESS, INPUT_DT)
                    VALUES ('B', :period, :code, :amount, :apless, :now)
                """), {"period": period, "code": code, "amount": amount or 0, "apless": apless, "now": now})
        else:
            for code, amount in values.items():
                db.session.execute(text("""
                    UPDATE CAFFS SET AMOUNT = :amount, INPUT_DT = :now
                    WHERE ITEM_CODE = :code AND FS_CODE = 'B' AND APLESS = :apless AND PERIOD = :period
                """), {"amount": amount or 0, "now": now, "code": code, "apless": apless, "period": period})
        return None

    try:
        db.session.execute(text(
            "UPDATE CAFLESS SET FS_Curr = :curr WHERE APLESS = :apless"
        ), {"curr": currency, "apless": apless})

        for p in (p1, p2):
            if not p.get("period"):
                continue
            err = upsert_period(p)
            if err:
                db.session.rollback()
                return jsonify({"success": False, "message": err}), 200

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("corporate balance sheet save failed")
        return jsonify({"success": False, "message": "Failed"}), 500

    return jsonify({"success": True, "apless": apless, "applno": applno})

@cam_customer_bp.route("/corporate", methods=["DELETE"])
@login_required
def delete_corporate():
    apless = request.args.get("apless", "")
    period = request.args.get("period", "")
    if not apless or not period:
        return jsonify({"message": "apless and period are required"}), 400

    try:
        db.session.execute(text(
            "DELETE FROM CAFFS WHERE PERIOD = :period AND APLESS = :apless AND FS_CODE = 'B'"
        ), {"period": period, "apless": apless})
        db.session.execute(text(
            "DELETE FROM CAFLA WHERE PERIOD = :period AND APLESS = :apless"
        ), {"period": period, "apless": apless})
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("corporate balance sheet delete failed")
        return jsonify({"success": False, "message": "Failed"}), 500

    return jsonify({"success": True})