from flask import Blueprint, jsonify, current_app
from app import db
from sqlalchemy import text

industry_bp = Blueprint('industry', __name__, url_prefix='/MasterData')

def build_tree(rows: list[dict], parent_code: str = '', parent_kepala: str = '') -> list[dict]:
    children = []
    for row in rows:
        row_parent = (row['parent'] or '').strip()
        row_kepala = (row['kepala'] or '').strip()

        parent_matches = row_parent == parent_code
        kepala_matches = True if parent_kepala == '' else (row_kepala == parent_kepala)

        if parent_matches and kepala_matches:
            node = {
                "code":     row['code'],
                "parent":   row['parent'] or '',
                "kepala":   row['kepala'] or '',
                "descrip":  row['descrip'] or '',
                "children": build_tree(rows, parent_code=row['code'], parent_kepala=row['kepala'])
            }
            children.append(node)

    return children

@industry_bp.route('/api/industry')
def get_industry():
    try:
        query = text("""
            SELECT
                CASE WHEN ISNULL(MLCI_Code, '') = '' THEN Header
                     ELSE MLCI_Code
                END                                                          AS code,
                ISNULL(Parent, '')                                           AS parent,
                Header                                                       AS kepala,
                CONCAT(Header, ' ', MLCI_Code, ' - ', Descrip)               AS descrip
            FROM  MstIndustry_lbpp WITH (NOLOCK)
            ORDER BY
                ISNULL(Parent, ''),
                Header,
                CASE WHEN ISNULL(MLCI_Code, '') = '' THEN Header
                     ELSE MLCI_Code
                END
        """)

        result = db.session.execute(query)

        rows = [
            {
                "code":    row.code,
                "parent":  row.parent,
                "kepala":  row.kepala,
                "descrip": row.descrip,
            }
            for row in result
        ]

        tree = build_tree(rows, parent_code='', parent_kepala='')

        return jsonify({"data": tree})

    except Exception as e:
        current_app.logger.exception("Industry tree error")
        return jsonify({"data": [], "error": str(e)}), 500