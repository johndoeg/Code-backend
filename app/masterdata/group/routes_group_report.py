from flask import Blueprint, jsonify, request, current_app
from app import db
from sqlalchemy import text

group_report_bp = Blueprint('group_report', __name__, url_prefix='/MasterData')

@group_report_bp.route('/api/group-report')
def get_group_report():
    page    = request.args.get('page', 1, type=int)
    limit   = request.args.get('limit', 25, type=int)
    grpname = request.args.get('grpname', '').strip()

    if not grpname:
        return jsonify({"data": [], "total": 0, "grand_total": 0,
                        "error": "grpname is required"}), 400

    try:
        params = {"grpname": f"%{grpname}%"}

        total = db.session.execute(text("""
            SELECT COUNT(*) as total
            FROM CLFGROUP a WITH(NOLOCK)
            LEFT JOIN CAFLESS b WITH(NOLOCK) ON a.GrpCode = b.GrpCode
            WHERE a.GrpName LIKE :grpname
              AND a.FLGDEL = '0'
        """), params).fetchone().total

        offset = (page - 1) * limit

        result = db.session.execute(text("""
            SELECT
                b.APLESS,
                b.LESSEE_NM,
                b.ADDRESS1,
                b.CITY1,
                ISNULL(SUM(latest_pay.OUTS_PRINC), 0) AS OUTS_TOTAL
            FROM CLFGROUP a WITH(NOLOCK)
            LEFT JOIN CAFLESS b WITH(NOLOCK) ON a.GrpCode = b.GrpCode
            OUTER APPLY (
                SELECT SUM(lp.OUTS_PRINC) AS OUTS_PRINC
                FROM CLFCONT cc WITH(NOLOCK)
                INNER JOIN CAFCONT bc WITH(NOLOCK) ON cc.APPL_NO = bc.APPL_NO
                OUTER APPLY (
                    SELECT TOP 1 OUTS_PRINC
                    FROM CLFPAY WITH(NOLOCK)
                    WHERE LEASE_NO = cc.LEASE_NO
                    ORDER BY DATE_PAY DESC
                ) lp
                WHERE bc.APLESS = b.APLESS
            ) latest_pay
            WHERE a.GrpName LIKE :grpname
              AND a.FLGDEL = '0'
            GROUP BY b.APLESS, b.LESSEE_NM, b.ADDRESS1, b.CITY1
            ORDER BY b.LESSEE_NM
            OFFSET :offset ROWS
            FETCH NEXT :limit ROWS ONLY
        """), {**params, "offset": offset, "limit": limit}).fetchall()

        data = [
            {
                "APLESS":     row.APLESS    or "",
                "LESSEE_NM":  row.LESSEE_NM or "",
                "ADDRESS1":   row.ADDRESS1  or "",
                "CITY1":      row.CITY1     or "",
                "OUTS_TOTAL": float(row.OUTS_TOTAL or 0),
            }
            for row in result
        ]

        grand_total_row = db.session.execute(text("""
            SELECT ISNULL(SUM(latest_pay.OUTS_PRINC), 0) AS GRAND_TOTAL
            FROM CLFGROUP a WITH(NOLOCK)
            LEFT JOIN CAFLESS b WITH(NOLOCK) ON a.GrpCode = b.GrpCode
            OUTER APPLY (
                SELECT SUM(lp.OUTS_PRINC) AS OUTS_PRINC
                FROM CLFCONT cc WITH(NOLOCK)
                INNER JOIN CAFCONT bc WITH(NOLOCK) ON cc.APPL_NO = bc.APPL_NO
                OUTER APPLY (
                    SELECT TOP 1 OUTS_PRINC
                    FROM CLFPAY WITH(NOLOCK)
                    WHERE LEASE_NO = cc.LEASE_NO
                    ORDER BY DATE_PAY DESC
                ) lp
                WHERE bc.APLESS = b.APLESS
            ) latest_pay
            WHERE a.GrpName LIKE :grpname
              AND a.FLGDEL = '0'
        """), params).fetchone()

        grand_total = float(grand_total_row.GRAND_TOTAL or 0)

        return jsonify({
            "data":        data,
            "total":       total,
            "page":        page,
            "limit":       limit,
            "grand_total": grand_total,
        })

    except Exception as e:
        current_app.logger.exception("Group report error")
        return jsonify({"data": [], "total": 0, "grand_total": 0,
                        "error": str(e)}), 500

@group_report_bp.route('/api/group-report/export')
def export_group_report():
    grpname = request.args.get('grpname', '').strip()
    if not grpname:
        return jsonify({"data": [], "grand_total": 0,
                        "error": "grpname is required"}), 400

    try:
        params = {"grpname": f"%{grpname}%"}

        result = db.session.execute(text("""
            SELECT
                b.APLESS,
                b.LESSEE_NM,
                b.ADDRESS1,
                b.CITY1,
                ISNULL(SUM(latest_pay.OUTS_PRINC), 0) AS OUTS_TOTAL
            FROM CLFGROUP a WITH(NOLOCK)
            LEFT JOIN CAFLESS b WITH(NOLOCK) ON a.GrpCode = b.GrpCode
            OUTER APPLY (
                SELECT SUM(lp.OUTS_PRINC) AS OUTS_PRINC
                FROM CLFCONT cc WITH(NOLOCK)
                INNER JOIN CAFCONT bc WITH(NOLOCK) ON cc.APPL_NO = bc.APPL_NO
                OUTER APPLY (
                    SELECT TOP 1 OUTS_PRINC
                    FROM CLFPAY WITH(NOLOCK)
                    WHERE LEASE_NO = cc.LEASE_NO
                    ORDER BY DATE_PAY DESC
                ) lp
                WHERE bc.APLESS = b.APLESS
            ) latest_pay
            WHERE a.GrpName LIKE :grpname
              AND a.FLGDEL = '0'
            GROUP BY b.APLESS, b.LESSEE_NM, b.ADDRESS1, b.CITY1
            ORDER BY b.LESSEE_NM
        """), params).fetchall()

        data = [
            {
                "APLESS":     row.APLESS    or "",
                "LESSEE_NM":  row.LESSEE_NM or "",
                "ADDRESS1":   row.ADDRESS1  or "",
                "CITY1":      row.CITY1     or "",
                "OUTS_TOTAL": float(row.OUTS_TOTAL or 0),
            }
            for row in result
        ]
        grand_total = sum(r["OUTS_TOTAL"] for r in data)
        return jsonify({"data": data, "grand_total": grand_total})

    except Exception as e:
        current_app.logger.exception("Group report export error")
        return jsonify({"data": [], "grand_total": 0, "error": str(e)}), 500