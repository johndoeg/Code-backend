from flask import Blueprint, request, send_file, jsonify, current_app
from app import db
from sqlalchemy import text
from datetime import datetime
from dateutil.relativedelta import relativedelta
import xlsxwriter
import io

sipesat_bp = Blueprint('sipesat', __name__, url_prefix='/SIPESAT')

def _parse_period(period_str: str) -> datetime | None:
    try:
        dt = datetime.strptime(period_str, '%m-%Y')
        return dt + relativedelta(months=1, day=1, days=-1)
    except (ValueError, TypeError):
        return None

def _build_excel(data_rows: list[dict]) -> io.BytesIO:
    output = io.BytesIO()
    
    with xlsxwriter.Workbook(output, {'in_memory': True}) as workbook:
        worksheet = workbook.add_worksheet('SIPESAT')
        
        columns = [
            (' IDPJK ', 'idpjk', 5, False),
            (' Kode Nasabah ', 'KodeNasabah', None, False),
            (' Nama Nasabah ', 'LESSEE_NM', None, False),
            (' Tempat Lahir ', 'tmptLahir', None, False),
            (' Tanggal Lahir ', 'tglLahir', None, False),
            (' Alamat ', 'alamat', 100, False),
            (' KTP ', 'KTP', None, True),
            (' Identitas Lain ', 'identitaslain', None, False),
            (' CIF/Kepersertaan ', 'NoCIFDebitur', None, True),
            (' NPWP ', 'NPWP', None, True),
        ]
        
        header_fmt = workbook.add_format({
            'align': 'center', 'valign': 'vcenter',
            'font_name': 'Tahoma', 'font_size': 10,
            'bg_color': '#FFFF00', 'border': 1, 'border_color': 'black',
        })
        
        data_fmt = workbook.add_format({
            'font_name': 'Tahoma', 'font_size': 10,
            'border': 1, 'border_color': 'black',
        })
        center_fmt = workbook.add_format({**data_fmt.__dict__, 'align': 'center', 'valign': 'vcenter'})
        left_fmt = workbook.add_format({**data_fmt.__dict__, 'align': 'left', 'valign': 'vcenter'})
        wrap_fmt = workbook.add_format({**data_fmt.__dict__, 'text_wrap': True})
        center_wrap_fmt = workbook.add_format({**data_fmt.__dict__, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
        
        for col_idx, (header, _, width, _) in enumerate(columns):
            worksheet.write(0, col_idx, header, header_fmt)
            if width:
                worksheet.set_column(col_idx, col_idx, width)
            else:
                worksheet.set_column(col_idx, col_idx, max(len(header.strip()) + 2, 10))
        
        for row_idx, row in enumerate(data_rows, start=1):
            for col_idx, (_, field, _, is_string) in enumerate(columns):
                value = row.get(field, '')
                if value is None:
                    value = ''
                if isinstance(value, datetime):
                    value = value.strftime('%Y-%m-%d')
                
                if col_idx == 5:
                    fmt = center_wrap_fmt if col_idx <= 4 else wrap_fmt
                elif col_idx <= 4:
                    fmt = center_fmt
                elif col_idx >= 6:
                    fmt = left_fmt
                else:
                    fmt = data_fmt
                
                if is_string and str(value).strip():
                    worksheet.write_string(row_idx, col_idx, str(value), fmt)
                else:
                    worksheet.write(row_idx, col_idx, str(value), fmt)
    
    output.seek(0)
    return output

@sipesat_bp.route('/api/export/excel')
def export_sipesat_excel():
    period = request.args.get('period')
    
    if not period:
        return jsonify({'error': 'period parameter required (format: MM-YYYY)'}), 400
    
    selected_date = _parse_period(period)
    if not selected_date:
        return jsonify({'error': 'Invalid period format. Use MM-YYYY (e.g., 11-2025)'}), 400
    
    sql_date = selected_date.strftime('%Y-%m-%d')
    
    try:
        result = db.session.execute(
            text("EXEC USP_OJK_SIPESAT :selected_date"),
            {"selected_date": sql_date}
        )
        
        columns = result.keys()
        rows = [dict(zip(columns, row)) for row in result]
        
        excel_file = _build_excel(rows)
        
        filename = f"PELAPORAN SIPESAT {selected_date.strftime('%B %Y').upper()}.xlsx"
        
        current_app.logger.info(f"Generated SIPESAT export: {filename} for period {period}")
        
        return send_file(
            excel_file,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename,
            max_age=0
        )
        
    except Exception as e:
        current_app.logger.exception("SIPESAT export error")
        return jsonify({'error': 'Failed to generate report'}), 500

@sipesat_bp.route('/api/check-data')
def check_sipesat_data():
    period = request.args.get('period')
    
    if not period:
        return jsonify({'error': 'period required'}), 400
    
    selected_date = _parse_period(period)
    if not selected_date:
        return jsonify({'error': 'Invalid period format'}), 400
    
    sql_date = selected_date.strftime('%Y-%m-%d')
    
    try:
        result = db.session.execute(
            text("EXEC USP_OJK_SIPESAT :selected_date"),
            {"selected_date": sql_date}
        )
        has_data = result.first() is not None
        
        return jsonify({'data': has_data, 'period': period})
        
    except Exception as e:
        current_app.logger.exception("SIPESAT check-data error")
        return jsonify({'error': 'Failed to check data'}), 500

@sipesat_bp.route('/api/reprocess')
def reprocess_sipesat():
    period = request.args.get('period')
    
    if not period:
        return jsonify({'error': 'period required'}), 400
    
    selected_date = _parse_period(period)
    if not selected_date:
        return jsonify({'error': 'Invalid period format'}), 400
    
    sql_date = selected_date.strftime('%Y-%m-%d')
    
    try:
        db.session.execute(
            text("EXEC USP_OJK_SIPESAT :selected_date"),
            {"selected_date": sql_date}
        )
        db.session.commit()
        
        current_app.logger.info(f"Reprocessed SIPESAT data for period {period}")
        return jsonify({'success': True, 'period': period})
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("SIPESAT reprocess error")
        return jsonify({'error': 'Reprocess failed'}), 500