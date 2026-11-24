import io
from datetime import date, datetime

import xlsxwriter
from dateutil.relativedelta import relativedelta
from flask import Blueprint, current_app, jsonify, request, send_file
from sqlalchemy import text

from app import db
from app.auth.decorators import login_required

sipesat_bp = Blueprint('sipesat', __name__, url_prefix='/SIPESAT')

_PERIOD_FORMATS = ('%m-%Y', '%b-%Y', '%B-%Y')

_COLUMNS = [
    (' IDPJK ', 'idpjk', 5, 'center', False),
    (' Kode Nasabah ', 'KodeNasabah', 14, 'center', False),
    (' Nama Nasabah ', 'LESSEE_NM', 14, 'center', False),
    (' Tempat Lahir ', 'tmptLahir', 14, 'center', False),
    (' Tanggal Lahir ', 'tglLahir', 15, 'center', False),
    (' Alamat ', 'alamat', 100, 'wrap', False),
    (' KTP ', 'KTP', 5, 'left', True),
    (' Identitas Lain ', 'identitaslain', 16, 'left', False),
    (' CIF/Kepersertaan ', 'NoCIFDebitur', 18, 'left', True),
    (' NPWP ', 'NPWP', 6, 'left', True),
]

_BASE_FONT = {'font_name': 'Tahoma', 'font_size': 10}
_BASE_BORDER = {'border': 1, 'border_color': '#000000'}

def _parse_period(period_str):
    period_str = (period_str or '').strip()
    if not period_str:
        return None
    for fmt in _PERIOD_FORMATS:
        try:
            parsed = datetime.strptime(period_str, fmt)
        except ValueError:
            continue
        return (parsed + relativedelta(months=1, day=1, days=-1)).date()
    return None

def _cell_value(value):
    if value is None:
        return ''
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d')
    if isinstance(value, date):
        return value.strftime('%Y-%m-%d')
    return value

def _build_excel(data_rows):
    output = io.BytesIO()

    with xlsxwriter.Workbook(output, {'in_memory': True}) as workbook:
        worksheet = workbook.add_worksheet('SIPESAT')

        header_fmt = workbook.add_format({
            **_BASE_FONT,
            **_BASE_BORDER,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#FFFF00',
        })
        center_fmt = workbook.add_format({**_BASE_FONT, **_BASE_BORDER, 'align': 'center'})
        left_fmt = workbook.add_format({**_BASE_FONT, **_BASE_BORDER, 'align': 'left'})
        wrap_fmt = workbook.add_format({**_BASE_FONT, **_BASE_BORDER, 'text_wrap': True})
        body_fmt = {'center': center_fmt, 'left': left_fmt, 'wrap': wrap_fmt}

        for col_idx, (header, _field, width, _align, _as_string) in enumerate(_COLUMNS):
            worksheet.write_string(0, col_idx, header, header_fmt)
            worksheet.set_column(col_idx, col_idx, width)

        for row_idx, row in enumerate(data_rows, start=1):
            for col_idx, (_header, field, _width, align, as_string) in enumerate(_COLUMNS):
                value = _cell_value(row.get(field))
                cell_fmt = body_fmt[align]
                if as_string:
                    worksheet.write_string(row_idx, col_idx, str(value), cell_fmt)
                else:
                    worksheet.write(row_idx, col_idx, value, cell_fmt)

    output.seek(0)
    return output

@sipesat_bp.route('/export/excel')
@login_required
def export_sipesat_excel():
    period = request.args.get('period')
    selected_date = _parse_period(period)
    if not selected_date:
        return jsonify({'error': 'Invalid period. Use MM-YYYY (e.g. 11-2025).'}), 400

    try:
        result = db.session.execute(
            text("EXEC USP_OJK_SIPESAT :selected_date"),
            {"selected_date": selected_date.strftime('%Y-%m-%d')},
        )
        rows = result.mappings().all()

        excel_file = _build_excel(rows)
        filename = f"PELAPORAN SIPESAT {selected_date.strftime('%B %Y').upper()}.xlsx"

        return send_file(
            excel_file,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename,
            max_age=0,
        )
    except Exception:
        current_app.logger.exception("SIPESAT export error")
        return jsonify({'error': 'Failed to generate report'}), 500