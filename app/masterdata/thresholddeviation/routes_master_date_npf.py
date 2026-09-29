from datetime import date, datetime
from flask import Blueprint, jsonify, request, current_app, session
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text
from app.utils.helpers.base_format import fmt_date, get_combo

master_data_npf_bp = Blueprint('master_data_npf', __name__, url_prefix='/MasterData')

@master_data_npf_bp.route('/npf-range/options')
@login_required
def get_options():
    try:
        all_threshold = get_combo("THRESHOLD")
        threshold = [opt for opt in all_threshold if opt["value"] != "5"]
        return jsonify({"threshold": threshold})
    except Exception as e:
        current_app.logger.exception("Options error")
        return jsonify({"error": str(e)}), 500

@master_data_npf_bp.route('/npf-range/list')
@login_required
def get_list():
    try:
        rows = db.session.execute(
            text("""
                SELECT
                    xx.Id,
                    xx.Implement_Date,
                    xx.Actual,
                    ss.DESC_VALUE AS actual_desc,
                    xx.Npf_Range_From,
                    xx.Npf_Range_To,
                    xx.Multiguna,
                    xx.Investasi
                FROM mstrange xx
                    LEFT JOIN MSTCOMBO ss
                        ON ss.VALUE = xx.Actual AND ss.CAT_VALUE = 'THRESHOLD'
                ORDER BY xx.Created_Date
            """)
        ).fetchall()

        today = date.today()

        data = []
        for r in rows:
            imp_date_only = r.Implement_Date.date() if isinstance(r.Implement_Date, datetime) else r.Implement_Date
            can_edit = not (today > imp_date_only)

            data.append({
                "id": r.Id,
                "imp_date": fmt_date(r.Implement_Date, "%d %b %Y"),
                "imp_date_raw": fmt_date(r.Implement_Date, "%Y-%m-%d"),
                "actual": str(r.Actual) if r.Actual is not None else "",
                "actual_desc": r.actual_desc or "",
                "rangefrom": r.Npf_Range_From,
                "rangeto": r.Npf_Range_To,
                "multiguna": r.Multiguna,
                "investasi": r.Investasi,
                "can_edit": can_edit,
            })

        return jsonify(data)
    except Exception as e:
        current_app.logger.exception("List error")
        return jsonify({"error": str(e)}), 500

@master_data_npf_bp.route('/npf-range/last-update')
@login_required
def get_last_update():
    try:
        row = db.session.execute(
            text("""
                SELECT TOP 1
                    CASE WHEN xx.Update_By <> '' THEN xx.Update_Date ELSE xx.Created_Date END AS Created_Date,
                    CASE WHEN xx.Update_By <> '' THEN dd.fullname ELSE cc.fullname END AS fullname
                FROM mstrange xx
                    LEFT JOIN APP_USRMST cc WITH(NOLOCK) ON cc.employee_id = xx.Created_By
                    LEFT JOIN APP_USRMST dd WITH(NOLOCK) ON dd.employee_id = xx.Update_By
                ORDER BY xx.Created_Date DESC
            """)
        ).fetchone()

        if not row:
            return jsonify({"fullname": "", "update_date": ""})

        return jsonify({
            "fullname": row.fullname or "",
            "update_date": fmt_date(row.Created_Date, "%d %b %Y") if row.Created_Date else "",
        })
    except Exception as e:
        current_app.logger.exception("Last update error")
        return jsonify({"error": str(e)}), 500

@master_data_npf_bp.route('/npf-range/<int:id>', methods=['GET'])
@login_required
def get_one(id):
    try:
        row = db.session.execute(
            text("""
                SELECT Id, Implement_Date, Actual,
                       Npf_Range_From AS rangefrom,
                       Npf_Range_To AS rangeto,
                       Multiguna AS multi,
                       Investasi AS inves
                FROM mstrange
                WHERE Id = :id
            """),
            {"id": id}
        ).fetchone()

        if not row:
            return jsonify({"error": "Record not found"}), 404

        return jsonify({
            "id": row.Id,
            "imp_date": fmt_date(row.Implement_Date, "%Y-%m-%d"),
            "threshold": str(row.Actual) if row.Actual is not None else "",
            "rangefrom": row.rangefrom,
            "rangeto": row.rangeto,
            "multiguna": row.multi,
            "investasi": row.inves,
        })
    except Exception as e:
        current_app.logger.exception("Get one error")
        return jsonify({"error": str(e)}), 500

@master_data_npf_bp.route('/npf-range', methods=['POST'])
@login_required
def create_range():
    try:
        data = request.get_json()
        emp_id = session.get("emp_id", "")

        required = ["imp_date", "threshold", "rangefrom", "rangeto", "multi", "inves"]
        if not all(data.get(f) not in (None, "") for f in required):
            return jsonify({"error": "Lengkapi data terlebih dahulu"}), 400

        db.session.execute(
            text("""
                INSERT INTO [dbo].[MSTRange]
                    ([Implement_Date]
                    ,[Actual]
                    ,[Npf_Range_From]
                    ,[Npf_Range_To]
                    ,[Multiguna]
                    ,[Investasi]
                    ,[Created_By]
                    ,[Created_Date]
                    ,[Update_By]
                    ,[Update_Date])
                VALUES
                    (:imp_date, :threshold, :rangefrom, :rangeto, :multi, :inves, :emp_id, GETDATE(), NULL, NULL)
            """),
            {
                "imp_date": data["imp_date"],
                "threshold": data["threshold"],
                "rangefrom": data["rangefrom"],
                "rangeto": data["rangeto"],
                "multi": data["multi"],
                "inves": data["inves"],
                "emp_id": emp_id,
            }
        )
        db.session.commit()
        return jsonify({"message": "success"})
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Create error")
        return jsonify({"error": str(e)}), 500

@master_data_npf_bp.route('/npf-range/<int:id>', methods=['PUT'])
@login_required
def update_range(id):
    try:
        data = request.get_json()
        emp_id = session.get("emp_id", "")

        required = ["imp_date", "threshold", "rangefrom", "rangeto", "multi", "inves"]
        if not all(data.get(f) not in (None, "") for f in required):
            return jsonify({"error": "Lengkapi data terlebih dahulu"}), 400

        result = db.session.execute(
            text("""
                UPDATE [dbo].[MSTRange]
                SET [Implement_Date] = :imp_date
                    ,[Actual] = :threshold
                    ,[Npf_Range_From] = :rangefrom
                    ,[Npf_Range_To] = :rangeto
                    ,[Multiguna] = :multi
                    ,[Investasi] = :inves
                    ,[Update_By] = :emp_id
                    ,[Update_Date] = GETDATE()
                WHERE Id = :id
            """),
            {
                "imp_date": data["imp_date"],
                "threshold": data["threshold"],
                "rangefrom": data["rangefrom"],
                "rangeto": data["rangeto"],
                "multi": data["multi"],
                "inves": data["inves"],
                "emp_id": emp_id,
                "id": id,
            }
        )

        if result.rowcount == 0:
            db.session.rollback()
            return jsonify({"error": "Record not found"}), 404

        db.session.commit()
        return jsonify({"message": "success"})
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Update error")
        return jsonify({"error": str(e)}), 500

@master_data_npf_bp.route('/npf-range/<int:id>', methods=['DELETE'])
@login_required
def delete_range(id):
    try:
        result = db.session.execute(
            text("DELETE FROM MSTRange WHERE Id = :id"),
            {"id": id}
        )

        if result.rowcount == 0:
            db.session.rollback()
            return jsonify({"error": "Record not found"}), 404

        db.session.commit()
        return jsonify({"message": "success"})
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Delete error")
        return jsonify({"error": str(e)}), 500