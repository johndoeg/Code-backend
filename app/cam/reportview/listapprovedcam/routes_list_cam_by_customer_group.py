from __future__ import annotations

from datetime import date
from typing import Optional
from flask import Blueprint, jsonify, request, current_app, Response

from openpyxl import Workbook

from app.auth.decorators import login_required
from app.utils.helpers.base_format import (
    ALL_BORDERS,
    CENTER,
    HEADER_FONT,
    ITALIC_FONT,
    RED_BOLD_FONT,
    RIGHT,
    _access_level,
    _branch,
    _emp_id,
    _username,
    branch_name,
    build_comments_payload,
    exec_rows,
    fetch_revisions,
    fetch_subordinate_ids,
    num,
    parse_iso_date,
    period_label,
    period_label_long,
    today_ddmmyyyy,
    workbook_response,
    write_report_header,
)
from app.utils.helpers.settings_helpers import company_name as get_company_name

cam_by_cust_group_bp = Blueprint('cam_by_cust_group', __name__, url_prefix='/CAM/Approved')

PAGE_SIZE = 100

def _own_branch_name() -> str:
    return branch_name(_branch())

def _resolve_scope() -> dict:
    access_level = _access_level()
    emp_id = _emp_id()
    own_branch_cd = _branch()

    if access_level == 'CMO':
        return {'cmo_filter': [emp_id], 'branch_filter': None}

    if access_level == 'CMH':
        return {'cmo_filter': fetch_subordinate_ids(emp_id), 'branch_filter': None}

    if access_level == 'BM':
        return {'cmo_filter': None, 'branch_filter': own_branch_cd}

    return {'cmo_filter': None, 'branch_filter': None if own_branch_cd == '100' else own_branch_cd}

def _build_common_filter(scope: dict, start_date: Optional[date], end_date: Optional[date],
                          lessee_nm: str, grp_code: str) -> tuple[str, list]:
    clauses = []
    params: list = []

    if scope['cmo_filter'] is not None:
        placeholders = ','.join('?' for _ in scope['cmo_filter'])
        clauses.append(f"a.CMO IN ({placeholders})")
        params.extend(scope['cmo_filter'])
    elif scope['branch_filter']:
        clauses.append("a.BRANCH_CD = ?")
        params.append(scope['branch_filter'])

    if grp_code:
        clauses.append("b.GrpCode = ?")
        params.append(grp_code)

    if start_date and end_date:
        clauses.append("CAST(a.CREATE_DATE AS DATE) >= ? AND CAST(a.CREATE_DATE AS DATE) <= ?")
        params.append(start_date)
        params.append(end_date)

    if lessee_nm:
        clauses.append("b.LESSEE_NM LIKE ?")
        params.append(f"%{lessee_nm}%")

    if not clauses:
        return "1=1", []
    return " AND ".join(clauses), params

_LIST_SELECT = """
SELECT a.APPL_NO, a.Cons_Leas, b.LESSEE_NM, a.TENOR, a.DECLRATE, j.AdmDate,
       c.USERNAME, h.BRAND_NM, i.TYPE_NM, v.Net_Finance,
       a.APLESS, a.HAS_GUARANTOR, b.LESSEE_TP, g.SUPP, LTRIM(RTRIM(g.[CONDITION])) AS CONDITION
FROM CAFCONT a WITH (NOLOCK)
    LEFT JOIN CAFLESS b WITH (NOLOCK) ON a.APLESS = b.APLESS
    LEFT JOIN APP_USRMST c WITH (NOLOCK) ON a.CMO = c.EMPLOYEE_ID
    LEFT JOIN CAFEQUIP g WITH (NOLOCK) ON a.APPL_NO = g.APPL_NO
    LEFT JOIN UMFBRAND h WITH (NOLOCK) ON g.BRAND = h.BRAND
    LEFT JOIN UMFTYPE i WITH (NOLOCK) ON g.BRAND = i.BRAND AND g.TYPE = i.TYPE
    INNER JOIN mcmocamcompletelist j WITH (NOLOCK) ON a.APPL_NO = j.APPL_NO
    INNER JOIN V_NetFinance v WITH (NOLOCK) ON a.APPL_NO = v.APPL_NO
"""

def _fetch_count(where_sql: str, params: list) -> int:
    sql = f"""
    SELECT COUNT(*) AS cnt
    FROM CAFCONT a WITH (NOLOCK)
        LEFT JOIN CAFLESS b WITH (NOLOCK) ON a.APLESS = b.APLESS
        LEFT JOIN CAFEQUIP g WITH (NOLOCK) ON a.APPL_NO = g.APPL_NO
        INNER JOIN mcmocamcompletelist j WITH (NOLOCK) ON a.APPL_NO = j.APPL_NO
        INNER JOIN V_NetFinance v WITH (NOLOCK) ON a.APPL_NO = v.APPL_NO
    WHERE {where_sql}
    """
    rows = exec_rows(sql, params)
    return int(rows[0]['cnt']) if rows else 0

def _fetch_page(where_sql: str, params: list, page: int, page_size: int) -> list[dict]:
    offset = (page - 1) * page_size
    sql = _LIST_SELECT + f"WHERE {where_sql} ORDER BY j.AdmDate OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
    return exec_rows(sql, params + [offset, page_size])

def _fetch_all(where_sql: str, params: list) -> list[dict]:
    sql = _LIST_SELECT + f"WHERE {where_sql} ORDER BY j.AdmDate"
    return exec_rows(sql, params)

def _fetch_date_range(where_sql: str, params: list) -> tuple[Optional[date], Optional[date]]:
    sql = f"""
    SELECT MIN(j.AdmDate) AS min_dt, MAX(j.AdmDate) AS max_dt
    FROM CAFCONT a WITH (NOLOCK)
        LEFT JOIN CAFLESS b WITH (NOLOCK) ON a.APLESS = b.APLESS
        LEFT JOIN CAFEQUIP g WITH (NOLOCK) ON a.APPL_NO = g.APPL_NO
        INNER JOIN mcmocamcompletelist j WITH (NOLOCK) ON a.APPL_NO = j.APPL_NO
        INNER JOIN V_NetFinance v WITH (NOLOCK) ON a.APPL_NO = v.APPL_NO
    WHERE {where_sql}
    """
    rows = exec_rows(sql, params)
    if not rows:
        return None, None
    min_dt, max_dt = rows[0].get('min_dt'), rows[0].get('max_dt')
    return (min_dt.date() if min_dt else None), (max_dt.date() if max_dt else None)

def _edit_link_params(r: dict) -> dict:
    cons_leas = (r.get('Cons_Leas') or '').strip()
    fin_type = cons_leas or None
    guarantor = 2 if r.get('HAS_GUARANTOR') == '1' else 1
    ind_cor = 2 if r.get('LESSEE_TP') == 'PT' else 1
    c2c = 1 if str(r.get('SUPP')) == '999999' else 0
    condition = (r.get('CONDITION') or '').strip()
    new_car = 2 if condition == 'NEW' else 1
    return {
        'id1': fin_type, 'id2': ind_cor, 'id3': 1, 'id4': guarantor, 'id5': new_car,
        'id6': 'Edit', 'id7': r.get('TENOR'), 'id8': c2c,
        'apless': r.get('APLESS'), 'applno': r.get('APPL_NO'),
    }

def _row_to_detail(r: dict, no: int, revision: str) -> dict:
    adm_date = r.get('AdmDate')
    brand = (r.get('BRAND_NM') or '').strip()
    type_nm = (r.get('TYPE_NM') or '').strip()
    return {
        'no': no,
        'cam_no': f"{r.get('Cons_Leas')} - {r.get('APPL_NO')}{revision}",
        'appl_no': r.get('APPL_NO'),
        'customer_name': r.get('LESSEE_NM') or '-',
        'brand_type': f"{brand} / {type_nm}" if (brand or type_nm) else '-',
        'net_finance': num(r.get('Net_Finance')),
        'interest': round(num(r.get('DECLRATE')), 4),
        'tenor': int(num(r.get('TENOR'))),
        'approval_date': adm_date.strftime('%d-%m-%Y') if adm_date else '',
        'cmo': r.get('USERNAME') or '-',
        'is_revision': bool(revision),
        'edit_link_params': _edit_link_params(r),
    }

_TOTAL_BASE = """
SELECT ISNULL(SUM(v.Net_Finance), 0) AS tot_fin, ISNULL(COUNT(a.APPL_NO), 0) AS tot_unit
FROM CAFCONT a WITH (NOLOCK)
    LEFT JOIN CAFLESS b WITH (NOLOCK) ON a.APLESS = b.APLESS
    INNER JOIN mcmocamcompletelist j WITH (NOLOCK) ON a.APPL_NO = j.APPL_NO
    INNER JOIN V_NetFinance v WITH (NOLOCK) ON a.APPL_NO = v.APPL_NO
WHERE a.APPL_NO NOT IN (SELECT NewAppl_No FROM MCMORevisi WITH (NOLOCK) WHERE NewAppl_No IS NOT NULL)
  AND {filter}
"""

def _fetch_grand_total(where_sql: str, params: list) -> dict:
    sql = _TOTAL_BASE.format(filter=where_sql)
    rows = exec_rows(sql, params)
    row = rows[0] if rows else {}
    return {'net_finance': num(row.get('tot_fin')), 'units': int(num(row.get('tot_unit')))}

def _resolve_period(where_sql: str, params: list, start_date, end_date, lessee_nm: str) -> tuple[str, str]:
    if start_date and end_date:
        date_label = period_label(start_date, end_date)
        period_long = period_label_long(start_date, end_date)
    else:
        data_start, data_end = _fetch_date_range(where_sql, params)
        date_label = ''
        period_long = period_label_long(data_start, data_end)
    return (f"Name : {lessee_nm}" if lessee_nm else date_label), period_long

@cam_by_cust_group_bp.route('/cam-by-cust-group/groups')
@login_required
def list_groups():
    try:
        rows = exec_rows(
            "SELECT RTRIM(GrpCode) AS GrpCode, RTRIM(GrpName) AS GrpName FROM CLFGROUP WITH (NOLOCK) WHERE FLGDEL = '0'",
            [],
        )
        return jsonify([{'grp_code': r.get('GrpCode'), 'grp_name': r.get('GrpName')} for r in rows])
    except Exception as e:
        current_app.logger.exception("Group list error")
        return jsonify({'error': str(e)}), 500

@cam_by_cust_group_bp.route('/cam-by-cust-group/context')
@login_required
def get_context():
    return jsonify({'branch_name': _own_branch_name()})

@cam_by_cust_group_bp.route('/cam-by-cust-group/list')
@login_required
def get_list():
    start_date = parse_iso_date(request.args.get('start_date', ''))
    end_date = parse_iso_date(request.args.get('end_date', ''))
    lessee_nm = request.args.get('lessee_nm', '').strip()
    grp_code = request.args.get('grp_code', '').strip()
    try:
        page = max(int(request.args.get('page', 1) or 1), 1)
    except ValueError:
        page = 1

    scope = _resolve_scope()
    where_sql, params = _build_common_filter(scope, start_date, end_date, lessee_nm, grp_code)

    try:
        total_count = _fetch_count(where_sql, params)
        total_pages = max((total_count + PAGE_SIZE - 1) // PAGE_SIZE, 1)
        page = min(page, total_pages)

        raw_rows = _fetch_page(where_sql, params, page, PAGE_SIZE)
        appl_nos = [r['APPL_NO'] for r in raw_rows if r.get('APPL_NO')]
        revisions = fetch_revisions(appl_nos)

        start_no = (page - 1) * PAGE_SIZE + 1
        details = [_row_to_detail(r, start_no + i, revisions.get(r['APPL_NO'], '')) for i, r in enumerate(raw_rows)]

        grand_total = _fetch_grand_total(where_sql, params)
        period, period_long = _resolve_period(where_sql, params, start_date, end_date, lessee_nm)

        return jsonify({
            'rows': details,
            'total_count': total_count,
            'page': page,
            'page_size': PAGE_SIZE,
            'total_pages': total_pages,
            'grand_total': grand_total,
            'period_label': period,
            'grand_total_period': period_long,
            'company_name': get_company_name(),
            'printed_by': _username(),
            'branch_name': _own_branch_name(),
        })
    except Exception as e:
        current_app.logger.exception("CAM by Customer/Group list error")
        return jsonify({'error': str(e)}), 500

_LIST_COLUMNS = ['No.', 'CAM No.', 'Customer Name', 'Brand/Type', 'Net Finance', 'Interest (%)', 'Tenor (Month)',
                  'Approval Date', 'CMO']

def _build_workbook(period_text: str, period_long: str, lessee_nm: str, branch_label: str, rows: list[dict], grand_total: dict) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = 'CamByCustGroup'

    write_report_header(
        ws,
        title='List CAM by Customer / Group',
        branch_line=f"Branch : {branch_label}",
        period_line=period_text,
        stamp_cell='I1',
        row_height=28,
    )
    ws.column_dimensions['I'].width = max(ws.column_dimensions['I'].width or 0, 20)

    row_num = 6
    for col_idx, label in enumerate(_LIST_COLUMNS, start=1):
        cell = ws.cell(row=row_num, column=col_idx, value=label)
        cell.border = ALL_BORDERS
        cell.alignment = CENTER
        cell.font = HEADER_FONT
    row_num += 1

    if not rows:
        ws.merge_cells(f'A{row_num}:I{row_num}')
        cell = ws[f'A{row_num}']
        cell.value = 'Data Not Found'
        cell.font = RED_BOLD_FONT
        cell.alignment = CENTER
        row_num += 1
    else:
        for d in rows:
            values = [d['no'], d['cam_no'], d['customer_name'], d['brand_type'], d['net_finance'],
                      d['interest'], d['tenor'], d['approval_date'], d['cmo']]
            for col_idx, val in enumerate(values, start=1):
                cell = ws.cell(row=row_num, column=col_idx, value=val)
                cell.border = ALL_BORDERS
                if col_idx in (5, 6):
                    cell.alignment = RIGHT
            row_num += 1

    row_num += 2
    ws.merge_cells(f'A{row_num}:B{row_num}')
    ws[f'A{row_num}'] = f"Grand Total* ({period_long or 'All Dates'})"
    ws[f'A{row_num}'].font = HEADER_FONT
    row_num += 1
    ws.cell(row=row_num, column=1, value='Net Finance')
    ws.cell(row=row_num, column=2, value=grand_total['net_finance']).alignment = RIGHT
    row_num += 1
    ws.cell(row=row_num, column=1, value='Units')
    ws.cell(row=row_num, column=2, value=grand_total['units']).alignment = RIGHT
    row_num += 2
    ws.merge_cells(f'A{row_num}:D{row_num}')
    ws[f'A{row_num}'] = '*Grand Total Amount and Unit Exclude CAM Revision'
    ws[f'A{row_num}'].font = ITALIC_FONT

    ws.column_dimensions['A'].width = 6
    for col in 'BCDEFGHI':
        ws.column_dimensions[col].width = 16

    return wb

@cam_by_cust_group_bp.route('/cam-by-cust-group/export')
@login_required
def export_excel():
    start_date = parse_iso_date(request.args.get('start_date', ''))
    end_date = parse_iso_date(request.args.get('end_date', ''))
    lessee_nm = request.args.get('lessee_nm', '').strip()
    grp_code = request.args.get('grp_code', '').strip()

    scope = _resolve_scope()
    where_sql, params = _build_common_filter(scope, start_date, end_date, lessee_nm, grp_code)

    try:
        raw_rows = _fetch_all(where_sql, params)
        appl_nos = [r['APPL_NO'] for r in raw_rows if r.get('APPL_NO')]
        revisions = fetch_revisions(appl_nos)
        rows = [_row_to_detail(r, i, revisions.get(r['APPL_NO'], '')) for i, r in enumerate(raw_rows, start=1)]
        grand_total = _fetch_grand_total(where_sql, params)
        period, period_long = _resolve_period(where_sql, params, start_date, end_date, lessee_nm)

        wb = _build_workbook(period, period_long, lessee_nm, _own_branch_name(), rows, grand_total)
        return workbook_response(wb, 'ListCamByCustGroup.xlsx')
    except Exception as e:
        current_app.logger.exception("CAM by Customer/Group export error")
        return jsonify({'error': str(e)}), 500

_PRINT_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{company} - List CAM by Customer / Group</title>
<style>
body {{ font-family: Tahoma, Geneva, sans-serif; font-size: 12px; }}
td {{ font-size: 12px; }}
table {{ border-collapse: collapse; }}
</style>
</head>
<body bgcolor="#FFFFFF" onload="window.print();">
    <table cellpadding="2" cellspacing="0" width="100%">
        <tr>
            <td width="25%" nowrap="nowrap">{company}</td>
            <td width="50%"></td>
            <td width="10%"></td>
            <td width="15%">Date : {today}<br>Print By : {printed_by}</td>
        </tr>
        <tr>
            <td colspan="4" align="center" style="font-size:16px; letter-spacing:0.2em;"><strong>List CAM by Customer / Group</strong></td>
        </tr>
        <tr><td colspan="4">Branch : {branch_name}</td></tr>
        <tr><td colspan="4" nowrap="nowrap">{period}</td></tr>
    </table>
    <table cellpadding="2" cellspacing="0" width="100%" style="margin-top:6px;">
        <tr align="center">
            <td style="border:thin solid #000" width="3%">No.</td>
            <td style="border:thin solid #000" width="14%">CAM No.</td>
            <td style="border:thin solid #000" width="16%">Customer Name</td>
            <td style="border:thin solid #000" width="17%">Brand/Type</td>
            <td style="border:thin solid #000" width="12%">Net Finance</td>
            <td style="border:thin solid #000" width="6%">Interest (%)</td>
            <td style="border:thin solid #000" width="5%">Tenor (Month)</td>
            <td style="border:thin solid #000" width="11%">Approval Date</td>
            <td style="border:thin solid #000" width="16%">CMO</td>
        </tr>
        {rows_html}
    </table>
    <table border="0" style="border-collapse:collapse; margin-top:10px;" cellpadding="2" cellspacing="0" width="100%">
        <tr>
            <td width="40%" colspan="2">
                <u><strong>Grand Total* ({period_plain}):</strong></u>
            </td>
        </tr>
        <tr>
            <td width="10%">Net Finance</td>
            <td>: {grand_fin}</td>
        </tr>
        <tr>
            <td width="10%">Units</td>
            <td> : {grand_units}</td>
        </tr>
        <tr><td colspan="2">&nbsp;</td></tr>
        <tr><td colspan="2"><i>*Grand Total Amount and Unit Exclude CAM Revision</i></td></tr>
    </table>
</body>
</html>"""

def _render_rows_html(rows: list[dict]) -> str:
    if not rows:
        return ('<tr><td colspan="9" align="center" style="border:thin solid #000">'
                '<font color="red"><b>Data Not Found</b></font></td></tr>')
    parts = []
    for d in rows:
        parts.append(f"""
            <tr>
                <td style="border:thin solid #000" align="center">{d['no']}</td>
                <td style="border:thin solid #000">{d['cam_no']}</td>
                <td style="border:thin solid #000">{d['customer_name']}</td>
                <td style="border:thin solid #000">{d['brand_type']}</td>
                <td style="border:thin solid #000" align="right">{d['net_finance']:,.0f}</td>
                <td style="border:thin solid #000" align="right">{d['interest']:.4f}</td>
                <td style="border:thin solid #000" align="center">{d['tenor']}</td>
                <td style="border:thin solid #000">{d['approval_date']}</td>
                <td style="border:thin solid #000">{d['cmo']}</td>
            </tr>""")
    return ''.join(parts)

@cam_by_cust_group_bp.route('/cam-by-cust-group/print')
@login_required
def print_view():
    start_date = parse_iso_date(request.args.get('start_date', ''))
    end_date = parse_iso_date(request.args.get('end_date', ''))
    lessee_nm = request.args.get('lessee_nm', '').strip()
    grp_code = request.args.get('grp_code', '').strip()

    scope = _resolve_scope()
    where_sql, params = _build_common_filter(scope, start_date, end_date, lessee_nm, grp_code)

    try:
        raw_rows = _fetch_all(where_sql, params)
        appl_nos = [r['APPL_NO'] for r in raw_rows if r.get('APPL_NO')]
        revisions = fetch_revisions(appl_nos)
        rows = [_row_to_detail(r, i, revisions.get(r['APPL_NO'], '')) for i, r in enumerate(raw_rows, start=1)]
        grand_total = _fetch_grand_total(where_sql, params)
        period, period_long = _resolve_period(where_sql, params, start_date, end_date, lessee_nm)

        html = _PRINT_TEMPLATE.format(
            company=get_company_name(),
            today=today_ddmmyyyy(),
            printed_by=_username(),
            branch_name=_own_branch_name(),
            period=period,
            period_plain=period_long or 'All Dates',
            rows_html=_render_rows_html(rows),
            grand_fin=f"{grand_total['net_finance']:,.0f}",
            grand_units=grand_total['units'],
        )
        return Response(html, mimetype='text/html')
    except Exception as e:
        current_app.logger.exception("CAM by Customer/Group print error")
        return jsonify({'error': str(e)}), 500

@cam_by_cust_group_bp.route('/cam-by-cust-group/comments')
@login_required
def get_comments():
    appl_no = request.args.get('appl_no', '').strip()
    if not appl_no:
        return jsonify({'error': 'appl_no is required'}), 400

    try:
        return jsonify(build_comments_payload(appl_no))
    except Exception as e:
        current_app.logger.exception("Credit committee comments error")
        return jsonify({'error': str(e)}), 500