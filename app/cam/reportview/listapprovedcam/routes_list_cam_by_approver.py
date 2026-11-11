from __future__ import annotations

from datetime import date
from typing import Optional
from flask import Blueprint, jsonify, request, current_app, session, Response

from openpyxl import Workbook

from app.auth.decorators import login_required
from app.utils.helpers.base_format import (
    ALL_BORDERS,
    CENTER,
    COMMITTEE_ROLE_CODES,
    HEADER_FONT,
    ITALIC_FONT,
    RED_BOLD_FONT,
    RIGHT,
    _username,
    branch_name,
    build_comments_payload,
    exec_rows,
    fetch_branch_list,
    num,
    parse_iso_date,
    period_label,
    sp_date,
    today_ddmmyyyy,
    workbook_response,
    write_report_header,
)
from app.utils.helpers.settings_helpers import company_name as get_company_name

cam_by_approver_bp = Blueprint('cam_by_approver', __name__, url_prefix='/CAM/Approved')

_ROLE_LABELS = {
    'CRH': 'CREDIT REVIEW UNIT HEAD',
    'ODH': 'BUSINESS OPERATION DIVISION HEAD',
    'CRDH': 'CREDIT REVIEW DIVISION HEAD',
    'DR': 'BUSINESS OPERATION DIRECTOR',
    'PD': 'PRESIDENT DIRECTOR',
}
_APPROVER_ROLES = [(code, _ROLE_LABELS[code]) for code in COMMITTEE_ROLE_CODES]

def _resolve_branch(requested_branch_cd: str) -> dict:
    own_branch_cd = session.get('branchcode')
    if own_branch_cd == '100':
        return {'disabled': False, 'search_branch': requested_branch_cd}
    return {'disabled': True, 'search_branch': own_branch_cd}

@cam_by_approver_bp.route('/cam-by-approver/branches')
@login_required
def list_branches():
    try:
        return jsonify(fetch_branch_list())
    except Exception as e:
        current_app.logger.exception("Branch list error")
        return jsonify({'error': str(e)}), 500

@cam_by_approver_bp.route('/cam-by-approver/context')
@login_required
def get_context():
    resolved = _resolve_branch(request.args.get('branch_cd', '').strip())
    return jsonify({'disabled': resolved['disabled'], 'forced_branch_cd': resolved['search_branch']})

def _exec_sp_approver(start_date: Optional[date], end_date: Optional[date], branch_cd: str, mode: str) -> list[dict]:
    return exec_rows(
        "EXEC USP_CAM_By_Approver ?, ?, ?, ?",
        [sp_date(start_date), sp_date(end_date), branch_cd, mode],
    )

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

def _fetch_link_extra(appl_nos: list[str]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    unique = list(dict.fromkeys(appl_nos))
    for i in range(0, len(unique), 1000):
        chunk = unique[i:i + 1000]
        placeholders = ','.join('?' for _ in chunk)
        rows = exec_rows(
            f"""
            SELECT a.APPL_NO, a.APLESS, a.TENOR, a.HAS_GUARANTOR, b.LESSEE_TP, g.SUPP,
                   LTRIM(RTRIM(g.[CONDITION])) AS CONDITION
            FROM CAFCONT a WITH (NOLOCK)
                LEFT JOIN CAFLESS b WITH (NOLOCK) ON a.APLESS = b.APLESS
                LEFT JOIN CAFEQUIP g WITH (NOLOCK) ON a.APPL_NO = g.APPL_NO
            WHERE a.APPL_NO IN ({placeholders})
            """,
            chunk,
        )
        for row in rows:
            result.setdefault(row['APPL_NO'], row)
    return result

def _row_to_detail(r: dict, no: int, link_extra: Optional[dict] = None) -> dict:
    revisi = r.get('Revisi')
    revision_suffix = f"R{revisi}" if revisi else ''
    appr_date = r.get('APPR_DATE')
    detail = {
        'no': no,
        'branch_name': r.get('BRANCH_NAME') or '-',
        'customer_name': r.get('LESSEE_NM') or '-',
        'cam_no': f"{r.get('Cons_Leas')} - {r.get('APPL_NO')}{revision_suffix}",
        'appl_no': r.get('APPL_NO'),
        'approved_date': appr_date.strftime('%d-%m-%Y') if appr_date else '',
        'model': r.get('model'),
        'brand_type': r.get('tipe_mobil'),
        'car_status': r.get('CONDITION'),
        'contract_status': r.get('ContractStatus'),
        'outstanding_old_cam': num(r.get('Out_OldCAM')),
        'net_finance_new_cam': num(r.get('Out_NewCAM')),
        'total_outstanding': num(r.get('TotOut')),
        'cmo': r.get('CMO') or '-',
    }
    if link_extra is not None:
        detail['edit_link_params'] = _edit_link_params({**r, **link_extra})
    return detail

def _fetch_report(start_date: Optional[date], end_date: Optional[date], branch_cd: str,
                  with_links: bool = False) -> dict:
    raw_sections = [
        (role_code, role_label, _exec_sp_approver(start_date, end_date, branch_cd, role_code))
        for role_code, role_label in _APPROVER_ROLES
    ]

    link_extra: dict[str, dict] = {}
    if with_links:
        appl_nos = [r['APPL_NO'] for _, _, rows in raw_sections for r in rows if r.get('APPL_NO')]
        link_extra = _fetch_link_extra(appl_nos)

    sections = []
    for role_code, role_label, rows in raw_sections:
        sections.append({
            'role_code': role_code,
            'role_label': role_label,
            'rows': [
                _row_to_detail(r, i, link_extra.get(r.get('APPL_NO'), {}) if with_links else None)
                for i, r in enumerate(rows, start=1)
            ],
        })

    total_rows = _exec_sp_approver(start_date, end_date, branch_cd, 'TOTAL')
    total = total_rows[0] if total_rows else {}
    return {
        'sections': sections,
        'grand_total': {
            'net_finance': num(total.get('tot_ntf')),
            'units': int(num(total.get('tot_unit'))),
        },
    }

@cam_by_approver_bp.route('/cam-by-approver/list')
@login_required
def get_list():
    start_date = parse_iso_date(request.args.get('start_date', ''))
    end_date = parse_iso_date(request.args.get('end_date', ''))
    requested_branch = request.args.get('branch_cd', '').strip()

    scope = _resolve_branch(requested_branch)
    try:
        result = _fetch_report(start_date, end_date, scope['search_branch'], with_links=True)
        return jsonify({
            **result,
            'disabled': scope['disabled'],
            'search_branch': scope['search_branch'],
            'company_name': get_company_name(),
            'printed_by': _username(),
            'branch_name': branch_name(scope['search_branch']),
            'period_label': period_label(start_date, end_date),
        })
    except Exception as e:
        current_app.logger.exception("CAM by Approver list error")
        return jsonify({'error': str(e)}), 500

_COLUMNS = [
    'No.', 'Branch', 'Customer Name', 'CAM No.', 'Approved Date', 'Model', 'Brand/Type',
    'Car Status', 'Contract Status', 'Outstanding', 'Net Finance', 'Total Outstanding', 'CMO',
]

def _build_workbook(start_date, end_date, branch_cd, result: dict) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = 'CamByApprover'

    write_report_header(
        ws,
        title='List CAM by Approver',
        branch_line=f"Branch : {branch_name(branch_cd)}",
        period_line=period_label(start_date, end_date),
        stamp_cell='M1',
    )

    row_num = 6
    for section in result['sections']:
        ws.merge_cells(f'A{row_num}:M{row_num}')
        ws[f'A{row_num}'] = f"Approved by : {section['role_label']}"
        ws[f'A{row_num}'].border = ALL_BORDERS
        ws[f'A{row_num}'].font = HEADER_FONT
        row_num += 1

        for col_idx, label in enumerate(_COLUMNS, start=1):
            cell = ws.cell(row=row_num, column=col_idx, value=label)
            cell.border = ALL_BORDERS
            cell.alignment = CENTER
            cell.font = HEADER_FONT
        row_num += 1

        if not section['rows']:
            ws.merge_cells(f'A{row_num}:M{row_num}')
            cell = ws[f'A{row_num}']
            cell.value = 'Data Not Found'
            cell.font = RED_BOLD_FONT
            cell.alignment = CENTER
            row_num += 1
        else:
            for d in section['rows']:
                values = [
                    d['no'], d['branch_name'], d['customer_name'], d['cam_no'], d['approved_date'],
                    d['model'], d['brand_type'], d['car_status'], d['contract_status'],
                    d['outstanding_old_cam'], d['net_finance_new_cam'], d['total_outstanding'], d['cmo'],
                ]
                for col_idx, val in enumerate(values, start=1):
                    cell = ws.cell(row=row_num, column=col_idx, value=val)
                    cell.border = ALL_BORDERS
                    if col_idx in (10, 11, 12):
                        cell.alignment = RIGHT
                row_num += 1

    row_num += 1
    ws.merge_cells(f'A{row_num}:B{row_num}')
    ws[f'A{row_num}'] = f"Grand Total* ({period_label(start_date, end_date).replace('Period : ', '')})"
    ws[f'A{row_num}'].font = HEADER_FONT
    row_num += 1
    ws.cell(row=row_num, column=1, value='Net Finance')
    ws.cell(row=row_num, column=2, value=result['grand_total']['net_finance']).alignment = RIGHT
    row_num += 1
    ws.cell(row=row_num, column=1, value='Units')
    ws.cell(row=row_num, column=2, value=result['grand_total']['units']).alignment = RIGHT
    row_num += 2
    ws.merge_cells(f'A{row_num}:D{row_num}')
    ws[f'A{row_num}'] = '*Grand Total Amount and Unit Exclude CAM Revision'
    ws[f'A{row_num}'].font = ITALIC_FONT

    ws.column_dimensions['A'].width = 6
    for col in 'BCDEFGHIJKLM':
        ws.column_dimensions[col].width = 16

    ws.column_dimensions['M'].width = 22

    return wb

@cam_by_approver_bp.route('/cam-by-approver/export')
@login_required
def export_excel():
    start_date = parse_iso_date(request.args.get('start_date', ''))
    end_date = parse_iso_date(request.args.get('end_date', ''))
    requested_branch = request.args.get('branch_cd', '').strip()

    scope = _resolve_branch(requested_branch)
    try:
        result = _fetch_report(start_date, end_date, scope['search_branch'])
        wb = _build_workbook(start_date, end_date, scope['search_branch'], result)
        return workbook_response(wb, 'ListCamByApprover.xlsx')
    except Exception as e:
        current_app.logger.exception("CAM by Approver export error")
        return jsonify({'error': str(e)}), 500

_PRINT_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{company} - Credit Approval Memorandum</title>
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
            <td width="15%">Date : {today}</td>
        </tr>
        <tr>
            <td></td>
            <td align="center" style="font-size:20px; letter-spacing:0.2em;"><strong>List CAM by Approver</strong></td>
            <td></td>
            <td nowrap="nowrap">Print By : {printed_by}</td>
        </tr>
        <tr><td>Branch : {branch_name}</td></tr>
        <tr><td nowrap="nowrap">{period}</td></tr>
        <tr>
            <td colspan="4">
                <table cellpadding="2" cellspacing="0" width="100%">
                    <tr align="center">
                        <td style="border:thin solid #000">No.</td><td style="border:thin solid #000">Branch</td>
                        <td style="border:thin solid #000">Customer Name</td><td style="border:thin solid #000">CAM No.</td>
                        <td style="border:thin solid #000">Approved Date</td><td style="border:thin solid #000">Model</td>
                        <td style="border:thin solid #000">Brand/Type</td><td style="border:thin solid #000">Car Status</td>
                        <td style="border:thin solid #000">Contract Status</td><td style="border:thin solid #000">Outstanding</td>
                        <td style="border:thin solid #000">Net Finance</td><td style="border:thin solid #000">Total Outstanding</td>
                        <td style="border:thin solid #000">CMO</td>
                    </tr>
                {rows_html}
                </table>
            </td>
        </tr>
        <tr><td colspan="2" height="30px"></td></tr>
        <tr>
            <td colspan="2">
                <table cellpadding="2" cellspacing="0" width="100%">
                        <tr><td width="40%" colspan="2"><u><strong>Grand Total* ({period_plain}):</strong></u></td></tr>
                        <tr><td width="10%">Net Finance</td><td>: {grand_net_finance}</td></tr>
                        <tr><td width="10%">Units</td><td> : {grand_units}</td></tr>
                        <tr><td colspan="2">&nbsp;</td></tr>
                        <tr><td colspan="2"><i>*Grand Total Amount and Unit Exclude CAM Revision</i></td></tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

def _render_section_rows_html(sections: list[dict]) -> str:
    parts = []
    for section in sections:
        parts.append(f'<tr><td colspan="13" style="border:thin solid #000">Approved by : {section["role_label"]}</td></tr>')
        if not section['rows']:
            parts.append('<tr><td style="background-color:#E5E5E5; border:thin solid #000" colspan="13" align="center"><font color="red"><b>Data Not Found</b></font></td></tr>')
            continue
        for i, d in enumerate(section['rows']):
            warna = '#E5E5E5' if i % 2 == 0 else '#F5F5F5'
            parts.append(f"""
                <tr style="background-color:{warna}">
                    <td style="border:thin solid #000" align="center">{d['no']}</td>
                    <td style="border:thin solid #000">{d['branch_name']}</td>
                    <td style="border:thin solid #000">{d['customer_name']}</td>
                    <td style="border:thin solid #000">{d['cam_no']}</td>
                    <td style="border:thin solid #000">{d['approved_date']}</td>
                    <td style="border:thin solid #000">{d['model']}</td>
                    <td style="border:thin solid #000">{d['brand_type']}</td>
                    <td style="border:thin solid #000">{d['car_status']}</td>
                    <td style="border:thin solid #000">{d['contract_status']}</td>
                    <td style="border:thin solid #000" align="right">{d['outstanding_old_cam']:,.0f}</td>
                    <td style="border:thin solid #000" align="right">{d['net_finance_new_cam']:,.0f}</td>
                    <td style="border:thin solid #000" align="right">{d['total_outstanding']:,.0f}</td>
                    <td style="border:thin solid #000">{d['cmo']}</td>
                </tr>""")
    return ''.join(parts)

@cam_by_approver_bp.route('/cam-by-approver/print')
@login_required
def print_view():
    start_date = parse_iso_date(request.args.get('start_date', ''))
    end_date = parse_iso_date(request.args.get('end_date', ''))
    requested_branch = request.args.get('branch_cd', '').strip()

    scope = _resolve_branch(requested_branch)
    try:
        result = _fetch_report(start_date, end_date, scope['search_branch'])
        period = period_label(start_date, end_date)
        html = _PRINT_TEMPLATE.format(
            company=get_company_name(),
            today=today_ddmmyyyy(),
            printed_by=_username(),
            branch_name=branch_name(scope['search_branch']),
            period=period,
            period_plain=period.replace('Period : ', ''),
            rows_html=_render_section_rows_html(result['sections']),
            grand_net_finance=f"{result['grand_total']['net_finance']:,.0f}",
            grand_units=f"{result['grand_total']['units']:,}",
        )
        return Response(html, mimetype='text/html')
    except Exception as e:
        current_app.logger.exception("CAM by Approver print error")
        return jsonify({'error': str(e)}), 500

@cam_by_approver_bp.route('/cam-by-approver/comments')
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