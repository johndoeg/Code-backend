from flask import Blueprint, jsonify, current_app
from sqlalchemy import text
from app import db 
from app.auth.decorators import login_required

common_bp = Blueprint('common', __name__, url_prefix='/Common')

@common_bp.route('/branches', methods=['GET'])
@login_required
def get_branches():
    try:
        data_query = text("""
            SELECT BRANCH_CD, BRANCH_NAME
            FROM UMFBRANCH WITH(NOLOCK)
            WHERE IsDeleted = 0
            ORDER BY BRANCH_CD ASC
        """)
        
        result = db.session.execute(data_query)
        branches = [
            {
                "BRANCH_CD": row.BRANCH_CD or "",
                "BRANCH_NAME": row.BRANCH_NAME or ""
            }
            for row in result
        ]
        
        return jsonify({
            "success": True,
            "data": branches,
            "total": len(branches)
        })
        
    except ValueError as e:
        current_app.logger.error(f"Invalid parameter in branches endpoint: {e}")
        return jsonify({"success": False, "message": "Invalid parameter value"}), 400
    except Exception:
        current_app.logger.exception("Failed to fetch branches")
        return jsonify({"success": False, "message": "Failed to fetch branches"}), 500
    
@common_bp.route('/combo/<category>', methods=['GET'])
@login_required
def get_combos(category: str):
    try:
        category = category.strip()
        if not category:
            return jsonify({"success": False, "message": "Category parameter is required"}), 400
        
        data_query = text("""
            SELECT VALUE, DESC_VALUE 
            FROM MSTCOMBO WITH(NOLOCK)
            WHERE CAT_VALUE = :category
            ORDER BY DESC_VALUE ASC
        """)
        
        result = db.session.execute(data_query, {"category": category})
        combos = [
            {
                "VALUE": row.VALUE or "",
                "DESC_VALUE": row.DESC_VALUE or ""
            }
            for row in result
        ]
        
        return jsonify({
            "success": True,
            "data": combos,
            "total": len(combos)
        })
        
    except Exception:
        current_app.logger.exception(f"Failed to fetch combos for category: {category}")
        return jsonify({"success": False, "message": "Failed to fetch combo data"}), 500