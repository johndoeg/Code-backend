from flask import Blueprint, jsonify, request, current_app, session
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text

model_bp = Blueprint("model", __name__, url_prefix="/MasterData")

@model_bp.route("/model-entry")
@login_required
def get_model():
    page       = request.args.get("page",       1,  type=int)
    limit      = request.args.get("limit",      25, type=int)
    search_val = request.args.get("search_val", "").strip()
    search_by  = request.args.get("search_by",  "").strip()
    akses      = session.get("akses", "9")

    try:
        params: dict = {}
        if search_val:
            if search_by == "1":
                where  = "MODEL = :exact_val"
                params = {"exact_val": search_val}
            elif search_by == "2":
                where  = "MODEL_NM LIKE :like_val"
                params = {"like_val": f"%{search_val}%"}
            else:
                where  = "MODEL = :exact_val OR MODEL_NM LIKE :like_val"
                params = {"exact_val": search_val, "like_val": f"%{search_val}%"}
        else:
            where = "1=1"

        total = db.session.execute(text(
            f"SELECT COUNT(*) FROM UMFMODEL WITH(NOLOCK) WHERE {where}"
        ), params).scalar() or 0

        offset = (page - 1) * limit
        rows = db.session.execute(text(f"""
            SELECT MODEL, MODEL_NM
            FROM   UMFMODEL WITH(NOLOCK)
            WHERE  {where}
            ORDER  BY MODEL
            OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
        """), {**params, "offset": offset, "limit": limit}).mappings().all()

        return jsonify({
            "data":  [dict(r) for r in rows],
            "total": total,
            "page":  page,
            "limit": limit,
            "akses": akses,
        })

    except Exception:
        current_app.logger.exception("Model list error")
        return jsonify({"data": [], "total": 0}), 500

@model_bp.route("/model/next-code")
@login_required
def get_next_model_code():
    try:
        row = db.session.execute(text(
            "SELECT ISNULL(MAX(CONVERT(int, MODEL)), 0) + 1 AS n FROM UMFMODEL WITH(NOLOCK)"
        )).first()
        return jsonify({"next_code": str(row[0]).zfill(2)})
    except Exception:
        current_app.logger.exception("Get next model code error")
        return jsonify({"error": "Failed to get next code"}), 500

@model_bp.route("/model/<string:model_code>")
@login_required
def get_model_detail(model_code):
    try:
        row = db.session.execute(text(
            "SELECT MODEL, MODEL_NM FROM UMFMODEL WITH(NOLOCK) WHERE MODEL=:c"
        ), {"c": model_code}).first()
        if not row:
            return jsonify({"error": "Not found"}), 404
        return jsonify({"MODEL": row[0], "MODEL_NM": row[1]})
    except Exception:
        current_app.logger.exception("Model detail error")
        return jsonify({"error": "Failed"}), 500

@model_bp.route("/model", methods=["POST"])
@login_required
def save_model():
    d        = request.get_json(force=True) or {}
    model    = (d.get("model")    or "").strip()
    model_nm = (d.get("model_nm") or "").strip()

    errors = []
    if not model:    errors.append("Model Code must not be empty.")
    if not model_nm: errors.append("Model Name must not be empty.")
    if errors:
        return jsonify({"success": False, "message": " ".join(errors)}), 400

    try:
        db.session.execute(
            text("INSERT INTO UMFMODEL (MODEL, MODEL_NM) VALUES (:m, :nm)"),
            {"m": model, "nm": model_nm},
        )
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Model save error")
        return jsonify({"success": False, "message": "Save failed"}), 500

@model_bp.route("/model/<string:model_code>", methods=["PUT"])
@login_required
def update_model(model_code):
    d        = request.get_json(force=True) or {}
    model_nm = (d.get("model_nm") or "").strip()

    if not model_nm:
        return jsonify({"success": False,
                        "message": "Model Name must not be empty."}), 400
    try:
        db.session.execute(
            text("UPDATE UMFMODEL SET MODEL_NM=:nm WHERE MODEL=:c"),
            {"nm": model_nm, "c": model_code},
        )
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Model update error")
        return jsonify({"success": False, "message": "Update failed"}), 500

@model_bp.route("/model/<string:model_code>", methods=["DELETE"])
@login_required
def delete_model(model_code):
    try:
        db.session.execute(
            text("DELETE FROM UMFKAROSERI WHERE MODEL=:c"), {"c": model_code}
        )
        db.session.execute(
            text("DELETE FROM UMFMODEL WHERE MODEL=:c"), {"c": model_code}
        )
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Model delete error")
        return jsonify({"success": False, "message": "Delete failed"}), 500