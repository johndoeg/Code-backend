from flask import Blueprint, jsonify, request, current_app, session
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text

from app.utils.helpers.approver_helpers import (
    resolve_approval_context,
    get_next_available_approver,
    approver_option_from_raw,
)

cam_approval_bp = Blueprint('cam_approval', __name__, url_prefix='/CAM/Approval')

STATUS_LABELS = {
    'N': 'Send for Approval',
    'A': 'Approved',
    'R': 'Reject',
    'RW': 'Rejected to Watchlist',
    'T': 'Withdrawn',
    'P': 'In Progress',
}

SURVEY_INDEPENDENT_LEVELS = {'CR', 'CRH', 'CH', 'ODH', 'DR', 'PD', 'CRUH', 'CRDH', 'OPDH'}
CREDIT_RECOMMENDATION_LEVELS = {'CRH'}
REJECT_TO_WATCHLIST_LEVELS = {'BM', 'CRH', 'CH', 'ODH', 'DR', 'PD', 'CRUH', 'OPDH'}

@cam_approval_bp.route('/<appl_no>', methods=['GET'])
@login_required
def get_cam_approval(appl_no):
    access_level = session.get("accesslevel", "")
    username = session.get("username", "")
    branch_cd = session.get("branchcode", "")

    try:
        header = db.session.execute(
            text("""
                SELECT a.APLESS, LTRIM(RTRIM(a.CMO)) AS CMO, b.LESSEE_NM, c.USERNAME, b.lessee_cat
                FROM CAFCONT a WITH (NOLOCK)
                    LEFT JOIN CAFLESS b WITH (NOLOCK) ON a.APLESS = b.APLESS
                    LEFT JOIN APP_USRMST c WITH (NOLOCK) ON a.CMO = c.EMPLOYEE_ID
                WHERE a.APPL_NO = :appl_no
            """),
            {"appl_no": appl_no},
        ).mappings().first()

        if header is None:
            return jsonify({"error": "CAM not found"}), 404

        withdrawn_by = None
        rejected_message = None

        if access_level not in ("CMO", "NCH", "ODH", "DR"):
            status_row = db.session.execute(
                text("""
                    SELECT TOP 1 APPR_STS, APPR_ID, APPR_ID_From
                    FROM MCMOCAMStatus WITH (NOLOCK)
                    WHERE APPL_NO = :appl_no
                    ORDER BY No DESC
                """),
                {"appl_no": appl_no},
            ).mappings().first()

            if status_row:
                appr_sts = status_row["APPR_STS"]
                appr_id = status_row["APPR_ID"]
                appr_id_from = status_row["APPR_ID_From"]

                if appr_sts == 'T' and appr_id == username:
                    withdrawn_by = appr_id_from
                elif appr_sts == 'R' and appr_id != username:
                    rejected_message = f"this Cam has been rejected by {appr_id}"

        locked_by = None
        lock_row = db.session.execute(
            text("""
                SELECT APPR_ID FROM MCMOCAMStatus WITH (NOLOCK)
                WHERE APPL_NO = :appl_no AND APPR_STS = 'P'
            """),
            {"appl_no": appl_no},
        ).mappings().first()
        if lock_row:
            held_by = (lock_row["APPR_ID"] or "").strip().upper()
            if held_by and held_by != username.strip().upper():
                locked_by = lock_row["APPR_ID"]

        history_rows = db.session.execute(
            text("""
                SELECT No, APPR_STS, APPR_ID, COMMENT, APPR_DATE, IsNotRecommend
                FROM MCMOCAMStatus WITH (NOLOCK)
                WHERE APPL_NO = :appl_no
                ORDER BY No ASC
            """),
            {"appl_no": appl_no},
        ).mappings().all()

        def _is_not_recommend(value):
            return str(value).strip().upper() in ("1", "Y", "YES", "TRUE") if value else False

        def _status_label(value):
            key = (value or "").strip().upper()
            return STATUS_LABELS.get(key, value or "-")

        history = [
            {
                "date": r["APPR_DATE"].strftime("%d-%m-%Y %H:%M") if r["APPR_DATE"] else "-",
                "approvedBy": r["APPR_ID"] or "-",
                "statusLabel": _status_label(r["APPR_STS"]),
                "recommendation": "Not Recommended" if _is_not_recommend(r["IsNotRecommend"]) else "Recommended",
                "comment": r["COMMENT"] or "-",
                "lowRecommendation": _is_not_recommend(r["IsNotRecommend"]),
            }
            for r in history_rows
        ]

        result_independent_options = [
            {"value": r["VALUE"], "label": r["DESC_VALUE"]}
            for r in db.session.execute(
                text("SELECT [VALUE], DESC_VALUE FROM mstcombo WITH (NOLOCK) WHERE CAT_VALUE = 'Result_Independent'")
            ).mappings().all()
        ]

        is_cmo = access_level == "CMO"

        approval_form_id, appr_plafond, appr_level_skrg, _effective_access_level = (
            resolve_approval_context(appl_no, access_level, username)
        )
        next_approver_raw = get_next_available_approver(
            branch_cd, username,
            current_approval_level=appr_level_skrg,
            approval_form_id=approval_form_id,
            appr_plafond=appr_plafond,
        )
        approver_options = [approver_option_from_raw(next_approver_raw)]

        watchlist = {"listed": False}

        gps_vendors = [
            {"value": r["SUPP"], "label": r["NAME"]}
            for r in db.session.execute(text("""
                SELECT SUPP, NAME FROM VENDOR WITH (NOLOCK) WHERE Supp_Category = 'GPS' ORDER BY NAME
            """)).mappings().all()
        ]

        equip_row = db.session.execute(text("""
            SELECT c.IsRedCode, c.GPS_Vendor
            FROM CAFEQUIP a WITH (NOLOCK)
                LEFT JOIN CAFEQUIP_DETAIL c WITH (NOLOCK) ON a.CAFEQUIP_ID = c.CAFEQUIP_ID
            WHERE a.APPL_NO = :appl_no
        """), {"appl_no": appl_no}).mappings().first()
        red_code_checked = bool(equip_row and str(equip_row.get("IsRedCode") or "") == "1")
        gps_vendor_value = (equip_row.get("GPS_Vendor") or "") if red_code_checked and equip_row else ""

        show_credit_recommendation = access_level in CREDIT_RECOMMENDATION_LEVELS
        allow_reject_to_watchlist = access_level in REJECT_TO_WATCHLIST_LEVELS
        show_survey_independent = access_level in SURVEY_INDEPENDENT_LEVELS

        payload = {
            "applNo": appl_no,
            "applNoDisplay": appl_no,
            "isMultiple": False,
            "multipleApplNos": [],
            "lesseeName": header["LESSEE_NM"] or "-",
            "cmoName": header["USERNAME"] or None,
            "accessLevel": access_level,
            "isCmo": is_cmo,
            "allowRejectToWatchlist": allow_reject_to_watchlist,
            "showCreditRecommendation": show_credit_recommendation,
            "showSurveyIndependent": show_survey_independent,
            "surveyIndependentDisabled": bool(locked_by),
            "resultIndependentDisabled": bool(locked_by),
            "strength": "",
            "weakness": "",
            "tbo": "",
            "isiSurv": "",
            "isiResult": "",
            "resultIndependentOptions": result_independent_options,
            "redCodeChecked": red_code_checked,
            "gpsVendor": gps_vendor_value,
            "gpsVendorOptions": gps_vendors,
            "approverOptions": approver_options,
            "warningMessage": None,
            "submitDisabled": bool(locked_by),
            "alreadySentToAdmin": None,
            "watchlist": watchlist,
            "history": history,
            "lockedBy": locked_by,
            "rejectedMessage": rejected_message,
            "withdrawnBy": withdrawn_by,
            "completed": False,
            "purposeRequiresYearlyAssessment": False,
            "totalNetFinanceExternal": None,
            "totalOutstanding": 0,
        }
        return jsonify(payload)

    except Exception:
        current_app.logger.exception("get_cam_approval error (appl_no=%s)", appl_no)
        return jsonify({"error": "Failed to load CAM approval data"}), 500

@cam_approval_bp.route('/<appl_no>/decision', methods=['POST'])
@login_required
def submit_cam_decision(appl_no):
    body = request.get_json(force=True) or {}
    approval_sts = body.get("approvalSts")
    comment = body.get("comment", "")
    next_approver = body.get("nextApprover", "")
    not_recommend = body.get("notRecommend", False)
    send_to_admin = bool(body.get("sendToAdmin", False))
    username = session.get("username", "")
    access_level = session.get("accesslevel", "")
    emp_id = session.get("emp_id", "")

    if approval_sts not in ("A", "R", "RW"):
        return jsonify({"success": False, "message": "Invalid approval status."}), 400

    try:
        current_row = db.session.execute(
            text("""
                SELECT TOP 1 APPR_STS, APPR_ID, APPR_ID_From
                FROM MCMOCAMStatus WITH (NOLOCK)
                WHERE APPL_NO = :appl_no
                ORDER BY No DESC
            """),
            {"appl_no": appl_no},
        ).mappings().first()

        if current_row:
            if current_row["APPR_STS"] == "P" and current_row["APPR_ID"] != username:
                return jsonify({
                    "success": False,
                    "message": f"This CAM has been taken over by {current_row['APPR_ID']}.",
                }), 409
            if current_row["APPR_STS"] == "T" and current_row["APPR_ID"] == username:
                return jsonify({
                    "success": False,
                    "message": f"Your CAM has been withdrawn/rejected by {current_row['APPR_ID_From']}.",
                }), 409

        if approval_sts in ("R", "RW"):
            result = db.session.execute(
                text("""
                    UPDATE MCMOCAMStatus
                    SET APPR_STS = :sts, COMMENT = :comment, APPR_DATE = GETDATE(), IsNotRecommend = :is_not_recommend
                    WHERE APPL_NO = :appl_no AND APPR_STS = 'P' AND APPR_ID = :appr_id
                """),
                {
                    "sts": approval_sts,
                    "comment": comment,
                    "is_not_recommend": "1" if not_recommend else "0",
                    "appl_no": appl_no,
                    "appr_id": username,
                },
            )
            if result.rowcount == 0:
                db.session.rollback()
                return jsonify({
                    "success": False,
                    "message": "No in-progress approval row found for this user on this CAM.",
                }), 409

        else:
            approver_parts = (next_approver or "").split("|", 1)
            approval1 = approver_parts[0] or "Admin"
            approver_access_level = approver_parts[1] if len(approver_parts) > 1 else ""

            header_row = db.session.execute(
                text("SELECT LTRIM(RTRIM(CMO)) AS CMO FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :appl_no"),
                {"appl_no": appl_no},
            ).mappings().first()
            cmo_id = (header_row["CMO"] if header_row else "") or ""

            withdrawn_before = db.session.execute(
                text("SELECT 1 FROM MCMOCAMStatus WITH (NOLOCK) WHERE APPL_NO = :appl_no AND APPR_STS LIKE 'T'"),
                {"appl_no": appl_no},
            ).first()
            withdrawn_flag = "1" if withdrawn_before else ""

            approval_form_id, _appr_plafond, _appr_level_skrg, effective_access_level = (
                resolve_approval_context(appl_no, access_level, username)
            )

            appr_sts_for_sp = "F" if send_to_admin else "A"

            counter_sp = 0

            sp_result = db.session.execute(
                text("""
                    SET NOCOUNT ON;
                    EXEC USP_CAM_SENTBYAPPLNO
                        :appl_no, :withdrawn_flag, :approval1, :access_level, :username,
                        :appr_sts, :comment, :cmo_id, :emp_id, :send_to_admin,
                        :counter_sp, :approval_form_id, :not_recommend, :approver_access_level
                """),
                {
                    "appl_no": appl_no,
                    "withdrawn_flag": withdrawn_flag,
                    "approval1": approval1,
                    "access_level": effective_access_level,
                    "username": username,
                    "appr_sts": appr_sts_for_sp,
                    "comment": comment,
                    "cmo_id": cmo_id,
                    "emp_id": emp_id,
                    "send_to_admin": "1" if send_to_admin else "0",
                    "counter_sp": counter_sp,
                    "approval_form_id": approval_form_id,
                    "not_recommend": "1" if not_recommend else "0",
                    "approver_access_level": approver_access_level,
                },
            )
            sp_row = sp_result.mappings().first()
            sp_status = (sp_row or {}).get("status")

            if sp_status and sp_status != "SUCCESS":
                db.session.rollback()
                return jsonify({"success": False, "message": "Failed to submit CAM. Please contact your administrator."}), 500

        db.session.execute(
            text("UPDATE MCMOCAMCOMPLETELIST SET Picked_by = NULL WHERE APPL_NO = :appl_no"),
            {"appl_no": appl_no},
        )

        db.session.commit()
        return jsonify({"success": True, "message": "Decision recorded."})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("submit_cam_decision error (appl_no=%s)", appl_no)
        return jsonify({"success": False, "message": "Database error."}), 500