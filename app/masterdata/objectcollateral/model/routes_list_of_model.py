import io
from datetime import datetime

from flask import Blueprint, jsonify, current_app, session, send_file
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import text

from app import db
from app.auth.decorators import login_required

list_model_bp = Blueprint('list_model', __name__, url_prefix='/MasterData')

EXCEL_COLUMNS = (
    ("No.", "no", 8),
    ("Model", "MODEL_NM", 60),
)

def _dash(value) -> str:
    v = "" if value is None else str(value).strip()
    return v if v else "-"

def _fetch_models() -> list:
    rows = db.session.execute(
        text("SELECT MODEL_NM FROM UMFMODEL WITH(NOLOCK) ORDER BY MODEL_NM")
    ).fetchall()
    return [{"no": i, "MODEL_NM": _dash(r.MODEL_NM)} for i, r in enumerate(rows, 1)]

def _print_by_line() -> str:
    return f"Print By - Date : {session.get('username', '')} - {datetime.now().strftime('%d/%m/%Y')}"

@list_model_bp.route('/list-model')
@login_required
def get_list_model():
    try:
        data = _fetch_models()
        return jsonify({"data": data, "total": len(data)})
    except Exception as e:
        current_app.logger.exception("List model error")
        return jsonify({"data": [], "total": 0, "error": str(e)}), 500

@list_model_bp.route('/list-model/print')
@login_required
def print_list_model():
    try:
        data = _fetch_models()
        return jsonify({
            "data": data,
            "total": len(data),
            "print_by": session.get("username", ""),
            "print_date": datetime.now().strftime('%d/%m/%Y'),
        })
    except Exception as e:
        current_app.logger.exception("List model print error")
        return jsonify({"data": [], "error": str(e)}), 500

@list_model_bp.route('/list-model/excel')
@login_required
def export_list_model_excel():
    try:
        records = _fetch_models()
        col_count = len(EXCEL_COLUMNS)
        last_col = get_column_letter(col_count)
        thin = Side(style='thin', color='000000')
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        font = Font(name='Tahoma', size=9)

        wb = Workbook()
        ws = wb.active
        ws.title = 'ListofModel'

        ws.merge_cells(f'A1:{last_col}1')
        ws['A1'] = 'List of Model'
        ws['A1'].font = Font(name='Tahoma', size=15, bold=True)
        ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[1].height = 24

        ws.merge_cells(f'A2:{last_col}2')
        ws['A2'] = _print_by_line()
        ws['A2'].font = font
        ws['A2'].alignment = Alignment(horizontal='center')

        header_row = 4
        for idx, (label, _, width) in enumerate(EXCEL_COLUMNS, start=1):
            cell = ws.cell(row=header_row, column=idx, value=label)
            cell.font = Font(name='Tahoma', size=9, bold=True)
            cell.fill = PatternFill('solid', fgColor='F0F0F0')
            cell.border = border
            cell.alignment = Alignment(horizontal='center', vertical='center')
            ws.column_dimensions[get_column_letter(idx)].width = width

        if records:
            for r_idx, record in enumerate(records, start=header_row + 1):
                for c_idx, (_, key, _) in enumerate(EXCEL_COLUMNS, start=1):
                    cell = ws.cell(row=r_idx, column=c_idx, value=record[key])
                    cell.font = font
                    cell.border = border
                    cell.alignment = (
                        Alignment(horizontal='center', vertical='top')
                        if key == 'no' else Alignment(vertical='top', wrap_text=True)
                    )
        else:
            row = header_row + 1
            ws.merge_cells(f'A{row}:{last_col}{row}')
            cell = ws.cell(row=row, column=1, value='Data Not Found..')
            cell.font = Font(name='Tahoma', size=12, color='EE0000')
            cell.alignment = Alignment(horizontal='center')
            for c_idx in range(1, col_count + 1):
                ws.cell(row=row, column=c_idx).border = border

        ws.freeze_panes = f'A{header_row + 1}'
        ws.print_title_rows = f'{header_row}:{header_row}'
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='ListofModel.xlsx',
        )

    except Exception as e:
        current_app.logger.exception("List model excel error")
        return jsonify({"error": str(e)}), 500