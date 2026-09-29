from __future__ import annotations

from typing import Optional
from flask import Blueprint, jsonify, request, current_app, session

from app import db
from app.auth.decorators import login_required

detail_incentive_3rd_party_bp = Blueprint('detail_incentive_3rd_party', __name__, url_prefix='/CAM/Incentive')

_INDO_MONTHS = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli',
                'Agustus', 'September', 'Oktober', 'November', 'Desember']

_HO_BRANCH_CODES = ('100', '000')

def _month_name(month_num) -> str:
    try:
        n = int(month_num)
    except (TypeError, ValueError):
        return str(month_num)
    if 1 <= n <= 12:
        return _INDO_MONTHS[n - 1]
    return str(n)

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

@detail_incentive_3rd_party_bp.route('/detail-incentive-3rd-party-report/branches')
@login_required
def list_branches():
    try:
        rows = _exec_rows(
            "SELECT BRANCH_CD, BRANCH_NAME FROM UMFBRANCH WITH (NOLOCK) "
            "WHERE BRANCH_CD <> '100' ORDER BY BRANCH_NAME",
            [],
        )
        return jsonify([{'branch_cd': r['BRANCH_CD'], 'branch_name': r['BRANCH_NAME']} for r in rows])
    except Exception as e:
        current_app.logger.exception("Branch list error")
        return jsonify({'error': str(e)}), 500

@detail_incentive_3rd_party_bp.route('/detail-incentive-3rd-party-report/cmo-options')
@login_required
def cmo_options():
    branch_cd = request.args.get('branch_cd', '').strip()
    accesslevel = session.get('accesslevel', '')
    employee_id = session.get('emp_id', '')

    sql = ("SELECT FULLNAME, EMPLOYEE_ID FROM APP_USRMST WITH (NOLOCK) "
           "WHERE ACCESSCAM = 'CMO' AND RECSTATUS = 'A'")
    params: list = []

    if accesslevel == 'CMO':
        sql += " AND EMPLOYEE_ID = ?"
        params.append(employee_id)

    if branch_cd and branch_cd not in _HO_BRANCH_CODES:
        sql += " AND BRANCHCODE = ?"
        params.append(branch_cd)

    sql += " ORDER BY FULLNAME"

    try:
        rows = _exec_rows(sql, params)
        return jsonify([{'employee_id': r['EMPLOYEE_ID'], 'full_name': r['FULLNAME']} for r in rows])
    except Exception as e:
        current_app.logger.exception("CMO options error")
        return jsonify({'error': str(e)}), 500

@detail_incentive_3rd_party_bp.route('/detail-incentive-3rd-party-report/dealers')
@login_required
def search_dealers():
    branch_cd = request.args.get('branch_cd', '').strip()
    search_name = request.args.get('search', '').strip()

    where = []
    params: list = []
    if branch_cd:
        where.append("BRANCH_CD = ?")
        params.append(branch_cd)
    if search_name:
        where.append("NAME LIKE ?")
        params.append(f"%{search_name}%")
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    try:
        rows = _exec_rows(
            f"""
            SELECT TOP 100 SUPP, NAME, NICKNAME, ADDRESS, PHONE, CONTACT
            FROM CLFSUPP WITH (NOLOCK) {where_sql}
            ORDER BY NAME
            """,
            params,
        )
        return jsonify([
            {
                'supp': r.get('SUPP'),
                'name': r.get('NAME') or '-',
                'nickname': r.get('NICKNAME') or '',
                'address': r.get('ADDRESS') or '-',
                'phone': r.get('PHONE') or '-',
                'contact': r.get('CONTACT') or '-',
            }
            for r in rows
        ])
    except Exception as e:
        current_app.logger.exception("Dealer search error")
        return jsonify({'error': str(e)}), 500

_MONTHLY_QUERY = """
    SELECT
        MONTH(a.EXECUTION) AS MonthNum,
        SUM(ISNULL(n.TOTAL_INCOME, 0)) AS TotalIncome,
        SUM(ISNULL(n.COMM_THIRDPARTY, 0)) AS Incentive3rdParty,
        SUM(ISNULL(k.gross, 0)) + SUM(ISNULL(k.ppn_amount, 0)) AS PaidIncentive
    FROM CLFCONT a WITH (NOLOCK)
        INNER JOIN CLFLESS b WITH (NOLOCK) ON a.LESSEE_NO = b.LESSEE_NO
        LEFT JOIN CLFEQUIP d WITH (NOLOCK) ON a.LEASE_NO = d.LEASE_NO
        LEFT JOIN CAFCONT f WITH (NOLOCK) ON a.APPL_NO = f.APPL_NO
        LEFT JOIN (
            SELECT APPL_NO, SUM(GrossAmount) AS gross, SUM(PPNAmount) AS ppn_amount
            FROM CAFKOMIS WITH (NOLOCK)
            WHERE PaidBy = 'I'
            GROUP BY APPL_NO
        ) k ON a.APPL_NO = k.APPL_NO
        LEFT JOIN COMM_PARTY n WITH (NOLOCK) ON a.APPL_NO = n.APPL_NO
    WHERE YEAR(a.EXECUTION) = ?
        {where_extra}
    GROUP BY MONTH(a.EXECUTION)
    ORDER BY MONTH(a.EXECUTION)
"""

def _build_monthly_where(branch_cd: str, supplier: str, cmo: str,
                         accesslevel: str, employee_id: str) -> tuple[str, list]:
    where = []
    params: list = []

    if branch_cd:
        where.append("a.BRANCH_CD = ?")
        params.append(branch_cd)
    if supplier:
        where.append("d.SUPP = ?")
        params.append(supplier)
    if cmo:
        where.append("f.CMO = ?")
        params.append(cmo)

    if accesslevel == 'CMO':
        where.append("a.CMO = ?")
        params.append(employee_id)

    where_extra = ("AND " + " AND ".join(where)) if where else ""
    return where_extra, params

def _fetch_monthly(year: int, branch_cd: str, supplier: str, cmo: str,
                   accesslevel: str, employee_id: str) -> list[dict]:
    
    where_extra, params = _build_monthly_where(branch_cd, supplier, cmo, accesslevel, employee_id)
    sql = _MONTHLY_QUERY.format(where_extra=where_extra)
    rows = _exec_rows(sql, [year] + params)

    result = []
    cum_paid = 0.0
    cum_income = 0.0

    for r in rows:
        total_income = float(r.get('TotalIncome') or 0)
        incentive_3rd = float(r.get('Incentive3rdParty') or 0)
        paid_incentive = float(r.get('PaidIncentive') or 0)
        incentive_excess = max(paid_incentive - incentive_3rd, 0)

        cum_paid += paid_incentive
        cum_income += total_income

        monthly_pct = round(paid_incentive / total_income * 100, 2) if total_income else None
        ytd_pct = round(cum_paid / cum_income * 100, 2) if cum_income else None

        month_num = r.get('MonthNum')
        result.append({
            'month': month_num,
            'month_name': _month_name(month_num),
            'total_income': total_income,
            'incentive_3rd_party': incentive_3rd,
            'incentive_excess': incentive_excess,
            'paid_incentive': paid_incentive,
            'monthly_fee_pct': monthly_pct,
            'ytd_fee_pct': ytd_pct,
        })

    return result

@detail_incentive_3rd_party_bp.route('/detail-incentive-3rd-party-report/monthly')
@login_required
def monthly_report():
    try:
        year = int(request.args.get('year', ''))
    except (TypeError, ValueError):
        return jsonify({'error': 'A valid year is required'}), 400

    branch_cd = request.args.get('branch_cd', '').strip()
    supplier = request.args.get('supplier', '').strip()
    cmo = request.args.get('cmo', '').strip()

    accesslevel = session.get('accesslevel', '')
    employee_id = session.get('emp_id', '')

    try:
        data = _fetch_monthly(year, branch_cd, supplier, cmo, accesslevel, employee_id)
        return jsonify({'data': data, 'year': year})
    except Exception as e:
        current_app.logger.exception("Incentive monthly report error")
        return jsonify({'error': str(e)}), 500