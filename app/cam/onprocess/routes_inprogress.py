from flask import Blueprint, jsonify, request, current_app, session
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text

inprogress_cam_bp = Blueprint("inprogress_cam_bp", __name__, url_prefix="/CAM")

def _get_session_ctx() -> dict:
    return {
        "emp_id":       session.get("emp_id", ""),
        "username":     session.get("username", ""),
        "access_level": session.get("accesslevel", ""),
        "branch_cd":    session.get("branchcode", ""),
    }

def _build_list_query(username: str, search_by: str, search_val: str):
    params = {"username": username}

    base_union = """
        SELECT a.APPL_NO, a.APPR_STS, a.[No], a.CreateDate, a.APPR_ID, a.APPR_ID_From
        FROM MCMOCAMStatus a WITH (NOLOCK)
        WHERE a.APPR_STS = 'P' AND a.APPR_ID <> :username
            AND a.APPL_NO IN (
                SELECT APPL_NO FROM MCMOCAMStatus WITH (NOLOCK)
                WHERE APPR_ID = :username AND APPR_STS NOT IN ('P', 'R', 'T')
            )
          
        UNION
        
        SELECT a.APPL_NO, a.APPR_STS, a.[No], a.CreateDate, a.APPR_ID, a.APPR_ID_From
        FROM MCMOCAMStatus a WITH (NOLOCK)
        WHERE a.APPR_STS = 'P' AND a.APPR_ID <> :username
            AND a.APPL_NO IN (
                SELECT APPL_NO FROM MCMOCAMoutsStatus WITH (NOLOCK)
                WHERE APPR_ID = :username AND APPR_STS NOT IN ('P', 'R', 'T')
            )
        
        UNION
        
        SELECT a.APPL_NO, a.APPR_STS, a.[No], a.CREATE_DATE AS CreateDate, a.APPR_ID, a.APPR_ID_From
        FROM MCMOCAMoutsStatus a WITH (NOLOCK)
        WHERE a.APPR_STS = 'P' AND a.APPR_ID <> :username
            AND a.APPL_NO IN (
                SELECT APPL_NO FROM MCMOCAMoutsStatus WITH (NOLOCK)
                WHERE APPR_ID = :username AND APPR_STS NOT IN ('P', 'T')
            )
    """

    if search_val and search_by == "2":
        sql = f"""
            SELECT x.APPL_NO, x.APPR_STS, x.[No], x.CreateDate, x.APPR_ID, x.APPR_ID_From
            FROM ({base_union}) x
                INNER JOIN CAFCONT c WITH (NOLOCK) ON x.APPL_NO = c.APPL_NO
                INNER JOIN CAFLESS d WITH (NOLOCK) ON c.APLESS = d.APLESS
            WHERE d.LESSEE_NM LIKE :search_val
        """
        params["search_val"] = f"%{search_val}%"
    elif search_val and search_by == "1":
        sql = f"""
            SELECT a.APPL_NO, a.APPR_STS, a.[No], a.CreateDate, a.APPR_ID, a.APPR_ID_From
            FROM ({base_union}) a
            WHERE a.APPL_NO = :search_val
        """
        params["search_val"] = search_val
    else:
        sql = base_union

    return sql, params

def _fetch_inprogress_page(username: str, offset: int, end: int, search_by: str, search_val: str):
    sql, params = _build_list_query(username, search_by, search_val)

    paged_sql = f"""
        SELECT * FROM (
            SELECT *, ROW_NUMBER() OVER (ORDER BY CreateDate DESC, APPL_NO DESC) AS ROW_NUM
            FROM ({sql}) inner_q
        ) ranked
        WHERE ROW_NUM BETWEEN :offset AND :end
    """
    rows = db.session.execute(
        text(paged_sql), dict(params, offset=offset, end=end)
    ).mappings().all()

    total = db.session.execute(
        text(f"SELECT COUNT(*) FROM ({sql}) inner_q"), params
    ).scalar() or 0

    return total, rows

@inprogress_cam_bp.route("/inprogress")
@login_required
def get_cam_inprogress():
    ctx = _get_session_ctx()
    username = ctx["username"]

    page = request.args.get("page", 1, type=int)
    limit = request.args.get("limit", 25, type=int)
    search_by = request.args.get("search_by", "")
    search_val = request.args.get("search_val", "")

    offset = (page - 1) * limit + 1
    end = page * limit

    try:
        total, rows = _fetch_inprogress_page(username, offset, end, search_by, search_val)

        data = []
        for row in rows:
            appl_no = str(row.get("APPL_NO", "")).strip()
            if not appl_no:
                continue

            detail = db.session.execute(
                text("""
                    SELECT a.HAS_GUARANTOR, a.Cons_Leas, a.TENOR, a.APLESS,
                           a.PURPOFFINC, a.cont_type,
                           b.LESSEE_TP, b.LESSEE_NM, c.SUPP,
                           LTRIM(RTRIM(c.[CONDITION])) AS CONDITION
                    FROM CAFCONT a WITH (NOLOCK)
                        LEFT JOIN CAFLESS b WITH (NOLOCK) ON a.APLESS = b.APLESS
                        LEFT JOIN CAFEQUIP c WITH (NOLOCK) ON a.APPL_NO = c.APPL_NO
                    WHERE a.APPL_NO = :appl
                """),
                {"appl": appl_no}
            ).mappings().first() or {}

            fin_type = str(detail.get("Cons_Leas", "") or "")
            tenor = str(detail.get("TENOR", "") or "")
            apless = str(detail.get("APLESS", "") or "")
            purpoffinc = str(detail.get("PURPOFFINC", "") or "")
            cont_type = str(detail.get("cont_type", "") or "")
            guarantor = "2" if detail.get("HAS_GUARANTOR") == "1" else "1"
            ind_cor = "1" if detail.get("LESSEE_TP") == "PR" else "2"
            c2c = "1" if detail.get("SUPP") == 999999 else "0"
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

            if cbgnow == "CO":
                continue

            has_bo = db.session.execute(
                text("SELECT TOP 1 1 FROM BENEFICIARY_LINK WITH (NOLOCK) WHERE APPL_NO = :appl"),
                {"appl": appl_no}
            ).scalar()
            menmen = 10 if has_bo else 9

            tgl_raw = row.get("CreateDate")
            tgl = tgl_raw.strftime("%d-%m-%Y %H:%M:%S") if tgl_raw else ""

            data.append({
                "appl_no":      appl_no,
                "tgl":          tgl,
                "cons_leas":    fin_type,
                "lessee_nm":    str(detail.get("LESSEE_NM", "") or ""),
                "appr_id":      str(row.get("APPR_ID", "") or ""),
                "cbgnow":       cbgnow,
                "color":        "revise" if str_revisi else "default",
                "str_revisi":   str_revisi,
                "str_multiple": str_multiple,
                "fin_type":     fin_type,
                "ind_cor":      ind_cor,
                "guarantor":    guarantor,
                "new_car":      new_car,
                "tenor":        tenor,
                "c2c":          c2c,
                "purpoffinc":   purpoffinc,
                "cont_type":    cont_type,
                "apless":       apless,
                "menmen":       menmen,
                "can_withdraw": str(row.get("APPR_ID_From", "") or "") == username,
            })

        return jsonify({"data": data, "total": total})

    except Exception:
        current_app.logger.exception("CAM inprogress error")
        return jsonify({"error": "Failed to load data"}), 500

@inprogress_cam_bp.route("/inprogress/withdraw", methods=["POST"])
@login_required
def withdraw_cam():
    ctx = _get_session_ctx()
    username = ctx["username"]
    access_level = ctx["access_level"]

    body = request.get_json(force=True) or {}
    appl_no = body.get("appl_no", "")

    if not appl_no:
        return jsonify({"success": False, "message": "Missing appl_no"}), 400

    try:
        audit = db.session.execute(
            text("""
                SELECT TOP 1 Event AS aksi, UserId
                FROM MCMOUserAudit WITH (NOLOCK)
                WHERE UserId IN (
                    SELECT appr_id FROM MCMOCAMStatus WITH (NOLOCK)
                    WHERE APPL_NO = :appl AND APPR_STS = 'P'
                )
                ORDER BY [No] DESC, Waktu DESC
            """),
            {"appl": appl_no}
        ).mappings().first() or {}

        event = audit.get("aksi") or ""
        reviewer_id = audit.get("UserId") or ""
        page_event = event[:12]
        appl_nobuka = event[-11:]

        mstr_can = db.session.execute(
            text("SELECT MSTR_CA FROM TAMASTER WITH (NOLOCK) WHERE APPL_NO = :appl"),
            {"appl": appl_nobuka}
        ).scalar() or ""
        mstr_cam = db.session.execute(
            text("SELECT MSTR_CA FROM TAMASTER WITH (NOLOCK) WHERE APPL_NO = :appl"),
            {"appl": appl_no}
        ).scalar() or ""

        if (mstr_can or mstr_cam) and mstr_can == mstr_cam:
            return jsonify({"success": False, "message": f"This CAM is being reviewed by {reviewer_id}"}), 409

        my_step = db.session.execute(
            text("""
                SELECT TOP 1 No, APPR_STS FROM MCMOCAMStatus WITH (NOLOCK)
                WHERE APPL_NO = :appl AND APPR_ID = :user AND APPR_STS IN ('A', 'N')
            """),
            {"appl": appl_no, "user": username}
        ).mappings().first() or {}
        nomornya, apprsts = my_step.get("No"), my_step.get("APPR_STS")

        my_last_step = db.session.execute(
            text("""
                SELECT TOP 1 No, APPR_STS FROM MCMOCAMStatus WITH (NOLOCK)
                WHERE APPL_NO = :appl AND APPR_ID = :user ORDER BY No DESC
            """),
            {"appl": appl_no, "user": username}
        ).mappings().first() or {}
        nomornya7, apprsts7 = my_last_step.get("No"), my_last_step.get("APPR_STS")

        def _next_status(after_no):
            if after_no is None:
                return None
            return db.session.execute(
                text("""
                    SELECT TOP 1 APPR_STS FROM MCMOCAMStatus WITH (NOLOCK)
                    WHERE APPL_NO = :appl AND No > :no ORDER BY No
                """),
                {"appl": appl_no, "no": after_no}
            ).scalar()

        next_status_a = _next_status(nomornya)
        next_status_b = _next_status(nomornya7)

        if next_status_a not in ("P", "E") and apprsts in ("A", "N"):
            approver_id = db.session.execute(
                text("""
                    SELECT TOP 1 appr_id FROM MCMOCAMStatus WITH (NOLOCK)
                    WHERE APPL_NO = :appl AND APPR_STS = 'A' ORDER BY No DESC
                """),
                {"appl": appl_no}
            ).scalar()
            return jsonify({"success": False, "message": f"This CAM has already been approved by {approver_id}"}), 409

        if next_status_b not in ("P", "E") and apprsts7 in ("R", "AR"):
            rejecter_id = db.session.execute(
                text("""
                    SELECT TOP 1 appr_id FROM MCMOCAMStatus WITH (NOLOCK)
                    WHERE APPL_NO = :appl AND APPR_STS = 'R' ORDER BY No DESC
                """),
                {"appl": appl_no}
            ).scalar()
            return jsonify({"success": False, "message": f"This CAM has already been rejected by {rejecter_id}"}), 409

        if page_event == "Cam Approval" and event[-11:] == appl_no:
            return jsonify({"success": False, "message": f"This CAM is being reviewed by {reviewer_id}"}), 409

        needs_outs_flag = db.session.execute(
            text("""
                SELECT TOP 1 1 FROM CAFCONT xx WITH (NOLOCK)
                    INNER JOIN CAFEQUIP cc WITH (NOLOCK) ON cc.APPL_NO = xx.APPL_NO
                    INNER JOIN CLFSUPP ss WITH (NOLOCK) ON ss.SUPP = cc.SUPP
                WHERE xx.APPL_NO = :appl
                    AND cc.CONDITION = 'NEW' AND ss.Supp_Type IN ('SI', 'SP', 'IU')
            """),
            {"appl": appl_no}
        ).scalar()

        approval_x = "0"
        if needs_outs_flag:
            pending_outs = db.session.execute(
                text("""
                    SELECT TOP 1 1 FROM MCMOCAMOUTSSTATUS WITH (NOLOCK)
                    WHERE APPL_NO = :appl AND appr_sts = 'P'
                """),
                {"appl": appl_no}
            ).scalar()
            approval_x = "1" if pending_outs else "0"

        db.session.execute(
            text("EXEC USP_CAM_SETWITHDRAW :appl_no, :username, :access_level, :approval_x"),
            {"appl_no": appl_no, "username": username, "access_level": access_level, "approval_x": approval_x}
        )
        db.session.commit()

        return jsonify({"success": True})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("CAM withdraw error")
        return jsonify({"success": False, "message": "Withdraw failed. Please try again."}), 500