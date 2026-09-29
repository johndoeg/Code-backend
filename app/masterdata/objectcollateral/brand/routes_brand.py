from flask import Blueprint, jsonify, request, current_app, session
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text

brand_bp = Blueprint("brand", __name__, url_prefix="/MasterData")

@brand_bp.route("/brand")
@login_required
def get_brand():
    
    page       = request.args.get("page",       1,  type=int)
    limit      = request.args.get("limit",      25, type=int)
    search_val = request.args.get("search_val", "").strip()
    search_by  = request.args.get("search_by",  "").strip()
    akses      = session.get("akses", "9")

    try:
        params: dict = {}
        if search_val:
            if search_by == "1":
                where  = "BRAND = :exact_val"
                params = {"exact_val": search_val}
            elif search_by == "2":
                where  = "BRAND_NM LIKE :like_val"
                params = {"like_val": f"%{search_val}%"}
            else:
                where  = "BRAND = :exact_val OR BRAND_NM LIKE :like_val"
                params = {"exact_val": search_val, "like_val": f"%{search_val}%"}
        else:
            where = "1=1"

        total = db.session.execute(text(
            f"SELECT COUNT(*) FROM UMFBRAND WITH(NOLOCK) WHERE {where}"
        ), params).scalar() or 0

        offset = (page - 1) * limit
        rows = db.session.execute(text(f"""
            SELECT BRAND, BRAND_NM, BRAND_COUNTRY
            FROM UMFBRAND WITH(NOLOCK)
            WHERE {where}
            ORDER BY BRAND
            OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
        """), {**params, "offset": offset, "limit": limit}).mappings().all()

        return jsonify({
            "data":  [dict(r) for r in rows],
            "total": total, "page": page, "limit": limit, "akses": akses,
        })
    except Exception:
        current_app.logger.exception("Brand list error")
        return jsonify({"data": [], "total": 0}), 500

@brand_bp.route("/brand/<string:brand_code>")
@login_required
def get_brand_detail(brand_code):
    try:
        row = db.session.execute(text(
            "SELECT BRAND, BRAND_NM, BRAND_COUNTRY FROM UMFBRAND WITH(NOLOCK) WHERE BRAND=:b"
        ), {"b": brand_code}).first()
        if not row:
            return jsonify({"error": "Not found"}), 404
        return jsonify({"BRAND": row[0], "BRAND_NM": row[1], "BRAND_COUNTRY": row[2]})
    except Exception:
        current_app.logger.exception("Brand detail error")
        return jsonify({"error": "Failed"}), 500

@brand_bp.route("/brand", methods=["POST"])
@login_required
def save_brand():
    d             = request.get_json(force=True) or {}
    brand         = (d.get("brand")         or "").strip()
    brand_nm      = (d.get("brand_nm")      or "").strip()
    brand_country = (d.get("brand_country") or "").strip()

    errors = []
    if not brand:         errors.append("Brand Code must not be empty.")
    if not brand_nm:      errors.append("Brand Name must not be empty.")
    if not brand_country: errors.append("Brand Country must not be empty.")
    if errors:
        return jsonify({"success": False, "message": " ".join(errors)}), 400

    try:
        db.session.execute(text(
            "INSERT INTO UMFBRAND (BRAND, BRAND_NM, BRAND_COUNTRY) VALUES (:b,:nm,:c)"
        ), {"b": brand, "nm": brand_nm, "c": brand_country})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Brand save error")
        return jsonify({"success": False, "message": "Save failed"}), 500

@brand_bp.route("/brand/<string:brand_code>", methods=["PUT"])
@login_required
def update_brand(brand_code):
    d             = request.get_json(force=True) or {}
    brand_nm      = (d.get("brand_nm")      or "").strip()
    brand_country = (d.get("brand_country") or "").strip()

    errors = []
    if not brand_nm:      errors.append("Brand Name must not be empty.")
    if not brand_country: errors.append("Brand Country must not be empty.")
    if errors:
        return jsonify({"success": False, "message": " ".join(errors)}), 400

    try:
        db.session.execute(text(
            "UPDATE UMFBRAND SET BRAND_NM=:nm, BRAND_COUNTRY=:c WHERE BRAND=:b"
        ), {"nm": brand_nm, "c": brand_country, "b": brand_code})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Brand update error")
        return jsonify({"success": False, "message": "Update failed"}), 500

@brand_bp.route("/brand/<string:brand_code>", methods=["DELETE"])
@login_required
def delete_brand(brand_code):
    try:
        db.session.execute(text("DELETE FROM UMFTYPE  WHERE BRAND=:b"), {"b": brand_code})
        db.session.execute(text("DELETE FROM UMFBRAND WHERE BRAND=:b"), {"b": brand_code})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Brand delete error")
        return jsonify({"success": False, "message": "Delete failed"}), 500

@brand_bp.route("/brand/vehicle-options")
@login_required
def get_vehicle_options():
    try:
        models = db.session.execute(text(
            "SELECT MODEL, MODEL_NM FROM UMFMODEL WITH(NOLOCK) ORDER BY MODEL"
        )).mappings().all()
        fuels = db.session.execute(text(
            "SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE='FUEL'"
        )).mappings().all()
        return jsonify({
            "models": [{"value": r["MODEL"], "label": r["MODEL_NM"]} for r in models],
            "fuels":  [{"value": r["VALUE"], "label": r["DESC_VALUE"]} for r in fuels],
        })
    except Exception:
        current_app.logger.exception("Vehicle options error")
        return jsonify({"models": [], "fuels": []}), 500

@brand_bp.route("/brand/vehicle-next-code")
@login_required
def get_vehicle_next_code():
    model = request.args.get("model", "").strip()
    brand = request.args.get("brand", "").strip()
    if not model or not brand:
        return jsonify({"error": "model and brand are required"}), 400
    try:
        row = db.session.execute(text("""
            SELECT TOP 1 [TYPE]
            FROM UMFTYPE WITH(NOLOCK)
            WHERE LEFT([TYPE], :ml) = :model AND BRAND = :brand
            ORDER BY [TYPE] DESC
        """), {"ml": len(model), "model": model, "brand": brand}).first()

        if not row or not row[0]:
            next_type = model + "001"
        else:
            current = row[0]
            try:
                next_int = int(current) + 1
                next_type = ("0" + str(next_int)) if current[0] == "0" else str(next_int)
            except ValueError:
                next_type = model + "001"

        return jsonify({"next_code": next_type})
    except Exception:
        current_app.logger.exception("Vehicle next-code error")
        return jsonify({"error": "Failed"}), 500

@brand_bp.route("/brand/<string:brand_code>/vehicles")
@login_required
def get_vehicles(brand_code):
    page  = request.args.get("page",  1,  type=int)
    limit = request.args.get("limit", 25, type=int)
    name  = request.args.get("name",  "").strip()
    akses = session.get("akses", "9")

    try:
        params: dict = {"brand": brand_code}
        name_filter = ""
        if name:
            name_filter = "AND a.TYPE_NM LIKE :name"
            params["name"] = f"%{name}%"

        total = db.session.execute(text(f"""
            SELECT COUNT(*) FROM UMFTYPE a WITH(NOLOCK)
            WHERE a.BRAND=:brand {name_filter}
        """), params).scalar() or 0

        offset = (page - 1) * limit
        rows = db.session.execute(text(f"""
            SELECT
                a.TYPE, a.TYPE_NM, a.Fuel, a.isActive,
                b.DESC_VALUE                                       AS fuel_desc,
                SUBSTRING(a.TYPE, 1, LEN(a.TYPE)-3)               AS model_cd,
                c.MODEL_NM
            FROM UMFTYPE a WITH(NOLOCK)
                LEFT JOIN MSTCOMBO b WITH(NOLOCK)
                    ON b.value = a.Fuel AND b.CAT_VALUE = 'FUEL'
                LEFT JOIN UMFMODEL c WITH(NOLOCK)
                    ON c.MODEL = SUBSTRING(a.TYPE, 1, LEN(a.TYPE)-3)
            WHERE a.BRAND=:brand {name_filter}
            ORDER BY a.TYPE_NM
            OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
        """), {**params, "offset": offset, "limit": limit}).mappings().all()

        brand_row = db.session.execute(text(
            "SELECT BRAND_NM FROM UMFBRAND WITH(NOLOCK) WHERE BRAND=:b"
        ), {"b": brand_code}).first()

        return jsonify({
            "data": [{
                "TYPE":      r["TYPE"]      or "",
                "TYPE_NM":   r["TYPE_NM"]   or "",
                "Fuel":      r["Fuel"]       or "",
                "fuel_desc": r["fuel_desc"] or "",
                "isActive":  bool(r["isActive"]),
                "model_cd":  r["model_cd"]  or "",
                "MODEL_NM":  r["MODEL_NM"]  or "",
            } for r in rows],
            "total":    total,
            "page":     page,
            "limit":    limit,
            "akses":    akses,
            "brand_nm": brand_row[0] if brand_row else "",
        })
    except Exception:
        current_app.logger.exception("Vehicle list error")
        return jsonify({"data": [], "total": 0}), 500

@brand_bp.route("/brand/<string:brand_code>/vehicles", methods=["POST"])
@login_required
def save_vehicle(brand_code):
    d        = request.get_json(force=True) or {}
    type_cd  = (d.get("type")    or "").strip()
    type_nm  = (d.get("type_nm") or "").strip()
    fuel     = (d.get("fuel")    or "").strip()
    is_active = d.get("isActive")

    errors = []
    if not type_cd:    errors.append("Type Code must not be empty.")
    if not type_nm:    errors.append("Type Description must not be empty.")
    if not fuel:       errors.append("Fuel Type must not be empty.")
    if is_active is None or is_active == "":
        errors.append("Status must be selected.")
    if errors:
        return jsonify({"success": False, "message": " ".join(errors)}), 400

    try:
        db.session.execute(text("""
            INSERT INTO UMFTYPE (BRAND, TYPE, TYPE_NM, FUEL, isActive)
            VALUES (:brand, :type, :nm, :fuel, :active)
        """), {"brand": brand_code, "type": type_cd, "nm": type_nm,
               "fuel": fuel, "active": int(is_active)})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Vehicle save error")
        return jsonify({"success": False, "message": "Save failed"}), 500

@brand_bp.route("/brand/<string:brand_code>/vehicles/<string:type_code>", methods=["PUT"])
@login_required
def update_vehicle(brand_code, type_code):
    d         = request.get_json(force=True) or {}
    type_nm   = (d.get("type_nm") or "").strip()
    fuel      = (d.get("fuel")    or "").strip()
    is_active = d.get("isActive")

    errors = []
    if not type_nm:  errors.append("Type Description must not be empty.")
    if not fuel:     errors.append("Fuel Type must not be empty.")
    if is_active is None or is_active == "":
        errors.append("Status must be selected.")
    if errors:
        return jsonify({"success": False, "message": " ".join(errors)}), 400

    try:
        db.session.execute(text("""
            UPDATE UMFTYPE
            SET TYPE_NM=:nm, Fuel=:fuel, isActive=:active
            WHERE BRAND=:brand AND TYPE=:type
        """), {"nm": type_nm, "fuel": fuel, "active": int(is_active),
               "brand": brand_code, "type": type_code})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Vehicle update error")
        return jsonify({"success": False, "message": "Update failed"}), 500

@brand_bp.route("/brand/<string:brand_code>/vehicles/<string:type_code>", methods=["DELETE"])
@login_required
def delete_vehicle(brand_code, type_code):
    try:
        db.session.execute(text(
            "DELETE FROM UMFTYPE WHERE BRAND=:brand AND TYPE=:type"
        ), {"brand": brand_code, "type": type_code})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Vehicle delete error")
        return jsonify({"success": False, "message": "Delete failed"}), 500