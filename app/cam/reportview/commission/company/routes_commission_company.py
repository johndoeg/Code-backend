from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from flask import Blueprint, jsonify, request, current_app

from app import db
from app.auth.decorators import login_required

commission_company_bp = Blueprint('commission_company', __name__, url_prefix='/CAM/Commission')

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

def _fetch_parties(as_of: date, search: str) -> list[dict]:
    
    first_date = date(as_of.year, 1, 1)
    where = ""
    params: list = [as_of, as_of, first_date, as_of, as_of, as_of, first_date, as_of]

    sql = """
        SELECT * FROM (
            SELECT
                c.BeneficiaryID AS RegNo,
                'AGENT' AS Type,
                b.NAME AS CommRecvName,
                b.ADDRESS AS CommRecvAddress,
                '' AS DealerType,
                '' AS DealerStatus,
                ISNULL(d.NPWP_No, '') AS Npwp,
                CASE WHEN ? BETWEEN d.TFFrom AND d.TFTo THEN 'SKB' ELSE 'Non SKB' END AS Skb,
                CASE WHEN ? > d.DateStart AND d.PPN = 1 THEN 'PPN' ELSE 'Non PPN' END AS Ppn
            FROM CAFKOMIS a WITH (NOLOCK)
                INNER JOIN CLFSALES b WITH (NOLOCK) ON a.SALES_NO = b.SALES_NO
                INNER JOIN BeneficiaryAccount c ON b.SALES_NO = c.BeneficiaryID
                INNER JOIN BeneficiaryTax d ON b.SALES_NO = d.BeneficiaryID
                INNER JOIN CLFCONT e ON a.APPL_NO = e.APPL_NO
            WHERE d.NPWP_Type = 'PT'
                AND c.Category = 'SALES' AND d.Category = 'SALES'
                AND c.AccountType = 'C'
                AND e.EXECUTION IS NOT NULL
                AND a.SD_TYPE = 'S'
                AND e.EXECUTION BETWEEN ? AND ?
                
            UNION
            
            SELECT
                c.BeneficiaryID AS RegNo,
                UPPER(c.Category) AS Type,
                b.NAME AS CommRecvName,
                b.ADDRESS AS CommRecvAddress,
                ISNULL(e.DESCRIPTION, '') AS DealerType,
                CASE WHEN b.FLGDEL = '0' OR ISNULL(b.FLGDEL, 0) = '0' THEN 'Active' ELSE '' END AS DealerStatus,
                ISNULL(d.NPWP_No, '') AS Npwp,
                CASE WHEN ? BETWEEN d.TFFrom AND d.TFTo THEN 'SKB' ELSE 'Non SKB' END AS Skb,
                CASE WHEN ? > d.DateStart AND d.PPN = 1 THEN 'PPN' ELSE 'Non PPN' END AS Ppn
            FROM CAFKOMIS a WITH (NOLOCK)
                INNER JOIN CLFSUPP b WITH (NOLOCK) ON a.SALES_NO = b.SUPP
                INNER JOIN BeneficiaryAccount c ON b.SUPP = c.BeneficiaryID
                INNER JOIN BeneficiaryTax d ON b.SUPP = d.BeneficiaryID
                INNER JOIN MSTDEALERTYPE e ON b.Supp_Type = e.CODE
                INNER JOIN CLFCONT f ON a.APPL_NO = f.APPL_NO
            WHERE f.EXECUTION BETWEEN ? AND ?
                AND c.Category = 'DEALER' AND d.Category = 'DEALER'
                AND c.AccountType = 'C'
                AND f.EXECUTION IS NOT NULL
                AND a.SD_TYPE = 'D'
        ) hasil
        {where}
        ORDER BY CommRecvName
    """

    if search:
        where = "WHERE hasil.CommRecvName LIKE ?"
        params.append(f"%{search}%")

    rows = _exec_rows(sql.format(where=where), params)
    return [
        {
            'reg_no': r.get('RegNo'),
            'type': r.get('Type'),
            'name': r.get('CommRecvName') or '-',
            'address': r.get('CommRecvAddress') or '-',
            'dealer_type': r.get('DealerType') or '',
            'dealer_status': r.get('DealerStatus') or '',
            'npwp': r.get('Npwp') or '',
            'skb': r.get('Skb'),
            'ppn': r.get('Ppn'),
        }
        for r in rows
    ]

@commission_company_bp.route('/commission-company-report/parties')
@login_required
def list_parties():
    as_of = _parse_date(request.args.get('as_of', ''))
    if as_of is None:
        return jsonify({'error': 'as_of is required (YYYY-MM-DD)'}), 400
    search = request.args.get('search', '').strip()

    try:
        return jsonify(_fetch_parties(as_of, search))
    except Exception as e:
        current_app.logger.exception("Commission party search error")
        return jsonify({'error': str(e)}), 500

def _fetch_history(as_of: date, reg_no: str, party_type: str, sort_by_execution: bool) -> dict:
    first_date = date(as_of.year, 1, 1)
    order_clause = "ORDER BY c.EXECUTION" if sort_by_execution else "ORDER BY c.LEASE_NO"

    if party_type == 'DEALER':
        sql = f"""
            SELECT
                d.LESSEE_NM AS CustName,
                c.LEASE_NO AS ContNo,
                c.EXECUTION AS ExecutionDate,
                ISNULL(a.GrossAmount, 0) AS Gross,
                ISNULL(a.PPNAmount, 0) AS Ppn,
                ISNULL(a.TaxAmount, 0) AS Tax
            FROM CAFKOMIS a WITH (NOLOCK)
                INNER JOIN CLFSUPP b WITH (NOLOCK) ON a.SALES_NO = b.SUPP
                INNER JOIN CLFCONT c WITH (NOLOCK) ON a.APPL_NO = c.APPL_NO
                INNER JOIN CLFLESS d WITH (NOLOCK) ON c.LESSEE_NO = d.LESSEE_NO
            WHERE b.SUPP = ?
                AND c.EXECUTION IS NOT NULL
                AND a.SD_TYPE = 'D'
                AND a.INCENTIVE = '1'
                AND c.EXECUTION BETWEEN ? AND ?
            {order_clause}
        """
    else:
        sql = f"""
            SELECT
                d.LESSEE_NM AS CustName,
                c.LEASE_NO AS ContNo,
                c.EXECUTION AS ExecutionDate,
                ISNULL(a.GrossAmount, 0) AS Gross,
                ISNULL(a.PPNAmount, 0) AS Ppn,
                ISNULL(a.TaxAmount, 0) AS Tax
            FROM CAFKOMIS a WITH (NOLOCK)
                INNER JOIN CLFSALES b WITH (NOLOCK) ON a.SALES_NO = b.SALES_NO
                INNER JOIN CLFCONT c WITH (NOLOCK) ON a.APPL_NO = c.APPL_NO
                INNER JOIN CLFLESS d WITH (NOLOCK) ON c.LESSEE_NO = d.LESSEE_NO
                INNER JOIN BeneficiaryTax e WITH (NOLOCK) ON b.SALES_NO = e.BeneficiaryID
            WHERE b.SALES_NO = ?
                AND c.EXECUTION IS NOT NULL
                AND e.NPWP_Type = 'PT'
                AND e.Category = 'SALES'
                AND a.SD_TYPE = 'S'
                AND a.INCENTIVE = '1'
                AND c.EXECUTION BETWEEN ? AND ?
            {order_clause}
        """

    rows = _exec_rows(sql, [reg_no, first_date, as_of])

    data = []
    tot_gross = 0.0
    tot_net = 0.0

    for i, r in enumerate(rows, start=1):
        gross = float(r.get('Gross') or 0)
        ppn = float(r.get('Ppn') or 0)
        tax = float(r.get('Tax') or 0)
        net = gross + ppn - tax
        comm_cam = gross + ppn

        tot_gross += gross
        tot_net += net

        exec_date = _fmt_value(r.get('ExecutionDate'))

        data.append({
            'no': i,
            'customer_name': r.get('CustName') or '-',
            'contract_no': r.get('ContNo') or '-',
            'disbursement_date': exec_date,
            'commission_date': exec_date,
            'gross_amount': gross,
            'ppn_amount': ppn,
            'tax_amount': tax,
            'net_payment': net,
            'commission_cam': comm_cam,
        })

    return {
        'data': data,
        'totals': {
            'gross_amount': tot_gross,
            'net_payment': tot_net,
        },
    }

@commission_company_bp.route('/commission-company-report/history')
@login_required
def get_history():
    as_of = _parse_date(request.args.get('as_of', ''))
    if as_of is None:
        return jsonify({'error': 'as_of is required (YYYY-MM-DD)'}), 400

    reg_no = request.args.get('reg_no', '').strip()
    if not reg_no:
        return jsonify({'error': 'reg_no is required'}), 400

    party_type = request.args.get('type', '').strip().upper()
    sort_by_execution = request.args.get('sort_by_execution', '').lower() in ('1', 'true')

    try:
        return jsonify(_fetch_history(as_of, reg_no, party_type, sort_by_execution))
    except Exception as e:
        current_app.logger.exception("Commission company payment history error")
        return jsonify({'error': str(e)}), 500