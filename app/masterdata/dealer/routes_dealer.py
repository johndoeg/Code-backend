from flask import Blueprint, jsonify, request, current_app, session
from app import db
from sqlalchemy import text

dealer_bp = Blueprint('dealer', __name__, url_prefix='/MasterData')

@dealer_bp.route('/api/dealer')
def get_dealer():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 25, type=int)
    search_val = request.args.get('search_val', '').strip()
    search_by = request.args.get('search_by', '').strip()

    try:
        where_clause = "1=1" 
        if search_val:
            if search_by == '1':
                where_clause = "SUPP = :search_val"
            elif search_by == '2':
                where_clause = "[NAME] LIKE :search_val"
                search_val = f"%{search_val}%"
            elif search_by == '3':
                where_clause = "NICKNAME LIKE :search_val"
            else:
                where_clause = "SUPP = :search_val OR [NAME] LIKE :search_val OR NICKNAME LIKE :search_val"
                search_val = f"%{search_val}%"
        else:
            where_clause = "1=1"

        count_query = text(f"""
            SELECT COUNT(*) as total 
            FROM CLFSUPP WITH(NOLOCK) 
            WHERE {where_clause}
        """)
        
        count_params = {"search_val": search_val} if search_val else {}
        count_result = db.session.execute(count_query, count_params)
        total = count_result.fetchone().total

        offset = (page - 1) * limit
        data_query = text(f"""
            SELECT 
                SUPP, 
                [NAME], 
                NICKNAME, 
                ADDRESS
            FROM CLFSUPP WITH(NOLOCK) 
            WHERE {where_clause}
            ORDER BY SUPP
            OFFSET :offset ROWS 
            FETCH NEXT :limit ROWS ONLY
        """)
        
        data_params = {
            **count_params,
            "offset": offset,
            "limit": limit
        }
        
        result = db.session.execute(data_query, data_params)
        dealer_data = []
        
        for row in result:

            dealer_data.append({
                "SUPP": row.SUPP or "",
                "NAME": row.NAME or "",
                "NICKNAME": row.NICKNAME or "",
                "ADDRESS": row.ADDRESS or "",
            })
        
        return jsonify({
            "data": dealer_data,
            "total": total,
            "page": page,
            "limit": limit,
            "akses": "9"
        })

    except Exception as e:
        current_app.logger.exception("Dealer list error")
        return jsonify({"data": [], "total": 0, "error": str(e)}), 500
