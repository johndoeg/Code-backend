from __future__ import annotations

from flask import Blueprint, jsonify, request, current_app

from app import db
from app.auth.decorators import login_required

customer_lookup_bp = Blueprint('customer_lookup', __name__, url_prefix='/MasterData')

_VALID_LESSEE_TYPES = {'PR', 'PT'}
_MAX_RESULTS = 100

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

@customer_lookup_bp.route('/customers')
@login_required
def search_customers():
    name = request.args.get('name', '').strip()
    lessee_type = request.args.get('lessee_type', '').strip().upper()

    where = []
    params: list = []

    if name:
        where.append("LESSEE_NM LIKE ?")
        params.append(f"%{name}%")
    if lessee_type in _VALID_LESSEE_TYPES:
        where.append("LESSEE_TP = ?")
        params.append(lessee_type)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    try:
        rows = _exec_rows(
            f"""
            SELECT DISTINCT TOP {_MAX_RESULTS}
                APLESS, LESSEE_NM, LESSEE_TP, ADDRESS1, ID_CARD, NPWP, PHONE1
            FROM CAFLESS WITH (NOLOCK)
            {where_sql}
            ORDER BY LESSEE_NM
            """,
            params,
        )
        data = [
            {
                'apless': r.get('APLESS'),
                'name': r.get('LESSEE_NM') or '-',
                'lessee_type': (r.get('LESSEE_TP') or '').strip(),
                'address': r.get('ADDRESS1') or '-',
                'id_card': r.get('ID_CARD') or None,
                'npwp': r.get('NPWP') or None,
                'phone': r.get('PHONE1') or '-',
            }
            for r in rows
        ]
        return jsonify({'data': data, 'truncated': len(data) == _MAX_RESULTS})
    except Exception as e:
        current_app.logger.exception("Customer lookup error")
        return jsonify({'error': str(e)}), 500