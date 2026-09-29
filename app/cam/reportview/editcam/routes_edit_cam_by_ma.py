from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from flask import Blueprint, jsonify, request, session, current_app

from app import db
from app.auth.decorators import login_required

edit_cam_by_ma_bp = Blueprint('edit_cam_by_ma', __name__, url_prefix='/CAM/Edit')

def _exec_rows(sql: str, params: list) -> list[dict]:
    raw_conn = db.session.connection().connection
    cursor = raw_conn.cursor()
    try:
        cursor.execute(sql, params)
        if cursor.description is None:
            return []
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        cursor.close()

def _exec_write(sql: str, params: list) -> None:
    raw_conn = db.session.connection().connection
    cursor = raw_conn.cursor()
    try:
        cursor.execute(sql, params)
    finally:
        cursor.close()

def _parse_date(raw: str) -> Optional[date]:
    raw = (raw or '').strip()
    if not raw:
        return None
    for fmt in ('%d-%m-%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None

def _num(val) -> float:
    if val is None:
        return 0.0
    return float(val)

def _fetch_revisions(appl_nos: list[str]) -> dict[str, str]:
    if not appl_nos:
        return {}
    revisions: dict[str, str] = {}
    chunk_size = 1000
    for i in range(0, len(appl_nos), chunk_size):
        chunk = appl_nos[i:i + chunk_size]
        placeholders = ','.join('?' for _ in chunk)
        rows = _exec_rows(
            f"SELECT NEWAPPL_NO, REVISI FROM MCMORevisi WITH (NOLOCK) WHERE NEWAPPL_NO IN ({placeholders})",
            chunk,
        )
        revisions.update({r['NEWAPPL_NO']: f"R{r['REVISI']}" for r in rows})
    return revisions

@edit_cam_by_ma_bp.route('/cam-on-hand/list')
@login_required
def cam_on_hand_list():
    search_by = request.args.get('search_by', '').strip()
    search_val = request.args.get('search_val', '').strip()

    try:
        page = max(int(request.args.get('page', 1) or 1), 1)
    except ValueError:
        page = 1
    try:
        limit = max(int(request.args.get('limit', 10) or 10), 1)
    except ValueError:
        limit = 10

    offset = (page - 1) * limit

    base_select = """
    SELECT a.CREATE_DATE, a.Cons_Leas, a.APPL_NO, b.LESSEE_NM, d.BRANCH_NAME, c.FULLNAME, e.AdmSts, f.EXECUTION
    FROM CAFCONT a WITH (NOLOCK)
        INNER JOIN CAFLESS b WITH (NOLOCK) ON a.apless = b.apless
        LEFT JOIN APP_USRMST c WITH (NOLOCK) ON a.CMO = c.EMPLOYEE_ID
        LEFT JOIN UMFBRANCH d WITH (NOLOCK) ON a.BRANCH_CD = d.BRANCH_CD
        LEFT JOIN MCMOCAMCOMPLETELIST e WITH (NOLOCK) ON a.APPL_NO = e.APPL_NO
        LEFT JOIN CLFCONT f WITH (NOLOCK) ON a.APPL_NO = f.APPL_NO
    """

    if search_by == '1':
        where_clause = "WHERE a.appl_no = ? AND e.AdmSts = '1'"
        params = [search_val]
    elif search_by == '2':
        where_clause = "WHERE b.LESSEE_NM LIKE ? AND e.AdmSts = '1'"
        params = [f"%{search_val}%"]
    else:
        where_clause = "WHERE e.AdmSts = '1' AND (b.Cust_Type = '' OR b.Indus_Code = '')"
        params = []

    try:
        count_sql = f"SELECT COUNT(*) AS cnt FROM ({base_select} {where_clause}) x"
        count_rows = _exec_rows(count_sql, params)
        total = count_rows[0]['cnt'] if count_rows else 0
        page_sql = (
            base_select + where_clause +
            " ORDER BY a.CREATE_DATE DESC OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
        )
        rows = _exec_rows(page_sql, params + [offset, limit])

        appl_nos = [r['APPL_NO'] for r in rows if r.get('APPL_NO')]
        revisions = _fetch_revisions(appl_nos)

        results = []
        for r in rows:
            appl_no = r.get('APPL_NO') or ''
            if r.get('EXECUTION'):
                status = 'Disbursed'
            elif r.get('AdmSts') == '1':
                status = 'Approved'
            else:
                status = 'Not Yet Approved'
            create_date = r.get('CREATE_DATE')
            results.append({
                'appl_no': appl_no,
                'cam_no': f"{r.get('Cons_Leas')} - {appl_no}{revisions.get(appl_no, '')}",
                'create_date': create_date.strftime('%d-%m-%Y') if create_date else '',
                'customer_name': r.get('LESSEE_NM') or '-',
                'status': status,
                'branch_cmo': f"{r.get('BRANCH_NAME') or ''} - {r.get('FULLNAME') or ''}",
                'editable': len(appl_no) <= 11,
            })

        return jsonify({'data': results, 'total': total})
    except Exception as e:
        current_app.logger.exception("Cam On Hand list error")
        return jsonify({'error': str(e)}), 500

@edit_cam_by_ma_bp.route('/customer-bo-search')
@login_required
def customer_bo_search():
    mode = request.args.get('mode', 'customer').strip()
    lessee_tp = request.args.get('lessee_tp', 'PR').strip()
    search = request.args.get('search', '').strip()
    own_apless = request.args.get('own_apless', '').strip()
    try:
        page = max(int(request.args.get('page', 1) or 1), 1)
    except ValueError:
        page = 1
    page_size = 100
    offset = (page - 1) * page_size + 1
    end = page * page_size

    try:
        if mode == 'customer':
            rows = _exec_rows(
                "EXEC USP_CAM_ListCustomer ?, ?, ?, ?, ?",
                [offset, end, search, lessee_tp, own_apless],
            )
            results = [{
                'id': r.get('APLESS'),
                'label': r.get('LESSEE_NM'),
                'address': r.get('ADDRESS1'),
                'id_card': r.get('ID_CARD'),
                'appl_no': r.get('APPL_NO'),
                'selectable': r.get('APLESS') != own_apless,
                'source': 'customer',
            } for r in rows]
        else:
            rows = _exec_rows(
                "SELECT TOP 200 BO_ID, BO_Name, Alias FROM BENEFICIARY_OWNER WITH (NOLOCK) "
                "WHERE BO_TP = ? AND BO_Name LIKE ? ORDER BY BO_Name",
                [lessee_tp, f"%{search}%"],
            )
            results = [{
                'id': r.get('BO_ID'),
                'label': r.get('BO_Name'),
                'address': r.get('Alias'),
                'id_card': '',
                'appl_no': '',
                'selectable': True,
                'source': 'beneficiary',
            } for r in rows]
        return jsonify(results)
    except Exception as e:
        current_app.logger.exception("Customer/BO search error")
        return jsonify({'error': str(e)}), 500

def _industry_root_options() -> list[dict]:
    rows = _exec_rows(
        "SELECT Header, Descrip FROM MstIndustry_lbpp WITH (NOLOCK) WHERE MLCI_Code = '' ORDER BY Descrip", [])
    return [{'value': r['Header'], 'label': r['Descrip']} for r in rows]

def _industry_level1_options(header: str) -> list[dict]:
    rows = _exec_rows(
        "SELECT MLCI_Code, Descrip, Header FROM MstIndustry_lbpp WITH (NOLOCK) WHERE Parent = ? ORDER BY MLCI_Code",
        [header])
    return [{'value': f"{r['MLCI_Code']}|{r['Header']}", 'label': f"{r['MLCI_Code']}-{r['Descrip']}"} for r in rows]

def _industry_children_options(parent: str, header: str, leaf: bool = False) -> list[dict]:
    if not parent:
        return []
    if leaf:
        rows = _exec_rows(
            "SELECT MLCI_Code, Descrip FROM MstIndustry_lbpp WITH (NOLOCK) WHERE Parent = ? AND Header = ? ORDER BY MLCI_Code",
            [parent, header])
        return [{'value': r['MLCI_Code'], 'label': f"{r['MLCI_Code']}-{r['Descrip']}"} for r in rows]
    rows = _exec_rows(
        "SELECT MLCI_Code, Descrip, Header FROM MstIndustry_lbpp WITH (NOLOCK) WHERE Parent = ? AND Header = ? ORDER BY MLCI_Code",
        [parent, header])
    return [{'value': f"{r['MLCI_Code']}|{r['Header']}", 'label': f"{r['MLCI_Code']}-{r['Descrip']}"} for r in rows]

def _lookup_industry_row(code: str) -> dict:
    if not code:
        return {}
    rows = _exec_rows("SELECT Header, Parent FROM MstIndustry_lbpp WITH (NOLOCK) WHERE MLCI_Code = ?", [code])
    return rows[0] if rows else {}

def _build_industry_state(ind_code5: str) -> dict:
    root_options = _industry_root_options()
    empty = {
        'level0_options': root_options, 'level0_selected': '',
        'level1_options': [], 'level1_selected': '',
        'level2_options': [], 'level2_selected': '',
        'level3_options': [], 'level3_selected': '',
        'level4_options': [], 'level4_selected': '',
        'level5_options': [], 'level5_selected': '',
    }
    if not ind_code5:
        return empty

    row0 = _lookup_industry_row(ind_code5)
    header, parent = row0.get('Header', ''), row0.get('Parent', '')
    row1 = _lookup_industry_row(parent)
    header1, parent1 = row1.get('Header', ''), row1.get('Parent', '')
    row2 = _lookup_industry_row(parent1)
    header2, parent2 = row2.get('Header', ''), row2.get('Parent', '')
    row3 = _lookup_industry_row(parent2)
    header3, parent3 = row3.get('Header', ''), row3.get('Parent', '')

    return {
        'level0_options': root_options, 'level0_selected': header,
        'level1_options': _industry_level1_options(header),
        'level1_selected': f"{parent3}|{header}" if parent3 else '',
        'level2_options': _industry_children_options(parent3, header),
        'level2_selected': f"{parent2}|{header}" if parent2 else '',
        'level3_options': _industry_children_options(ind_code5[:3], header),
        'level3_selected': f"{ind_code5[:4]}|{header}",
        'level4_options': _industry_children_options(ind_code5[:4], header),
        'level4_selected': f"{ind_code5[:5]}|{header}",
        'level5_options': _industry_children_options(ind_code5[:5], header, leaf=True),
        'level5_selected': ind_code5,
    }

@edit_cam_by_ma_bp.route('/cam-edit-ma/industry-children')
@login_required
def industry_children():
    level = request.args.get('level', '').strip()
    header = request.args.get('header', '').strip()
    parent = request.args.get('parent', '').strip()
    try:
        if level == '1':
            return jsonify(_industry_level1_options(header))
        if level == '5':
            return jsonify(_industry_children_options(parent, header, leaf=True))
        return jsonify(_industry_children_options(parent, header))
    except Exception as e:
        current_app.logger.exception("Industry children lookup error")
        return jsonify({'error': str(e)}), 500

def _occupation_options(bo_cat: str) -> dict:
    if bo_cat == 'EM':
        rows = _exec_rows("SELECT [VALUE], DESC_VALUE FROM MSTCOMBO WITH (NOLOCK) WHERE CAT_VALUE = 'PEP'", [])
    elif bo_cat in ('EN', 'CV', 'PT'):
        rows = _exec_rows(
            "SELECT [VALUE], DESC_VALUE FROM MSTCOMBO WITH (NOLOCK) WHERE CAT_VALUE = 'USAHA_HIGH_RISK'", [])
    elif bo_cat == 'CO':
        rows = _exec_rows(
            "SELECT [VALUE], DESC_VALUE FROM MSTCOMBO WITH (NOLOCK) WHERE CAT_VALUE = 'KOPERASI_HIGH_RISK'", [])
    else:
        rows = []
    options = [{'value': r['VALUE'], 'label': r['DESC_VALUE']} for r in rows]
    disabled = bo_cat in ('FD', 'PF')
    return {'options': options, 'disabled': disabled}

@edit_cam_by_ma_bp.route('/cam-edit-ma/occupation-options')
@login_required
def occupation_options():
    bo_cat = request.args.get('bo_cat', '').strip()
    try:
        return jsonify(_occupation_options(bo_cat))
    except Exception as e:
        current_app.logger.exception("Occupation options error")
        return jsonify({'error': str(e)}), 500

@edit_cam_by_ma_bp.route('/cam-edit-ma/province-city')
@login_required
def province_city():
    area_cd = request.args.get('area_cd', '').strip()
    if not area_cd:
        return jsonify({'province': '', 'city': ''})
    try:
        rows = _exec_rows(
            "SELECT Propinsi, Kabupaten FROM UMFAREA WITH (NOLOCK) WHERE area_cd = ? AND FLAG_DEL = 0", [area_cd])
        if not rows:
            return jsonify({'province': '', 'city': ''})
        return jsonify({'province': rows[0].get('Propinsi') or '', 'city': rows[0].get('Kabupaten') or ''})
    except Exception as e:
        current_app.logger.exception("Province/city lookup error")
        return jsonify({'error': str(e)}), 500

@edit_cam_by_ma_bp.route('/cam-edit-ma/lookups')
@login_required
def lookups():
    try:
        bi_customer_types = _exec_rows(
            "SELECT OJK_Code, MLCI_Desc FROM UMFBITYP_LBPP WITH (NOLOCK) WHERE OJK_Code IS NOT NULL ORDER BY MLCI_Desc", [])
        areas = _exec_rows(
            "SELECT AREA_CD, Propinsi, Kabupaten FROM UMFAREA WITH (NOLOCK) WHERE FLAG_DEL = 0 ORDER BY Propinsi", [])
        marital_statuses = _exec_rows(
            "SELECT Marital, name FROM MSTMARITAL WITH (NOLOCK) WHERE Marital <> 'P'", [])
        source_funds_pr = _exec_rows(
            "SELECT [VALUE], DESC_VALUE FROM MSTCOMBO WITH (NOLOCK) WHERE CAT_VALUE = 'SOURCE_FUND'", [])
        source_funds_pt = _exec_rows(
            "SELECT [VALUE], DESC_VALUE FROM MSTCOMBO WITH (NOLOCK) WHERE CAT_VALUE = 'SOURCE_FUND' AND [VALUE] IN ('2','3','4')", [])
        bo_categories_pr = _exec_rows(
            "SELECT CUST_TYPE, NAME FROM MSTLESSEETYPE WITH (NOLOCK) WHERE LESSEE_TP = 'PR'", [])
        bo_categories_pt = _exec_rows(
            "SELECT CUST_TYPE, NAME FROM MSTLESSEETYPE WITH (NOLOCK) WHERE LESSEE_TP = 'PT'", [])

        return jsonify({
            'bi_customer_types': [{'value': r['OJK_Code'], 'label': r['MLCI_Desc']} for r in bi_customer_types],
            'areas': [{'value': r['AREA_CD'], 'label': f"{r['Propinsi']} - {r['Kabupaten']}"} for r in areas],
            'marital_statuses': [{'value': r['Marital'], 'label': r['name']} for r in marital_statuses],
            'source_funds_pr': [{'value': r['VALUE'], 'label': r['DESC_VALUE']} for r in source_funds_pr],
            'source_funds_pt': [{'value': r['VALUE'], 'label': r['DESC_VALUE']} for r in source_funds_pt],
            'bo_categories_pr': [{'value': r['CUST_TYPE'], 'label': r['NAME']} for r in bo_categories_pr],
            'bo_categories_pt': [{'value': r['CUST_TYPE'], 'label': r['NAME']} for r in bo_categories_pt],
        })
    except Exception as e:
        current_app.logger.exception("Lookups error")
        return jsonify({'error': str(e)}), 500

def _fetch_bo_address(bo_id: str, address_type: str) -> dict:
    rows = _exec_rows(
        "SELECT ADDRESS, AREA_CD, CITY, KECAMATAN, KELURAHAN, RT, RW, ZIPCODE, FAX, PHONE "
        "FROM BENEFICIARY_OWNER_ADDRESS WITH (NOLOCK) WHERE BO_ID = ? AND ADDRESS_TYPE = ?",
        [bo_id, address_type])
    return rows[0] if rows else {}

def _load_pr_from_beneficiary_owner(bo_id: str) -> dict:
    rows = _exec_rows(
        "SELECT BO_Name, Alias, BO_Cat, Mobile, Email, IDCard, PlaceBirth, DateBirth, Gender, Marital, "
        "Citizenship, Nationality, AverageIncome, SourceFund, SourceFundOther, CompanyName, UpdateBy, "
        "LastUpdate, BUSINESS_TYPE"
        "FROM BENEFICIARY_OWNER WITH (NOLOCK) WHERE BO_ID = ?", [bo_id])
    r = rows[0] if rows else {}
    id_addr = _fetch_bo_address(bo_id, 'ID')
    add_addr = _fetch_bo_address(bo_id, 'ADDITIONAL')
    office_addr = _fetch_bo_address(bo_id, 'OFFICE')
    birth = r.get('DateBirth')
    last_update = r.get('LastUpdate')
    return {
        'bo_name': r.get('BO_Name', ''), 'alias': r.get('Alias', ''), 'bo_cat': r.get('BO_Cat', ''),
        'mobile_phone1': r.get('Mobile', ''), 'email1': r.get('Email', ''), 'id_card': r.get('IDCard', ''),
        'placebirth': r.get('PlaceBirth', ''), 'tglbirth': birth.strftime('%d-%m-%Y') if birth else '',
        'gender': r.get('Gender', ''), 'marital': r.get('Marital', ''), 'citizen': r.get('Citizenship', ''),
        'nationality': r.get('Nationality', ''), 'income': _num(r.get('AverageIncome')),
        'src_fund1': r.get('SourceFund', ''), 'lain1': r.get('SourceFundOther', ''),
        'comp_name': r.get('CompanyName', ''), 'ocu_type': r.get('BUSINESS_TYPE', ''),
        'update_by': r.get('UpdateBy', ''), 'last_update': last_update.strftime('%d-%m-%Y') if last_update else '',
        'bo_address': id_addr.get('ADDRESS', ''), 'area_cd': id_addr.get('AREA_CD', ''),
        'city1': id_addr.get('CITY', ''), 'kecamatan1': id_addr.get('KECAMATAN', ''),
        'kelurahan1': id_addr.get('KELURAHAN', ''), 'rt1': id_addr.get('RT', ''), 'rw1': id_addr.get('RW', ''),
        'zipcode1': id_addr.get('ZIPCODE', ''), 'fax1': id_addr.get('FAX', ''), 'phone1': id_addr.get('PHONE', ''),
        'add_address': add_addr.get('ADDRESS', ''), 'add_city': add_addr.get('CITY', ''),
        'add_phone': add_addr.get('PHONE', ''), 'add_post': add_addr.get('ZIPCODE', ''),
        'add_fax': add_addr.get('FAX', ''),
        'comp_address': office_addr.get('ADDRESS', ''), 'comp_phone': office_addr.get('PHONE', ''),
    }

def _load_pr_from_customer(apless: str) -> dict:
    rows = _exec_rows(
        """SELECT ca.LESSEE_NM, ca.Lessee_Cat, ca.ADDRESS1, kec.Desc_Name AS KECAMATAN,
           kel.Desc_Name AS KELURAHAN, cda.RT, cda.RW, ca.CITY1, ca.ZipCode1, ca.PHONE2,
           ca.Mobile_phone1, ca.EMAIL1, ca.Area_CD, ca.Fax1, ca.PLACEBIRTH, ca.TGLBIRTH,
           ca.GENDER, ca.MARITAL, ca.Citizen, ca.Nationality, ca.ALIAS_NAME, cld.BUSINESS_TYPE
           FROM CAFLESS ca WITH (NOLOCK)
                LEFT JOIN CAFLESS_DETAIL_ADDRESS cda ON ca.APLESS = cda.APLESS
                LEFT JOIN CAFLESS_DETAIL cld ON ca.APLESS = cld.APLESS
                LEFT JOIN Mst_Kelurahan kel ON kel.Kelurahan_CD = cda.KELURAHAN
                LEFT JOIN Mst_Kecamatan kec ON kec.Kecamatan_CD = cda.KECAMATAN
           WHERE ca.APLESS = ?""",
        [apless])
    r = rows[0] if rows else {}

    addr_rows = _exec_rows(
        "SELECT ADDRESS3, CITY3, PHONE3, ZipCode3, Fax3, ADDRESS1, CITY1, PHONE2, ZipCode1, Fax1 "
        "FROM CAFLESS WITH (NOLOCK) WHERE APLESS = ?", [apless])
    addr = addr_rows[0] if addr_rows else {}
    if addr.get('ADDRESS3'):
        add_address, add_city, add_phone = addr.get('ADDRESS3'), addr.get('CITY3'), addr.get('PHONE3')
        add_post, add_fax = addr.get('ZipCode3'), addr.get('Fax3')
    else:
        add_address, add_city, add_phone = addr.get('ADDRESS1'), addr.get('CITY1'), addr.get('PHONE2')
        add_post, add_fax = addr.get('ZipCode1'), addr.get('Fax1')

    hist_rows = _exec_rows(
        "SELECT TOP 1 Company, Company_Address, Phone FROM CAFLESS_History WITH (NOLOCK) "
        "WHERE APLESS = ? ORDER BY ID DESC", [apless])
    hist = hist_rows[0] if hist_rows else {}

    surv_rows = _exec_rows(
        "SELECT TOP 1 a.FIX_INC_SOURCE, a.FIX_SOURCE_REMARK, a.TOT_INC_YEAR FROM CAFSURV_PR a WITH (NOLOCK) "
        "INNER JOIN CAFCONT b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO WHERE b.APLESS = ? ORDER BY b.CREATE_DATE DESC",
        [apless])
    surv = surv_rows[0] if surv_rows else {}

    birth = r.get('TGLBIRTH')
    return {
        'bo_name': r.get('LESSEE_NM', ''), 'bo_cat': r.get('Lessee_Cat', ''), 'bo_address': r.get('ADDRESS1', ''),
        'kecamatan1': r.get('KECAMATAN', ''), 'kelurahan1': r.get('KELURAHAN', ''), 'rt1': r.get('RT', ''),
        'rw1': r.get('RW', ''), 'city1': r.get('CITY1', ''), 'alias': r.get('ALIAS_NAME', ''),
        'ocu_type': r.get('BUSINESS_TYPE', ''), 'zipcode1': r.get('ZipCode1', ''), 'phone1': r.get('PHONE2', ''),
        'mobile_phone1': r.get('Mobile_phone1', ''), 'email1': r.get('EMAIL1', ''),
        'area_cd': r.get('Area_CD', ''), 'fax1': r.get('Fax1', ''), 'placebirth': r.get('PLACEBIRTH', ''),
        'tglbirth': birth.strftime('%d-%m-%Y') if birth else '', 'gender': r.get('GENDER', ''),
        'marital': r.get('MARITAL', ''), 'citizen': r.get('Citizen', ''), 'nationality': r.get('Nationality', ''),
        'income': _num(surv.get('TOT_INC_YEAR')), 'src_fund1': surv.get('FIX_INC_SOURCE', ''),
        'lain1': surv.get('FIX_SOURCE_REMARK', ''),
        'add_address': add_address or '', 'add_city': add_city or '', 'add_phone': add_phone or '',
        'add_post': add_post or '', 'add_fax': add_fax or '',
        'comp_address': hist.get('Company_Address', ''), 'comp_phone': hist.get('Phone', ''),
        'comp_name': hist.get('Company', ''), 'update_by': '', 'last_update': '',
    }

def _load_pr_form(bo_id: str, bo_ide: str) -> dict:
    if bo_id and not bo_ide:
        return _load_pr_from_beneficiary_owner(bo_id)
    if bo_ide:
        if len(bo_ide) == 6:
            return _load_pr_from_customer(bo_ide)
        return _load_pr_from_beneficiary_owner(bo_ide)
    return {}

def _load_pt_from_beneficiary_owner(bo_id: str) -> dict:
    rows = _exec_rows(
        "SELECT BO_Name, BO_Cat, PlaceBirth, DateBirth, SourceFund, SourceFundOther, NPWP, SIUPNo, LOB, "
        "ContactName, ContactPosition, UpdateBy, LastUpdate, BUSINESS_TYPE FROM BENEFICIARY_OWNER WITH (NOLOCK) "
        "WHERE BO_ID = ?", [bo_id])
    r = rows[0] if rows else {}
    office_addr = _fetch_bo_address(bo_id, 'OFFICE')
    contact_addr = _fetch_bo_address(bo_id, 'CONTACT')
    birth = r.get('DateBirth')
    last_update = r.get('LastUpdate')
    return {
        'bo_name': r.get('BO_Name', ''), 'bo_cat': r.get('BO_Cat', ''), 'placebirth': r.get('PlaceBirth', ''),
        'tglbirth': birth.strftime('%d-%m-%Y') if birth else '', 'npwp': r.get('NPWP', ''),
        'siup': r.get('SIUPNo', ''), 'lob': r.get('LOB', ''), 'comp_position': r.get('ContactPosition', ''),
        'comp_name': r.get('ContactName', ''), 'src_fund1': r.get('SourceFund', ''),
        'lain1': r.get('SourceFundOther', ''), 'ocu_type': r.get('BUSINESS_TYPE', ''),
        'update_by': r.get('UpdateBy', ''), 'last_update': last_update.strftime('%d-%m-%Y') if last_update else '',
        'bo_address': office_addr.get('ADDRESS', ''), 'area_cd': office_addr.get('AREA_CD', ''),
        'city1': office_addr.get('CITY', ''), 'kecamatan1': office_addr.get('KECAMATAN', ''),
        'kelurahan1': office_addr.get('KELURAHAN', ''), 'rt1': office_addr.get('RT', ''),
        'rw1': office_addr.get('RW', ''), 'zipcode1': office_addr.get('ZIPCODE', ''),
        'fax1': office_addr.get('FAX', ''), 'phone1': office_addr.get('PHONE', ''),
        'comp_address': contact_addr.get('ADDRESS', ''),
    }

def _load_pt_from_customer(apless: str) -> dict:
    rows = _exec_rows(
        """SELECT ca.LESSEE_NM, ca.Lessee_Cat, ca.ADDRESS1, ca.ADDRESS2, kec.Desc_Name AS KECAMATAN,
           kel.Desc_Name AS KELURAHAN, cda.RT, cda.RW, cda.SIUP_NO, ca.CITY2, ca.ZipCode2, ca.PHONE1,
           ca.EMAIL1, ca.NPWP, ca.Occupation, ca.Area_CD, ca.Fax1, ca.Contact, ca.PLACEBIRTH, ca.TGLBIRTH,
           ca.LOB, cld.BUSINESS_TYPE
           FROM CAFLESS ca WITH (NOLOCK)
                LEFT JOIN CAFLESS_DETAIL_ADDRESS cda ON ca.APLESS = cda.APLESS
                LEFT JOIN CAFLESS_DETAIL cld ON ca.APLESS = cld.APLESS
                LEFT JOIN Mst_Kelurahan kel ON kel.Kelurahan_CD = cda.KELURAHAN
                LEFT JOIN Mst_Kecamatan kec ON kec.Kecamatan_CD = cda.KECAMATAN
           WHERE ca.APLESS = ?""",
        [apless])
    r = rows[0] if rows else {}
    surv_rows = _exec_rows(
        "SELECT TOP 1 a.MONTH_PROFIT_SOURCE, a.MONTH_PROFIT_REMARK FROM CAFSURV_PT a WITH (NOLOCK) "
        "INNER JOIN CAFCONT b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO WHERE b.APLESS = ? ORDER BY b.CREATE_DATE DESC",
        [apless])
    surv = surv_rows[0] if surv_rows else {}
    birth = r.get('TGLBIRTH')
    return {
        'bo_name': r.get('LESSEE_NM', ''), 'bo_cat': r.get('Lessee_Cat', ''),
        'comp_address': r.get('ADDRESS1', ''), 'bo_address': r.get('ADDRESS2', ''),
        'kecamatan1': r.get('KECAMATAN', ''), 'kelurahan1': r.get('KELURAHAN', ''), 'rt1': r.get('RT', ''),
        'rw1': r.get('RW', ''), 'placebirth': r.get('PLACEBIRTH', ''),
        'tglbirth': birth.strftime('%d-%m-%Y') if birth else '',
        'city1': r.get('CITY2', ''), 'zipcode1': r.get('ZipCode2', ''), 'phone1': r.get('PHONE1', ''),
        'ocu_type': r.get('BUSINESS_TYPE', ''), 'email1': r.get('EMAIL1', ''), 'npwp': r.get('NPWP', ''),
        'comp_position': r.get('Occupation', ''), 'area_cd': r.get('Area_CD', ''), 'fax1': r.get('Fax1', ''),
        'comp_name': r.get('Contact', ''), 'siup': r.get('SIUP_NO', ''), 'lob': r.get('LOB', ''),
        'src_fund1': surv.get('MONTH_PROFIT_SOURCE', ''), 'lain1': surv.get('MONTH_PROFIT_REMARK', ''),
        'update_by': '', 'last_update': '',
    }

def _load_pt_form(bo_id: str, bo_ide: str) -> dict:
    if bo_id and not bo_ide:
        return _load_pt_from_beneficiary_owner(bo_id)
    if bo_ide:
        if len(bo_ide) == 6:
            return _load_pt_from_customer(bo_ide)
        return _load_pt_from_beneficiary_owner(bo_ide)
    return {}

@edit_cam_by_ma_bp.route('/cam-edit-ma/detail')
@login_required
def detail():
    appl_no = request.args.get('applno', '').strip()
    bo_ide = request.args.get('bo_ide', '').strip()
    bo_type_override = request.args.get('bo_type', '').strip()
    if not appl_no:
        return jsonify({'error': 'applno is required'}), 400

    try:
        cam_rows = _exec_rows(
            "SELECT b.LESSEE_NM, b.Cust_Type, b.INDUS_CODE, a.apless FROM CAFCONT a WITH (NOLOCK) "
            "INNER JOIN CAFLESS b WITH (NOLOCK) ON a.apless = b.apless WHERE a.appl_no = ?", [appl_no])
        cam = cam_rows[0] if cam_rows else {}
        apless = cam.get('apless', '')

        link_rows = _exec_rows(
            "SELECT BO_ID, BO_TYPE FROM BENEFICIARY_LINK WITH (NOLOCK) WHERE appl_no = ?", [appl_no])
        link = link_rows[0] if link_rows else {}
        bo_id = link.get('BO_ID', '') or ''
        bo_type = bo_type_override or link.get('BO_TYPE', '') or ''

        if bo_type == 'PR':
            bo_form = _load_pr_form(bo_id, bo_ide)
        elif bo_type == 'PT':
            bo_form = _load_pt_form(bo_id, bo_ide)
        else:
            bo_form = {}

        occupation = _occupation_options(bo_form.get('bo_cat', ''))

        return jsonify({
            'cam': {'appl_no': appl_no, 'lessee_nm': cam.get('LESSEE_NM', ''), 'apless': apless},
            'bi_cust_type': cam.get('Cust_Type', '') or '',
            'industry': _build_industry_state(cam.get('INDUS_CODE', '') or ''),
            'bo_id': bo_id,
            'bo_type': bo_type,
            'bo_ide': bo_ide,
            'is_apless_source': len(bo_ide) == 6,
            'bo_form': bo_form,
            'occupation_options': occupation['options'],
            'occupation_disabled': occupation['disabled'],
        })
    except Exception as e:
        current_app.logger.exception("Edit CAM by MA detail error")
        return jsonify({'error': str(e)}), 500

def _next_bo_id() -> str:
    rows = _exec_rows("SELECT TOP 1 BO_ID FROM BENEFICIARY_OWNER WITH (NOLOCK) ORDER BY BO_ID DESC", [])
    last_id = rows[0]['BO_ID'] if rows else None
    numeric_part = int(last_id[2:8]) if last_id and len(last_id) >= 8 else 0
    return f"BO{numeric_part + 1:06d}"

def _validate_pr(fields: dict) -> list[str]:
    errors = []
    if not fields.get('bo_name'):
        errors.append('Beneficial Name must not be empty')
    if not fields.get('bo_cat'):
        errors.append('Beneficial Owner Category must not be empty')
    if not fields.get('bo_address'):
        errors.append('ID Address must not be empty')
    birth = _parse_date(fields.get('tglbirth', ''))
    if not birth or birth >= date.today():
        errors.append('Date of Birth not valid')
    return errors

def _validate_pt(fields: dict) -> list[str]:
    errors = []
    if not fields.get('bo_name'):
        errors.append('Beneficial Name must not be empty')
    if not fields.get('bo_cat'):
        errors.append('Beneficial Owner Category must not be empty')
    if not fields.get('bo_address'):
        errors.append('Address must not be empty')
    birth = _parse_date(fields.get('tglbirth', ''))
    if not birth or birth >= date.today():
        errors.append('Establishment Date not valid')
    return errors

def _update_pr_bo(bo_id: str, fields: dict, ocu_type: Optional[str], username: str, target_bo_id: str = None):
    _exec_write(
        "UPDATE BENEFICIARY_OWNER SET BO_ID=?, BO_Name=?, Alias=?, BO_Cat=?, Mobile=?, Email=?, IDCard=?, "
        "PlaceBirth=?, DateBirth=?, Gender=?, Marital=?, Citizenship=?, Nationality=?, AverageIncome=?, "
        "SourceFund=?, SourceFundOther=?, CompanyName=?, UpdateBy=?, LastUpdate=GETDATE(), BUSINESS_TYPE=? "
        "WHERE BO_ID=?",
        [target_bo_id or bo_id, fields.get('bo_name'), fields.get('alias'), fields.get('bo_cat'),
         fields.get('mobile_phone1'), fields.get('email1'), fields.get('id_card'), fields.get('placebirth'),
         _parse_date(fields.get('tglbirth', '')), fields.get('gender'), fields.get('marital'), fields.get('citizen'),
         fields.get('nationality'), fields.get('income'), fields.get('src_fund1'), fields.get('lain1'),
         fields.get('comp_name'), username, ocu_type, bo_id])

def _update_pr_addresses(bo_id: str, fields: dict, target_bo_id: str = None):
    tgt = target_bo_id or bo_id
    _exec_write(
        "UPDATE BENEFICIARY_OWNER_ADDRESS SET BO_ID=?, ADDRESS=?, AREA_CD=?, CITY=?, KECAMATAN=?, KELURAHAN=?, "
        "RT=?, RW=?, ZIPCODE=?, FAX=?, PHONE=? WHERE BO_ID=? AND ADDRESS_TYPE='ID'",
        [tgt, fields.get('bo_address'), fields.get('area_cd'), fields.get('city1'), fields.get('kecamatan1'),
         fields.get('kelurahan1'), fields.get('rt1'), fields.get('rw1'), fields.get('zipcode1'), fields.get('fax1'),
         fields.get('phone1'), bo_id])
    _exec_write(
        "UPDATE BENEFICIARY_OWNER_ADDRESS SET BO_ID=?, ADDRESS=?, CITY=?, ZIPCODE=?, FAX=?, PHONE=? "
        "WHERE BO_ID=? AND ADDRESS_TYPE='ADDITIONAL'",
        [tgt, fields.get('add_address'), fields.get('add_city'), fields.get('add_post'), fields.get('add_fax'),
         fields.get('add_phone'), bo_id])
    _exec_write(
        "UPDATE BENEFICIARY_OWNER_ADDRESS SET BO_ID=?, ADDRESS=?, PHONE=? WHERE BO_ID=? AND ADDRESS_TYPE='OFFICE'",
        [tgt, fields.get('comp_address'), fields.get('comp_phone'), bo_id])

def _insert_new_pr_bo(new_bo_id: str, appl_no: str, apless_source: str, fields: dict, ocu_type: Optional[str], username: str):
    _exec_write("INSERT INTO BENEFICIARY_LINK (APPL_NO, BO_ID, BO_TYPE) VALUES (?, ?, 'PR')", [appl_no, new_bo_id])
    _exec_write(
        "INSERT INTO BENEFICIARY_OWNER (BO_ID, BO_Name, Alias, BO_TP, BO_Cat, Mobile, Email, IDCard, PlaceBirth, "
        "DateBirth, Gender, Marital, Citizenship, Nationality, AverageIncome, SourceFund, SourceFundOther, "
        "CompanyName, NPWP, SIUPNo, LOB, ContactName, ContactPosition, APLESS, UpdateBy, LastUpdate, "
        "BUSINESS_TYPE) VALUES (?, ?, ?, 'PR', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, "
        "NULL, ?, ?, GETDATE(), ?)",
        [new_bo_id, fields.get('bo_name'), fields.get('alias'), fields.get('bo_cat'), fields.get('mobile_phone1'),
         fields.get('email1'), fields.get('id_card'), fields.get('placebirth'), _parse_date(fields.get('tglbirth', '')),
         fields.get('gender'), fields.get('marital'), fields.get('citizen'), fields.get('nationality'),
         fields.get('income'), fields.get('src_fund1'), fields.get('lain1'), fields.get('comp_name'),
         apless_source, username, ocu_type])
    _exec_write(
        "INSERT INTO BENEFICIARY_OWNER_ADDRESS (BO_ID, ADDRESS_TYPE, ADDRESS, AREA_CD, CITY, KECAMATAN, "
        "KELURAHAN, RT, RW, ZIPCODE, FAX, PHONE) VALUES (?, 'ID', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [new_bo_id, fields.get('bo_address'), fields.get('area_cd'), fields.get('city1'), fields.get('kecamatan1'),
         fields.get('kelurahan1'), fields.get('rt1'), fields.get('rw1'), fields.get('zipcode1'), fields.get('fax1'),
         fields.get('phone1')])
    _exec_write(
        "INSERT INTO BENEFICIARY_OWNER_ADDRESS (BO_ID, ADDRESS_TYPE, ADDRESS, CITY, ZIPCODE, FAX, PHONE) "
        "VALUES (?, 'ADDITIONAL', ?, ?, ?, ?, ?)",
        [new_bo_id, fields.get('add_address'), fields.get('add_city'), fields.get('add_post'), fields.get('add_fax'),
         fields.get('add_phone')])
    _exec_write(
        "INSERT INTO BENEFICIARY_OWNER_ADDRESS (BO_ID, ADDRESS_TYPE, ADDRESS, PHONE) VALUES (?, 'OFFICE', ?, ?)",
        [new_bo_id, fields.get('comp_address'), fields.get('comp_phone')])

def _save_pr(appl_no: str, bo_id: str, bo_ide: str, is_apless_source: bool, fields: dict, username: str) -> dict:
    errors = _validate_pr(fields)
    if errors:
        return {'success': False, 'errors': errors}

    ocu_type = None if fields.get('bo_cat') == 'PF' else (fields.get('ocu_type') or None)

    if bo_id and not bo_ide:
        _update_pr_bo(bo_id, fields, ocu_type, username)
        _update_pr_addresses(bo_id, fields)
        return {'success': True, 'bo_id': bo_id, 'ocu_type': ocu_type}

    if bo_ide:
        if is_apless_source:
            existing = _exec_rows("SELECT 1 AS ada FROM BENEFICIARY_OWNER WHERE apless = ?", [bo_ide])
            if existing:
                return {'success': False, 'errors': ['Data already exists as a Beneficial Owner. Please choose it from the link.']}
            new_bo_id = _next_bo_id()
            if not bo_id:
                _insert_new_pr_bo(new_bo_id, appl_no, bo_ide, fields, ocu_type, username)
            else:
                _exec_write("UPDATE BENEFICIARY_LINK SET BO_ID=?, BO_TYPE='PR' WHERE APPL_NO=?", [new_bo_id, appl_no])
                _update_pr_bo(bo_id, fields, ocu_type, username, target_bo_id=new_bo_id)
                _update_pr_addresses(bo_id, fields, target_bo_id=new_bo_id)
            return {'success': True, 'bo_id': new_bo_id, 'ocu_type': ocu_type}
        else:
            _exec_write("UPDATE BENEFICIARY_LINK SET BO_ID=?, BO_TYPE='PR' WHERE APPL_NO=?", [bo_ide, appl_no])
            _update_pr_bo(bo_ide, fields, ocu_type, username)
            _update_pr_addresses(bo_ide, fields)
            return {'success': True, 'bo_id': bo_ide, 'ocu_type': ocu_type}

    new_bo_id = _next_bo_id()
    _insert_new_pr_bo(new_bo_id, appl_no, bo_ide, fields, ocu_type, username)
    return {'success': True, 'bo_id': new_bo_id, 'ocu_type': ocu_type}

def _update_pt_bo(bo_id: str, fields: dict, ocu_type: Optional[str], username: str, target_bo_id: str = None):
    _exec_write(
        "UPDATE BENEFICIARY_OWNER SET BO_ID=?, BO_Name=?, BO_Cat=?, PlaceBirth=?, DateBirth=?, SourceFund=?, "
        "SourceFundOther=?, NPWP=?, SIUPNo=?, LOB=?, ContactName=?, ContactPosition=?, UpdateBy=?, "
        "LastUpdate=GETDATE(), BUSINESS_TYPE=? WHERE BO_ID=?",
        [target_bo_id or bo_id, fields.get('bo_name'), fields.get('bo_cat'), fields.get('placebirth'),
         _parse_date(fields.get('tglbirth', '')), fields.get('src_fund1'), fields.get('lain1'), fields.get('npwp'),
         fields.get('siup'), fields.get('lob'), fields.get('comp_name'), fields.get('comp_position'), username,
         ocu_type, bo_id])

def _update_pt_addresses(bo_id: str, fields: dict, target_bo_id: str = None):
    tgt = target_bo_id or bo_id
    _exec_write(
        "UPDATE BENEFICIARY_OWNER_ADDRESS SET BO_ID=?, ADDRESS=?, AREA_CD=?, CITY=?, KECAMATAN=?, KELURAHAN=?, "
        "RT=?, RW=?, ZIPCODE=?, FAX=?, PHONE=? WHERE BO_ID=? AND ADDRESS_TYPE='OFFICE'",
        [tgt, fields.get('bo_address'), fields.get('area_cd'), fields.get('city1'), fields.get('kecamatan1'),
         fields.get('kelurahan1'), fields.get('rt1'), fields.get('rw1'), fields.get('zipcode1'), fields.get('fax1'),
         fields.get('phone1'), bo_id])
    _exec_write(
        "UPDATE BENEFICIARY_OWNER_ADDRESS SET BO_ID=?, ADDRESS=? WHERE BO_ID=? AND ADDRESS_TYPE='CONTACT'",
        [tgt, fields.get('comp_address'), bo_id])

def _insert_new_pt_bo(new_bo_id: str, appl_no: str, apless_source: str, fields: dict, ocu_type: Optional[str], username: str):
    _exec_write("INSERT INTO BENEFICIARY_LINK (APPL_NO, BO_ID, BO_TYPE) VALUES (?, ?, 'PT')", [appl_no, new_bo_id])
    _exec_write(
        "INSERT INTO BENEFICIARY_OWNER (BO_ID, BO_Name, BO_TP, BO_Cat, PlaceBirth, DateBirth, SourceFund, "
        "SourceFundOther, NPWP, SIUPNo, LOB, ContactName, ContactPosition, APLESS, UpdateBy, LastUpdate, "
        "BUSINESS_TYPE) VALUES (?, ?, 'PT', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE(), ?)",
        [new_bo_id, fields.get('bo_name'), fields.get('bo_cat'), fields.get('placebirth'),
         _parse_date(fields.get('tglbirth', '')), fields.get('src_fund1'), fields.get('lain1'), fields.get('npwp'),
         fields.get('siup'), fields.get('lob'), fields.get('comp_name'), fields.get('comp_position'),
         apless_source, username, ocu_type])
    _exec_write(
        "INSERT INTO BENEFICIARY_OWNER_ADDRESS (BO_ID, ADDRESS_TYPE, ADDRESS, AREA_CD, CITY, KECAMATAN, "
        "KELURAHAN, RT, RW, ZIPCODE, FAX, PHONE) VALUES (?, 'OFFICE', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [new_bo_id, fields.get('bo_address'), fields.get('area_cd'), fields.get('city1'), fields.get('kecamatan1'),
         fields.get('kelurahan1'), fields.get('rt1'), fields.get('rw1'), fields.get('zipcode1'), fields.get('fax1'),
         fields.get('phone1')])
    _exec_write(
        "INSERT INTO BENEFICIARY_OWNER_ADDRESS (BO_ID, ADDRESS_TYPE, ADDRESS) VALUES (?, 'CONTACT', ?)",
        [new_bo_id, fields.get('comp_address')])

def _save_pt(appl_no: str, bo_id: str, bo_ide: str, is_apless_source: bool, fields: dict, username: str) -> dict:
    errors = _validate_pt(fields)
    if errors:
        return {'success': False, 'errors': errors}

    ocu_type = None if fields.get('bo_cat') == 'PF' else (fields.get('ocu_type') or None)

    if bo_id and not bo_ide:
        _update_pt_bo(bo_id, fields, ocu_type, username)
        _update_pt_addresses(bo_id, fields)
        return {'success': True, 'bo_id': bo_id, 'ocu_type': ocu_type}

    if bo_ide:
        if is_apless_source:
            existing = _exec_rows("SELECT 1 AS ada FROM BENEFICIARY_OWNER WHERE apless = ?", [bo_ide])
            if existing:
                return {'success': False, 'errors': ['Data already exists as a Beneficial Owner. Please choose it from the link.']}
            new_bo_id = _next_bo_id()
            if not bo_id:
                _insert_new_pt_bo(new_bo_id, appl_no, bo_ide, fields, ocu_type, username)
            else:
                _exec_write("UPDATE BENEFICIARY_LINK SET BO_ID=?, BO_TYPE='PT' WHERE APPL_NO=?", [new_bo_id, appl_no])
                _update_pt_bo(bo_id, fields, ocu_type, username, target_bo_id=new_bo_id)
                _update_pt_addresses(bo_id, fields, target_bo_id=new_bo_id)
            return {'success': True, 'bo_id': new_bo_id, 'ocu_type': ocu_type}
        else:
            _exec_write("UPDATE BENEFICIARY_LINK SET BO_ID=?, BO_TYPE='PT' WHERE APPL_NO=?", [bo_ide, appl_no])
            _update_pt_bo(bo_ide, fields, ocu_type, username)
            _update_pt_addresses(bo_ide, fields)
            return {'success': True, 'bo_id': bo_ide, 'ocu_type': ocu_type}

    new_bo_id = _next_bo_id()
    _insert_new_pt_bo(new_bo_id, appl_no, bo_ide, fields, ocu_type, username)
    return {'success': True, 'bo_id': new_bo_id, 'ocu_type': ocu_type}

def _clear_edd_bo_if_needed(appl_no: str, ocu_type: Optional[str]):
    business_type_char = (ocu_type or '')[3:4]
    if business_type_char != 'H':
        _exec_write("UPDATE Kuisioner_EDD SET EDD_BO = NULL WHERE APPL_NO = ?", [appl_no])

def _update_cafless(apless: str, bi_cust_type: str, ind_code5: str):
    _exec_write("UPDATE CAFLESS SET Cust_Type=?, INDUS_CODE=? WHERE APLESS=?", [bi_cust_type, ind_code5, apless])

@edit_cam_by_ma_bp.route('/cam-edit-ma/save', methods=['POST'])
@login_required
def save():
    data = request.get_json(force=True, silent=True) or {}
    appl_no = (data.get('appl_no') or '').strip()
    apless = (data.get('apless') or '').strip()
    bo_id = (data.get('bo_id') or '').strip()
    bo_ide = (data.get('bo_ide') or '').strip()
    bo_type = (data.get('bo_type') or '').strip()
    bi_cust_type = (data.get('bi_cust_type') or '').strip()
    ind_code5 = (data.get('ind_code5') or '').strip()
    is_apless_source = bool(data.get('is_apless_source'))
    username = session.get('username', '')

    if not appl_no or not apless:
        return jsonify({'success': False, 'errors': ['appl_no and apless are required']}), 400

    raw_conn = db.session.connection().connection
    try:
        result = {'success': True}
        if bo_type == 'PR':
            result = _save_pr(appl_no, bo_id, bo_ide, is_apless_source, data.get('pr', {}) or {}, username)
            if not result['success']:
                raw_conn.rollback()
                return jsonify(result), 400
            _clear_edd_bo_if_needed(appl_no, result.get('ocu_type'))
        elif bo_type == 'PT':
            result = _save_pt(appl_no, bo_id, bo_ide, is_apless_source, data.get('pt', {}) or {}, username)
            if not result['success']:
                raw_conn.rollback()
                return jsonify(result), 400
            _clear_edd_bo_if_needed(appl_no, result.get('ocu_type'))

        _update_cafless(apless, bi_cust_type, ind_code5)
        raw_conn.commit()
        return jsonify({'success': True, 'message': 'Successful', 'bo_id': result.get('bo_id', bo_id)})
    except Exception as e:
        raw_conn.rollback()
        current_app.logger.exception("Edit CAM by MA save error")
        return jsonify({'success': False, 'errors': [str(e)]}), 500