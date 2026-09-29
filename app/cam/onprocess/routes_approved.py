import calendar
from datetime import date

from flask import Blueprint, jsonify, request, current_app, session
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text

approved_cam_bp = Blueprint("approved_cam_bp", __name__, url_prefix="/CAM")

HQ_APPROVER_LEVELS = ("CRH", "CRDH", "DR", "PD", "ODH")

def _get_session_ctx() -> dict:
    return {
        "emp_id":       session.get("emp_id", ""),
        "username":     session.get("username", ""),
        "access_level": session.get("accesslevel", ""),
        "branch_cd":    session.get("branchcode", ""),
    }

def _months_ago(d: date, months: int) -> date:
    month = d.month - months
    year = d.year
    while month <= 0:
        month += 12
        year -= 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)

def _group_hq_approvers_query(username, search_by, search_val, lastmonth):
    base_from = """
        FROM MCMOCAMStatus a WITH (NOLOCK)
            LEFT JOIN MCMOCAMCompleteList b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
            LEFT JOIN CLFCONT d WITH (NOLOCK) ON a.APPL_NO = d.APPL_NO
            LEFT JOIN MCMOREVISI e WITH (NOLOCK) ON a.APPL_NO = e.OldAppl_No
    """
    where_common = """
        a.APPR_STS = 'E'
        AND (d.EXECUTION IS NULL OR d.EXECUTION = '')
        AND b.AdmSts = '1'
        AND a.APPL_NO <> ISNULL(e.OldAppl_No, 0)
    """
    params = {}
    if not search_val:
        sql = f"SELECT DISTINCT a.APPL_NO, b.AdmDate, a.APPR_ID_From {base_from} WHERE {where_common} AND b.AdmDate >= :lastmonth"
        params["lastmonth"] = lastmonth
    elif search_by == "1":
        sql = f"""
            SELECT x.APPL_NO, x.AdmDate, x.APPR_ID_From FROM (
                SELECT DISTINCT a.APPL_NO, b.AdmDate, a.APPR_ID_From {base_from} WHERE {where_common}
            ) x WHERE x.APPL_NO = :search_val
        """
        params["search_val"] = search_val
    else:
        sql = f"""
            SELECT DISTINCT a.APPL_NO, b.AdmDate, a.APPR_ID_From
            {base_from}
            LEFT JOIN CAFCONT f WITH (NOLOCK) ON a.APPL_NO = f.APPL_NO
            LEFT JOIN CAFLESS g WITH (NOLOCK) ON f.APLESS = g.APLESS
            WHERE {where_common} AND g.LESSEE_NM LIKE :search_val
        """
        params["search_val"] = f"%{search_val}%"
    return sql, params


def _group_branch_approvers_query(branch_cd, search_by, search_val, lastmonth):
    branch_filter_join = """
        RIGHT JOIN (
            SELECT x.APPL_NO, z.BRANCH_CD
            FROM MCMOCAMStatus x WITH (NOLOCK)
            LEFT JOIN CAFCONT z WITH (NOLOCK) ON z.APPL_NO = x.APPL_NO
            WHERE z.BRANCH_CD = :branch_cd
            GROUP BY x.APPL_NO, z.BRANCH_CD
        ) c ON a.APPL_NO = c.APPL_NO
    """
    base_from = f"""
        FROM MCMOCAMStatus a WITH (NOLOCK)
        LEFT JOIN MCMOCAMCompleteList b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
        {branch_filter_join}
        LEFT JOIN CLFCONT d WITH (NOLOCK) ON a.APPL_NO = d.APPL_NO
        LEFT JOIN MCMOREVISI e WITH (NOLOCK) ON a.APPL_NO = e.OldAppl_No
    """
    where_common = """
        a.APPR_STS = 'E'
        AND (d.EXECUTION IS NULL OR d.EXECUTION = '')
        AND b.AdmSts = '1'
        AND a.APPL_NO <> ISNULL(e.OldAppl_No, 0)
    """
    params = {"branch_cd": branch_cd}
    if not search_val:
        sql = f"SELECT DISTINCT a.APPL_NO, b.AdmDate, a.APPR_ID_From {base_from} WHERE {where_common} AND b.AdmDate >= :lastmonth"
        params["lastmonth"] = lastmonth
    elif search_by == "1":
        sql = f"""
            SELECT x.APPL_NO, x.AdmDate, x.APPR_ID_From FROM (
                SELECT DISTINCT a.APPL_NO, b.AdmDate, a.APPR_ID_From {base_from} WHERE {where_common}
            ) x WHERE x.APPL_NO = :search_val
        """
        params["search_val"] = search_val
    else:
        sql = f"""
            SELECT DISTINCT a.APPL_NO, b.AdmDate, a.APPR_ID_From
            {base_from}
            LEFT JOIN CAFCONT f WITH (NOLOCK) ON c.APPL_NO = f.APPL_NO
            LEFT JOIN CAFLESS g WITH (NOLOCK) ON f.APLESS = g.APLESS
            WHERE {where_common} AND g.LESSEE_NM LIKE :search_val
        """
        params["search_val"] = f"%{search_val}%"
    return sql, params


def _group_ca_hq_query(search_by, search_val, lastmonth):
    branch_filter_join = """
        RIGHT JOIN (
            SELECT x.APPL_NO
            FROM MCMOCAMStatus x WITH (NOLOCK)
            LEFT JOIN CAFCONT z WITH (NOLOCK) ON z.APPL_NO = x.APPL_NO
            GROUP BY x.APPL_NO
        ) c ON a.APPL_NO = c.APPL_NO
    """
    base_from = f"""
        FROM MCMOCAMStatus a WITH (NOLOCK)
        LEFT JOIN MCMOCAMCompleteList b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
        {branch_filter_join}
        LEFT JOIN CLFCONT d WITH (NOLOCK) ON a.APPL_NO = d.APPL_NO
        LEFT JOIN MCMOREVISI e WITH (NOLOCK) ON a.APPL_NO = e.OldAppl_No
    """
    where_common = """
        (a.APPR_STS = 'E' OR a.APPR_STS = 'F')
        AND (d.EXECUTION IS NULL OR d.EXECUTION = '')
        AND b.AdmSts = '1'
        AND a.APPL_NO <> ISNULL(e.OldAppl_No, 0)
    """
    params = {}
    if not search_val:
        sql = f"SELECT DISTINCT a.APPL_NO, b.AdmDate, a.APPR_ID_From {base_from} WHERE {where_common} AND b.AdmDate >= :lastmonth"
        params["lastmonth"] = lastmonth
    elif search_by == "1":
        sql = f"""
            SELECT x.APPL_NO, x.AdmDate, x.APPR_ID_From FROM (
                SELECT DISTINCT a.APPL_NO, b.AdmDate, a.APPR_ID_From {base_from} WHERE {where_common}
            ) x WHERE x.APPL_NO = :search_val
        """
        params["search_val"] = search_val
    else:
        sql = f"""
            SELECT DISTINCT a.APPL_NO, b.AdmDate, a.APPR_ID_From
            {base_from}
            LEFT JOIN CAFCONT f WITH (NOLOCK) ON c.APPL_NO = f.APPL_NO
            LEFT JOIN CAFLESS g WITH (NOLOCK) ON f.APLESS = g.APLESS
            WHERE {where_common} AND g.LESSEE_NM LIKE :search_val
        """
        params["search_val"] = f"%{search_val}%"
    return sql, params

def _group_default_query(username, emp_id, search_by, search_val, lastmonth):
    join_tail = """
        LEFT JOIN CLFCONT d WITH (NOLOCK) ON a.APPL_NO = d.APPL_NO
        LEFT JOIN MCMOREVISI e WITH (NOLOCK) ON a.APPL_NO = e.OldAppl_No
    """
    watchlist_branch = """
        SELECT a.APPL_NO,
               CASE WHEN a.CreateDate IS NULL THEN DATEADD(yy, -3, GETDATE()) ELSE a.CreateDate END AS AdmDate,
               'Reject to watchlist' AS NAMACMO, a.APPR_ID_From, a.appr_id
        FROM MCMOCAMStatus a WITH (NOLOCK)
            LEFT JOIN CAFCONT b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
        WHERE a.APPR_STS = 'RW'
          AND b.cmo IN (SELECT EMPLOYEE_ID FROM APP_USRMST WHERE username LIKE :username)
    """
    params = {"username": username, "emp_id": emp_id}

    if not search_val:
        approver_branch = f"""
            SELECT DISTINCT a.APPL_NO, b.AdmDate, '' AS NAMACMO, a.APPR_ID_From, a.appr_id
            FROM MCMOCAMStatus a WITH (NOLOCK)
                LEFT JOIN MCMOCAMCompleteList b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
                RIGHT JOIN (
                    SELECT APPL_NO FROM MCMOCAMStatus WITH (NOLOCK)
                    WHERE APPR_ID = :username OR (APPR_ID_From = :username AND APPR_STS = 'N')
                    UNION
                    SELECT APPL_NO FROM MCMOCAMOUTSSTATUS WITH (NOLOCK)
                    WHERE APPR_ID = :username OR (APPR_ID_From = :username AND APPR_STS = 'N')
                    GROUP BY APPL_NO
                ) c ON a.APPL_NO = c.APPL_NO
            {join_tail}
            WHERE a.APPR_STS = 'E' AND (d.EXECUTION IS NULL OR d.EXECUTION = '')
              AND b.AdmSts = '1' AND b.AdmDate >= :lastmonth
              AND a.APPL_NO <> ISNULL(e.OldAppl_No, 0)
        """
        cmo_branch = f"""
            SELECT DISTINCT a.APPL_NO, b.AdmDate, '' AS NAMACMO, a.APPR_ID_From, a.appr_id
            FROM MCMOCAMStatus a WITH (NOLOCK)
            LEFT JOIN MCMOCAMCompleteList b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
            {join_tail}
            WHERE a.APPR_STS = 'E' AND (d.EXECUTION IS NULL OR d.EXECUTION = '')
              AND b.AdmSts = '1' AND b.AdmDate >= :lastmonth
              AND d.CMO = :emp_id AND a.APPL_NO <> ISNULL(e.OldAppl_No, 0)
        """
        params["lastmonth"] = lastmonth
        return f"{approver_branch} UNION {cmo_branch} UNION {watchlist_branch}", params

    approver_id_clause = "APPR_ID = :username" if search_by == "1" else "APPR_ID = ''"

    if search_by == "1":
        approver_branch = f"""
            SELECT DISTINCT a.APPL_NO, b.AdmDate, '' AS NAMACMO, a.APPR_ID_From, a.appr_id
            FROM MCMOCAMStatus a WITH (NOLOCK)
            LEFT JOIN MCMOCAMCompleteList b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
            RIGHT JOIN (
                SELECT APPL_NO FROM MCMOCAMStatus WITH (NOLOCK)
                WHERE ({approver_id_clause} OR APPR_ID_From = :username) AND APPR_STS = 'N'
                GROUP BY APPL_NO
            ) c ON a.APPL_NO = c.APPL_NO
            {join_tail}
            WHERE a.APPR_STS = 'E' AND (d.EXECUTION IS NULL OR d.EXECUTION = '')
              AND b.AdmSts = '1' AND a.APPL_NO <> ISNULL(e.OldAppl_No, 0)
        """
        cmo_branch = f"""
            SELECT DISTINCT a.APPL_NO, b.AdmDate, '' AS NAMACMO, a.APPR_ID_From, a.appr_id
            FROM MCMOCAMStatus a WITH (NOLOCK)
            LEFT JOIN MCMOCAMCompleteList b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
            {join_tail}
            WHERE a.APPR_STS = 'E' AND (d.EXECUTION IS NULL OR d.EXECUTION = '')
              AND b.AdmSts = '1' AND d.CMO = :emp_id AND a.APPL_NO <> ISNULL(e.OldAppl_No, 0)
        """
        inner = f"{approver_branch} UNION {cmo_branch} UNION {watchlist_branch}"
        params["search_val"] = search_val
        return f"SELECT x.* FROM ({inner}) x WHERE x.APPL_NO = :search_val", params

    approver_branch = f"""
        SELECT DISTINCT a.APPL_NO, b.AdmDate, '' AS NAMACMO, a.APPR_ID_From, a.appr_id
        FROM MCMOCAMStatus a WITH (NOLOCK)
        LEFT JOIN MCMOCAMCompleteList b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
        RIGHT JOIN (
            SELECT APPL_NO FROM MCMOCAMStatus WITH (NOLOCK)
            WHERE ({approver_id_clause} OR APPR_ID_From = :username) AND APPR_STS = 'N'
            GROUP BY APPL_NO
        ) c ON a.APPL_NO = c.APPL_NO
        {join_tail}
        LEFT JOIN CAFCONT f WITH (NOLOCK) ON c.APPL_NO = f.APPL_NO
        LEFT JOIN CAFLESS g WITH (NOLOCK) ON f.APLESS = g.APLESS
        WHERE a.APPR_STS = 'E' AND (d.EXECUTION IS NULL OR d.EXECUTION = '')
          AND b.AdmSts = '1' AND a.APPL_NO <> ISNULL(e.OldAppl_No, 0)
          AND g.LESSEE_NM LIKE :search_val
    """
    cmo_branch = f"""
        SELECT DISTINCT a.APPL_NO, b.AdmDate, '' AS NAMACMO, a.APPR_ID_From, a.appr_id
        FROM MCMOCAMStatus a WITH (NOLOCK)
        LEFT JOIN MCMOCAMCompleteList b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
        {join_tail}
        LEFT JOIN CAFCONT f WITH (NOLOCK) ON a.APPL_NO = f.APPL_NO
        LEFT JOIN CAFLESS g WITH (NOLOCK) ON f.APLESS = g.APLESS
        WHERE a.APPR_STS = 'E' AND (d.EXECUTION IS NULL OR d.EXECUTION = '')
          AND b.AdmSts = '1' AND d.CMO = :emp_id AND a.APPL_NO <> ISNULL(e.OldAppl_No, 0)
          AND g.LESSEE_NM LIKE :search_val
    """
    params["search_val"] = f"%{search_val}%"
    return f"{approver_branch} UNION {cmo_branch} UNION {watchlist_branch}", params

def _build_approved_query(access_level, branch_cd, emp_id, username, search_by, search_val, lastmonth):
    if access_level in HQ_APPROVER_LEVELS:
        sql, params = _group_hq_approvers_query(username, search_by, search_val, lastmonth)
        extra_order_by = None
    elif access_level in ("BM", "MAO") or (access_level == "CA" and branch_cd != "01"):
        sql, params = _group_branch_approvers_query(branch_cd, search_by, search_val, lastmonth)
        extra_order_by = None
    elif access_level == "CA" and branch_cd == "01":
        sql, params = _group_ca_hq_query(search_by, search_val, lastmonth)
        extra_order_by = "AdmDate DESC, APPR_ID_From DESC"
    else:
        sql, params = _group_default_query(username, emp_id, search_by, search_val, lastmonth)
        extra_order_by = None
    return sql, params, extra_order_by

def _fetch_approved_page(sql, params, offset, end, extra_order_by=None):
    paged_sql = f"""
        SELECT * FROM (
            SELECT *, ROW_NUMBER() OVER (ORDER BY AdmDate DESC, APPL_NO DESC) AS ROW_NUM
            FROM ({sql}) inner_q
        ) ranked
        WHERE ROW_NUM BETWEEN :offset AND :end
    """
    if extra_order_by:
        paged_sql += f" ORDER BY {extra_order_by}"

    rows = db.session.execute(text(paged_sql), dict(params, offset=offset, end=end)).mappings().all()
    total = db.session.execute(text(f"SELECT COUNT(*) FROM ({sql}) inner_q"), params).scalar() or 0
    return total, rows

@approved_cam_bp.route("/approved")
@login_required
def get_cam_approved():
    ctx = _get_session_ctx()
    emp_id = ctx["emp_id"]
    username = ctx["username"]
    access_level = ctx["access_level"]
    branch_cd = ctx["branch_cd"]

    page = request.args.get("page", 1, type=int)
    limit = request.args.get("limit", 25, type=int)
    search_by = request.args.get("search_by", "")
    search_val = request.args.get("search_val", "")

    offset = (page - 1) * limit + 1
    end = page * limit
    lastmonth = _months_ago(date.today(), 9)

    try:
        sql, params, extra_order_by = _build_approved_query(
            access_level, branch_cd, emp_id, username, search_by, search_val, lastmonth
        )
        total, rows = _fetch_approved_page(sql, params, offset, end, extra_order_by)

        data = []
        seen_appl = set()
        for row in rows:
            appl_no = str(row.get("APPL_NO", "")).strip()
            if not appl_no or appl_no in seen_appl:
                continue
            seen_appl.add(appl_no)

            detail = db.session.execute(
                text("""
                    SELECT a.HAS_GUARANTOR, a.Cons_Leas, a.TENOR, a.APLESS,
                           b.LESSEE_TP, c.SUPP, LTRIM(RTRIM(c.[CONDITION])) AS CONDITION
                    FROM CAFCONT a WITH (NOLOCK)
                        LEFT JOIN CAFLESS b WITH (NOLOCK) ON a.APLESS = b.APLESS
                        LEFT JOIN CAFEQUIP c WITH (NOLOCK) ON a.APPL_NO = c.APPL_NO
                    WHERE a.APPL_NO = :appl
                """),
                {"appl": appl_no}
            ).mappings().first() or {}

            fin_type = str(detail.get("Cons_Leas", "") or "")
            tenor = str(detail.get("TENOR", "") or "")
            has_guarantor_raw = detail.get("HAS_GUARANTOR")
            guarantor = "1" if has_guarantor_raw in (None, "0") else "2"
            ind_cor = "1" if detail.get("LESSEE_TP") == "PR" else "2"
            c2c = "2" if detail.get("SUPP") == 999999 else "1"
            new_car = "2" if (detail.get("CONDITION") or "").strip() == "NEW" else "1"

            revisi = db.session.execute(
                text("SELECT REVISI FROM MCMOREVISI WITH (NOLOCK) WHERE NEWAPPL_NO = :appl"),
                {"appl": appl_no}
            ).scalar()
            str_revisi = f"R{revisi}" if revisi is not None else ""

            corp_ret = db.session.execute(
                text("SELECT CORP_RET FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :appl"),
                {"appl": appl_no}
            ).scalar()
            str_multiple = "M" if corp_ret == "M" else ""

            already_revised = db.session.execute(
                text("SELECT TOP 1 1 FROM MCMOREVISI WITH (NOLOCK) WHERE OLDAPPL_NO = :appl"),
                {"appl": appl_no}
            ).scalar()

            last_status = db.session.execute(
                text("SELECT TOP 1 APPR_STS FROM MCMOCAMStatus WITH (NOLOCK) WHERE APPL_NO = :appl ORDER BY No DESC"),
                {"appl": appl_no}
            ).scalar()
            rejected_to_watchlist_status = (last_status or "").strip() == "RW"

            cbg = db.session.execute(
                text("""
                    SELECT c.NICKNAME AS Nname
                    FROM CAFCONT a WITH (NOLOCK)
                        LEFT JOIN APP_USRMST b WITH (NOLOCK) ON a.CMO = b.EMPLOYEE_ID
                        LEFT JOIN UMFBRANCH c WITH (NOLOCK) ON b.BRANCHCODE = c.BRANCH_CD
                    WHERE a.APPL_NO = :appl
                """),
                {"appl": appl_no}
            ).mappings().first()
            cbgnow = (cbg or {}).get("Nname") or ""

            owner = db.session.execute(
                text("""
                    SELECT LTRIM(RTRIM(a.CMO)) AS CMO, a.APLESS, b.LESSEE_NM
                    FROM CAFCONT a WITH (NOLOCK)
                    LEFT JOIN CAFLESS b WITH (NOLOCK) ON a.APLESS = b.APLESS
                    WHERE a.APPL_NO = :appl
                """),
                {"appl": appl_no}
            ).mappings().first() or {}
            apless = str(owner.get("APLESS", "") or "")
            cmo_of_contract = str(owner.get("CMO", "") or "")

            can_revise = (
                cmo_of_contract == emp_id
                and not already_revised
                and not rejected_to_watchlist_status
            )

            date_trans = db.session.execute(
                text("SELECT DateTrans FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :appl"),
                {"appl": appl_no}
            ).scalar()
            can_withdraw = (
                (date_trans is None or date_trans == "")
                and access_level in HQ_APPROVER_LEVELS
                and str(row.get("APPR_ID_From", "") or "") == username
            )

            has_bo = db.session.execute(
                text("SELECT TOP 1 1 FROM BENEFICIARY_LINK WITH (NOLOCK) WHERE APPL_NO = :appl"),
                {"appl": appl_no}
            ).scalar()
            menmen = 10 if has_bo else 9

            namacmo = str(row.get("NAMACMO", "") or "")
            if namacmo == "Reject to watchlist":
                status = "Reject to watchlist"
                last_approved = str(row.get("appr_id", "") or "")
            else:
                status = "APPROVED"
                last_approved = str(row.get("APPR_ID_From", "") or "")

            adm_date = row.get("AdmDate")
            tgl = adm_date.strftime("%d-%m-%Y %H:%M:%S") if adm_date else ""

            data.append({
                "appl_no":       appl_no,
                "tgl":           tgl,
                "cons_leas":     fin_type,
                "lessee_nm":     str(owner.get("LESSEE_NM", "") or ""),
                "status":        status,
                "last_approved": last_approved,
                "cbgnow":        cbgnow,
                "color":         "revise" if str_revisi else "default",
                "str_revisi":    str_revisi,
                "str_multiple":  str_multiple,
                "fin_type":      fin_type,
                "ind_cor":       ind_cor,
                "guarantor":     guarantor,
                "new_car":       new_car,
                "tenor":         tenor,
                "c2c":           c2c,
                "apless":        apless,
                "menmen":        menmen,
                "can_withdraw":  can_withdraw,
                "can_revise":    can_revise,
            })

        return jsonify({"data": data, "total": total})

    except Exception:
        current_app.logger.exception("CAM approved error")
        return jsonify({"error": "Failed to load data"}), 500