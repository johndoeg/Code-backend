from flask import Blueprint, jsonify, request, current_app, send_file
from app import db
from sqlalchemy import text
import io
import pandas as pd
from datetime import datetime

dealer_report_bp = Blueprint('dealer_report', __name__, url_prefix='/MasterData')

@dealer_report_bp.route('/api/branches')
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
    
@dealer_report_bp.route('/api/dealer-list')
def get_dealer_list():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 25, type=int)
    branch_cd = request.args.get('branch_cd', '').strip()
    
    if not branch_cd:
        return jsonify({"data": [], "total": 0})

    try:
        where_clause = ""
        params = {}
        if branch_cd == '000':
            where_clause = "1=1"
        else:
            where_clause = "a.BRANCH_CD = :branch_cd"
            params["branch_cd"] = branch_cd

        count_query = text(f"""
            SELECT COUNT(*) as total
            FROM CLFSUPP a WITH(NOLOCK)
            LEFT JOIN BeneficiaryAccount b WITH(NOLOCK) 
                ON a.SUPP = b.BeneficiaryID AND b.Category = 'Dealer'
            LEFT JOIN BeneficiaryTax d WITH(NOLOCK) 
                ON a.SUPP = d.BeneficiaryID AND d.Category = 'Dealer'
            WHERE {where_clause}
        """)
        
        count_result = db.session.execute(count_query, params)
        total = count_result.fetchone().total

        offset = (page - 1) * limit

        data_query = text(f"""
            SELECT 
                t.NAME,
                t.NICKNAME,
                t.ADDRESS,
                t.CITY,
                t.PHONE,
                t.CONTACT,
                t.POSITION,
                t.Acc_NO,
                t.Acc_BankBranch,
                t.[DESC]
            FROM (
                SELECT 
                    ROW_NUMBER() OVER(ORDER BY a.NAME) as RowNr,
                    a.NAME,
                    a.NICKNAME,
                    a.ADDRESS,
                    a.CITY,
                    b.PHONE,
                    a.CONTACT,
                    b.POSITION,
                    c.Acc_NO,         -- ← comma was missing here
                    c.Acc_BankBranch, -- ← comma was missing here
                    b.[DESC]
                FROM CLFSUPP a WITH(NOLOCK)
                    LEFT JOIN BeneficiaryAccount b WITH(NOLOCK) 
                        ON a.SUPP = b.BeneficiaryID AND b.Category = 'Dealer' AND AccountType = 'D'
                    LEFT JOIN UMFBANK c WITH(NOLOCK) 
                        ON b.Acc_Bank = c.Bank_Code
                WHERE {where_clause}
            ) t
            WHERE t.RowNr BETWEEN :start_row AND :end_row
            ORDER BY t.NAME
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
                "name": row.NAME or "",
                "nickname": row.NICKNAME or "",
                "address": row.ADDRESS or "",
                "city": row.CITY or "",
                "phone": row.PHONE or "",
                "contact": row.CONTACT or "",
                "position": row.POSITION or "",
                "accNo": row.Acc_NO or "",
                "bankBranch": row.Acc_BankBranch or "",
                "bankDesc": row.DESC or "",
                "status": status_text,
            })
            start_no += 1
        
        return jsonify({
            "data": records,
            "total": total
        })

    except Exception as e:
        current_app.logger.exception("Dealer list report error")
        return jsonify({"data": [], "total": 0}), 500

@dealer_report_bp.route('/api/sales-list/print')
def print_sales_list():
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
                b.Acc_No,
                c.[Desc] as bank_name,
                b.Acc_BankBranch,
                d.NPWP_No
            FROM CLFSUPP a WITH(NOLOCK)
            LEFT JOIN BeneficiaryAccount b WITH(NOLOCK) 
                ON a.sales_no = b.BeneficiaryID AND b.Category = 'Sales'
            LEFT JOIN UMFBANK c WITH(NOLOCK) 
                ON b.Acc_Bank = c.Bank_Code
            LEFT JOIN BeneficiaryTax d WITH(NOLOCK) 
                ON a.sales_no = d.BeneficiaryID AND d.Category = 'Sales'
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
                "accNo": row.Acc_No or "-",
                "bankName": row.bank_name or "-",
                "bankBranch": row.Acc_BankBranch or "-",
                "npwpNo": row.NPWP_No or "-",
                "status": status_text
            })

        branch_name = "All Branches"
        if branch_cd != '000':
            branch_query = text("SELECT BRANCH_NAME FROM UMFBRANCH WITH(NOLOCK) WHERE BRANCH_CD = :branch_cd")
            branch_result = db.session.execute(branch_query, {"branch_cd": branch_cd})
            branch_row = branch_result.fetchone()
            if branch_row:
                branch_name = branch_row.BRANCH_NAME

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Sales List Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ text-align: center; margin-bottom: 30px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid #000; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .status-active {{ color: green; }}
                .status-inactive {{ color: red; }}
            </style>
        </head>
        <body>
            <h1>List of Sales - {branch_name}</h1>
            <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <table>
                <thead>
                    <tr>
                        <th>No.</th>
                        <th>Sales No.</th>
                        <th>Name</th>
                        <th>Address</th>
                        <th>Acc No.</th>
                        <th>Bank</th>
                        <th>Bank Branch</th>
                        <th>NPWP</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(f'''
                    <tr>
                        <td>{r['no']}</td>
                        <td>{r['salesNo']}</td>
                        <td>{r['name']}</td>
                        <td>{r['address']}</td>
                        <td>{r['accNo']}</td>
                        <td>{r['bankName']}</td>
                        <td>{r['bankBranch']}</td>
                        <td>{r['npwpNo']}</td>
                        <td class="{'status-active' if r['status'] == 'Active' else 'status-inactive'}">{r['status']}</td>
                    </tr>''' for r in records)}
                </tbody>
            </table>
        </body>
        </html>
        """
        
    except Exception as e:
        current_app.logger.exception("Print report error")
        return "Error generating report", 500

@dealer_report_bp.route('/api/sales-list/excel')
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
                b.Acc_No,
                c.[Desc] as bank_name,
                b.Acc_BankBranch,
                d.NPWP_No
            FROM CLFSUPP a WITH(NOLOCK)
            LEFT JOIN BeneficiaryAccount b WITH(NOLOCK) 
                ON a.sales_no = b.BeneficiaryID AND b.Category = 'Sales'
            LEFT JOIN UMFBANK c WITH(NOLOCK) 
                ON b.Acc_Bank = c.Bank_Code
            LEFT JOIN BeneficiaryTax d WITH(NOLOCK) 
                ON a.sales_no = d.BeneficiaryID AND d.Category = 'Sales'
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
                "Address": row.ADDRESS or "",
                "Acc No.": row.Acc_No or "",
                "Bank": row.bank_name or "",
                "Bank Branch": row.Acc_BankBranch or "",
                "NPWP": row.NPWP_No or "",
                "Status": status_text
            })

        df = pd.DataFrame(records)
        output = io.BytesIO()
        df.to_excel(output, index=False, sheet_name='Sales List')
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
