from flask import Blueprint, jsonify, request, current_app, session
from app import db
from sqlalchemy import text

model_bp = Blueprint('model', __name__, url_prefix='/MasterData')

@model_bp.route('/api/model-entry')
def get_model():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 25, type=int)
    search_val = request.args.get('search_val', '').strip()
    search_by = request.args.get('search_by', '').strip()

    try:
        where_clause = "1=1"
        if search_val:
            if search_by == '1':
                where_clause = "MODEL = :search_val"
            elif search_by == '2':
                where_clause = "MODEL_NM LIKE :search_val"
                search_val = f"%{search_val}%"
            else:
                where_clause = "MODEL = :search_val OR MODEL_NM LIKE :search_val"
                search_val = f"%{search_val}%"

        count_query = text(f"""
            SELECT COUNT(*) as total
            FROM UMFMODEL WITH(NOLOCK)
            WHERE {where_clause}
        """)

        count_params = {"search_val": search_val} if search_val else {}
        count_result = db.session.execute(count_query, count_params)
        total = count_result.fetchone().total

        offset = (page - 1) * limit
        data_query = text(f"""
            SELECT
                MODEL,
                MODEL_NM
            FROM UMFMODEL WITH(NOLOCK)
            WHERE {where_clause}
            ORDER BY MODEL
            OFFSET :offset ROWS
            FETCH NEXT :limit ROWS ONLY
        """)

        data_params = {
            **count_params,
            "offset": offset,
            "limit": limit
        }

        result = db.session.execute(data_query, data_params)
        model_data = []

        for row in result:
            model_data.append({
                "MODEL": row.MODEL or "",
                "MODEL_NM": row.MODEL_NM or "",
            })

        return jsonify({
            "data": model_data,
            "total": total,
            "page": page,
            "limit": limit,
            "akses": session.get("accesslevel", "")
        })

    except Exception as e:
        current_app.logger.exception("Model list error")
        return jsonify({"data": [], "total": 0, "error": str(e)}), 500


@model_bp.route('/api/model/next-code')
def get_next_model_code():
    try:
        query = text("""
            SELECT ISNULL(MAX(CONVERT(int, MODEL)), 0) + 1 AS NEXT_MODEL
            FROM UMFMODEL WITH(NOLOCK)
        """)
        result = db.session.execute(query).fetchone()
        next_code = str(result.NEXT_MODEL).zfill(2)

        return jsonify({"next_code": next_code})

    except Exception as e:
        current_app.logger.exception("Get next model code error")
        return jsonify({"error": str(e)}), 500


@model_bp.route('/api/model', methods=['POST'])
def save_model():
    data = request.get_json()
    model = (data.get('model') or '').strip()
    model_nm = (data.get('model_nm') or '').strip()

    errors = []
    if not model:
        errors.append("Model Code must not be empty")
    if not model_nm:
        errors.append("Model Name must not be empty")
    if errors:
        return jsonify({"success": False, "message": errors}), 400

    try:
        db.session.execute(
            text("INSERT INTO UMFMODEL (MODEL, MODEL_NM) VALUES (:model, :model_nm)"),
            {"model": model, "model_nm": model_nm}
        )
        db.session.commit()
        return jsonify({"success": True, "message": "Successful"})

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Model save error")
        return jsonify({"success": False, "message": "Failed", "error": str(e)}), 500


@model_bp.route('/api/model/<string:model_code>', methods=['DELETE'])
def delete_model(model_code):
    try:
        db.session.execute(
            text("DELETE FROM UMFKAROSERI WHERE MODEL = :model"),
            {"model": model_code}
        )
        db.session.execute(
            text("DELETE FROM UMFMODEL WHERE MODEL = :model"),
            {"model": model_code}
        )
        db.session.commit()
        return jsonify({"success": True, "message": "Successful"})

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Model delete error")
        return jsonify({"success": False, "message": "Failed", "error": str(e)}), 500