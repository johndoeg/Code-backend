from datetime import datetime
from sqlalchemy import bindparam, text
from app.services.legacy_cam import (
    hitung_irr,
    get_next_available_approver,
    register_privy,
    check_finish_approval,
    send_telegram,
)

FUND_FACILITY_LIMIT = 500_000_000
CAPITAL_FACILITY_LIMIT = 10_000_000_000
INDIVIDUAL_ASSESSMENT_THRESHOLD = 3_000_000_000
ENFORCE_DEED_OF_ESTABLISHMENT = False
WATCHLIST_CAPABLE_ROLES = {'BM', 'CRH', 'CH', 'ODH', 'DR', 'PD', 'CRUH', 'OPDH'}
SURVEY_FIELD_ROLES = {'CR', 'CRH', 'CH', 'ODH', 'DR', 'PD', 'CRUH', 'CRDH', 'OPDH'}
SURVEY_NOT_REQUIRED_ROLES = {'CMO', 'BM', 'CMH', 'NCH'}

def get_cam_review_data(conn, appl_no, username, access_level, branch_cd):
    lock = _get_lock_status(conn, appl_no, username, access_level)
    is_multiple, l_amount, appl_no_list = _get_multiple_info(conn, appl_no)
    withdrawn_before = _row_exists(
        conn,
        "SELECT 1 FROM MCMOCAMStatus WITH (NOLOCK) WHERE APPL_NO=:appl_no AND APPR_STS LIKE 'T'",
        {"appl_no": appl_no},
    )

    header = _get_header_info(conn, appl_no)
    revision_suffix = _get_revision_suffix(conn, ",".join(appl_no_list))
    tot_outs = _get_total_outstanding(conn, appl_no)
    sent_to_admin = _get_sent_to_admin(conn, appl_no)
    lessee = _get_lessee_info(conn, header["apless"])
    watchlist = _get_watchlist(conn, lessee)
    equip = _get_equipment_info(conn, appl_no)

    approval_form_id = _get_approval_form_id(conn, access_level, appl_no, tot_outs)
    appr_level = _get_current_approval_level(conn, approval_form_id, access_level)

    fund_warning, fund_disabled = _fund_capital_warning(
        conn, header["fin_type"], header["apless"]
    ) if header["fin_type"] in ("D", "M", "W") else (None, False)
    ojk_warning, ojk_disabled = _ojk_warning(
        conn, header["fin_type"], header["apless"]
    ) if header["fin_type"] in ("D", "M", "W") else (None, False)
    warning_message = ojk_warning or fund_warning
    submit_disabled = fund_disabled or ojk_disabled

    total_net_finance_external = None
    purpose_requires_yearly_assessment = header["purpoffinc"] in ("3", "4")
    if purpose_requires_yearly_assessment:
        total_net_finance_external = _compute_simplified_net_finance(
            conn, appl_no, header["apless"]
        )

    approver_options = _get_approver_options(
        conn,
        appl_no=appl_no,
        access_level=access_level,
        username=username,
        branch_cd=branch_cd,
        approval_form_id=approval_form_id,
        appr_level=appr_level,
        tot_outs=tot_outs,
        l_amount=l_amount,
    )

    strength, weakness, tbo = _get_credit_recommendation(conn, appl_no)
    result_independent = _get_result_independent(conn, appl_no)

    completed = _row_exists(
        conn,
        "SELECT 1 FROM MCMOCAMStatus WITH (NOLOCK) WHERE APPL_NO=:appl_no AND APPR_STS='E'",
        {"appl_no": appl_no},
    )

    survey_disabled, result_disabled = _survey_field_state(
        access_level, result_independent, lock["locked_by"]
    )

    return {
        "applNo": appl_no,
        "applNoDisplay": ", ".join(appl_no_list) + revision_suffix,
        "isMultiple": is_multiple,
        "multipleApplNos": appl_no_list,
        "lesseeName": header["lessee_nm"],
        "cmoName": header["cmo_nm"],
        "accessLevel": access_level,
        "isCmo": access_level == "CMO",
        "allowRejectToWatchlist": access_level in WATCHLIST_CAPABLE_ROLES,
        "showCreditRecommendation": access_level == "CRH",
        "showSurveyIndependent": access_level in SURVEY_FIELD_ROLES,
        "surveyIndependentDisabled": survey_disabled,
        "resultIndependentDisabled": result_disabled,
        "strength": strength,
        "weakness": weakness,
        "tbo": tbo,
        "isiSurv": result_independent["survey_value"],
        "isiResult": result_independent["result_value"],
        "resultIndependentOptions": result_independent["options"],
        "redCodeChecked": equip["is_red_code"],
        "gpsVendor": equip["gps_vendor"],
        "gpsVendorOptions": _get_gps_vendor_options(conn),
        "approverOptions": approver_options,
        "warningMessage": warning_message,
        "submitDisabled": submit_disabled,
        "alreadySentToAdmin": sent_to_admin,
        "watchlist": watchlist,
        "history": _get_history(conn, appl_no),
        "lockedBy": lock["locked_by"],
        "rejectedMessage": lock["rejected_message"],
        "completed": completed,
        "purposeRequiresYearlyAssessment": purpose_requires_yearly_assessment,
        "totalNetFinanceExternal": total_net_finance_external,
        "totalOutstanding": tot_outs,
        "withdrawnBefore": withdrawn_before,
    }

def _row_exists(conn, sql, params):
    return conn.execute(text(sql), params).first() is not None

def _get_lock_status(conn, appl_no, username, access_level):
    locked_by, rejected_message = None, None
    if access_level not in ("CMO", "NCH", "ODH", "DR"):
        row = conn.execute(
            text(
                """
                SELECT TOP 1 APPR_STS, APPR_ID, APPR_ID_From
                FROM MCMOCAMStatus WITH (NOLOCK)
                WHERE APPL_NO=:appl_no ORDER BY No DESC
                """
            ),
            {"appl_no": appl_no},
        ).mappings().first()
        if row:
            if row["APPR_STS"] == "T" and row["APPR_ID"] == username:
                locked_by = row["APPR_ID_From"]
            elif row["APPR_STS"] == "R" and row["APPR_ID"] != username:
                rejected_message = f"this CAM has been rejected by {row['APPR_ID']}"

    row = conn.execute(
        text(
            "SELECT APPR_ID FROM MCMOCAMStatus WITH (NOLOCK) WHERE APPL_NO=:appl_no AND APPR_STS='P'"
        ),
        {"appl_no": appl_no},
    ).mappings().first()
    if row and row["APPR_ID"] and row["APPR_ID"].strip().lower() != username.strip().lower():
        locked_by = row["APPR_ID"]

    return {"locked_by": locked_by, "rejected_message": rejected_message}

def _get_multiple_info(conn, appl_no):
    row = conn.execute(
        text(
            "SELECT CORP_RET, L_AMOUNT FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO=:appl_no"
        ),
        {"appl_no": appl_no},
    ).mappings().first()
    l_amount = row["L_AMOUNT"] if row else None
    is_multiple = bool(row and row["CORP_RET"] == "M")

    if is_multiple:
        rows = conn.execute(
            text(
                """
                SELECT APPL_NO FROM TAMASTER WITH (NOLOCK)
                WHERE MSTR_CA IN (SELECT MSTR_CA FROM TAMASTER WITH (NOLOCK) WHERE APPL_NO=:appl_no)
                """
            ),
            {"appl_no": appl_no},
        ).mappings().all()
        appl_no_list = [r["APPL_NO"] for r in rows] or [appl_no]
    else:
        appl_no_list = [appl_no]

    return is_multiple, l_amount, appl_no_list

def _get_header_info(conn, appl_no):
    row = conn.execute(
        text(
            """
            SELECT LTRIM(RTRIM(a.CMO)) AS CMO, b.LESSEE_NM, c.USERNAME, b.lessee_cat,
                   a.APLESS, a.PURPOFFINC, a.Cons_Leas AS fin_type
            FROM CAFCONT a WITH (NOLOCK)
                LEFT JOIN CAFLESS b WITH (NOLOCK) ON a.APLESS = b.APLESS
                LEFT JOIN APP_USRMST c WITH (NOLOCK) ON a.CMO = c.EMPLOYEE_ID
            WHERE a.APPL_NO=:appl_no
            """
        ),
        {"appl_no": appl_no},
    ).mappings().first() or {}

    return {
        "cmo_id": row.get("CMO"),
        "lessee_nm": row.get("LESSEE_NM"),
        "cmo_nm": row.get("USERNAME"),
        "lessee_cat": row.get("lessee_cat"),
        "apless": row.get("APLESS"),
        "purpoffinc": row.get("PURPOFFINC"),
        "fin_type": row.get("fin_type"),
    }

def _get_revision_suffix(conn, new_appl_no_csv):
    row = conn.execute(
        text("SELECT REVISI FROM MCMOREVISI WITH (NOLOCK) WHERE NEWAPPL_NO=:v"),
        {"v": new_appl_no_csv},
    ).mappings().first()
    return f"R{row['REVISI']}" if row else ""

def _get_total_outstanding(conn, appl_no):
    row = conn.execute(
        text(
            """
            SELECT SUM(OUTS) AS tot_outs FROM CAFCUST_OUTS WITH (NOLOCK)
            WHERE APPL_NO=:appl_no
              AND ASOF=(SELECT MAX(ASOF) FROM CAFCUST_OUTS WITH (NOLOCK) WHERE APPL_NO=:appl_no)
            """
        ),
        {"appl_no": appl_no},
    ).mappings().first()
    return (row["tot_outs"] if row else None) or 0

def _get_sent_to_admin(conn, appl_no):
    row = conn.execute(
        text(
            "SELECT APPR_ID, APPR_DATE FROM MCMOCAMStatus WITH (NOLOCK) WHERE APPL_NO=:appl_no AND APPR_STS='F'"
        ),
        {"appl_no": appl_no},
    ).mappings().first()
    if row and row["APPR_ID"]:
        return {"sentAt": row["APPR_DATE"].strftime("%d-%m-%Y %H:%M:%S")}
    return None

def _get_lessee_info(conn, apless):
    row = conn.execute(
        text(
            """
            SELECT LESSEE_NM, ADDRESS1, ADDRESS2, ID_CARD, LESSEE_TP, NPWP
            FROM CAFLESS WITH (NOLOCK) WHERE APLESS=:apless
            """
        ),
        {"apless": apless},
    ).mappings().first() or {}
    return {
        "lessee_nm": row.get("LESSEE_NM"),
        "address1": row.get("ADDRESS1"),
        "address2": row.get("ADDRESS2"),
        "id_card": row.get("ID_CARD"),
        "lessee_tp": row.get("LESSEE_TP"),
        "npwp": row.get("NPWP"),
    }

def _get_watchlist(conn, lessee):
    less_tp = lessee["lessee_tp"]
    base_sql = """
        SELECT TOP 1 a.NAME, b.DESC_VALUE,
               ISNULL(a.LastUser, a.CreateUser) AS createby,
               ISNULL(a.LastUpdate, a.CreateDate) AS createdt,
               CASE WHEN (a.LastUser<>'' OR a.LastUser IS NOT NULL) THEN 'U' ELSE 'C' END AS cekjenis
        FROM MCMOWATCHLIST a
        INNER JOIN mstcombo b ON a.Reason_Category=b.value AND b.cat_value='BLACKLIST_CATEGORY'
        WHERE {where} AND a.Flag_Type='W' AND a.FlagDel='0'
    """

    if less_tp == "PR":
        row = conn.execute(
            text(base_sql.format(where="a.ID_card LIKE :idlike")),
            {"idlike": f"%{lessee['id_card']}%"},
        ).mappings().first()
    else:
        row = conn.execute(
            text(base_sql.format(where="a.NPWP LIKE :npwplike")),
            {"npwplike": f"%{lessee['npwp']}%"},
        ).mappings().first()

    if not row:
        row = conn.execute(
            text(base_sql.format(where="a.Name LIKE :namelike AND a.Address LIKE :addrlike")),
            {"namelike": f"%{lessee['lessee_nm']}%", "addrlike": f"%{lessee['address1']}%"},
        ).mappings().first()

    if not row and less_tp == "PR":
        row = conn.execute(
            text(base_sql.format(where="a.Address LIKE :addrlike")),
            {"addrlike": f"%{lessee['address1']}%"},
        ).mappings().first()

    if not row:
        return {"listed": False}

    is_update = row["cekjenis"] == "U"
    return {
        "listed": True,
        "description": row["DESC_VALUE"],
        "byLabel": "Update By" if is_update else "Created By",
        "by": row["createby"],
        "dateLabel": "Last Update" if is_update else "Created Date",
        "date": row["createdt"].strftime("%d-%m-%Y"),
    }

def _get_equipment_info(conn, appl_no):
    row = conn.execute(
        text(
            """
            SELECT b.SUPP, a.CONDITION, c.IsRedCode, c.GPS_Vendor
            FROM CAFEQUIP a WITH (NOLOCK)
            LEFT JOIN CLFSUPP b WITH (NOLOCK) ON a.SUPP=b.SUPP
            LEFT JOIN CAFEQUIP_DETAIL c WITH (NOLOCK) ON a.CAFEQUIP_ID=c.CAFEQUIP_ID
            WHERE a.APPL_NO=:appl_no
            """
        ),
        {"appl_no": appl_no},
    ).mappings().first() or {}
    is_red_code = row.get("IsRedCode") == "1"
    return {
        "supp_code": row.get("SUPP"),
        "condition": row.get("CONDITION"),
        "is_red_code": is_red_code,
        "gps_vendor": row.get("GPS_Vendor") if is_red_code else "",
    }

def _fund_capital_warning(conn, fin_type, apless):
    total_fd = conn.execute(
        text(
            "SELECT SUM(outstanding) AS v FROM V_CustomerOutstanding WHERE Cons_Leas='D' AND APLESS=:apless"
        ),
        {"apless": apless},
    ).scalar() or 0
    total_fmu = conn.execute(
        text(
            "SELECT SUM(outstanding) AS v FROM V_CustomerOutstanding WHERE Cons_Leas='M' AND APLESS=:apless"
        ),
        {"apless": apless},
    ).scalar() or 0

    if fin_type == "D" and total_fd > FUND_FACILITY_LIMIT:
        return (
            "CAM cannot be processed because \"Grand Total Customer's Outstanding "
            "Contract & CAM Net Finance for Fund Facility (FF)\" > Rp. 500.000.000,-",
            True,
        )
    if fin_type == "M" and total_fmu > CAPITAL_FACILITY_LIMIT:
        return (
            "CAM cannot be processed because \"Grand Total Customer's Outstanding "
            "Contract & CAM Net Finance for Business Capital Facility (FMU)\" > Rp. 10.000.000.000,-",
            True,
        )
    return None, False

def _ojk_warning(conn, fin_type, apless):

    def _sum_outs(cons_leas_filter):
        sql = f"""
            SELECT SUM(OutsPrinc_ACC) AS v FROM TotalOutsPrinc a
            INNER JOIN CLFCONT b ON a.lease_no=b.LEASE_NO
            WHERE asof = CAST(GETDATE() AS date) {cons_leas_filter}
        """
        v = conn.execute(text(sql)).scalar()
        if v and v > 0:
            return v
        sql_fallback = f"""
            SELECT SUM(OutsPrinc_ACC) AS v FROM TotalOutsPrinc a
            INNER JOIN CLFCONT b ON a.lease_no=b.LEASE_NO
            WHERE asof = EOMONTH(DATEADD(M, -2, GETDATE())) {cons_leas_filter}
        """
        return conn.execute(text(sql_fallback)).scalar() or 0

    total_outs_company = conn.execute(
        text("SELECT SUM(OutsPrinc_ACC) AS v FROM TotalOutsPrinc WHERE asof = CAST(GETDATE() AS date)")
    ).scalar()
    if not total_outs_company or total_outs_company <= 0:
        total_outs_company = conn.execute(
            text(
                "SELECT SUM(OutsPrinc_ACC) AS v FROM TotalOutsPrinc "
                "WHERE asof = EOMONTH(DATEADD(M, -1, GETDATE()))"
            )
        ).scalar() or 0

    total_outs_type = _sum_outs(f"AND b.Cons_Leas='{fin_type}'") if fin_type in ("D", "M", "W") else 0

    undisbursed_company = _sum_undisbursed(conn, cons_leas_filter=None)
    undisbursed_type = _sum_undisbursed(conn, cons_leas_filter=fin_type)

    total_mitsui = undisbursed_company + total_outs_company
    total_mitsui_type = undisbursed_type + total_outs_type
    allowed_limit = total_mitsui * 0.25

    facility_label = {
        "D": "Fund Facility", "M": "Business Capital Facility", "W": "Showroom Financing"
    }.get(fin_type, fin_type)

    if total_mitsui_type > allowed_limit:
        return f"CAM cannot be proceed, because the {facility_label} limit OJK Regulation", True
    return None, False

def _sum_undisbursed(conn, cons_leas_filter):
    leas_clause_a = ""
    leas_clause_b = ""
    if cons_leas_filter == "D":
        leas_clause_a = "AND a.Cons_Leas='D'"
        leas_clause_b = "AND b.Cons_Leas='D'"
    elif cons_leas_filter == "M":
        leas_clause_a = "AND a.Cons_Leas IN ('M','W')"
        leas_clause_b = "AND b.Cons_Leas='M'"
    elif cons_leas_filter == "W":
        leas_clause_a = "AND a.Cons_Leas='W'"
        leas_clause_b = "AND b.Cons_Leas='W'"

    sql = f"""
        SELECT a.APPL_NO, a.LEASE_NO FROM CLFCONT a WITH (NOLOCK)
        LEFT JOIN CAFCONT b WITH (NOLOCK) ON a.APPL_NO=b.APPL_NO
        LEFT JOIN MCMORevisi g WITH (NOLOCK) ON a.APPL_NO = g.oldAppl_No
        LEFT JOIN TACrossNo h WITH (NOLOCK) ON a.LEASE_NO = h.CROSSNO
        WHERE a.UPD_STAT='Y' AND a.EXECUTION IS NULL AND a.FLGDEL='0' {leas_clause_a}
          AND a.APPL_NO <> ISNULL(g.oldAppl_No, 0) AND h.CROSSNO IS NULL
        UNION
        SELECT b.APPL_NO, '' FROM CAFCONT b WITH (NOLOCK)
        LEFT JOIN MCMORevisi g WITH (NOLOCK) ON b.APPL_NO = g.oldAppl_No
        WHERE b.DateTrans IS NULL {leas_clause_b} AND b.APPL_NO <> ISNULL(g.oldAppl_No, 0)
          AND b.APPL_NO IN (SELECT appl_no FROM MCMOCAMCOMPLETELIST WHERE Admsts='1')
    """
    rows = conn.execute(text(sql)).mappings().all()
    total = 0
    for r in rows:
        if r["LEASE_NO"]:
            v = conn.execute(
                text("SELECT Net_Finance FROM V_NetFinance WHERE LEASE_NO=:v"),
                {"v": r["LEASE_NO"]},
            ).scalar()
        else:
            v = conn.execute(
                text("SELECT Net_Finance FROM V_NetFinance WHERE APPL_NO=:v"),
                {"v": r["APPL_NO"]},
            ).scalar()
        total += v or 0
    return total

def _compute_simplified_net_finance(conn, appl_no, apless):
    row = conn.execute(
        text(
            """
            SELECT L_AMOUNT, SECURITY, AdmFee, PROVISION, OTHERLOAN
            FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO=:appl_no AND APLESS=:apless
            """
        ),
        {"appl_no": appl_no, "apless": apless},
    ).mappings().first()
    if not row:
        return 0

    credit_amt = conn.execute(
        text("SELECT CREDITAMT FROM CAFINSU WITH (NOLOCK) WHERE APPL_NO=:appl_no"),
        {"appl_no": appl_no},
    ).scalar() or 0

    bbn_loan = conn.execute(
        text("SELECT BBNloan FROM BBN WITH (NOLOCK) WHERE APPL_NO=:appl_no"),
        {"appl_no": appl_no},
    ).scalar() or 0

    prov_loan = conn.execute(
        text("SELECT Prov_loan FROM Provision_Loan WITH (NOLOCK) WHERE APPL_NO=:appl_no"),
        {"appl_no": appl_no},
    ).scalar() or 0

    net_finance = (row["L_AMOUNT"] or 0) - (row["SECURITY"] or 0) + credit_amt + (row["OTHERLOAN"] or 0) + prov_loan
    return net_finance + bbn_loan

def _get_approval_form_id(conn, access_level, appl_no, tot_outs):
    if access_level == "CMO":
        return 1
    row = conn.execute(
        text(
            """
            SELECT TOP 1 ApprovalFormId FROM mstCamApprovalFlow WITH (NOLOCK)
            WHERE :tot_outs BETWEEN OutstandingFrom AND OutstandingTo
            ORDER BY OutstandingTo DESC
            """
        ),
        {"tot_outs": tot_outs},
    ).scalar()
    if row is not None:
        return row
    return conn.execute(
        text("SELECT ApprovalFormId FROM documentApproval WHERE DocumentNumber=:appl_no"),
        {"appl_no": appl_no},
    ).scalar()

def _get_current_approval_level(conn, approval_form_id, access_level):
    return conn.execute(
        text(
            "SELECT ApprovalLevel FROM mstApprovalMatrix WITH (NOLOCK) "
            "WHERE ApprovalFormId=:form_id AND AccessLevel=:level"
        ),
        {"form_id": approval_form_id, "level": access_level},
    ).scalar()

def _get_appr_plafond(conn, tot_outs):
    return conn.execute(
        text(
            """
            SELECT TOP 1 OutstandingTo FROM mstCamApprovalFlow WITH (NOLOCK)
            WHERE :tot_outs BETWEEN OutstandingFrom AND OutstandingTo
            ORDER BY OutstandingTo DESC
            """
        ),
        {"tot_outs": tot_outs},
    ).scalar()

def _get_approver_options(conn, appl_no, access_level, username, branch_cd,
                           approval_form_id, appr_level, tot_outs, l_amount):
    appr_plafond = _get_appr_plafond(conn, tot_outs)

    if access_level == "CMO":
        next_approver = get_next_available_approver(
            conn, appr_level, approval_form_id, branch_cd, username, appr_plafond
        )
        return [_approver_option(next_approver)]

    max_level = conn.execute(
        text("SELECT MAX(ApprovalLevel) AS v FROM mstApprovalMatrix WITH (NOLOCK) WHERE ApprovalFormId=:f"),
        {"f": approval_form_id},
    ).scalar()

    is_top_bracket = appr_plafond is not None and float(appr_plafond) == 3000000001

    past_final_level = False
    if not is_top_bracket:
        past_final_level = appr_level is not None and max_level is not None and appr_level > max_level
    else:
        odh_level = conn.execute(
            text(
                "SELECT ApprovalLevel FROM mstApprovalMatrix WITH (NOLOCK) "
                "WHERE AccessLevel='ODH' AND ApprovalFormId=:f"
            ),
            {"f": approval_form_id},
        ).scalar()
        if odh_level is not None and appr_level is not None and appr_level >= odh_level:
            past_final_level = max_level is not None and appr_level > max_level

    if past_final_level:
        return [{"value": "Admin", "label": "Send to Admin"}]

    next_approver = get_next_available_approver(
        conn, appr_level, approval_form_id, branch_cd, username, appr_plafond
    )
    return [_approver_option(next_approver)]

def _approver_option(next_approver):
    if isinstance(next_approver, str) and next_approver.upper() == "ADMIN":
        return {"value": next_approver, "label": "Send to Admin"}
    name = next_approver.split("|")[0] if next_approver else ""
    return {"value": next_approver, "label": name}

def _get_credit_recommendation(conn, appl_no):
    row = conn.execute(
        text(
            """
            SELECT b.Strength, b.Weakness, b.Tbo
            FROM CAFCONT a WITH (NOLOCK)
            LEFT JOIN CAFCONT_DETAIL b WITH (NOLOCK) ON a.Appl_No=b.Appl_No
            WHERE a.APPL_NO=:appl_no
            """
        ),
        {"appl_no": appl_no},
    ).mappings().first() or {}
    to_text = lambda v: (v or "").replace("<br />", "\n")
    return to_text(row.get("Strength")), to_text(row.get("Weakness")), to_text(row.get("Tbo"))

def _get_result_independent(conn, appl_no):
    result_value = conn.execute(
        text("SELECT Result_Independent FROM mcmocamcompletelist WITH (NOLOCK) WHERE APPL_NO=:appl_no"),
        {"appl_no": appl_no},
    ).scalar()
    survey_value = "1" if result_value not in (None, "") else "0"

    options = []
    if result_value not in (None, ""):
        rows = conn.execute(
            text("SELECT VALUE, DESC_VALUE FROM mstcombo WITH (NOLOCK) WHERE CAT_VALUE='Result_Independent'")
        ).mappings().all()
        options = [{"value": r["VALUE"], "label": r["DESC_VALUE"]} for r in rows]

    return {"result_value": result_value or "", "survey_value": survey_value, "options": options}

def _get_gps_vendor_options(conn):
    rows = conn.execute(
        text("SELECT SUPP, NAME FROM VENDOR WITH (NOLOCK) WHERE Supp_Category='GPS' ORDER BY NAME")
    ).mappings().all()
    return [{"value": r["SUPP"], "label": r["NAME"]} for r in rows]

def _survey_field_state(access_level, result_independent, locked_by):
    if locked_by:
        return True, True
    has_result = result_independent["result_value"] != ""
    if access_level == "CRH":
        if result_independent["result_value"] == "1":
            return True, False
        return True, True
    if access_level in ("CH", "ODH", "DR", "PD", "CRUH", "OPDH"):
        return True, True
    if access_level == "CR":
        return False, (not has_result)
    return False, False

def _get_history(conn, appl_no):
    rows = conn.execute(
        text(
            """
            SELECT a.APPR_DATE, a.COMMENT, SUBSTRING(a.APPR_STS, 1, 1) AS APPR_STS,
                   b.FULLNAME,
                   CASE WHEN a.IsNotRecommend=1 THEN 'No'
                        WHEN a.IsNotRecommend=0 THEN 'Yes' ELSE '-' END AS Recommendation
            FROM MCMOCAMStatus a WITH (NOLOCK)
            INNER JOIN APP_USRMST b ON b.USERNAME=a.APPR_ID
            WHERE a.APPL_NO=:appl_no AND (a.APPR_STS IN ('N','A','F','R') OR a.APPR_STS LIKE '%R')
            ORDER BY a.APPR_DATE, a.[No]
            """
        ),
        {"appl_no": appl_no},
    ).mappings().all()

    status_labels = {
        "A": "Approved",
        "F": "Approved & Send to Admin",
        "R": "Reject",
        "N": "Send for Approval",
    }
    history = []
    for r in rows:
        if r["APPR_STS"] == "T":
            continue
        history.append({
            "date": r["APPR_DATE"].strftime("%d-%m-%Y %H:%M:%S"),
            "approvedBy": r["FULLNAME"],
            "statusLabel": status_labels.get(r["APPR_STS"], r["APPR_STS"]),
            "recommendation": r["Recommendation"],
            "comment": r["COMMENT"] or "",
            "lowRecommendation": r["Recommendation"] == "No",
        })
    return history

def submit_cam_decision(conn, appl_no, username, access_level, emp_id, branch_cd, payload):
    approval_sts = payload.get("approvalSts")
    comment = (payload.get("comment") or "").strip()

    lock = _get_lock_status(conn, appl_no, username, access_level)
    if lock["locked_by"] and access_level not in ("CMO", "NCH", "ODH", "DR"):
        return {
            "success": False,
            "message": f"This CAM has been taken over by {lock['locked_by']}",
        }

    if approval_sts in ("R", "RW"):
        if not comment:
            return {"success": False, "validationErrors": ["Comment must not be empty"]}
        return _process_reject(conn, appl_no, username, access_level, approval_sts, comment, payload)

    return _process_approve(conn, appl_no, username, access_level, emp_id, branch_cd, payload)

def _process_reject(conn, appl_no, username, access_level, approval_sts, comment, payload):
    is_multiple, l_amount, appl_no_list = _get_multiple_info(conn, appl_no)
    not_recommend = 1 if payload.get("notRecommend") else 0
    action_code = "reject-to-watchlist" if approval_sts == "RW" else "reject"
    status_code = "rejected-to-watchlist" if approval_sts == "RW" else "rejected"

    for one_appl_no in appl_no_list:
        remarks = f"{access_level} has rejected CAM No. {one_appl_no}"
        if approval_sts == "RW":
            remarks += " to watchlist"

        rows = conn.execute(
            text(
                "SELECT APPR_STS, [No] FROM MCMOCAMStatus WITH (NOLOCK) "
                "WHERE APPL_NO=:v AND APPR_STS<>'P' AND APPR_STS NOT LIKE '%R'"
            ),
            {"v": one_appl_no},
        ).mappings().all()
        for r in rows:
            if len(r["APPR_STS"]) == 2:
                new_sts = r["APPR_STS"][1] + "R"
            else:
                if r["APPR_STS"] == "T":
                    conn.execute(
                        text("DELETE FROM MCMOCAMStatus WHERE APPL_NO=:v AND [No]=:no AND APPR_STS='T'"),
                        {"v": one_appl_no, "no": r["No"]},
                    )
                new_sts = r["APPR_STS"] + "R"
            conn.execute(
                text("UPDATE MCMOCAMStatus SET APPR_STS=:sts WHERE APPL_NO=:v AND [No]=:no"),
                {"sts": new_sts, "v": one_appl_no, "no": r["No"]},
            )

        conn.execute(
            text(
                "UPDATE MCMOCAMStatus SET APPR_STS=:sts, COMMENT=:comment, APPR_DATE=GETDATE(), "
                "IsNotRecommend=:nr WHERE APPL_NO=:v AND APPR_STS='P'"
            ),
            {"sts": approval_sts, "comment": comment, "nr": not_recommend, "v": one_appl_no},
        )

        conn.execute(
            text(
                "UPDATE documentApproval SET Progress=0, CurrentApprover=NULL, "
                "DocumentStatusCode=:status_code, LastApprovalActionCode=:action_code, "
                "LastActionBy=:username, LastActionDate=GETDATE(), UpdatedBy=:username, "
                "UpdatedDate=GETDATE() WHERE DocumentNumber=:v"
            ),
            {"status_code": status_code, "action_code": action_code, "username": username, "v": one_appl_no},
        )
        conn.execute(
            text(
                """
                INSERT INTO documentApprovalHistory (DocumentApprovalId, ApprovalActionCode, Remarks, CreatedBy, CreatedDate)
                VALUES ((SELECT TOP 1 Id FROM documentApproval WHERE DocumentNumber=:v), :action_code, :remarks, :username, GETDATE())
                """
            ),
            {"action_code": action_code, "remarks": remarks, "username": username, "v": one_appl_no},
        )

        _notify_reject(conn, one_appl_no, username, comment)
        conn.execute(text("DELETE FROM TAMASTER WHERE appl_no=:v"), {"v": one_appl_no})

    if approval_sts == "RW":
        apless = _get_header_info(conn, appl_no_list[0])["apless"]
        _upsert_watchlist(conn, apless, comment, username)

    conn.commit()
    return {"success": True}

def _notify_reject(conn, appl_no, username, comment):
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT cc.CMO, d.TelegramID, cl.LESSEE_NM, f.TelegramID AS CMH_ID, e.FULLNAME
            FROM CAFCONT cc
            INNER JOIN CAFLESS cl ON cl.Apless = cc.Apless
            LEFT JOIN EMPLOYEE_DATA d ON cc.CMO = d.Employee_ID
            LEFT JOIN APP_USRMST e ON cc.CMO = e.Employee_ID
            LEFT JOIN EMPLOYEE_DATA f ON e.SUPERIOR = f.Employee_ID
            WHERE cc.APPL_NO=:v
            """
        ),
        {"v": appl_no},
    ).mappings().all()
    for r in rows:
        message = f"CAM No. {appl_no} - {r['LESSEE_NM']} has been rejected by {username}. Note: {comment}"
        message_cmh = (
            f"CAM No. {appl_no} - {r['LESSEE_NM']} (CMO : {r['FULLNAME']}) "
            f"has been rejected by {username}. Note: {comment}"
        )
        if r["TelegramID"]:
            send_telegram(r["TelegramID"], message)
        if r["CMH_ID"]:
            send_telegram(r["CMH_ID"], message_cmh)

def _upsert_watchlist(conn, apless, comment, username):
    lessee = _get_lessee_info(conn, apless)
    less_tp = lessee["lessee_tp"]

    existing = conn.execute(
        text("SELECT Reason, CreateDate, LastUpdate FROM MCMOWATCHLIST WHERE apless=:a AND FlagDel='0'"),
        {"a": apless},
    ).mappings().first()

    if existing:
        history_date = existing["LastUpdate"] or existing["CreateDate"]
        conn.execute(
            text(
                "INSERT INTO MCMOWATCHLIST_REASONHISTORY (APLESS, FirstCreateDate, ReasonDate, Reason) "
                "SELECT APLESS, CreateDate, :hist_date, Reason FROM MCMOWATCHLIST WITH (NOLOCK) WHERE APLESS=:a"
            ),
            {"hist_date": history_date, "a": apless},
        )
        conn.execute(
            text(
                "UPDATE MCMOWatchList SET LastUser=:u, LastUpdate=GETDATE(), Reason=:reason "
                "WHERE APLESS=:a AND FlagDel='0'"
            ),
            {"u": username, "reason": comment, "a": apless},
        )
    else:
        if less_tp == "PR":
            conn.execute(
                text(
                    """
                    INSERT INTO MCMOWatchList (No, Name, Address, ID_Card, Phone, ContactPerson,
                        ContactAddress, CreateUser, CreateDate, Reason, DOB, Flag_type, apless, FlagDel,
                        Mother, Reason_Category, Customer_Type, Spouse_Name, NPWP)
                    SELECT (SELECT ISNULL(MAX(No), 0) + 1 FROM MCMOWatchList),
                        LESSEE_NM, ADDRESS1, ID_CARD, PHONE2, Contact, '', :u, GETDATE(), :reason,
                        TGLBIRTH, 'W', :a, '0', Mother, '10', LESSEE_TP, Spouse, NPWP
                    FROM cafless WITH (NOLOCK) WHERE APLESS=:a
                    """
                ),
                {"u": username, "reason": comment, "a": apless},
            )
        else:
            conn.execute(
                text(
                    """
                    INSERT INTO MCMOWatchList (No, Name, Address, ID_Card, Phone, ContactPerson,
                        ContactAddress, CreateUser, CreateDate, Reason, DOB, Flag_type, apless, FlagDel,
                        Reason_Category, Customer_Type, Spouse_Name, NPWP)
                    SELECT (SELECT ISNULL(MAX(No), 0) + 1 FROM MCMOWatchList),
                        LESSEE_NM, ADDRESS2, ID_CARD, PHONE1, Contact, '', :u, SYSDATETIME(), :reason,
                        TGLBIRTH, 'W', :a, '0', '10', LESSEE_TP, Spouse, NPWP
                    FROM cafless WITH (NOLOCK) WHERE APLESS=:a
                    """
                ),
                {"u": username, "reason": comment, "a": apless},
            )
            conn.execute(
                text(
                    "INSERT INTO MCMOWATCHLIST_REASONHISTORY (APLESS, FirstCreateDate, ReasonDate, Reason) "
                    "VALUES (:a, SYSDATETIME(), SYSDATETIME(), :reason)"
                ),
                {"a": apless, "reason": comment},
            )

    if less_tp == "PR":
        alias_name = conn.execute(
            text("SELECT ALIAS_NAME FROM CAFLESS WITH (NOLOCK) WHERE APLESS=:a"), {"a": apless}
        ).scalar()
        if alias_name:
            already_has_alias = conn.execute(
                text(
                    "SELECT TOP 1 1 FROM MCMOWATCHLIST_ALIASNM WITH (NOLOCK) WHERE No=("
                    "SELECT No FROM MCMOWatchList WHERE apless=:a AND FlagDel='0')"
                ),
                {"a": apless},
            ).first()
            if not already_has_alias:
                conn.execute(
                    text(
                        "INSERT INTO MCMOWATCHLIST_ALIASNM (NO, ID, NAME) "
                        "SELECT No, (SELECT ISNULL(COUNT(ID), 0) + 1 FROM MCMOWATCHLIST_ALIASNM), :alias "
                        "FROM MCMOWatchList WHERE apless=:a AND FlagDel='0'"
                    ),
                    {"alias": alias_name, "a": apless},
                )

def _process_approve(conn, appl_no, username, access_level, emp_id, branch_cd, payload):
    is_multiple, l_amount, appl_no_list = _get_multiple_info(conn, appl_no)
    header = _get_header_info(conn, appl_no)
    lessee = _get_lessee_info(conn, header["apless"])

    hitung_irr(appl_no)

    errors = _validate_approve(conn, appl_no, header, lessee, payload)
    if errors:
        return {"success": False, "validationErrors": errors}

    _save_role_specific_fields(conn, appl_no_list, access_level, payload)

    if access_level in ("CMO", "CMH"):
        corp_ret = "C" if payload.get("indCor") == 2 else "R"
        extra = "" if access_level == "CMO" else " AND CORP_RET IS NULL"
        conn.execute(
            text(f"UPDATE CAFCONT SET CORP_RET=:v WHERE APPL_NO=:appl_no{extra}"),
            {"v": corp_ret, "appl_no": appl_no},
        )

    _upsert_total_outs(conn, appl_no, l_amount)

    send_to_admin = bool(payload.get("sendToAdmin"))
    appr_sts = "F" if send_to_admin else "A"
    next_appr = payload.get("nextApprover", "")
    next_appr_value = next_appr.split("|")[0] if next_appr else ""
    approver_access_level = next_appr.split("|")[1] if "|" in next_appr else ""

    tot_outs = _get_total_outstanding(conn, appl_no)
    appr_plafond = _get_appr_plafond(conn, tot_outs)
    approval_form_id = _get_approval_form_id(conn, access_level, appl_no, tot_outs)

    approval1 = next_appr_value
    if next_appr_value == "CRH":
        crh_row = conn.execute(
            text("EXEC USP_CAM_GETVALIDCRH :plafond"), {"plafond": appr_plafond}
        ).mappings().first()
        if crh_row:
            approval1 = crh_row["Username"]
        else:
            appr_level = _get_current_approval_level(conn, approval_form_id, access_level)
            fallback = get_next_available_approver(
                conn, appr_level, approval_form_id, branch_cd, username, appr_plafond
            )
            approval1 = "Admin" if str(fallback).upper() == "ADMIN" else fallback

    withdrawn_before = _row_exists(
        conn,
        "SELECT 1 FROM MCMOCAMStatus WITH (NOLOCK) WHERE APPL_NO=:v AND APPR_STS LIKE 'T'",
        {"v": appl_no},
    )
    not_recommend = 1 if payload.get("notRecommend") else 0

    if is_multiple:
        proc_sql = (
            "EXEC USP_CAM_SENTBYMULTIPLE :appl_no, :withdrawn, :approval1, :access_level, "
            ":username, :appr_sts, :comment, :cmo_id, :emp_id, :send_to_admin, :counter_sp, "
            ":form_id, :not_recommend"
        )
        params = {
            "appl_no": appl_no, "withdrawn": withdrawn_before, "approval1": approval1,
            "access_level": access_level, "username": username, "appr_sts": appr_sts,
            "comment": payload.get("comment", ""), "cmo_id": header["cmo_id"], "emp_id": emp_id,
            "send_to_admin": send_to_admin, "counter_sp": 0, "form_id": approval_form_id,
            "not_recommend": not_recommend,
        }
    else:
        proc_sql = (
            "EXEC USP_CAM_SENTBYAPPLNO :appl_no, :withdrawn, :approval1, :access_level, "
            ":username, :appr_sts, :comment, :cmo_id, :emp_id, :send_to_admin, :counter_sp, "
            ":form_id, :not_recommend, :approver_level"
        )
        params = {
            "appl_no": ",".join(appl_no_list), "withdrawn": withdrawn_before, "approval1": approval1,
            "access_level": access_level, "username": username, "appr_sts": appr_sts,
            "comment": payload.get("comment", ""), "cmo_id": header["cmo_id"], "emp_id": emp_id,
            "send_to_admin": send_to_admin, "counter_sp": 0, "form_id": approval_form_id,
            "not_recommend": not_recommend, "approver_level": approver_access_level,
        }

    result_row = conn.execute(text(proc_sql), params).mappings().first()
    status_process_app = result_row["status"] if result_row else None

    messages = []
    if access_level == "CMO" and lessee["lessee_tp"] == "PT" and appr_sts == "A" and status_process_app == "SUCCESS":
        messages.append(register_privy(appl_no) or "Approval has been sent successfully.")

    if approval1 == "Admin" and status_process_app == "SUCCESS":
        if lessee["lessee_tp"] == "PR" and check_finish_approval(appl_no):
            messages.append(register_privy(appl_no) or "Final approval completed successfully.")
        _notify_final_approval(conn, appl_no_list, is_multiple)

    conn.commit()

    if status_process_app == "FAILED":
        return {"success": False, "message": "Failed to submit CAM. Please contact your administrator."}

    return {"success": True, "message": " ".join(messages) if messages else None}

def _notify_final_approval(conn, appl_no_list, is_multiple):
    display_no = ",".join(appl_no_list)
    stmt = text(
        """
        SELECT DISTINCT cc.CMO, d.TelegramID, cl.LESSEE_NM, f.TelegramID AS CMH_ID, e.FULLNAME,
               g.MSTR_CA
        FROM CAFCONT cc
        INNER JOIN CAFLESS cl ON cl.Apless = cc.Apless
            LEFT JOIN EMPLOYEE_DATA d ON cc.CMO = d.Employee_ID
            LEFT JOIN APP_USRMST e ON cc.CMO = e.Employee_ID
            LEFT JOIN EMPLOYEE_DATA f ON e.SUPERIOR = f.Employee_ID
            LEFT JOIN TAMASTER g ON cc.APPL_NO = g.APPL_NO
        WHERE cc.APPL_NO IN :appl_no_list
        """
    ).bindparams(bindparam("appl_no_list", expanding=True))
    rows = conn.execute(stmt, {"appl_no_list": list(appl_no_list)}).mappings().all()
    for r in rows:
        label = r["MSTR_CA"] if is_multiple and r["MSTR_CA"] else display_no
        prefix = "CAM Master No." if is_multiple else "CAM No."
        message = f"Good news! {prefix} {label} - {r['LESSEE_NM']} has been finally approved"
        message_cmh = (
            f"Good news! {prefix} {label} - {r['LESSEE_NM']} (CMO : {r['FULLNAME']}) has been finally approved"
        )
        if r["TelegramID"]:
            send_telegram(r["TelegramID"], message)
        if r["CMH_ID"]:
            send_telegram(r["CMH_ID"], message_cmh)

def _upsert_total_outs(conn, appl_no, l_amount):
    exists = conn.execute(
        text("SELECT APPL_NO FROM CAFCONT_TOTOUTS WITH (NOLOCK) WHERE APPL_NO=:v"), {"v": appl_no}
    ).scalar()
    if exists:
        conn.execute(
            text("UPDATE CAFCONT_TOTOUTS SET OUTSTANDING=:amt WHERE APPL_NO=:v"),
            {"amt": l_amount, "v": appl_no},
        )
    else:
        conn.execute(
            text("INSERT INTO CAFCONT_TOTOUTS (APPL_NO, OUTSTANDING) VALUES (:v, :amt)"),
            {"v": appl_no, "amt": l_amount},
        )

def _save_role_specific_fields(conn, appl_no_list, access_level, payload):
    strength = payload.get("strength", "").replace("\r\n", "<br />").replace("\n", "<br />")
    weakness = payload.get("weakness", "").replace("\r\n", "<br />").replace("\n", "<br />")
    tbo = payload.get("tbo", "").replace("\r\n", "<br />").replace("\n", "<br />")
    isi_result = payload.get("isiResult", "")
    red_code = "1" if payload.get("redCode") else "0"
    gps_vendor = payload.get("gpsVendor", "") if payload.get("redCode") else ""

    for one_appl_no in appl_no_list:
        if access_level == "CRH":
            has_detail = conn.execute(
                text("SELECT 1 FROM CAFCONT_DETAIL WITH (NOLOCK) WHERE APPL_NO=:v"), {"v": one_appl_no}
            ).first()
            if has_detail:
                conn.execute(
                    text(
                        "UPDATE CAFCONT_DETAIL SET Strength=:s, Weakness=:w, Tbo=:t WHERE Appl_No=:v"
                    ),
                    {"s": strength, "w": weakness, "t": tbo, "v": one_appl_no},
                )
            else:
                conn.execute(
                    text(
                        "INSERT INTO CAFCONT_DETAIL (Appl_No, Strength, Weakness, Tbo) VALUES (:v, :s, :w, :t)"
                    ),
                    {"v": one_appl_no, "s": strength, "w": weakness, "t": tbo},
                )

        if access_level in ("CR", "CRH", "CRDH", "DR", "PD"):
            conn.execute(
                text(
                    "UPDATE mcmocamcompletelist SET Result_Independent=:r WHERE APPL_NO=:v"
                ),
                {"r": isi_result or None, "v": one_appl_no},
            )

        cafequip_id = conn.execute(
            text("SELECT Cafequip_ID FROM Cafequip_Detail WITH (NOLOCK) WHERE APPL_NO=:v"),
            {"v": one_appl_no},
        ).scalar()
        if not cafequip_id:
            conn.execute(
                text(
                    "INSERT INTO Cafequip_Detail (Cafequip_ID, APPL_NO, IsRedCode, GPS_Vendor) "
                    "SELECT cafequip_id, appl_no, :rc, :gv FROM CAFEQUIP WHERE APPL_NO=:v"
                ),
                {"rc": red_code, "gv": gps_vendor, "v": one_appl_no},
            )
        else:
            conn.execute(
                text("UPDATE CAFEQUIP_DETAIL SET IsRedCode=:rc, GPS_Vendor=:gv WHERE APPL_NO=:v"),
                {"rc": red_code, "gv": gps_vendor, "v": one_appl_no},
            )

def _validate_approve(conn, appl_no, header, lessee, payload):
    errors = []

    bpkb_an_tp = conn.execute(
        text("SELECT BPKB_AN_TP FROM CAFEQUIP WITH (NOLOCK) WHERE APPL_NO=:v"), {"v": appl_no}
    ).scalar()
    if not bpkb_an_tp:
        errors.append("BPKB Name Type is empty")

    errors.extend(_validate_contact_info(conn, appl_no, header["apless"]))

    cont_type = conn.execute(
        text("SELECT cont_type FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO=:v"), {"v": appl_no}
    ).scalar()
    if not cont_type or not str(cont_type).strip():
        errors.append("Contract Type is empty please check")

    if header["purpoffinc"] in ("3", "4") and lessee["lessee_tp"] == "PT":
        total_net_finance_external = _compute_simplified_net_finance(conn, appl_no, header["apless"])
        if total_net_finance_external >= INDIVIDUAL_ASSESSMENT_THRESHOLD:
            tot_asset, tot_asset2, tot_passiva, tot_passiva2, tot_profit = _get_balance_sheet_totals(
                conn, header["apless"], appl_no
            )
            if (tot_asset <= 1 or tot_passiva <= 1) and (tot_asset2 <= 1 or tot_passiva2 <= 1):
                errors.append("Neraca (Balance Sheet) and / Laporan Laba Rugi (Profit Loss) must not be 0 or empty")
            elif tot_profit <= 1:
                errors.append("Neraca (Balance Sheet) and / Laporan Laba Rugi (Profit Loss) must not be 0 or empty")

    rscl = conn.execute(
        text(
            "SELECT Notary_no, ISNULL(Gross,0) AS Gross, Cons_Leas FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO=:v"
        ),
        {"v": appl_no},
    ).mappings().first()
    if rscl and rscl["Cons_Leas"] != "F":
        if rscl["Notary_no"] and str(rscl["Notary_no"]).strip():
            if rscl["Gross"] <= 0:
                errors.append("Gross Amount must more than 0 please check")
        else:
            errors.append("please fill Notary in Equipment BPKB")

    has_outs = conn.execute(
        text("SELECT 1 FROM CAFCUST_OUTS WITH (NOLOCK) WHERE APPL_NO=:v"), {"v": appl_no}
    ).first()
    if not has_outs:
        errors.append("Calculate Total Outstanding first!")

    errors.extend(_validate_dp_regulation(conn, appl_no))
    errors.extend(_validate_disbursement_consistency(conn, appl_no))

    npwp = conn.execute(
        text(
            "SELECT NPWP FROM cafless a WITH (NOLOCK) INNER JOIN cafcont b WITH (NOLOCK) ON a.APLESS=b.APLESS "
            "WHERE b.APPL_NO=:v"
        ),
        {"v": appl_no},
    ).scalar()
    if header["fin_type"] == "S" and lessee["lessee_tp"] == "PT" and not npwp:
        errors.append("You must fill the NPWP first")

    if payload.get("redCode") and not payload.get("gpsVendor"):
        errors.append("Please select GPS Vendor")

    return errors

def _validate_contact_info(conn, appl_no, apless):
    errors = []
    spouse = conn.execute(
        text(
            """
            SELECT cc.MARITAL, cd.SPOUSE_MobilePhone, cd.SPOUSE_Email
            FROM CAFCONT c WITH (NOLOCK)
                INNER JOIN CAFLESS cc WITH (NOLOCK) ON cc.APLESS = c.APLESS
                LEFT JOIN CAFLESS_DETAIL cd WITH (NOLOCK) ON cd.APLESS = cc.APLESS
            WHERE c.APPL_NO=:v
            """
        ),
        {"v": appl_no},
    ).mappings().first() or {}
    if spouse.get("MARITAL") == "M":
        if not spouse.get("SPOUSE_MobilePhone"):
            errors.append("Spouse Mobile Phone No. must not be empty")
        if not spouse.get("SPOUSE_Email"):
            errors.append("Spouse Email must not be empty")

    email1 = conn.execute(
        text(
            "SELECT EMAIL1 FROM CAFLESS WITH (NOLOCK) WHERE APLESS=(SELECT APLESS FROM CAFCONT WHERE APPL_NO=:v)"
        ),
        {"v": appl_no},
    ).scalar()
    if not email1:
        errors.append("Email 1 must not be empty")

    signer_rows = conn.execute(
        text("SELECT Phone, Email FROM V_ContractSigner WHERE appl_no=:v"), {"v": appl_no}
    ).mappings().all()
    for signer in signer_rows:
        if not signer.get("Phone"):
            errors.append("Mobile Phone No. must not be empty")
        if not signer.get("Email"):
            errors.append("Email must not be empty")

    return errors

def _get_balance_sheet_totals(conn, apless, appl_no):
    create_date = conn.execute(
        text("SELECT CONVERT(varchar(6), CREATE_DATE, 112) AS v FROM CAFCONT WITH (NOLOCK) WHERE APLESS=:a AND APPL_NO=:v"),
        {"a": apless, "v": appl_no},
    ).scalar() or datetime.now().strftime("%Y%m")

    periods = conn.execute(
        text(
            """
            SELECT TOP 2 PERIOD FROM CAFFS WITH (NOLOCK)
            WHERE APLESS=:a AND PERIOD<=:d AND FS_CODE='B'
            GROUP BY PERIOD ORDER BY PERIOD DESC
            """
        ),
        {"a": apless, "d": create_date},
    ).scalars().all()
    period2 = periods[0] if len(periods) > 0 else None
    period1 = periods[1] if len(periods) > 1 else None

    def _sum_fs(period, code_lt, code_gte=None):
        clause = "FS_CODE < :hi" if code_gte is None else "FS_CODE >= :lo AND FS_CODE < :hi"
        params = {"a": apless, "p": period, "hi": code_lt}
        if code_gte is not None:
            params["lo"] = code_gte
        codes = conn.execute(
            text(f"SELECT FS_CODE FROM MSTFS WITH (NOLOCK) WHERE {clause} AND SUBSTRING(FS_CODE,4,2)<>'00'"),
            params,
        ).scalars().all()
        total = 0
        for code in codes:
            v = conn.execute(
                text(
                    "SELECT AMOUNT FROM CAFFS WITH (NOLOCK) WHERE FS_CODE='B' AND PERIOD=:p AND APLESS=:a AND ITEM_CODE=:c"
                ),
                {"p": period, "a": apless, "c": code},
            ).scalar()
            total += v or 0
        return total

    tot_asset = _sum_fs(period1, "120000") if period1 else 0
    tot_asset2 = _sum_fs(period2, "120000") if period2 else 0
    tot_passiva = _sum_fs(period1, "21000", "12000") if period1 else 0
    tot_passiva2 = _sum_fs(period2, "21000", "12000") if period2 else 0

    period3 = conn.execute(
        text(
            """
            SELECT TOP 1 PERIOD FROM CAFFS WITH (NOLOCK)
            WHERE APLESS=:a AND PERIOD<=:d AND FS_CODE='P'
            GROUP BY PERIOD ORDER BY PERIOD DESC
            """
        ),
        {"a": apless, "d": create_date},
    ).scalar()
    tot_profit = 0
    if period3:
        tot_profit = conn.execute(
            text(
                "SELECT AMOUNT FROM CAFFS WITH (NOLOCK) WHERE FS_CODE='P' AND PERIOD=:p AND APLESS=:a AND ITEM_CODE='210901'"
            ),
            {"p": period3, "a": apless},
        ).scalar() or 0

    return tot_asset, tot_asset2, tot_passiva, tot_passiva2, tot_profit

def _validate_dp_regulation(conn, appl_no):
    errors = []
    dev_row = conn.execute(
        text("SELECT down_payment, base_rate FROM deviation_dp WHERE appl_no=:v"), {"v": appl_no}
    ).mappings().first() or {}
    investasi = multiguna = None
    if dev_row.get("down_payment") == "1":
        row = conn.execute(text("EXEC USP_CHECK_DEVIASI_DP :v"), {"v": appl_no}).mappings().first()
        if row:
            investasi, multiguna = row.get("I"), row.get("M")
    if investasi in (None, "") or multiguna in (None, ""):
        row = conn.execute(text("EXEC USP_CHECK_DP :v"), {"v": appl_no}).mappings().first()
        if row:
            investasi, multiguna = row.get("I"), row.get("M")

    cont = conn.execute(
        text(
            "SELECT purpoffinc, cons_leas, ROUND((security/l_amount)*100,0) AS security_persen, BaseAdmFee "
            "FROM cafcont WHERE appl_no=:v"
        ),
        {"v": appl_no},
    ).mappings().first() or {}
    purpoffinc = cont.get("purpoffinc")
    fin_type = cont.get("cons_leas")
    security_persen = cont.get("security_persen") or 0
    base_surv = cont.get("BaseAdmFee") or 0

    if not dev_row.get("down_payment") and purpoffinc == "4" and security_persen < 10:
        errors.append("Min. DP which allowed is 10%")
    if purpoffinc == "3" and investasi is not None and security_persen < float(investasi):
        errors.append(f"Min. DP which allowed is {investasi}%")
    if purpoffinc == "5" and multiguna is not None and security_persen < float(multiguna):
        errors.append(f"Min. DP which allowed is {multiguna}%")
    if dev_row.get("base_rate") != "1" and fin_type != "W" and base_surv < 1_500_000:
        errors.append("Minimum Survey Fee is 1,500,000")

    return errors

def _validate_disbursement_consistency(conn, appl_no):
    errors = []

    ins_amt_row = conn.execute(
        text(
            """
            SELECT TOP 1 i.INS_AMT, c.L_AMOUNT FROM CAFINSU i, CAFINSUD d, CAFCONT c
            WHERE i.INS_POL = d.INS_POL AND c.APPL_NO = i.APPL_NO
              AND c.APPL_NO=:v AND d.YEAR_NO='1'
            """
        ),
        {"v": appl_no},
    ).mappings().first()
    if ins_amt_row and ins_amt_row["INS_AMT"] not in (None, 0) and ins_amt_row["L_AMOUNT"] != ins_amt_row["INS_AMT"]:
        errors.append("The Asset value is different with the insurance amount of the first year")

    splits = {}
    for split in ("Dealer", "Accessories", "Karoseri", "Others"):
        row = conn.execute(
            text(
                "SELECT L_AMOUNT, FIRST_INST, DP, Prov, surveyfeegross_cigna FROM CAFDISB WITH (NOLOCK) "
                "WHERE APPL_NO=:v AND split=:s"
            ),
            {"v": appl_no, "s": split},
        ).mappings().first() or {}
        net = (
            (row.get("L_AMOUNT") or 0) - (row.get("DP") or 0) - (row.get("FIRST_INST") or 0)
            - (row.get("Prov") or 0) - (row.get("surveyfeegross_cigna") or 0)
        )
        splits[split] = net

    bbn = conn.execute(
        text("SELECT bbnvia, paidby, BBNloan FROM BBN WITH (NOLOCK) WHERE appl_no=:v"), {"v": appl_no}
    ).mappings().first() or {}
    bbn_loan = bbn.get("BBNloan") or 0 if (bbn.get("bbnvia") == "Dealer" and bbn.get("paidby") == "Loan") else 0

    total_net_finance = sum(splits.values()) + bbn_loan

    amount_rek = conn.execute(
        text("SELECT SUM(AMOUNT) AS v FROM CAFDISBACC WITH (NOLOCK) WHERE APPL_NO=:v"), {"v": appl_no}
    ).scalar() or 0
    amount_rekt = conn.execute(
        text("SELECT SUM(AMOUNT) AS v FROM TACROSSNO WITH (NOLOCK) WHERE APPL_NO=:v AND CROSS_TYPE='CD'"),
        {"v": appl_no},
    ).scalar() or 0
    total_amount_rek_cross = amount_rek + amount_rekt

    if total_net_finance != total_amount_rek_cross:
        errors.append("Total bank amount isn't same with the disbursement to dealer amount")

    ins_loan = conn.execute(
        text("SELECT CREDITAMT FROM CAFINSU WITH (NOLOCK) WHERE APPL_NO=:v"), {"v": appl_no}
    ).scalar() or 0
    disb_row = conn.execute(
        text("SELECT GROSS_PREM, DISB_INSC FROM CAFDISB WITH (NOLOCK) WHERE APPL_NO=:v"), {"v": appl_no}
    ).mappings().first() or {}
    gross_prem = disb_row.get("GROSS_PREM") or 0
    disb_insc = disb_row.get("DISB_INSC") or 0
    if (ins_loan + disb_insc) > gross_prem:
        errors.append("Insurance loan + insurance disbursement cannot more than gross insurance premium")

    fin_row = conn.execute(
        text(
            """
            SELECT c.TENOR, c.CONS_LEAS, cl.LESSEE_NM, e.BPKB_AN, c.NPWP, e.BPKB_AN_TP, e.BPKB_AN_STS
            FROM CAFCONT c WITH (NOLOCK)
                INNER JOIN CAFLESS cl WITH (NOLOCK) ON c.APLESS=cl.APLESS
                INNER JOIN CAFEQUIP e WITH (NOLOCK) ON c.APPL_NO=e.APPL_NO
            WHERE c.APPL_NO=:v
            """
        ),
        {"v": appl_no},
    ).mappings().first()
    if fin_row:
        if fin_row["CONS_LEAS"] == "L":
            if (fin_row["TENOR"] or 0) < 36:
                errors.append("Contract is Finance Lease, minimum period are 3 years.")
            if fin_row["LESSEE_NM"] != fin_row["BPKB_AN"]:
                errors.append("Contract is Finance Lease, Name of BPKB must same with Name of Contract.")
            if not fin_row.get("NPWP"):
                errors.append("Contract is Finance Lease, Customer must has NPWP.")
        else:
            if fin_row["LESSEE_NM"] != fin_row["BPKB_AN"] and fin_row["BPKB_AN_TP"] == "PR":
                if not fin_row.get("BPKB_AN_STS"):
                    errors.append("Name of BPKB is different with Name of Contract, Please fill the family status.")

    return errors