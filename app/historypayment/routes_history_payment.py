from flask import Blueprint, request, send_file, current_app, jsonify, session
from sqlalchemy import text
from app import db
import pandas as pd
import io
from datetime import datetime

history_payment_bp = Blueprint('historypayment', __name__, url_prefix='/HistoryPayment')

def _fmt_date(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d-%m-%Y")
    if hasattr(value, "strftime"):
        return value.strftime("%d-%m-%Y")
    return str(value)
 
 
def _float(value) -> float:
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0

@history_payment_bp.route('/api/history-payment', methods=['GET'])
def get_history_payment_records():
    try:
        print_by = request.args.get('print_by', '').strip()
        page = max(1, int(request.args.get('page', 1)))
        limit = min(100, max(1, int(request.args.get('limit', 25))))
        offset = (page - 1) * limit
        
        police_no = request.args.get('police_no', '').strip()
        lease_no = request.args.get('lease_no', '').strip()
        lessee_no = request.args.get('lessee_no', '').strip()
        lessee_nm = request.args.get('lessee_nm', '').strip()
        master_no = request.args.get('master_no', '').strip()
        type_cust = request.args.get('type_cust', '1')
        
        if not print_by:
            return jsonify({"success": False, "message": "print_by parameter is required"}), 400
        
        where_clauses = []
        params = {}
        
        if print_by in ('1', '6', '7'):
            if not police_no:
                return jsonify({"success": False, "message": "police_no parameter is required"}), 400
            if print_by == '1':
                where_clauses.append("eq.POLICENO LIKE :search_term")
            elif print_by == '6':
                where_clauses.append("eq.CHASIS LIKE :search_term")
            elif print_by == '7':
                where_clauses.append("eq.ENGINE LIKE :search_term")
            params['search_term'] = f"%{police_no}%"
            
        elif print_by == '2':
            if not lease_no:
                return jsonify({"success": False, "message": "lease_no parameter is required"}), 400
            where_clauses.append("a.LEASE_NO = :search_term")
            params['search_term'] = lease_no
            
        elif print_by == '3':
            if not lessee_no:
                return jsonify({"success": False, "message": "lessee_no parameter is required"}), 400
            where_clauses.append("b.LESSEE_NO = :search_term")
            params['search_term'] = lessee_no
            if type_cust == '2':
                where_clauses.append("a.UPD_STAT = 'Y'")
                
        elif print_by == '4':
            if not lessee_nm:
                return jsonify({"success": False, "message": "lessee_nm parameter is required"}), 400
            where_clauses.append("b.LESSEE_NM LIKE :search_term")
            params['search_term'] = f"{lessee_nm}%"
            
        elif print_by == '5':
            if not master_no:
                return jsonify({"success": False, "message": "master_no parameter is required"}), 400
            where_clauses.append("d.MSTR_CL = :search_term")
            params['search_term'] = master_no
        else:
            return jsonify({"success": False, "message": "Invalid print_by value"}), 400
        
        where_clause = " AND ".join(where_clauses)
        
        count_query = text("""
            SELECT COUNT(*) as total
            FROM (
                SELECT a.LEASE_NO, b.LESSEE_NM, b.LESSEE_NO
                FROM CLFCONT a WITH(NOLOCK)
                LEFT JOIN CLFLESS b WITH(NOLOCK) ON a.LESSEE_NO = b.LESSEE_NO
                LEFT JOIN CAFEQUIP eq WITH(NOLOCK) ON a.APPL_NO = eq.APPL_NO
                LEFT JOIN TAMASTER d WITH(NOLOCK) ON a.LEASE_NO = d.LEASE_NO
                WHERE {where}
            ) AS subquery
        """.format(where=where_clause))
        
        data_query = text("""
            SELECT * FROM (
                SELECT *,
                    ROW_NUMBER() OVER(ORDER BY LESSEE_NM, LESSEE_NO, LEASE_NO) AS ROW_NUM
                FROM (
                    SELECT 
                        a.LEASE_NO,
                        eq.POLICENO,
                        eq.CHASIS,
                        eq.ENGINE,
                        b.LESSEE_NM,
                        b.LESSEE_NO,
                        CASE 
                            WHEN b.LESSEE_TP = 'PR' THEN 
                                CONCAT(b.address1, ', RT. ', e.rt, '/', e.rw, ', ', 
                                ISNULL(g.Desc_Name, e.KELURAHAN), ', ', 
                                ISNULL(f.Desc_Name, e.KECAMATAN), ', ', 
                                ISNULL(b.city1, ''), ' ', b.ZipCode1)
                            ELSE 
                                CONCAT(b.address2, ', RT. ', e.rt, '/', e.rw, ', ', 
                                ISNULL(g.Desc_Name, e.KELURAHAN), ', ', 
                                ISNULL(f.Desc_Name, e.KECAMATAN), ', ', 
                                ISNULL(b.city2, ''), ' ', b.ZipCode2)
                        END AS address,
                        b.PHONE1,
                        a.EXECUTION,
                        a.UPD_STAT,
                        d.MSTR_CL
                    FROM CLFCONT a WITH(NOLOCK)
                    LEFT JOIN CLFLESS b WITH(NOLOCK) ON a.LESSEE_NO = b.LESSEE_NO
                    LEFT JOIN CAFEQUIP eq WITH(NOLOCK) ON a.APPL_NO = eq.APPL_NO
                    LEFT JOIN CAFLESS_DETAIL_ADDRESS e WITH(NOLOCK) ON b.APLESS = e.APLESS
                    LEFT JOIN Mst_Kecamatan f WITH(NOLOCK) ON e.KECAMATAN = f.Kecamatan_CD
                    LEFT JOIN Mst_Kelurahan g WITH(NOLOCK) ON e.KELURAHAN = g.Kelurahan_CD
                    LEFT JOIN TAMASTER d WITH(NOLOCK) ON a.LEASE_NO = d.LEASE_NO
                    WHERE {where}
                ) AS inner_query
            ) AS outer_query
            WHERE ROW_NUM BETWEEN :offset_plus_1 AND :offset_plus_limit
        """.format(where=where_clause))
        
        params['offset'] = offset
        params['limit'] = limit
        params['offset_plus_1'] = offset + 1
        params['offset_plus_limit'] = offset + limit
        
        count_result = db.session.execute(count_query, params).fetchone()
        total = count_result.total if count_result else 0
        
        result = db.session.execute(data_query, params)
        records = []
        
        for row in result:
            records.append({
                "LESSEE_NM": row.LESSEE_NM or "",
                "LESSEE_NO": row.LESSEE_NO or "",
                "LEASE_NO": row.LEASE_NO or "",
                "POLICENO": row.POLICENO or "",
                "CHASIS": row.CHASIS or "",
                "ENGINE": row.ENGINE or "",
                "MSTR_CL": row.MSTR_CL or "",
                "ADDRESS": row.address or "",
                "PHONE1": row.PHONE1 or "",
                "EXECUTION": row.EXECUTION or "",
                "UPD_STAT": row.UPD_STAT or "",
            })
        
        return jsonify({
            "success": True,
            "data": records,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1)
        })
        
    except ValueError as e:
        current_app.logger.error(f"Invalid parameter: {e}")
        return jsonify({"success": False, "message": "Invalid parameter value"}), 400
    except Exception as e:
        print(f"Error: {e}")
        current_app.logger.exception("History payment search error")
        return jsonify({"success": False, "message": "Failed to fetch payment history"}), 500

@history_payment_bp.route('/api/amortization', methods=['GET'])
def get_amortization_data():
    lease_no = request.args.get('lease_no', '').strip()
    
    if not lease_no:
        return jsonify({"error": "lease_no parameter is required"}), 400
    
    try:
        query = text("""
            SELECT 
                a.PERIOD, 
                FORMAT(a.DATE_DUE, 'dd-MMM-yyyy') AS DueDate, 
                FORMAT(a.RENTAL, 'N0', 'id-ID') as RENTAL, 
                FORMAT(a.ACCRUAL1, 'N0', 'id-ID') as ACCRUAL1, 
                FORMAT(a.ACCRUAL2, 'N0', 'id-ID') as ACCRUAL2, 
                FORMAT(a.L_INCOME, 'N0', 'id-ID') as L_INCOME, 
                FORMAT(a.I_RECOVERY, 'N0', 'id-ID') as I_RECOVERY, 
                FORMAT(a.OUTS_PRINC, 'N0', 'id-ID') as OUTS_PRINC, 
                FORMAT(a.UN_INCOME, 'N0', 'id-ID') as UN_INCOME, 
                FORMAT(a.OUTS_REC, 'N0', 'id-ID') as OUTS_REC, 
                FORMAT(a.DATE_PAY, 'dd-MMM-yyyy') AS Payment,
                FORMAT(a.L_INCOME_PSAK, 'N0', 'id-ID') as L_INCOME_PSAK, 
                FORMAT(a.I_RECOVERY_PSAK, 'N0', 'id-ID') as I_RECOVERY_PSAK, 
                FORMAT(a.OUTS_PRINC_PSAK, 'N0', 'id-ID') as OUTS_PRINC_PSAK, 
                FORMAT(a.UN_INCOME_PSAK, 'N0', 'id-ID') as UN_INCOME_PSAK, 
                FORMAT(a.ATRIBUTE, 'N0', 'id-ID') as ATRIBUTE, 
                c.lessee_nm, 
                ROUND(d.declrate, 2) as declrate, 
                ROUND(e.irr, 2) as irr
            FROM CLFPAY a WITH(NOLOCK) 
                INNER JOIN clfcont_data b WITH(NOLOCK) ON a.lease_no = b.lease_no
                INNER JOIN clfless c WITH(NOLOCK) ON b.lessee_no = c.lessee_no
                INNER JOIN cafcont d WITH(NOLOCK) ON b.appl_no = d.appl_no
                INNER JOIN clfatr e WITH(NOLOCK) ON a.lease_no = e.lease_no
            WHERE a.lease_no = :lease_no 
            ORDER BY a.PERIOD
        """)
        
        result = db.session.execute(query, {"lease_no": lease_no})
        rows = []
        customer_name = ""
        declrate = 0
        irr = 0
        
        for row in result:
            if not customer_name:
                customer_name = row.lessee_nm or ""
                declrate = row.declrate or 0
                irr = row.irr or 0
            
            rows.append({
                "PERIOD": row.PERIOD,
                "DueDate": row.DueDate or "",
                "RENTAL": row.RENTAL or "0",
                "ACCRUAL1": row.ACCRUAL1 or "0",
                "ACCRUAL2": row.ACCRUAL2 or "0",
                "L_INCOME": row.L_INCOME or "0",
                "I_RECOVERY": row.I_RECOVERY or "0",
                "OUTS_PRINC": row.OUTS_PRINC or "0",
                "UN_INCOME": row.UN_INCOME or "0",
                "OUTS_REC": row.OUTS_REC or "0",
                "Payment": row.Payment or "",
                "L_INCOME_PSAK": row.L_INCOME_PSAK or "0",
                "I_RECOVERY_PSAK": row.I_RECOVERY_PSAK or "0",
                "OUTS_PRINC_PSAK": row.OUTS_PRINC_PSAK or "0",
                "UN_INCOME_PSAK": row.UN_INCOME_PSAK or "0",
                "ATRIBUTE": row.ATRIBUTE or "0",
            })
        
        return jsonify({
            "customerName": customer_name,
            "declrate": declrate,
            "irr": irr,
            "rows": rows
        })
        
    except Exception as e:
        current_app.logger.exception(f"Amortization fetch error for {lease_no}")
        return jsonify({"error": "Failed to fetch amortization data"}), 500

def parse_asof_date(asof_str: str) -> str:
    
    try:
        day, month, year = asof_str.split('-')
        return f"{year}-{month}-{day}"
    except Exception:
        raise ValueError("Invalid date format. Expected DD-MM-YYYY")

@history_payment_bp.route('/export/aging-detail', methods=['GET'])
def export_aging_detail_excel():
  
    try:
        asof = request.args.get('asof', '').strip()
        branch_cd = request.args.get('branch_cd', '').strip() or None
        type_of = request.args.get('type_of', '').strip() or None
        
        if not asof:
            return jsonify({"error": "asof parameter is required"}), 400
        
        try:
            day, month, year = asof.split('-')
            asof_sql = f"{year}-{month}-{day}"
        except ValueError:
            return jsonify({"error": "Invalid date format. Use DD-MM-YYYY"}), 400

        query = text("""
            EXEC USP_AGING_DETAIL 
                @asof = :asof,
                @branch_cd = :branch_cd,
                @type_of = :type_of
        """)
        
        result = db.session.execute(query, {
            "asof": asof_sql,
            "branch_cd": branch_cd,
            "type_of": type_of
        })
        
        df = pd.DataFrame([dict(row._mapping) for row in result])
        
        if df.empty:
            columns = [
                "no_urut", "LESSEE_NM", "LESSEE_NO", "LEASE_NO", "ALAMAT", "HP", 
                "GIRODT", "nominal", "HARI", "BUCKET", "OUTS_PRINC", "UN_INCOME", 
                "periode", "TENOR", "KENDARAAN", "POLICENO", "RedCode", "CONDITION", 
                "penalty", "DEALER", "CMO", "KODEPOS", "Catatan", "BRANCH_NAME", 
                "cont_type", "fin_purpose", "Status_JFG", "RENTAL", "EXECUTION", 
                "ntf", "PaymentType", "os_contractual", "income_contractual"
            ]
            df = pd.DataFrame(columns=columns)
        
        date_cols = ['GIRODT', 'EXECUTION']
        for col in date_cols:
            if col in df.columns and df[col].notna().any():
                df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%d-%m-%Y')
        
        currency_cols = ['nominal', 'OUTS_PRINC', 'UN_INCOME', 'penalty', 'RENTAL', 'ntf', 'os_contractual', 'income_contractual']
        for col in currency_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                df[col] = df[col].apply(lambda x: f"{int(x):,}".replace(',', '.'))

        def safe_sum_currency(series_name):
            if series_name not in df.columns or df[series_name].empty:
                return 0
            cleaned = df[series_name].astype(str).str.replace('.', '', regex=False).str.replace(',', '', regex=False)
            return pd.to_numeric(cleaned, errors='coerce').fillna(0).sum()
        
        totals = {
            'nominal': safe_sum_currency('nominal'),
            'OUTS_PRINC': safe_sum_currency('OUTS_PRINC'),
            'UN_INCOME': safe_sum_currency('UN_INCOME'),
            'penalty': safe_sum_currency('penalty'),
            'os_contractual': safe_sum_currency('os_contractual'),
            'income_contractual': safe_sum_currency('income_contractual'),
        }
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='DetailAging', index=False, startrow=4)
            worksheet = writer.sheets['DetailAging']
            
            workbook = writer.book
            
            from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
            from openpyxl.utils import get_column_letter
            
            header_font = Font(name='Tahoma', size=10, bold=True)
            header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=False)
            thin_border = Border(
                left=Side(style='thin'), right=Side(style='thin'),
                top=Side(style='thin'), bottom=Side(style='thin')
            )
            
            data_font = Font(name='Tahoma', size=7)
            data_alignment_center = Alignment(horizontal='center', vertical='center')
            data_alignment_right = Alignment(horizontal='right', vertical='center')
            data_alignment_left = Alignment(horizontal='left', vertical='center')
            
            headers = [
                'NO.', 'NAMA CUSTOMER', 'NO. CUSTOMER', 'NO. KONTRAK', 'ALAMAT', 'NO. HP',
                'TGL JTH TEMPO', 'ANGSURAN TERTUNGGAK', 'DAYS', 'BUCKET', 'OUTSTANDING PRINCIPAL',
                'OUTSTANDING INCOME', 'INST', 'TENOR', 'MEREK/ TIPE KENDARAAN', 'NO. POLISI',
                'RED CODE', 'CONDITION', 'PENALTI', 'DEALER', 'CMO', 'KODE POS', 'COLLECTOR',
                'LATE CONDITION', 'BRANCH NAME', 'CONTRACT TYPE', 'PURPOSE OF FINANCE', 'STATUS JFG',
                'INSTALLMENT', 'TANGGAL DISBURSED', 'NTF', 'Type Of Payment',
                'OUTSTANDING PRINCIPAL (CONTRACTUAL)', 'OUTSTANDING INCOME (CONTRACTUAL)'
            ]
            
            for col_idx, header in enumerate(headers, start=1):
                cell = worksheet.cell(row=5, column=col_idx, value=header)
                cell.font = header_font
                cell.alignment = header_alignment
                cell.border = thin_border
            
            for row_idx, row in enumerate(df.itertuples(index=False), start=6):
                for col_idx, value in enumerate(row, start=1):
                    cell = worksheet.cell(row=row_idx, column=col_idx, value=value)
                    cell.font = data_font
                    cell.border = thin_border
                    
                    if col_idx in [1, 3, 4, 9, 10, 13, 14, 17, 18, 22, 23, 26, 29, 30, 32]:
                        cell.alignment = data_alignment_center
                    elif col_idx in [7, 8, 11, 12, 19, 31, 33, 34]:
                        cell.alignment = data_alignment_right
                    else:
                        cell.alignment = data_alignment_left
                    
                    if col_idx == 5:
                        cell.alignment = Alignment(wrap_text=True, vertical='center')
            
            for col_idx, header in enumerate(headers, start=1):
                col_letter = get_column_letter(col_idx)
                max_len = max(len(str(header)), df.iloc[:, col_idx-1].astype(str).str.len().max() if not df.empty else 0)
                worksheet.column_dimensions[col_letter].width = min(max_len + 2, 50)  # Cap at 50 chars
            
            totals_row = len(df) + 6
            total_labels = ['', '', '', '', '', '', '', 'TOTAL', '', '', '', '', '', '', '', '', '', '', 'TOTAL', '', '', '', '', '', '', '', '', '', '', '', '', '', 'TOTAL', 'TOTAL']
            
            for col_idx, (label, col_name) in enumerate(zip(total_labels, [
                None, None, None, None, None, None, None, 'nominal', None, None, 'OUTS_PRINC', 
                'UN_INCOME', None, None, None, None, None, None, 'penalty', None, None, None, 
                None, None, None, None, None, None, None, None, None, None, 'os_contractual', 'income_contractual'
            ]), start=1):
                if col_name and col_name in totals:
                    cell = worksheet.cell(row=totals_row, column=col_idx, value=totals[col_name])
                    cell.font = Font(name='Tahoma', size=7, bold=True)
                    cell.alignment = data_alignment_right
                    cell.border = thin_border
                    cell.number_format = '#,##0'
                elif label:
                    cell = worksheet.cell(row=totals_row, column=col_idx, value=label)
                    cell.font = Font(name='Tahoma', size=7, bold=True)
                    cell.alignment = data_alignment_right
                    cell.border = thin_border
            
            worksheet.merge_cells('A1:AA1')
            worksheet.merge_cells('A2:AA2')
            worksheet['A2'] = current_app.config.get('COMPANY_NAME', 'PT Genie Finance Indonesia')
            worksheet['A2'].font = Font(name='Tahoma', size=10)
            worksheet['A2'].alignment = Alignment(horizontal='left')
            
            worksheet['AB1'] = f'Date : {datetime.now().strftime("%d %b %Y")}'
            worksheet['AB1'].font = Font(name='Tahoma', size=10)
            worksheet['AB1'].alignment = Alignment(horizontal='left')
            
            worksheet['AB2'] = f'Print By : {request.headers.get("X-Username", "System")}'
            worksheet['AB2'].font = Font(name='Tahoma', size=10)
            worksheet['AB2'].alignment = Alignment(horizontal='left')
            
            worksheet.merge_cells('A3:AB3')
            worksheet['A3'] = 'DETAIL AGING REPORT'
            worksheet['A3'].font = Font(name='Tahoma', size=10, bold=True)
            worksheet['A3'].alignment = Alignment(horizontal='center', vertical='center')
            
            worksheet.merge_cells('A4:AB4')
            worksheet['A4'] = f'As of {datetime.strptime(asof_sql, "%Y-%m-%d").strftime("%d-%m-%Y")}'
            worksheet['A4'].font = Font(name='Tahoma', size=10)
            worksheet['A4'].alignment = Alignment(horizontal='center', vertical='center')
        
        output.seek(0)
        
        filename = f"DetailAging_{asof}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        current_app.logger.exception(f"Excel export error: {e}")
        return jsonify({"error": "Failed to generate Excel file"}), 500

@history_payment_bp.route('/api/history-payment/print', methods=['GET'])
def get_history_payment_print():
   
    try:
        lease_no = request.args.get('lease_no', '').strip()
        if not lease_no:
            return jsonify({"success": False, "message": "lease_no is required"}), 400
 
        username = session.get('username', '')
       
        contract_sql = text("""
            SELECT
                a.LESSEE_NO,
                i.[name]                    AS trans_code,
                b.LESSEE_NM,
                CASE
                    WHEN b.LESSEE_TP = 'PR' THEN
                        CONCAT(b.address1, ', RT. ', j.rt, '/', j.rw, ', ',
                               ISNULL(l.Desc_Name, j.KELURAHAN), ', ',
                               ISNULL(k.Desc_Name, j.KECAMATAN), ', ',
                               ISNULL(b.city1, ''), ' ', b.ZipCode1)
                    ELSE
                        CONCAT(b.address2, ', RT. ', j.rt, '/', j.rw, ', ',
                               ISNULL(l.Desc_Name, j.KELURAHAN), ', ',
                               ISNULL(k.Desc_Name, j.KECAMATAN), ', ',
                               ISNULL(b.city2, ''), ' ', b.ZipCode2)
                END                         AS ADDRESS,
                b.PHONE1,
                b.PHONE2,
                b.PHONE3,
                c.BPKB_AN,
                c.POLICENO,
                c.CHASIS,
                c.ENGINE,
                c.TAHUN,
                c.COLOUR,
                d.NAME                      AS suppname,
                e.TYPE_NM,
                f.MODEL_NM,
                g.BRANCH_NAME,
                h.BRAND_NM,
                c.DATEBLOKIR,
                c.NOPOLBLOKIR,
                CASE
                    WHEN a.UPD_STAT = 'Y' AND a.EXECUTION IS NULL     THEN 'Undisburse'
                    WHEN a.UPD_STAT = 'Y' AND a.EXECUTION IS NOT NULL  THEN 'Outstanding'
                    WHEN a.UPD_STAT = 'F'                              THEN 'Finish'
                    ELSE 'Terminate'
                END                         AS status_kontrak,
                -- IIF in PHP checks <> '' but a LEFT JOIN miss gives NULL, so IS NOT NULL guard needed
                IIF(m.lease_no IS NOT NULL AND m.lease_no <> '', '(JFG)', '') AS JFG
            FROM      CLFCONT  a WITH(NOLOCK)
            LEFT JOIN CLFLESS  b WITH(NOLOCK) ON a.LESSEE_NO   = b.LESSEE_NO
            LEFT JOIN CLFEQUIP c WITH(NOLOCK) ON a.LEASE_NO    = c.LEASE_NO
            LEFT JOIN CLFSUPP  d WITH(NOLOCK) ON c.SUPP        = d.SUPP
            LEFT JOIN UMFTYPE  e WITH(NOLOCK) ON c.BRAND       = e.BRAND  AND c.TYPE  = e.TYPE
            LEFT JOIN UMFMODEL f WITH(NOLOCK) ON c.MODEL       = f.MODEL
            LEFT JOIN UMFBRANCH g WITH(NOLOCK) ON a.BRANCH_CD  = g.BRANCH_CD
            LEFT JOIN UMFBRAND  h WITH(NOLOCK) ON c.BRAND      = h.BRAND
            LEFT JOIN MSTCFFL   i WITH(NOLOCK) ON i.Cons_Leas  = a.Cons_Leas
            LEFT JOIN CAFLESS_DETAIL_ADDRESS j WITH(NOLOCK) ON b.APLESS      = j.APLESS
            LEFT JOIN Mst_Kecamatan k WITH(NOLOCK) ON j.KECAMATAN = k.Kecamatan_CD
            LEFT JOIN Mst_Kelurahan l WITH(NOLOCK) ON j.KELURAHAN = l.Kelurahan_CD
            LEFT JOIN JF_GANESHA m WITH(NOLOCK) ON a.lease_no  = m.lease_no
            WHERE a.LEASE_NO = :lease_no
        """)
 
        row = db.session.execute(contract_sql, {"lease_no": lease_no}).fetchone()
        if row is None:
            return jsonify({"success": False, "message": "Contract not found"}), 404
 
        type_nm = f"{row.BRAND_NM or ''} {row.TYPE_NM or ''}".strip()
 
        contract_info = {
            "LESSEE_NO":      row.LESSEE_NO      or "",
            "trans_code":     row.trans_code      or "",
            "LESSEE_NM":      row.LESSEE_NM       or "",
            "ADDRESS":        (row.ADDRESS or "").upper(),
            "PHONE1":         row.PHONE1          or "",
            "PHONE2":         row.PHONE2          or "",
            "PHONE3":         row.PHONE3          or "",
            "BPKB_AN":        row.BPKB_AN         or "",
            "POLICENO":       row.POLICENO        or "",
            "CHASIS":         row.CHASIS          or "",
            "ENGINE":         row.ENGINE          or "",
            "TAHUN":          row.TAHUN           or "",
            "COLOUR":         row.COLOUR          or "",
            "suppname":       row.suppname        or "",
            "TYPE_NM":        type_nm,
            "MODEL_NM":       row.MODEL_NM        or "",
            "BRANCH_NAME":    row.BRANCH_NAME     or "",
            "DATEBLOKIR":     _fmt_date(row.DATEBLOKIR),
            "NOPOLBLOKIR":    row.NOPOLBLOKIR     or "",
            "status_kontrak": row.status_kontrak  or "",
            "JFG":            row.JFG             or "",
        }
 
        sp_sql = text("EXEC USP_RPT_CustHistCheque :lease_no, :username")
        sp_result = db.session.execute(sp_sql, {"lease_no": lease_no, "username": username})
 
        payments = []
        for p in sp_result:
            payments.append({
                "girono":           getattr(p, "girono",           None) or "",
                "girodt":           _fmt_date(getattr(p, "girodt",  None)),
                "payment":          _fmt_date(getattr(p, "payment", None)),
                "bank":             getattr(p, "bank",             None) or "",
                "nominal":          _float(getattr(p, "nominal",          None)),
                "period":           getattr(p, "period",           None) or "",
                "penalty":          _float(getattr(p, "penalty",          None)),
                "Shortage":         _float(getattr(p, "Shortage",         None)),
                "inkaso":           _float(getattr(p, "inkaso",           None)),
                "status":           getattr(p, "status",           None),
                "reject_description": getattr(p, "reject_description", None) or "",
                "penalty_payment":  _float(getattr(p, "penalty_payment",  None)),
                "ShortagePay":      _float(getattr(p, "ShortagePay",      None)),
                "InkasoPay":        _float(getattr(p, "InkasoPay",        None)),
            })
 
        return jsonify({
            "success":      True,
            "contractInfo": contract_info,
            "payments":     payments,
        })
 
    except Exception:
        current_app.logger.exception("History payment print error")
        return jsonify({"success": False, "message": "Failed to fetch print data"}), 500