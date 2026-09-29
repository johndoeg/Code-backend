from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from flask import Blueprint, jsonify, request, current_app

from app import db
from app.auth.decorators import login_required

commission_individual_detail_bp = Blueprint('commission_individual_detail', __name__, url_prefix='/CAM/Commission')

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

def _parse_date(raw: str) -> Optional[date]:
    raw = (raw or '').strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError:
        return None

def _fmt_value(val):
    if isinstance(val, (date, datetime)):
        return val.strftime('%d-%m-%Y')
    return val

def _fetch_sales(as_of: date, search: str) -> list[dict]:
    first_date = date(as_of.year, 1, 1)

    where = [
        "d.NPWP_Type IN ('PR', '00')",
        "c.Category = 'SALES'",
        "d.Category = 'SALES'",
        "c.AccountType = 'C'",
        "e.EXECUTION IS NOT NULL",
        "a.SD_TYPE = 'S'",
        "e.EXECUTION BETWEEN ? AND ?",
    ]
    params: list = [first_date, as_of]

    top_clause = ""
    if search:
        where.append("b.NAME LIKE ?")
        params.append(f"%{search}%")
    else:
        top_clause = "TOP 200"

    sql = f"""
        SELECT {top_clause}
            c.BeneficiaryID AS RegNo,
            'Individual' AS Type,
            b.NAME AS CommRecvName,
            b.ADDRESS AS CommRecvAddress,
            d.NPWP_Start AS Npwp,
            ISNULL(d.NPWP_No, '') AS NpwpNumber
        FROM CAFKOMIS a WITH (NOLOCK)
            INNER JOIN CLFSALES b WITH (NOLOCK) ON a.SALES_NO = b.SALES_NO
            INNER JOIN BeneficiaryAccount c ON b.SALES_NO = c.BeneficiaryID
            INNER JOIN BeneficiaryTax d ON b.SALES_NO = d.BeneficiaryID
            INNER JOIN CLFCONT e ON a.APPL_NO = e.APPL_NO
        WHERE {' AND '.join(where)}
        GROUP BY c.BeneficiaryID, b.NAME, b.ADDRESS, d.NPWP_Start, d.NPWP_No
        ORDER BY b.NAME
    """
    rows = _exec_rows(sql, params)
    return [
        {
            'reg_no': r.get('RegNo'),
            'type': r.get('Type'),
            'name': r.get('CommRecvName') or '-',
            'address': r.get('CommRecvAddress') or '-',
            'npwp': _fmt_value(r.get('Npwp')),
            'npwp_number': r.get('NpwpNumber') or '-',
        }
        for r in rows
    ]

@commission_individual_detail_bp.route('/commission-detail-report/sales')
@login_required
def list_sales():
    as_of = _parse_date(request.args.get('as_of', ''))
    if as_of is None:
        return jsonify({'error': 'as_of is required (YYYY-MM-DD)'}), 400
    search = request.args.get('search', '').strip()

    try:
        return jsonify(_fetch_sales(as_of, search))
    except Exception as e:
        current_app.logger.exception("Commission receiver search error")
        return jsonify({'error': str(e)}), 500

def _fetch_history(as_of: date, reg_no: str, sort_by_execution: bool) -> dict:
    first_date = date(as_of.year, 1, 1)
    order_clause = "ORDER BY c.EXECUTION" if sort_by_execution else "ORDER BY c.LEASE_NO"

    sql = f"""
        SELECT
            d.LESSEE_NM AS CustName,
            c.LEASE_NO AS ContNo,
            c.EXECUTION AS ExecutionDate,
            ISNULL(a.GrossAmount, 0) AS Gross,
            ISNULL(a.TaxAmount, 0) AS Tax
        FROM CAFKOMIS a WITH (NOLOCK)
            INNER JOIN CLFSALES b WITH (NOLOCK) ON a.SALES_NO = b.SALES_NO
            INNER JOIN CLFCONT c WITH (NOLOCK) ON a.APPL_NO = c.APPL_NO
            INNER JOIN CLFLESS d WITH (NOLOCK) ON c.LESSEE_NO = d.LESSEE_NO
            INNER JOIN BeneficiaryTax f WITH (NOLOCK) ON b.SALES_NO = f.BeneficiaryID
        WHERE b.SALES_NO = ?
            AND c.EXECUTION IS NOT NULL
            AND f.NPWP_Type IN ('PR', '00')
            AND f.Category = 'SALES'
            AND a.SD_TYPE = 'S'
            AND a.PaidBy = 'I'
            AND c.EXECUTION BETWEEN ? AND ?
        {order_clause}
    """
    rows = _exec_rows(sql, [reg_no, first_date, as_of])

    data = []
    tot_gross = 0.0
    tot_tax = 0.0

    for i, r in enumerate(rows, start=1):
        gross = float(r.get('Gross') or 0)
        tax = float(r.get('Tax') or 0)
        net = gross - tax
        tot_gross += gross
        tot_tax += tax

        exec_date = _fmt_value(r.get('ExecutionDate'))

        data.append({
            'no': i,
            'customer_name': r.get('CustName') or '-',
            'contract_no': r.get('ContNo') or '-',
            'disbursement_date': exec_date,
            'commission_date': exec_date,
            'gross_amount': gross,
            'tax_amount': tax,
            'net_payment': net,
            'dpp_cumulative': 0,
            'pph21_cumulative': 0,
        })

    return {
        'data': data,
        'totals': {
            'gross_amount': tot_gross,
            'tax_amount': tot_tax,
            'net_payment': tot_gross - tot_tax,
        },
    }

@commission_individual_detail_bp.route('/commission-detail-report/history')
@login_required
def get_history():
    as_of = _parse_date(request.args.get('as_of', ''))
    if as_of is None:
        return jsonify({'error': 'as_of is required (YYYY-MM-DD)'}), 400

    reg_no = request.args.get('reg_no', '').strip()
    if not reg_no:
        return jsonify({'error': 'reg_no is required'}), 400

    sort_by_execution = request.args.get('sort_by_execution', '').lower() in ('1', 'true')

    try:
        return jsonify(_fetch_history(as_of, reg_no, sort_by_execution))
    except Exception as e:
        current_app.logger.exception("Commission payment history error")
        return jsonify({'error': str(e)}), 500