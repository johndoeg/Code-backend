from flask import Blueprint, jsonify, request, current_app, session
from app import db
from sqlalchemy import text
from datetime import datetime

cam_onhand_bp = Blueprint('camonhand', __name__, url_prefix='/CAM')

@cam_onhand_bp.route('/api/onprocess/on-hand', methods=['GET'])
def get_cam_on_hand():
    try:
        page = max(1, request.args.get('page', 1, type=int))
        limit = min(100, max(1, request.args.get('limit', 25, type=int)))
        offset = (page - 1) * limit
        
        search_by = request.args.get('search_by', '1')
        search_val = request.args.get('search_val', '').strip()
        
        emp_id = session.get('emp_id')
        username = session.get('username')
        accesslevel = session.get('accesslevel')
        branch_cd = session.get('branchcode')
        
        if not emp_id or not username:
            return jsonify({"success": False, "message": "Unauthorized"}), 401
        
        if accesslevel == "CMO":
            order_clause = "ORDER BY tgl DESC, APPL_NO DESC"
        else:
            order_clause = "ORDER BY tgl ASC, APPL_NO ASC"
        
        if not search_val:
            count_query = text("""
                EXEC USP_CAM_ONHAND 
                    :emp_id, 
                    :username, 
                    0,
                    0,
                    :order
            """)
            data_query = text("""
                EXEC USP_CAM_ONHAND 
                    :emp_id, 
                    :username, 
                    :offset, 
                    :limit, 
                    :order
            """)
            params = {
                "emp_id": emp_id,
                "username": username,
                "offset": offset,
                "limit": limit,
                "order": order_clause,
            }
        elif search_by == '1':
            count_query = text("""
                EXEC USP_CAM_ONHANDSEARCHBYCAM 
                    :emp_id, 
                    :username, 
                    0, 0, 
                    :order, 
                    :search_val
            """)
            data_query = text("""
                EXEC USP_CAM_ONHANDSEARCHBYCAM 
                    :emp_id, 
                    :username, 
                    :offset, 
                    :limit, 
                    :order, 
                    :search_val
            """)
            params = {
                "emp_id": emp_id,
                "username": username,
                "offset": offset,
                "limit": limit,
                "order": order_clause,
                "search_val": f"%{search_val}%",
            }
        elif search_by == '2':
            count_query = text("""
                EXEC USP_CAM_ONHANDSEARCHBYNM 
                    :emp_id, 
                    :username, 
                    0, 0, 
                    :order, 
                    :search_val
            """)
            data_query = text("""
                EXEC USP_CAM_ONHANDSEARCHBYNM 
                    :emp_id, 
                    :username, 
                    :offset, 
                    :limit, 
                    :order, 
                    :search_val
            """)
            params = {
                "emp_id": emp_id,
                "username": username,
                "offset": offset,
                "limit": limit,
                "order": order_clause,
                "search_val": f"%{search_val}%",
            }
        else:
            return jsonify({"success": False, "message": "Invalid search parameter"}), 400
        
        count_result = db.session.execute(count_query, params).fetchone()
        total = count_result.TOTAL if count_result and hasattr(count_result, 'TOTAL') else 0
        
        result = db.session.execute(data_query, params)
        records = []
        
        for row in result:
            status_color = "#000000" 
            status_label = row.NAMACMO or ""
            
            if row.str_revisi:
                status_color = "#009900"
                status_label = f"{status_label} (Revised)" if status_label else "Revised"
            elif row.NAMACMO == "Reject":
                status_color = "#FF00FF"
                status_label = f"Rejected"
            
            can_edit = False
            can_delete = False
            can_reject = False
            can_send = False
            
            if accesslevel == "CMO":
                if row.NAMACMO in ["NAMACMO", "Reject", None]:
                    can_edit = True
                    can_delete = True
                    can_reject = True
                can_send = True
            elif accesslevel == "CRH":
                if row.cbgnow != "CO":
                    can_send = True
                if row.Picked_by and row.Picked_by == emp_id:
                    can_send = True
            
            records.append({
                "APPL_NO": row.APPL_NO or "",
                "APLESS": row.apless or "",
                "Cons_Leas": row.Cons_Leas or "",
                
                # "LESSEE_NM": row.LESSEE_NM or "",
                
                "NAMACMO": row.NAMACMO or "",
                "status_color": status_color,
                "status_label": status_label,
                "tgl": row.tgl,
                "str_revisi": row.str_revisi or "",
                "str_multiple": row.str_multiple or "",
                
                "brch_code": row.brch_code or "",
                "cbgnow": row.cbgnow or "",
                "CMOnow": row.CMOnow or "",
                
                "guarantor": row.guarantor or "",
                "fin_type": row.fin_type or "",
                "tenor": row.tenor or "",
                "ind_cor": row.ind_cor or "",
                "c2c": row.c2c or "",
                # "purpoffinc": row.purpoffinc or "",
                # "conttype": row.conttype or "",
                "new_car": row.new_car or "",
                
                # "r_change": row.r_change or "",
                # "publicgo": row.publicgo or "",
                
                "can_edit": can_edit,
                "can_delete": can_delete,
                "can_reject": can_reject,
                "can_send": can_send,
                
                # "is_picked": bool(row.Picked_by and row.Picked_by == emp_id),
                # "tot_outs": float(row.tot_outs or 0),
            })
        
        return jsonify({
            "success": True,
            "data": records,
            "meta": {
                "current_page": page,
                "total_pages": (total + limit - 1) // limit if limit > 0 else 1,
                "total_items": total,
                "items_per_page": limit,
            }
        })
        
    except Exception as e:
        current_app.logger.exception(f"Failed to fetch CAM on hand: {e}")
        return jsonify({
            "success": False, 
            "message": "Failed to load CAM records. Please try again."
        }), 500