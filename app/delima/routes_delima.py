from flask import Blueprint, jsonify, request, current_app
from app import db
from sqlalchemy import text

delima_bp = Blueprint('delima', __name__, url_prefix='/Delima')

@delima_bp.route('/api/invoice')
def get_delima_invoice_summary():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 25, type=int)

    try:
        result = db.session.execute(
            text("EXEC USP_INVOICE_DELIMA :mode, :param2"),
            {"mode": "Summary", "param2": ""}
        )

        all_rows = []
        for row in result:
            all_rows.append({
                "invoice_no": row.invoice_no or "",
                "disb_month": row.disb_month or "",
                "tot_kontrak_inv": str(row.tot_kontrak_inv) if row.tot_kontrak_inv is not None else "0",
                "tot_biaya_inv": str(row.tot_biaya_inv) if row.tot_biaya_inv is not None else "0",
                "tot_kontrak_sys": str(row.tot_kontrak_sys) if row.tot_kontrak_sys is not None else "0",
                "tot_biaya_sys": str(row.tot_biaya_sys) if row.tot_biaya_sys is not None else "0"
            })

        total = len(all_rows)
        start = (page - 1) * limit
        paginated = all_rows[start:start + limit]

        return jsonify({
            "data": paginated,
            "total": total
        })

    except Exception as e:
        current_app.logger.exception("Delima invoice summary error")
        return jsonify({"data": [], "total": 0})

@delima_bp.route('/api/invoice/detail')
def get_delima_invoice_detail():
    invoice_no = request.args.get('id')
    if not invoice_no:
        return jsonify([])

    try:
        result = db.session.execute(
            text("EXEC USP_INVOICE_DELIMA :mode, :invoice_no"),
            {"mode": "Detail", "invoice_no": invoice_no}
        )

        details = []
        for row in result:
            totalnett = "-" if not row.TotalNett or str(row.TotalNett).strip() == "" else str(row.TotalNett)
            gross = "-" if not row.Gross or str(row.Gross).strip() == "" else str(row.Gross)
            batchdt = "-" if not row.BatchDt or str(row.BatchDt).strip() == "" else str(row.BatchDt)

            remark_parts = []
            try:
                if row.TotalNett and row.Gross and float(row.TotalNett) != float(row.Gross):
                    remark_parts.append("Biaya Fidusia")
            except (ValueError, TypeError):
                pass

            if row.Invoice != row.System:
                remark_parts.append("No. kontrak")

            remark = "<br>".join(remark_parts)

            details.append({
                "lease_no": row.lease_no or "",
                "lessee_nm": row.LESSEE_NM or "",
                "execution": str(row.EXECUTION) if row.EXECUTION else "",
                "batchdt": batchdt,
                "totalnett": totalnett,
                "gross": gross,
                "invoice": row.Invoice or "",
                "system": row.System or "",
                "remark": remark
            })

        return jsonify(details)

    except Exception as e:
        current_app.logger.exception("Delima invoice detail error")
        return jsonify([])