from flask import Blueprint, jsonify, request, current_app, session
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text

uacc_bp = Blueprint('uacc', __name__, url_prefix='/SystemAdmin')

USER_RIGHT_LABELS = {
    0: "None",
    1: "View",
    3: "Add & Edit",
    7: "Delete",
    9: "Full",
}

@uacc_bp.route('/uacc/access-options')
@login_required
def get_access_options():
    try:
        result = db.session.execute(
            text("SELECT DISTINCT ACCESSCAM FROM APP_CAMMNACC WITH(NOLOCK) ORDER BY ACCESSCAM")
        )
        return jsonify({"data": [row.ACCESSCAM for row in result.fetchall()]})
    except Exception as e:
        current_app.logger.exception("Access options error")
        return jsonify({"data": [], "error": str(e)}), 500

@uacc_bp.route('/uacc/menu-rights')
@login_required
def get_menu_rights():
   
    accesscam = request.args.get('accesscam', '').strip()
    if not accesscam:
        return jsonify({"data": [], "error": "accesscam is required"}), 400

    try:
        result = db.session.execute(text("""
            SELECT
                m.menu_id,
                m.menu_desc,
                ISNULL(a.userright, 0) AS userright
            FROM APP_CAMMNLST m WITH(NOLOCK)
                LEFT JOIN APP_CAMMNACC a WITH(NOLOCK)
                    ON a.menu_id = m.menu_id AND a.ACCESSCAM = :accesscam
            WHERE m.url <> ''
            ORDER BY m.menu_id
        """), {"accesscam": accesscam})

        data = [
            {
                "menu_id":   row.menu_id,
                "menu_desc": row.menu_desc,
                "userright": int(row.userright),
            }
            for row in result.fetchall()
        ]
        return jsonify({
            "data":  data,
            "akses": session.get("accesslevel", "")
        })

    except Exception as e:
        current_app.logger.exception("Menu rights error")
        return jsonify({"data": [], "error": str(e)}), 500

@uacc_bp.route('/uacc/save', methods=['POST'])
@login_required
def save_uacc():
    
    body      = request.get_json()
    accesscam = (body.get('accesscam') or '').strip()
    rights    = body.get('rights', [])

    if not accesscam:
        return jsonify({"success": False, "message": ["Please select Access Level"]}), 400

    try:
        for item in rights:
            menu_id   = (item.get('menu_id')   or '').strip()
            userright = int(item.get('userright', 0))

            if not menu_id:
                continue

            existing = db.session.execute(text("""
                SELECT 1 FROM APP_CAMMNACC WITH(NOLOCK)
                WHERE ACCESSCAM = :ac AND menu_id = :mid
            """), {"ac": accesscam, "mid": menu_id}).fetchone()

            if existing:
                if userright == 0:
                    db.session.execute(text("""
                        DELETE FROM APP_CAMMNACC
                        WHERE ACCESSCAM = :ac AND menu_id = :mid
                    """), {"ac": accesscam, "mid": menu_id})
                else:
                    db.session.execute(text("""
                        UPDATE APP_CAMMNACC
                        SET userright = :ur
                        WHERE ACCESSCAM = :ac AND menu_id = :mid
                    """), {"ur": userright, "ac": accesscam, "mid": menu_id})
            else:
                if userright != 0:
                    db.session.execute(text("""
                        INSERT INTO APP_CAMMNACC (ACCESSCAM, menu_id, userright)
                        VALUES (:ac, :mid, :ur)
                    """), {"ac": accesscam, "mid": menu_id, "ur": userright})

        db.session.commit()
        return jsonify({"success": True, "message": "Successful"})

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("User access save error")
        return jsonify({"success": False, "message": "Failed", "error": str(e)}), 500