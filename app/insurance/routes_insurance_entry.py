from flask import Blueprint, jsonify, request, current_app, session
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text
import re
import httpx

insurance_entry_bp = Blueprint('insurance_entry', __name__, url_prefix='/InsuranceEntry')

def _clean_lease(lease_no: str) -> str:
    return re.sub(r'\s+', '', lease_no)

@insurance_entry_bp.route('/companies')
@login_required
def get_companies():
    try:
        result = db.session.execute(text("""
            SELECT INS_CD, INS_CO
            FROM UMFINSCD
            WHERE INS_CD IN ('01', '02')
        """))
        return jsonify([{"INS_CD": r[0], "INS_CO": r[1]} for r in result])
    except Exception:
        current_app.logger.exception("companies error")
        return jsonify([])

@insurance_entry_bp.route('/list')
@login_required
def get_list():
    ins_cd     = request.args.get('ins_cd',     '00')
    search_val = request.args.get('search_val', '')
    is_failed  = request.args.get('is_failed',  0, type=int)
    page       = request.args.get('page',       1, type=int)
    limit      = request.args.get('limit',      25, type=int)

    try:
        result = db.session.execute(
            text("EXEC USP_INSURANCE_ENTRY :ins_cd, :search_val, :is_failed"),
            {"ins_cd": ins_cd, "search_val": search_val, "is_failed": is_failed},
        )
        all_rows = [
            {
                "lease_no":   row.Lease_No        or "",
                "lessee_nm":  row.LESSEE_NM       or "",
                "ins_co":     row.INS_CO           or "",
                "policy_no":  row.PolicyNo         or "",
                "execution":  str(row.Execution)   if row.Execution  else "",
                "status":     row.ResponseStatus   or "",
                "respond":    row.ResponseMessage  or "",
                "success_dt": str(row.success_dt)  if row.success_dt else "",
            }
            for row in result
        ]

        total     = len(all_rows)
        start     = (page - 1) * limit
        paginated = all_rows[start:start + limit]

        return jsonify({"data": paginated, "total": total})

    except Exception:
        current_app.logger.exception("insurance list error")
        return jsonify({"error": "Failed to load"}), 500

@insurance_entry_bp.route('/contract')
@login_required
def get_contract():
    lease_no = request.args.get('lease_no', '').strip()
    if not lease_no:
        return jsonify({"error": "lease_no is required"}), 400

    try:
        result = db.session.execute(
            text("EXEC USP_GET_INSURANCE_ENTRY_DATA :lease_no"),
            {"lease_no": lease_no},
        )
        rows = result.fetchall()

        if not rows:
            return jsonify({"error": "Data already exist"}), 409

        data = [
            {
                "MSTR_CL":   row.MSTR_CL   or "",
                "lease_no":  row.lease_no  or "",
                "lessee_no": row.lessee_no or "",
                "LESSEE_NM": row.LESSEE_NM or "",
                "INS_CD":    row.INS_CD    or "",
                "INS_CO":    row.INS_CO    or "",
            }
            for row in rows
        ]
        return jsonify(data)

    except Exception:
        current_app.logger.exception("get contract error")
        return jsonify({"error": "Failed to fetch contract"}), 500

@insurance_entry_bp.route('/save', methods=['POST'])
@login_required
def save_insurance():
    body       = request.get_json(force=True) or {}
    array_data = body.get('arrayData', [])
    username   = session.get('username', 'SYSTEM')

    if not array_data:
        return jsonify({"error": "No data provided"}), 400

    try:
        values_clauses = []
        params: dict = {}

        for i, item in enumerate(array_data):
            lease_no = _clean_lease(item.get('lease_no', ''))
            k_lease  = f"lease_{i}"
            k_user   = f"user_{i}"
            values_clauses.append(f"(:{k_lease}, GETDATE(), :{k_user})")
            params[k_lease] = lease_no
            params[k_user]  = username

        insert_sql = (
            "INSERT INTO INSURANCE_COVER (Lease_No, cover_dt, create_by) VALUES "
            + ", ".join(values_clauses)
        )
        db.session.execute(text(insert_sql), params)
        db.session.commit()

        _fire_h2h_requests(array_data)

        return jsonify({"success": True})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("save insurance error")
        return jsonify({"error": "Failed to save"}), 500
    
def _fire_h2h_requests(array_data: list[dict]) -> None:
    h2h_urls = current_app.config.get("INSURANCE_H2H_URLS", {})
    verify_ssl = current_app.config.get("INSURANCE_H2H_VERIFY_SSL", False)
    timeout = current_app.config.get("INSURANCE_H2H_TIMEOUT", 30)

    with httpx.Client(verify=verify_ssl, timeout=timeout) as client:
        for item in array_data:
            ins_cd   = item.get('ins_cd', '').strip()
            lease_no = _clean_lease(item.get('lease_no', ''))
            url      = h2h_urls.get(ins_cd)
            if not url:
                current_app.logger.warning("Unknown or unconfigured ins_cd %s — skipping H2H call", ins_cd)
                continue
            try:
                client.post(url, data={"lease_no": lease_no})
            except Exception:
                current_app.logger.exception("H2H call failed for lease_no=%s", lease_no)

@insurance_entry_bp.route('/cancel', methods=['POST'])
@login_required
def cancel_insurance():
    body     = request.get_json(force=True) or {}
    lease_no = _clean_lease(body.get('lease_no', ''))

    if not lease_no:
        return jsonify({"success": False, "error": "lease_no is required"}), 400

    try:
        db.session.execute(
            text("DELETE FROM INSURANCE_COVER WHERE Lease_No = :lease_no"),
            {"lease_no": lease_no},
        )
        db.session.commit()
        return jsonify({"success": True})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("cancel insurance error")
        return jsonify({"success": False, "error": "Cancel failed"}), 500