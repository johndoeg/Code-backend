from datetime import datetime

from flask import Blueprint, jsonify, request, current_app, session
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text

users_bp = Blueprint('users', __name__, url_prefix='/SystemAdmin')

MAX_PAGE_LIMIT = 200

def _is_admin() -> bool:
    return str(session.get("accesslevel", "")).strip().upper() == "ADMIN"

@users_bp.route('/users')
@login_required
def get_users():
    page       = request.args.get('page', 1, type=int)
    limit      = request.args.get('limit', 25, type=int)
    search_by  = request.args.get('search_by', '').strip()
    search_val = request.args.get('search_val', '').strip()

    page  = max(page, 1)
    limit = min(max(limit, 1), MAX_PAGE_LIMIT)

    try:
        where_clause = "1=1"
        params: dict = {}

        if search_val:
            if search_by == '2':
                where_clause = "a.USERNAME LIKE :like_val"
                params["like_val"] = f"%{search_val}%"
            elif search_by == '3':
                where_clause = "a.EMPLOYEE_ID = :exact_val"
                params["exact_val"] = search_val
            elif search_by == '4':
                where_clause = "a.ACCESSCAM LIKE :like_val"
                params["like_val"] = f"%{search_val}%"
            else:
                where_clause = (
                    "(a.USERNAME LIKE :like_val "
                    "OR a.FULLNAME LIKE :like_val "
                    "OR a.EMPLOYEE_ID = :exact_val)"
                )
                params["like_val"]  = f"%{search_val}%"
                params["exact_val"] = search_val

        total = db.session.execute(
            text(f"SELECT COUNT(*) AS total FROM APP_USRMST a WITH(NOLOCK) WHERE {where_clause}"),
            params
        ).fetchone().total

        offset = (page - 1) * limit
        result = db.session.execute(
            text(f"""
                SELECT
                    a.EMPLOYEE_ID,
                    a.USERNAME,
                    a.FULLNAME,
                    a.ACCESSCAM,
                    a.RECSTATUS,
                    b.BRANCH_NAME,
                    c.FULLNAME AS SUPERIOR,
                    CASE WHEN a.RECSTATUS = 'A' THEN 'Active' ELSE 'Non Active' END AS STATUS
                FROM APP_USRMST a WITH(NOLOCK)
                    LEFT JOIN UMFBRANCH  b WITH(NOLOCK) ON a.BRANCHCODE = b.BRANCH_CD
                    LEFT JOIN APP_USRMST c WITH(NOLOCK) ON a.SUPERIOR   = c.EMPLOYEE_ID
                WHERE {where_clause}
                ORDER BY a.USERNAME, a.EMPLOYEE_ID
                OFFSET :offset ROWS
                FETCH NEXT :limit ROWS ONLY
            """),
            {**params, "offset": offset, "limit": limit}
        )

        users = [
            {
                "EMPLOYEE_ID": row.EMPLOYEE_ID or "",
                "USERNAME":    row.USERNAME    or "",
                "FULLNAME":    row.FULLNAME    or "",
                "ACCESSCAM":   row.ACCESSCAM   or "",
                "BRANCH_NAME": row.BRANCH_NAME or "",
                "SUPERIOR":    row.SUPERIOR    or "",
                "STATUS":      row.STATUS      or "",
            }
            for row in result.fetchall()
        ]

        return jsonify({
            "data":  users,
            "total": total,
            "page":  page,
            "limit": limit,
            "akses": session.get("accesslevel", "")
        })

    except Exception as e:
        current_app.logger.exception("Users list error")
        return jsonify({"data": [], "total": 0, "error": str(e)}), 500

@users_bp.route('/users/branch-options')
@login_required
def get_branch_options():
    try:
        result = db.session.execute(
            text("SELECT BRANCH_CD, BRANCH_NAME FROM UMFBRANCH WITH(NOLOCK) ORDER BY BRANCH_NAME")
        )
        options = [{"branch_cd": row.BRANCH_CD, "branch_name": row.BRANCH_NAME} for row in result]
        return jsonify({"data": options})
    except Exception as e:
        current_app.logger.exception("Branch options error")
        return jsonify({"data": [], "error": str(e)}), 500

@users_bp.route('/users/access-group-options')
@login_required
def get_access_group_options():
    try:
        result = db.session.execute(
            text("SELECT DISTINCT ACCESSCAM FROM APP_CAMMNACC WITH(NOLOCK) ORDER BY ACCESSCAM")
        )
        options = [row.ACCESSCAM for row in result if row.ACCESSCAM]
        return jsonify({"data": options})
    except Exception as e:
        current_app.logger.exception("Access group options error")
        return jsonify({"data": [], "error": str(e)}), 500

@users_bp.route('/users/superior-options')
@login_required
def get_superior_options():
    try:
        result = db.session.execute(text("""
            SELECT EMPLOYEE_ID, FULLNAME
            FROM APP_USRMST WITH(NOLOCK)
            WHERE RECSTATUS = 'A' AND ACCESSCAM = 'CMH'
            ORDER BY FULLNAME
        """))
        options = [{"employee_id": row.EMPLOYEE_ID, "fullname": row.FULLNAME} for row in result]
        return jsonify({"data": options})
    except Exception as e:
        current_app.logger.exception("Superior options error")
        return jsonify({"data": [], "error": str(e)}), 500

@users_bp.route('/users/<string:employee_id>', methods=['GET'])
@login_required
def get_user_detail(employee_id):
    try:
        row = db.session.execute(text("""
            SELECT USERNAME, FULLNAME, BRANCHCODE, ACCESSCAM, SUPERIOR, RESIGN_DATE, RECSTATUS
            FROM APP_USRMST WITH(NOLOCK)
            WHERE EMPLOYEE_ID = :eid
        """), {"eid": employee_id}).fetchone()

        if not row:
            return jsonify({"success": False, "message": "User not found"}), 404

        data = {
            "employee_id": employee_id,
            "username":    row.USERNAME    or "",
            "fullname":    row.FULLNAME    or "",
            "branch_cd":   row.BRANCHCODE  or "",
            "accesscam":   row.ACCESSCAM   or "",
            "superior":    row.SUPERIOR    or "",
            "resign_date": row.RESIGN_DATE.strftime("%Y-%m-%d") if row.RESIGN_DATE else "",
            "status":      row.RECSTATUS   or "A",
        }
        return jsonify({"data": data, "akses": session.get("accesslevel", "")})

    except Exception as e:
        current_app.logger.exception("User detail error")
        return jsonify({"success": False, "message": str(e)}), 500

@users_bp.route('/users', methods=['POST'])
@login_required
def create_user():
    if not _is_admin():
        return jsonify({"success": False, "message": "Forbidden"}), 403

    data        = request.get_json(silent=True) or {}
    username    = (data.get('username')    or '').strip()
    employee_id = (data.get('employee_id') or '').strip()
    fullname    = (data.get('fullname')    or '').strip()
    branch_cd   = (data.get('branch_cd')   or '').strip()
    accesscam   = (data.get('accesscam')   or '').strip()
    superior    = (data.get('superior')    or '').strip()

    errors = []
    if not username:
        errors.append("Username must not be empty")
    if not employee_id:
        errors.append("Employee ID must not be empty")
    if not fullname:
        errors.append("Fullname must not be empty")
    if not branch_cd:
        errors.append("Branch must not be empty")
    if not accesscam:
        errors.append("Access Group must not be empty")

    if not errors:
        if db.session.execute(
            text("SELECT 1 FROM APP_USRMST WITH(NOLOCK) WHERE USERNAME = :u"),
            {"u": username}
        ).fetchone():
            errors.append("Username already exists")

        if db.session.execute(
            text("SELECT 1 FROM APP_USRMST WITH(NOLOCK) WHERE EMPLOYEE_ID = :e"),
            {"e": employee_id}
        ).fetchone():
            errors.append("Employee ID already exists")

    if errors:
        return jsonify({"success": False, "message": errors}), 400

    try:
        db.session.execute(
            text("""
                INSERT INTO APP_USRMST
                    (USERNAME, EMPLOYEE_ID, BRANCHCODE, FULLNAME, ACCESSCAM, SUPERIOR)
                VALUES
                    (:username, :employee_id, :branch_cd, :fullname, :accesscam, :superior)
            """),
            {
                "username":    username,
                "employee_id": employee_id,
                "branch_cd":   branch_cd,
                "fullname":    fullname,
                "accesscam":   accesscam,
                "superior":    superior or None,
            }
        )
        db.session.commit()
        return jsonify({"success": True, "message": "Successful"})

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("User create error")
        return jsonify({"success": False, "message": "Failed", "error": str(e)}), 500

@users_bp.route('/users/<string:employee_id>', methods=['PUT'])
@login_required
def update_user(employee_id):
    if not _is_admin():
        return jsonify({"success": False, "message": "Forbidden"}), 403

    data        = request.get_json(silent=True) or {}
    fullname    = (data.get('fullname')    or '').strip()
    branch_cd   = (data.get('branch_cd')   or '').strip()
    accesscam   = (data.get('accesscam')   or '').strip()
    superior    = (data.get('superior')    or '').strip()
    resign_date = (data.get('resign_date') or '').strip()

    errors = []
    if not fullname:
        errors.append("Fullname must not be empty")
    if not branch_cd:
        errors.append("Branch must not be empty")
    if not accesscam:
        errors.append("Access Group must not be empty")

    resign_dt = None
    if resign_date:
        try:
            resign_dt = datetime.strptime(resign_date, "%Y-%m-%d").date()
        except ValueError:
            errors.append("Resign Date must be in YYYY-MM-DD format")

    if errors:
        return jsonify({"success": False, "message": errors}), 400

    try:
        result = db.session.execute(
            text("""
                UPDATE APP_USRMST
                SET BRANCHCODE  = :branch_cd,
                    FULLNAME    = :fullname,
                    ACCESSCAM   = :accesscam,
                    SUPERIOR    = :superior,
                    RESIGN_DATE = :resign_date
                WHERE EMPLOYEE_ID = :employee_id
            """),
            {
                "branch_cd":   branch_cd,
                "fullname":    fullname,
                "accesscam":   accesscam,
                "superior":    superior or None,
                "resign_date": resign_dt,
                "employee_id": employee_id,
            }
        )
        if result.rowcount == 0:
            db.session.rollback()
            return jsonify({"success": False, "message": "User not found"}), 404

        db.session.commit()
        return jsonify({"success": True, "message": "Successful"})

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("User update error")
        return jsonify({"success": False, "message": "Failed", "error": str(e)}), 500

@users_bp.route('/users/<string:employee_id>', methods=['DELETE'])
@login_required
def delete_user(employee_id):
    if not _is_admin():
        return jsonify({"success": False, "message": "Forbidden"}), 403

    try:
        result = db.session.execute(
            text("DELETE FROM APP_USRMST WHERE EMPLOYEE_ID = :eid"),
            {"eid": employee_id}
        )
        if result.rowcount == 0:
            db.session.rollback()
            return jsonify({"success": False, "message": "User not found"}), 404

        db.session.commit()
        return jsonify({"success": True, "message": "Successful"})

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("User delete error")
        return jsonify({"success": False, "message": "Failed", "error": str(e)}), 500