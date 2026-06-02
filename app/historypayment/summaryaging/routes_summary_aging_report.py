from flask import Blueprint, jsonify, request, current_app, session, make_response
from app import db
from sqlalchemy import text
import io

from reportlab.lib           import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.styles    import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units     import mm
from reportlab.platypus      import (SimpleDocTemplate, Table, TableStyle,
                                     Paragraph, Spacer)
from reportlab.lib.enums     import TA_CENTER, TA_LEFT

from .summary_aging_excel import (
    build_excel_branch,
    build_excel_by_person,
    build_excel_other,
    build_excel_dealer,
    _fmt_date, _safe_pct,
    _KEYS_T1, _KEYS_T2, _KEYS_CMO,
)

summary_aging_bp = Blueprint('summary_aging', __name__, url_prefix='/SummaryAging')

def _exec_sp(sp_name: str, params: list) -> list[dict]:
   
    placeholders = ', '.join(['?'] * len(params))
    sql          = f"EXEC {sp_name} {placeholders}"
    raw_conn     = db.session.connection().connection
    cursor       = raw_conn.cursor()
    try:
        cursor.execute(sql, params)
        while cursor.description is None:
            if not cursor.nextset():
                return []
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        cursor.close()

@summary_aging_bp.route('/api/combo')
def get_combo():
   
    try:
        result = db.session.execute(text(
            "SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH (NOLOCK) "
            "WHERE CAT_VALUE = 'SUMMARY_AGING_BY' ORDER BY VALUE"
        ))
        options = [{'value': str(r.VALUE), 'label': r.DESC_VALUE}
                   for r in result]
        return jsonify(options)
    except Exception as e:
        current_app.logger.exception("Combo load error")
        return jsonify({'error': str(e)}), 500


@summary_aging_bp.route('/api/excel')
def export_excel():
   
    asof   = request.args.get('asof',   '').strip()
    by     = request.args.get('by',     '0').strip()
    cek_jf = request.args.get('cek_jf', '0').strip()

    if not asof:
        return jsonify({'error': 'asof is required'}), 400

    company  = session.get('company', '')
    
    print('data', asof, cek_jf)

    try:
        if by == '0':
            # Branch
            rows = _exec_sp('USP_SUMMARY_AGING', [asof, cek_jf])
            xlsx = build_excel_branch(rows, asof, company)
            fname = 'SummaryAging.xlsx'

        elif by == '1':
            # CMO — SP called twice: main data + outstanding section
            rows     = _exec_sp('USP_SUMMARY_AGING_BYCMO', [asof, cek_jf])
            rows_out = _exec_sp('USP_SUMMARY_AGING_BYCMO', [asof, cek_jf])
            xlsx = build_excel_by_person(rows, rows_out, asof, company,
                                         'CMO', '(BY CMO)')
            fname = 'SummaryAgingByCMO.xlsx'

        elif by == '2':
            # CMH — SP called twice
            rows     = _exec_sp('USP_SUMMARY_AGING_BYCMH', [asof, cek_jf])
            rows_out = _exec_sp('USP_SUMMARY_AGING_BYCMH', [asof, cek_jf])
            xlsx = build_excel_by_person(rows, rows_out, asof, company,
                                         'CMH', '(BY CMH)')
            fname = 'SummaryAgingByCMH.xlsx'

        elif by == '3':
            # Dealer — 3 separate sub-queries to the same SP
            rows_ta  = _exec_sp('USP_SUMMARY_AGING_OTHER', [asof, 'DEALER_TOT_ACC'])
            rows_od  = _exec_sp('USP_SUMMARY_AGING_OTHER', [asof, 'DEALER_TOT_OD'])
            rows_od90= _exec_sp('USP_SUMMARY_AGING_OTHER', [asof, 'DEALER_TOT_OD90'])
            xlsx = build_excel_dealer(rows_ta, rows_od, rows_od90, asof, company)
            fname = 'SummaryAgingByDealer.xlsx'

        else:
            # Other (Karoseri / Tenor / LTV)
            rows_k = _exec_sp('USP_SUMMARY_AGING_OTHER', [asof, 'KAROSERI'])
            rows_t = _exec_sp('USP_SUMMARY_AGING_OTHER', [asof, 'TENOR'])
            rows_l = _exec_sp('USP_SUMMARY_AGING_OTHER', [asof, 'LTV'])
            xlsx = build_excel_other(rows_k, rows_t, rows_l, asof, company)
            fname = 'SummaryAgingByOther.xlsx'

        response = make_response(xlsx)
        response.headers['Content-Type']        = (
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response.headers['Content-Disposition'] = f'attachment; filename="{fname}"'
        return response

    except Exception as e:
        current_app.logger.exception("Summary Aging Excel export error")
        return jsonify({'error': str(e)}), 500

@summary_aging_bp.route('/api/pdf')
def export_pdf():
   
    asof   = request.args.get('asof',   '').strip()
    cek_jf = request.args.get('cek_jf', '0').strip()
    by     = request.args.get('by',     '0').strip()

    if not asof:
        return jsonify({'error': 'asof is required'}), 400
    if by != '0':
        return jsonify({'error': 'PDF is only available for By Branch'}), 400

    try:
        rows = _exec_sp('USP_SUMMARY_AGING', [asof, cek_jf])
        pdf  = _build_pdf(rows, asof)

        response = make_response(pdf)
        response.headers['Content-Type']        = 'application/pdf'
        response.headers['Content-Disposition'] = (
            f'inline; filename="SummaryAging_{asof}.pdf"')
        return response

    except Exception as e:
        current_app.logger.exception("Summary Aging PDF export error")
        return jsonify({'error': str(e)}), 500

def _fmt_num(v) -> str:
    
    try:
        n = float(v or 0)
        if n != int(n):
            return f'{n:,.2f}'
        return f'{int(n):,}'
    except (TypeError, ValueError):
        return str(v or '')


def _build_pdf(rows: list[dict], asof: str) -> bytes:
  
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A3),
        leftMargin=10 * mm, rightMargin=10 * mm,
        topMargin=10 * mm,  bottomMargin=10 * mm,
    )

    styles  = getSampleStyleSheet()
    title_s = ParagraphStyle('t', parent=styles['Normal'],
                              fontSize=10, fontName='Helvetica-Bold',
                              alignment=TA_CENTER, spaceAfter=6)
    hdr_s   = ParagraphStyle('h', parent=styles['Normal'],
                              fontSize=6, fontName='Helvetica-Bold',
                              alignment=TA_CENTER)
    cell_s  = ParagraphStyle('c', parent=styles['Normal'],
                              fontSize=6, fontName='Helvetica')
    num_s   = ParagraphStyle('n', parent=styles['Normal'],
                              fontSize=6, fontName='Helvetica',
                              alignment=TA_CENTER)

    GREY    = colors.HexColor('#f2f2f2')
    BLACK   = colors.black
    WHITE   = colors.white

    def _ts(header_rows=2):
        base = [
            ('BACKGROUND', (0, 0), (-1, header_rows - 1), GREY),
            ('FONTNAME',   (0, 0), (-1, header_rows - 1), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, -1),               6),
            ('GRID',       (0, 0), (-1, -1),               0.3, BLACK),
            ('ALIGN',      (0, 0), (-1, header_rows - 1), 'CENTER'),
            ('VALIGN',     (0, 0), (-1, -1),              'MIDDLE'),
            ('ROWBACKGROUNDS', (0, header_rows), (-1, -1),
             [WHITE, colors.HexColor('#f9f9f9')]),
            ('FONTNAME',   (0, -1), (-1, -1), 'Helvetica-Bold'),  # total row bold
        ]
        return TableStyle(base)

    fmt = _fmt_date(asof)

    CATS_1 = ['curr', 'b1',   'b2',   'b3',   'b4',   '90up']
    CATS_2 = ['b5',   'b6',   'b7',   '180up','od',   'tot']
    FIELDS = ['acc',  'amt',  'op',   'ar']

    tots: dict = {}
    for cat in CATS_1 + CATS_2:
        for f in FIELDS:
            tots[f'{f}_{cat}'] = sum(r.get(f'{f}_{cat}', 0) or 0 for r in rows)

    tot_out = {f: rows[0].get(f'{f}_tot_out', 0) if rows else 0
               for f in FIELDS}

    def _pct_tots(cat): return [_safe_pct(tots[f'{f}_{cat}'], tot_out[f]) for f in FIELDS]

    PERIODS_1 = ['Current','01 s/d 10 Days','11 s/d 30 Days',
                 '31 s/d 60 Days','61 s/d 90 Days','> 90 Days']
    SUB_HDRS  = ['Acc','Amount','Outstanding Principal','AR Principal']

    h1 = ['Branch'] + [p for p in PERIODS_1 for _ in range(4)]
    h2 = ['']       + SUB_HDRS * 6
    t1_data = [h1, h2]

    for r in rows:
        row_vals = [r.get('BRANCH_NAME','')]
        for cat in CATS_1:
            row_vals += [_fmt_num(r.get(f'{f}_{cat}')) for f in FIELDS]
        t1_data.append(row_vals)

    tot_row = ['Total']
    for cat in CATS_1:
        tot_row += [_fmt_num(tots[f'{f}_{cat}']) for f in FIELDS]
    t1_data.append(tot_row)

    t1_spans = [('SPAN', (1 + i*4, 0), (4 + i*4, 0)) for i in range(6)]
    t1_style = _ts(2)
    for s in t1_spans:
        t1_style.add(*s)

    col_w = [30*mm] + [18*mm] * 24
    t1 = Table(t1_data, colWidths=col_w, repeatRows=2)
    t1.setStyle(t1_style)

    PERIODS_2 = ['91 s/d 120 Days','121 s/d 150 Days','151 s/d 180 Days',
                 '>180 Days','Total Overdue','Total']
    h1b = ['Branch'] + [p for p in PERIODS_2 for _ in range(4)]
    h2b = ['']       + SUB_HDRS * 6
    t2_data = [h1b, h2b]

    for r in rows:
        row_vals = [r.get('BRANCH_NAME','')]
        for cat in CATS_2:
            row_vals += [_fmt_num(r.get(f'{f}_{cat}')) for f in FIELDS]
        t2_data.append(row_vals)

    tot_row2 = ['Total']
    for cat in CATS_2:
        tot_row2 += [_fmt_num(tots[f'{f}_{cat}']) for f in FIELDS]
    t2_data.append(tot_row2)

    t2_style = _ts(2)
    for s in t1_spans:
        t2_style.add(*s)

    t2 = Table(t2_data, colWidths=col_w, repeatRows=2)
    t2.setStyle(t2_style)

    h3a = ['Branch', 'Outstanding',    '',     '',     '',     '',     '',     '',     '']
    h3b = ['',       'Acc','%','Amount','%','Outstanding Principal','%','AR Principal','%']
    t3_data = [h3a, h3b]

    for r in rows:
        t3_data.append([
            r.get('BRANCH_NAME',''),
            _fmt_num(r.get('tot_acc',0)),  _fmt_num(r.get('acc_persen',0)),
            _fmt_num(r.get('tot_amt',0)),  _fmt_num(r.get('amt_persen',0)),
            _fmt_num(r.get('tot_op',0)),   _fmt_num(r.get('op_persen',0)),
            _fmt_num(r.get('tot_ar',0)),   _fmt_num(r.get('ar_persen',0)),
        ])

    t3_data.append([
        'Total',
        _fmt_num(tot_out['acc']), '100',
        _fmt_num(tot_out['amt']), '100',
        _fmt_num(tot_out['op']),  '100',
        _fmt_num(tot_out['ar']),  '100',
    ])

    t3_style = _ts(2)
    t3_style.add('SPAN', (1, 0), (8, 0))

    t3 = Table(t3_data,
               colWidths=[30*mm,20*mm,12*mm,25*mm,12*mm,35*mm,12*mm,25*mm,12*mm],
               repeatRows=2)
    t3.setStyle(t3_style)

    t4_data = [h1, h2]
    for r in rows:
        row_vals = [r.get('BRANCH_NAME','')]
        for cat in CATS_1:
            row_vals += [_fmt_num(r.get(f'{f}_{cat}_tot')) for f in FIELDS]
        t4_data.append(row_vals)

    tot_row4 = ['Total']
    for cat in CATS_1:
        tot_row4 += [_fmt_num(_safe_pct(tots[f'{f}_{cat}'], tot_out[f])) for f in FIELDS]
    t4_data.append(tot_row4)

    t4_style = _ts(2)
    for s in t1_spans:
        t4_style.add(*s)
    t4 = Table(t4_data, colWidths=col_w, repeatRows=2)
    t4.setStyle(t4_style)

    t5_data = [h1b, h2b]
    for r in rows:
        row_vals = [r.get('BRANCH_NAME','')]
        for cat in CATS_2:
            row_vals += [_fmt_num(r.get(f'{f}_{cat}_tot')) for f in FIELDS]
        t5_data.append(row_vals)

    tot_row5 = ['Total']
    for cat in CATS_2:
        tot_row5 += [_fmt_num(_safe_pct(tots[f'{f}_{cat}'], tot_out[f])) for f in FIELDS]
    t5_data.append(tot_row5)

    t5_style = _ts(2)
    for s in t1_spans:
        t5_style.add(*s)
    t5 = Table(t5_data, colWidths=col_w, repeatRows=2)
    t5.setStyle(t5_style)

    story = [
        Paragraph(f'SUMMARY OF AGING DAILY LATE PAYMENT REPORT AS OF {fmt}<br/>'
                  f'CURRENCY : IDR', title_s),
        Spacer(1, 4*mm),
        t1,
        Spacer(1, 6*mm),
        t2,
        Spacer(1, 6*mm),
        Paragraph(f'TOTAL OUTSTANDING AS OF {fmt}', title_s),
        Spacer(1, 2*mm),
        t3,
        Spacer(1, 6*mm),
        Paragraph('COMPARISON TO TOTAL OUTSTANDING', title_s),
        Spacer(1, 2*mm),
        t4,
        Spacer(1, 6*mm),
        t5,
    ]

    doc.build(story)
    buf.seek(0)
    return buf.read()