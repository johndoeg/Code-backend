from flask import Blueprint, jsonify, request, current_app
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text

insurance_bp = Blueprint('insurance', __name__, url_prefix='/Insurance')

@insurance_bp.route('/simas/invoice')
@login_required
def get_simas_invoice_summary():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 25, type=int)

    try:
        result = db.session.execute(
            text("EXEC USP_INVOICE_SIMAS :mode, :param2, :param3"),
            {
                "mode": "Summary",
                "param2": "",
                "param3": ""
            }
        )

        all_rows = []
        for row in result:
            all_rows.append({
                "asof": row.tanggal or "",
                "disb_month": row.disb_month or "",
                "tot_kontrak_inv": str(row.tot_kontrak_inv) if row.tot_kontrak_inv is not None else "0",
                "tot_biaya_inv": str(row.tot_nett_inv) if row.tot_nett_inv is not None else "0",
                "tot_kontrak_sys": str(row.tot_kontrak_sys) if row.tot_kontrak_sys is not None else "0",
                "tot_biaya_sys": str(row.tot_nett_sys) if row.tot_nett_sys is not None else "0",
                "payment_dt": row.Payment_Dt or "",
                "batchno": row.BatchNo or "",
                "confirmby": row.ConfirmBy or "",
                "confirmdate": row.ConfirmDate or "",
            })

        total = len(all_rows)
        start = (page - 1) * limit
        paginated = all_rows[start:start + limit]

        return jsonify({
            "data": paginated,
            "total": total
        })

    except Exception:
        current_app.logger.exception("Simas invoice summary error")
        return jsonify({"data": [], "total": 0}), 500
        
@insurance_bp.route('/simas/detail')
@login_required
def get_simas_invoice_detail():
    invoice_no = request.args.get('id')
    filter_param = request.args.get('filter', '')
    if not invoice_no:
        return jsonify([])

    try:
        result = db.session.execute(
            text("EXEC USP_INVOICE_SIMAS :mode, :param2, :param3"),
            {
                "mode": "Detail",
                "param2": invoice_no,
                "param3": filter_param
            }
        )

        details = []
        for row in result:
            totalnett = row.TotalNett
            gross = row.TotalNettSystem

            totalnett_str = "-" if not totalnett or str(totalnett).strip() == "" else str(totalnett)
            gross_str = "-" if not gross or str(gross).strip() == "" else str(gross)
            batchdt = "-" if not row.CoverDt or str(row.CoverDt).strip() == "" else str(row.CoverDt)

            remark = ""
            try:
                nett_val = float(totalnett) if totalnett else 0
                sys_val = float(gross) if gross else 0
                if sys_val - nett_val > 10000:
                    remark = "Net Premi<br>"
            except (ValueError, TypeError):
                pass

            if row.Invoice != row.System:
                remark += "No. kontrak"

            details.append({
                "lease_no": row.lease_no or "",
                "lessee_nm": row.LESSEE_NM or "",
                "execution": str(row.EXECUTION) if row.EXECUTION else "",
                "batchdt": batchdt,
                "totalnett": totalnett_str,
                "gross": gross_str,
                "invoice": row.Invoice or "",
                "system": row.System or "",
                "remark": remark,
                "branch": row.BRANCH_NAME or "",
                "isconfirm": row.isConfirm or "",
                "confirmby": row.ConfirmBy or "",
                "confirmdate": row.ConfirmDate or "",
                "hasil": row.Hasil or "",
            })

        return jsonify(details)

    except Exception:
        current_app.logger.exception("Simas invoice detail error")
        return jsonify([])
    
@insurance_bp.route('/raksa/invoice')
@login_required
def get_raksa_invoice_summary():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 25, type=int)

    try:
        result = db.session.execute(
            text("EXEC USP_INVOICE_RAKSA :mode, :param2, :param3"),
            {
                "mode": "Summary",
                "param2": "",
                "param3": ""
            }
        )

        all_rows = []
        for row in result:
            all_rows.append({
                "asof": row.tanggal or "",
                "disb_month": row.disb_month or "",
                "tot_kontrak_inv": str(row.tot_kontrak_inv) if row.tot_kontrak_inv is not None else "0",
                "tot_biaya_inv": str(row.tot_nett_inv) if row.tot_nett_inv is not None else "0",
                "tot_kontrak_sys": str(row.tot_kontrak_sys) if row.tot_kontrak_sys is not None else "0",
                "tot_biaya_sys": str(row.tot_nett_sys) if row.tot_nett_sys is not None else "0",
                "confirmby": row.ConfirmBy or "",
                "confirmdate": row.ConfirmDate or "",
            })

        total = len(all_rows)
        start = (page - 1) * limit
        paginated = all_rows[start:start + limit]

        return jsonify({
            "data": paginated,
            "total": total
        })

    except Exception:
        current_app.logger.exception("Raksa invoice summary error")
        return jsonify({"data": [], "total": 0}), 500

@insurance_bp.route('/raksa/detail')
@login_required
def get_raksa_invoice_detail():
    invoice_no = request.args.get('id')
    filter_param = request.args.get('filter', '')
    if not invoice_no:
        return jsonify([])

    try:
        result = db.session.execute(
            text("EXEC USP_INVOICE_RAKSA :mode, :param2, :param3"),
            {
                "mode": "Detail",
                "param2": invoice_no,
                "param3": filter_param
            }
        )

        details = []
        for row in result:
            totalnett = row.TotalNett
            gross = row.TotalNettSystem

            totalnett_str = "-" if not totalnett or str(totalnett).strip() == "" else str(totalnett)
            gross_str = "-" if not gross or str(gross).strip() == "" else str(gross)
            batchdt = "-" if not row.CoverDt or str(row.CoverDt).strip() == "" else str(row.CoverDt)

            remark = ""
            try:
                nett_val = float(totalnett) if totalnett else 0
                sys_val = float(gross) if gross else 0
                if sys_val - nett_val > 10000:
                    remark = "Net Premi<br>"
            except (ValueError, TypeError):
                pass

            if row.Invoice != row.System:
                remark += "No. kontrak"

            details.append({
                "lease_no": row.lease_no or "",
                "lessee_nm": row.LESSEE_NM or "",
                "execution": str(row.EXECUTION) if row.EXECUTION else "",
                "batchdt": batchdt,
                "totalnett": totalnett_str,
                "gross": gross_str,
                "invoice": row.Invoice or "",
                "system": row.System or "",
                "remark": remark,
                "branch": row.BRANCH_NAME or "",
                "isconfirm": row.isConfirm or "",
                "confirmby": row.ConfirmBy or "",
                "confirmdate": row.ConfirmDate or "",
                "hasil": row.Hasil or "",
            })

        return jsonify(details)

    except Exception:
        current_app.logger.exception("Raksa invoice detail error")
        return jsonify([])