from flask import Blueprint, jsonify, request, current_app
from app import db
from sqlalchemy import text

list_karoseri_bp = Blueprint('list_karoseri', __name__, url_prefix='/MasterData')

@list_karoseri_bp.route('/api/list-karoseri')
def get_list_karoseri():
    model = request.args.get('model', '').strip()

    if not model:
        return jsonify({"data": [], "total": 0, "error": "model is required"}), 400

    try:
        result = db.session.execute(
            text("""
                SELECT
                    c.KAROSERI_DESC,
                    d.MODEL_NM
                FROM UMFKAROSERI c WITH(NOLOCK)
                LEFT JOIN UMFMODEL d WITH(NOLOCK) ON c.MODEL = d.MODEL
                WHERE c.MODEL = :model
                ORDER BY c.KAROSERI_DESC
            """),
            {"model": model}
        )
        data = [
            {
                "MODEL_NM":     row.MODEL_NM     or "-",
                "KAROSERI_DESC": row.KAROSERI_DESC or "-",
            }
            for row in result
        ]
        return jsonify({"data": data, "total": len(data)})

    except Exception as e:
        current_app.logger.exception("List karoseri error")
        return jsonify({"data": [], "total": 0, "error": str(e)}), 500


@list_karoseri_bp.route('/api/list-karoseri/model-options')
def get_model_options():
    try:
        result = db.session.execute(
            text("SELECT MODEL, MODEL_NM FROM UMFMODEL WITH(NOLOCK) ORDER BY MODEL")
        )
        return jsonify({
            "data": [{"MODEL": row.MODEL, "MODEL_NM": row.MODEL_NM} for row in result]
        })
    except Exception as e:
        current_app.logger.exception("Model options error")
        return jsonify({"data": [], "error": str(e)}), 500