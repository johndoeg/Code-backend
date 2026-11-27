from flask import Blueprint, jsonify, request, current_app, send_file, Response, session
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text
import io
import pandas as pd
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

dealer_report_bp = Blueprint('dealer_report', __name__, url_prefix='/MasterData')

@dealer_report_bp.route('/branches')
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
    
@dealer_report_bp.route('/sales-list/print')
@login_required
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

@dealer_report_bp.route('/sales-list/excel')
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

ALL_BRANCHES = '000'
MAX_PAGE_LIMIT = 200

DEALER_FROM = """
    FROM CLFSUPP a WITH(NOLOCK)
        LEFT JOIN BeneficiaryAccount c WITH(NOLOCK)
            ON a.SUPP = c.BeneficiaryID AND c.Category = 'Dealer' AND c.AccountType = 'D'
        LEFT JOIN UMFBANK b WITH(NOLOCK)
            ON c.Acc_Bank = b.BANK_CODE
"""

DEALER_COLUMNS = """
    a.NAME, a.NICKNAME, a.ADDRESS, a.CITY, a.PHONE, a.CONTACT, a.POSITION,
    c.Acc_NO AS AccNo, c.Acc_BankBranch AS BankBranch, b.[DESC] AS BankDesc
"""

DEALER_ORDER = "ORDER BY a.NAME, a.SUPP"

DEALER_FIELDS = (
    ("No.", "no", 5),
    ("Name", "name", 28),
    ("Nickname", "nickname", 18),
    ("Address", "address", 45),
    ("City", "city", 16),
    ("Phone", "phone", 18),
    ("Contact", "contact", 20),
    ("Position", "position", 14),
    ("Acc No.", "accNo", 18),
    ("Bank", "bank", 22),
    ("Bank Branch", "bankBranch", 22),
)


def _branch_filter(branch_cd: str):
    if branch_cd == ALL_BRANCHES:
        return "1=1", {}
    return "a.BRANCH_CD = :branch_cd", {"branch_cd": branch_cd}


def _dash(value) -> str:
    v = "" if value is None else str(value).strip()
    return v if v else "-"


def _to_record(no: int, row) -> dict:
    return {
        "no": no,
        "name": _dash(row.NAME),
        "nickname": _dash(row.NICKNAME),
        "address": _dash(row.ADDRESS),
        "city": _dash(row.CITY),
        "phone": _dash(row.PHONE),
        "contact": _dash(row.CONTACT),
        "position": _dash(row.POSITION),
        "accNo": _dash(row.AccNo),
        "bank": _dash(row.BankDesc),
        "bankBranch": _dash(row.BankBranch),
    }


def _fetch_all_dealers(branch_cd: str) -> list:
    where, params = _branch_filter(branch_cd)
    rows = db.session.execute(
        text(f"SELECT {DEALER_COLUMNS} {DEALER_FROM} WHERE {where} {DEALER_ORDER}"),
        params,
    ).fetchall()
    return [_to_record(i, r) for i, r in enumerate(rows, 1)]


def _print_by_line() -> str:
    return f"Print By - Date : {session.get('username', '')} - {datetime.now().strftime('%d/%m/%Y')}"


@dealer_report_bp.route('/dealer-list')
@login_required
def get_dealer_list():
    page = max(request.args.get('page', 1, type=int), 1)
    limit = min(max(request.args.get('limit', 25, type=int), 1), MAX_PAGE_LIMIT)
    branch_cd = request.args.get('branch_cd', '').strip()

    if not branch_cd:
        return jsonify({"data": [], "total": 0})

    try:
        where, params = _branch_filter(branch_cd)

        total = db.session.execute(
            text(f"SELECT COUNT(*) AS total {DEALER_FROM} WHERE {where}"),
            params,
        ).fetchone().total

        offset = (page - 1) * limit
        rows = db.session.execute(
            text(f"""
                SELECT {DEALER_COLUMNS} {DEALER_FROM}
                WHERE {where}
                {DEALER_ORDER}
                OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
            """),
            {**params, "offset": offset, "limit": limit},
        ).fetchall()

        return jsonify({
            "data": [_to_record(offset + i, r) for i, r in enumerate(rows, 1)],
            "total": total,
        })
    except Exception:
        current_app.logger.exception("Dealer list report error")
        return jsonify({"data": [], "total": 0}), 500


@dealer_report_bp.route('/dealer-list/print')
@login_required
def print_dealer_list():
    branch_cd = request.args.get('branch_cd', '').strip()
    if not branch_cd:
        return jsonify({"error": "Please Fill The Field"}), 400

    try:
        records = _fetch_all_dealers(branch_cd)
        return jsonify({
            "data": records,
            "total": len(records),
            "print_by": session.get("username", ""),
            "print_date": datetime.now().strftime('%d/%m/%Y'),
        })
    except Exception:
        current_app.logger.exception("Dealer print report error")
        return jsonify({"error": "Error generating report"}), 500


@dealer_report_bp.route('/dealer-list/excel')
@login_required
def export_dealer_excel():
    branch_cd = request.args.get('branch_cd', '').strip()
    if not branch_cd:
        return Response("Please Fill The Field", status=400, mimetype='text/plain')

    try:
        records = _fetch_all_dealers(branch_cd)
        col_count = len(DEALER_FIELDS)
        last_col = get_column_letter(col_count)
        thin = Side(style='thin', color='000000')
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        font = Font(name='Tahoma', size=9)
        top_wrap = Alignment(vertical='top', wrap_text=True)

        wb = Workbook()
        ws = wb.active
        ws.title = 'ListofDealer'

        ws.merge_cells(f'A1:{last_col}1')
        ws['A1'] = 'List of Dealer'
        ws['A1'].font = Font(name='Tahoma', size=15, bold=True)
        ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[1].height = 24

        ws.merge_cells(f'A2:{last_col}2')
        ws['A2'] = _print_by_line()
        ws['A2'].font = font
        ws['A2'].alignment = Alignment(horizontal='center')

        header_row = 4
        for idx, (label, _, width) in enumerate(DEALER_FIELDS, start=1):
            c = ws.cell(row=header_row, column=idx, value=label)
            c.font = font
            c.border = border
            c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
            ws.column_dimensions[get_column_letter(idx)].width = width

        if records:
            for r_idx, r in enumerate(records, start=header_row + 1):
                for c_idx, (_, key, _) in enumerate(DEALER_FIELDS, start=1):
                    c = ws.cell(row=r_idx, column=c_idx, value=r[key])
                    c.font = font
                    c.border = border
                    c.alignment = Alignment(horizontal='center', vertical='top') if key == 'no' else top_wrap
        else:
            row = header_row + 1
            ws.merge_cells(f'A{row}:{last_col}{row}')
            c = ws.cell(row=row, column=1, value='Data Not Found..')
            c.font = Font(name='Tahoma', size=12, color='EE0000')
            c.alignment = Alignment(horizontal='center')
            for c_idx in range(1, col_count + 1):
                ws.cell(row=row, column=c_idx).border = border

        ws.freeze_panes = f'A{header_row + 1}'

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='ListofDealer.xlsx',
        )

    except Exception:
        current_app.logger.exception("Dealer excel export error")
        return Response("Error exporting to Excel", status=500, mimetype='text/plain')