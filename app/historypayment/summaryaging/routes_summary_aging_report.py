from flask import Blueprint, jsonify, request, current_app, session, make_response
from app import db
from app.auth.decorators import login_required
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

@summary_aging_bp.route('/combo')
@login_required
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

@summary_aging_bp.route('/excel')
@login_required
def export_excel():
    asof   = request.args.get('asof',   '').strip()
    by     = request.args.get('by',     '0').strip()
    cek_jf = request.args.get('cek_jf', '0').strip()

    if not asof:
        return jsonify({'error': 'asof is required'}), 400

    company = session.get('company', '')

    try:
        if by == '0':
            rows = _exec_sp('USP_SUMMARY_AGING', [asof, cek_jf])
            xlsx = build_excel_branch(rows, asof, company)
            fname = 'SummaryAging.xlsx'

        elif by == '1':
            rows     = _exec_sp('USP_SUMMARY_AGING_BYCMO', [asof, cek_jf])
            rows_out = _exec_sp('USP_SUMMARY_AGING_BYCMO', [asof, cek_jf])
            xlsx = build_excel_by_person(rows, rows_out, asof, company,
                                         'CMO', '(BY CMO)')
            fname = 'SummaryAgingByCMO.xlsx'

        elif by == '2':
            rows     = _exec_sp('USP_SUMMARY_AGING_BYCMH', [asof, cek_jf])
            rows_out = _exec_sp('USP_SUMMARY_AGING_BYCMH', [asof, cek_jf])
            xlsx = build_excel_by_person(rows, rows_out, asof, company,
                                         'CMH', '(BY CMH)')
            fname = 'SummaryAgingByCMH.xlsx'

        elif by == '3':
            rows_ta   = _exec_sp('USP_SUMMARY_AGING_OTHER', [asof, 'DEALER_TOT_ACC'])
            rows_od   = _exec_sp('USP_SUMMARY_AGING_OTHER', [asof, 'DEALER_TOT_OD'])
            rows_od90 = _exec_sp('USP_SUMMARY_AGING_OTHER', [asof, 'DEALER_TOT_OD90'])
            xlsx = build_excel_dealer(rows_ta, rows_od, rows_od90, asof, company)
            fname = 'SummaryAgingByDealer.xlsx'

        else:
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

@summary_aging_bp.route('/pdf')
@login_required
def export_pdf():
    asof   = request.args.get('asof',   '').strip()
    cek_jf = request.args.get('cek_jf', '0').strip()
    by     = request.args.get('by',     '0').strip()

    if not asof:
        return jsonify({'error': 'asof is required'}), 400
    if by != '0':
        return jsonify({'error': 'PDF is only available for By Branch'}), 400

    try:
        rows    = _exec_sp('USP_SUMMARY_AGING', [asof, cek_jf])
        company = session.get('company', '') or current_app.config.get('COMPANY_NAME', '')
        pdf     = _build_pdf(rows, asof, company)

        response = make_response(pdf)
        response.headers['Content-Type']        = 'application/pdf'
        response.headers['Content-Disposition'] = (
            f'inline; filename="SummaryAging_{asof}.pdf"')
        response.headers['Content-Length']       = str(len(pdf))
        response.headers['Cache-Control']        = 'no-store'
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

_MARGIN   = 8 * mm
_USABLE_W = landscape(A3)[0] - 2 * _MARGIN
_BRANCH_W = 26 * mm
_DATA_W   = (_USABLE_W - _BRANCH_W) / 24
_FS       = 5.3

def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 6)
    canvas.drawRightString(landscape(A3)[0] - _MARGIN, 6 * mm, f'Page {doc.page}')
    canvas.restoreState()

def _build_pdf(rows: list[dict], asof: str, company: str = '') -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A3),
        leftMargin=_MARGIN, rightMargin=_MARGIN,
        topMargin=10 * mm,  bottomMargin=10 * mm,
        title='Summary Aging Report',
    )

    styles  = getSampleStyleSheet()
    title_s = ParagraphStyle('t', parent=styles['Normal'],
                             fontSize=10, fontName='Helvetica-Bold',
                             alignment=TA_CENTER, spaceAfter=6, leading=13)
    comp_s  = ParagraphStyle('co', parent=styles['Normal'],
                             fontSize=9, fontName='Helvetica-Bold',
                             alignment=TA_LEFT, leading=11)
    head_s  = ParagraphStyle('hc', parent=styles['Normal'],
                             fontSize=_FS, fontName='Helvetica-Bold',
                             alignment=TA_CENTER, leading=_FS + 1)

    GREY  = colors.HexColor('#e8eef5')
    GREY2 = colors.HexColor('#f4f7fb')
    BLACK = colors.black
    WHITE = colors.white

    def P(txt):
        return Paragraph(str(txt), head_s)

    def _ts(header_rows=2, num_from_col=1):
        return TableStyle([
            ('BACKGROUND',     (0, 0), (-1, header_rows - 1), GREY),
            ('FONTNAME',       (0, 0), (-1, header_rows - 1), 'Helvetica-Bold'),
            ('FONTSIZE',       (0, 0), (-1, -1), _FS),
            ('GRID',           (0, 0), (-1, -1), 0.3, BLACK),
            ('ALIGN',          (0, 0), (-1, header_rows - 1), 'CENTER'),
            ('ALIGN',          (0, header_rows), (num_from_col - 1, -1), 'LEFT'),
            ('ALIGN',          (num_from_col, header_rows), (-1, -1), 'RIGHT'),
            ('VALIGN',         (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING',    (0, 0), (-1, -1), 2),
            ('RIGHTPADDING',   (0, 0), (-1, -1), 2),
            ('TOPPADDING',     (0, 0), (-1, -1), 1.5),
            ('BOTTOMPADDING',  (0, 0), (-1, -1), 1.5),
            ('ROWBACKGROUNDS', (0, header_rows), (-1, -2), [WHITE, GREY2]),
            ('BACKGROUND',     (0, -1), (-1, -1), GREY),
            ('FONTNAME',       (0, -1), (-1, -1), 'Helvetica-Bold'),
        ])

    fmt = _fmt_date(asof)

    CATS_1 = ['curr', 'b1', 'b2', 'b3', 'b4', '90up']
    CATS_2 = ['b5', 'b6', 'b7', '180up', 'od', 'tot']
    FIELDS = ['acc', 'amt', 'op', 'ar']

    tots: dict = {}
    for cat in CATS_1 + CATS_2:
        for f in FIELDS:
            tots[f'{f}_{cat}'] = sum(r.get(f'{f}_{cat}', 0) or 0 for r in rows)

    tot_out = {f: (rows[0].get(f'{f}_tot_out', 0) if rows else 0) for f in FIELDS}

    PERIODS_1 = ['Current', '01 s/d 10 Days', '11 s/d 30 Days',
                 '31 s/d 60 Days', '61 s/d 90 Days', '> 90 Days']
    PERIODS_2 = ['91 s/d 120 Days', '121 s/d 150 Days', '151 s/d 180 Days',
                 '>180 Days', 'Total Overdue', 'Total']
    SUB_HDRS  = ['Acc', 'Amount', 'Outstanding Principal', 'AR Principal']

    col_w     = [_BRANCH_W] + [_DATA_W] * 24
    bucket_spans = [('SPAN', (1 + i * 4, 0), (4 + i * 4, 0)) for i in range(6)]
    branch_span  = ('SPAN', (0, 0), (0, 1))

    def _bucket_table(periods, cats, value_fn):
        h1 = [P('Branch')] + [P(p) for p in periods for _ in range(4)]
        h2 = [''] + [P(s) for s in SUB_HDRS] * 6
        data = [h1, h2]
        for r in rows:
            row_vals = [r.get('BRANCH_NAME', '')]
            for cat in cats:
                row_vals += [value_fn(r, f, cat) for f in FIELDS]
            data.append(row_vals)
        tot_row = ['Total']
        for cat in cats:
            tot_row += [value_fn(None, f, cat) for f in FIELDS]
        data.append(tot_row)

        t = Table(data, colWidths=col_w, repeatRows=2)
        st = _ts(2)
        st.add(*branch_span)
        for sp in bucket_spans:
            st.add(*sp)
        t.setStyle(st)
        return t

    def _amt(r, f, cat):
        if r is None:
            return _fmt_num(tots[f'{f}_{cat}'])
        return _fmt_num(r.get(f'{f}_{cat}'))

    t1 = _bucket_table(PERIODS_1, CATS_1, _amt)
    t2 = _bucket_table(PERIODS_2, CATS_2, _amt)

    h3a = [P('Branch'), P('Outstanding'), '', '', '', '', '', '', '']
    h3b = ['', P('Acc'), P('%'), P('Amount'), P('%'),
           P('Outstanding Principal'), P('%'), P('AR Principal'), P('%')]
    t3_data = [h3a, h3b]
    for r in rows:
        t3_data.append([
            r.get('BRANCH_NAME', ''),
            _fmt_num(r.get('tot_acc', 0)), _fmt_num(r.get('acc_persen', 0)),
            _fmt_num(r.get('tot_amt', 0)), _fmt_num(r.get('amt_persen', 0)),
            _fmt_num(r.get('tot_op', 0)),  _fmt_num(r.get('op_persen', 0)),
            _fmt_num(r.get('tot_ar', 0)),  _fmt_num(r.get('ar_persen', 0)),
        ])
    t3_data.append([
        'Total',
        _fmt_num(tot_out['acc']), '100',
        _fmt_num(tot_out['amt']), '100',
        _fmt_num(tot_out['op']),  '100',
        _fmt_num(tot_out['ar']),  '100',
    ])
    t3_style = _ts(2)
    t3_style.add('SPAN', (0, 0), (0, 1))
    t3_style.add('SPAN', (1, 0), (8, 0))
    t3 = Table(t3_data,
               colWidths=[30 * mm, 24 * mm, 14 * mm, 30 * mm, 14 * mm,
                          40 * mm, 14 * mm, 30 * mm, 14 * mm],
               repeatRows=2)
    t3.setStyle(t3_style)

    def _cmp(r, f, cat):
        if r is None:
            return _fmt_num(_safe_pct(tots[f'{f}_{cat}'], tot_out[f]))
        return _fmt_num(r.get(f'{f}_{cat}_tot'))

    t4 = _bucket_table(PERIODS_1, CATS_1, _cmp)
    t5 = _bucket_table(PERIODS_2, CATS_2, _cmp)

    story = []
    if company:
        story.append(Paragraph(str(company), comp_s))
    story += [
        Paragraph(f'SUMMARY OF AGING DAILY LATE PAYMENT REPORT AS OF {fmt}<br/>'
                  f'CURRENCY : IDR', title_s),
        Spacer(1, 3 * mm),
        t1,
        Spacer(1, 5 * mm),
        t2,
        Spacer(1, 6 * mm),
        Paragraph(f'TOTAL OUTSTANDING AS OF {fmt}', title_s),
        Spacer(1, 2 * mm),
        t3,
        Spacer(1, 6 * mm),
        Paragraph('COMPARISON TO TOTAL OUTSTANDING', title_s),
        Spacer(1, 2 * mm),
        t4,
        Spacer(1, 5 * mm),
        t5,
    ]

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buf.seek(0)
    return buf.read()