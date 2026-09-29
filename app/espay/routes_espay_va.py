from flask import Blueprint, request, jsonify, current_app
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text

va_bp = Blueprint('va', __name__, url_prefix='/va')

@va_bp.route('/search', methods=['GET'])
@login_required
def search_va_records():
    lease_no = request.args.get('lease_no', '').strip()
    search_by = request.args.get('search_by', '1').strip()

    if not lease_no:
        return jsonify([])

    if search_by not in ('1', '2'):
        return jsonify({"error": "Invalid search_by parameter"}), 400

    try:
        if search_by == '1':
            query = text("""
                SELECT b.Bank_Name, a.va_number, a.lease_no 
                FROM ESPAY_Generate_VA a WITH(NOLOCK)
                    INNER JOIN ESPAY_Master_VA b WITH(NOLOCK) ON a.bank_code = b.Bank_Code 
                WHERE a.lease_no = :lease_no
            """)
            params = {"lease_no": lease_no}
        else:
            query = text("""
                SELECT b.Bank_Name, a.va_number, a.lease_no 
                FROM ESPAY_Generate_VA a WITH(NOLOCK)
                    INNER JOIN ESPAY_Master_VA b WITH(NOLOCK) ON a.bank_code = b.Bank_Code 
                WHERE a.va_number = :va_number
            """)
            params = {"va_number": lease_no}

        result = db.session.execute(query, params)
        records = []
        
        for row in result:
            records.append({
                "Bank": getattr(row, 'Bank_Name', '') or "",
                "VA_No": getattr(row, 'va_number', '') or "",
                "Lease_No": getattr(row, 'lease_no', '') or ""
            })
        
        return jsonify(records)

    except Exception as e:
        current_app.logger.exception("VA search error")
        return jsonify([]), 500

@va_bp.route('/search-options')
@login_required
def get_search_options():
    try:
        query = text("""
            SELECT VALUE, DESC_VALUE 
            FROM MSTCOMBO WITH(NOLOCK) 
            WHERE CAT_VALUE = 'SEARCH_VA'
            ORDER BY VALUE
        """)
        result = db.session.execute(query)
        options = []
        for row in result:
            options.append({
                "value": str(getattr(row, 'VALUE', '')),
                "descValue": str(getattr(row, 'DESC_VALUE', ''))
            })
        
        return jsonify(options)
        
    except Exception as e:
        current_app.logger.exception("Failed to load search options")
        return jsonify([
            {"value": "1", "descValue": "Lease Number"},
            {"value": "2", "descValue": "VA Number"}
        ]), 200