from flask import Blueprint, jsonify, request, current_app, session
from app import db
from sqlalchemy import text

menu_user_access_bp = Blueprint('menu', __name__, url_prefix='/SystemAdmin')

@menu_user_access_bp.route('/api/menu')
def get_menu():
    page  = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 25, type=int)

    try:
        count_query = text("SELECT COUNT(*) as total FROM APP_CAMMNLST WITH(NOLOCK)")
        total = db.session.execute(count_query).fetchone().total

        offset = (page - 1) * limit

        result = db.session.execute(text("""
            SELECT
                a.menu_id,
                a.menu_desc,
                a.menu_parent,
                a.[url],
                CASE
                    WHEN a.menu_parent = '0' THEN 'Parent'
                    ELSE b.menu_desc
                END AS parent_label
            FROM APP_CAMMNLST a WITH(NOLOCK)
            LEFT JOIN APP_CAMMNLST b WITH(NOLOCK) ON a.menu_parent = b.menu_id
            ORDER BY a.menu_id
            OFFSET :offset ROWS
            FETCH NEXT :limit ROWS ONLY
        """), {"offset": offset, "limit": limit})

        rows = [
            {
                "menu_id":      row.menu_id      or "",
                "menu_desc":    row.menu_desc    or "",
                "menu_parent":  row.menu_parent  or "",
                "parent_label": row.parent_label or row.menu_parent or "",
                "url":          row.url          or "",
            }
            for row in result.fetchall()
        ]

        return jsonify({
            "data":  rows,
            "total": total,
            "page":  page,
            "limit": limit,
            "akses": session.get("accesslevel", "")
        })

    except Exception as e:
        current_app.logger.exception("Menu list error")
        return jsonify({"data": [], "total": 0, "error": str(e)}), 500

@menu_user_access_bp.route('/api/menu/parent-options')
def get_parent_options():
    try:
        result = db.session.execute(
            text("SELECT menu_id, menu_desc FROM APP_CAMMNLST WITH(NOLOCK) ORDER BY menu_id")
        )
        options = [{"menu_id": row.menu_id, "menu_desc": row.menu_desc} for row in result]
        return jsonify({"data": options})
    except Exception as e:
        current_app.logger.exception("Parent options error")
        return jsonify({"data": [], "error": str(e)}), 500


@menu_user_access_bp.route('/api/menu', methods=['POST'])
def save_menu():
    data        = request.get_json()
    menu_parent = (data.get('menu_parent') or '').strip()
    menu_desc   = (data.get('menu_desc')   or '').strip()
    url         = (data.get('url')         or '').strip()

    errors = []
    if not menu_parent:
        errors.append("Menu Parent must not be empty")
    if not menu_desc:
        errors.append("Menu Description must not be empty")
    if errors:
        return jsonify({"success": False, "message": errors}), 400

    try:
       
        max_row = db.session.execute(
            text("SELECT MAX(menu_id) AS urutan FROM APP_CAMMNLST WHERE menu_parent = :parent"),
            {"parent": menu_parent}
        ).fetchone()

        urutan = max_row.urutan if max_row and max_row.urutan else None

        if urutan:
            parts   = urutan.split('.')
            counter = int(parts[-1]) + 1
        else:
            counter = 1

        if menu_parent == '0':
            menu_id_new = str(counter)
        else:
            menu_id_new = f"{menu_parent}.{counter}"

        db.session.execute(
            text("""
                INSERT INTO APP_CAMMNLST (menu_id, menu_desc, menu_parent, url)
                VALUES (:menu_id, :menu_desc, :menu_parent, :url)
            """),
            {
                "menu_id":     menu_id_new,
                "menu_desc":   menu_desc,
                "menu_parent": menu_parent,
                "url":         url,
            }
        )
        db.session.commit()
        return jsonify({"success": True, "message": "Successful", "menu_id": menu_id_new})

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Menu save error")
        return jsonify({"success": False, "message": "Failed", "error": str(e)}), 500


@menu_user_access_bp.route('/api/menu/<path:menu_id>', methods=['DELETE'])
def delete_menu(menu_id):
   
    try:
        children = db.session.execute(
            text("SELECT menu_id FROM APP_CAMMNLST WHERE menu_parent = :pid"),
            {"pid": menu_id}
        ).fetchall()

        for child in children:
            db.session.execute(
                text("DELETE FROM APP_CAMMNACC WHERE menu_id = :mid"),
                {"mid": child.menu_id}
            )
            db.session.execute(
                text("DELETE FROM APP_CAMMNLST WHERE menu_id = :mid"),
                {"mid": child.menu_id}
            )

        db.session.execute(
            text("DELETE FROM APP_CAMMNACC WHERE menu_id = :mid"), {"mid": menu_id}
        )
        db.session.execute(
            text("DELETE FROM APP_CAMMNLST WHERE menu_id = :mid"), {"mid": menu_id}
        )
        db.session.commit()
        return jsonify({"success": True, "message": "Successful"})

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Menu delete error")
        return jsonify({"success": False, "message": "Failed", "error": str(e)}), 500