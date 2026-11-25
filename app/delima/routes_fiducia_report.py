from flask import Blueprint, jsonify, request, current_app, session, make_response
from app import db
from app.auth.decorators import login_required
from app.utils.helpers.settings_helpers import company_name as get_company_name
from sqlalchemy import text

import base64
import zipfile
import io
from datetime import date, datetime

from reportlab.lib           import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles    import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units     import mm
from reportlab.platypus      import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums     import TA_CENTER, TA_LEFT

fiducia_bp = Blueprint('fiducia', __name__, url_prefix='/FiduciaReport')

def _exec_sp(sp_name: str, params: list) -> list[dict]:
  
    placeholders = ', '.join(['?'] * len(params))
    sql = f"EXEC {sp_name} {placeholders}"

    raw_conn = db.session.connection().connection
    cursor   = raw_conn.cursor()

    try:
        cursor.execute(sql, params)
        while cursor.description is None:
            if not cursor.nextset():
                return []

        columns = [col[0] for col in cursor.description]
        rows    = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return rows

    finally:
        cursor.close()

_CERT_LABELS = {
    'fiducia_not_accepted':      'Fidusia Belum Diterima',
    'roya_fiducia_not_accepted': 'Roya Fidusia Belum Diterima',
    'fiducia_not_scan':          'List Fidusia Belum Di Scan',
}

_MONTHS_ID = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
              'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']

_DATE_FMT      = '%d-%m-%Y'
_DATE_PATTERNS = ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S',
                  '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%d-%b-%Y', '%d-%B-%Y')

_PRINT_REPORTS = {
    'fiducia_not_accepted': {
        'title': 'Laporan Sertifikat Fidusia Yang Belum Diterima',
        'columns': [
            ('No.',               None,           5),
            ('Contract No.',      'LeaseNo',      10),
            ('Customer Name',     'CustomerName', 25),
            ('Disbursement Date', 'DisbDate',     10),
            ('Cover Date',        'CoverDate',    10),
            ('Overdue Days *',    'od',           10),
            ('Remarks',           'Remark',       30),
        ],
        'notes': [
            '* Overdue Days:',
            'Perhitungan \u201cOverdue Days\u201d adalah sebagai berikut :',
            '-   Kondisi \u201cDisbursement Date\u201d dan "Cover Date" terisi = Tanggal Login \u2013 Cover Date',
            '-   Kondisi \u201cCover Date\u201d kosong = Tanggal Login \u2013 Disbursement Date',
        ],
    },
    'roya_fiducia_not_accepted': {
        'title': 'Laporan Sertifikat Roya Fidusia Yang Belum Diterima',
        'columns': [
            ('No.',            None,           5),
            ('Contract No.',   'LeaseNo',      10),
            ('Customer Name',  'CustomerName', 25),
            ('Release Date',   'ReleaseDate',  10),
            ('Roya Date',      'RoyaDate',     10),
            ('Overdue Days *', 'od',           10),
            ('Remarks',        'Remark',       30),
        ],
        'notes': [
            '* Overdue Days:',
            'Perhitungan \u201cOverdue Days\u201d adalah sebagai berikut :',
            '-   Kondisi \u201cRelease Date\u201d dan "Roya Date" terisi = Tanggal Login \u2013 Roya Date',
            '-   Kondisi \u201cRoya Date\u201d kosong = Tanggal Login \u2013 Release Date',
        ],
    },
    'fiducia_not_scan': {
        'title': 'List fidusia yang belum di scan',
        'columns': [
            ('No.',                         None,           5),
            ('Contract No.',                'LeaseNo',      15),
            ('Customer Name',               'CustomerName', 25),
            ('Disbursement Date',           'DisbDate',     10),
            ('Cover Date',                  'CoverDate',    10),
            ('Fiducia Receive From Vendor', 'ReceiveDate',  25),
            ('Overdue Days *',              'od',           10),
        ],
        'notes': [
            '* Rumus = Tanggal Login - Fiducia Receive From Vendor',
        ],
    },
}

def _fmt_date(value) -> str:
    if value in (None, ''):
        return ''
    if isinstance(value, datetime):
        return value.strftime(_DATE_FMT)
    if isinstance(value, date):
        return value.strftime(_DATE_FMT)
    raw = str(value).strip()
    if not raw:
        return ''
    for fmt in _DATE_PATTERNS:
        try:
            return datetime.strptime(raw, fmt).strftime(_DATE_FMT)
        except ValueError:
            continue
    return raw

def _asof_label(asof: str) -> str:
    for fmt in _DATE_PATTERNS:
        try:
            parsed = datetime.strptime(asof.strip(), fmt)
        except ValueError:
            continue
        return f"{parsed.day:02d} {_MONTHS_ID[parsed.month - 1]} {parsed.year}"
    return asof

def _asof_sql(asof: str) -> str:
    for fmt in _DATE_PATTERNS:
        try:
            return datetime.strptime(asof.strip(), fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return asof

def _branch_label(branch_cd: str) -> str:
    if branch_cd == '100':
        return 'Consolidate'
    try:
        row = db.session.execute(
            text("""
                SELECT a.BRANCH_NAME
                FROM UMFBRANCH a WITH (NOLOCK)
                INNER JOIN APP_USRMST b WITH (NOLOCK) ON a.BRANCH_CD = b.BRANCHCODE
                WHERE a.BRANCH_CD = :branch_cd AND b.EMPLOYEE_ID = :employee
            """),
            {"branch_cd": branch_cd, "employee": session.get('emp_id', '')},
        ).first()
    except Exception:
        current_app.logger.exception("Fiducia branch lookup error")
        return ''
    if not row or not row[0]:
        return ''
    return f"{str(row[0]).strip()} Branch"

def _build_print_pdf(cert_type: str, asof: str, rows: list[dict], branch_label: str) -> bytes:
    report = _PRINT_REPORTS[cert_type]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=12 * mm,  bottomMargin=12 * mm,
    )

    styles   = getSampleStyleSheet()
    head_st  = ParagraphStyle('head', parent=styles['Normal'],
                              fontSize=11, fontName='Helvetica',
                              alignment=TA_LEFT, leading=14)
    title_st = ParagraphStyle('title', parent=styles['Normal'],
                              fontSize=16, fontName='Helvetica-Bold',
                              alignment=TA_CENTER, leading=20)
    cell_st  = ParagraphStyle('cell', parent=styles['Normal'],
                              fontSize=8, fontName='Helvetica',
                              alignment=TA_CENTER, leading=10)
    head_cell_st = ParagraphStyle('headcell', parent=cell_st, fontName='Helvetica-Bold')
    note_st  = ParagraphStyle('note', parent=styles['Normal'],
                              fontSize=8, fontName='Helvetica',
                              alignment=TA_LEFT, leading=11)

    story = [
        Paragraph(get_company_name(), head_st),
        Paragraph(branch_label, head_st),
        Spacer(1, 6 * mm),
        Paragraph(report['title'], title_st),
        Paragraph(f"As Of {_asof_label(asof)}", title_st),
        Spacer(1, 8 * mm),
    ]

    usable    = doc.width
    col_widths = [usable * pct / 100.0 for _, _, pct in report['columns']]

    table_data = [[Paragraph(label, head_cell_st) for label, _, _ in report['columns']]]
    for i, r in enumerate(rows, start=1):
        line = []
        for _, field, _ in report['columns']:
            value = f"{i}." if field is None else r.get(field, '')
            line.append(Paragraph(str(value or ''), cell_st))
        table_data.append(line)

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0),  colors.HexColor('#60caf2')),
        ('TEXTCOLOR',     (0, 0), (-1, 0),  colors.black),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID',          (0, 0), (-1, -1), 0.75, colors.black),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING',   (0, 0), (-1, -1), 3),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 3),
    ]))

    story.append(tbl)
    story.append(Spacer(1, 6 * mm))
    for note in report['notes']:
        story.append(Paragraph(note, note_st))

    doc.build(story)
    buffer.seek(0)

    return buffer.read()

@fiducia_bp.route('/fiducia-data', methods=['POST'])
@login_required
def get_fiducia_data():
   
    body        = request.get_json(silent=True) or {}
    cert_type   = body.get('cert_type',   '').strip()
    search_by   = body.get('search_by',   '').strip()
    lease_no    = body.get('lease_no',    '').strip()
    lessee_nm   = body.get('lessee_nm',   '').strip()
    date_before = body.get('date_before', '').strip()
    date_after  = body.get('date_after',  '').strip()
    branch_cd   = session.get('branchcode', '')

    if not cert_type:
        return jsonify({'data': [], 'error': 'cert_type is required'}), 400

    try:
        raw_rows = _exec_sp(
            'USP_CA_GetDataFiducia',
            [cert_type, search_by, lease_no, lessee_nm, date_before, date_after, branch_cd],
        )

        rows = []
        for r in raw_rows:
            if cert_type == 'fidusia':
                disb = r.get('DisbDate')
                rows.append({
                    'lease_no':        r.get('LEASE_NO',        ''),
                    'lessee_nm':       r.get('LESSEE_NM',       ''),
                    'DisbDate':        _fmt_date(disb),
                    'has_certificate': bool(r.get('CertificateFile')),
                })
            elif cert_type == 'roya_fidusia':
                rel = r.get('ReleaseDate')
                rows.append({
                    'lease_no':    r.get('LEASE_NO',   ''),
                    'lessee_nm':   r.get('LESSEE_NM',  ''),
                    'ReleaseDate': _fmt_date(rel),
                    'has_file':    bool(r.get('RoyaFile')),
                })

        return jsonify({'data': rows})

    except Exception as e:
        current_app.logger.exception("Fiducia data fetch error")
        return jsonify({'data': [], 'error': str(e)}), 500

@fiducia_bp.route('/fiducia-file')
@login_required
def get_fiducia_file():
   
    lease_no_raw = request.args.get('lease_no',   '').strip()
    trans_type   = request.args.get('trans_type', '').strip()

    if not lease_no_raw or not trans_type:
        return jsonify({'error': 'lease_no and trans_type are required'}), 400

    lease_nos = [ln.strip() for ln in lease_no_raw.split(',') if ln.strip()]

    if trans_type == 'roya_fidusia':
        file_col    = 'RoyaFile'
        table       = 'API_DELIMA.dbo.Roya_Fiducia'
        file_prefix = 'SERTIFIKAT_ROYA_FIDUSIA'
        zip_name    = 'download_roya_fiducia_pdf.zip'
    else:
        file_col    = 'CertificateFile'
        table       = 'API_DELIMA.dbo.Sertifikat_Fiducia'
        file_prefix = 'SERTIFIKAT_JAMINAN_FIDUSIA'
        zip_name    = 'download_fiducia_pdf.zip'

    try:
        def _fetch_pdf(ln: str) -> bytes | None:
            result = db.session.execute(
                text(f"SELECT {file_col} FROM {table} WHERE AgreementNo = :ln"),
                {'ln': ln},
            ).fetchone()
            if result and result[0]:
                return base64.b64decode(result[0])
            return None

        if len(lease_nos) == 1:
            pdf_bytes = _fetch_pdf(lease_nos[0])
            if not pdf_bytes:
                return jsonify({'error': 'File not found'}), 404

            response = make_response(pdf_bytes)
            response.headers['Content-Type']        = 'application/pdf'
            response.headers['Content-Disposition'] = 'inline'
            return response

        else:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for ln in lease_nos:
                    pdf_bytes = _fetch_pdf(ln)
                    if pdf_bytes:
                        zf.writestr(f"{file_prefix}_{ln}.pdf", pdf_bytes)

            zip_buffer.seek(0)
            response = make_response(zip_buffer.read())
            response.headers['Content-Type']        = 'application/zip'
            response.headers['Content-Disposition'] = f'attachment; filename="{zip_name}"'
            return response

    except Exception as e:
        current_app.logger.exception("Fiducia file fetch error")
        return jsonify({'error': str(e)}), 500

@fiducia_bp.route('/context')
@login_required
def get_context():
    try:
        row = db.session.execute(
            text("""
                SELECT a.BRANCH_CD, a.BRANCH_NAME, b.FULLNAME, b.ACCESSCAM
                FROM UMFBRANCH a WITH (NOLOCK)
                INNER JOIN APP_USRMST b WITH (NOLOCK) ON a.BRANCH_CD = b.BRANCHCODE
                WHERE b.EMPLOYEE_ID = :employee
            """),
            {"employee": session.get('emp_id', '')},
        ).mappings().first()

        if not row:
            return jsonify({'access': '', 'branch_cd': '', 'branch_name': '', 'full_name': ''})

        return jsonify({
            'access':      (row['ACCESSCAM'] or '').strip().upper(),
            'branch_cd':   (row['BRANCH_CD'] or '').strip(),
            'branch_name': (row['BRANCH_NAME'] or '').strip(),
            'full_name':   (row['FULLNAME'] or '').strip(),
        })
    except Exception:
        current_app.logger.exception("Fiducia context error")
        return jsonify({'access': '', 'branch_cd': '', 'branch_name': '', 'full_name': ''})

@fiducia_bp.route('/fiducia-print')
@login_required
def fiducia_print():

    cert_type = request.args.get('cert_type', '').strip()
    asof      = request.args.get('asof',      '').strip()

    if cert_type not in _PRINT_REPORTS:
        return jsonify({'error': 'Invalid cert_type for print'}), 400
    if not asof:
        return jsonify({'error': 'asof is required'}), 400

    branch_cd = session.get('branchcode', '')

    try:
        raw_rows = _exec_sp(
            'USP_CA_ReportFiducia',
            [cert_type, _asof_sql(asof), branch_cd],
        )

        date_fields = {'DisbDate', 'CoverDate', 'ReceiveDate', 'ReleaseDate', 'RoyaDate'}
        rows = []
        for r in raw_rows:
            row = {}
            for _, field, _w in _PRINT_REPORTS[cert_type]['columns']:
                if field is None:
                    continue
                value = r.get(field)
                row[field] = _fmt_date(value) if field in date_fields else (value if value is not None else '')
            rows.append(row)

        pdf_bytes = _build_print_pdf(cert_type, asof, rows, _branch_label(branch_cd))

        label    = _CERT_LABELS.get(cert_type, cert_type).replace(' ', '_')
        filename = f"Report_{label}_{_fmt_date(asof)}.pdf"

        response = make_response(pdf_bytes)
        response.headers['Content-Type']        = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename="{filename}"'
        return response

    except Exception as e:
        current_app.logger.exception("Fiducia print error")
        return jsonify({'error': str(e)}), 500