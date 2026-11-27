import urllib.parse
import urllib.request
from datetime import datetime

from flask import Blueprint, jsonify, request, current_app, session
from sqlalchemy import text

from app import db
from app.auth.decorators import login_required

employee_memo_bp = Blueprint("memo", __name__, url_prefix="/Employee")

DIV_HR = "11"
DIV_IT = "15"
MEMO_TYPES = ("NW", "RL", "RS")

def _s(value) -> str:
    if value is None:
        return ""
    return str(value).strip()

def _ddmm_to_iso(v: str) -> str:
    v = _s(v)
    if not v:
        return ""
    try:
        return datetime.strptime(v, "%d-%m-%Y").strftime("%Y-%m-%d")
    except ValueError:
        return ""

def _send_telegram(chat_id: str, message: str) -> None:
    token = current_app.config.get("TELEGRAM_BOT_TOKEN", "")
    if not token or not chat_id:
        return
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode()
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=10) as resp:
            resp.read()
    except Exception:
        current_app.logger.exception("Telegram send failed for %s", chat_id)

def _notify_division(div_id: str, message: str) -> None:
    try:
        rows = db.session.execute(
            text("SELECT TelegramID FROM EMPLOYEE_DATA WITH(NOLOCK) WHERE Div_Id = :div AND TelegramID <> ''"),
            {"div": div_id},
        ).mappings().all()
    except Exception:
        current_app.logger.exception("Telegram recipient lookup failed")
        return
    for r in rows:
        chat_id = _s(r["TelegramID"])
        if chat_id:
            _send_telegram(chat_id, message)

def _ddmm_to_sql(v: str) -> str:
    v = _s(v)
    if not v:
        return ""
    try:
        return datetime.strptime(v, "%d-%m-%Y").strftime("%Y%m%d")
    except ValueError:
        return ""

def _exec_proc_rows(sql: str, params: tuple) -> list:
    raw = db.session.connection().connection
    cursor = raw.cursor()
    try:
        cursor.execute(sql, params)
        while cursor.description is None:
            if not cursor.nextset():
                return []
        columns = [c[0] for c in cursor.description]
        return [dict(zip(columns, r)) for r in cursor.fetchall()]
    finally:
        cursor.close()

def _positions_by_div(div_id) -> list:
    rows = db.session.execute(
        text("SELECT Position_Id, Position_Desc FROM UMF_EMPOS WITH(NOLOCK) WHERE Div_Id = :div ORDER BY Position_Desc"),
        {"div": div_id},
    ).mappings().all()
    return [{"position_id": _s(r["Position_Id"]), "position_desc": r["Position_Desc"]} for r in rows]

@employee_memo_bp.route("/memo/role")
@login_required
def get_role():
    employee = session.get("emp_id", "")
    try:
        row = db.session.execute(
            text("SELECT Div_Id FROM EMPLOYEE_DATA WITH(NOLOCK) WHERE Employee_ID = :emp"),
            {"emp": employee},
        ).mappings().first()
        div_id = _s(row["Div_Id"]) if row else ""
        return jsonify({"is_hr": div_id == DIV_HR, "is_it": div_id == DIV_IT})
    except Exception:
        current_app.logger.exception("Role error")
        return jsonify({"is_hr": False, "is_it": False})

@employee_memo_bp.route("/memo/memo-types")
@login_required
def get_memo_types():
    try:
        rows = db.session.execute(
            text("SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE = 'MEMO_EMPLOYEE_TYPE'")
        ).mappings().all()
        return jsonify([{"value": _s(r["VALUE"]), "label": r["DESC_VALUE"]} for r in rows])
    except Exception:
        current_app.logger.exception("Memo types error")
        return jsonify([]), 500

@employee_memo_bp.route("/memo/employees")
@login_required
def get_employees():
    try:
        rows = db.session.execute(
            text("SELECT EMPLOYEE_ID, EMPLOYEE_FULLNAME FROM EMPLOYEE_DATA WITH(NOLOCK) ORDER BY EMPLOYEE_FULLNAME")
        ).mappings().all()
        return jsonify([{"employee_id": _s(r["EMPLOYEE_ID"]), "employee_fullname": r["EMPLOYEE_FULLNAME"]} for r in rows])
    except Exception:
        current_app.logger.exception("Employees error")
        return jsonify([]), 500

@employee_memo_bp.route("/memo/branches")
@login_required
def get_branches():
    try:
        rows = db.session.execute(
            text("SELECT BRANCH_CD, BRANCH_NAME FROM UMFBRANCH WITH(NOLOCK) WHERE BRANCH_CD <> '000'")
        ).mappings().all()
        return jsonify([{"branch_cd": _s(r["BRANCH_CD"]), "branch_name": r["BRANCH_NAME"]} for r in rows])
    except Exception:
        current_app.logger.exception("Branches error")
        return jsonify([]), 500

@employee_memo_bp.route("/memo/divisions")
@login_required
def get_divisions():
    try:
        rows = db.session.execute(
            text("SELECT DIV_ID, DIV_DESC FROM UMF_DIV WITH(NOLOCK) ORDER BY DIV_DESC")
        ).mappings().all()
        return jsonify([{"div_id": _s(r["DIV_ID"]), "div_desc": r["DIV_DESC"]} for r in rows])
    except Exception:
        current_app.logger.exception("Divisions error")
        return jsonify([]), 500

@employee_memo_bp.route("/memo/positions")
@login_required
def get_positions():
    div_id = request.args.get("div_id", "")
    try:
        return jsonify(_positions_by_div(div_id))
    except Exception:
        current_app.logger.exception("Positions error")
        return jsonify([]), 500

@employee_memo_bp.route("/memo/positions-all")
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
        return jsonify([{"position_id": _s(r["Position_ID"]), "position_desc": r["Position_Desc"]} for r in rows])
    except Exception:
        current_app.logger.exception("Positions-all error")
        return jsonify([]), 500

@employee_memo_bp.route("/memo/search")
@login_required
def search_memos():
    from_dt = _ddmm_to_sql(request.args.get("memo_from", ""))
    to_dt = _ddmm_to_sql(request.args.get("memo_to", ""))
    if not from_dt or not to_dt:
        from_dt, to_dt = "", ""
    try:
        rows = _exec_proc_rows("SET NOCOUNT ON; EXEC USP_MEMO_EMPLOYEE ?, ?", (from_dt, to_dt))
        return jsonify([
            {
                "id": _s(r.get("Id")),
                "memo_type": _s(r.get("Memo_Type")),
                "memo_type_desc": _s(r.get("Memo_Type_Desc")),
                "memo_date": _s(r.get("Memo_Date")),
                "employee_id": _s(r.get("Employee_Id")),
                "employee_fullname": _s(r.get("Employee_Fullname")),
                "branch_name": _s(r.get("BRANCH_NAME")),
                "div_desc": _s(r.get("Div_Desc")),
                "position_desc": _s(r.get("Position_Desc")),
                "facility": _s(r.get("Facility")),
                "email": _s(r.get("Email")),
                "new_branch": _s(r.get("New_Branch")),
                "new_position": _s(r.get("New_Position")),
                "email_off": _s(r.get("Email_OffDate")),
                "app_off": _s(r.get("App_OffDate")),
                "lewat": _s(r.get("Lewat")) or "0",
                "cancel": _s(r.get("Cancel")) or "0",
            }
            for r in rows
        ])
    except Exception as e:
        current_app.logger.exception("Memo search error from=%s to=%s", from_dt, to_dt)
        return jsonify({"error": str(e)}), 500

@employee_memo_bp.route("/memo/employee/<employee_id>")
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
            return jsonify({"error": "Data Not Found!"}), 404

        return jsonify({
            "employee_id": _s(row["Employee_ID"]),
            "employee_fullname": _s(row["Employee_fullname"]),
            "branch_cd": _s(row["Branch_Cd"]),
            "div_id": _s(row["Div_Id"]),
            "position_id": _s(row["Position_Id"]),
            "positions": _positions_by_div(row["Div_Id"]),
        })
    except Exception:
        current_app.logger.exception("Employee detail error")
        return jsonify({"error": "Failed"}), 500

@employee_memo_bp.route("/memo/detail/<memo_id>")
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
            return jsonify({"error": "Data Not Found!"}), 404

        return jsonify({
            "employee_id": _s(row["Employee_ID"]),
            "employee_fullname": _s(row["Employee_fullname"]),
            "branch_cd": _s(row["Branch_Cd"]),
            "div_id": _s(row["Div_Id"]),
            "position_id": _s(row["Position_Id"]),
            "memo_type": _s(row["memo_type"]),
            "memo_date": _s(row["memo_date"]),
            "facility_laptop": _s(row["facility_laptop"]) or "0",
            "facility_email": _s(row["facility_email"]) or "0",
            "facility_app": _s(row["facility_app"]) or "0",
            "new_branch": _s(row["new_branch"]),
            "new_position": _s(row["new_position"]),
            "email_offdate": _s(row["email_offdate"]),
            "app_offdate": _s(row["app_offdate"]),
            "positions": _positions_by_div(row["Div_Id"]),
        })
    except Exception:
        current_app.logger.exception("Memo detail error")
        return jsonify({"error": "Failed"}), 500

@employee_memo_bp.route("/memo/save", methods=["POST"])
@login_required
def save_memo():
    username = session.get("username", "")
    b = request.get_json(force=True, silent=True) or {}

    memo_id = _s(b.get("memo_id")) or "0"
    memo_type = _s(b.get("memo_type"))
    raw_dt = _s(b.get("memo_dt"))
    memo_dt = _ddmm_to_iso(raw_dt)
    employee_id = _s(b.get("employee_id"))
    employee_fullname = _s(b.get("employee_fullname"))
    branch_cd = _s(b.get("branch_cd"))
    div_id = _s(b.get("div_id"))
    position_id = _s(b.get("position_id"))
    facility_laptop = 1 if _s(b.get("facility_laptop")) == "1" else 0
    facility_email = 1 if _s(b.get("facility_email")) == "1" else 0
    facility_app = 1 if _s(b.get("facility_app")) == "1" else 0
    new_branch = _s(b.get("new_branch")) if memo_type == "RL" else ""
    new_position = _s(b.get("new_position")) if memo_type == "RL" else ""
    raw_email_off = _s(b.get("email_off")) if memo_type == "RS" else ""
    raw_app_off = _s(b.get("app_off")) if memo_type == "RS" else ""
    email_off = _ddmm_to_iso(raw_email_off) or None
    app_off = _ddmm_to_iso(raw_app_off) or None
    is_new = memo_id == "0"

    if is_new and (memo_type not in MEMO_TYPES or not employee_id or not employee_fullname
                   or not branch_cd or not div_id or not position_id):
        return jsonify({"success": False, "message": "Please fill all required fields."}), 400
    if not memo_dt:
        return jsonify({"success": False, "message": "Please fill all required fields."}), 400

    try:
        if is_new:
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
                        :new_branch, :new_position, :email_off, :app_off,
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
            current = db.session.execute(
                text("SELECT Memo_Type, Employee_ID, Employee_Fullname FROM EMPLOYEE_MEMO WITH(NOLOCK) WHERE Id = :id"),
                {"id": memo_id},
            ).mappings().first()
            if not current:
                return jsonify({"success": False, "message": "Data Not Found!"}), 404

            memo_type = _s(current["Memo_Type"])
            employee_id = _s(current["Employee_ID"])
            employee_fullname = _s(current["Employee_Fullname"])
            if memo_type != "RL":
                new_branch, new_position = "", ""
            if memo_type != "RS":
                email_off, app_off = None, None

            db.session.execute(
                text("""
                    UPDATE EMPLOYEE_MEMO SET
                        Memo_Date       = :memo_dt,
                        Facility_Laptop = :facility_laptop,
                        Facility_Email  = :facility_email,
                        Facility_App    = :facility_app,
                        New_Branch      = :new_branch,
                        New_Position    = :new_position,
                        Email_OffDate   = :email_off,
                        App_OffDate     = :app_off,
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
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Memo save error")
        return jsonify({"success": False, "message": "Save failed"}), 500

    if is_new:
        if memo_type == "NW":
            fasilitas = ", ".join(
                label for flag, label in (
                    (facility_laptop, "Laptop"), (facility_email, "Email"), (facility_app, "Aplikasi"),
                ) if flag
            )
            message = f"Memo On Boarding tgl {raw_dt} atas nama {employee_fullname} ({employee_id}) dengan fasilitas {fasilitas}."
        elif memo_type == "RL":
            message = f"Memo Relokasi tgl {raw_dt} atas nama {employee_fullname} ({employee_id}). Lebih jelasnya lihat di Employee Memo."
        else:
            message = (
                f"Memo Off Boarding tgl {raw_dt} atas nama {employee_fullname} ({employee_id}) "
                f"dengan tgl off email {raw_email_off} dan tgl off aplikasi {raw_app_off}."
            )
    else:
        jenis = "On Boarding" if memo_type == "NW" else ("Relokasi" if memo_type == "RL" else "Off Boarding")
        message = f"Terdapat perubahan pada Memo {jenis} atas nama {employee_fullname} ({employee_id}). Lebih jelasnya lihat di Employee Memo."

    _notify_division(DIV_IT, message)
    return jsonify({"success": True, "message": "Successful"})

@employee_memo_bp.route("/memo/cancel", methods=["POST"])
@login_required
def cancel_memo():
    username = session.get("username", "")
    b = request.get_json(force=True, silent=True) or {}
    memo_id = _s(b.get("memo_id"))
    cancel_reason = _s(b.get("cancel_reason"))

    if not memo_id or not cancel_reason:
        return jsonify({"success": False, "message": "Please enter a cancel reason."}), 400

    try:
        result = db.session.execute(
            text("UPDATE EMPLOYEE_MEMO SET Cancel_Reason = :reason, Cancel_By = :by, Cancel_Dt = GETDATE() WHERE Id = :id"),
            {"reason": cancel_reason, "by": username, "id": memo_id},
        )
        if result.rowcount == 0:
            db.session.rollback()
            return jsonify({"success": False, "message": "Failed"}), 404
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
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Memo cancel error")
        return jsonify({"success": False, "message": "Failed"}), 500

    if row:
        _notify_division(DIV_IT, (
            f"Cancel Memo {row['Memo_Type']} tgl {row['Memo_Date']} "
            f"atas nama {row['Employee_Fullname']} ({row['Employee_ID']}) "
            f"dengan alasan {cancel_reason}."
        ))
    return jsonify({"success": True, "message": "Successful"})

@employee_memo_bp.route("/memo/email", methods=["POST"])
@login_required
def update_email():
    b = request.get_json(force=True, silent=True) or {}
    memo_id = _s(b.get("memo_id"))
    email = _s(b.get("email"))

    if not memo_id or not email:
        return jsonify({"success": False, "message": "Please enter an email."}), 400

    try:
        result = db.session.execute(
            text("UPDATE EMPLOYEE_MEMO SET Email = :email WHERE Id = :id"),
            {"email": email, "id": memo_id},
        )
        if result.rowcount == 0:
            db.session.rollback()
            return jsonify({"success": False, "message": "Failed"}), 404
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
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Memo email error")
        return jsonify({"success": False, "message": "Failed"}), 500

    if row:
        _notify_division(DIV_HR, (
            f"Alamat email dari karyawan baru atas nama {row['Employee_Fullname']} "
            f"({row['Employee_ID']}) adalah {row['Email']}."
        ))
    return jsonify({"success": True, "message": "Successful"})