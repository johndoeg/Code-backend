from flask import Blueprint, jsonify, request, current_app, session
from app import db
from sqlalchemy import text

prechecking_onhand_bp = Blueprint('onhand', __name__, url_prefix='/Prechecking')

def _exec_sp(sp_name: str, params: list):
    
    placeholders = ", ".join(["?" * len(params)]) if params else ""
    param_str = ", ".join([f":p{i}" for i in range(len(params))])
    named = {f"p{i}": v for i, v in enumerate(params)}
    result = db.session.execute(
        text(f"EXEC {sp_name} {param_str}"), named
    )
    return result.fetchall()

@prechecking_onhand_bp.route('/api/onhand')
def get_onhand():
    page        = request.args.get('page', 1, type=int)
    limit       = request.args.get('limit', 25, type=int)
    search_by   = request.args.get('search_by', '').strip()
    search_val  = request.args.get('search_val', '').strip()

    emp_id      = session.get('emp_id', '')
    username    = session.get('username', '')
    accesslevel = session.get('accesslevel', '')

    offset = (page - 1) * limit
    end    = offset + limit

    order = 'CMO' if accesslevel == 'CMO' else ''
    
    try:
        if accesslevel in ('CMO', 'CMH'):
            if search_val and search_by == '1':
                sp   = 'USP_CAM_REQUEST_ONHANDSEARCHBYCAM'
                args = [emp_id, username, offset, end, order, search_val, accesslevel]
            elif search_val and search_by == '2':
                sp   = 'USP_CAM_REQUEST_ONHANDSEARCHBYNM'
                args = [emp_id, username, offset, end, order, search_val, accesslevel]
            else:
                sp   = 'USP_CAM_REQUEST_ONHAND'
                args = [emp_id, username, offset, end, order, accesslevel]

            rows = _exec_sp(sp, args)

            total = int(rows[0].TOTAL) if rows and hasattr(rows[0], 'TOTAL') else 0
            data_rows = rows[1:] if rows and hasattr(rows[0], 'TOTAL') else rows

            data = []
            for row in data_rows:
                tgl = ""
                if row.tgl:
                    try:
                        yr = row.tgl.strftime('%Y')
                        tgl = "" if yr == '2011' else row.tgl.strftime('%d-%m-%Y %H:%M:%S')
                    except Exception:
                        tgl = str(row.tgl)

                data.append({
                    "apless":          row.apless          or "",
                    "LESSEE_NM":       row.LESSEE_NM       or "",
                    "PRECHECKING_ID":  row.PRECHECKING_ID  or "",
                    "NAMACMO":         row.NAMACMO          or "",
                    "LastApprovalActionCode": row.LastApprovalActionCode or "",
                    "ApprovalActionCode":     row.ApprovalActionCode     or "",
                    "LESSEE_TP":       row.LESSEE_TP        or "",
                    "tgl":             tgl,
                })

            return jsonify({
                "data":         data,
                "total":        total,
                "page":         page,
                "limit":        limit,
                "accesslevel":  accesslevel,
                "username":     username,
            })

        elif accesslevel == 'CR':
            if search_val and search_by == '2':
                sp   = 'USP_CAM_REQUEST_ONHANDCRSEARCHBYNM'
                args = [emp_id, username, offset, end, order, search_val]
            else:
                sp   = 'USP_CAM_REQUEST_ONHANDCR'
                args = [emp_id, username, offset, end, order]

            rows = _exec_sp(sp, args)

            total     = int(rows[0].TOTAL) if rows and hasattr(rows[0], 'TOTAL') else 0
            data_rows = rows[1:] if rows and hasattr(rows[0], 'TOTAL') else rows

            data = []
            for row in data_rows:
                tgl = ""
                tgl_cek = ""
                try:
                    tgl     = row.tgl.strftime('%d-%m-%Y %H:%M:%S')     if row.tgl     else ""
                    tgl_cek = row.tgl_cek.strftime('%d-%m-%Y %H:%M:%S') if row.tgl_cek else ""
                except Exception:
                    tgl     = str(row.tgl)     if row.tgl     else ""
                    tgl_cek = str(row.tgl_cek) if row.tgl_cek else ""

                data.append({
                    "APLESS":          row.APLESS          or "",
                    "LESSEE_NM":       row.LESSEE_NM       or "",
                    "NAMACMO":         row.NAMACMO          or "",
                    "Prechecking_Id":  row.Prechecking_Id  or "",
                    "tgl":             tgl,
                    "tgl_cek":         tgl_cek,
                })

            return jsonify({
                "data":        data,
                "total":       total,
                "page":        page,
                "limit":       limit,
                "accesslevel": accesslevel,
            })

        else:
            return jsonify({"data": [], "total": 0,
                            "error": "Access level not supported"}), 403

    except Exception as e:
        current_app.logger.exception("Onhand list error")
        return jsonify({"data": [], "total": 0, "error": str(e)}), 500