from flask import Blueprint, jsonify, request, current_app
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text

summary_rundown_osp_bp = Blueprint("summary_rundown_osp", __name__, url_prefix="/CAM/Others")

_SP = text("EXEC USP_SUMMARY_RUNDOWNOSP :mode, :start_dt, :end_dt, :until, :branch_cd, :bulan")

def _base_params(req) -> dict:
    return {
        "start_dt":  req.args.get("start_dt",  "").strip(),
        "end_dt":    req.args.get("end_dt",    "").strip(),
        "until":     req.args.get("until",     "").strip(),
        "branch_cd": req.args.get("branch_cd", "").strip(),
    }

@summary_rundown_osp_bp.route("/SummaryRundownOSP/branches")
@login_required
def get_branches():
    try:
        rows = db.session.execute(
            text("""
                SELECT BRANCH_CD, BRANCH_NAME
                FROM UMFBRANCH WITH(NOLOCK)
                WHERE BRANCH_CD <> '100'
                ORDER BY BRANCH_CD
            """)
        ).mappings().all()
        return jsonify([
            {"branch_cd": r["BRANCH_CD"], "branch_name": r["BRANCH_NAME"]}
            for r in rows
        ])
    except Exception:
        current_app.logger.exception("Branches fetch error")
        return jsonify({"error": "Failed to load branches"}), 500

@summary_rundown_osp_bp.route("/SummaryRundownOSP/summary")
@login_required
def get_summary():
    
    p = _base_params(request)
    try:
        rows = db.session.execute(
            _SP, {**p, "mode": "SUMMARY", "bulan": ""}
        ).mappings().all()
        return jsonify([
            {
                "periode":         r["periode"]       or "",
                "bulan":           r["bulan"]         or "",
                "if_osp":          r["if_osp"],
                "if_ar":           r["if_ar"],
                "if_unit":         r["if_unit"],
                "if_rundownosp":   r["if_rundownosp"],
                "sl_osp":          r["sl_osp"],
                "sl_ar":           r["sl_ar"],
                "sl_unit":         r["sl_unit"],
                "sl_rundownosp":   r["sl_rundownosp"],
                "total_osp":       r["TotalOSP"],
                "total_ar":        r["TotalAR"],
                "total_unit":      r["TotalUnit"],
                "total_rundownosp":r["TotalRundownOSP"],
            }
            for r in rows
        ])
    except Exception:
        current_app.logger.exception("Summary Rundown OSP summary error")
        return jsonify({"error": "Failed to load summary"}), 500

@summary_rundown_osp_bp.route("/SummaryRundownOSP/detail")
@login_required
def get_detail():
    
    p    = _base_params(request)
    bulan = request.args.get("bulan", "").strip()
    try:
        rows = db.session.execute(
            _SP, {**p, "mode": "DETAIL", "bulan": bulan}
        ).mappings().all()
        return jsonify([
            {
                "appl_no":   r["appl_no"]   or "",
                "lessee_nm": r["LESSEE_NM"] or "",
                "ntf":       r["ntf"],
                "osp":       r["osp"],
                "ar":        r["ar"],
                "payment":   r["PERIOD"],
                "tenor":     r["tenor"],
            }
            for r in rows
        ])
    except Exception:
        current_app.logger.exception("Summary Rundown OSP detail error")
        return jsonify({"error": "Failed to load detail"}), 500