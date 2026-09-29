import json
import os
import re
from datetime import date, datetime

from flask import Blueprint, jsonify, request, current_app, session, send_from_directory
from sqlalchemy import text

from app import db
from app.auth.decorators import login_required
from app.utils.helpers.ahing_query import (
    check_id_card_status, check_npwp_status,
    save_blacklist_image, save_general_attachment, delete_blacklist_file,
)
from app.utils.helpers.base_format import fmt_date

blacklist_bp = Blueprint('blacklist', __name__, url_prefix='/MasterData')

ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/pjpeg', 'image/x-png', 'image/png', 'image/gif'}
MAX_IMAGE_SIZE = 2_000_000
MAX_PAGE_LIMIT = 200

BOD_OS_CODE = 'PT02'
BOC_OS_CODE = 'PT03'
BOD_OTHER_VALUE = '5'
BOC_OTHER_VALUE = '10'

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

def _lookup_apless(name: str, address: str) -> str:
    row = db.session.execute(
        text("SELECT apless FROM cafless WITH(NOLOCK) WHERE LESSEE_NM LIKE :name AND [address1] LIKE :address"),
        {"name": name, "address": address}
    ).fetchone()
    return row.apless if row and row.apless else "nonMLCI"

def _validate_core(data: dict, customer_type: str) -> tuple:
    errors = []

    if customer_type == 'PR' and not (data.get('id_card') or '').strip():
        errors.append("ID Card must not empty")
    if not (data.get('name') or '').strip():
        errors.append("Name must not empty")
    if not (data.get('address') or '').strip():
        errors.append("Address must not empty")

    reason_category = (data.get('reason_category') or '').strip()
    if not reason_category:
        errors.append("Reason Category must not empty")
    if reason_category == '5' and not (data.get('reason_other') or '').strip():
        errors.append("Reason Other must not empty")

    dob = _parse_date(data.get('dob'), errors) if customer_type == 'PR' else None
    est = _parse_date(data.get('establishment_date'), errors) if customer_type == 'PT' else None

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

def _member_image(files, index: int, blacklist_name: str, member_name: str, apless: str, errors: list):
    file = files.get(f'member_image_{index}')
    if not file or not file.filename:
        return None

    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)

    if file.mimetype not in ALLOWED_IMAGE_TYPES:
        errors.append(f"{file.filename}: only JPEG, PNG or GIF images are allowed")
        return None
    if size > MAX_IMAGE_SIZE:
        errors.append(f"{file.filename}: file size exceeds Maximum Upload Limit")
        return None

    suffix = f"-blacklist_{blacklist_name}_{member_name}".replace(".", "_")
    return save_blacklist_image(file, suffix, apless, current_app.config['UPLOAD_FOLDER_BLACKLIST'])

def _save_members(blacklist_name, npwp, customer_type, members, files, apless,
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

        uploaded = _member_image(files, i, blacklist_name, member_name, apless, errors)
        image = uploaded if uploaded else (entry.get('image') or None)

        db.session.execute(
            text("""
                INSERT INTO CAFORGSTRUCT_Blacklist
                    (Blacklist_NM, MANAGEMENT_NM, POSITION, OS_CODE, NPWP, ADDRESS, CITY, ID_CARD, IMAGES)
                VALUES
                    (:bn, :mn, :pos, :os_code, :npwp, :addr, :city, :idc, :img)
            """),
            {
                "bn": blacklist_name,
                "mn": member_name,
                "pos": position,
                "os_code": os_code,
                "npwp": npwp,
                "addr": (entry.get('address') or '').strip() or None,
                "city": (entry.get('city') or '').strip() or None,
                "idc": (entry.get('id_card') or '').strip() or None,
                "img": image,
            }
        )

    return errors

@blacklist_bp.route('/blacklist/options')
@login_required
def get_options():
    try:
        reasons = db.session.execute(
            text("SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE = 'BLACKLIST_CATEGORY' AND VALUE NOT IN ('6','7') ORDER BY VALUE")
        ).fetchall()

        groups = db.session.execute(
            text("SELECT GrpCode, GrpName FROM CLFGROUP WITH(NOLOCK) WHERE FLGDEL = '0' ORDER BY GrpName")
        ).fetchall()

        bod_positions = db.session.execute(
            text("SELECT ID_OS_POSITION, [DESC] FROM MSTOS_POSITION WITH(NOLOCK) WHERE OS_CODE = :os ORDER BY ID_OS_POSITION"),
            {"os": BOD_OS_CODE}
        ).fetchall()

        boc_positions = db.session.execute(
            text("SELECT ID_OS_POSITION, [DESC] FROM MSTOS_POSITION WITH(NOLOCK) WHERE OS_CODE = :os ORDER BY ID_OS_POSITION"),
            {"os": BOC_OS_CODE}
        ).fetchall()

        return jsonify({
            "reasons": [{"value": (r.VALUE or '').strip(), "label": r.DESC_VALUE, "disabled": (r.VALUE or '').strip() == '4'} for r in reasons],
            "groups": [{"value": g.GrpCode, "label": g.GrpName} for g in groups],
            "bod_positions": [{"value": p.ID_OS_POSITION, "label": p.DESC} for p in bod_positions],
            "boc_positions": [{"value": p.ID_OS_POSITION, "label": p.DESC} for p in boc_positions],
        })
    except Exception as e:
        current_app.logger.exception("Options error")
        return jsonify({"error": str(e)}), 500

@blacklist_bp.route('/blacklist/equip-types')
@login_required
def get_equip_types():
    brand = request.args.get('brand', '').strip()
    if not brand:
        return jsonify([])

    rows = db.session.execute(
        text("SELECT TYPE, TYPE_NM FROM UMFTYPE WITH(NOLOCK) WHERE BRAND = :brand"),
        {"brand": brand}
    ).fetchall()

    return jsonify([{"value": r.TYPE, "label": r.TYPE_NM} for r in rows])

@blacklist_bp.route('/blacklist/validate/id-card')
@login_required
def validate_id_card():
    id_card = request.args.get('id_card', '').strip()
    exclude_no = request.args.get('exclude_no', type=int)

    if exclude_no:
        row = db.session.execute(
            text("""
                SELECT TOP 1 Flag_Type FROM MCMOWATCHLIST WITH(NOLOCK)
                WHERE FlagDel = 0 AND Flag_Type IN ('W','B')
                  AND ID_Card = :id_card AND ID_Card IS NOT NULL AND ID_Card <> ''
                  AND No <> :no
            """),
            {"id_card": id_card, "no": exclude_no}
        ).fetchone()
        if not row:
            return jsonify({"ok": True, "message": ""})
        where = "Watchlist" if row.Flag_Type == 'W' else "Blacklist"
        return jsonify({"ok": False, "message": f"ID Card is exist in {where}"})

    ok, message = check_id_card_status(db, id_card)
    return jsonify({"ok": ok, "message": message})

@blacklist_bp.route('/blacklist/validate/npwp')
@login_required
def validate_npwp():
    npwp = request.args.get('npwp', '').strip()
    exclude_no = request.args.get('exclude_no', type=int)

    if exclude_no:
        row = db.session.execute(
            text("""
                SELECT TOP 1 Flag_Type FROM MCMOWATCHLIST WITH(NOLOCK)
                WHERE FlagDel = 0 AND Flag_Type IN ('W','B')
                  AND NPWP = :npwp AND NPWP IS NOT NULL AND NPWP <> ''
                  AND No <> :no
            """),
            {"npwp": npwp, "no": exclude_no}
        ).fetchone()
        if not row:
            return jsonify({"ok": True, "message": ""})
        where = "Watchlist" if row.Flag_Type == 'W' else "Blacklist"
        return jsonify({"ok": False, "message": f"NPWP is exist in {where}"})

    ok, message = check_npwp_status(db, npwp)
    return jsonify({"ok": ok, "message": message})

@blacklist_bp.route('/blacklist/list')
@login_required
def get_list():
    search_by = request.args.get('search_by', '').strip()
    search_val = request.args.get('search_val', '').strip()
    page = max(request.args.get('page', 1, type=int), 1)
    limit = min(max(request.args.get('limit', 20, type=int), 1), MAX_PAGE_LIMIT)

    where = "Flag_type = 'B' AND (flagdel <> '1' OR flagdel IS NULL)"
    params = {}

    if search_val:
        if search_by == '1':
            where += " AND ID_Card = :search_val"
            params["search_val"] = search_val
        elif search_by == '3':
            where += " AND NPWP = :search_val"
            params["search_val"] = search_val
        else:
            where += " AND Name LIKE :search_val"
            params["search_val"] = f"%{search_val}%"

    try:
        total = db.session.execute(
            text(f"SELECT COUNT(*) AS total FROM MCMOWatchList WITH(NOLOCK) WHERE {where}"),
            params
        ).fetchone().total

        params["offset"] = (page - 1) * limit
        params["limit"] = limit

        rows = db.session.execute(
            text(f"""
                SELECT No, ID_Card, Name, Address, apless, customer_type, NPWP
                FROM MCMOWatchList WITH(NOLOCK)
                WHERE {where}
                ORDER BY No
                OFFSET :offset ROWS
                FETCH NEXT :limit ROWS ONLY
            """),
            params
        ).fetchall()

        data = [
            {
                "no": r.No,
                "id_card_npwp": (r.ID_Card if r.customer_type == 'PR' else r.NPWP) or "",
                "name": r.Name or "",
                "address": r.Address or "",
                "apless": r.apless or "",
                "customer_type": r.customer_type or "PR",
            }
            for r in rows
        ]

        return jsonify({"rows": data, "total": total, "page": page, "limit": limit})
    except Exception as e:
        current_app.logger.exception("List error")
        return jsonify({"error": str(e)}), 500

@blacklist_bp.route('/blacklist/<int:no>')
@login_required
def get_blacklist(no):
    try:
        row = db.session.execute(
            text("""
                SELECT a.No, a.Customer_Type, a.Name, a.Address, a.Phone, a.NPWP, a.ID_Card, a.DOB,
                       a.Spouse_Name, a.Mother, a.ContactPerson, a.ContactAddress, a.Contact_Group,
                       a.Reason, a.Reason_Category, a.Reason_Other, a.Problem_Since,
                       a.CreateUser, a.CreateDate, a.LastUser, a.LastUpdate, a.apless,
                       b.NAME AS alias_name
                FROM MCMOWatchList a WITH(NOLOCK)
                    LEFT JOIN MCMOWATCHLIST_ALIASNM b WITH(NOLOCK) ON a.No = b.NO
                WHERE a.No = :no AND a.Flag_type = 'B'
            """),
            {"no": no}
        ).fetchone()

        if not row:
            return jsonify({"error": "Record not found"}), 404

        is_pr = row.Customer_Type == 'PR'
        npwp = row.NPWP or ""

        members = []
        if not is_pr:
            known_positions = {
                (r.OS_CODE, r.ID_OS_POSITION)
                for r in db.session.execute(
                    text("SELECT OS_CODE, ID_OS_POSITION FROM MSTOS_POSITION WITH(NOLOCK) WHERE OS_CODE IN (:bod, :boc)"),
                    {"bod": BOD_OS_CODE, "boc": BOC_OS_CODE}
                ).fetchall()
            }

            member_rows = db.session.execute(
                text("""
                    SELECT ID_Blacklist, MANAGEMENT_NM, POSITION, OS_CODE, ADDRESS, CITY, ID_CARD, IMAGES
                    FROM CAFORGSTRUCT_Blacklist WITH(NOLOCK)
                    WHERE Blacklist_NM = :name AND NPWP = :npwp
                    ORDER BY OS_CODE, ID_Blacklist
                """),
                {"name": row.Name, "npwp": npwp}
            ).fetchall()

            for r in member_rows:
                is_known = (r.OS_CODE, r.POSITION) in known_positions
                bod_position = boc_position = other = ""
                if r.OS_CODE == BOD_OS_CODE:
                    bod_position = r.POSITION if is_known else BOD_OTHER_VALUE
                    other = "" if is_known else (r.POSITION or "")
                else:
                    boc_position = r.POSITION if is_known else BOC_OTHER_VALUE
                    other = "" if is_known else (r.POSITION or "")

                members.append({
                    "id_blacklist": r.ID_Blacklist,
                    "name": r.MANAGEMENT_NM or "",
                    "bod_position": bod_position or "",
                    "boc_position": boc_position or "",
                    "other": other,
                    "id_card": r.ID_CARD or "",
                    "address": r.ADDRESS or "",
                    "city": r.CITY or "",
                    "image": r.IMAGES or "",
                })

        return jsonify({
            "no": row.No,
            "customer_type": row.Customer_Type,
            "name": row.Name or "",
            "alias_name": row.alias_name or "",
            "address": row.Address or "",
            "phone": row.Phone or "",
            "npwp": npwp,
            "id_card": row.ID_Card or "",
            "dob": fmt_date(row.DOB, "%Y-%m-%d") if (is_pr and row.DOB) else "",
            "spouse_name": row.Spouse_Name or "",
            "mother": row.Mother or "",
            "contact_person": row.ContactPerson or "",
            "contact_address": row.ContactAddress or "",
            "contact_group": row.Contact_Group or "",
            "establishment_date": fmt_date(row.DOB, "%Y-%m-%d") if (not is_pr and row.DOB) else "",
            "reason_category": (row.Reason_Category or "").strip(),
            "reason_other": (row.Reason_Other or "").strip(),
            "remark": row.Reason or "",
            "problem_since": fmt_date(row.Problem_Since, "%Y-%m-%d") if row.Problem_Since else "",
            "create_by": row.CreateUser or "",
            "create_date": fmt_date(row.CreateDate, "%Y-%m-%d") if row.CreateDate else "",
            "last_user": row.LastUser or "",
            "last_update": fmt_date(row.LastUpdate, "%Y-%m-%d") if row.LastUpdate else "",
            "apless": row.apless or "",
            "members": members,
        })
    except Exception as e:
        current_app.logger.exception("Get blacklist error")
        return jsonify({"error": str(e)}), 500

@blacklist_bp.route('/blacklist', methods=['POST'])
@login_required
def create_blacklist():
    try:
        username = session.get("username", "")

        try:
            data = json.loads(request.form.get('data', '{}'))
        except ValueError:
            return jsonify({"error": "Malformed payload"}), 400

        customer_type = data.get('customer_type')
        if customer_type not in ('PR', 'PT'):
            return jsonify({"error": "Customer Type must not empty"}), 400

        name = (data.get('name') or '').strip()
        address = (data.get('address') or '').strip()
        npwp = _strip_special(data.get('npwp'))
        id_card = (data.get('id_card') or '').strip()
        alias_name = (data.get('alias_name') or '').strip()
        reason_category = (data.get('reason_category') or '').strip()
        members = data.get('members', [])

        errors, dob, est = _validate_core(data, customer_type)
        if customer_type == 'PT':
            errors += _validate_members(members)
        if errors:
            return jsonify({"error": " ".join(errors)}), 400

        name_uth = _strip_special(name)
        address_uth = _strip_special(address)

        if customer_type == 'PR':
            existing = db.session.execute(
                text("""
                    SELECT TOP 1 Flag_Type FROM MCMOWatchList WITH(NOLOCK)
                    WHERE dbo.RemoveSpecialChars(Name) = :n AND dbo.RemoveSpecialChars(Address) = :a
                      AND dbo.RemoveSpecialChars(ID_Card) = :i AND Flagdel = 0
                """),
                {"n": name_uth, "a": address_uth, "i": _strip_special(id_card)}
            ).fetchone()
            if not existing:
                existing = db.session.execute(
                    text("""
                        SELECT TOP 1 Flag_Type FROM MCMOWatchList WITH(NOLOCK)
                        WHERE dbo.RemoveSpecialChars(Name) = :n AND dbo.RemoveSpecialChars(Address) = :a
                          AND Flagdel = 0
                    """),
                    {"n": name_uth, "a": address_uth}
                ).fetchone()
        else:
            existing = db.session.execute(
                text("""
                    SELECT TOP 1 Flag_Type FROM MCMOWatchList WITH(NOLOCK)
                    WHERE dbo.RemoveSpecialChars(Name) = :n AND dbo.RemoveSpecialChars(Address) = :a
                      AND dbo.RemoveSpecialChars(NPWP) = :p AND Flagdel = 0
                """),
                {"n": name_uth, "a": address_uth, "p": npwp}
            ).fetchone()

        if existing:
            if existing.Flag_Type == 'W':
                return jsonify({"error": "Customer sudah terdaftar di Watchlist"}), 400
            if existing.Flag_Type == 'B':
                return jsonify({"error": "Customer sudah terdaftar di Blacklist"}), 400

        max_row = db.session.execute(
            text("SELECT MAX(No) AS no FROM MCMOWatchList WITH(UPDLOCK, HOLDLOCK)")
        ).fetchone()
        new_no = (max_row.no or 0) + 1

        problem_since_sql = "GETDATE()" if reason_category == '2' else "NULL"

        if customer_type == 'PR':
            db.session.execute(
                text(f"""
                    INSERT INTO MCMOWatchList
                        (No, Name, Address, ID_Card, Phone, CreateUser, CreateDate, Reason, DOB,
                         Flag_type, Customer_Type, Spouse_Name, FlagDel, Mother,
                         Reason_Category, Reason_Other, NPWP, Problem_Since)
                    VALUES
                        (:no, :name, :address, :id_card, :phone, :create_user, GETDATE(), :remark, :dob,
                         'B', 'PR', :spouse_name, '0', :mother,
                         :reason_category, :reason_other, :npwp, {problem_since_sql})
                """),
                {"no": new_no, "name": name, "address": address, "id_card": id_card,
                 "phone": (data.get('phone') or '').strip(), "create_user": username,
                 "remark": (data.get('remark') or '').strip(), "dob": dob,
                 "spouse_name": (data.get('spouse_name') or '').strip(),
                 "mother": (data.get('mother') or '').strip(),
                 "reason_category": reason_category,
                 "reason_other": (data.get('reason_other') or '').strip(), "npwp": npwp}
            )
        else:
            db.session.execute(
                text(f"""
                    INSERT INTO MCMOWatchList
                        (No, Name, Address, Phone, CreateUser, CreateDate, Reason,
                         ContactPerson, ContactAddress, DOB, Flag_type, Customer_Type, FlagDel,
                         Contact_Group, Reason_Category, Reason_Other, NPWP, Problem_Since)
                    VALUES
                        (:no, :name, :address, :phone, :create_user, GETDATE(), :remark,
                         :contact_person, :contact_address, :est_date, 'B', 'PT', '0',
                         :contact_group, :reason_category, :reason_other, :npwp, {problem_since_sql})
                """),
                {"no": new_no, "name": name, "address": address,
                 "phone": (data.get('phone') or '').strip(), "create_user": username,
                 "remark": (data.get('remark') or '').strip(),
                 "contact_person": (data.get('contact_person') or '').strip(),
                 "contact_address": (data.get('contact_address') or '').strip(),
                 "est_date": est, "contact_group": (data.get('contact_group') or '').strip(),
                 "reason_category": reason_category,
                 "reason_other": (data.get('reason_other') or '').strip(), "npwp": npwp}
            )

        if customer_type == 'PR' and alias_name:
            _insert_alias(new_no, alias_name)

        apless = _lookup_apless(name, address)
        file_errors = _save_members(name, npwp, customer_type, members, request.files, apless)
        if file_errors:
            db.session.rollback()
            return jsonify({"error": " ".join(file_errors)}), 400

        db.session.commit()
        return jsonify({"message": "success", "no": new_no})
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Create blacklist error")
        return jsonify({"error": str(e)}), 500

def _insert_alias(no: int, alias_name: str):
    row = db.session.execute(
        text("SELECT MAX(ID) AS id FROM MCMOWATCHLIST_ALIASNM WITH(UPDLOCK, HOLDLOCK)")
    ).fetchone()
    db.session.execute(
        text("INSERT INTO MCMOWATCHLIST_ALIASNM (NO, ID, NAME) VALUES (:no, :id, :name)"),
        {"no": no, "id": (row.id or 0) + 1, "name": alias_name}
    )

@blacklist_bp.route('/blacklist/<int:no>', methods=['PUT'])
@login_required
def update_blacklist(no):
    try:
        username = session.get("username", "")

        try:
            data = json.loads(request.form.get('data', '{}'))
        except ValueError:
            return jsonify({"error": "Malformed payload"}), 400

        current = db.session.execute(
            text("""
                SELECT Customer_Type, Name, NPWP, Reason_Category, apless
                FROM MCMOWatchList WITH(NOLOCK)
                WHERE No = :no AND Flag_Type = 'B' AND FlagDel = '0'
            """),
            {"no": no}
        ).fetchone()

        if not current:
            return jsonify({"error": "Record not found"}), 404

        customer_type = current.Customer_Type
        old_name = current.Name
        old_npwp = current.NPWP or ""

        name = (data.get('name') or '').strip()
        address = (data.get('address') or '').strip()
        npwp = _strip_special(data.get('npwp'))
        alias_name = (data.get('alias_name') or '').strip()
        members = data.get('members', [])

        stored_category = (current.Reason_Category or '').strip()
        if stored_category == '4':
            reason_category = '4'
            data = {**data, 'reason_category': '4'}
        else:
            reason_category = (data.get('reason_category') or '').strip()

        errors, dob, est = _validate_core(data, customer_type)
        if customer_type == 'PT':
            errors += _validate_members(members)
        if errors:
            return jsonify({"error": " ".join(errors)}), 400

        if customer_type == 'PR':
            db.session.execute(
                text("""
                    UPDATE MCMOWatchList SET
                        Name = :name, Address = :address, ID_Card = :id_card, DOB = :dob,
                        Phone = :phone, Spouse_Name = :spouse_name, Mother = :mother,
                        LastUser = :last_user, LastUpdate = SYSDATETIME(), Reason = :remark,
                        Reason_Category = :reason_category, Reason_Other = :reason_other, NPWP = :npwp
                    WHERE No = :no AND FlagDel = '0' AND Flag_Type = 'B'
                """),
                {"name": name, "address": address, "id_card": (data.get('id_card') or '').strip(),
                 "dob": dob, "phone": (data.get('phone') or '').strip(),
                 "spouse_name": (data.get('spouse_name') or '').strip(),
                 "mother": (data.get('mother') or '').strip(), "last_user": username,
                 "remark": (data.get('remark') or '').strip(), "reason_category": reason_category,
                 "reason_other": (data.get('reason_other') or '').strip(), "npwp": npwp, "no": no}
            )

            alias_exists = db.session.execute(
                text("SELECT TOP 1 NAME FROM MCMOWATCHLIST_ALIASNM WITH(NOLOCK) WHERE NO = :no"),
                {"no": no}
            ).fetchone()

            if alias_exists:
                db.session.execute(
                    text("UPDATE MCMOWATCHLIST_ALIASNM SET NAME = :name WHERE NO = :no"),
                    {"name": alias_name, "no": no}
                )
            elif alias_name:
                _insert_alias(no, alias_name)
        else:
            db.session.execute(
                text("""
                    UPDATE MCMOWatchList SET
                        Name = :name, Address = :address, Phone = :phone,
                        ContactPerson = :contact_person, ContactAddress = :contact_address,
                        Contact_Group = :contact_group, DOB = :dob,
                        LastUser = :last_user, LastUpdate = SYSDATETIME(), Reason = :remark,
                        Reason_Category = :reason_category, Reason_Other = :reason_other, NPWP = :npwp
                    WHERE No = :no AND FlagDel = '0' AND Flag_Type = 'B'
                """),
                {"name": name, "address": address, "phone": (data.get('phone') or '').strip(),
                 "contact_person": (data.get('contact_person') or '').strip(),
                 "contact_address": (data.get('contact_address') or '').strip(),
                 "contact_group": (data.get('contact_group') or '').strip(), "dob": est,
                 "last_user": username, "remark": (data.get('remark') or '').strip(),
                 "reason_category": reason_category,
                 "reason_other": (data.get('reason_other') or '').strip(), "npwp": npwp, "no": no}
            )

        apless = current.apless or _lookup_apless(name, address)
        file_errors = _save_members(
            name, npwp, customer_type, members, request.files, apless,
            old_name=old_name, old_npwp=old_npwp
        )
        if file_errors:
            db.session.rollback()
            return jsonify({"error": " ".join(file_errors)}), 400

        db.session.commit()
        return jsonify({"message": "success"})
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Update blacklist error")
        return jsonify({"error": str(e)}), 500

@blacklist_bp.route('/blacklist/<int:no>/delete', methods=['POST'])
@login_required
def delete_blacklist(no):
    try:
        username = session.get("username", "")
        reason = (request.form.get('reason') or '').strip()

        if not reason:
            return jsonify({"error": "fill the reason first"}), 400

        file = request.files.get('attachment')
        if not file or not file.filename:
            return jsonify({"error": "Upload the file first"}), 400

        row = db.session.execute(
            text("""
                SELECT Name, Address, apless FROM MCMOWatchList WITH(NOLOCK)
                WHERE No = :no AND Flag_Type = 'B' AND (FlagDel <> '1' OR FlagDel IS NULL)
            """),
            {"no": no}
        ).fetchone()

        if not row:
            return jsonify({"error": "Record not found"}), 404

        apless = row.apless or _lookup_apless(row.Name, row.Address)
        filename = save_general_attachment(file, f"blacklist-{no}", apless, current_app.config['UPLOAD_FOLDER'])

        result = db.session.execute(
            text("""
                UPDATE MCMOWATCHLIST
                SET flagdel = '1', attachment = :attachment, deleteby = :deleteby,
                    Reason_Delete = :reason, DeleteDate = SYSDATETIME()
                WHERE No = :no AND flag_type = 'B' AND (FlagDel <> '1' OR FlagDel IS NULL)
            """),
            {"attachment": filename, "deleteby": username, "reason": reason, "no": no}
        )

        if result.rowcount == 0:
            db.session.rollback()
            return jsonify({"error": "Record not found"}), 404

        db.session.commit()
        return jsonify({"message": "success"})
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Delete blacklist error")
        return jsonify({"error": str(e)}), 500

@blacklist_bp.route('/blacklist/management/<int:id_blacklist>/image')
@login_required
def get_management_image(id_blacklist):
    try:
        row = db.session.execute(
            text("SELECT IMAGES FROM CAFORGSTRUCT_Blacklist WITH(NOLOCK) WHERE ID_Blacklist = :id"),
            {"id": id_blacklist}
        ).fetchone()

        if not row or not row.IMAGES:
            return jsonify({"error": "No image found"}), 404

        return send_from_directory(current_app.config['UPLOAD_FOLDER_BLACKLIST'], row.IMAGES)
    except Exception as e:
        current_app.logger.exception("Get image error")
        return jsonify({"error": str(e)}), 500

@blacklist_bp.route('/blacklist/management/<int:id_blacklist>/image', methods=['DELETE'])
@login_required
def delete_management_image(id_blacklist):
    try:
        row = db.session.execute(
            text("SELECT IMAGES FROM CAFORGSTRUCT_Blacklist WITH(NOLOCK) WHERE ID_Blacklist = :id"),
            {"id": id_blacklist}
        ).fetchone()

        if not row or not row.IMAGES:
            return jsonify({"error": "No image found"}), 404

        delete_blacklist_file(row.IMAGES, current_app.config['UPLOAD_FOLDER_BLACKLIST'])

        db.session.execute(
            text("UPDATE CAFORGSTRUCT_Blacklist SET IMAGES = NULL WHERE ID_Blacklist = :id"),
            {"id": id_blacklist}
        )
        db.session.commit()
        return jsonify({"message": "success"})
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Delete image error")
        return jsonify({"error": str(e)}), 500