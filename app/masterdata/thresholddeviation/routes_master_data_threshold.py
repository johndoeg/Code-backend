from datetime import date, datetime
from flask import Blueprint, jsonify, request, current_app, session
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text
from app.utils.helpers.base_format import fmt_date, can_edit, format_threshold, get_combo

master_data_threshold_bp = Blueprint('master_data_threshold', __name__, url_prefix='/MasterData')

def _parse_imp_date(raw: str) -> str:
   
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date format: {raw!r}")

@master_data_threshold_bp.route('/ratio-threshold/options')
@login_required
def get_options():
    
    try:
        return jsonify({
            "ratio":     get_combo("RATIO"),
            "remark":    get_combo("REMARK_THRS"),
            "threshold": get_combo("THRESHOLD"),
        })
    except Exception as e:
        current_app.logger.exception("Options error")
        return jsonify({"error": str(e)}), 500

@master_data_threshold_bp.route('/ratio-threshold')
@login_required
def get_list():
   
    ratio_filter = request.args.get('ratio', '').strip()
    page  = request.args.get('page', 1,  type=int)
    limit = request.args.get('limit', 25, type=int)

    try:
        where  = "1=1"
        params: dict = {}
        if ratio_filter:
            where += " AND a.Ratio = :ratio"
            params["ratio"] = ratio_filter

        total = db.session.execute(
            text(f"SELECT COUNT(*) AS total FROM MSTThreshold a WITH(NOLOCK) WHERE {where}"),
            params
        ).fetchone().total

        offset = (page - 1) * limit
        rows = db.session.execute(
            text(f"""
                SELECT
                    a.Id,
                    a.Ratio,
                    a.Implement_Date,
                    a.Remark,
                    a.Remark                                        AS remark_val,
                    -- threshold display: ratio 1&5 resolve via combo; others stay raw
                    CASE WHEN a.Ratio IN ('1','5')
                         THEN d.DESC_VALUE
                         ELSE CAST(a.Threshold_Level_From AS VARCHAR(20))
                    END                                             AS ojk_from,
                    CASE WHEN a.Ratio IN ('1','5')
                         THEN e.DESC_VALUE
                         ELSE CAST(a.Threshold_Level_To   AS VARCHAR(20))
                    END                                             AS ojk_to,
                    x.DESC_VALUE                                    AS ratio_desc,
                    i.DESC_VALUE                                    AS remark_desc,
                    f.fullname                                      AS created_by,
                    a.Created_Date,
                    g.fullname                                      AS update_by,
                    a.Update_Date
                FROM MSTThreshold a WITH(NOLOCK)
                    LEFT JOIN MSTCOMBO  d WITH(NOLOCK) ON d.VALUE = a.Threshold_Level_From AND d.CAT_VALUE = 'threshold'
                    LEFT JOIN MSTCOMBO  e WITH(NOLOCK) ON e.VALUE = a.Threshold_Level_To   AND e.CAT_VALUE = 'threshold'
                    LEFT JOIN MSTCOMBO  i WITH(NOLOCK) ON i.VALUE = a.Remark               AND i.CAT_VALUE = 'REMARK_THRS'
                    LEFT JOIN MSTCOMBO  x WITH(NOLOCK) ON x.VALUE = a.Ratio                AND x.CAT_VALUE = 'RATIO'
                    LEFT JOIN APP_USRMST f WITH(NOLOCK) ON f.employee_id = a.Created_By
                    LEFT JOIN APP_USRMST g WITH(NOLOCK) ON g.employee_id = a.Update_By
                WHERE {where}
                ORDER BY a.Implement_Date DESC
                OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
            """),
            {**params, "offset": offset, "limit": limit}
        ).fetchall()

        data = []
        for r in rows:
            update_by   = r.update_by   or "-"
            update_date = fmt_date(r.Update_Date) or "-"

            data.append({
                "id":            r.Id,
                "ratio":         r.Ratio,
                "ratio_desc":    r.ratio_desc   or "",
                "imp_date":      fmt_date(r.Implement_Date),
                "remark":        r.Remark,
                "remark_desc":   r.remark_desc  or "",
                "threshold_display": format_threshold(
                    r.Ratio, r.remark_val,
                    r.ojk_from or "", r.ojk_to or ""
                ),
                "threshold1":    r.ojk_from or "",
                "threshold2":    r.ojk_to   or "",
                "created_by":    r.created_by   or "",
                "created_date":  fmt_date(r.Created_Date),
                "update_by":     update_by,
                "update_date":   update_date,
                "can_edit":      can_edit(r.Implement_Date),
            })

        return jsonify({
            "data":  data,
            "total": total,
            "page":  page,
            "limit": limit,
        })

    except Exception as e:
        current_app.logger.exception("List error")
        return jsonify({"data": [], "total": 0, "error": str(e)}), 500

@master_data_threshold_bp.route('/ratio-threshold/<int:record_id>')
@login_required
def get_one(record_id: int):
   
    try:
        row = db.session.execute(
            text("""
                SELECT
                    Id,
                    Ratio,
                    Implement_Date,
                    Remark,
                    Threshold_Level_From    AS ojk_from,
                    Threshold_Level_To      AS ojk_to
                FROM MSTThreshold WITH(NOLOCK)
                WHERE Id = :id
            """),
            {"id": record_id}
        ).fetchone()

        if not row:
            return jsonify({"error": "Record not found"}), 404

        return jsonify({
            "id":         row.Id,
            "ratio":      row.Ratio,
            "imp_date":   fmt_date(row.Implement_Date, "%Y-%m-%d"),
            "remark":     row.Remark,
            "threshold1": row.ojk_from or "",
            "threshold2": row.ojk_to   or "",
        })

    except Exception as e:
        current_app.logger.exception("Get one error")
        return jsonify({"error": str(e)}), 500

@master_data_threshold_bp.route('/ratio-threshold', methods=['POST'])
@login_required
def create():
    
    body       = request.get_json(force=True)
    ratio      = str(body.get("ratio",      "")).strip()
    remark     = str(body.get("remark",     "")).strip()
    imp_date   = str(body.get("imp_date",   "")).strip()
    threshold1 = str(body.get("threshold1", "")).strip()
    threshold2 = str(body.get("threshold2", "")).strip()
    employee_id = session.get("emp_id", session.get("username", "SYSTEM"))

    if not ratio or not remark or not imp_date:
        return jsonify({"error": "Lengkapi data terlebih dahulu"}), 400

    if remark in ("1", "2"):
        if not threshold1:
            return jsonify({"error": "Lengkapi data Threshold dahulu"}), 400
        threshold2 = None
    elif remark == "3":
        if not threshold1 or not threshold2:
            return jsonify({"error": "Lengkapi data Threshold dahulu"}), 400
    else:
        return jsonify({"error": "Invalid remark value"}), 400

    try:
        imp_date_sql = _parse_imp_date(imp_date)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        db.session.execute(
            text("""
                INSERT INTO MSTThreshold
                    (Ratio, Implement_Date, Remark,
                     Threshold_Level_From, Threshold_Level_To,
                     Created_By, Created_Date)
                VALUES
                    (:ratio, :imp_date, :remark,
                     :t1, :t2,
                     :emp, GETDATE())
            """),
            {
                "ratio":    ratio,
                "imp_date": imp_date_sql,
                "remark":   remark,
                "t1":       threshold1,
                "t2":       threshold2,
                "emp":      employee_id,
            }
        )
        db.session.commit()
        return jsonify({"message": "Data berhasil disimpan"}), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Create error")
        return jsonify({"error": str(e)}), 500

@master_data_threshold_bp.route('/ratio-threshold/<int:record_id>', methods=['PUT'])
@login_required
def update(record_id: int):
   
    body        = request.get_json(force=True)
    ratio       = str(body.get("ratio",      "")).strip()
    remark      = str(body.get("remark",     "")).strip()
    imp_date    = str(body.get("imp_date",   "")).strip()
    threshold1  = str(body.get("threshold1", "")).strip()
    threshold2  = str(body.get("threshold2", "")).strip()
    employee_id = session.get("emp_id", session.get("username", "SYSTEM"))

    if not ratio or not remark or not imp_date:
        return jsonify({"error": "Lengkapi data terlebih dahulu"}), 400

    if remark in ("1", "2"):
        if not threshold1:
            return jsonify({"error": "Lengkapi data Threshold dahulu"}), 400
    elif remark == "3":
        if not threshold1 or not threshold2:
            return jsonify({"error": "Lengkapi data Threshold dahulu"}), 400
    else:
        return jsonify({"error": "Invalid remark value"}), 400

    try:
        imp_date_sql = _parse_imp_date(imp_date)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        if remark in ("1", "2"):
            sql = """
                UPDATE MSTThreshold SET
                    Ratio                = :ratio,
                    Implement_Date       = :imp_date,
                    Remark               = :remark,
                    Threshold_Level_From = :t1,
                    Update_By            = :emp,
                    Update_Date          = GETDATE()
                WHERE Id = :id
            """
            params = {
                "ratio": ratio, "imp_date": imp_date_sql,
                "remark": remark, "t1": threshold1,
                "emp": employee_id, "id": record_id,
            }
        else:
            sql = """
                UPDATE MSTThreshold SET
                    Ratio                = :ratio,
                    Implement_Date       = :imp_date,
                    Remark               = :remark,
                    Threshold_Level_From = :t1,
                    Threshold_Level_To   = :t2,
                    Update_By            = :emp,
                    Update_Date          = GETDATE()
                WHERE Id = :id
            """
            params = {
                "ratio": ratio, "imp_date": imp_date_sql,
                "remark": remark, "t1": threshold1, "t2": threshold2,
                "emp": employee_id, "id": record_id,
            }

        result = db.session.execute(text(sql), params)
        db.session.commit()

        if result.rowcount == 0:
            return jsonify({"error": "Record not found"}), 404

        return jsonify({"message": "Data berhasil di update"})

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Update error")
        return jsonify({"error": str(e)}), 500

@master_data_threshold_bp.route('/ratio-threshold/<int:record_id>', methods=['DELETE'])
@login_required
def delete(record_id: int):

    try:
        result = db.session.execute(
            text("DELETE FROM MSTThreshold WHERE Id = :id"),
            {"id": record_id}
        )
        db.session.commit()

        if result.rowcount == 0:
            return jsonify({"error": "Record not found"}), 404

        return jsonify({"message": "Deleted successfully"})

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Delete error")
        return jsonify({"error": str(e)}), 500