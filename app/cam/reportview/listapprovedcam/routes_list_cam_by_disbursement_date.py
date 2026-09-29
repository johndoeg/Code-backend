from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from flask import Blueprint, jsonify, request, current_app

from app import db
from app.auth.decorators import login_required

cam_by_disbursement_date_bp = Blueprint('cam_by_disbursement_date', __name__, url_prefix='/CAM/Report')

def _exec_rows(sql: str, params: list) -> list[dict]:
    raw_conn = db.session.connection().connection
    cursor = raw_conn.cursor()
    try:
        cursor.execute(sql, params)
        if cursor.description is None:
            return []
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        cursor.close()

def _parse_date(raw: str) -> Optional[date]:
    raw = (raw or '').strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError:
        return None

def _fmt_long(val) -> str:
    if isinstance(val, (date, datetime)):
        return val.strftime('%d %B %Y')
    return ''

def _fmt_short(val) -> str:
    if isinstance(val, (date, datetime)):
        return val.strftime('%d-%m-%Y')
    return ''

def _num(val) -> float:
    if val is None:
        return 0.0
    return float(val)

def _safe_div(a, b):
    return (a / b) if b else 0

def _exec_sp(mode: str, branch_cd: str, start_date: Optional[date], end_date: Optional[date], dimension: str, exclude_jf: str) -> list[dict]:
    return _exec_rows(
        "EXEC USP_CAM_By_Disbursement ?, ?, ?, ?, ?, ?, ?",
        [mode, branch_cd, start_date, end_date, dimension, '', exclude_jf],
    )

@cam_by_disbursement_date_bp.route('/cam-by-disbursement-date/branches')
@login_required
def list_branches():
    try:
        rows = _exec_rows(
            "SELECT BRANCH_CD, BRANCH_NAME FROM UMFBRANCH WITH (NOLOCK) WHERE BRANCH_CD <> '100' ORDER BY BRANCH_CD",
            [],
        )
        return jsonify([{'branch_cd': r.get('BRANCH_CD'), 'branch_name': r.get('BRANCH_NAME')} for r in rows])
    except Exception as e:
        current_app.logger.exception("Branch list error")
        return jsonify({'error': str(e)}), 500

def _fetch_detail(branch_cd: str, start_date: Optional[date], end_date: Optional[date], exclude_jf: str) -> dict:
    rows = _exec_sp('DETAIL', branch_cd, start_date, end_date, '', exclude_jf)

    seen_appl_no = set()
    kept_rows = []
    for r in rows:
        appl_no = r.get('APPL_NO')
        if appl_no in seen_appl_no:
            continue
        seen_appl_no.add(appl_no)
        kept_rows.append(r)

    start_date_approval = None
    finish_date_approval = None

    revision_by_appl_no = {}
    if kept_rows:
        appl_nos = [r.get('APPL_NO') for r in kept_rows]
        placeholders = ','.join(['?'] * len(appl_nos))
        rev_rows = _exec_rows(
            f"SELECT NewAppl_No, REVISI FROM MCMORevisi WHERE NewAppl_No IN ({placeholders})",
            appl_nos,
        )
        for rr in rev_rows:
            revision_by_appl_no[rr.get('NewAppl_No')] = rr.get('REVISI')

    detail = []
    for i, r in enumerate(kept_rows, start=1):
        execution = r.get('EXECUTION')
        if i == 1:
            start_date_approval = _fmt_long(execution)
        finish_date_approval = _fmt_long(execution)

        has_guarantor = r.get('HAS_GUARANTOR')
        guarantor = 2 if has_guarantor == '1' else 1

        lessee_tp = r.get('LESSEE_TP')
        ind_cor = 2 if lessee_tp == 'PT' else 1

        condition = (r.get('CONDITION') or '').strip()
        new_car = 2 if condition == 'NEW' else 1

        appl_no = r.get('APPL_NO')
        revision = revision_by_appl_no.get(appl_no)
        revision_suffix = f"R{revision}" if revision is not None else ''

        edit_params = {
            'id1': r.get('Cons_Leas'),
            'id2': ind_cor,
            'id3': 1,
            'id4': guarantor,
            'id5': new_car,
            'id6': 'Edit',
            'id7': r.get('TENOR'),
            'id8': 0,
            'id9': '',
            'apless': r.get('APLESS'),
            'applno': appl_no,
        }

        detail.append({
            'no': i,
            'appl_no': appl_no,
            'cons_leas': r.get('Cons_Leas'),
            'revision_suffix': revision_suffix,
            'customer_name': r.get('LESSEE_NM') or '-',
            'brand_type': f"{r.get('BRAND_NM') or ''} / {r.get('tipe_mobil') or ''}",
            'net_finance': _num(r.get('ntf')),
            'irr': round(_num(r.get('IRR')), 2),
            'selling_rate': round(_num(r.get('DECLRATE')), 2),
            'ltv': round(_num(r.get('LTV')), 2),
            'tenor': r.get('TENOR'),
            'disbursement_date': _fmt_short(execution),
            'cmo': r.get('CMO'),
            'edit_link_params': edit_params,
        })

    summary_by_vehicle = _build_summary_by_vehicle(branch_cd, start_date, end_date, exclude_jf)

    return {
        'data': detail,
        'date_range_label': (
            f"{_fmt_long(start_date)} - {_fmt_long(end_date)}"
            if start_date and end_date
            else f"{start_date_approval or ''} - {finish_date_approval or ''}"
        ),
        'summary_by_vehicle': summary_by_vehicle,
    }

def _build_summary_by_vehicle(branch_cd: str, start_date: Optional[date], end_date: Optional[date], exclude_jf: str) -> list[dict]:
   
    rows = _exec_sp('TOTAL', branch_cd, start_date, end_date, 'Vehicle', exclude_jf)

    out = []
    cek = None
    group = {'fin': 0, 'unit': 0, 'tenor': 0, 'income': 0, 'ltv': 0, 'sell_income': 0}
    grand = {'fin': 0, 'unit': 0, 'tenor': 0, 'income': 0, 'ltv': 0, 'sell_income': 0}

    def group_averages(g):
        return {
            'avg_irr': round(_safe_div(g['income'], g['fin']) * 100, 2),
            'avg_sell': round(_safe_div(g['sell_income'], g['unit']), 2),
            'avg_ltv': round(_safe_div(g['ltv'], g['unit']), 2),
            'avg_tenor': round(_safe_div(g['tenor'], g['unit']), 2),
            'avg_fin': round(_safe_div(g['fin'], g['unit'])),
        }

    for r in rows:
        tot = {
            'fin': _num(r.get('tot_fin')),
            'unit': _num(r.get('tot_unit')),
            'tenor': _num(r.get('tot_tenor')),
            'income': _num(r.get('tot_income')),
            'ltv': _num(r.get('tot_ltv')),
            'sell_income': _num(r.get('tot_sell_income')),
        }
        cons_leas = r.get('Cons_Leas')

        if cek is not None and cek != cons_leas:
            out.append({
                'type': 'subtotal',
                'label': f"Grand Total {cek}",
                'net_finance': round(group['fin']),
                'units': int(group['unit']),
                **group_averages(group),
            })
            group = dict(tot)
        else:
            for k in group:
                group[k] += tot[k]

        cek = cons_leas
        for k in grand:
            grand[k] += tot[k]

        row_avgs = {
            'avg_irr': round(_safe_div(tot['income'], tot['fin']) * 100, 2),
            'avg_sell': round(_safe_div(tot['sell_income'], tot['unit']), 2),
            'avg_ltv': round(_safe_div(tot['ltv'], tot['unit']), 2),
            'avg_tenor': round(_safe_div(tot['tenor'], tot['unit']), 2),
            'avg_fin': round(_safe_div(tot['fin'], tot['unit'])),
        }
        out.append({
            'type': 'detail',
            'cons_leas': cons_leas,
            'model': r.get('Model'),
            'condition': r.get('CONDITION'),
            'net_finance': round(tot['fin']),
            'units': int(tot['unit']),
            **row_avgs,
        })

    if cek is not None:
        out.append({
            'type': 'subtotal',
            'label': f"Grand Total {cek}",
            'net_finance': round(group['fin']),
            'units': int(group['unit']),
            **group_averages(group),
        })
        out.append({
            'type': 'grand_total',
            'label': 'Grand Total',
            'net_finance': round(grand['fin']),
            'units': int(grand['unit']),
            **group_averages(grand),
        })

    return out

@cam_by_disbursement_date_bp.route('/cam-by-disbursement-date/detail')
@login_required
def get_detail():
    branch_cd = request.args.get('branch', '').strip()
    start_date = _parse_date(request.args.get('start_date', ''))
    end_date = _parse_date(request.args.get('end_date', ''))
    exclude_jf = '1' if request.args.get('exclude_jf', '0') == '1' else '0'

    if not branch_cd and not start_date and not end_date:
        return jsonify({'error': 'Please fill at least one search field'}), 400

    try:
        return jsonify(_fetch_detail(branch_cd, start_date, end_date, exclude_jf))
    except Exception as e:
        current_app.logger.exception("CAM by disbursement date detail error")
        return jsonify({'error': str(e)}), 500

_DIMENSION_CONFIG = {
    'branch': {'sp_dimension': 'Branch', 'label_field': 'BRANCH_NAME', 'metric': 'tenor_and_year'},
    'cmo': {'sp_dimension': 'CMO', 'label_field': 'FULLNAME', 'metric': 'tenor'},
    'tenor': {'sp_dimension': 'Tenor', 'label_field': 'tenor', 'metric': 'proportion_tenor'},
    'karoseri': {'sp_dimension': 'Karoseri', 'label_field': 'Karoseri', 'metric': 'proportion_fin'},
    'model': {'sp_dimension': 'Model', 'label_field': 'MODEL_NM', 'metric': 'proportion_fin'},
    'cmh': {'sp_dimension': 'CMH', 'label_field': 'CMH', 'metric': 'tenor'},
}

def _fetch_dimension_summary(dimension_key: str, branch_cd: str, start_date: Optional[date], end_date: Optional[date], exclude_jf: str) -> dict:
    config = _DIMENSION_CONFIG[dimension_key]
    rows = _exec_sp('TOTAL', branch_cd, start_date, end_date, config['sp_dimension'], exclude_jf)

    data = []
    grand = {'fin': 0, 'unit': 0, 'tenor': 0, 'income': 0, 'ltv': 0, 'sell_income': 0}
    last_tenor_all = 0
    last_fin_all = 0

    for r in rows:
        tot_fin = _num(r.get('tot_fin'))
        tot_unit = _num(r.get('tot_unit'))
        tot_tenor = _num(r.get('tot_tenor'))
        tot_income = _num(r.get('tot_income'))
        tot_ltv = _num(r.get('tot_ltv'))
        tot_sell_income = _num(r.get('tot_sell_income'))

        avg_irr = round(_safe_div(tot_income, tot_fin) * 100, 2)
        avg_sell = round(_safe_div(tot_sell_income, tot_unit), 2)
        avg_ltv = round(_safe_div(tot_ltv, tot_unit), 2)
        avg_fin = round(_safe_div(tot_fin, tot_unit))

        row_out = {
            'label': r.get(config['label_field']),
            'net_finance': round(tot_fin),
            'units': int(tot_unit),
            'avg_irr': avg_irr,
            'avg_sell': avg_sell,
            'avg_ltv': avg_ltv,
            'avg_fin': avg_fin,
        }

        if config['metric'] == 'tenor_and_year':
            tot_tahun = _num(r.get('tot_tahun'))
            row_out['avg_tenor'] = round(_safe_div(tot_tenor, tot_unit), 2)
            row_out['avg_tahun'] = round(_safe_div(tot_tahun, tot_unit))
            grand.setdefault('tahun', 0)
            grand['tahun'] += tot_tahun
        elif config['metric'] == 'tenor':
            row_out['avg_tenor'] = round(_safe_div(tot_tenor, tot_unit), 2)
        elif config['metric'] == 'proportion_tenor':
            last_tenor_all = _num(r.get('tot_tenor_all'))
            row_out['proportion'] = round(_safe_div(tot_tenor, last_tenor_all) * 100, 2)
        elif config['metric'] == 'proportion_fin':
            last_fin_all = _num(r.get('tot_fin_all'))
            row_out['proportion'] = round(_safe_div(tot_fin, last_fin_all) * 100, 2)

        data.append(row_out)

        grand['fin'] += tot_fin
        grand['unit'] += tot_unit
        grand['tenor'] += tot_tenor
        grand['income'] += tot_income
        grand['ltv'] += tot_ltv
        grand['sell_income'] += tot_sell_income

    grand_out = {
        'label': 'Grand Total',
        'net_finance': round(grand['fin']),
        'units': int(grand['unit']),
        'avg_irr': round(_safe_div(grand['income'], grand['fin']) * 100, 2),
        'avg_sell': round(_safe_div(grand['sell_income'], grand['unit']), 2),
        'avg_ltv': round(_safe_div(grand['ltv'], grand['unit']), 2),
        'avg_fin': round(_safe_div(grand['fin'], grand['unit'])),
    }
    if config['metric'] == 'tenor_and_year':
        grand_out['avg_tenor'] = round(_safe_div(grand['tenor'], grand['unit']), 2)
        grand_out['avg_tahun'] = round(_safe_div(grand.get('tahun', 0), grand['unit']))
    elif config['metric'] == 'tenor':
        grand_out['avg_tenor'] = round(_safe_div(grand['tenor'], grand['unit']), 2)
    elif config['metric'] == 'proportion_tenor':
        grand_out['proportion'] = round(_safe_div(grand['tenor'], last_tenor_all) * 100, 2)
    elif config['metric'] == 'proportion_fin':
        grand_out['proportion'] = round(_safe_div(grand['fin'], last_fin_all) * 100, 2)

    return {'metric': config['metric'], 'data': data, 'grand_total': grand_out}

@cam_by_disbursement_date_bp.route('/cam-by-disbursement-date/summary')
@login_required
def get_dimension_summary():
    dimension_key = request.args.get('dimension', '').strip().lower()
    if dimension_key not in _DIMENSION_CONFIG:
        return jsonify({'error': f"dimension must be one of {list(_DIMENSION_CONFIG)}"}), 400

    branch_cd = request.args.get('branch', '').strip()
    start_date = _parse_date(request.args.get('start_date', ''))
    end_date = _parse_date(request.args.get('end_date', ''))
    exclude_jf = '1' if request.args.get('exclude_jf', '0') == '1' else '0'

    try:
        return jsonify(_fetch_dimension_summary(dimension_key, branch_cd, start_date, end_date, exclude_jf))
    except Exception as e:
        current_app.logger.exception("CAM by disbursement date summary error")
        return jsonify({'error': str(e)}), 500