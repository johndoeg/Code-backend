from __future__ import annotations

import os
import uuid
from datetime import date, datetime
from typing import Optional

from flask import Blueprint, jsonify, request, current_app, session

from app import db
from app.auth.decorators import login_required

watchlist_by_corsec_bp = Blueprint('watchlist_by_corsec', __name__, url_prefix='/MasterData')

REASON_CATEGORY_CORSEC = '8'
MAX_ATTACHMENTS = 3
MAX_ATTACHMENT_SIZE = 2_000_000

SEARCH_BY_ID_CARD = '1'
SEARCH_BY_NAME = '2'
SEARCH_BY_NPWP = '3'

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

def _exec(sql: str, params: list) -> None:
    raw_conn = db.session.connection().connection
    cursor = raw_conn.cursor()
    try:
        cursor.execute(sql, params)
    finally:
        cursor.close()

def _exec_scalar(sql: str, params: list):
    raw_conn = db.session.connection().connection
    cursor = raw_conn.cursor()
    try:
        cursor.execute(sql, params)
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        cursor.close()

def _fmt_date(val) -> Optional[str]:
    if isinstance(val, (date, datetime)):
        return val.strftime('%d-%m-%Y')
    return None

def _parse_date(raw: str) -> Optional[date]:
    raw = (raw or '').strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError:
        return None

def _format_npwp(npwp: Optional[str]) -> str:
    if not npwp:
        return '-'
    return (f"{npwp[0:2]}.{npwp[2:5]}.{npwp[5:8]}.{npwp[8:9]}"
            f"-{npwp[9:12]}.{npwp[12:16]}")

def _serialize_summary(r: dict) -> dict:
    lessee_type = (r.get('customer_type') or '').strip()
    identitas = r.get('ID_Card') if lessee_type == 'PR' else r.get('NPWP')
    return {
        'no': r.get('No'),
        'identitas': identitas or '-',
        'name': r.get('Name') or '-',
        'address': r.get('Address') or '-',
        'lessee_type': lessee_type,
        'reason_category': (r.get('reason_category') or '').strip(),
    }

def _serialize_detail(r: dict) -> dict:
    lessee_type = (r.get('Customer_Type') or '').strip()
    return {
        'no': r.get('No'),
        'apless': r.get('APLESS'),
        'lessee_type': lessee_type,
        'name': r.get('Name') or '',
        'alias_name': r.get('AliasName') or '',
        'address': r.get('Address') or '',
        'phone': r.get('Phone') or '',
        'id_card': r.get('ID_Card') or '',
        'npwp': r.get('NPWP') or '',
        'date_of_birth': _fmt_date(r.get('DOB')),
        'spouse_name': r.get('Spouse_Name') or '',
        'mothers_maiden_name': r.get('Mother') or '',
        'contact_person': r.get('ContactPerson') or '',
        'contact_address': r.get('ContactAddress') or '',
        'contact_group_code': r.get('Contact_Group') or '',
        'reason_category': (r.get('Reason_Category') or '').strip(),
        'reason_other': r.get('Reason_Other') or '',
        'remark': r.get('Reason') or '',
        'create_user': r.get('CreateUser') or '',
        'create_date': _fmt_date(r.get('CreateDate')),
        'last_user': r.get('LastUser') or '',
        'last_update': _fmt_date(r.get('LastUpdate')),
    }

_LIST_QUERY_BASE = """
    SELECT No, ID_Card, Name, Address, APLESS, customer_type, NPWP, reason_category
    FROM MCMOWatchList WITH (NOLOCK)
    WHERE Flag_type = 'W'
      AND (Flagdel <> '1' OR Flagdel IS NULL)
"""

@watchlist_by_corsec_bp.route('/watchlist-corsec/list')
@login_required
def list_entries():
    search_by = request.args.get('search_by', '').strip()
    search_val = request.args.get('search_val', '').strip()

    try:
        page = max(int(request.args.get('page', 1)), 1)
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = min(max(int(request.args.get('page_size', 20)), 1), 200)
    except (TypeError, ValueError):
        page_size = 20

    where = ""
    params: list = []

    if search_by == SEARCH_BY_ID_CARD and search_val:
        where = "AND ID_Card = ? AND Reason_Category = ?"
        params += [search_val, REASON_CATEGORY_CORSEC]
    elif search_by == SEARCH_BY_NAME and search_val:
        where = "AND Name LIKE ?"
        params.append(f"%{search_val}%")
    elif search_by == SEARCH_BY_NPWP and search_val:
        where = "AND NPWP = ?"
        params.append(search_val)

    count_sql = f"SELECT COUNT(*) FROM ({_LIST_QUERY_BASE} {where}) t"
    total = _exec_scalar(count_sql, params) or 0

    data_sql = f"{_LIST_QUERY_BASE} {where} ORDER BY Name ASC OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
    data_params = params + [(page - 1) * page_size, page_size]

    current_app.logger.debug("watchlist list query: %s | params=%s", data_sql, data_params)

    try:
        rows = _exec_rows(data_sql, data_params)
        return jsonify({
            'data': [_serialize_summary(r) for r in rows],
            'page': page,
            'page_size': page_size,
            'total': total,
            'total_pages': max((total + page_size - 1) // page_size, 1),
        })
    except Exception as e:
        current_app.logger.exception("Watchlist entry list error")
        return jsonify({'error': str(e)}), 500

@watchlist_by_corsec_bp.route('/watchlist-corsec/<int:no>')
@login_required
def get_entry(no: int):
    try:
        rows = _exec_rows(
            """
            SELECT a.No, a.APLESS, a.Customer_Type, a.Name, b.NAME AS AliasName,
                   a.Address, a.Phone, a.ID_Card, a.NPWP, a.DOB, a.Spouse_Name, a.Mother,
                   a.ContactPerson, a.ContactAddress, a.Contact_Group,
                   a.Reason_Category, a.Reason_Other, a.Reason,
                   a.CreateUser, a.CreateDate, a.LastUser, a.LastUpdate
            FROM MCMOWatchList a WITH (NOLOCK)
                LEFT JOIN MCMOWATCHLIST_ALIASNM b WITH (NOLOCK) ON a.[No] = b.[NO]
            WHERE a.[No] = ? AND a.Flag_type = 'W'
            """,
            [no],
        )
        if not rows:
            return jsonify({'error': 'Watchlist entry not found'}), 404
        return jsonify(_serialize_detail(rows[0]))
    except Exception as e:
        current_app.logger.exception("Watchlist entry detail error")
        return jsonify({'error': str(e)}), 500

def _check_duplicate(name: str, address: str, id_card: str, npwp: str,
                      lessee_type: str) -> Optional[str]:
    if lessee_type == 'PR':
        flag = _exec_scalar(
            """
            SELECT TOP 1 Flag_Type FROM MCMOWatchList WITH (NOLOCK)
            WHERE dbo.RemoveSpecialChars(Name) = dbo.RemoveSpecialChars(?)
                AND dbo.RemoveSpecialChars(Address) = dbo.RemoveSpecialChars(?)
                AND dbo.RemoveSpecialChars(ID_Card) = dbo.RemoveSpecialChars(?)
                AND Flagdel = '0'
            """,
            [name, address, id_card],
        )
        if flag:
            return flag

        return _exec_scalar(
            """
            SELECT TOP 1 Flag_Type FROM MCMOWatchList WITH (NOLOCK)
            WHERE dbo.RemoveSpecialChars(Name) = dbo.RemoveSpecialChars(?)
                AND dbo.RemoveSpecialChars(Address) = dbo.RemoveSpecialChars(?)
                AND Flagdel = '0'
            """,
            [name, address],
        )

    return _exec_scalar(
        """
        SELECT TOP 1 Flag_Type FROM MCMOWatchList WITH (NOLOCK)
        WHERE dbo.RemoveSpecialChars(Name) = dbo.RemoveSpecialChars(?)
            AND dbo.RemoveSpecialChars(Address) = dbo.RemoveSpecialChars(?)
            AND dbo.RemoveSpecialChars(NPWP) = dbo.RemoveSpecialChars(?)
            AND Flagdel = '0'
        """,
        [name, address, npwp],
    )

def _validate_entry_payload(payload: dict) -> list[str]:
    errors = []
    lessee_type = payload.get('lessee_type')
    if lessee_type not in ('PR', 'PT'):
        errors.append('Customer type (PR/PT) is required')
    if not payload.get('name'):
        errors.append('Name must not be empty')
    if lessee_type == 'PR' and not payload.get('id_card'):
        errors.append('ID Card must not be empty')
    if lessee_type == 'PT' and not payload.get('npwp'):
        errors.append('NPWP must not be empty')
    return errors

@watchlist_by_corsec_bp.route('/watchlist-corsec', methods=['POST'])
@login_required
def create_entry():
    payload = request.get_json(silent=True) or {}
    errors = _validate_entry_payload(payload)
    if errors:
        return jsonify({'errors': errors}), 400

    lessee_type = payload['lessee_type']
    name = payload.get('name', '')
    address = payload.get('address', '')
    id_card = payload.get('id_card', '')
    npwp = payload.get('npwp', '')

    dup_flag_type = _check_duplicate(name, address, id_card, npwp, lessee_type)
    if dup_flag_type == 'W':
        return jsonify({'error': 'Customer sudah terdaftar di Watchlist'}), 409
    if dup_flag_type == 'B':
        return jsonify({'error': 'Customer sudah terdaftar di Blacklist'}), 409

    username = session.get('username', '')
    dob = _parse_date(payload.get('date_of_birth', ''))

    try:
        next_no = (_exec_scalar("SELECT MAX(No) FROM MCMOWatchList WITH (NOLOCK)", []) or 0) + 1
        if lessee_type == 'PR':
            _exec(
                """
                INSERT INTO MCMOWatchList
                    (No, Name, Address, ID_Card, Phone, CreateUser, CreateDate, Reason, DOB,
                     Flag_type, Customer_Type, Spouse_Name, FlagDel, Mother,
                     Reason_Category, Reason_Other, NPWP, APLESS)
                VALUES (?, ?, ?, ?, ?, ?, SYSDATETIME(), ?, ?,
                        'W', 'PR', ?, '0', ?, ?, ?, ?, ?)
                """,
                [next_no, name, address, id_card, payload.get('phone', ''), username,
                 payload.get('remark', ''), dob,
                 payload.get('spouse_name', ''), payload.get('mothers_maiden_name', ''),
                 REASON_CATEGORY_CORSEC, payload.get('reason_other', ''), npwp,
                 payload.get('apless')],
            )
        else:
            _exec(
                """
                INSERT INTO MCMOWatchList
                    (No, Name, Address, Phone, CreateUser, CreateDate, Reason,
                     ContactPerson, ContactAddress, DOB, Flag_type, Customer_Type,
                     FlagDel, Contact_Group, Reason_Category, Reason_Other, NPWP, APLESS)
                VALUES (?, ?, ?, ?, ?, SYSDATETIME(), ?,
                        ?, ?, ?, 'W', 'PT',
                        '0', ?, ?, ?, ?, ?)
                """,
                [next_no, name, address, payload.get('phone', ''), username,
                 payload.get('remark', ''),
                 payload.get('contact_person', ''), payload.get('contact_address', ''), dob,
                 payload.get('contact_group_code', ''), REASON_CATEGORY_CORSEC,
                 payload.get('reason_other', ''), npwp, payload.get('apless')],
            )

        alias_name = payload.get('alias_name', '').strip()
        if alias_name:
            next_alias_id = (_exec_scalar(
                "SELECT COUNT(ID) FROM MCMOWATCHLIST_ALIASNM WITH (NOLOCK)", []) or 0) + 1
            _exec(
                "INSERT INTO MCMOWATCHLIST_ALIASNM (NO, ID, NAME) VALUES (?, ?, ?)",
                [next_no, next_alias_id, alias_name],
            )

        db.session.commit()
        return jsonify({'no': next_no, 'message': 'Successful'}), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Watchlist entry create error")
        return jsonify({'error': str(e)}), 500

@watchlist_by_corsec_bp.route('/watchlist-corsec/<int:no>', methods=['PUT'])
@login_required
def update_entry(no: int):
    payload = request.get_json(silent=True) or {}
    errors = _validate_entry_payload(payload)
    if errors:
        return jsonify({'errors': errors}), 400

    lessee_type = payload['lessee_type']
    username = session.get('username', '')
    dob = _parse_date(payload.get('date_of_birth', ''))

    try:
        if lessee_type == 'PR':
            _exec(
                """
                UPDATE MCMOWatchList SET
                    Name = ?, Address = ?, ID_Card = ?, DOB = ?, Phone = ?,
                    Spouse_Name = ?, Mother = ?, LastUser = ?, LastUpdate = SYSDATETIME(),
                    Reason = ?, Reason_Other = ?, NPWP = ?
                WHERE No = ? AND FlagDel = '0' AND Flag_Type = 'W'
                """,
                [payload.get('name', ''), payload.get('address', ''), payload.get('id_card', ''),
                 dob, payload.get('phone', ''), payload.get('spouse_name', ''),
                 payload.get('mothers_maiden_name', ''), username,
                 payload.get('remark', ''), payload.get('reason_other', ''),
                 payload.get('npwp', ''), no],
            )
        else:
            _exec(
                """
                UPDATE MCMOWatchList SET
                    Name = ?, Address = ?, Phone = ?, ContactPerson = ?, ContactAddress = ?,
                    DOB = ?, Contact_Group = ?, LastUser = ?, LastUpdate = SYSDATETIME(),
                    Reason = ?, Reason_Other = ?, NPWP = ?
                WHERE No = ? AND FlagDel = '0' AND Flag_Type = 'W'
                """,
                [payload.get('name', ''), payload.get('address', ''), payload.get('phone', ''),
                 payload.get('contact_person', ''), payload.get('contact_address', ''),
                 dob, payload.get('contact_group_code', ''), username,
                 payload.get('remark', ''), payload.get('reason_other', ''),
                 payload.get('npwp', ''), no],
            )

        alias_name = payload.get('alias_name', '').strip()
        if alias_name:
            existing = _exec_rows(
                "SELECT 1 FROM MCMOWATCHLIST_ALIASNM WITH (NOLOCK) WHERE No = ?", [no])
            if existing:
                _exec("UPDATE MCMOWATCHLIST_ALIASNM SET NAME = ? WHERE No = ?", [alias_name, no])
            else:
                next_alias_id = (_exec_scalar(
                    "SELECT COUNT(ID) FROM MCMOWATCHLIST_ALIASNM WITH (NOLOCK)", []) or 0) + 1
                _exec(
                    "INSERT INTO MCMOWATCHLIST_ALIASNM (NO, ID, NAME) VALUES (?, ?, ?)",
                    [no, next_alias_id, alias_name],
                )

        db.session.commit()
        return jsonify({'no': no, 'message': 'Successful'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Watchlist entry update error")
        return jsonify({'error': str(e)}), 500

@watchlist_by_corsec_bp.route('/watchlist-corsec/<int:no>/delete', methods=['POST'])
@login_required
def delete_entry(no: int):
    payload = request.get_json(silent=True) or {}
    reason = (payload.get('reason') or '').strip()
    if not reason:
        return jsonify({'error': 'Reason for delete must not be empty'}), 400

    username = session.get('username', '')

    try:
        _exec(
            """
            UPDATE MCMOWatchList
            SET FlagDel = '1', DeleteBy = ?, Reason_Delete = ?, DeleteDate = GETDATE()
            WHERE No = ? AND Flag_type = 'W'
            """,
            [username, reason, no],
        )
        db.session.commit()
        return jsonify({'no': no, 'message': 'Successful'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Watchlist entry delete error")
        return jsonify({'error': str(e)}), 500

_ALLOWED_ATTACHMENT_EXT = {'.pdf', '.doc', '.docx', '.xls', '.xlsx',
                            '.png', '.jpg', '.jpeg', '.gif'}

@watchlist_by_corsec_bp.route('/watchlist-corsec/<int:no>/attachments', methods=['GET'])
@login_required
def list_attachments(no: int):
    try:
        rows = _exec_rows(
            """
            SELECT File_Nm, File_Ext FROM CLFCONT_FILE WITH (NOLOCK)
            WHERE lease_no = (SELECT APLESS FROM MCMOWatchList WHERE No = ?)
              AND Cat = 'WATCHLIST_PPATK'
            """,
            [no],
        )
        return jsonify([f"{r['File_Nm']}.{r['File_Ext']}" for r in rows])
    except Exception as e:
        current_app.logger.exception("Watchlist attachment list error")
        return jsonify({'error': str(e)}), 500

@watchlist_by_corsec_bp.route('/watchlist-corsec/<int:no>/attachments', methods=['POST'])
@login_required
def upload_attachments(no: int):
    apless = _exec_scalar("SELECT APLESS FROM MCMOWatchList WHERE No = ?", [no])
    if apless is None:
        return jsonify({'error': 'Watchlist entry not found'}), 404

    existing_count = _exec_scalar(
        "SELECT COUNT(*) FROM CLFCONT_FILE WITH (NOLOCK) WHERE lease_no = ? AND Cat = 'WATCHLIST_PPATK'",
        [apless],
    ) or 0

    files = request.files.getlist('files')
    if existing_count + len(files) > MAX_ATTACHMENTS:
        return jsonify({'error': f'Maximum {MAX_ATTACHMENTS} supporting documents allowed'}), 400

    upload_dir = current_app.config.get('PPATK_UPLOAD_DIR')
    saved = []

    try:
        for f in files:
            if f.content_length and f.content_length > MAX_ATTACHMENT_SIZE:
                return jsonify({'error': 'File size exceeds maximum upload limit (2MB)'}), 400

            ext = os.path.splitext(f.filename or '')[1].lower()
            if ext not in _ALLOWED_ATTACHMENT_EXT:
                return jsonify({'error': f'Unsupported file type: {ext}'}), 400

            file_stem = f"{apless}-watchlistPPATK{uuid.uuid4().hex[:8]}"
            f.save(os.path.join(upload_dir, f"{file_stem}{ext}"))

            _exec(
                "INSERT INTO CLFCONT_FILE (lease_no, File_Nm, File_Ext, Cat) VALUES (?, ?, ?, 'WATCHLIST_PPATK')",
                [apless, file_stem, ext.lstrip('.')],
            )
            saved.append(f"{file_stem}{ext}")

        db.session.commit()
        return jsonify({'saved': saved}), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Watchlist attachment upload error")
        return jsonify({'error': str(e)}), 500

@watchlist_by_corsec_bp.route('/watchlist-corsec/<int:no>/attachments/<path:filename>', methods=['DELETE'])
@login_required
def delete_attachment(no: int, filename: str):
    safe_name = os.path.basename(filename)
    if not safe_name or safe_name != filename or '..' in filename:
        return jsonify({'error': 'Invalid filename'}), 400

    file_stem, _, file_ext = safe_name.rpartition('.')
    if not file_stem:
        return jsonify({'error': 'Invalid filename'}), 400

    apless = _exec_scalar("SELECT APLESS FROM MCMOWatchList WHERE No = ?", [no])
    if apless is None:
        return jsonify({'error': 'Watchlist entry not found'}), 404

    try:
        _exec(
            "DELETE FROM CLFCONT_FILE WHERE lease_no = ? AND Cat = 'WATCHLIST_PPATK' AND File_Nm = ?",
            [apless, file_stem],
        )
        db.session.commit()

        upload_dir = current_app.config.get('PPATK_UPLOAD_DIR')
        full_path = os.path.join(upload_dir, safe_name)
        if os.path.isfile(full_path) and os.path.abspath(full_path).startswith(os.path.abspath(upload_dir)):
            os.remove(full_path)

        return jsonify({'message': 'Successful'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Watchlist attachment delete error")
        return jsonify({'error': str(e)}), 500