from flask import Blueprint, jsonify, request, current_app, session
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text

prechecking_rejected_bp = Blueprint('prechecking_rejected', __name__, url_prefix='/Prechecking/Rejected')

@prechecking_rejected_bp.route('/data')
@login_required
def get_rejected():
    
    page       = request.args.get('page', 1, type=int)
    limit      = request.args.get('limit', 25, type=int)
    search_by  = request.args.get('search_by', '').strip()
    search_val = request.args.get('search_val', '').strip()

    try:
       
        if search_val and search_by == '1':
            where_clause = "a.Apless = :search_val"
            params: dict = {"search_val": search_val}
        elif search_val and search_by == '2':
            where_clause = "a.LesseeName LIKE :search_val"
            params = {"search_val": f"%{search_val}%"}
        else:
            where_clause = "DATEDIFF(d, b.LastActionDate, GETDATE()) <= 30"
            params = {}
            
        base_query = f"""
            FROM TEMP_CAFLESS a WITH(NOLOCK)
                INNER JOIN documentApproval b WITH(NOLOCK) ON a.Prechecking_Id = b.DocumentNumber
                LEFT JOIN documentApprovalHistory c WITH(NOLOCK)
                    ON  b.Id = c.DocumentApprovalId
                    AND c.ApprovalActionCode = 'reject'
                    AND c.Id = (
                        SELECT MAX(Id)
                        FROM documentApprovalHistory WITH(NOLOCK)
                        WHERE DocumentApprovalId = b.Id
                        AND ApprovalActionCode = 'reject'
                    )
            WHERE a.FINAL_APLESS IS NULL
            AND b.LastApprovalActionCode IN ('draft', 'withdraw', 'reject')
            AND c.ApprovalActionCode = 'reject'
            AND {where_clause}
        """

        count_result = db.session.execute(
            text(f"SELECT COUNT(*) as total {base_query}"), params
        ).fetchone()
        total = count_result.total

        offset = (page - 1) * limit
        result = db.session.execute(text(f"""
            SELECT
                a.Prechecking_Id,
                a.Apless,
                a.LesseeName,
                a.CreatedBy,
                c.CreatedBy       AS Rejected_By,
                c.CreatedDate     AS Rejected_Date
            {base_query}
            ORDER BY b.LastActionDate DESC
            OFFSET :offset ROWS
            FETCH NEXT :limit ROWS ONLY
        """), {**params, "offset": offset, "limit": limit}).fetchall()

        data = []
        for row in result:
            rejected_date = ""
            if row.Rejected_Date:
                try:
                    rejected_date = row.Rejected_Date.strftime('%d-%m-%Y %H:%M:%S')
                except Exception:
                    rejected_date = str(row.Rejected_Date)

            data.append({
                "Prechecking_Id": row.Prechecking_Id or "",
                "Apless":         row.Apless         or "",
                "LesseeName":     row.LesseeName      or "",
                "CreatedBy":      row.CreatedBy       or "",
                "Rejected_By":    row.Rejected_By     or "",
                "Rejected_Date":  rejected_date,
            })

        return jsonify({
            "data":  data,
            "total": total,
            "page":  page,
            "limit": limit,
        })

    except Exception as e:
        current_app.logger.exception("Prechecking rejected list error")
        return jsonify({"data": [], "total": 0, "error": str(e)}), 500