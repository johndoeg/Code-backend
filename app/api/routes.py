from flask import Blueprint, jsonify, session, current_app
from sqlalchemy import text
from app import db

api_bp = Blueprint('api', __name__)

@api_bp.route('/menus')
def get_menus_flat():
    if not session.get('logged_in'):
        return jsonify([])

    accesslevel = session['accesslevel']

    try:
        acc_query = "SELECT menu_id FROM APP_CAMMNACC WHERE ACCESSCAM = :accesslevel"
        acc_result = db.session.execute(db.text(acc_query), {"accesslevel": accesslevel})
        allowed_menu_ids = {row[0] for row in acc_result.fetchall()}

        if not allowed_menu_ids:
            return jsonify([])

        expanded_menu_ids = set(allowed_menu_ids)
        for menu_id in allowed_menu_ids:
            parts = menu_id.split('.')
            for i in range(1, len(parts)):
                parent_id = '.'.join(parts[:i])
                expanded_menu_ids.add(parent_id)

        menu_query = """
            SELECT 
                menu_id, 
                ISNULL(menu_parent, '0') AS menu_parent,
                menu_desc, 
                url 
            FROM APP_CAMMNLST 
            ORDER BY Seq
        """
        menu_result = db.session.execute(db.text(menu_query))
        flat_menu = []

        for row in menu_result:
            menu_id, menu_parent, menu_desc, url = row
            if menu_id in expanded_menu_ids:
                flat_menu.append({
                    "menu_id": menu_id,
                    "menu_parent": menu_parent,
                    "menu_desc": menu_desc,
                    "url": url
                })

        return jsonify(flat_menu)

    except Exception as e:
        current_app.logger.exception("Menu fetch error")
        return jsonify([])