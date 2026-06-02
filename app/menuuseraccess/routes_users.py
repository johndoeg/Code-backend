from flask import Blueprint, jsonify, request, current_app, session
from app import db
from sqlalchemy import text

users_bp = Blueprint('users', __name__, url_prefix='/SystemAdmin')

@users_bp.route('/api/users')
def get_users():
    page       = request.args.get('page', 1, type=int)
    limit      = request.args.get('limit', 25, type=int)
    search_by  = request.args.get('search_by', '').strip()
    search_val = request.args.get('search_val', '').strip()

    try:
        where_clause = "1=1"
        params: dict = {}

        if search_val:
            if search_by == '2':
                where_clause = "a.USERNAME LIKE :search_val"
                params["search_val"] = f"%{search_val}%"
            elif search_by == '3':
                where_clause = "a.EMPLOYEE_ID = :search_val"
                params["search_val"] = search_val
            elif search_by == '4':
                where_clause = "a.ACCESSCAM LIKE :search_val"
                params["search_val"] = f"%{search_val}%"

        base_query = f"""
            FROM APP_USRMST a WITH(NOLOCK)
            LEFT JOIN UMFBRANCH b WITH(NOLOCK) ON a.BRANCHCODE = b.BRANCH_CD
            LEFT JOIN APP_USRMST c WITH(NOLOCK) ON a.SUPERIOR  = c.EMPLOYEE_ID
            WHERE {where_clause}
        """

        count_result = db.session.execute(
            text(f"SELECT COUNT(*) as total {base_query}"), params
        )
        total = count_result.fetchone().total

        offset = (page - 1) * limit
        data_query = text(f"""
            SELECT
                a.EMPLOYEE_ID,
                a.USERNAME,
                a.FULLNAME,
                a.ACCESSCAM,
                a.RECSTATUS,
                b.BRANCH_NAME,
                c.FULLNAME  AS SUPERIOR,
                CASE WHEN a.RECSTATUS = 'A' THEN 'Active' ELSE 'Non Active' END AS STATUS
            {base_query}
            ORDER BY a.USERNAME
            OFFSET :offset ROWS
            FETCH NEXT :limit ROWS ONLY
        """)
        result = db.session.execute(
            data_query, {**params, "offset": offset, "limit": limit}
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

@users_bp.route('/api/users/<string:employee_id>', methods=['DELETE'])
def delete_user(employee_id):
    try:
        db.session.execute(
            text("DELETE FROM APP_USRMST WHERE EMPLOYEE_ID = :eid"),
            {"eid": employee_id}
        )
        db.session.commit()
        return jsonify({"success": True, "message": "Successful"})
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("User delete error")
        return jsonify({"success": False, "message": "Failed", "error": str(e)}), 500