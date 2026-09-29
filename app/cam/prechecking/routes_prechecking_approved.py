from flask import Blueprint, jsonify, request, session, current_app
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text
from datetime import datetime

prechecking_approved_bp = Blueprint('approved', __name__, url_prefix='/Prechecking/Approved')

def format_date(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        if value.year == 2011:
            return ""
        return value.strftime("%d-%m-%Y %H:%M:%S")
    return str(value)

@prechecking_approved_bp.route('/data')
@login_required
def get_approved():
    page       = request.args.get('page', 1, type=int)
    limit      = request.args.get('limit', 10, type=int)
    search_by  = request.args.get('search_by', '')
    search_val = request.args.get('search_val', '').strip()

    username     = session.get('username', '')
    emp_id       = session.get('emp_id', '')
    access_level = session.get('accesslevel', '')

    offset = (page - 1) * limit
    end    = offset + limit

    try:
        if search_val == '':
            result = db.session.execute(
                text("EXEC USP_CAM_REQUEST_APPROVED :username, :offset, :end, :accesslevel, :emp_id"),
                {
                    "username":    username,
                    "offset":      offset,
                    "end":         end,
                    "accesslevel": access_level,
                    "emp_id":      emp_id,
                }
            )
        elif search_by == '1':
            result = db.session.execute(
                text("EXEC USP_CAM_REQUEST_APPROVEDSEARCHBYCAM :username, :offset, :end, :search_val, :accesslevel, :emp_id"),
                {
                    "username":    username,
                    "offset":      offset,
                    "end":         end,
                    "search_val":  search_val,
                    "accesslevel": access_level,
                    "emp_id":      emp_id,
                }
            )
        else:
            result = db.session.execute(
                text("EXEC USP_CAM_REQUEST_APPROVEDSEARCHBYNM :username, :offset, :end, :search_val, :accesslevel, :emp_id"),
                {
                    "username":    username,
                    "offset":      offset,
                    "end":         end,
                    "search_val":  search_val,
                    "accesslevel": access_level,
                    "emp_id":      emp_id,
                }
            )
            
        all_rows = []
        for row in result:
            all_rows.append({
                "approved_date":  format_date(row.LastActionDate),
                "customer_no":    row.apless          or "",
                "customer_name":  row.LESSEE_NM       or "",
                "prechecking_id": row.PRECHECKING_ID  or "",
                "cmo":            row.NAMACMO         or "",
                "approver":       row.Approver        or "",
                "apless":         row.apless          or "",
                "customer_type":  "",
            })

        total     = len(all_rows)
        start     = (page - 1) * limit
        paginated = all_rows[start:start + limit]

        return jsonify({
            "data":         paginated,
            "total":        total,
            "access_level": access_level,
        })

    except Exception:
        current_app.logger.exception("CAM approved error")
        return jsonify({"data": [], "total": 0, "access_level": access_level}), 500