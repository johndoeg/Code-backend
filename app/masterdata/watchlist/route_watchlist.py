import os
import re
import uuid
from datetime import datetime, date
from flask import Blueprint, request, jsonify, session, current_app
from werkzeug.utils import secure_filename
from app import db
from sqlalchemy import text

watchlist_bp = Blueprint('watchlist', __name__, url_prefix='/MasterData')

UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', '/uploads/watchlist')
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'}
MAX_FILE_SIZE = 2 * 1024 * 1024

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def remove_special_chars(s: str) -> str:
    return re.sub(r'[^a-zA-Z0-9]', '', s or '')

def parse_date(value: str) -> date | None:
    if not value:
        return None
    for fmt in ('%Y-%m-%d', '%d-%m-%Y'):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None

def upload_file(file, prefix: str, apless: str) -> str | None:
    if not file or not allowed_file(file.filename):
        return None
    ext = file.filename.rsplit('.', 1)[1].lower()
    safe_prefix = re.sub(r'[^a-zA-Z0-9_\-]', '_', prefix)
    filename = secure_filename(f"{safe_prefix}_{uuid.uuid4().hex[:8]}.{ext}")
    dest = os.path.join(UPLOAD_FOLDER, apless or 'nonMLCI')
    os.makedirs(dest, exist_ok=True)
    file.save(os.path.join(dest, filename))
    return filename

def get_next_no() -> int:
    row = db.session.execute(
        text("SELECT ISNULL(MAX(No), 0) + 1 AS next_no FROM MCMOWatchList WITH (NOLOCK)")
    ).fetchone()
    return row.next_no

@watchlist_bp.route('/api/watchlist')
def list_entries():
    page       = request.args.get('page', 1, type=int)
    limit      = request.args.get('limit', 25, type=int)
    search_by  = request.args.get('search_by', '2').strip()
    search_val = request.args.get('search_val', '').strip()

    base_filter = "Flag_type = 'W' AND (flagdel <> '1' OR flagdel IS NULL)"

    if search_val:
        if search_by == '1':
            where  = f"{base_filter} AND ID_Card = :val"
            params = {'val': search_val}
        elif search_by == '3':
            where  = f"{base_filter} AND NPWP = :val"
            params = {'val': search_val}
        else:
            where  = f"{base_filter} AND Name LIKE :val"
            params = {'val': f'%{search_val}%'}
    else:
        where  = base_filter
        params = {}

    try:
        total = db.session.execute(
            text(f"SELECT COUNT(*) AS total FROM MCMOWatchList WITH (NOLOCK) WHERE {where}"),
            params
        ).fetchone().total

        offset = (page - 1) * limit
        rows = db.session.execute(
            text(f"""
                SELECT No, ID_Card, ISNULL(NPWP, '') AS NPWP,
                       Name, Address, ISNULL(APLESS, '') AS apless,
                       customer_type, ISNULL(reason_category, 0) AS reason_category
                FROM MCMOWatchList WITH (NOLOCK)
                WHERE {where}
                ORDER BY No
                OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
            """),
            {**params, 'offset': offset, 'limit': limit}
        ).fetchall()

        data = []
        for r in rows:
            ctype      = r.customer_type or 'PR'
            display_id = r.ID_Card if ctype == 'PR' else r.NPWP
            data.append({
                'no':              r.No,
                'display_id':      display_id or '',
                'id_card':         r.ID_Card or '',
                'npwp':            r.NPWP or '',
                'name':            r.Name or '',
                'address':         r.Address or '',
                'apless':          r.apless or '',
                'customer_type':   ctype,
                'reason_category': r.reason_category,
            })

        return jsonify({'data': data, 'total': total, 'page': page, 'limit': limit})

    except Exception:
        current_app.logger.exception('Watchlist list error')
        return jsonify({'data': [], 'total': 0}), 500

@watchlist_bp.route('/api/watchlist/reasons')
def get_reasons():
    try:
        rows = db.session.execute(text("""
            SELECT VALUE, DESC_VALUE
            FROM   MSTCOMBO WITH (NOLOCK)
            WHERE  CAT_VALUE = 'BLACKLIST_CATEGORY'
              AND  VALUE IN ('3', '6', '7')
            ORDER BY VALUE
        """)).fetchall()
        return jsonify([{
            'value':    r.VALUE,
            'label':    r.DESC_VALUE,
            'disabled': r.VALUE in ('6', '7'),
        } for r in rows])
    except Exception:
        current_app.logger.exception('Watchlist reasons error')
        return jsonify([]), 500

@watchlist_bp.route('/api/watchlist/groups')
def get_groups():
    try:
        rows = db.session.execute(text("""
            SELECT GrpCode, GrpName FROM CLFGROUP WITH (NOLOCK)
            WHERE  FLGDEL = '0'
            ORDER BY GrpName
        """)).fetchall()
        return jsonify([{'code': r.GrpCode, 'name': r.GrpName} for r in rows])
    except Exception:
        current_app.logger.exception('Watchlist groups error')
        return jsonify([]), 500

@watchlist_bp.route('/api/watchlist/save', methods=['POST'])
def save_entry():
    body        = request.get_json(force=True)
    cust_type   = body.get('customer_type', 'PR')
    name        = (body.get('name') or '').strip()
    address     = (body.get('address') or '').strip()
    phone       = (body.get('phone') or '').strip()
    alias_name  = (body.get('alias_name') or '').strip()
    reason      = (body.get('reason') or '').strip()
    reason_other= (body.get('reason_other') or '').strip()
    remark      = (body.get('remark') or '').strip()
    create_user = session.get('username', body.get('create_user', ''))
    create_date = parse_date(body.get('create_date') or datetime.today().strftime('%Y-%m-%d'))

    # PR fields
    id_card      = (body.get('id_card') or '').strip()
    birth_date   = parse_date(body.get('birth') or '')
    spouse_name  = (body.get('spouse_name') or '').strip()
    mother       = (body.get('mother') or '').strip()
    npwp_pr      = (body.get('npwp') or '').strip() if cust_type == 'PR' else ''

    # PT fields
    npwp_pt         = (body.get('npwp') or '').strip() if cust_type == 'PT' else ''
    es_birth_date   = parse_date(body.get('es_birth') or '')
    contact_person  = (body.get('contact_person') or '').strip()
    contact_address = (body.get('contact_address') or '').strip()
    group_code      = (body.get('group_code') or '').strip()

    npwp = npwp_pr if cust_type == 'PR' else npwp_pt

    errors = []
    if cust_type == 'PR' and not id_card:
        errors.append('ID Card must not be empty')
    if cust_type == 'PT' and not npwp_pt:
        errors.append('NPWP must not be empty')
    if not name:
        errors.append('Name must not be empty')
    if not address:
        errors.append('Address must not be empty')
    if not reason:
        errors.append('Reason must not be empty')
    if reason == '5' and not reason_other:
        errors.append('Reason Other must not be empty')
    if birth_date and birth_date > date.today():
        errors.append('DOB / Establishment Date not valid')
    if es_birth_date and es_birth_date > date.today():
        errors.append('DOB / Establishment Date not valid')
    if errors:
        return jsonify({'success': False, 'errors': errors}), 422

    clean_name    = remove_special_chars(name)
    clean_address = remove_special_chars(address)
    clean_id      = remove_special_chars(id_card)
    clean_npwp    = remove_special_chars(npwp_pt)

    try:
        if cust_type == 'PR':
            dup = db.session.execute(text("""
                SELECT Flag_Type FROM MCMOWatchList WITH (NOLOCK)
                WHERE dbo.RemoveSpecialChars(Name)    = :nm
                  AND dbo.RemoveSpecialChars(Address) = :addr
                  AND dbo.RemoveSpecialChars(ID_Card) = :idc
                  AND ISNULL(Flagdel, '0') = '0'
            """), {'nm': clean_name, 'addr': clean_address, 'idc': clean_id}).fetchone()

            if not dup:
                dup = db.session.execute(text("""
                    SELECT Flag_Type FROM MCMOWatchList WITH (NOLOCK)
                    WHERE dbo.RemoveSpecialChars(Name)    = :nm
                      AND dbo.RemoveSpecialChars(Address) = :addr
                      AND ISNULL(Flagdel, '0') = '0'
                """), {'nm': clean_name, 'addr': clean_address}).fetchone()
        else:
            dup = db.session.execute(text("""
                SELECT Flag_Type FROM MCMOWatchList WITH (NOLOCK)
                WHERE dbo.RemoveSpecialChars(Name)    = :nm
                  AND dbo.RemoveSpecialChars(Address) = :addr
                  AND dbo.RemoveSpecialChars(NPWP)   = :npwp
                  AND ISNULL(Flagdel, '0') = '0'
            """), {'nm': clean_name, 'addr': clean_address, 'npwp': clean_npwp}).fetchone()

        if dup:
            label = 'Watchlist' if dup.Flag_Type == 'W' else 'Blacklist'
            return jsonify({'success': False, 'errors': [f'Customer already registered in {label}']}), 409

        no             = get_next_no()
        insert_birth   = birth_date.strftime('%Y-%m-%d') if birth_date else None
        insert_esbirth = es_birth_date.strftime('%Y-%m-%d') if es_birth_date else None
        insert_date    = create_date.strftime('%Y-%m-%d') if create_date else None

        if cust_type == 'PR':
            db.session.execute(text("""
                INSERT INTO MCMOWatchList
                    (No, Name, Address, ID_Card, Phone, CreateUser, CreateDate,
                     Reason, DOB, Flag_type, Customer_Type, Spouse_Name, FlagDel,
                     Mother, Reason_Category, Reason_Other, NPWP)
                VALUES
                    (:no, :name, :address, :id_card, :phone, :create_user, :create_date,
                     :remark, :birth, 'W', 'PR', :spouse, '0',
                     :mother, :reason, :reason_other, :npwp)
            """), {
                'no': no, 'name': name, 'address': address, 'id_card': id_card,
                'phone': phone, 'create_user': create_user, 'create_date': insert_date,
                'remark': remark, 'birth': insert_birth, 'spouse': spouse_name,
                'mother': mother, 'reason': reason, 'reason_other': reason_other,
                'npwp': npwp_pr,
            })
        else:
            db.session.execute(text("""
                INSERT INTO MCMOWatchList
                    (No, Name, Address, Phone, CreateUser, CreateDate, Reason,
                     ContactPerson, ContactAddress, DOB, Flag_type, Customer_Type,
                     FlagDel, Contact_Group, Reason_Category, Reason_Other, NPWP)
                VALUES
                    (:no, :name, :address, :phone, :create_user, :create_date, :remark,
                     :contact_person, :contact_address, :esbirth, 'W', 'PT', '0',
                     :group_code, :reason, :reason_other, :npwp)
            """), {
                'no': no, 'name': name, 'address': address, 'phone': phone,
                'create_user': create_user, 'create_date': insert_date,
                'remark': remark, 'contact_person': contact_person,
                'contact_address': contact_address, 'esbirth': insert_esbirth,
                'group_code': group_code, 'reason': reason,
                'reason_other': reason_other, 'npwp': npwp_pt,
            })

        if alias_name and cust_type == 'PR':
            alias_id_row = db.session.execute(
                text("SELECT ISNULL(COUNT(ID), 0) + 1 AS next_id FROM MCMOWATCHLIST_ALIASNM")
            ).fetchone()
            db.session.execute(text("""
                INSERT INTO MCMOWATCHLIST_ALIASNM (No, ID, Name)
                VALUES (:no, :id, :alias)
            """), {'no': no, 'id': alias_id_row.next_id, 'alias': alias_name})

        db.session.commit()
        return jsonify({'success': True, 'no': no}), 201

    except Exception:
        db.session.rollback()
        current_app.logger.exception('Watchlist save error')
        return jsonify({'success': False, 'errors': ['An unexpected error occurred']}), 500

@watchlist_bp.route('/api/watchlist/delete', methods=['POST'])
def delete_entry():
    no            = request.form.get('no', '').strip()
    reason_delete = request.form.get('reason_delete', '').strip()
    delete_by     = session.get('username', request.form.get('deleteby', ''))
    file          = request.files.get('attachment_delete')

    errors = []
    if not no:
        errors.append('Record number is required')
    if not reason_delete:
        errors.append('Fill in the reason first')
    if not file or file.filename == '':
        errors.append('Upload the supporting file first')
    if errors:
        return jsonify({'success': False, 'errors': errors}), 422

    file.seek(0, 2)
    if file.tell() > MAX_FILE_SIZE:
        return jsonify({'success': False, 'errors': ['File size exceeds 2 MB']}), 413
    file.seek(0)

    if not allowed_file(file.filename):
        return jsonify({'success': False, 'errors': ['Invalid file type']}), 415

    try:
        row = db.session.execute(
            text("SELECT ISNULL(APLESS, 'nonMLCI') AS apless FROM MCMOWatchList WITH (NOLOCK) WHERE No = :no AND Flag_type = 'W'"),
            {'no': no}
        ).fetchone()
        if not row:
            return jsonify({'success': False, 'errors': ['Record not found']}), 404

        stored_name = upload_file(file, prefix=f'watchlist-{no}', apless=row.apless)
        if not stored_name:
            return jsonify({'success': False, 'errors': ['File upload failed']}), 500

        db.session.execute(text("""
            UPDATE MCMOWatchList
            SET    flagdel       = '1',
                   attachment    = :attachment,
                   deleteby      = :deleteby,
                   Reason_Delete = :reason,
                   DeleteDate    = SYSDATETIME()
            WHERE  No            = :no
              AND  flag_type     = 'W'
        """), {
            'attachment': stored_name,
            'deleteby':   delete_by,
            'reason':     reason_delete,
            'no':         no,
        })
        db.session.commit()
        return jsonify({'success': True})

    except Exception:
        db.session.rollback()
        current_app.logger.exception('Watchlist delete error')
        return jsonify({'success': False, 'errors': ['An unexpected error occurred']}), 500