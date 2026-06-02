from flask import Blueprint, jsonify, request, current_app, session
from app import db
from sqlalchemy import text

brand_bp = Blueprint('brand', __name__, url_prefix='/MasterData')

@brand_bp.route('/api/brand')
def get_brand():
    page       = request.args.get('page', 1, type=int)
    limit      = request.args.get('limit', 25, type=int)
    search_val = request.args.get('search_val', '').strip()
    search_by  = request.args.get('search_by', '').strip()

    try:
        if search_val:
            if search_by == '1':
                where_clause = "BRAND = :search_val"
            elif search_by == '2':
                where_clause = "BRAND_NM LIKE :search_val"
                search_val = f"%{search_val}%"
            else:
                where_clause = "BRAND = :search_val OR BRAND_NM LIKE :search_val"
                search_val = f"%{search_val}%"
        else:
            where_clause = "1=1"

        count_params = {"search_val": search_val} if search_val else {}

        count_query = text(f"""
            SELECT COUNT(*) as total
            FROM UMFBRAND WITH(NOLOCK)
            WHERE {where_clause}
        """)
        total = db.session.execute(count_query, count_params).fetchone().total

        offset = (page - 1) * limit
        data_query = text(f"""
            SELECT
                BRAND,
                BRAND_NM,
                BRAND_COUNTRY
            FROM UMFBRAND WITH(NOLOCK)
            WHERE {where_clause}
            ORDER BY BRAND
            OFFSET :offset ROWS
            FETCH NEXT :limit ROWS ONLY
        """)
        data_params = {**count_params, "offset": offset, "limit": limit}
        result = db.session.execute(data_query, data_params)

        brand_data = []
        for row in result:
            brand_data.append({
                "BRAND":         row.BRAND or "",
                "BRAND_NM":      row.BRAND_NM or "",
                "BRAND_COUNTRY": row.BRAND_COUNTRY or "",
            })

        return jsonify({
            "data":  brand_data,
            "total": total,
            "page":  page,
            "limit": limit,
            "akses": session.get("accesslevel", "")
        })

    except Exception as e:
        current_app.logger.exception("Brand list error")
        return jsonify({"data": [], "total": 0, "error": str(e)}), 500

@brand_bp.route('/api/brand', methods=['POST'])
def save_brand():
    data          = request.get_json()
    brand         = (data.get('brand') or '').strip()
    brand_nm      = (data.get('brand_nm') or '').strip()
    brand_country = (data.get('brand_country') or '').strip()

    errors = []
    if not brand:
        errors.append("Brand Code must not be empty")
    if not brand_nm:
        errors.append("Brand Name must not be empty")
    if not brand_country:
        errors.append("Brand Country must not be empty")
    if errors:
        return jsonify({"success": False, "message": errors}), 400

    try:
        db.session.execute(
            text("""
                INSERT INTO UMFBRAND (BRAND, BRAND_NM, BRAND_COUNTRY)
                VALUES (:brand, :brand_nm, :brand_country)
            """),
            {"brand": brand, "brand_nm": brand_nm, "brand_country": brand_country}
        )
        db.session.commit()
        return jsonify({"success": True, "message": "Successful"})

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Brand save error")
        return jsonify({"success": False, "message": "Failed", "error": str(e)}), 500


@brand_bp.route('/api/brand/<string:brand_code>', methods=['DELETE'])
def delete_brand(brand_code):
    try:
        
        db.session.execute(
            text("DELETE FROM UMFTYPE WHERE BRAND = :brand"),
            {"brand": brand_code}
        )
        db.session.execute(
            text("DELETE FROM UMFBRAND WHERE BRAND = :brand"),
            {"brand": brand_code}
        )
        db.session.commit()
        return jsonify({"success": True, "message": "Successful"})

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Brand delete error")
        return jsonify({"success": False, "message": "Failed", "error": str(e)}), 500