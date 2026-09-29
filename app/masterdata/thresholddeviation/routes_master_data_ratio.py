from datetime import date, datetime
from flask import Blueprint, jsonify, request, current_app, session, Response
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text
from app.utils.helpers.base_format import fmt_date, as_of_date, format_threshold, get_combo

master_data_ratio_bp = Blueprint('master_data_ratio', __name__, url_prefix='/MasterData')

@master_data_ratio_bp.route('/actual-ratio/options')
@login_required
def get_options():
   
    try:
        employee_id = session.get("emp_id", "")
        fullname = ""
        if employee_id:
            row = db.session.execute(
                text("SELECT fullname FROM APP_USRMST WITH(NOLOCK) WHERE employee_id = :emp"),
                {"emp": employee_id}
            ).fetchone()
            if row:
                fullname = row.fullname or ""

        return jsonify({
            "ratio":     get_combo("RATIO"),
            "remark":    get_combo("REMARK_THRS"),
            "threshold": get_combo("THRESHOLD"),
            "fullname":  fullname,
        })
    except Exception as e:
        current_app.logger.exception("Options error")
        return jsonify({"error": str(e)}), 500

@master_data_ratio_bp.route('/actual-ratio/ojk-threshold')
@login_required
def get_ojk_threshold():
   
    ratio    = request.args.get('ratio', '').strip()
    imp_date = request.args.get('imp_date', '').strip()

    if not ratio:
        return jsonify({"error": "ratio is required"}), 400

    try:
        if ratio != "5":
            row = db.session.execute(
                text("""
                    SELECT TOP 1
                        Id, Ratio, Implement_Date, Remark,
                        Threshold_Level_From AS ojk_from,
                        Threshold_Level_To   AS ojk_to
                    FROM MSTThreshold WITH(NOLOCK)
                    WHERE DATEDIFF(MONTH, Implement_Date, GETDATE()) >= 0
                        AND Ratio = :ratio
                    ORDER BY Implement_Date DESC
                """),
                {"ratio": ratio}
            ).fetchone()
        else:
            row = db.session.execute(
                text("""
                    SELECT TOP 1
                        Id, Ratio, Implement_Date, Remark,
                        Threshold_Level_From AS ojk_from,
                        Threshold_Level_To   AS ojk_to
                    FROM MSTThreshold WITH(NOLOCK)
                    WHERE YEAR(Implement_Date) <= YEAR(GETDATE())
                        AND Ratio = :ratio
                    ORDER BY Implement_Date DESC
                """),
                {"ratio": ratio}
            ).fetchone()

        if not row:
            return jsonify({"error": "No threshold found for this ratio"}), 404

        return jsonify({
            "id":         row.Id,
            "ratio":      row.Ratio,
            "imp_date":   fmt_date(row.Implement_Date, "%d %B %Y"),
            "remark":     row.Remark,
            "ojk_from":   row.ojk_from or "",
            "ojk_to":     row.ojk_to   or "",
        })

    except Exception as e:
        current_app.logger.exception("OJK threshold fetch error")
        return jsonify({"error": str(e)}), 500

@master_data_ratio_bp.route('/actual-ratio')
@login_required
def get_list():
   
    ratio  = request.args.get('ratio', '').strip()
    tahun  = request.args.get('tahun', '').strip()
    page   = request.args.get('page', 1,  type=int)
    limit  = request.args.get('limit', 25, type=int)

    if not ratio or not tahun:
        return jsonify({"data": [], "total": 0, "error": "ratio and tahun are required"}), 400

    try:
        where  = "a.Ratio = :ratio AND YEAR(a.As_Of) = :tahun"
        params = {"ratio": ratio, "tahun": int(tahun)}

        total = db.session.execute(
            text(f"SELECT COUNT(*) AS total FROM Ratio a WITH(NOLOCK) WHERE {where}"),
            params
        ).fetchone().total

        offset = (page - 1) * limit
        rows = db.session.execute(
            text(f"""
                SELECT
                    a.Id,
                    a.Ratio                                                       AS ratio_val,
                    j.DESC_VALUE                                                  AS ratio_desc,
                    i.DESC_VALUE                                                  AS remark_desc,
                    a.Remark                                                      AS remark_val,
                    a.As_Of,
                    CASE WHEN a.Ratio IN ('1','5')
                         THEN z.DESC_VALUE
                         ELSE CAST(a.Actual_From AS VARCHAR(20))
                    END                                                           AS actual_from,
                    CASE WHEN a.Ratio IN ('1','5')
                         THEN x.DESC_VALUE
                         ELSE CAST(a.Actual_To AS VARCHAR(20))
                    END                                                           AS actual_to,
                    CASE WHEN a.Ratio IN ('1','5')
                         THEN d.DESC_VALUE
                         ELSE CAST(a.Thresholder_Level_From AS VARCHAR(20))
                    END                                                           AS ojk_from,
                    CASE WHEN a.Ratio IN ('1','5')
                         THEN e.DESC_VALUE
                         ELSE CAST(a.Threshold_Level_To AS VARCHAR(20))
                    END                                                           AS ojk_to,
                    f.fullname                                                    AS created_by,
                    a.Created_Date,
                    g.fullname                                                    AS update_by,
                    a.Update_Date
                FROM Ratio a WITH(NOLOCK)
                    LEFT JOIN MSTCOMBO  d WITH(NOLOCK) ON d.VALUE = a.Thresholder_Level_From AND d.CAT_VALUE = 'threshold'
                    LEFT JOIN MSTCOMBO  e WITH(NOLOCK) ON e.VALUE = a.Threshold_Level_To     AND e.CAT_VALUE = 'threshold'
                    LEFT JOIN MSTCOMBO  z WITH(NOLOCK) ON z.VALUE = a.Actual_From            AND z.CAT_VALUE = 'threshold'
                    LEFT JOIN MSTCOMBO  x WITH(NOLOCK) ON x.VALUE = a.Actual_To              AND x.CAT_VALUE = 'threshold'
                    LEFT JOIN MSTCOMBO  i WITH(NOLOCK) ON i.VALUE = a.Remark                 AND i.CAT_VALUE = 'REMARK_THRS'
                    LEFT JOIN MSTCOMBO  j WITH(NOLOCK) ON j.VALUE = a.Ratio                  AND j.CAT_VALUE = 'RATIO'
                    LEFT JOIN APP_USRMST f WITH(NOLOCK) ON f.employee_id = a.Created_By
                    LEFT JOIN APP_USRMST g WITH(NOLOCK) ON g.employee_id = a.Update_By
                WHERE {where}
                ORDER BY a.As_Of DESC
                OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
            """),
            {**params, "offset": offset, "limit": limit}
        ).fetchall()

        data = []
        for r in rows:
            update_by   = r.update_by   or "-"
            update_date = fmt_date(r.Update_Date, "%d-%m-%Y") or "-"
            as_of_display = fmt_date(r.As_Of, "%B %Y")

            data.append({
                "id":                r.Id,
                "ratio":             r.ratio_val,
                "ratio_desc":        r.ratio_desc   or "",
                "as_of":             as_of_display,
                "remark":            r.remark_val,
                "remark_desc":       r.remark_desc  or "",
                "actual_display":    format_threshold(r.ratio_val, r.remark_val,
                                                       r.actual_from or "", r.actual_to or ""),
                "ojk_display":       format_threshold(r.ratio_val, r.remark_val,
                                                       r.ojk_from    or "", r.ojk_to    or ""),
                "actual_from":       r.actual_from  or "",
                "actual_to":         r.actual_to    or "",
                "ojk_from":          r.ojk_from     or "",
                "ojk_to":            r.ojk_to       or "",
                "created_by":        r.created_by   or "",
                "created_date":      fmt_date(r.Created_Date, "%d-%m-%Y"),
                "update_by":         update_by,
                "update_date":       update_date,
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

@master_data_ratio_bp.route('/actual-ratio/<int:record_id>')
@login_required
def get_one(record_id: int):
    
    try:
        row = db.session.execute(
            text("""
                SELECT
                    a.Id, a.Ratio,
                    x.DESC_VALUE                    AS ratio_name,
                    a.Remark,
                    a.As_Of,
                    a.Actual_From,
                    a.Actual_To,
                    a.Thresholder_Level_From        AS ojk_from,
                    a.Threshold_Level_To            AS ojk_to,
                    b.fullname                      AS created_by,
                    a.Created_Date
                FROM Ratio a WITH(NOLOCK)
                    LEFT JOIN APP_USRMST b WITH(NOLOCK) ON b.employee_id = a.Created_By
                    LEFT JOIN MSTCOMBO   x WITH(NOLOCK) ON x.VALUE = a.Ratio AND x.CAT_VALUE = 'RATIO'
                WHERE a.Id = :id
            """),
            {"id": record_id}
        ).fetchone()

        if not row:
            return jsonify({"error": "Record not found"}), 404

        if isinstance(row.As_Of, (datetime, date)):
            d = row.As_Of if isinstance(row.As_Of, date) else row.As_Of.date()
        else:
            d = None

        as_of_edit = ""
        if d:
            as_of_edit = str(d.year) if row.Ratio == "5" else d.strftime("%Y-%m")

        return jsonify({
            "id":           row.Id,
            "ratio":        row.Ratio,
            "ratio_name":   row.ratio_name  or "",
            "remark":       row.Remark,
            "as_of":        as_of_edit,
            "actual_from":  row.Actual_From or "",
            "actual_to":    row.Actual_To   or "",
            "ojk_from":     row.ojk_from    or "",
            "ojk_to":       row.ojk_to      or "",
            "created_by":   row.created_by  or "",
            "created_date": fmt_date(row.Created_Date, "%d-%m-%Y"),
        })

    except Exception as e:
        current_app.logger.exception("Get one error")
        return jsonify({"error": str(e)}), 500

@master_data_ratio_bp.route('/actual-ratio', methods=['POST'])
@login_required
def create():
    
    body          = request.get_json(force=True)
    ratio         = str(body.get("ratio",         "")).strip()
    remark        = str(body.get("remark",        "")).strip()
    imp_date      = str(body.get("imp_date",      "")).strip()
    actual1       = str(body.get("actual1",       "")).strip()
    actual2       = str(body.get("actual2",       "")).strip()
    ojk1          = str(body.get("ojk1",          "")).strip()
    ojk2          = str(body.get("ojk2",          "")).strip()
    employee_id   = session.get("emp_id", session.get("username", "SYSTEM"))

    if not ratio or not remark or not imp_date:
        return jsonify({"error": "Lengkapi data terlebih dahulu"}), 400

    if remark in ("1", "2"):
        if not actual1:
            return jsonify({"error": "Lengkapi data Actual dahulu"}), 400
        actual2 = None
        ojk2    = None
    elif remark == "3":
        if not actual1 or not actual2:
            return jsonify({"error": "Lengkapi data Actual dahulu"}), 400
    else:
        return jsonify({"error": "Invalid remark value"}), 400

    try:
        as_of = as_of_date(ratio, imp_date)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        db.session.execute(
            text("""
                INSERT INTO Ratio
                    (Ratio, As_Of, Remark,
                     Actual_From, Actual_To,
                     Thresholder_Level_From, Threshold_Level_To,
                     Created_By, Created_Date,
                     Update_By, Update_Date)
                VALUES
                    (:ratio, :as_of, :remark,
                     :a1, :a2,
                     :ojk1, :ojk2,
                     :emp, GETDATE(),
                     NULL, NULL)
            """),
            {
                "ratio": ratio, "as_of": as_of, "remark": remark,
                "a1": actual1,  "a2": actual2,
                "ojk1": ojk1 or None, "ojk2": ojk2 or None,
                "emp": employee_id,
            }
        )
        db.session.commit()
        return jsonify({"message": "Data berhasil disimpan"}), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Create error")
        return jsonify({"error": str(e)}), 500

@master_data_ratio_bp.route('/actual-ratio/<int:record_id>', methods=['PUT'])
@login_required
def update(record_id: int):
   
    body        = request.get_json(force=True)
    ratio       = str(body.get("ratio",   "")).strip()
    remark      = str(body.get("remark",  "")).strip()
    actual1     = str(body.get("actual1", "")).strip()
    actual2     = str(body.get("actual2", "")).strip()
    employee_id = session.get("emp_id", session.get("username", "SYSTEM"))

    if not ratio or not remark:
        return jsonify({"error": "ratio and remark are required"}), 400

    if remark in ("1", "2"):
        if not actual1:
            return jsonify({"error": "Lengkapi data Actual dahulu"}), 400
        actual2 = None
    elif remark == "3":
        if not actual1 or not actual2:
            return jsonify({"error": "Lengkapi data Actual dahulu"}), 400
    else:
        return jsonify({"error": "Invalid remark value"}), 400

    try:
        result = db.session.execute(
            text("""
                UPDATE Ratio SET
                    Actual_From = :a1,
                    Actual_To   = :a2,
                    Update_By   = :emp,
                    Update_Date = GETDATE()
                WHERE Id = :id
            """),
            {"a1": actual1, "a2": actual2, "emp": employee_id, "id": record_id}
        )
        db.session.commit()

        if result.rowcount == 0:
            return jsonify({"error": "Record not found"}), 404

        return jsonify({"message": "Data berhasil di update"})

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Update error")
        return jsonify({"error": str(e)}), 500

@master_data_ratio_bp.route('/actual-ratio/<int:record_id>', methods=['DELETE'])
@login_required
def delete(record_id: int):
    
    try:
        result = db.session.execute(
            text("DELETE FROM Ratio WHERE Id = :id"),
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

def _fetch_ratio_rows(ratio: str, tahun: str) -> list:
    rows = db.session.execute(
        text("""
            SELECT
                a.Ratio                                                       AS ratio_val,
                i.DESC_VALUE                                                  AS remark_desc,
                a.Remark                                                      AS remark_val,
                a.As_Of,
                CASE WHEN a.Ratio IN ('1','5') THEN z.DESC_VALUE ELSE CAST(a.Actual_From AS VARCHAR(20)) END AS actual_from,
                CASE WHEN a.Ratio IN ('1','5') THEN x.DESC_VALUE ELSE CAST(a.Actual_To   AS VARCHAR(20)) END AS actual_to,
                CASE WHEN a.Ratio IN ('1','5') THEN d.DESC_VALUE ELSE CAST(a.Thresholder_Level_From AS VARCHAR(20)) END AS ojk_from,
                CASE WHEN a.Ratio IN ('1','5') THEN e.DESC_VALUE ELSE CAST(a.Threshold_Level_To     AS VARCHAR(20)) END AS ojk_to,
                f.fullname AS created_by,
                a.Created_Date,
                g.fullname AS update_by,
                a.Update_Date
            FROM Ratio a WITH(NOLOCK)
                LEFT JOIN MSTCOMBO d WITH(NOLOCK) ON d.VALUE = a.Thresholder_Level_From AND d.CAT_VALUE = 'threshold'
                LEFT JOIN MSTCOMBO e WITH(NOLOCK) ON e.VALUE = a.Threshold_Level_To     AND e.CAT_VALUE = 'threshold'
                LEFT JOIN MSTCOMBO z WITH(NOLOCK) ON z.VALUE = a.Actual_From            AND z.CAT_VALUE = 'threshold'
                LEFT JOIN MSTCOMBO x WITH(NOLOCK) ON x.VALUE = a.Actual_To              AND x.CAT_VALUE = 'threshold'
                LEFT JOIN MSTCOMBO i WITH(NOLOCK) ON i.VALUE = a.Remark                 AND i.CAT_VALUE = 'REMARK_THRS'
                LEFT JOIN APP_USRMST f WITH(NOLOCK) ON f.employee_id = a.Created_By
                LEFT JOIN APP_USRMST g WITH(NOLOCK) ON g.employee_id = a.Update_By
            WHERE a.Ratio = :ratio AND YEAR(a.As_Of) = :tahun
            ORDER BY a.As_Of
        """),
        {"ratio": ratio, "tahun": int(tahun)}
    ).fetchall()

    result = []
    for r in rows:
        update_by   = r.update_by   or "-"
        update_date = fmt_date(r.Update_Date, "%d-%m-%Y") or "-"
        result.append({
            "as_of":        fmt_date(r.As_Of, "%B %Y"),
            "remark_desc":  r.remark_desc or "",
            "actual":       format_threshold(r.ratio_val, r.remark_val, r.actual_from or "", r.actual_to   or ""),
            "ojk":          format_threshold(r.ratio_val, r.remark_val, r.ojk_from    or "", r.ojk_to      or ""),
            "created_by":   r.created_by   or "",
            "created_date": fmt_date(r.Created_Date, "%d-%m-%Y"),
            "update_by":    update_by,
            "update_date":  update_date,
        })
    return result

def _ratio_title(ratio: str) -> str:
    row = db.session.execute(
        text("SELECT DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE = 'RATIO' AND VALUE = :v"),
        {"v": ratio}
    ).fetchone()
    return row.DESC_VALUE if row else ratio

@master_data_ratio_bp.route('/actual-ratio/print')
@login_required
def print_ratio():
    ratio = request.args.get('ratio', '').strip()
    tahun = request.args.get('tahun', '').strip()

    if not ratio or not tahun:
        return "ratio and tahun are required", 400

    try:
        title = _ratio_title(ratio)
        data  = _fetch_ratio_rows(ratio, tahun)
    except Exception as e:
        current_app.logger.exception("Print error")
        return str(e), 500

    rows_html = ""
    for i, r in enumerate(data, 1):
        rows_html += f"""
        <tr align='center' style='font-size:12px;'>
            <td>{i}</td><td>{r['as_of']}</td><td>{r['remark_desc']}</td>
            <td>{r['actual']}</td><td>{r['ojk']}</td>
            <td>{r['created_by']}</td><td>{r['created_date']}</td>
            <td>{r['update_by']}</td><td>{r['update_date']}</td>
        </tr>"""

    html = f"""<!DOCTYPE html><html><head>
    <style>
        body {{ font-family: Arial, sans-serif; font-size: 12px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        td, th {{ border: 1px solid #000; padding: 3px 6px; }}
        th {{ background: #e0e0e0; font-weight: bold; }}
    </style></head><body>
    <center>
        <span style='font-size:14pt; font-weight:bold;'>{title}</span><br>
        <span style='font-size:12pt;'>Period {tahun}</span>
    </center><br>
    <table>
        <tr align='center' style='font-size:12px; font-weight:bold;'>
            <td rowspan='2'>No.</td><td rowspan='2'>As of</td><td rowspan='2'>Remark</td>
            <td colspan='2'>Amount / Category</td>
            <td rowspan='2'>Create By</td><td rowspan='2'>Create Date</td>
            <td rowspan='2'>Update By</td><td rowspan='2'>Update Date</td>
        </tr>
        <tr align='center' style='font-size:12px; font-weight:bold;'>
            <td>Actual</td><td>Threshold Level (OJK)</td>
        </tr>
        {rows_html}
    </table>
    <script>window.print();</script>
    </body></html>"""

    return Response(html, mimetype="text/html")

@master_data_ratio_bp.route('/actual-ratio/export')
@login_required
def export_ratio():
    ratio = request.args.get('ratio', '').strip()
    tahun = request.args.get('tahun', '').strip()

    if not ratio or not tahun:
        return "ratio and tahun are required", 400

    try:
        title = _ratio_title(ratio)
        data  = _fetch_ratio_rows(ratio, tahun)
    except Exception as e:
        current_app.logger.exception("Export error")
        return str(e), 500

    rows_html = ""
    for i, r in enumerate(data, 1):
        rows_html += f"""
        <tr align='center' style='font-size:12px;'>
            <td>{i}</td><td>{r['as_of']}</td><td>{r['remark_desc']}</td>
            <td>{r['actual']}</td><td>{r['ojk']}</td>
            <td>{r['created_by']}</td><td>{r['created_date']}</td>
            <td>{r['update_by']}</td><td>{r['update_date']}</td>
        </tr>"""

    html = f"""<center>
    <span style='font-size:15px; font-weight:bold'>{title}</span><br>
    <span style='font-size:15px;'>Period {tahun}</span>
    </center>
    <table width='100%' border='1' cellpadding='0' cellspacing='0' style='border-collapse:collapse;'>
        <tr align='center' style='font-size:12px;'>
            <td rowspan='2'><b>No.</b></td><td rowspan='2'><b>As of</b></td><td rowspan='2'><b>Remark</b></td>
            <td colspan='2'><b>Amount / Category</b></td>
            <td rowspan='2'><b>Create By</b></td><td rowspan='2'><b>Create Date</b></td>
            <td rowspan='2'><b>Update By</b></td><td rowspan='2'><b>Update Date</b></td>
        </tr>
        <tr align='center' style='font-size:12px;'>
            <td><b>Actual</b></td><td><b>Threshold Level (OJK)</b></td>
        </tr>
        {rows_html}
    </table>"""


    filename = f"Actual Ratio.xls"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": "application/vnd.ms-excel",
    }
    
    return Response(html, headers=headers)