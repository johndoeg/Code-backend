from flask import Blueprint, jsonify, current_app
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text

top20_customer_bp = Blueprint("top20_customer", __name__, url_prefix="/CAM/Others")

_QUERY = text("""
    SELECT TOP 20
           a.lessee_no,
           c.LESSEE_NM,
           SUM(b.outs_princ) AS total
    FROM clfcont a WITH(NOLOCK)
        INNER JOIN clfpay b WITH(NOLOCK) ON a.lease_no = b.LEASE_NO
          AND b.PERIOD = (
                SELECT MAX(Period)
                FROM CLFPAY WITH(NOLOCK)
                WHERE lease_no = a.lease_no
                  AND DATE_PAY <> ''
              )
        INNER JOIN CLFLESS c WITH(NOLOCK) ON a.lessee_no = c.LESSEE_NO
    WHERE a.UPD_STAT = 'Y'
        AND a.EXECUTION IS NOT NULL
    GROUP BY a.lessee_no, c.LESSEE_NM
    ORDER BY SUM(b.outs_princ) DESC
""")

@top20_customer_bp.route("/Top20Customer/data")
@login_required
def get_data():
    try:
        rows = db.session.execute(_QUERY).mappings().all()
        return jsonify([
            {
                "lessee_nm": r["LESSEE_NM"] or "",
                "total":     float(r["total"] or 0),
            }
            for r in rows
        ])
    except Exception:
        current_app.logger.exception("Top 20 Customer fetch error")
        return jsonify({"error": "Failed to load data"}), 500