from flask import Blueprint, jsonify, request, current_app, session
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text

karoseri_bp = Blueprint("karoseri", __name__, url_prefix="/MasterData")

@karoseri_bp.route("/karoseri")
@login_required
def get_karoseri():
    page       = request.args.get("page",       1,  type=int)
    limit      = request.args.get("limit",      25, type=int)
    search_val = request.args.get("search_val", "").strip()
    search_by  = request.args.get("search_by",  "").strip()
    akses      = session.get("akses", "9")

    try:
        params: dict = {}
        if search_val:
            if search_by == "1":
                where  = "b.MODEL_NM LIKE :like_val"
                params = {"like_val": f"%{search_val}%"}
            elif search_by == "2":
                where  = "a.KAROSERI_DESC LIKE :like_val"
                params = {"like_val": f"%{search_val}%"}
            else:
                where  = "b.MODEL_NM LIKE :like_val OR a.KAROSERI_DESC LIKE :like_val"
                params = {"like_val": f"%{search_val}%"}
        else:
            where = "1=1"

        total = db.session.execute(text(f"""
            SELECT COUNT(*) FROM UMFKAROSERI a WITH(NOLOCK)
            LEFT JOIN UMFMODEL b WITH(NOLOCK) ON a.MODEL = b.MODEL
            WHERE {where}
        """), params).scalar() or 0

        offset = (page - 1) * limit
        rows = db.session.execute(text(f"""
            SELECT
                a.ID_Key, a.KAROSERI, a.KAROSERI_DESC, a.isActive,
                b.MODEL, b.MODEL_NM
            FROM UMFKAROSERI a WITH(NOLOCK)
                LEFT JOIN UMFMODEL b WITH(NOLOCK) ON a.MODEL = b.MODEL
            WHERE {where}
            ORDER BY a.MODEL
            OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
        """), {**params, "offset": offset, "limit": limit}).mappings().all()

        return jsonify({
            "data": [{
                "ID_Key":        r["ID_Key"]        or "",
                "KAROSERI":      r["KAROSERI"]      or "",
                "KAROSERI_DESC": r["KAROSERI_DESC"] or "",
                "isActive":      bool(r["isActive"]),
                "MODEL":         r["MODEL"]          or "",
                "MODEL_NM":      r["MODEL_NM"]       or "",
            } for r in rows],
            "total": total,
            "page":  page,
            "limit": limit,
            "akses": akses,
        })

    except Exception:
        current_app.logger.exception("Karoseri list error")
        return jsonify({"data": [], "total": 0}), 500

@karoseri_bp.route("/karoseri/models")
@login_required
def get_model_options():
    try:
        rows = db.session.execute(text(
            "SELECT MODEL, MODEL_NM FROM UMFMODEL WITH(NOLOCK) ORDER BY MODEL"
        )).mappings().all()
        return jsonify({"data": [dict(r) for r in rows]})
    except Exception:
        current_app.logger.exception("Karoseri model options error")
        return jsonify({"data": []}), 500

@karoseri_bp.route("/karoseri/next-code")
@login_required
def get_next_karoseri_code():
    model = request.args.get("model", "").strip()
    if not model:
        return jsonify({"error": "model is required"}), 400
    try:
        row = db.session.execute(text("""
            SELECT ISNULL(MAX(CONVERT(int, KAROSERI)), 0) + 1 AS n
            FROM UMFKAROSERI WITH(NOLOCK) WHERE MODEL=:m
        """), {"m": model}).first()
        return jsonify({"next_code": str(row[0]).zfill(2)})
    except Exception:
        current_app.logger.exception("Karoseri next-code error")
        return jsonify({"error": "Failed"}), 500

@karoseri_bp.route("/karoseri/<string:model_code>/<string:karoseri_code>")
@login_required
def get_karoseri_detail(model_code, karoseri_code):
    try:
        row = db.session.execute(text("""
            SELECT a.KAROSERI_DESC, a.ID_Key, a.isActive, b.MODEL_NM
            FROM UMFKAROSERI a WITH(NOLOCK)
                LEFT JOIN UMFMODEL b WITH(NOLOCK) ON a.MODEL = b.MODEL
            WHERE a.MODEL=:m AND a.KAROSERI=:k
        """), {"m": model_code, "k": karoseri_code}).first()
        if not row:
            return jsonify({"error": "Not found"}), 404
        return jsonify({
            "KAROSERI_DESC": row[0] or "",
            "ID_Key":        row[1] or "",
            "isActive":      bool(row[2]),
            "MODEL_NM":      row[3] or "",
        })
    except Exception:
        current_app.logger.exception("Karoseri detail error")
        return jsonify({"error": "Failed"}), 500

@karoseri_bp.route("/karoseri", methods=["POST"])
@login_required
def save_karoseri():
    d             = request.get_json(force=True) or {}
    model         = (d.get("model")         or "").strip()
    karoseri      = (d.get("karoseri")      or "").strip()
    karoseri_desc = (d.get("karoseri_desc") or "").strip()
    is_active     = d.get("isActive")

    errors = []
    if not model:         errors.append("Model must not be empty.")
    if not karoseri:      errors.append("Karoseri Code must not be empty.")
    if not karoseri_desc: errors.append("Karoseri Description must not be empty.")
    if is_active is None or is_active == "":
        errors.append("Status must be selected.")
    if errors:
        return jsonify({"success": False, "message": " ".join(errors)}), 400

    try:
        db.session.execute(text("""
            INSERT INTO UMFKAROSERI (MODEL, KAROSERI, KAROSERI_DESC, isActive)
            VALUES (:m, :k, :desc, :active)
        """), {"m": model, "k": karoseri, "desc": karoseri_desc, "active": int(is_active)})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Karoseri save error")
        return jsonify({"success": False, "message": "Save failed"}), 500

@karoseri_bp.route("/karoseri/<string:model_code>/<string:karoseri_code>", methods=["PUT"])
@login_required
def update_karoseri(model_code, karoseri_code):
    d             = request.get_json(force=True) or {}
    karoseri_desc = (d.get("karoseri_desc") or "").strip()
    is_active     = d.get("isActive")

    errors = []
    if not karoseri_desc:
        errors.append("Karoseri Description must not be empty.")
    if is_active is None or is_active == "":
        errors.append("Status must be selected.")
    if errors:
        return jsonify({"success": False, "message": " ".join(errors)}), 400

    try:
        db.session.execute(text("""
            UPDATE UMFKAROSERI
            SET KAROSERI_DESC=:desc, isActive=:active
            WHERE MODEL=:m AND KAROSERI=:k
        """), {"desc": karoseri_desc, "active": int(is_active),
               "m": model_code, "k": karoseri_code})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Karoseri update error")
        return jsonify({"success": False, "message": "Update failed"}), 500

@karoseri_bp.route("/karoseri/<string:model_code>/<string:karoseri_code>", methods=["DELETE"])
@login_required
def delete_karoseri(model_code, karoseri_code):
    try:
        db.session.execute(text(
            "DELETE FROM UMFKAROSERI WHERE MODEL=:m AND KAROSERI=:k"
        ), {"m": model_code, "k": karoseri_code})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Karoseri delete error")
        return jsonify({"success": False, "message": "Delete failed"}), 500