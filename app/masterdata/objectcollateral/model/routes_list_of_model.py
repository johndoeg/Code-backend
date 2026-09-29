from flask import Blueprint, jsonify, request, current_app
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text

list_model_bp = Blueprint('list_model', __name__, url_prefix='/MasterData')

@list_model_bp.route('/list-model')
@login_required
def get_list_model():
    try:
        result = db.session.execute(
            text("SELECT MODEL_NM FROM UMFMODEL WITH(NOLOCK) ORDER BY MODEL_NM")
        )
        data = [{"MODEL_NM": row.MODEL_NM or "-"} for row in result]
        return jsonify({"data": data, "total": len(data)})

    except Exception as e:
        current_app.logger.exception("List model error")
        return jsonify({"data": [], "total": 0, "error": str(e)}), 500