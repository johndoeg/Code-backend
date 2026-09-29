import os
from datetime import datetime
from flask import Blueprint, jsonify, request, current_app, session
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text

employee_memo_bp = Blueprint("memo", __name__, url_prefix="/Employee")

def _ddmm_to_iso(v: str) -> str:
    if not v:
        return ""
    try:
        return datetime.strptime(v, "%d-%m-%Y").strftime("%Y-%m-%d")
    except ValueError:
        return ""

@employee_memo_bp.route("/role")
@login_required
def get_role():
    employee = session.get("emp_id", "")
    try:
        row = db.session.execute(
            text("SELECT Div_Id FROM EMPLOYEE_DATA WITH(NOLOCK) WHERE Employee_ID = :emp"),
            {"emp": employee},
        ).mappings().first()
        div_id = str(row["Div_Id"]).strip() if row else ""
        return jsonify({"is_hr": div_id == "11", "is_it": div_id == "15"})
    except Exception:
        current_app.logger.exception("Role error")
        return jsonify({"is_hr": False, "is_it": False})

@employee_memo_bp.route("/memo-types")
@login_required
def get_memo_types():
    try:
        rows = db.session.execute(
            text("SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE = 'MEMO_EMPLOYEE_TYPE' ORDER BY VALUE")
        ).mappings().all()
        return jsonify([{"value": r["VALUE"], "label": r["DESC_VALUE"]} for r in rows])
    except Exception:
        current_app.logger.exception("Memo types error")
        return jsonify([]), 500

@employee_memo_bp.route("/employees")
@login_required
def get_employees():
    try:
        rows = db.session.execute(
            text("SELECT EMPLOYEE_ID, EMPLOYEE_FULLNAME FROM EMPLOYEE_DATA WITH(NOLOCK) ORDER BY EMPLOYEE_FULLNAME")
        ).mappings().all()
        return jsonify([{"employee_id": r["EMPLOYEE_ID"], "employee_fullname": r["EMPLOYEE_FULLNAME"]} for r in rows])
    except Exception:
        current_app.logger.exception("Employees error")
        return jsonify([]), 500

@employee_memo_bp.route("/branches")
@login_required
def get_branches():
    try:
        rows = db.session.execute(
            text("SELECT BRANCH_CD, BRANCH_NAME FROM UMFBRANCH WITH(NOLOCK) WHERE BRANCH_CD <> '000' ORDER BY BRANCH_NAME")
        ).mappings().all()
        return jsonify([{"branch_cd": r["BRANCH_CD"], "branch_name": r["BRANCH_NAME"]} for r in rows])
    except Exception:
        current_app.logger.exception("Branches error")
        return jsonify([]), 500

@employee_memo_bp.route("/divisions")
@login_required
def get_divisions():
    try:
        rows = db.session.execute(
            text("SELECT DIV_ID, DIV_DESC FROM UMF_DIV WITH(NOLOCK) ORDER BY DIV_DESC")
        ).mappings().all()
        return jsonify([{"div_id": r["DIV_ID"], "div_desc": r["DIV_DESC"]} for r in rows])
    except Exception:
        current_app.logger.exception("Divisions error")
        return jsonify([]), 500

@employee_memo_bp.route("/positions")
@login_required
def get_positions():
    div_id = request.args.get("div_id", "")
    try:
        rows = db.session.execute(
            text("SELECT Position_Id, Position_Desc FROM UMF_EMPOS WITH(NOLOCK) WHERE Div_Id = :div ORDER BY Position_Desc"),
            {"div": div_id},
        ).mappings().all()
        return jsonify([{"position_id": r["Position_Id"], "position_desc": r["Position_Desc"]} for r in rows])
    except Exception:
        current_app.logger.exception("Positions error")
        return jsonify([]), 500

@employee_memo_bp.route("/positions-all")
@login_required
def get_positions_all():
    try:
        rows = db.session.execute(
            text("""
                SELECT a.Position_ID,
                       CONCAT(b.Div_Desc, ' - ', a.Position_Desc) AS Position_Desc
                FROM UMF_EMPOS a WITH(NOLOCK)
                    INNER JOIN UMF_DIV b WITH(NOLOCK) ON a.Div_Id = b.Div_Id
                ORDER BY b.Div_Desc, a.Position_Desc
            """)
        ).mappings().all()
        return jsonify([{"position_id": r["Position_ID"], "position_desc": r["Position_Desc"]} for r in rows])
    except Exception:
        current_app.logger.exception("Positions-all error")
        return jsonify([]), 500

@employee_memo_bp.route("/search")
@login_required
def search_memos():
    memo_from = request.args.get("memo_from", "")
    memo_to   = request.args.get("memo_to",   "")
    from_iso  = _ddmm_to_iso(memo_from)
    to_iso    = _ddmm_to_iso(memo_to)
    try:
        rows = db.session.execute(
            text("EXEC USP_MEMO_EMPLOYEE :from_dt, :to_dt"),
            {"from_dt": from_iso or None, "to_dt": to_iso or None},
        ).mappings().all()
        return jsonify([
            {
                "id":                str(r.get("Id",               "") or ""),
                "memo_type":         str(r.get("Memo_Type",        "") or ""),
                "memo_type_desc":    str(r.get("Memo_Type_Desc",   "") or ""),
                "memo_date":         str(r.get("Memo_Date",        "") or ""),
                "employee_id":       str(r.get("Employee_Id",      "") or ""),
                "employee_fullname": str(r.get("Employee_Fullname","") or ""),
                "branch_name":       str(r.get("BRANCH_NAME",      "") or ""),
                "div_desc":          str(r.get("Div_Desc",         "") or ""),
                "position_desc":     str(r.get("Position_Desc",    "") or ""),
                "facility":          str(r.get("Facility",         "") or ""),
                "email":             str(r.get("Email",            "") or ""),
                "new_branch":        str(r.get("New_Branch",       "") or ""),
                "new_position":      str(r.get("New_Position",     "") or ""),
                "email_off":         str(r.get("Email_OffDate",    "") or ""),
                "app_off":           str(r.get("App_OffDate",      "") or ""),
                "lewat":             str(r.get("Lewat",            "0") or "0"),
                "cancel":            str(r.get("Cancel",           "0") or "0"),
            }
            for r in rows
        ])
    except Exception:
        current_app.logger.exception("Memo search error")
        return jsonify({"error": "Search failed"}), 500

@employee_memo_bp.route("/employee/<employee_id>")
@login_required
def get_employee_detail(employee_id: str):
    try:
        row = db.session.execute(
            text("""
                SELECT a.Employee_ID, a.Employee_fullname, a.Branch_Cd,
                       a.Div_Id, a.Position_Id, b.Position_Desc
                FROM EMPLOYEE_DATA a WITH(NOLOCK)
                    INNER JOIN UMF_EMPOS b WITH(NOLOCK)
                        ON a.Div_Id = b.Div_Id AND a.Position_Id = b.Position_ID
                WHERE a.Employee_ID = :emp_id
            """),
            {"emp_id": employee_id},
        ).mappings().first()

        if not row:
            return jsonify({"error": "Not found"}), 404

        positions = db.session.execute(
            text("SELECT Position_Id, Position_Desc FROM UMF_EMPOS WITH(NOLOCK) WHERE Div_Id = :div ORDER BY Position_Desc"),
            {"div": row["Div_Id"]},
        ).mappings().all()

        return jsonify({
            "employee_id":       row["Employee_ID"]       or "",
            "employee_fullname": row["Employee_fullname"] or "",
            "branch_cd":         row["Branch_Cd"]         or "",
            "div_id":            row["Div_Id"]            or "",
            "position_id":       row["Position_Id"]       or "",
            "positions": [
                {"position_id": p["Position_Id"], "position_desc": p["Position_Desc"]}
                for p in positions
            ],
        })
    except Exception:
        current_app.logger.exception("Employee detail error")
        return jsonify({"error": "Failed"}), 500

@employee_memo_bp.route("/detail/<memo_id>")
@login_required
def get_memo_detail(memo_id: str):
    try:
        row = db.session.execute(
            text("""
                SELECT a.Employee_ID, a.Employee_fullname, a.Branch_Cd,
                       a.Div_Id, a.Position_Id, b.Position_Desc, a.memo_type,
                       FORMAT(a.memo_date,     'dd-MM-yyyy') AS memo_date,
                       a.facility_laptop, a.facility_email, a.facility_app,
                       a.new_branch, a.new_position,
                       FORMAT(a.email_offdate, 'dd-MM-yyyy') AS email_offdate,
                       FORMAT(a.app_offdate,   'dd-MM-yyyy') AS app_offdate
                FROM EMPLOYEE_MEMO a WITH(NOLOCK)
                    INNER JOIN UMF_EMPOS b WITH(NOLOCK)
                        ON a.Div_Id = b.Div_Id AND a.Position_Id = b.Position_ID
                WHERE a.id = :id
            """),
            {"id": memo_id},
        ).mappings().first()

        if not row:
            return jsonify({"error": "Not found"}), 404

        positions = db.session.execute(
            text("SELECT Position_Id, Position_Desc FROM UMF_EMPOS WITH(NOLOCK) WHERE Div_Id = :div ORDER BY Position_Desc"),
            {"div": row["Div_Id"]},
        ).mappings().all()

        return jsonify({
            "employee_id":       str(row["Employee_ID"]       or ""),
            "employee_fullname": str(row["Employee_fullname"] or ""),
            "branch_cd":         str(row["Branch_Cd"]         or ""),
            "div_id":            str(row["Div_Id"]            or ""),
            "position_id":       str(row["Position_Id"]       or ""),
            "memo_type":         str(row["memo_type"]         or ""),
            "memo_date":         str(row["memo_date"]         or ""),
            "facility_laptop":   str(row["facility_laptop"]   or "0"),
            "facility_email":    str(row["facility_email"]    or "0"),
            "facility_app":      str(row["facility_app"]      or "0"),
            "new_branch":        str(row["new_branch"]        or ""),
            "new_position":      str(row["new_position"]      or ""),
            "email_offdate":     str(row["email_offdate"]     or ""),
            "app_offdate":       str(row["app_offdate"]       or ""),
            "positions": [
                {"position_id": p["Position_Id"], "position_desc": p["Position_Desc"]}
                for p in positions
            ],
        })
    except Exception:
        current_app.logger.exception("Memo detail error")
        return jsonify({"error": "Failed"}), 500

@employee_memo_bp.route("/save", methods=["POST"])
@login_required
def save_memo():
    username = session.get("username", "")
    b = request.get_json(force=True) or {}

    memo_id           = b.get("memo_id",           "0")
    memo_type         = b.get("memo_type",         "")
    memo_dt           = _ddmm_to_iso(b.get("memo_dt", ""))
    employee_id       = b.get("employee_id",       "")
    employee_fullname = b.get("employee_fullname", "")
    branch_cd         = b.get("branch_cd",         "")
    div_id            = b.get("div_id",            "")
    position_id       = b.get("position_id",       "")
    facility_laptop   = int(b.get("facility_laptop", 0))
    facility_email    = int(b.get("facility_email",  0))
    facility_app      = int(b.get("facility_app",    0))
    new_branch        = b.get("new_branch",        "")
    new_position      = b.get("new_position",      "")
    email_off         = _ddmm_to_iso(b.get("email_off", "")) or None
    app_off           = _ddmm_to_iso(b.get("app_off",   "")) or None

    try:
        if memo_id == "0":
            db.session.execute(
                text("""
                    INSERT INTO EMPLOYEE_MEMO (
                        Memo_Type, Memo_Date, Employee_ID, Employee_Fullname,
                        Branch_Cd, Div_Id, Position_Id,
                        Facility_Laptop, Facility_Email, Facility_App,
                        New_Branch, New_Position, Email_OffDate, App_OffDate,
                        Create_By, Create_Dt
                    ) VALUES (
                        :memo_type, :memo_dt, :employee_id, :employee_fullname,
                        :branch_cd, :div_id, :position_id,
                        :facility_laptop, :facility_email, :facility_app,
                        :new_branch, :new_position,
                        NULLIF(:email_off, ''), NULLIF(:app_off, ''),
                        :username, GETDATE()
                    )
                """),
                {
                    "memo_type": memo_type, "memo_dt": memo_dt,
                    "employee_id": employee_id, "employee_fullname": employee_fullname,
                    "branch_cd": branch_cd, "div_id": div_id, "position_id": position_id,
                    "facility_laptop": facility_laptop, "facility_email": facility_email,
                    "facility_app": facility_app, "new_branch": new_branch,
                    "new_position": new_position, "email_off": email_off,
                    "app_off": app_off, "username": username,
                },
            )
        else:
            db.session.execute(
                text("""
                    UPDATE EMPLOYEE_MEMO SET
                        Memo_Date       = :memo_dt,
                        Facility_Laptop = :facility_laptop,
                        Facility_Email  = :facility_email,
                        Facility_App    = :facility_app,
                        New_Branch      = :new_branch,
                        New_Position    = :new_position,
                        Email_OffDate   = NULLIF(:email_off, ''),
                        App_OffDate     = NULLIF(:app_off,   ''),
                        Update_By       = :username,
                        Update_Dt       = GETDATE()
                    WHERE Id = :memo_id
                """),
                {
                    "memo_dt": memo_dt, "facility_laptop": facility_laptop,
                    "facility_email": facility_email, "facility_app": facility_app,
                    "new_branch": new_branch, "new_position": new_position,
                    "email_off": email_off, "app_off": app_off,
                    "username": username, "memo_id": memo_id,
                },
            )
        db.session.commit()

        raw_dt = b.get("memo_dt", "")
        if memo_id == "0":
            if memo_type == "NW":
                fac = (
                    ("Laptop"   if facility_laptop else "") +
                    ("Email"    if facility_email  else "") +
                    ("Aplikasi" if facility_app    else "")
                )
                msg = f"Memo On Boarding tgl {raw_dt} atas nama {employee_fullname} ({employee_id}) dengan fasilitas {fac}."
            elif memo_type == "RL":
                msg = f"Memo Relokasi tgl {raw_dt} atas nama {employee_fullname} ({employee_id}). Lebih jelasnya lihat di Employee Memo."
            else:
                msg = f"Memo Off Boarding tgl {raw_dt} atas nama {employee_fullname} ({employee_id}) dengan tgl off email {b.get('email_off')} dan tgl off aplikasi {b.get('app_off')}."
        else:
            jenis = "On Boarding" if memo_type == "NW" else ("Relokasi" if memo_type == "RL" else "Off Boarding")
            msg = f"Terdapat perubahan pada Memo {jenis} atas nama {employee_fullname} ({employee_id}). Lebih jelasnya lihat di Employee Memo."

        return jsonify({"success": True, "message": "Successful"})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Memo save error")
        return jsonify({"success": False, "message": "Save failed"}), 500

@employee_memo_bp.route("/cancel", methods=["POST"])
@login_required
def cancel_memo():
    username = session.get("username", "")
    b        = request.get_json(force=True) or {}
    memo_id       = b.get("memo_id",       "")
    cancel_reason = b.get("cancel_reason", "")
    try:
        db.session.execute(
            text("UPDATE EMPLOYEE_MEMO SET Cancel_Reason = :reason, Cancel_By = :by, Cancel_Dt = GETDATE() WHERE Id = :id"),
            {"reason": cancel_reason, "by": username, "id": memo_id},
        )
        db.session.commit()

        row = db.session.execute(
            text("""
                SELECT FORMAT(a.Memo_Date, 'dd-MM-yyyy') AS Memo_Date,
                       a.Employee_ID, a.Employee_Fullname, b.DESC_VALUE AS Memo_Type
                FROM EMPLOYEE_MEMO a WITH(NOLOCK)
                    INNER JOIN MSTCOMBO b WITH(NOLOCK)
                        ON a.Memo_Type = b.VALUE AND b.CAT_VALUE = 'MEMO_EMPLOYEE_TYPE'
                WHERE a.Id = :id
            """),
            {"id": memo_id},
        ).mappings().first()

        if row:
            msg = (
                f"Cancel Memo {row['Memo_Type']} tgl {row['Memo_Date']} "
                f"atas nama {row['Employee_Fullname']} ({row['Employee_ID']}) "
                f"dengan alasan {cancel_reason}."
            )

        return jsonify({"success": True, "message": "Successful"})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Memo cancel error")
        return jsonify({"success": False, "message": "Failed"}), 500

@employee_memo_bp.route("/email", methods=["POST"])
@login_required
def update_email():
    b       = request.get_json(force=True) or {}
    memo_id = b.get("memo_id", "")
    email   = b.get("email",   "")
    try:
        db.session.execute(
            text("UPDATE EMPLOYEE_MEMO SET Email = :email WHERE Id = :id"),
            {"email": email, "id": memo_id},
        )
        db.session.commit()

        row = db.session.execute(
            text("""
                SELECT a.Employee_ID, a.Employee_Fullname, a.Email
                FROM EMPLOYEE_MEMO a WITH(NOLOCK)
                INNER JOIN MSTCOMBO b WITH(NOLOCK)
                    ON a.Memo_Type = b.VALUE AND b.CAT_VALUE = 'MEMO_EMPLOYEE_TYPE'
                WHERE a.Id = :id
            """),
            {"id": memo_id},
        ).mappings().first()

        if row:
            msg = f"Alamat email dari karyawan baru atas nama {row['Employee_Fullname']} ({row['Employee_ID']}) adalah {row['Email']}."

        return jsonify({"success": True, "message": "Successful"})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Memo email error")
        return jsonify({"success": False, "message": "Failed"}), 500