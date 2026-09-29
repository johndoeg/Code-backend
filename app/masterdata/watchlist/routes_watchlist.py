import json
import re
import uuid
from datetime import date, datetime

from flask import Blueprint, request, jsonify, session, current_app, send_from_directory
from sqlalchemy import text

from app import db
from app.auth.decorators import login_required
from app.utils.helpers.ahing_query import (
    save_blacklist_image, save_general_attachment, save_ppatk_file, delete_blacklist_file,
)
from app.utils.helpers.base_format import fmt_date

watchlist_bp = Blueprint('watchlist', __name__, url_prefix='/MasterData')

MAX_PAGE_LIMIT = 200
MAX_FILE_SIZE = 2_000_000
MAX_PPATK_FILES = 3
ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/pjpeg', 'image/x-png', 'image/png', 'image/gif'}

BOD_OS_CODE = 'PT02'
BOC_OS_CODE = 'PT03'
BOD_OTHER_VALUE = '5'
BOC_OTHER_VALUE = '10'

ENTRY_REASONS = ('3', '6', '7')
CORSEC_REASON = '8'

def _strip_special(value: str) -> str:
    return re.sub(r'[^a-zA-Z0-9]', '', value or '')

def _parse_date(raw: str, errors: list):
    raw = (raw or '').strip()
    if not raw:
        return None
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        errors.append("DOB / Establishment Date not valid")
        return None
    if parsed > date.today():
        errors.append("DOB / Establishment Date not valid")
        return None
    return parsed

def _upload_folder(key: str) -> str:
    folder = current_app.config.get(key)
    if not folder:
        raise ValueError(f"{key} is not configured")
    return folder

def _lookup_apless(name: str, address: str) -> str:
    row = db.session.execute(
        text("SELECT apless FROM cafless WITH(NOLOCK) WHERE LESSEE_NM LIKE :name AND [address1] LIKE :address"),
        {"name": name, "address": address}
    ).fetchone()
    return row.apless if row and row.apless else "nonMLCI"

def _next_no() -> int:
    row = db.session.execute(
        text("SELECT ISNULL(MAX(No), 0) + 1 AS next_no FROM MCMOWatchList WITH(UPDLOCK, HOLDLOCK)")
    ).fetchone()
    return row.next_no

def _insert_alias(no: int, alias_name: str):
    row = db.session.execute(
        text("SELECT ISNULL(MAX(ID), 0) + 1 AS next_id FROM MCMOWATCHLIST_ALIASNM WITH(UPDLOCK, HOLDLOCK)")
    ).fetchone()
    db.session.execute(
        text("INSERT INTO MCMOWATCHLIST_ALIASNM (NO, ID, NAME) VALUES (:no, :id, :name)"),
        {"no": no, "id": row.next_id, "name": alias_name}
    )

def _validate_core(data: dict, customer_type: str, reason: str) -> tuple:
    errors = []

    if customer_type == 'PR' and not (data.get('id_card') or '').strip():
        errors.append("ID Card must not empty")
    if not (data.get('name') or '').strip():
        errors.append("Name must not empty")
    if not (data.get('address') or '').strip():
        errors.append("Address must not empty")
    if not reason:
        errors.append("Reason Category must not empty")
    if reason == '5' and not (data.get('reason_other') or '').strip():
        errors.append("Reason Other must not empty")

    dob = _parse_date(data.get('birth'), errors) if customer_type == 'PR' else None
    est = _parse_date(data.get('es_birth'), errors) if customer_type == 'PT' else None

    return errors, dob, est

def _validate_members(members: list) -> list:
    errors = []
    for entry in members:
        name = (entry.get('name') or '').strip()
        if not name:
            continue
        if not (entry.get('bod_position') or '').strip() and not (entry.get('boc_position') or '').strip():
            errors.append(f"BOD or BOC position must be selected for {name}")
    return errors

def _member_image(files, index: int, subject_name: str, member_name: str, apless: str, errors: list):
    file = files.get(f'member_image_{index}')
    if not file or not file.filename:
        return None

    file.seek(0, 2)
    size = file.tell()
    file.seek(0)

    if file.mimetype not in ALLOWED_IMAGE_TYPES:
        errors.append(f"{file.filename}: only JPEG, PNG or GIF images are allowed")
        return None
    if size > MAX_FILE_SIZE:
        errors.append(f"{file.filename}: file size exceeds Maximum Upload Limit")
        return None

    suffix = f"-watchlist{subject_name}_{member_name}".replace(".", "_")
    return save_blacklist_image(file, suffix, apless, _upload_folder('UPLOAD_FOLDER_BLACKLIST'))

def _save_members(subject_name, npwp, customer_type, members, files, apless,
                  old_name=None, old_npwp=None):
   
    if customer_type != 'PT':
        return []

    errors = []

    if old_name is not None:
        db.session.execute(
            text("DELETE FROM CAFORGSTRUCT_Blacklist WHERE NPWP = :npwp AND Blacklist_NM = :name"),
            {"npwp": old_npwp, "name": old_name}
        )

    for i, entry in enumerate(members):
        member_name = (entry.get('name') or '').strip()
        if not member_name:
            continue

        bod_pos = (entry.get('bod_position') or '').strip()
        boc_pos = (entry.get('boc_position') or '').strip()
        other = (entry.get('other') or '').strip()

        if bod_pos:
            os_code = BOD_OS_CODE
            position = other if bod_pos == BOD_OTHER_VALUE else bod_pos
        elif boc_pos:
            os_code = BOC_OS_CODE
            position = other if boc_pos == BOC_OTHER_VALUE else boc_pos
        else:
            continue

        uploaded = _member_image(files, i, subject_name, member_name, apless, errors)
        image = uploaded if uploaded else (entry.get('image') or None)

        db.session.execute(
            text("""
                INSERT INTO CAFORGSTRUCT_Blacklist
                    (Blacklist_NM, MANAGEMENT_NM, POSITION, OS_CODE, NPWP, ADDRESS, CITY, ID_CARD, IMAGES)
                VALUES
                    (:bn, :mn, :pos, :os_code, :npwp, :addr, :city, :idc, :img)
            """),
            {
                "bn": subject_name, "mn": member_name, "pos": position, "os_code": os_code,
                "npwp": npwp,
                "addr": (entry.get('address') or '').strip() or None,
                "city": (entry.get('city') or '').strip() or None,
                "idc": (entry.get('id_card') or '').strip() or None,
                "img": image,
            }
        )

    return errors

def _load_members(subject_name: str, npwp: str) -> list:
    known = {
        (r.OS_CODE, r.ID_OS_POSITION)
        for r in db.session.execute(
            text("SELECT OS_CODE, ID_OS_POSITION FROM MSTOS_POSITION WITH(NOLOCK) WHERE OS_CODE IN (:bod, :boc)"),
            {"bod": BOD_OS_CODE, "boc": BOC_OS_CODE}
        ).fetchall()
    }

    rows = db.session.execute(
        text("""
            SELECT ID_Blacklist, MANAGEMENT_NM, POSITION, OS_CODE, [ADDRESS], CITY, ID_CARD, IMAGES
            FROM CAFORGSTRUCT_Blacklist WITH(NOLOCK)
            WHERE Blacklist_NM = :name AND NPWP = :npwp
            ORDER BY OS_CODE, ID_Blacklist
        """),
        {"name": subject_name, "npwp": npwp}
    ).fetchall()

    members = []
    for r in rows:
        is_known = (r.OS_CODE, r.POSITION) in known
        bod_position = boc_position = other = ""
        if r.OS_CODE == BOD_OS_CODE:
            bod_position = r.POSITION if is_known else BOD_OTHER_VALUE
            other = "" if is_known else (r.POSITION or "")
        elif r.OS_CODE == BOC_OS_CODE:
            boc_position = r.POSITION if is_known else BOC_OTHER_VALUE
            other = "" if is_known else (r.POSITION or "")

        members.append({
            "id_blacklist": r.ID_Blacklist,
            "os_code": r.OS_CODE,
            "name": r.MANAGEMENT_NM or "",
            "bod_position": bod_position or "",
            "boc_position": boc_position or "",
            "other": other,
            "id_card": r.ID_CARD or "",
            "address": r.ADDRESS or "",
            "city": r.CITY or "",
            "image": r.IMAGES or "",
        })
    return members

@watchlist_bp.route('/watchlist')
@login_required
def list_entries():
    page = max(request.args.get('page', 1, type=int), 1)
    limit = min(max(request.args.get('limit', 25, type=int), 1), MAX_PAGE_LIMIT)
    search_by = request.args.get('search_by', '2').strip()
    search_val = request.args.get('search_val', '').strip()

    where = "Flag_type = 'W' AND (flagdel <> '1' OR flagdel IS NULL)"
    params = {}

    if search_val:
        if search_by == '1':
            where += " AND ID_Card = :val"
            params['val'] = search_val
        elif search_by == '3':
            where += " AND NPWP = :val"
            params['val'] = search_val
        else:
            where += " AND Name LIKE :val"
            params['val'] = f'%{search_val}%'

    try:
        total = db.session.execute(
            text(f"SELECT COUNT(*) AS total FROM MCMOWatchList WITH(NOLOCK) WHERE {where}"),
            params
        ).fetchone().total

        rows = db.session.execute(
            text(f"""
                SELECT No, ID_Card, ISNULL(NPWP, '') AS NPWP, Name, Address,
                       ISNULL(APLESS, '') AS apless, customer_type,
                       ISNULL(reason_category, '') AS reason_category
                FROM MCMOWatchList WITH(NOLOCK)
                WHERE {where}
                ORDER BY No
                OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
            """),
            {**params, 'offset': (page - 1) * limit, 'limit': limit}
        ).fetchall()

        data = []
        for r in rows:
            ctype = r.customer_type or 'PR'
            category = str(r.reason_category or '').strip()
            data.append({
                'no': r.No,
                'display_id': (r.ID_Card if ctype == 'PR' else r.NPWP) or '',
                'id_card': r.ID_Card or '',
                'npwp': r.NPWP or '',
                'name': r.Name or '',
                'address': r.Address or '',
                'apless': r.apless or '',
                'customer_type': ctype,
                'reason_category': category,
            })

        return jsonify({'data': data, 'total': total, 'page': page, 'limit': limit})

    except Exception as e:
        current_app.logger.exception('Watchlist list error')
        return jsonify({'data': [], 'total': 0, 'error': str(e)}), 500

@watchlist_bp.route('/watchlist/reasons')
@login_required
def get_reasons():
    current = (request.args.get('current') or '').strip()
    values = list(ENTRY_REASONS)
    if current and current not in values:
        values.append(current)

    placeholders = ", ".join(f":v{i}" for i in range(len(values)))
    params = {f"v{i}": v for i, v in enumerate(values)}

    try:
        rows = db.session.execute(text(f"""
            SELECT VALUE, DESC_VALUE
            FROM MSTCOMBO WITH(NOLOCK)
            WHERE CAT_VALUE = 'BLACKLIST_CATEGORY' AND VALUE IN ({placeholders})
            ORDER BY VALUE
        """), params).fetchall()

        return jsonify([{
            'value': (r.VALUE or '').strip(),
            'label': r.DESC_VALUE,
            'disabled': (r.VALUE or '').strip() in ('6', '7') or (r.VALUE or '').strip() not in ENTRY_REASONS,
        } for r in rows])
    except Exception:
        current_app.logger.exception('Watchlist reasons error')
        return jsonify([]), 500

@watchlist_bp.route('/watchlist/groups')
@login_required
def get_groups():
    try:
        rows = db.session.execute(text("""
            SELECT GrpCode, GrpName FROM CLFGROUP WITH(NOLOCK)
            WHERE FLGDEL = '0' ORDER BY GrpName
        """)).fetchall()
        return jsonify([{'code': r.GrpCode, 'name': r.GrpName} for r in rows])
    except Exception:
        current_app.logger.exception('Watchlist groups error')
        return jsonify([]), 500

@watchlist_bp.route('/watchlist/positions')
@login_required
def get_positions():
    try:
        bod = db.session.execute(
            text("SELECT ID_OS_POSITION, [DESC] FROM MSTOS_POSITION WITH(NOLOCK) WHERE OS_CODE = :os ORDER BY ID_OS_POSITION"),
            {"os": BOD_OS_CODE}
        ).fetchall()
        boc = db.session.execute(
            text("SELECT ID_OS_POSITION, [DESC] FROM MSTOS_POSITION WITH(NOLOCK) WHERE OS_CODE = :os ORDER BY ID_OS_POSITION"),
            {"os": BOC_OS_CODE}
        ).fetchall()
        return jsonify({
            'bod_options': [{'value': r.ID_OS_POSITION, 'label': r.DESC or ''} for r in bod],
            'boc_options': [{'value': r.ID_OS_POSITION, 'label': r.DESC or ''} for r in boc],
        })
    except Exception:
        current_app.logger.exception('Watchlist positions error')
        return jsonify({'bod_options': [], 'boc_options': []}), 500

@watchlist_bp.route('/watchlist/corsec/prefill')
@login_required
def corsec_prefill():
   
    apless = (request.args.get('apless') or '').strip()
    customer_type = (request.args.get('customer_type') or 'PR').strip().upper()
    if not apless:
        return jsonify({'error': 'apless is required'}), 400

    try:
        if customer_type == 'PR':
            row = db.session.execute(text("""
                SELECT LESSEE_NM, ALIAS_NAME, ADDRESS1, PHONE2, ID_CARD, TGLBIRTH, NPWP, Spouse, Mother
                FROM cafless WITH(NOLOCK) WHERE apless = :apless
            """), {'apless': apless}).fetchone()
            if not row:
                return jsonify({'error': 'Application not found'}), 404
            data = {
                'name': row.LESSEE_NM or '', 'alias_name': row.ALIAS_NAME or '',
                'address': row.ADDRESS1 or '', 'phone': row.PHONE2 or '',
                'id_card': row.ID_CARD or '',
                'birth': fmt_date(row.TGLBIRTH, "%Y-%m-%d") if row.TGLBIRTH else '',
                'npwp': row.NPWP or '', 'spouse_name': row.Spouse or '',
                'mother': row.Mother or '', 'contact_person': '', 'contact_address': '',
                'group_code': '', 'es_birth': '',
            }
        else:
            row = db.session.execute(text("""
                SELECT LESSEE_NM, ADDRESS1, ADDRESS2, PHONE1, PHONE3, TGLBIRTH, Contact, GrpCode, NPWP
                FROM cafless WITH(NOLOCK) WHERE apless = :apless
            """), {'apless': apless}).fetchone()
            if not row:
                return jsonify({'error': 'Application not found'}), 404
            data = {
                'name': row.LESSEE_NM or '', 'alias_name': '',
                'address': row.ADDRESS1 or '', 'phone': row.PHONE1 or '',
                'id_card': '', 'birth': '', 'npwp': row.NPWP or '',
                'spouse_name': '', 'mother': '',
                'contact_person': row.Contact or '', 'contact_address': row.ADDRESS2 or '',
                'group_code': row.GrpCode or '',
                'es_birth': fmt_date(row.TGLBIRTH, "%Y-%m-%d") if row.TGLBIRTH else '',
            }

        members = []
        if customer_type == 'PT':
            rows = db.session.execute(text("""
                SELECT MANAGEMENT_NM, POS_DEEDNO, OS_CODE
                FROM CAFORGSTRUCT_DETAIL WITH(NOLOCK)
                WHERE APLESS = :apless AND OS_CODE IN (:bod, :boc)
                  AND period = (SELECT MAX(period) FROM CAFORGSTRUCT_DETAIL WITH(NOLOCK) WHERE APLESS = :apless)
                ORDER BY OS_CODE
            """), {'apless': apless, 'bod': BOD_OS_CODE, 'boc': BOC_OS_CODE}).fetchall()
            for r in rows:
                is_bod = r.OS_CODE == BOD_OS_CODE
                members.append({
                    'name': r.MANAGEMENT_NM or '',
                    'bod_position': r.POS_DEEDNO if is_bod else '',
                    'boc_position': '' if is_bod else r.POS_DEEDNO,
                    'other': '', 'id_card': '', 'address': '', 'city': '', 'image': '',
                })

        data.update({'apless': apless, 'customer_type': customer_type,
                     'reason': CORSEC_REASON, 'members': members})
        return jsonify(data)

    except Exception as e:
        current_app.logger.exception('Corsec prefill error')
        return jsonify({'error': str(e)}), 500

@watchlist_bp.route('/watchlist/save', methods=['POST'])
@login_required
def save_entry():
    body = request.get_json(silent=True) or {}

    cust_type = body.get('customer_type', 'PR')
    if cust_type not in ('PR', 'PT'):
        return jsonify({'success': False, 'errors': ['Customer Type must not empty']}), 422

    apless = (body.get('apless') or '').strip()
    reason = CORSEC_REASON if apless else (body.get('reason') or '').strip()

    name = (body.get('name') or '').strip()
    address = (body.get('address') or '').strip()
    npwp = _strip_special(body.get('npwp'))
    id_card = (body.get('id_card') or '').strip()
    alias_name = (body.get('alias_name') or '').strip()
    reason_other = (body.get('reason_other') or '').strip()
    remark = (body.get('remark') or '').strip()
    create_user = session.get('username', '')

    errors, birth, es_birth = _validate_core(body, cust_type, reason)
    if cust_type == 'PT' and not npwp:
        errors.append('NPWP must not be empty')
    if errors:
        return jsonify({'success': False, 'errors': errors}), 422

    try:
        clean_name = _strip_special(name)
        clean_address = _strip_special(address)

        if cust_type == 'PR':
            dup = db.session.execute(text("""
                SELECT TOP 1 Flag_Type FROM MCMOWatchList WITH(NOLOCK)
                WHERE dbo.RemoveSpecialChars(Name) = :nm
                  AND dbo.RemoveSpecialChars(Address) = :addr
                  AND dbo.RemoveSpecialChars(ID_Card) = :idc
                  AND ISNULL(Flagdel, '0') = '0'
            """), {'nm': clean_name, 'addr': clean_address, 'idc': _strip_special(id_card)}).fetchone()

            if not dup:
                dup = db.session.execute(text("""
                    SELECT TOP 1 Flag_Type FROM MCMOWatchList WITH(NOLOCK)
                    WHERE dbo.RemoveSpecialChars(Name) = :nm
                      AND dbo.RemoveSpecialChars(Address) = :addr
                      AND ISNULL(Flagdel, '0') = '0'
                """), {'nm': clean_name, 'addr': clean_address}).fetchone()
        else:
            dup = db.session.execute(text("""
                SELECT TOP 1 Flag_Type FROM MCMOWatchList WITH(NOLOCK)
                WHERE dbo.RemoveSpecialChars(Name) = :nm
                  AND dbo.RemoveSpecialChars(Address) = :addr
                  AND dbo.RemoveSpecialChars(NPWP) = :npwp
                  AND ISNULL(Flagdel, '0') = '0'
            """), {'nm': clean_name, 'addr': clean_address, 'npwp': npwp}).fetchone()

        if dup:
            label = 'Watchlist' if dup.Flag_Type == 'W' else 'Blacklist'
            return jsonify({'success': False, 'errors': [f'Customer sudah terdaftar di {label}']}), 409

        no = _next_no()

        if cust_type == 'PR':
            db.session.execute(text("""
                INSERT INTO MCMOWatchList
                    (No, Name, Address, ID_Card, Phone, CreateUser, CreateDate, Reason, DOB,
                     Flag_type, Customer_Type, Spouse_Name, FlagDel, Mother,
                     Reason_Category, Reason_Other, NPWP, APLESS)
                VALUES
                    (:no, :name, :address, :id_card, :phone, :create_user, GETDATE(), :remark, :birth,
                     'W', 'PR', :spouse, '0', :mother,
                     :reason, :reason_other, :npwp, :apless)
            """), {
                'no': no, 'name': name, 'address': address, 'id_card': id_card,
                'phone': (body.get('phone') or '').strip(), 'create_user': create_user,
                'remark': remark, 'birth': birth,
                'spouse': (body.get('spouse_name') or '').strip(),
                'mother': (body.get('mother') or '').strip(),
                'reason': reason, 'reason_other': reason_other,
                'npwp': npwp, 'apless': apless or None,
            })
        else:
            db.session.execute(text("""
                INSERT INTO MCMOWatchList
                    (No, Name, Address, Phone, CreateUser, CreateDate, Reason,
                     ContactPerson, ContactAddress, DOB, Flag_type, Customer_Type, FlagDel,
                     Contact_Group, Reason_Category, Reason_Other, NPWP, APLESS)
                VALUES
                    (:no, :name, :address, :phone, :create_user, GETDATE(), :remark,
                     :contact_person, :contact_address, :esbirth, 'W', 'PT', '0',
                     :group_code, :reason, :reason_other, :npwp, :apless)
            """), {
                'no': no, 'name': name, 'address': address,
                'phone': (body.get('phone') or '').strip(), 'create_user': create_user,
                'remark': remark,
                'contact_person': (body.get('contact_person') or '').strip(),
                'contact_address': (body.get('contact_address') or '').strip(),
                'esbirth': es_birth, 'group_code': (body.get('group_code') or '').strip(),
                'reason': reason, 'reason_other': reason_other,
                'npwp': npwp, 'apless': apless or None,
            })

        if alias_name and cust_type == 'PR':
            _insert_alias(no, alias_name)

        db.session.commit()
        return jsonify({'success': True, 'no': no}), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception('Watchlist save error')
        return jsonify({'success': False, 'errors': [str(e)]}), 500

@watchlist_bp.route('/watchlist/detail')
@login_required
def get_detail():
    no = request.args.get('no', type=int)
    if not no:
        return jsonify({'error': 'no is required'}), 400

    try:
        row = db.session.execute(text("""
            SELECT a.[No], a.Customer_Type, a.Name, b.NAME AS alias_name, a.Address, a.Phone, a.NPWP,
                   a.ID_Card, a.DOB, a.Spouse_Name, a.Mother, a.ContactPerson, a.ContactAddress,
                   a.Contact_Group, a.Reason_Category, a.Reason_Other, a.Reason, a.CreateUser,
                   a.CreateDate, a.LastUser, a.LastUpdate, a.Problem_Since, a.apless
            FROM MCMOWatchList a WITH(NOLOCK)
                LEFT JOIN MCMOWATCHLIST_ALIASNM b WITH(NOLOCK) ON a.[No] = b.[NO]
            WHERE a.[No] = :no AND a.Flag_type = 'W'
        """), {'no': no}).fetchone()

        if not row:
            return jsonify({'error': 'Record not found'}), 404

        apless = row.apless or ''
        is_pr = row.Customer_Type == 'PR'
        npwp = row.NPWP or ''
        category = str(row.Reason_Category or '').strip()

        files = db.session.execute(text("""
            SELECT File_Nm, File_Ext, File_Nm + '.' + File_Ext AS fname
            FROM CLFCONT_FILE WITH(NOLOCK)
            WHERE cat = 'WATCHLIST_PPATK' AND lease_no = :apless
        """), {'apless': apless}).fetchall() if apless else []

        return jsonify({
            'no': row.No,
            'customer_type': row.Customer_Type,
            'name': row.Name or '',
            'alias_name': row.alias_name or '',
            'address': row.Address or '',
            'phone': row.Phone or '',
            'npwp': npwp,
            'id_card': row.ID_Card or '',
            'birth': fmt_date(row.DOB, "%Y-%m-%d") if (is_pr and row.DOB) else '',
            'spouse_name': row.Spouse_Name or '',
            'mother': row.Mother or '',
            'es_birth': fmt_date(row.DOB, "%Y-%m-%d") if (not is_pr and row.DOB) else '',
            'contact_person': row.ContactPerson or '',
            'contact_address': row.ContactAddress or '',
            'group_code': row.Contact_Group or '',
            'reason_category': category,
            'reason_other': (row.Reason_Other or '').strip(),
            'remark': row.Reason or '',
            'problem_since': fmt_date(row.Problem_Since, "%Y-%m-%d") if row.Problem_Since else '',
            'create_user': row.CreateUser or '',
            'create_date': fmt_date(row.CreateDate, "%Y-%m-%d") if row.CreateDate else '',
            'last_user': row.LastUser or '',
            'last_update': fmt_date(row.LastUpdate, "%Y-%m-%d") if row.LastUpdate else '',
            'apless': apless,
            'members': _load_members(row.Name, npwp) if not is_pr else [],
            'ppatk_files': [{'file_nm': f.File_Nm, 'fname': f.fname} for f in files],
        })

    except Exception as e:
        current_app.logger.exception('Watchlist detail error')
        return jsonify({'error': str(e)}), 500

@watchlist_bp.route('/watchlist/update', methods=['POST'])
@login_required
def update_entry():
    try:
        try:
            d = json.loads(request.form.get('data', '{}')) if request.form.get('data') else (request.get_json(silent=True) or {})
        except ValueError:
            return jsonify({'errors': ['Malformed payload']}), 400

        no = d.get('no')
        if not no:
            return jsonify({'errors': ['no is required']}), 400

        existing = db.session.execute(text("""
            SELECT Customer_Type, Name, NPWP, Reason_Category, apless
            FROM MCMOWatchList WITH(NOLOCK)
            WHERE [No] = :no AND Flag_type = 'W' AND FlagDel = '0'
        """), {'no': no}).fetchone()

        if not existing:
            return jsonify({'errors': ['Record not found']}), 404

        cust_type = existing.Customer_Type
        old_name = existing.Name
        old_npwp = existing.NPWP or ''
        stored_category = str(existing.Reason_Category or '').strip()

        if stored_category in ('4', CORSEC_REASON):
            reason_category = stored_category
        else:
            reason_category = str(d.get('reason_category') or '').strip()

        name = (d.get('name') or '').strip()
        address = (d.get('address') or '').strip()
        npwp = _strip_special(d.get('npwp'))
        members = d.get('members', [])

        errors, birth, es_birth = _validate_core(
            {**d, 'id_card': d.get('id_card')}, cust_type, reason_category
        )
        if cust_type == 'PT' and reason_category != CORSEC_REASON:
            errors += _validate_members(members)
        if errors:
            return jsonify({'errors': errors}), 422

        username = session.get('username', '')

        if cust_type == 'PR':
            db.session.execute(text("""
                UPDATE MCMOWatchList SET
                    Name = :name, Address = :address, ID_Card = :id_card, DOB = :dob, Phone = :phone,
                    Spouse_Name = :spouse_name, Mother = :mother, LastUser = :last_user,
                    LastUpdate = SYSDATETIME(), Reason = :remark,
                    Reason_Category = :reason_category, Reason_Other = :reason_other, NPWP = :npwp
                WHERE [No] = :no AND FlagDel = '0' AND Flag_Type = 'W'
            """), {
                'name': name, 'address': address, 'id_card': (d.get('id_card') or '').strip(),
                'dob': birth, 'phone': (d.get('phone') or '').strip(),
                'spouse_name': (d.get('spouse_name') or '').strip(),
                'mother': (d.get('mother') or '').strip(), 'last_user': username,
                'remark': (d.get('remark') or '').strip(), 'reason_category': reason_category,
                'reason_other': (d.get('reason_other') or '').strip(), 'npwp': npwp, 'no': no,
            })

            alias_name = (d.get('alias_name') or '').strip()
            alias_row = db.session.execute(
                text("SELECT TOP 1 NAME FROM MCMOWATCHLIST_ALIASNM WITH(NOLOCK) WHERE NO = :no"),
                {'no': no}
            ).fetchone()
            if alias_row:
                db.session.execute(
                    text("UPDATE MCMOWATCHLIST_ALIASNM SET NAME = :alias WHERE NO = :no"),
                    {'alias': alias_name, 'no': no}
                )
            elif alias_name:
                _insert_alias(no, alias_name)
        else:
            db.session.execute(text("""
                UPDATE MCMOWatchList SET
                    Name = :name, Address = :address, Phone = :phone,
                    ContactPerson = :contact_person, ContactAddress = :contact_address,
                    Contact_Group = :group_code, DOB = :dob, LastUser = :last_user,
                    LastUpdate = SYSDATETIME(), Reason = :remark,
                    Reason_Category = :reason_category, Reason_Other = :reason_other, NPWP = :npwp
                WHERE [No] = :no AND FlagDel = '0' AND Flag_Type = 'W'
            """), {
                'name': name, 'address': address, 'phone': (d.get('phone') or '').strip(),
                'contact_person': (d.get('contact_person') or '').strip(),
                'contact_address': (d.get('contact_address') or '').strip(),
                'group_code': (d.get('group_code') or '').strip(), 'dob': es_birth,
                'last_user': username, 'remark': (d.get('remark') or '').strip(),
                'reason_category': reason_category,
                'reason_other': (d.get('reason_other') or '').strip(), 'npwp': npwp, 'no': no,
            })

        if cust_type == 'PT' and reason_category != CORSEC_REASON:
            apless = existing.apless or _lookup_apless(name, address)
            file_errors = _save_members(
                name, npwp, cust_type, members, request.files, apless,
                old_name=old_name, old_npwp=old_npwp
            )
            if file_errors:
                db.session.rollback()
                return jsonify({'errors': file_errors}), 422

        db.session.commit()
        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception('Watchlist update error')
        return jsonify({'errors': [str(e)]}), 500

@watchlist_bp.route('/watchlist/delete', methods=['POST'])
@login_required
def delete_entry():
    no = request.form.get('no', type=int)
    reason_delete = (request.form.get('reason_delete') or '').strip()
    file = request.files.get('attachment_delete')

    errors = []
    if not no:
        errors.append('Record number is required')
    if not reason_delete:
        errors.append('fill the reason first')
    if not file or not file.filename:
        errors.append('Upload the file first')
    if errors:
        return jsonify({'success': False, 'errors': errors}), 422

    file.seek(0, 2)
    if file.tell() > MAX_FILE_SIZE:
        return jsonify({'success': False, 'errors': ['File size exceeds 2 MB']}), 413
    file.seek(0)

    try:
        row = db.session.execute(text("""
            SELECT Name, Address, ISNULL(APLESS, '') AS apless
            FROM MCMOWatchList WITH(NOLOCK)
            WHERE No = :no AND Flag_type = 'W' AND (FlagDel <> '1' OR FlagDel IS NULL)
        """), {'no': no}).fetchone()

        if not row:
            return jsonify({'success': False, 'errors': ['Record not found']}), 404

        apless = row.apless or _lookup_apless(row.Name, row.Address)
        stored_name = save_general_attachment(
            file, f'watchlist-{no}', apless, _upload_folder('UPLOAD_FOLDER')
        )

        result = db.session.execute(text("""
            UPDATE MCMOWatchList
            SET flagdel = '1', attachment = :attachment, deleteby = :deleteby,
                Reason_Delete = :reason, DeleteDate = SYSDATETIME()
            WHERE No = :no AND flag_type = 'W' AND (FlagDel <> '1' OR FlagDel IS NULL)
        """), {
            'attachment': stored_name, 'deleteby': session.get('username', ''),
            'reason': reason_delete, 'no': no,
        })

        if result.rowcount == 0:
            db.session.rollback()
            return jsonify({'success': False, 'errors': ['Record not found']}), 404

        db.session.commit()
        return jsonify({'success': True})

    except ValueError as e:
        db.session.rollback()
        return jsonify({'success': False, 'errors': [str(e)]}), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception('Watchlist delete error')
        return jsonify({'success': False, 'errors': [str(e)]}), 500

@watchlist_bp.route('/watchlist/management/<int:id_blacklist>/image')
@login_required
def get_management_image(id_blacklist):
    try:
        row = db.session.execute(
            text("SELECT IMAGES FROM CAFORGSTRUCT_Blacklist WITH(NOLOCK) WHERE ID_Blacklist = :id"),
            {'id': id_blacklist}
        ).fetchone()

        if not row or not row.IMAGES:
            return jsonify({'error': 'No image found'}), 404

        return send_from_directory(_upload_folder('UPLOAD_FOLDER_BLACKLIST'), row.IMAGES)
    except Exception as e:
        current_app.logger.exception('Watchlist image error')
        return jsonify({'error': str(e)}), 500

@watchlist_bp.route('/watchlist/management/<int:id_blacklist>/image', methods=['DELETE'])
@login_required
def delete_management_image(id_blacklist):
   
    try:
        row = db.session.execute(
            text("SELECT IMAGES FROM CAFORGSTRUCT_Blacklist WITH(NOLOCK) WHERE ID_Blacklist = :id"),
            {'id': id_blacklist}
        ).fetchone()

        if not row or not row.IMAGES:
            return jsonify({'error': 'No image found'}), 404

        if not delete_blacklist_file(row.IMAGES, _upload_folder('UPLOAD_FOLDER_BLACKLIST')):
            current_app.logger.warning(
                'Watchlist member image %s not found on disk; clearing the reference anyway', row.IMAGES
            )

        db.session.execute(
            text("UPDATE CAFORGSTRUCT_Blacklist SET IMAGES = NULL WHERE ID_Blacklist = :id"),
            {'id': id_blacklist}
        )
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception('Watchlist delete image error')
        return jsonify({'error': str(e)}), 500

@watchlist_bp.route('/watchlist/ppatk')
@login_required
def get_ppatk_file():
   
    apless = (request.args.get('apless') or '').strip()
    file_nm = (request.args.get('file_nm') or '').strip()
    if not apless or not file_nm:
        return jsonify({'error': 'apless and file_nm are required'}), 400

    try:
        row = db.session.execute(text("""
            SELECT File_Nm + '.' + File_Ext AS fname
            FROM CLFCONT_FILE WITH(NOLOCK)
            WHERE cat = 'WATCHLIST_PPATK' AND lease_no = :apless AND File_Nm = :file_nm
        """), {'apless': apless, 'file_nm': file_nm}).fetchone()

        if not row:
            return jsonify({'error': 'File not found'}), 404

        return send_from_directory(_upload_folder('UPLOAD_FOLDER_PPATK'), row.fname)
    except Exception as e:
        current_app.logger.exception('PPATK fetch error')
        return jsonify({'error': str(e)}), 500

@watchlist_bp.route('/watchlist/upload-ppatk', methods=['POST'])
@login_required
def upload_ppatk():
    apless = (request.form.get('apless') or '').strip()
    file = request.files.get('fileppatk')
    if not apless or not file or not file.filename:
        return jsonify({'success': False, 'error': 'apless and fileppatk are required'}), 400

    file.seek(0, 2)
    if file.tell() > MAX_FILE_SIZE:
        return jsonify({'success': False, 'error': 'File size exceeds 2 MB'}), 413
    file.seek(0)

    try:
        count = db.session.execute(text("""
            SELECT COUNT(*) AS total FROM CLFCONT_FILE WITH(NOLOCK)
            WHERE cat = 'WATCHLIST_PPATK' AND lease_no = :apless
        """), {'apless': apless}).fetchone().total

        if count >= MAX_PPATK_FILES:
            return jsonify({'success': False, 'error': f'Maximum {MAX_PPATK_FILES} PPATK files'}), 400

        file_nm = f"{apless}-watchlistPPATK{uuid.uuid4().hex[:8]}"
        stored = save_ppatk_file(file, file_nm, _upload_folder('UPLOAD_FOLDER_PPATK'))
        stem, _, ext = stored.rpartition('.')

        db.session.execute(text("""
            INSERT INTO CLFCONT_FILE ([lease_no], [File_Nm], [File_Ext], [Cat])
            VALUES (:apless, :file_nm, :file_ext, 'WATCHLIST_PPATK')
        """), {'apless': apless, 'file_nm': stem, 'file_ext': ext})
        db.session.commit()

        return jsonify({'success': True, 'file_nm': stem, 'fname': stored})

    except ValueError as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception('PPATK upload error')
        return jsonify({'success': False, 'error': str(e)}), 500

@watchlist_bp.route('/watchlist/delete-ppatk', methods=['POST'])
@login_required
def delete_ppatk():
    d = request.get_json(silent=True) or {}
    file_nm = (d.get('file_nm') or '').strip()
    apless = (d.get('apless') or '').strip()
    if not file_nm or not apless:
        return jsonify({'error': 'file_nm and apless are required'}), 400

    try:
        row = db.session.execute(text("""
            SELECT File_Nm + '.' + File_Ext AS fname
            FROM CLFCONT_FILE WITH(NOLOCK)
            WHERE cat = 'WATCHLIST_PPATK' AND lease_no = :apless AND File_Nm = :file_nm
        """), {'apless': apless, 'file_nm': file_nm}).fetchone()

        if not row:
            return jsonify({'error': 'File not found'}), 404

        if not delete_blacklist_file(row.fname, _upload_folder('UPLOAD_FOLDER_PPATK')):
            current_app.logger.warning('PPATK file %s not found on disk; removing the row anyway', row.fname)

        db.session.execute(text("""
            DELETE FROM CLFCONT_FILE
            WHERE cat = 'WATCHLIST_PPATK' AND File_Nm = :file_nm AND lease_no = :apless
        """), {'file_nm': file_nm, 'apless': apless})
        db.session.commit()
        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception('PPATK delete error')
        return jsonify({'error': str(e)}), 500