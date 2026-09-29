from sqlalchemy import text
from app import db

def current_approval_level(appl_no):
    count = db.session.execute(text("""
        SELECT COUNT(*) AS cnt
        FROM MCMOCAMStatus WITH (NOLOCK) WHERE APPL_NO = :a
    """), {"a": appl_no}).mappings().first()
    return int((count or {}).get("cnt") or 0) + 1

def resolve_approval_context(appl_no, access_level, username):
    appr_plafond = ""
    approval_form_id = 1

    if access_level != "CMO":
        tot_outs_row = db.session.execute(text("""
            SELECT SUM(OUTS) AS tot_outs
            FROM CAFCUST_OUTS WITH (NOLOCK)
            WHERE APPL_NO = :a
                AND ASOF = (SELECT MAX(ASOF)
                            FROM CAFCUST_OUTS WITH (NOLOCK)
                            WHERE APPL_NO = :a)
        """), {"a": appl_no}).mappings().first()
        tot_outs = tot_outs_row.get("tot_outs") if tot_outs_row else None

        if tot_outs is not None:
            flow_row = db.session.execute(text("""
                SELECT TOP 1 OutstandingTo, ApprovalFormId
                FROM mstCamApprovalFlow WITH (NOLOCK)
                WHERE :tot_outs BETWEEN OutstandingFrom AND OutstandingTo
                ORDER BY OutstandingTo DESC
            """), {"tot_outs": tot_outs}).mappings().first()
            if flow_row:
                appr_plafond = flow_row["OutstandingTo"]
                approval_form_id = flow_row["ApprovalFormId"]
        else:
            doc_row = db.session.execute(text("""
                SELECT ApprovalFormId FROM documentApproval WHERE DocumentNumber = :a
            """), {"a": appl_no}).mappings().first()
            if doc_row and doc_row.get("ApprovalFormId"):
                approval_form_id = doc_row["ApprovalFormId"]

    role_row = db.session.execute(text("""
        SELECT TOP 1 [Role] FROM MCMOCAMStatus WHERE APPL_NO = :a AND APPR_ID = :u ORDER BY [No] DESC
    """), {"a": appl_no, "u": username}).mappings().first()
    effective_access_level = access_level
    if role_row and (role_row.get("Role") or "").strip():
        effective_access_level = role_row["Role"]

    level_row = db.session.execute(text("""
        SELECT ApprovalLevel
        FROM mstApprovalMatrix WITH (NOLOCK)
        WHERE ApprovalFormId = :form_id AND AccessLevel = :level
    """), {"form_id": approval_form_id, "level": effective_access_level}).mappings().first()
    appr_level_skrg = level_row["ApprovalLevel"] if level_row else 1

    return approval_form_id, appr_plafond, appr_level_skrg, effective_access_level

def get_next_available_approver(branch_code, username, current_approval_level=1, approval_form_id=1, appr_plafond='0'):
   
    next_approval_level = int(current_approval_level) + 1
    row = db.session.execute(text("""
        EXEC USP_CAM_GETAVAILABLEAPPROVER :level, :form_id, :branch_code, :username, :appr_plafond
    """), {
        "level": next_approval_level,
        "form_id": approval_form_id,
        "branch_code": branch_code,
        "username": username,
        "appr_plafond": appr_plafond,
    }).mappings().first()

    if row and (row.get("USERNAME") or "").strip():
        return f"{row['USERNAME']}|{row.get('AccessLevel', '')}"
    return "Admin|Admin"

def approver_option_from_raw(cmh):
    parts = cmh.split("|")
    name = parts[0] if parts else cmh
    label = "Send to Admin" if name.strip().upper() == "ADMIN" else name
    return {"value": cmh, "label": label}