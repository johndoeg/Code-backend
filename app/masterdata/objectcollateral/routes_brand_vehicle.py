from flask import Blueprint, jsonify, request, current_app, session
from app import db
from sqlalchemy import text

brand_vehicle_bp = Blueprint('brand_vehicle', __name__, url_prefix='/MasterData')

@brand_vehicle_bp.route('/api/brand-vehicle')
def get_brand_vehicle():
    page       = request.args.get('page', 1, type=int)
    limit      = request.args.get('limit', 25, type=int)
    brand      = request.args.get('brand', '').strip()
    search_val = request.args.get('search_val', '').strip()

    if not brand:
        return jsonify({"data": [], "total": 0, "error": "brand is required"}), 400

    try:
        where_clause = "a.BRAND = :brand"
        count_params = {"brand": brand}

        if search_val:
            where_clause += " AND a.TYPE_NM LIKE :search_val"
            count_params["search_val"] = f"%{search_val}%"

        count_query = text(f"""
            SELECT COUNT(*) as total
            FROM UMFTYPE a WITH(NOLOCK)
            WHERE {where_clause}
        """)
        total = db.session.execute(count_query, count_params).fetchone().total

        offset = (page - 1) * limit
        data_query = text(f"""
            SELECT
                a.ID_Key,
                a.TYPE,
                a.TYPE_NM,
                a.Fuel,
                a.isActive,
                b.DESC_VALUE as fuel_desc
            FROM UMFTYPE a WITH(NOLOCK)
            LEFT JOIN MSTCOMBO b WITH(NOLOCK)
                ON a.Fuel = b.VALUE AND b.CAT_VALUE = 'FUEL'
            WHERE {where_clause}
            ORDER BY a.TYPE_NM
            OFFSET :offset ROWS
            FETCH NEXT :limit ROWS ONLY
        """)
        data_params = {**count_params, "offset": offset, "limit": limit}
        result = db.session.execute(data_query, data_params)

        vehicle_data = []
        for row in result:
            vehicle_data.append({
                "ID_Key":    str(row.ID_Key) if row.ID_Key else "",
                "TYPE":      row.TYPE or "",
                "TYPE_NM":   row.TYPE_NM or "",
                "Fuel":      row.Fuel or "",
                "fuel_desc": row.fuel_desc or "",
                "isActive":  bool(row.isActive),
            })

        return jsonify({
            "data":  vehicle_data,
            "total": total,
            "page":  page,
            "limit": limit,
            "akses": session.get("accesslevel", "")
        })

    except Exception as e:
        current_app.logger.exception("Brand vehicle list error")
        return jsonify({"data": [], "total": 0, "error": str(e)}), 500


@brand_vehicle_bp.route('/api/brand-vehicle/brand-info')
def get_brand_info():
    
    brand = request.args.get('brand', '').strip()
    if not brand:
        return jsonify({"error": "brand is required"}), 400
    try:
        result = db.session.execute(
            text("SELECT BRAND_NM FROM UMFBRAND WITH(NOLOCK) WHERE BRAND = :brand"),
            {"brand": brand}
        ).fetchone()
        if not result:
            return jsonify({"error": "Brand not found"}), 404
        return jsonify({"BRAND_NM": result.BRAND_NM or ""})
    except Exception as e:
        current_app.logger.exception("Brand info error")
        return jsonify({"error": str(e)}), 500

@brand_vehicle_bp.route('/api/brand-vehicle/models')
def get_vehicle_models():
    
    try:
        result = db.session.execute(
            text("SELECT MODEL, MODEL_NM FROM UMFMODEL WITH(NOLOCK) ORDER BY MODEL ASC")
        )
        models = [{"MODEL": row.MODEL, "MODEL_NM": row.MODEL_NM} for row in result]
        return jsonify({"data": models})
    except Exception as e:
        current_app.logger.exception("Vehicle models error")
        return jsonify({"data": [], "error": str(e)}), 500


@brand_vehicle_bp.route('/api/brand-vehicle/type-code')
def get_type_code():
    
    brand = request.args.get('brand', '').strip()
    model = request.args.get('model', '').strip()
    if not brand or not model:
        return jsonify({"error": "brand and model are required"}), 400
    try:
        result = db.session.execute(
            text("""
                SELECT ISNULL(MAX(CONVERT(int, TYPE)), 0) + 1 AS NEXT_TYPE
                FROM UMFTYPE WITH(NOLOCK)
                WHERE BRAND = :brand
            """),
            {"brand": brand}
        ).fetchone()
        next_code = str(result.NEXT_TYPE).zfill(2)
        return jsonify({"type_code": next_code})
    except Exception as e:
        current_app.logger.exception("Type code error")
        return jsonify({"error": str(e)}), 500


@brand_vehicle_bp.route('/api/brand-vehicle/fuel-options')
def get_fuel_options():
    
    try:
        result = db.session.execute(
            text("SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE = 'FUEL'")
        )
        fuels = [{"VALUE": row.VALUE, "DESC_VALUE": row.DESC_VALUE} for row in result]
        return jsonify({"data": fuels})
    except Exception as e:
        current_app.logger.exception("Fuel options error")
        return jsonify({"data": [], "error": str(e)}), 500


@brand_vehicle_bp.route('/api/brand-vehicle', methods=['POST'])
def save_brand_vehicle():
    data     = request.get_json()
    brand    = (data.get('brand') or '').strip()
    type_cd  = (data.get('type') or '').strip()
    type_nm  = (data.get('type_nm') or '').strip()
    fuel     = (data.get('fuel') or '').strip()
    is_active = data.get('isActive')

    errors = []
    if not brand:
        errors.append("Brand must not be empty")
    if not type_cd:
        errors.append("Type Code must not be empty")
    if not type_nm:
        errors.append("Type Description must not be empty")
    if not fuel:
        errors.append("Fuel Type must not be empty")
    if is_active is None or is_active == '':
        errors.append("Status must be chosen")
    if errors:
        return jsonify({"success": False, "message": errors}), 400

    try:
        db.session.execute(
            text("""
                INSERT INTO UMFTYPE (BRAND, TYPE, TYPE_NM, FUEL, isActive)
                VALUES (:brand, :type, :type_nm, :fuel, :is_active)
            """),
            {
                "brand":     brand,
                "type":      type_cd,
                "type_nm":   type_nm,
                "fuel":      fuel,
                "is_active": int(is_active),
            }
        )
        db.session.commit()
        return jsonify({"success": True, "message": "Successful Insert"})

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Brand vehicle save error")
        return jsonify({"success": False, "message": "Failed Insert", "error": str(e)}), 500


@brand_vehicle_bp.route('/api/brand-vehicle/<string:brand_code>/<string:type_code>', methods=['DELETE'])
def delete_brand_vehicle(brand_code, type_code):
    
    try:
        db.session.execute(
            text("DELETE FROM UMFTYPE WHERE BRAND = :brand AND TYPE = :type"),
            {"brand": brand_code, "type": type_code}
        )
        db.session.commit()
        return jsonify({"success": True, "message": "Successful Delete"})
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Brand vehicle delete error")
        return jsonify({"success": False, "message": "Failed Delete", "error": str(e)}), 500