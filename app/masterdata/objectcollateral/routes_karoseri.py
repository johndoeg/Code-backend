from flask import Blueprint, jsonify, request, current_app, session
from app import db
from sqlalchemy import text

karoseri_bp = Blueprint('karoseri', __name__, url_prefix='/MasterData')

@karoseri_bp.route('/api/karoseri')
def get_karoseri():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 25, type=int)
    search_val = request.args.get('search_val', '').strip()
    search_by = request.args.get('search_by', '').strip()

    try:
        if search_val:
            if search_by == '1':
                where_clause = "b.MODEL_NM LIKE :search_val"
                search_val = f"%{search_val}%"
            elif search_by == '2':
                where_clause = "a.KAROSERI_DESC LIKE :search_val"
                search_val = f"%{search_val}%"
            else:
                where_clause = "b.MODEL_NM LIKE :search_val OR a.KAROSERI_DESC LIKE :search_val"
                search_val = f"%{search_val}%"
        else:
            where_clause = "1=1"

        count_params = {"search_val": search_val} if search_val else {}

        count_query = text(f"""
            SELECT COUNT(*) as total
            FROM UMFKAROSERI a WITH(NOLOCK)
            LEFT JOIN UMFMODEL b WITH(NOLOCK) ON a.MODEL = b.MODEL
            WHERE {where_clause}
        """)
        total = db.session.execute(count_query, count_params).fetchone().total

        offset = (page - 1) * limit
        data_query = text(f"""
            SELECT
                a.ID_Key,
                a.KAROSERI,
                a.KAROSERI_DESC,
                a.isActive,
                b.MODEL,
                b.MODEL_NM
            FROM UMFKAROSERI a WITH(NOLOCK)
            LEFT JOIN UMFMODEL b WITH(NOLOCK) ON a.MODEL = b.MODEL
            WHERE {where_clause}
            ORDER BY a.MODEL
            OFFSET :offset ROWS
            FETCH NEXT :limit ROWS ONLY
        """)
        data_params = {**count_params, "offset": offset, "limit": limit}
        result = db.session.execute(data_query, data_params)

        karoseri_data = []
        for row in result:
            karoseri_data.append({
                "ID_Key":       row.ID_Key or "",
                "KAROSERI":     row.KAROSERI or "",
                "KAROSERI_DESC": row.KAROSERI_DESC or "",
                "isActive":     bool(row.isActive),
                "MODEL":        row.MODEL or "",
                "MODEL_NM":     row.MODEL_NM or "",
            })

        return jsonify({
            "data": karoseri_data,
            "total": total,
            "page": page,
            "limit": limit,
            "akses": session.get("accesslevel", "")
        })

    except Exception as e:
        current_app.logger.exception("Karoseri list error")
        return jsonify({"data": [], "total": 0, "error": str(e)}), 500

@karoseri_bp.route('/api/karoseri/next-code')
def get_next_karoseri_code():
    model = request.args.get('model', '').strip()
    if not model:
        return jsonify({"error": "model is required"}), 400

    try:
        query = text("""
            SELECT ISNULL(MAX(CONVERT(int, KAROSERI)), 0) + 1 AS NEXT_KAROSERI
            FROM UMFKAROSERI WITH(NOLOCK)
            WHERE MODEL = :model
        """)
        result = db.session.execute(query, {"model": model}).fetchone()
        next_code = str(result.NEXT_KAROSERI).zfill(2)

        return jsonify({"next_code": next_code})

    except Exception as e:
        current_app.logger.exception("Get next karoseri code error")
        return jsonify({"error": str(e)}), 500


@karoseri_bp.route('/api/karoseri/models')
def get_model_options():
    
    try:
        result = db.session.execute(
            text("SELECT MODEL, MODEL_NM FROM UMFMODEL WITH(NOLOCK) ORDER BY MODEL")
        )
        models = [{"MODEL": row.MODEL, "MODEL_NM": row.MODEL_NM} for row in result]
        return jsonify({"data": models})

    except Exception as e:
        current_app.logger.exception("Model options error")
        return jsonify({"data": [], "error": str(e)}), 500


@karoseri_bp.route('/api/karoseri', methods=['POST'])
def save_karoseri():
    data = request.get_json()
    model        = (data.get('model') or '').strip()
    karoseri     = (data.get('karoseri') or '').strip()
    karoseri_desc = (data.get('karoseri_desc') or '').strip()
    is_active    = data.get('isActive')

    errors = []
    if not model:
        errors.append("Model must not be empty")
    if not karoseri:
        errors.append("Karoseri Code must not be empty")
    if not karoseri_desc:
        errors.append("Karoseri Description must not be empty")
    if is_active is None or is_active == '':
        errors.append("Status must be chosen")
    if errors:
        return jsonify({"success": False, "message": errors}), 400

    try:
        db.session.execute(
            text("""
                INSERT INTO UMFKAROSERI (MODEL, KAROSERI, KAROSERI_DESC, isActive)
                VALUES (:model, :karoseri, :karoseri_desc, :is_active)
            """),
            {
                "model":        model,
                "karoseri":     karoseri,
                "karoseri_desc": karoseri_desc,
                "is_active":    int(is_active),
            }
        )
        db.session.commit()
        return jsonify({"success": True, "message": "Successful Insert"})

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Karoseri save error")
        return jsonify({"success": False, "message": "Failed Insert", "error": str(e)}), 500


@karoseri_bp.route('/api/karoseri/<string:model_code>/<string:karoseri_code>', methods=['DELETE'])
def delete_karoseri(model_code, karoseri_code):
    try:
        db.session.execute(
            text("DELETE FROM UMFKAROSERI WHERE MODEL = :model AND KAROSERI = :karoseri"),
            {"model": model_code, "karoseri": karoseri_code}
        )
        db.session.commit()
        return jsonify({"success": True, "message": "Successful Delete"})

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Karoseri delete error")
        return jsonify({"success": False, "message": "Failed Delete", "error": str(e)}), 500