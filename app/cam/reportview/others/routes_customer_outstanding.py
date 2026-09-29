from flask import Blueprint, jsonify, request, current_app
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text

customer_outstanding_bp = Blueprint("customer_outstanding", __name__, url_prefix="/CAM/Others")

@customer_outstanding_bp.route("/CustomerOutstanding/autocomplete")
@login_required
def autocomplete():
   
    term = request.args.get("term", "").strip()
    if len(term) < 2:
        return jsonify([])

    try:
        rows = db.session.execute(
            text("""
                SELECT TOP 30 APLESS, LESSEE_NM
                FROM CAFLESS WITH(NOLOCK)
                WHERE (LESSEE_NM LIKE :t OR APLESS LIKE :t)
                  AND Lessee_No IS NOT NULL
                ORDER BY LESSEE_NM
            """),
            {"t": f"%{term}%"},
        ).mappings().all()

        return jsonify([
            {"apless": r["APLESS"] or "", "lessee_nm": r["LESSEE_NM"] or ""}
            for r in rows
        ])
    except Exception:
        current_app.logger.exception("Customer autocomplete error")
        return jsonify({"error": "Failed to search"}), 500

@customer_outstanding_bp.route("/CustomerOutstanding/data")
@login_required
def get_data():
    
    apless = request.args.get("apless", "").strip()
    if not apless:
        return jsonify({"error": "apless is required"}), 400

    try:
        rows = db.session.execute(
            text("EXEC USP_CUSTOMER_OUTSTANDING :apless"),
            {"apless": apless},
        ).mappings().all()

        result     = []
        tot_out    = 0.0
        tot_ntf    = 0.0

        for r in rows:
            out = float(r["OUTS_PRINC"] or 0)
            ntf = float(r["ntf"]        or 0)
            tot_out += out
            tot_ntf += ntf
            result.append({
                "lease_no":  r["lease_no"]   or "",
                "outs_princ": out,
                "period":    int(r["period"]  or 0),
                "tenor":     int(r["TENOR"]   or 0),
                "late":      int(r["late"]    or 0),
                "ntf":       ntf,
                "tenor_app": r["tenor_app"]  or "",
            })

        return jsonify({
            "rows":        result,
            "tot_out":     tot_out,
            "tot_ntf":     tot_ntf,
            "grand_total": tot_out + tot_ntf,
        })
    except Exception:
        current_app.logger.exception("Customer Outstanding data error")
        return jsonify({"error": "Failed to load data"}), 500