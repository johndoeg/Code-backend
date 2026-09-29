from flask import Blueprint, jsonify, request, current_app, session, make_response
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text

import base64
import zipfile
import io
from datetime import datetime

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

def _build_print_pdf(cert_type: str, asof: str, rows: list[dict]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm,  bottomMargin=15 * mm,
    )

    styles   = getSampleStyleSheet()
    title_st = ParagraphStyle('title', parent=styles['Normal'],
                              fontSize=13, fontName='Helvetica-Bold',
                              alignment=TA_CENTER, spaceAfter=4)
    sub_st   = ParagraphStyle('sub', parent=styles['Normal'],
                              fontSize=9, alignment=TA_CENTER, spaceAfter=8)
    cell_st  = ParagraphStyle('cell', parent=styles['Normal'],
                              fontSize=8, fontName='Helvetica', leading=10)

    story = [
        Paragraph(f"Report {_CERT_LABELS.get(cert_type, cert_type)}", title_st),
        Paragraph(f"As Of : {asof}", sub_st),
        Spacer(1, 4 * mm),
    ]

    header     = ['No.', 'Contract No.', 'Customer Name', 'Address', 'City', 'Phone', 'As Of Date']
    col_widths = [12*mm, 35*mm, 60*mm, 80*mm, 35*mm, 30*mm, 28*mm]

    table_data = [header]
    for i, r in enumerate(rows, start=1):
        table_data.append([
            str(i),
            Paragraph(r.get('lease_no',  ''), cell_st),
            Paragraph(r.get('lessee_nm', ''), cell_st),
            Paragraph(r.get('address',   ''), cell_st),
            Paragraph(r.get('city',      ''), cell_st),
            Paragraph(r.get('phone',     ''), cell_st),
            Paragraph(r.get('asof_date', ''), cell_st),
        ])

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0),  colors.HexColor('#235b98')),
        ('TEXTCOLOR',     (0, 0), (-1, 0),  colors.white),
        ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, 0),  8),
        ('ALIGN',         (0, 0), (-1, 0),  'CENTER'),
        ('VALIGN',        (0, 0), (-1, 0),  'MIDDLE'),
        ('FONTSIZE',      (0, 1), (-1, -1), 8),
        ('VALIGN',        (0, 1), (-1, -1), 'TOP'),
        ('ALIGN',         (0, 1), (0, -1),  'CENTER'),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f4f6')]),
        ('GRID',          (0, 0), (-1, -1), 0.4, colors.HexColor('#d1d5db')),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
    ]))

    story.append(tbl)
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
                    'DisbDate':        disb.strftime('%d-%m-%Y') if isinstance(disb, datetime) else (disb or ''),
                    'has_certificate': bool(r.get('CertificateFile')),
                })
            elif cert_type == 'roya_fidusia':
                rel = r.get('ReleaseDate')
                rows.append({
                    'lease_no':    r.get('LEASE_NO',   ''),
                    'lessee_nm':   r.get('LESSEE_NM',  ''),
                    'ReleaseDate': rel.strftime('%d-%m-%Y') if isinstance(rel, datetime) else (rel or ''),
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

@fiducia_bp.route('/fiducia-print')
@login_required
def fiducia_print():
   
    cert_type = request.args.get('cert_type', '').strip()
    asof      = request.args.get('asof',      '').strip()

    PRINT_ONLY = {'fiducia_not_accepted', 'roya_fiducia_not_accepted', 'fiducia_not_scan'}
    if cert_type not in PRINT_ONLY:
        return jsonify({'error': 'Invalid cert_type for print'}), 400
    if not asof:
        return jsonify({'error': 'asof is required'}), 400

    branch_cd = session.get('branchcode', '')

    try:
        raw_rows = _exec_sp(
            'USP_CA_GetDataFiducia',
            [cert_type, 'asof', '', '', asof, asof, branch_cd],
        )

        rows = []
        for r in raw_rows:
            asof_val = r.get('ASOF_DATE')
            rows.append({
                'lease_no':  r.get('LEASE_NO',  ''),
                'lessee_nm': r.get('LESSEE_NM', ''),
                'address':   r.get('ADDRESS',   ''),
                'city':      r.get('CITY',      ''),
                'phone':     r.get('PHONE',     ''),
                'asof_date': asof_val.strftime('%d-%m-%Y') if isinstance(asof_val, datetime) else (asof_val or asof),
            })

        pdf_bytes = _build_print_pdf(cert_type, asof, rows)

        label    = _CERT_LABELS.get(cert_type, cert_type).replace(' ', '_')
        filename = f"Report_{label}_{asof}.pdf"

        response = make_response(pdf_bytes)
        response.headers['Content-Type']        = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename="{filename}"'
        return response

    except Exception as e:
        current_app.logger.exception("Fiducia print error")
        return jsonify({'error': str(e)}), 500