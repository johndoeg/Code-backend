from __future__ import annotations

from datetime import date, datetime
from flask import Blueprint, jsonify, request, current_app
from app import db
from app.auth.decorators import login_required

ttot_report_bp = Blueprint('ttot_report', __name__, url_prefix='/MasterData')

_TTOT_REASON_CATEGORY = '1'

_TTOT_QUERY = """
    SELECT
        tt.ID_BLACKLIST AS BlacklistId,
        vv.Name         AS Name,
        xx.NAME         AS Alias,
        vv.Address      AS Address
    FROM Blacklist_Dttot tt WITH (NOLOCK)
        INNER JOIN MCMOWatchList vv WITH (NOLOCK) ON vv.No = tt.ID_BLACKLIST
        LEFT JOIN MCMOWATCHLIST_ALIASNM xx WITH (NOLOCK) ON xx.No = tt.ID_BLACKLIST
    WHERE vv.Reason_Category = ?
        AND vv.Flag_Type = 'B'
        AND (vv.FlagDel <> '1' OR vv.FlagDel IS NULL)
        AND CONVERT(date, tt.CAM_DATE) >= ?
        AND CONVERT(date, tt.CAM_DATE) <= ?
    GROUP BY tt.ID_BLACKLIST, vv.Name, xx.NAME, vv.Address
    ORDER BY vv.Name ASC
"""

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

def _parse_date(raw: str, field_name: str) -> date:
    raw = (raw or '').strip()
    if not raw:
        raise ValueError(f'{field_name} is required')
    try:
        return datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError as exc:
        raise ValueError(f'{field_name} must be in YYYY-MM-DD format') from exc

def _query_ttot(date_from: date, date_to: date) -> list[dict]:
    return _exec_rows(_TTOT_QUERY, [_TTOT_REASON_CATEGORY, date_from, date_to])

def _serialize_row(r: dict, no: int) -> dict:
    return {
        'no': no,
        'blacklist_id': r.get('BlacklistId'),
        'name': r.get('Name') or '-',
        'alias': r.get('Alias') or '-',
        'address': r.get('Address') or '-',
    }

@ttot_report_bp.route('/ttot-report/list')
@login_required
def list_ttot():
    try:
        date_from = _parse_date(request.args.get('date_from', ''), 'date_from')
        date_to = _parse_date(request.args.get('date_to', ''), 'date_to')
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    if date_from > date_to:
        return jsonify({'error': 'date_from cannot be later than date_to'}), 400

    try:
        rows = _query_ttot(date_from, date_to)
        data = [_serialize_row(r, i) for i, r in enumerate(rows, start=1)]
        return jsonify({
            'data': data,
            'total': len(data),
            'date_from': date_from.isoformat(),
            'date_to': date_to.isoformat(),
        })
    except Exception as e:
        current_app.logger.exception("TTOT report list error")
        return jsonify({'error': str(e)}), 500