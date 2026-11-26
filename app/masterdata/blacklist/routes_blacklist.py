import json
import re
from datetime import date, datetime

from flask import Blueprint, jsonify, request, current_app, session
from sqlalchemy import text

from app import db
from app.auth.decorators import login_required
from app.utils.helpers.base_format import fmt_date
from app.utils.helpers.shared_helpers import _strip_special

blacklist_bp = Blueprint('blacklist', __name__, url_prefix='/MasterData')

MAX_PAGE_LIMIT = 200

OS_CODE_ALLOWED = {
    'CO': ('CO01', 'CO02'),
    'CV': ('CV01', 'CV02'),
    'FD': ('FD01', 'FD02', 'FD03'),
    'PT': ('PT01', 'PT02', 'PT03'),
}
OS_CODE_LABEL = {
    'CO01': 'Pengurus',
    'CO02': 'Pengawas',
    'CV01': 'Persero Aktif',
    'CV02': 'Persero Pasif',
    'FD01': 'Pembina',
    'FD02': 'Pengurus',
    'FD03': 'Pengawas',
    'PT01': 'Shareholder',
    'PT02': 'BOD / Direksi',
    'PT03': 'BOC / Komisaris',
}
OS_CODE_WHITELIST = frozenset(c for codes in OS_CODE_ALLOWED.values() for c in codes)
SHAREHOLDER_OS_CODE = 'PT01'
SHAREHOLDER_STATUS_CODES = ('PR', 'PT')

MEMBER_LIMITS = (
    ('Name', 'name', 200),
    ('ID Card', 'id_card', 40),
    ('NPWP', 'npwp', 30),
    ('Position Other', 'position_other', 500),
    ('Shareholder Status', 'shareholder_status', 2),
)

REASON_RULES = {
    'create': {'excluded': ('6', '7', '10'), 'disabled': ('4', '9')},
    'edit': {'excluded': ('6', '7'), 'disabled': ('4',)},
}
REASON_LOCKED = '4'
REASON_OTHER = '5'
REASON_PROBLEM_SINCE = '2'

PR_NAME_PATTERN = re.compile(r'^[a-zA-Z., ]*$')

WHERE_ID_CARD = "ID_Card = :v AND ID_Card IS NOT NULL AND ID_Card <> ''"
WHERE_NPWP = "NPWP = :v AND NPWP IS NOT NULL AND NPWP <> ''"
WHERE_PERSON_ID = (
    "((ID_Card = :v AND ID_Card IS NOT NULL AND ID_Card <> '') "
    "OR (SpouseIDCard = :v AND SpouseIDCard IS NOT NULL AND SpouseIDCard <> ''))"
)
WHERE_NAME_DOB = (
    "((dbo.RemoveSpecialChars(Name) = :n AND CONVERT(date, DOB) = :d) "
    "OR (dbo.RemoveSpecialChars(Spouse_Name) = :n AND CONVERT(date, SpouseDOB) = :d))"
)

_caforg_identity_cache = None


def _s(value) -> str:
    if value is None:
        return ''
    return str(value).strip()


def _alnum(value: str) -> str:
    return re.sub(r'[^a-zA-Z0-9]', '', value or '')


def _is_other_position(desc) -> bool:
    d = (desc or '').lower()
    return 'other' in d or 'lain' in d


def _wl_label(flag: str) -> str:
    return 'Watchlist' if flag == 'W' else 'Blacklist'


def _wl_find(where: str, params: dict, exclude_no=None) -> str:
    sql = (
        "SELECT TOP 1 Flag_Type FROM MCMOWatchList WITH (NOLOCK) "
        "WHERE ISNULL(FlagDel, '0') <> '1' AND Flag_Type IN ('W', 'B') AND " + where
    )
    bind = dict(params)
    if exclude_no:
        sql += " AND [No] <> :exclude_no"
        bind['exclude_no'] = exclude_no
    row = db.session.execute(text(sql), bind).fetchone()
    return _s(row.Flag_Type) if row else ''


def _caforg_exists(where: str, params: dict, exclude_no=None) -> bool:
    sql = "SELECT TOP 1 MANAGEMENT_NM FROM CAFORGSTRUCT_Blacklist WITH (NOLOCK) WHERE " + where
    bind = dict(params)
    if exclude_no:
        sql += " AND ISNULL(McmoWatchlistID, 0) <> :exclude_no"
        bind['exclude_no'] = exclude_no
    return db.session.execute(text(sql), bind).fetchone() is not None


def _caforg_id_is_identity() -> bool:
    global _caforg_identity_cache
    if _caforg_identity_cache is None:
        row = db.session.execute(text(
            "SELECT COLUMNPROPERTY(OBJECT_ID('CAFORGSTRUCT_Blacklist'), 'ID_Blacklist', 'IsIdentity') AS is_ident"
        )).fetchone()
        _caforg_identity_cache = bool(row and row.is_ident == 1)
    return _caforg_identity_cache


def _other_position_ids() -> set:
    rows = db.session.execute(
        text("SELECT ID_OS_POSITION, [DESC] FROM MSTOS_POSITION WITH (NOLOCK)")
    ).fetchall()
    return {_s(r.ID_OS_POSITION) for r in rows if _is_other_position(r.DESC)}


def _parse_past_date(raw: str, errors: list, message: str):
    raw = _s(raw)
    if not raw:
        return None
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        errors.append(message)
        return None
    if parsed > date.today():
        errors.append(message)
        return None
    return parsed


def _load_payload():
    try:
        data = json.loads(request.form.get('data', '{}'))
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _errors_response(errors: list):
    return jsonify({"error": " ".join(errors), "errors": errors}), 400


def _read_fields(data: dict, customer_type: str) -> dict:
    is_pr = customer_type == 'PR'
    return {
        'name': _s(data.get('name')),
        'address': _s(data.get('address')),
        'phone': _s(data.get('phone')),
        'npwp': _strip_special(_s(data.get('npwp'))) or '',
        'id_card': _s(data.get('id_card')) if is_pr else '',
        'dob': _s(data.get('dob')) if is_pr else _s(data.get('establishment_date')),
        'spouse_name': _s(data.get('spouse_name')) if is_pr else '',
        'spouse_idcard': _s(data.get('spouse_idcard')) if is_pr else '',
        'spouse_dob': _s(data.get('spouse_dob')) if is_pr else '',
        'mother': _s(data.get('mother')) if is_pr else '',
        'contact_person': '' if is_pr else _s(data.get('contact_person')),
        'contact_address': '' if is_pr else _s(data.get('contact_address')),
        'lessee_cat': '' if is_pr else _s(data.get('lessee_cat')),
        'reason_category': _s(data.get('reason_category')),
        'reason_other': _s(data.get('reason_other')),
        'remark': _s(data.get('remark')),
    }


def _read_members(raw, customer_type: str) -> list:
    rows = []
    for entry in raw if isinstance(raw, list) else []:
        if not isinstance(entry, dict):
            continue
        os_code = _s(entry.get('os_code'))
        shareholder = _s(entry.get('shareholder_status'))
        id_card = _s(entry.get('id_card'))
        npwp = _s(entry.get('npwp'))

        if customer_type != 'PT' or os_code != SHAREHOLDER_OS_CODE:
            shareholder = ''
        if shareholder not in SHAREHOLDER_STATUS_CODES:
            shareholder = ''
        if shareholder == 'PT':
            id_card = ''
        else:
            npwp = ''

        rows.append({
            'name': _s(entry.get('name')),
            'os_code': os_code,
            'position': _s(entry.get('position')),
            'position_other': _s(entry.get('position_other')),
            'shareholder_status': shareholder,
            'id_card': id_card,
            'npwp': npwp,
        })
    return rows


def _validate_members(members: list, lessee_cat: str, exclude_no=None) -> list:
    errors = []
    allowed = OS_CODE_ALLOWED.get(lessee_cat, ())
    owner = "another blacklisted customer" if exclude_no else "a blacklisted customer"

    for idx, m in enumerate(members, start=1):
        name = m['name']
        if not name:
            if m['id_card'] or m['npwp']:
                errors.append(
                    f"Row {idx} has details but no Name. "
                    "Enter the Name in the BOD / BOC grid or clear the row."
                )
            continue

        if not m['os_code']:
            errors.append(f"Type must be selected for {name}")
            continue

        if m['os_code'] not in OS_CODE_WHITELIST or m['os_code'] not in allowed:
            errors.append(f"Type is not valid for the selected Company Profile ({name})")
            continue

        for label, key, limit in MEMBER_LIMITS:
            if len(m[key]) > limit:
                errors.append(f"{label} for {name} exceeds {limit} characters")

        if m['id_card']:
            flag = _wl_find(WHERE_PERSON_ID, {'v': m['id_card']}, exclude_no)
            if flag:
                errors.append(f"ID Card for {name} is already registered in {_wl_label(flag)}")
            if _caforg_exists("ID_CARD = :v AND ID_CARD IS NOT NULL AND ID_CARD <> ''", {'v': m['id_card']}, exclude_no):
                errors.append(f"ID Card for {name} is already registered as management of {owner}")

        if m['os_code'] == SHAREHOLDER_OS_CODE and m['npwp']:
            flag = _wl_find(WHERE_NPWP, {'v': m['npwp']}, exclude_no)
            if flag:
                errors.append(f"NPWP for {name} is already registered in {_wl_label(flag)}")
            if _caforg_exists("NPWP = :v AND NPWP IS NOT NULL AND NPWP <> ''", {'v': m['npwp']}, exclude_no):
                errors.append(f"NPWP for {name} is already registered as a shareholder of {owner}")

    return errors


def _validate(f: dict, customer_type: str, members: list, mode: str,
              exclude_no=None, locked_category: str = '') -> tuple:
    errors, date_errors = [], []
    is_pr = customer_type == 'PR'

    dob = _parse_past_date(f['dob'], date_errors, "DOB / Establishment Date not valid")
    spouse_dob = _parse_past_date(f['spouse_dob'], date_errors, "Spouse Date of Birth not valid") if is_pr else None

    if is_pr and f['id_card']:
        flag = _wl_find(WHERE_ID_CARD, {'v': f['id_card']}, exclude_no)
        if flag:
            errors.append(f"ID Card is already registered in {_wl_label(flag)}")

    if not is_pr and f['npwp']:
        flag = _wl_find(WHERE_NPWP, {'v': f['npwp']}, exclude_no)
        if flag:
            errors.append(f"NPWP is already registered in {_wl_label(flag)}")

    spouse_key = _alnum(f['spouse_name'])
    if is_pr and spouse_key and spouse_dob:
        flag = _wl_find(WHERE_NAME_DOB, {'n': spouse_key, 'd': spouse_dob}, exclude_no)
        if flag:
            errors.append(f"Spouse Name and Date of Birth are already registered in {_wl_label(flag)}")

    if is_pr and f['spouse_idcard']:
        flag = _wl_find(WHERE_PERSON_ID, {'v': f['spouse_idcard']}, exclude_no)
        if flag:
            errors.append(f"Spouse ID Card is already registered in {_wl_label(flag)}")

    if is_pr and not f['id_card']:
        errors.append("ID Card must not empty")

    if not f['name']:
        errors.append("Name must not empty")
    elif is_pr and not PR_NAME_PATTERN.match(f['name']):
        errors.append("Name only allows letters, dot, comma and space")

    if not f['address']:
        errors.append("Address must not empty")

    if not is_pr and not f['lessee_cat']:
        errors.append("Company Profile must not empty")

    if not is_pr and not f['npwp']:
        errors.append("NPWP must not empty")

    rules = REASON_RULES[mode]
    category = f['reason_category']
    if not category:
        errors.append("Reason Category must not empty")
    elif category in rules['excluded'] or (category in rules['disabled'] and category != locked_category):
        errors.append("Reason Category not valid")

    if category == REASON_OTHER and not f['reason_other']:
        errors.append("Reason Other must not empty")

    errors += date_errors

    if not is_pr:
        errors += _validate_members(members, f['lessee_cat'], exclude_no)

    return errors, dob, spouse_dob


def _save_members(blacklist_no: int, customer_type: str, lessee_cat: str, members: list, replace: bool) -> None:
    if replace:
        db.session.execute(
            text("DELETE FROM CAFORGSTRUCT_Blacklist WHERE McmoWatchlistID = :no"),
            {"no": blacklist_no}
        )

    if customer_type != 'PT':
        return

    allowed = OS_CODE_ALLOWED.get(lessee_cat, ())
    rows = [m for m in members if m['name'] and m['os_code'] in allowed]
    if not rows:
        return

    other_ids = _other_position_ids()
    columns = "McmoWatchlistID, MANAGEMENT_NM, POSITION, Position_Other, OS_CODE, SHAREHOLDER_STATUS, NPWP, ID_CARD"
    values = ":no, :mn, :pos, :pos_other, :os_code, :shst, :npwp, :idc"

    if _caforg_id_is_identity():
        sql = f"INSERT INTO CAFORGSTRUCT_Blacklist ({columns}) VALUES ({values})"
    else:
        sql = (
            f"INSERT INTO CAFORGSTRUCT_Blacklist (ID_Blacklist, {columns}) "
            f"SELECT ISNULL(MAX(ID_Blacklist), 0) + 1, {values} "
            "FROM CAFORGSTRUCT_Blacklist WITH (UPDLOCK, HOLDLOCK)"
        )

    for m in rows:
        position = m['position'] or None
        position_other = m['position_other'] if position in other_ids else ''
        db.session.execute(text(sql), {
            "no": blacklist_no,
            "mn": m['name'],
            "pos": position,
            "pos_other": position_other or None,
            "os_code": m['os_code'],
            "shst": m['shareholder_status'] or None,
            "npwp": m['npwp'] or None,
            "idc": m['id_card'] or None,
        })


def _check_response(flag: str, subject: str):
    if not flag:
        return jsonify({"ok": True, "message": ""})
    return jsonify({"ok": False, "message": f"{subject} exist in {_wl_label(flag)}"})


@blacklist_bp.route('/blacklist/options')
@login_required
def get_options():
    mode = 'edit' if request.args.get('mode') == 'edit' else 'create'
    rules = REASON_RULES[mode]
    try:
        reasons = db.session.execute(
            text("SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH (NOLOCK) WHERE CAT_VALUE = 'BLACKLIST_CATEGORY' ORDER BY VALUE")
        ).fetchall()

        profiles = db.session.execute(
            text("SELECT CUST_TYPE, NAME FROM MSTLESSEETYPE WITH (NOLOCK) WHERE LESSEE_TP = 'PT' ORDER BY NAME")
        ).fetchall()

        position_rows = db.session.execute(
            text("SELECT OS_CODE, ID_OS_POSITION, [DESC] FROM MSTOS_POSITION WITH (NOLOCK) ORDER BY ID_OS_POSITION")
        ).fetchall()

        positions = {code: [] for code in sorted(OS_CODE_WHITELIST)}
        for p in position_rows:
            code = _s(p.OS_CODE)
            if code in positions:
                positions[code].append({
                    "value": _s(p.ID_OS_POSITION),
                    "label": p.DESC,
                    "is_other": _is_other_position(p.DESC),
                })

        return jsonify({
            "reasons": [
                {"value": _s(r.VALUE), "label": r.DESC_VALUE, "disabled": _s(r.VALUE) in rules['disabled']}
                for r in reasons if _s(r.VALUE) not in rules['excluded']
            ],
            "company_profiles": [{"value": _s(p.CUST_TYPE), "label": p.NAME} for p in profiles],
            "os_types": {
                prefix: [{"value": c, "label": OS_CODE_LABEL[c]} for c in codes]
                for prefix, codes in OS_CODE_ALLOWED.items()
            },
            "positions": positions,
            "current_user": session.get("username", ""),
            "today": date.today().strftime("%d-%m-%Y"),
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
    value = _s(request.args.get('id_card'))
    exclude_no = request.args.get('exclude_no', type=int)
    if not value:
        return _check_response('', '')
    try:
        return _check_response(_wl_find(WHERE_ID_CARD, {'v': value}, exclude_no), "ID Card is")
    except Exception as e:
        current_app.logger.exception("Validate ID card error")
        return jsonify({"error": str(e)}), 500


@blacklist_bp.route('/blacklist/validate/npwp')
@login_required
def validate_npwp():
    value = _strip_special(_s(request.args.get('npwp'))) or ''
    exclude_no = request.args.get('exclude_no', type=int)
    if not value:
        return _check_response('', '')
    try:
        return _check_response(_wl_find(WHERE_NPWP, {'v': value}, exclude_no), "NPWP is")
    except Exception as e:
        current_app.logger.exception("Validate NPWP error")
        return jsonify({"error": str(e)}), 500


@blacklist_bp.route('/blacklist/validate/spouse-id-card')
@login_required
def validate_spouse_id_card():
    value = _s(request.args.get('spouse_idcard'))
    exclude_no = request.args.get('exclude_no', type=int)
    if not value:
        return _check_response('', '')
    try:
        return _check_response(_wl_find(WHERE_PERSON_ID, {'v': value}, exclude_no), "Spouse ID Card is")
    except Exception as e:
        current_app.logger.exception("Validate spouse ID card error")
        return jsonify({"error": str(e)}), 500


@blacklist_bp.route('/blacklist/validate/spouse-dob')
@login_required
def validate_spouse_dob():
    spouse_key = _alnum(_s(request.args.get('spouse_name')))
    exclude_no = request.args.get('exclude_no', type=int)
    try:
        spouse_dob = datetime.strptime(_s(request.args.get('spouse_dob')), "%Y-%m-%d").date()
    except ValueError:
        spouse_dob = None
    if not spouse_key or not spouse_dob:
        return _check_response('', '')
    try:
        flag = _wl_find(WHERE_NAME_DOB, {'n': spouse_key, 'd': spouse_dob}, exclude_no)
        return _check_response(flag, "Spouse Name and Date of Birth are")
    except Exception as e:
        current_app.logger.exception("Validate spouse DOB error")
        return jsonify({"error": str(e)}), 500


@blacklist_bp.route('/blacklist/list')
@login_required
def get_list():
    search_by = request.args.get('search_by', '').strip()
    search_val = request.args.get('search_val', '').strip()
    page = max(request.args.get('page', 1, type=int), 1)
    limit = min(max(request.args.get('limit', 20, type=int), 1), MAX_PAGE_LIMIT)

    where = "Flag_type = 'B' AND ISNULL(flagdel, '0') <> '1'"
    params = {}

    if search_val:
        if search_by == '1':
            where += " AND ID_Card = :search_val"
            params["search_val"] = search_val
        elif search_by == '3':
            where += " AND NPWP = :search_val"
            params["search_val"] = re.sub(r'\D', '', search_val)
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
                "id_card_npwp": (r.ID_Card if _s(r.customer_type) == 'PR' else r.NPWP) or "",
                "name": r.Name or "",
                "address": r.Address or "",
                "apless": _s(r.apless),
                "customer_type": _s(r.customer_type) or "PR",
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
                SELECT No, Customer_Type, Lessee_Cat, Name, Address, Phone, NPWP, ID_Card, DOB,
                       Spouse_Name, SpouseIDCard, SpouseDOB, Mother, ContactPerson, ContactAddress,
                       Reason, Reason_Category, Reason_Other,
                       CreateUser, CreateDate, LastUser, LastUpdate, apless, FlagDel
                FROM MCMOWatchList WITH(NOLOCK)
                WHERE No = :no AND Flag_type = 'B'
            """),
            {"no": no}
        ).fetchone()

        if not row:
            return jsonify({"error": "Record not found"}), 404

        customer_type = 'PR' if _s(row.Customer_Type) == 'PR' else 'PT'
        is_pr = customer_type == 'PR'

        members = []
        if not is_pr:
            member_rows = db.session.execute(
                text("""
                    SELECT ID_Blacklist, MANAGEMENT_NM, POSITION, Position_Other, OS_CODE,
                           SHAREHOLDER_STATUS, NPWP, ID_CARD
                    FROM CAFORGSTRUCT_Blacklist WITH(NOLOCK)
                    WHERE McmoWatchlistID = :no
                    ORDER BY OS_CODE, ID_Blacklist
                """),
                {"no": row.No}
            ).fetchall()

            for r in member_rows:
                if not _s(r.MANAGEMENT_NM):
                    continue
                os_code = _s(r.OS_CODE)
                members.append({
                    "id_blacklist": r.ID_Blacklist,
                    "name": r.MANAGEMENT_NM or "",
                    "os_code": os_code if os_code in OS_CODE_WHITELIST else "",
                    "position": _s(r.POSITION),
                    "position_other": r.Position_Other or "",
                    "shareholder_status": _s(r.SHAREHOLDER_STATUS),
                    "npwp": r.NPWP or "",
                    "id_card": r.ID_CARD or "",
                })

        dob_iso = fmt_date(row.DOB, "%Y-%m-%d") if row.DOB else ""

        return jsonify({
            "no": row.No,
            "customer_type": customer_type,
            "lessee_cat": "" if is_pr else _s(row.Lessee_Cat),
            "name": row.Name or "",
            "address": row.Address or "",
            "phone": row.Phone or "",
            "npwp": _s(row.NPWP),
            "id_card": (row.ID_Card or "") if is_pr else "",
            "dob": dob_iso if is_pr else "",
            "establishment_date": "" if is_pr else dob_iso,
            "spouse_name": (row.Spouse_Name or "") if is_pr else "",
            "spouse_idcard": (row.SpouseIDCard or "") if is_pr else "",
            "spouse_dob": fmt_date(row.SpouseDOB, "%Y-%m-%d") if (is_pr and row.SpouseDOB) else "",
            "mother": (row.Mother or "") if is_pr else "",
            "contact_person": "" if is_pr else (row.ContactPerson or ""),
            "contact_address": "" if is_pr else (row.ContactAddress or ""),
            "reason_category": _s(row.Reason_Category),
            "reason_other": _s(row.Reason_Other),
            "remark": _s(row.Reason),
            "create_by": row.CreateUser or session.get("username", ""),
            "create_date": fmt_date(row.CreateDate, "%d-%m-%Y") if row.CreateDate else "",
            "last_user": row.LastUser or "",
            "last_update": fmt_date(row.LastUpdate, "%d-%m-%Y") if row.LastUpdate else "",
            "apless": _s(row.apless),
            "deleted": _s(row.FlagDel) == '1',
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

        data = _load_payload()
        if data is None:
            return jsonify({"error": "Malformed payload"}), 400

        customer_type = _s(data.get('customer_type'))
        if customer_type not in ('PR', 'PT'):
            return jsonify({"error": "Customer Type must not empty"}), 400

        is_pr = customer_type == 'PR'
        f = _read_fields(data, customer_type)
        members = [] if is_pr else _read_members(data.get('members'), customer_type)

        errors, dob, spouse_dob = _validate(f, customer_type, members, 'create')
        if errors:
            return _errors_response(errors)

        new_no = int(db.session.execute(
            text("SELECT ISNULL(MAX(No), 0) + 1 AS no FROM MCMOWatchList WITH (UPDLOCK, HOLDLOCK)")
        ).fetchone().no)

        problem_since_sql = "CONVERT(date, GETDATE())" if f['reason_category'] == REASON_PROBLEM_SINCE else "NULL"

        db.session.execute(
            text(f"""
                INSERT INTO MCMOWatchList
                    (No, Name, Address, ID_Card, Phone, CreateUser, CreateDate, Reason,
                     DOB, Flag_Type, Customer_Type, Lessee_Cat, Spouse_Name, SpouseIDCard,
                     SpouseDOB, FlagDel, Mother, ContactPerson, ContactAddress,
                     Reason_Category, Reason_Other, NPWP, Problem_Since)
                VALUES
                    (:no, :name, :address, :id_card, :phone, :create_user, CONVERT(date, GETDATE()), :remark,
                     :dob, 'B', :customer_type, :lessee_cat, :spouse_name, :spouse_idcard,
                     :spouse_dob, '0', :mother, :contact_person, :contact_address,
                     :reason_category, :reason_other, :npwp, {problem_since_sql})
            """),
            {
                "no": new_no,
                "name": f['name'],
                "address": f['address'],
                "id_card": f['id_card'] if is_pr else None,
                "phone": f['phone'],
                "create_user": username,
                "remark": f['remark'],
                "dob": dob,
                "customer_type": customer_type,
                "lessee_cat": None if is_pr else f['lessee_cat'],
                "spouse_name": f['spouse_name'] if is_pr else None,
                "spouse_idcard": f['spouse_idcard'] if is_pr else None,
                "spouse_dob": spouse_dob if is_pr else None,
                "mother": f['mother'] if is_pr else None,
                "contact_person": None if is_pr else f['contact_person'],
                "contact_address": None if is_pr else f['contact_address'],
                "reason_category": f['reason_category'],
                "reason_other": f['reason_other'],
                "npwp": f['npwp'],
            }
        )

        _save_members(new_no, customer_type, f['lessee_cat'], members, replace=False)

        db.session.commit()
        return jsonify({"message": "success", "no": new_no})
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Create blacklist error")
        return jsonify({"error": str(e)}), 500


@blacklist_bp.route('/blacklist/<int:no>', methods=['PUT'])
@login_required
def update_blacklist(no):
    try:
        username = session.get("username", "")

        data = _load_payload()
        if data is None:
            return jsonify({"error": "Malformed payload"}), 400

        current = db.session.execute(
            text("""
                SELECT Customer_Type, Reason_Category, apless
                FROM MCMOWatchList
                WHERE No = :no AND Flag_Type = 'B' AND ISNULL(FlagDel, '0') <> '1'
            """),
            {"no": no}
        ).fetchone()

        if not current:
            return jsonify({"error": "Record not found"}), 404

        if _s(current.apless):
            return jsonify({"error": "Record linked to a customer cannot be edited"}), 403

        customer_type = 'PR' if _s(current.Customer_Type) == 'PR' else 'PT'
        is_pr = customer_type == 'PR'

        f = _read_fields(data, customer_type)
        locked_category = REASON_LOCKED if _s(current.Reason_Category) == REASON_LOCKED else ''
        if locked_category:
            f['reason_category'] = locked_category

        members = [] if is_pr else _read_members(data.get('members'), customer_type)

        errors, dob, spouse_dob = _validate(f, customer_type, members, 'edit', no, locked_category)
        if errors:
            return _errors_response(errors)

        if is_pr:
            result = db.session.execute(
                text("""
                    UPDATE MCMOWatchList SET
                        Name = :name, Address = :address, ID_Card = :id_card, DOB = :dob, Phone = :phone,
                        Spouse_Name = :spouse_name, SpouseIDCard = :spouse_idcard, SpouseDOB = :spouse_dob,
                        Mother = :mother, LastUser = :last_user, LastUpdate = SYSDATETIME(),
                        Reason = :remark, Reason_Category = :reason_category,
                        Reason_Other = :reason_other, NPWP = :npwp
                    WHERE No = :no AND ISNULL(FlagDel, '0') <> '1' AND Flag_Type = 'B'
                """),
                {
                    "name": f['name'], "address": f['address'], "id_card": f['id_card'],
                    "dob": dob, "phone": f['phone'],
                    "spouse_name": f['spouse_name'], "spouse_idcard": f['spouse_idcard'],
                    "spouse_dob": spouse_dob, "mother": f['mother'], "last_user": username,
                    "remark": f['remark'], "reason_category": f['reason_category'],
                    "reason_other": f['reason_other'], "npwp": f['npwp'], "no": no,
                }
            )
        else:
            result = db.session.execute(
                text("""
                    UPDATE MCMOWatchList SET
                        Name = :name, Address = :address, Phone = :phone,
                        ContactPerson = :contact_person, ContactAddress = :contact_address,
                        Lessee_Cat = :lessee_cat, DOB = :dob,
                        LastUser = :last_user, LastUpdate = SYSDATETIME(),
                        Reason = :remark, Reason_Category = :reason_category,
                        Reason_Other = :reason_other, NPWP = :npwp
                    WHERE No = :no AND ISNULL(FlagDel, '0') <> '1' AND Flag_Type = 'B'
                """),
                {
                    "name": f['name'], "address": f['address'], "phone": f['phone'],
                    "contact_person": f['contact_person'], "contact_address": f['contact_address'],
                    "lessee_cat": f['lessee_cat'], "dob": dob, "last_user": username,
                    "remark": f['remark'], "reason_category": f['reason_category'],
                    "reason_other": f['reason_other'], "npwp": f['npwp'], "no": no,
                }
            )

        if result.rowcount == 0:
            db.session.rollback()
            return jsonify({"error": "Record not found"}), 404

        _save_members(no, customer_type, f['lessee_cat'], members, replace=True)

        db.session.commit()
        return jsonify({"message": "success"})
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Update blacklist error")
        return jsonify({"error": str(e)}), 500