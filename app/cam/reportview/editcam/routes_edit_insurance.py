from __future__ import annotations

from flask import Blueprint, jsonify, request, current_app

from app import db
from app.auth.decorators import login_required

edit_insurance_bp = Blueprint('edit_insurance', __name__, url_prefix='/CAM/Edit')

def _exec_rows(sql: str, params: list) -> list[dict]:
    raw_conn = db.session.connection().connection
    cursor = raw_conn.cursor()
    try:
        cursor.execute(sql, params)
        if cursor.description is None:
            return []
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        cursor.close()

def _exec_write(sql: str, params: list) -> None:
    raw_conn = db.session.connection().connection
    cursor = raw_conn.cursor()
    try:
        cursor.execute(sql, params)
    finally:
        cursor.close()

def _num(val) -> float:
    if val is None:
        return 0.0
    return float(val)

@edit_insurance_bp.route('/edit-insurance/search')
@login_required
def search():
    appl_no = request.args.get('appl_no', '').strip()
    if not appl_no:
        return jsonify({'status': 'error', 'message': 'appl_no is required'}), 400

    try:
        completed = _exec_rows(
            "SELECT COUNT(1) AS complete FROM MCMOCAMCOMPLETELIST WHERE APPL_NO = ? AND AdmSts = 1",
            [appl_no],
        )
        if completed and completed[0].get('complete') == 1:
            return jsonify({'status': 'approved'})

        rows = _exec_rows(
            """SELECT ci.APPL_NO, cl.LESSEE_NM, ui.INS_CO, cid.INS_AMT, cid.YEAR_NO,
                      cid.PRER_AMT, cid.PREP_AMT, cid.Rate_Premi
               FROM CAFINSU ci
                    LEFT JOIN CAFINSUD cid WITH (NOLOCK) ON ci.INS_POL = cid.INS_POL
                    LEFT JOIN UMFINSCD ui WITH (NOLOCK) ON ui.INS_CD = ci.INS_CD
                    LEFT JOIN CAFCONT cc WITH (NOLOCK) ON cc.APPL_NO = ci.APPL_NO
                    LEFT JOIN CAFLESS cl WITH (NOLOCK) ON cl.APLESS = cc.APLESS
               WHERE ci.APPL_NO = ?
               ORDER BY cid.YEAR_NO""",
            [appl_no],
        )
        if not rows:
            return jsonify({'status': 'not_found'})

        return jsonify({
            'status': 'ok',
            'customer_name': rows[0].get('LESSEE_NM') or '',
            'ins_company': rows[0].get('INS_CO') or '',
            'rows': [{
                'appl_no': r.get('APPL_NO'),
                'year_no': r.get('YEAR_NO'),
                'ins_amt': _num(r.get('INS_AMT')),
                'rate_premi': _num(r.get('Rate_Premi')),
                'prer_amt': _num(r.get('PRER_AMT')),
                'prep_amt': _num(r.get('PREP_AMT')),
            } for r in rows],
        })
    except Exception as e:
        current_app.logger.exception("Edit Insurance search error")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@edit_insurance_bp.route('/edit-insurance/save', methods=['POST'])
@login_required
def save():
    payload = request.get_json(force=True, silent=True) or {}
    rows = payload.get('rows') or []
    if not rows:
        return jsonify({'success': False, 'message': 'No data to save'}), 400

    raw_conn = db.session.connection().connection
    try:
        sum_prer = 0.0
        appl_no = ''
        
        for row in rows:
            appl_no = row.get('appl_no', '')
            year_no = row.get('year_no')
            rate_premi = float(row.get('rate_premi') or 0)
            prer_amt = float(row.get('prer_amt') or 0)
            prep_amt = float(row.get('prep_amt') or 0)
            sum_prer += prer_amt

            _exec_write(
                "UPDATE CAFINSUD SET PRER_AMT = ?, PREP_AMT = ?, Rate_Premi = ? "
                "WHERE INS_POL = (SELECT INS_POL FROM CAFINSU WHERE APPL_NO = ?) AND YEAR_NO = ?",
                [prer_amt, prep_amt, rate_premi, appl_no, year_no],
            )

        _exec_write(
            "UPDATE CAFDISB SET GROSS_PREM = ?, NET_COM = ?, DISB_INSC = ? WHERE APPL_NO = ?",
            [round(sum_prer), round(0.75 * sum_prer), sum_prer, appl_no],
        )
        raw_conn.commit()
        return jsonify({'success': True, 'message': 'Data has been updated!'})
    except Exception as e:
        raw_conn.rollback()
        current_app.logger.exception("Edit Insurance save error")
        return jsonify({'success': False, 'message': str(e)}), 500