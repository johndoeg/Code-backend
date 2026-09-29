from datetime import datetime

from flask import Blueprint, jsonify, request, current_app, session
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text

import os
import uuid
from urllib.parse import quote
from werkzeug.utils import secure_filename
from botocore.exceptions import BotoCoreError, ClientError
from app.utils.helpers.aws_helpers import _aws_presign, _aws_upload, _aws_delete
from app.utils.helpers.access_helpers import user_right

VALID_SALES_DOC_TYPES = {
    "commission-receiver", "sales-ktp", "sales-npwp", "sales-bank-account",
    "sales-npwp-statement", "sales-other", "sales-contact-person", "sales-siup",
}

sales_bp = Blueprint('sales', __name__, url_prefix='/MasterData')

def _build_download_url(aws_key: str, file_name: str) -> str:
    return f"/MasterData/sales-entry/aws-download?aws_key={quote(aws_key)}&file_name={quote(file_name)}"

def _sales_search_params(search_val: str) -> tuple[str, dict]:
    if search_val:
        where = (
            "SALES_NO = :exact "
            "OR [NAME] LIKE :like_val "
            "OR REPLACE(IDCARD, '.', '') = :exact"
        )
        params = {"exact": search_val, "like_val": f"%{search_val}%"}
    else:
        where = "1=1"
        params = {}
    return where, params

def _validate_sales_no(sales_no: str) -> bool:
    return bool(sales_no) and sales_no.isalnum() and len(sales_no) <= 20

def _next_tv_sales_no() -> str:
    last = db.session.execute(text(
        "SELECT TOP 1 SALES_NO FROM CLFSALES WITH(NOLOCK) "
        "WHERE IsSalesTV = 1 ORDER BY CAST(SALES_NO AS BIGINT) DESC"
    )).scalar()
    return str(int(last) + 1) if last else "1"

@sales_bp.route('/sales')
@login_required
def get_sales():
    page       = request.args.get('page',       1,  type=int)
    limit      = request.args.get('limit',      25, type=int)
    search_val = request.args.get('search_val', '').strip()
    menu_id    = request.args.get('menu_id',    '').strip()
    
    try:
        where, params = _sales_search_params(search_val)

        total = db.session.execute(
            text(f"SELECT COUNT(*) AS total FROM CLFSALES WITH(NOLOCK) WHERE {where}"),
            params,
        ).scalar()

        offset = (page - 1) * limit
        rows = db.session.execute(text(f"""
            SELECT
                s.SALES_NO,
                s.[NAME],
                s.ADDRESS,
                ISNULL(s.IDCARD,      '')  AS IDCARD,
                s.Status,
                ISNULL(s.Sales_Type,  '')  AS Sales_Type,
                ISNULL(s.IsSalesTV,   0)   AS IsSalesTV,
                (
                    SELECT TOP 1 tv.SALES_NO
                    FROM CLFSALES tv WITH(NOLOCK)
                    WHERE tv.Initial_Sales_No = s.SALES_NO AND tv.IsSalesTV = 1
                ) AS CopiedToSalesNo
            FROM CLFSALES s WITH(NOLOCK)
            WHERE {where}
            ORDER BY s.SALES_NO
            OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
        """), {**params, "offset": offset, "limit": limit}).mappings().all()

        akses = user_right(session.get('accesslevel', ''), menu_id)

        data = [
            {
                "SALES_NO":        r["SALES_NO"]   or "",
                "NAME":            r["NAME"]        or "",
                "ADDRESS":         r["ADDRESS"]     or "",
                "IDCARD":          r["IDCARD"]      or "",
                "Status":          "Active" if r["Status"] == "A" else "Inactive",
                "Sales_Type":      r["Sales_Type"]  or "",
                "IsSalesTV":       bool(r["IsSalesTV"]),
                "CopiedToSalesNo": r["CopiedToSalesNo"] or "",
            }
            for r in rows
        ]

        return jsonify({"data": data, "total": total, "page": page, "limit": limit, "akses": akses})

    except Exception:
        current_app.logger.exception("Sales list error")
        return jsonify({"data": [], "total": 0, "error": "Failed to load sales data"}), 500

@sales_bp.route('/sales/<sales_no>')
@login_required
def get_sales_detail(sales_no):
    if not _validate_sales_no(sales_no):
        return jsonify({"error": "Invalid sales number"}), 400

    try:
        row = db.session.execute(text("""
            SELECT SALES_NO, [NAME], ADDRESS, NPWP, Tax, IDCARD, ACCNAME, BANK,
                   BRANCH_BANK, ACCNO, PAID, ID_ValidDt, Status, BD_Occupation,
                   ISNULL(IsSalesTV, 0) AS IsSalesTV, Sales_Type
            FROM CLFSALES WITH(NOLOCK) WHERE SALES_NO = :s
        """), {"s": sales_no}).mappings().first()

        if not row:
            return jsonify({"error": "Sales entry not found"}), 404

        return jsonify({
            "sales_no":      row["SALES_NO"]     or "",
            "name":          row["NAME"]          or "",
            "address":       row["ADDRESS"]       or "",
            "npwp":          row["NPWP"]          or "",
            "tax":           row["Tax"]           or "",
            "idcard":        row["IDCARD"]        or "",
            "accname":       row["ACCNAME"]       or "",
            "bank":          row["BANK"]          or "",
            "branch_bank":   row["BRANCH_BANK"]   or "",
            "accno":         row["ACCNO"]         or "",
            "paid":          row["PAID"]          or "",
            "id_valid_dt":   row["ID_ValidDt"].strftime('%Y-%m-%d') if row["ID_ValidDt"] else "",
            "status":        row["Status"]        or "",
            "bd_occupation": row["BD_Occupation"] or "",
            "is_sales_tv":   bool(row["IsSalesTV"]),
            "sales_type":    row["Sales_Type"]    or "",
        })

    except Exception:
        current_app.logger.exception("Sales detail error")
        return jsonify({"error": "Failed to load sales detail"}), 500

@sales_bp.route('/sales', methods=['POST'])
@login_required
def create_sales():
    try:
        emp_id = session.get('emp_id')

        body          = request.get_json(force=True) or {}
        city          = (body.get('city')          or '').strip()
        name          = (body.get('name')          or '').strip()
        status        =  body.get('status',  '1')
        idcard        = (body.get('idcard')        or '').strip()
        npwp          = (body.get('npwp')          or '').strip()
        bank          = (body.get('bank')          or '').strip()
        accno         = (body.get('accno')         or '').strip()
        tax           =  body.get('tax',    '')
        paid          =  body.get('paid',   '1')
        address       = (body.get('address')       or '').strip()
        id_validdt    = (body.get('id_validdt')    or '').strip()
        accname       = (body.get('accname')       or '').strip()
        bd_occupation = (body.get('bd_occupation') or '').strip()
        branch_bank   = (body.get('branch_bank')   or '').strip()

        if not all([city, name, idcard, address, id_validdt]):
            return jsonify({"success": False, "message": "Required fields missing"}), 400

        try:
            id_valid_date = datetime.strptime(id_validdt, '%Y-%m-%d')
            if id_valid_date.date() <= datetime.today().date():
                return jsonify({"success": False, "message": "ID Valid Date must be in the future"}), 400
        except ValueError:
            return jsonify({"success": False, "message": "Invalid date format (expected YYYY-MM-DD)"}), 400

        if city.lower() == 'jakarta':
            branch_cd = '10'
        else:
            branch_row = db.session.execute(
                text("SELECT BRANCH_CD FROM UMFBRANCH WITH(NOLOCK) WHERE CITY = :c"),
                {"c": city},
            ).first()
            if not branch_row:
                return jsonify({"success": False, "message": "City not found"}), 400
            branch_cd = branch_row.BRANCH_CD

        propertygroupname = f'CLFSALES{branch_cd}'
        nextno = db.session.execute(
            text("SELECT NextNumber FROM TANUMBER WITH(NOLOCK) WHERE PropertyGroupName = :p"),
            {"p": propertygroupname},
        ).scalar()
        if nextno is None:
            return jsonify({"success": False, "message": "Sales number configuration not found"}), 500

        sales_no = f"{branch_cd}{str(nextno).zfill(4)}"

        db.session.execute(text("""
            INSERT INTO CLFSALES
                (SALES_NO, [NAME], ADDRESS, NPWP, Tax, IDCARD, ACCNAME, BANK,
                 BRANCH_BANK, ACCNO, PAID, LastUpdate, UpdateBy, BD_Occupation,
                 ID_ValidDt, Status)
            VALUES
                (:sno, :name, :addr, :npwp, :tax, :idcard, :accname, :bank,
                 :bbank, :accno, :paid, SYSDATETIME(), :emp_id, :bd_occ,
                 :idvdt, :status)
        """), {
            "sno": sales_no, "name": name, "addr": address, "npwp": npwp,
            "tax": tax, "idcard": idcard, "accname": accname, "bank": bank,
            "bbank": branch_bank, "accno": accno, "paid": paid,
            "emp_id": emp_id, "bd_occ": bd_occupation,
            "idvdt": id_valid_date, "status": status,
        })

        db.session.execute(text("""
            UPDATE TANUMBER
            SET NextNumber = :n, LastUpdate = SYSDATETIME()
            WHERE PropertyGroupName = :p
        """), {"n": nextno + 1, "p": propertygroupname})

        db.session.commit()
        return jsonify({"success": True, "message": "Sales entry created successfully", "sales_no": sales_no})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Sales creation error")
        return jsonify({"success": False, "message": "Failed to create sales entry"}), 500

@sales_bp.route('/sales/generate', methods=['POST'])
@login_required
def generate_sales_number():
    try:
        body = request.get_json(force=True) or {}
        city = (body.get('city') or '').strip()
        if not city:
            return jsonify({"error": "City is required"}), 400

        if city.lower() == 'jakarta':
            branch_cd = '10'
        else:
            branch_row = db.session.execute(
                text("SELECT BRANCH_CD FROM UMFBRANCH WITH(NOLOCK) WHERE CITY = :c"),
                {"c": city},
            ).first()
            if not branch_row:
                return jsonify({"error": "City not found"}), 400
            branch_cd = branch_row.BRANCH_CD

        row = db.session.execute(text("""
            SELECT TOP 1 (CONVERT(bigint, SALES_NO) + 1) AS sales FROM CLFSALES WITH(NOLOCK)
            WHERE LEFT(SALES_NO, 2) = :b ORDER BY SALES_NO DESC
        """), {"b": branch_cd}).scalar()
        sales_no = str(row) if row else f"{branch_cd}0001"

        return jsonify({
            "sales_no":  sales_no,
            "branch_cd": branch_cd,
        })

    except Exception:
        current_app.logger.exception("Sales number generation error")
        return jsonify({"error": "Failed to generate sales number"}), 500

@sales_bp.route('/sales/copy-tv-info/<sales_no>')
@login_required
def get_copy_tv_info(sales_no):
    if not _validate_sales_no(sales_no):
        return jsonify({"error": "Invalid sales number"}), 400

    try:
        row = db.session.execute(
            text("SELECT SALES_NO, [NAME] FROM CLFSALES WITH(NOLOCK) WHERE SALES_NO = :s"),
            {"s": sales_no},
        ).mappings().first()
        if not row:
            return jsonify({"error": "Sales not found"}), 404

        return jsonify({
            "initial_sales_no": row["SALES_NO"],
            "initial_name":     row["NAME"],
            "new_sales_no":     _next_tv_sales_no(),
            "new_name":         f"{row['NAME']} (tv)",
            "created_by":       session.get('username', ''),
        })

    except Exception:
        current_app.logger.exception("Copy TV info error")
        return jsonify({"error": "Failed to load copy TV info"}), 500

@sales_bp.route('/sales/copy-tv', methods=['POST'])
@login_required
def copy_sales_tv():
    try:
        emp_id   = session.get('emp_id')
        username = session.get('username', '')

        body             = request.get_json(force=True) or {}
        initial_sales_no = (body.get('initial_sales_no') or '').strip()

        if not initial_sales_no:
            return jsonify({"success": False, "message": "initial_sales_no is required"}), 400
        if not _validate_sales_no(initial_sales_no):
            return jsonify({"success": False, "message": "Invalid sales number format"}), 400

        src = db.session.execute(
            text("SELECT SALES_NO, [NAME] FROM CLFSALES WITH(NOLOCK) WHERE SALES_NO = :s"),
            {"s": initial_sales_no},
        ).mappings().first()
        if not src:
            return jsonify({"success": False, "message": "Source sales record not found"}), 404

        existing_copy = db.session.execute(text("""
            SELECT TOP 1 SALES_NO FROM CLFSALES WITH(NOLOCK)
            WHERE Initial_Sales_No = :s AND IsSalesTV = 1
        """), {"s": initial_sales_no}).scalar()
        if existing_copy:
            return jsonify({
                "success": False,
                "message": f"Sales sudah pernah disalin dengan nomor: {existing_copy}",
                "existing_sales_no": existing_copy,
            }), 409

        new_sales_no = _next_tv_sales_no()
        new_name     = f"{src['NAME']} (tv)"

        # 1. CLFSALES
        db.session.execute(text("""
            INSERT INTO CLFSALES
                (SALES_NO, NAME, ADDRESS, City, PHONE, IDCARD, PAID,
                 BD_Occupation, BD_OccupationOther, ID_ValidDt, Status,
                 Sales_Type, Created_By, BRANCH_CD, ZipCode, Sales_Nickname,
                 FAX, CREATE_DATE, SALES_NOTES, Initial_Sales_No, IsSalesTV)
            SELECT
                :new_no, :new_name, ADDRESS, City, PHONE, IDCARD, PAID,
                BD_Occupation, BD_OccupationOther, ID_ValidDt, Status,
                Sales_Type, :username, BRANCH_CD, ZipCode, Sales_Nickname,
                FAX, GETDATE(), SALES_NOTES, :init_no, 1
            FROM CLFSALES WITH(NOLOCK)
            WHERE SALES_NO = :init_no
        """), {"new_no": new_sales_no, "new_name": new_name,
               "username": username, "init_no": initial_sales_no})

        # 2. BeneficiaryAccount
        db.session.execute(text("""
            INSERT INTO BeneficiaryAccount
                (Category, BeneficiaryID, Acc_NO, Acc_Name, Acc_Bank,
                 Acc_BankBranch, BeneficiaryType, ResidentStatus, [Default], AccountType)
            SELECT Category, :new_no, Acc_NO, Acc_Name, Acc_Bank,
                   Acc_BankBranch, BeneficiaryType, ResidentStatus, [Default], AccountType
            FROM BeneficiaryAccount WITH(NOLOCK)
            WHERE BeneficiaryID = :init_no AND Category = 'SALES'
        """), {"new_no": new_sales_no, "init_no": initial_sales_no})

        # 3. BeneficiaryTax
        db.session.execute(text("""
            INSERT INTO BeneficiaryTax
                (Category, BeneficiaryID, TFFrom, TFTo, PPN, DateStart,
                 TaxType, TaxRate, DPP, NPWP_No, NPWP_Name, NPWP_Address,
                 NPWP_City, NPWP_Prov, NPWP_Type, NPWP_Start)
            SELECT Category, :new_no, TFFrom, TFTo, PPN, DateStart,
                   TaxType, TaxRate, DPP, NPWP_No, NPWP_Name, NPWP_Address,
                   NPWP_City, NPWP_Prov, NPWP_Type, NPWP_Start
            FROM BeneficiaryTax WITH(NOLOCK)
            WHERE BeneficiaryID = :init_no AND Category = 'SALES'
        """), {"new_no": new_sales_no, "init_no": initial_sales_no})

        # 4. CLFSALESPIC
        db.session.execute(text("""
            INSERT INTO CLFSALESPIC
                (SALES_NO, Contact_Name, Contact_IDCard, Contact_IDValidDt,
                 Contact_Address, Contact_City, Contact_Post, Contact_Phone,
                 Contact_Position, Contact_PositionOther, Occupation)
            SELECT
                :new_no, Contact_Name, Contact_IDCard, Contact_IDValidDt,
                Contact_Address, Contact_City, Contact_Post, Contact_Phone,
                Contact_Position, Contact_PositionOther, Occupation
            FROM CLFSALESPIC WITH(NOLOCK)
            WHERE SALES_NO = :init_no
        """), {"new_no": new_sales_no, "init_no": initial_sales_no})

        # 5. SalesPaidBy_Ext
        db.session.execute(text("""
            INSERT INTO SalesPaidBy_Ext
                (SalesNo, CAM_StartDate, CAM_EndDate, CreateBy, CreateDate)
            VALUES (:new_no, '2022-01-01', '2999-12-31', :emp_id, CAST(GETDATE() AS DATE))
        """), {"new_no": new_sales_no, "emp_id": emp_id})

        # 6. CLFSALES_FILE
        has_files = db.session.execute(text(
            "SELECT TOP 1 1 FROM CLFSALES_FILE WITH(NOLOCK) WHERE SALES_NO = :s"
        ), {"s": initial_sales_no}).scalar()
        if has_files:
            db.session.execute(text("""
                INSERT INTO CLFSALES_FILE (SALES_NO, FILE_NM, FILE_EXT, CAT, KET)
                SELECT :new_no,
                       REPLACE(FILE_NM, :init_no, :new_no),
                       FILE_EXT, CAT, KET
                FROM CLFSALES_FILE WITH(NOLOCK)
                WHERE SALES_NO = :init_no
            """), {"new_no": new_sales_no, "init_no": initial_sales_no})

        db.session.commit()
        return jsonify({
            "success":      True,
            "message":      "Sales TV copy created successfully",
            "new_sales_no": new_sales_no,
        })

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Copy TV error")
        return jsonify({"success": False, "message": "Failed to copy sales TV"}), 500

def _resolve_sales_no(sales_no: str) -> str:
    row = db.session.execute(text("""
        SELECT Initial_Sales_No FROM CLFSALES WITH(NOLOCK)
        WHERE SALES_NO = :s AND IsSalesTV = 1
    """), {"s": sales_no}).first()
    return row.Initial_Sales_No if row and row.Initial_Sales_No else sales_no

@sales_bp.route('/sales-entry/aws-download', methods=['GET'])
@login_required
def sales_entry_aws_download():
    aws_key   = request.args.get('aws_key', '').strip()
    file_name = request.args.get('file_name', 'download').strip()

    if not aws_key:
        return jsonify({"error": "aws_key required"}), 400

    try:
        url = _aws_presign(aws_key, file_name)
        return jsonify({"url": url, "file_name": file_name})
    except (BotoCoreError, ClientError) as exc:
        current_app.logger.exception(exc)
        return jsonify({"error": str(exc)}), 500

@sales_bp.route('/sales-entry/<sales_no>/files', methods=['GET'])
@login_required
def get_sales_entry_files(sales_no):
    if not _validate_sales_no(sales_no):
        return jsonify({"error": "Invalid sales number"}), 400

    try:
        real_sno = _resolve_sales_no(sales_no)

        rows = db.session.execute(text("""
            SELECT ID, AWSKey, File_Nm, File_Ext, DocumentType, Ket,
                   FORMAT(CreatedDate, 'dd-MM-yyyy HH:mm') AS CreatedDate
            FROM CLFSALES_FILE WITH(NOLOCK)
            WHERE SALES_NO = :s AND Cat = 'Sales'
                  AND File_Nm IS NOT NULL AND File_Nm NOT IN ('', '-')
            ORDER BY DocumentType, CreatedDate DESC
        """), {"s": real_sno}).mappings().all()

        files_by_type = {}
        lainnya = ""
        for r in rows:
            doc_type = r["DocumentType"] or ""
            file_name = f'{r["File_Nm"]}.{r["File_Ext"]}' if r["File_Ext"] else (r["File_Nm"] or "")
            files_by_type.setdefault(doc_type, []).append({
                "id":           r["ID"],
                "aws_key":      r["AWSKey"] or "",
                "file_nm":      r["File_Nm"] or "",
                "file_ext":     r["File_Ext"] or "",
                "doc_type":     doc_type,
                "ket":          r["Ket"] or "",
                "created_date": r["CreatedDate"] or "",
                "download_url": _build_download_url(r["AWSKey"] or "", file_name),
            })
            if not lainnya and r["Ket"]:
                lainnya = r["Ket"]

        return jsonify({"files": files_by_type, "lainnya": lainnya})

    except Exception:
        current_app.logger.exception("Sales entry files list error")
        return jsonify({"error": "Failed to load files"}), 500

@sales_bp.route('/sales-entry/<sales_no>/files/<doc_type>', methods=['POST'])
@login_required
def upload_sales_entry_file(sales_no, doc_type):
    if not _validate_sales_no(sales_no):
        return jsonify({"success": False, "message": "Invalid sales number"}), 400
    if doc_type not in VALID_SALES_DOC_TYPES:
        return jsonify({"success": False, "message": "Invalid document type"}), 400

    files = request.files.getlist('file')
    if not files:
        return jsonify({"success": False, "message": "No file(s) provided"}), 400

    ket = (request.form.get('lainnya') or '').strip()
    uploaded = []

    try:
        for f in files:
            safe_name = secure_filename(f.filename or '')
            file_nm, file_ext = os.path.splitext(safe_name)
            file_ext = file_ext.lstrip('.')
            aws_key = f"sales/{sales_no}/{doc_type}/{uuid.uuid4().hex}_{safe_name}"

            _aws_upload(f, aws_key)

            db.session.execute(text("""
                INSERT INTO CLFSALES_FILE
                    (SALES_NO, AWSKey, File_Nm, File_Ext, DocumentType, Cat, Ket, CreatedDate)
                VALUES
                    (:sno, :aws_key, :file_nm, :file_ext, :doc_type, 'Sales', :ket, SYSDATETIME())
            """), {
                "sno": sales_no, "aws_key": aws_key, "file_nm": file_nm,
                "file_ext": file_ext, "doc_type": doc_type, "ket": ket,
            })
            uploaded.append(safe_name)

        db.session.commit()
        return jsonify({"success": True, "uploaded": uploaded})

    except (BotoCoreError, ClientError):
        db.session.rollback()
        current_app.logger.exception("S3 upload failed")
        return jsonify({"success": False, "message": "Upload to storage failed"}), 500
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Sales entry file upload error")
        return jsonify({"success": False, "message": "Upload failed"}), 500

@sales_bp.route('/sales-entry/<sales_no>/files/<int:file_id>', methods=['DELETE'])
@login_required
def delete_sales_entry_file(sales_no, file_id):
    if not _validate_sales_no(sales_no):
        return jsonify({"success": False, "message": "Invalid sales number"}), 400

    try:
        row = db.session.execute(text("""
            SELECT AWSKey FROM CLFSALES_FILE WITH(NOLOCK) WHERE ID = :id AND SALES_NO = :sno
        """), {"id": file_id, "sno": sales_no}).first()

        if not row:
            return jsonify({"success": False, "message": "File not found"}), 404

        db.session.execute(text("""
            DELETE FROM CLFSALES_FILE WHERE ID = :id AND SALES_NO = :sno
        """), {"id": file_id, "sno": sales_no})
        db.session.commit()

        if row.AWSKey:
            try:
                _aws_delete(row.AWSKey)
            except (BotoCoreError, ClientError):
                current_app.logger.exception("S3 cleanup failed for %s", row.AWSKey)

        return jsonify({"success": True})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Sales entry file delete error")
        return jsonify({"success": False, "message": "Delete failed"}), 500