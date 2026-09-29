from flask import Blueprint, jsonify, request, current_app
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text

employee_bp = Blueprint("employee", __name__, url_prefix="/Employee")

@employee_bp.route("/search-options")
@login_required
def get_search_options():
    try:
        rows = db.session.execute(
            text("""
                SELECT VALUE, DESC_VALUE
                FROM MSTCOMBO WITH(NOLOCK)
                WHERE CAT_VALUE = 'SEARCH_EMPLOYEE'
                ORDER BY VALUE
            """)
        ).mappings().all()
        return jsonify([{"value": r["VALUE"], "label": r["DESC_VALUE"]} for r in rows])
    except Exception:
        current_app.logger.exception("Employee search-options error")
        return jsonify([]), 500

@employee_bp.route("/branches")
@login_required
def get_branches():
    try:
        rows = db.session.execute(
            text("SELECT BRANCH_CD, BRANCH_NAME FROM UMFBRANCH WITH(NOLOCK) ORDER BY BRANCH_NAME")
        ).mappings().all()
        return jsonify([{"branch_cd": r["BRANCH_CD"], "branch_name": r["BRANCH_NAME"]} for r in rows])
    except Exception:
        current_app.logger.exception("Employee branches error")
        return jsonify([]), 500

@employee_bp.route("/divisions")
@login_required
def get_divisions():
    try:
        rows = db.session.execute(
            text("SELECT DIV_ID, DIV_DESC FROM UMF_DIV WITH(NOLOCK) ORDER BY DIV_DESC")
        ).mappings().all()
        return jsonify([{"div_id": r["DIV_ID"], "div_desc": r["DIV_DESC"]} for r in rows])
    except Exception:
        current_app.logger.exception("Employee divisions error")
        return jsonify([]), 500

@employee_bp.route("/positions")
@login_required
def get_positions():
    try:
        rows = db.session.execute(
            text("SELECT POSITION_ID, POSITION_DESC FROM UMF_EMPOS WITH(NOLOCK) ORDER BY POSITION_DESC")
        ).mappings().all()
        return jsonify([{"position_id": r["POSITION_ID"], "position_desc": r["POSITION_DESC"]} for r in rows])
    except Exception:
        current_app.logger.exception("Employee positions error")
        return jsonify([]), 500

@employee_bp.route("/search")
@login_required
def search_employees():
    search_by  = request.args.get("search_by",  "All")
    search_val = request.args.get("search_val", "").strip()

    try:
        rows = db.session.execute(
            text("EXEC USP_EMPLOYEE_DATA :search_by, :search_val"),
            {"search_by": search_by, "search_val": search_val},
        ).mappings().all()

        if not rows:
            return jsonify([])

        return jsonify([
            {
                "EmployeeID":        r["Employee_ID"]       or "",
                "Employee_Fullname": r["Employee_fullname"] or "",
                "Branch_Name":       r["BRANCH_NAME"]       or "",
                "Div_Desc":          r["Div_Desc"]          or "",
                "Position_Desc":     r["Position_Desc"]     or "",
            }
            for r in rows
        ])

    except Exception:
        current_app.logger.exception("Employee search error")
        return jsonify({"error": "Search failed"}), 500
    
@employee_bp.route('/detail')
@login_required
def get_employee_detail():
    search_by = request.args.get('search_by')
    search_val = request.args.get('search_val')

    try:
        result = db.session.execute(
            text("EXEC USP_EMPLOYEE_DATA :search_by, :search_val"),
            {"search_by": search_by, "search_val": search_val}
        )

        details = []
        for row in result:
            details.append({
                "EmployeeID": row.Employee_ID or "",
                "Employee_Fullname": row.Employee_fullname or "",
                "Branch_Name": str(row.BRANCH_NAME) or "",
                "Div_Desc": row.Div_Desc or "",
                "Position_Desc": row.Position_Desc or "",
            })

        return jsonify({"data": details})

    except Exception as e:
        current_app.logger.exception("Employee detail error")
        return jsonify({"error": "Failed to load details"}), 500

@employee_bp.route('/memo/details')
@login_required
def get_employee_memo():
    memo_from = request.args.get('memo_from')
    memo_to = request.args.get('memo_to')

    try:
        result = db.session.execute(
            text("EXEC USP_MEMO_EMPLOYEE :memo_from, :memo_to"),
            {"memo_from": memo_from, "memo_to": memo_to}
        )

        details = []
        for row in result:
            details.append({
                "memo_type_desc": row.Memo_Type_Desc or "",
                "memo_date": row.Memo_Date or "",
                "employee_id": row.Employee_Id or "",
                "memo_type": row.Memo_Type or "",
                "employee_fullname": row.Employee_Fullname or "",
                "branch_name": row.BRANCH_NAME or "",
                "div_desc": row.Div_Desc or "",
                "position_desc": row.Position_Desc or "",
                "facility": row.Facility or "",
                "new_branch": row.New_Branch or "",
                "new_position": row.New_Position or "",
                "email_off": row.Email_OffDate or "",
                "app_off": row.App_OffDate or "",
                "id": row.Id or "",
                "lewat": row.Lewat or "",
                "cancel": row.Cancel or "",
                "email": row.Email or ""
            })

        return jsonify({"data": details})

    except Exception as e:
        current_app.logger.exception("Invoice detail error")
        return jsonify({"error": "Failed to load details"}), 500