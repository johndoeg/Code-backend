from flask import Blueprint, jsonify, request, current_app, session
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text

list_brand_bp = Blueprint('list_brand', __name__, url_prefix='/MasterData')

@list_brand_bp.route('/list-brand')
@login_required
def get_list_brand():
    page  = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 25, type=int)
    brand = request.args.get('brand', '').strip()
    model = request.args.get('model', '').strip()

    try:
        conditions = []
        params: dict = {}

        if brand:
            conditions.append("a.BRAND = :brand")
            params["brand"] = brand
        if model:
            conditions.append("SUBSTRING(a.TYPE, 1, 2) = :model")
            params["model"] = model

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        count_query = text(f"""
            SELECT COUNT(*) as total
            FROM UMFTYPE a WITH(NOLOCK)
                LEFT JOIN UMFBRAND b WITH(NOLOCK) ON a.BRAND = b.BRAND
                LEFT JOIN UMFMODEL c WITH(NOLOCK) ON SUBSTRING(a.TYPE, 1, 2) = c.MODEL
            {where_clause}
        """)
        total = db.session.execute(count_query, params).fetchone().total

        offset = (page - 1) * limit
        data_query = text(f"""
            SELECT
                a.TYPE,
                a.TYPE_NM,
                b.BRAND_NM,
                c.MODEL_NM
            FROM UMFTYPE a WITH(NOLOCK)
                LEFT JOIN UMFBRAND b WITH(NOLOCK) ON a.BRAND = b.BRAND
                LEFT JOIN UMFMODEL c WITH(NOLOCK) ON SUBSTRING(a.TYPE, 1, 2) = c.MODEL
            {where_clause}
            ORDER BY a.TYPE
            OFFSET :offset ROWS
            FETCH NEXT :limit ROWS ONLY
        """)
        data_params = {**params, "offset": offset, "limit": limit}
        result = db.session.execute(data_query, data_params)

        list_data = []
        for row in result:
            list_data.append({
                "TYPE":     row.TYPE     or "-",
                "TYPE_NM":  row.TYPE_NM  or "-",
                "BRAND_NM": row.BRAND_NM or "-",
                "MODEL_NM": row.MODEL_NM or "-",
            })

        return jsonify({
            "data":  list_data,
            "total": total,
            "page":  page,
            "limit": limit,
        })

    except Exception as e:
        current_app.logger.exception("List brand error")
        return jsonify({"data": [], "total": 0, "error": str(e)}), 500

@list_brand_bp.route('/list-brand/brand-options')
@login_required
def get_brand_options():
    
    try:
        result = db.session.execute(text("""
            SELECT BRAND, BRAND_NM
            FROM UMFBRAND WITH(NOLOCK)
            WHERE BRAND_NM NOT IN ('CBU', 'All Brand', 'Used Cars', 'Used Trucks')
            ORDER BY BRAND_NM
        """))
        return jsonify({"data": [{"BRAND": r.BRAND, "BRAND_NM": r.BRAND_NM} for r in result]})
    except Exception as e:
        current_app.logger.exception("Brand options error")
        return jsonify({"data": [], "error": str(e)}), 500

@list_brand_bp.route('/list-brand/model-options')
@login_required
def get_model_options():
    
    try:
        result = db.session.execute(text("""
            SELECT MODEL, MODEL_NM FROM UMFMODEL WITH(NOLOCK) ORDER BY MODEL
        """))
        return jsonify({"data": [{"MODEL": r.MODEL, "MODEL_NM": r.MODEL_NM} for r in result]})
    except Exception as e:
        current_app.logger.exception("Model options error")
        return jsonify({"data": [], "error": str(e)}), 500

@list_brand_bp.route('/list-brand/export')
@login_required
def export_list_brand():
   
    brand = request.args.get('brand', '').strip()
    model = request.args.get('model', '').strip()

    try:
        conditions = []
        params: dict = {}

        if brand:
            conditions.append("a.BRAND = :brand")
            params["brand"] = brand
        if model:
            conditions.append("SUBSTRING(a.TYPE, 1, 2) = :model")
            params["model"] = model

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        result = db.session.execute(text(f"""
            SELECT
                a.TYPE,
                a.TYPE_NM,
                b.BRAND_NM,
                c.MODEL_NM
            FROM UMFTYPE a WITH(NOLOCK)
                LEFT JOIN UMFBRAND b WITH(NOLOCK) ON a.BRAND = b.BRAND
                LEFT JOIN UMFMODEL c WITH(NOLOCK) ON SUBSTRING(a.TYPE, 1, 2) = c.MODEL
            {where_clause}
            ORDER BY a.TYPE
        """), params)

        export_data = []
        for row in result:
            export_data.append({
                "TYPE":     row.TYPE     or "-",
                "TYPE_NM":  row.TYPE_NM  or "-",
                "BRAND_NM": row.BRAND_NM or "-",
                "MODEL_NM": row.MODEL_NM or "-",
            })

        return jsonify({"data": export_data, "total": len(export_data)})

    except Exception as e:
        current_app.logger.exception("List brand export error")
        return jsonify({"data": [], "error": str(e)}), 500