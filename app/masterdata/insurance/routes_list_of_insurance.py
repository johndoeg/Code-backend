from flask import Blueprint, jsonify, request, current_app
from app import db
from sqlalchemy import text

insurance_list_bp = Blueprint("insurance_list", __name__, url_prefix="/MasterData")

@insurance_list_bp.route("/api/companies")
def get_companies():
    try:
        rows = db.session.execute(
            text("SELECT INS_CD, INS_CO FROM UMFINSCD WITH(NOLOCK) ORDER BY INS_CO")
        ).mappings().all()
        return jsonify([{"ins_cd": r["INS_CD"], "ins_co": r["INS_CO"]} for r in rows])
    except Exception:
        current_app.logger.exception("Insurance companies error")
        return jsonify([]), 500

@insurance_list_bp.route("/api/models")
def get_models():
    try:
        rows = db.session.execute(
            text("""
                SELECT VALUE AS model, DESC_VALUE AS model_nm
                FROM MSTCOMBO WITH(NOLOCK)
                WHERE CAT_VALUE = 'MODEL_ASURANSI'
                ORDER BY DESC_VALUE
            """)
        ).mappings().all()
        return jsonify([{"model": r["model"], "model_nm": r["model_nm"]} for r in rows])
    except Exception:
        current_app.logger.exception("Insurance models error")
        return jsonify([]), 500

@insurance_list_bp.route("/api/premi")
def get_premi():
    ins_cd = request.args.get("ins_cd", "00")
    model  = request.args.get("model",  "00")

    try:
        rows = db.session.execute(
            text("""
                SELECT
                    a.ID,
                    e.INS_CO,
                    b.DESC_VALUE  AS model_nm,
                    c.NAME        AS coverage,
                    a.PREMI,
                    d.Name        AS insurance_area
                FROM CLFINSPRE a WITH(NOLOCK)
                LEFT JOIN UMFINSCD         e WITH(NOLOCK) ON a.INS_CD = e.INS_CD
                LEFT JOIN MSTCOMBO         b WITH(NOLOCK) ON a.MODEL  = b.VALUE
                                                          AND b.CAT_VALUE = 'MODEL_ASURANSI'
                LEFT JOIN mstTLOAR         c WITH(NOLOCK) ON a.TLO_AR = c.CODE
                LEFT JOIN MSTINSURANCEAREA d WITH(NOLOCK) ON a.Insurance_Area = d.Code
                WHERE (a.INS_CD = :ins_cd OR :ins_cd = '00')
                  AND (a.MODEL  = :model  OR :model  = '00')
                ORDER BY e.INS_CO, d.Name, b.DESC_VALUE
            """),
            {"ins_cd": ins_cd, "model": model},
        ).mappings().all()

        return jsonify([
            {
                "id":             r["ID"],
                "ins_co":         r["INS_CO"]         or "",
                "model_nm":       r["model_nm"]        or "",
                "coverage":       r["coverage"]        or "",
                "premi":          str(r["PREMI"])       if r["PREMI"] is not None else "0",
                "insurance_area": r["insurance_area"]  or "",
            }
            for r in rows
        ])
    except Exception:
        current_app.logger.exception("Insurance premi error")
        return jsonify({"error": "Failed to load premi data"}), 500

@insurance_list_bp.route("/api/tpl")
def get_tpl():
    ins_cd = request.args.get("ins_cd", "00")
    model  = request.args.get("model",  "00")

    try:
        rows = db.session.execute(
            text("""
                SELECT
                    e.INS_CO,
                    b.DESC_VALUE AS model_nm,
                    a.TPL_AMT,
                    a.TPL_FEE,
                    a.TPL_FEE2
                FROM CLFINSTPL a WITH(NOLOCK)
                LEFT JOIN UMFINSCD e WITH(NOLOCK) ON a.INS_CD = e.INS_CD
                LEFT JOIN MSTCOMBO b WITH(NOLOCK) ON a.MODEL  = b.VALUE
                                                  AND b.CAT_VALUE = 'MODEL_ASURANSI'
                WHERE (a.INS_CD = :ins_cd OR :ins_cd = '00')
                  AND (a.MODEL  = :model  OR :model  = '00')
                ORDER BY e.INS_CO, b.DESC_VALUE
            """),
            {"ins_cd": ins_cd, "model": model},
        ).mappings().all()

        def fmt(val) -> str:
            """Replicate PHP number_format($val, 0)."""
            try:
                return f"{int(val):,}"
            except (TypeError, ValueError):
                return "0"

        return jsonify([
            {
                "ins_co":   r["INS_CO"]   or "",
                "model_nm": r["model_nm"] or "",
                "tpl_amt":  fmt(r["TPL_AMT"]),
                "tpl_fee":  fmt(r["TPL_FEE"]),
                "tpl_fee2": fmt(r["TPL_FEE2"]),
            }
            for r in rows
        ])
    except Exception:
        current_app.logger.exception("Insurance TPL error")
        return jsonify({"error": "Failed to load TPL data"}), 500