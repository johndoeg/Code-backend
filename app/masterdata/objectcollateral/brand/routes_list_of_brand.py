import io
from datetime import datetime

from flask import Blueprint, jsonify, request, current_app, session, send_file
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import text

from app import db
from app.auth.decorators import login_required

list_brand_bp = Blueprint('list_brand', __name__, url_prefix='/MasterData')

MAX_PAGE_LIMIT = 200
FILL_FIELD_MESSAGE = "Please Fill The Field"

BRAND_FROM = """
    FROM UMFTYPE a WITH(NOLOCK)
        LEFT JOIN UMFBRAND b WITH(NOLOCK) ON a.BRAND = b.BRAND
        LEFT JOIN UMFMODEL c WITH(NOLOCK) ON SUBSTRING(a.TYPE, 1, 2) = c.MODEL
"""
BRAND_COLUMNS = "a.TYPE, a.TYPE_NM, b.BRAND_NM, c.MODEL_NM"

EXCEL_COLUMNS = (
    ("No.", "no", 7),
    ("Brand", "BRAND_NM", 24),
    ("Model", "MODEL_NM", 24),
    ("Type", "TYPE", 16),
    ("Type Name", "TYPE_NM", 45),
)

def _dash(value) -> str:
    v = "" if value is None else str(value).strip()
    return v if v else "-"

def _read_filters(args) -> dict:
    return {
        "brand": args.get('brand', '').strip(),
        "model": args.get('model', '').strip(),
    }

def _where(filters: dict) -> tuple:
    conditions, params = [], {}
    if filters["brand"]:
        conditions.append("a.BRAND = :brand")
        params["brand"] = filters["brand"]
    if filters["model"]:
        conditions.append("SUBSTRING(a.TYPE, 1, 2) = :model")
        params["model"] = filters["model"]
    return ("WHERE " + " AND ".join(conditions)) if conditions else "", params

def _to_record(no: int, row) -> dict:
    return {
        "no": no,
        "TYPE": _dash(row.TYPE),
        "TYPE_NM": _dash(row.TYPE_NM),
        "BRAND_NM": _dash(row.BRAND_NM),
        "MODEL_NM": _dash(row.MODEL_NM),
    }

def _fetch_all(filters: dict) -> list:
    where_clause, params = _where(filters)
    rows = db.session.execute(
        text(f"SELECT {BRAND_COLUMNS} {BRAND_FROM} {where_clause} ORDER BY a.TYPE"),
        params,
    ).fetchall()
    return [_to_record(i, r) for i, r in enumerate(rows, 1)]

def _print_by_line() -> str:
    return f"Print By - Date : {session.get('username', '')} - {datetime.now().strftime('%d/%m/%Y')}"

@list_brand_bp.route('/list-brand')
@login_required
def get_list_brand():
    page = max(request.args.get('page', 1, type=int), 1)
    limit = min(max(request.args.get('limit', 25, type=int), 1), MAX_PAGE_LIMIT)
    filters = _read_filters(request.args)

    if not filters["brand"] and not filters["model"]:
        return jsonify({"data": [], "total": 0, "page": page, "limit": limit})

    try:
        where_clause, params = _where(filters)

        total = db.session.execute(
            text(f"SELECT COUNT(*) AS total {BRAND_FROM} {where_clause}"),
            params,
        ).fetchone().total

        offset = (page - 1) * limit
        rows = db.session.execute(
            text(f"""
                SELECT {BRAND_COLUMNS} {BRAND_FROM}
                {where_clause}
                ORDER BY a.TYPE
                OFFSET :offset ROWS
                FETCH NEXT :limit ROWS ONLY
            """),
            {**params, "offset": offset, "limit": limit},
        ).fetchall()

        return jsonify({
            "data": [_to_record(offset + i, r) for i, r in enumerate(rows, 1)],
            "total": total,
            "page": page,
            "limit": limit,
        })

    except Exception as e:
        current_app.logger.exception("List brand error")
        return jsonify({"data": [], "total": 0, "error": str(e)}), 500

@list_brand_bp.route('/list-brand/brand-options')
@login_required
def get_brand_options():
    try:
        result = db.session.execute(text("""
            SELECT BRAND, BRAND_NM
            FROM UMFBRAND WITH(NOLOCK)
            WHERE BRAND_NM NOT IN ('CBU', 'All Brand', 'Used Cars', 'Used Trucks')
            ORDER BY BRAND_NM
        """))
        return jsonify({"data": [{"BRAND": r.BRAND, "BRAND_NM": r.BRAND_NM} for r in result]})
    except Exception as e:
        current_app.logger.exception("Brand options error")
        return jsonify({"data": [], "error": str(e)}), 500

@list_brand_bp.route('/list-brand/model-options')
@login_required
def get_model_options():
    try:
        result = db.session.execute(text("""
            SELECT MODEL, MODEL_NM FROM UMFMODEL WITH(NOLOCK) ORDER BY MODEL
        """))
        return jsonify({"data": [{"MODEL": r.MODEL, "MODEL_NM": r.MODEL_NM} for r in result]})
    except Exception as e:
        current_app.logger.exception("Model options error")
        return jsonify({"data": [], "error": str(e)}), 500

@list_brand_bp.route('/list-brand/print')
@login_required
def print_list_brand():
    filters = _read_filters(request.args)
    if not filters["brand"] and not filters["model"]:
        return jsonify({"error": FILL_FIELD_MESSAGE}), 400

    try:
        records = _fetch_all(filters)
        return jsonify({
            "data": records,
            "total": len(records),
            "print_by": session.get("username", ""),
            "print_date": datetime.now().strftime('%d/%m/%Y'),
        })
    except Exception as e:
        current_app.logger.exception("List brand print error")
        return jsonify({"data": [], "error": str(e)}), 500

@list_brand_bp.route('/list-brand/excel')
@login_required
def export_list_brand_excel():
    filters = _read_filters(request.args)
    if not filters["brand"] and not filters["model"]:
        return jsonify({"error": FILL_FIELD_MESSAGE}), 400

    try:
        records = _fetch_all(filters)
        col_count = len(EXCEL_COLUMNS)
        last_col = get_column_letter(col_count)
        thin = Side(style='thin', color='000000')
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        font = Font(name='Tahoma', size=9)

        wb = Workbook()
        ws = wb.active
        ws.title = 'ListofBrand'

        ws.merge_cells(f'A1:{last_col}1')
        ws['A1'] = 'List of Brand'
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
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
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
            download_name='ListofBrand.xlsx',
        )

    except Exception as e:
        current_app.logger.exception("List brand excel error")
        return jsonify({"error": str(e)}), 500