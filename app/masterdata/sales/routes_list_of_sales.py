from flask import Blueprint, jsonify, request, current_app, send_file, session
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text
import io
import pandas as pd
from openpyxl.styles import Font
from datetime import datetime

sales_report_bp = Blueprint('sales_report', __name__, url_prefix='/MasterData')

_ACCOUNT_APPLY = """
    OUTER APPLY (
        SELECT TOP 1 b.Acc_No, b.Acc_Bank, b.Acc_BankBranch
        FROM BeneficiaryAccount b WITH(NOLOCK)
        WHERE b.BeneficiaryID = a.SALES_NO AND b.Category = 'Sales'
        ORDER BY b.[Default] DESC, b.Acc_No
    ) acct
    LEFT JOIN UMFBANK bank WITH(NOLOCK)
        ON acct.Acc_Bank = bank.Bank_Code
"""

_TAX_APPLY = """
    OUTER APPLY (
        SELECT TOP 1 d.NPWP_No
        FROM BeneficiaryTax d WITH(NOLOCK)
        WHERE d.BeneficiaryID = a.SALES_NO AND d.Category = 'Sales'
        ORDER BY d.DateStart DESC, d.NPWP_No
    ) tax
"""

@sales_report_bp.route('/branches')
@login_required
def get_branches():
    try:
        query = text("""
            SELECT BRANCH_CD, CITY, BRANCH_NAME 
            FROM UMFBRANCH WITH(NOLOCK) 
            ORDER BY BRANCH_NAME
        """)
        result = db.session.execute(query)
        branches = [
            {
                "branchCd": row.BRANCH_CD or "",
                "cityName": row.CITY or "",
                "branchName": row.BRANCH_NAME or ""
            }
            for row in result
        ]
        return jsonify(branches)
    except Exception as e:
        current_app.logger.exception("Failed to load branches")
        return jsonify([]), 500

@sales_report_bp.route('/sales-list')
@login_required
def get_sales_list():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 25, type=int)
    branch_cd = request.args.get('branch_cd', '').strip()
    
    if not branch_cd:
        return jsonify({"data": [], "total": 0})

    try:
        if branch_cd == '000':
            where_clause = "1=1"
            params = {}
        else:
            where_clause = "a.BRANCH_CD = :branch_cd"
            params = {"branch_cd": branch_cd}

        count_query = text(f"""
            SELECT COUNT(*) as total
            FROM CLFSALES a WITH(NOLOCK)
            WHERE {where_clause}
        """)
        
        count_result = db.session.execute(count_query, params)
        total = count_result.fetchone().total

        offset = (page - 1) * limit
        data_query = text(f"""
            SELECT 
                t.SALES_NO,
                t.NAME,
                t.ADDRESS,
                t.Status,
                t.Acc_No,
                t.bank_name,
                t.Acc_BankBranch,
                t.NPWP_No
            FROM (
                SELECT 
                    ROW_NUMBER() OVER(ORDER BY a.SALES_NO) as RowNr,
                    a.SALES_NO,
                    a.NAME,
                    a.ADDRESS,
                    a.Status,
                    acct.Acc_No,
                    bank.[Desc] as bank_name,
                    acct.Acc_BankBranch,
                    tax.NPWP_No
                FROM CLFSALES a WITH(NOLOCK)
                {_ACCOUNT_APPLY}
                {_TAX_APPLY}
                WHERE {where_clause}
            ) t
            WHERE t.RowNr BETWEEN :start_row AND :end_row
            ORDER BY t.SALES_NO
        """)
        
        data_params = {
            **params,
            "start_row": offset + 1,
            "end_row": offset + limit
        }
        
        result = db.session.execute(data_query, data_params)
        records = []
        start_no = offset + 1
        
        for row in result:
            status_text = "Active" if row.Status == 'A' else "Inactive"
            
            records.append({
                "no": start_no,
                "salesNo": row.SALES_NO or "",
                "name": row.NAME or "",
                "address": row.ADDRESS or "",
                "accNo": row.Acc_No or "",
                "bankName": row.bank_name or "",
                "bankBranch": row.Acc_BankBranch or "",
                "npwpNo": row.NPWP_No or "",
                "status": status_text
            })
            start_no += 1
        
        return jsonify({
            "data": records,
            "total": total
        })

    except Exception as e:
        current_app.logger.exception("Sales list report error")
        return jsonify({"data": [], "total": 0}), 500

@sales_report_bp.route('/sales-list/print')
@login_required
def print_sales_list():
    branch_cd = request.args.get('branch_cd', '').strip()
    if not branch_cd:
        return jsonify({"success": False, "message": "branch_cd is required"}), 400

    try:
        where_clause = "1=1" if branch_cd == '000' else "a.BRANCH_CD = :branch_cd"
        params = {"branch_cd": branch_cd} if branch_cd != '000' else {}

        query = text(f"""
            SELECT 
                a.SALES_NO,
                a.NAME,
                a.ADDRESS,
                a.Status,
                acct.Acc_No,
                bank.[Desc] as bank_name,
                acct.Acc_BankBranch,
                tax.NPWP_No
            FROM CLFSALES a WITH(NOLOCK)
            {_ACCOUNT_APPLY}
            {_TAX_APPLY}
            WHERE {where_clause}
            ORDER BY a.SALES_NO
        """)
        
        result = db.session.execute(query, params)
        records = []
        for i, row in enumerate(result, 1):
            status_text = "Active" if row.Status == 'A' else "Inactive"
            records.append({
                "no": i,
                "salesNo": row.SALES_NO or "",
                "name": row.NAME or "",
                "address": row.ADDRESS or "-",
                "accNo": row.Acc_No or "",
                "bankName": row.bank_name or "",
                "bankBranch": row.Acc_BankBranch or "",
                "npwpNo": row.NPWP_No or "",
                "status": status_text
            })

        return jsonify({
            "success": True,
            "printBy": session.get('username') or '',
            "records": records,
        })

    except Exception as e:
        current_app.logger.exception("Print report error")
        return jsonify({"success": False, "message": "Failed to fetch print data"}), 500

@sales_report_bp.route('/sales-list/excel')
@login_required
def export_sales_excel():
    branch_cd = request.args.get('branch_cd', '').strip()
    if not branch_cd:
        return "Branch parameter required", 400

    try:
        where_clause = "1=1" if branch_cd == '000' else "a.BRANCH_CD = :branch_cd"
        params = {"branch_cd": branch_cd} if branch_cd != '000' else {}

        query = text(f"""
            SELECT 
                a.SALES_NO,
                a.NAME,
                a.ADDRESS,
                a.Status,
                acct.Acc_No,
                bank.[Desc] as bank_name,
                acct.Acc_BankBranch,
                tax.NPWP_No
            FROM CLFSALES a WITH(NOLOCK)
            {_ACCOUNT_APPLY}
            {_TAX_APPLY}
            WHERE {where_clause}
            ORDER BY a.SALES_NO
        """)
        
        result = db.session.execute(query, params)
        records = []
        for i, row in enumerate(result, 1):
            status_text = "Active" if row.Status == 'A' else "Inactive"
            records.append({
                "No.": i,
                "Sales No.": row.SALES_NO or "",
                "Name": row.NAME or "",
                "Address": row.ADDRESS or "-",
                "Acc No.": row.Acc_No or "",
                "Bank": row.bank_name or "",
                "Bank Branch": row.Acc_BankBranch or "",
                "NPWP": row.NPWP_No or "",
                "Status": status_text
            })

        username = session.get('username') or ''
        print_date = datetime.now().strftime('%d/%m/%Y')

        df = pd.DataFrame(records)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Sales List', startrow=3)
            worksheet = writer.sheets['Sales List']
            worksheet.cell(row=1, column=1, value="List of Sales").font = Font(bold=True, size=14)
            worksheet.cell(row=2, column=1, value=f"Print By - Date : {username} - {print_date}")
        output.seek(0)
        
        branch_name = "AllBranches"
        if branch_cd != '000':
            branch_query = text("SELECT BRANCH_NAME FROM UMFBRANCH WITH(NOLOCK) WHERE BRANCH_CD = :branch_cd")
            branch_result = db.session.execute(branch_query, {"branch_cd": branch_cd})
            branch_row = branch_result.fetchone()
            if branch_row:
                branch_name = branch_row.BRANCH_NAME.replace(' ', '')
        
        filename = f"SalesList_{branch_name}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        current_app.logger.exception("Excel export error")
        return "Error exporting to Excel", 500