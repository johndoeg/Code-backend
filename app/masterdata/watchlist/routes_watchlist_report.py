from __future__ import annotations

import io
from datetime import date, datetime
from typing import Optional

from flask import Blueprint, jsonify, request, current_app, send_file
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter

from app.auth.decorators import login_required
from app.utils.helpers.shared_helpers import _exec_rows, _exec_scalar

watchlist_report_bp = Blueprint('watchlist_report', __name__, url_prefix='/MasterData')

SEARCH_BY_CUSTOMER_NO = '1'
SEARCH_BY_CUSTOMER_NAME = '2'

FLAG_ACTIVE = '0'
FLAG_DELETED = '1'

AS_OF_REQUIRED_MESSAGE = 'Please fill the as of date first.'

_FROM_JOINS = """
    FROM MCMOWatchList mw WITH (NOLOCK)
    LEFT JOIN cafless  cf WITH (NOLOCK) ON cf.APLESS = mw.APLESS
    LEFT JOIN MSTCOMBO ms WITH (NOLOCK) ON ms.CAT_VALUE = 'BLACKLIST_CATEGORY'
                                       AND ms.VALUE = mw.Reason_Category
"""

_SELECT_COLS = """
    SELECT
        mw.Name       AS Name,
        cf.APLESS     AS APLESS,
        mw.Address    AS Address,
        mw.ID_Card    AS ID_Card,
        mw.Phone      AS Phone,
        CASE WHEN mw.Reason_Category = '5' THEN mw.Reason_Other ELSE ms.DESC_VALUE END AS Reason,
        mw.CreateUser AS CreateUser,
        mw.CreateDate AS CreateDate,
        IIF(mw.Flagdel = '1', 'Deleted', 'Active') AS Status,
        mw.DeleteBy   AS DeleteBy
"""

_ORDER_BY = " ORDER BY ISNULL(mw.Name, '-') DESC, mw.no DESC"

COLUMNS = (
    ("No", "no", 6),
    ("Customer Name", "name", 30),
    ("Customer Number", "customer_no", 16),
    ("Address", "address", 45),
    ("ID Card", "id_card", 20),
    ("Phone", "phone", 16),
    ("Reason", "reason", 28),
    ("Create By", "create_user", 14),
    ("Create Date", "create_date", 12),
    ("Status", "status", 10),
    ("Delete By", "delete_by", 14),
)

_CENTER_KEYS = {"no", "create_date", "status", "delete_by"}

def _dash(value) -> str:
    v = "" if value is None else str(value).strip()
    return v if v else "-"

def _dmy(value) -> str:
    if isinstance(value, (datetime, date)):
        return value.strftime('%d-%m-%Y')
    return _dash(value)

def _like_contains(text_value: str) -> str:
    escaped = text_value.replace('[', '[[]').replace('%', '[%]').replace('_', '[_]')
    return f'%{escaped}%'

def _parse_args(args) -> dict:
    as_of_raw = (args.get('as_of') or '').strip()
    if not as_of_raw:
        raise ValueError(AS_OF_REQUIRED_MESSAGE)
    try:
        as_of = datetime.strptime(as_of_raw, '%Y-%m-%d').date()
    except ValueError as exc:
        raise ValueError('as_of must be in YYYY-MM-DD format') from exc

    searchby = (args.get('searchby') or '').strip()
    if searchby not in (SEARCH_BY_CUSTOMER_NO, SEARCH_BY_CUSTOMER_NAME):
        searchby = ''

    return {
        'as_of': as_of,
        'as_of_raw': as_of_raw,
        'searchby': searchby,
        'searchbytext': (args.get('searchbytext') or '').strip(),
        'existing': (args.get('existing') or '').strip() == '1',
        'deleted': (args.get('deleted') or '').strip() == '1',
    }

def _build_where(p: dict) -> Optional[tuple[str, list]]:
    flags = []
    if p['existing']:
        flags.append(FLAG_ACTIVE)
    if p['deleted']:
        flags.append(FLAG_DELETED)
    if not flags:
        return None

    where = [
        "CONVERT(date, mw.CreateDate) <= ?",
        "mw.Flag_type = 'W'",
        f"mw.Flagdel IN ({', '.join('?' * len(flags))})",
    ]
    params: list = [p['as_of'], *flags]

    if p['searchby'] == SEARCH_BY_CUSTOMER_NO:
        where.append("mw.APLESS = ?")
        params.append(p['searchbytext'])
    elif p['searchby'] == SEARCH_BY_CUSTOMER_NAME:
        where.append("mw.Name LIKE ?")
        params.append(_like_contains(p['searchbytext']))

    return " AND ".join(where), params

def _to_record(r: dict, no: int) -> dict:
    return {
        'no': no,
        'name': _dash(r.get('Name')),
        'customer_no': _dash(r.get('APLESS')),
        'address': _dash(r.get('Address')),
        'id_card': _dash(r.get('ID_Card')),
        'phone': _dash(r.get('Phone')),
        'reason': _dash(r.get('Reason')),
        'create_user': _dash(r.get('CreateUser')),
        'create_date': _dmy(r.get('CreateDate')),
        'status': r.get('Status') or 'Active',
        'delete_by': _dash(r.get('DeleteBy')),
    }

def _query_watchlist(p: dict, page: Optional[int] = None, page_size: Optional[int] = None):
    built = _build_where(p)
    if built is None:
        return 0, []
    where_sql, params = built

    total = _exec_scalar(f"SELECT COUNT(*) {_FROM_JOINS} WHERE {where_sql}", params) or 0

    data_sql = f"{_SELECT_COLS} {_FROM_JOINS} WHERE {where_sql}{_ORDER_BY}"
    data_params = list(params)
    offset = 0
    if page is not None and page_size is not None:
        offset = (page - 1) * page_size
        data_sql += " OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
        data_params += [offset, page_size]

    rows = _exec_rows(data_sql, data_params)
    return total, [_to_record(r, offset + i) for i, r in enumerate(rows, start=1)]

def _describe_search(p: dict) -> str:
    if p['searchby'] == SEARCH_BY_CUSTOMER_NO:
        return f"Customer No / {p['searchbytext']}"
    if p['searchby'] == SEARCH_BY_CUSTOMER_NAME:
        return f"Customer Name / {p['searchbytext']}"
    return ''

def _describe_view(p: dict) -> str:
    parts = []
    if p['existing']:
        parts.append('Existing in Watchlist Report')
    if p['deleted']:
        parts.append('Data Deleted from Watchlist Report')
    return ' / '.join(parts)

def _as_of_label(as_of: date) -> str:
    return as_of.strftime('%d %b %Y')

def _header_info(p: dict) -> dict:
    return {
        'search_desc': _describe_search(p),
        'view_desc': _describe_view(p),
        'as_of': p['as_of_raw'],
        'as_of_label': _as_of_label(p['as_of']),
    }

def _build_excel(records: list, p: dict) -> io.BytesIO:
    col_count = len(COLUMNS)
    last_col = get_column_letter(col_count)
    thin = Side(style='thin', color='000000')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    font = Font(name='Tahoma', size=9)
    bold = Font(name='Tahoma', size=9, bold=True)

    wb = Workbook()
    ws = wb.active
    ws.title = 'Watchlist'

    ws.merge_cells(f'A1:{last_col}1')
    ws['A1'] = 'WATCHLIST REPORT'
    ws['A1'].font = Font(name='Tahoma', size=15, bold=True)
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 24

    ws.merge_cells(f'A2:{last_col}2')
    ws['A2'] = f"As of {_as_of_label(p['as_of'])}"
    ws['A2'].font = Font(name='Tahoma', size=10, bold=True)
    ws['A2'].alignment = Alignment(horizontal='center')

    info_rows = (
        ('Branch', 'Consolidate'),
        ('Search by', _describe_search(p)),
        ('View', _describe_view(p)),
    )
    for offset, (label, value) in enumerate(info_rows):
        row = 4 + offset
        ws.merge_cells(f'A{row}:B{row}')
        ws.cell(row=row, column=1, value=label).font = bold
        ws.merge_cells(f'C{row}:{last_col}{row}')
        ws.cell(row=row, column=3, value=f': {value}').font = font

    header_row = 8
    for idx, (label, _, width) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=header_row, column=idx, value=label)
        cell.font = bold
        cell.fill = PatternFill('solid', fgColor='F0F0F0')
        cell.border = border
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        ws.column_dimensions[get_column_letter(idx)].width = width

    if records:
        for r_idx, record in enumerate(records, start=header_row + 1):
            for c_idx, (_, key, _) in enumerate(COLUMNS, start=1):
                cell = ws.cell(row=r_idx, column=c_idx, value=record[key])
                cell.font = font
                cell.border = border
                cell.alignment = (
                    Alignment(horizontal='center', vertical='top')
                    if key in _CENTER_KEYS else Alignment(vertical='top', wrap_text=True)
                )
    else:
        row = header_row + 1
        ws.merge_cells(f'A{row}:{last_col}{row}')
        cell = ws.cell(row=row, column=1, value='Data Not Found')
        cell.font = Font(name='Tahoma', size=12, bold=True, color='EE0000')
        cell.alignment = Alignment(horizontal='center')
        for c_idx in range(1, col_count + 1):
            ws.cell(row=row, column=c_idx).border = border

    ws.freeze_panes = f'A{header_row + 1}'
    ws.print_title_rows = f'{header_row}:{header_row}'
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output

@watchlist_report_bp.route('/watchlist-report/list')
@login_required
def list_watchlist():
    try:
        p = _parse_args(request.args)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    try:
        page = max(int(request.args.get('page', 1)), 1)
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = min(max(int(request.args.get('page_size', 20)), 1), 200)
    except (TypeError, ValueError):
        page_size = 20

    try:
        total, data = _query_watchlist(p, page=page, page_size=page_size)
        return jsonify({
            'data': data,
            'page': page,
            'page_size': page_size,
            'total': total,
            'total_pages': max((total + page_size - 1) // page_size, 1),
            **_header_info(p),
        })
    except Exception as e:
        current_app.logger.exception("Watchlist list error")
        return jsonify({'error': str(e)}), 500

@watchlist_report_bp.route('/watchlist-report/print')
@login_required
def print_watchlist():
    try:
        p = _parse_args(request.args)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    try:
        total, data = _query_watchlist(p)
        return jsonify({'data': data, 'total': total, **_header_info(p)})
    except Exception as e:
        current_app.logger.exception("Watchlist print error")
        return jsonify({'data': [], 'error': str(e)}), 500

@watchlist_report_bp.route('/watchlist-report/excel')
@login_required
def export_excel():
    try:
        p = _parse_args(request.args)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    try:
        _, data = _query_watchlist(p)
        return send_file(
            _build_excel(data, p),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='Watchlist.xlsx',
        )
    except Exception as e:
        current_app.logger.exception("Watchlist Excel export error")
        return jsonify({'error': str(e)}), 500