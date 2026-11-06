import datetime
import mimetypes
import os
import re
import uuid

from flask import Blueprint, jsonify, request, current_app, session
from werkzeug.utils import secure_filename
from botocore.exceptions import BotoCoreError, ClientError
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text
from app.utils.helpers.aws_helpers import (
    _aws_presign, _aws_upload, _aws_delete, _validate_file, _aws_object_exists,
)
from app.utils.helpers.access_helpers import user_right

BUCKET_CAM = current_app.config.get("BUCKET_CAM") if current_app else None

DEALER_MENU_URL = "module_other/supplier.php"
_DEALER_MENU_ID_CACHE: str = ""
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "doc", "docx"}
DEALER_MAX_FILE_MB = 2

DEALER_DOC_TYPES: dict = {
    "dealer-ktp":   "KTP Contact Person",
    "dealer-siup":  "SIUP / NIB",
    "dealer-npwp":  "NPWP",
    "dealer-akta":  "Akta Pendirian",
    "dealer-bpkb":  "Contoh BPKB",
    "dealer-bank":  "Buku Tabungan / Rekening Koran",
    "dealer-other": "Lainnya",
}

LEGACY_TO_NEW_DOC_TYPE = {
    "KTP":              "dealer-ktp",
    "SIUP":             "dealer-siup",
    "TDP":              "dealer-siup",
    "NPWP":             "dealer-npwp",
    "Akta1":            "dealer-akta",
    "Akta20":           "dealer-akta",
    "BukuTabungan":     "dealer-bank",
    "BPKB":             "dealer-bpkb",
    "KID":              "dealer-other",
    "SK":               "dealer-other",
    "SuratKuasa":       "dealer-other",
    "SuratPengukuhan":  "dealer-other",
    "SuratPernyataan":  "dealer-other",
    "InternalMemo":     "dealer-other",
    "UploadLainnya":    "dealer-other",
}

NEW_TO_LEGACY_DOC_TYPE = {
    "dealer-ktp":   "KTP",
    "dealer-siup":  "SIUP",
    "dealer-npwp":  "NPWP",
    "dealer-akta":  "Akta1",
    "dealer-bpkb":  "BPKB",
    "dealer-bank":  "BukuTabungan",
    "dealer-other": "UploadLainnya",
}

def _to_canonical_doc_type(raw: str) -> str:
    t = (raw or "").strip()
    if t in DEALER_DOC_TYPES:
        return t
    return LEGACY_TO_NEW_DOC_TYPE.get(t, "dealer-other")

def _to_legacy_doc_type(canonical: str) -> str:
    return NEW_TO_LEGACY_DOC_TYPE.get(canonical, "UploadLainnya")

dealer_bp = Blueprint("dealer", __name__, url_prefix="/MasterData")

def _fd(dt, fmt="%d-%m-%Y") -> str:
    if dt is None:
        return ""
    try:
        return dt.strftime(fmt)
    except Exception:
        return str(dt)

def _bit(value, default: str = "0") -> str:
    if value is None:
        return default
    if isinstance(value, bool):
        return "1" if value else "0"
    return "1" if str(value).strip().lower() in ("1", "true", "y", "yes") else "0"

def _num(value, default: str = "") -> str:
    if value is None:
        return default
    try:
        return f"{value:g}"
    except (TypeError, ValueError):
        return str(value)

def _parse_date(s: str):
    if not s:
        return None
    m = re.match(r"^(\d{2})-(\d{2})-(\d{4})$", str(s).strip())
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None

def _uname(emp_id) -> str:
    if not emp_id:
        return ""
    row = db.session.execute(
        text("SELECT USERNAME FROM APP_USRMST WITH(NOLOCK) WHERE EMPLOYEE_ID=:e"),
        {"e": emp_id},
    ).first()
    return row[0] if row else ""

def _discard_keys(keys) -> None:
    for k in keys:
        try:
            _aws_delete(k)
        except (BotoCoreError, ClientError):
            current_app.logger.exception("Orphan cleanup failed for %s", k)

def _dealer_menu_id() -> str:
    cfg = (current_app.config.get("DEALER_MENU_ID") or "").strip()
    if cfg:
        return cfg

    global _DEALER_MENU_ID_CACHE
    if _DEALER_MENU_ID_CACHE:
        return _DEALER_MENU_ID_CACHE

    row = db.session.execute(text("""
        SELECT TOP 1 MENU_ID
        FROM   APP_CAMMNLST WITH(NOLOCK)
        WHERE  LTRIM(RTRIM(URL)) = :url
        ORDER  BY MENU_ID
    """), {"url": DEALER_MENU_URL}).first()

    if row and row[0]:
        _DEALER_MENU_ID_CACHE = str(row[0]).strip()
    else:
        current_app.logger.error(
            "No APP_CAMMNLST row for URL=%r - dealer rights cannot be checked",
            DEALER_MENU_URL,
        )
    return _DEALER_MENU_ID_CACHE

def _dealer_akses() -> str:
    return user_right(session.get("accesslevel", ""), _dealer_menu_id())

def _require_dealer_write(action: str):
    akses = _dealer_akses()
    if akses == "":
        current_app.logger.warning(
            "No APP_CAMMNACC row for menu_id=%r accesslevel=%r",
            _dealer_menu_id(), session.get("accesslevel"),
        )
    if akses != "9":
        return jsonify({
            "success": False,
            "message": f"You do not have permission to {action} files.",
        }), 403
    return None

@dealer_bp.route("/dealer")
@login_required
def get_dealer():
    page       = request.args.get("page",       1,  type=int)
    limit      = request.args.get("limit",      25, type=int)
    search_val = request.args.get("search_val", "").strip()
    search_by  = request.args.get("search_by",  "").strip()
    akses      = session.get("akses", "9")

    try:
        params: dict = {}

        if search_val:
            if search_by == "1":
                where  = "a.SUPP = :exact_val AND a.flgdel IS NULL"
                params = {"exact_val": search_val}
            elif search_by == "2":
                where  = "a.[NAME] LIKE :like_val AND a.flgdel IS NULL"
                params = {"like_val": f"%{search_val}%"}
            elif search_by == "3":
                where  = "a.NICKNAME LIKE :like_val AND a.flgdel IS NULL"
                params = {"like_val": f"%{search_val}%"}
            else:
                where  = (
                    "(a.SUPP = :exact_val OR a.[NAME] LIKE :like_val "
                    " OR a.NICKNAME LIKE :like_val) AND a.flgdel IS NULL"
                )
                params = {"exact_val": search_val, "like_val": f"%{search_val}%"}
        else:
            where = "a.flgdel IS NULL"

        total = db.session.execute(
            text(f"SELECT COUNT(*) FROM CLFSUPP a WITH(NOLOCK) WHERE {where}"),
            params,
        ).scalar() or 0

        offset = (page - 1) * limit
        rows   = db.session.execute(
            text(f"""
                SELECT a.SUPP, a.[NAME], a.NICKNAME, a.ADDRESS
                FROM   CLFSUPP a WITH(NOLOCK)
                WHERE  {where}
                ORDER  BY a.[NAME]
                OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
            """),
            {**params, "offset": offset, "limit": limit},
        ).mappings().all()

        return jsonify({
            "data":     [dict(r) for r in rows],
            "total":    total,
            "page":     page,
            "limit":    limit,
            "akses":    akses,
            "username": _uname(session.get("emp_id", "")),
        })

    except Exception:
        current_app.logger.exception("Dealer list error")
        return jsonify({"data": [], "total": 0}), 500

@dealer_bp.route("/dealer/options")
@login_required
def get_dealer_options():

    try:
        def q(sql):
            return db.session.execute(text(sql)).mappings().all()

        def o(rows, v, l):
            return [{"value": str(r[v] or ""), "label": r[l] or ""} for r in rows]

        return jsonify({
            "dealer_types": o(
                q("SELECT CODE, DESCRIPTION FROM MSTDEALERTYPE WITH(NOLOCK) ORDER BY DESCRIPTION"),
                "CODE", "DESCRIPTION",
            ),
            "car_conditions": o(
                q("SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE='DEALER_CON' ORDER BY DESC_VALUE"),
                "VALUE", "DESC_VALUE",
            ),
            "branches": o(
                q("SELECT BRANCH_CD, BRANCH_NAME FROM UMFBRANCH WITH(NOLOCK) ORDER BY BRANCH_CD"),
                "BRANCH_CD", "BRANCH_NAME",
            ),
            "showroom_cats": [{"value": "0", "label": "none"}] + o(
                q("SELECT CAST(bpkbcat_id AS VARCHAR) AS bpkbcat_id, bpkbcat_desc FROM MSTDEALERBPKBCATEGORY WITH(NOLOCK) ORDER BY bpkbcat_desc"),
                "bpkbcat_id", "bpkbcat_desc",
            ),
            "npwp_details": o(
                q("SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE='NPWP_DETAIL' ORDER BY DESC_VALUE"),
                "VALUE", "DESC_VALUE",
            ),
            "provinces": [
                {"value": r["PROPINSI"], "label": r["PROPINSI"]}
                for r in q(
                    "SELECT PROPINSI FROM UMFAREA WITH(NOLOCK) WHERE FLAG_DEL=0 GROUP BY PROPINSI ORDER BY PROPINSI"
                )
            ],
            "cities": [
                {"value": r["AREA_CD"], "label": r["KABUPATEN"], "province": r["PROPINSI"]}
                for r in q(
                    "SELECT AREA_CD, KABUPATEN, PROPINSI FROM UMFAREA WITH(NOLOCK) WHERE FLAG_DEL=0 ORDER BY KABUPATEN"
                )
            ],
            "tax_types": o(
                q("SELECT CAST(PPH_ID AS VARCHAR) AS PPH_ID, PPH_Desc FROM UMF_TAX WITH(NOLOCK)"),
                "PPH_ID", "PPH_Desc",
            ),
            "banks": o(
                q("SELECT BANK_CODE, [DESC] FROM UMFBANK WITH(NOLOCK) WHERE STATUS='1' ORDER BY [DESC]"),
                "BANK_CODE", "DESC",
            ),
            "beneficiary_types": o(
                q("SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE='BENEFICIARY_TYPE' ORDER BY DESC_VALUE"),
                "VALUE", "DESC_VALUE",
            ),
            "resident_statuses": o(
                q("SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE='RESIDENT_STATUS' ORDER BY DESC_VALUE"),
                "VALUE", "DESC_VALUE",
            ),
            "areas": o(
                q("SELECT CODE, DESCRIPTION FROM MSTDEALERAREA ORDER BY DESCRIPTION"),
                "CODE", "DESCRIPTION",
            ),
            "cmos": o(
                q("SELECT CAST(EMPLOYEE_ID AS VARCHAR) AS EMPLOYEE_ID, USERNAME "
                  "FROM APP_USRMST WITH(NOLOCK) WHERE ACCESSCAM='CMO' ORDER BY USERNAME"),
                "EMPLOYEE_ID", "USERNAME",
            ),
            "brands": o(
                q("SELECT BRAND, BRAND_NM FROM UMFBRAND WITH(NOLOCK) "
                  "WHERE BRAND_NM NOT IN ('CBU','All Brand','Used Cars','Used Trucks') "
                  "ORDER BY BRAND_NM"),
                "BRAND", "BRAND_NM",
            ),
            "statuses": [
                {"value": "1", "label": "Active"},
                {"value": "0", "label": "Inactive"},
            ],
        })

    except Exception:
        current_app.logger.exception("Dealer options error")
        return jsonify({}), 500

@dealer_bp.route("/dealer/<supp>")
@login_required
def get_dealer_detail(supp):
    try:
        row = db.session.execute(
            text("SELECT * FROM CLFSUPP WITH(NOLOCK) WHERE SUPP=:s"),
            {"s": supp},
        ).mappings().first()

        if not row:
            return jsonify({"error": "Dealer not found"}), 404

        return jsonify({
            "supp":          row["SUPP"]             or "",
            "status":        _bit(row["isActive"], "1"),
            "supp_type":     row["Supp_Type"]        or "",
            "car_condition": row["Car_Condition"]    or "",
            "name":          row["NAME"]              or "",
            "nickname":      row["NICKNAME"]          or "",
            "address":       row["ADDRESS"]           or "",
            "city":          row["CITY"]              or "",
            "zipcode":       row["ZipCode"]           or "",
            "phone":         row["PHONE"]             or "",
            "fax":           row["Fax"]               or "",
            "contact":       row["CONTACT"]           or "",
            "idcard":        row["IDCARD"]            or "",
            "exp_date":      "1" if row["ID_ValidDt"] else "0",
            "certain_per":   _fd(row["ID_ValidDt"]),
            "position":      row["POSITION"]          or "",
            "addr_con":      row["ADDR_CON"]          or "",
            "city_con":      row["CITY_CON"]          or "",
            "zipcode1":      row["ZipCode1"]          or "",
            "phone_con":     row["PHONE_CON"]         or "",
            "email_addr":    row["Email_Address"]     or "",
            "adm_name":      row["ADM_NAME"]          or "",
            "bpkbstaf":      row["BPKBSTAF"]         or "",
            "branch_mgr":    row["Branch_Mgr"]       or "",
            "remark":        row["Remark"]            or "",
            "branch_cd":     row["BRANCH_CD"]         or "",
            "showroom_cat":  str(row["BPKBCAT_ID"] or "0"),
            "create_by":     row["Created_By"]        or "",
            "create_date":   _fd(row["CREATE_DATE"]),
            "update_by":     row["CA_UpdateBy"]       or "",
            "ca_lastupd":    _fd(row["CA_LastUpdate"]),
        })

    except Exception:
        current_app.logger.exception("Dealer detail error")
        return jsonify({"error": "Load failed"}), 500

@dealer_bp.route("/dealer", methods=["POST"])
@login_required
def create_dealer():
    emp_id = session.get("emp_id")
    if not emp_id:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    d = request.get_json(force=True) or {}
    if not d.get("supp_type") or not d.get("name") or not d.get("nickname"):
        return jsonify({"success": False, "message": "Dealer Type, Name, and Nick Name are required."}), 400

    try:
        row = db.session.execute(text(
            "SELECT RIGHT(CONCAT('0000000', CAST(MAX(CAST(SUPP AS BIGINT))+1 AS VARCHAR)), 7) AS supp "
            "FROM CLFSUPP WITH(NOLOCK)"
        )).first()
        supp        = row[0] if row and row[0] else "0000001"
        username    = _uname(emp_id)
        certain_per = _parse_date(d.get("certain_per", "")) if d.get("exp_date") == "1" else None

        db.session.execute(text("""
            INSERT INTO CLFSUPP
            (SUPP, [NAME], NICKNAME, ADDRESS, CITY,
             PHONE, IDCARD, CONTACT, ID_ValidDt, POSITION, ADDR_CON, CITY_CON, PHONE_CON,
             ADM_NAME, BPKBSTAF, Branch_Mgr, ZipCode, ZipCode1,
             BRANCH_CD, Fax, Remark, LastUpd, Supp_Type,
             BPKBCAT_ID, Car_Condition, Created_By, CREATE_DATE, Email_Address, isActive)
            VALUES
            (:supp, :name, :nickname, :address, :city,
             :phone, :idcard, :contact, NULLIF(:certain_per,''), :position,
             :addr_con, :city_con, :phone_con,
             :adm_name, :bpkbstaf, :branch_mgr, :zipcode, :zipcode1,
             :branch_cd, :fax, :remark, SYSDATETIME(), :supp_type,
             :showroom_cat, :car_condition, :create_by, SYSDATETIME(), :email_addr, :status)
        """), {
            "supp": supp,
            "name": d.get("name", ""),           "nickname": d.get("nickname", ""),
            "address": d.get("address", ""),     "city": d.get("city", ""),
            "phone": d.get("phone", ""),         "idcard": d.get("idcard", ""),
            "contact": d.get("contact", ""),     "certain_per": certain_per or "",
            "position": d.get("position", ""),   "addr_con": d.get("addr_con", ""),
            "city_con": d.get("city_con", ""),   "phone_con": d.get("phone_con", ""),
            "adm_name": d.get("adm_name", ""),   "bpkbstaf": d.get("bpkbstaf", ""),
            "branch_mgr": d.get("branch_mgr", ""),
            "zipcode": d.get("zipcode", ""),     "zipcode1": d.get("zipcode1", ""),
            "branch_cd": d.get("branch_cd", ""), "fax": d.get("fax", ""),
            "remark": d.get("remark", ""),       "supp_type": d.get("supp_type", ""),
            "showroom_cat": d.get("showroom_cat", "0") or "0",
            "car_condition": d.get("car_condition", ""),
            "create_by": username,               "email_addr": d.get("email_addr", ""),
            "status": _bit(d.get("status"), "1"),
        })

        db.session.execute(text("""
            INSERT INTO SUPP_DEV (SUPP, DEV_CD, Description, IsCheck, Modified_By, Modified_Date)
            SELECT :supp, Dev_cd, Dev_doc, '0', :emp_id, GETDATE()
            FROM   SUPPDEV_REQ_Doc WITH(NOLOCK)
            WHERE  LEFT(Dev_cd, 2) = :st
        """), {"supp": supp, "emp_id": emp_id, "st": d.get("supp_type", "")})

        db.session.commit()
        return jsonify({"success": True, "supp": supp})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Dealer create error")
        return jsonify({"success": False, "message": "Failed to create dealer"}), 500

@dealer_bp.route("/dealer/<supp>", methods=["PUT"])
@login_required
def update_dealer(supp):
    emp_id = session.get("emp_id")
    if not emp_id:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    d = request.get_json(force=True) or {}
    if not d.get("supp_type") or not d.get("name") or not d.get("nickname"):
        return jsonify({"success": False, "message": "Dealer Type, Name, and Nick Name are required."}), 400

    try:
        username    = _uname(emp_id)
        old_type    = db.session.execute(
            text("SELECT Supp_Type FROM CLFSUPP WITH(NOLOCK) WHERE SUPP=:s"), {"s": supp}
        ).scalar() or ""
        certain_per = _parse_date(d.get("certain_per", "")) if d.get("exp_date") == "1" else None

        db.session.execute(text("""
            UPDATE CLFSUPP SET
                [NAME]=:name,        NICKNAME=:nickname,   ADDRESS=:address,    CITY=:city,
                PHONE=:phone,        CONTACT=:contact,     POSITION=:position,
                ADDR_CON=:addr_con,  CITY_CON=:city_con,
                ADM_NAME=:adm_name,  BPKBSTAF=:bpkbstaf,  Branch_Mgr=:branch_mgr,
                ZipCode=:zipcode,    ZipCode1=:zipcode1,   BRANCH_CD=:branch_cd,
                Fax=:fax,            Remark=:remark,       Supp_Type=:supp_type,
                CA_LastUpdate=SYSDATETIME(), CA_UpdateBy=:update_by,
                BPKBCAT_ID=:showroom_cat,   LastUpd=SYSDATETIME(),
                IDCARD=:idcard,             ID_ValidDt=NULLIF(:certain_per,''),
                PHONE_CON=:phone_con,       Car_Condition=:car_condition,
                Email_Address=:email_addr,  isActive=:status
            WHERE SUPP=:supp
        """), {
            "supp": supp,
            "name": d.get("name", ""),           "nickname": d.get("nickname", ""),
            "address": d.get("address", ""),     "city": d.get("city", ""),
            "phone": d.get("phone", ""),         "contact": d.get("contact", ""),
            "position": d.get("position", ""),   "addr_con": d.get("addr_con", ""),
            "city_con": d.get("city_con", ""),   "adm_name": d.get("adm_name", ""),
            "bpkbstaf": d.get("bpkbstaf", ""),  "branch_mgr": d.get("branch_mgr", ""),
            "zipcode": d.get("zipcode", ""),     "zipcode1": d.get("zipcode1", ""),
            "branch_cd": d.get("branch_cd", ""), "fax": d.get("fax", ""),
            "remark": d.get("remark", ""),       "supp_type": d.get("supp_type", ""),
            "showroom_cat": d.get("showroom_cat", "0") or "0",
            "idcard": d.get("idcard", ""),       "certain_per": certain_per or "",
            "phone_con": d.get("phone_con", ""), "car_condition": d.get("car_condition", ""),
            "email_addr": d.get("email_addr", ""), "status": _bit(d.get("status"), "1"),
            "update_by": username,
        })

        if old_type.strip() != d.get("supp_type", "").strip():
            db.session.execute(text("DELETE FROM SUPP_DEV WHERE SUPP=:s"), {"s": supp})
            db.session.execute(text("""
                INSERT INTO SUPP_DEV (SUPP, DEV_CD, Description, IsCheck, Modified_By, Modified_Date)
                SELECT :supp, Dev_cd, Dev_doc, '0', :emp_id, GETDATE()
                FROM   SUPPDEV_REQ_Doc WITH(NOLOCK)
                WHERE  LEFT(Dev_cd, 2) = :st
            """), {"supp": supp, "emp_id": emp_id, "st": d.get("supp_type", "")})

        db.session.commit()
        return jsonify({"success": True})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Dealer update error")
        return jsonify({"success": False, "message": "Failed to update dealer"}), 500

@dealer_bp.route("/dealer/<supp>", methods=["DELETE"])
@login_required
def delete_dealer(supp):
    emp_id = session.get("emp_id")
    if not emp_id:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    reason = (request.get_json(force=True) or {}).get("reason", "").strip()
    if not reason:
        return jsonify({"success": False, "message": "Reason is required."}), 400

    try:
        last = db.session.execute(text(
            "SELECT TOP 1 form_no FROM CLFSUPP_DELETE WITH(NOLOCK) ORDER BY delete_date DESC"
        )).scalar() or ""
        try:
            urut = str(int((last or "")[:4]) + 1).zfill(4)
        except ValueError:
            urut = "0001"
        now     = datetime.datetime.now()
        form_no = f"{urut}/SFI-SUPP/{now.month:02d}-{now.year}"

        db.session.execute(
            text("UPDATE CLFSUPP SET FLGDEL='1' WHERE SUPP=:s"), {"s": supp}
        )
        db.session.execute(text("""
            INSERT INTO CLFSUPP_DELETE (SUPP, Form_No, Delete_By, Reason, Delete_Date)
            VALUES (:supp, :form_no, :emp_id, :reason, GETDATE())
        """), {"supp": supp, "form_no": form_no, "emp_id": emp_id, "reason": reason})

        db.session.commit()
        return jsonify({"success": True, "form_no": form_no})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Dealer delete error")
        return jsonify({"success": False, "message": "Failed to delete dealer"}), 500

@dealer_bp.route("/dealer/<supp>/tax")
@login_required
def get_dealer_tax(supp):
    try:
        row = db.session.execute(text("""
            SELECT a.*, b.USERNAME
            FROM   BeneficiaryTax a WITH(NOLOCK)
            LEFT JOIN APP_USRMST b WITH(NOLOCK) ON a.UpdateBy = b.EMPLOYEE_ID
            WHERE  a.BeneficiaryID=:s AND a.Category='Dealer'
        """), {"s": supp}).mappings().first()

        if not row:
            return jsonify({"is_saved": False, "pph": "2", "rate": "2", "dpp": "100"})

        pph  = str(row["TaxType"] or "")
        rate = "1" if pph == "1" else "2"

        return jsonify({
            "is_saved":      True,
            "npwp_no":       row["NPWP_No"]                       or "",
            "npwp_detail":   row["NPWP_Detail"]                   or "",
            "npwp_nm":       row["NPWP_Name"]                      or "",
            "npwp_addr":     row["NPWP_Address"]                   or "",
            "province":      row["NPWP_Prov"]                      or "",
            "city":          row["NPWP_City"]                      or "",
            "ppnsts":        _bit(row["PPN"]),
            "ppnstartdate":  _fd(row["DateStart"]),
            "taxfree":       _fd(row["TFFrom"]),
            "taxfree2":      _fd(row["TFTo"]),
            "pph":           pph,
            "rate":          rate,
            "dpp":           _num(row["DPP"], "100"),
            "kores_address": row.get("CorrespondenceAddress") or "",
            "update_by":     row["USERNAME"]                       or "",
            "lastupdate":    _fd(row["UpdateDate"]),
        })

    except Exception:
        current_app.logger.exception("Dealer tax get error")
        return jsonify({"is_saved": False}), 500

@dealer_bp.route("/dealer/<supp>/tax", methods=["POST", "PUT"])
@login_required
def save_dealer_tax(supp):
    emp_id = session.get("emp_id")
    if not emp_id:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    d     = request.get_json(force=True) or {}
    ppnsd = _parse_date(d.get("ppnstartdate", ""))
    tf1   = _parse_date(d.get("taxfree",      ""))
    tf2   = _parse_date(d.get("taxfree2",     ""))
    pph   = d.get("pph", "2") or "2"
    rate  = "1" if pph == "1" else "2"

    params = {
        "s":     supp,
        "emp":   emp_id,
        "ppn":   _bit(d.get("ppnsts")),
        "ppnsd": ppnsd,
        "tf1":   tf1,
        "tf2":   tf2,
        "pph":   pph,
        "rate":  rate,
        "dpp":   d.get("dpp",          "100"),
        "nn":    d.get("npwp_no",      ""),
        "nnm":   d.get("npwp_nm",      ""),
        "na":    d.get("npwp_addr",    ""),
        "nc":    d.get("city",         ""),
        "np":    d.get("province",     ""),
        "nd":    d.get("npwp_detail",  ""),
        "kores": d.get("kores_address",""),
    }

    try:
        exists = db.session.execute(text(
            "SELECT TOP 1 1 FROM BeneficiaryTax WITH(NOLOCK) "
            "WHERE BeneficiaryID=:s AND Category='Dealer'"
        ), {"s": supp}).scalar()

        if exists:
            db.session.execute(text("""
                UPDATE BeneficiaryTax SET
                    PPN=:ppn,          DateStart=:ppnsd,
                    TFFrom=:tf1,       TFTo=:tf2,
                    TaxType=:pph,      TaxRate=:rate,     DPP=:dpp,
                    NPWP_No=:nn,       NPWP_Name=:nnm,    NPWP_Address=:na,
                    NPWP_City=:nc,     NPWP_Prov=:np,     NPWP_Detail=:nd,
                    NPWP_Type='PT',    UpdateBy=:emp,      UpdateDate=SYSDATETIME(),
                    CorrespondenceAddress=:kores
                WHERE BeneficiaryID=:s AND Category='Dealer'
            """), params)
        else:
            db.session.execute(text("""
                INSERT INTO BeneficiaryTax
                    (Category,    BeneficiaryID, PPN,     DateStart,
                     TFFrom,      TFTo,          TaxType, TaxRate,  DPP,
                     NPWP_No,     NPWP_Name,     NPWP_Address,
                     NPWP_City,   NPWP_Prov,     NPWP_Detail,
                     NPWP_Type,   UpdateBy,      UpdateDate,
                     CorrespondenceAddress)
                VALUES
                    ('Dealer',    :s,            :ppn,    :ppnsd,
                     :tf1,        :tf2,          :pph,    :rate,    :dpp,
                     :nn,         :nnm,          :na,
                     :nc,         :np,           :nd,
                     'PT',        :emp,          SYSDATETIME(),
                     :kores)
            """), params)

        db.session.commit()
        return jsonify({"success": True})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Dealer tax save error")
        return jsonify({"success": False, "message": "Failed to save tax"}), 500

def _bank_rows(supp: str, acc_type: str) -> list:
    rows = db.session.execute(text("""
        SELECT
            a.Acc_NO, a.Acc_Name, a.Acc_Bank, a.Acc_BankBranch,
            a.BeneficiaryType, a.ResidentStatus, a.[Default], a.UpdateDate,
            b.[DESC]        AS BankDesc,
            c.DESC_VALUE    AS BenefDesc,
            d.DESC_VALUE    AS ResidentDesc
        FROM BeneficiaryAccount a WITH(NOLOCK)
            LEFT JOIN UMFBANK  b WITH(NOLOCK) ON b.BANK_CODE = a.Acc_Bank AND b.STATUS='1'
            LEFT JOIN MSTCOMBO c WITH(NOLOCK) ON c.CAT_VALUE='BENEFICIARY_TYPE' AND c.VALUE = a.BeneficiaryType
            LEFT JOIN MSTCOMBO d WITH(NOLOCK) ON d.CAT_VALUE='RESIDENT_STATUS'  AND d.VALUE = a.ResidentStatus
        WHERE a.BeneficiaryID=:s AND a.Category='Dealer' AND a.AccountType=:at
        ORDER BY a.[Default] DESC, a.UpdateDate DESC
    """), {"s": supp, "at": acc_type}).mappings().all()

    return [{
        "acc_no":                 r["Acc_NO"]          or "",
        "acc_name":               r["Acc_Name"]        or "",
        "acc_bank":               r["Acc_Bank"]        or "",
        "acc_bank_desc":          r["BankDesc"]        or "",
        "acc_bank_branch":        r["Acc_BankBranch"]  or "",
        "beneficiary_type":       r["BeneficiaryType"] or "",
        "beneficiary_type_desc":  r["BenefDesc"]       or "",
        "resident_status":        r["ResidentStatus"]  or "",
        "resident_status_desc":   r["ResidentDesc"]    or "",
        "acc_type":               acc_type,
        "is_default":             _bit(r["Default"]) == "1",
        "last_update":            _fd(r["UpdateDate"]),
    } for r in rows]

def _clear_default(supp: str, acc_type: str):
    db.session.execute(text("""
        UPDATE BeneficiaryAccount SET [Default]='0'
        WHERE BeneficiaryID=:s AND Category='Dealer' AND AccountType=:at
    """), {"s": supp, "at": acc_type})

@dealer_bp.route("/dealer/<supp>/bank-accounts")
@login_required
def get_bank_accounts(supp):
    try:
        return jsonify({
            "disbursement": _bank_rows(supp, "D"),
            "commission":   _bank_rows(supp, "C"),
        })
    except Exception:
        current_app.logger.exception("Dealer bank accounts list error")
        return jsonify({"disbursement": [], "commission": []}), 500

@dealer_bp.route("/dealer/<supp>/bank-accounts", methods=["POST"])
@login_required
def add_bank_account(supp):
    emp_id = session.get("emp_id")
    if not emp_id:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    d  = request.get_json(force=True) or {}
    at = d.get("acc_type", "")
    df = _bit(d.get("is_default"))

    for f in ["acc_type", "acc_name", "bank", "bank_brch",
              "beneficiary_type", "resident_status"]:
        if not d.get(f):
            return jsonify({"success": False,
                            "message": f"{f.replace('_',' ').title()} is required."}), 400
    try:
        if df == "1":
            _clear_default(supp, at)

        db.session.execute(text("""
            INSERT INTO BeneficiaryAccount
                (Category, BeneficiaryID, Acc_NO, Acc_Name, Acc_Bank, Acc_BankBranch,
                 BeneficiaryType, ResidentStatus, [Default], AccountType, UpdateBy, UpdateDate)
            VALUES
                ('Dealer',:s,:an,:nm,:bk,:bb,:bt,:rs,:df,:at,:usr,SYSDATETIME())
        """), {
            "s": supp, "an": d.get("acc_no",""), "nm": d["acc_name"],
            "bk": d["bank"], "bb": d["bank_brch"],
            "bt": d["beneficiary_type"], "rs": d["resident_status"],
            "df": df, "at": at, "usr": _uname(emp_id),
        })
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Dealer bank account add error")
        return jsonify({"success": False, "message": "Failed to add account"}), 500

@dealer_bp.route("/dealer/<supp>/bank-accounts/<acc_type>/<path:acc_no>", methods=["PUT"])
@login_required
def update_bank_account(supp, acc_type, acc_no):
    emp_id = session.get("emp_id")
    if not emp_id:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    d  = request.get_json(force=True) or {}
    df = _bit(d.get("is_default"))
    usr = _uname(emp_id)

    try:
        if df == "1":
            _clear_default(supp, acc_type)

        db.session.execute(text("""
            UPDATE BeneficiaryAccount SET
                Acc_Name=:nm, Acc_Bank=:bk, Acc_BankBranch=:bb,
                BeneficiaryType=:bt, ResidentStatus=:rs,
                [Default]=:df, AccountType=:at,
                UpdateBy=:usr, UpdateDate=SYSDATETIME()
            WHERE BeneficiaryID=:s AND Category='Dealer'
              AND Acc_No=:an AND AccountType=:at
        """), {
            "s": supp, "an": acc_no,
            "nm": d.get("acc_name",""), "bk": d.get("bank",""),
            "bb": d.get("bank_brch",""), "bt": d.get("beneficiary_type",""),
            "rs": d.get("resident_status",""), "df": df, "at": acc_type, "usr": usr,
        })
        db.session.execute(text(
            "UPDATE CLFSUPP SET CA_LastUpdate=SYSDATETIME(), CA_UpdateBy=:usr WHERE SUPP=:s"
        ), {"s": supp, "usr": usr})

        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Dealer bank account update error")
        return jsonify({"success": False, "message": "Failed to update account"}), 500

@dealer_bp.route("/dealer/<supp>/bank-accounts/<acc_type>/<path:acc_no>", methods=["DELETE"])
@login_required
def delete_bank_account(supp, acc_type, acc_no):
    emp_id = session.get("emp_id")
    if not emp_id:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    try:
        db.session.execute(text("""
            DELETE FROM BeneficiaryAccount
            WHERE BeneficiaryID=:s AND Category='Dealer'
              AND Acc_No=:an AND AccountType=:at
        """), {"s": supp, "an": acc_no, "at": acc_type})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Dealer bank account delete error")
        return jsonify({"success": False, "message": "Delete failed"}), 500

@dealer_bp.route("/dealer/<supp>/additional")
@login_required
def get_additional(supp):
    try:
        row = db.session.execute(text(
            "SELECT BD_Area, CMO, Brand FROM CLFSUPP WITH(NOLOCK) WHERE SUPP=:s"
        ), {"s": supp}).first()
        return jsonify({
            "bd_area": row[0] or "" if row else "",
            "cmo":     row[1] or "" if row else "",
            "brand":   row[2] or "" if row else "",
        })
    except Exception:
        current_app.logger.exception("Dealer additional get error")
        return jsonify({"bd_area": "", "cmo": "", "brand": ""}), 500

@dealer_bp.route("/dealer/<supp>/additional", methods=["POST", "PUT"])
@login_required
def save_additional(supp):
    emp_id = session.get("emp_id")
    if not emp_id:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    d   = request.get_json(force=True) or {}
    usr = _uname(emp_id)
    try:
        db.session.execute(text("""
            UPDATE CLFSUPP SET
                BD_Area=:area, CMO=:cmo, Brand=:brand,
                CA_LastUpdate=SYSDATETIME(), CA_UpdateBy=:usr
            WHERE SUPP=:s
        """), {
            "s":    supp,
            "area": d.get("bd_area",""),
            "cmo":  d.get("cmo",""),
            "brand":d.get("brand",""),
            "usr":  usr,
        })
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Dealer additional save error")
        return jsonify({"success": False, "message": "Failed to save additional info"}), 500

@dealer_bp.route("/dealer/<supp>/deviation")
@login_required
def get_deviation(supp):
    try:
        if not db.session.execute(text(
            "SELECT TOP 1 1 FROM SUPP_DEV WHERE SUPP=:s"
        ), {"s": supp}).scalar():
            supp_type = db.session.execute(text(
                "SELECT Supp_Type FROM CLFSUPP WITH(NOLOCK) WHERE SUPP=:s"
            ), {"s": supp}).scalar() or ""
            db.session.execute(text("""
                INSERT INTO SUPP_DEV (SUPP, DEV_CD, [Description], IsCheck, Modified_By, Modified_Date)
                SELECT :supp, Dev_cd, Dev_doc, '0', NULL, NULL
                FROM SUPPDEV_REQ_Doc WITH(NOLOCK)
                WHERE LEFT(Dev_cd, 2) = :st
            """), {"supp": supp, "st": supp_type})
            db.session.commit()

        items = db.session.execute(text(
            "SELECT DEV_CD, [Description], IsCheck FROM SUPP_DEV WHERE SUPP=:s ORDER BY DEV_CD"
        ), {"s": supp}).mappings().all()

        nr = db.session.execute(text(
            "SELECT NOTE1, NOTE2, NOTE3, NOTE4, NOTE5, CMO_PROMISE FROM CLFSUPP WITH(NOLOCK) WHERE SUPP=:s"
        ), {"s": supp}).first()

        return jsonify({
            "items": [{"dev_cd": r["DEV_CD"] or "", "description": r["Description"] or "",
                       "is_check": _bit(r["IsCheck"])} for r in items],
            "notes": {
                "note1": nr[0] or "" if nr else "",
                "note2": nr[1] or "" if nr else "",
                "note3": nr[2] or "" if nr else "",
                "note4": nr[3] or "" if nr else "",
                "note5": nr[4] or "" if nr else "",
                "janji": nr[5] or "" if nr else "",
            },
        })
    except Exception:
        current_app.logger.exception("Dealer deviation get error")
        return jsonify({"items": [], "notes": {}}), 500

@dealer_bp.route("/dealer/<supp>/deviation/<dev_cd>", methods=["PATCH", "PUT"])
@login_required
def toggle_deviation(supp, dev_cd):
    emp_id = session.get("emp_id")
    if not emp_id:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    is_check = _bit((request.get_json(force=True) or {}).get("is_check"))
    dev      = (dev_cd or "").strip()

    try:
        res = db.session.execute(text("""
            UPDATE SUPP_DEV
            SET IsCheck=:chk, Modified_By=:usr, Modified_Date=GETDATE()
            WHERE SUPP=:s AND LTRIM(RTRIM(DEV_CD))=:dev
        """), {"chk": is_check, "usr": _uname(emp_id), "s": supp, "dev": dev})

        if res.rowcount == 0:
            db.session.rollback()
            current_app.logger.warning(
                "Deviation toggle matched 0 rows: supp=%r dev_cd=%r", supp, dev
            )
            return jsonify({
                "success": False,
                "message": f"Checklist item {dev} not found for this dealer.",
            }), 404

        db.session.commit()
        return jsonify({"success": True, "is_check": is_check})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Dealer deviation toggle error")
        return jsonify({"success": False, "message": "Toggle failed"}), 500

@dealer_bp.route("/dealer/<supp>/deviation/notes", methods=["POST", "PUT"])
@login_required
def save_deviation_notes(supp):
    emp_id = session.get("emp_id")
    if not emp_id:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    d   = request.get_json(force=True) or {}
    usr = _uname(emp_id)
    try:
        db.session.execute(text("""
            UPDATE CLFSUPP SET
                NOTE1=:n1, NOTE2=:n2, NOTE3=:n3, NOTE4=:n4, NOTE5=:n5,
                CMO_PROMISE=:janji,
                CA_LastUpdate=SYSDATETIME(), CA_UpdateBy=:usr
            WHERE SUPP=:s
        """), {
            "s":     supp,
            "n1":    d.get("note1",""), "n2": d.get("note2",""),
            "n3":    d.get("note3",""), "n4": d.get("note4",""),
            "n5":    d.get("note5",""), "janji": d.get("janji",""),
            "usr":   usr,
        })
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Dealer deviation notes save error")
        return jsonify({"success": False, "message": "Failed to save notes"}), 500

@dealer_bp.route("/dealer/<supp>/files", methods=["GET"])
@login_required
def get_dealer_files(supp):
    try:
        rows = db.session.execute(text("""
            SELECT Id, AWSKey, DocumentName, DocumentType, CreatedBy, CreatedDate
            FROM   DEALER_FILE WITH (NOLOCK)
            WHERE  DealerNo = :supp
            ORDER  BY DocumentType, CreatedDate DESC
        """), {"supp": supp}).mappings().all()

        files: dict = {}

        for r in rows:
            aws_key = (r["AWSKey"] or "").strip()
            if not aws_key:
                continue

            doc_key   = _to_canonical_doc_type(r["DocumentType"])
            full_name = (r["DocumentName"] or "").strip() or os.path.basename(aws_key)
            name, ext = os.path.splitext(full_name)

            try:
                url = _aws_presign(aws_key, full_name)
            except (BotoCoreError, ClientError):
                current_app.logger.exception("Presign failed for %s", aws_key)
                url = ""

            files.setdefault(doc_key, []).append({
                "id":           r["Id"],
                "aws_key":      aws_key,
                "file_nm":      name,
                "file_ext":     ext.lstrip("."),
                "doc_type":     doc_key,
                "ket":          "",
                "created_by":   r["CreatedBy"] or "",
                "created_date": _fd(r["CreatedDate"]),
                "download_url": url,
            })

        current_app.logger.info("dealer files: supp=%r rows=%d", supp, len(rows))
        return jsonify({"files": files, "lainnya": ""})

    except Exception:
        current_app.logger.exception("Dealer files list error")
        return jsonify({"files": {}, "lainnya": "", "error": "query_failed"}), 500

@dealer_bp.route("/dealer/<supp>/files/<doc_type>", methods=["POST"])
@login_required
def upload_dealer_file(supp, doc_type):
    emp_id = session.get("emp_id")
    if not emp_id:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    denied = _require_dealer_write("upload")
    if denied:
        return denied

    if doc_type not in DEALER_DOC_TYPES:
        return jsonify({"success": False, "message": f"Unknown doc type: {doc_type}"}), 400

    files_list = [f for f in request.files.getlist("file") if f and f.filename]
    if not files_list:
        return jsonify({"success": False, "message": "No files selected"}), 400

    legacy_type = _to_legacy_doc_type(doc_type)
    username    = _uname(emp_id)

    staged = []
    for f in files_list:
        safe_name  = secure_filename(f.filename) or "file"
        file_bytes = f.read()
        if not file_bytes:
            return jsonify({"success": False, "message": f"{f.filename}: file is empty."}), 400

        err = _validate_file(file_bytes, safe_name, DEALER_MAX_FILE_MB)
        if err:
            return jsonify({"success": False, "message": f"{f.filename}: {err}"}), 400

        file_nm, file_ext = os.path.splitext(safe_name)
        staged.append({
            "safe_name":    safe_name,
            "file_nm":      file_nm,
            "file_ext":     file_ext.lstrip("."),
            "bytes":        file_bytes,
            "content_type": mimetypes.guess_type(safe_name)[0] or "application/octet-stream",
            "aws_key":      f"Dealer/{supp}/{legacy_type}_FILE/{uuid.uuid4().hex}-{safe_name}",
        })

    uploaded_keys = []
    try:
        for item in staged:
            _aws_upload(item["bytes"], item["aws_key"], item["content_type"])
            uploaded_keys.append(item["aws_key"])

            db.session.execute(text("""
                INSERT INTO DEALER_FILE
                    (DealerNo, DocumentType, DocumentName, AWSKey, CreatedBy, CreatedDate)
                VALUES (:supp, :dt, :nm, :key, :usr, SYSDATETIME())
            """), {
                "supp": supp, "dt": legacy_type, "nm": item["safe_name"],
                "key": item["aws_key"], "usr": username,
            })

        db.session.commit()
        return jsonify({"success": True, "uploaded": [
            {"file_nm": i["file_nm"], "file_ext": i["file_ext"]} for i in staged
        ]})

    except (BotoCoreError, ClientError):
        db.session.rollback()
        _discard_keys(uploaded_keys)
        current_app.logger.exception("Dealer file S3 upload failed")
        return jsonify({"success": False, "message": "Upload to storage failed"}), 500
    except Exception:
        db.session.rollback()
        _discard_keys(uploaded_keys)
        current_app.logger.exception("Dealer file upload error")
        return jsonify({"success": False, "message": "Upload failed"}), 500

@dealer_bp.route("/dealer/<supp>/files/<int:file_id>", methods=["DELETE"])
@login_required
def delete_dealer_file(supp, file_id):
    denied = _require_dealer_write("delete")
    if denied:
        return denied

    try:
        row = db.session.execute(text(
            "SELECT AWSKey FROM DEALER_FILE WITH(NOLOCK) WHERE Id=:id AND DealerNo=:s"
        ), {"id": file_id, "s": supp}).first()

        if not row:
            return jsonify({"success": False, "message": "File not found"}), 404

        db.session.execute(text(
            "DELETE FROM DEALER_FILE WHERE Id=:id AND DealerNo=:s"
        ), {"id": file_id, "s": supp})
        db.session.commit()

        if row.AWSKey:
            try:
                _aws_delete(row.AWSKey)
            except (BotoCoreError, ClientError):
                current_app.logger.exception("S3 cleanup failed for %s", row.AWSKey)

        return jsonify({"success": True})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Dealer file delete error")
        return jsonify({"success": False, "message": "Delete failed"}), 500

@dealer_bp.route("/dealer/<supp>/files/<int:file_id>/download")
@login_required
def download_dealer_file(supp, file_id):
    mode = "attachment" if request.args.get("mode") == "attachment" else "inline"

    try:
        row = db.session.execute(text(
            "SELECT AWSKey, DocumentName FROM DEALER_FILE WITH(NOLOCK) "
            "WHERE Id=:id AND DealerNo=:s"
        ), {"id": file_id, "s": supp}).first()

        if not row or not row.AWSKey:
            return jsonify({"error": "No data for this file."}), 404

        if not _aws_object_exists(row.AWSKey):
            current_app.logger.warning(
                "DEALER_FILE row %s points at a missing object: %s", file_id, row.AWSKey
            )
            return jsonify({"error": "No data found in storage for this file."}), 404

        file_name = row.DocumentName or os.path.basename(row.AWSKey)
        url = _aws_presign(row.AWSKey, file_name, disposition=mode)
        return jsonify({"url": url, "file_name": file_name})

    except (BotoCoreError, ClientError) as exc:
        current_app.logger.exception(exc)
        return jsonify({"error": str(exc)}), 500
    except Exception:
        current_app.logger.exception("Dealer file download error")
        return jsonify({"error": "Download failed"}), 500

@dealer_bp.route("/dealer/<supp>/notes")
@login_required
def get_dealer_notes(supp):
    try:
        row = db.session.execute(text(
            "SELECT SUPP_NOTES FROM CLFSUPP WITH(NOLOCK) WHERE SUPP=:s"
        ), {"s": supp}).first()
        return jsonify({"notes": (row[0] or "") if row else ""})
    except Exception:
        current_app.logger.exception("Dealer notes get error")
        return jsonify({"notes": ""}), 500

@dealer_bp.route("/dealer/<supp>/notes", methods=["POST", "PUT"])
@login_required
def save_dealer_notes(supp):
    emp_id = session.get("emp_id")
    if not emp_id:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    notes_raw = (request.get_json(force=True) or {}).get("notes", "")
    notes     = re.sub(r"<[^>]+>", "", notes_raw).replace("'", "`")
    usr       = _uname(emp_id)

    try:
        db.session.execute(text("""
            UPDATE CLFSUPP
            SET SUPP_NOTES=:n, CA_LastUpdate=GETDATE(), CA_UpdateBy=:usr
            WHERE SUPP=:s
        """), {"n": notes, "usr": usr, "s": supp})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Dealer notes save error")
        return jsonify({"success": False, "message": "Failed to save notes"}), 500