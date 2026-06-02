from flask import Blueprint, jsonify, request, current_app, session
from app import db
from sqlalchemy import text

sales_bp = Blueprint('sales', __name__, url_prefix='/MasterData')

@sales_bp.route('/api/sales')
def get_sales():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 25, type=int)
    search_val = request.args.get('search_val', '').strip()
    search_by = request.args.get('search_by', '').strip()
    
    emp_id = session.get('emp_id')
    menu_id = request.args.get('menu_id')
    accesslevel = session.get('accesslevel')

    try:
        where_clause = "1=1" 
        if search_val:
            if search_by == '1':
                where_clause = "SALES_NO = :search_val"
            elif search_by == '2':
                where_clause = "[NAME] LIKE :search_val"
                search_val = f"%{search_val}%"
            elif search_by == '3':
                where_clause = "REPLACE(IDCARD, '.', '') = :search_val"
            else:
                where_clause = "SALES_NO = :search_val OR [NAME] LIKE :search_val OR REPLACE(IDCARD, '.', '') = :search_val"
                search_val = f"%{search_val}%"
        else:
            where_clause = "1=1"

        count_query = text(f"""
            SELECT COUNT(*) as total 
            FROM CLFSALES WITH(NOLOCK) 
            WHERE {where_clause}
        """)
        
        count_params = {"search_val": search_val} if search_val else {}
        count_result = db.session.execute(count_query, count_params)
        total = count_result.fetchone().total

        offset = (page - 1) * limit
        data_query = text(f"""
            SELECT 
                SALES_NO, 
                [NAME], 
                ADDRESS, 
                ISNULL(IDCARD, '') as IDCARD, 
                Status,
                Sales_Type,
                IsSalesTV
            FROM CLFSALES WITH(NOLOCK) 
            WHERE {where_clause}
            ORDER BY SALES_NO
            OFFSET :offset ROWS 
            FETCH NEXT :limit ROWS ONLY
        """)
        
        data_params = {
            **count_params,
            "offset": offset,
            "limit": limit
        }
        
        result = db.session.execute(data_query, data_params)
        sales_data = []
        
        for row in result:
            status_text = "Active" if row.Status == 'A' else "Inactive"
            
            action = "Edit"

            sales_data.append({
                "SALES_NO": row.SALES_NO or "",
                "NAME": row.NAME or "",
                "ADDRESS": row.ADDRESS or "",
                "IDCARD": row.IDCARD or "",
                "Status": status_text,
                "action": action,
                "Sales_Type": row.Sales_Type or "",
                "IsSalesTV": row.IsSalesTV or ""
            })
        
        return jsonify({
            "data": sales_data,
            "total": total,
            "page": page,
            "limit": limit,
            "akses": "9"
        })

    except Exception as e:
        current_app.logger.exception("Sales list error")
        return jsonify({"data": [], "total": 0, "error": str(e)}), 500

@sales_bp.route('/api/sales', methods=['POST'])
def create_sales():
    try:
        emp_id = session.get('emp_id')
        if not emp_id:
            return jsonify({"success": False, "message": "Not authenticated"}), 401

        city = request.json.get('city', '').strip()
        name = request.json.get('name', '').strip()
        status = request.json.get('status', '1')
        idcard = request.json.get('idcard', '').strip()
        npwp = request.json.get('npwp', '').strip()
        bank = request.json.get('bank', '').strip()
        accno = request.json.get('accno', '').strip()
        tax = request.json.get('tax', '')
        paid = request.json.get('paid', '1')
        address = request.json.get('address', '').strip()
        id_validdt = request.json.get('id_validdt', '').strip()
        accname = request.json.get('accname', '').strip()
        bd_occupation = request.json.get('bd_occupation', '').strip()
        branch_bank = request.json.get('branch_bank', '').strip()

        if not all([city, name, idcard, address, id_validdt]):
            return jsonify({"success": False, "message": "Required fields missing"}), 400

        from datetime import datetime
        try:
            id_valid_date = datetime.strptime(id_validdt, '%Y-%m-%d')
            if id_valid_date.date() <= datetime.today().date():
                return jsonify({"success": False, "message": "ID Valid Date must be in the future"}), 400
        except ValueError:
            return jsonify({"success": False, "message": "Invalid date format"}), 400

        if city.lower() == 'jakarta':
            branch_cd = '10'
        else:
            branch_query = text("SELECT BRANCH_CD FROM UMFBRANCH WITH(NOLOCK) WHERE CITY = :city")
            branch_result = db.session.execute(branch_query, {"city": city})
            branch_row = branch_result.fetchone()
            if not branch_row:
                return jsonify({"success": False, "message": "City not found"}), 400
            branch_cd = branch_row.BRANCH_CD

        propertygroupname = f'CLFSALES{branch_cd}'
        nextnum_query = text("SELECT NextNumber FROM TANUMBER WITH(NOLOCK) WHERE PropertyGroupName = :propertygroupname")
        nextnum_result = db.session.execute(nextnum_query, {"propertygroupname": propertygroupname})
        nextnum_row = nextnum_result.fetchone()
        
        if not nextnum_row:
            return jsonify({"success": False, "message": "Sales number configuration not found"}), 500
            
        nextno = nextnum_row.NextNumber
        sales_no = f"{branch_cd}{str(nextno).zfill(4)}"

        db.session.begin()

        insert_query = text("""
            INSERT INTO CLFSALES (
                SALES_NO, [NAME], ADDRESS, NPWP, Tax, IDCARD, ACCNAME, BANK, 
                BRANCH_BANK, ACCNO, PAID, LastUpdate, UpdateBy, BD_Occupation, 
                ID_ValidDt, Status
            ) VALUES (
                :sales_no, :name, :address, :npwp, :tax, :idcard, :accname, :bank,
                :branch_bank, :accno, :paid, SYSDATETIME(), :emp_id, :bd_occupation,
                :id_valid_dt, :status
            )
        """)
        
        insert_params = {
            "sales_no": sales_no,
            "name": name,
            "address": address,
            "npwp": npwp,
            "tax": tax,
            "idcard": idcard,
            "accname": accname,
            "bank": bank,
            "branch_bank": branch_bank,
            "accno": accno,
            "paid": paid,
            "emp_id": emp_id,
            "bd_occupation": bd_occupation,
            "id_valid_dt": id_valid_date,
            "status": status
        }
        
        db.session.execute(insert_query, insert_params)

        nextno_baru = nextno + 1
        update_query = text("""
            UPDATE TANUMBER 
            SET NextNumber = :nextno_baru, LastUpdate = SYSDATETIME() 
            WHERE PropertyGroupName = :propertygroupname
        """)
        db.session.execute(update_query, {
            "nextno_baru": nextno_baru,
            "propertygroupname": propertygroupname
        })

        db.session.commit()

        return jsonify({
            "success": True, 
            "message": "Sales entry created successfully",
            "sales_no": sales_no
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Sales creation error")
        return jsonify({"success": False, "message": "Failed to create sales entry"}), 500

@sales_bp.route('/api/sales/<sales_no>')
def get_sales_detail(sales_no):
   
    try:
        query = text("""
            SELECT 
                SALES_NO, [NAME], ADDRESS, NPWP, Tax, IDCARD, ACCNAME, BANK, 
                BRANCH_BANK, ACCNO, PAID, ID_ValidDt, Status, BD_Occupation
            FROM CLFSALES WITH(NOLOCK) 
            WHERE SALES_NO = :sales_no
        """)
        result = db.session.execute(query, {"sales_no": sales_no})
        row = result.fetchone()
        
        if not row:
            return jsonify({"error": "Sales entry not found"}), 404
            
        return jsonify({
            "sales_no": row.SALES_NO or "",
            "name": row.NAME or "",
            "address": row.ADDRESS or "",
            "npwp": row.NPWP or "",
            "tax": row.Tax or "",
            "idcard": row.IDCARD or "",
            "accname": row.ACCNAME or "",
            "bank": row.BANK or "",
            "branch_bank": row.BRANCH_BANK or "",
            "accno": row.ACCNO or "",
            "paid": row.PAID or "",
            "id_valid_dt": row.ID_ValidDt.strftime('%Y-%m-%d') if row.ID_ValidDt else "",
            "status": row.Status or "",
            "bd_occupation": row.BD_Occupation or ""
        })
        
    except Exception as e:
        current_app.logger.exception("Sales detail error")
        return jsonify({"error": "Failed to load sales details"}), 500

@sales_bp.route('/api/sales/generate', methods=['POST'])
def generate_sales_number():
    try:
        city = request.json.get('city', '').strip()
        if not city:
            return jsonify({"error": "City is required"}), 400

        if city.lower() == 'jakarta':
            branch_cd = '10'
        else:
            branch_query = text("SELECT BRANCH_CD FROM UMFBRANCH WITH(NOLOCK) WHERE CITY = :city")
            branch_result = db.session.execute(branch_query, {"city": city})
            branch_row = branch_result.fetchone()
            if not branch_row:
                return jsonify({"error": "City not found"}), 400
            branch_cd = branch_row.BRANCH_CD

        propertygroupname = f'CLFSALES{branch_cd}'
        nextnum_query = text("SELECT NextNumber FROM TANUMBER WITH(NOLOCK) WHERE PropertyGroupName = :propertygroupname")
        nextnum_result = db.session.execute(nextnum_query, {"propertygroupname": propertygroupname})
        nextnum_row = nextnum_result.fetchone()
        
        if not nextnum_row:
            return jsonify({"error": "Sales number configuration not found"}), 500
            
        nextno = nextnum_row.NextNumber
        sales_no = f"{branch_cd}{str(nextno).zfill(4)}"

        return jsonify({
            "sales_no": sales_no,
            "branch_cd": branch_cd
        })

    except Exception as e:
        current_app.logger.exception("Sales number generation error")
        return jsonify({"error": "Failed to generate sales number"}), 500
    
