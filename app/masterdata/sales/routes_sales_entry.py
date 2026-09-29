from flask import Blueprint, jsonify, request, current_app, session, redirect
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text
from datetime import datetime
import re
from werkzeug.utils import secure_filename as _sf
from app.utils.helpers.aws_helpers import build_key, upload_fileobj, delete_object, _aws_presign

sales_entry_bp = Blueprint("sales_entry", __name__, url_prefix="/MasterData")

_DOC_PREFIX = {
    "commission-receiver":  "PENERIMA_KOMISI-",
    "sales-ktp":            "KTP-",
    "sales-contact-person": "CONTACT_PERSON-",
    "sales-siup":           "SIUP-",
    "sales-npwp":           "NPWP-",
    "sales-bank-account":   "BUKU_TABUNGAN-",
    "sales-npwp-statement": "SURAT_PERNYATAAN_NPWP-",
    "sales-other":          "OTHER-",
}

def _fd(dt, fmt="%d-%m-%Y"):
    if dt is None:
        return ""
    try:
        return dt.strftime(fmt)
    except Exception:
        return str(dt)

def _combo(cat, extra_where=""):
    rows = db.session.execute(text(
        f"SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) "
        f"WHERE CAT_VALUE=:c {extra_where} ORDER BY VALUE"
    ), {"c": cat}).mappings().all()
    return [{"value": r["VALUE"], "label": r["DESC_VALUE"]} for r in rows]

def _uname(emp_id):
    row = db.session.execute(
        text("SELECT USERNAME FROM APP_USRMST WITH(NOLOCK) WHERE EMPLOYEE_ID=:e"),
        {"e": emp_id}
    ).first()
    return row[0] if row else ""

def _broker_type(sales_no):
    row = db.session.execute(text(
        "SELECT ISNULL(NPWP_Type,'') AS t FROM BeneficiaryTax WITH(NOLOCK) "
        "WHERE BeneficiaryID=:s AND Category='SALES'"
    ), {"s": sales_no}).first()
    v = (row[0] or "").strip() if row else ""
    return "PR" if v == "00" else v

def _tv_copy(sales_no):
    row = db.session.execute(text(
        "SELECT TOP 1 SALES_NO FROM CLFSALES WITH(NOLOCK) "
        "WHERE Initial_Sales_No=:s AND IsSalesTV=1"
    ), {"s": sales_no}).first()
    return row[0] if row else None

@sales_entry_bp.route("/sales-entry/options")
@login_required
def get_options():
    
    try:
        branches = db.session.execute(text(
            "SELECT BRANCH_CD, BRANCH_NAME FROM UMFBRANCH WITH(NOLOCK) "
            "WHERE BRANCH_CD NOT IN ('00','01') ORDER BY BRANCH_NAME"
        )).mappings().all()

        banks = db.session.execute(text(
            "SELECT BANK_CODE, [DESC] FROM UMFBANK WITH(NOLOCK) "
            "WHERE STATUS='1' ORDER BY [DESC]"
        )).mappings().all()

        tax_types = db.session.execute(text(
            "SELECT PPH_ID, PPH_Desc FROM UMF_TAX WITH(NOLOCK)"
        )).mappings().all()

        provinces = db.session.execute(text(
            "SELECT DISTINCT PROPINSI FROM UMFAREA WITH(NOLOCK) "
            "WHERE FLAG_DEL=0 ORDER BY PROPINSI"
        )).mappings().all()

        cities = db.session.execute(text(
            "SELECT AREA_CD, KABUPATEN, PROPINSI FROM UMFAREA WITH(NOLOCK) "
            "WHERE FLAG_DEL=0 ORDER BY KABUPATEN"
        )).mappings().all()

        occ = [
            {"value": "1", "label": "Kacab"}, {"value": "2", "label": "OM"},
            {"value": "3", "label": "PIC"},   {"value": "4", "label": "Salesman"},
            {"value": "5", "label": "Supervisor"}, {"value": "6", "label": "Owner"},
            {"value": "7", "label": "Director"},
        ]
        pic_occ = occ[:5]

        return jsonify({
            "sales_types":        _combo("SALES_TYPE"),
            "broker_types":       _combo("TIPE_CUST", "AND VALUE NOT IN ('00')"),
            "npwp_types_pr":      _combo("TIPE_CUST", "AND VALUE IN ('PR','00')"),
            "npwp_types_pt":      _combo("TIPE_CUST", "AND VALUE IN ('PT')"),
            "genders":            _combo("GENDER"),
            "npwp_details":       _combo("NPWP_DETAIL"),
            "beneficiary_types":  _combo("BENEFICIARY_TYPE"),
            "resident_statuses":  _combo("RESIDENT_STATUS"),
            "branches":      [{"value": r["BRANCH_CD"], "label": r["BRANCH_NAME"]} for r in branches],
            "banks":         [{"value": r["BANK_CODE"],  "label": r["DESC"]}        for r in banks],
            "tax_types":     [{"value": r["PPH_ID"],    "label": r["PPH_Desc"]}     for r in tax_types],
            "provinces":     [{"value": r["PROPINSI"],  "label": r["PROPINSI"]}     for r in provinces],
            "cities":        [{"value": r["AREA_CD"],   "label": r["KABUPATEN"],
                               "province": r["PROPINSI"]}                           for r in cities],
            "occupations":   occ,
            "pic_occupations": pic_occ,
            "current_user":    session.get("username", ""),
        })

    except Exception:
        current_app.logger.exception("Sales entry options error")
        return jsonify({"error": "Failed to load options"}), 500

@sales_entry_bp.route("/sales-entry/cmo-list")
@login_required
def get_cmo_list():
    branch_cd = request.args.get("branch_cd", "").strip()
    try:
        rows = db.session.execute(text("""
            SELECT EMPLOYEE_ID, FULLNAME FROM APP_USRMST WITH(NOLOCK)
            WHERE ACCESSCAM='CMO' AND BRANCHCODE=:b
              AND EMPLOYEE_ID <> '' AND EMPLOYEE_ID <> '9999'
            ORDER BY FULLNAME
        """), {"b": branch_cd}).mappings().all()
        return jsonify([{"value": r["EMPLOYEE_ID"], "label": r["FULLNAME"]} for r in rows])
    except Exception:
        current_app.logger.exception("CMO list error")
        return jsonify([]), 500

@sales_entry_bp.route("/sales-entry/<sales_no>")
@login_required
def get_edit_data(sales_no):

    try:
        s = db.session.execute(text("""
            SELECT SALES_NO, [NAME], ADDRESS, City, PHONE, IDCARD, PAID,
                   BD_Occupation, ID_ValidDt, Status, Sales_Type,
                   Created_By, ID_CMO, BRANCH_CD, ZipCode, Sales_Nickname, FAX,
                   CREATE_DATE, SALES_NOTES, Initial_Sales_No,
                   ISNULL(IsSalesTV,0) AS IsSalesTV, Email_Address, Gender,
                   LastUpdate, UpdateBy
            FROM CLFSALES WITH(NOLOCK) WHERE SALES_NO=:sno
        """), {"sno": sales_no}).mappings().first()

        if not s:
            return jsonify({"error": "Sales not found"}), 404

        update_by_nm = s["UpdateBy"] or ""
        if update_by_nm and len(update_by_nm) == 4:
            update_by_nm = _uname(update_by_nm)

        broker = _broker_type(sales_no)

        main = {
            "sales_no":          s["SALES_NO"]          or "",
            "initial_sales_no":  s["Initial_Sales_No"]  or "",
            "sal_type":          s["Sales_Type"]         or "",
            "broker":            broker,
            "status":            s["Status"]             or "",
            "branch":            (s["BRANCH_CD"]         or "").strip(),
            "cmo_name":          (s["ID_CMO"]            or "").strip(),
            "name":              s["NAME"]                or "",
            "gender":            (s["Gender"]            or "").strip(),
            "nick_name":         s["Sales_Nickname"]     or "",
            "bd_occupation":     s["BD_Occupation"]      or "",
            "idcard":            s["IDCARD"]             or "",
            "exp_date":          "1" if s["ID_ValidDt"] else "0",
            "certain_per":       _fd(s["ID_ValidDt"]),
            "address":           s["ADDRESS"]            or "",
            "city_sales":        s["City"]               or "",
            "post":              s["ZipCode"]            or "",
            "phone":             s["PHONE"]              or "",
            "email_addr":        s["Email_Address"]      or "",
            "fax":               s["FAX"]                or "",
            "paid":              s["PAID"]               or "1",
            "create_by":         s["Created_By"]         or "",
            "create_date":       _fd(s["CREATE_DATE"]),
            "update_by":         update_by_nm,
            "lastupdate":        _fd(s["LastUpdate"]),
            "is_sales_tv":       bool(s["IsSalesTV"]),
        }

        p = db.session.execute(text("""
            SELECT Contact_Name, Contact_IDCard, Contact_IDValidDt,
                   Contact_Address, Contact_City, Contact_Post, Contact_Phone,
                   Occupation, Email_Address
            FROM CLFSALESPIC WITH(NOLOCK) WHERE SALES_NO=:sno
        """), {"sno": sales_no}).mappings().first()

        pic = {
            "cont_name":  p["Contact_Name"]     if p else "",
            "cont_idcard": p["Contact_IDCard"]  if p else "",
            "exp_date":   "1" if (p and p["Contact_IDValidDt"]) else "0",
            "id_validdt": _fd(p["Contact_IDValidDt"]) if p else "",
            "cont_addr":  p["Contact_Address"]  if p else "",
            "cont_city":  p["Contact_City"]     if p else "",
            "post":       p["Contact_Post"]     if p else "",
            "cont_phone": p["Contact_Phone"]    if p else "",
            "occupation": p["Occupation"]       if p else "",
            "email_addr": p["Email_Address"]    if p else "",
        } if p else None

        ba_rows = db.session.execute(text("""
            SELECT ba.Acc_NO, ba.Acc_Name, ba.Acc_Bank, ba.Acc_BankBranch,
                   ba.BeneficiaryType, ba.ResidentStatus, ba.[Default],
                   b.[DESC] AS bank_name,
                   mc1.DESC_VALUE AS ben_type_label,
                   mc2.DESC_VALUE AS res_status_label
            FROM BeneficiaryAccount ba WITH(NOLOCK)
                LEFT JOIN UMFBANK b WITH(NOLOCK) ON ba.Acc_Bank=b.BANK_CODE
                LEFT JOIN MSTCOMBO mc1 WITH(NOLOCK)
                    ON mc1.VALUE=ba.BeneficiaryType AND mc1.CAT_VALUE='BENEFICIARY_TYPE'
                LEFT JOIN MSTCOMBO mc2 WITH(NOLOCK)
                    ON mc2.VALUE=ba.ResidentStatus AND mc2.CAT_VALUE='RESIDENT_STATUS'
            WHERE ba.BeneficiaryID=:sno AND ba.AccountType='C' AND ba.Category='SALES'
            ORDER BY ba.[Default] DESC
        """), {"sno": sales_no}).mappings().all()

        banks = [
            {
                "acc_no":           r["Acc_NO"]          or "",
                "acc_name":         r["Acc_Name"]        or "",
                "bank":             r["Acc_Bank"]        or "",
                "bank_name":        r["bank_name"]       or "",
                "bank_branch":      r["Acc_BankBranch"]  or "",
                "beneficiary_type": r["BeneficiaryType"] or "",
                "ben_type_label":   r["ben_type_label"]  or "",
                "resident_status":  r["ResidentStatus"]  or "",
                "res_status_label": r["res_status_label"] or "",
                "is_default":       bool(r["Default"]),
            }
            for r in ba_rows
        ]

        t = db.session.execute(text("""
            SELECT NPWP_Type, NPWP_No, NPWP_Detail, NPWP_Name, NPWP_Address,
                   NPWP_City, NPWP_Prov, NPWP_Start, TaxType, TaxRate, DPP,
                   PPN, DateStart, TFFrom, TFTo, UpdateBy, UpdateDate
            FROM BeneficiaryTax WITH(NOLOCK)
            WHERE BeneficiaryID=:sno AND Category='SALES'
        """), {"sno": sales_no}).mappings().first()

        tax = None
        if t:
            npwp_type = (t["NPWP_Type"] or "").strip()
            if npwp_type == "00":
                npwp_type = "00"
            t_updateby = (t["UpdateBy"] or "").strip()
            if t_updateby and len(t_updateby) == 4:
                t_updateby = _uname(t_updateby)
            tax = {
                "npwp_type":    npwp_type,
                "npwp_no":      t["NPWP_No"]      or "",
                "npwp_detail":  (t["NPWP_Detail"] or "").strip(),
                "npwp_nm":      t["NPWP_Name"]    or "",
                "npwp_addr":    t["NPWP_Address"] or "",
                "city":         t["NPWP_City"]    or "",
                "province":     t["NPWP_Prov"]    or "",
                "npwp_start":   str(t["NPWP_Start"] or ""),
                "pph":          str(t["TaxType"]  or ""),
                "rate":         str(t["TaxRate"]  or ""),
                "dpp":          str(t["DPP"]       or ""),
                "ppnsts":       str(t["PPN"]       or ""),
                "ppnstartdate": _fd(t["DateStart"]),
                "taxfree":      _fd(t["TFFrom"]),
                "taxfree2":     _fd(t["TFTo"]),
                "update_by":    t_updateby,
                "lastupdate":   _fd(t["UpdateDate"]),
                "is_saved":     True,
            }

        return jsonify({
            "main":       main,
            "pic":        pic,
            "banks":      banks,
            "tax":        tax,
            "has_pic":    pic is not None,
            "has_tax":    tax is not None,
        })

    except Exception:
        current_app.logger.exception("Sales entry get-edit-data error")
        return jsonify({"error": "Failed to load sales entry data"}), 500

@sales_entry_bp.route("/sales-entry", methods=["POST"])
@login_required
def create_sales_entry():
    
    emp_id   = session.get("emp_id")
    username = session.get("username", "")
    if not emp_id:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    try:
        b = request.get_json(force=True) or {}

        sal_type     = (b.get("sal_type")     or "").strip()
        broker_type  = (b.get("broker")       or "").strip()
        name         = (b.get("name")         or "").strip()
        status       = (b.get("status")       or "A").strip()
        branch_cd    = (b.get("branch")       or "").strip()
        cmo_name     = (b.get("cmo_name")     or "").strip()
        address      = (b.get("address")      or "").strip()
        city_sales   = (b.get("city_sales")   or "").strip()
        post         = (b.get("post")         or "").strip()
        phone        = (b.get("phone")        or "").strip()
        email_addr   = (b.get("email_addr")   or "").strip()
        fax          = (b.get("fax")          or "").strip()
        paid         = (b.get("paid")         or "1").strip()
        bd_occ       = (b.get("bd_occupation") or "").strip()
        nick_name    = (b.get("nick_name")    or "").strip()
        idcard       = (b.get("idcard")       or "").strip()
        gender       = (b.get("gender")       or "").strip()
        exp_date     = (b.get("exp_date")     or "0").strip()
        certain_per  = (b.get("certain_per")  or "").strip()

        if not name or not branch_cd or not sal_type:
            return jsonify({"success": False, "message": "Name, Branch, and Sales Type are required"}), 400

        if sal_type == "PR":
            dup = db.session.execute(text(
                "SELECT TOP 1 1 FROM CLFSALES WITH(NOLOCK) WHERE IDCARD=:idc AND [NAME]=:nm"
            ), {"idc": idcard, "nm": name}).first()
            if dup:
                return jsonify({"success": False, "message": "Sales already exists."}), 400

        id_valid_dt = None
        if exp_date == "1" and certain_per and sal_type == "PR":
            try:
                id_valid_dt = datetime.strptime(certain_per, "%d-%m-%Y").date()
                from datetime import date
                if id_valid_dt <= date.today():
                    return jsonify({"success": False, "message": "ID Valid Date must be in the future"}), 400
            except ValueError:
                return jsonify({"success": False, "message": "Invalid date format for ID Valid Date"}), 400

        prefix = branch_cd[:2]
        row = db.session.execute(text(
            "SELECT TOP 1 CAST(SALES_NO AS INT)+1 AS nxt FROM CLFSALES WITH(NOLOCK) "
            "WHERE LEFT(SALES_NO,2)=:p ORDER BY CAST(SALES_NO AS INT) DESC"
        ), {"p": prefix}).first()
        if row and row[0]:
            sales_no = str(row[0])
        else:
            sales_no = f"{prefix}0001"

        npwp_detail = "1" if gender == "M" else ""

        if sal_type == "PT" and broker_type:
            db.session.execute(text("""
                INSERT INTO BeneficiaryTax
                    (Category, BeneficiaryID, TFFrom, TFTo, PPN, DateStart,
                     TaxType, TaxRate, DPP, NPWP_No, NPWP_Name, NPWP_Address,
                     NPWP_City, NPWP_Prov, NPWP_Type, NPWP_Start, UpdateBy, UpdateDate)
                VALUES ('SALES',:sno,NULL,NULL,NULL,NULL,NULL,:paid,NULL,NULL,
                        NULL,NULL,NULL,NULL,:bt,NULL,:emp_id,SYSDATETIME())
            """), {"sno": sales_no, "paid": paid, "bt": broker_type, "emp_id": emp_id})
        else:
            db.session.execute(text("""
                INSERT INTO BeneficiaryTax
                    (Category, BeneficiaryID, TFFrom, TFTo, PPN, DateStart,
                     TaxType, TaxRate, DPP, NPWP_No, NPWP_Name, NPWP_Address,
                     NPWP_City, NPWP_Prov, NPWP_Type, NPWP_Start, UpdateBy, UpdateDate,
                     NPWP_Detail)
                VALUES ('SALES',:sno,NULL,NULL,NULL,NULL,NULL,:paid,NULL,NULL,
                        NULL,NULL,NULL,NULL,'',:NULL_val,:emp_id,SYSDATETIME(),:nd)
            """), {"sno": sales_no, "paid": paid, "NULL_val": None,
                   "emp_id": emp_id, "nd": npwp_detail or None})

        include_idcard = not (sal_type == "PT" and broker_type == "PT")

        db.session.execute(text("""
            INSERT INTO CLFSALES
                (SALES_NO, [NAME], ADDRESS, City, PHONE,
                 IDCARD, PAID, LastUpdate, UpdateBy,
                 BD_Occupation, ID_ValidDt, Status,
                 Sales_Type, Created_By, ID_CMO, BRANCH_CD, ZipCode, Sales_Nickname,
                 FAX, CREATE_DATE, Email_Address, Gender)
            VALUES
                (:sno, :nm, :addr, :city, :ph,
                 :idcard, :paid, NULL, NULL,
                 :bd_occ, :id_vdt, :status,
                 :st, :cb, :cmo, :br, :post, :nick,
                 :fax, SYSDATETIME(), :email, :gender)
        """), {
            "sno":    sales_no,
            "nm":     name,
            "addr":   address,
            "city":   city_sales,
            "ph":     phone,
            "idcard": idcard if include_idcard else None,
            "paid":   paid,
            "bd_occ": bd_occ if include_idcard else None,
            "id_vdt": id_valid_dt,
            "status": status,
            "st":     sal_type,
            "cb":     username,
            "cmo":    cmo_name,
            "br":     branch_cd,
            "post":   post,
            "nick":   nick_name if not include_idcard else None,
            "fax":    fax if not include_idcard else None,
            "email":  email_addr if include_idcard else None,
            "gender": gender,
        })

        db.session.commit()
        return jsonify({"success": True, "sales_no": sales_no, "broker": broker_type})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Sales entry create error")
        return jsonify({"success": False, "message": "Failed to create sales entry"}), 500

@sales_entry_bp.route("/sales-entry/<sales_no>", methods=["PUT"])
@login_required
def update_main(sales_no):
   
    emp_id   = session.get("emp_id")
    username = session.get("username", "")
    if not emp_id:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    try:
        b = request.get_json(force=True) or {}

        sal_type    = (b.get("sal_type")     or "").strip()
        broker_type = (b.get("broker")       or "").strip()
        name        = (b.get("name")         or "").strip()
        status      = (b.get("status")       or "A").strip()
        branch_cd   = (b.get("branch")       or "").strip()
        cmo_name    = (b.get("cmo_name")     or "").strip()
        address     = (b.get("address")      or "").strip()
        city_sales  = (b.get("city_sales")   or "").strip()
        post        = (b.get("post")         or "").strip()
        phone       = (b.get("phone")        or "").strip()
        email_addr  = (b.get("email_addr")   or "").strip()
        fax         = (b.get("fax")          or "").strip()
        paid        = (b.get("paid")         or "1").strip()
        bd_occ      = (b.get("bd_occupation") or "").strip()
        nick_name   = (b.get("nick_name")    or "").strip()
        idcard      = (b.get("idcard")       or "").strip()
        gender      = (b.get("gender")       or "").strip()
        exp_date    = (b.get("exp_date")     or "0").strip()
        certain_per = (b.get("certain_per")  or "").strip()
        create_by   = (b.get("create_by")    or username).strip()
        create_date = (b.get("create_date")  or "").strip()

        id_valid_dt = None
        if exp_date == "1" and certain_per:
            try:
                id_valid_dt = datetime.strptime(certain_per, "%d-%m-%Y").date()
            except ValueError:
                pass

        create_date_py = None
        if create_date:
            try:
                create_date_py = datetime.strptime(create_date, "%d-%m-%Y").date()
            except ValueError:
                pass

        include_idcard = not (sal_type == "PT" and broker_type == "PT")

        if include_idcard:
            db.session.execute(text("""
                UPDATE CLFSALES SET
                    [NAME]=:nm, ADDRESS=:addr, City=:city, PHONE=:ph,
                    IDCARD=:idcard, PAID=:paid, LastUpdate=SYSDATETIME(), UpdateBy=:uby,
                    BD_Occupation=:bd_occ, ID_ValidDt=:id_vdt, Status=:status,
                    Sales_Type=:st, Created_By=:cb, ID_CMO=:cmo,
                    BRANCH_CD=:br, ZipCode=:post, CREATE_DATE=:cd,
                    Email_Address=:email, Gender=:gender
                WHERE SALES_NO=:sno
            """), {
                "nm": name, "addr": address, "city": city_sales, "ph": phone,
                "idcard": idcard, "paid": paid, "uby": username,
                "bd_occ": bd_occ, "id_vdt": id_valid_dt, "status": status,
                "st": sal_type, "cb": create_by, "cmo": cmo_name,
                "br": branch_cd, "post": post, "cd": create_date_py,
                "email": email_addr, "gender": gender, "sno": sales_no,
            })
        else:
            db.session.execute(text("""
                UPDATE CLFSALES SET
                    [NAME]=:nm, ADDRESS=:addr, City=:city, PHONE=:ph,
                    PAID=:paid, LastUpdate=SYSDATETIME(), UpdateBy=:uby,
                    Status=:status, Sales_Type=:st, Created_By=:cb,
                    ID_CMO=:cmo, BRANCH_CD=:br, ZipCode=:post, CREATE_DATE=:cd,
                    Sales_Nickname=:nick, FAX=:fax, Gender=:gender
                WHERE SALES_NO=:sno
            """), {
                "nm": name, "addr": address, "city": city_sales, "ph": phone,
                "paid": paid, "uby": username, "status": status,
                "st": sal_type, "cb": create_by, "cmo": cmo_name,
                "br": branch_cd, "post": post, "cd": create_date_py,
                "nick": nick_name, "fax": fax, "gender": gender, "sno": sales_no,
            })

        if gender == "M":
            db.session.execute(text("""
                UPDATE BeneficiaryTax SET NPWP_Detail='1'
                WHERE BeneficiaryID=:sno AND Category='SALES'
            """), {"sno": sales_no})

        if sal_type == "PT" and broker_type:
            existing = db.session.execute(text(
                "SELECT TOP 1 1 FROM BeneficiaryTax WITH(NOLOCK) "
                "WHERE BeneficiaryID=:s AND Category='SALES'"
            ), {"s": sales_no}).first()
            if existing:
                db.session.execute(text("""
                    UPDATE BeneficiaryTax SET NPWP_Type=:bt
                    WHERE BeneficiaryID=:sno AND Category='SALES'
                """), {"bt": broker_type, "sno": sales_no})
            else:
                db.session.execute(text("""
                    INSERT INTO BeneficiaryTax
                        (Category,BeneficiaryID,NPWP_Type,UpdateBy,UpdateDate)
                    VALUES ('SALES',:sno,:bt,:emp_id,SYSDATETIME())
                """), {"sno": sales_no, "bt": broker_type, "emp_id": emp_id})

        db.session.commit()
        return jsonify({"success": True})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Sales entry update error")
        return jsonify({"success": False, "message": "Failed to update sales entry"}), 500

@sales_entry_bp.route("/sales-entry/<sales_no>/pic", methods=["POST", "PUT"])
@login_required
def save_pic(sales_no):
   
    emp_id   = session.get("emp_id")
    username = session.get("username", "")
    if not emp_id:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    try:
        b = request.get_json(force=True) or {}

        cont_name  = (b.get("cont_name")  or "").strip()
        cont_idcard= (b.get("cont_idcard") or "").strip()
        exp_date   = (b.get("exp_date")   or "0").strip()
        id_validdt = (b.get("id_validdt") or "").strip()
        cont_addr  = (b.get("cont_addr")  or "").strip()
        cont_city  = (b.get("cont_city")  or "").strip()
        post       = (b.get("post")       or "").strip()
        cont_phone = (b.get("cont_phone") or "").strip()
        occupation = (b.get("occupation") or "").strip()
        email_addr = (b.get("email_addr") or "").strip()

        id_valid_dt_py = None
        if exp_date == "1" and id_validdt:
            try:
                id_valid_dt_py = datetime.strptime(id_validdt, "%d-%m-%Y").date()
            except ValueError:
                pass

        exists = db.session.execute(text(
            "SELECT TOP 1 1 FROM CLFSALESPIC WITH(NOLOCK) WHERE SALES_NO=:s"
        ), {"s": sales_no}).first()

        if exists:
            db.session.execute(text("""
                UPDATE CLFSALESPIC SET
                    Contact_Name=:cn, Contact_IDCard=:ci,
                    Contact_IDValidDt=:cvdt, Contact_Address=:ca,
                    Contact_City=:cc, Contact_Post=:cp, Contact_Phone=:cph,
                    Occupation=:occ, Email_Address=:email
                WHERE SALES_NO=:sno
            """), {
                "cn": cont_name, "ci": cont_idcard, "cvdt": id_valid_dt_py,
                "ca": cont_addr, "cc": cont_city, "cp": post,
                "cph": cont_phone, "occ": occupation, "email": email_addr,
                "sno": sales_no,
            })
        else:
            db.session.execute(text("""
                INSERT INTO CLFSALESPIC
                    (SALES_NO, Contact_Name, Contact_IDCard, Contact_IDValidDt,
                     Contact_Address, Contact_City, Contact_Post, Contact_Phone,
                     Occupation, Email_Address)
                VALUES (:sno,:cn,:ci,:cvdt,:ca,:cc,:cp,:cph,:occ,:email)
            """), {
                "sno": sales_no, "cn": cont_name, "ci": cont_idcard,
                "cvdt": id_valid_dt_py, "ca": cont_addr, "cc": cont_city,
                "cp": post, "cph": cont_phone, "occ": occupation, "email": email_addr,
            })

        db.session.execute(text(
            "UPDATE CLFSALES SET LastUpdate=GETDATE(), UpdateBy=:u WHERE SALES_NO=:s"
        ), {"u": username, "s": sales_no})

        db.session.commit()
        return jsonify({"success": True})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Sales PIC save error")
        return jsonify({"success": False, "message": "Failed to save PIC"}), 500

@sales_entry_bp.route("/sales-entry/<sales_no>/bank-accounts")
@login_required
def get_bank_accounts(sales_no):
    try:
        rows = db.session.execute(text("""
            SELECT ba.Acc_NO, ba.Acc_Name, ba.Acc_Bank, ba.Acc_BankBranch,
                   ba.BeneficiaryType, ba.ResidentStatus, ba.[Default],
                   b.[DESC] AS bank_name,
                   mc1.DESC_VALUE AS ben_type_label,
                   mc2.DESC_VALUE AS res_status_label
            FROM BeneficiaryAccount ba WITH(NOLOCK)
                LEFT JOIN UMFBANK b WITH(NOLOCK) ON ba.Acc_Bank=b.BANK_CODE AND b.STATUS='1'
                LEFT JOIN MSTCOMBO mc1 WITH(NOLOCK)
                    ON mc1.VALUE=ba.BeneficiaryType AND mc1.CAT_VALUE='BENEFICIARY_TYPE'
                LEFT JOIN MSTCOMBO mc2 WITH(NOLOCK)
                    ON mc2.VALUE=ba.ResidentStatus AND mc2.CAT_VALUE='RESIDENT_STATUS'
            WHERE ba.BeneficiaryID=:sno AND ba.AccountType='C' AND ba.Category='SALES'
            ORDER BY ba.[Default] DESC
        """), {"sno": sales_no}).mappings().all()

        return jsonify([{
            "acc_no":           r["Acc_NO"]          or "",
            "acc_name":         r["Acc_Name"]        or "",
            "bank":             r["Acc_Bank"]        or "",
            "bank_name":        r["bank_name"]       or "",
            "bank_branch":      r["Acc_BankBranch"]  or "",
            "beneficiary_type": r["BeneficiaryType"] or "",
            "ben_type_label":   r["ben_type_label"]  or "",
            "resident_status":  r["ResidentStatus"]  or "",
            "res_status_label": r["res_status_label"] or "",
            "is_default":       bool(r["Default"]),
        } for r in rows])

    except Exception:
        current_app.logger.exception("Bank accounts list error")
        return jsonify([]), 500

@sales_entry_bp.route("/sales-entry/<sales_no>/bank-accounts", methods=["POST"])
@login_required
def add_bank_account(sales_no):
    user = session.get("username", "")
    if not user:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    try:
        b = request.get_json(force=True) or {}
        acc_no   = (b.get("acc_no")           or "").strip()
        acc_name = (b.get("acc_name")         or "").strip()
        bank     = (b.get("bank")             or "").strip()
        bank_br  = (b.get("bank_branch")      or "").strip()
        ben_type = (b.get("beneficiary_type") or "").strip()
        res_sts  = (b.get("resident_status")  or "").strip()
        is_def   = 1 if b.get("is_default") else 0

        if not acc_no:
            return jsonify({"success": False, "message": "Account number is required"}), 400

        if is_def:
            db.session.execute(text("""
                UPDATE BeneficiaryAccount SET [Default]=0
                WHERE BeneficiaryID=:sno AND Category='SALES' AND AccountType='C'
            """), {"sno": sales_no})

        db.session.execute(text("""
            INSERT INTO BeneficiaryAccount
                (Category, BeneficiaryID, Acc_NO, Acc_Name, Acc_Bank,
                 Acc_BankBranch, BeneficiaryType, ResidentStatus, [Default],
                 AccountType, UpdateBy, UpdateDate)
            VALUES ('Sales',:sno,:acc,:nm,:bk,:bkbr,:bt,:rs,:def,'C',:u,SYSDATETIME())
        """), {
            "sno": sales_no, "acc": acc_no, "nm": acc_name, "bk": bank,
            "bkbr": bank_br, "bt": ben_type, "rs": res_sts, "def": is_def, "u": user,
        })

        tv = _tv_copy(sales_no)
        if tv:
            db.session.execute(text("""
                INSERT INTO BeneficiaryAccount
                    (Category, BeneficiaryID, Acc_NO, Acc_Name, Acc_Bank,
                     Acc_BankBranch, BeneficiaryType, ResidentStatus, [Default],
                     AccountType, UpdateBy, UpdateDate)
                VALUES ('Sales',:tv,:acc,:nm,:bk,:bkbr,:bt,:rs,:def,'C',:u,SYSDATETIME())
            """), {
                "tv": tv, "acc": acc_no, "nm": acc_name, "bk": bank,
                "bkbr": bank_br, "bt": ben_type, "rs": res_sts, "def": is_def, "u": user,
            })

        db.session.commit()
        return jsonify({"success": True})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Bank account add error")
        return jsonify({"success": False, "message": "Failed to add bank account"}), 500

@sales_entry_bp.route("/sales-entry/<sales_no>/bank-accounts/<path:acc_no>", methods=["PUT"])
@login_required
def update_bank_account(sales_no, acc_no):
    user = session.get("username", "")
    if not user:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    try:
        b = request.get_json(force=True) or {}
        acc_name = (b.get("acc_name")         or "").strip()
        bank     = (b.get("bank")             or "").strip()
        bank_br  = (b.get("bank_branch")      or "").strip()
        ben_type = (b.get("beneficiary_type") or "").strip()
        res_sts  = (b.get("resident_status")  or "").strip()
        is_def   = 1 if b.get("is_default") else 0

        if (b.get("acc_no") or "").strip() not in ("", acc_no):
            return jsonify({"success": False,
                            "message": "Account No. cannot be changed. Delete and re-add."}), 400

        if is_def:
            db.session.execute(text("""
                UPDATE BeneficiaryAccount SET [Default]=0
                WHERE BeneficiaryID=:sno AND Category='SALES' AND AccountType='C'
            """), {"sno": sales_no})

        db.session.execute(text("""
            UPDATE BeneficiaryAccount SET
                Acc_Name=:nm, Acc_Bank=:bk, Acc_BankBranch=:bkbr,
                BeneficiaryType=:bt, ResidentStatus=:rs,
                [Default]=:def, UpdateBy=:u, UpdateDate=SYSDATETIME()
            WHERE BeneficiaryID=:sno AND Acc_NO=:acc AND Category='SALES'
        """), {
            "nm": acc_name, "bk": bank, "bkbr": bank_br, "bt": ben_type,
            "rs": res_sts, "def": is_def, "u": user, "sno": sales_no, "acc": acc_no,
        })

        tv = _tv_copy(sales_no)
        if tv:
            db.session.execute(text("""
                UPDATE BeneficiaryAccount SET
                    Acc_Name=:nm, Acc_Bank=:bk, Acc_BankBranch=:bkbr,
                    BeneficiaryType=:bt, ResidentStatus=:rs,
                    UpdateBy=:u, UpdateDate=SYSDATETIME()
                WHERE BeneficiaryID=:tv AND Acc_NO=:acc AND Category='SALES'
            """), {
                "nm": acc_name, "bk": bank, "bkbr": bank_br, "bt": ben_type,
                "rs": res_sts, "u": user, "tv": tv, "acc": acc_no,
            })

        db.session.commit()
        return jsonify({"success": True})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Bank account update error")
        return jsonify({"success": False, "message": "Failed to update bank account"}), 500

@sales_entry_bp.route("/sales-entry/<sales_no>/bank-accounts/<path:acc_no>", methods=["DELETE"])
@login_required
def delete_bank_account(sales_no, acc_no):
    if not session.get("username"):
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    try:
        db.session.execute(text(
            "DELETE FROM BeneficiaryAccount WHERE BeneficiaryID=:sno AND Acc_NO=:acc"
        ), {"sno": sales_no, "acc": acc_no})

        tv = _tv_copy(sales_no)
        if tv:
            db.session.execute(text(
                "DELETE FROM BeneficiaryAccount WHERE BeneficiaryID=:tv AND Acc_NO=:acc"
            ), {"tv": tv, "acc": acc_no})

        db.session.commit()
        return jsonify({"success": True})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Bank account delete error")
        return jsonify({"success": False, "message": "Failed to delete bank account"}), 500

@sales_entry_bp.route("/sales-entry/<sales_no>/tax", methods=["POST", "PUT"])
@login_required
def save_tax(sales_no):
    
    emp_id = session.get("emp_id")
    if not emp_id:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    try:
        b = request.get_json(force=True) or {}

        npwp_type   = (b.get("npwp_type")    or "").strip()
        npwp_no     = (b.get("npwp_no")      or "").strip()
        npwp_detail = (b.get("npwp_detail")  or "").strip()
        npwp_nm     = (b.get("npwp_nm")      or "").strip()
        npwp_addr   = (b.get("npwp_addr")    or "").strip()
        city        = (b.get("city")         or "").strip()
        province    = (b.get("province")     or "").strip()
        npwp_start  = (b.get("npwp_start")   or "").strip()
        ppnsts      = (b.get("ppnsts")       or "").strip()
        ppnstartdate= (b.get("ppnstartdate") or "").strip()
        taxfree     = (b.get("taxfree")      or "").strip()
        taxfree2    = (b.get("taxfree2")     or "").strip()
        sal_type    = (b.get("sal_type")     or "").strip()
        gender      = (b.get("gender")       or "").strip()

        if npwp_type != "00" and sal_type == "PR" and npwp_start:
            from datetime import date
            if int(npwp_start) < date.today().year:
                return jsonify({"success": False,
                                "message": "NPWP Start cannot be earlier than current year"}), 400

        if npwp_type == "PT":
            pph, rate, flatpersen, dpp = "2", "2", "2", "100"
        else:
            pph, rate, flatpersen, dpp = "1", "", "", "100"

        if gender == "M":
            npwp_detail = "1"

        npwp_no_db  = npwp_no      if npwp_type != "00" else None
        npwp_nm_db  = npwp_nm      if npwp_type != "00" else None
        npwp_addr_db= npwp_addr    if npwp_type != "00" else None
        city_db     = city         if npwp_type != "00" else None
        province_db = province     if npwp_type != "00" else None
        start_db    = npwp_start   if (npwp_type != "00" and npwp_type == "PR" and npwp_start) else None

        def parse_dt(s):
            if not s:
                return None
            try:
                return datetime.strptime(s, "%d-%m-%Y").date()
            except ValueError:
                return None

        ppn_start_db = parse_dt(ppnstartdate)
        tf_from_db   = parse_dt(taxfree)
        tf_to_db     = parse_dt(taxfree2)

        ppnsts_db = ppnsts if npwp_type == "PT" else None

        exists = db.session.execute(text(
            "SELECT TOP 1 1 FROM BeneficiaryTax WITH(NOLOCK) "
            "WHERE BeneficiaryID=:s AND Category='SALES'"
        ), {"s": sales_no}).first()

        params = {
            "sno": sales_no, "nt": npwp_type, "nn": npwp_no_db,
            "nd": npwp_detail or None, "nnm": npwp_nm_db, "na": npwp_addr_db,
            "nc": city_db, "np": province_db, "ns": start_db,
            "pph": pph, "rt": rate, "dpp": dpp,
            "ppn": ppnsts_db, "ppnsd": ppn_start_db,
            "tff": tf_from_db, "tft": tf_to_db,
            "emp_id": emp_id,
        }

        if exists:
            db.session.execute(text("""
                UPDATE BeneficiaryTax SET
                    NPWP_Type=:nt, NPWP_No=:nn, NPWP_Detail=:nd,
                    NPWP_Name=:nnm, NPWP_Address=:na, NPWP_City=:nc,
                    NPWP_Prov=:np, NPWP_Start=:ns, TaxType=:pph,
                    TaxRate=:rt, DPP=:dpp, PPN=:ppn, DateStart=:ppnsd,
                    TFFrom=:tff, TFTo=:tft,
                    UpdateBy=:emp_id, UpdateDate=SYSDATETIME()
                WHERE BeneficiaryID=:sno AND Category='SALES'
            """), params)
        else:
            db.session.execute(text("""
                INSERT INTO BeneficiaryTax
                    (Category, BeneficiaryID, NPWP_Type, NPWP_No, NPWP_Detail,
                     NPWP_Name, NPWP_Address, NPWP_City, NPWP_Prov, NPWP_Start,
                     TaxType, TaxRate, DPP, PPN, DateStart, TFFrom, TFTo,
                     UpdateBy, UpdateDate)
                VALUES ('SALES',:sno,:nt,:nn,:nd,:nnm,:na,:nc,:np,:ns,
                        :pph,:rt,:dpp,:ppn,:ppnsd,:tff,:tft,:emp_id,SYSDATETIME())
            """), params)

        db.session.commit()
        return jsonify({"success": True})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Sales tax save error")
        return jsonify({"success": False, "message": "Failed to save tax information"}), 500

def _resolve_file_sno(sales_no: str) -> str:
    row = db.session.execute(text(
        "SELECT Initial_Sales_No FROM CLFSALES WITH(NOLOCK) "
        "WHERE SALES_NO=:s AND IsSalesTV=1"
    ), {"s": sales_no}).first()
    return row[0] if row else sales_no

@sales_entry_bp.route("/sales-entry/<sales_no>/files")
@login_required
def get_files(sales_no):
   
    try:
        display_sno = _resolve_file_sno(sales_no)

        lainnya_row = db.session.execute(text(
            "SELECT TOP 1 KET FROM CLFSALES_FILE WITH(NOLOCK) "
            "WHERE SALES_NO=:s AND Cat='Sales' AND KET <> '' ORDER BY CreatedDate DESC"
        ), {"s": display_sno}).first()
        lainnya = lainnya_row[0] if lainnya_row else ""

        rows = db.session.execute(text("""
            SELECT ID, AWSKey, FILE_NM, FILE_EXT, DocumentType, KET, CreatedDate
            FROM CLFSALES_FILE WITH(NOLOCK)
            WHERE SALES_NO=:s AND Cat='Sales'
            ORDER BY DocumentType, CreatedDate DESC
        """), {"s": display_sno}).mappings().all()

        files: dict = {}
        for r in rows:
            dt = (r["DocumentType"] or "").strip()
            files.setdefault(dt, []).append({
                "id":           r["ID"],
                "aws_key":      r["AWSKey"]        or "",
                "file_nm":      r["FILE_NM"]       or "",
                "file_ext":     r["FILE_EXT"]      or "",
                "doc_type":     dt,
                "ket":          r["KET"]           or "",
                "created_date": _fd(r["CreatedDate"]),
                "download_url": _aws_presign(r["AWSKey"], f"{r['FILE_NM']}.{r['FILE_EXT']}") if r["AWSKey"] else None,
            })

        return jsonify({"files": files, "lainnya": lainnya})

    except Exception:
        current_app.logger.exception("Sales files list error")
        return jsonify({"files": {}, "lainnya": ""}), 500

@sales_entry_bp.route("/sales-entry/<sales_no>/files/<doc_type>", methods=["POST"])
@login_required
def upload_file(sales_no, doc_type):
  
    emp_id = session.get("emp_id")
    if not emp_id:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    if doc_type not in _DOC_PREFIX:
        return jsonify({"success": False, "message": f"Unknown document type: {doc_type}"}), 400

    files = request.files.getlist("file")
    if not files or all(f.filename == "" for f in files):
        return jsonify({"success": False, "message": "No files selected"}), 400

    lainnya = (request.form.get("lainnya") or "").strip()
    prefix  = _DOC_PREFIX[doc_type]

    try:
        inserted = []
        for f in files:
            if not f.filename:
                continue

            safe  = _sf(f.filename)
            parts = safe.rsplit(".", 1)
            ext   = parts[1].lower() if len(parts) == 2 else ""
            base  = parts[0]
            stored_nm = f"{prefix}{base}"

            aws_key = build_key("sales", sales_no, doc_type, f"{stored_nm}.{ext}")
            if not upload_fileobj(aws_key, f):
                return jsonify({"success": False, "message": "Upload failed"}), 500

            db.session.execute(text("""
                INSERT INTO CLFSALES_FILE
                    (SALES_NO, FILE_NM, FILE_EXT, AWSKey, DocumentType, Cat, KET, CreatedDate)
                VALUES (:sno, :nm, :ext, :key, :dt, 'Sales', :ket, SYSDATETIME())
            """), {
                "sno": sales_no, "nm": stored_nm, "ext": ext,
                "key": aws_key,  "dt": doc_type,
                "ket": lainnya if doc_type == "sales-other" else "",
            })
            inserted.append({"file_nm": stored_nm, "file_ext": ext, "aws_key": aws_key})

        db.session.commit()
        return jsonify({"success": True, "uploaded": inserted})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Sales file upload error")
        return jsonify({"success": False, "message": "Upload failed"}), 500

@sales_entry_bp.route("/sales-entry/<sales_no>/files/<int:file_id>", methods=["DELETE"])
@login_required
def delete_file(sales_no, file_id):

    if not session.get("emp_id"):
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    try:
        row = db.session.execute(text(
            "SELECT AWSKey FROM CLFSALES_FILE WITH(NOLOCK) WHERE ID=:id"
        ), {"id": file_id}).first()

        db.session.execute(text("DELETE FROM CLFSALES_FILE WHERE ID=:id"), {"id": file_id})

        if row and row[0]:
            delete_object(row[0])

        db.session.commit()
        return jsonify({"success": True})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Sales file delete error")
        return jsonify({"success": False, "message": "Delete failed"}), 500

@sales_entry_bp.route("/sales-entry/<sales_no>/files/<int:file_id>/download")
@login_required
def download_file(sales_no, file_id):

    try:
        row = db.session.execute(text(
            "SELECT AWSKey, FILE_NM, FILE_EXT FROM CLFSALES_FILE WITH(NOLOCK) WHERE ID=:id"
        ), {"id": file_id}).first()

        if not row or not row[0]:
            return jsonify({"error": "File not found"}), 404

        url = _aws_presign(row[0], f"{row[1]}.{row[2]}")
        if not url:
            return jsonify({"error": "Failed to generate download URL"}), 500

        return redirect(url)

    except Exception:
        current_app.logger.exception("Sales file download error")
        return jsonify({"error": "Download failed"}), 500

@sales_entry_bp.route("/sales-entry/<sales_no>/notes")
@login_required
def get_notes(sales_no):
    try:
        row = db.session.execute(text(
            "SELECT SALES_NOTES FROM CLFSALES WITH(NOLOCK) WHERE SALES_NO=:s"
        ), {"s": sales_no}).first()
        return jsonify({"notes": (row[0] or "") if row else ""})
    except Exception:
        current_app.logger.exception("Sales notes get error")
        return jsonify({"notes": ""}), 500

@sales_entry_bp.route("/sales-entry/<sales_no>/notes", methods=["POST", "PUT"])
@login_required
def save_notes(sales_no):
   
    username = session.get("username", "")
    if not session.get("emp_id"):
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    try:
        
        notes_raw = (request.get_json(force=True) or {}).get("notes", "")
        catatan = re.sub(r"<[^>]+>", "", notes_raw).replace("'", "`")

        db.session.execute(text("""
            UPDATE CLFSALES
            SET SALES_NOTES=:n, LastUpdate=GETDATE(), UpdateBy=:u
            WHERE SALES_NO=:s
        """), {"n": catatan, "u": username, "s": sales_no})

        tv = _tv_copy(sales_no)
        if tv:
            db.session.execute(text("""
                UPDATE CLFSALES
                SET SALES_NOTES=:n, LastUpdate=SYSDATETIME(), UpdateBy=:u
                WHERE SALES_NO=:tv
            """), {"n": catatan, "u": username, "tv": tv})

        db.session.commit()
        return jsonify({"success": True})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Sales notes save error")
        return jsonify({"success": False, "message": "Failed to save notes"}), 500