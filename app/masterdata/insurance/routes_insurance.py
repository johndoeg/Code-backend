from flask import Blueprint, jsonify, request, current_app
from app import db
from sqlalchemy import text

insurance_master_bp = Blueprint('insurance_master', __name__, url_prefix='/MasterData')

@insurance_master_bp.route('/api/insurance')
def get_insurance():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 25, type=int)
    search_by = request.args.get('search_by', '1')
    search_val = request.args.get('search_val', '').strip()

    try:
        if search_val == '':
            stmt = text("""
                SELECT INS_CD, INS_CO
                FROM UMFINSCD WITH (NOLOCK)
                ORDER BY INS_CO
            """)
            params = {}
        elif search_by == '1':
            stmt = text("""
                SELECT INS_CD, INS_CO
                FROM UMFINSCD WITH (NOLOCK)
                WHERE INS_CD = :search_val
                ORDER BY INS_CO
            """)
            params = {"search_val": search_val}
        else:
            stmt = text("""
                SELECT INS_CD, INS_CO
                FROM UMFINSCD WITH (NOLOCK)
                WHERE INS_CO LIKE :search_val
                ORDER BY INS_CO
            """)
            params = {"search_val": f"%{search_val}%"}

        result = db.session.execute(stmt, params)
        all_rows = [
            {"INS_CD": row.INS_CD, "INS_CO": row.INS_CO}
            for row in result
        ]

        total = len(all_rows)
        start = (page - 1) * limit
        paginated = all_rows[start:start + limit]

        return jsonify({"data": paginated, "total": total})

    except Exception:
        current_app.logger.exception("Insurance list error")
        return jsonify({"data": [], "total": 0}), 500


@insurance_master_bp.route('/api/insurance/<string:ins_cd>', methods=['DELETE'])
def delete_insurance(ins_cd: str):
   
    try:
        with db.session.begin():
            child_tables = [
                "CLFINSPRE",
                "CLFINSTPL",
                "CLFINSCLA",
                "CLFINSPA",
                "CLFINSSEAT",
                "CLFINSLR",
            ]
            for table in child_tables:
                db.session.execute(
                    text(f"DELETE FROM {table} WHERE INS_CD = :ins_cd"),
                    {"ins_cd": ins_cd},
                )

            db.session.execute(
                text("DELETE FROM UMFINSCD WHERE INS_CD = :ins_cd"),
                {"ins_cd": ins_cd},
            )

        return jsonify({"message": "Deleted successfully"}), 200

    except Exception:
        current_app.logger.exception("Insurance delete error for ins_cd=%s", ins_cd)
        return jsonify({"message": "Failed to delete"}), 500