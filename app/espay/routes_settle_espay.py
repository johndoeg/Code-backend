from datetime import date, datetime

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import text

from app import db
from app.auth.decorators import login_required

settle_espay_bp = Blueprint('settle_espay', __name__, url_prefix='/SettleEspay')

_LIKE = "h.CD_HISTORY_BGIRO LIKE :p ESCAPE '\\'"

def _prefix_pattern(id_trans: str) -> str:
    esc = (id_trans.replace('\\', '\\\\')
                   .replace('%', '\\%')
                   .replace('_', '\\_')
                   .replace('[', '\\['))
    return esc + '%'

def _read_id_trans(source) -> str:
    return str(source.get('id_trans') or '').strip()

def _s(v) -> str:
    return "" if v is None else str(v)

@settle_espay_bp.route('/list', methods=['GET'])
@login_required
def list_history():
    id_trans = _read_id_trans(request.args)
    if not id_trans:
        return jsonify({"error": "ID Transaksi ESPAY is required"}), 400

    try:
        rows = db.session.execute(text("""
            SELECT a.CD_HISTORY_BGIRO, a.LEASE_NO, a.[PERIOD],
                   FORMAT(a.GIRO_DT, 'dd-MM-yyyy')    AS GIRO_DT,
                   a.NOMINAL,
                   FORMAT(a.PAYMENT_DT, 'dd-MM-yyyy') AS PAYMENT_DT,
                   a.VOUCHER, a.TRCODE,
                   b.STATUS,
                   FORMAT(b.PAYMENT, 'dd-MM-yyyy')    AS PAYMENT,
                   c.TRANS_TYPE, c.PAYMENT_REF,
                   FORMAT(c.PAYMENT_DATE, 'dd-MM-yyyy') AS PAYMENT_DATE
            FROM BGHISTORY a WITH (NOLOCK)
                INNER JOIN BGIRO b WITH (NOLOCK) ON a.LEASE_NO = b.LEASE_NO AND a.[PERIOD] = b.[PERIOD]
                LEFT JOIN ESPAY_INVOICE c WITH (NOLOCK)
                       ON a.LEASE_NO = c.LEASE_NO AND a.[PERIOD] = c.[PERIOD] AND c.flagdel = 0
            WHERE a.CD_HISTORY_BGIRO LIKE :p ESCAPE '\\'
        """), {"p": _prefix_pattern(id_trans)}).fetchall()

        data = [{
            "cd_history_bgiro": _s(r.CD_HISTORY_BGIRO),
            "lease_no": _s(r.LEASE_NO),
            "period": _s(r.PERIOD),
            "giro_dt": _s(r.GIRO_DT),
            "nominal": _s(r.NOMINAL),
            "payment_dt": _s(r.PAYMENT_DT),
            "voucher": _s(r.VOUCHER),
            "trcode": _s(r.TRCODE),
            "status": _s(r.STATUS),
            "payment": _s(r.PAYMENT),
            "trans_type": _s(r.TRANS_TYPE),
            "payment_ref": _s(r.PAYMENT_REF),
            "payment_date": _s(r.PAYMENT_DATE),
        } for r in rows]
        return jsonify({"data": data, "total": len(data)}), 200
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Settle ESPAY list failed")
        return jsonify({"error": "Failed to load data"}), 500

@settle_espay_bp.route('/delete', methods=['POST'])
@login_required
def delete_history():
    id_trans = _read_id_trans(request.get_json(silent=True) or {})
    if not id_trans:
        return jsonify({"error": "ID Transaksi ESPAY is required"}), 400

    p = {"p": _prefix_pattern(id_trans)}
    try:
        db.session.execute(text(f"""
            UPDATE b SET [STATUS] = NULL, PAYMENT = NULL
            FROM BGIRO b
            WHERE EXISTS (SELECT 1 FROM BGHISTORY h
                          WHERE h.LEASE_NO = b.LEASE_NO AND h.[PERIOD] = b.[PERIOD] AND {_LIKE})
        """), p)
        res = db.session.execute(text(
            "DELETE FROM BGHISTORY WHERE CD_HISTORY_BGIRO LIKE :p ESCAPE '\\'"), p)
        deleted = res.rowcount
        db.session.commit()
        return jsonify({"message": "DELETE SUCCESSFUL", "deleted": deleted}), 200
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Settle ESPAY delete failed")
        return jsonify({"error": "Delete failed"}), 500

@settle_espay_bp.route('/update', methods=['POST'])
@login_required
def update_payment():
    body = request.get_json(silent=True) or {}
    id_trans = _read_id_trans(body)
    debit_from = str(body.get('debit_from') or '').strip()
    pay_raw = str(body.get('payment_date') or '').strip()

    if not id_trans:
        return jsonify({"error": "ID Transaksi ESPAY is required"}), 400
    if not pay_raw:
        return jsonify({"error": "Payment Date is required"}), 400
    if not debit_from:
        return jsonify({"error": "Debit From is required"}), 400
    try:
        payment_date: date = datetime.strptime(pay_raw[:10], "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid Payment Date"}), 400

    try:
        va = db.session.execute(text(
            "SELECT TOP 1 Bank_Code FROM ESPAY_Generate_VA WITH (NOLOCK) WHERE va_number = :va"),
            {"va": debit_from}).fetchone()
        if not va:
            return jsonify({"error": f"VA number {debit_from} not found"}), 400

        res = db.session.execute(text(f"""
            UPDATE e SET PAYMENT_DATE = :pd, PAYMENT_REF = :ref,
                         DEBIT_FROM = :df, DEBIT_FROM_BANK = :bank
            FROM ESPAY_INVOICE e
            WHERE e.flagdel = '0' AND e.PAYMENT_REF IS NULL
              AND EXISTS (SELECT 1 FROM BGHISTORY h WITH (NOLOCK)
                          WHERE h.LEASE_NO = e.LEASE_NO AND h.[PERIOD] = e.[PERIOD] AND {_LIKE})
        """), {"pd": payment_date, "ref": id_trans, "df": debit_from,
               "bank": va.Bank_Code, "p": _prefix_pattern(id_trans)})
        updated = res.rowcount
        db.session.commit()
        return jsonify({"message": "UPDATE SUCCESSFUL", "updated": updated}), 200
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Settle ESPAY update failed")
        return jsonify({"error": "Update failed"}), 500