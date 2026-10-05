from __future__ import annotations

import math
import uuid
import boto3
import mimetypes
import re
import time

import mimetypes
import os
import datetime as pydt

from io import BytesIO
from botocore.exceptions import ClientError
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, session, send_file
from sqlalchemy import text, bindparam
from werkzeug.utils import secure_filename

from app import db
from app.auth.decorators import login_required
from app.utils.helpers.aws_helpers import _s3_client, _s3_bucket, build_key, upload_fileobj, delete_object, _aws_presign, _aws_presign_bucket

from datetime import datetime as dt, date
from typing import Optional

from app.utils.helpers import financial_formulas as ff, cam_outstanding as outstanding, cam_navigation as camnav
from app.utils.helpers import fin_financing_formulas as fff
from botocore.config import Config as BotoConfig
from flask import redirect
from models.customer_document import CustomerDocument

from app.services.customer_document_service import (
    delete_customer_document,
    get_document_view_url,
    get_lessee_category,
    list_customer_documents,
    upload_customer_document,
)

from app.services.cam_creation_service import (
    CamCreationError,
    create_new_cam,
    get_dp_ratio_info,
    get_finance_type_options,
    get_portfolio_limit_check,
    get_purpose_of_finance_options,
)

cam_edit_bp = Blueprint("cam_edit", __name__, url_prefix="/CAM/EditIndex")

FUND_FACILITY_LIMIT = 500_000_000
CAPITAL_FACILITY_LIMIT = 10_000_000_000

def _session_str(key: str) -> str:
    return session.get(key, "") or ""

_CAM_BLOCKED_MESSAGE = "The Application is on approval process or has finished. The Data cannot be changed"

def _check_cam_editable(appl_no: str):
    row = db.session.execute(text("""
        SELECT 1
        FROM mcmocamstatus WITH (NOLOCK)
        WHERE appl_no = :a AND (appr_sts = 'P' OR appr_sts = 'E')
        
        UNION
        
        SELECT 1
        FROM mcmocamoutsstatus a WITH (NOLOCK)
            INNER JOIN mcmocamstatus b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
        WHERE a.appl_no = :a AND (a.appr_sts = 'P' OR a.appr_STS = 'A')
                AND b.APPR_STS NOT IN ('R', 'NR', 'AR', 'TR', 'XR', 'X', 'T')
        
        UNION
        
        SELECT 1
        FROM MCMOCAMOUTSSTATUS WITH (NOLOCK)
        WHERE appl_no = :a AND (appr_sts = 'P' OR appr_STS = 'A')
                AND appl_no NOT IN (SELECT APPL_NO FROM mcmocamstatus WHERE appl_no = :a)
    """), {"a": appl_no}).mappings().first()

    if not row:
        return False, ""

    try:
        db.session.execute(text("""
            INSERT INTO MCMOUSERAUDIT (USERID, WAKTU, [EVENT], USER_IP, server_addr, sessionid)
            VALUES (:userid, :waktu, :event, :ip, :server_addr, :sessionid)
        """), {
            "userid": _session_str("username"),
            "waktu": datetime.now(),
            "event": f"{_CAM_BLOCKED_MESSAGE}({appl_no})",
            "ip": request.remote_addr or "",
            "server_addr": request.host or "",
            "sessionid": request.cookies.get(current_app.config.get("SESSION_COOKIE_NAME", "session"), ""),
        })
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to write MCMOUSERAUDIT entry for %s", appl_no)

    return True, _CAM_BLOCKED_MESSAGE

def _fetch_combo(cat_value: str):
    rows = db.session.execute(text(
        "SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE = :cat"
    ), {"cat": cat_value}).fetchall()
    return [{"value": r.VALUE, "label": r.DESC_VALUE} for r in rows]

def _fetch_purposes():
    rows = db.session.execute(text("""
        SELECT PURPOFFINC, [DESC] FROM MSTPURPOFFINC WITH(NOLOCK) WHERE Flag_Active = '1'
    """)).fetchall()
    return [{"value": str(r.PURPOFFINC), "label": r.DESC} for r in rows]

def _fetch_finance_types(purpoffinc: str):
    if purpoffinc in ("1", "2"):
        leas = ("C", "F")
    elif purpoffinc == "3":
        leas = ("F", "S", "I")
    elif purpoffinc == "4":
        leas = ("S", "M", "W")
    else:
        leas = ("F", "I", "D")
    return _query_finance_types(leas)

def _query_finance_types(leas):
    stmt = text("""
        SELECT Cons_Leas, name FROM MSTCFFL WITH(NOLOCK)
        WHERE Cons_Leas IN :leas AND Flag_Active = '1'
    """).bindparams(bindparam("leas", expanding=True))
    rows = db.session.execute(stmt, {"leas": list(leas)}).fetchall()
    return [{"value": r.Cons_Leas, "label": r.name} for r in rows]

def _fetch_all_contract_types():
    rows = db.session.execute(text("""
        SELECT Cont_type, name FROM MSTCONTTYPE WITH(NOLOCK) WHERE LEFT(Cont_type, 2) <> 'RF'
    """)).fetchall()
    return [{"value": (r.Cont_type or "").strip(), "label": r.name} for r in rows]

def _current_bo(appl_no: str):
    row = db.session.execute(text("""
        SELECT BO_ID, BO_TYPE FROM BENEFICIARY_LINK WITH(NOLOCK) WHERE APPL_NO = :appl_no
    """), {"appl_no": appl_no}).fetchone()
    if not row:
        return "1", "0", None
    boa = "2"
    bot = {"PR": "1", "PT": "2"}.get(row.BO_TYPE, "0")
    return boa, bot, row.BO_ID

def _fetch_lessee_name(apless: str, applno: str) -> str:
    row = None
    if apless:
        row = db.session.execute(text("""
            SELECT LESSEE_NM FROM CAFLESS WITH (NOLOCK) WHERE APLESS = :apless
        """), {"apless": apless}).fetchone()
    elif applno:
        row = db.session.execute(text("""
            SELECT b.LESSEE_NM
            FROM CAFCONT a WITH (NOLOCK)
                LEFT JOIN CAFLESS b WITH (NOLOCK) ON a.APLESS = b.APLESS
            WHERE a.APPL_NO = :applno
        """), {"applno": applno}).fetchone()

    return (row.LESSEE_NM if row else "") or ""

@cam_edit_bp.route("/get-data", methods=["GET"])
@login_required
def get_data():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    if not apless or not applno:
        return jsonify({"error": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"blocked": True, "message": block_message}), 409

    row = db.session.execute(text("""
        SELECT c.Cons_Leas, c.Cont_type, c.PURPOFFINC, c.HAS_GUARANTOR,
               e.CONDITION, cd.GO_PUBLIC, r.RESTRUCTURING_CHANGE
        FROM CAFCONT c WITH(NOLOCK)
            LEFT JOIN CAFEQUIP e WITH(NOLOCK) ON e.APPL_NO = c.APPL_NO
            LEFT JOIN CAFLESS_DETAIL cd WITH(NOLOCK) ON cd.APLESS = c.APLESS
            LEFT JOIN CAFCONT_RESTRUCTURING r WITH(NOLOCK) ON r.APPL_NO = c.APPL_NO
        WHERE c.APPL_NO = :applno AND c.APLESS = :apless
    """), {"applno": applno, "apless": apless}).fetchone()

    if not row:
        return jsonify({"error": "Not found"}), 404

    boa, bot, _bo_id = _current_bo(applno)
    purpoffinc = str(row.PURPOFFINC or "").strip()

    return jsonify({
        "apless": apless,
        "applno": applno,
        "finType": (row.Cons_Leas or "").strip(),
        "purpoffinc": purpoffinc,
        "contType": (row.Cont_type or "").strip(),
        "guarantor": "2" if row.HAS_GUARANTOR else "1",
        "newCar": {"NEW": "2", "USED": "1"}.get((row.CONDITION or "").strip().upper(), ""),
        "goPublic": "" if row.GO_PUBLIC is None else str(row.GO_PUBLIC),
        "restructuringChange": row.RESTRUCTURING_CHANGE or "",
        "boa": boa,
        "bot": bot,
        "lookups": {
            "purposes": _fetch_purposes(),
            "financeTypes": _fetch_finance_types(purpoffinc),
            "contractTypes": _fetch_all_contract_types(),
            "restructuringChanges": _fetch_combo("RESTRUCTURING_CHANGE"),
        },
    })

@cam_edit_bp.route("/header", methods=["GET"])
@login_required
def get_header():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    if not apless and not applno:
        return jsonify({"error": "apless or applno is required"}), 400

    return jsonify({"custName": _fetch_lessee_name(apless, applno)})

@cam_edit_bp.route("/finance-types", methods=["GET"])
@login_required
def finance_types():
    purpoffinc = request.args.get("purpoffinc", "")
    return jsonify(_fetch_finance_types(purpoffinc))

@cam_edit_bp.route("/contract-types", methods=["GET"])
@login_required
def contract_types():
    fin_type = request.args.get("finType", "")
    if fin_type in ("S", "M", "D", "W", "I", "F"):
        rows = db.session.execute(text("""
            SELECT Cont_type, name FROM MSTCONTTYPE WITH(NOLOCK) WHERE Cont_type = 'NEW'
        """)).fetchall()
        return jsonify([{"value": (r.Cont_type or "").strip(), "label": r.name, "selected": True} for r in rows])
    return jsonify(_fetch_all_contract_types())

@cam_edit_bp.route("/dp-confirmation", methods=["GET"])
@login_required
def dp_confirmation():
    applno = request.args.get("applno", "")
    if not applno:
        return jsonify({"error": "applno is required"}), 400

    ratio_row = db.session.execute(text("EXEC USP_CHECK_RATIO :applno"), {"applno": applno}).fetchone()
    dp_row = db.session.execute(text("EXEC USP_CHECK_DP :applno"), {"applno": applno}).fetchone()

    if not ratio_row or not dp_row:
        return jsonify({"error": "Unable to compute DP confirmation for this application"}), 404

    return jsonify({
        "asOfDate": ratio_row.tgl_acuan,
        "periodFrom": ratio_row.tgl_from,
        "periodTo": ratio_row.tgl_to,
        "npfRatio": dp_row.npf,
        "minDpInvestasi": dp_row.I,
        "minDpMultiguna": dp_row.M,
    })

@cam_edit_bp.route("/submit", methods=["POST"])
@login_required
def submit():
    payload = request.get_json(silent=True) or {}
    apless = payload.get("apless", "")
    applno = payload.get("applno", "")
    fin_type = payload.get("finType", "")
    purpoffinc = str(payload.get("purpoffinc", ""))
    ind_cor = payload.get("indCor", "")
    guarantor = payload.get("guarantor", "")
    new_car = payload.get("newCar", "")
    cont_type = payload.get("contType", "")
    r_change = payload.get("restructuringChange", "")
    go_public = payload.get("goPublic", "")
    boa = payload.get("boa", "")
    bot = payload.get("bot", "")

    if not apless or not applno:
        return jsonify({"success": False, "message": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"success": False, "message": block_message}), 409

    errors = {}
    if not guarantor:
        errors["guarantor"] = "Guarantor availability must not be empty"
    if not purpoffinc:
        errors["purpoffinc"] = "Purpose of Finance must not be empty"
    if not new_car:
        errors["newCar"] = "Vehicle condition must not be empty"
    if not cont_type:
        errors["contType"] = "Contract Type must not be empty"
    if not boa:
        errors["boa"] = "Beneficial Owner Availability must not be empty"
    if boa == "2" and not bot:
        errors["bot"] = "Beneficial Owner Type must not be empty"
    if cont_type in ("RS1", "RS0") and not r_change:
        errors["restructuringChange"] = "Changes from Restructuring can't be empty"
    if ind_cor == "2" and not go_public:
        errors["goPublic"] = "Go Public must not be empty"

    if errors:
        return jsonify({"success": False, "errors": errors}), 422

    try:
        current = db.session.execute(text("""
            SELECT Cons_Leas, PURPOFFINC, Cont_type, HAS_GUARANTOR
            FROM CAFCONT WITH(NOLOCK) WHERE APPL_NO = :applno AND APLESS = :apless
        """), {"applno": applno, "apless": apless}).fetchone()
        if not current:
            db.session.rollback()
            return jsonify({"success": False, "message": "Application not found"}), 404

        equip = db.session.execute(text(
            "SELECT CONDITION FROM CAFEQUIP WITH(NOLOCK) WHERE APPL_NO = :applno"
        ), {"applno": applno}).fetchone()
        current_new_car = "2" if (equip and (equip.CONDITION or "").upper() == "NEW") else "1"

        current_boa, current_bot, bo_id = _current_bo(applno)

        fin_type_changed = fin_type != (current.Cons_Leas or "")
        purpoffinc_changed = purpoffinc != str(current.PURPOFFINC or "")
        cont_type_changed = cont_type != (current.Cont_type or "").strip()
        guarantor_changed = guarantor != ("2" if current.HAS_GUARANTOR else "1")
        new_car_changed = new_car != current_new_car
        boa_changed = boa != current_boa
        bot_changed = bot != current_bot

        reset_finance = False

        def _clear_downstream_docs():
            db.session.execute(text("""
                UPDATE BBN SET BBNVia = NULL, PaidBy = NULL, ServiceAgencyNM = NULL,
                    NettServiceAgencyFee = NULL, BBN_FEE = NULL, BBNLoan = NULL, SERVICEAGENCYFEE = NULL
                WHERE APPL_NO = :applno
            """), {"applno": applno})
            db.session.execute(text("""
                UPDATE CAFKOMIS SET SALES_NO = NULL, FEE = NULL, PAY_DT = NULL, PAY_AMOUNT = NULL, SD_TYPE = NULL
                WHERE SD_TYPE = 'D' AND APPL_NO = :applno
            """), {"applno": applno})
            db.session.execute(text("""
                UPDATE CAFEQUIP SET BPKB_NO = NULL, BPKB_AN_TP = NULL, BPKB_AN = NULL, RELATION = NULL,
                    BPKB_ADDR = NULL, CITY_BPKB = NULL, Fdc_Area = NULL, INSURANCE_AREA = NULL, brand = NULL,
                    type = NULL, model = NULL, tahun = NULL, supp = NULL, userusage = NULL, purpose = NULL,
                    park_loc = NULL, city_park = NULL, karoseri = NULL, karoseri_supp = NULL, wheels = NULL,
                    accessories_supp=NULL, other_supp=NULL
                WHERE APPL_NO = :applno
            """), {"applno": applno})

        if fin_type_changed:
            _clear_downstream_docs()
            reset_finance = True

        if purpoffinc_changed:
            db.session.execute(text(
                "UPDATE CAFCONT SET PURPOFFINC = :p WHERE APPL_NO = :applno AND APLESS = :apless"
            ), {"p": purpoffinc, "applno": applno, "apless": apless})
            _clear_downstream_docs()
            reset_finance = True

        if fin_type != "L":
            db.session.execute(text(
                "UPDATE CAFCONT SET Cons_Leas = :ft WHERE APPL_NO = :applno AND APLESS = :apless"
            ), {"ft": fin_type, "applno": applno, "apless": apless})
        else:
            db.session.execute(text("""
                UPDATE CAFCONT SET Cons_Leas = :ft, Notary_no = NULL
                WHERE APPL_NO = :applno AND APLESS = :apless
            """), {"ft": fin_type, "applno": applno, "apless": apless})

        if ind_cor == "1":
            db.session.execute(text("DELETE FROM CAFSURV_PT WHERE APPL_NO = :applno"), {"applno": applno})
        elif ind_cor == "2":
            db.session.execute(text("DELETE FROM CAFSURV_PR WHERE APPL_NO = :applno"), {"applno": applno})

        exists_detail = db.session.execute(text(
            "SELECT 1 FROM CAFLESS_DETAIL WITH(NOLOCK) WHERE APLESS = :apless"
        ), {"apless": apless}).fetchone()
        if exists_detail:
            db.session.execute(text(
                "UPDATE CAFLESS_DETAIL SET GO_PUBLIC = :gp WHERE APLESS = :apless"
            ), {"gp": go_public, "apless": apless})
        else:
            db.session.execute(text(
                "INSERT INTO CAFLESS_DETAIL (APLESS, GO_PUBLIC) VALUES (:apless, :gp)"
            ), {"apless": apless, "gp": go_public})

        if guarantor_changed:
            has_guarantor = None
            if guarantor == "1":
                has_guarantor = 0
                db.session.execute(text("DELETE FROM CAFGUARN WHERE APPL_NO = :applno"), {"applno": applno})
                db.session.execute(text(
                    "DELETE FROM GUARANTOR_BANK_STATEMENT_DOCUMENT WHERE APPL_NO = :applno"
                ), {"applno": applno})
                db.session.execute(text(
                    "DELETE FROM CUSTOMER_DOCUMENT WHERE appl_no = :applno AND doc_type = 'guarn'"
                ), {"applno": applno})
            elif guarantor == "2":
                has_guarantor = 1
            db.session.execute(text(
                "UPDATE CAFCONT SET HAS_GUARANTOR = :hg WHERE APPL_NO = :applno AND APLESS = :apless"
            ), {"hg": has_guarantor, "applno": applno, "apless": apless})

        if new_car_changed:
            reset_finance = True
            if new_car == "1":
                condition, tahun = "USED", None
            else:
                condition, tahun = "NEW", str(datetime.utcnow().year)
            db.session.execute(text(
                "UPDATE CAFEQUIP SET CONDITION = :c, TAHUN = :t WHERE APPL_NO = :applno"
            ), {"c": condition, "t": tahun, "applno": applno})

        if cont_type_changed:
            db.session.execute(text("""
                UPDATE CAFCONT SET Cont_type = :ct, Disb_Type = 'N' WHERE APPL_NO = :applno AND APLESS = :apless
            """), {"ct": cont_type, "applno": applno, "apless": apless})
            db.session.execute(text("DELETE FROM TACrossNo WHERE APPL_NO = :applno"), {"applno": applno})
            db.session.execute(text("DELETE FROM CAFDISBACC WHERE APPL_NO = :applno"), {"applno": applno})

        if reset_finance:
            ins_pol = f"{applno}1"
            db.session.execute(text("DELETE FROM CAFINSUD WHERE INS_POL = :ip"), {"ip": ins_pol})
            db.session.execute(text("DELETE FROM CAFINSU WHERE APPL_NO = :applno"), {"applno": applno})
            db.session.execute(text("UPDATE CAFINSU SET INS_CD_AREA = NULL WHERE APPL_NO = :applno"), {"applno": applno})
            db.session.execute(text("DELETE FROM CAFDISB WHERE APPL_NO = :applno"), {"applno": applno})
            db.session.execute(text("DELETE FROM CAFDISBACC WHERE APPL_NO = :applno"), {"applno": applno})
            db.session.execute(text("DELETE FROM CAFKOMIS WHERE APPL_NO = :applno AND SD_TYPE = 'D'"), {"applno": applno})
            db.session.execute(text("DELETE FROM CAFKOMIS WHERE APPL_NO = :applno AND SD_TYPE = 'S'"), {"applno": applno})
            db.session.execute(text("DELETE FROM CAFCUST_OUTS WHERE APPL_NO = :applno"), {"applno": applno})
            db.session.execute(text("DELETE FROM CAFLR WHERE APPL_NO = :applno"), {"applno": applno})
            db.session.execute(text("DELETE FROM TACrossNo WHERE APPL_NO = :applno"), {"applno": applno})
            db.session.execute(text("""
                UPDATE CAFCONT SET L_AMOUNT = NULL, Notary_no = NULL, SECURITY = NULL, RESIDUAL = NULL, DECLRATE = NULL,
                    FLATRATE = NULL, OVERATE = NULL, ADV_ARR = NULL, L_TYPE = NULL, FIX_FLOAT = NULL, FLOAT_CYC = NULL,
                    DL_SLB = NULL, TENOR = NULL, PAY_CYCLE = NULL, RENTAL = NULL, MLCIDECL = NULL, MLCIFLAT = NULL,
                    MLCIRENT = NULL, MLCITAX = NULL, NOTARYFEE = NULL, OTHERFEE = NULL, G_TERM = NULL, G_PERIOD = NULL,
                    G_INT_RATE = NULL, G_INT_AMT = NULL, ContSts = NULL, OutStanding = NULL, Out_Amount = NULL,
                    COL_TYPE_Supp = NULL, Refund_Supp = NULL, REMARK = NULL, DateTrans = NULL, Nbr_Contract = NULL,
                    Disc_Cust = NULL, Disc_MLCI = NULL, AdmFee = NULL, Otherloan = NULL, DECLRATE1000 = NULL,
                    FLATRATE1000 = NULL, TENOR1000 = NULL, SUBSIDY = NULL, FLAGCOM = NULL, PROVISION = NULL,
                    COMM_PROVISION = NULL, Incentive = NULL
                WHERE APPL_NO = :applno
            """), {"applno": applno})

            l_type_row = db.session.execute(text(
                "SELECT L_TYPE FROM CAFCONT WITH(NOLOCK) WHERE APPL_NO = :applno AND APLESS = :apless"
            ), {"applno": applno, "apless": apless}).fetchone()
            if l_type_row and l_type_row.L_TYPE in ("3", "4"):
                db.session.execute(text("DELETE FROM CAFSTEP WHERE APPL_NO = :applno"), {"applno": applno})

            if fin_type != "I":
                db.session.execute(text("""
                    UPDATE CAFCONT SET RENTAL = NULL, MLCIRENT = NULL, Gross = NULL, Fiduciary = NULL, Notary = NULL,
                        Notary_No = NULL, RESIDUAL = SECURITY
                    WHERE APPL_NO = :applno AND APLESS = :apless
                """), {"applno": applno, "apless": apless})
            else:
                db.session.execute(text("""
                    UPDATE CAFCONT SET RENTAL = NULL, MLCIRENT = NULL, Gross = NULL, Fiduciary = NULL, Notary = NULL,
                        Notary_No = NULL, RESIDUAL = NULL
                    WHERE APPL_NO = :applno AND APLESS = :apless
                """), {"applno": applno, "apless": apless})

        if boa_changed or bot_changed:
            if bo_id:
                db.session.execute(text("DELETE FROM BENEFICIARY_LINK WHERE BO_ID = :bo_id"), {"bo_id": bo_id})
            db.session.execute(text("UPDATE Kuisioner_EDD SET EDD_BO = NULL WHERE APPL_NO = :applno"), {"applno": applno})

        if cont_type in ("RS1", "RS0"):
            exists_restructuring = db.session.execute(text(
                "SELECT 1 FROM CAFCONT_RESTRUCTURING WITH(NOLOCK) WHERE APPL_NO = :applno"
            ), {"applno": applno}).fetchone()
            if exists_restructuring:
                db.session.execute(text(
                    "UPDATE CAFCONT_RESTRUCTURING SET RESTRUCTURING_CHANGE = :rc WHERE APPL_NO = :applno"
                ), {"rc": r_change, "applno": applno})
            else:
                db.session.execute(text(
                    "INSERT INTO CAFCONT_RESTRUCTURING (APPL_NO, RESTRUCTURING_CHANGE) VALUES (:applno, :rc)"
                ), {"applno": applno, "rc": r_change})
        else:
            db.session.execute(text(
                "DELETE FROM CAFCONT_RESTRUCTURING WHERE APPL_NO = :applno"
            ), {"applno": applno})

        if fin_type == "S":
            db.session.execute(text("UPDATE CAFEQUIP SET SUPP = NULL WHERE APPL_NO = :applno"), {"applno": applno})

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("edit_index submit failed")
        return jsonify({"success": False, "message": "Failed to save. Please try again."}), 500

    return jsonify({
        "success": True,
        "financeTypeReset": fin_type_changed,
        "purposeReset": purpoffinc_changed,
    })

def _fetch_lessee_cat(apless: str) -> str:
    row = db.session.execute(text("""
        SELECT Lessee_Cat FROM CAFLESS WITH(NOLOCK) WHERE APLESS = :apless
    """), {"apless": apless}).fetchone()
    return (row.Lessee_Cat or "") if row else ""

def _fetch_positions():
    rows = db.session.execute(text("""
        SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE = 'HISTORY_POSITION'
    """)).fetchall()
    return [{"value": r.VALUE, "label": r.DESC_VALUE} for r in rows]

def _split_period(raw: str):
    raw = raw or ""
    if len(raw) < 6:
        return "", ""
    return raw[4:6], raw[0:4]

def _fetch_rows(apless: str):
    rows = db.session.execute(text("""
        SELECT ch.ID, ch.[FROM], ch.UNTIL, ch.Company, ch.Position, ch.Company_Address,
               ch.Phone, ch.Position_Other, ch.Employee_ID, ch.Area_Cd, ch.Postcode,
               ua.PROPINSI, ua.KABUPATEN, mc.DESC_VALUE AS Position_Label
        FROM CAFLESS_History ch WITH(NOLOCK)
            INNER JOIN UMFAREA ua WITH(NOLOCK) ON ua.AREA_CD = ch.Area_Cd
            INNER JOIN MSTCOMBO mc WITH(NOLOCK) ON mc.VALUE = ch.Position AND mc.CAT_VALUE = 'HISTORY_POSITION'
        WHERE ch.APLESS = :apless
        ORDER BY ch.ID
    """), {"apless": apless}).fetchall()

    out = []
    for r in rows:
        from_month, from_year = _split_period(r.FROM)
        until_month, until_year = _split_period(r.UNTIL)
        out.append({
            "id": r.ID,
            "fromMonth": from_month,
            "fromYear": from_year,
            "untilMonth": until_month,
            "untilYear": until_year,
            "company": r.Company or "",
            "companyAddress": r.Company_Address or "",
            "position": r.Position or "",
            "positionLabel": r.Position_Label or "",
            "positionOther": r.Position_Other or "",
            "employeeId": r.Employee_ID or "",
            "areaCd": r.Area_Cd or "",
            "province": r.PROPINSI or "",
            "city": r.KABUPATEN or "",
            "postcode": r.Postcode or "",
            "phone": r.Phone or "",
        })
    
    return out

@cam_edit_bp.route("/business-history", methods=["GET"])
@login_required
def get_business_history():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    if not apless or not applno:
        return jsonify({"error": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"blocked": True, "message": block_message}), 409

    return jsonify({
        "lesseeCat": _fetch_lessee_cat(apless),
        "positions": _fetch_positions(),
        "rows": _fetch_rows(apless),
    })

@cam_edit_bp.route("/business-history", methods=["POST"])
@login_required
def save_business_history():
    body = request.get_json(force=True) or {}
    apless = (body.get("apless") or "").strip()
    applno = (body.get("applno") or "").strip()
    if not apless:
        return jsonify({"success": False, "message": "apless is required"}), 400

    try:
        row_id = int(body.get("id") or 0)
    except (TypeError, ValueError):
        row_id = 0

    from_month = (body.get("fromMonth") or "").strip()
    from_year = (body.get("fromYear") or "").strip()
    until_month = (body.get("untilMonth") or "").strip()
    until_year = (body.get("untilYear") or "").strip()
    company = (body.get("company") or "").strip()
    company_address = (body.get("companyAddress") or "").strip()
    position = (body.get("position") or "").strip()
    position_other = (body.get("positionOther") or "").strip()
    employee_id = (body.get("employeeId") or "").strip()
    area_cd = (body.get("areaCd") or "").strip()
    postcode = (body.get("postcode") or "").strip()
    phone = (body.get("phone") or "").strip()

    errors = []
    if not from_month:
        errors.append("Month (From) must not be empty.")
    if not from_year:
        errors.append("Year (From) must not be empty.")
    if not until_month:
        errors.append("Month (Until) must not be empty.")
    if until_month != "00" and not until_year:
        errors.append("Year (Until) must not be empty.")
    if not company:
        errors.append("Company must not be empty.")
    if not position:
        errors.append("Position must not be empty.")
    if not position_other:
        errors.append("Position Other must not be empty.")
    if not area_cd:
        errors.append("Area must not be empty.")
    if not postcode:
        errors.append("Post Code must not be empty.")
    if until_month != "00" and from_year and until_year and from_year > until_year:
        errors.append("Year (From) must not exceed Year (Until).")

    if errors:
        return jsonify({"success": False, "message": " ".join(errors)})

    from_val = f"{from_year}{from_month}"
    until_val = f"{until_year}{until_month}"

    try:
        if row_id:
            db.session.execute(text("""
                UPDATE CAFLESS_History
                SET [FROM] = :from_val, UNTIL = :until_val, Company = :company, Position = :position,
                    Company_Address = :company_address, Phone = :phone, Position_Other = :position_other,
                    Employee_ID = :employee_id, Area_Cd = :area_cd, Postcode = :postcode
                WHERE APLESS = :apless AND ID = :row_id
            """), {
                "from_val": from_val, "until_val": until_val, "company": company, "position": position,
                "company_address": company_address, "phone": phone, "position_other": position_other,
                "employee_id": employee_id, "area_cd": area_cd, "postcode": postcode,
                "apless": apless, "row_id": row_id,
            })
        else:
            db.session.execute(text("""
                INSERT INTO CAFLESS_History
                    (APLESS, [FROM], UNTIL, Company, Position, Company_Address, Phone,
                     Position_Other, Employee_ID, Area_Cd, Postcode)
                VALUES
                    (:apless, :from_val, :until_val, :company, :position, :company_address, :phone,
                     :position_other, :employee_id, :area_cd, :postcode)
            """), {
                "apless": apless, "from_val": from_val, "until_val": until_val, "company": company,
                "position": position, "company_address": company_address, "phone": phone,
                "position_other": position_other, "employee_id": employee_id, "area_cd": area_cd,
                "postcode": postcode,
            })
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Failed to save business history — apless=%s applno=%s id=%s", apless, applno, row_id
        )
        return jsonify({"success": False, "message": "Save failed. Please try again."}), 500

    return jsonify({"success": True})

@cam_edit_bp.route("/business-history", methods=["DELETE"])
@login_required
def delete_business_history():
    apless = (request.args.get("apless") or "").strip()
    row_id = request.args.get("id", "")
    if not apless or not row_id:
        return jsonify({"success": False, "message": "apless and id are required"}), 400

    try:
        db.session.execute(text("""
            DELETE FROM CAFLESS_History WHERE APLESS = :apless AND ID = :row_id
        """), {"apless": apless, "row_id": row_id})
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Failed to delete business history — apless=%s id=%s", apless, row_id
        )
        return jsonify({"success": False, "message": "Delete failed. Please try again."}), 500

    return jsonify({"success": True})

SURVEY_TYPES = ("home-survey", "office-survey", "other-survey")

def _s3_key(applno: str, survey_type: str, filename: str) -> str:
    safe_name = secure_filename(filename) or "file"
    return f"cam-survey-files/{applno}/{survey_type}/{uuid.uuid4().hex}-{safe_name}"

def _generate_download_url(key: str, filename: str):
    try:
        return _s3_client().generate_presigned_url(
            "get_object",
            Params={
                "Bucket": _s3_bucket(),
                "Key": key,
                "ResponseContentDisposition": f'inline; filename="{filename}"',
            },
            ExpiresIn=300,
        )
    except ClientError:
        current_app.logger.exception("Failed to generate presigned URL for key=%s", key)
        return None

def _upload_to_s3(key: str, file_storage) -> bool:
    try:
        _s3_client().upload_fileobj(file_storage, _s3_bucket(), key)
        return True
    except ClientError:
        current_app.logger.exception("Failed to upload to S3 — key=%s", key)
        return False

def _delete_from_s3(key: str) -> None:
    try:
        _s3_client().delete_object(Bucket=_s3_bucket(), Key=key)
    except ClientError:
        current_app.logger.exception("Failed to delete S3 object — key=%s", key)

def _fetch_contract_summary(apless: str, applno: str):
    name_row = db.session.execute(text("""
        SELECT LESSEE_NM FROM CAFLESS WITH(NOLOCK) WHERE APLESS = :apless
    """), {"apless": apless}).fetchone()

    cont_row = db.session.execute(text("""
        SELECT ContSts FROM CAFCONT WITH(NOLOCK) WHERE APPL_NO = :applno
    """), {"applno": applno}).fetchone()

    if cont_row is None or cont_row.ContSts is None:
        status_label = " - "
    elif cont_row.ContSts == "N":
        status_label = "NEW"
    else:
        status_label = "REPEAT"

    vs_row = db.session.execute(text("""
        SELECT
            b.BRAND_NM, d.TYPE_NM, c.MODEL_NM,
            a.CHASIS, a.ENGINE, a.COLOUR, a.POLICENO,
            a.BPKB_AN, a.BPKB_ADDR, a.TAHUN, a.CONDITION, a.BPKB_AN_TP,
            e.NAME AS SUPPLIER_NAME,
            DATEDIFF(yy, a.BPKB_TGLBIRTH, f.CREATE_DATE)
                - CASE WHEN MONTH(a.BPKB_TGLBIRTH) > MONTH(f.CREATE_DATE) THEN 1 ELSE 0 END AS AGE_YEARS
        FROM CAFEQUIP a WITH(NOLOCK)
            LEFT JOIN CAFCONT f WITH(NOLOCK) ON a.APPL_NO = f.APPL_NO
            LEFT JOIN UMFBRAND b WITH(NOLOCK) ON a.brand = b.brand
            LEFT JOIN UMFMODEL c WITH(NOLOCK) ON a.model = c.model
            LEFT JOIN UMFType d WITH(NOLOCK) ON a.brand = d.brand AND a.Type = d.Type
            LEFT JOIN clfsupp e WITH(NOLOCK) ON a.SUPP = e.Supp
        WHERE a.appl_no = :applno
    """), {"applno": applno}).fetchone()

    bpkb_an = _or_dash(vs_row.BPKB_AN if vs_row else None)
    age_years = vs_row.AGE_YEARS if vs_row else None
    age_suffix = ""
    if vs_row and vs_row.BPKB_AN_TP == "PR" and age_years not in (None, ""):
        age_suffix = f" ({age_years} years old)"

    return {
        "status": status_label,
        "brand": _or_dash(vs_row.BRAND_NM if vs_row else None),
        "model": _or_dash(vs_row.MODEL_NM if vs_row else None),
        "modelType": _or_dash(vs_row.TYPE_NM if vs_row else None),
        "customerName": _or_dash(name_row.LESSEE_NM if name_row else None),
        "chassis": _or_dash(vs_row.CHASIS if vs_row else None),
        "engine": _or_dash(vs_row.ENGINE if vs_row else None),
        "bpkbName": f"{bpkb_an}{age_suffix}",
        "bpkbAddress": _or_dash(vs_row.BPKB_ADDR if vs_row else None),
        "year": _or_dash(vs_row.TAHUN if vs_row else None),
        "condition": _or_dash(vs_row.CONDITION if vs_row else None),
        "supplier": _or_dash(vs_row.SUPPLIER_NAME if vs_row else None),
        "color": _or_dash(vs_row.COLOUR if vs_row else None),
        "policeNo": _or_dash(vs_row.POLICENO if vs_row else None),
    }

def _copy_from_prior_application_if_repeat(apless: str, applno: str, status: str) -> None:
    if status != "RO":
        return

    emp_id = _session_str("emp_id")
    username = _session_str("username")
    if not emp_id:
        return

    prior = db.session.execute(text("""
        SELECT TOP 1 appl_no FROM CUSTOMER_DOCUMENT WITH(NOLOCK)
        WHERE APLESS = :apless AND LEFT(appl_no, 4) = :emp_id
        ORDER BY appl_no DESC
    """), {"apless": apless, "emp_id": emp_id}).fetchone()

    if not prior or not prior.appl_no:
        return

    already = db.session.execute(text("""
        SELECT COUNT(1) AS c FROM SURVEY_FILE WITH(NOLOCK) WHERE ApplNo = :applno
    """), {"applno": applno}).fetchone()
    if already and already.c > 0:
        return

    db.session.execute(text("""
        INSERT INTO SURVEY_FILE (ApplNo, Apless, SurveyType, DocumentType, DocumentName, AWSKey, CreatedBy, CreatedDate)
        SELECT :applno, :apless, SurveyType, DocumentType, DocumentName, AWSKey, :username, GETDATE()
        FROM SURVEY_FILE WITH(NOLOCK)
        WHERE ApplNo = :old_applno AND DocumentType IN ('home-survey', 'office-survey', 'other-survey')
    """), {"applno": applno, "apless": apless, "username": username, "old_applno": prior.appl_no})

    db.session.execute(text("""
        INSERT INTO SURVEY_NOTES (ApplNo, SurveyType, Notes, CreatedBy, CreatedDate)
        SELECT :applno, SurveyType, Notes, CreatedBy, CreatedDate
        FROM SURVEY_NOTES WITH(NOLOCK)
        WHERE ApplNo = :old_applno
    """), {"applno": applno, "old_applno": prior.appl_no})

    db.session.commit()

def _fetch_notes(applno: str, survey_type: str) -> str:
    row = db.session.execute(text("""
        SELECT TOP 1 NOTES FROM SURVEY_NOTES WITH(NOLOCK)
        WHERE ApplNo = :applno AND SurveyType = :survey_type
        ORDER BY CreatedDate DESC
    """), {"applno": applno, "survey_type": survey_type}).fetchone()
    return (row.NOTES or "") if row else ""

def _fetch_customer_survey_files(apless: str, applno: str, survey_type: str):
    rows = db.session.execute(text("""
        SELECT Id, DocumentName, AWSKey FROM SURVEY_FILE WITH(NOLOCK)
        WHERE Apless = :apless AND ApplNo = :applno AND DocumentType = :survey_type
        ORDER BY CreatedDate
    """), {"apless": apless, "applno": applno, "survey_type": survey_type}).fetchall()

    out = []
    for r in rows:
        if not r.DocumentName:
            continue
        out.append({
            "id": r.Id,
            "documentName": r.DocumentName,
            "downloadUrl": _generate_download_url(r.AWSKey, r.DocumentName) or "",
        })
    return out

@cam_edit_bp.route("/survey-file", methods=["GET"])
@login_required
def get_survey_file():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    status = request.args.get("status", "")
    
    if not apless or not applno:
        return jsonify({"error": "apless and applno are required"}), 400

    _copy_from_prior_application_if_repeat(apless, applno, status)

    return jsonify({
        "contract": _fetch_contract_summary(apless, applno),
        "home": {"notes": _fetch_notes(applno, "home-survey"), "files": _fetch_customer_survey_files(apless, applno, "home-survey")},
        "office": {"notes": _fetch_notes(applno, "office-survey"), "files": _fetch_customer_survey_files(apless, applno, "office-survey")},
        "other": {"notes": _fetch_notes(applno, "other-survey"), "files": _fetch_customer_survey_files(apless, applno, "other-survey")},
    })

def _fetch_customer_survey_files(apless: str, applno: str, survey_type: str):
    rows = db.session.execute(text("""
        SELECT Id, DocumentName, AWSKey FROM SURVEY_FILE WITH(NOLOCK)
        WHERE Apless = :apless AND ApplNo = :applno AND DocumentType = :survey_type
        ORDER BY CreatedDate
    """), {"apless": apless, "applno": applno, "survey_type": survey_type}).fetchall()
    
    out = []
    for r in rows:
        if not r.DocumentName:
            continue
        out.append({
            "id": r.Id,
            "documentName": r.DocumentName,
            "downloadUrl": _download_url(r.AWSKey, r.DocumentName) or "",
        })
    return out

@cam_edit_bp.route("/survey-file/upload", methods=["POST"])
@login_required
def upload_survey_file():
    apless = (request.form.get("apless") or "").strip()
    applno = (request.form.get("applno") or "").strip()
    survey_type = (request.form.get("surveyType") or "").strip()
    username = _session_str("username")

    if not apless or not applno:
        return jsonify({"success": False, "message": "apless and applno are required"}), 400
    if survey_type not in SURVEY_TYPES:
        return jsonify({"success": False, "message": "Invalid survey type."}), 400

    files = request.files.getlist("files")
    if not files:
        return jsonify({"success": False, "message": "No file selected."}), 400

    try:
        for f in files:
            if not f or not f.filename:
                continue
            key = _s3_key(applno, survey_type, f.filename)
            if not _upload_to_s3(key, f):
                return jsonify({"success": False, "message": f"Failed to upload {f.filename}."}), 500

            db.session.execute(text("""
                INSERT INTO SURVEY_FILE (ApplNo, Apless, SurveyType, DocumentType, DocumentName, AWSKey, CreatedBy, CreatedDate)
                VALUES (:applno, :apless, :survey_type, :survey_type, :document_name, :aws_key, :username, GETDATE())
            """), {
                "applno": applno, "apless": apless, "survey_type": survey_type,
                "document_name": f.filename, "aws_key": key, "username": username,
            })
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to save uploaded survey file(s) — apless=%s applno=%s", apless, applno)
        return jsonify({"success": False, "message": "Upload failed. Please try again."}), 500

    return jsonify({"success": True, "files": _fetch_customer_survey_files(apless, applno, survey_type)})

@cam_edit_bp.route("/survey-file", methods=["DELETE"])
@login_required
def delete_survey_file():
    apless = (request.args.get("apless") or "").strip()
    applno = (request.args.get("applno") or "").strip()
    doc_id = request.args.get("id", "")
    if not apless or not applno or not doc_id:
        return jsonify({"success": False, "message": "apless, applno and id are required"}), 400

    row = db.session.execute(text("""
        SELECT AWSKey FROM SURVEY_FILE WITH(NOLOCK) WHERE Id = :id AND Apless = :apless
    """), {"id": doc_id, "apless": apless}).fetchone()

    try:
        if row and row.AWSKey:
            _delete_from_s3(row.AWSKey)
        db.session.execute(text("""
            DELETE FROM SURVEY_FILE WHERE Id = :id AND Apless = :apless
        """), {"id": doc_id, "apless": apless})
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to delete survey file — id=%s apless=%s", doc_id, apless)
        return jsonify({"success": False, "message": "Delete failed. Please try again."}), 500

    return jsonify({"success": True})

@cam_edit_bp.route("/survey-file/download/<int:file_id>", methods=["GET"])
def download_survey_file(file_id):
    row = db.session.execute(db.text("""
        SELECT AWSKey, DocumentName FROM SURVEY_FILE WHERE ID = :id
    """), {"id": file_id}).fetchone()
    if not row:
        return jsonify({"message": "File not found"}), 404

    s3_key, document_name = row
    url = _aws_presign(s3_key, document_name)
    if not url:
        return jsonify({"message": "File not found in storage"}), 404

    return redirect(url)

@cam_edit_bp.route("/survey-file/next", methods=["POST"])
@login_required
def next_survey_file():
    body = request.get_json(force=True) or {}
    apless = (body.get("apless") or "").strip()
    applno = (body.get("applno") or "").strip()
    if not apless or not applno:
        return jsonify({"success": False, "message": "apless and applno are required"}), 400

    username = _session_str("username")
    notes_by_type = {
        "home-survey": (body.get("notesHome") or "").strip(),
        "office-survey": (body.get("notesOffice") or "").strip(),
        "other-survey": (body.get("notesOther") or "").strip(),
    }

    try:
        for survey_type, notes in notes_by_type.items():
            existing = db.session.execute(text("""
                SELECT COUNT(1) AS c FROM SURVEY_NOTES WITH(NOLOCK)
                WHERE ApplNo = :applno AND SurveyType = :survey_type
            """), {"applno": applno, "survey_type": survey_type}).fetchone()

            if existing and existing.c > 0:
                db.session.execute(text("""
                    UPDATE SURVEY_NOTES SET Notes = :notes, UpdatedBy = :username, UpdatedDate = GETDATE()
                    WHERE ApplNo = :applno AND SurveyType = :survey_type
                """), {"notes": notes, "username": username, "applno": applno, "survey_type": survey_type})
            else:
                db.session.execute(text("""
                    INSERT INTO SURVEY_NOTES (ApplNo, SurveyType, Notes, CreatedBy, CreatedDate)
                    VALUES (:applno, :survey_type, :notes, :username, GETDATE())
                """), {"applno": applno, "survey_type": survey_type, "notes": notes, "username": username})
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to save survey notes — apless=%s applno=%s", apless, applno)
        return jsonify({"success": False, "message": "Save failed. Please try again."}), 500

    has_files = db.session.execute(text("""
        SELECT COUNT(1) AS c FROM SURVEY_FILE WITH(NOLOCK)
        WHERE ApplNo = :applno AND SurveyType IN ('home-survey', 'office-survey', 'other-survey')
    """), {"applno": applno}).fetchone()

    if not has_files or has_files.c == 0:
        return jsonify({"success": False, "message": "Please upload Survey File."})

    return jsonify({"success": True})

ORG_TYPE_INDIVIDUAL = "PR"
S3_KEY_PREFIX = "cam-customer-documents"

INDIVIDUAL_DOCUMENT_TYPES = (
    "cust-spouse-kk",
    "cust-kitas",
    "cust-spouse-kitas",
    "cust-wna-spouse-ktp",
    "cust-family-tree",
    "cust-reference",
    "cust-salary-receipt",
    "cust-ktp-bpkb",
    "cust-kk-bpkb",
    "cust-other",
    "cust-ktp",
    "cust-spouse-ktp",
    "cust-kk",
    "cust-npwp",
    "cust-spk",
    "cust-marriage-or-death-statement",
)

def _fetch_citizen(apless: str) -> str:
    row = db.session.execute(text("""
        SELECT Citizen FROM CAFLESS WITH(NOLOCK) WHERE APLESS = :apless
    """), {"apless": apless}).fetchone()
    return (row.Citizen if row and row.Citizen else "") or "WNI"

def _fetch_spouse_citizen(apless: str) -> str:
    row = db.session.execute(text("""
        SELECT SPOUSE_CITIZEN FROM CAFLESS_Detail WITH(NOLOCK) WHERE APLESS = :apless
    """), {"apless": apless}).fetchone()
    return (row.SPOUSE_CITIZEN if row and row.SPOUSE_CITIZEN else "") or "WNI"

def _fetch_individual_documents(apless: str, applno: str) -> dict:
    rows = db.session.execute(text("""
        SELECT id_customer_document, AWSKey, file_document, DocumentType
        FROM CUSTOMER_DOCUMENT WITH(NOLOCK)
        WHERE doc_type = 'non' AND appl_no = :applno AND APLESS = :apless AND APLESS IS NOT NULL
        ORDER BY DocumentType, Upload_Dt DESC
    """), {"applno": applno, "apless": apless}).fetchall()

    out: dict = {}
    for r in rows:
        if not r.file_document or r.file_document == "-":
            continue
        out.setdefault(r.DocumentType, []).append({
            "id": r.id_customer_document,
            "documentName": r.file_document,
            "downloadUrl": _generate_download_url(r.AWSKey, r.file_document) or "",
        })
    return out

@cam_edit_bp.route("/document/individual", methods=["GET"])
@login_required
def get_individual_document():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    if not apless or not applno:
        return jsonify({"error": "apless and applno are required"}), 400

    return jsonify({
        "citizen": _fetch_citizen(apless),
        "spouseCitizen": _fetch_spouse_citizen(apless),
        "files": _fetch_individual_documents(apless, applno),
    })

@cam_edit_bp.route("/document/individual/upload", methods=["POST"])
@login_required
def upload_individual_document():
    apless = (request.form.get("apless") or "").strip()
    applno = (request.form.get("applno") or "").strip()
    document_type = (request.form.get("documentType") or "").strip()

    if not apless or not applno:
        return jsonify({"success": False, "message": "apless and applno are required"}), 400
    if document_type not in INDIVIDUAL_DOCUMENT_TYPES:
        return jsonify({"success": False, "message": "Invalid document type."}), 400

    files = request.files.getlist("files")
    if not files:
        return jsonify({"success": False, "message": "No file selected."}), 400

    try:
        for f in files:
            if not f or not f.filename:
                continue
            key = build_key(S3_KEY_PREFIX, applno, document_type, f.filename)
            if not upload_fileobj(key, f):
                db.session.rollback()
                return jsonify({"success": False, "message": f"Failed to upload {f.filename}."}), 500

            db.session.execute(text("""
                INSERT INTO CUSTOMER_DOCUMENT
                    (appl_no, APLESS, DocumentType, doc_type, organization_type, file_document, AWSKey, Upload_Dt)
                VALUES
                    (:applno, :apless, :document_type, 'non', :org_type, :file_document, :aws_key, GETDATE())
            """), {
                "applno": applno, "apless": apless, "document_type": document_type,
                "org_type": ORG_TYPE_INDIVIDUAL, "file_document": f.filename, "aws_key": key,
            })
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Failed to save uploaded customer document(s) — apless=%s applno=%s documentType=%s",
            apless, applno, document_type,
        )
        return jsonify({"success": False, "message": "Upload failed. Please try again."}), 500

    return jsonify({"success": True, "files": _fetch_individual_documents(apless, applno).get(document_type, [])})

@cam_edit_bp.route("/document/individual/next", methods=["POST"])
@login_required
def next_individual_document():
    body = request.get_json(force=True) or {}
    apless = (body.get("apless") or "").strip()
    applno = (body.get("applno") or "").strip()
    if not apless or not applno:
        return jsonify({"success": False, "message": "apless and applno are required"}), 400

    if not _fetch_individual_documents(apless, applno):
        return jsonify({"success": False, "message": "Please upload Customer's Document."})

    return jsonify({"success": True})

def _fetch_references(apless: str):
    rows = db.session.execute(text("""
        SELECT ID, REF_NAME, REF_PHONE, REMARK FROM CAFREF WITH(NOLOCK)
        WHERE APLESS = :apless ORDER BY INPUT_DT DESC
    """), {"apless": apless}).fetchall()
    return [{
        "id": r.ID,
        "refName": r.REF_NAME or "",
        "refPhone": r.REF_PHONE or "",
        "remark": r.REMARK or "",
    } for r in rows]

@cam_edit_bp.route("/references", methods=["GET"])
@login_required
def get_references():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    if not apless or not applno:
        return jsonify({"error": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"blocked": True, "message": block_message}), 409

    return jsonify({"rows": _fetch_references(apless)})

ORG_TYPE_INDIVIDUAL = "PR"
S3_KEY_PREFIX = "cam-customer-documents"

INDIVIDUAL_DOCUMENT_TYPES = (
    "cust-spouse-kk",
    "cust-kitas",
    "cust-spouse-kitas",
    "cust-wna-spouse-ktp",
    "cust-family-tree",
    "cust-reference",
    "cust-salary-receipt",
    "cust-ktp-bpkb",
    "cust-kk-bpkb",
    "cust-other",
    "cust-ktp",
    "cust-spouse-ktp",
    "cust-kk",
    "cust-npwp",
    "cust-spk",
    "cust-marriage-or-death-statement",
)

@cam_edit_bp.route("/document/individual", methods=["DELETE"])
@login_required
def delete_individual_document():
    apless = (request.args.get("apless") or "").strip()
    doc_id = request.args.get("id", "")
    if not apless or not doc_id:
        return jsonify({"success": False, "message": "apless and id are required"}), 400

    row = db.session.execute(text("""
        SELECT AWSKey FROM CUSTOMER_DOCUMENT WITH(NOLOCK)
        WHERE id_customer_document = :id AND APLESS = :apless
    """), {"id": doc_id, "apless": apless}).fetchone()

    try:
        if row and row.AWSKey:
            delete_object(row.AWSKey)
        db.session.execute(text("""
            DELETE FROM CUSTOMER_DOCUMENT WHERE id_customer_document = :id AND APLESS = :apless
        """), {"id": doc_id, "apless": apless})
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to delete customer document — id=%s apless=%s", doc_id, apless)
        return jsonify({"success": False, "message": "Delete failed. Please try again."}), 500

    return jsonify({"success": True})

@cam_edit_bp.route("/references", methods=["POST"])
@login_required
def save_reference():
    body = request.get_json(force=True) or {}
    apless = (body.get("apless") or "").strip()
    applno = (body.get("applno") or "").strip()
    if not apless or not applno:
        return jsonify({"success": False, "message": "apless and applno are required"}), 400

    try:
        row_id = int(body.get("id") or 0)
    except (TypeError, ValueError):
        row_id = 0

    ref_name = (body.get("refName") or "").strip()[:100]
    ref_phone = (body.get("refPhone") or "").strip()[:60]
    remark = (body.get("remark") or "").strip()[:250]

    errors = []
    if not ref_name:
        errors.append("Name must not be empty.")
    if not ref_phone:
        errors.append("Telephone Number must not be empty.")
    if not remark:
        errors.append("Remark/Notes must not be empty.")

    if errors:
        return jsonify({"success": False, "message": " ".join(errors)})

    try:
        if row_id:
            db.session.execute(text("""
                UPDATE CAFREF SET REF_NAME = :ref_name, REF_PHONE = :ref_phone, REMARK = :remark
                WHERE APLESS = :apless AND ID = :row_id
            """), {
                "ref_name": ref_name, "ref_phone": ref_phone, "remark": remark,
                "apless": apless, "row_id": row_id,
            })
        else:
            db.session.execute(text("""
                INSERT INTO CAFREF (APLESS, appl_no, REF_NAME, REF_PHONE, REMARK, INPUT_DT)
                VALUES (:apless, :applno, :ref_name, :ref_phone, :remark, SYSDATETIME())
            """), {
                "apless": apless, "applno": applno, "ref_name": ref_name,
                "ref_phone": ref_phone, "remark": remark,
            })
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Failed to save reference — apless=%s applno=%s id=%s", apless, applno, row_id
        )
        return jsonify({"success": False, "message": "Save failed. Please try again."}), 500

    return jsonify({"success": True})

@cam_edit_bp.route("/references", methods=["DELETE"])
@login_required
def delete_reference():
    apless = (request.args.get("apless") or "").strip()
    row_id = request.args.get("id", "")
    if not apless or not row_id:
        return jsonify({"success": False, "message": "apless and id are required"}), 400

    try:
        db.session.execute(text("""
            DELETE FROM CAFREF WHERE APLESS = :apless AND ID = :row_id
        """), {"apless": apless, "row_id": row_id})
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to delete reference — apless=%s id=%s", apless, row_id)
        return jsonify({"success": False, "message": "Delete failed. Please try again."}), 500

    return jsonify({"success": True})

EQUIPMENT_WHEELS_REQUIRED_MODELS = ("05", "06", "07", "09", "10")
EQUIPMENT_KAROSERI_ELIGIBLE_MODELS = ("01", "04", "05", "06", "10")
EQUIPMENT_STNK_EXEMPT_MODELS = ("04", "05", "06", "07", "09")
FINANCING_PURPOSE_FIN_TYPES = ("D", "M", "W")
SUPPLIER_CATEGORY_TYPES = {"karoseri": "KR", "accessories": "AC", "other": "OT"}

def _fetch_brands():
    rows = db.session.execute(text("""
        SELECT BRAND, BRAND_NM FROM UMFBRAND WITH(NOLOCK)
        WHERE BRAND_NM NOT IN ('CBU', 'All Brand', 'Used Cars', 'Used Trucks')
        ORDER BY BRAND_NM
    """)).fetchall()
    return [{"value": r.BRAND, "label": r.BRAND_NM} for r in rows]

def _fetch_vehicle_models():
    rows = db.session.execute(text("""
        SELECT MODEL, MODEL_NM FROM UMFMODEL WITH(NOLOCK) ORDER BY MODEL_NM
    """)).fetchall()
    return [{"value": r.MODEL, "label": r.MODEL_NM} for r in rows]

def _fetch_vehicle_purposes():
    rows = db.session.execute(text("""
        SELECT Purpose, name FROM mstPurpose WITH(NOLOCK) ORDER BY name
    """)).fetchall()
    return [{"value": r.Purpose, "label": r.name} for r in rows]

def _fetch_areas():
    rows = db.session.execute(text("""
        SELECT AREA_CD, Propinsi, Kabupaten FROM UMFAREA WITH(NOLOCK) WHERE FLAG_DEL = 0
        ORDER BY Propinsi, Kabupaten
    """)).fetchall()
    return [{"value": r.AREA_CD, "label": f"{r.Propinsi} - {r.Kabupaten}"} for r in rows]

def _fetch_gps_vendors():
    rows = db.session.execute(text("""
        SELECT SUPP, NAME FROM VENDOR WITH(NOLOCK) WHERE Supp_Category = 'GPS' ORDER BY NAME
    """)).fetchall()
    return [{"value": r.SUPP, "label": r.NAME} for r in rows]

def _fetch_financing_purposes(fin_type: str, purpoffinc: str):
    if fin_type == "D":
        rows = db.session.execute(text("""
            SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK)
            WHERE CAT_VALUE = 'Fund_Facility' AND VALUE NOT IN ('08') ORDER BY DESC_VALUE
        """)).fetchall()
    elif fin_type == "M" or (purpoffinc == "4" and fin_type == "S"):
        rows = db.session.execute(text("""
            SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK)
            WHERE CAT_VALUE = 'Business_Capital_Facility' ORDER BY DESC_VALUE
        """)).fetchall()
    elif fin_type == "W":
        rows = db.session.execute(text("""
            SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK)
            WHERE CAT_VALUE = 'Business_Capital_Facility' AND VALUE = '61' ORDER BY DESC_VALUE
        """)).fetchall()
    else:
        return []
    return [{"value": r.VALUE, "label": r.DESC_VALUE} for r in rows]

def _fetch_ojk_fin_goods(purpoffinc: str, fin_type: str):
    if purpoffinc == "3":
        rows = db.session.execute(text("""
            SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK)
            WHERE CAT_VALUE = 'OJK_COL_TYPE' AND VALUE IN ('P', 'K')
        """)).fetchall()
    elif purpoffinc == "4" and fin_type in ("M", "S"):
        rows = db.session.execute(text("""
            SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK)
            WHERE CAT_VALUE = 'OJK_FIN_TYPE' AND VALUE IN ('P', 'J')
        """)).fetchall()
    elif purpoffinc == "4" and fin_type == "W":
        rows = db.session.execute(text("""
            SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK)
            WHERE CAT_VALUE = 'OJK_FIN_TYPE' AND VALUE = 'P'
        """)).fetchall()
    elif purpoffinc == "5" and fin_type == "I":
        rows = db.session.execute(text("""
            SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK)
            WHERE CAT_VALUE = 'OJK_FIN_TYPE' AND VALUE = 'K'
        """)).fetchall()
    elif purpoffinc == "5" and fin_type == "D":
        rows = db.session.execute(text("""
            SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK)
            WHERE CAT_VALUE = 'OJK_FIN_TYPE' AND VALUE = 'J'
        """)).fetchall()
    else:
        return []
    return [{"value": r.VALUE, "label": r.DESC_VALUE} for r in rows]

def _fetch_ojk_fin_goods_detail(fin_good: str, fin_type: str, purpoffinc: str, brand: str, veh_type: str, model: str, condition: str):
    if purpoffinc == "4":
        if fin_good == "P":
            values = ("e20",) if fin_type == "W" else ("e3", "e5", "e6", "e7", "e11", "e20")
            rows = db.session.execute(text(
                "SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE = 'OJK_FIN_GOOD_P' AND VALUE IN :vals"
            ).bindparams(bindparam("vals", expanding=True)), {"vals": list(values)}).fetchall()
        elif fin_good == "J":
            rows = db.session.execute(text("""
                SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE = 'OJK_FIN_GOOD_J' AND VALUE = 'e61'
            """)).fetchall()
        else:
            return []
    elif purpoffinc == "3":
        if fin_good == "P":
            rows = db.session.execute(text("""
                SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE = 'OJK_FIN_GOOD_P' AND VALUE IN ('e9', 'e20')
            """)).fetchall()
        elif fin_good == "K":
            fuel_row = db.session.execute(text("""
                SELECT FUEL FROM UMFTYPE WITH(NOLOCK) WHERE BRAND = :brand AND TYPE = :type AND Model = :model
            """), {"brand": brand, "type": veh_type, "model": model}).fetchone()
            fuel = fuel_row.FUEL if fuel_row else None
            if condition == "NEW":
                detail = "e382" if fuel in ("B", "G", "S") else ("e383" if fuel in ("HG", "HL") else "e381")
            else:
                detail = "e392" if fuel in ("B", "G", "S") else ("e393" if fuel in ("HG", "HL") else "e391")
            rows = db.session.execute(text("""
                SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE = 'OJK_FIN_GOOD_K' AND VALUE = :detail
            """), {"detail": detail}).fetchall()
        else:
            return []
    else:
        return []
    return [{"value": r.VALUE, "label": r.DESC_VALUE} for r in rows]

def _compute_ojk_coll_goods(model: str, new_car: str, purpoffinc: str, fin_type: str):
    eligible = (
        (purpoffinc == "3" and fin_type in ("I", "S"))
        or purpoffinc == "4"
        or (purpoffinc == "5" and fin_type != "F")
    )
    if not eligible or not model:
        return None, []

    if model in ("01", "02", "03"):
        detail_value = "e39" if new_car == "1" else "e38"
        category = "K"
        cat_table, detail_table = "OJK_COL_GOOD_K", detail_value
    elif model in ("04", "05", "06", "07", "08", "09", "10"):
        category = "P"
        detail_value = "e9"
        cat_table = "OJK_COL_GOOD_P"
    else:
        return None, []

    cat_row = db.session.execute(text("""
        SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE = 'OJK_COL_TYPE' AND VALUE = :val
    """), {"val": category}).fetchone()
    detail_row = db.session.execute(text("""
        SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE = :cat AND VALUE = :val
    """), {"cat": cat_table, "val": detail_value}).fetchone()

    cat = {"value": cat_row.VALUE, "label": cat_row.DESC_VALUE} if cat_row else None
    details = [{"value": detail_row.VALUE, "label": detail_row.DESC_VALUE}] if detail_row else []
    return cat, details

def _equipment_model_dependent_lookups(brand: str, model: str, new_car: str, purpoffinc: str, fin_type: str):
    types = []
    if brand and model:
        rows = db.session.execute(text("""
            SELECT TYPE, TYPE_NM FROM UMFTYPE WITH(NOLOCK)
            WHERE BRAND = :brand AND Model = :model AND isActive = 1 ORDER BY TYPE_NM
        """), {"brand": brand, "model": model}).fetchall()
        types = [{"value": r.TYPE, "label": r.TYPE_NM} for r in rows]

    karoseri = []
    if model in EQUIPMENT_KAROSERI_ELIGIBLE_MODELS:
        rows = db.session.execute(text("""
            SELECT KAROSERI, KAROSERI_DESC FROM UMFKAROSERI WITH(NOLOCK)
            WHERE MODEL = :model AND isActive = 1 ORDER BY KAROSERI_DESC
        """), {"model": model}).fetchall()
        karoseri = [{"value": r.KAROSERI, "label": r.KAROSERI_DESC} for r in rows]

    coll_good, coll_good_detail = _compute_ojk_coll_goods(model, new_car, purpoffinc, fin_type)

    return {
        "types": types,
        "karoseri": karoseri,
        "ojkCollGood": coll_good,
        "ojkCollGoodDetail": coll_good_detail,
        "wheelsRequired": model in EQUIPMENT_WHEELS_REQUIRED_MODELS,
    }

def _fetch_equipment(applno: str):
    row = db.session.execute(text("""
        SELECT a.CAFEQUIP_ID, a.SUPP, a.BRAND, a.TYPE, a.MODEL, a.TAHUN, a.CONDITION,
               a.CHASIS, a.ENGINE, a.COLOUR, a.POLICENO, a.USERUSAGE, a.PURPOSE, a.PARK_LOC,
               a.PARK_ZIPCODE, a.CITY_PARK, a.KAROSERI, a.STNK_VALIDDT, a.KAROSERI_SUPP,
               a.ACCESSORIES_SUPP, a.OTHER_SUPP, a.WHEELS, a.FUND_PURPOSE,
               b.NAME AS SUPP_NM, b.ADDRESS AS SUPP_ADDR, b.CITY AS SUPP_CITY, b.Supp_Type,
               c.NAME AS KAROSERI_NM, c.ADDRESS AS KAROSERI_ADDR, c.CITY AS KAROSERI_CITY,
               d.NAME AS ACCESSORIES_NM, d.ADDRESS AS ACCESSORIES_ADDR, d.CITY AS ACCESSORIES_CITY,
               e.NAME AS OTHER_NM, e.ADDRESS AS OTHER_ADDR, e.CITY AS OTHER_CITY,
               f.FIN_PURPOSE, f.OJK_Fin_Goods, f.OJK_Fin_Goods_Detail, f.OJK_Coll_Goods,
               f.OJK_Coll_Goods_Detail, f.IsRedCode, f.GPS_Vendor
        FROM CAFEQUIP a WITH(NOLOCK)
                LEFT JOIN CLFSUPP b WITH(NOLOCK) ON a.SUPP = b.SUPP
                LEFT JOIN CLFSUPP c WITH(NOLOCK) ON a.KAROSERI_SUPP = c.SUPP
                LEFT JOIN CLFSUPP d WITH(NOLOCK) ON a.ACCESSORIES_SUPP = d.SUPP
                LEFT JOIN CLFSUPP e WITH(NOLOCK) ON a.OTHER_SUPP = e.SUPP
                LEFT JOIN Cafequip_Detail f WITH(NOLOCK) ON a.APPL_NO = f.APPL_NO AND f.Cafequip_ID = a.CAFEQUIP_ID
        WHERE a.APPL_NO = :applno
    """), {"applno": applno}).fetchone()

    if not row:
        return None

    def addr(a, city):
        return f"{a}\n{city}" if a else ""

    return {
        "cafequipId": row.CAFEQUIP_ID,
        "supp": row.SUPP or "",
        "suppName": row.SUPP_NM or "",
        "suppAddress": addr(row.SUPP_ADDR, row.SUPP_CITY),
        "suppType": row.Supp_Type or "",
        "brand": row.BRAND or "",
        "type": row.TYPE or "",
        "model": row.MODEL or "",
        "tahun": (row.TAHUN or "").strip(),
        "condition": (row.CONDITION or "").strip(),
        "chasis": row.CHASIS or "",
        "engine": row.ENGINE or "",
        "colour": row.COLOUR or "",
        "policeno": row.POLICENO or "",
        "userusage": row.USERUSAGE or "",
        "purpose": row.PURPOSE or "",
        "parkLoc": row.PARK_LOC or "",
        "parkZipcode": row.PARK_ZIPCODE or "",
        "cityPark": row.CITY_PARK or "",
        "karoseri": row.KAROSERI or "",
        "karoseriSupp": row.KAROSERI_SUPP or "",
        "karoseriName": row.KAROSERI_NM or "",
        "karoseriAddress": addr(row.KAROSERI_ADDR, row.KAROSERI_CITY),
        "accessoriesSupp": row.ACCESSORIES_SUPP or "",
        "accessoriesName": row.ACCESSORIES_NM or "",
        "accessoriesAddress": addr(row.ACCESSORIES_ADDR, row.ACCESSORIES_CITY),
        "otherSupp": row.OTHER_SUPP or "",
        "otherName": row.OTHER_NM or "",
        "otherAddress": addr(row.OTHER_ADDR, row.OTHER_CITY),
        "stnkValidDt": row.STNK_VALIDDT.strftime("%Y-%m-%d") if row.STNK_VALIDDT else "",
        "wheels": row.WHEELS if row.WHEELS is not None else "",
        "fundPurpose": row.FUND_PURPOSE or "",
        "finPurpose": row.FIN_PURPOSE or "",
        "ojkFinGoods": row.OJK_Fin_Goods or "",
        "ojkFinGoodsDetail": row.OJK_Fin_Goods_Detail or "",
        "ojkCollGoods": row.OJK_Coll_Goods or "",
        "ojkCollGoodsDetail": row.OJK_Coll_Goods_Detail or "",
        "redCode": row.IsRedCode == "1",
        "gpsVendor": row.GPS_Vendor or "",
    }

TYPE_CD_DEFAULT = "07"

PASSENGER_MODELS = ("01", "02", "03")
COMMERCIAL_MODELS = ("04", "05", "06", "07", "08", "09", "10")
KAROSERI_MODELS = ("01", "04", "05", "06", "10")
WHEELS_INPUT_MODELS = ("05", "06", "07", "09", "10", "21")
WHEELS_VALIDATION_MODELS = ("05", "06", "07", "09", "10")

DEALER_LOCK_EXEMPT_APPROVERS = ("ricky irawan", "christian haryanto")
DEALER_LOCK_LEGACY_APPROVER = "antonius martono"
DEALER_LOCK_PARAMETER_DATE = date(2022, 11, 1)

SEMBRANI_NAME_LIKE = "%SEMBRANI FINANCE INDONESIA, PT.%"

W61_FUND_PURPOSE = "Pembelian Kendaraan Bermotor (mobil) untuk Kegiatan usaha Debitur"
SUPPLIER_CATEGORIES = {"dealer": None, "karoseri": "KR", "accessories": "AC", "other": "OT"}
SUPPLIER_SEARCH_LIMIT = 100

FIN_PURPOSE_OJK_MAP = {
    "06": ("J", "e56"),   # Education
    "07": ("J", "e57"),   # Healthcare
    "09": ("J", "e61"),   # House Renovation
    "10": ("J", "e58"),   # Leisure
    "11": ("J", "e61"),   # Religious
    "12": ("J", "e59"),   # Wedding
    "51": ("P", "e2"),    # Heavy Equipment
    "52": ("P", "e3"),    # Office Equipment
    "53": ("P", "e5"),    # Photo Equipment
    "54": ("P", "e6"),    # Medical Equipment
    "55": ("P", "e7"),    # Printer Equipment
    "56": ("P", "e8"),    # Machine
    "57": ("P", "e9"),    # Transportation Car
    "58": ("P", "e86"),   # Airplane
    "59": ("P", "e87"),   # Ship / Water Equipment
    "60": ("P", "e11"),   # Computer
    "61": ("P", "e20"),   # Others Productive Goods
    "62": ("J", "e61"),   # Productive Services
}

def _s(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else ""
    return str(value).strip()

def _options(rows, value_attr="val", label_attr="lbl"):
    return [
        {"value": _s(getattr(row, value_attr)), "label": _s(getattr(row, label_attr))}
        for row in rows
    ]

def _in_clause(prefix, values, params):
    keys = []
    for index, value in enumerate(values):
        key = "%s%d" % (prefix, index)
        params[key] = value
        keys.append(":" + key)
    return ", ".join(keys)

def _combo_options(cat_value, values=None, exclude=None):
    """SELECT [VALUE], DESC_VALUE FROM MSTCOMBO WHERE CAT_VALUE = ... [AND ...]"""
    params = {"cat": cat_value}
    sql = ("SELECT [VALUE] AS val, DESC_VALUE AS lbl "
           "FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE = :cat")
    if values is not None:
        values = [v for v in values if v not in (None, "")]
        if not values:
            return []
        sql += " AND [VALUE] IN (%s)" % _in_clause("v", values, params)
    if exclude:
        sql += " AND [VALUE] NOT IN (%s)" % _in_clause("x", exclude, params)
    return _options(db.session.execute(text(sql), params).fetchall())

def _as_date(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(value)[:19], fmt).date()
        except ValueError:
            continue
    return None

def _iso(value):
    parsed = _as_date(value)
    return parsed.isoformat() if parsed else ""

def _address(row, address_attr="ADDRESS", city_attr="CITY"):
    if row is None:
        return ""
    return "%s\n%s" % (_s(getattr(row, address_attr)), _s(getattr(row, city_attr)))

def _dealer_locked(applno):
    row = db.session.execute(text("""
        SELECT TOP 1 APPR_STS, APPR_ID, APPR_DATE
        FROM MCMOCAMACCSTATUS WITH(NOLOCK)
        WHERE APPL_NO = :applno
        ORDER BY [NO] DESC
    """), {"applno": applno}).fetchone()
    if not row:
        return False

    appr_sts = _s(row.APPR_STS)
    appr_id = _s(row.APPR_ID).lower()
    appr_dt = _as_date(row.APPR_DATE)

    if appr_sts == "A" and appr_id in DEALER_LOCK_EXEMPT_APPROVERS:
        return False

    if appr_sts == "R":
        pending = db.session.execute(text("""
            SELECT 1 FROM MCMOCAMACCSTATUS WITH(NOLOCK)
            WHERE APPL_NO = :applno AND APPR_STS = 'P'
        """), {"applno": applno}).fetchone()
        return bool(pending)

    if appr_sts == "P":
        return True

    if (appr_sts == "A" and appr_id == DEALER_LOCK_LEGACY_APPROVER
            and appr_dt is not None and appr_dt < DEALER_LOCK_PARAMETER_DATE):
        return False

    return True

def _show_ojk_fin_goods(purpoffinc, fin_type):
    return ((purpoffinc == "3" and fin_type != "F")
            or purpoffinc == "4"
            or (purpoffinc == "5" and fin_type != "F"))

def _ojk_fin_goods_disabled(purpoffinc, fin_type):
    return ((purpoffinc == "4" and fin_type in ("M", "S"))
            or (purpoffinc == "5" and fin_type == "D"))

def _ojk_fin_goods_required(fin_type):
    return fin_type not in ("M", "D")

def _show_coll_goods(purpoffinc, fin_type):
    if purpoffinc == "3":
        return fin_type in ("I", "S")
    if purpoffinc == "4":
        return True
    if purpoffinc == "5":
        return fin_type != "F"
    return False

def _show_financing_purpose(purpoffinc, fin_type):
    return fin_type in ("D", "M", "W") or (purpoffinc == "4" and fin_type == "S")

def _show_fund_purpose(fin_type):
    return fin_type in ("D", "M", "W")

def _ojk_fin_goods_options(purpoffinc, fin_type):
    if purpoffinc == "3":
        return _combo_options("OJK_COL_TYPE", ["P", "K"])
    if purpoffinc == "4":
        if fin_type in ("M", "S"):
            return _combo_options("OJK_FIN_TYPE", ["P", "J"])
        if fin_type == "W":
            return _combo_options("OJK_FIN_TYPE", ["P"])
        return []
    if purpoffinc == "5":
        if fin_type == "I":
            return _combo_options("OJK_FIN_TYPE", ["K"])
        if fin_type == "D":
            return _combo_options("OJK_FIN_TYPE", ["J"])
    return []

def _consumer_fin_goods_detail(brand, type_code, model, condition):
    row = db.session.execute(text("""
        SELECT FUEL FROM UMFTYPE WITH(NOLOCK)
        WHERE BRAND = :brand AND [TYPE] = :type_code AND Model = :model
    """), {"brand": brand, "type_code": type_code, "model": model}).fetchone()
    fuel = _s(row.FUEL) if row else ""

    if condition == "NEW":
        if fuel in ("B", "G", "S"):
            return "e382"
        if fuel in ("HG", "HL"):
            return "e383"
        return "e381"
    if condition == "USED":
        if fuel in ("B", "G", "S"):
            return "e392"
        if fuel in ("HG", "HL"):
            return "e393"
        return "e391"
    return ""

def _ojk_fin_goods_detail_initial(purpoffinc, fin_type, brand, type_code, model, condition):
    if purpoffinc == "3":
        return _combo_options("OJK_FIN_GOOD_P", ["e9", "e20"]), None

    if purpoffinc == "4":
        if fin_type == "M":
            rows = db.session.execute(text("""
                SELECT [VALUE] AS val, DESC_VALUE AS lbl
                FROM MSTCOMBO WITH(NOLOCK)
                WHERE CAT_VALUE = 'OJK_FIN_GOOD_P' OR CAT_VALUE = 'OJK_FIN_GOOD_J'
            """)).fetchall()
            return _options(rows), None
        
        if fin_type == "W":
            return _combo_options("OJK_FIN_GOOD_P", ["e20"]), None
        if fin_type == "S":
            rows = db.session.execute(text("""
                SELECT [VALUE] AS val, DESC_VALUE AS lbl
                FROM MSTCOMBO WITH(NOLOCK)
                WHERE (CAT_VALUE = 'OJK_FIN_GOOD_P'
                       AND [VALUE] IN ('e3', 'e5', 'e6', 'e7', 'e11', 'e20'))
                   OR (CAT_VALUE = 'OJK_FIN_GOOD_J' AND [VALUE] IN ('e61'))
            """)).fetchall()
            return _options(rows), None
        return [], None

    if purpoffinc == "5":
        if fin_type == "I":
            forced = _consumer_fin_goods_detail(brand, type_code, model, condition)
            return _combo_options("OJK_FIN_GOOD_K", [forced]), forced
        if fin_type == "D":
            return _combo_options("OJK_FIN_GOOD_J", exclude=["e60"]), None

    return [], None

def _ojk_fin_goods_detail_options(fin_good, fin_type, purpoffinc,
                                  brand, type_code, model, condition):
    if purpoffinc == "4":
        if fin_good == "P":
            if fin_type == "W":
                return _combo_options("OJK_FIN_GOOD_P", ["e20"])
            return _combo_options("OJK_FIN_GOOD_P", ["e3", "e5", "e6", "e7", "e11", "e20"])
        if fin_good == "J":
            return _combo_options("OJK_FIN_GOOD_J", ["e61"])
        return []

    if purpoffinc == "3":
        if fin_good == "P":
            return _combo_options("OJK_FIN_GOOD_P", ["e9", "e20"])
        if fin_good == "K":
            value = _consumer_fin_goods_detail(brand, type_code, model, condition)
            return _combo_options("OJK_FIN_GOOD_K", [value])
        return []

    return []

def _resolve_coll_goods(purpoffinc, fin_type, model, new_car, stored_detail):
    if not _show_coll_goods(purpoffinc, fin_type):
        return None, [], "", ""

    detail_value = _s(stored_detail)
    if model:
        if model in PASSENGER_MODELS:
            detail_value = "e39" if new_car == "1" else "e38"
        elif model in COMMERCIAL_MODELS:
            detail_value = "e9"

    head_value = "P" if detail_value == "e9" else "K"
    head_options = _combo_options("OJK_COL_TYPE", [head_value])
    head_option = head_options[0] if head_options else None

    detail_options = []
    if model:
        if model in PASSENGER_MODELS:
            detail_options = _combo_options("OJK_COL_GOOD_K", [detail_value])
        elif model in COMMERCIAL_MODELS:
            detail_options = _combo_options("OJK_COL_GOOD_P", ["e9"])

    if not detail_options:
        detail_value = ""

    return head_option, detail_options, head_value, detail_value

def _karoseri_options(model):
    if not model or model not in KAROSERI_MODELS:
        return []
    rows = db.session.execute(text("""
        SELECT KAROSERI AS val, KAROSERI_DESC AS lbl
        FROM UMFKAROSERI WITH(NOLOCK)
        WHERE MODEL = :model AND isActive = 1
        ORDER BY KAROSERI_DESC
    """), {"model": model}).fetchall()
    return _options(rows)

def _type_options(brand, model):
    if not brand or not model:
        return []
    rows = db.session.execute(text("""
        SELECT [TYPE] AS val, TYPE_NM AS lbl
        FROM UMFTYPE WITH(NOLOCK)
        WHERE BRAND = :brand AND Model = :model AND isActive = 1
        ORDER BY TYPE_NM
    """), {"brand": brand, "model": model}).fetchall()
    return _options(rows)

def _financing_purpose_options(purpoffinc, fin_type):
    if fin_type == "D":
        return _combo_options("Fund_Facility", exclude=["08"])
    if fin_type == "M" or (purpoffinc == "4" and fin_type == "S"):
        return _combo_options("Business_Capital_Facility")
    if fin_type == "W":
        return _combo_options("Business_Capital_Facility", ["61"])
    return []

def _tax_free_flag(applno, supp):
    if not supp:
        return "0"
    cont = db.session.execute(text("""
        SELECT CREATE_DATE FROM CAFCONT WITH(NOLOCK) WHERE APPL_NO = :applno
    """), {"applno": applno}).fetchone()
    created = _as_date(cont.CREATE_DATE) if cont else None
    if created is None:
        return "0"

    row = db.session.execute(text("""
        SELECT TFFrom, TFTo FROM BeneficiaryTax WITH(NOLOCK)
        WHERE BeneficiaryID = :supp AND Category = 'DEALER'
    """), {"supp": supp}).fetchone()
    if not row:
        return "0"

    tf_from = _as_date(row.TFFrom)
    tf_to = _as_date(row.TFTo)
    if tf_from is None or tf_to is None:
        return "0"
    return "1" if tf_from <= created <= tf_to else "0"

TYPE_CD_DEFAULT = "07"
PASSENGER_MODELS = ("01", "02", "03")
COMMERCIAL_MODELS = ("04", "05", "06", "07", "08", "09", "10")
KAROSERI_MODELS = ("01", "04", "05", "06", "10")
WHEELS_INPUT_MODELS = ("05", "06", "07", "09", "10", "21")
WHEELS_VALIDATION_MODELS = ("05", "06", "07", "09", "10")
DEALER_LOCK_EXEMPT_APPROVERS = ("ricky irawan", "christian haryanto")
DEALER_LOCK_LEGACY_APPROVER = "antonius martono"
DEALER_LOCK_PARAMETER_DATE = date(2022, 11, 1)
SEMBRANI_NAME_LIKE = "%SEMBRANI FINANCE INDONESIA, PT.%"
W61_FUND_PURPOSE = "Pembelian Kendaraan Bermotor (mobil) untuk Kegiatan usaha Debitur"
SUPPLIER_CATEGORIES = {"dealer": None, "karoseri": "KR", "accessories": "AC", "other": "OT"}

SUPPLIER_PAGE_SIZE = 20
SUPPLIER_PAGE_SIZE_MAX = 100

FIN_PURPOSE_OJK_MAP = {
    "06": ("J", "e56"),   # Education
    "07": ("J", "e57"),   # Healthcare
    "09": ("J", "e61"),   # House Renovation
    "10": ("J", "e58"),   # Leisure
    "11": ("J", "e61"),   # Religious
    "12": ("J", "e59"),   # Wedding
    "51": ("P", "e2"),    # Heavy Equipment
    "52": ("P", "e3"),    # Office Equipment
    "53": ("P", "e5"),    # Photo Equipment
    "54": ("P", "e6"),    # Medical Equipment
    "55": ("P", "e7"),    # Printer Equipment
    "56": ("P", "e8"),    # Machine
    "57": ("P", "e9"),    # Transportation Car
    "58": ("P", "e86"),   # Airplane
    "59": ("P", "e87"),   # Ship / Water Equipment
    "60": ("P", "e11"),   # Computer
    "61": ("P", "e20"),   # Others Productive Goods
    "62": ("J", "e61"),   # Productive Services
}

def _s(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else ""
    return str(value).strip()

def _options(rows, value_attr="val", label_attr="lbl"):
    return [
        {"value": _s(getattr(row, value_attr)), "label": _s(getattr(row, label_attr))}
        for row in rows
    ]

def _in_clause(prefix, values, params):
    keys = []
    for index, value in enumerate(values):
        key = "%s%d" % (prefix, index)
        params[key] = value
        keys.append(":" + key)
    return ", ".join(keys)

def _combo_options(cat_value, values=None, exclude=None):
    params = {"cat": cat_value}
    sql = ("SELECT [VALUE] AS val, DESC_VALUE AS lbl "
           "FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE = :cat")
    if values is not None:
        values = [v for v in values if v not in (None, "")]
        if not values:
            return []
        sql += " AND [VALUE] IN (%s)" % _in_clause("v", values, params)
    if exclude:
        sql += " AND [VALUE] NOT IN (%s)" % _in_clause("x", exclude, params)
    return _options(db.session.execute(text(sql), params).fetchall())

def _as_date(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(value)[:19], fmt).date()
        except ValueError:
            continue
    return None

def _iso(value):
    parsed = _as_date(value)
    return parsed.isoformat() if parsed else ""

def _address(row, address_attr="ADDRESS", city_attr="CITY"):
    if row is None:
        return ""
    return "%s\n%s" % (_s(getattr(row, address_attr)), _s(getattr(row, city_attr)))

def _dealer_locked(applno):
    row = db.session.execute(text("""
        SELECT TOP 1 APPR_STS, APPR_ID, APPR_DATE
        FROM MCMOCAMACCSTATUS WITH(NOLOCK)
        WHERE APPL_NO = :applno
        ORDER BY [NO] DESC
    """), {"applno": applno}).fetchone()
    if not row:
        return False

    appr_sts = _s(row.APPR_STS)
    appr_id = _s(row.APPR_ID).lower()
    appr_dt = _as_date(row.APPR_DATE)

    if appr_sts == "A" and appr_id in DEALER_LOCK_EXEMPT_APPROVERS:
        return False

    if appr_sts == "R":
        pending = db.session.execute(text("""
            SELECT 1 FROM MCMOCAMACCSTATUS WITH(NOLOCK)
            WHERE APPL_NO = :applno AND APPR_STS = 'P'
        """), {"applno": applno}).fetchone()
        return bool(pending)

    if appr_sts == "P":
        return True

    if (appr_sts == "A" and appr_id == DEALER_LOCK_LEGACY_APPROVER
            and appr_dt is not None and appr_dt < DEALER_LOCK_PARAMETER_DATE):
        return False

    return True

def _show_ojk_fin_goods(purpoffinc, fin_type):
    return ((purpoffinc == "3" and fin_type != "F")
            or purpoffinc == "4"
            or (purpoffinc == "5" and fin_type != "F"))

def _ojk_fin_goods_disabled(purpoffinc, fin_type):
    return ((purpoffinc == "4" and fin_type in ("M", "S"))
            or (purpoffinc == "5" and fin_type == "D"))

def _ojk_fin_goods_required(fin_type):
    return fin_type not in ("M", "D")

def _show_coll_goods(purpoffinc, fin_type):
    if purpoffinc == "3":
        return fin_type in ("I", "S")
    if purpoffinc == "4":
        return True
    if purpoffinc == "5":
        return fin_type != "F"
    return False

def _show_financing_purpose(purpoffinc, fin_type):
    return fin_type in ("D", "M", "W") or (purpoffinc == "4" and fin_type == "S")

def _show_fund_purpose(fin_type):
    return fin_type in ("D", "M", "W")

def _ojk_fin_goods_options(purpoffinc, fin_type):
    if purpoffinc == "3":
        return _combo_options("OJK_COL_TYPE", ["P", "K"])
    if purpoffinc == "4":
        if fin_type in ("M", "S"):
            return _combo_options("OJK_FIN_TYPE", ["P", "J"])
        if fin_type == "W":
            return _combo_options("OJK_FIN_TYPE", ["P"])
        return []
    if purpoffinc == "5":
        if fin_type == "I":
            return _combo_options("OJK_FIN_TYPE", ["K"])
        if fin_type == "D":
            return _combo_options("OJK_FIN_TYPE", ["J"])
    return []

def _consumer_fin_goods_detail(brand, type_code, model, condition):
    row = db.session.execute(text("""
        SELECT FUEL FROM UMFTYPE WITH(NOLOCK)
        WHERE BRAND = :brand AND [TYPE] = :type_code AND Model = :model
    """), {"brand": brand, "type_code": type_code, "model": model}).fetchone()
    fuel = _s(row.FUEL) if row else ""

    if condition == "NEW":
        if fuel in ("B", "G", "S"):
            return "e382"
        if fuel in ("HG", "HL"):
            return "e383"
        return "e381"
    if condition == "USED":
        if fuel in ("B", "G", "S"):
            return "e392"
        if fuel in ("HG", "HL"):
            return "e393"
        return "e391"
    return ""

def _ojk_fin_goods_detail_initial(purpoffinc, fin_type, brand, type_code, model, condition):
    if purpoffinc == "3":
        return _combo_options("OJK_FIN_GOOD_P", ["e9", "e20"]), None

    if purpoffinc == "4":
        if fin_type == "M":
            rows = db.session.execute(text("""
                SELECT [VALUE] AS val, DESC_VALUE AS lbl
                FROM MSTCOMBO WITH(NOLOCK)
                WHERE CAT_VALUE = 'OJK_FIN_GOOD_P' OR CAT_VALUE = 'OJK_FIN_GOOD_J'
            """)).fetchall()
            return _options(rows), None
        if fin_type == "W":
            return _combo_options("OJK_FIN_GOOD_P", ["e20"]), None
        if fin_type == "S":
            rows = db.session.execute(text("""
                SELECT [VALUE] AS val, DESC_VALUE AS lbl
                FROM MSTCOMBO WITH(NOLOCK)
                WHERE (CAT_VALUE = 'OJK_FIN_GOOD_P'
                       AND [VALUE] IN ('e3', 'e5', 'e6', 'e7', 'e11', 'e20'))
                   OR (CAT_VALUE = 'OJK_FIN_GOOD_J' AND [VALUE] IN ('e61'))
            """)).fetchall()
            return _options(rows), None
        return [], None

    if purpoffinc == "5":
        if fin_type == "I":
            forced = _consumer_fin_goods_detail(brand, type_code, model, condition)
            return _combo_options("OJK_FIN_GOOD_K", [forced]), forced
        if fin_type == "D":
            return _combo_options("OJK_FIN_GOOD_J", exclude=["e60"]), None

    return [], None

def _ojk_fin_goods_detail_options(fin_good, fin_type, purpoffinc,
                                  brand, type_code, model, condition):
    if purpoffinc == "4":
        if fin_good == "P":
            if fin_type == "W":
                return _combo_options("OJK_FIN_GOOD_P", ["e20"])
            return _combo_options("OJK_FIN_GOOD_P", ["e3", "e5", "e6", "e7", "e11", "e20"])
        if fin_good == "J":
            return _combo_options("OJK_FIN_GOOD_J", ["e61"])
        return []

    if purpoffinc == "3":
        if fin_good == "P":
            return _combo_options("OJK_FIN_GOOD_P", ["e9", "e20"])
        if fin_good == "K":
            value = _consumer_fin_goods_detail(brand, type_code, model, condition)
            return _combo_options("OJK_FIN_GOOD_K", [value])
        return []

    return []

def _resolve_coll_goods(purpoffinc, fin_type, model, new_car, stored_detail):
    if not _show_coll_goods(purpoffinc, fin_type):
        return None, [], "", ""

    detail_value = _s(stored_detail)
    if model:
        if model in PASSENGER_MODELS:
            detail_value = "e39" if new_car == "1" else "e38"
        elif model in COMMERCIAL_MODELS:
            detail_value = "e9"

    head_value = "P" if detail_value == "e9" else "K"
    head_options = _combo_options("OJK_COL_TYPE", [head_value])
    head_option = head_options[0] if head_options else None

    detail_options = []
    if model:
        if model in PASSENGER_MODELS:
            detail_options = _combo_options("OJK_COL_GOOD_K", [detail_value])
        elif model in COMMERCIAL_MODELS:
            detail_options = _combo_options("OJK_COL_GOOD_P", ["e9"])

    if not detail_options:
        detail_value = ""

    return head_option, detail_options, head_value, detail_value

def _karoseri_options(model):
    if not model or model not in KAROSERI_MODELS:
        return []
    rows = db.session.execute(text("""
        SELECT KAROSERI AS val, KAROSERI_DESC AS lbl
        FROM UMFKAROSERI WITH(NOLOCK)
        WHERE MODEL = :model AND isActive = 1
        ORDER BY KAROSERI_DESC
    """), {"model": model}).fetchall()
    return _options(rows)

def _type_options(brand, model):
    if not brand or not model:
        return []
    rows = db.session.execute(text("""
        SELECT [TYPE] AS val, TYPE_NM AS lbl
        FROM UMFTYPE WITH(NOLOCK)
        WHERE BRAND = :brand AND Model = :model AND isActive = 1
        ORDER BY TYPE_NM
    """), {"brand": brand, "model": model}).fetchall()
    return _options(rows)

def _dealer_type_options():
    rows = db.session.execute(text("""
        SELECT CODE AS val, DESCRIPTION AS lbl FROM MSTDEALERTYPE WITH(NOLOCK)
        ORDER BY DESCRIPTION
    """)).fetchall()
    return _options(rows)

def _equipment_type_options():
    rows = db.session.execute(text("""
        SELECT TYPE_CD AS val, TYPE_NM AS lbl FROM UMFJBM WITH(NOLOCK)
    """)).fetchall()
    return _options(rows)

def _financing_purpose_options(purpoffinc, fin_type):
    if fin_type == "D":
        return _combo_options("Fund_Facility", exclude=["08"])
    if fin_type == "M" or (purpoffinc == "4" and fin_type == "S"):
        return _combo_options("Business_Capital_Facility")
    if fin_type == "W":
        return _combo_options("Business_Capital_Facility", ["61"])
    return []

def _tax_free_flag(applno, supp):
    if not supp:
        return "0"
    cont = db.session.execute(text("""
        SELECT CREATE_DATE FROM CAFCONT WITH(NOLOCK) WHERE APPL_NO = :applno
    """), {"applno": applno}).fetchone()
    created = _as_date(cont.CREATE_DATE) if cont else None
    if created is None:
        return "0"

    row = db.session.execute(text("""
        SELECT TFFrom, TFTo FROM BeneficiaryTax WITH(NOLOCK)
        WHERE BeneficiaryID = :supp AND Category = 'DEALER'
    """), {"supp": supp}).fetchone()
    if not row:
        return "0"

    tf_from = _as_date(row.TFFrom)
    tf_to = _as_date(row.TFTo)
    if tf_from is None or tf_to is None:
        return "0"
    return "1" if tf_from <= created <= tf_to else "0"

@cam_edit_bp.route("/equipment", methods=["GET"])
@login_required
def get_cam_equipment():
    apless = _s(request.args.get("apless"))
    applno = _s(request.args.get("applno"))
    fin_type = _s(request.args.get("finType"))
    purpoffinc = _s(request.args.get("purpoffinc"))
    new_car = _s(request.args.get("newCar"))
    conttype = _s(request.args.get("conttype"))

    if not apless or not applno:
        return jsonify({"error": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"blocked": True, "message": block_message}), 409

    condition = "USED" if new_car == "1" else "NEW" if new_car == "2" else ""
    conttype_rs = conttype[:2]

    row = db.session.execute(text("""
        SELECT a.CAFEQUIP_ID, a.SUPP, a.TYPE_CD, a.BRAND, a.[TYPE] AS TYPE_CODE, a.MODEL,
               a.TAHUN, a.CONDITION AS COND, a.PARK_ZIPCODE, a.CHASIS, a.ENGINE, a.COLOUR,
               a.POLICENO, a.USERUSAGE, a.PURPOSE, a.PARK_LOC, a.CITY_PARK, a.KAROSERI,
               a.STNK_VALIDDT, a.KAROSERI_SUPP, a.ACCESSORIES_SUPP, a.OTHER_SUPP,
               a.WHEELS, a.FUND_PURPOSE,
               b.NAME AS SUPP_NM, b.ADDRESS AS SUPP_ADDR, b.CITY AS SUPP_CITY,
               b.Supp_Type AS SUPP_TYPE,
               c.NAME AS KAROSERI_NM, c.ADDRESS AS KAROSERI_ADDR, c.CITY AS KAROSERI_CITY,
               d.NAME AS ACC_NM, d.ADDRESS AS ACC_ADDR, d.CITY AS ACC_CITY,
               e.NAME AS OTHER_NM, e.ADDRESS AS OTHER_ADDR, e.CITY AS OTHER_CITY,
               f.FIN_PURPOSE, f.OJK_Fin_Goods, f.OJK_Fin_Goods_Detail,
               f.OJK_Coll_Goods, f.OJK_Coll_Goods_Detail, f.IsRedCode, f.GPS_Vendor
        FROM CAFEQUIP AS a WITH(NOLOCK)
            LEFT JOIN CLFSUPP AS b WITH(NOLOCK) ON a.SUPP = b.SUPP
            LEFT JOIN CLFSUPP AS c WITH(NOLOCK) ON a.KAROSERI_SUPP = c.SUPP
            LEFT JOIN CLFSUPP AS d WITH(NOLOCK) ON a.ACCESSORIES_SUPP = d.SUPP
            LEFT JOIN CLFSUPP AS e WITH(NOLOCK) ON a.OTHER_SUPP = e.SUPP
            LEFT JOIN Cafequip_Detail AS f WITH(NOLOCK)
                   ON a.APPL_NO = f.APPL_NO AND f.Cafequip_ID = a.CAFEQUIP_ID
        WHERE a.APPL_NO = :applno
    """), {"applno": applno}).fetchone()

    equipment = {
        "supp": "", "suppName": "", "suppAddress": "", "suppType": "",
        "typeCd": TYPE_CD_DEFAULT,
        "brand": "", "type": "", "model": "", "tahun": "",
        "chasis": "", "engine": "", "colour": "", "policeno": "",
        "userusage": "", "purpose": "",
        "karoseri": "", "karoseriSupp": "", "karoseriName": "", "karoseriAddress": "",
        "accessoriesSupp": "", "accessoriesName": "", "accessoriesAddress": "",
        "otherSupp": "", "otherName": "", "otherAddress": "",
        "parkLoc": "", "parkZipcode": "", "cityPark": "",
        "wheels": "", "stnkValidDt": "", "fundPurpose": "", "finPurpose": "",
        "ojkFinGoods": "", "ojkFinGoodsDetail": "",
        "ojkCollGoods": "", "ojkCollGoodsDetail": "",
        "redCode": False, "gpsVendor": "",
    }

    cafequip_id = _s(row.CAFEQUIP_ID) if row else ""

    if cafequip_id:
        if conttype_rs == "RS" and fin_type != "S":
            sembrani = db.session.execute(text("""
                SELECT SUPP, NAME, ADDRESS, CITY FROM CLFSUPP WITH(NOLOCK)
                WHERE NAME LIKE :name
            """), {"name": SEMBRANI_NAME_LIKE}).fetchone()
            if sembrani:
                equipment["supp"] = _s(sembrani.SUPP)
                equipment["suppName"] = _s(sembrani.NAME)
                equipment["suppAddress"] = _address(sembrani)
        else:
            equipment["supp"] = _s(row.SUPP)
            equipment["suppName"] = _s(row.SUPP_NM)
            equipment["suppAddress"] = _address(row, "SUPP_ADDR", "SUPP_CITY")

        equipment.update({
            "suppType": _s(row.SUPP_TYPE),
            "typeCd": _s(row.TYPE_CD) or TYPE_CD_DEFAULT,
            "brand": _s(row.BRAND),
            "type": _s(row.TYPE_CODE),
            "model": _s(row.MODEL),
            "tahun": _s(row.TAHUN),
            "chasis": _s(row.CHASIS),
            "engine": _s(row.ENGINE),
            "colour": _s(row.COLOUR),
            "policeno": _s(row.POLICENO),
            "purpose": _s(row.PURPOSE),
            "karoseri": _s(row.KAROSERI),
            "karoseriSupp": _s(row.KAROSERI_SUPP),
            "karoseriName": _s(row.KAROSERI_NM),
            "karoseriAddress": _address(row, "KAROSERI_ADDR", "KAROSERI_CITY"),
            "accessoriesSupp": _s(row.ACCESSORIES_SUPP),
            "accessoriesName": _s(row.ACC_NM),
            "accessoriesAddress": _address(row, "ACC_ADDR", "ACC_CITY"),
            "otherSupp": _s(row.OTHER_SUPP),
            "otherName": _s(row.OTHER_NM),
            "otherAddress": _address(row, "OTHER_ADDR", "OTHER_CITY"),
            "wheels": _s(row.WHEELS),
            "fundPurpose": _s(row.FUND_PURPOSE),
            "finPurpose": _s(row.FIN_PURPOSE),
            "ojkFinGoods": _s(row.OJK_Fin_Goods),
            "ojkFinGoodsDetail": _s(row.OJK_Fin_Goods_Detail),
            "ojkCollGoods": _s(row.OJK_Coll_Goods),
            "ojkCollGoodsDetail": _s(row.OJK_Coll_Goods_Detail),
            "stnkValidDt": _iso(row.STNK_VALIDDT),
            "redCode": _s(row.IsRedCode) == "1",
        })
        equipment["gpsVendor"] = _s(row.GPS_Vendor) if equipment["redCode"] else ""

        if _s(row.PARK_ZIPCODE):
            equipment["parkZipcode"] = _s(row.PARK_ZIPCODE)
        else:
            lessee = db.session.execute(text("""
                SELECT ADDRESS3, ZipCode1, ZipCode3 FROM CAFLESS WITH(NOLOCK)
                WHERE APLESS = :apless
            """), {"apless": apless}).fetchone()
            if lessee:
                equipment["parkZipcode"] = (_s(lessee.ZipCode3) if _s(lessee.ADDRESS3)
                                            else _s(lessee.ZipCode1))

        if row.PARK_LOC is None and row.CITY_PARK is None and row.USERUSAGE is None:
            lessee = db.session.execute(text("""
                SELECT LESSEE_NM, ADDRESS1, ADDRESS3, AREA_CD FROM CAFLESS WITH(NOLOCK)
                WHERE APLESS = :apless
            """), {"apless": apless}).fetchone()
            if lessee:
                equipment["userusage"] = _s(lessee.LESSEE_NM)
                equipment["cityPark"] = _s(lessee.AREA_CD)
                equipment["parkLoc"] = (_s(lessee.ADDRESS3) if _s(lessee.ADDRESS3)
                                        else _s(lessee.ADDRESS1))
        else:
            equipment["parkLoc"] = _s(row.PARK_LOC)
            equipment["cityPark"] = _s(row.CITY_PARK)
            equipment["userusage"] = _s(row.USERUSAGE)
    else:
        equipment["tahun"] = str(date.today().year) if new_car == "2" else ""

    brand = equipment["brand"]
    model = equipment["model"]
    type_code = equipment["type"]

    wheels_required = bool(model) and model in WHEELS_INPUT_MODELS
    if model and not wheels_required:
        equipment["wheels"] = "4"

    show_fin_goods = _show_ojk_fin_goods(purpoffinc, fin_type)
    fin_goods_options = _ojk_fin_goods_options(purpoffinc, fin_type) if show_fin_goods else []
    fin_goods_detail_options, forced_detail = (
        _ojk_fin_goods_detail_initial(purpoffinc, fin_type, brand, type_code, model, condition)
        if show_fin_goods else ([], None)
    )
    if forced_detail:
        equipment["ojkFinGoodsDetail"] = forced_detail
    if not show_fin_goods:
        equipment["ojkFinGoods"] = ""
        equipment["ojkFinGoodsDetail"] = ""

    coll_head, coll_detail, coll_head_value, coll_detail_value = _resolve_coll_goods(
        purpoffinc, fin_type, model, new_car, equipment["ojkCollGoodsDetail"]
    )
    equipment["ojkCollGoods"] = coll_head_value
    equipment["ojkCollGoodsDetail"] = coll_detail_value

    brands = _options(db.session.execute(text("""
        SELECT BRAND AS val, BRAND_NM AS lbl FROM UMFBRAND WITH(NOLOCK)
        WHERE BRAND_NM NOT IN ('CBU', 'All Brand', 'Used Cars', 'Used Trucks')
        ORDER BY BRAND_NM
    """)).fetchall())

    models = _options(db.session.execute(text("""
        SELECT MODEL AS val, MODEL_NM AS lbl FROM UMFMODEL WITH(NOLOCK) ORDER BY MODEL_NM
    """)).fetchall())

    purposes = _options(db.session.execute(text("""
        SELECT Purpose AS val, name AS lbl FROM mstPurpose WITH(NOLOCK) ORDER BY name
    """)).fetchall())

    areas = [
        {"value": _s(r.val), "label": "%s - %s" % (_s(r.propinsi), _s(r.kabupaten))}
        for r in db.session.execute(text("""
            SELECT AREA_CD AS val, Propinsi AS propinsi, Kabupaten AS kabupaten
            FROM UMFAREA WITH(NOLOCK) WHERE FLAG_DEL = 0
            ORDER BY Propinsi, Kabupaten
        """)).fetchall()
    ]

    gps_vendors = _options(db.session.execute(text("""
        SELECT SUPP AS val, NAME AS lbl FROM VENDOR WITH(NOLOCK)
        WHERE Supp_Category = 'GPS' ORDER BY NAME
    """)).fetchall())

    dealer_locked = _dealer_locked(applno)

    return jsonify({
        "equipment": equipment,
        "lookups": {
            "brands": brands,
            "models": models,
            "types": _type_options(brand, model),
            "karoseri": _karoseri_options(model),
            "purposes": purposes,
            "areas": areas,
            "gpsVendors": gps_vendors,
            "dealerTypes": _dealer_type_options(),
            "equipmentTypes": _equipment_type_options(),
            "financingPurposes": _financing_purpose_options(purpoffinc, fin_type),
            "ojkFinGoods": fin_goods_options,
            "ojkFinGoodsDetail": fin_goods_detail_options,
            "ojkCollGood": coll_head,
            "ojkCollGoodDetail": coll_detail,
            "wheelsRequired": wheels_required,
        },
        "showOjkFinGoods": show_fin_goods,
        "ojkFinGoodsRequired": _ojk_fin_goods_required(fin_type),
        "ojkFinGoodsDisabled": _ojk_fin_goods_disabled(purpoffinc, fin_type),
        "showFinancingPurpose": _show_financing_purpose(purpoffinc, fin_type),
        "showFundPurpose": _show_fund_purpose(fin_type),
        "canSearchDealer": (fin_type not in ("S", "D", "M", "W")
                            and conttype_rs != "RS" and not dealer_locked),
        "canSearchSupplier": fin_type != "S" and conttype_rs != "RS",
    })

@cam_edit_bp.route("/equipment/model-options", methods=["GET"])
@login_required
def get_cam_equipment_model_options():
    brand = _s(request.args.get("brand"))
    model = _s(request.args.get("model"))
    new_car = _s(request.args.get("newCar"))
    purpoffinc = _s(request.args.get("purpoffinc"))
    fin_type = _s(request.args.get("finType"))
    stored_detail = _s(request.args.get("ojkCollGoodsDetail"))

    coll_head, coll_detail, _, _ = _resolve_coll_goods(
        purpoffinc, fin_type, model, new_car, stored_detail
    )

    return jsonify({
        "types": _type_options(brand, model),
        "karoseri": _karoseri_options(model),
        "ojkCollGood": coll_head,
        "ojkCollGoodDetail": coll_detail,
        "wheelsRequired": bool(model) and model in WHEELS_INPUT_MODELS,
    })

@cam_edit_bp.route("/equipment/ojk-fin-goods-detail", methods=["GET"])
@login_required
def get_cam_equipment_fin_goods_detail():
    return jsonify(_ojk_fin_goods_detail_options(
        _s(request.args.get("finGood")),
        _s(request.args.get("finType")),
        _s(request.args.get("purpoffinc")),
        _s(request.args.get("brand")),
        _s(request.args.get("type")),
        _s(request.args.get("model")),
        _s(request.args.get("condition")),
    ))

@cam_edit_bp.route("/suppliers", methods=["GET"])
@login_required
def search_cam_suppliers():
    category = _s(request.args.get("category"))
    name = _s(request.args.get("name"))
    new_car = _s(request.args.get("newCar"))
    all_branch = _s(request.args.get("allBranch"))

    if category not in SUPPLIER_CATEGORIES:
        return jsonify({"error": "Unknown supplier category"}), 400

    params = {"name": "%%%s%%" % name}
    branch_sql = ""
    if all_branch != "1":
        params["branch_cd"] = session.get("branchcode", "")
        branch_sql = " AND BRANCH_CD = :branch_cd"

    if category == "dealer":
        where = ("Supp_Type <> 'KR' AND Supp_Type <> 'AC' AND NAME LIKE :name"
                 + branch_sql + " AND isActive = 1")
        
        if new_car == "1":
            where += (" AND Car_Condition IN ('UC', 'NU')"
                      " OR SUPP = '999999'"
                      " AND SUPP NOT IN (SELECT SUPP FROM CLFSUPP_DELETE)"
                      " AND FLGDEL IS NULL")
        elif new_car == "2":
            where += (" AND Car_Condition IN ('NC', 'NU') AND SUPP <> '999999'"
                      " AND SUPP NOT IN (SELECT SUPP FROM CLFSUPP_DELETE)"
                      " AND FLGDEL IS NULL")
    else:
        params["supp_type"] = SUPPLIER_CATEGORIES[category]
        where = "Supp_Type = :supp_type AND NAME LIKE :name" + branch_sql
        if new_car == "2":
            where += " AND SUPP <> '999999'"

    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
        
    try:
        page_size = int(request.args.get("pageSize", SUPPLIER_PAGE_SIZE))
    except (TypeError, ValueError):
        page_size = SUPPLIER_PAGE_SIZE
    page_size = max(1, min(page_size, SUPPLIER_PAGE_SIZE_MAX))

    total_row = db.session.execute(text("""
        SELECT COUNT(*) AS total FROM CLFSUPP WITH(NOLOCK) WHERE %s
    """ % where), params).fetchone()
    total = int(total_row.total) if total_row else 0

    params["row_from"] = (page - 1) * page_size + 1
    params["row_to"] = page * page_size

    rows = db.session.execute(text("""
        SELECT * FROM (
            SELECT ROW_NUMBER() OVER (ORDER BY NAME) AS RowNr,
                   SUPP, NAME, NICKNAME, ADDRESS, PHONE, CONTACT, CITY, Supp_Type
            FROM CLFSUPP WITH(NOLOCK)
            WHERE %s
        ) t
        WHERE RowNr BETWEEN :row_from AND :row_to
        ORDER BY RowNr
    """ % where), params).fetchall()

    return jsonify({
        "items": [{
            "supp": _s(r.SUPP),
            "name": _s(r.NAME),
            "nickname": _s(r.NICKNAME),
            "address": _s(r.ADDRESS),
            "city": _s(r.CITY),
            "phone": _s(r.PHONE),
            "contact": _s(r.CONTACT),
            "suppType": _s(r.Supp_Type),
        } for r in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
    })

@cam_edit_bp.route("/equipment", methods=["POST"])
@login_required
def save_cam_equipment():
    payload = request.get_json(force=True) or {}

    def f(key):
        return _s(payload.get(key))

    apless = f("apless")
    applno = f("applno")
    fin_type = f("finType")
    purpoffinc = f("purpoffinc")
    new_car = f("newCar")

    if not apless or not applno:
        return jsonify({"success": False, "message": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"success": False, "blocked": True, "message": block_message}), 409

    condition = "USED" if new_car == "1" else "NEW" if new_car == "2" else ""

    supp = f("supp")
    brand = f("brand")
    type_code = f("type")
    model = f("model")
    tahun = f("tahun")
    chasis = f("chasis")
    engine = f("engine")
    colour = f("colour")
    policeno = f("policeno")
    userusage = f("userusage")
    purpose = f("purpose")
    karoseri = f("karoseri")
    karoseri_supp = f("karoseriSupp")
    accessories_supp = f("accessoriesSupp")
    other_supp = f("otherSupp")
    park_loc = f("parkLoc")
    park_zipcode = f("parkZipcode")
    city_park = f("cityPark")
    fin_purpose = f("finPurpose")
    fund_purpose = f("fundPurpose")
    stnk_validdt = f("stnkValidDt")
    wheels_raw = f("wheels")
    red_code = "1" if payload.get("redCode") else "0"
    gps_vendor = f("gpsVendor") if red_code == "1" else ""

    clear_karoseri = bool(payload.get("clearKaroseri"))
    clear_accessories = bool(payload.get("clearAccessories"))
    clear_other = bool(payload.get("clearOther"))

    type_cd = TYPE_CD_DEFAULT

    if model not in KAROSERI_MODELS:
        karoseri = ""
    if not _show_financing_purpose(purpoffinc, fin_type):
        fin_purpose = ""
    if not _show_fund_purpose(fin_type):
        fund_purpose = ""

    supp_row = None
    if supp:
        supp_row = db.session.execute(text("""
            SELECT NAME, ADDRESS, CITY, Supp_Type FROM CLFSUPP WITH(NOLOCK)
            WHERE SUPP = :supp
        """), {"supp": supp}).fetchone()
    supp_address = _address(supp_row).strip()

    if model and model not in WHEELS_INPUT_MODELS:
        wheels_raw = "4"
    try:
        wheels = int(wheels_raw) if wheels_raw else 0
    except (TypeError, ValueError):
        wheels = 0

    errors = []
    if not supp and fin_type not in ("S", "D", "M", "W"):
        errors.append("Supplier Name must not empty")
    if supp and not supp_address:
        errors.append("Supplier Address must not empty")
    if not type_cd:
        errors.append("Type of Equipment must not empty")
    if not brand:
        errors.append("Brand must not empty")
    if not type_code:
        errors.append("Type must not empty")
    if not model:
        errors.append("Model must not empty")
    if not tahun:
        errors.append("Year must not empty")
    if not condition:
        errors.append("Condition must not empty")
    if not userusage:
        errors.append("User Usage must not empty")
    if not purpose:
        errors.append("Purpose must not empty")
    if fin_type in ("D", "M", "W") and not fin_purpose:
        errors.append("Financing Purpose must not empty")
    if not park_loc:
        errors.append("Parking Address must not empty")
    if not city_park:
        errors.append("City must not empty")
    if len(park_zipcode) != 5:
        errors.append("Zip Code must not empty or should be 5 characters. Ex.: (11480)")
    if model in WHEELS_VALIDATION_MODELS and not wheels_raw:
        errors.append("the Wheels must not empty")
    if red_code == "1" and not gps_vendor:
        errors.append("Please select GPS Vendor")

    if errors:
        return jsonify({"success": False, "message": "\n".join(errors)})

    if _show_ojk_fin_goods(purpoffinc, fin_type):
        ojk_fin_goods = f("ojkFinGoods")
        ojk_fin_goods_detail = f("ojkFinGoodsDetail")
        if purpoffinc == "5" and fin_type == "I":
            ojk_fin_goods_detail = _consumer_fin_goods_detail(brand, type_code, model, condition)
    else:
        ojk_fin_goods = ""
        ojk_fin_goods_detail = ""

    _, _, ojk_coll_goods, ojk_coll_goods_detail = _resolve_coll_goods(
        purpoffinc, fin_type, model, new_car, f("ojkCollGoodsDetail")
    )

    supp_value = None if fin_type == "S" else (supp or None)
    karoseri_supp_value = None if clear_karoseri else (karoseri_supp or None)
    accessories_supp_value = None if clear_accessories else (accessories_supp or None)
    other_supp_value = None if clear_other else (other_supp or None)
    stnk_value = _as_date(stnk_validdt) if condition == "USED" else None

    tax_free = _tax_free_flag(applno, supp)

    existing = db.session.execute(text("""
        SELECT CAFEQUIP_ID FROM CAFEQUIP WITH(NOLOCK) WHERE APPL_NO = :applno
    """), {"applno": applno}).fetchone()
    cafequip_id = _s(existing.CAFEQUIP_ID) if existing else ""

    common = {
        "applno": applno,
        "supp": supp_value,
        "type_cd": type_cd,
        "brand": brand or None,
        "type_code": type_code or None,
        "model": model or None,
        "tahun": tahun or None,
        "condition": condition,
        "chasis": chasis or None,
        "engine": engine or None,
        "colour": colour or None,
        "policeno": policeno or None,
        "userusage": userusage,
        "purpose": purpose,
        "park_loc": park_loc or None,
        "park_zipcode": park_zipcode,
        "city_park": city_park or None,
        "karoseri": karoseri,
        "karoseri_supp": karoseri_supp_value,
        "accessories_supp": accessories_supp_value,
        "other_supp": other_supp_value,
        "wheels": wheels,
        "tax_free": tax_free,
        "fund_purpose": fund_purpose,
    }

    detail_params = {
        "applno": applno,
        "fin_purpose": fin_purpose,
        "ojk_fin_goods": ojk_fin_goods,
        "ojk_fin_goods_detail": ojk_fin_goods_detail,
        "ojk_coll_goods": ojk_coll_goods,
        "ojk_coll_goods_detail": ojk_coll_goods_detail,
        "red_code": red_code,
        "gps_vendor": gps_vendor,
    }

    try:
        if cafequip_id:
            same_supp = db.session.execute(text("""
                SELECT 1 FROM CAFEQUIP WITH(NOLOCK)
                WHERE APPL_NO = :applno AND SUPP = :supp
            """), {"applno": applno, "supp": supp or None}).fetchone()
            supplier_changed = (not same_supp) and fin_type not in ("S", "D", "M")

            same_brand = db.session.execute(text("""
                SELECT 1 FROM CAFEQUIP WITH(NOLOCK)
                WHERE APPL_NO = :applno AND BRAND = :brand
            """), {"applno": applno, "brand": brand or None}).fetchone()
            brand_changed = not same_brand

            if brand_changed:
                db.session.execute(text("""
                    DELETE FROM CafcontSubsidyDetail
                    WHERE APPL_NO = :applno AND SubsidyType IN ('IA', 'SA', 'RD')
                """), {"applno": applno})
                db.session.execute(text("""
                    UPDATE CAFCONT SET Refund_Supp = 0, Incentive = 0, SUBSIDY = 0
                    WHERE APPL_NO = :applno
                """), {"applno": applno})

            if supplier_changed:
                db.session.execute(text("""
                    DELETE FROM CAFDISBACC WHERE APPL_NO = :applno
                """), {"applno": applno})

            for flag, split in ((clear_karoseri, "Karoseri"),
                                (clear_accessories, "Accessories"),
                                (clear_other, "Other")):
                if flag:
                    db.session.execute(text("""
                        DELETE FROM CAFDISBACC WHERE APPL_NO = :applno AND Split = :split
                    """), {"applno": applno, "split": split})

            stnk_sql = "STNK_VALIDDT = :stnk_validdt," if condition == "USED" else ""
            params = dict(common, cafequip_id=cafequip_id)
            if condition == "USED":
                params["stnk_validdt"] = stnk_value

            db.session.execute(text("""
                UPDATE CAFEQUIP SET
                    SUPP = :supp,
                    TYPE_CD = :type_cd,
                    BRAND = :brand,
                    [TYPE] = :type_code,
                    MODEL = :model,
                    TAHUN = :tahun,
                    CONDITION = :condition,
                    CHASIS = :chasis,
                    ENGINE = :engine,
                    COLOUR = :colour,
                    POLICENO = :policeno,
                    USERUSAGE = :userusage,
                    PURPOSE = :purpose,
                    PARK_LOC = REPLACE(REPLACE(:park_loc, CHAR(13), ' '), CHAR(10), ' '),
                    PARK_ZIPCODE = NULLIF(LTRIM(RTRIM(:park_zipcode)), ''),
                    CITY_PARK = :city_park,
                    KAROSERI = NULLIF(:karoseri, ''),
                    %s
                    KAROSERI_SUPP = :karoseri_supp,
                    ACCESSORIES_SUPP = :accessories_supp,
                    OTHER_SUPP = :other_supp,
                    WHEELS = :wheels,
                    TAX_FREE = :tax_free,
                    FUND_PURPOSE = :fund_purpose
                WHERE APPL_NO = :applno AND CAFEQUIP_ID = :cafequip_id
            """ % stnk_sql), params)

            detail_exists = db.session.execute(text("""
                SELECT 1 FROM Cafequip_Detail WITH(NOLOCK) WHERE CAFEQUIP_ID = :cafequip_id
            """), {"cafequip_id": cafequip_id}).fetchone()

        else:
            number = db.session.execute(text("""
                SELECT NextNumber FROM TANUMBER WITH (UPDLOCK, HOLDLOCK)
                WHERE PropertyGroupName = 'CAFEQUIP_ID'
            """)).fetchone()
            if not number or number.NextNumber is None:
                db.session.rollback()
                return jsonify({"success": False,
                                "message": "CAFEQUIP_ID sequence is not configured."}), 500

            cafequip_id = _s(number.NextNumber)

            stnk_column = "STNK_VALIDDT," if condition == "USED" else ""
            stnk_param = ":stnk_validdt," if condition == "USED" else ""
            params = dict(common, cafequip_id=cafequip_id)
            if condition == "USED":
                params["stnk_validdt"] = stnk_value

            db.session.execute(text("""
                INSERT INTO CAFEQUIP (
                    CAFEQUIP_ID, APPL_NO, SUPP, TYPE_CD, BRAND, [TYPE], MODEL, TAHUN,
                    CONDITION, CHASIS, ENGINE, COLOUR, POLICENO, USERUSAGE, PURPOSE,
                    PARK_LOC, PARK_ZIPCODE, CITY_PARK, KAROSERI, %s
                    KAROSERI_SUPP, TAX_FREE, ACCESSORIES_SUPP, OTHER_SUPP, WHEELS, FUND_PURPOSE
                ) VALUES (
                    :cafequip_id, :applno, :supp, :type_cd, :brand, :type_code, :model, :tahun,
                    :condition, :chasis, :engine, :colour, :policeno, :userusage, :purpose,
                    REPLACE(REPLACE(:park_loc, CHAR(13), ' '), CHAR(10), ' '),
                    NULLIF(LTRIM(RTRIM(:park_zipcode)), ''), :city_park, NULLIF(:karoseri, ''), %s
                    :karoseri_supp, :tax_free, :accessories_supp, :other_supp, :wheels, :fund_purpose
                )
            """ % (stnk_column, stnk_param)), params)

            db.session.execute(text("""
                UPDATE TANUMBER SET NextNumber = :next_number, LastUpdate = SYSDATETIME()
                WHERE PropertyGroupName = 'CAFEQUIP_ID'
            """), {"next_number": str(int(cafequip_id) + 1)})

            detail_exists = db.session.execute(text("""
                SELECT 1 FROM Cafequip_Detail WITH(NOLOCK) WHERE APPL_NO = :applno
            """), {"applno": applno}).fetchone()

        if detail_exists:
            db.session.execute(text("""
                UPDATE Cafequip_Detail SET
                    FIN_PURPOSE = :fin_purpose,
                    OJK_Fin_Goods = NULLIF(:ojk_fin_goods, ''),
                    OJK_Fin_Goods_Detail = NULLIF(:ojk_fin_goods_detail, ''),
                    OJK_Coll_Goods = NULLIF(:ojk_coll_goods, ''),
                    OJK_Coll_Goods_Detail = NULLIF(:ojk_coll_goods_detail, ''),
                    IsRedCode = :red_code,
                    GPS_Vendor = :gps_vendor
                WHERE APPL_NO = :applno AND CAFEQUIP_ID = :cafequip_id
            """), dict(detail_params, cafequip_id=cafequip_id))
        else:
            db.session.execute(text("""
                INSERT INTO Cafequip_Detail (
                    Cafequip_ID, APPL_NO, FIN_PURPOSE, OJK_Fin_Goods, OJK_Fin_Goods_Detail,
                    OJK_Coll_Goods, OJK_Coll_Goods_Detail, IsRedCode, GPS_Vendor
                ) VALUES (
                    :cafequip_id, :applno, :fin_purpose,
                    NULLIF(:ojk_fin_goods, ''), NULLIF(:ojk_fin_goods_detail, ''),
                    NULLIF(:ojk_coll_goods, ''), NULLIF(:ojk_coll_goods_detail, ''),
                    :red_code, :gps_vendor
                )
            """), dict(detail_params, cafequip_id=cafequip_id))

        db.session.execute(
            text("EXEC USP_AUTO_DEVIATION :flag, :apless, :applno"),
            {"flag": "2" if condition == "NEW" else "3", "apless": apless, "applno": applno},
        )

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to save CAM equipment for applno=%s", applno)
        return jsonify({"success": False, "message": "Save failed. Please try again."}), 500

    return jsonify({
        "success": True,
        "apless": apless,
        "applno": applno,
        "c2c": "1" if supp == "999999" else "0",
    })

NOT_FAMILY_CODES = {"40", "50"}
LEASING_COMPANY_NORMALIZED = "MITSUILEASINGCAPITALINDONESIAPT"
FDC_AREA_CODE = "07"

def _normalize_name(value):
    return (value or "").strip().upper()

def _compute_id_fams(fin_type, bpkb_an_tp, names_match, id_fam):
    if fin_type == "F":
        return "Not Family"
    if bpkb_an_tp != "PR":
        return "Not Family"
    if names_match:
        return "Not Family"
    if not id_fam:
        return ""
    return "Not Family" if id_fam in NOT_FAMILY_CODES else "Family"

def _to_iso_date(value):
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d")

def _from_iso_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None

def _fetch_bpkb_name_types():
    rows = db.session.execute(text(
        "SELECT Grnttp, Name FROM MSTTYPE WITH(NOLOCK) ORDER BY Name"
    )).fetchall()
    return [{"value": r.Grnttp, "label": r.Name} for r in rows]

def _fetch_family_statuses():
    rows = db.session.execute(text(
        "SELECT ID_FAM, DESKRIPSI FROM MSTFAMSTATUS WITH(NOLOCK) ORDER BY DESKRIPSI"
    )).fetchall()
    return [{"value": r.ID_FAM, "label": r.DESKRIPSI} for r in rows]

def _fetch_marital_statuses():
    rows = db.session.execute(text(
        "SELECT Marital, name FROM MSTMARITAL WITH(NOLOCK) WHERE Marital IN ('M', 'S') ORDER BY name"
    )).fetchall()
    return [{"value": r.Marital, "label": r.name} for r in rows]

def _fetch_spouse_statuses():
    rows = db.session.execute(text(
        "SELECT [value], DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE = 'SPOUSE_STATUS' ORDER BY DESC_VALUE"
    )).fetchall()
    return [{"value": r.value, "label": r.DESC_VALUE} for r in rows]

def _fetch_attorney_occupations():
    rows = db.session.execute(text(
        "SELECT code, name FROM mstBoardMitsui WITH(NOLOCK) ORDER BY name"
    )).fetchall()
    return [{"value": r.code, "label": r.name} for r in rows]

def _fetch_notaries():
    rows = db.session.execute(text("""
        SELECT Notary_no, Notary_nm, NPWP_No, NPWP_addrs
        FROM UMFNOTARY WITH(NOLOCK) WHERE Flgdel = '0' ORDER BY Notary_nm
    """)).fetchall()
    return [
        {"value": r.Notary_no, "label": r.Notary_nm, "npwpNo": r.NPWP_No or "", "npwpAddrs": r.NPWP_addrs or ""}
        for r in rows
    ]

FAMILY_STATUS_FIN_TYPES = ("S", "I", "M", "D", "W")

@cam_edit_bp.route("/bpkb", methods=["GET"])
@login_required
def get_bpkb():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    if not apless or not applno:
        return jsonify({"error": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"blocked": True, "message": block_message}), 409

    equip = db.session.execute(text("""
        SELECT CAFEQUIP_ID, CONDITION, BPKB_NO, BPKB_AN_TP, BPKB_AN, Relation,
               BPKB_ADDR, CITY_BPKB, BPKB_AREA_CD, BPKB_AN_STS, CANCEL_ORDER,
               ADD_COLLATERAL, BPKB_PLACEBIRTH, BPKB_TGLBIRTH
        FROM CAFEQUIP WITH(NOLOCK) WHERE APPL_NO = :applno
    """), {"applno": applno}).fetchone()

    lessee = db.session.execute(text("""
        SELECT LESSEE_NM, LESSEE_TP, ADDRESS1, CITY1, ADDRESS2, CITY2,
               PLACEBIRTH, TGLBIRTH, AREA_CD
        FROM CAFLESS WITH(NOLOCK) WHERE APLESS = :apless
    """), {"apless": apless}).fetchone()
    lessee_name = (lessee.LESSEE_NM if lessee else "") or ""
    lessee_tp = ((lessee.LESSEE_TP if lessee else "") or "").strip()

    cont = db.session.execute(text("""
        SELECT Notary_no FROM CAFCONT WITH(NOLOCK) WHERE APPL_NO = :applno AND APLESS = :apless
    """), {"applno": applno, "apless": apless}).fetchone()
    notary_no = ((cont.Notary_no if cont else "") or "").strip()

    notary_npwp = None
    if notary_no:
        notary_npwp = db.session.execute(text("""
            SELECT NPWP_No, NPWP_addrs FROM UMFNOTARY WITH(NOLOCK) WHERE Notary_no = :notary_no
        """), {"notary_no": notary_no}).fetchone()

    if equip is None:
        cafequip_id = None
        car_condition = ""
        cancel_order = False
        add_collateral = False
        has_bpkb_record = False
    else:
        cafequip_id = equip.CAFEQUIP_ID
        car_condition = (equip.CONDITION or "").strip().upper()
        cancel_order = (equip.CANCEL_ORDER or "").strip() == "1"
        add_collateral = (equip.ADD_COLLATERAL or "").strip() == "1"
        has_bpkb_record = bool((equip.BPKB_AN or "").strip())

    if has_bpkb_record:
        bpkb_no = equip.BPKB_NO or ""
        bpkb_an_tp = (equip.BPKB_AN_TP or "").strip()
        bpkb_an = equip.BPKB_AN or ""
        relation = equip.Relation or ""
        bpkb_addr = equip.BPKB_ADDR or ""
        area_cd = (equip.BPKB_AREA_CD or "").strip()
        city_bpkb = equip.CITY_BPKB or ""
        id_fam = (equip.BPKB_AN_STS or "").strip()
        names_match = bpkb_an != "" and _normalize_name(bpkb_an) == _normalize_name(lessee_name)
        if names_match and lessee:
            placebirth = lessee.PLACEBIRTH or ""
            tglbirth = _to_iso_date(lessee.TGLBIRTH)
        else:
            placebirth = equip.BPKB_PLACEBIRTH or ""
            tglbirth = _to_iso_date(equip.BPKB_TGLBIRTH)
    else:
        bpkb_no = ""
        bpkb_an_tp = lessee_tp
        bpkb_an = lessee_name
        relation = ""
        area_cd = ((lessee.AREA_CD if lessee else "") or "").strip()
        id_fam = ""
        placebirth = (lessee.PLACEBIRTH if lessee else "") or ""
        tglbirth = _to_iso_date(lessee.TGLBIRTH if lessee else None)
        if bpkb_an_tp == "PR":
            bpkb_addr = (lessee.ADDRESS1 if lessee else "") or ""
            city_bpkb = (lessee.CITY1 if lessee else "") or ""
        elif bpkb_an_tp == "PT":
            bpkb_addr = (lessee.ADDRESS2 if lessee else "") or ""
            city_bpkb = (lessee.CITY2 if lessee else "") or ""
        else:
            bpkb_addr = ""
            city_bpkb = ""

    status_rows = db.session.execute(text("""
        SELECT Id, bpkb_marital_status, BPKB_SPOUSE_NAME, BPKB_SPOUSE_ADDRESS,
               BPKB_SPOUSE_STATUS, POA_NAME, POA_OCCUPATION, POA_ADDRESS
        FROM CAFEQUIP_BPKBSTATUS WITH(NOLOCK)
        WHERE APPL_NO = :applno
        ORDER BY Id
    """), {"applno": applno}).fetchall()

    detail = {"maritalStatus": "-", "spouseName": "", "spouseStatus": "-", "spouseAddress": "", "attorneys": []}
    for row in status_rows:
        if row.bpkb_marital_status or row.BPKB_SPOUSE_NAME:
            detail["maritalStatus"] = row.bpkb_marital_status or "-"
            detail["spouseName"] = row.BPKB_SPOUSE_NAME or ""
            detail["spouseStatus"] = row.BPKB_SPOUSE_STATUS or "-"
            detail["spouseAddress"] = row.BPKB_SPOUSE_ADDRESS or ""
        elif row.POA_NAME:
            detail["attorneys"].append({
                "name": row.POA_NAME or "",
                "occupation": (row.POA_OCCUPATION or "").strip(),
                "address": row.POA_ADDRESS or "",
            })

    return jsonify({
        "apless": apless,
        "applno": applno,
        "cafequipId": cafequip_id,
        "lesseeName": lessee_name,
        "lesseeTp": lessee_tp,
        "carCondition": car_condition,
        "bpkb": {
            "bpkbNo": bpkb_no,
            "bpkbAnTp": bpkb_an_tp,
            "bpkbAn": bpkb_an,
            "relation": relation,
            "bpkbAddr": bpkb_addr,
            "areaCd": area_cd,
            "cityBpkb": city_bpkb,
            "idFam": id_fam,
            "placebirth": placebirth,
            "tglbirth": tglbirth,
            "cancelOrder": cancel_order,
            "addCollateral": add_collateral,
        },
        "detail": detail,
        "notary": {
            "notaryNo": notary_no,
            "npwpNo": (notary_npwp.NPWP_No if notary_npwp else "") or "",
            "npwpAddrs": (notary_npwp.NPWP_addrs if notary_npwp else "") or "",
        },
        "lookups": {
            "bpkbNameTypes": _fetch_bpkb_name_types(),
            "familyStatuses": _fetch_family_statuses(),
            "maritalStatuses": _fetch_marital_statuses(),
            "spouseStatuses": _fetch_spouse_statuses(),
            "attorneyOccupations": _fetch_attorney_occupations(),
            "notaries": _fetch_notaries(),
        },
    })

def _validate_bpkb(fin_type, names_match, is_company_itself, id_fams, new_car, payload):
    errors = []
    bpkb_an_tp = payload.get("bpkbAnTp") or ""
    bpkb_an = (payload.get("bpkbAn") or "").strip()
    bpkb_addr = (payload.get("bpkbAddr") or "").strip()
    city_bpkb = (payload.get("cityBpkb") or "").strip()
    area_cd = payload.get("areaCd") or ""
    notary_no = (payload.get("notaryNo") or "").strip()
    relation = (payload.get("relation") or "").strip()

    if not bpkb_an_tp:
        errors.append("BPKB Name Type must not be blank")
    if not bpkb_an:
        errors.append("BPKB Name must not be blank")
    if not bpkb_addr:
        errors.append("BPKB Address must not be blank")
    if not city_bpkb:
        errors.append("City must not be blank")
    if not area_cd and fin_type != "W":
        errors.append("Area must not be blank")
    if fin_type not in ("S", "F", "W") and not notary_no:
        errors.append("Notary must not be blank")
    if not id_fams:
        errors.append("Family Status must not be blank")
    if not names_match and not is_company_itself and fin_type != "F" and not relation:
        errors.append("Relationship with Customer must not be blank")

    detail_trigger = bool(bpkb_an_tp) and not names_match and new_car == "2" and id_fams == "Not Family"
    if detail_trigger:
        detail = payload.get("detail") or {}
        if bpkb_an_tp == "PR":
            marital = detail.get("maritalStatus") or "-"
            if marital == "-":
                errors.append("You have to choose BPKB Name Marital Status first")
            elif marital == "M":
                if not (detail.get("spouseAddress") or "").strip():
                    errors.append("Spouse BPKB Address must not be empty")
                if not (detail.get("spouseName") or "").strip():
                    errors.append("Spouse BPKB Name must not be empty")
                if (detail.get("spouseStatus") or "-") == "-":
                    errors.append("Spouse BPKB Status must not be empty")
        else:
            attorneys = detail.get("attorneys") or []
            if not attorneys:
                errors.append("At least one Power of Attorney signer is required")
            for idx, attorney in enumerate(attorneys, start=1):
                if not (attorney.get("name") or "").strip():
                    errors.append(f"POA name {idx} is empty")
                if not (attorney.get("occupation") or "").strip():
                    errors.append(f"POA Occupation {idx} is empty")
                if not (attorney.get("address") or "").strip():
                    errors.append(f"POA Address {idx} is empty")

    return errors

@cam_edit_bp.route("/bpkb", methods=["POST"])
@login_required
def save_bpkb():
    payload = request.get_json(force=True) or {}
    apless = (payload.get("apless") or "").strip()
    applno = (payload.get("applno") or "").strip()
    new_car = (payload.get("newCar") or "").strip()
    if not apless or not applno:
        return jsonify({"success": False, "message": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"success": False, "blocked": True, "message": block_message}), 409

    cont = db.session.execute(text("""
        SELECT Cons_Leas, Notary_no FROM CAFCONT WITH(NOLOCK) WHERE APPL_NO = :applno AND APLESS = :apless
    """), {"applno": applno, "apless": apless}).fetchone()
    if not cont:
        return jsonify({"success": False, "message": "Application not found"}), 404
    fin_type = (cont.Cons_Leas or "").strip()
    existing_notary_no = (cont.Notary_no or "").strip()

    equip = db.session.execute(text("""
        SELECT CAFEQUIP_ID, CONDITION FROM CAFEQUIP WITH(NOLOCK) WHERE APPL_NO = :applno
    """), {"applno": applno}).fetchone()
    if not equip:
        return jsonify({"success": False, "message": "Equipment record not found. Please save the Equipment tab before entering BPKB details."}), 404
    cafequip_id = equip.CAFEQUIP_ID
    car_condition = (equip.CONDITION or "").strip().upper()

    lessee = db.session.execute(text("""
        SELECT LESSEE_NM, PLACEBIRTH, TGLBIRTH FROM CAFLESS WITH(NOLOCK) WHERE APLESS = :apless
    """), {"apless": apless}).fetchone()
    lessee_name = (lessee.LESSEE_NM if lessee else "") or ""
    lessee_placebirth = (lessee.PLACEBIRTH if lessee else "") or ""
    lessee_birthdate = lessee.TGLBIRTH if lessee else None

    bpkb_an = (payload.get("bpkbAn") or "").strip()
    bpkb_an_tp = payload.get("bpkbAnTp") or ""
    names_match = _normalize_name(bpkb_an) != "" and _normalize_name(bpkb_an) == _normalize_name(lessee_name)
    is_company_itself = _normalize_name(bpkb_an).replace(" ", "") == LEASING_COMPANY_NORMALIZED
    id_fam = payload.get("idFam") or ""
    id_fams = _compute_id_fams(fin_type, bpkb_an_tp, names_match, id_fam)

    errors = _validate_bpkb(fin_type, names_match, is_company_itself, id_fams, new_car, payload)
    if errors:
        return jsonify({"success": False, "errors": errors})

    if names_match and bpkb_an_tp == "PR" and fin_type != "F":
        placebirth = lessee_placebirth
        id_fam = ""
    else:
        placebirth = (payload.get("placebirth") or "").strip()

    submitted_tglbirth = _from_iso_date(payload.get("tglbirth"))
    bpkb_tglbirth = lessee_birthdate if names_match else submitted_tglbirth

    skip_cafdev_cleanup = (
        fin_type == "I" and car_condition == "NEW" and id_fams == "Not Family" and not names_match
    )

    warning = None
    try:
        db.session.execute(text("""
            UPDATE CAFEQUIP SET
                BPKB_NO = :bpkb_no, BPKB_AN_TP = :bpkb_an_tp, BPKB_AN = :bpkb_an,
                Relation = :relation, BPKB_ADDR = :bpkb_addr, CITY_BPKB = :city_bpkb,
                Fdc_Area = :fdc_area, BPKB_AREA_CD = :area_cd, BPKB_AN_STS = :id_fam,
                BPKB_AN_FAM = :id_fams, CANCEL_ORDER = :cancel_order,
                BPKB_PLACEBIRTH = :placebirth, BPKB_TGLBIRTH = :tglbirth,
                ADD_COLLATERAL = :add_collateral
            WHERE APPL_NO = :applno AND CAFEQUIP_ID = :cafequip_id
        """), {
            "bpkb_no": (payload.get("bpkbNo") or "").strip() or None,
            "bpkb_an_tp": bpkb_an_tp or None,
            "bpkb_an": bpkb_an or None,
            "relation": (payload.get("relation") or "").strip() or None,
            "bpkb_addr": (payload.get("bpkbAddr") or "").strip() or None,
            "city_bpkb": (payload.get("cityBpkb") or "").strip() or None,
            "fdc_area": FDC_AREA_CODE,
            "area_cd": payload.get("areaCd") or None,
            "id_fam": id_fam or None,
            "id_fams": id_fams or None,
            "cancel_order": "1" if payload.get("cancelOrder") else None,
            "placebirth": placebirth or None,
            "tglbirth": bpkb_tglbirth,
            "add_collateral": "1" if payload.get("addCollateral") else None,
            "applno": applno,
            "cafequip_id": cafequip_id,
        })

        if car_condition == "NEW" and not skip_cafdev_cleanup:
            db.session.execute(text("""
                DELETE FROM CAFDEV WHERE APPL_NO = :applno AND LEFT(DEVIATION_CD, 1) = '3'
            """), {"applno": applno})

        db.session.execute(text("DELETE FROM CAFEQUIP_BPKBSTATUS WHERE APPL_NO = :applno"), {"applno": applno})
        detail = payload.get("detail") or {}
        if bpkb_an_tp == "PR":
            db.session.execute(text("""
                INSERT INTO CAFEQUIP_BPKBSTATUS (APPL_NO, Id, bpkb_marital_status, BPKB_SPOUSE_NAME, BPKB_SPOUSE_ADDRESS, BPKB_SPOUSE_STATUS)
                VALUES (:applno, '1', :marital, :spouse_name, :spouse_addr, :spouse_status)
            """), {
                "applno": applno,
                "marital": detail.get("maritalStatus") or None,
                "spouse_name": (detail.get("spouseName") or "").strip() or None,
                "spouse_addr": (detail.get("spouseAddress") or "").strip() or None,
                "spouse_status": detail.get("spouseStatus") or None,
            })
        else:
            for idx, attorney in enumerate(detail.get("attorneys") or [], start=1):
                db.session.execute(text("""
                    INSERT INTO CAFEQUIP_BPKBSTATUS (appl_no, id, POA_NAME, POA_OCCUPATION, POA_ADDRESS)
                    VALUES (:applno, :idx, :name, :occupation, :address)
                """), {
                    "applno": applno,
                    "idx": str(idx),
                    "name": (attorney.get("name") or "").strip() or None,
                    "occupation": attorney.get("occupation") or None,
                    "address": (attorney.get("address") or "").strip() or None,
                })

        submitted_notary_no = (payload.get("notaryNo") or "").strip()
        if fin_type != "F":
            if submitted_notary_no == "":
                db.session.execute(text("""
                    UPDATE CAFCONT SET Notary_no = NULL, Fiduciary = NULL, Notary = NULL, gross = NULL
                    WHERE APPL_NO = :applno AND APLESS = :apless
                """), {"applno": applno, "apless": apless})
            else:
                db.session.execute(text("""
                    UPDATE CAFCONT SET Notary_no = :notary_no WHERE APPL_NO = :applno AND APLESS = :apless
                """), {"notary_no": submitted_notary_no, "applno": applno, "apless": apless})
            if submitted_notary_no != existing_notary_no:
                warning = "Please re-calculate the financing, insurance and disbursement instantly."
        elif submitted_notary_no == "":
            db.session.execute(text("""
                UPDATE CAFCONT SET Notary_no = NULL, Fiduciary = NULL, Notary = NULL, gross = NULL
                WHERE APPL_NO = :applno AND APLESS = :apless
            """), {"applno": applno, "apless": apless})
            if existing_notary_no != "":
                warning = "Please re-calculate the financing, insurance and disbursement instantly."

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to save BPKB for applno=%s", applno)
        return jsonify({"success": False, "message": "Save failed. Please try again."}), 500

    response = {"success": True, "apless": apless, "applno": applno}
    if warning:
        response["warning"] = warning
    return jsonify(response)

@cam_edit_bp.route("/bpkb/reset-name", methods=["POST"])
@login_required
def reset_bpkb_name():
    payload = request.get_json(force=True) or {}
    apless = (payload.get("apless") or "").strip()
    applno = (payload.get("applno") or "").strip()
    if not apless or not applno:
        return jsonify({"success": False, "message": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"success": False, "message": block_message}), 409

    equip = db.session.execute(text("""
        SELECT CAFEQUIP_ID FROM CAFEQUIP WITH(NOLOCK) WHERE APPL_NO = :applno
    """), {"applno": applno}).fetchone()
    if not equip:
        return jsonify({"success": False, "message": "Equipment record not found. Please save the Equipment tab before entering BPKB details."}), 404

    try:
        db.session.execute(text("""
            UPDATE CAFEQUIP SET BPKB_AN = NULL, BPKB_ADDR = NULL, CITY_BPKB = NULL
            WHERE APPL_NO = :applno AND CAFEQUIP_ID = :cafequip_id
        """), {"applno": applno, "cafequip_id": equip.CAFEQUIP_ID})
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to reset BPKB name for applno=%s", applno)
        return jsonify({"success": False, "message": "Reset failed. Please try again."}), 500

    return jsonify({"success": True})

def _load_survey_file_row(file_id):
    return db.session.execute(text("""
        SELECT Id, ApplNo, Apless, AWSKey, DocumentName
        FROM SURVEY_FILE WITH(NOLOCK)
        WHERE Id = :id AND SurveyType = :survey_type
    """), {"id": file_id, "survey_type": SURVEY_TYPE}).fetchone()

def _stream_survey_file(file_id, as_attachment):
    row = _load_survey_file_row(file_id)
    if not row:
        return jsonify({"success": False, "message": "File not found"}), 404

    if boto3 is None:
        current_app.logger.error("boto3 is not installed; cannot read survey files.")
        return jsonify({"success": False, "message": "File storage is not configured on this server."}), 500

    try:
        obj = _s3_client().get_object(Bucket=_s3_bucket(), Key=row.AWSKey)
        body = obj["Body"].read()
    except Exception:
        current_app.logger.exception("Failed to read S3 object %s", row.AWSKey)
        return jsonify({"success": False, "message": "Could not read the file from storage."}), 502

    filename = (row.DocumentName or "").strip() or os.path.basename(row.AWSKey) or f"survey-{file_id}"
    mimetype = obj.get("ContentType") or mimetypes.guess_type(filename)[0] or "application/octet-stream"

    return send_file(
        BytesIO(body),
        mimetype=mimetype,
        as_attachment=as_attachment,
        download_name=filename,
        max_age=0,
    )

@cam_edit_bp.route("/eq-survey-file/view/<int:file_id>", methods=["GET"])
@login_required
def view_eq_survey_file(file_id):
    return _stream_survey_file(file_id, as_attachment=False)

@cam_edit_bp.route("/eq-survey-file/download/<int:file_id>", methods=["GET"])
@login_required
def download_eq_survey_file(file_id):
    return _stream_survey_file(file_id, as_attachment=True)

SURVEY_TYPE = "vehicle-survey"

CATEGORY_CONFIG = {
    "front-photo": {"document_type": "vehicle-photo-front", "tag": "VEHICLE_PHOTO_FRONT", "subfolder": "VEHICLE_PHOTO", "single": True},
    "vehicle-photo": {"document_type": "vehicle-photo", "tag": "VEHICLE_PHOTO", "subfolder": "VEHICLE_PHOTO", "single": False},
    "data-bpkb": {"document_type": "vehicle-data-bpkb", "tag": "VEHICLE_DATA_BPKB", "subfolder": "VEHICLE_DATA", "single": True},
    "vehicle-data": {"document_type": "vehicle-data", "tag": "VEHICLE_DATA", "subfolder": "VEHICLE_DATA", "single": False},
}

CATEGORY_RESPONSE_KEY = {
    "front-photo": "frontPhoto",
    "vehicle-photo": "vehiclePhoto",
    "data-bpkb": "dataBpkb",
    "vehicle-data": "vehicleData",
}

ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/pjpeg", "image/x-png", "image/png", "image/gif",
    "image/bmp", "image/heic", "image/heif", "application/download",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

_SPACE_VARIANTS = [" ", "\u00a0", "\u2002", "\u2003", "\u2009", "\u200b", "\u2007", "\u3000"]
_STRIPPED_CHARS = "&$@=;:/+,?%"

def _download_url(key, expires_in=3600):
    content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
    return _s3_client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": _s3_bucket(),
            "Key": key,
            "ResponseContentType": content_type,
        },
        ExpiresIn=3600,
    )

def _sanitize_filename(original_name: str) -> str:
    result = original_name or "file"
    for ch in _STRIPPED_CHARS:
        result = result.replace(ch, "")
    for ch in _SPACE_VARIANTS:
        result = result.replace(ch, "_")
    return result

def _build_document_name(applno: str, tag: str, sequence: int, original_filename: str) -> str:
    return f"{applno}-{tag}-{sequence}-{_sanitize_filename(original_filename)}"

def _build_s3_key(apless: str, applno: str, subfolder: str, document_name: str) -> str:
    return f"upload_doc/{apless}/{applno}/{subfolder}/{document_name}"

def _validate_cam_file(content_type: str, file_size: int, max_file_size_mb: int = 2) -> str:
    if content_type not in ALLOWED_MIME_TYPES:
        return "Invalid uploaded file format."
    effective_max_mb = None if content_type == "application/pdf" else max_file_size_mb
    if effective_max_mb is not None and file_size > effective_max_mb * 1024 * 1024:
        return f"File size exceeded maximum allowed file size ({effective_max_mb}MB)."
    return ""

def _file_size(file_storage) -> int:
    stream = file_storage.stream
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(0)
    return size

def _upload_one_survey_document(applno, apless, survey_type, document_type, subfolder, tag, sequence, file_storage, username):
    error = _validate_cam_file(file_storage.mimetype, _file_size(file_storage))
    if error:
        return error, None

    document_name = _build_document_name(applno, tag, sequence, file_storage.filename)
    aws_key = _build_s3_key(apless, applno, subfolder, document_name)

    content_type = file_storage.mimetype or mimetypes.guess_type(file_storage.filename)[0] or "application/octet-stream"
    _s3_client().upload_fileobj(
        file_storage, _s3_bucket(), aws_key,
        ExtraArgs={"ContentType": content_type},
    )

    db.session.execute(text("""
        INSERT INTO SURVEY_FILE
            (ApplNo, Apless, DocumentType, DocumentName, AWSKey, CreatedBy, CreatedDate, UpdatedBy, UpdatedDate, SurveyType)
        VALUES
            (:applno, :apless, :doc_type, :doc_name, :aws_key, :username, GETDATE(), :username, GETDATE(), :survey_type)
    """), {
        "applno": applno, "apless": apless, "doc_type": document_type, "doc_name": document_name,
        "aws_key": aws_key, "username": username, "survey_type": survey_type,
    })

    return "", aws_key

def _replace_single_survey_document(applno, apless, document_type, subfolder, tag, file_storage, username):
    error, new_key = _upload_one_survey_document(
        applno, apless, SURVEY_TYPE, document_type, subfolder, tag, 1, file_storage, username
    )
    if error:
        return error

    existing = db.session.execute(text("""
        SELECT Id, AWSKey FROM SURVEY_FILE WITH(NOLOCK)
        WHERE Apless = :apless AND ApplNo = :applno AND DocumentType = :doc_type AND AWSKey != :new_key
    """), {"apless": apless, "applno": applno, "doc_type": document_type, "new_key": new_key}).fetchall()

    for old in existing:
        try:
            _s3_client().delete_object(Bucket=_s3_bucket(), Key=old.AWSKey)
        except Exception:
            current_app.logger.exception("Failed to delete S3 object %s while replacing it", old.AWSKey)
        db.session.execute(text("DELETE FROM SURVEY_FILE WHERE Id = :id"), {"id": old.Id})

    return ""

def _add_survey_documents(applno, apless, document_type, subfolder, tag, file_storages, username):
    existing_count = db.session.execute(text("""
        SELECT COUNT(1) AS c FROM SURVEY_FILE WITH(NOLOCK)
        WHERE Apless = :apless AND ApplNo = :applno AND DocumentType = :doc_type
    """), {"apless": apless, "applno": applno, "doc_type": document_type}).fetchone().c

    for i, file_storage in enumerate(file_storages):
        error, _ = _upload_one_survey_document(
            applno, apless, SURVEY_TYPE, document_type, subfolder, tag, existing_count + i + 1, file_storage, username
        )
        if error:
            return error
    return ""

def _fetch_files(applno, apless):
    rows = db.session.execute(text("""
        SELECT Id, DocumentName, AWSKey, DocumentType
        FROM SURVEY_FILE WITH(NOLOCK)
        WHERE Apless = :apless AND ApplNo = :applno AND SurveyType = :survey_type
        ORDER BY DocumentType, CreatedDate
    """), {"apless": apless, "applno": applno, "survey_type": SURVEY_TYPE}).fetchall()

    doc_type_to_response_key = {cfg["document_type"]: CATEGORY_RESPONSE_KEY[cat] for cat, cfg in CATEGORY_CONFIG.items()}
    grouped = {key: [] for key in CATEGORY_RESPONSE_KEY.values()}
    for row in rows:
        response_key = doc_type_to_response_key.get(row.DocumentType)
        if not response_key:
            continue
        grouped[response_key].append({
            "id": row.Id,
            "documentName": row.DocumentName,
            "downloadUrl": _download_url(row.AWSKey),
        })
    return grouped

def _compute_age(birthdate, as_of):
    if not birthdate or not as_of:
        return None
    years = as_of.year - birthdate.year
    if (as_of.month, as_of.day) < (birthdate.month, birthdate.day):
        years -= 1
    return years if years >= 0 else None

def _or_dash(value):
    return value if value not in (None, "") else "-"

@cam_edit_bp.route("/eq-survey-file", methods=["GET"])
@login_required
def get_eq_survey_file():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    status = request.args.get("status", "")
    if not apless or not applno:
        return jsonify({"error": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"blocked": True, "message": block_message}), 409

    cont = db.session.execute(text("""
        SELECT ContSts FROM CAFCONT WITH(NOLOCK) WHERE APPL_NO = :applno
    """), {"applno": applno}).fetchone()
    cont_sts = cont.ContSts if cont else None
    if cont_sts is None:
        contract_status = "-"
    elif cont_sts == "N":
        contract_status = "NEW"
    else:
        contract_status = "REPEAT"

    lessee = db.session.execute(text("""
        SELECT LESSEE_NM FROM CAFLESS WITH(NOLOCK) WHERE APLESS = :apless
    """), {"apless": apless}).fetchone()
    customer_name = _or_dash(lessee.LESSEE_NM if lessee else None)

    spec = db.session.execute(text("""
        SELECT a.CHASIS, a.ENGINE, a.COLOUR, a.POLICENO, a.BPKB_AN, a.BPKB_ADDR,
               a.TAHUN, a.CONDITION, a.BPKB_TGLBIRTH, a.BPKB_AN_TP,
               b.BRAND_NM, d.TYPE_NM, c.MODEL_NM, e.NAME AS SUPPLIER_NM,
               f.CREATE_DATE
        FROM CAFEQUIP a
            LEFT JOIN CAFCONT f ON a.APPL_NO = f.APPL_NO
            LEFT JOIN UMFBRAND b ON a.brand = b.brand
            LEFT JOIN UMFMODEL c ON a.model = c.model
            LEFT JOIN UMFType d ON a.brand = d.brand AND a.Type = d.Type
            LEFT JOIN clfsupp e ON a.SUPP = e.Supp
        WHERE a.appl_no = :applno
    """), {"applno": applno}).fetchone()

    if spec is None:
        contract = {
            "status": contract_status, "brand": "-", "model": "-", "modelType": "-",
            "customerName": customer_name, "chassis": "-", "engine": "-",
            "bpkbName": "-", "bpkbAddress": "-", "year": "-", "condition": "-",
            "supplier": "-", "color": "-", "policeNo": "-",
        }
    else:
        bpkb_name = _or_dash(spec.BPKB_AN)
        if spec.BPKB_AN_TP == "PR" and spec.BPKB_TGLBIRTH and spec.CREATE_DATE:
            age = _compute_age(spec.BPKB_TGLBIRTH, spec.CREATE_DATE)
            if age is not None:
                bpkb_name = f"{bpkb_name} ({age} years old)"
        contract = {
            "status": contract_status,
            "brand": _or_dash(spec.BRAND_NM),
            "model": _or_dash(spec.MODEL_NM),
            "modelType": _or_dash(spec.TYPE_NM),
            "customerName": customer_name,
            "chassis": _or_dash(spec.CHASIS),
            "engine": _or_dash(spec.ENGINE),
            "bpkbName": bpkb_name,
            "bpkbAddress": _or_dash(spec.BPKB_ADDR),
            "year": _or_dash(spec.TAHUN),
            "condition": _or_dash(spec.CONDITION),
            "supplier": _or_dash(spec.SUPPLIER_NM),
            "color": _or_dash(spec.COLOUR),
            "policeNo": _or_dash(spec.POLICENO),
        }

    notes = ""
    if status != "RO":
        note_row = db.session.execute(text("""
            SELECT TOP 1 NOTES FROM SURVEY_NOTES WITH(NOLOCK)
            WHERE ApplNo = :applno AND SurveyType = :survey_type
            ORDER BY CreatedDate DESC
        """), {"applno": applno, "survey_type": SURVEY_TYPE}).fetchone()
        notes = (note_row.NOTES if note_row else "") or ""

    return jsonify({
        "contract": contract,
        "notes": notes,
        "files": _fetch_files(applno, apless),
    })

@cam_edit_bp.route("/eq-survey-file/upload", methods=["POST"])
@login_required
def upload_eq_survey_file():
    apless = (request.form.get("apless") or "").strip()
    applno = (request.form.get("applno") or "").strip()
    category = request.form.get("category") or ""
    files = request.files.getlist("files")

    if not apless or not applno:
        return jsonify({"success": False, "message": "apless and applno are required"}), 400
    if category not in CATEGORY_CONFIG:
        return jsonify({"success": False, "message": "Unknown upload category"}), 400
    if not files:
        return jsonify({"success": False, "message": "Please select a file."}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"success": False, "message": block_message}), 409

    if boto3 is None:
        current_app.logger.error("boto3 is not installed; cannot upload survey files.")
        return jsonify({"success": False, "message": "File storage is not configured on this server."}), 500

    cfg = CATEGORY_CONFIG[category]
    username = session.get("username", "")

    try:
        if cfg["single"]:
            error = _replace_single_survey_document(
                applno, apless, cfg["document_type"], cfg["subfolder"], cfg["tag"], files[0], username
            )
        else:
            error = _add_survey_documents(
                applno, apless, cfg["document_type"], cfg["subfolder"], cfg["tag"], files, username
            )

        if error:
            db.session.rollback()
            return jsonify({"success": False, "message": error})

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to upload survey file for applno=%s category=%s", applno, category)
        return jsonify({"success": False, "message": "Upload failed. Please try again."}), 500

    return jsonify({"success": True, "files": _fetch_files(applno, apless)[CATEGORY_RESPONSE_KEY[category]]})

@cam_edit_bp.route("/eq-survey-file", methods=["DELETE"])
@login_required
def delete_eq_survey_file():
    apless = (request.args.get("apless") or "").strip()
    applno = (request.args.get("applno") or "").strip()
    file_id = request.args.get("id", type=int)
    if not apless or not applno or not file_id:
        return jsonify({"success": False, "message": "apless, applno and id are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"success": False, "message": block_message}), 409

    row = db.session.execute(text("""
        SELECT AWSKey FROM SURVEY_FILE WITH(NOLOCK)
        WHERE Id = :id AND Apless = :apless AND ApplNo = :applno AND SurveyType = :survey_type
    """), {"id": file_id, "apless": apless, "applno": applno, "survey_type": SURVEY_TYPE}).fetchone()
    if not row:
        return jsonify({"success": False, "message": "File not found"}), 404

    try:
        if boto3 is not None:
            try:
                _s3_client().delete_object(Bucket=_s3_bucket(), Key=row.AWSKey)
            except Exception:
                current_app.logger.exception("Failed to delete S3 object %s", row.AWSKey)
        db.session.execute(text("DELETE FROM SURVEY_FILE WHERE Id = :id"), {"id": file_id})
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to delete survey file id=%s", file_id)
        return jsonify({"success": False, "message": "Delete failed. Please try again."}), 500

    return jsonify({"success": True})

@cam_edit_bp.route("/eq-survey-file/next", methods=["POST"])
@login_required
def next_eq_survey_file():
    payload = request.get_json(force=True) or {}
    apless = (payload.get("apless") or "").strip()
    applno = (payload.get("applno") or "").strip()
    notes = (payload.get("notes") or "").strip()
    if not apless or not applno:
        return jsonify({"success": False, "message": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"success": False, "message": block_message}), 409

    username = session.get("username", "")

    try:
        existing_note = db.session.execute(text("""
            SELECT 1 FROM SURVEY_NOTES WHERE ApplNo = :applno AND SurveyType = :survey_type
        """), {"applno": applno, "survey_type": SURVEY_TYPE}).fetchone()
        if existing_note:
            db.session.execute(text("""
                UPDATE SURVEY_NOTES SET NOTES = :notes, UpdatedBy = :username, UpdatedDate = GETDATE()
                WHERE ApplNo = :applno AND SurveyType = :survey_type
            """), {"notes": notes, "username": username, "applno": applno, "survey_type": SURVEY_TYPE})
        else:
            db.session.execute(text("""
                INSERT INTO SURVEY_NOTES (ApplNo, SurveyType, Notes, CreatedBy, CreatedDate, UpdatedBy, UpdatedDate)
                VALUES (:applno, :survey_type, :notes, :username, GETDATE(), :username, GETDATE())
            """), {"applno": applno, "survey_type": SURVEY_TYPE, "notes": notes, "username": username})
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to save survey notes for applno=%s", applno)
        return jsonify({"success": False, "message": "Save failed. Please try again."}), 500

    has_file = db.session.execute(text("""
        SELECT 1 FROM SURVEY_FILE WITH(NOLOCK) WHERE ApplNo = :applno AND SurveyType = :survey_type
    """), {"applno": applno, "survey_type": SURVEY_TYPE}).fetchone()
    if not has_file:
        return jsonify({"success": False, "message": "Used car must at least have 1 survey file"})

    return jsonify({"success": True, "apless": apless, "applno": applno})

def _fetch_tenor(lease_no):
    row = db.session.execute(text("""
        SELECT a.tenor, b.TENOR1000, b.L_TYPE
        FROM CLFCONT a WITH(NOLOCK)
            INNER JOIN CAFCONT b WITH(NOLOCK) ON a.APPL_NO = b.APPL_NO
        WHERE a.LEASE_NO = :lease_no
    """), {"lease_no": lease_no}).fetchone()
    if not row:
        return None
    return row.TENOR1000 if row.L_TYPE == "4" else row.tenor

def _fetch_installment_paid(lease_no):
    terminate_row = db.session.execute(text("""
        SELECT TOP 1 a.[status], b.TENOR
        FROM bgiro a WITH(NOLOCK)
            INNER JOIN clfcont b WITH(NOLOCK) ON a.LEASE_NO = b.LEASE_NO
        WHERE a.LEASE_NO = :lease_no
        ORDER BY a.payment DESC, a.period DESC
    """), {"lease_no": lease_no}).fetchone()

    if terminate_row and terminate_row.status == "T":
        return terminate_row.TENOR

    count_row = db.session.execute(text("""
        SELECT COUNT(a.payment) AS jlh_byr, b.ADV_ARR
        FROM bgiro a WITH(NOLOCK)
            INNER JOIN clfcont b WITH(NOLOCK) ON a.LEASE_NO = b.LEASE_NO
        WHERE a.LEASE_NO = :lease_no
            AND a.PAYMENT IS NOT NULL
            AND a.STATUS NOT IN ('T', 'P')
        GROUP BY b.ADV_ARR
    """), {"lease_no": lease_no}).fetchone()

    if not count_row:
        return 0

    jlh_byr = count_row.jlh_byr or 0
    if count_row.ADV_ARR == "V":
        return jlh_byr + 1

    exec_row = db.session.execute(text("""
        SELECT ADV_ARR FROM clfcont WITH(NOLOCK) WHERE LEASE_NO = :lease_no AND EXECUTION IS NOT NULL
    """), {"lease_no": lease_no}).fetchone()
    if exec_row and exec_row.ADV_ARR == "V":
        return jlh_byr + 1
    return jlh_byr

def _fetch_cross_collateral_rows(applno, apless):
    candidates = db.session.execute(
        text("EXEC USP_CAM_CROSSCOLLATERAL :applno, :apless"),
        {"applno": applno, "apless": apless},
    ).fetchall()

    rows = []
    for row in candidates:
        lease_no = row.LEASE_NO
        checked = (row.counters == "1") and (getattr(row, "CROSS_COLL", None) == "1")
        rows.append({
            "leaseNo": lease_no,
            "customerName": row.LESSEE_NM or "",
            "brand": row.BRAND_NM or "",
            "type": row.TYPE_NM or "",
            "installmentPaid": _fetch_installment_paid(lease_no),
            "installmentTenor": _fetch_tenor(lease_no),
            "crossCollateral": checked,
            "remark": row.remark or "",
        })
    return rows

_LEASE_CHUNK = 500

def _s(value):
    if value is None:
        return ""
    return str(value).strip()

def _flag(value):
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    return str(value).strip() == "1"

def _chunks(seq, size=_LEASE_CHUNK):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]

def _in_clause(prefix, values, params):
    keys = []
    for index, value in enumerate(values):
        key = "%s%d" % (prefix, index)
        params[key] = value
        keys.append(":" + key)
    return ", ".join(keys)

def _fetch_tenor_map(lease_nos):
    tenors = {}
    for chunk in _chunks(lease_nos):
        params = {}
        clause = _in_clause("l", chunk, params)
        rows = db.session.execute(text("""
            SELECT a.LEASE_NO, a.tenor AS tenor, b.TENOR1000, b.L_TYPE
            FROM CLFCONT a WITH(NOLOCK)
                INNER JOIN CAFCONT b WITH(NOLOCK) ON a.APPL_NO = b.APPL_NO
            WHERE a.LEASE_NO IN (%s)
        """ % clause), params).fetchall()
        for row in rows:
            lease_no = _s(row.LEASE_NO)
            if lease_no in tenors:
                continue
            tenors[lease_no] = row.TENOR1000 if _s(row.L_TYPE) == "4" else row.tenor
    return tenors

def _fetch_installment_paid_map(lease_nos):
    terminate = {}
    counts = {}
    executions = {}

    for chunk in _chunks(lease_nos):
        params = {}
        clause = _in_clause("l", chunk, params)

        for row in db.session.execute(text("""
            SELECT LEASE_NO, sts, TENOR
            FROM (
                SELECT a.LEASE_NO, a.[status] AS sts, b.TENOR,
                       ROW_NUMBER() OVER (PARTITION BY a.LEASE_NO
                                          ORDER BY a.payment DESC, a.period DESC) AS rn
                FROM bgiro a WITH(NOLOCK)
                    INNER JOIN clfcont b WITH(NOLOCK) ON a.LEASE_NO = b.LEASE_NO
                WHERE a.LEASE_NO IN (%s)
            ) t
            WHERE rn = 1
        """ % clause), params).fetchall():
            terminate[_s(row.LEASE_NO)] = (_s(row.sts), row.TENOR)

        for row in db.session.execute(text("""
            SELECT a.LEASE_NO, COUNT(a.payment) AS jlh_byr, b.ADV_ARR
            FROM bgiro a WITH(NOLOCK)
                INNER JOIN clfcont b WITH(NOLOCK) ON a.LEASE_NO = b.LEASE_NO
            WHERE a.LEASE_NO IN (%s)
                AND a.PAYMENT IS NOT NULL
                AND a.STATUS NOT IN ('T', 'P')
            GROUP BY a.LEASE_NO, b.ADV_ARR
        """ % clause), params).fetchall():
            lease_no = _s(row.LEASE_NO)
            if lease_no not in counts:
                counts[lease_no] = (row.jlh_byr or 0, _s(row.ADV_ARR))

        for row in db.session.execute(text("""
            SELECT LEASE_NO, ADV_ARR FROM clfcont WITH(NOLOCK)
            WHERE LEASE_NO IN (%s) AND EXECUTION IS NOT NULL
        """ % clause), params).fetchall():
            lease_no = _s(row.LEASE_NO)
            if lease_no not in executions:
                executions[lease_no] = _s(row.ADV_ARR)

    paid = {}
    for lease_no in lease_nos:
        latest = terminate.get(lease_no)
        if latest and latest[0] == "T":
            paid[lease_no] = latest[1]
            continue

        counted = counts.get(lease_no)
        if counted is None:
            paid[lease_no] = 1 if executions.get(lease_no) == "V" else None
            continue

        jlh_byr, adv_arr = counted
        if adv_arr == "V" or executions.get(lease_no) == "V":
            paid[lease_no] = jlh_byr + 1
        else:
            paid[lease_no] = jlh_byr
    return paid

def _fetch_cross_collateral_rows(applno, apless):
    candidates = db.session.execute(
        text("EXEC USP_CAM_CROSSCOLLATERAL :applno, :apless"),
        {"applno": applno, "apless": apless},
    ).fetchall()

    lease_nos = []
    for row in candidates:
        lease_no = _s(row.LEASE_NO)
        if lease_no and lease_no not in lease_nos:
            lease_nos.append(lease_no)

    tenor_map = _fetch_tenor_map(lease_nos)
    paid_map = _fetch_installment_paid_map(lease_nos)

    rows = []
    for row in candidates:
        lease_no = _s(row.LEASE_NO)
        checked = _flag(row.counters) and _flag(getattr(row, "CROSS_COLL", None))
        rows.append({
            "leaseNo": lease_no,
            "customerName": row.LESSEE_NM or "",
            "brand": row.BRAND_NM or "",
            "type": row.TYPE_NM or "",
            "installmentPaid": paid_map.get(lease_no),
            "installmentTenor": tenor_map.get(lease_no),
            "crossCollateral": checked,
            "remark": row.remark or "",
        })
    return rows

@cam_edit_bp.route("/cross-collateral", methods=["GET"])
@login_required
def get_cross_collateral():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    if not apless or not applno:
        return jsonify({"error": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"blocked": True, "message": block_message}), 409

    return jsonify({"rows": _fetch_cross_collateral_rows(applno, apless)})

@cam_edit_bp.route("/cross-collateral/next", methods=["POST"])
@login_required
def next_cross_collateral():
    payload = request.get_json(force=True) or {}
    apless = (payload.get("apless") or "").strip()
    applno = (payload.get("applno") or "").strip()
    selections = payload.get("rows") or []
    if not apless or not applno:
        return jsonify({"success": False, "message": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"success": False, "blocked": True, "message": block_message}), 409

    username = session.get("username", "")

    selected = {
        _s(r.get("leaseNo")): bool(r.get("crossCollateral"))
        for r in selections if _s(r.get("leaseNo"))
    }

    rows = _fetch_cross_collateral_rows(applno, apless)

    try:
        db.session.execute(text("DELETE FROM CAFCROSSCOLL WHERE APPL_NO = :applno"), {"applno": applno})
        for row in rows:
            db.session.execute(text("""
                INSERT INTO CAFCROSSCOLL
                    (APPL_NO, LEASE_NO, CROSS_COLL, remark, installment, APPLICATION, CREATEBY)
                VALUES (:applno, :lease_no, :cross, :remark, :installment, 'CAM', :username)
            """), {
                "applno": applno,
                "lease_no": row["leaseNo"],
                "cross": "1" if selected.get(row["leaseNo"], False) else "0",
                "remark": row["remark"] or None,
                "installment": row["installmentPaid"],
                "username": username,
            })
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to save cross collateral selections for applno=%s", applno)
        return jsonify({"success": False, "message": "Save failed. Please try again."}), 500

    return jsonify({"success": True, "apless": apless, "applno": applno})

EDD_LABEL = "Enhanced Due Diligence (EDD)"
EDD_VALIDATION_MESSAGE = (
    "Seluruh kuisioner Enhanced Due Diligence (EDD) harus terisi 'YES' / "
    "All Enhanced Due Diligence (EDD) questionnaire must be filled in 'YES'"
)

def _fetch_edd_questions(cat_value):
    rows = db.session.execute(text("""
        SELECT [VALUE], DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) WHERE cat_value = :cat_value ORDER BY [VALUE]
    """), {"cat_value": cat_value}).fetchall()
    return [{"value": r.VALUE, "description": r.DESC_VALUE} for r in rows]

def _fetch_apu_ppt_summary(applno):
    
    row = db.session.execute(text("""
        SELECT cl.LESSEE_NM,
               CASE WHEN cl.LESSEE_TP = 'PR' THEN 'Individu' ELSE 'Corporate' END AS lesse_tp,
               mlt.NAME,
               mc.DESC_VALUE,
               CASE WHEN SUBSTRING(cld.BUSINESS_TYPE, 4, 1) = 'H' THEN 'High Risk' ELSE 'Non High Risk' END AS status,
               CASE WHEN SUBSTRING(cld.BUSINESS_TYPE, 4, 1) = 'H' THEN 'Enhanced Due Diligence (EDD)' ELSE 'Customer Due Diligence (CDD)' END AS identity_cus,
               bo.BO_Name,
               CASE WHEN bo.BO_TP = 'PR' THEN 'Individu' ELSE 'Corporate' END AS lesse_tp2,
               mlt1.NAME AS name2,
               mc1.DESC_VALUE AS desc_value2,
               CASE WHEN SUBSTRING(bo.BUSINESS_TYPE, 4, 1) = 'H' THEN 'High Risk' ELSE 'Non High Risk' END AS status2,
               CASE WHEN SUBSTRING(bo.BUSINESS_TYPE, 4, 1) = 'H' THEN 'Enhanced Due Diligence (EDD)' ELSE 'Customer Due Diligence (CDD)' END AS identity_bo
        FROM CAFCONT cc WITH(NOLOCK)
            INNER JOIN CAFLESS cl WITH(NOLOCK) ON cl.APLESS = cc.APLESS
            LEFT JOIN CAFLESS_DETAIL cld WITH(NOLOCK) ON cld.APLESS = cc.APLESS
            LEFT JOIN MSTCOMBO mc WITH(NOLOCK) ON mc.VALUE = cld.BUSINESS_TYPE
                AND mc.CAT_VALUE IN ('PEP', 'USAHA_HIGH_RISK', 'KOPERASI_HIGH_RISK')
            INNER JOIN MSTLESSEETYPE mlt WITH(NOLOCK) ON mlt.CUST_TYPE = cl.Lessee_Cat
            LEFT JOIN BENEFICIARY_LINK bl WITH(NOLOCK) ON bl.APPL_NO = cc.APPL_NO
            LEFT JOIN BENEFICIARY_OWNER bo WITH(NOLOCK) ON bo.BO_ID = bl.BO_ID
            LEFT JOIN MSTLESSEETYPE mlt1 WITH(NOLOCK) ON mlt1.CUST_TYPE = bo.BO_Cat
            LEFT JOIN MSTCOMBO mc1 WITH(NOLOCK) ON mc1.VALUE = bo.BUSINESS_TYPE
        WHERE cc.APPL_NO = :applno
    """), {"applno": applno}).fetchone()

    if row is None:
        return None

    customer = {
        "name": row.LESSEE_NM or "-",
        "type": f"{row.lesse_tp} / {row.NAME or '-'}" if row.lesse_tp else "-",
        "occupationBusinessType": row.DESC_VALUE or "-",
        "apuPptStatus": row.status or "-",
        "identificationProcess": row.identity_cus or "-",
    }

    beneficial_owner = None
    if row.BO_Name:
        beneficial_owner = {
            "name": row.BO_Name,
            "type": f"{row.lesse_tp2} / {row.name2 or '-'}" if row.lesse_tp2 else "-",
            "occupationBusinessType": row.desc_value2 or "-",
            "apuPptStatus": row.status2 or "-",
            "identificationProcess": row.identity_bo or "-",
        }

    return {"customer": customer, "beneficialOwner": beneficial_owner}

def _is_edd_required(identification_process):
    return identification_process == EDD_LABEL

@cam_edit_bp.route("/apu-ppt", methods=["GET"])
@login_required
def get_apu_ppt():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    if not apless or not applno:
        return jsonify({"error": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"blocked": True, "message": block_message}), 409

    summary = _fetch_apu_ppt_summary(applno)
    if summary is None:
        return jsonify({"error": "No APU PPT data found for this application"}), 404

    edd_row = db.session.execute(text("""
        SELECT EDD_Customer, EDD_BO FROM Kuisioner_EDD WITH(NOLOCK) WHERE APPL_NO = :applno
    """), {"applno": applno}).fetchone()
    edd_customer_flag = edd_row.EDD_Customer if edd_row else None
    edd_bo_flag = edd_row.EDD_BO if edd_row else None

    customer = summary["customer"]
    customer_required = _is_edd_required(customer.get("identificationProcess"))
    customer_payload = {
        **customer,
        "eddRequired": customer_required,
        "eddQuestions": _fetch_edd_questions("EDD_Customer") if customer_required else [],
        "previouslyPassed": edd_customer_flag == "1",
    }

    bo = summary.get("beneficialOwner")
    bo_payload = None
    if bo is not None:
        bo_required = _is_edd_required(bo.get("identificationProcess"))
        bo_payload = {
            **bo,
            "eddRequired": bo_required,
            "eddQuestions": _fetch_edd_questions("EDD_BO") if bo_required else [],
            "previouslyPassed": edd_bo_flag == "1",
        }

    return jsonify({"customer": customer_payload, "beneficialOwner": bo_payload})

@cam_edit_bp.route("/apu-ppt/next", methods=["POST"])
@login_required
def next_apu_ppt():
    payload = request.get_json(force=True) or {}
    apless = (payload.get("apless") or "").strip()
    applno = (payload.get("applno") or "").strip()
    customer_answers = payload.get("customerAnswers") or {}
    bo_answers = payload.get("boAnswers") or {}
    if not apless or not applno:
        return jsonify({"success": False, "message": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"success": False, "message": block_message}), 409

    summary = _fetch_apu_ppt_summary(applno)
    if summary is None:
        return jsonify({"success": False, "message": "No APU PPT data found for this application"}), 404

    customer_required = _is_edd_required(summary["customer"].get("identificationProcess"))
    bo = summary.get("beneficialOwner")
    bo_required = bo is not None and _is_edd_required(bo.get("identificationProcess"))

    if not customer_required and not bo_required:
        return jsonify({"success": True, "apless": apless, "applno": applno})

    def _all_yes(answers, questions):
        return all(str(answers.get(str(q["value"]))) == "1" for q in questions)

    valid = True
    if customer_required and not _all_yes(customer_answers, _fetch_edd_questions("EDD_Customer")):
        valid = False
    if bo_required and not _all_yes(bo_answers, _fetch_edd_questions("EDD_BO")):
        valid = False

    if not valid:
        return jsonify({"success": False, "message": EDD_VALIDATION_MESSAGE})

    flag_cust = "1" if customer_required else ""
    flag_bo = "1" if bo_required else ""

    try:
        db.session.execute(text("DELETE FROM Kuisioner_EDD WHERE APPL_NO = :applno"), {"applno": applno})
        db.session.execute(text("""
            INSERT INTO Kuisioner_EDD (appl_no, EDD_Customer, EDD_BO) VALUES (:applno, :flag_cust, :flag_bo)
        """), {"applno": applno, "flag_cust": flag_cust, "flag_bo": flag_bo})
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to save APU PPT EDD questionnaire for applno=%s", applno)
        return jsonify({"success": False, "message": "Save failed. Please try again."}), 500

    return jsonify({"success": True, "apless": apless, "applno": applno})

@cam_edit_bp.route("/cam-notes", methods=["GET"])
@login_required
def get_cam_notes():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    if not apless or not applno:
        return jsonify({"error": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"blocked": True, "message": block_message}), 409

    row = db.session.execute(text("""
        SELECT CAM_NOTES FROM CAFCONT WITH(NOLOCK) WHERE APPL_NO = :applno
    """), {"applno": applno}).fetchone()

    return jsonify({"notes": (row.CAM_NOTES if row else "") or ""})

@cam_edit_bp.route("/cam-notes/save", methods=["POST"])
@login_required
def save_cam_notes():
    payload = request.get_json(force=True) or {}
    apless = (payload.get("apless") or "").strip()
    applno = (payload.get("applno") or "").strip()
    notes = payload.get("notes") or ""
    if not apless or not applno:
        return jsonify({"success": False, "message": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"success": False, "message": block_message}), 409

    try:
        result = db.session.execute(text("""
            UPDATE CAFCONT SET CAM_NOTES = :notes WHERE APPL_NO = :applno
        """), {"notes": notes, "applno": applno})
        if result.rowcount == 0:
            db.session.rollback()
            return jsonify({"success": False, "message": "Failed"})
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to save CAM notes for applno=%s", applno)
        return jsonify({"success": False, "message": "Failed"}), 500

    return jsonify({"success": True})

@cam_edit_bp.route("/cam-notes/next", methods=["POST"])
@login_required
def next_cam_notes():
    payload = request.get_json(force=True) or {}
    apless = (payload.get("apless") or "").strip()
    applno = (payload.get("applno") or "").strip()
    if not apless or not applno:
        return jsonify({"success": False, "message": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"success": False, "message": block_message}), 409

    return jsonify({"success": True, "apless": apless, "applno": applno})

@cam_edit_bp.route("/customer-notes", methods=["GET"])
@login_required
def get_customer_notes():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    if not apless or not applno:
        return jsonify({"error": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"blocked": True, "message": block_message}), 409

    row = db.session.execute(text("""
        SELECT NOTES FROM CAFCONT WITH(NOLOCK) WHERE APPL_NO = :applno
    """), {"applno": applno}).fetchone()

    return jsonify({"notes": (row.NOTES if row else "") or ""})

@cam_edit_bp.route("/customer-notes/save", methods=["POST"])
@login_required
def save_customer_notes():
    payload = request.get_json(force=True) or {}
    apless = (payload.get("apless") or "").strip()
    applno = (payload.get("applno") or "").strip()
    notes = payload.get("notes") or ""
    if not apless or not applno:
        return jsonify({"success": False, "message": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"success": False, "message": block_message}), 409

    try:
        result = db.session.execute(text("""
            UPDATE CAFCONT SET NOTES = :notes WHERE APPL_NO = :applno
        """), {"notes": notes, "applno": applno})
        if result.rowcount == 0:
            db.session.rollback()
            return jsonify({"success": False, "message": "Failed"})
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to save customer notes for applno=%s", applno)
        return jsonify({"success": False, "message": "Failed"}), 500

    return jsonify({"success": True})

@cam_edit_bp.route("/customer-notes/next", methods=["POST"])
@login_required
def next_customer_notes():
    payload = request.get_json(force=True) or {}
    apless = (payload.get("apless") or "").strip()
    applno = (payload.get("applno") or "").strip()
    if not apless or not applno:
        return jsonify({"success": False, "message": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"success": False, "message": block_message}), 409

    return jsonify({"success": True, "apless": apless, "applno": applno})

MAX_LENGTH = 255
@cam_edit_bp.route("/revision-notes", methods=["GET"])
@login_required
def get_revision_notes():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    if not apless or not applno:
        return jsonify({"error": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"blocked": True, "message": block_message}), 409

    row = db.session.execute(text("""
        SELECT REVISI_NOTE FROM MCMOREVISI WITH(NOLOCK) WHERE NEWAPPL_NO = :applno
    """), {"applno": applno}).fetchone()

    return jsonify({"notes": (row.REVISI_NOTE if row else "") or ""})

@cam_edit_bp.route("/revision-notes/save", methods=["POST"])
@login_required
def save_revision_notes():
    payload = request.get_json(force=True) or {}
    apless = (payload.get("apless") or "").strip()
    applno = (payload.get("applno") or "").strip()
    notes = (payload.get("notes") or "")[:MAX_LENGTH]
    if not apless or not applno:
        return jsonify({"success": False, "message": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"success": False, "message": block_message}), 409

    try:
        exists = db.session.execute(text("""
            SELECT 1 FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :applno
        """), {"applno": applno}).fetchone()

        if not exists:
            db.session.rollback()
            return jsonify({"success": False, "message": "Failed"})

        result = db.session.execute(text("""
            UPDATE MCMOREVISI SET REVISI_NOTE = :notes WHERE NEWAPPL_NO = :applno
        """), {"notes": notes, "applno": applno})
        if result.rowcount == 0:
            db.session.execute(text("""
                INSERT INTO MCMOREVISI (NEWAPPL_NO, REVISI_NOTE) VALUES (:applno, :notes)
            """), {"notes": notes, "applno": applno})

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to save revision notes for applno=%s", applno)
        return jsonify({"success": False, "message": "Failed"}), 500

    return jsonify({"success": True})

@cam_edit_bp.route("/revision-notes/next", methods=["POST"])
@login_required
def next_revision_notes():
    payload = request.get_json(force=True) or {}
    apless = (payload.get("apless") or "").strip()
    applno = (payload.get("applno") or "").strip()
    if not apless or not applno:
        return jsonify({"success": False, "message": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"success": False, "message": block_message}), 409

    return jsonify({"success": True, "apless": apless, "applno": applno})

@cam_edit_bp.route("/get-data", methods=["GET"])
@login_required
def get_data_survey():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    if not apless or not applno:
        return jsonify({"error": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"blocked": True, "message": block_message}), 409

    row = db.session.execute(text("""
        SELECT c.Cons_Leas, c.Cont_type, c.PURPOFFINC, c.HAS_GUARANTOR,
               e.CONDITION, cd.GO_PUBLIC, r.RESTRUCTURING_CHANGE
        FROM CAFCONT c WITH(NOLOCK)
            LEFT JOIN CAFEQUIP e WITH(NOLOCK) ON e.APPL_NO = c.APPL_NO
            LEFT JOIN CAFLESS_DETAIL cd WITH(NOLOCK) ON cd.APLESS = c.APLESS
            LEFT JOIN CAFCONT_RESTRUCTURING r WITH(NOLOCK) ON r.APPL_NO = c.APPL_NO
        WHERE c.APPL_NO = :applno AND c.APLESS = :apless
    """), {"applno": applno, "apless": apless}).fetchone()

    if not row:
        return jsonify({"error": "Not found"}), 404

    boa, bot, _bo_id = _current_bo(applno)
    purpoffinc = str(row.PURPOFFINC or "").strip()

    return jsonify({
        "apless": apless,
        "applno": applno,
        "finType": (row.Cons_Leas or "").strip(),
        "purpoffinc": purpoffinc,
        "contType": (row.Cont_type or "").strip(),
        "guarantor": "2" if row.HAS_GUARANTOR else "1",
        "newCar": {"NEW": "2", "USED": "1"}.get((row.CONDITION or "").strip().upper(), ""),
        "goPublic": "" if row.GO_PUBLIC is None else str(row.GO_PUBLIC),
        "restructuringChange": row.RESTRUCTURING_CHANGE or "",
        "boa": boa,
        "bot": bot,
        "lookups": {
            "purposes": _fetch_purposes(),
            "financeTypes": _fetch_finance_types(purpoffinc),
            "contractTypes": _fetch_all_contract_types(),
            "restructuringChanges": _fetch_combo("RESTRUCTURING_CHANGE"),
        },
    })

_CREDIT_HIS_OPTS = [{"value": "1", "label": "Good"}, {"value": "2", "label": "Medium"}, {"value": "3", "label": "Low"}]
_REF_OPTS = [{"value": "1", "label": "Customer"}, {"value": "2", "label": "Showroom/ Dealer"}, {"value": "3", "label": "Employee"}]
_WORK_EXP_OPTS = [{"value": "1", "label": "<2 years"}, {"value": "2", "label": "2-5 years"}, {"value": "3", "label": ">5 years"}]
_LIVING_OPTS = [{"value": "1", "label": "House"}, {"value": "2", "label": "Apartment"}]
_LIVING_STS_HOUSE_OPTS = [
    {"value": "1", "label": "Rent"}, {"value": "2", "label": "Permanent - Owned"},
    {"value": "3", "label": "Permanent - Family Owned"}, {"value": "4", "label": "Company"},
]
_LIVING_STS_APT_OPTS = [{"value": "1", "label": "Rent"}, {"value": "2", "label": "Owned"}, {"value": "3", "label": "Company"}]
_CAR_OWN_OPTS = [{"value": "1", "label": "First Car User"}, {"value": "2", "label": "More than 1 Car"}]
_JOB_OPTS = [
    {"value": "1", "label": "Not Work"}, {"value": "2", "label": "Entrepreneur"},
    {"value": "3", "label": "Employee"}, {"value": "4", "label": "Professional"},
]
_DP_OPTS = [{"value": "1", "label": "< Standard"}, {"value": "2", "label": "= Standard"}, {"value": "3", "label": "> Standard"}]
_PMT_IND_OPTS = [{"value": "0", "label": "Auto Debet BCA"}, {"value": "1", "label": "Giro"}, {"value": "2", "label": "Transfer/ Cash"}]
_PMT_CORP_OPTS = [{"value": "0", "label": "Auto Debet BCA"}, {"value": "1", "label": "Giro/ Cheque"}, {"value": "2", "label": "Transfer/ Cash"}]
_COMP_STS_OPTS = [
    {"value": "1", "label": "Pure Foreign Company"},
    {"value": "2", "label": "Joint Venture Company/ Multinational Company"},
    {"value": "3", "label": "National Company"}, {"value": "4", "label": "Family Business"},
    {"value": "5", "label": "Private Business"},
]
_SCALE_OPTS = [{"value": "1", "label": "Local"}, {"value": "2", "label": "National"}, {"value": "3", "label": "International"}]
_BUS_LOC_OPTS = [
    {"value": "1", "label": "Business District (Gedung, Ruko, Pasar)"},
    {"value": "2", "label": "House Complex"}, {"value": "3", "label": "Non Permanent"},
]
_UNIT_OWN_OPTS = [{"value": "1", "label": "> 10"}, {"value": "2", "label": "< 10"}, {"value": "3", "label": "None"}]
_UNIT_FREE_OPTS = [{"value": "1", "label": "> 50%"}, {"value": "2", "label": "30 - 50%"}, {"value": "3", "label": "< 30%"}]
_NET_PROFIT_OPTS = [{"value": "1", "label": "> 30%"}, {"value": "2", "label": "10 - 30%"}, {"value": "3", "label": "< 10%"}]

def _to_number(value):
    if value in (None, ""):
        return 0
    if isinstance(value, str):
        value = value.replace(",", "")
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0

def _fetch_contract_status(appl_no):
    row = db.session.execute(text(
        "SELECT ContSts FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :appl_no"
    ), {"appl_no": appl_no}).fetchone()
    return row.ContSts if row else None

def _has_reference(apless):
    row = db.session.execute(text(
        "SELECT 1 FROM CAFREF WITH (NOLOCK) WHERE APLESS = :apless"
    ), {"apless": apless}).fetchone()
    return row is not None

def _fetch_lessee_info(apless):
    row = db.session.execute(text(
        "SELECT MARITAL, Lessee_Cat FROM CAFLESS WITH (NOLOCK) WHERE APLESS = :apless"
    ), {"apless": apless}).fetchone()
    return (row.MARITAL if row else None, row.Lessee_Cat if row else None)

def _fetch_business_size(apless):
    row = db.session.execute(text(
        "SELECT BUSINESS_SIZE FROM CAFLESS WITH (NOLOCK) WHERE APLESS = :apless"
    ), {"apless": apless}).fetchone()
    return row.BUSINESS_SIZE if row else ""

def _col_type_pmt(applno):
    row = db.session.execute(text(
        "SELECT COL_TYPE FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :applno"
    ), {"applno": applno}).fetchone()
    col_type = row.COL_TYPE if row else None
    return col_type, {"AU": "0", "BG": "1", "TR": "2"}.get(col_type, "")

def _resolve_pmt(stored_pmt, applno):
    if stored_pmt not in (None, ""):
        return stored_pmt
    return _col_type_pmt(applno)[1]

def _resolve_pmt_corporate(stored_pmt, applno):
    col_type, mapped = _col_type_pmt(applno)
    if stored_pmt in (None, "") or stored_pmt != col_type:
        return mapped
    return stored_pmt

def _sik_download_url(aws_key):
    if not aws_key:
        return None
    bucket = current_app.config.get("BUCKET_PEFINDO")
    if not bucket:
        current_app.logger.warning("BUCKET_PEFINDO is not configured; cannot build SIK download URL (key=%s)", aws_key)
        return None
    file_name = aws_key.rsplit("/", 1)[-1]
    return _aws_presign_bucket(aws_key, file_name, bucket)

def _fetch_sik_checking_documents(applno):
    rows = db.session.execute(text("""
        SELECT DISTINCT [Subject], [Description], CreditBureau, RelatedParty, [Status], [Type],
               Score, Grade, Pefindo, AWSKey
        FROM SIK_CHECKING_DOCUMENT WITH (NOLOCK) WHERE ApplNo = :applno
    """), {"applno": applno}).fetchall()

    docs = []
    for r in rows:
        docs.append({
            "subject": r.Subject,
            "description": r.Description,
            "creditBureau": r.CreditBureau,
            "relatedParty": r.RelatedParty,
            "status": r.Status,
            "type": r.Type,
            "score": r.Score,
            "grade": r.Grade,
            "downloadUrl": _sik_download_url(r.AWSKey) if r.Pefindo else None,
        })
    return docs

def _individual_work_exp(apless):
    rows = db.session.execute(text("""
        SELECT (CAST(LEFT(UNTIL, 4) AS INT) - CAST(LEFT([FROM], 4) AS INT)) AS WORK_EXP
        FROM CAFLESS_History WITH (NOLOCK) WHERE APLESS = :apless ORDER BY ID DESC
    """), {"apless": apless}).fetchall()
    total_years = sum((r.WORK_EXP or 0) for r in rows)
    if total_years < 2:
        return "1"
    if total_years <= 5:
        return "2"
    return "3"

def _individual_bank_stats(apless, applno):
    bank_row = db.session.execute(text("""
        SELECT DISTINCT TOP 1 Bank, Period FROM CAFBANKSTM WITH (NOLOCK)
        WHERE APLESS = :apless AND APPL_NO = :applno ORDER BY Period DESC
    """), {"apless": apless, "applno": applno}).fetchone()

    avr_credit, avr_endbal = 0, 0
    if bank_row and bank_row.Bank:
        bank_count_row = db.session.execute(text("""
            SELECT COUNT(DISTINCT Bank) AS cnt FROM CAFBANKSTM WITH (NOLOCK)
            WHERE APLESS = :apless AND APPL_NO = :applno
        """), {"apless": apless, "applno": applno}).fetchone()
        bank_count = bank_count_row.cnt or 1

        rows = db.session.execute(text("""
            SELECT Credit, EndBal FROM CAFBANKSTM WITH (NOLOCK)
            WHERE APLESS = :apless AND APPL_NO = :applno ORDER BY Period DESC
        """), {"apless": apless, "applno": applno}).fetchall()

        total_credit = sum((r.Credit or 0) for r in rows)
        total_endbal = sum((r.EndBal or 0) for r in rows)
        count = len(rows)
        if count:
            divisor = max(1, -(-count // bank_count))
            avr_credit = round(total_credit / divisor)
            avr_endbal = total_endbal / count

    return avr_credit, avr_endbal

def _classify_bank_stat_amt_individual(avr_endbal, asset_value):
    if avr_endbal is None or asset_value is None:
        return ""
    if avr_endbal > asset_value:
        return "1"
    if avr_endbal == asset_value:
        return "2"
    return "3"

def _survey_individual_defaults(apless, applno, asset_value):
    row = db.session.execute(text("""
        SELECT a.CREDIT_HIS, a.REF, a.WORK_EXP, a.NOTE_CHAR, a.LIVING, a.LIVING_STS, a.CAR_OWN,
               a.DEPOSIT, a.BANK_STAT, a.DEPOSIT_AMT, a.BANK_STAT_AMT, a.NOTE_CAPITAL, a.FIX_INC,
               a.JOB, a.TOT_OTH_INC, a.TOT_INC, a.TOT_CREDIT, a.NOTE_CAPACITY, a.DP, a.PMT,
               a.NOTE_COLLATERAL, a.FIX_INC_SOURCE, a.TOT_OTH_INC_SOURCE, a.FIX_SOURCE_REMARK,
               a.OTH_SOURCE_REMARK, a.TOT_INC_YEAR,
               IIF(a.NOTE_SID_CHECKING = '', d.Remarks, a.NOTE_SID_CHECKING) AS NOTE_SID_CHECKING
        FROM CAFSURV_PR a WITH (NOLOCK)
            LEFT JOIN TEMP_CAFCONT b WITH (NOLOCK) ON a.APPL_NO = b.FINAL_APPL_NO
            LEFT JOIN documentApproval c WITH (NOLOCK) ON b.ApplNo = c.DocumentNumber
            LEFT JOIN documentApprovalHistory d WITH (NOLOCK)
                ON c.id = d.DocumentApprovalId AND d.ApprovalActionCode = 'approve'
        WHERE a.APPL_NO = :applno
    """), {"applno": applno}).fetchone()

    marital, lessee_cat = _fetch_lessee_info(apless)
    business_disabled = lessee_cat in ("EM", "PF", "EN")
    business_size = "5" if business_disabled else _fetch_business_size(apless)

    work_exp = row.WORK_EXP if row else None
    if not work_exp:
        work_exp = _individual_work_exp(apless)

    fix_inc_row = db.session.execute(text("""
        SELECT TOP 1 AMOUNT FROM CAFFS WITH (NOLOCK)
        WHERE APLESS = :apless AND FS_CODE = 'I' AND ITEM_CODE = '310101'
        ORDER BY PERIOD DESC
    """), {"apless": apless}).fetchone()
    caffs_fix_inc = fix_inc_row.AMOUNT if fix_inc_row else 0

    stored_fix_inc = row.FIX_INC if row else None
    fix_inc = caffs_fix_inc if (not stored_fix_inc or stored_fix_inc != caffs_fix_inc) else stored_fix_inc

    other_inc_row = db.session.execute(text("""
        SELECT TOP 1 AMOUNT FROM CAFFS WITH (NOLOCK)
        WHERE FS_CODE = 'I' AND ITEM_CODE = '310102' AND APLESS = :apless
          AND [PERIOD] <= (SELECT YEAR(CREATE_DATE) FROM CAFCONT WHERE APPL_NO = :applno)
        ORDER BY PERIOD DESC
    """), {"apless": apless, "applno": applno}).fetchone()
    tot_oth_inc = other_inc_row.AMOUNT if other_inc_row else 0

    spouse_row = db.session.execute(text("""
        SELECT TOP 1 AMOUNT FROM CAFFS WITH (NOLOCK)
        WHERE APLESS = :apless AND ITEM_CODE = '310103' ORDER BY PERIOD DESC
    """), {"apless": apless}).fetchone()
    spouse_income = spouse_row.AMOUNT if spouse_row else 0

    tot_inc = (fix_inc or 0) + (tot_oth_inc or 0) + (spouse_income or 0)
    tot_inc_year = row.TOT_INC_YEAR if (row and row.TOT_INC_YEAR) else tot_inc * 12

    avr_credit, avr_endbal = _individual_bank_stats(apless, applno)
    tot_credit = (row.TOT_CREDIT if row else None) or avr_credit
    bank_stat_amt = (row.BANK_STAT_AMT if row else None) or _classify_bank_stat_amt_individual(avr_endbal, asset_value)

    return {
        "creditHis": row.CREDIT_HIS if row else "",
        "reference": row.REF if row else "",
        "workExp": str(work_exp) if work_exp else "",
        "businessSize": business_size,
        "businessSizeDisabled": business_disabled,
        "noteChar": row.NOTE_CHAR if row else "",
        "living": row.LIVING if row else "",
        "livingSts": row.LIVING_STS if row else "",
        "carOwn": row.CAR_OWN if row else "",
        "deposit": (row.DEPOSIT == "1") if row else False,
        "bankStat": (row.BANK_STAT == "1") if row else False,
        "depositAmt": row.DEPOSIT_AMT if row else 0,
        "bankStatAmt": bank_stat_amt,
        "noteCapital": row.NOTE_CAPITAL if row else "",
        "fixInc": fix_inc or 0,
        "fixIncSource": row.FIX_INC_SOURCE if row else "",
        "fixIncSourceOther": row.FIX_SOURCE_REMARK if row else "",
        "spouseMaritalDisabled": marital == "S",
        "spouseJob": row.JOB if row else "",
        "spouseIncome": spouse_income or 0,
        "totOthInc": tot_oth_inc or 0,
        "totOthIncSource": row.TOT_OTH_INC_SOURCE if row else "",
        "totOthIncSourceOther": row.OTH_SOURCE_REMARK if row else "",
        "totInc": tot_inc,
        "totIncYear": tot_inc_year,
        "totCredit": tot_credit or 0,
        "noteCapacity": row.NOTE_CAPACITY if row else "",
        "dp": row.DP if row else "",
        "pmt": _resolve_pmt(row.PMT if row else None, applno),
        "noteCollateral": row.NOTE_COLLATERAL if row else "",
        "noteSid": row.NOTE_SID_CHECKING if row else "",
    }

def _save_individual(apless, applno, f):
    exists = db.session.execute(text(
        "SELECT 1 FROM CAFSURV_PR WITH (NOLOCK) WHERE APPL_NO = :applno"
    ), {"applno": applno}).fetchone()

    tot_oth_inc = _to_number(f.get("totOthInc"))
    params = {
        "applno": applno,
        "credit_his": f.get("creditHis") or "", "ref": f.get("reference") or "",
        "work_exp": f.get("workExp") or "", "note_char": f.get("noteChar") or "",
        "living": f.get("living") or "", "living_sts": f.get("livingSts") or "",
        "car_own": f.get("carOwn") or "", "deposit": "1" if f.get("deposit") else "0",
        "bank_stat": "1" if f.get("bankStat") else "0", "deposit_amt": _to_number(f.get("depositAmt")),
        "bank_stat_amt": f.get("bankStatAmt") or "", "note_capital": f.get("noteCapital") or "",
        "fix_inc": _to_number(f.get("fixInc")), "job": f.get("spouseJob") or "",
        "tot_oth_inc": tot_oth_inc, "tot_inc": _to_number(f.get("totInc")),
        "tot_credit": _to_number(f.get("totCredit")), "note_capacity": f.get("noteCapacity") or "",
        "dp": f.get("dp") or "", "pmt": f.get("pmt") or "", "note_collateral": f.get("noteCollateral") or "",
        "fix_inc_source": f.get("fixIncSource") or "", "tot_oth_inc_source": f.get("totOthIncSource") or "",
        "fix_source_remark": f.get("fixIncSourceOther") or "", "oth_source_remark": f.get("totOthIncSourceOther") or "",
        "note_sid": f.get("noteSid") or "", "tot_inc_year": _to_number(f.get("totIncYear")),
    }

    if exists:
        db.session.execute(text("""
            UPDATE CAFSURV_PR SET CREDIT_HIS=:credit_his, REF=:ref, WORK_EXP=:work_exp, NOTE_CHAR=:note_char,
                LIVING=:living, LIVING_STS=:living_sts, CAR_OWN=:car_own, DEPOSIT=:deposit, BANK_STAT=:bank_stat,
                DEPOSIT_AMT=:deposit_amt, BANK_STAT_AMT=:bank_stat_amt, NOTE_CAPITAL=:note_capital, FIX_INC=:fix_inc,
                JOB=:job, TOT_OTH_INC=:tot_oth_inc, TOT_INC=:tot_inc, TOT_CREDIT=:tot_credit,
                NOTE_CAPACITY=:note_capacity, DP=:dp, PMT=:pmt, NOTE_COLLATERAL=:note_collateral,
                FIX_INC_SOURCE=:fix_inc_source, TOT_OTH_INC_SOURCE=:tot_oth_inc_source,
                FIX_SOURCE_REMARK=:fix_source_remark, OTH_SOURCE_REMARK=:oth_source_remark,
                NOTE_SID_CHECKING=:note_sid, TOT_INC_YEAR=:tot_inc_year
            WHERE APPL_NO = :applno
        """), params)
    else:
        db.session.execute(text("""
            INSERT INTO CAFSURV_PR (APPL_NO, CREDIT_HIS, REF, WORK_EXP, NOTE_CHAR, LIVING, LIVING_STS, CAR_OWN,
                DEPOSIT, BANK_STAT, DEPOSIT_AMT, BANK_STAT_AMT, NOTE_CAPITAL, FIX_INC, JOB, TOT_OTH_INC, TOT_INC,
                TOT_CREDIT, NOTE_CAPACITY, DP, PMT, NOTE_COLLATERAL, FIX_INC_SOURCE, TOT_OTH_INC_SOURCE,
                FIX_SOURCE_REMARK, OTH_SOURCE_REMARK, NOTE_SID_CHECKING, TOT_INC_YEAR)
            VALUES (:applno, :credit_his, :ref, :work_exp, :note_char, :living, :living_sts, :car_own, :deposit,
                :bank_stat, :deposit_amt, :bank_stat_amt, :note_capital, :fix_inc, :job, :tot_oth_inc, :tot_inc,
                :tot_credit, :note_capacity, :dp, :pmt, :note_collateral, :fix_inc_source, :tot_oth_inc_source,
                :fix_source_remark, :oth_source_remark, :note_sid, :tot_inc_year)
        """), params)

    db.session.execute(text(
        "UPDATE CAFLESS SET SPOUSE_INCOME = :spouse_income, BUSINESS_SIZE = :business_size WHERE APLESS = :apless"
    ), {"spouse_income": _to_number(f.get("spouseIncome")), "business_size": f.get("businessSize") or "", "apless": apless})

    db.session.execute(text(
        "UPDATE CAFFS SET AMOUNT = :amount WHERE APLESS = :apless AND ITEM_CODE = '310102' AND FS_CODE = 'I'"
    ), {"amount": tot_oth_inc, "apless": apless})

def _classify_business_size(avg_income):
    if avg_income <= 300_000_000:
        return "1"
    if avg_income <= 2_500_000_000:
        return "2"
    if avg_income <= 50_000_000_000:
        return "3"
    return "4"

def _corporate_work_exp(apless):
    row = db.session.execute(text("""
        SELECT DATEDIFF(HOUR, TGLBIRTH, GETDATE()) / 8766 AS workexp
        FROM CAFLESS WITH (NOLOCK) WHERE APLESS = :apless
    """), {"apless": apless}).fetchone()
    years = int(row.workexp) if row and row.workexp is not None else 0
    if years < 2:
        return "1"
    if years <= 5:
        return "2"
    return "3"

def _corporate_bank_stats(apless, applno):
    bank_row = db.session.execute(text("""
        SELECT DISTINCT TOP 1 Bank, Period
        FROM CAFBANKSTM WITH (NOLOCK)
        WHERE APLESS = :apless AND APPL_NO = :applno ORDER BY Period DESC
    """), {"apless": apless, "applno": applno}).fetchone()

    if not (bank_row and bank_row.Bank):
        return 0, False

    saving_row = db.session.execute(text("""
        SELECT SUM(EndBal) AS Saving
        FROM CAFBANKSTM cbs WITH (NOLOCK)
        INNER JOIN (
            SELECT Bank, ACC_No, MAX([Period]) AS Periode
            FROM CAFBANKSTM WITH (NOLOCK)
            WHERE APPL_NO = :applno AND Curr_code = 'IDR'
            GROUP BY Bank, ACC_No
        ) cbm ON cbs.Bank = cbm.Bank AND cbs.ACC_No = cbm.ACC_No AND cbs.[Period] = cbm.Periode
        WHERE cbs.APPL_NO = :applno AND Curr_code = 'IDR'
    """), {"applno": applno}).fetchone()

    return (saving_row.Saving or 0), True

def _corporate_total_credit(applno):
    row = db.session.execute(text("""
        SELECT SUM(g.CreditAve) AS CreditTrans
        FROM (
            SELECT APPL_NO, Bank, ACC_No, ROUND(ISNULL(SUM(Credit), 0), 0) AS CreditAve
            FROM CAFBANKSTM WITH (NOLOCK)
            WHERE APPL_NO = :applno AND Curr_code = 'IDR'
            GROUP BY APPL_NO, Bank, ACC_No
        ) g
    """), {"applno": applno}).fetchone()
    total_credit = row.CreditTrans or 0

    bank_count_row = db.session.execute(text("""
        SELECT COUNT(DISTINCT Bank) AS cnt FROM CAFBANKSTM WITH (NOLOCK) WHERE APPL_NO = :applno
    """), {"applno": applno}).fetchone()
    bank_count = bank_count_row.cnt or 1

    return round(total_credit / bank_count)

def _net_finance(applno):
    row = db.session.execute(text("""
        SELECT Net_Finance FROM V_NetFinance WITH (NOLOCK) WHERE APPL_NO = :applno
    """), {"applno": applno}).fetchone()
    return row.Net_Finance if row else None

def _classify_bank_stat_amt_corporate(avr_endbal, net_finance):
    if not net_finance:
        return ""
    ratio = (avr_endbal or 0) / net_finance
    if ratio < 1:
        return "3"
    if ratio == 1:
        return "2"
    return "1"

def _estimated_total_asset(applno):
    as_of_row = db.session.execute(text("""
        SELECT TOP 1 FORMAT(ASOF, 'dd MMM yyyy') AS asof FROM CAFCUST_OUTS WITH (NOLOCK)
        WHERE APPL_NO = :applno GROUP BY ASOF ORDER BY ASOF DESC
    """), {"applno": applno}).fetchone()
    as_of = as_of_row.asof if as_of_row else None

    tier_row = db.session.execute(text("""
        SELECT CASE
            WHEN OUTS > 1000000000000 THEN '5'
            WHEN OUTS > 100000000000 THEN '4'
            WHEN OUTS > 10000000000 THEN '3'
            WHEN OUTS > 500000000 THEN '2'
            WHEN OUTS > 50000000 THEN '1'
            ELSE '0' END AS total_asset
        FROM CAFCUST_OUTS WITH (NOLOCK)
        WHERE APPL_NO = :applno
            AND ASOF = (SELECT TOP 1 ASOF
                        FROM CAFCUST_OUTS WITH (NOLOCK)
                        WHERE APPL_NO = :applno
                        GROUP BY ASOF ORDER BY ASOF DESC)
    """), {"applno": applno}).fetchone()

    return as_of, (tier_row.total_asset if tier_row and tier_row.total_asset else "0")

def _survey_corporate_defaults(apless, applno):
    row = db.session.execute(text("""
        SELECT CREDIT_HIS, REF, WORK_EXP, COMP_STS, SCALE, NOTE_CHAR, BUS_LOC, UNIT_OWN, UNIT_FREE,
               DEPOSIT, BANK_STAT, DEPOSIT_AMT, BANK_STAT_AMT, NOTE_CAPITAL, MONTH_PROFIT, NET_PROFIT,
               TOT_CREDIT, NOTE_CAPACITY, DP, PMT, NOTE_COLLATERAL, MONTH_SALES, MONTH_PROFIT_SOURCE,
               MONTH_PROFIT_REMARK,
               IIF(NOTE_SID_CHECKING = '', d.Remarks, NOTE_SID_CHECKING) AS NOTE_SID_CHECKING
        FROM CAFSURV_PT a WITH (NOLOCK)
            LEFT JOIN TEMP_CAFCONT b WITH (NOLOCK) ON a.APPL_NO = b.FINAL_APPL_NO
            LEFT JOIN documentApproval c WITH (NOLOCK) ON b.ApplNo = c.DocumentNumber
            LEFT JOIN documentApprovalHistory d WITH (NOLOCK)
                ON c.id = d.DocumentApprovalId AND d.ApprovalActionCode = 'approve'
        WHERE APPL_NO = :applno
    """), {"applno": applno}).fetchone()

    month_profit = row.MONTH_PROFIT if row else None
    if not month_profit or month_profit <= 0:
        p = db.session.execute(text("""
            SELECT AMOUNT FROM CAFFS WHERE APLESS = :apless AND FS_CODE = 'P' AND ITEM_CODE = '210701'
            ORDER BY ID_CAFFS DESC
        """), {"apless": apless}).fetchone()
        month_profit = p.AMOUNT if p else 0

    month_sales = row.MONTH_SALES if row else None
    if not month_sales or month_sales <= 0:
        s = db.session.execute(text("""
            SELECT AMOUNT FROM CAFFS WHERE APLESS = :apless AND FS_CODE = 'P' AND ITEM_CODE = '210101'
            ORDER BY ID_CAFFS DESC
        """), {"apless": apless}).fetchone()
        month_sales = s.AMOUNT if s else 0

    avg_income = (month_sales or 0) * 12

    stored_business_size = _fetch_business_size(apless)
    if not stored_business_size or stored_business_size == "0":
        business_size = _classify_business_size(avg_income)
        db.session.execute(text(
            "UPDATE CAFLESS SET BUSINESS_SIZE = :size WHERE APLESS = :apless"
        ), {"size": business_size, "apless": apless})
        db.session.commit()
    else:
        business_size = stored_business_size

    work_exp = row.WORK_EXP if row else None
    if not work_exp:
        work_exp = _corporate_work_exp(apless)

    avr_endbal, has_bank_data = _corporate_bank_stats(apless, applno)
    tot_credit = (row.TOT_CREDIT if row else None) or _corporate_total_credit(applno)
    net_finance = _net_finance(applno)
    bank_stat_amt = _classify_bank_stat_amt_corporate(avr_endbal, net_finance)
    if not bank_stat_amt:
        bank_stat_amt = (row.BANK_STAT_AMT if row else None) or ""
    as_of, estimated_asset = _estimated_total_asset(applno)

    return {
        "creditHis": row.CREDIT_HIS if row else "",
        "reference": row.REF if row else "",
        "workExp": str(work_exp) if work_exp else "",
        "companyStatus": row.COMP_STS if row else "",
        "scale": row.SCALE if row else "",
        "businessSize": business_size,
        "noteChar": row.NOTE_CHAR if row else "",
        "businessLocation": row.BUS_LOC if row else "",
        "unitOwned": row.UNIT_OWN if row else "",
        "unitFree": row.UNIT_FREE if row else "",
        "deposit": (row.DEPOSIT == "1") if row else False,
        "bankStat": has_bank_data,
        "bankStatDisabled": has_bank_data,
        "depositAmt": row.DEPOSIT_AMT if row else 0,
        "bankStatAmt": bank_stat_amt,
        "noteCapital": row.NOTE_CAPITAL if row else "",
        "monthProfit": month_profit or 0,
        "monthProfitSource": row.MONTH_PROFIT_SOURCE if row else "",
        "monthProfitSourceOther": row.MONTH_PROFIT_REMARK if row else "",
        "monthSales": month_sales or 0,
        "netProfit": row.NET_PROFIT if row else "",
        "totCredit": tot_credit or 0,
        "noteCapacity": row.NOTE_CAPACITY if row else "",
        "dp": row.DP if row else "",
        "pmt": _resolve_pmt_corporate(row.PMT if row else None, applno),
        "noteCollateral": row.NOTE_COLLATERAL if row else "",
        "noteSid": row.NOTE_SID_CHECKING if row else "",
        "estimatedAsset": estimated_asset,
        "estimatedAssetAsOf": as_of,
    }

def _save_corporate(apless, applno, f):
    exists = db.session.execute(text(
        "SELECT 1 FROM CAFSURV_PT WITH (NOLOCK) WHERE APPL_NO = :applno"
    ), {"applno": applno}).fetchone()

    params = {
        "applno": applno,
        "credit_his": f.get("creditHis") or "", "ref": f.get("reference") or "", "work_exp": f.get("workExp") or "",
        "comp_sts": f.get("companyStatus") or "", "scale": f.get("scale") or "", "note_char": f.get("noteChar") or "",
        "bus_loc": f.get("businessLocation") or "", "unit_own": f.get("unitOwned") or "",
        "unit_free": f.get("unitFree") or "", "deposit": "1" if f.get("deposit") else "0",
        "bank_stat": "1" if f.get("bankStat") else "0", "deposit_amt": _to_number(f.get("depositAmt")),
        "bank_stat_amt": f.get("bankStatAmt") or "", "note_capital": f.get("noteCapital") or "",
        "month_profit": _to_number(f.get("monthProfit")), "net_profit": f.get("netProfit") or "",
        "tot_credit": _to_number(f.get("totCredit")), "note_capacity": f.get("noteCapacity") or "",
        "dp": f.get("dp") or "", "pmt": f.get("pmt") or "", "note_collateral": f.get("noteCollateral") or "",
        "month_sales": _to_number(f.get("monthSales")), "month_profit_source": f.get("monthProfitSource") or "",
        "month_profit_remark": f.get("monthProfitSourceOther") or "", "note_sid": f.get("noteSid") or "",
    }

    if exists:
        db.session.execute(text("""
            UPDATE CAFSURV_PT SET CREDIT_HIS=:credit_his, REF=:ref, WORK_EXP=:work_exp, COMP_STS=:comp_sts,
                SCALE=:scale, NOTE_CHAR=:note_char, BUS_LOC=:bus_loc, UNIT_OWN=:unit_own, UNIT_FREE=:unit_free,
                DEPOSIT=:deposit, BANK_STAT=:bank_stat, DEPOSIT_AMT=:deposit_amt, BANK_STAT_AMT=:bank_stat_amt,
                NOTE_CAPITAL=:note_capital, MONTH_PROFIT=:month_profit, NET_PROFIT=:net_profit, TOT_CREDIT=:tot_credit,
                NOTE_CAPACITY=:note_capacity, DP=:dp, PMT=:pmt, NOTE_COLLATERAL=:note_collateral,
                MONTH_SALES=:month_sales, MONTH_PROFIT_SOURCE=:month_profit_source,
                MONTH_PROFIT_REMARK=:month_profit_remark, NOTE_SID_CHECKING=:note_sid
            WHERE APPL_NO = :applno
        """), params)
    else:
        db.session.execute(text("""
            INSERT INTO CAFSURV_PT (APPL_NO, CREDIT_HIS, REF, WORK_EXP, COMP_STS, SCALE, NOTE_CHAR, BUS_LOC,
                UNIT_OWN, UNIT_FREE, DEPOSIT, BANK_STAT, DEPOSIT_AMT, BANK_STAT_AMT, NOTE_CAPITAL, MONTH_PROFIT,
                NET_PROFIT, TOT_CREDIT, NOTE_CAPACITY, DP, PMT, NOTE_COLLATERAL, MONTH_SALES, MONTH_PROFIT_SOURCE,
                MONTH_PROFIT_REMARK, NOTE_SID_CHECKING)
            VALUES (:applno, :credit_his, :ref, :work_exp, :comp_sts, :scale, :note_char, :bus_loc, :unit_own,
                :unit_free, :deposit, :bank_stat, :deposit_amt, :bank_stat_amt, :note_capital, :month_profit,
                :net_profit, :tot_credit, :note_capacity, :dp, :pmt, :note_collateral, :month_sales,
                :month_profit_source, :month_profit_remark, :note_sid)
        """), params)

    db.session.execute(text(
        "UPDATE CAFLESS SET BUSINESS_SIZE = :business_size WHERE APLESS = :apless"
    ), {"business_size": f.get("businessSize") or "", "apless": apless})

@cam_edit_bp.route("/survey", methods=["GET"])
@login_required
def survey_get():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    ind_cor = request.args.get("indCor", "")
    if not apless or not applno or ind_cor not in ("1", "2"):
        return jsonify({"error": "apless, applno and indCor are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"blocked": True, "message": block_message}), 409

    contsts = _fetch_contract_status(applno)
    show_credit_history = contsts not in (None, "N")
    show_reference = _has_reference(apless)

    cont_row = db.session.execute(text(
        "SELECT L_AMOUNT FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :applno"
    ), {"applno": applno}).fetchone()
    asset_value = cont_row.L_AMOUNT if cont_row else None

    payload = {
        "apless": apless, "applno": applno, "indCor": ind_cor,
        "showCreditHistory": show_credit_history, "showReference": show_reference,
        "lookups": {
            "creditHistory": _CREDIT_HIS_OPTS, "reference": _REF_OPTS, "workExp": _WORK_EXP_OPTS,
            "dp": _DP_OPTS, "sourceOfFund": _fetch_combo("SOURCE_FUND"),
        },
        "individual": None, "corporate": None,
        "sikCheckingDocuments": _fetch_sik_checking_documents(applno),
    }

    if ind_cor == "1":
        payload["lookups"].update({
            "businessSize": _fetch_combo("BUSINESS_SIZE_IND"),
            "livingType": _LIVING_OPTS, "livingStatusHouse": _LIVING_STS_HOUSE_OPTS,
            "livingStatusApartment": _LIVING_STS_APT_OPTS, "carOwnership": _CAR_OWN_OPTS,
            "spouseJob": _JOB_OPTS, "paymentMethod": _PMT_IND_OPTS,
        })
        payload["individual"] = _survey_individual_defaults(apless, applno, asset_value)
    else:
        source_of_fund = [o for o in payload["lookups"]["sourceOfFund"] if o["value"] in ("2", "3", "4")]
        payload["lookups"].update({
            "sourceOfFund": source_of_fund,
            "businessSize": _fetch_combo("BUSINESS_SIZE"),
            "companyStatus": _COMP_STS_OPTS, "businessScale": _SCALE_OPTS,
            "businessLocation": _BUS_LOC_OPTS, "unitOwned": _UNIT_OWN_OPTS,
            "unitFree": _UNIT_FREE_OPTS, "netProfitRatio": _NET_PROFIT_OPTS,
            "estimatedAsset": _fetch_combo("ESTIMATED_ASSET"), "paymentMethod": _PMT_CORP_OPTS,
        })
        payload["corporate"] = _survey_corporate_defaults(apless, applno)

    return jsonify(payload)

def _persist_survey(data):
    apless = data.get("apless", "")
    applno = data.get("applno", "")
    ind_cor = data.get("indCor", "")
    if not apless or not applno or ind_cor not in ("1", "2"):
        return jsonify({"success": False, "message": "apless, applno and indCor are required"}), 400

    try:
        if ind_cor == "1":
            _save_individual(apless, applno, data.get("individual") or {})
        else:
            _save_corporate(apless, applno, data.get("corporate") or {})
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to save survey for applno=%s", applno)
        return jsonify({"success": False, "message": "Failed to save survey."}), 500

    return jsonify({"success": True, "apless": apless, "applno": applno})

@cam_edit_bp.route("/survey/save", methods=["POST"])
@login_required
def survey_save():
    return _persist_survey(request.get_json(force=True) or {})

@cam_edit_bp.route("/survey/next", methods=["POST"])
@login_required
def survey_next():
    return _persist_survey(request.get_json(force=True) or {})

CLAUSE_NAMES = ["SRCC", "EQ", "FW", "AW", "COM", "TS"]

_PAY_METHOD_CASH_AND_CREDIT = [{"value": "1", "label": "Cash"}, {"value": "3", "label": "Credit"}]
_PAY_METHOD_CREDIT_ONLY = [{"value": "3", "label": "Credit"}]

_INSTALLMENT_PERCENT_BY_YEAR = {1: 1, 2: 0.85, 3: 0.75, 4: 0.7, 5: 0.7}

_SURVEY_CAP_BY_FIN_TYPE = {"I": 2_500_000, "S": 3_500_000}

_SELF_INSURED = "Self Insured"

def _ins_str(value):
    if value is None:
        return ""
    return str(value).strip()

def _ins_raw(value):
    if value is None:
        return ""
    return str(value)

def _ins_year(value):
    return int(fff.to_float(value, 0.0))

def _ins_default_amount(l_amount, year_no):
    percent = _INSTALLMENT_PERCENT_BY_YEAR.get(year_no, 0)
    return fff.php_round(fff.to_float(l_amount) * percent, 0)

def _ins_select_value(current, options):
    if not options:
        return ""
    current_text = _ins_str(current)
    for option in options:
        if _ins_str(option) == current_text:
            return current_text
    return _ins_str(options[0])

def _fetch_contract_context(applno, apless):
    row = db.session.execute(text("""
        SELECT YEAR(CREATE_DATE) AS year_cam, L_TYPE, TENOR1000, TENOR
        FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :applno
    """), {"applno": applno}).fetchone()

    if not row:
        return None

    year_cam = row.year_cam if row.year_cam not in (None, "") else pydt.date.today().year

    l_type = _ins_str(row.L_TYPE)
    if l_type == "4":
        jlh_year = math.ceil(fff.to_float(row.TENOR1000) / 12)
    else:
        jlh_year = math.ceil(fff.to_float(row.TENOR) / 12)
    jlh_year = int(jlh_year)

    equip = db.session.execute(text("""
        SELECT CONDITION, TAHUN FROM CAFEQUIP WITH (NOLOCK) WHERE APPL_NO = :applno
    """), {"applno": applno}).fetchone()

    percentage_row = db.session.execute(text("""
        SELECT CAST([Percentage] AS FLOAT) AS pct FROM COMM_PARTY WITH (NOLOCK) WHERE APPL_NO = :applno
    """), {"applno": applno}).fetchone()
    percentage = percentage_row.pct if (percentage_row and percentage_row.pct) else 17.5

    amount_row = db.session.execute(text("""
        SELECT L_AMOUNT FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :applno AND APLESS = :apless
    """), {"applno": applno, "apless": apless}).fetchone()

    rounding_row = db.session.execute(text("""
        SELECT a.ROUNDING FROM UMFCURR a WITH (NOLOCK)
        INNER JOIN CAFCONT b WITH (NOLOCK) ON a.CURR_CODE = b.CURR_CODE
        WHERE b.APPL_NO = :applno
    """), {"applno": applno}).fetchone()

    return {
        "year_cam": _ins_year(year_cam),
        "l_type": l_type,
        "jlh_year": jlh_year,
        "l_amount": fff.to_float(amount_row.L_AMOUNT) if amount_row else 0.0,
        "percentage": fff.to_float(percentage),
        "rounding": (rounding_row.ROUNDING if rounding_row else 1) or 1,
        "year_car": _ins_year(equip.TAHUN if equip else None),
        "condition": _ins_raw(equip.CONDITION if equip else None),
    }

def _condition_label(condition):
    return "New" if _ins_str(condition).upper() == "NEW" else "Used"

def _fetch_companies():
    rows = db.session.execute(text("""
        SELECT INS_CD, INS_CO FROM UMFINSCD WITH (NOLOCK)
        WHERE INS_CD IN ('01', '02') ORDER BY INS_CO, INS_CD DESC
    """)).fetchall()
    options = []
    previous = ""
    for row in rows:
        name = _ins_str(row.INS_CO)
        if previous.lower() != name.lower():
            options.append({"value": _ins_str(row.INS_CD), "label": name})
            previous = name
    return options

def _fetch_insurance_co_name(ins_cd):
    row = db.session.execute(text("""
        SELECT LTRIM(RTRIM(INS_CO)) AS INS_CO FROM UMFINSCD WITH (NOLOCK) WHERE INS_CD = :ins_cd
    """), {"ins_cd": ins_cd}).fetchone()
    return _ins_str(row.INS_CO) if row else ""

def _fetch_models():
    rows = db.session.execute(text("""
        SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH (NOLOCK)
        WHERE CAT_VALUE = 'MODEL_ASURANSI' ORDER BY DESC_VALUE
    """)).fetchall()
    return [{"value": _ins_str(r.VALUE), "label": _ins_str(r.DESC_VALUE)} for r in rows]

def _fetch_insurance_areas(fin_type):
    if fin_type == "W":
        return [], True
    rows = db.session.execute(text("SELECT Code, Name FROM MSTINSURANCEAREA WITH (NOLOCK)")).fetchall()
    return [{"value": _ins_str(r.Code), "label": _ins_str(r.Name)} for r in rows], False

def _fetch_tpl_options(ins_cd, model):
    rows = db.session.execute(text("""
        SELECT TPL_AMT FROM CLFINSTPL WITH (NOLOCK)
        WHERE INS_CD = :ins_cd AND MODEL = :model ORDER BY TPL_AMT
    """), {"ins_cd": ins_cd, "model": model}).fetchall()
    return [_ins_str(r.TPL_AMT) for r in rows]

def _fetch_tlo_options(ins_cd, year_cam, year_car):
    age = _ins_year(year_cam) - _ins_year(year_car)
    if 3 < age <= 5 and _ins_str(ins_cd) == "02":
        sql = "SELECT CODE, NAME FROM mstTLOAR WITH (NOLOCK) WHERE CODE IN ('0','1','5')"
    elif age > 5:
        sql = "SELECT CODE, NAME FROM mstTLOAR WITH (NOLOCK) WHERE CODE IN ('0','1','4')"
    else:
        sql = "SELECT CODE, NAME FROM mstTLOAR WITH (NOLOCK) WHERE CODE <= '2'"
    rows = db.session.execute(text(sql)).fetchall()
    return [{"value": _ins_str(r.CODE), "label": _ins_str(r.NAME)} for r in rows]

def _fetch_clause_codes_for_row(ins_cd, tlo_ar, bpkb_area):
    locked = _ins_str(tlo_ar) == "0"
    if locked:
        rows = db.session.execute(text("""
            SELECT DISTINCT xx.CLAUSE, cc.name
            FROM CLFINSCLA xx WITH (NOLOCK)
                INNER JOIN mstCLAUSE cc WITH (NOLOCK) ON cc.code = xx.CLAUSE
            WHERE xx.INS_CD = :ins_cd AND xx.Insurance_Area = :area
        """), {"ins_cd": ins_cd, "area": bpkb_area}).fetchall()
    else:
        rows = db.session.execute(text("""
            SELECT DISTINCT xx.CLAUSE, cc.name
            FROM CLFINSCLA xx WITH (NOLOCK)
                INNER JOIN mstCLAUSE cc WITH (NOLOCK) ON cc.code = xx.CLAUSE
            WHERE xx.INS_CD = :ins_cd AND xx.TLO_AR = :tlo_ar AND xx.Insurance_Area = :area
        """), {"ins_cd": ins_cd, "tlo_ar": tlo_ar, "area": bpkb_area}).fetchall()

    codes = {}
    for row in rows:
        name = _ins_str(row.name)
        if name in CLAUSE_NAMES:
            codes[name] = _ins_str(row.CLAUSE)
    return codes, locked

def _fetch_subsidy_sums(applno):
    def _sum(amount_type):
        row = db.session.execute(text("""
            SELECT SUM(Amount) AS jumlah
            FROM CAFCONT a WITH (NOLOCK)
                INNER JOIN CafcontSubsidyDetail b WITH (NOLOCK) ON a.APPL_NO = b.APPL_No
            WHERE a.APPL_NO = :applno AND b.AmountType = :amount_type
        """), {"applno": applno, "amount_type": amount_type}).fetchone()
        return fff.to_float(row.jumlah if row else 0)

    return {
        "survey": _sum("Survey"),
        "provision": _sum("Provision"),
        "interest": _sum("Interest"),
        "survey_fee2": _sum("SurveyFee2"),
    }

def _fetch_cafcont_rates(applno):
    row = db.session.execute(text("""
        SELECT PROVISION, Admfee, BaseAdmFee, BaseInterestFee, InterestIncome, Max_Fee
        FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :applno
    """), {"applno": applno}).fetchone()
    if not row:
        return {"mlci_rent": 0.0, "rental": 0.0, "surv_inc": 0.0, "prov_inc": 0.0, "base_surv": 0.0, "max_fee": 0.0}
    return {
        "mlci_rent": fff.to_float(row.BaseInterestFee),
        "rental": fff.to_float(row.InterestIncome),
        "surv_inc": fff.to_float(row.Admfee),
        "prov_inc": fff.to_float(row.PROVISION),
        "base_surv": fff.to_float(row.BaseAdmFee),
        "max_fee": fff.to_float(row.Max_Fee),
    }

def _fetch_cigna_fee_and_base_rate(applno):
    row = db.session.execute(text("""
        SELECT Survey_Fee_Cigna, Survey_Base_Rate_Cigna FROM cigna_fee WITH (NOLOCK) WHERE APPL_NO = :applno
    """), {"applno": applno}).fetchone()
    if not row:
        return 0.0, 0.0
    return fff.to_float(row.Survey_Fee_Cigna), fff.to_float(row.Survey_Base_Rate_Cigna)

def _fetch_disb(applno):
    row = db.session.execute(text("""
        SELECT GROSS_PREM, NET_COM FROM CAFDISB WITH (NOLOCK) WHERE APPL_NO = :applno
    """), {"applno": applno}).fetchone()
    if not row:
        return 0.0, 0.0
    return fff.to_float(row.GROSS_PREM), fff.to_float(row.NET_COM)

def _compute_income_summary(applno, fin_type, percentage, gross_prem, net_com, eligible_comm=None):
    sums = _fetch_subsidy_sums(applno)
    rates = _fetch_cafcont_rates(applno)
    surv_inc2, base_surv2 = _fetch_cigna_fee_and_base_rate(applno)

    ttl_income = gross_prem - net_com
    ttl_income_net = ttl_income
    ttl_sub_inc_net = ttl_income_net
    exec_inc = ttl_income - 0
    subsidy_total = sums["survey"] + sums["provision"] + sums["interest"] + sums["survey_fee2"]

    ttl_int = rates["rental"] + sums["interest"]
    exc_int = ttl_int - rates["mlci_rent"]
    ttl_surv = rates["surv_inc"] + sums["survey"]
    ttl_surv2 = surv_inc2 + sums["survey_fee2"]
    exce_surv = ttl_surv - rates["base_surv"]
    exce_surv2 = ttl_surv2 - base_surv2
    ttl_prov = rates["prov_inc"] + sums["provision"]
    prov_exec = ttl_prov

    cap = _SURVEY_CAP_BY_FIN_TYPE.get(fin_type)
    if cap is not None and ttl_surv >= cap:
        ttl_surv = cap

    ttl_sub_tot = ttl_surv + ttl_prov + ttl_int + ttl_sub_inc_net + ttl_surv2
    ttl_exc_tot = exce_surv + prov_exec + exc_int + exec_inc + exce_surv2
    max_comm = ttl_sub_tot * percentage / 100

    if eligible_comm is None:
        eligible_comm = rates["max_fee"]

    marketing_fees = eligible_comm - fff.php_round(max_comm, 0)
    marketing_fee = 0.0 if eligible_comm <= max_comm else marketing_fees

    return {
        "ttlIncome": ttl_income,
        "ttlIncomeNet": ttl_income_net,
        "ttlSubIncNet": ttl_sub_inc_net,
        "baseInc": 0,
        "execInc": exec_inc,
        "survInc": rates["surv_inc"],
        "subSurv": sums["survey"],
        "ttlSurv": ttl_surv,
        "baseSurv": rates["base_surv"],
        "exceSurv": exce_surv,
        "survInc2": surv_inc2,
        "subSurv2": sums["survey_fee2"],
        "ttlSurv2": ttl_surv2,
        "baseSurv2": base_surv2,
        "exceSurv2": exce_surv2,
        "provInc": rates["prov_inc"],
        "subProv": sums["provision"],
        "ttlProv": ttl_prov,
        "provBase": 0,
        "provExec": prov_exec,
        "interestIncome": rates["rental"],
        "subInt": sums["interest"],
        "ttlInt": ttl_int,
        "baseInterest": rates["mlci_rent"],
        "excInt": exc_int,
        "subsidyTotal": subsidy_total,
        "ttlSubTot": ttl_sub_tot,
        "ttlExcTot": ttl_exc_tot,
        "maxComm": max_comm,
        "percentage": percentage,
        "eligibleComm": eligible_comm,
        "marketingFee": marketing_fee,
    }

def _fetch_existing_policy(applno):
    return db.session.execute(text("""
        SELECT a.INS_POL, a.INS_CD, a.PAY_METHOD, a.MODEL, a.Condition, a.Total_Seat, b.INSURANCE_AREA
        FROM CAFINSU a WITH (NOLOCK) INNER JOIN CAFEQUIP b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
        WHERE a.APPL_NO = :applno
    """), {"applno": applno}).fetchone()

def _fetch_existing_rows(ins_pol, jlh_year, l_amount):
    stored = {}
    if ins_pol:
        results = db.session.execute(text("""
            SELECT INS_AMT, YEAR_NO, TPL_AMT, TLO_AR, PRER_AMT, PREP_AMT, Rate_Premi, Rate_Premicla
            FROM CAFINSUD WITH (NOLOCK) WHERE INS_POL = :ins_pol ORDER BY YEAR_NO
        """), {"ins_pol": ins_pol}).fetchall()
        for r in results:
            stored[_ins_year(r.YEAR_NO)] = {
                "tplAmt": _ins_str(r.TPL_AMT),
                "tloAr": _ins_str(r.TLO_AR),
                "prerAmt": fff.php_round(fff.to_float(r.PRER_AMT), 0),
                "prepAmt": fff.php_round(fff.to_float(r.PREP_AMT), 0),
                "savePremi": fff.to_float(r.Rate_Premi),
                "savePremicla": fff.to_float(r.Rate_Premicla),
            }

    rows = []
    for year_no in range(1, jlh_year + 1):
        saved = stored.get(year_no)
        rows.append({
            "year": year_no,
            "insAmt": _ins_default_amount(l_amount, year_no),
            "tplAmt": saved["tplAmt"] if saved else "",
            "tloAr": saved["tloAr"] if saved else "",
            "prerAmt": saved["prerAmt"] if saved else "",
            "prepAmt": saved["prepAmt"] if saved else "",
            "savePremi": saved["savePremi"] if saved else "",
            "savePremicla": saved["savePremicla"] if saved else "",
        })
    return rows

def _fetch_existing_clauses(applno, ins_pol, jlh_year):
    selected_by_year = {year_no: {} for year_no in range(1, jlh_year + 1)}
    if not ins_pol:
        return selected_by_year
    rows = db.session.execute(text("""
        SELECT xx.Year_No, xx.Clause, cc.name
        FROM CAFINSUD_Clause xx WITH (NOLOCK)
            INNER JOIN mstCLAUSE cc WITH (NOLOCK) ON cc.code = xx.Clause
        WHERE xx.INS_POL = :ins_pol AND xx.Appl_No = :applno
        ORDER BY xx.Year_No
    """), {"ins_pol": ins_pol, "applno": applno}).fetchall()
    for row in rows:
        year_no = _ins_year(row.Year_No)
        name = _ins_str(row.name)
        clause = _ins_str(row.Clause)
        if year_no in selected_by_year and name in CLAUSE_NAMES and clause in ("1", "2", "3", "4", "5", "6"):
            selected_by_year[year_no][name] = clause
    return selected_by_year

def _apply_row_lookups(rows, ins_cd, model, bpkb_area, tlo_options, clauses_by_year=None):
    tpl_options = _fetch_tpl_options(ins_cd, model)
    tlo_values = [option["value"] for option in tlo_options]

    for row in rows:
        clause_codes, clause_locked = _fetch_clause_codes_for_row(ins_cd, row.get("tloAr", ""), bpkb_area)
        row["tplAmt"] = _ins_select_value(row.get("tplAmt", ""), tpl_options)
        row["tloAr"] = _ins_select_value(row.get("tloAr", ""), tlo_values)
        row["clauseCodes"] = clause_codes
        row["clauseLocked"] = clause_locked

        if clauses_by_year is None:
            selected = row.get("clauseSelected") or {}
        else:
            selected = clauses_by_year.get(row.get("year"), {})
        row["clauseSelected"] = {
            name: code for name, code in selected.items()
            if name in clause_codes and _ins_str(code) == clause_codes[name]
        }

    return tpl_options

@cam_edit_bp.route("/insurance", methods=["GET"])
@login_required
def insurance_get():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    fin_type = request.args.get("finType", "")
    ins_loan = request.args.get("insLoan", "")
    credit_amt = _to_number(request.args.get("creditAmt", 0))

    if not apless or not applno:
        return jsonify({"error": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"blocked": True, "message": block_message}), 409

    ctx = _fetch_contract_context(applno, apless)
    if not ctx:
        return jsonify({"error": "Contract not found"}), 404

    branch_cd = _session_str("branchcode")

    existing = _fetch_existing_policy(applno)
    ins_pol = _ins_str(existing.INS_POL) if existing else ""
    ins_cd = _ins_str(existing.INS_CD) if existing else ""
    has_policy = bool(ins_cd and ins_pol)

    bpkb_area = _ins_str(existing.INSURANCE_AREA) if existing else ""
    if not bpkb_area:
        bpkb_area = "2"
    if branch_cd == "101":
        bpkb_area = "2"

    if has_policy:
        pay_method = _ins_str(existing.PAY_METHOD)
        model = _ins_str(existing.MODEL)
        condition = _ins_raw(existing.Condition)
        total_seat = _ins_str(existing.Total_Seat)
    else:
        ins_cd = ""
        pay_method = "3" if credit_amt > 0 else "1"
        model = ""
        condition = ctx["condition"]
        total_seat = ""

    rows = _fetch_existing_rows(ins_pol if has_policy else "", ctx["jlh_year"], ctx["l_amount"])
    clauses_by_year = _fetch_existing_clauses(applno, ins_pol if has_policy else "", ctx["jlh_year"])

    tlo_options = _fetch_tlo_options(ins_cd, ctx["year_cam"], ctx["year_car"])
    area_options, area_disabled = _fetch_insurance_areas(fin_type)
    tpl_options = _apply_row_lookups(rows, ins_cd, model, bpkb_area, tlo_options, clauses_by_year)

    gross_prem, net_com = _fetch_disb(applno)
    income_summary = _compute_income_summary(applno, fin_type, ctx["percentage"], gross_prem, net_com)

    return jsonify({
        "insPol": ins_pol,
        "insCd": ins_cd,
        "payMethod": pay_method,
        "payMethodOptions": _PAY_METHOD_CREDIT_ONLY if _ins_str(ins_loan) not in ("", "0") else _PAY_METHOD_CASH_AND_CREDIT,
        "payMethodLocked": credit_amt > 0,
        "model": model,
        "condition": condition,
        "conditionLabel": _condition_label(ctx["condition"]),
        "equipCondition": ctx["condition"],
        "bpkbArea": bpkb_area,
        "branchCd": branch_cd,
        "insuranceAreaOptions": area_options,
        "insuranceAreaDisabled": area_disabled,
        "totalSeat": total_seat,
        "grossPrem": gross_prem,
        "netCom": net_com,
        "jlhYear": ctx["jlh_year"],
        "rows": rows,
        "companies": _fetch_companies(),
        "models": _fetch_models(),
        "tplOptions": tpl_options,
        "tloOptions": tlo_options,
        "incomeSummary": income_summary,
        "clauseNames": CLAUSE_NAMES,
    })

@cam_edit_bp.route("/insurance/lookups", methods=["POST"])
@login_required
def insurance_lookups():
    payload = request.get_json(force=True) or {}
    applno = payload.get("applno", "")
    apless = payload.get("apless", "")
    ins_cd = payload.get("insCd", "")
    model = payload.get("model", "")
    bpkb_area = payload.get("bpkbArea", "")
    rows = [dict(row) for row in (payload.get("rows") or [])]

    ctx = _fetch_contract_context(applno, apless) or {"year_cam": 0, "year_car": 0}

    tlo_options = _fetch_tlo_options(ins_cd, ctx.get("year_cam"), ctx.get("year_car"))
    tpl_options = _apply_row_lookups(rows, ins_cd, model, bpkb_area, tlo_options)

    return jsonify({
        "tplOptions": tpl_options,
        "tloOptions": tlo_options,
        "rows": [{
            "year": row.get("year"),
            "tplAmt": row.get("tplAmt", ""),
            "tloAr": row.get("tloAr", ""),
            "clauseCodes": row.get("clauseCodes", {}),
            "clauseLocked": row.get("clauseLocked", False),
            "clauseSelected": row.get("clauseSelected", {}),
        } for row in rows],
    })

@cam_edit_bp.route("/insurance/calculate", methods=["POST"])
@login_required
def insurance_calculate():
    payload = request.get_json(force=True) or {}
    applno = payload.get("applno", "")
    apless = payload.get("apless", "")
    fin_type = payload.get("finType", "")
    ins_cd = payload.get("insCd", "")
    model = payload.get("model", "")
    bpkb_area = payload.get("bpkbArea", "")
    rows_in = [dict(row) for row in (payload.get("rows") or [])]

    if not applno or not apless:
        return jsonify({"error": "apless and applno are required"}), 400

    ctx = _fetch_contract_context(applno, apless)
    if not ctx:
        return jsonify({"error": "Contract not found"}), 404

    try:
        stamp_duty_row = db.session.execute(text("""
            SELECT Stamp_Duty FROM UMFINSCD WITH (NOLOCK) WHERE INS_CD = :ins_cd
        """), {"ins_cd": ins_cd}).fetchone()
        stamp_duty_year1 = fff.to_float(stamp_duty_row.Stamp_Duty) if stamp_duty_row else 0.0

        gross_prem = 0.0
        net_com = 0.0
        rows_out = []

        for row in rows_in:
            year_no = _ins_year(row.get("year"))
            ins_amt = fff.to_float(row.get("insAmt"))
            tpl_amt = _ins_str(row.get("tplAmt"))
            tlo_ar = _ins_str(row.get("tloAr"))
            clause_selected = row.get("clauseSelected") or {}

            pre_row = db.session.execute(text("""
                SELECT TOP 1 NET_PREMI, PREMI FROM CLFINSPRE WITH (NOLOCK)
                WHERE INS_CD = :ins_cd AND MODEL = :model AND TLO_AR = :tlo_ar
                  AND L_AMOUNT <= :ins_amt AND Insurance_Area = :area
                ORDER BY L_AMOUNT DESC
            """), {"ins_cd": ins_cd, "model": model, "tlo_ar": tlo_ar,
                   "ins_amt": ins_amt, "area": bpkb_area}).fetchone()
            net_premi = fff.to_float(pre_row.NET_PREMI) if pre_row else 0.0
            premi = fff.to_float(pre_row.PREMI) if pre_row else 0.0

            net_premicla = 0.0
            premicla = 0.0
            for name in CLAUSE_NAMES:
                code = _ins_str(clause_selected.get(name))
                if code == "":
                    continue
                cla_row = db.session.execute(text("""
                    SELECT PREMI, NET_PREMI FROM CLFINSCLA WITH (NOLOCK)
                    WHERE INS_CD = :ins_cd AND TLO_AR = :tlo_ar AND Insurance_Area = :area AND CLAUSE = :clause
                """), {"ins_cd": ins_cd, "tlo_ar": tlo_ar, "area": bpkb_area, "clause": code}).fetchone()
                if cla_row:
                    net_premicla += fff.to_float(cla_row.NET_PREMI)
                    premicla += fff.to_float(cla_row.PREMI)

            tpl_row = db.session.execute(text("""
                SELECT TPL_FEE2, TPL_FEE FROM CLFINSTPL WITH (NOLOCK)
                WHERE INS_CD = :ins_cd AND MODEL = :model AND TPL_AMT = :tpl_amt
            """), {"ins_cd": ins_cd, "model": model, "tpl_amt": tpl_amt}).fetchone()
            tpl_fee2 = fff.to_float(tpl_row.TPL_FEE2) if tpl_row else 0.0
            tpl_fee = fff.to_float(tpl_row.TPL_FEE) if tpl_row else 0.0

            stamp_duty = stamp_duty_year1 if year_no == 1 else 0.0

            prer_raw = fff.pembulatan((ins_amt * ((premi + premicla) / 100)) + tpl_fee2 + stamp_duty, ctx["rounding"])
            prep_raw = (ins_amt * ((net_premi + net_premicla) / 100)) + tpl_fee + stamp_duty

            gross_prem += prer_raw
            net_com += prep_raw

            rows_out.append({
                "year": year_no,
                "prerAmt": fff.php_round(prer_raw, 0),
                "prepAmt": fff.php_round(prep_raw, 0),
                "savePremi": premi,
                "savePremicla": premicla,
            })

        posted_eligible_comm = fff.to_float(payload.get("eligibleComm"))
        db.session.execute(text(
            "UPDATE CAFCONT SET Max_Fee = :max_fee WHERE APPL_NO = :applno"
        ), {"max_fee": posted_eligible_comm, "applno": applno})
        db.session.commit()

        income_summary = _compute_income_summary(applno, fin_type, ctx["percentage"], gross_prem, net_com)
        max_comm = income_summary["maxComm"]
        marketing_fees = max_comm - fff.php_round(max_comm, 0)
        income_summary["eligibleComm"] = max_comm
        income_summary["marketingFee"] = 0.0 if marketing_fees < 0 else marketing_fees
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Failed to calculate insurance for applno=%s", applno)
        return jsonify({"error": f"Calculation failed: {type(exc).__name__}: {exc}"}), 500

    return jsonify({
        "grossPrem": fff.php_round(gross_prem, 0),
        "netCom": fff.php_round(net_com, 0),
        "rows": rows_out,
        "incomeSummary": income_summary,
    })

@cam_edit_bp.route("/insurance/next", methods=["POST"])
@login_required
def insurance_next():
    payload = request.get_json(force=True) or {}
    applno = payload.get("applno", "")
    apless = payload.get("apless", "")

    if not applno or not apless:
        return jsonify({"success": False, "message": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"success": False, "message": block_message}), 409

    ins_cd = _ins_str(payload.get("insCd"))
    pay_method = _ins_str(payload.get("payMethod"))
    model = _ins_str(payload.get("model"))
    condition = _ins_raw(payload.get("condition"))
    bpkb_area = _ins_str(payload.get("bpkbArea"))
    total_seat = _ins_str(payload.get("totalSeat"))
    rows = [dict(row) for row in (payload.get("rows") or [])]

    eligible_comm = fff.to_float(payload.get("eligibleComm"))
    ttl_sub_tot = fff.to_float(payload.get("ttlSubTot"))
    max_comm = fff.to_float(payload.get("maxComm"))
    gross_prem = fff.to_float(payload.get("grossPrem"))
    net_com = fff.to_float(payload.get("netCom"))

    messages = []
    if ins_cd == "":
        messages.append("Ins. Company must not empty")
    if pay_method == "":
        messages.append("Pay Method must not empty")
    if model == "":
        messages.append("Model must not empty")
    if _ins_str(condition) == "":
        messages.append("Condition must not empty")
    if bpkb_area == "":
        messages.append("Insurance Area must not empty")

    if _fetch_insurance_co_name(ins_cd) != _SELF_INSURED:
        for row in rows:
            year_no = _ins_year(row.get("year"))
            if _ins_str(row.get("insAmt")) == "":
                messages.append(f"Insurance Amount Year {year_no} must not empty")
            if _ins_str(row.get("tloAr")) == "":
                messages.append(f"TLP CP Year {year_no} must not empty")
            if _ins_str(row.get("prerAmt")) == "":
                messages.append(f"Premium Receive Year {year_no} must not empty")
            if _ins_str(row.get("prepAmt")) == "":
                messages.append(f"Premium Payment Year {year_no} must not empty")

    equip_row = db.session.execute(text("""
        SELECT TAHUN, karoseri_supp, ACCESSORIES_SUPP, OTHER_SUPP
        FROM CAFEQUIP WITH (NOLOCK) WHERE APPL_NO = :applno
    """), {"applno": applno}).fetchone()
    if not equip_row or _ins_str(equip_row.TAHUN) == "":
        messages.append("Year in equipment must not empty")

    try:
        max_fee_row = db.session.execute(text(
            "SELECT Max_Fee FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :applno"
        ), {"applno": applno}).fetchone()
        current_max_fee = fff.to_float(max_fee_row.Max_Fee) if max_fee_row else 0.0
        if eligible_comm != current_max_fee:
            db.session.execute(text("DELETE FROM CAFKOMIS WHERE APPL_NO = :applno"), {"applno": applno})
            db.session.execute(text("DELETE FROM CafkomisACC WHERE APPL_NO = :applno"), {"applno": applno})
            db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to clear commission rows for applno=%s", applno)

    if messages:
        return jsonify({"success": False, "message": "<br>".join(messages)})

    ins_pol_row = db.session.execute(text(
        "SELECT INS_POL FROM CAFINSU WITH (NOLOCK) WHERE APPL_NO = :applno"
    ), {"applno": applno}).fetchone()
    ins_pol = _ins_str(ins_pol_row.INS_POL) if ins_pol_row else ""
    if ins_pol == "":
        return jsonify({"success": False, "message": "No insurance policy found for this application."}), 404

    try:
        db.session.execute(text("""
            UPDATE CAFINSU SET INS_CD = :ins_cd, PAY_METHOD = :pay_method, MODEL = :model,
                Condition = :condition, Total_Seat = :total_seat WHERE APPL_NO = :applno
        """), {"ins_cd": ins_cd, "pay_method": pay_method, "model": model, "condition": condition,
               "total_seat": total_seat, "applno": applno})
        db.session.execute(text(
            "UPDATE CAFEQUIP SET INSURANCE_AREA = :area WHERE APPL_NO = :applno"
        ), {"area": bpkb_area, "applno": applno})

        db.session.execute(text(
            "DELETE FROM CAFINSUD_Clause WHERE Appl_No = :applno AND Ins_Pol = :ins_pol"
        ), {"applno": applno, "ins_pol": ins_pol})
        db.session.execute(text("DELETE FROM CAFINSUD WHERE INS_POL = :ins_pol"), {"ins_pol": ins_pol})

        for row in rows:
            year_no = _ins_year(row.get("year"))
            db.session.execute(text("""
                INSERT INTO CAFINSUD (INS_POL, INS_AMT, YEAR_NO, TPL_AMT, TLO_AR, PRER_AMT, PREP_AMT,
                    Rate_Premi, Rate_Premicla)
                VALUES (:ins_pol, :ins_amt, :year_no, :tpl_amt, :tlo_ar, :prer_amt, :prep_amt,
                    :save_premi, :save_premicla)
            """), {
                "ins_pol": ins_pol,
                "ins_amt": fff.to_float(row.get("insAmt")),
                "year_no": year_no,
                "tpl_amt": _ins_str(row.get("tplAmt")),
                "tlo_ar": _ins_str(row.get("tloAr")),
                "prer_amt": fff.to_float(row.get("prerAmt")),
                "prep_amt": fff.to_float(row.get("prepAmt")),
                "save_premi": fff.to_float(row.get("savePremi")),
                "save_premicla": fff.to_float(row.get("savePremicla")),
            })

            clause_selected = row.get("clauseSelected") or {}
            for name in CLAUSE_NAMES:
                code = _ins_str(clause_selected.get(name))
                if code == "":
                    continue
                db.session.execute(text("""
                    INSERT INTO CAFINSUD_Clause (Appl_No, Ins_Pol, Year_No, Clause)
                    VALUES (:applno, :ins_pol, :year_no, :clause)
                """), {"applno": applno, "ins_pol": ins_pol, "year_no": year_no, "clause": code})

        db.session.execute(text("""
            UPDATE CAFINSUD_Clause SET Premi = d.PREMI
            FROM CAFINSUD_Clause a
                LEFT JOIN cafinsu b ON a.Ins_Pol = b.INS_POL AND a.Appl_No = b.APPL_NO
                LEFT JOIN cafinsud c ON a.Ins_Pol = c.INS_POL AND a.Year_No = c.YEAR_NO
                LEFT JOIN cafequip e ON a.Appl_No = e.APPL_NO
                LEFT JOIN CLFINSCLA d ON b.INS_CD = d.INS_CD AND e.INSURANCE_AREA = d.Insurance_Area
                    AND c.TLO_AR = d.TLO_AR AND a.Clause = d.CLAUSE
            WHERE a.APPL_NO = :applno AND a.Ins_Pol = :ins_pol
        """), {"applno": applno, "ins_pol": ins_pol})

        disb_exists = db.session.execute(text(
            "SELECT 1 FROM CAFDISB WITH (NOLOCK) WHERE APPL_NO = :applno"
        ), {"applno": applno}).fetchone()

        if disb_exists:
            db.session.execute(text(
                "UPDATE CAFDISB SET GROSS_PREM = :gross_prem, NET_COM = :net_com WHERE APPL_NO = :applno"
            ), {"gross_prem": gross_prem, "net_com": net_com, "applno": applno})
        else:
            splits = []
            if _ins_str(equip_row.karoseri_supp) != "":
                splits.append("Karoseri")
            if _ins_str(equip_row.ACCESSORIES_SUPP) != "":
                splits.append("Accessories")
            if _ins_str(equip_row.OTHER_SUPP) != "":
                splits.append("Others")
            splits.append("Dealer")
            for split_label in splits:
                db.session.execute(text("""
                    INSERT INTO CAFDISB (APPL_NO, GROSS_PREM, NET_COM, DISB_INSC, SPLIT)
                    VALUES (:applno, :gross_prem, :net_com, NULL, :split_label)
                """), {"applno": applno, "gross_prem": gross_prem, "net_com": net_com,
                       "split_label": split_label})

        db.session.execute(text(
            "UPDATE CAFCONT SET Max_Fee = :max_fee WHERE APPL_NO = :applno AND APLESS = :apless"
        ), {"max_fee": eligible_comm, "applno": applno, "apless": apless})

        comm_exists = db.session.execute(text(
            "SELECT 1 FROM COMM_PARTY WITH (NOLOCK) WHERE APPL_NO = :applno"
        ), {"applno": applno}).fetchone()
        if comm_exists:
            db.session.execute(text(
                "UPDATE COMM_PARTY SET TOTAL_INCOME = :ttl_sub_tot, COMM_THIRDPARTY = :max_comm WHERE APPL_NO = :applno"
            ), {"ttl_sub_tot": ttl_sub_tot, "max_comm": max_comm, "applno": applno})
        else:
            db.session.execute(text(
                "INSERT INTO COMM_PARTY (appl_no, TOTAL_INCOME, COMM_THIRDPARTY) VALUES (:applno, :ttl_sub_tot, :max_comm)"
            ), {"applno": applno, "ttl_sub_tot": ttl_sub_tot, "max_comm": max_comm})

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to save insurance for applno=%s", applno)
        return jsonify({"success": False, "message": "Failed to save. Please try again."}), 500

    return jsonify({"success": True, "apless": apless, "applno": applno})

SPLIT_LABELS = ["Dealer", "Karoseri", "Accessories", "Others"]
_APPROVAL_LOCK_MESSAGE = (
    "Disbursement cannot be changed, because your bank account is on approval at Operation "
    "Admin (OA). Please contact OA for Approve or Reject CAM."
)

def _fetch_approval_lock(applno):
    row = db.session.execute(text("""
        SELECT TOP 1 APPR_STS, APPR_ID, APPR_DATE FROM MCMOCAMACCSTATUS WITH (NOLOCK)
        WHERE APPL_NO = :applno ORDER BY [NO] DESC
    """), {"applno": applno}).fetchone()
    if not row:
        return False, ""

    appr_sts = row.APPR_STS
    appr_id = (row.APPR_ID or "").strip().lower()
    appr_date = row.APPR_DATE

    if appr_sts == "A" and appr_id in ("ricky irawan", "denny_dilham"):
        return False, ""
    if appr_sts == "R":
        pending = db.session.execute(text("""
            SELECT 1 FROM MCMOCAMACCSTATUS WITH (NOLOCK) WHERE APPL_NO = :applno AND APPR_STS = 'P'
        """), {"applno": applno}).fetchone()
        return (True, _APPROVAL_LOCK_MESSAGE) if pending else (False, "")
    if appr_sts == "P":
        return True, _APPROVAL_LOCK_MESSAGE
    if appr_sts == "A" and appr_id == "edisamsuri":
        try:
            if appr_date and appr_date.date() < date(2022, 11, 1):
                return False, ""
        except AttributeError:
            pass
    return True, _APPROVAL_LOCK_MESSAGE

def _fetch_bbn(applno):
    row = db.session.execute(text("""
        SELECT bbnvia, paidby, serviceagencyNM, BBNloan, BBN_FEE, ServiceAgencyFee
        FROM BBN WITH (NOLOCK) WHERE appl_no = :applno
    """), {"applno": applno}).fetchone()
    if not row:
        return {"paid_by": "", "birja": 0, "bbn": 0, "birja_raw": 0, "bbn_raw": 0}
    paid_by = row.paidby or ""
    birja_raw = fff.to_float(row.ServiceAgencyFee)
    bbn_raw = fff.to_float(row.BBN_FEE)
    deducted = paid_by == "Deduct from disbursement"
    return {
        "paid_by": paid_by,
        "birja": birja_raw if deducted else 0,
        "bbn": bbn_raw if deducted else 0,
        "birja_raw": birja_raw,
        "bbn_raw": bbn_raw,
    }

def _fetch_provision_loan(applno):
    row = db.session.execute(text(
        "SELECT Prov_loan FROM Provision_Loan WITH (NOLOCK) WHERE APPL_NO = :applno"
    ), {"applno": applno}).fetchone()
    return fff.to_float(row.Prov_loan) if row else 0.0

def _fetch_cigna_fee_and_disbursement_delta(applno):
    row = db.session.execute(text("""
        SELECT Survey_Fee_Cigna, Survey_Loan_Cigna FROM cigna_fee WITH (NOLOCK) WHERE APPL_NO = :applno
    """), {"applno": applno}).fetchone()
    if not row:
        return 0, 0
    fee = fff.to_float(row.Survey_Fee_Cigna)
    loan = fff.to_float(row.Survey_Loan_Cigna)
    return fee, fee - loan

def _fetch_commission_to_dealer(applno):
    row = db.session.execute(text("""
        SELECT FEE, PPNAmount, GrossAmount FROM CAFKOMIS WITH (NOLOCK) WHERE APPL_NO = :applno AND SD_TYPE = 'D'
    """), {"applno": applno}).fetchone()
    if not row:
        return 0.0
    return fff.to_float(row.GrossAmount) + fff.to_float(row.PPNAmount)

def _fetch_equip_suppliers(applno):
    row = db.session.execute(text("""
        SELECT BRAND, SUPP, MODEL, KAROSERI_SUPP, ACCESSORIES_SUPP, OTHER_SUPP
        FROM CAFEQUIP WITH (NOLOCK) WHERE APPL_NO = :applno
    """), {"applno": applno}).fetchone()
    if not row:
        return {"dealer": "", "karoseri": "", "accessories": "", "others": ""}
    return {
        "dealer": (row.SUPP or "").strip(),
        "karoseri": (row.KAROSERI_SUPP or "").strip(),
        "accessories": (row.ACCESSORIES_SUPP or "").strip(),
        "others": (row.OTHER_SUPP or "").strip(),
    }

def _fetch_insurance_disbursement(applno, fin_type, disc_cust):
    ins_row = db.session.execute(text(
        "SELECT CREDITAMT FROM CAFINSU WITH (NOLOCK) WHERE APPL_NO = :applno"
    ), {"applno": applno}).fetchone()
    ins_loan = fff.to_float(ins_row.CREDITAMT) if ins_row else 0.0

    if disc_cust == "1":
        return ins_loan, 0.0, ins_loan

    if fin_type != "W":
        row = db.session.execute(text("""
            SELECT GROSS_PREM, DISB_INSC, SurveyFeeGross_Cigna FROM VDISBURSE WITH (NOLOCK)
            WHERE APPL_NO = :applno AND GROSS_PREM IS NOT NULL
        """), {"applno": applno}).fetchone()
    else:
        row = db.session.execute(text("""
            SELECT GROSS_PREM, DISB_INSC, SurveyFeeGross_Cigna FROM VDISBURSE WITH (NOLOCK)
            WHERE APPL_NO = :applno
        """), {"applno": applno}).fetchone()

    if not row:
        return 0.0 - ins_loan, 0.0, ins_loan

    gross_prem = fff.to_float(row.GROSS_PREM)
    disb = row.DISB_INSC
    credit_amt = fff.to_float(disb) if disb not in (None, "", 0) else (gross_prem - ins_loan)
    return credit_amt, fff.to_float(row.SurveyFeeGross_Cigna), ins_loan

def _fetch_cafdisb_split(applno, split):
    return db.session.execute(text("""
        SELECT L_AMOUNT, FIRST_INST, ADMFEE, DP, Prov, Advance_Grace_Month, Advance_Grace_Amount,
               SPLIT_OTHERS, DISB_INSC, SERVICE_AGENCY_FEE, BBN_FEE, Notary_Fee, SurveyFeeGross_Cigna
        FROM CAFDISB WITH (NOLOCK) WHERE APPL_NO = :applno AND split = :split
    """), {"applno": applno, "split": split}).fetchone()

def _dealer_net_finance(f, refund_supp, subsidy_supp):
    net = (
        f["assetValue"] - f["dp"] - f["surveyFeeGross1"] - f["provisionFee"] - f["insurance"]
        - f["firstInstallment"] - f["advanceGraceAmount"] - f["notaryFeeGross"] - f["businessTripFee"]
        - f["agencyFeeGross"] - f["bbnFee"] + refund_supp - subsidy_supp - f["surveyFeeGross2"]
    )
    return net

def _other_split_net_finance(f, refund_supp, subsidy_supp):
    net = (
        f["assetValue"] - f["dp"] - f["surveyFeeGross1"] - f["provisionFee"] - f["insurance"]
        - f["firstInstallment"] - f["agencyFeeGross"] - f["bbnFee"] + refund_supp - subsidy_supp
        - f["surveyFeeGross2"]
    )
    return net

def _empty_category_fields():
    return {
        "assetValue": 0, "dp": 0, "surveyFeeGross1": 0, "surveyFeeGross2": 0, "notaryFeeGross": 0,
        "provisionFee": 0, "businessTripFee": 0, "insurance": 0, "firstInstallment": 0,
        "advanceGraceMonths": 0, "advanceGraceAmount": 0, "agencyFeeGross": 0, "bbnFee": 0,
    }

def _build_category_defaults(applno, apless, fin_type, cont, split_label, is_dealer, bbn, prov_loan, refund_supp, subsidy_supp):
    stored = _fetch_cafdisb_split(applno, split_label)
    f = _empty_category_fields()

    if is_dealer:
        f["assetValue"] = cont["l_amount"]
        f["dp"] = cont["security"]
        f["surveyFeeGross1"] = cont["admfee"] - cont["otherloan"]
        f["provisionFee"] = cont["provision"] - prov_loan
        f["notaryFeeGross"] = cont["gross"]
        f["businessTripFee"] = cont["business_trip_fee"]
        f["firstInstallment"] = 0 if cont["adv_arr"] == "R" else cont["rental"]
        f["agencyFeeGross"] = bbn["birja"]
        f["bbnFee"] = bbn["bbn"]
        _, cigna_delta = _fetch_cigna_fee_and_disbursement_delta(applno)
        f["surveyFeeGross2"] = cigna_delta

    if stored:
        if stored.L_AMOUNT not in (None, ""):
            f["assetValue"] = fff.to_float(stored.L_AMOUNT)
        if stored.DP not in (None, ""):
            f["dp"] = fff.to_float(stored.DP)
        if stored.Notary_Fee not in (None, ""):
            f["notaryFeeGross"] = fff.to_float(stored.Notary_Fee)
        if stored.Advance_Grace_Month not in (None, ""):
            f["advanceGraceMonths"] = fff.to_float(stored.Advance_Grace_Month)
        if stored.Advance_Grace_Amount not in (None, ""):
            f["advanceGraceAmount"] = fff.to_float(stored.Advance_Grace_Amount)
        if stored.SurveyFeeGross_Cigna not in (None, ""):
            f["surveyFeeGross2"] = fff.to_float(stored.SurveyFeeGross_Cigna)
        if stored.FIRST_INST not in (None, ""):
            f["firstInstallment"] = 0 if cont["adv_arr"] == "R" else fff.to_float(stored.FIRST_INST)
        if stored.Prov not in (None, ""):
            f["provisionFee"] = fff.to_float(stored.Prov)
        if stored.ADMFEE not in (None, ""):
            f["surveyFeeGross1"] = fff.to_float(stored.ADMFEE)
        if not is_dealer:
            if stored.SERVICE_AGENCY_FEE not in (None, ""):
                f["agencyFeeGross"] = fff.to_float(stored.SERVICE_AGENCY_FEE) if bbn["paid_by"] == "Deduct from disbursement" else 0
            if stored.BBN_FEE not in (None, ""):
                f["bbnFee"] = fff.to_float(stored.BBN_FEE) if bbn["paid_by"] == "Deduct from disbursement" else 0

    credit_amt, _, ins_loan = _fetch_insurance_disbursement(applno, fin_type, cont["disc_cust"])
    if is_dealer:
        f["insurance"] = credit_amt
    else:
        f["insurance"] = ins_loan if cont["disc_cust"] == "1" else 0

    net_fn = _dealer_net_finance if is_dealer else _other_split_net_finance
    net_finance = net_fn(f, refund_supp, subsidy_supp)
    commission = _fetch_commission_to_dealer(applno) if is_dealer else 0
    total_payment = net_finance + commission

    return {
        **f,
        "netFinance": net_finance,
        "commissionToDealer": commission,
        "totalPayment": total_payment,
        "othersFieldLabel": stored.SPLIT_OTHERS if (stored and split_label == "Others") else "",
    }

def _fetch_contract_for_disbursement(applno, apless):
    row = db.session.execute(text("""
        SELECT L_AMOUNT, SECURITY, ADMFEE, RENTAL, REFUND_SUPP, DISC_CUST, ADV_ARR, L_TYPE, Gross,
               PROVISION, Otherloan, BusinessTrip_Fee, Subsidy_Supp, Cons_Leas, G_PERIOD, G_INT_AMT
        FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :applno AND APLESS = :apless
    """), {"applno": applno, "apless": apless}).fetchone()
    if not row:
        return None
    return {
        "l_amount": fff.to_float(row.L_AMOUNT), "security": fff.to_float(row.SECURITY),
        "admfee": fff.to_float(row.ADMFEE), "rental": fff.to_float(row.RENTAL),
        "refund_supp": fff.to_float(row.REFUND_SUPP), "disc_cust": row.DISC_CUST or "",
        "adv_arr": row.ADV_ARR or "", "l_type": row.L_TYPE or "", "gross": fff.to_float(row.Gross),
        "provision": fff.to_float(row.PROVISION), "otherloan": fff.to_float(row.Otherloan),
        "business_trip_fee": fff.to_float(row.BusinessTrip_Fee),
        "subsidy_supp": fff.to_float(row.Subsidy_Supp),
        "cons_leas": row.Cons_Leas or "", "g_period": fff.to_float(row.G_PERIOD),
        "g_int_amt": fff.to_float(row.G_INT_AMT),
    }

def _fetch_bank_accounts(applno):
    rows = db.session.execute(text("""
        SELECT a.[ID], a.BANK, a.BANK_BRANCH, a.ACC_NO, a.ACC_NM, a.AMOUNT, b.[DESC] AS bank_desc, a.split
        FROM CAFDISBACC a WITH (NOLOCK) LEFT JOIN UMFBANK b WITH (NOLOCK) ON a.BANK = b.BANK_CODE
        WHERE a.APPL_NO = :applno ORDER BY a.split
    """), {"applno": applno}).fetchall()
    return [
        {"id": r.ID, "split": r.split, "bank": (r.BANK or "").strip(), "bankLabel": r.bank_desc or "",
         "bankBranch": r.BANK_BRANCH or "", "accName": r.ACC_NM or "", "accNo": r.ACC_NO or "",
         "amount": fff.to_float(r.AMOUNT)}
        for r in rows
    ]

_PURPOSE_LABELS = {"1": "Finished", "2": "ET", "3": "Rental", "4": "Overdue Rental", "5": "Penalty"}
def _fetch_cross_accounts(applno):
    rows = db.session.execute(text("""
        SELECT ID_TACrossNo, CROSSNO, AMOUNT, PURPOSE FROM TACrossNo WITH (NOLOCK)
        WHERE APPL_NO = :applno AND CROSS_TYPE = 'CD'
    """), {"applno": applno}).fetchall()
    return [
        {"id": r.ID_TACrossNo, "crossNo": r.CROSSNO or "", "amount": fff.to_float(r.AMOUNT),
         "purpose": r.PURPOSE or "", "purposeLabel": _PURPOSE_LABELS.get(r.PURPOSE or "", "")}
        for r in rows
    ]

def _default_accounts_for_supplier(applno, supplier_id, split_label):
    if not supplier_id:
        return []
    rows = db.session.execute(text("""
        SELECT b.[DESC] AS bank_desc, a.Acc_BankBranch, a.Acc_Name, a.Acc_NO, a.[Default], b.BANK_CODE
        FROM BeneficiaryAccount a INNER JOIN UMFBANK b ON a.Acc_Bank = b.BANK_CODE
        WHERE a.BeneficiaryID = :supp AND a.Category = 'Dealer' AND a.AccountType = 'D' AND a.[Default] = '1'
    """), {"supp": supplier_id}).fetchall()

    if rows:
        return [
            {"bank": (r.BANK_CODE or "").strip(), "bankLabel": r.bank_desc or "", "bankBranch": r.Acc_BankBranch or "",
             "accName": r.Acc_Name or "", "accNo": r.Acc_NO or "", "amount": 0}
            for r in rows
        ]

    stmt_row = db.session.execute(text("""
        SELECT TOP 1 ACC_NM, acc_no, c.[DESC] AS bank_desc, c.BANK_CODE, Bank_Branch
        FROM CAFBANKSTM a WITH (NOLOCK) INNER JOIN cafcont b WITH (NOLOCK) ON a.APLESS = b.APLESS
        LEFT JOIN UMFBANK c WITH (NOLOCK) ON a.Bank = c.BANK_CODE
        WHERE a.APPL_NO = :applno AND ACC_NM IS NOT NULL ORDER BY ID_CAFBANKSTM
    """), {"applno": applno}).fetchone()

    if stmt_row:
        return [{
            "bank": (stmt_row.BANK_CODE or "").strip(), "bankLabel": stmt_row.bank_desc or "",
            "bankBranch": stmt_row.Bank_Branch or "", "accName": stmt_row.ACC_NM or "",
            "accNo": stmt_row.acc_no or "", "amount": 0,
        }]

    return []

@cam_edit_bp.route("/disbursement", methods=["GET"])
@login_required
def disbursement_get():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    fin_type = request.args.get("finType", "")
    cont_type = request.args.get("contType", "")

    if not apless or not applno:
        return jsonify({"error": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"blocked": True, "message": block_message}), 409

    cont = _fetch_contract_for_disbursement(applno, apless)
    if not cont:
        return jsonify({"error": "Contract not found"}), 404

    locked, lock_message = _fetch_approval_lock(applno)
    suppliers = _fetch_equip_suppliers(applno)
    bbn = _fetch_bbn(applno)
    prov_loan = _fetch_provision_loan(applno)

    disb_type_row = db.session.execute(text(
        "SELECT disb_type FROM cafcont WHERE appl_no = :applno"
    ), {"applno": applno}).fetchone()
    disb_type = disb_type_row.disb_type if disb_type_row else ""

    active = {
        "dealer": True,
        "karoseri": bool(suppliers["karoseri"]),
        "accessories": bool(suppliers["accessories"]),
        "others": bool(suppliers["others"]),
    }
    split_purchase_order = sum(active.values()) > 1

    categories = {}
    for key, split_label, is_dealer in [
        ("dealer", "Dealer", True), ("karoseri", "Karoseri", False),
        ("accessories", "Accessories", False), ("others", "Others", False),
    ]:
        categories[key] = _build_category_defaults(
            applno, apless, fin_type, cont, split_label, is_dealer, bbn, prov_loan,
            cont["refund_supp"], cont["subsidy_supp"],
        )

    accounts_by_split = {}
    for row in _fetch_bank_accounts(applno):
        accounts_by_split.setdefault(row["split"], []).append(row)

    for split_label, supplier_key in [("Dealer", "dealer"), ("Karoseri", "karoseri"), ("Accessories", "accessories"), ("Others", "others")]:
        if split_label not in accounts_by_split:
            accounts_by_split[split_label] = _default_accounts_for_supplier(applno, suppliers[supplier_key], split_label)
    accounts_by_split.setdefault("Customer", [])

    disb_to_options = []
    for supplier_key, split_label, option_label in [
        ("dealer", "Dealer", "Dealer"), ("karoseri", "Karoseri", "Karoseri"),
        ("accessories", "Accessories", "Accessories"), ("others", "Others", "Other"),
    ]:
        if suppliers[supplier_key]:
            disb_to_options.append({"value": split_label, "label": option_label})
    disb_to_options.append({"value": "Customer", "label": "Customer"})

    return jsonify({
        "locked": locked,
        "lockMessage": lock_message,
        "ketDpSecurity": "Security Deposit" if fin_type in ("F", "S") else "Down Payment",
        "splitPurchaseOrder": split_purchase_order,
        "active": active,
        "categories": categories,
        "totals": {
            "assetValue": cont["l_amount"], "dp": cont["security"],
            "surveyFeeGross1": cont["admfee"] - cont["otherloan"], "provisionFee": cont["provision"] - prov_loan,
            "notaryFeeGross": cont["gross"], "businessTripFee": cont["business_trip_fee"],
            "firstInstallment": 0 if cont["adv_arr"] == "R" else cont["rental"],
            "advanceGraceAmount": sum(c.get("advanceGraceAmount", 0) for c in categories.values()),
            "agencyFeeGross": bbn["birja"], "bbnFee": bbn["bbn"],
            "commissionToDealer": _fetch_commission_to_dealer(applno),
        },
        "refundToDealer": cont["refund_supp"],
        "subsidyFromDealer": cont["subsidy_supp"],
        "showRefund": cont["refund_supp"] > 0,
        "externalAccounts": accounts_by_split,
        "internalAccounts": _fetch_cross_accounts(applno),
        "disbursementType": disb_type,
        "disbursementTypeOptions": _disbursement_type_options(disb_type, fin_type),
        "disbursessToOptions": disb_to_options,
        "bankOptions": _fetch_bank_options(),
        "purposeOptions": _fetch_combo("PURPOSE_CD"),
        "gracePeriodMaxMonths": cont["g_period"],
        "gracePeriodAmountPerMonth": cont["g_int_amt"],
        "readonlyFirstInstallment": cont["adv_arr"] == "R",
    })

_DISB_EXTERNAL_OPTION = {"value": "1", "label": "External Disbursement"}
_DISB_INTERNAL_OPTION = {"value": "2", "label": "Internal Disbursement"}

def _disbursement_type_options(disb_type, fin_type):
    disb_type = (disb_type or "").strip()
    fin_type = (fin_type or "").strip()
    if disb_type == "C" and fin_type not in ("S", "M", "D"):
        return [_DISB_INTERNAL_OPTION]
    if disb_type == "C" and fin_type in ("S", "M", "D"):
        return [_DISB_EXTERNAL_OPTION, _DISB_INTERNAL_OPTION]
    return [_DISB_EXTERNAL_OPTION]

def _fetch_bank_options():
    rows = db.session.execute(text(
        "SELECT BANK_CODE, [DESC] FROM UMFBANK WITH (NOLOCK) WHERE STATUS = '1' ORDER BY [DESC]"
    )).fetchall()
    return [{"value": r.BANK_CODE, "label": r.DESC} for r in rows]

@cam_edit_bp.route("/disbursement/validate-contract", methods=["GET"])
@login_required
def disbursement_validate_contract():
    contract = request.args.get("contract", "").strip()
    if not contract:
        return jsonify({"valid": False, "message": "Contract number is required"})
    row = db.session.execute(text("""
        SELECT 1 FROM CLFCONT WITH (NOLOCK)
        WHERE LEASE_NO = :contract AND FLGDEL = '0' AND Execution IS NOT NULL AND UPD_STAT = 'Y'
    """), {"contract": contract}).fetchone()
    if row:
        return jsonify({"valid": True})
    return jsonify({"valid": False, "message": "Contract not exist"})

def _check_genie_finance(applno, acc_name):
    normalized = (acc_name or "").upper().replace(" ", "").replace(",", "").replace(".", "")
    if "GENIEFINANCE" not in normalized:
        return True, ""
    row = db.session.execute(text(
        "SELECT crossno FROM TACrossNo WITH (NOLOCK) WHERE appl_no = :applno"
    ), {"applno": applno}).fetchone()
    if not row or not row.crossno:
        return False, "Your Cam doesn't have Cross Number, please contact helpdesk."
    return True, ""

@cam_edit_bp.route("/disbursement/accounts/save", methods=["POST"])
@login_required
def disbursement_accounts_save():
    payload = request.get_json(force=True) or {}
    applno = payload.get("applno", "")
    apless = payload.get("apless", "")
    split_label = payload.get("split", "")
    rows = payload.get("rows", [])

    if not applno or not split_label:
        return jsonify({"success": False, "message": "applno and split are required"}), 400

    locked, lock_message = _fetch_approval_lock(applno)
    if locked:
        return jsonify({"success": False, "message": lock_message}), 409

    for r in rows:
        ok, message = _check_genie_finance(applno, r.get("accName", ""))
        if not ok:
            return jsonify({"success": False, "message": message})

    try:
        db.session.execute(text(
            "DELETE FROM CAFDISBACC WHERE APPL_NO = :applno AND Split = :split"
        ), {"applno": applno, "split": split_label})
        for r in rows:
            if "checked" in r and not r.get("checked"):
                continue
            amount = _to_number(r.get("amount"))
            if not amount:
                continue
            db.session.execute(text("""
                INSERT INTO CAFDISBACC (APPL_NO, BANK, ACC_NO, ACC_NM, AMOUNT, BANK_BRANCH, SPLIT)
                VALUES (:applno, :bank, :acc_no, :acc_name, :amount, :bank_branch, :split)
            """), {
                "applno": applno, "bank": r.get("bank", ""), "acc_no": r.get("accNo", ""),
                "acc_name": r.get("accName", ""), "amount": amount, "bank_branch": r.get("bankBranch", ""),
                "split": split_label,
            })
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to save disbursement accounts for applno=%s", applno)
        return jsonify({"success": False, "message": "Failed to save."}), 500

    return jsonify({"success": True, "accounts": [a for a in _fetch_bank_accounts(applno) if a["split"] == split_label]})

@cam_edit_bp.route("/disbursement/accounts/<int:account_id>", methods=["PUT"])
@login_required
def disbursement_accounts_update(account_id):
    payload = request.get_json(force=True) or {}
    applno = payload.get("applno", "")
    if not applno:
        return jsonify({"success": False, "message": "applno is required"}), 400

    locked, lock_message = _fetch_approval_lock(applno)
    if locked:
        return jsonify({"success": False, "message": lock_message}), 409

    bank = (payload.get("bank") or "").strip()
    bank_branch = (payload.get("bankBranch") or "").strip()
    acc_name = (payload.get("accName") or "").strip()
    acc_no = (payload.get("accNo") or "").strip()
    amount = _to_number(payload.get("amount"))

    ok, message = _check_genie_finance(applno, acc_name)
    if not ok:
        return jsonify({"success": False, "message": message})

    try:
        if amount == 0:
            db.session.execute(text(
                "DELETE FROM CAFDISBACC WHERE APPL_NO = :applno AND [ID] = :id"
            ), {"applno": applno, "id": account_id})
        else:
            db.session.execute(text("""
                UPDATE CAFDISBACC SET BANK = :bank, ACC_NO = :acc_no, ACC_NM = :acc_name,
                    AMOUNT = :amount, BANK_BRANCH = :bank_branch
                WHERE APPL_NO = :applno AND [ID] = :id
            """), {"bank": bank, "acc_no": acc_no, "acc_name": acc_name, "amount": amount,
                   "bank_branch": bank_branch, "applno": applno, "id": account_id})
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to update disbursement account id=%s", account_id)
        return jsonify({"success": False, "message": "Data Failed"}), 500

    return jsonify({"success": True, "message": "Success", "accounts": _fetch_bank_accounts(applno)})

@cam_edit_bp.route("/disbursement/accounts/<int:account_id>", methods=["DELETE"])
@login_required
def disbursement_accounts_delete(account_id):
    applno = request.args.get("applno", "")
    if not applno:
        return jsonify({"success": False, "message": "applno is required"}), 400

    locked, lock_message = _fetch_approval_lock(applno)
    if locked:
        return jsonify({"success": False, "message": lock_message}), 409

    try:
        db.session.execute(text(
            "DELETE FROM CAFDISBACC WHERE APPL_NO = :applno AND [ID] = :id"
        ), {"applno": applno, "id": account_id})
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to delete disbursement account id=%s", account_id)
        return jsonify({"success": False, "message": "Failed to delete."}), 500

    return jsonify({"success": True})

@cam_edit_bp.route("/disbursement/cross-accounts/save", methods=["POST"])
@login_required
def disbursement_cross_accounts_save():
    payload = request.get_json(force=True) or {}
    applno = payload.get("applno", "")
    rows = payload.get("rows", [])

    if not applno:
        return jsonify({"success": False, "message": "applno is required"}), 400

    locked, lock_message = _fetch_approval_lock(applno)
    if locked:
        return jsonify({"success": False, "message": lock_message}), 409

    try:
        db.session.execute(text(
            "DELETE FROM TACrossNo WHERE APPL_NO = :applno AND CROSS_TYPE = 'CD'"
        ), {"applno": applno})
        for r in rows:
            if "checked" in r and not r.get("checked"):
                continue
            amount = _to_number(r.get("amount"))
            if not amount:
                continue
            db.session.execute(text("""
                INSERT INTO TACrossNo (APPL_NO, LEASE_NO, CROSSNO, CROSS_TYPE, AMOUNT, PURPOSE)
                VALUES (:applno, '', :cross_no, 'CD', :amount, :purpose)
            """), {"applno": applno, "cross_no": r.get("crossNo", ""), "amount": amount, "purpose": r.get("purpose", "")})
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to save cross accounts for applno=%s", applno)
        return jsonify({"success": False, "message": "Failed to save."}), 500

    return jsonify({"success": True, "accounts": _fetch_cross_accounts(applno)})

@cam_edit_bp.route("/disbursement/cross-accounts/<int:cross_id>", methods=["PUT"])
@login_required
def disbursement_cross_accounts_update(cross_id):
    payload = request.get_json(force=True) or {}
    applno = payload.get("applno", "")
    if not applno:
        return jsonify({"success": False, "message": "applno is required"}), 400

    locked, lock_message = _fetch_approval_lock(applno)
    if locked:
        return jsonify({"success": False, "message": lock_message}), 409

    cross_no = (payload.get("crossNo") or "").strip()
    purpose = (payload.get("purpose") or "").strip()
    amount = _to_number(payload.get("amount"))

    try:
        if amount == 0:
            db.session.execute(text("""
                DELETE FROM TACrossNo WHERE APPL_NO = :applno AND CROSS_TYPE = 'CD' AND ID_TACrossNo = :id
            """), {"applno": applno, "id": cross_id})
        else:
            db.session.execute(text("""
                UPDATE TACrossNo SET CROSSNO = :cross_no, AMOUNT = :amount, PURPOSE = :purpose
                WHERE APPL_NO = :applno AND ID_TACrossNo = :id
            """), {"cross_no": cross_no, "amount": amount, "purpose": purpose,
                   "applno": applno, "id": cross_id})
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to update cross account id=%s", cross_id)
        return jsonify({"success": False, "message": "Data Failed"}), 500

    return jsonify({"success": True, "message": "Success", "accounts": _fetch_cross_accounts(applno)})

@cam_edit_bp.route("/disbursement/cross-accounts/<int:cross_id>", methods=["DELETE"])
@login_required
def disbursement_cross_accounts_delete(cross_id):
    applno = request.args.get("applno", "")
    if not applno:
        return jsonify({"success": False, "message": "applno is required"}), 400
    try:
        db.session.execute(text(
            "DELETE FROM TACrossNo WHERE APPL_NO = :applno AND CROSS_TYPE = 'CD' AND ID_TACrossNo = :id"
        ), {"applno": applno, "id": cross_id})
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to delete cross account id=%s", cross_id)
        return jsonify({"success": False, "message": "Failed to delete."}), 500
    return jsonify({"success": True})

def _validate_split_sums(cont, categories, split_purchase_order, total_insurance_disb):
    if not split_purchase_order:
        return []
    errors = []
    total_asset = sum(c["assetValue"] for c in categories.values())
    total_dp = sum(c["dp"] for c in categories.values())
    total_survey1 = sum(c["surveyFeeGross1"] for c in categories.values())
    total_provision = sum(c["provisionFee"] for c in categories.values())
    total_insurance = sum(c["insurance"] for c in categories.values())

    if round(total_asset) != round(cont["l_amount"]):
        errors.append("Total Asset value not Valid")
    if round(total_dp) != round(cont["security"]):
        errors.append("Total Down Payment Not Valid")
    if round(total_survey1) != round(cont["admfee"] - cont["otherloan"]):
        errors.append("Survey Fee Not Valid")
    if total_provision > cont["provision"]:
        errors.append("Provision Not Valid")
    if total_insurance > total_insurance_disb:
        errors.append("Insurance Not Valid")
    return errors

def _recompute_category(applno, fin_type, cont, split_label, is_dealer, fields, bbn, refund_supp, subsidy_supp):
    f = {**_empty_category_fields(), **fields}
    net_fn = _dealer_net_finance if is_dealer else _other_split_net_finance
    net_finance = net_fn(f, refund_supp, subsidy_supp)
    commission = _fetch_commission_to_dealer(applno) if is_dealer else 0
    return {**f, "netFinance": net_finance, "commissionToDealer": commission, "totalPayment": net_finance + commission}

@cam_edit_bp.route("/disbursement/calculate", methods=["POST"])
@login_required
def disbursement_calculate():
    payload = request.get_json(force=True) or {}
    applno = payload.get("applno", "")
    apless = payload.get("apless", "")
    fin_type = payload.get("finType", "")
    categories_in = payload.get("categories", {})
    split_purchase_order = bool(payload.get("splitPurchaseOrder"))

    cont = _fetch_contract_for_disbursement(applno, apless)
    if not cont:
        return jsonify({"error": "Contract not found"}), 404

    bbn = _fetch_bbn(applno)
    normalized = {}
    for key, split_label, is_dealer in [
        ("dealer", "Dealer", True), ("karoseri", "Karoseri", False),
        ("accessories", "Accessories", False), ("others", "Others", False),
    ]:
        if key in categories_in:
            fields = {k: _to_number(v) for k, v in categories_in[key].items() if k != "othersFieldLabel"}
            if not is_dealer:
                fields["surveyFeeGross1"] = 0
            normalized[key] = _recompute_category(
                applno, fin_type, cont, split_label, is_dealer, fields, bbn, cont["refund_supp"], cont["subsidy_supp"]
            )

    errors = _validate_split_sums(cont, normalized, split_purchase_order, _fetch_insurance_disbursement(applno, fin_type, cont["disc_cust"])[0]) if split_purchase_order else []
    if not split_purchase_order and "dealer" in normalized:
        if round(normalized["dealer"]["dp"]) != round(cont["security"]):
            errors.append("Total Down Payment Not Valid")

    if errors:
        return jsonify({"success": False, "message": "<br>".join(errors)})

    try:
        for key, split_label in [("dealer", "Dealer"), ("karoseri", "Karoseri"), ("accessories", "Accessories"), ("others", "Others")]:
            if key not in normalized:
                db.session.execute(text(
                    "DELETE FROM CAFDISB WHERE APPL_NO = :applno AND split = :split"
                ), {"applno": applno, "split": split_label})
                continue
            _persist_category(applno, split_label, normalized[key], key == "dealer")
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to save disbursement calculation for applno=%s", applno)
        return jsonify({"success": False, "message": "Failed to save."}), 500

    return jsonify({"success": True, "categories": normalized})

def _persist_category(applno, split_label, c, is_dealer):
    exists = db.session.execute(text(
        "SELECT 1 FROM CAFDISB WITH (NOLOCK) WHERE APPL_NO = :applno AND split = :split"
    ), {"applno": applno, "split": split_label}).fetchone()

    params = {
        "applno": applno, "split": split_label, "l_amount": c["assetValue"], "dp": c["dp"],
        "admfee": c["surveyFeeGross1"], "disb_insc": c["insurance"], "first_inst": c["firstInstallment"],
        "prov": c["provisionFee"], "agency_fee": c["agencyFeeGross"], "bbn_fee": c["bbnFee"],
        "notary_fee": c["notaryFeeGross"], "cigna": c["surveyFeeGross2"],
        "grace_month": c.get("advanceGraceMonths", 0), "grace_amount": c.get("advanceGraceAmount", 0),
        "others_field": c.get("othersFieldLabel", ""),
    }
    if exists:
        db.session.execute(text("""
            UPDATE CAFDISB SET L_AMOUNT = :l_amount, DP = :dp, ADMFEE = :admfee, DISB_INSC = :disb_insc,
                FIRST_INST = :first_inst, Prov = :prov, SERVICE_AGENCY_FEE = :agency_fee, BBN_FEE = :bbn_fee,
                Notary_Fee = :notary_fee, SurveyFeeGross_Cigna = :cigna, Advance_Grace_Month = :grace_month,
                Advance_Grace_Amount = :grace_amount, SPLIT_OTHERS = :others_field
            WHERE APPL_NO = :applno AND split = :split
        """), params)
    else:
        db.session.execute(text("""
            INSERT INTO CAFDISB (APPL_NO, DP, ADMFEE, DISB_INSC, FIRST_INST, Prov, split, L_AMOUNT,
                SERVICE_AGENCY_FEE, BBN_FEE, Notary_Fee, SurveyFeeGross_Cigna, Advance_Grace_Month,
                Advance_Grace_Amount, SPLIT_OTHERS)
            VALUES (:applno, :dp, :admfee, :disb_insc, :first_inst, :prov, :split, :l_amount,
                :agency_fee, :bbn_fee, :notary_fee, :cigna, :grace_month, :grace_amount, :others_field)
        """), params)

_RS_CONT_TYPES = ("RS0", "RS1", "RS2")

def _disb_default_supplier_accounts(supplier_id):
    if not supplier_id:
        return []
    rows = db.session.execute(text("""
        SELECT a.Acc_BankBranch, a.Acc_Name, a.Acc_NO, b.BANK_CODE
        FROM BeneficiaryAccount a INNER JOIN UMFBANK b ON a.Acc_Bank = b.BANK_CODE
        WHERE a.BeneficiaryID = :supp AND a.Category = 'Dealer' AND a.AccountType = 'D' AND a.[Default] = '1'
    """), {"supp": supplier_id}).fetchall()
    return [{
        "bank": (r.BANK_CODE or "").strip(),
        "accNo": (r.Acc_NO or "").strip(),
        "accName": (r.Acc_Name or "").strip(),
        "bankBranch": (r.Acc_BankBranch or "").strip(),
    } for r in rows]

def _disb_bank_statement_account(applno):
    row = db.session.execute(text("""
        SELECT TOP 1 ACC_NM, acc_no, c.BANK_CODE, Bank_Branch
        FROM CAFBANKSTM a WITH (NOLOCK) INNER JOIN cafcont b WITH (NOLOCK) ON a.APLESS = b.APLESS
        LEFT JOIN UMFBANK c WITH (NOLOCK) ON a.Bank = c.BANK_CODE
        WHERE a.APPL_NO = :applno AND ACC_NM IS NOT NULL ORDER BY ID_CAFBANKSTM
    """), {"applno": applno}).fetchone()
    if not row:
        return []
    return [{
        "bank": (row.BANK_CODE or "").strip(),
        "accNo": (row.acc_no or "").strip(),
        "accName": (row.ACC_NM or "").strip(),
        "bankBranch": (row.Bank_Branch or "").strip(),
    }]

def _disb_insert_account(applno, account, amount, split_label):
    if not (account["bank"] or account["accNo"] or account["accName"] or account["bankBranch"]):
        return
    db.session.execute(text("""
        INSERT INTO CAFDISBACC (APPL_NO, BANK, ACC_NO, ACC_NM, AMOUNT, BANK_BRANCH, SPLIT)
        VALUES (:applno, :bank, :acc_no, :acc_name, :amount, :bank_branch, :split)
    """), {
        "applno": applno, "bank": account["bank"], "acc_no": account["accNo"],
        "acc_name": account["accName"], "amount": amount,
        "bank_branch": account["bankBranch"], "split": split_label,
    })

@cam_edit_bp.route("/disbursement/reset", methods=["POST"])
@login_required
def disbursement_reset():
    payload = request.get_json(force=True) or {}
    applno = payload.get("applno", "")
    apless = payload.get("apless", "")
    fin_type = payload.get("finType", "")
    cont_type = (payload.get("contType", "") or "").strip()

    if not applno or not apless:
        return jsonify({"success": False, "message": "applno and apless are required"}), 400

    locked, lock_message = _fetch_approval_lock(applno)
    if locked:
        return jsonify({"success": False, "message": lock_message}), 409

    cont = _fetch_contract_for_disbursement(applno, apless)
    if not cont:
        return jsonify({"success": False, "message": "Contract not found"}), 404

    suppliers = _fetch_equip_suppliers(applno)
    bbn = _fetch_bbn(applno)
    prov_loan = _fetch_provision_loan(applno)
    _, cigna_delta = _fetch_cigna_fee_and_disbursement_delta(applno)
    credit_amt, _, _ = _fetch_insurance_disbursement(applno, fin_type, cont["disc_cust"])

    rental = 0 if cont["adv_arr"] == "R" else cont["rental"]
    if cont["disc_cust"] == "1" and cont["adv_arr"] != "V":
        rental = 0

    provision = cont["provision"] - prov_loan
    params = {
        "applno": applno, "l_amount": cont["l_amount"], "dp": cont["security"],
        "admfee": cont["admfee"], "disb_insc": credit_amt, "first_inst": rental,
        "prov": provision, "agency_fee": bbn["birja_raw"], "bbn_fee": bbn["bbn_raw"],
        "notary_fee": cont["gross"], "cigna": cigna_delta,
    }

    net_finance = (
        cont["l_amount"] - cont["security"] - (cont["admfee"] - cont["otherloan"]) - provision
        - credit_amt - rental - bbn["birja"] - cont["business_trip_fee"] - cont["gross"]
        - bbn["bbn"] + cont["refund_supp"] - cont["subsidy_supp"] - cigna_delta
    )

    try:
        for key, split_label in [("karoseri", "Karoseri"), ("accessories", "Accessories"), ("others", "Others")]:
            if suppliers[key]:
                db.session.execute(text("""
                    UPDATE cafdisb SET DISB_INSC = NULL, ADMFEE = NULL, FIRST_INST = NULL, DP = NULL, PROV = NULL,
                        L_AMOUNT = NULL, SPLIT_OTHERS = NULL, SERVICE_AGENCY_FEE = NULL, BBN_FEE = NULL,
                        SurveyFeeGross_Cigna = NULL
                    WHERE appl_no = :applno AND SPLIT = :split
                """), {"applno": applno, "split": split_label})
            else:
                db.session.execute(text(
                    "DELETE FROM cafdisb WHERE appl_no = :applno AND split = :split"
                ), {"applno": applno, "split": split_label})

        dealer_exists = db.session.execute(text(
            "SELECT 1 FROM CAFDISB WITH (NOLOCK) WHERE APPL_NO = :applno AND split = 'Dealer'"
        ), {"applno": applno}).fetchone()

        if dealer_exists:
            db.session.execute(text("""
                UPDATE CAFDISB SET L_AMOUNT = :l_amount, DP = :dp, ADMFEE = :admfee, DISB_INSC = :disb_insc,
                    FIRST_INST = :first_inst, Prov = :prov, SERVICE_AGENCY_FEE = :agency_fee,
                    BBN_FEE = :bbn_fee, Notary_Fee = :notary_fee, SurveyFeeGross_Cigna = :cigna
                WHERE APPL_NO = :applno AND split = 'Dealer'
            """), params)
        else:
            db.session.execute(text("""
                INSERT INTO CAFDISB (APPL_NO, DP, ADMFEE, DISB_INSC, FIRST_INST, Prov, split,
                    SERVICE_AGENCY_FEE, BBN_FEE, Notary_Fee, SurveyFeeGross_Cigna)
                VALUES (:applno, :dp, :admfee, :disb_insc, :first_inst, :prov, 'Dealer',
                    :agency_fee, :bbn_fee, :notary_fee, :cigna)
            """), params)

        db.session.execute(text("DELETE FROM CAFDISBACC WHERE APPL_NO = :applno"), {"applno": applno})

        if cont_type in _RS_CONT_TYPES:
            cross_row = db.session.execute(text("""
                SELECT CROSSNO FROM TACrossNo WITH (NOLOCK) WHERE APPL_NO = :applno AND CROSS_TYPE = 'CN'
            """), {"applno": applno}).fetchone()
            db.session.execute(text(
                "DELETE FROM TACrossNo WHERE APPL_NO = :applno AND CROSS_TYPE = 'CD'"
            ), {"applno": applno})
            db.session.execute(text("""
                INSERT INTO TACrossNo (APPL_NO, LEASE_NO, CROSSNO, CROSS_TYPE, AMOUNT, PURPOSE)
                VALUES (:applno, '', :cross_no, 'CD', :amount, '2')
            """), {"applno": applno, "cross_no": (cross_row.CROSSNO if cross_row else "") or "",
                   "amount": net_finance})
        else:
            dealer_accounts = _disb_default_supplier_accounts(suppliers["dealer"])
            if not dealer_accounts:
                dealer_accounts = _disb_bank_statement_account(applno)
            for index, account in enumerate(dealer_accounts):
                _disb_insert_account(applno, account, net_finance if index == 0 else 0, "Dealer")

        for key, split_label in [("karoseri", "Karoseri"), ("accessories", "Accessories"), ("others", "Others")]:
            for account in _disb_default_supplier_accounts(suppliers[key]):
                _disb_insert_account(applno, account, 0, split_label)

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to reset disbursement for applno=%s", applno)
        return jsonify({"success": False, "message": "Reset failed."}), 500

    return jsonify({"success": True})

def _disb_split_totals(applno):
    rows = db.session.execute(text("""
        SELECT split, SUM(AMOUNT) AS total FROM CAFDISBACC WITH (NOLOCK)
        WHERE APPL_NO = :applno GROUP BY split
    """), {"applno": applno}).fetchall()
    return {(r.split or "").strip(): _to_number(r.total) for r in rows}

@cam_edit_bp.route("/disbursement/next", methods=["POST"])
@login_required
def disbursement_next():
    payload = request.get_json(force=True) or {}
    applno = payload.get("applno", "")
    apless = payload.get("apless", "")
    fin_type = payload.get("finType", "")
    categories_in = payload.get("categories", {})
    split_purchase_order = bool(payload.get("splitPurchaseOrder"))

    if not applno or not apless:
        return jsonify({"success": False, "message": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"success": False, "message": block_message}), 409

    cont = _fetch_contract_for_disbursement(applno, apless)
    if not cont:
        return jsonify({"success": False, "message": "Contract not found"}), 404

    normalized = {}
    if categories_in:
        locked, lock_message = _fetch_approval_lock(applno)
        if locked:
            return jsonify({"success": False, "message": lock_message}), 409

        bbn = _fetch_bbn(applno)
        for key, split_label, is_dealer in [
            ("dealer", "Dealer", True), ("karoseri", "Karoseri", False),
            ("accessories", "Accessories", False), ("others", "Others", False),
        ]:
            if key not in categories_in:
                continue
            fields = {k: _to_number(v) for k, v in categories_in[key].items() if k != "othersFieldLabel"}
            if not is_dealer:
                fields["surveyFeeGross1"] = 0
            normalized[key] = _recompute_category(
                applno, fin_type, cont, split_label, is_dealer, fields, bbn,
                cont["refund_supp"], cont["subsidy_supp"],
            )
            normalized[key]["othersFieldLabel"] = categories_in[key].get("othersFieldLabel", "")

        errors = _validate_split_sums(
            cont, normalized, split_purchase_order,
            _fetch_insurance_disbursement(applno, fin_type, cont["disc_cust"])[0],
        ) if split_purchase_order else []
        if not split_purchase_order and "dealer" in normalized:
            if round(normalized["dealer"]["dp"]) != round(cont["security"]):
                errors.append("Total Down Payment Not Valid")
        if errors:
            return jsonify({"success": False, "message": "<br>".join(errors)})

        try:
            for key, split_label in [("dealer", "Dealer"), ("karoseri", "Karoseri"),
                                     ("accessories", "Accessories"), ("others", "Others")]:
                if key not in normalized:
                    db.session.execute(text(
                        "DELETE FROM CAFDISB WHERE APPL_NO = :applno AND split = :split"
                    ), {"applno": applno, "split": split_label})
                    continue
                _persist_category(applno, split_label, normalized[key], key == "dealer")
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Failed to save disbursement for applno=%s", applno)
            return jsonify({"success": False, "message": "Failed to save."}), 500

    split_totals = _disb_split_totals(applno)
    mismatch = "Total bank amount isn`t same with the disbursement to dealer amount"
    for key, split_label in [("karoseri", "Karoseri"), ("accessories", "Accessories"), ("others", "Others")]:
        if key not in normalized:
            continue
        if round(normalized[key]["netFinance"]) != round(split_totals.get(split_label, 0)):
            return jsonify({"success": False, "message": mismatch})

    accounts_total = sum(split_totals.values())
    cross_total = sum(a["amount"] for a in _fetch_cross_accounts(applno))

    if normalized:
        expected = sum(normalized[key]["netFinance"] for key in normalized)
    else:
        expected = _to_number(payload.get("totalNetFinance"))

    if round(expected) != round(accounts_total + cross_total):
        return jsonify({"success": False, "message": mismatch})

    return jsonify({"success": True, "apless": apless, "applno": applno})

def _to_date(value) -> Optional[pydt.date]:
    if value is None:
        return None
    if isinstance(value, pydt.datetime):
        return value.date()
    if isinstance(value, pydt.date):
        return value
    return None

def _n(value, default=0):
    return fff.to_float(value, default)

def _fin_str(value) -> str:
    if value is None:
        return ""
    return str(value).strip()

def _fin_rounding(curr_code) -> float:
    row = db.session.execute(
        text("SELECT ROUNDING FROM UMFCURR WITH (NOLOCK) WHERE CURR_CODE = :cc"),
        {"cc": curr_code or "IDR"},
    ).fetchone()
    return _n(row.ROUNDING, 1) if row and row.ROUNDING is not None else 1

def _fin_restricted(les_tipe: str, cont_type: str, nationality: str) -> bool:
    return les_tipe == "PT" or cont_type in ("RS1", "RS0") or nationality in ("US", "USA")

def _fin_customer_profile(applno: str) -> dict:
    row = db.session.execute(
        text(
            """
            SELECT LESSEE_TP, Nationality,
                   DATEDIFF(d, DATEADD(year, 55, TGLBIRTH), GETDATE()) AS days_past_55
            FROM CAFLESS WITH (NOLOCK)
            WHERE APLESS = (SELECT TOP 1 APLESS FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :applno)
            """
        ),
        {"applno": applno},
    ).fetchone()
    age_row = db.session.execute(
        text(
            """
            SELECT DATEDIFF(yy, t.b, t.v) AS y,
                   DATEDIFF(mm, DATEADD(yy, DATEDIFF(yy, t.b, t.v), t.b), t.v) AS m,
                   DATEDIFF(dd, DATEADD(mm, DATEDIFF(mm, DATEADD(yy, DATEDIFF(yy, t.b, t.v), t.b), t.v),
                            DATEADD(yy, DATEDIFF(yy, t.b, t.v), t.b)), t.v) AS d
            FROM (
                SELECT TGLBIRTH AS b, GETDATE() AS v
                FROM CAFLESS WITH (NOLOCK)
                WHERE APLESS = (SELECT TOP 1 APLESS FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :applno)
            ) t
            """
        ),
        {"applno": applno},
    ).fetchone()
    tenor_age_row = db.session.execute(
        text(
            """
            SELECT DATEDIFF(d, DATEADD(m, b.TENOR, GETDATE()), DATEADD(year, 65, a.TGLBIRTH)) AS celicih
            FROM CAFLESS a WITH (NOLOCK)
                INNER JOIN CAFCONT b WITH (NOLOCK) ON a.APLESS = b.APLESS
            WHERE b.APPL_NO = :applno
            """
        ),
        {"applno": applno},
    ).fetchone()
    return {
        "lesseeType": _fin_str(row.LESSEE_TP) if row else "",
        "nationality": _fin_str(row.Nationality) if row else "",
        "daysPast55": int(row.days_past_55) if row and row.days_past_55 is not None else None,
        "ageYears": int(age_row.y) if age_row and age_row.y is not None else 0,
        "ageMonths": int(age_row.m) if age_row and age_row.m is not None else 0,
        "ageDays": int(age_row.d) if age_row and age_row.d is not None else 0,
        "daysTo65AfterTenor": int(tenor_age_row.celicih) if tenor_age_row and tenor_age_row.celicih is not None else None,
    }

def _fin_total_outs_before(apless: str) -> float:
    row = db.session.execute(
        text(
            """
            SELECT TOTAL_OUTS_PRINC FROM VOUTS_PRINC_CIGNA WITH (NOLOCK)
            WHERE LESSEE_NO = (SELECT TOP 1 LESSEE_NO FROM CLFLESS WITH (NOLOCK) WHERE APLESS = :apless)
            """
        ),
        {"apless": apless},
    ).fetchone()
    return _n(row.TOTAL_OUTS_PRINC) if row else 0.0

def _fin_customer_outstanding(apless: str, applno: str) -> dict:
    result = {}
    for key, cons_leas in (("totalFDana", "D"), ("totalFModal", "M")):
        row = db.session.execute(
            text(
                """
                SELECT SUM(outstanding) AS totalpembiayaan
                FROM V_CustomerOutstanding
                WHERE Cons_Leas = :cl AND APLESS = :apless AND APPL_NO <> :applno
                """
            ),
            {"cl": cons_leas, "apless": apless, "applno": applno},
        ).fetchone()
        result[key] = _n(row.totalpembiayaan) if row else 0.0
    return result

def _fin_dp_minimum(applno: str) -> dict:
    deviation = db.session.execute(
        text("SELECT down_payment, base_rate FROM deviation_dp WHERE appl_no = :applno"),
        {"applno": applno},
    ).fetchone()
    down_payment = _fin_str(deviation.down_payment) if deviation else ""
    base_rate = _fin_str(deviation.base_rate) if deviation else ""

    investasi = multiguna = None
    as_of = npf = None

    def read(proc: str):
        return db.session.execute(text(f"EXEC {proc} :applno"), {"applno": applno}).fetchone()

    if down_payment == "1":
        row = read("USP_CHECK_DEVIASI_DP")
        if row:
            investasi = row.I
            multiguna = row.M
            as_of = row.tgl_acuan
            npf = row.npf
            if _fin_str(investasi) == "" or _fin_str(multiguna) == "":
                investasi = multiguna = None

    if investasi is None or multiguna is None:
        row = read("USP_CHECK_DP")
        if row:
            investasi = row.I
            multiguna = row.M
            as_of = row.tgl_acuan
            npf = row.npf

    if hasattr(as_of, "strftime"):
        as_of_text = as_of.strftime("%Y-%m-%d")
    else:
        as_of_text = _fin_str(as_of)
    npf_text = _fin_str(npf)

    return {
        "downPayment": down_payment,
        "freeBaseRate": base_rate == "1",
        "investasi": None if _fin_str(investasi) == "" else _n(investasi),
        "multiguna": None if _fin_str(multiguna) == "" else _n(multiguna),
        "asOfDate": as_of_text,
        "npf": npf_text,
        "notif": f"NPF as of {as_of_text} is {npf_text}%, then Min. DP which allowed is ",
    }

def _fin_dp_errors(purpoffinc: str, security_persen: float, dp: dict) -> list:
    errors = []
    if dp["downPayment"] == "" and purpoffinc == "4" and security_persen < 5:
        errors.append(dp["notif"] + "5%")
    if purpoffinc == "3" and dp["investasi"] is not None and security_persen < dp["investasi"]:
        errors.append(dp["notif"] + fff.php_str(dp["investasi"]) + "%")
    if purpoffinc == "5" and dp["multiguna"] is not None and security_persen < dp["multiguna"]:
        errors.append(dp["notif"] + fff.php_str(dp["multiguna"]) + "%")
    return errors

_FIN_ACCOUNT_BLOCK_MESSAGE = (
    "*Financing cannot be changed, because your bank account is on approval at "
    "Operation Admin (OA). Please contact OA for Approve or Reject CAM."
)

def _fin_account_blocked(applno: str) -> bool:
    row = db.session.execute(
        text(
            """
            SELECT TOP 1 APPR_STS, APPR_ID, APPR_DATE
            FROM MCMOCAMACCSTATUS WITH (NOLOCK)
            WHERE APPL_NO = :applno ORDER BY [NO] DESC
            """
        ),
        {"applno": applno},
    ).fetchone()
    if not row:
        return False
    appr_sts = _fin_str(row.APPR_STS)
    appr_id = _fin_str(row.APPR_ID).lower()
    appr_dt = _to_date(row.APPR_DATE)
    if appr_sts == "A" and appr_id in ("ricky irawan", "denny_dilham"):
        return False
    if appr_sts == "R":
        pending = db.session.execute(
            text("SELECT 1 FROM MCMOCAMACCSTATUS WITH (NOLOCK) WHERE APPL_NO = :applno AND APPR_STS = 'P'"),
            {"applno": applno},
        ).fetchone()
        return bool(pending)
    if appr_sts == "P":
        return True
    if appr_sts == "A" and appr_id == "edisamsuri" and appr_dt and appr_dt < pydt.date(2022, 11, 1):
        return False
    return True

def _fin_notary_context(applno: str):
    fdc_row = db.session.execute(
        text("SELECT Fdc_Area FROM CAFEQUIP WITH (NOLOCK) WHERE APPL_NO = :applno"),
        {"applno": applno},
    ).fetchone()
    notary_row = db.session.execute(
        text("SELECT Notary_no FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :applno"),
        {"applno": applno},
    ).fetchone()
    return (fdc_row.Fdc_Area if fdc_row else None), (notary_row.Notary_no if notary_row else None)

def _fin_notary_default(applno: str) -> dict:
    fdc_cd, notary_no = _fin_notary_context(applno)
    row = db.session.execute(
        text(
            """
            SELECT Gross, Nett_Fiduciary, Nett_Notary FROM CLFNOTARY WITH (NOLOCK)
            WHERE Notary_no = :notary_no AND Fdc_Area = :fdc_cd
            """
        ),
        {"notary_no": notary_no, "fdc_cd": fdc_cd},
    ).fetchone()
    return {
        "notaryFee": fff.php_round(_n(row.Gross)) if row else 0,
        "notary": fff.php_round(_n(row.Nett_Notary)) if row else 0,
        "fiduciary": fff.php_round(_n(row.Nett_Fiduciary)) if row else 0,
    }

def _fin_notary_by_otr(applno: str, l_amount: float) -> Optional[dict]:
    fdc_cd, notary_no = _fin_notary_context(applno)
    rows = db.session.execute(
        text(
            """
            SELECT Gross, Nett_Fiduciary, Nett_Notary, OTR_min, OTR_max FROM CLFNOTARY WITH (NOLOCK)
            WHERE Notary_no = :notary_no AND Fdc_Area = :fdc_cd
            """
        ),
        {"notary_no": notary_no, "fdc_cd": fdc_cd},
    ).fetchall()
    found = None
    for r in rows:
        otr_min = _n(r.OTR_min)
        has_max = r.OTR_max is not None and _n(r.OTR_max) != 0
        if has_max:
            matched = otr_min <= l_amount <= _n(r.OTR_max)
        else:
            matched = l_amount >= otr_min
        if matched:
            found = {
                "notaryFee": fff.php_round(_n(r.Gross)),
                "notary": fff.php_round(_n(r.Nett_Notary)),
                "fiduciary": fff.php_round(_n(r.Nett_Fiduciary)),
            }
    return found

def _fin_percentage(applno: str) -> float:
    row = db.session.execute(
        text("SELECT CAST([Percentage] AS float) AS pct FROM COMM_PARTY WITH (NOLOCK) WHERE APPL_NO = :applno"),
        {"applno": applno},
    ).fetchone()
    if row is None or row.pct is None:
        return 17.5
    return _n(row.pct)

def _fin_income_base(applno: str) -> dict:
    row = db.session.execute(
        text("SELECT GROSS_PREM, NET_COM FROM CAFDISB WITH (NOLOCK) WHERE APPL_NO = :applno"),
        {"applno": applno},
    ).fetchone()
    gross = _n(row.GROSS_PREM) if row else 0.0
    net = _n(row.NET_COM) if row else 0.0
    return {"grossPremium": gross, "netCommission": net, "insuranceIncome": gross - net}

def _fin_income_totals(fin_type: str, percentage: float, insurance_income: float, sums: dict,
                       surv_inc: float, base_surv: float, surv_inc2: float, base_surv2: float,
                       prov_inc: float, gross_int_rate: float, net_int_rate: float) -> dict:
    ttlsurv = surv_inc + sums["survey"]
    if fin_type == "I" and ttlsurv >= 2500000:
        ttlsurv = 2500000
    elif fin_type == "S" and ttlsurv >= 5000000:
        ttlsurv = 5000000
    ttlsurv2 = surv_inc2 + sums["surveyFee2"]
    ttlprov = prov_inc + sums["provision"]
    ttlint = gross_int_rate + sums["interest"]
    excint = ttlint - net_int_rate
    ttlsubtot = ttlprov + ttlint + ttlsurv + insurance_income + ttlsurv2
    ttlexctot = insurance_income + (ttlsurv - base_surv) + ttlprov + excint + (ttlsurv2 - base_surv2)
    maxcomm = ttlsubtot * percentage / 100
    return {
        "ttlSubTot": ttlsubtot,
        "ttlExcTot": ttlexctot,
        "maxComm": maxcomm,
    }

def _fin_reset_survey_fee2(applno: str) -> None:
    rows = db.session.execute(
        text("SELECT SubsidyType FROM CafcontSubsidyDetail WHERE AmountType = 'SurveyFee2' AND APPL_No = :applno"),
        {"applno": applno},
    ).fetchall()
    for row in rows:
        subsidy_type = row.SubsidyType
        amount_row = db.session.execute(
            text(
                "SELECT Amount FROM CafcontSubsidyDetail WITH (NOLOCK) "
                "WHERE APPL_NO = :applno AND SubsidyType = :st AND AmountType = 'SurveyFee2'"
            ),
            {"applno": applno, "st": subsidy_type},
        ).fetchone()
        amount = _n(amount_row.Amount) if amount_row else 0.0
        if subsidy_type in ("IA", "SA"):
            cur = db.session.execute(
                text("SELECT SUBSIDY FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :applno"), {"applno": applno}
            ).fetchone()
            remainder = max(_n(cur.SUBSIDY if cur else 0) - amount, 0)
            db.session.execute(
                text("UPDATE CAFCONT SET SUBSIDY = :s WHERE APPL_NO = :applno"), {"s": remainder, "applno": applno}
            )
        elif subsidy_type == "SD":
            cur = db.session.execute(
                text("SELECT Subsidy_Supp FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :applno"), {"applno": applno}
            ).fetchone()
            remainder = max(_n(cur.Subsidy_Supp if cur else 0) - amount, 0)
            db.session.execute(
                text("UPDATE CAFCONT SET Subsidy_Supp = :s WHERE APPL_NO = :applno"), {"s": remainder, "applno": applno}
            )
        db.session.execute(
            text(
                "DELETE FROM CafcontSubsidyDetail "
                "WHERE APPL_NO = :applno AND SubsidyType = :st AND AmountType = 'SurveyFee2'"
            ),
            {"applno": applno, "st": subsidy_type},
        )

def _fin_clear(applno: str, fin_type: str) -> None:
    current = db.session.execute(
        text("SELECT Cons_Leas FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :applno"), {"applno": applno}
    ).fetchone()
    if fin_type and current and _fin_str(current.Cons_Leas) != fin_type:
        db.session.execute(
            text("UPDATE CAFCONT SET Cons_Leas = :fin_type WHERE APPL_NO = :applno"),
            {"fin_type": fin_type, "applno": applno},
        )
    db.session.execute(text("DELETE FROM CafcontSubsidyDetail WHERE APPL_NO = :applno"), {"applno": applno})
    db.session.execute(
        text(
            """
            UPDATE CAFCONT SET AdmFee = 0, PROVISION = 0, BaseAdmFee = 0, BusinessTrip_Fee = 0,
                   Refund_Supp = 0, SUBSIDY = 0, Subsidy_Supp = 0
            WHERE APPL_NO = :applno
            """
        ),
        {"applno": applno},
    )

def _fin_default_base_surv(fin_type: str) -> float:
    return 0.0 if fin_type == "W" else 1500000.0

def _subsidy_sums(applno: str) -> dict:
    rows = db.session.execute(
        text(
            """
            SELECT b.AmountType, SUM(b.Amount) AS jumlah
            FROM CAFCONT a WITH (NOLOCK)
                INNER JOIN CafcontSubsidyDetail b ON a.APPL_NO = b.APPL_No
            WHERE a.APPL_NO = :applno
            GROUP BY b.AmountType
            """
        ),
        {"applno": applno},
    ).fetchall()
    sums = {r.AmountType: _n(r.jumlah) for r in rows}
    return {
        "dp": sums.get("DP", 0.0),
        "installment": sums.get("Installment", 0.0),
        "insurance": sums.get("Insurance", 0.0),
        "survey": sums.get("Survey", 0.0),
        "provision": sums.get("Provision", 0.0),
        "interest": sums.get("Interest", 0.0),
        "surveyFee2": sums.get("SurveyFee2", 0.0),
    }

def _subsidy_source_totals(applno: str) -> dict:
    dealer_row = db.session.execute(
        text(
            """
            SELECT SUM(b.Amount) AS jumlah
            FROM CAFCONT a WITH (NOLOCK)
                INNER JOIN CafcontSubsidyDetail b ON a.APPL_NO = b.APPL_No
            WHERE a.APPL_NO = :applno AND b.SubsidyType = 'SD'
              AND b.AmountType IN ('Survey', 'Provision', 'Interest', 'SurveyFee2')
            """
        ),
        {"applno": applno},
    ).fetchone()
    apm_row = db.session.execute(
        text(
            """
            SELECT SUM(b.Amount) AS jumlah
            FROM CAFCONT a WITH (NOLOCK)
                INNER JOIN CafcontSubsidyDetail b ON a.APPL_NO = b.APPL_No
            WHERE a.APPL_NO = :applno AND b.SubsidyType IN ('SA', 'IA')
              AND b.AmountType IN ('Survey', 'Provision', 'Interest', 'SurveyFee2')
            """
        ),
        {"applno": applno},
    ).fetchone()
    return {
        "fromDealer": _n(dealer_row.jumlah) if dealer_row else 0.0,
        "fromApm": _n(apm_row.jumlah) if apm_row else 0.0,
    }

AMOUNT_TYPE_LABELS = {
    "DP": "For DP",
    "Installment": "For Installment",
    "Insurance": "For Insurance",
    "Survey": "For Survey Fee 1",
    "SurveyFee2": "For Survey Fee 2",
    "Provision": "For Provision Fee",
    "Interest": "For Interest",
}

SUBSIDY_TYPE_LABELS = {
    "SD": "Subsidy From Dealer",
    "SA": "Subsidy From APM",
    "IA": "Incentive From APM",
    "RD": "Refund To Dealer",
}

def _subsidy_grid(applno: str) -> list[dict]:
    rows = db.session.execute(
        text(
            """
            SELECT b.SubsidyType, b.Amount, b.AmountType
            FROM CAFCONT a WITH (NOLOCK)
            INNER JOIN CafcontSubsidyDetail b ON a.APPL_NO = b.APPL_No
            WHERE a.APPL_NO = :applno
            """
        ),
        {"applno": applno},
    ).fetchall()
    return [
        {
            "subsidyType": r.SubsidyType,
            "subsidyTypeLabel": SUBSIDY_TYPE_LABELS.get(r.SubsidyType, r.SubsidyType),
            "amountType": r.AmountType,
            "amountTypeLabel": AMOUNT_TYPE_LABELS.get(r.AmountType, r.AmountType),
            "amount": _n(r.Amount),
            "deletable": r.SubsidyType != "RD",
        }
        for r in rows
    ]

def _fin_lookups(fin_type: str) -> dict:
    amor_sql = (
        "SELECT L_Type, name FROM MSTAMORTYPE WITH (NOLOCK) WHERE L_Type = '6'"
        if fin_type == "W"
        else "SELECT L_Type, name FROM MSTAMORTYPE WITH (NOLOCK) WHERE L_Type <> '4'"
    )
    return {
        "contractStatuses": [
            {"value": "N", "label": "New"}, {"value": "R1", "label": "R1"},
            {"value": "R2", "label": "R2"}, {"value": "R3", "label": "R3"},
            {"value": "R4", "label": "R4"}, {"value": "R5", "label": "R5"},
            {"value": ">5", "label": ">5"},
        ],
        "currencies": [
            {"value": _fin_str(r.CURR_CODE), "label": r.DESCRIP}
            for r in db.session.execute(text("SELECT CURR_CODE, DESCRIP FROM UMFCURR WITH (NOLOCK)")).fetchall()
        ],
        "paymentMethods": [
            {"value": _fin_str(r.Col_Type), "label": r.name}
            for r in db.session.execute(text("SELECT Col_Type, name FROM MSTCOLLTYPE WITH (NOLOCK)")).fetchall()
        ],
        "amortizationTypes": [
            {"value": _fin_str(r.L_Type), "label": r.name}
            for r in db.session.execute(text(amor_sql)).fetchall()
        ],
        "disbursementTypes": [
            {"value": _fin_str(r.Disb_Type), "label": r.name}
            for r in db.session.execute(text("SELECT Disb_Type, name FROM MSTDISBTYPE WITH (NOLOCK)")).fetchall()
        ],
        # "agencyNames": [
        #     r.Agency_nm
        #     for r in db.session.execute(text("SELECT Agency_nm FROM umf_agency WITH (NOLOCK)")).fetchall()
        # ],
    }

def _fin_empty_form() -> dict:
    return {
        "contSts": "N", "currCode": "IDR", "disbType": "", "colType": "TR", "advArr": "V",
        "fixFloat": "X", "floatCyc": "", "lType": "0", "tenor": "", "payCycle": 1,
        "gPeriod": 0, "gIntRate": "", "gIntAmt": "",
        "lAmount": "", "security": "", "securityPersen": "",
        "creditAmt": "", "commAdmFee": "", "otherLoan": "", "provisionLoan": "",
        "surveyLoan2": "", "flatRate": "", "mlciFlat": "", "declRate": "", "mlciDecl": "",
        "declRateFull": "", "mlciDeclFull": "", "declRate1000": "",
        "rental": "", "mlciRent": "", "tenor1000": "", "flatRate1000": "",
        "noStep": "", "steps": [],
        "notaryFee": "", "notary": "", "fiduciary": "", "otherFee": "", "businessTripFee": "",
        "residual": "",
        "bbn": {"via": "", "paidBy": "", "bbnLoan": "", "agencyName": "", "bbnFee": "",
                "agencyFeeGross": "", "agencyFeeNet": ""},
        "survInc": "", "baseSurv": "", "survInc2": 0, "baseSurv2": 0, "baseSurv2Default": 0,
        "provInc": "", "creditProtection": "", "guaranteed": "0",
        "grossIntRate": 0, "netIntRate": 0, "eligibleComm": 0,
        "loanToValue": "", "crossNo": "",
    }

@cam_edit_bp.route("/fin-financing", methods=["GET"])
@login_required
def get_financing():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    fin_type = _fin_str(request.args.get("finType"))
    cont_type_param = _fin_str(request.args.get("contType"))
    purpoffinc_param = _fin_str(request.args.get("purpoffinc"))
    if not apless or not applno:
        return jsonify({"error": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"blocked": True, "message": block_message}), 409

    head = db.session.execute(
        text(
            """
            SELECT a.Cons_Leas, a.Cont_type, a.L_AMOUNT, e.CONDITION
            FROM CAFCONT a WITH (NOLOCK)
                LEFT JOIN CAFEQUIP e WITH (NOLOCK) ON e.APPL_NO = a.APPL_NO
            WHERE a.APPL_NO = :applno AND a.APLESS = :apless
            """
        ),
        {"applno": applno, "apless": apless},
    ).fetchone()
    if not head:
        return jsonify({"error": "Not found"}), 404

    fin_type = fin_type or _fin_str(head.Cons_Leas)
    cont_type = cont_type_param or _fin_str(head.Cont_type)
    purpoffinc = purpoffinc_param

    try:
        profile = _fin_customer_profile(applno)
        restricted = _fin_restricted(profile["lesseeType"], cont_type, profile["nationality"])
        total_outs_before = _fin_total_outs_before(apless)

        survey_locked = False
        survey_yes = None
        guaranteed_yes = False
        lock_reason = ""

        if restricted:
            survey_locked = True
            lock_reason = "Lessee type PT, contract type RS1/RS0, or nationality US/USA"
            has_cigna = db.session.execute(
                text("SELECT 1 FROM cigna_fee WITH (NOLOCK) WHERE APPL_NO = :applno"), {"applno": applno}
            ).fetchone()
            if has_cigna:
                db.session.execute(text("DELETE FROM cigna_fee WHERE APPL_NO = :applno"), {"applno": applno})
                _fin_reset_survey_fee2(applno)

        cigna_row = db.session.execute(
            text(
                """
                SELECT Survey_Fee_Cigna, Survey_Base_Rate_Cigna, Survey_Loan_Cigna,
                       Credit_Protection, GuarantedAcceptance
                FROM cigna_fee WITH (NOLOCK) WHERE APPL_NO = :applno
                """
            ),
            {"applno": applno},
        ).fetchone()
        survey_yes = bool(cigna_row and _n(cigna_row.Survey_Fee_Cigna) > 0)

        if not restricted:
            if purpoffinc == "3":
                if (profile["daysPast55"] or 0) > 0:
                    survey_locked = True
                    survey_yes = False
                    lock_reason = "Purpose 3 and customer is older than 55"
                else:
                    survey_locked = False
            if purpoffinc in ("4", "5"):
                if profile["daysTo65AfterTenor"] is not None and profile["daysTo65AfterTenor"] < 0:
                    survey_locked = True
                    survey_yes = False
                    lock_reason = "Purpose 4/5 and customer is older than 65 at end of tenor"
                else:
                    survey_locked = False

        dp = _fin_dp_minimum(applno)
        percentage = _fin_percentage(applno)
        outstanding_totals = _fin_customer_outstanding(apless, applno)
        account_blocked = _fin_account_blocked(applno)
        income_base = _fin_income_base(applno)
        sums = _subsidy_sums(applno)

        form = _fin_empty_form()
        has_data = _n(head.L_AMOUNT) != 0

        if has_data:
            c = db.session.execute(
                text(
                    """
                    SELECT a.PURPOFFINC, a.CURR_CODE, a.L_AMOUNT, a.SECURITY, a.DECLRATE, a.FLATRATE, a.COL_TYPE,
                           a.ADV_ARR, a.L_TYPE, a.FIX_FLOAT, a.FLOAT_CYC, a.TENOR, a.PAY_CYCLE, a.RENTAL,
                           a.MLCIDECL, a.MLCIFLAT, a.MLCIRENT, a.Gross, a.OTHERFEE, a.ContSts, a.AdmFee,
                           a.Otherloan, a.DECLRATE1000, a.FLATRATE1000, a.tenor1000, a.Notary, a.Fiduciary,
                           a.Disb_Type, a.Cont_type, a.G_PERIOD, a.G_INT_RATE, a.G_INT_AMT, a.RESIDUAL,
                           a.PROVISION, a.BusinessTrip_Fee, a.BaseAdmFee, a.InterestIncome,
                           a.BaseInterestFee, a.Max_Fee
                    FROM CAFCONT a WITH (NOLOCK)
                    WHERE a.APPL_NO = :applno AND a.APLESS = :apless
                    """
                ),
                {"applno": applno, "apless": apless},
            ).fetchone()

            insu = db.session.execute(
                text("SELECT CREDITAMT, CommAdmFee FROM CAFINSU WITH (NOLOCK) WHERE APPL_NO = :applno"),
                {"applno": applno},
            ).fetchone()
            bbn = db.session.execute(
                text(
                    """
                    SELECT bbnvia, paidby, serviceagencyNM, BBNloan, BBN_FEE, ServiceAgencyFee, NettServiceAgencyFee
                    FROM BBN WITH (NOLOCK) WHERE APPL_NO = :applno
                    """
                ),
                {"applno": applno},
            ).fetchone()
            prov = db.session.execute(
                text("SELECT Prov_loan FROM Provision_Loan WITH (NOLOCK) WHERE APPL_NO = :applno"),
                {"applno": applno},
            ).fetchone()

            l_amount = _n(c.L_AMOUNT)
            security = _n(c.SECURITY)
            l_type = _fin_str(c.L_TYPE)
            fix_float = _fin_str(c.FIX_FLOAT)
            base_surv = _n(c.BaseAdmFee)
            if base_surv == 0:
                base_surv = _fin_default_base_surv(fin_type)

            steps = []
            if l_type == "3":
                step_rows = db.session.execute(
                    text("SELECT STEP, NO_STEP, PMT_STEP, MLCI_STEP FROM CAFSTEP WITH (NOLOCK) WHERE APPL_NO = :applno ORDER BY STEP"),
                    {"applno": applno},
                ).fetchall()
                steps = [
                    {
                        "month": _n(r.NO_STEP),
                        "rental": fff.php_round(_n(r.PMT_STEP)),
                        "base": fff.php_round(_n(r.MLCI_STEP)),
                    }
                    for r in step_rows
                ]

            bbn_loan = _n(bbn.BBNloan) if bbn else 0.0
            prov_loan = _n(prov.Prov_loan) if prov else 0.0
            credit_amt = _n(insu.CREDITAMT) if insu else 0.0
            survey_loan2 = _n(cigna_row.Survey_Loan_Cigna) if cigna_row else 0.0
            tot_net = l_amount - security + credit_amt + _n(c.Otherloan) + bbn_loan + prov_loan

            form.update({
                "contSts": _fin_str(c.ContSts) or "N",
                "currCode": _fin_str(c.CURR_CODE) or "IDR",
                "disbType": _fin_str(c.Disb_Type),
                "colType": _fin_str(c.COL_TYPE) or "TR",
                "advArr": _fin_str(c.ADV_ARR) or "V",
                "fixFloat": fix_float or "X",
                "floatCyc": _fin_str(c.FLOAT_CYC) if fix_float == "L" else "",
                "lType": l_type,
                "tenor": _n(c.TENOR) if c.TENOR is not None else "",
                "payCycle": _n(c.PAY_CYCLE, 1) if c.PAY_CYCLE is not None else "",
                "businessTripFee": fff.php_round(_n(c.BusinessTrip_Fee)),
                "baseSurv": base_surv,
                "grossIntRate": _n(c.InterestIncome),
                "netIntRate": _n(c.BaseInterestFee),
                "eligibleComm": _n(c.Max_Fee),
                "lAmount": fff.php_round(l_amount),
                "security": fff.php_round(security),
                "securityPersen": fff.php_round(security * 100 / l_amount, 2) if l_amount else "",
                "otherLoan": fff.php_round(_n(c.Otherloan)),
                "gPeriod": _n(c.G_PERIOD),
                "gIntRate": fff.trunc4(c.G_INT_RATE),
                "gIntAmt": fff.php_round(_n(c.G_INT_AMT)),
                "creditAmt": fff.php_round(credit_amt),
                "commAdmFee": fff.php_round(_n(insu.CommAdmFee)) if insu else 0,
                "steps": steps,
                "noStep": len(steps) if steps else "",
                "tenor1000": _n(c.tenor1000) if l_type == "4" and c.tenor1000 is not None else "",
                "flatRate1000": _n(c.FLATRATE1000) if l_type == "4" and c.FLATRATE1000 is not None else "",
                "declRate1000": _n(c.DECLRATE1000) if c.DECLRATE1000 is not None else "",
                "survInc": _n(c.AdmFee),
                "notary": fff.php_round(_n(c.Notary)),
                "flatRate": _n(c.FLATRATE) if c.FLATRATE is not None else "",
                "mlciFlat": _n(c.MLCIFLAT) if c.MLCIFLAT is not None else "",
                "notaryFee": fff.php_round(_n(c.Gross)),
                "fiduciary": fff.php_round(_n(c.Fiduciary)),
                "declRateFull": _n(c.DECLRATE) if c.DECLRATE is not None else "",
                "mlciDeclFull": _n(c.MLCIDECL) if c.MLCIDECL is not None else "",
                "declRate": fff.trunc4(c.DECLRATE) if c.DECLRATE is not None else "",
                "mlciDecl": fff.trunc4(c.MLCIDECL) if c.MLCIDECL is not None else "",
                "otherFee": fff.php_round(_n(c.OTHERFEE)),
                "rental": fff.php_round(_n(c.RENTAL)),
                "mlciRent": fff.php_round(_n(c.MLCIRENT)),
                "residual": fff.php_round(_n(c.RESIDUAL)),
                "bbn": {
                    "via": _fin_str(bbn.bbnvia) if bbn else "",
                    "paidBy": _fin_str(bbn.paidby) if bbn else "",
                    "bbnLoan": fff.php_round(bbn_loan),
                    "agencyName": _fin_str(bbn.serviceagencyNM) if bbn else "",
                    "bbnFee": fff.php_round(_n(bbn.BBN_FEE)) if bbn else 0,
                    "agencyFeeGross": fff.php_round(_n(bbn.ServiceAgencyFee)) if bbn else 0,
                    "agencyFeeNet": fff.php_round(_n(bbn.NettServiceAgencyFee)) if bbn else 0,
                },
                "provisionLoan": fff.php_round(prov_loan),
                "provInc": _n(c.PROVISION),
                "baseSurv2": _n(cigna_row.Survey_Base_Rate_Cigna) if cigna_row else 0,
                "baseSurv2Default": _n(cigna_row.Survey_Base_Rate_Cigna) if cigna_row else 0,
                "survInc2": _n(cigna_row.Survey_Fee_Cigna) if cigna_row else 0,
                "surveyLoan2": fff.php_round(survey_loan2),
                "creditProtection": fff.php_round(_n(cigna_row.Credit_Protection)) if cigna_row else 0,
            })

            guaranteed_yes = bool(cigna_row and _fin_str(cigna_row.GuarantedAcceptance) == "1")
            tot_net2 = tot_net
            if survey_loan2 != 0:
                tot_net2 = tot_net + survey_loan2
                total_with_outs = total_outs_before + tot_net2
                if not restricted:
                    if purpoffinc == "3":
                        if total_with_outs > 1500000000:
                            survey_locked = True
                            survey_yes = False
                            lock_reason = "Purpose 3 and outstanding + Total Net Finance > 1,500,000,000"
                        else:
                            survey_locked = False
                    if purpoffinc in ("4", "5"):
                        if total_with_outs > 1000000000:
                            survey_locked = True
                            survey_yes = False
                            lock_reason = "Purpose 4/5 and outstanding + Total Net Finance > 1,000,000,000"
                        else:
                            survey_locked = False

            if (tot_net2 + total_outs_before) > 300000000 or not survey_yes:
                guaranteed_yes = False

            ltv_row = db.session.execute(
                text("SELECT Net_Finance FROM V_NetFinance WHERE APPL_NO = :applno"), {"applno": applno}
            ).fetchone()
            if ltv_row and l_amount:
                form["loanToValue"] = fff.php_round(_n(ltv_row.Net_Finance) / l_amount * 100, 2)
        else:
            base_row = db.session.execute(
                text("SELECT BaseAdmFee FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :applno AND APLESS = :apless"),
                {"applno": applno, "apless": apless},
            ).fetchone()
            base_surv = _n(base_row.BaseAdmFee) if base_row else 0.0
            form["baseSurv"] = base_surv if base_surv != 0 else _fin_default_base_surv(fin_type)
            guaranteed_yes = False

        if not survey_yes:
            form["survInc2"] = 0
            form["baseSurv2"] = 0
            form["surveyLoan2"] = 0

        cross_rows = db.session.execute(
            text("SELECT CROSSNO FROM TACrossNo WITH (NOLOCK) WHERE APPL_NO = :applno AND CROSS_TYPE = 'CN'"),
            {"applno": applno},
        ).fetchall()
        if cross_rows:
            form["crossNo"] = _fin_str(cross_rows[-1].CROSSNO)

        cleared = bool(fin_type) and _fin_str(head.Cons_Leas) != fin_type
        if cleared:
            _fin_clear(applno, fin_type)
            keep_surv_inc = form["survInc"]
            keep_base_surv = form["baseSurv"]
            keep_cross = form["crossNo"]
            keep_loan2 = form["surveyLoan2"]
            keep_inc2 = form["survInc2"]
            keep_base2 = form["baseSurv2"]
            keep_base2_default = form["baseSurv2Default"]
            keep_credit_protection = form["creditProtection"]
            form = _fin_empty_form()
            form.update(_fin_notary_default(applno))
            form.update({
                "contSts": "N", "disbType": "N", "survInc": keep_surv_inc, "baseSurv": keep_base_surv,
                "crossNo": keep_cross, "surveyLoan2": keep_loan2, "survInc2": keep_inc2,
                "baseSurv2": keep_base2, "baseSurv2Default": keep_base2_default,
                "creditProtection": keep_credit_protection, "tenor": "",
            })
            sums = _subsidy_sums(applno)

        form["guaranteed"] = "1" if guaranteed_yes else "0"

        contract_type_row = db.session.execute(
            text("SELECT Cont_type, name FROM MSTCONTTYPE WITH (NOLOCK) WHERE Cont_type = :ct"),
            {"ct": cont_type},
        ).fetchone()
        purpose_row = db.session.execute(
            text("SELECT [DESC] FROM MSTPURPOFFINC WITH (NOLOCK) WHERE PURPOFFINC = :p AND Flag_Active = '1'"),
            {"p": purpoffinc},
        ).fetchone()
        npwp_row = db.session.execute(
            text("SELECT NPWP FROM CAFLESS WITH (NOLOCK) WHERE APLESS = :apless"), {"apless": apless}
        ).fetchone()

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("fin-financing load failed for %s", applno)
        return jsonify({"error": "Failed to load Financing data."}), 500

    return jsonify({
        "apless": apless,
        "applno": applno,
        "finType": fin_type,
        "newCar": {"NEW": "2", "USED": "1"}.get(_fin_str(head.CONDITION).upper(), ""),
        "hasData": has_data,
        "cleared": cleared,
        "accountBlocked": account_blocked,
        "accountBlockMessage": _FIN_ACCOUNT_BLOCK_MESSAGE if account_blocked else "",
        "npwp": _fin_str(npwp_row.NPWP) if npwp_row else "",
        "contract": {
            "contType": _fin_str(contract_type_row.Cont_type) if contract_type_row else cont_type,
            "contTypeName": contract_type_row.name if contract_type_row else "",
            "consLeas": _fin_str(head.Cons_Leas),
            "purpoffinc": purpoffinc,
            "purpoffincDesc": purpose_row.DESC if purpose_row else "",
        },
        "form": form,
        "flags": {
            "restricted": restricted,
            "surveyFee2Locked": survey_locked,
            "surveyFee2LockReason": lock_reason if survey_locked else "",
            "surveyFee2": "1" if survey_yes else "0",
            "lesseeType": profile["lesseeType"],
            "nationality": profile["nationality"],
            "ageYears": profile["ageYears"],
            "ageMonths": profile["ageMonths"],
            "ageDays": profile["ageDays"],
            "daysPast55": profile["daysPast55"] or 0,
            "totalOutsBefore": total_outs_before,
            "notaryEditable": fin_type == "W",
        },
        "dpMinimum": dp,
        "income": {
            **income_base,
            "percentage": percentage,
            "subsidy": sums,
            "subsidySourceTotals": _subsidy_source_totals(applno),
        },
        "outstanding": outstanding_totals,
        "lookups": _fin_lookups(fin_type),
    })

@cam_edit_bp.route("/fin-financing/income-summary", methods=["GET"])
@login_required
def financing_income_summary():
    applno = request.args.get("applno", "")
    if not applno:
        return jsonify({"error": "applno is required"}), 400
    return jsonify({
        "subsidy": _subsidy_sums(applno),
        "subsidySourceTotals": _subsidy_source_totals(applno),
        "grid": _subsidy_grid(applno),
    })

def _fin_parse_steps(payload: dict) -> tuple[list, list, list]:
    months, rentals, bases = [], [], []
    for step in payload.get("steps") or []:
        months.append(_n(step.get("month")))
        rentals.append(_n(step.get("rental")))
        bases.append(_n(step.get("base")))
    return months, rentals, bases

def _fin_limit_error(fin_type: str, facility_total: float, strict_equal: bool) -> Optional[str]:
    if fin_type == "D" and facility_total > FUND_FACILITY_LIMIT:
        return (
            "CAM cannot be processed because \"Grand Total Customer's Outstanding Contract & CAM Net Finance "
            "for Fund Facility (FF)\" > Rp. 500.000.000,-"
        )
    if fin_type == "M":
        exceeded = facility_total >= CAPITAL_FACILITY_LIMIT if strict_equal else facility_total > CAPITAL_FACILITY_LIMIT
        if exceeded:
            return (
                "CAM cannot be processed because \"Grand Total Customer's Outstanding Contract & CAM Net Finance "
                "for Business Capital Facility (FMU)\" > Rp. 10.000.000.000,-"
            )
    return None

@cam_edit_bp.route("/fin-financing/calculate", methods=["POST"])
@login_required
def calculate_financing():
    try:
        return _calculate_financing()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("fin-financing calculate failed")
        return jsonify({"error": f"Calculation failed: {type(exc).__name__}: {exc}"}), 500

def _calculate_financing():
    payload = request.get_json(force=True) or {}
    apless = _fin_str(payload.get("apless"))
    applno = _fin_str(payload.get("applno"))
    fin_type = _fin_str(payload.get("finType"))
    if not apless or not applno:
        return jsonify({"error": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"error": block_message}), 409
    if _fin_account_blocked(applno):
        return jsonify({"error": _FIN_ACCOUNT_BLOCK_MESSAGE}), 409

    l_type = _fin_str(payload.get("lType"))
    adv_arr = _fin_str(payload.get("advArr"))
    curr_code = _fin_str(payload.get("currCode")) or "IDR"
    tenor = _n(payload.get("tenor"))
    pay_cycle = _n(payload.get("payCycle"))
    g_period = _n(payload.get("gPeriod"))
    tenor1000 = _n(payload.get("tenor1000"))
    flat_rate1000 = _n(payload.get("flatRate1000"))

    l_amount = _n(payload.get("lAmount"))
    security = _n(payload.get("security"))
    residual = _n(payload.get("residual"))
    credit_amt = _n(payload.get("creditAmt"))
    other_loan = _n(payload.get("otherLoan"))
    bbn_loan = _n(payload.get("bbnLoan"))
    prov_loan = _n(payload.get("provisionLoan"))
    survey_loan2 = _n(payload.get("surveyLoan2"))
    survey_fee2 = _fin_str(payload.get("surveyFee2")) == "1"

    flat_rate_in = payload.get("flatRate")
    mlci_flat_in = payload.get("mlciFlat")
    decl_rate_in = payload.get("declRate")
    mlci_decl_in = payload.get("mlciDecl")
    rental_in = payload.get("rental")
    mlci_rent_in = payload.get("mlciRent")
    decl_full_prev = payload.get("declRateFull")
    mlci_decl_full_prev = payload.get("mlciDeclFull")

    errors = []
    if adv_arr not in ("V", "R"):
        errors.append("In Adv / In Arr must not empty")
    if l_type == "":
        errors.append("Amortization Type must not empty")
    if tenor <= 0:
        errors.append("Tenor must not empty")
    if pay_cycle <= 0:
        errors.append("Payment Cycle must not empty")
    if tenor > 0 and g_period >= tenor:
        errors.append("Grace Period must be less than Tenor")
    if l_type == "4" and (tenor1000 <= 0 or tenor1000 <= g_period):
        errors.append("Customer Tenor must not empty")
    if errors:
        return jsonify({"error": "<br>".join(errors)}), 422

    tot_net = l_amount - security + credit_amt + other_loan + bbn_loan + prov_loan
    tot_net2 = tot_net + survey_loan2
    op = tot_net2
    if op <= 0:
        return jsonify({"error": "Total Net Finance must be filled"}), 422

    rounding = _fin_rounding(curr_code)
    tot_loan = credit_amt + other_loan
    is_fl = fin_type in ("S", "F")
    due = 1 if adv_arr == "V" else 0
    mlci_tax = 0.0

    flat_rate = _n(flat_rate_in)
    mlci_flat = _n(mlci_flat_in)
    decl_rate = _n(decl_rate_in)
    mlci_decl = _n(mlci_decl_in)
    rental = _n(rental_in)
    mlci_rent = _n(mlci_rent_in)
    decl_full = decl_full_prev
    mlci_decl_full = mlci_decl_full_prev
    decl_rate_1000 = payload.get("declRate1000")
    steps_out = None

    try:
        if l_type == "0":
            recompute_rates = (not is_fl) or security == residual
            if not fff.php_empty(flat_rate_in) and not fff.php_empty(mlci_flat_in):
                rental = fff.php_round(fff.pembulatan(fff.calc_rental_flat(op, tenor, pay_cycle, flat_rate, g_period), rounding))
                decl_rate1 = fff.calc_decl_flat(flat_rate, pay_cycle, tenor, g_period, adv_arr)
                mlci_rent = fff.php_round(fff.pembulatan(fff.calc_rental_flat(op, tenor, pay_cycle, mlci_flat, g_period), rounding))
                mlci_decl_full = fff.calc_decl_flat(mlci_flat, pay_cycle, tenor, g_period, adv_arr)
                flat_rate_adj = fff.calc_flat_rental(op, tenor, pay_cycle, rental, g_period)
                decl_full = fff.calc_decl_flat(flat_rate_adj, pay_cycle, tenor, g_period, adv_arr)
            elif not fff.php_empty(decl_rate_in) and not fff.php_empty(mlci_decl_in):
                decl_rate1 = decl_rate
                if not is_fl:
                    rental = fff.php_round(fff.pembulatan(fff.calc_rental_decl(op, tenor, pay_cycle, decl_rate, adv_arr, g_period), rounding))
                    mlci_rent = fff.php_round(fff.pembulatan(fff.calc_rental_decl(op, tenor, pay_cycle, mlci_decl, adv_arr, g_period), rounding))
                else:
                    rental = fff.php_round(fff.pembulatan(fff.calc_rental_decl_fl(l_amount, security, residual, tot_loan, tenor, pay_cycle, decl_rate, adv_arr, g_period), rounding))
                    mlci_rent = fff.php_round(fff.pembulatan(fff.calc_rental_decl_fl(l_amount, security, residual, tot_loan, tenor, pay_cycle, mlci_decl, adv_arr, g_period), rounding))
                decl_full = decl_rate
                mlci_decl_full = mlci_decl
                if recompute_rates:
                    flat_rate = fff.php_round(fff.calc_flat_rental(op, tenor, pay_cycle, rental, g_period), 4)
                    mlci_flat = fff.php_round(fff.calc_flat_rental(op, tenor, pay_cycle, mlci_rent, g_period), 4)
                    decl_full = fff.calc_decl_flat(flat_rate, pay_cycle, tenor, g_period, adv_arr)
            elif not fff.php_empty(rental_in) and not fff.php_empty(mlci_rent_in):
                if recompute_rates:
                    flat_rate = fff.php_round(fff.calc_flat_rental(op, tenor, pay_cycle, rental, g_period), 4)
                    decl_full = fff.calc_decl_flat(flat_rate, pay_cycle, tenor, g_period, adv_arr)
                    mlci_flat = fff.php_round(fff.calc_flat_rental(op, tenor, pay_cycle, mlci_rent, g_period), 4)
                    mlci_decl_full = fff.calc_decl_flat(mlci_flat, pay_cycle, tenor, g_period, adv_arr)
                decl_rate1 = _n(decl_full)
            else:
                return jsonify({"error": "Please fill Flat Rate, Effective Rate, or Installment for both Selling and Base"}), 422

            if fff.php_empty(mlci_decl):
                mlci_decl = _n(mlci_decl_full)
            rate = mlci_decl if decl_rate1 < mlci_decl else decl_rate1
            gross_int_rate = fff.pembulatan((op * tenor / 12 * flat_rate) / 100, rounding)
            refund_int_rate = fff.pembulatan(fff.pv(rate / 1200, tenor / pay_cycle, abs(mlci_rent - rental), 0, due), rounding) - mlci_tax
            refund_int_rate = -abs(refund_int_rate) if decl_rate1 < mlci_decl else abs(refund_int_rate)
            net_int_rate = gross_int_rate - refund_int_rate

        elif l_type == "1":
            decl_rate = 0.0
            decl_full = 0.0
            flat_rate = 0.0
            rental = fff.php_round(fff.pembulatan(op / ((tenor - g_period) / pay_cycle), rounding))
            if not fff.php_empty(mlci_flat_in):
                mlci_rent = fff.php_round(fff.pembulatan(fff.calc_rental_flat(op, tenor, pay_cycle, mlci_flat, g_period), rounding))
                mlci_decl_full = fff.calc_decl_flat(mlci_flat, pay_cycle, tenor, g_period, adv_arr)
            elif not fff.php_empty(mlci_decl_in):
                if not is_fl:
                    mlci_rent = fff.php_round(fff.pembulatan(fff.calc_rental_decl(op, tenor, pay_cycle, mlci_decl, adv_arr, g_period), rounding))
                    mlci_flat = fff.php_round(fff.calc_flat_rental(op, tenor, pay_cycle, mlci_rent, g_period), 4)
                else:
                    mlci_rent = fff.php_round(fff.pembulatan(fff.calc_rental_decl_fl(l_amount, security, residual, tot_loan, tenor, pay_cycle, mlci_decl, adv_arr, g_period), rounding))
                mlci_decl_full = mlci_decl
            elif not fff.php_empty(mlci_rent_in):
                if not is_fl:
                    mlci_flat = fff.php_round(fff.calc_flat_rental(op, tenor, pay_cycle, mlci_rent, g_period), 4)
                    mlci_decl_full = fff.calc_decl_flat(mlci_flat, pay_cycle, tenor, g_period, adv_arr)
                else:
                    mlci_decl_full = mlci_decl
            else:
                mlci_rent = rental
                mlci_decl_full = mlci_decl

            if fff.php_empty(mlci_decl):
                mlci_decl = _n(mlci_decl_full)
            rate = mlci_decl if 0 < mlci_decl else 0.0
            gross_int_rate = 0.0
            refund_int_rate = fff.pembulatan(fff.pv(rate / 1200, tenor / pay_cycle, abs(mlci_rent - rental), 0, due), rounding) - mlci_tax
            refund_int_rate = -abs(refund_int_rate) if 0 < mlci_decl else abs(refund_int_rate)
            net_int_rate = gross_int_rate - refund_int_rate

        elif l_type == "3":
            months, rentals, bases = _fin_parse_steps(payload)
            if not months:
                return jsonify({"error": "No. of Step must not empty"}), 422
            decl_interest = fff.calc_step_rental_decl(op, pay_cycle, adv_arr, months, rentals, tenor)
            decl_full = decl_interest
            mlci_decl_full = mlci_decl
            rental = rentals[0]
            mlci_rent = rental
            if fff.php_empty(mlci_decl):
                mlci_decl = _n(mlci_decl_full)
            rate = mlci_decl if decl_interest < mlci_decl else decl_interest
            tot_gross = 0.0
            tot_step = 0.0
            period = 0
            for month, step_rental, step_base in zip(months, rentals, bases):
                tot_gross += month * step_rental
                diff = abs(step_rental - step_base)
                for _ in range(int(month)):
                    tot_step += fff.pv(rate / 1200, period, 0, diff, due)
                    period += 1
            gross_int_rate = fff.pembulatan(tot_gross - op, rounding)
            refund_int_rate = fff.php_round(fff.pembulatan(abs(tot_step), rounding) - mlci_tax)
            refund_int_rate = -abs(refund_int_rate) if decl_interest < mlci_decl else abs(refund_int_rate)
            net_int_rate = gross_int_rate - refund_int_rate
            flat_rate = 0.0
            mlci_flat = 0.0
            steps_out = [
                {"month": m, "rental": r, "base": b} for m, r, b in zip(months, rentals, bases)
            ]

        elif l_type == "4":
            installment1 = fff.php_round(fff.pembulatan(fff.calc_rental_flat(op, tenor1000, pay_cycle, flat_rate1000, g_period), rounding))
            rental = installment1
            flat_rate1 = fff.calc_flat_rental_1000(op, tenor1000, pay_cycle, installment1, g_period, tenor)
            decl_full = fff.calc_decl_flat_1000(flat_rate1, pay_cycle, tenor, g_period, adv_arr, op, tenor1000, installment1)
            decl_1000_calc = fff.calc_decl_flat_1000(flat_rate1000, pay_cycle, tenor1000, g_period, adv_arr, op, tenor1000, installment1)
            if not fff.php_empty(mlci_flat_in):
                mlci_rent = fff.php_round(fff.pembulatan(fff.calc_rental_flat(op, tenor1000, pay_cycle, mlci_flat, g_period), rounding))
                mlci_decl_full = fff.calc_decl_flat(mlci_flat, pay_cycle, tenor1000, g_period, adv_arr)
            elif not fff.php_empty(mlci_decl_in):
                if not is_fl:
                    mlci_rent = fff.php_round(fff.pembulatan(fff.calc_rental_decl(op, tenor1000, pay_cycle, mlci_decl, adv_arr, g_period), rounding))
                    mlci_flat = fff.php_round(fff.calc_flat_rental(op, tenor1000, pay_cycle, mlci_rent, g_period), 4)
                else:
                    mlci_rent = fff.php_round(fff.pembulatan(fff.calc_rental_decl_fl(l_amount, security, residual, tot_loan, tenor, pay_cycle, mlci_decl, adv_arr, g_period), rounding))
                mlci_decl_full = mlci_decl
            elif not fff.php_empty(mlci_rent_in):
                if not is_fl:
                    mlci_flat = fff.php_round(fff.calc_flat_rental(op, tenor1000, pay_cycle, mlci_rent, g_period), 4)
                    mlci_decl_full = fff.calc_decl_flat(mlci_flat, pay_cycle, tenor1000, g_period, adv_arr)
                else:
                    mlci_decl_full = mlci_decl
            else:
                mlci_decl_full = mlci_decl

            decl_rate_1000 = fff.substr6(decl_1000_calc)
            if fff.php_empty(mlci_decl):
                mlci_decl = _n(mlci_decl_full)
            gross_int_rate = fff.pembulatan((op * tenor1000 / 12 * flat_rate1000) / 100, rounding)
            refund_int_rate = fff.pembulatan(fff.pv(decl_rate_1000 / 1200, tenor1000 / pay_cycle, abs(mlci_rent - rental), 0, due), rounding) - mlci_tax
            refund_int_rate = -abs(refund_int_rate) if decl_rate < mlci_decl else abs(refund_int_rate)
            net_int_rate = gross_int_rate - refund_int_rate

        elif l_type in ("2", "6"):
            if l_type == "2":
                if adv_arr == "V":
                    income = 0.0
                    income_mlci = 0.0
                else:
                    income = (op * decl_rate) * (pay_cycle / 1200)
                    income_mlci = (op * mlci_decl) * (pay_cycle / 1200)
                recovery = (op / (tenor - g_period)) * pay_cycle
                rental_raw = recovery + income
                mlci_rent_raw = recovery + income_mlci
            else:
                rental_raw = (op * decl_rate) / 1200
                mlci_rent_raw = (op * mlci_decl) / 1200
            rental = fff.php_round(fff.pembulatan(rental_raw, rounding))
            mlci_rent = fff.php_round(fff.pembulatan(mlci_rent_raw, rounding))
            decl_full = decl_rate
            mlci_decl_full = mlci_decl
            rate = mlci_decl if decl_rate < mlci_decl else decl_rate
            gross_int_rate = fff.pembulatan((op * tenor / 12 * decl_rate) / 100, rounding)
            refund_int_rate = fff.pembulatan(fff.pv(rate / 1200, tenor / pay_cycle, abs(mlci_rent_raw - rental_raw), 0, due), rounding) - mlci_tax
            refund_int_rate = -abs(refund_int_rate) if decl_rate < mlci_decl else abs(refund_int_rate)
            net_int_rate = gross_int_rate - refund_int_rate

        else:
            return jsonify({"error": f"Unknown Amortization Type '{l_type}'"}), 422
    except (ZeroDivisionError, ValueError, OverflowError):
        return jsonify({"error": "Calculation failed. Please check Tenor, Payment Cycle, rates and amounts."}), 422

    decl_full_num = _n(decl_full)
    mlci_decl_full_num = _n(mlci_decl_full)

    if g_period > 0:
        g_int_rate = fff.trunc4(decl_full_num)
        g_int_amt = fff.php_round(fff.pembulatan((decl_full_num * op) / 1200, rounding))
    else:
        g_int_rate = 0
        g_int_amt = 0

    surv_inc = _n(payload.get("survInc"))
    prov_inc = _n(payload.get("provInc"))
    base_surv = _n(payload.get("baseSurv"))
    surv_inc2 = _n(payload.get("survInc2"))
    base_surv2 = _n(payload.get("baseSurv2"))
    credit_protection = _n(payload.get("creditProtection"))
    guaranteed = "1" if _fin_str(payload.get("guaranteed")) == "1" else "0"

    notary_update = None
    if fin_type != "W":
        try:
            notary_update = _fin_notary_by_otr(applno, l_amount)
        except Exception:
            db.session.rollback()
            current_app.logger.exception("fin-financing notary OTR lookup failed for %s", applno)
            notary_update = None

    try:
        db.session.execute(
            text("UPDATE CAFCONT SET AdmFee = :adm, PROVISION = :prov, BaseAdmFee = :base WHERE APPL_NO = :applno"),
            {"adm": surv_inc, "prov": prov_inc, "base": base_surv, "applno": applno},
        )
        if survey_fee2:
            cigna_rate = fff.cigna_rate_percent(tenor1000 if l_type == "4" else tenor) or 0
            cigna_params = {
                "fee": surv_inc2, "base": base_surv2, "loan": survey_loan2, "cp": credit_protection,
                "ga": guaranteed, "rate": cigna_rate, "applno": applno,
            }
            exists = db.session.execute(
                text("SELECT 1 FROM cigna_fee WITH (NOLOCK) WHERE APPL_NO = :applno"), {"applno": applno}
            ).fetchone()
            if exists:
                db.session.execute(
                    text(
                        """
                        UPDATE cigna_fee SET Survey_Fee_Cigna = :fee, Survey_Base_Rate_Cigna = :base,
                               Survey_Loan_Cigna = :loan, Credit_Protection = :cp,
                               GuarantedAcceptance = :ga, Cigna_Rate = :rate
                        WHERE APPL_NO = :applno
                        """
                    ),
                    cigna_params,
                )
            else:
                db.session.execute(
                    text(
                        """
                        INSERT INTO cigna_fee (appl_no, Survey_Fee_Cigna, Survey_Base_Rate_Cigna, Survey_Loan_Cigna,
                                               Credit_Protection, GuarantedAcceptance, Cigna_Rate)
                        VALUES (:applno, :fee, :base, :loan, :cp, :ga, :rate)
                        """
                    ),
                    cigna_params,
                )
        else:
            db.session.execute(text("DELETE FROM cigna_fee WHERE APPL_NO = :applno"), {"applno": applno})
            tot_net2 = tot_net
            surv_inc2 = 0.0
            base_surv2 = 0.0
            survey_loan2 = 0.0
            credit_protection = 0.0
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("fin-financing calculate write failed for %s", applno)
        return jsonify({"error": f"Calculation failed while saving fees: {type(exc).__name__}: {exc}"}), 500

    outstanding_totals = _fin_customer_outstanding(apless, applno)
    facility_outstanding = outstanding_totals["totalFDana"] if fin_type == "D" else outstanding_totals["totalFModal"]
    grand_total = facility_outstanding + int(tot_net2) if fin_type in ("D", "M") else None
    limit_error = _fin_limit_error(fin_type, grand_total or 0, strict_equal=True) if grand_total is not None else None
    if limit_error:
        try:
            _fin_clear(applno, fin_type)
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception("fin-financing clear after limit failed for %s", applno)
        return jsonify({"error": limit_error, "shouldClear": True}), 422

    sums = _subsidy_sums(applno)
    income_base = _fin_income_base(applno)
    totals = _fin_income_totals(
        fin_type, _fin_percentage(applno), income_base["insuranceIncome"], sums,
        surv_inc, base_surv, surv_inc2, base_surv2, prov_inc, gross_int_rate, net_int_rate,
    )

    result = {
        "rental": rental,
        "mlciRent": mlci_rent,
        "flatRate": flat_rate,
        "mlciFlat": mlci_flat,
        "declRate": fff.trunc4(decl_full_num),
        "mlciDecl": fff.trunc4(mlci_decl_full_num),
        "declRateFull": decl_full_num,
        "mlciDeclFull": mlci_decl_full_num,
        "declRate1000": decl_rate_1000 if decl_rate_1000 not in (None, "") else "",
        "gIntRate": g_int_rate,
        "gIntAmt": g_int_amt,
        "grossIntRate": gross_int_rate,
        "netIntRate": net_int_rate,
        "survInc": surv_inc,
        "provInc": prov_inc,
        "baseSurv": base_surv,
        "survInc2": surv_inc2,
        "baseSurv2": base_surv2,
        "surveyLoan2": survey_loan2,
        "creditProtection": credit_protection,
        "surveyFee2": "1" if survey_fee2 else "0",
        "guaranteedDisabled": tot_net2 > 300000000,
        "subsidy": sums,
        "eligibleComm": fff.php_round(totals["maxComm"]),
        "totalNetFinance": tot_net,
        "totalNetFinancePlusSurveyLoan2": tot_net2,
        "outstanding": outstanding_totals,
        "steps": steps_out,
    }
    if notary_update:
        result.update(notary_update)
    return jsonify(result)

@cam_edit_bp.route("/fin-financing/save", methods=["POST"])
@login_required
def save_financing():
    payload = request.get_json(force=True) or {}
    apless = _fin_str(payload.get("apless"))
    applno = _fin_str(payload.get("applno"))
    if not apless or not applno:
        return jsonify({"success": False, "message": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"success": False, "message": block_message}), 409
    if _fin_account_blocked(applno):
        return jsonify({"success": False, "message": _FIN_ACCOUNT_BLOCK_MESSAGE}), 409

    fin_type = _fin_str(payload.get("finType"))
    purpoffinc = _fin_str(payload.get("purpoffinc"))
    cont_type_name = _fin_str(payload.get("contTypeName"))
    cont_sts = _fin_str(payload.get("contSts"))
    col_type = _fin_str(payload.get("colType"))
    l_type = _fin_str(payload.get("lType"))
    disb_type = _fin_str(payload.get("disbType"))
    adv_arr = _fin_str(payload.get("advArr"))
    fix_float = _fin_str(payload.get("fixFloat"))
    float_cyc = _fin_str(payload.get("floatCyc")) if fix_float == "L" else ""
    curr_code = _fin_str(payload.get("currCode"))
    cross_no = _fin_str(payload.get("crossNo"))

    pay_cycle_raw = payload.get("payCycle")
    l_amount_raw = payload.get("lAmount")
    tenor = _n(payload.get("tenor"))
    pay_cycle = _n(pay_cycle_raw)
    l_amount = _n(l_amount_raw)
    security = _n(payload.get("security"))
    security_persen = _n(payload.get("securityPersen"))
    credit_amt = _n(payload.get("creditAmt"))
    comm_adm_fee = _n(payload.get("commAdmFee"))
    other_loan = _n(payload.get("otherLoan"))
    prov_loan = _n(payload.get("provisionLoan"))
    bbn = payload.get("bbn") or {}
    bbn_loan = _n(bbn.get("bbnLoan"))
    survey_fee2 = _fin_str(payload.get("surveyFee2")) == "1"
    survey_loan2 = _n(payload.get("surveyLoan2")) if survey_fee2 else 0.0
    surv_inc = _n(payload.get("survInc"))
    prov_inc = _n(payload.get("provInc"))
    base_surv = _n(payload.get("baseSurv"))
    surv_inc2 = _n(payload.get("survInc2")) if survey_fee2 else 0.0
    base_surv2 = _n(payload.get("baseSurv2")) if survey_fee2 else 0.0
    credit_protection = _n(payload.get("creditProtection")) if survey_fee2 else 0.0
    guaranteed = "1" if _fin_str(payload.get("guaranteed")) == "1" else "0"
    eligible_comm = fff.php_round(_n(payload.get("eligibleComm")))
    ttl_sub_tot = fff.php_round(_n(payload.get("ttlSubTot")))
    max_comm = fff.php_round(_n(payload.get("maxComm")))
    interest_income = fff.php_round(_n(payload.get("grossIntRate")))
    base_interest_income = fff.php_round(_n(payload.get("netIntRate")))
    percentage = _fin_percentage(applno)
    flat_rate_raw = payload.get("flatRate")
    g_period = _n(payload.get("gPeriod"))
    g_int_rate = _n(payload.get("gIntRate"))
    g_int_amt = _n(payload.get("gIntAmt"))
    tenor1000 = _n(payload.get("tenor1000"))
    flat_rate1000 = _n(payload.get("flatRate1000"))
    decl_rate1000 = _n(payload.get("declRate1000"))

    if disb_type == "N" and fin_type != "S":
        cross_no = ""

    dp = _fin_dp_minimum(applno)
    errors = []
    if cont_sts == "":
        errors.append("Status must not empty")
    if col_type == "":
        errors.append("Payment Method must not empty")
    if l_type == "":
        errors.append("Amortization Type must not empty")
    if disb_type == "":
        errors.append("Disbursement Type must not empty")
    if cont_type_name == "":
        errors.append("Contract Type must not empty")
    if _fin_str(pay_cycle_raw) == "":
        errors.append("Payment Cycle must not empty")
    if _fin_str(l_amount_raw) == "":
        errors.append("Asset Value must not empty")
    if security == 0:
        errors.append("Down Payment must not empty")
    if security_persen == 0:
        errors.append("Down Payment (%) must not empty")
    errors.extend(_fin_dp_errors(purpoffinc, security_persen, dp))
    if not dp["freeBaseRate"] and fin_type != "W" and base_surv < 1500000:
        errors.append("Minimum Survey Fee is 1,500,000")
    if l_type == "0":
        if _fin_str(flat_rate_raw) == "":
            errors.append("The Flat Rate must not empty")
        elif _n(flat_rate_raw) == 0:
            errors.append("The Flat Rate cannot be 0")
    if fin_type in ("F", "S") and security == 0:
        errors.append("The DP cannot be 0")
    if disb_type == "C" and fin_type not in ("S", "D", "M") and cross_no == "":
        errors.append("Cross No must not empty")
    if l_type in ("0", "1", "2", "3", "4", "6") and (tenor <= 0 or pay_cycle <= 0):
        errors.append("Tenor must not empty")

    months, rentals, bases = _fin_parse_steps(payload)
    if l_type == "3" and not months:
        errors.append("No. of Step must not empty")

    lease = db.session.execute(
        text(
            """
            SELECT CAFCONT.TENOR, CAFCONT.CONS_LEAS, CAFLESS.LESSEE_NM, CAFLESS.LESSEE_TP, CAFEQUIP.BPKB_AN,
                   CAFLESS.NPWP, CAFEQUIP.BPKB_AN_TP, CAFEQUIP.MODEL, CAFEQUIP.BPKB_AN_STS
            FROM CAFCONT WITH (NOLOCK)
                INNER JOIN CAFLESS WITH (NOLOCK) ON CAFCONT.APLESS = CAFLESS.APLESS
                INNER JOIN CAFEQUIP WITH (NOLOCK) ON CAFCONT.APPL_NO = CAFEQUIP.APPL_NO
            WHERE CAFCONT.APPL_NO = :applno
            """
        ),
        {"applno": applno},
    ).fetchone()
    if lease:
        names_differ = (lease.LESSEE_NM or "") != (lease.BPKB_AN or "")
        if _fin_str(lease.CONS_LEAS) == "L":
            if _n(lease.TENOR) < 36:
                errors.append("Contract is Finance Lease, minimum period are 3 years")
            if names_differ:
                errors.append("Contract is Finance Lease, Name of BPKB must be the same as Name of Contract")
            if l_amount > 500000000 and _fin_str(lease.LESSEE_TP) == "PR" and _fin_str(lease.MODEL) in ("1", "2", "3"):
                errors.append("Maximum price for Finance Lease (Individual) for car type 'minibus, sedan, jeep' is Rp.500.000.000")
            if _fin_str(lease.NPWP) == "":
                errors.append("Contract is Finance Lease, Customer must has NPWP")
        elif names_differ and _fin_str(lease.BPKB_AN_TP) == "PR" and _fin_str(lease.BPKB_AN_STS) == "":
            errors.append("Name of BPKB is different with Name of Contract, Please fill the family status")

    tot_net1 = l_amount - security + credit_amt + other_loan + bbn_loan + prov_loan
    warning = ""
    if not errors:
        outstanding_totals = _fin_customer_outstanding(apless, applno)
        if fin_type == "D":
            limit_error = _fin_limit_error("D", outstanding_totals["totalFDana"] + tot_net1, strict_equal=False)
        elif fin_type == "M":
            limit_error = _fin_limit_error("M", outstanding_totals["totalFModal"] + tot_net1, strict_equal=False)
        else:
            limit_error = None
            if fin_type == "W" and tot_net1 > CAPITAL_FACILITY_LIMIT:
                warning = (
                    "CAM cannot be processed because 'Total Net Finance+Survey Loan 2' + "
                    "'Total Customer`s Outstanding for Fund Facility and Business Capital Facility' > Rp. 10.000.000.000"
                )
        if limit_error:
            try:
                _fin_clear(applno, fin_type)
                db.session.commit()
            except Exception:
                db.session.rollback()
                current_app.logger.exception("fin-financing clear after limit failed for %s", applno)
            return jsonify({"success": False, "message": limit_error, "shouldClear": True}), 422

    if errors:
        return jsonify({"success": False, "message": "<br>".join(errors)}), 422

    decl_full = payload.get("declRateFull")
    mlci_decl_full = payload.get("mlciDeclFull")
    decl_rate_save = _n(payload.get("declRate")) if _fin_str(decl_full) == "" else _n(decl_full)
    mlci_decl_save = _n(payload.get("mlciDecl")) if _fin_str(mlci_decl_full) == "" else _n(mlci_decl_full)
    residual = security if fin_type in ("S", "F") else 0.0
    overate = "0.1" if fin_type == "W" else "0.25"
    branch_cd = _session_str("branchcode")
    notary_fee = _n(payload.get("notaryFee"))
    notary = _n(payload.get("notary"))
    fiduciary = _n(payload.get("fiduciary"))
    other_fee = _n(payload.get("otherFee"))
    business_trip = _n(payload.get("businessTripFee"))
    rental = _n(payload.get("rental"))
    mlci_rent = _n(payload.get("mlciRent"))
    flat_rate = _n(flat_rate_raw)
    mlci_flat = _n(payload.get("mlciFlat"))
    notice = ""

    try:
        current = db.session.execute(
            text("SELECT L_AMOUNT, Max_Fee FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :applno"),
            {"applno": applno},
        ).fetchone()
        old_amount = fff.php_round(_n(current.L_AMOUNT)) if current else 0
        if old_amount != 0 and fff.php_round(l_amount) != old_amount:
            notice = "Recalculate your insurance, commission, disbursement and outstanding"
            ins = db.session.execute(
                text("SELECT INS_POL FROM CAFINSU WITH (NOLOCK) WHERE APPL_NO = :applno"), {"applno": applno}
            ).fetchone()
            db.session.execute(text("DELETE FROM CAFDISB WHERE APPL_NO = :applno"), {"applno": applno})
            db.session.execute(text("DELETE FROM CAFDISBACC WHERE APPL_NO = :applno"), {"applno": applno})
            if ins and ins.INS_POL:
                db.session.execute(
                    text("UPDATE CAFINSUD SET PREP_AMT = 0, PRER_AMT = 0, TPL_AMT = 0, TLO_AR = 0, INS_AMT = 0 WHERE INS_POL = :pol"),
                    {"pol": ins.INS_POL},
                )
        if current is None or _n(current.Max_Fee) != eligible_comm:
            db.session.execute(text("DELETE FROM CAFKOMIS WHERE APPL_NO = :applno"), {"applno": applno})
            db.session.execute(text("DELETE FROM CafkomisACC WHERE APPL_NO = :applno"), {"applno": applno})

        common = {
            "curr_code": curr_code, "l_amount": l_amount, "security": security, "decl_rate": decl_rate_save,
            "overate": overate, "col_type": col_type, "adv_arr": adv_arr, "l_type": l_type,
            "fix_float": fix_float, "float_cyc": float_cyc, "tenor": tenor, "pay_cycle": pay_cycle,
            "mlci_decl": mlci_decl_save, "gross": notary_fee, "other_fee": other_fee, "cont_sts": cont_sts,
            "adm_fee": surv_inc, "branch_cd": branch_cd, "other_loan": other_loan, "notary": notary,
            "fiduciary": fiduciary, "disb_type": disb_type, "residual": residual, "provision": prov_inc,
            "purpoffinc": purpoffinc, "business_trip": business_trip, "base_adm_fee": base_surv,
            "max_fee": eligible_comm, "base_interest": base_interest_income, "interest_income": interest_income,
            "g_period": g_period, "g_int_rate": g_int_rate, "g_int_amt": g_int_amt,
            "applno": applno, "apless": apless,
        }
        common_set = """
            CURR_CODE = :curr_code, L_AMOUNT = :l_amount, SECURITY = :security, DECLRATE = :decl_rate,
            OVERATE = :overate, COL_TYPE = :col_type, ADV_ARR = :adv_arr, L_TYPE = :l_type,
            FIX_FLOAT = :fix_float, FLOAT_CYC = :float_cyc, TENOR = :tenor, PAY_CYCLE = :pay_cycle,
            RENTAL = :rental, MLCIDECL = :mlci_decl, MLCIRENT = :mlci_rent, FLATRATE = :flat_rate,
            MLCIFLAT = :mlci_flat, Gross = :gross, OTHERFEE = :other_fee, ContSts = :cont_sts,
            AdmFee = :adm_fee, BRANCH_CD = :branch_cd, Otherloan = :other_loan, Notary = :notary,
            Fiduciary = :fiduciary, Disb_Type = :disb_type, RESIDUAL = :residual, PROVISION = :provision,
            COMM_PROVISION = 0, purpoffinc = :purpoffinc, BusinessTrip_Fee = :business_trip,
            BaseAdmFee = :base_adm_fee, Max_Fee = :max_fee, BaseInterestFee = :base_interest,
            InterestIncome = :interest_income, G_PERIOD = :g_period, G_INT_RATE = :g_int_rate,
            G_INT_AMT = :g_int_amt
        """

        if l_type == "3":
            common.update({
                "rental": rentals[0], "mlci_rent": bases[0], "flat_rate": 0, "mlci_flat": 0,
            })
            db.session.execute(
                text(f"UPDATE CAFCONT SET {common_set} WHERE APPL_NO = :applno AND APLESS = :apless"), common
            )
        elif l_type == "4":
            common.update({
                "rental": rental, "mlci_rent": mlci_rent, "flat_rate": flat_rate, "mlci_flat": mlci_flat,
                "decl1000": decl_rate1000, "flat1000": flat_rate1000, "tenor1000": tenor1000,
            })
            db.session.execute(
                text(
                    f"UPDATE CAFCONT SET {common_set}, DECLRATE1000 = :decl1000, FLATRATE1000 = :flat1000, "
                    "tenor1000 = :tenor1000 WHERE APPL_NO = :applno AND APLESS = :apless"
                ),
                common,
            )
        else:
            common.update({
                "rental": rental, "mlci_rent": mlci_rent, "flat_rate": flat_rate, "mlci_flat": mlci_flat,
            })
            db.session.execute(
                text(f"UPDATE CAFCONT SET {common_set} WHERE APPL_NO = :applno AND APLESS = :apless"), common
            )

        db.session.execute(text("DELETE FROM CAFSTEP WHERE APPL_NO = :applno"), {"applno": applno})
        step_insert = text(
            "INSERT INTO CAFSTEP (APPL_NO, STEP, NO_STEP, PMT_STEP, MLCI_STEP) "
            "VALUES (:applno, :step, :no_step, :pmt, :mlci)"
        )
        if l_type == "4":
            db.session.execute(step_insert, {"applno": applno, "step": 1, "no_step": tenor1000, "pmt": rental, "mlci": rental})
            db.session.execute(step_insert, {"applno": applno, "step": 2, "no_step": tenor - tenor1000, "pmt": 1000, "mlci": 1000})
        elif l_type == "3":
            for idx, (month, step_rental, step_base) in enumerate(zip(months, rentals, bases), start=1):
                db.session.execute(step_insert, {"applno": applno, "step": idx, "no_step": month, "pmt": step_rental, "mlci": step_base})

        db.session.execute(text("DELETE FROM TACrossNo WHERE APPL_NO = :applno"), {"applno": applno})
        if cross_no:
            db.session.execute(
                text("INSERT INTO TACrossNo (APPL_NO, LEASE_NO, CROSSNO, CROSS_TYPE) VALUES (:applno, '', :cross_no, 'CN')"),
                {"applno": applno, "cross_no": cross_no},
            )

        existing_insu = db.session.execute(
            text("SELECT 1 FROM CAFINSU WITH (NOLOCK) WHERE APPL_NO = :applno"), {"applno": applno}
        ).fetchone()
        if existing_insu:
            db.session.execute(
                text("UPDATE CAFINSU SET CREDITAMT = :credit_amt, CommAdmFee = :comm WHERE APPL_NO = :applno"),
                {"credit_amt": credit_amt, "comm": comm_adm_fee, "applno": applno},
            )
        else:
            db.session.execute(
                text("INSERT INTO CAFINSU (INS_POL, APPL_NO, CREDITAMT, CommAdmFee) VALUES (:pol, :applno, :credit_amt, :comm)"),
                {"pol": f"{applno}1", "applno": applno, "credit_amt": credit_amt, "comm": comm_adm_fee},
            )

        if _fin_str(bbn.get("paidBy")) != "Deduct from disbursement":
            db.session.execute(
                text("UPDATE CAFDISB SET SERVICE_AGENCY_FEE = 0, BBN_FEE = 0 WHERE SPLIT = 'Dealer' AND APPL_NO = :applno"),
                {"applno": applno},
            )
        bbn_params = {
            "via": _fin_str(bbn.get("via")), "paid_by": _fin_str(bbn.get("paidBy")),
            "agency_name": _fin_str(bbn.get("agencyName")), "bbn_loan": bbn_loan,
            "bbn_fee": _n(bbn.get("bbnFee")), "agency_fee_gross": _n(bbn.get("agencyFeeGross")),
            "agency_fee_net": _n(bbn.get("agencyFeeNet")), "applno": applno,
        }
        existing_bbn = db.session.execute(
            text("SELECT 1 FROM BBN WITH (NOLOCK) WHERE APPL_NO = :applno"), {"applno": applno}
        ).fetchone()
        if existing_bbn:
            db.session.execute(
                text(
                    """
                    UPDATE BBN SET BBNVIA = :via, PAIDBY = :paid_by, SERVICEAGENCYNM = :agency_name,
                           BBNLOAN = :bbn_loan, BBN_FEE = :bbn_fee, ServiceAgencyFee = :agency_fee_gross,
                           NettServiceAgencyFee = :agency_fee_net
                    WHERE APPL_NO = :applno
                    """
                ),
                bbn_params,
            )
        else:
            db.session.execute(
                text(
                    """
                    INSERT INTO BBN (appl_no, bbnvia, serviceagencyNM, bbnloan, BBN_FEE,
                                     ServiceAgencyFee, NettServiceAgencyFee, PAIDBY)
                    VALUES (:applno, :via, :agency_name, :bbn_loan, :bbn_fee,
                            :agency_fee_gross, :agency_fee_net, :paid_by)
                    """
                ),
                bbn_params,
            )

        comm_params = {
            "total_income": ttl_sub_tot, "comm_third_party": max_comm,
            "percentage": percentage, "applno": applno,
        }
        existing_comm = db.session.execute(
            text("SELECT 1 FROM COMM_PARTY WITH (NOLOCK) WHERE APPL_NO = :applno"), {"applno": applno}
        ).fetchone()
        if existing_comm:
            db.session.execute(
                text(
                    "UPDATE COMM_PARTY SET TOTAL_INCOME = :total_income, COMM_THIRDPARTY = :comm_third_party, "
                    "Percentage = :percentage WHERE APPL_NO = :applno"
                ),
                comm_params,
            )
        else:
            db.session.execute(
                text(
                    "INSERT INTO COMM_PARTY (appl_no, TOTAL_INCOME, COMM_THIRDPARTY, Percentage) "
                    "VALUES (:applno, :total_income, :comm_third_party, :percentage)"
                ),
                comm_params,
            )

        if prov_loan == 0:
            db.session.execute(text("DELETE FROM Provision_Loan WHERE APPL_NO = :applno"), {"applno": applno})
        else:
            existing_prov = db.session.execute(
                text("SELECT 1 FROM Provision_Loan WITH (NOLOCK) WHERE APPL_NO = :applno"), {"applno": applno}
            ).fetchone()
            if existing_prov:
                db.session.execute(
                    text("UPDATE Provision_Loan SET Prov_loan = :prov_loan WHERE APPL_NO = :applno"),
                    {"prov_loan": prov_loan, "applno": applno},
                )
            else:
                db.session.execute(
                    text("INSERT INTO Provision_Loan (appl_no, Prov_loan) VALUES (:applno, :prov_loan)"),
                    {"applno": applno, "prov_loan": prov_loan},
                )

        if survey_fee2:
            cigna_params = {
                "fee": surv_inc2, "base": base_surv2, "loan": survey_loan2, "cp": credit_protection,
                "ga": guaranteed, "rate": fff.cigna_rate_percent(tenor1000 if l_type == "4" else tenor) or 0,
                "applno": applno,
            }
            existing_cigna = db.session.execute(
                text("SELECT 1 FROM cigna_fee WITH (NOLOCK) WHERE APPL_NO = :applno"), {"applno": applno}
            ).fetchone()
            if existing_cigna:
                db.session.execute(
                    text(
                        """
                        UPDATE cigna_fee SET Survey_Fee_Cigna = :fee, Survey_Base_Rate_Cigna = :base,
                               Survey_Loan_Cigna = :loan, Credit_Protection = :cp,
                               GuarantedAcceptance = :ga, Cigna_Rate = :rate
                        WHERE APPL_NO = :applno
                        """
                    ),
                    cigna_params,
                )
            elif surv_inc2 != 0:
                db.session.execute(
                    text(
                        """
                        INSERT INTO cigna_fee (appl_no, Survey_Fee_Cigna, Survey_Base_Rate_Cigna, Survey_Loan_Cigna,
                                               Credit_Protection, GuarantedAcceptance, Cigna_Rate)
                        VALUES (:applno, :fee, :base, :loan, :cp, :ga, :rate)
                        """
                    ),
                    cigna_params,
                )
        else:
            db.session.execute(text("DELETE FROM cigna_fee WHERE APPL_NO = :applno"), {"applno": applno})

        if disb_type == "N":
            db.session.execute(text("DELETE FROM TACrossNo WHERE APPL_NO = :applno"), {"applno": applno})

        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("fin-financing save failed for %s", applno)
        return jsonify({"success": False, "message": f"Save failed: {type(exc).__name__}: {exc}"}), 500

    return jsonify({
        "success": True,
        "apless": apless,
        "applno": applno,
        "notice": notice,
        "warning": warning,
        "insLoan": credit_amt,
        "netFinance": l_amount - security,
        "totalNetFinance": tot_net1,
    })

@cam_edit_bp.route("/fin-financing/clear", methods=["POST"])
@login_required
def clear_financing():
    payload = request.get_json(force=True) or {}
    applno = _fin_str(payload.get("applno"))
    fin_type = _fin_str(payload.get("finType"))
    if not applno:
        return jsonify({"error": "applno is required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"error": block_message}), 409

    try:
        _fin_clear(applno, fin_type)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("fin-financing clear failed for %s", applno)
        return jsonify({"error": "Failed to clear."}), 500

    return jsonify({
        "success": True,
        "notary": _fin_notary_default(applno),
        "subsidy": _subsidy_sums(applno),
        "subsidySourceTotals": _subsidy_source_totals(applno),
    })
@cam_edit_bp.route("/fin-financing/subsidies", methods=["GET"])
@login_required
def list_subsidies():
    applno = request.args.get("applno", "")
    if not applno:
        return jsonify({"error": "applno is required"}), 400

    brand_row = db.session.execute(text("SELECT BRAND FROM CAFEQUIP WHERE APPL_NO = :applno"), {"applno": applno}).fetchone()
    brand = (brand_row.BRAND or "").strip() if brand_row else ""
    contract_row = db.session.execute(text("SELECT Incentive, SUBSIDY FROM CAFCONT WHERE APPL_NO = :applno"), {"applno": applno}).fetchone()
    incentive_flag = contract_row.Incentive if contract_row else None
    subsidy_total = contract_row.SUBSIDY if contract_row else 0

    dealer_apm_options = ["Subsidy From Dealer"]
    if incentive_flag == "1" and subsidy_total not in (0, None) and brand == "MIT":
        dealer_apm_options.append("Incentive From APM")
    elif incentive_flag == "0" and subsidy_total not in (0, None) and brand in ("ISZ", "HIN"):
        dealer_apm_options.append("Subsidy From APM")
    elif brand == "MIT":
        dealer_apm_options.append("Incentive From APM")
    elif brand in ("ISZ", "HIN"):
        dealer_apm_options.append("Subsidy From APM")

    return jsonify({
        "grid": _subsidy_grid(applno),
        "dealerApmOptions": dealer_apm_options,
        "includeSurveyFee2Option": True,
    })

SUBSIDY_SOURCE_TO_TYPE = {"1": "SD", "2": "SA", "3": "IA"}
AMOUNT_TYPE_BY_CODE = {
    "1": "DP", "2": "Installment", "3": "Insurance", "4": "Survey",
    "5": "Provision", "6": "Interest", "7": "SurveyFee2",
}

@cam_edit_bp.route("/fin-financing/subsidies", methods=["POST"])
@login_required
def add_subsidy():
    payload = request.get_json(force=True) or {}
    applno = payload.get("applno")
    dealer_code = str(payload.get("dealer", ""))
    amount_code = str(payload.get("dpinstal", ""))
    amount = _n(payload.get("amount"))

    if not applno or not dealer_code or not amount_code:
        return jsonify({"error": "Please choose Dealer/APM and Payment For what"}), 422

    subsidy_type = SUBSIDY_SOURCE_TO_TYPE.get(dealer_code)
    amount_type = AMOUNT_TYPE_BY_CODE.get(amount_code)
    if not subsidy_type or not amount_type:
        return jsonify({"error": "Please Choose Payment For"}), 422

    def upsert(subsidy_type_: str, amount_type_: str, amount_: float):
        existing = db.session.execute(
            text("SELECT 1 FROM CafcontSubsidyDetail WITH (NOLOCK) WHERE APPL_NO = :applno AND SubsidyType = :st AND AmountType = :at"),
            {"applno": applno, "st": subsidy_type_, "at": amount_type_},
        ).fetchone()
        if existing:
            db.session.execute(
                text("UPDATE CafcontSubsidyDetail SET Amount = :amount WHERE APPL_NO = :applno AND SubsidyType = :st AND AmountType = :at"),
                {"amount": amount_, "applno": applno, "st": subsidy_type_, "at": amount_type_},
            )
        else:
            db.session.execute(
                text("INSERT INTO CafcontSubsidyDetail (APPL_No, SubsidyType, AmountType, Amount) VALUES (:applno, :st, :at, :amount)"),
                {"applno": applno, "st": subsidy_type_, "at": amount_type_, "amount": amount_},
            )

    upsert(subsidy_type, amount_type, amount)

    if subsidy_type == "SD":
        total = db.session.execute(
            text("SELECT SUM(Amount) AS amt FROM CafcontSubsidyDetail WITH (NOLOCK) WHERE APPL_NO = :applno AND SubsidyType = 'SD'"),
            {"applno": applno},
        ).fetchone()
        db.session.execute(
            text("UPDATE CAFCONT SET Subsidy_Supp = :amt WHERE APPL_NO = :applno"),
            {"amt": float(total.amt or amount), "applno": applno},
        )
    else:
        incentive_flag = "0" if subsidy_type == "SA" else "1"
        if amount_type in ("DP", "Installment", "Insurance"):
            upsert("RD", amount_type, amount)
        total = db.session.execute(
            text("SELECT SUM(Amount) AS amt FROM CafcontSubsidyDetail WITH (NOLOCK) WHERE APPL_NO = :applno AND SubsidyType = :st"),
            {"applno": applno, "st": subsidy_type},
        ).fetchone()
        refund_total = db.session.execute(
            text("SELECT SUM(Amount) AS amt FROM CafcontSubsidyDetail WITH (NOLOCK) WHERE APPL_NO = :applno AND SubsidyType = 'RD'"),
            {"applno": applno},
        ).fetchone()
        db.session.execute(
            text("UPDATE CAFCONT SET SUBSIDY = :amt, Incentive = :incentive WHERE APPL_NO = :applno"),
            {"amt": float(total.amt or amount), "incentive": incentive_flag, "applno": applno},
        )
        if amount_type in ("DP", "Installment", "Insurance"):
            db.session.execute(
                text("UPDATE CAFCONT SET Refund_Supp = :amt WHERE APPL_NO = :applno"),
                {"amt": float(refund_total.amt or amount), "applno": applno},
            )

    db.session.commit()
    return jsonify({"grid": _subsidy_grid(applno), "sums": _subsidy_sums(applno)})

@cam_edit_bp.route("/fin-financing/subsidies", methods=["DELETE"])
@login_required
def delete_subsidy():
    payload = request.get_json(force=True) or {}
    applno = payload.get("applno")
    subsidy_type = payload.get("subsidyType")
    amount_type = payload.get("amountType")
    amount = _n(payload.get("amount"))
    if not all([applno, subsidy_type, amount_type]):
        return jsonify({"error": "applno, subsidyType and amountType are required"}), 400

    def reduce_field(table_field: str, current_total_query, amount_to_subtract: float):
        row = db.session.execute(text(current_total_query), {"applno": applno}).fetchone()
        current_total = float(getattr(row, table_field, 0) or 0) if row else 0
        remainder = max(current_total - amount_to_subtract, 0)
        return remainder

    if subsidy_type == "SD":
        remainder = reduce_field("Subsidy_Supp", "SELECT Subsidy_Supp FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :applno", amount)
        db.session.execute(text("UPDATE CAFCONT SET Subsidy_Supp = :amt WHERE APPL_NO = :applno"), {"amt": remainder, "applno": applno})
        db.session.execute(
            text("DELETE FROM CafcontSubsidyDetail WHERE APPL_NO = :applno AND SubsidyType = 'SD' AND AmountType = :at"),
            {"applno": applno, "at": amount_type},
        )
    elif subsidy_type in ("SA", "IA"):
        subsidy_row = db.session.execute(text("SELECT SUBSIDY, Refund_Supp FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :applno"), {"applno": applno}).fetchone()
        subsidy_total = float(subsidy_row.SUBSIDY or 0) if subsidy_row else 0
        refund_total = float(subsidy_row.Refund_Supp or 0) if subsidy_row else 0
        subsidy_remainder = max(subsidy_total - amount, 0)
        refund_remainder = max(refund_total - amount, 0)
        db.session.execute(text("UPDATE CAFCONT SET SUBSIDY = :s WHERE APPL_NO = :applno"), {"s": subsidy_remainder, "applno": applno})
        if amount_type in ("DP", "Installment", "Insurance"):
            db.session.execute(text("UPDATE CAFCONT SET Refund_Supp = :r WHERE APPL_NO = :applno"), {"r": refund_remainder, "applno": applno})
            if subsidy_type == "IA":
                db.session.execute(text("UPDATE CAFCONT SET Incentive = 0 WHERE APPL_NO = :applno"), {"applno": applno})
            db.session.execute(text("DELETE FROM CafcontSubsidyDetail WHERE APPL_NO = :applno AND SubsidyType = 'RD' AND AmountType = :at"), {"applno": applno, "at": amount_type})
        db.session.execute(
            text("DELETE FROM CafcontSubsidyDetail WHERE APPL_NO = :applno AND SubsidyType = :st AND AmountType = :at"),
            {"applno": applno, "st": subsidy_type, "at": amount_type},
        )

    db.session.commit()
    return jsonify({"grid": _subsidy_grid(applno), "sums": _subsidy_sums(applno)})
@cam_edit_bp.route("/fin-financing/subsidies/reset-survey-fee2", methods=["POST"])
@login_required
def reset_survey_fee2():
    payload = request.get_json(force=True) or {}
    applno = payload.get("applno")
    if not applno:
        return jsonify({"error": "applno is required"}), 400

    try:
        _fin_reset_survey_fee2(applno)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("reset survey fee 2 failed for %s", applno)
        return jsonify({"error": "Failed to reset Survey Fee 2 subsidy."}), 500

    return jsonify({"grid": _subsidy_grid(applno), "sums": _subsidy_sums(applno)})

@cam_edit_bp.route("/fin-financing/agency-fee", methods=["GET"])
@login_required
def agency_fee():
    agent = request.args.get("agent", "")
    row = db.session.execute(
        text("SELECT Agency_Fee FROM umf_agency WITH (NOLOCK) WHERE Agency_nm = :agent"),
        {"agent": agent},
    ).fetchone()
    return jsonify({"fee": _n(row.Agency_Fee) if row and row.Agency_Fee is not None else 0})

@cam_edit_bp.route("/fin-financing/comm-flag", methods=["POST"])
@login_required
def set_comm_flag():
    payload = request.get_json(force=True) or {}
    apless = payload.get("apless")
    applno = payload.get("applno")
    yesno = _fin_str(payload.get("yesno"))
    fee = _fin_str(payload.get("fee"))

    if not apless or not applno:
        return jsonify({"error": "apless and applno are required"}), 400

    params = {"yesno": yesno, "applno": applno, "apless": apless}
    try:
        if yesno != "0" and fee in ("", "0"):
            db.session.execute(
                text("UPDATE CAFCONT SET FLAGCOM = NULL WHERE APPL_NO = :applno AND APLESS = :apless"), params
            )
        else:
            db.session.execute(
                text("UPDATE CAFCONT SET FLAGCOM = :yesno WHERE APPL_NO = :applno AND APLESS = :apless"), params
            )
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("comm-flag update failed for %s", applno)
        return jsonify({"error": "Failed to update commission flag."}), 500
    return jsonify({"success": True})

@cam_edit_bp.route("/fin-financing/step-rental-last-payment", methods=["POST"])
@login_required
def step_rental_last_payment():
    payload = request.get_json(force=True) or {}
    months = [_n(m) for m in payload.get("months", [])]
    rentals = [_n(r) for r in payload.get("rentals", [])]
    total_net_finance = _n(payload.get("totalNetFinance"))
    decl_rate = _n(payload.get("declRate"))
    mlci_decl = _n(payload.get("mlciDecl"))
    adv_arr = _fin_str(payload.get("advArr"))
    pay_cycle = _n(payload.get("payCycle"))

    if not months or len(months) != len(rentals):
        return jsonify({"error": "months and rentals must be non-empty and the same length"}), 422
    if pay_cycle <= 0:
        return jsonify({"error": "Payment Cycle must not empty"}), 422

    rounding = _fin_rounding(payload.get("currCode"))
    try:
        last_selling = fff.step_last_payment(total_net_finance, months, rentals, decl_rate, pay_cycle, adv_arr, rounding)
        if mlci_decl != 0:
            last_base = fff.step_last_payment(total_net_finance, months, rentals, mlci_decl, pay_cycle, adv_arr, rounding)
        else:
            last_base = fff.php_round(fff.pembulatan(rentals[-1], rounding))
    except (ZeroDivisionError, ValueError, OverflowError):
        return jsonify({"error": "Calculation failed."}), 422

    return jsonify({
        "lastStepSellingRental": last_selling,
        "lastStepBaseRental": last_base,
    })

@cam_edit_bp.route("/outstanding", methods=["GET"])
@login_required
def outstanding_get():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    if not apless or not applno:
        return jsonify({"error": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"blocked": True, "message": block_message}), 409

    return jsonify(outstanding.get_full_view(applno))

@cam_edit_bp.route("/outstanding/calculate", methods=["POST"])
@login_required
def outstanding_calculate():
    data = request.get_json(silent=True) or {}
    apless = data.get("apless", "")
    applno = data.get("applno", "")
    if not apless or not applno:
        return jsonify({"success": False, "message": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"success": False, "message": block_message}), 409

    try:
        outstanding.recalculate(
            applno, apless,
            notes=data.get("notes") or "",
            group_appl=data.get("groupAppl") or data.get("group_appl") or "",
        )
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Outstanding Calculate failed for appl_no=%s", applno)
        return jsonify({"success": False, "message": "Calculation failed. Please try again."}), 500

    db.session.commit()

    view = outstanding.get_full_view(applno)
    view["success"] = True
    return jsonify(view)

@cam_edit_bp.route("/outstanding/next", methods=["POST"])
@login_required
def outstanding_next():
    data = request.get_json(silent=True) or {}
    apless = data.get("apless", "")
    applno = data.get("applno", "")
    if not apless or not applno:
        return jsonify({"success": False, "message": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"success": False, "message": block_message}), 409

    success, message = outstanding.save_next(applno, data)
    return jsonify({"success": success, "message": message})

_KOM_ACCOUNT_BLOCK_MESSAGE = (
    "*Commission cannot be changed, because your bank account is on approval at "
    "Operation Admin (OA). Please contact OA for Approve or Reject CAM."
)

_KOM_SURTAX_SALES_NO = "212094"

def _kom_date(value):
    if value is None:
        return None
    if isinstance(value, pydt.datetime):
        return value.date()
    if isinstance(value, pydt.date):
        return value
    return None

def _kom_tax_profile(beneficiary_id, category):
    row = db.session.execute(text("""
        SELECT TFFrom, TFTo, DateStart, PPN FROM BeneficiaryTax WITH (NOLOCK)
        WHERE BeneficiaryID = :b AND Category = :c
    """), {"b": beneficiary_id, "c": category}).mappings().first()

    tf_from = _kom_date(row["TFFrom"]) if row else None
    tf_to = _kom_date(row["TFTo"]) if row else None
    ppn_from = _kom_date(row["DateStart"]) if row else None
    ppn = _s(row["PPN"]) if row else ""

    return {"tf_from": tf_from, "tf_to": tf_to, "ppn_from": ppn_from, "ppn": ppn}

def _kom_skb(profile, create_date):
    if not create_date or not profile["tf_from"] or not profile["tf_to"]:
        return False
    return profile["tf_from"] <= create_date <= profile["tf_to"]

def _kom_ppn_active(profile, create_date):
    ppn_from = profile["ppn_from"]
    if not ppn_from or ppn_from.year == 1900:
        return False
    if profile["ppn"] != "1":
        return False
    if not create_date:
        return False
    return ppn_from <= create_date

def _kom_save_tax_dealer(fee_amount, dealer_supp, create_date):
    profile = _kom_tax_profile(dealer_supp, "DEALER")
    default_fee = fee_amount
    if _kom_skb(profile, create_date):
        if _kom_ppn_active(profile, create_date):
            sisa = fee_amount / 1.1
            max_fee_net = fff.php_round(sisa, 0)
            tax_amount = 0.0
            ppn_amount = fee_amount - max_fee_net
            feekomis = max_fee_net + ppn_amount
            gross_amount = fff.php_round(sisa, 0)
        else:
            ppn_amount = 0.0
            tax_amount = 0.0
            feekomis = default_fee
            gross_amount = fee_amount
    else:
        if _kom_ppn_active(profile, create_date):
            sisa = fff.php_round(fee_amount / 1.1, 0)
            persen = math.floor(sisa * 2 / 100)
            tax_amount = math.floor(persen)
            ppn_amount = fee_amount - sisa
            gross_amount = fff.php_round(sisa, 0)
            feekomis = gross_amount - tax_amount + ppn_amount
        else:
            tax_amount = math.floor(default_fee * 2 / 100)
            ppn_amount = 0.0
            feekomis = default_fee - tax_amount + ppn_amount
            gross_amount = fee_amount
    return feekomis, gross_amount, tax_amount, ppn_amount

def _kom_save_tax_sales(fee_amount, sales_no, create_date):
    row = db.session.execute(text("""
        SELECT a.Sales_Type, b.NPWP_Type, b.NPWP_No
        FROM CLFSALES a WITH (NOLOCK)
            INNER JOIN BeneficiaryTax b ON a.SALES_NO = b.BeneficiaryID
        WHERE a.SALES_NO = :s AND b.Category = 'SALES'
    """), {"s": sales_no}).mappings().first()

    npwp_type = _s(row["NPWP_Type"]) if row else ""
    npwp_no = _s(row["NPWP_No"]) if row else ""
    default_fee = fee_amount

    if npwp_type == "PT" and npwp_no != "":
        profile = _kom_tax_profile(sales_no, "SALES")
        surtax = _s(sales_no) == _KOM_SURTAX_SALES_NO
        if _kom_skb(profile, create_date):
            if _kom_ppn_active(profile, create_date):
                sisa = fee_amount / 1.1
                max_fee_net = fff.php_round(sisa, 0)
                tax_amount = math.floor(sisa * 0.5 / 100) if surtax else 0.0
                ppn_amount = fee_amount - max_fee_net
                feekomis = max_fee_net + ppn_amount - tax_amount
                gross_amount = fff.php_round(sisa, 0)
            else:
                ppn_amount = 0.0
                tax_amount = math.floor(default_fee * 0.5 / 100) if surtax else 0.0
                feekomis = default_fee - tax_amount
                gross_amount = fee_amount
        else:
            if _kom_ppn_active(profile, create_date):
                sisa = fff.php_round(fee_amount / 1.1, 0)
                persen = math.floor(sisa * 2 / 100)
                tax_amount = math.floor(persen)
                ppn_amount = fee_amount - sisa
                gross_amount = fff.php_round(sisa, 0)
                feekomis = gross_amount - tax_amount + ppn_amount
            else:
                tax_amount = math.floor(default_fee * 2 / 100)
                ppn_amount = 0.0
                feekomis = default_fee - tax_amount + ppn_amount
                gross_amount = fee_amount
        return feekomis, gross_amount, tax_amount, ppn_amount

    if npwp_type == "PR" and npwp_no != "":
        profile = _kom_tax_profile(sales_no, "SALES")
        ppn_from = profile["ppn_from"]
        if ppn_from and ppn_from.year != 1900 and profile["ppn"] == "1":
            sisa = fee_amount / 1.1
            max_fee_net = fff.php_round(sisa, 0)
            tax_amount = 0.0
            ppn_amount = fee_amount - max_fee_net
            feekomis = max_fee_net + ppn_amount
            gross_amount = fff.php_round(sisa, 0)
        else:
            ppn_amount = 0.0
            tax_amount = 0.0
            feekomis = default_fee
            gross_amount = fee_amount
        return feekomis, gross_amount, tax_amount, ppn_amount

    return fee_amount, fee_amount, 0.0, 0.0

def _kom_edit_tax_dealer(gross_now, dealer_supp, create_date):
    profile = _kom_tax_profile(dealer_supp, "DEALER")
    default_fee = gross_now
    if _kom_skb(profile, create_date):
        if _kom_ppn_active(profile, create_date):
            sisa = gross_now / 1.11
            max_fee_net = fff.php_round(sisa, 0)
            tax_amount = 0.0
            ppn_amount = gross_now - max_fee_net
            feekomis = max_fee_net + ppn_amount
            gross_amount = fff.php_round(sisa, 0)
        else:
            ppn_amount = 0.0
            tax_amount = 0.0
            feekomis = default_fee
            gross_amount = gross_now
    else:
        if _kom_ppn_active(profile, create_date):
            sisa = fff.php_round(gross_now / 1.11, 0)
            persen = fff.php_round(sisa * 2 / 100, 0)
            tax_amount = fff.php_round(persen, 0)
            ppn_amount = gross_now - sisa
            gross_amount = fff.php_round(sisa, 0)
            feekomis = gross_amount - tax_amount + ppn_amount
        else:
            tax_amount = fff.php_round(default_fee * 2 / 100, 0)
            ppn_amount = 0.0
            feekomis = default_fee - tax_amount + ppn_amount
            gross_amount = gross_now
    return feekomis, gross_amount, tax_amount, ppn_amount

def _kom_edit_tax_sales(gross_now, sales_no, create_date):
    row = db.session.execute(text("""
        SELECT a.Sales_Type, b.NPWP_Type, b.NPWP_No
        FROM CLFSALES a WITH (NOLOCK)
            INNER JOIN BeneficiaryTax b ON a.SALES_NO = b.BeneficiaryID
        WHERE a.SALES_NO = :s AND b.Category = 'SALES'
    """), {"s": sales_no}).mappings().first()

    npwp_type = _s(row["NPWP_Type"]) if row else ""
    npwp_no = _s(row["NPWP_No"]) if row else ""
    default_fee = gross_now

    if npwp_type == "PT" and npwp_no != "":
        profile = _kom_tax_profile(sales_no, "SALES")
        surtax = _s(sales_no) == _KOM_SURTAX_SALES_NO
        if _kom_skb(profile, create_date):
            if _kom_ppn_active(profile, create_date):
                sisa = gross_now / 1.11
                max_fee_net = fff.php_round(sisa, 0)
                tax_amount = math.floor(sisa * 0.5 / 100) if surtax else 0.0
                ppn_amount = gross_now - max_fee_net
                feekomis = max_fee_net + ppn_amount - tax_amount
                gross_amount = fff.php_round(sisa, 0)
            else:
                ppn_amount = 0.0
                tax_amount = math.floor(default_fee * 0.5 / 100) if surtax else 0.0
                feekomis = default_fee - tax_amount
                gross_amount = gross_now
        else:
            if _kom_ppn_active(profile, create_date):
                sisa = fff.php_round(gross_now / 1.11, 0)
                persen = fff.php_round(sisa * 2 / 100, 0)
                tax_amount = fff.php_round(persen, 0)
                ppn_amount = gross_now - sisa
                gross_amount = fff.php_round(sisa, 0)
                feekomis = gross_amount - tax_amount + ppn_amount
            else:
                tax_amount = fff.php_round(default_fee * 2 / 100, 0)
                ppn_amount = 0.0
                feekomis = default_fee - tax_amount + ppn_amount
                gross_amount = gross_now
        return feekomis, gross_amount, tax_amount, ppn_amount

    if npwp_type == "PR" and npwp_no != "":
        profile = _kom_tax_profile(sales_no, "SALES")
        ppn_from = profile["ppn_from"]
        if ppn_from and ppn_from.year != 1900 and profile["ppn"] == "1":
            sisa = gross_now / 1.11
            max_fee_net = fff.php_round(sisa, 0)
            tax_amount = 0.0
            ppn_amount = gross_now - max_fee_net
            feekomis = max_fee_net + ppn_amount
            gross_amount = fff.php_round(sisa, 0)
        else:
            ppn_amount = 0.0
            tax_amount = 0.0
            feekomis = default_fee
            gross_amount = gross_now
        return feekomis, gross_amount, tax_amount, ppn_amount

    return gross_now, gross_now, 0.0, 0.0

def _kom_delete_tax_dealer(gross_now, dealer_supp, create_date):
    profile = _kom_tax_profile(dealer_supp, "DEALER")
    default_fee = gross_now
    if _kom_skb(profile, create_date):
        if _kom_ppn_active(profile, create_date):
            sisa = gross_now / 1.1
            max_fee_net = fff.php_round(sisa, 0)
            tax_amount = 0.0
            ppn_amount = gross_now - max_fee_net
            feekomis = max_fee_net
        else:
            ppn_amount = 0.0
            tax_amount = math.floor(default_fee * 2 / 100)
            feekomis = default_fee
    else:
        if _kom_ppn_active(profile, create_date):
            sisa = fff.php_round(gross_now / 1.1, 0)
            persen = math.floor(sisa * 2 / 100)
            tax_amount = persen
            ppn_amount = gross_now - sisa
            feekomis = gross_now - persen
        else:
            tax_amount = math.floor(default_fee * 2 / 100)
            ppn_amount = 0.0
            feekomis = default_fee - tax_amount + ppn_amount
    return feekomis, tax_amount, ppn_amount

def _kom_delete_tax_sales(gross_now, sales_no, create_date):
    row = db.session.execute(text(
        "SELECT Sales_Type FROM CLFSALES WITH (NOLOCK) WHERE SALES_NO = :s"
    ), {"s": sales_no}).mappings().first()
    sales_type = _s(row["Sales_Type"]) if row else ""

    if sales_type != "PT":
        return gross_now, 0.0, 0.0

    profile = _kom_tax_profile(sales_no, "SALES")
    default_fee = gross_now
    if _kom_skb(profile, create_date):
        if _kom_ppn_active(profile, create_date):
            sisa = fff.php_round(gross_now / 1.1, 0)
            tax_amount = 0.0
            ppn_amount = gross_now - sisa
            feekomis = sisa
        else:
            ppn_amount = 0.0
            tax_amount = math.floor(default_fee * 2 / 100)
            feekomis = default_fee
    else:
        if _kom_ppn_active(profile, create_date):
            sisa = fff.php_round(gross_now / 1.1, 0)
            persen = math.floor(sisa * 2 / 100)
            tax_amount = persen
            ppn_amount = gross_now - sisa
            feekomis = gross_now - persen
        else:
            tax_amount = math.floor(default_fee * 2 / 100)
            ppn_amount = 0.0
            feekomis = default_fee - tax_amount + ppn_amount
    return feekomis, tax_amount, ppn_amount

def _account_approval_block(appl_no: str):
    row = db.session.execute(text("""
        SELECT TOP 1 APPR_STS, APPR_ID, APPR_DATE
        FROM MCMOCAMACCSTATUS WITH(NOLOCK)
        WHERE APPL_NO = :a ORDER BY [NO] DESC
    """), {"a": appl_no}).mappings().first()

    if not row:
        return False, ""

    appr_sts = _s(row["APPR_STS"])
    appr_id = _s(row["APPR_ID"]).lower()
    appr_dt = _kom_date(row["APPR_DATE"])
    parameter_dt = pydt.date(2022, 11, 1)

    if appr_sts == "A" and appr_id in ("ricky irawan", "denny_dilham"):
        return False, ""
    if appr_sts == "R":
        pending = db.session.execute(text("""
            SELECT 1 FROM MCMOCAMACCSTATUS WITH(NOLOCK) WHERE APPL_NO = :a AND APPR_STS = 'P'
        """), {"a": appl_no}).first()
        return (True, _KOM_ACCOUNT_BLOCK_MESSAGE) if pending else (False, "")
    if appr_sts == "P":
        return True, _KOM_ACCOUNT_BLOCK_MESSAGE
    if appr_sts == "A" and appr_id == "edisamsuri" and appr_dt and appr_dt < parameter_dt:
        return False, ""
    return True, _KOM_ACCOUNT_BLOCK_MESSAGE

def _current_dealer(appl_no: str):
    row = db.session.execute(text("""
        SELECT a.SUPP, b.NAME, b.ADDRESS FROM CAFEQUIP AS a WITH(NOLOCK)
            LEFT JOIN CLFSUPP AS b WITH(NOLOCK) ON a.SUPP = b.SUPP
        WHERE a.APPL_NO = :a
    """), {"a": appl_no}).mappings().first()
    if not row:
        return {"name": "", "no": "", "address": ""}
    return {
        "name": _s(row["NAME"]),
        "no": _s(row["SUPP"]),
        "address": (row["ADDRESS"] or "").rstrip(),
    }

def _create_date(appl_no: str):
    row = db.session.execute(text("""
        SELECT CREATE_DATE FROM CAFCONT WITH(NOLOCK) WHERE APPL_NO = :a
    """), {"a": appl_no}).first()
    return _kom_date(row[0]) if row else None

def _kom_category(sd_type):
    return "SALES" if _s(sd_type) == "S" else "DEALER"

def _kom_beneficiary_accounts(sales_no, sd_type):
    return db.session.execute(text("""
        SELECT b.[DESC] AS bank_desc, a.Acc_BankBranch, a.Acc_Name, a.Acc_NO, a.[Default], a.Acc_Bank
        FROM BeneficiaryAccount a
            INNER JOIN UMFBANK b ON a.Acc_Bank = b.BANK_CODE
        WHERE a.BeneficiaryID = :s AND a.AccountType = 'C' AND a.Category = :cat
    """), {"s": sales_no, "cat": _kom_category(sd_type)}).mappings().all()

def _kom_party_info(sd_type, sales_no):
    if _s(sd_type) == "S":
        row = db.session.execute(text(
            "SELECT NAME, ADDRESS FROM CLFSALES WITH (NOLOCK) WHERE SALES_NO = :s"
        ), {"s": sales_no}).mappings().first()
    else:
        row = db.session.execute(text(
            "SELECT NAME, ADDRESS FROM CLFSUPP WITH (NOLOCK) WHERE SUPP = :s"
        ), {"s": sales_no}).mappings().first()
    return {
        "name": _s(row["NAME"]) if row else "",
        "address": (row["ADDRESS"] or "").rstrip() if row else "",
    }

def _kom_total_committed(applno):
    rows = db.session.execute(text("""
        SELECT a.SD_TYPE, a.SALES_NO, a.Amount FROM CafkomisACC a WITH(NOLOCK)
            INNER JOIN CAFKOMIS b WITH(NOLOCK)
                ON a.APPL_NO = b.APPL_NO AND a.SALES_NO = b.SALES_NO AND a.SD_TYPE = b.SD_TYPE
        WHERE a.APPL_NO = :a AND b.Incentive = 1
    """), {"a": applno}).mappings().all()
    return rows, sum(fff.to_float(r["Amount"]) for r in rows)

def _kom_max_fee_gross(applno):
    row = db.session.execute(text(
        "SELECT COMM_THIRDPARTY FROM COMM_PARTY WITH(NOLOCK) WHERE APPL_NO = :a"
    ), {"a": applno}).first()
    return fff.to_float(row[0]) if row else 0.0

def _kom_gross_now(applno, sales_no, sd_type=None):
    if sd_type is None:
        rows = db.session.execute(text("""
            SELECT Amount FROM CafkomisACC WITH (NOLOCK) WHERE APPL_NO = :a AND SALES_NO = :s
        """), {"a": applno, "s": sales_no}).fetchall()
    else:
        rows = db.session.execute(text("""
            SELECT Amount FROM CafkomisACC WITH (NOLOCK)
            WHERE APPL_NO = :a AND SALES_NO = :s AND SD_TYPE = :sd
        """), {"a": applno, "s": sales_no, "sd": sd_type}).fetchall()
    return len(rows), sum(fff.to_float(r[0]) for r in rows)

@cam_edit_bp.route("/commission-cam")
@login_required
def get_commission_cam():
    apless = _s(request.args.get("apless", ""))
    applno = _s(request.args.get("applno", ""))
    cont_type = _s(request.args.get("contType", ""))

    if not apless or not applno:
        return jsonify({"error": "apless and applno are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"blocked": True, "message": block_message}), 409

    account_blocked, account_message = _account_approval_block(applno)

    rows = db.session.execute(text("""
        SELECT a.SD_TYPE, a.SALES_NO, a.Amount, a.ACC_NO, a.ACC_NM, c.BANK
        FROM CafkomisACC a WITH(NOLOCK)
            INNER JOIN CAFKOMIS b WITH(NOLOCK)
                ON a.APPL_NO = b.APPL_NO AND a.Sales_No = b.SALES_NO AND a.SD_Type = b.SD_TYPE
            INNER JOIN UMFBANK c ON a.ACC_Bank = c.BANK_CODE
        WHERE a.APPL_NO = :a AND b.Incentive = 1
    """), {"a": applno}).mappings().all()

    result_rows = []
    total_commission = 0.0
    for r in rows:
        sd_type = _s(r["SD_TYPE"])
        sales_no = _s(r["SALES_NO"])
        if sd_type == "S":
            sd_type_label = "Salesman & Broker"
        elif sd_type == "D":
            sd_type_label = "Dealer"
        else:
            sd_type_label = ""
        info = _kom_party_info(sd_type, sales_no) if sd_type in ("S", "D") else {"name": "", "address": ""}

        amount = fff.to_float(r["Amount"])
        total_commission += amount
        result_rows.append({
            "sdType": sd_type,
            "sdTypeLabel": sd_type_label,
            "salesNo": sales_no,
            "name": info["name"],
            "address": info["address"],
            "bank": _s(r["BANK"]),
            "accName": _s(r["ACC_NM"]),
            "accNo": _s(r["ACC_NO"]),
            "amount": amount,
            "canEditDelete": not account_blocked,
        })

    max_fee_gross = _kom_max_fee_gross(applno)
    _, tot_komisi = _kom_total_committed(applno)

    if cont_type[:2] == "RS":
        sd_type_options = [{"value": "S", "label": "Salesman & Broker"}]
    else:
        sd_type_options = [
            {"value": "S", "label": "Salesman & Broker"},
            {"value": "D", "label": "Dealer"},
        ]

    return jsonify({
        "blocked": False,
        "accountBlocked": account_blocked,
        "blockMessage": account_message,
        "rows": result_rows,
        "totalCommission": total_commission,
        "totalIncentive": max_fee_gross,
        "sisaIncentive": max_fee_gross - tot_komisi,
        "dealer": _current_dealer(applno),
        "sdTypeOptions": sd_type_options,
        "commissionTypeLabel": "Incentive",
        "comType": "1",
    })

@cam_edit_bp.route("/commission/accounts")
@login_required
def get_commission_accounts():
    sales_no = _s(request.args.get("salesNo", ""))
    applno = _s(request.args.get("applno", ""))
    sd_type = _s(request.args.get("sdType", ""))

    amount_disabled = False
    if sd_type == "D":
        auto2000 = db.session.execute(text("""
            SELECT TOP 1 1 FROM CLFSUPP WITH(NOLOCK) WHERE LEFT(NICKNAME, 9) = 'AUTO 2000' AND SUPP = :s
        """), {"s": sales_no}).first()
        amount_disabled = bool(auto2000)

    accounts = _kom_beneficiary_accounts(sales_no, sd_type)

    if not accounts:
        return jsonify({"rows": [{
            "bankDesc": "", "bankBranch": "", "accName": "", "accNo": "",
            "isDefault": False, "amount": None, "checked": False,
            "amountDisabled": True, "checkboxDisabled": True,
        }], "hasAccounts": False})

    rows = []
    for acc in accounts:
        existing = db.session.execute(text("""
            SELECT AMOUNT FROM CafkomisACC WHERE APPL_NO = :a AND SD_Type = :sd AND ACC_NO = :acc
        """), {"a": applno, "sd": sd_type, "acc": acc["Acc_NO"]}).first()
        amount = fff.php_round(fff.to_float(existing[0]), 0) if existing else 0.0
        is_default = fff.to_float(acc["Default"]) == 1

        rows.append({
            "bankDesc": _s(acc["bank_desc"]),
            "bankBranch": _s(acc["Acc_BankBranch"]),
            "accName": _s(acc["Acc_Name"]),
            "accNo": _s(acc["Acc_NO"]),
            "isDefault": is_default,
            "amount": amount,
            "checked": is_default and amount >= 0,
            "amountDisabled": amount_disabled,
            "checkboxDisabled": False,
        })

    return jsonify({"rows": rows, "hasAccounts": True})

@cam_edit_bp.route("/commission/dealer-check")
@login_required
def get_commission_dealer_check():
    sales_no = _s(request.args.get("salesNo", ""))
    sd_type = _s(request.args.get("sdType", "D"))
    if sd_type != "D":
        return jsonify({"valid": True, "message": ""})

    row = db.session.execute(text("""
        SELECT NPWP_No FROM BeneficiaryTax WITH(NOLOCK) WHERE BeneficiaryID = :s AND Category = 'DEALER'
    """), {"s": sales_no}).first()

    if not row or _s(row[0]) == "":
        return jsonify({
            "valid": False,
            "message": "Commission to Dealer is not valid, cause the dealer does not have NPWP",
        })
    return jsonify({"valid": True, "message": ""})

@cam_edit_bp.route("/sales-search")
@login_required
def get_sales_search():
    name = _s(request.args.get("name", ""))
    all_branches = request.args.get("allBranches", "0") == "1"
    com_type = _s(request.args.get("comType", "1")) or "1"
    page = request.args.get("page", 1, type=int) or 1
    page_size = request.args.get("pageSize", 10, type=int) or 10
    branch_cd = _session_str("branchcode")

    params = {"name": f"%{name}%"}
    if not all_branches:
        params["branch_cd"] = branch_cd

    if com_type == "2":
        branch_filter = "" if all_branches else "AND BRANCH_CD = :branch_cd"
        inner = f"""
            SELECT SALES_NO, [NAME], [ADDRESS], [Status] FROM CLFSALES WITH(NOLOCK)
            WHERE [NAME] LIKE :name {branch_filter} AND [Status] = 'A' AND IsSalesTV = '1'
        """
    else:
        branch_filter = "" if all_branches else "AND a.BRANCH_CD = :branch_cd"
        branch_filter_union = "" if all_branches else "AND BRANCH_CD = :branch_cd"
        inner = f"""
            SELECT a.SALES_NO, a.[NAME], a.[ADDRESS], a.[Status]
            FROM CLFSALES a WITH(NOLOCK)
                LEFT JOIN BeneficiaryTax b WITH(NOLOCK) ON a.SALES_NO = b.BeneficiaryID AND b.Category = 'SALES'
            WHERE a.[NAME] LIKE :name {branch_filter}
                AND a.Status = 'A' AND (b.PPN = '1' OR b.NPWP_Type = 'PT' OR a.PAID = '0')
            UNION
            SELECT SALES_NO, [NAME], [ADDRESS], [Status] FROM CLFSALES WITH(NOLOCK)
            WHERE [NAME] LIKE :name {branch_filter_union}
                AND [Status] = 'A' AND IsSalesTV = '0'
        """

    total = db.session.execute(text(f"SELECT COUNT(*) FROM ({inner}) t"), params).scalar()

    offset = (page - 1) * page_size
    rows = db.session.execute(text(f"""
        SELECT * FROM (
            SELECT ROW_NUMBER() OVER(ORDER BY t.SALES_NO) AS RowNr, t.SALES_NO, t.[NAME], t.[ADDRESS], t.[Status]
            FROM ({inner}) t
        ) x WHERE x.RowNr > :off AND x.RowNr <= :end
    """), {**params, "off": offset, "end": offset + page_size}).mappings().all()

    result_rows = [{
        "salesNo": _s(r["SALES_NO"]),
        "name": _s(r["NAME"]),
        "address": (r["ADDRESS"] or "").rstrip(),
        "status": "Active" if _s(r["Status"]) == "A" else "Inactive",
    } for r in rows]

    return jsonify({"rows": result_rows, "total": total or 0})

@cam_edit_bp.route("/commission/max-fee")
@login_required
def get_commission_max_fee():
    applno = _s(request.args.get("applno", ""))
    sales_no = _s(request.args.get("salesNo", ""))
    sd_type = _s(request.args.get("sdType", ""))

    max_fee_gross = _kom_max_fee_gross(applno)
    existing_rows, tot_komisi = _kom_total_committed(applno)

    gross_sales = 0.0
    already = any(_s(r["SALES_NO"]) == sales_no and _s(r["SD_TYPE"]) == sd_type for r in existing_rows)
    if already:
        _, gross_sales = _kom_gross_now(applno, sales_no, sd_type)

    return jsonify({"maxFee": max_fee_gross - tot_komisi + gross_sales})

@cam_edit_bp.route("/commission/edit")
@login_required
def get_commission_edit():
    applno = _s(request.args.get("applno", ""))
    sales_no = _s(request.args.get("salesNo", ""))
    sd_type = _s(request.args.get("sdType", ""))
    acc_no = _s(request.args.get("accNo", ""))

    row = db.session.execute(text("""
        SELECT SD_TYPE, Amount FROM CafkomisACC WITH (NOLOCK)
        WHERE APPL_NO = :a AND SALES_NO = :s AND ACC_NO = :acc AND SD_TYPE = :sd
    """), {"a": applno, "s": sales_no, "acc": acc_no, "sd": sd_type}).mappings().first()

    if not row:
        return jsonify({"error": "Commission row not found"}), 404

    sd_type = _s(row["SD_TYPE"])
    fee = fff.to_float(row["Amount"])
    info = _kom_party_info(sd_type, sales_no)

    max_fee_gross = _kom_max_fee_gross(applno)
    others = db.session.execute(text("""
        SELECT a.Amount FROM CafkomisACC a WITH (NOLOCK)
            INNER JOIN CAFKOMIS b WITH (NOLOCK)
                ON a.APPL_NO = b.APPL_NO AND a.SD_TYPE = b.SD_TYPE AND a.SALES_NO = b.SALES_NO
        WHERE a.APPL_NO = :a AND a.ACC_NO <> :acc AND b.Incentive = 1
    """), {"a": applno, "acc": acc_no}).fetchall()
    tot_komisi = sum(fff.to_float(r[0]) for r in others)

    max_fee = max_fee_gross - tot_komisi

    return jsonify({
        "sdType": sd_type,
        "sdTypeLabel": "Sales" if sd_type == "S" else "Dealer",
        "salesNo": sales_no,
        "accNo": acc_no,
        "name": info["name"],
        "address": info["address"],
        "fee": fff.php_round(fee, 0),
        "maxFee": math.trunc(max_fee),
    })

@cam_edit_bp.route("/commission/edit/save", methods=["POST"])
@login_required
def post_commission_edit_save():
    d = request.get_json(silent=True) or {}
    applno = _s(d.get("applno", ""))
    sales_no = _s(d.get("salesNo", ""))
    sd_type = _s(d.get("sdType", ""))
    acc_no = _s(d.get("accNo", ""))
    fee_text = _s(d.get("fee", ""))
    fee = fff.to_float(fee_text)
    max_fee = fff.to_float(d.get("maxFee"))

    if not applno or not sales_no:
        return jsonify({"success": False, "message": "applno and salesNo are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"success": False, "message": block_message}), 409

    account_blocked, account_message = _account_approval_block(applno)
    if account_blocked:
        return jsonify({"success": False, "message": account_message}), 409

    messages = []
    if fee_text == "" or fee == 0:
        messages.append("Fee must not empty")
    if fee > max_fee:
        messages.append("Fee must not exceed Max Fee")
    if sd_type == "S" and fee < 50000:
        messages.append("Minimal commission Rp.50.000")

    if messages:
        return jsonify({"success": False, "message": "<br>".join(messages)})

    create_date = _create_date(applno)

    try:
        db.session.execute(text("""
            UPDATE CafkomisACC SET Amount = :amt
            WHERE APPL_NO = :a AND SALES_NO = :s AND ACC_NO = :acc AND SD_TYPE = :sd
        """), {"amt": fee, "a": applno, "s": sales_no, "acc": acc_no, "sd": sd_type})

        _, gross_now = _kom_gross_now(applno, sales_no, sd_type)

        type_row = db.session.execute(text(
            "SELECT SD_TYPE FROM CafkomisACC WITH (NOLOCK) WHERE APPL_NO = :a AND ACC_NO = :acc"
        ), {"a": applno, "acc": acc_no}).mappings().first()
        row_sd_type = _s(type_row["SD_TYPE"]) if type_row else ""

        if row_sd_type == "D":
            dealer = _current_dealer(applno)
            feekomis, gross_amount, tax_amount, ppn_amount = _kom_edit_tax_dealer(
                gross_now, dealer["no"], create_date)
        else:
            feekomis, gross_amount, tax_amount, ppn_amount = _kom_edit_tax_sales(
                gross_now, sales_no, create_date)

        db.session.execute(text("""
            UPDATE CAFKOMIS SET FEE = :fee, GrossAmount = :gross, TaxAmount = :tax, PPNAmount = :ppn
            WHERE APPL_NO = :a AND SALES_NO = :s AND SD_TYPE = :sd
        """), {"fee": feekomis, "gross": gross_amount, "tax": tax_amount, "ppn": ppn_amount,
               "a": applno, "s": sales_no, "sd": sd_type})

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to save commission edit for applno=%s", applno)
        return jsonify({"success": False, "message": "Failed"}), 500

    return jsonify({"success": True, "message": "Successful"})

@cam_edit_bp.route("/commission/delete", methods=["POST"])
@login_required
def post_commission_delete():
    d = request.get_json(silent=True) or {}
    applno = _s(d.get("applno", ""))
    sales_no = _s(d.get("salesNo", ""))
    acc_no = _s(d.get("accNo", ""))
    fee_sales = fff.to_float(d.get("feeSales"))

    if not applno or not sales_no:
        return jsonify({"success": False, "message": "applno and salesNo are required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"success": False, "message": block_message}), 409

    account_blocked, account_message = _account_approval_block(applno)
    if account_blocked:
        return jsonify({"success": False, "message": account_message}), 409

    create_date = _create_date(applno)

    try:
        _, tot_amount = _kom_gross_now(applno, sales_no)
        sisa_fee = tot_amount - fee_sales

        db.session.execute(text("""
            DELETE FROM CafkomisACC WHERE APPL_NO = :a AND SALES_NO = :s AND ACC_NO = :acc
        """), {"a": applno, "s": sales_no, "acc": acc_no})

        remaining, gross_now = _kom_gross_now(applno, sales_no)

        type_row = db.session.execute(text("""
            SELECT SD_TYPE FROM CafkomisACC WITH (NOLOCK)
            WHERE APPL_NO = :a AND ACC_NO <> :acc AND SALES_NO = :s
        """), {"a": applno, "acc": acc_no, "s": sales_no}).mappings().first()
        row_sd_type = _s(type_row["SD_TYPE"]) if type_row else ""

        if row_sd_type == "D":
            dealer = _current_dealer(applno)
            feekomis, tax_amount, _ppn = _kom_delete_tax_dealer(gross_now, dealer["no"], create_date)
        else:
            feekomis, tax_amount, _ppn = _kom_delete_tax_sales(gross_now, sales_no, create_date)

        if remaining > 0:
            db.session.execute(text("""
                UPDATE CAFKOMIS SET GrossAmount = :gross, FEE = :fee, TaxAmount = :tax
                WHERE APPL_NO = :a AND SALES_NO = :s
            """), {"gross": sisa_fee, "fee": feekomis, "tax": tax_amount,
                   "a": applno, "s": sales_no})
        else:
            db.session.execute(text(
                "DELETE FROM Cafkomis WHERE APPL_NO = :a AND SALES_NO = :s"
            ), {"a": applno, "s": sales_no})

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to delete commission for applno=%s", applno)
        return jsonify({"success": False, "message": "Failed"}), 500

    return jsonify({"success": True, "message": "Successful"})

@cam_edit_bp.route("/commission-cam/save", methods=["POST"])
@login_required
def post_commission_cam_save():
    d = request.get_json(silent=True) or {}
    apless = _s(d.get("apless", ""))
    applno = _s(d.get("applno", ""))
    sd_type = _s(d.get("sdType", ""))
    sales_no = _s(d.get("salesNo", ""))
    max_fee = fff.to_float(d.get("maxFee"))
    rows = d.get("rows") or []

    if not applno:
        return jsonify({"success": False, "message": "applno is required"}), 400

    blocked, block_message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"success": False, "message": block_message}), 409

    account_blocked, account_message = _account_approval_block(applno)
    if account_blocked:
        return jsonify({"success": False, "message": account_message}), 409

    checked_by_acc = {}
    for r in rows:
        if r.get("checked"):
            checked_by_acc[_s(r.get("accNo"))] = fff.to_float(r.get("amount"))

    fee_amount = sum(checked_by_acc.values())

    messages = []
    if sd_type == "":
        messages.append("Commission To must not empty")
    if sales_no == "":
        messages.append("Sales Name must not empty")
    if fee_amount > max_fee:
        messages.append("Fee must not exceed Max Fee")
    if sd_type == "S" and max_fee < 50000:
        messages.append("Minimal commission Rp.50.000")

    if messages:
        return jsonify({"success": False, "message": "<br>".join(messages)})

    accounts = _kom_beneficiary_accounts(sales_no, sd_type)
    if not accounts:
        label = "dealer" if sd_type == "D" else "sales"
        return jsonify({"success": False, "message": f"This {label} have no commission account"})

    if sd_type == "D":
        npwp_row = db.session.execute(text("""
            SELECT NPWP_No FROM BeneficiaryTax WITH(NOLOCK) WHERE BeneficiaryID = :s AND Category = 'DEALER'
        """), {"s": sales_no}).first()
        if not npwp_row or _s(npwp_row[0]) == "":
            return jsonify({
                "success": False,
                "message": "Commission to Dealer is not valid, cause the dealer does not have NPWP",
            })

    create_date = _create_date(applno)

    try:
        if sd_type == "D":
            db.session.execute(text(
                "DELETE FROM CafkomisACC WHERE APPL_NO = :a AND SD_Type = 'D'"
            ), {"a": applno})
            db.session.execute(text(
                "DELETE FROM Cafkomis WHERE APPL_NO = :a AND SD_Type = 'D'"
            ), {"a": applno})
        else:
            db.session.execute(text(
                "DELETE FROM CafkomisACC WHERE APPL_NO = :a AND SD_Type = 'S' AND Sales_No = :s"
            ), {"a": applno, "s": sales_no})
            db.session.execute(text(
                "DELETE FROM Cafkomis WHERE APPL_NO = :a AND SD_Type = 'S' AND Sales_No = :s"
            ), {"a": applno, "s": sales_no})

        for acc in accounts:
            acc_no = _s(acc["Acc_NO"])
            if acc_no not in checked_by_acc:
                continue
            amount = checked_by_acc[acc_no]
            if amount == 0:
                continue
            db.session.execute(text("""
                INSERT INTO CafkomisACC (APPL_NO, SALES_NO, SD_TYPE, ACC_NO, ACC_NM, ACC_Bank, ACC_BankBranch, Amount)
                VALUES (:a, :s, :sd, :acc, :nm, :bank, :branch, :amt)
            """), {
                "a": applno, "s": sales_no, "sd": sd_type, "acc": acc_no,
                "nm": _s(acc["Acc_Name"]), "bank": _s(acc["Acc_Bank"]),
                "branch": _s(acc["Acc_BankBranch"]).replace("'", "`"), "amt": amount,
            })

        if checked_by_acc:
            if sd_type == "D":
                dealer = _current_dealer(applno)
                feekomis, gross_amount, tax_amount, ppn_amount = _kom_save_tax_dealer(
                    fee_amount, dealer["no"], create_date)
            else:
                feekomis, gross_amount, tax_amount, ppn_amount = _kom_save_tax_sales(
                    fee_amount, sales_no, create_date)

            db.session.execute(text("""
                INSERT INTO CAFKOMIS (APPL_NO, SALES_NO, FEE, GrossAmount, SD_TYPE, TaxAmount, PPNAmount, Incentive)
                VALUES (:a, :s, :fee, :gross, :sd, :tax, :ppn, 1)
            """), {
                "a": applno, "s": sales_no, "fee": feekomis, "gross": gross_amount,
                "sd": sd_type, "tax": tax_amount, "ppn": ppn_amount,
            })

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to save commission for applno=%s", applno)
        return jsonify({"success": False, "message": "Failed"}), 500

    return jsonify({"success": True, "message": "Successful", "apless": apless, "applno": applno})
BOD_OTHER_VALUE = "5"
BOC_OTHER_VALUE = "10"

def _current_yyyymm() -> int:
	return int(datetime.now().strftime("%Y%m"))

def _fetch_lookups(conn):
	bod_positions = conn.execute(text(
		"SELECT ID_OS_POSITION AS value, [DESC] AS label FROM MSTOS_POSITION WITH (NOLOCK) WHERE OS_CODE = 'PT02'"
	)).mappings().all()
	boc_positions = conn.execute(text(
		"SELECT ID_OS_POSITION AS value, [DESC] AS label FROM MSTOS_POSITION WITH (NOLOCK) WHERE OS_CODE = 'PT03'"
	)).mappings().all()
	certificate_options = conn.execute(text(
		"SELECT ID_OS_CERTIFICATE AS value, CERT_CODE AS label FROM MSTOS_CERTIFICATE WITH (NOLOCK) WHERE CUST_TYPE = 'PT'"
	)).mappings().all()
	shareholder_status_options = conn.execute(text(
		"SELECT value, desc_value AS label FROM mstcombo WITH (NOLOCK) WHERE cat_value = 'SHAREHOLDER_STATUS'"
	)).mappings().all()
	contract_signer_options = conn.execute(text(
		"SELECT ID_OS_SIGNER AS value, [DESC] AS label FROM MSTOS_SIGNER WITH (NOLOCK) WHERE CUST_TYPE = 'PT'"
	)).mappings().all()
	area_options = conn.execute(text(
		"SELECT AREA_CD AS value, Propinsi + ' - ' + Kabupaten AS label FROM UMFAREA WITH (NOLOCK) WHERE FLAG_DEL = 0 ORDER BY Propinsi, Kabupaten"
	)).mappings().all()
	nationality_options = conn.execute(text(
		"SELECT ID2digit AS value, Name AS label FROM Mst_Country WITH (NOLOCK) ORDER BY Name"
	)).mappings().all()
	return {
		"bodPositions": [dict(r) for r in bod_positions],
		"bocPositions": [dict(r) for r in boc_positions],
		"certificateOptions": [dict(r) for r in certificate_options],
		"shareholderStatusOptions": [dict(r) for r in shareholder_status_options],
		"contractSignerOptions": [dict(r) for r in contract_signer_options],
		"areaOptions": [dict(r) for r in area_options],
		"nationalityOptions": [dict(r) for r in nationality_options],
	}

def _fetch_name_options(conn, apless: str):
	rows = conn.execute(text("""
		SELECT Id AS value, Nama AS label
		FROM TEMP_CAFLESS_OCR
		WHERE Prechecking_Id = (SELECT Prechecking_Id FROM CAFLESS WHERE APLESS = :apless)
	"""), {"apless": apless}).mappings().all()
	return [dict(r) for r in rows]

def _creation_yyyymm(conn, apless: str, applno: str) -> str:
	row = conn.execute(text("""
		SELECT CONCAT(YEAR(CREATE_DATE), RIGHT(CONCAT('0', MONTH(CREATE_DATE)), 2)) AS ym
		FROM CAFCONT WITH (NOLOCK) WHERE APLESS = :apless AND APPL_NO = :applno
	"""), {"apless": apless, "applno": applno}).mappings().first()
	ym = row["ym"] if row and row["ym"] else None
	return ym or datetime.now().strftime("%Y%m")

def _period_options(conn, apless: str, creation_ym: str):
	rows = conn.execute(text("""
		SELECT DISTINCT PERIOD FROM CAFORGSTRUCT WITH (NOLOCK)
		WHERE APLESS = :apless AND PERIOD <> '' AND PERIOD <= :creation_ym
		ORDER BY PERIOD DESC
	"""), {"apless": apless, "creation_ym": creation_ym}).mappings().all()
	return [r["PERIOD"] for r in rows]

def _normalize_phone(phone) -> str:
	if not phone:
		return ""
	digits = re.sub(r"[^0-9xX]", "", str(phone))
	if digits.startswith("62"):
		digits = digits[2:]
	elif digits.startswith("0"):
		digits = digits[1:]
	return digits

def _load_management_details(conn, apless: str, period: str):
	rows = conn.execute(text("""
		SELECT DISTINCT MANAGEMENT_NM, ID_CARD, NPWP, [ADDRESS], CITY, name, gender, kecamatan, kelurahan,
		       cod.PASSPORTNO, CITIZEN, NATIONALITY, ua.Propinsi, ua.AREA_CD,
		       ue.AREA_CD AS AREA_CDNPWP, ue.PROPINSI AS PROPINSINPWP,
		       NAME_NPWP, ADD_NPWP, CITY_NPWP, KECAMATAN_NPWP, KELURAHAN_NPWP,
		       PlaceOfBirth, DateOfBirth, PostCode, IDType, NoExpireDate, ValidityCertainPeriod,
		       PostCode_NPWP, MobilePhone, Email
		FROM CAFORGSTRUCT_DETAIL cod WITH (NOLOCK)
            LEFT JOIN UMFAREA ua WITH (NOLOCK) ON ua.KABUPATEN = CITY
            LEFT JOIN UMFAREA ue WITH (NOLOCK) ON ue.KABUPATEN = CITY_NPWP
		WHERE cod.APLESS = :apless AND PERIOD = :period AND OS_CODE IN ('PT01', 'PT02', 'PT03')
	"""), {"apless": apless, "period": period}).mappings().all()

	def fmt_date(v):
		return v.strftime("%d-%m-%Y") if isinstance(v, (date, datetime)) else ""

	result = {}
	for r in rows:
		name = r["MANAGEMENT_NM"]
		if not name:
			continue
		city_outside = r["CITY"] == "9999"
		city_npwp_outside = r["CITY_NPWP"] == "9999"
		birth_or_establish_place = r["PlaceOfBirth"] or ""
		birth_or_establish_date = fmt_date(r["DateOfBirth"])
		result[name] = {
			"nameWithoutTitle": r["name"] or "",
			"gender": r["gender"] or "",
			"placeOfBirth": birth_or_establish_place,
			"dateOfBirth": birth_or_establish_date,
			"address": r["ADDRESS"] or "",
			"areaCd": "9999" if city_outside else (r["AREA_CD"] or ""),
			"province": "Di Luar Wilayah Indonesia" if city_outside else (r["Propinsi"] or ""),
			"city": "Di Luar Wilayah Indonesia" if city_outside else (r["CITY"] or ""),
			"kecamatan": r["kecamatan"] or "",
			"kelurahan": r["kelurahan"] or "",
			"postCode": r["PostCode"] or "",
			"citizen": r["CITIZEN"] or "",
			"nationality": r["NATIONALITY"] or "",
			"idCard": r["ID_CARD"] or "",
			"passportNo": r["PASSPORTNO"] or "",
			"idType": r["IDType"] or "",
			"noExpireDate": str(r["NoExpireDate"]) if r["NoExpireDate"] is not None else "",
			"certainPeriod": fmt_date(r["ValidityCertainPeriod"]),
			"mobilePhone": _normalize_phone(r["MobilePhone"]),
			"email": r["Email"] or "",
			"nameInNpwp": r["NAME_NPWP"] or "",
			"establishPlace": birth_or_establish_place,
			"establishDate": birth_or_establish_date,
			"addressNpwp": r["ADD_NPWP"] or "",
			"areaCdNpwp": "9999" if city_npwp_outside else (r["AREA_CDNPWP"] or ""),
			"provinceNpwp": "Di Luar Wilayah Indonesia" if city_npwp_outside else (r["PROPINSINPWP"] or ""),
			"cityNpwp": "Di Luar Wilayah Indonesia" if city_npwp_outside else (r["CITY_NPWP"] or ""),
			"kecamatanNpwp": r["KECAMATAN_NPWP"] or "",
			"kelurahanNpwp": r["KELURAHAN_NPWP"] or "",
			"npwp": r["NPWP"] or "",
			"postCodeNpwp": r["PostCode_NPWP"] or "",
		}
	return result

def _parse_ddmmyyyy(s):
	if not s:
		return None
	try:
		return datetime.strptime(s, "%d-%m-%Y").date()
	except ValueError:
		return None

def _detail_columns_for_insert(name: str, share_status: str, management_details: dict) -> dict:
	empty = {
		"detail_name": "", "gender": "", "kecamatan": "", "kelurahan": "", "citizen": "", "nationality": "",
		"passportno": "", "address": "", "city": "", "id_card": "", "npwp": "",
		"name_npwp": "", "add_npwp": "", "city_npwp": "", "kecamatan_npwp": "", "kelurahan_npwp": "",
		"place_of_birth": "", "date_of_birth": None, "post_code": "", "id_type": "",
		"no_expire_date": "", "certain_period": None, "post_code_npwp": "", "mobile_phone": "", "email": "",
	}
	d = management_details.get(name)
	if not d:
		return empty
	is_corporate = share_status == "1"
	outside_id = d.get("areaCd") == "9999"
	outside_npwp = d.get("areaCdNpwp") == "9999"
	return {
		"detail_name": d.get("nameWithoutTitle", ""),
		"gender": "" if is_corporate else d.get("gender", ""),
		"kecamatan": "999999" if outside_id else d.get("kecamatan", ""),
		"kelurahan": "9999999999" if outside_id else d.get("kelurahan", ""),
		"citizen": "" if is_corporate else d.get("citizen", ""),
		"nationality": "" if is_corporate else ("ID" if d.get("citizen") == "WNI" else d.get("nationality", "")),
		"passportno": (d.get("passportNo", "") if (not is_corporate and d.get("citizen") == "WNA") else ""),
		"address": d.get("address", ""),
		"city": ("9999" if outside_id else d.get("city", "")),
		"id_card": "" if is_corporate else d.get("idCard", ""),
		"npwp": d.get("npwp", "") if is_corporate else "",
		"name_npwp": d.get("nameInNpwp", "") if is_corporate else "",
		"add_npwp": d.get("addressNpwp", "") if is_corporate else "",
		"city_npwp": ("9999" if outside_npwp else d.get("cityNpwp", "")) if is_corporate else "",
		"kecamatan_npwp": (("999999" if outside_npwp else d.get("kecamatanNpwp", "")) if is_corporate else ""),
		"kelurahan_npwp": (("9999999999" if outside_npwp else d.get("kelurahanNpwp", "")) if is_corporate else ""),
		"place_of_birth": (d.get("establishPlace", "") if is_corporate else d.get("placeOfBirth", "")) or "",
		"date_of_birth": _parse_ddmmyyyy(d.get("establishDate") if is_corporate else d.get("dateOfBirth")),
		"post_code": d.get("postCode", ""),
		"id_type": d.get("idType", ""),
		"no_expire_date": d.get("noExpireDate", ""),
		"certain_period": _parse_ddmmyyyy(d.get("certainPeriod")),
		"post_code_npwp": d.get("postCodeNpwp", ""),
		"mobile_phone": d.get("mobilePhone", ""),
		"email": d.get("email", ""),
	}

def _load_period_data(conn, apless: str, period: str):
	capital_row = conn.execute(text("""
		SELECT AUTHORIZED_CAPITAL, PAID_IN_CAPITAL, CONTRACT_SIGNER, OTHER_SIGNER, PIC
		FROM CAFORGSTRUCT WITH (NOLOCK) WHERE APLESS = :apless AND PERIOD = :period
	"""), {"apless": apless, "period": period}).mappings().first()

	shareholders = conn.execute(text("""
		SELECT MANAGEMENT_NM AS name, SHAREHOLDER_STATUS AS status, TOTOFSHARES AS totalShares,
		       NOMOFSHARES AS nominalShares, SIGNER AS signer
		FROM CAFORGSTRUCT_DETAIL WITH (NOLOCK)
		WHERE APLESS = :apless AND PERIOD = :period AND OS_CODE = 'PT01'
		ORDER BY ID_DETAIL
	"""), {"apless": apless, "period": period}).mappings().all()

	directors_raw = conn.execute(text("""
		SELECT MANAGEMENT_NM AS name, OS_CODE AS osCode, POS_DEEDNO AS posDeedNo,
		       SIGNER AS signer, OWNER AS owner, SIGNER_ECONTRACT AS signerEcontract
		FROM CAFORGSTRUCT_DETAIL WITH (NOLOCK)
		WHERE APLESS = :apless AND PERIOD = :period AND OS_CODE IN ('PT02', 'PT03')
		ORDER BY ID_DETAIL
	"""), {"apless": apless, "period": period}).mappings().all()

	bod_ids = {r["value"] for r in conn.execute(text(
		"SELECT ID_OS_POSITION AS value FROM MSTOS_POSITION WITH (NOLOCK) WHERE OS_CODE = 'PT02'"
	)).mappings().all()}
	boc_ids = {r["value"] for r in conn.execute(text(
		"SELECT ID_OS_POSITION AS value FROM MSTOS_POSITION WITH (NOLOCK) WHERE OS_CODE = 'PT03'"
	)).mappings().all()}

	directors = []
	for r in directors_raw:
		known = r["posDeedNo"] in (bod_ids if r["osCode"] == "PT02" else boc_ids)
		directors.append({
			"name": r["name"] or "",
			"bod": (r["posDeedNo"] if r["osCode"] == "PT02" and known else (BOD_OTHER_VALUE if r["osCode"] == "PT02" else "")),
			"boc": (r["posDeedNo"] if r["osCode"] == "PT03" and known else (BOC_OTHER_VALUE if r["osCode"] == "PT03" else "")),
			"other": ("" if known else (r["posDeedNo"] or "")),
			"owner": bool(r["owner"] == "1"),
			"signer": bool(r["signer"] == "1"),
			"signerEcontract": bool(r["signerEcontract"] == "1"),
		})

	deeds_raw = conn.execute(text("""
		SELECT MANAGEMENT_NM AS stateNo, POS_DEEDNO AS deedNo, DATE_OF_DEED AS deedDate,
		       NOTARY_NM AS notaryName, CERTIFICATE AS certificate
		FROM CAFORGSTRUCT_DETAIL WITH (NOLOCK)
		WHERE APLESS = :apless AND PERIOD = :period AND OS_CODE = 'PT04'
		ORDER BY ID_DETAIL
	"""), {"apless": apless, "period": period}).mappings().all()

	deeds = [{
		"stateNo": d["stateNo"] or "",
		"deedNo": "" if d["stateNo"] else (d["deedNo"] or ""),
		"deedDate": d["deedDate"].strftime("%d-%m-%Y") if isinstance(d["deedDate"], (date, datetime)) else "",
		"notaryName": d["notaryName"] or "",
		"certificate": d["certificate"] or "",
	} for d in deeds_raw]
	if any(d["stateNo"] for d in deeds_raw):
		for i, d in enumerate(deeds_raw):
			if d["stateNo"]:
				deeds[i]["deedNo"] = ""
			else:
				deeds[i]["stateNo"] = ""

	return {
		"capital": {
			"authorized": str(int(capital_row["AUTHORIZED_CAPITAL"])) if capital_row and capital_row["AUTHORIZED_CAPITAL"] else "",
			"paidIn": str(int(capital_row["PAID_IN_CAPITAL"])) if capital_row and capital_row["PAID_IN_CAPITAL"] else "",
		},
		"shareholders": [{
			"name": s["name"] or "", "status": s["status"] or "",
			"totalShares": str(s["totalShares"] or ""), "nominalShares": str(s["nominalShares"] or ""),
			"signer": bool(s["signer"] == "1"),
		} for s in shareholders],
		"directors": directors,
		"deeds": deeds,
		"contractSignerSelected": (capital_row["CONTRACT_SIGNER"] if capital_row else "") or "",
		"contractSignerOther": (capital_row["OTHER_SIGNER"] if capital_row else "") or "",
		"picSameAsE": not bool(capital_row and capital_row["PIC"]),
		"picName": (capital_row["PIC"] if capital_row else "") or "",
		"managementDetails": _load_management_details(conn, apless, period),
	}

@cam_edit_bp.route("/lessee-category", methods=["GET"])
@login_required
def get_lessee_category():

    apless = request.args.get("apless", "")
    appl_no = request.args.get("appl_no", "")
    with db.engine.connect() as conn:
        row = conn.execute(text("""
            SELECT Lessee_Cat, a.Cons_Leas, b.LESSEE_NM
            FROM    CAFCONT a WITH (NOLOCK)
                LEFT JOIN CAFLESS b WITH (NOLOCK) ON a.APLESS = b.APLESS
            WHERE a.APLESS = :apless AND a.APPL_NO = :appl_no
        """), {"apless": apless, "appl_no": appl_no}).mappings().first()
    return jsonify({
        "lesseeCat": ((row["Lessee_Cat"] or "") if row else "").strip().upper(),
        "finType": (row["Cons_Leas"] if row else "") or "",
        "custName": (row["LESSEE_NM"] if row else "") or "",
    })

DOC_TYPE_NON = "non"
_DIRECTOR_KTP_RE = re.compile(r"^corp-ocr-ktp_(\d+)$")
_WNA_BOARD_RE = re.compile(r"^wna-corp-board_(\d+)$")

def get_lessee_cat(apless: str) -> Optional[str]:
    row = db.session.execute(
        text("SELECT Lessee_Cat FROM CAFLESS WITH (NOLOCK) WHERE APLESS = :apless"),
        {"apless": apless},
    ).first()
    return row.Lessee_Cat if row else None

def validate_document_file(file_storage, max_file_size_mb: float) -> str:
    if file_storage is None or not file_storage.filename:
        return "No file selected."

    file_storage.stream.seek(0, os.SEEK_END)
    size_bytes = file_storage.stream.tell()
    file_storage.stream.seek(0)

    if max_file_size_mb:
        max_bytes = max_file_size_mb * 1024 * 1024
        if size_bytes > max_bytes:
            return f"File exceeds the {max_file_size_mb}MB limit."

    return ""

def _record_upload_audit_log(username: str, applno: str, apless: str, document_type: str, file_name: str) -> None:
    pass

def list_customer_documents(applno: str, apless: str, organization_type: str) -> dict:
    docs = (
        CustomerDocument.query
        .filter(
            CustomerDocument.organization_type == organization_type,
            CustomerDocument.doc_type == DOC_TYPE_NON,
            CustomerDocument.appl_no == applno,
            CustomerDocument.apless == apless,
            CustomerDocument.apless.isnot(None),
        )
        .order_by(CustomerDocument.document_type, CustomerDocument.upload_dt.desc())
        .all()
    )

    grouped: dict[str, list[dict]] = {}
    director_docs: list[dict] = []
    board_docs: list[dict] = []

    for doc in docs:
        if not doc.file_document or doc.file_document == "-":
            continue

        dtype = doc.document_type or ""
        director_match = _DIRECTOR_KTP_RE.match(dtype)
        board_match = _WNA_BOARD_RE.match(dtype)

        if director_match:
            director_docs.append({**doc.to_dict(), "index": int(director_match.group(1))})
        elif board_match:
            board_docs.append({**doc.to_dict(), "index": int(board_match.group(1))})
        else:
            grouped.setdefault(dtype, []).append(doc.to_dict())

    director_docs.sort(key=lambda d: d["index"])
    board_docs.sort(key=lambda d: d["index"])

    return {
        "documents": grouped,
        "director_documents": director_docs,
        "board_documents": board_docs,
        "next_director_index": max((d["index"] for d in director_docs), default=-1) + 1,
        "next_board_index": max((d["index"] for d in board_docs), default=-1) + 1,
        "has_any_document": bool(docs),
    }

@cam_edit_bp.route("/organization-structure", methods=["GET"])
@login_required
def get_organization_structure():
	apless = request.args.get("apless", "")
	applno = request.args.get("applno", "")
	period_override = request.args.get("period")

	with db.engine.connect() as conn:
		creation_ym = _creation_yyyymm(conn, apless, applno)
		period_options = _period_options(conn, apless, creation_ym)
		has_any = len(period_options) > 0

		period = period_override if period_override else (period_options[0] if period_options else "")
		period_data = _load_period_data(conn, apless, period) if period else {
			"capital": {"authorized": "", "paidIn": ""},
			"shareholders": [], "directors": [], "deeds": [],
			"contractSignerSelected": "", "contractSignerOther": "",
			"picSameAsE": True, "picName": "", "managementDetails": {},
		}
		lookups = _fetch_lookups(conn)
		name_options = _fetch_name_options(conn, apless)

	return jsonify({
		"periodOptions": period_options,
		"period": period,
		"hasAnyExistingPeriod": has_any,
		"nameOptions": name_options,
		**lookups,
		**period_data,
	})

@cam_edit_bp.route("/organization-structure/period-check", methods=["GET"])
@login_required
def check_organization_structure_period():
	apless = request.args.get("apless", "")
	applno = request.args.get("applno", "")
	period = request.args.get("period", "")

	if len(period) != 6 or not period.isdigit():
		return jsonify({"valid": False})

	with db.engine.connect() as conn:
		creation_ym = _creation_yyyymm(conn, apless, applno)

	return jsonify({"valid": int(period) <= int(creation_ym)})

@cam_edit_bp.route("/organization-structure", methods=["POST"])
@login_required
def save_organization_structure():
	payload = request.get_json(force=True)
	apless = payload.get("apless", "")
	applno = payload.get("applno", "")
	period = payload.get("period", "")
	is_new = payload.get("isNew", False)
	capital = payload.get("capital", {})
	shareholders = payload.get("shareholders", [])
	directors = payload.get("directors", [])
	deeds = payload.get("deeds", [])
	contract_signer = payload.get("contractSigner", {})
	pic = payload.get("pic", {})
	management_details = payload.get("managementDetails", {})

	messages = []

	if len(period) != 6 or not period.isdigit():
		messages.append("Period not valid")

	for i, d in enumerate(deeds, start=1):
		state_no, deed_no = d.get("stateNo", ""), d.get("deedNo", "")
		if state_no:
			if not d.get("deedDate"):
				messages.append(f"Date of Deed number {i} must not empty")
			if not d.get("certificate"):
				messages.append(f"Certification of Ministry of Law & Human Rights number {i} must not empty")
		if deed_no:
			if not d.get("deedDate"):
				messages.append(f"Date of Deed number {i} must not empty")
			if not d.get("notaryName"):
				messages.append(f"Notary Name number {i} must not empty")
			if not d.get("certificate"):
				messages.append(f"Certification of Ministry of Law & Human Rights number {i} must not empty")

	bod_rows = [d for d in directors if d.get("bod")]
	e_signer_count = sum(1 for d in bod_rows if d.get("signerEcontract"))
	if bod_rows and e_signer_count == 0:
		messages.append("Signer On E-Contract wajib dipilih salah satu")
	if e_signer_count > 1:
		messages.append("Signer On E-Contract hanya boleh dipilih satu")

	if messages:
		return jsonify({"success": False, "messages": messages})

	with db.engine.begin() as conn:
		if is_new:
			existing = conn.execute(text(
				"SELECT 1 FROM CAFORGSTRUCT WITH (NOLOCK) WHERE APLESS = :apless AND PERIOD = :period"
			), {"apless": apless, "period": period}).first()
			if existing:
				return jsonify({"success": False, "message": "Data already exists"})

			other_signer = contract_signer.get("other", "") if contract_signer.get("selected") == "5" else ""
			pic_value = "" if pic.get("sameAsE") else pic.get("name", "")

			conn.execute(text("""
				INSERT INTO CAFORGSTRUCT (APLESS, PERIOD, AUTHORIZED_CAPITAL, PAID_IN_CAPITAL, CONTRACT_SIGNER, OTHER_SIGNER, PIC)
				VALUES (:apless, :period, :authorized, :paid_in, :signer, :other_signer, :pic)
			"""), {
				"apless": apless, "period": period,
				"authorized": capital.get("authorized", "0") or "0",
				"paid_in": capital.get("paidIn", "0") or "0",
				"signer": contract_signer.get("selected", ""), "other_signer": other_signer, "pic": pic_value,
			})
		else:
			other_signer = contract_signer.get("other", "") if contract_signer.get("selected") == "5" else ""
			pic_value = "" if pic.get("sameAsE") else pic.get("name", "")
			conn.execute(text("""
				UPDATE CAFORGSTRUCT SET AUTHORIZED_CAPITAL = :authorized, PAID_IN_CAPITAL = :paid_in,
				       CONTRACT_SIGNER = :signer, OTHER_SIGNER = :other_signer, PIC = :pic
				WHERE APLESS = :apless AND PERIOD = :period
			"""), {
				"apless": apless, "period": period,
				"authorized": capital.get("authorized", "0") or "0",
				"paid_in": capital.get("paidIn", "0") or "0",
				"signer": contract_signer.get("selected", ""), "other_signer": other_signer, "pic": pic_value,
			})
			conn.execute(text(
				"DELETE FROM CAFORGSTRUCT_DETAIL WHERE APLESS = :apless AND PERIOD = :period AND OS_CODE IN ('PT01', 'PT02', 'PT03', 'PT04')"
			), {"apless": apless, "period": period})

		for s in shareholders:
			if not s.get("name"):
				continue
			dc = _detail_columns_for_insert(s["name"], s.get("status", ""), management_details)
			conn.execute(text("""
				INSERT INTO CAFORGSTRUCT_DETAIL (
					APLESS, PERIOD, OS_CODE, MANAGEMENT_NM, TOTOFSHARES, NOMOFSHARES, SIGNER, SHAREHOLDER_STATUS,
					name, gender, kecamatan, kelurahan, CITIZEN, NATIONALITY, PASSPORTNO, [ADDRESS], CITY,
					ID_CARD, NPWP, NAME_NPWP, ADD_NPWP, CITY_NPWP, KECAMATAN_NPWP, KELURAHAN_NPWP,
					PlaceOfBirth, DateOfBirth, PostCode, IDType, NoExpireDate, ValidityCertainPeriod,
					PostCode_NPWP, MobilePhone, Email
				) VALUES (
					:apless, :period, 'PT01', :name, :total, :nominal, :signer, :status,
					:detail_name, :gender, :kecamatan, :kelurahan, :citizen, :nationality, :passportno, :address, :city,
					:id_card, :npwp, :name_npwp, :add_npwp, :city_npwp, :kecamatan_npwp, :kelurahan_npwp,
					:place_of_birth, :date_of_birth, :post_code, :id_type, :no_expire_date, :certain_period,
					:post_code_npwp, :mobile_phone, :email
				)
			"""), {
				"apless": apless, "period": period, "name": s["name"],
				"total": s.get("totalShares", "0") or "0", "nominal": s.get("nominalShares", "0") or "0",
				"signer": "1" if s.get("signer") else "0", "status": s.get("status", ""),
				**dc,
			})

		for d in directors:
			if not d.get("name"):
				continue
			if d.get("bod"):
				os_code, pos = "PT02", (d.get("other", "") if d["bod"] == BOD_OTHER_VALUE else d["bod"])
			elif d.get("boc"):
				os_code, pos = "PT03", (d.get("other", "") if d["boc"] == BOC_OTHER_VALUE else d["boc"])
			else:
				continue

			dc = _detail_columns_for_insert(d["name"], "", management_details)
			conn.execute(text("""
				INSERT INTO CAFORGSTRUCT_DETAIL (
					APLESS, PERIOD, OS_CODE, MANAGEMENT_NM, POS_DEEDNO, SIGNER, OWNER, SIGNER_ECONTRACT,
					name, gender, kecamatan, kelurahan, CITIZEN, NATIONALITY, PASSPORTNO, [ADDRESS], CITY,
					ID_CARD, NPWP, NAME_NPWP, ADD_NPWP, CITY_NPWP, KECAMATAN_NPWP, KELURAHAN_NPWP,
					PlaceOfBirth, DateOfBirth, PostCode, IDType, NoExpireDate, ValidityCertainPeriod,
					PostCode_NPWP, MobilePhone, Email
				) VALUES (
					:apless, :period, :os_code, :name, :pos, :signer, :owner, :signer_econtract,
					:detail_name, :gender, :kecamatan, :kelurahan, :citizen, :nationality, :passportno, :address, :city,
					:id_card, :npwp, :name_npwp, :add_npwp, :city_npwp, :kecamatan_npwp, :kelurahan_npwp,
					:place_of_birth, :date_of_birth, :post_code, :id_type, :no_expire_date, :certain_period,
					:post_code_npwp, :mobile_phone, :email
				)
			"""), {
				"apless": apless, "period": period, "os_code": os_code, "name": d["name"], "pos": pos,
				"signer": "1" if d.get("signer") else "0", "owner": "1" if d.get("owner") else "0",
				"signer_econtract": "1" if d.get("signerEcontract") else "0",
				**dc,
			})

		for d in deeds:
			state_no, deed_no = d.get("stateNo", ""), d.get("deedNo", "")
			if not state_no and not deed_no:
				continue
			deed_date = None
			if d.get("deedDate"):
				try:
					deed_date = datetime.strptime(d["deedDate"], "%d-%m-%Y").date()
				except ValueError:
					deed_date = None
			conn.execute(text("""
				INSERT INTO CAFORGSTRUCT_DETAIL (APLESS, PERIOD, OS_CODE, MANAGEMENT_NM, POS_DEEDNO, DATE_OF_DEED, NOTARY_NM, CERTIFICATE)
				VALUES (:apless, :period, 'PT04', :state_no, :deed_no, :deed_date, :notary, :certificate)
			"""), {
				"apless": apless, "period": period, "state_no": state_no, "deed_no": deed_no,
				"deed_date": deed_date, "notary": d.get("notaryName", ""), "certificate": d.get("certificate", ""),
			})

		conn.execute(text(
			"DELETE FROM CAFDEV WHERE APPL_NO = :applno AND DEVIATION_CD IN ('2003', '2004', '2005')"
		), {"applno": applno})
		cert_to_dev = {"4": "2003", "5": "2004", "6": "2005"}
		for d in deeds:
			dev_cd = cert_to_dev.get(d.get("certificate", ""))
			if not dev_cd:
				continue
			existing_dev = conn.execute(text(
				"SELECT 1 FROM CAFDEV WITH (NOLOCK) WHERE APPL_NO = :applno AND DEVIATION_CD = :dev_cd"
			), {"applno": applno, "dev_cd": dev_cd}).first()
			if existing_dev:
				continue
			desc_row = conn.execute(text(
				"SELECT DEVIATION_DESC, STANDARD_DESC FROM MSTDEVIATION WITH (NOLOCK) WHERE DEVIATION_CD = :dev_cd"
			), {"dev_cd": dev_cd}).mappings().first()
			if desc_row:
				conn.execute(text("""
					INSERT INTO CAFDEV (APPL_NO, DEVIATION_CD, REASON, DEVIATION_DESC, STANDARD_DESC, INPUT_DT)
					VALUES (:applno, :dev_cd, '', :desc, :standard, SYSDATETIME())
				"""), {"applno": applno, "dev_cd": dev_cd, "desc": desc_row["DEVIATION_DESC"], "standard": desc_row["STANDARD_DESC"]})

	return jsonify({"success": True, "apless": apless, "applno": applno})

def _reconstruct_deed_slots(rows, valid_certs: set, z_start: int, make_entry, blank_entry: dict):
    total = len(rows)
    slots = [None] * total
    q, z = 1, z_start
    for r in rows:
        cert_value = str(r["certificate"]).strip() if r["certificate"] is not None else ""
        matches = cert_value in valid_certs
        idx = q if matches else z
        if matches:
            q += 1
        else:
            z += 1
        if 1 <= idx <= total:
            slots[idx - 1] = make_entry(r)
    return [s if s is not None else dict(blank_entry) for s in slots]

def _fetch_lookups_fd(conn):
	pengurus_positions = conn.execute(text(
		"SELECT ID_OS_POSITION AS value, [DESC] AS label FROM MSTOS_POSITION WITH (NOLOCK) WHERE OS_CODE = 'FD02'"
	)).mappings().all()
	certificate_options = conn.execute(text(
		"SELECT ID_OS_CERTIFICATE AS value, CERT_CODE AS label FROM MSTOS_CERTIFICATE WITH (NOLOCK) WHERE CUST_TYPE = 'FD'"
	)).mappings().all()
	certificate_descriptions = conn.execute(text(
		"SELECT CERT_CODE AS value, [DESC] AS label FROM MSTOS_CERTIFICATE WITH (NOLOCK) WHERE CUST_TYPE = 'FD'"
	)).mappings().all()
	contract_signer_options = conn.execute(text(
		"SELECT ID_OS_SIGNER AS value, [DESC] AS label FROM MSTOS_SIGNER WITH (NOLOCK) WHERE CUST_TYPE = 'FD'"
	)).mappings().all()
	area_options = conn.execute(text(
		"SELECT AREA_CD AS value, Propinsi + ' - ' + Kabupaten AS label FROM UMFAREA WITH (NOLOCK) WHERE FLAG_DEL = 0 ORDER BY Propinsi, Kabupaten"
	)).mappings().all()
	nationality_options = conn.execute(text(
		"SELECT ID2digit AS value, Name AS label FROM Mst_Country WITH (NOLOCK) ORDER BY Name"
	)).mappings().all()
	return {
		"pengurusPositions": [dict(r) for r in pengurus_positions],
		"certificateOptions": [dict(r) for r in certificate_options],
		"certificateDescriptions": [dict(r) for r in certificate_descriptions],
		"contractSignerOptions": [dict(r) for r in contract_signer_options],
		"areaOptions": [dict(r) for r in area_options],
		"nationalityOptions": [dict(r) for r in nationality_options],
	}

def _fetch_name_options(conn, apless: str):
	rows = conn.execute(text("""
		SELECT Id AS value, Nama AS label
		FROM TEMP_CAFLESS_OCR
		WHERE Prechecking_Id = (SELECT Prechecking_Id FROM CAFLESS WHERE APLESS = :apless)
	"""), {"apless": apless}).mappings().all()
	return [dict(r) for r in rows]

def _load_management_details_fd(conn, apless: str, period: str):
	rows = conn.execute(text("""
		SELECT DISTINCT MANAGEMENT_NM, ID_CARD, [ADDRESS], CITY, name, gender, kecamatan, kelurahan,
		       cod.PASSPORTNO, CITIZEN, NATIONALITY, ua.Propinsi, ua.AREA_CD,
		       PlaceOfBirth, DateOfBirth, PostCode, IDType, NoExpireDate, ValidityCertainPeriod,
		       PostCode_NPWP, MobilePhone, Email
		FROM CAFORGSTRUCT_DETAIL cod WITH (NOLOCK)
		    LEFT JOIN UMFAREA ua WITH (NOLOCK) ON ua.KABUPATEN = CITY
		WHERE cod.APLESS = :apless AND PERIOD = :period AND OS_CODE IN ('FD01', 'FD02', 'FD03')
	"""), {"apless": apless, "period": period}).mappings().all()

	def fmt_date(v):
		return v.strftime("%d-%m-%Y") if isinstance(v, (date, datetime)) else ""

	result = {}
	for r in rows:
		name = r["MANAGEMENT_NM"]
		if not name:
			continue
		city_outside = r["CITY"] == "9999"
		result[name] = {
			"nameWithoutTitle": r["name"] or "",
			"gender": r["gender"] or "",
			"placeOfBirth": r["PlaceOfBirth"] or "",
			"dateOfBirth": fmt_date(r["DateOfBirth"]),
			"address": r["ADDRESS"] or "",
			"areaCd": "9999" if city_outside else (r["AREA_CD"] or ""),
			"province": "Di Luar Wilayah Indonesia" if city_outside else (r["Propinsi"] or ""),
			"city": "Di Luar Wilayah Indonesia" if city_outside else (r["CITY"] or ""),
			"kecamatan": r["kecamatan"] or "",
			"kelurahan": r["kelurahan"] or "",
			"postCode": r["PostCode"] or "",
			"citizen": r["CITIZEN"] or "",
			"nationality": r["NATIONALITY"] or "",
			"idCard": r["ID_CARD"] or "",
			"passportNo": r["PASSPORTNO"] or "",
			"idType": r["IDType"] or "",
			"noExpireDate": str(r["NoExpireDate"]) if r["NoExpireDate"] is not None else "",
			"certainPeriod": fmt_date(r["ValidityCertainPeriod"]),
			"mobilePhone": _normalize_phone(r["MobilePhone"]),
			"email": r["Email"] or "",
			"nameInNpwp": "", "establishPlace": "", "establishDate": "", "addressNpwp": "",
			"areaCdNpwp": "", "provinceNpwp": "", "cityNpwp": "", "kecamatanNpwp": "",
			"kelurahanNpwp": "", "npwp": "", "postCodeNpwp": r["PostCode_NPWP"] or "",
		}
	return result

def _format_deed_date(value):
    if isinstance(value, (date, datetime)):
        return value.strftime("%d-%m-%Y")
    if isinstance(value, str):
        s = value.strip().split(".")[0]
        if not s:
            return ""
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(s, fmt).strftime("%d-%m-%Y")
            except ValueError:
                continue
    return ""

def _load_deeds_fd(conn, apless: str, period: str):
    rows = conn.execute(text("""
        SELECT POS_DEEDNO AS deedNo, DATE_OF_DEED AS deedDate, NOTARY_NM AS notaryName, CERTIFICATE AS certificate
        FROM CAFORGSTRUCT_DETAIL WITH (NOLOCK)
        WHERE APLESS = :apless AND PERIOD = :period AND OS_CODE = 'FD04'
        ORDER BY ID_DETAIL
    """), {"apless": apless, "period": period}).mappings().all()

    valid_certs = {
        str(r["value"]).strip()
        for r in conn.execute(text(
            "SELECT ID_OS_CERTIFICATE AS value FROM MSTOS_CERTIFICATE WITH (NOLOCK) WHERE CUST_TYPE = 'FD'"
        )).mappings().all()
    }

    def make_entry(r):
        return {
            "deedNo": r["deedNo"] or "",
            "deedDate": _format_deed_date(r["deedDate"]),
            "notaryName": r["notaryName"] or "",
            "certificate": r["certificate"] or "",
        }

    blank = {"deedNo": "", "deedDate": "", "notaryName": "", "certificate": ""}
    return _reconstruct_deed_slots(rows, valid_certs, 8, make_entry, blank)

def _load_period_data_fd(conn, apless: str, period: str):
	capital_row = conn.execute(text("""
		SELECT CONTRACT_SIGNER, OTHER_SIGNER, PIC
		FROM CAFORGSTRUCT WITH (NOLOCK) WHERE APLESS = :apless AND PERIOD = :period
	"""), {"apless": apless, "period": period}).mappings().first()

	def load_group(os_code, has_econtract=False):
		rows = conn.execute(text(f"""
			SELECT MANAGEMENT_NM AS name, POS_DEEDNO AS position, SIGNER AS signer, OWNER AS owner
			{", SIGNER_ECONTRACT AS signerEcontract" if has_econtract else ""}
			FROM CAFORGSTRUCT_DETAIL WITH (NOLOCK)
			WHERE APLESS = :apless AND PERIOD = :period AND OS_CODE = :os_code
			ORDER BY ID_DETAIL
		"""), {"apless": apless, "period": period, "os_code": os_code}).mappings().all()
		result = []
		for r in rows:
			row = {
				"name": r["name"] or "", "position": r["position"] or "",
				"owner": bool(r["owner"] == "1"), "signer": bool(r["signer"] == "1"),
			}
			if has_econtract:
				row["signerEcontract"] = bool(r["signerEcontract"] == "1")
			result.append(row)
		return result

	return {
		"pembina": load_group("FD01"),
		"pengurus": load_group("FD02", has_econtract=True),
		"pengawas": load_group("FD03"),
		"deeds": _load_deeds_fd(conn, apless, period),
		"contractSignerSelected": (capital_row["CONTRACT_SIGNER"] if capital_row else "") or "",
		"contractSignerOther": (capital_row["OTHER_SIGNER"] if capital_row else "") or "",
		"picSameAsE": not bool(capital_row and capital_row["PIC"]),
		"picName": (capital_row["PIC"] if capital_row else "") or "",
		"managementDetails": _load_management_details_fd(conn, apless, period),
	}

@cam_edit_bp.route("/organization-structure-fd", methods=["GET"])
@login_required
def get_organization_structure_fd():
	apless = request.args.get("apless", "")
	applno = request.args.get("applno", "")
	period_override = request.args.get("period")

	with db.engine.connect() as conn:
		creation_ym = _creation_yyyymm(conn, apless, applno)
		period_options = _period_options(conn, apless, creation_ym)
		has_any = len(period_options) > 0

		period = period_override if period_override else (period_options[0] if period_options else "")
		period_data = _load_period_data_fd(conn, apless, period) if period else {
			"pembina": [], "pengurus": [], "pengawas": [], "deeds": [],
			"contractSignerSelected": "", "contractSignerOther": "",
			"picSameAsE": True, "picName": "", "managementDetails": {},
		}
		lookups = _fetch_lookups_fd(conn)
		name_options = _fetch_name_options(conn, apless)

	return jsonify({
		"periodOptions": period_options,
		"period": period,
		"hasAnyExistingPeriod": has_any,
		"nameOptions": name_options,
		**lookups,
		**period_data,
	})

@cam_edit_bp.route("/organization-structure-fd/period-check", methods=["GET"])
@login_required
def check_organization_structure_period_fd():
	apless = request.args.get("apless", "")
	applno = request.args.get("applno", "")
	period = request.args.get("period", "")

	if len(period) != 6 or not period.isdigit():
		return jsonify({"code": None})

	with db.engine.connect() as conn:
		creation_ym = _creation_yyyymm(conn, apless, applno)

	tahun, bulan = int(creation_ym[:4]), int(creation_ym[4:6])
	year_new, month_new = int(period[:4]), int(period[4:6])

	code = None
	try:
		if tahun == year_new or year_new > tahun:
			if date(year_new, month_new, 1) > date(tahun, bulan, 1):
				code = "0"
		else:
			if date(tahun - 1, bulan, 1) > date(year_new, month_new, 1):
				code = "9"
	except ValueError:
		code = "0"

	return jsonify({"code": code})

@cam_edit_bp.route("/organization-structure-fd", methods=["POST"])
@login_required
def save_organization_structure_fd():
	payload = request.get_json(force=True)
	apless = payload.get("apless", "")
	applno = payload.get("applno", "")
	period = payload.get("period", "")
	is_new = payload.get("isNew", False)
	pembina = payload.get("pembina", [])
	pengurus = payload.get("pengurus", [])
	pengawas = payload.get("pengawas", [])
	deeds = payload.get("deeds", [])
	contract_signer = payload.get("contractSigner", {})
	pic = payload.get("pic", {})
	management_details = payload.get("managementDetails", {})

	messages = []

	if len(period) != 6 or not period.isdigit():
		messages.append("Period not valid")

	for i, d in enumerate(deeds, start=1):
		if d.get("deedNo") and not d.get("deedDate"):
			messages.append(f"Date of Deed number {i} must not empty")

	pengurus_with_position = [p for p in pengurus if p.get("position")]
	e_signer_count = sum(1 for p in pengurus_with_position if p.get("signerEcontract"))
	if pengurus_with_position and e_signer_count == 0:
		messages.append("Signer On E-Contract wajib dipilih salah satu")
	if e_signer_count > 1:
		messages.append("Signer On E-Contract hanya boleh dipilih satu")

	if messages:
		return jsonify({"success": False, "messages": messages})

	def detail_columns(name):
		d = management_details.get(name)
		if not d:
			return {
				"detail_name": "", "gender": "", "kecamatan": "", "kelurahan": "", "citizen": "",
				"nationality": "", "passportno": "", "address": "", "city": "", "id_card": "",
				"place_of_birth": "", "date_of_birth": None, "post_code": "", "id_type": "",
				"no_expire_date": "", "certain_period": None, "post_code_npwp": "",
				"mobile_phone": "", "email": "",
			}
		outside = d.get("areaCd") == "9999"
		return {
			"detail_name": d.get("nameWithoutTitle", ""),
			"gender": d.get("gender", ""),
			"kecamatan": "999999" if outside else d.get("kecamatan", ""),
			"kelurahan": "9999999999" if outside else d.get("kelurahan", ""),
			"citizen": d.get("citizen", ""),
			"nationality": "ID" if d.get("citizen") == "WNI" else d.get("nationality", ""),
			"passportno": d.get("passportNo", "") if d.get("citizen") == "WNA" else "",
			"address": d.get("address", ""),
			"city": "9999" if outside else d.get("city", ""),
			"id_card": d.get("idCard", ""),
			"place_of_birth": d.get("placeOfBirth", "") or "",
			"date_of_birth": _parse_ddmmyyyy(d.get("dateOfBirth")),
			"post_code": d.get("postCode", ""),
			"id_type": d.get("idType", ""),
			"no_expire_date": d.get("noExpireDate", ""),
			"certain_period": _parse_ddmmyyyy(d.get("certainPeriod")),
			"post_code_npwp": d.get("postCodeNpwp", ""),
			"mobile_phone": d.get("mobilePhone", ""),
			"email": d.get("email", ""),
		}

	with db.engine.begin() as conn:
		if is_new:
			existing = conn.execute(text(
				"SELECT 1 FROM CAFORGSTRUCT WITH (NOLOCK) WHERE APLESS = :apless AND PERIOD = :period"
			), {"apless": apless, "period": period}).first()
			if existing:
				return jsonify({"success": False, "message": "Data already exists"})

			other_signer = contract_signer.get("other", "") if contract_signer.get("selected") == "16" else ""
			pic_value = "" if pic.get("sameAsE") else pic.get("name", "")
			conn.execute(text("""
				INSERT INTO CAFORGSTRUCT (APLESS, PERIOD, CONTRACT_SIGNER, OTHER_SIGNER, PIC)
				VALUES (:apless, :period, :signer, :other_signer, :pic)
			"""), {"apless": apless, "period": period, "signer": contract_signer.get("selected", ""),
				"other_signer": other_signer, "pic": pic_value})
		else:
			other_signer = contract_signer.get("other", "") if contract_signer.get("selected") == "16" else ""
			pic_value = "" if pic.get("sameAsE") else pic.get("name", "")
			conn.execute(text("""
				UPDATE CAFORGSTRUCT SET CONTRACT_SIGNER = :signer, OTHER_SIGNER = :other_signer, PIC = :pic
				WHERE APLESS = :apless AND PERIOD = :period
			"""), {"apless": apless, "period": period, "signer": contract_signer.get("selected", ""),
				"other_signer": other_signer, "pic": pic_value})
			conn.execute(text(
				"DELETE FROM CAFORGSTRUCT_DETAIL WHERE APLESS = :apless AND PERIOD = :period AND OS_CODE IN ('FD01', 'FD02', 'FD03', 'FD04')"
			), {"apless": apless, "period": period})

		def insert_member(os_code, name, position, owner, signer, signer_econtract=None):
			dc = detail_columns(name)
			cols = "APLESS, PERIOD, OS_CODE, MANAGEMENT_NM, POS_DEEDNO, SIGNER, OWNER"
			vals = ":apless, :period, :os_code, :name, :pos, :signer, :owner"
			params = {
				"apless": apless, "period": period, "os_code": os_code, "name": name, "pos": position,
				"signer": "1" if signer else "0", "owner": "1" if owner else "0", **dc,
			}
			if signer_econtract is not None:
				cols += ", SIGNER_ECONTRACT"
				vals += ", :signer_econtract"
				params["signer_econtract"] = "1" if signer_econtract else "0"
			cols += (", name, gender, kecamatan, kelurahan, CITIZEN, NATIONALITY, PASSPORTNO, [ADDRESS], CITY, "
				"ID_CARD, PlaceOfBirth, DateOfBirth, PostCode, IDType, NoExpireDate, ValidityCertainPeriod, "
				"PostCode_NPWP, MobilePhone, Email")
			vals += (", :detail_name, :gender, :kecamatan, :kelurahan, :citizen, :nationality, :passportno, "
				":address, :city, :id_card, :place_of_birth, :date_of_birth, :post_code, :id_type, "
				":no_expire_date, :certain_period, :post_code_npwp, :mobile_phone, :email")
			conn.execute(text(f"INSERT INTO CAFORGSTRUCT_DETAIL ({cols}) VALUES ({vals})"), params)

		for p in pembina:
			if p.get("name"):
				insert_member("FD01", p["name"], p.get("position", ""), p.get("owner"), p.get("signer"))
		for p in pengurus:
			if p.get("name"):
				insert_member("FD02", p["name"], p.get("position", ""), p.get("owner"), p.get("signer"), p.get("signerEcontract"))
		for p in pengawas:
			if p.get("name"):
				insert_member("FD03", p["name"], p.get("position", ""), p.get("owner"), p.get("signer"))

		for d in deeds:
			if not d.get("deedNo"):
				continue
			conn.execute(text("""
				INSERT INTO CAFORGSTRUCT_DETAIL (APLESS, PERIOD, OS_CODE, POS_DEEDNO, DATE_OF_DEED, NOTARY_NM, CERTIFICATE)
				VALUES (:apless, :period, 'FD04', :deed_no, :deed_date, :notary, :certificate)
			"""), {
				"apless": apless, "period": period, "deed_no": d["deedNo"],
				"deed_date": _parse_ddmmyyyy(d.get("deedDate")), "notary": d.get("notaryName", ""),
				"certificate": d.get("certificate", ""),
			})

		conn.execute(text(
			"DELETE FROM CAFDEV WHERE APPL_NO = :applno AND DEVIATION_CD IN ('2102', '2103', '2104')"
		), {"applno": applno})
		cert_to_dev = {"20": "2102", "21": "2103", "22": "2104"}
		for d in deeds:
			dev_cd = cert_to_dev.get(d.get("certificate", ""))
			if not dev_cd:
				continue
			existing_dev = conn.execute(text(
				"SELECT 1 FROM CAFDEV WITH (NOLOCK) WHERE APPL_NO = :applno AND DEVIATION_CD = :dev_cd"
			), {"applno": applno, "dev_cd": dev_cd}).first()
			if existing_dev:
				continue
			desc_row = conn.execute(text(
				"SELECT DEVIATION_DESC, STANDARD_DESC FROM MSTDEVIATION WITH (NOLOCK) WHERE DEVIATION_CD = :dev_cd"
			), {"dev_cd": dev_cd}).mappings().first()
			if desc_row:
				conn.execute(text("""
					INSERT INTO CAFDEV (APPL_NO, DEVIATION_CD, REASON, DEVIATION_DESC, STANDARD_DESC, INPUT_DT)
					VALUES (:applno, :dev_cd, '', :desc, :standard, SYSDATETIME())
				"""), {"applno": applno, "dev_cd": dev_cd, "desc": desc_row["DEVIATION_DESC"], "standard": desc_row["STANDARD_DESC"]})

	return jsonify({"success": True, "apless": apless, "applno": applno})

ACTIVE_OTHER_VALUE = "15"
LIMITED_OTHER_VALUE = "18"

def _fetch_lookups_cv(conn):
	active_positions = conn.execute(text(
		"SELECT ID_OS_POSITION AS value, [DESC] AS label FROM MSTOS_POSITION WITH (NOLOCK) WHERE OS_CODE = 'CV01'"
	)).mappings().all()
	limited_positions = conn.execute(text(
		"SELECT ID_OS_POSITION AS value, [DESC] AS label FROM MSTOS_POSITION WITH (NOLOCK) WHERE OS_CODE = 'CV02'"
	)).mappings().all()
	certificate_options = conn.execute(text(
		"SELECT ID_OS_CERTIFICATE AS value, CERT_CODE AS label FROM MSTOS_CERTIFICATE WITH (NOLOCK) WHERE CUST_TYPE = 'CV'"
	)).mappings().all()
	contract_signer_options = conn.execute(text(
		"SELECT ID_OS_SIGNER AS value, [DESC] AS label FROM MSTOS_SIGNER WITH (NOLOCK) WHERE CUST_TYPE = 'CV'"
	)).mappings().all()
	area_options = conn.execute(text(
		"SELECT AREA_CD AS value, Propinsi + ' - ' + Kabupaten AS label FROM UMFAREA WITH (NOLOCK) WHERE FLAG_DEL = 0 ORDER BY Propinsi, Kabupaten"
	)).mappings().all()
	nationality_options = conn.execute(text(
		"SELECT ID2digit AS value, Name AS label FROM Mst_Country WITH (NOLOCK) ORDER BY Name"
	)).mappings().all()
	return {
		"activePositions": [dict(r) for r in active_positions],
		"limitedPositions": [dict(r) for r in limited_positions],
		"certificateOptions": [dict(r) for r in certificate_options],
		"contractSignerOptions": [dict(r) for r in contract_signer_options],
		"areaOptions": [dict(r) for r in area_options],
		"nationalityOptions": [dict(r) for r in nationality_options],
	}

def _fetch_name_options(conn, apless: str):
	rows = conn.execute(text("""
		SELECT Id AS value, Nama AS label
		FROM TEMP_CAFLESS_OCR
		WHERE Prechecking_Id = (SELECT Prechecking_Id FROM CAFLESS WHERE APLESS = :apless)
	"""), {"apless": apless}).mappings().all()
	return [dict(r) for r in rows]

def _load_management_details_cv(conn, apless: str, period: str):
	rows = conn.execute(text("""
		SELECT DISTINCT MANAGEMENT_NM, ID_CARD, [ADDRESS], CITY, name, gender, kecamatan, kelurahan,
		       cod.PASSPORTNO, CITIZEN, NATIONALITY, ua.Propinsi, ua.AREA_CD,
		       PlaceOfBirth, DateOfBirth, PostCode, IDType, NoExpireDate, ValidityCertainPeriod,
		       PostCode_NPWP, MobilePhone, Email
		FROM CAFORGSTRUCT_DETAIL cod WITH (NOLOCK)
		    LEFT JOIN UMFAREA ua WITH (NOLOCK) ON ua.KABUPATEN = CITY
		WHERE cod.APLESS = :apless AND PERIOD = :period AND OS_CODE IN ('CV01', 'CV02')
	"""), {"apless": apless, "period": period}).mappings().all()

	def fmt_date(v):
		return v.strftime("%d-%m-%Y") if isinstance(v, (date, datetime)) else ""

	result = {}
	for r in rows:
		name = r["MANAGEMENT_NM"]
		if not name:
			continue
		city_outside = r["CITY"] == "9999"
		result[name] = {
			"nameWithoutTitle": r["name"] or "",
			"gender": r["gender"] or "",
			"placeOfBirth": r["PlaceOfBirth"] or "",
			"dateOfBirth": fmt_date(r["DateOfBirth"]),
			"address": r["ADDRESS"] or "",
			"areaCd": "9999" if city_outside else (r["AREA_CD"] or ""),
			"province": "Di Luar Wilayah Indonesia" if city_outside else (r["Propinsi"] or ""),
			"city": "Di Luar Wilayah Indonesia" if city_outside else (r["CITY"] or ""),
			"kecamatan": r["kecamatan"] or "",
			"kelurahan": r["kelurahan"] or "",
			"postCode": r["PostCode"] or "",
			"citizen": r["CITIZEN"] or "",
			"nationality": r["NATIONALITY"] or "",
			"idCard": r["ID_CARD"] or "",
			"passportNo": r["PASSPORTNO"] or "",
			"idType": r["IDType"] or "",
			"noExpireDate": str(r["NoExpireDate"]) if r["NoExpireDate"] is not None else "",
			"certainPeriod": fmt_date(r["ValidityCertainPeriod"]),
			"mobilePhone": _normalize_phone(r["MobilePhone"]),
			"email": r["Email"] or "",
			"nameInNpwp": "", "establishPlace": "", "establishDate": "", "addressNpwp": "",
			"areaCdNpwp": "", "provinceNpwp": "", "cityNpwp": "", "kecamatanNpwp": "",
			"kelurahanNpwp": "", "npwp": "", "postCodeNpwp": r["PostCode_NPWP"] or "",
		}
	return result

def _load_period_data_cv(conn, apless: str, period: str):
	capital_row = conn.execute(text("""
		SELECT CONTRACT_SIGNER, OTHER_SIGNER, PIC
		FROM CAFORGSTRUCT WITH (NOLOCK) WHERE APLESS = :apless AND PERIOD = :period
	"""), {"apless": apless, "period": period}).mappings().first()

	active_ids = {r["value"] for r in conn.execute(text(
		"SELECT ID_OS_POSITION AS value FROM MSTOS_POSITION WITH (NOLOCK) WHERE OS_CODE = 'CV01'"
	)).mappings().all()}
	limited_ids = {r["value"] for r in conn.execute(text(
		"SELECT ID_OS_POSITION AS value FROM MSTOS_POSITION WITH (NOLOCK) WHERE OS_CODE = 'CV02'"
	)).mappings().all()}

	rows = conn.execute(text("""
		SELECT MANAGEMENT_NM AS name, OS_CODE AS osCode, POS_DEEDNO AS posDeedNo,
		       SIGNER AS signer, OWNER AS owner, SIGNER_ECONTRACT AS signerEcontract
		FROM CAFORGSTRUCT_DETAIL WITH (NOLOCK)
		WHERE APLESS = :apless AND PERIOD = :period AND OS_CODE IN ('CV01', 'CV02')
		ORDER BY ID_DETAIL
	"""), {"apless": apless, "period": period}).mappings().all()

	persero = []
	for r in rows:
		is_active = r["osCode"] == "CV01"
		known = r["posDeedNo"] in (active_ids if is_active else limited_ids)
		persero.append({
			"name": r["name"] or "",
			"active": (r["posDeedNo"] if is_active and known else (ACTIVE_OTHER_VALUE if is_active else "")),
			"limited": (r["posDeedNo"] if not is_active and known else (LIMITED_OTHER_VALUE if not is_active else "")),
			"other": ("" if known else (r["posDeedNo"] or "")),
			"owner": bool(r["owner"] == "1"),
			"signer": bool(r["signer"] == "1"),
			"signerEcontract": bool(r["signerEcontract"] == "1"),
		})

	deeds_raw = conn.execute(text("""
		SELECT POS_DEEDNO AS deedNo, DATE_OF_DEED AS deedDate, NOTARY_NM AS notaryName, CERTIFICATE AS certificate
		FROM CAFORGSTRUCT_DETAIL WITH (NOLOCK)
		WHERE APLESS = :apless AND PERIOD = :period AND OS_CODE = 'CV03'
		ORDER BY ID_DETAIL
	"""), {"apless": apless, "period": period}).mappings().all()
	deeds = [{
		"deedNo": d["deedNo"] or "",
		"deedDate": d["deedDate"].strftime("%d-%m-%Y") if isinstance(d["deedDate"], (date, datetime)) else "",
		"notaryName": d["notaryName"] or "",
		"certificate": d["certificate"] or "",
	} for d in deeds_raw]

	return {
		"persero": persero,
		"deeds": deeds,
		"contractSignerSelected": (capital_row["CONTRACT_SIGNER"] if capital_row else "") or "",
		"contractSignerOther": (capital_row["OTHER_SIGNER"] if capital_row else "") or "",
		"picSameAsE": not bool(capital_row and capital_row["PIC"]),
		"picName": (capital_row["PIC"] if capital_row else "") or "",
		"managementDetails": _load_management_details_cv(conn, apless, period),
	}

@cam_edit_bp.route("/organization-structure-cv", methods=["GET"])
@login_required
def get_organization_structure_cv():
	apless = request.args.get("apless", "")
	applno = request.args.get("applno", "")
	period_override = request.args.get("period")

	with db.engine.connect() as conn:
		creation_ym = _creation_yyyymm(conn, apless, applno)
		period_options = _period_options(conn, apless, creation_ym)
		has_any = len(period_options) > 0

		period = period_override if period_override else (period_options[0] if period_options else "")
		period_data = _load_period_data_cv(conn, apless, period) if period else {
			"persero": [], "deeds": [],
			"contractSignerSelected": "", "contractSignerOther": "",
			"picSameAsE": True, "picName": "", "managementDetails": {},
		}
		lookups = _fetch_lookups_cv(conn)
		name_options = _fetch_name_options(conn, apless)

	return jsonify({
		"periodOptions": period_options,
		"period": period,
		"hasAnyExistingPeriod": has_any,
		"nameOptions": name_options,
		**lookups,
		**period_data,
	})

@cam_edit_bp.route("/organization-structure-cv/period-check", methods=["GET"])
@login_required
def check_organization_structure_period_cv():
	apless = request.args.get("apless", "")
	applno = request.args.get("applno", "")
	period = request.args.get("period", "")

	if len(period) != 6 or not period.isdigit():
		return jsonify({"code": None})

	with db.engine.connect() as conn:
		creation_ym = _creation_yyyymm(conn, apless, applno)

	tahun, bulan = int(creation_ym[:4]), int(creation_ym[4:6])
	year_new, month_new = int(period[:4]), int(period[4:6])

	code = None
	try:
		if tahun == year_new or year_new > tahun:
			if date(year_new, month_new, 1) > date(tahun, bulan, 1):
				code = "0"
		else:
			if date(tahun - 1, bulan, 1) > date(year_new, month_new, 1):
				code = "9"
	except ValueError:
		code = "0"

	return jsonify({"code": code})

@cam_edit_bp.route("/organization-structure-cv", methods=["POST"])
@login_required
def save_organization_structure_cv():
	payload = request.get_json(force=True)
	apless = payload.get("apless", "")
	applno = payload.get("applno", "")
	period = payload.get("period", "")
	is_new = payload.get("isNew", False)
	persero = payload.get("persero", [])
	deeds = payload.get("deeds", [])
	contract_signer = payload.get("contractSigner", {})
	pic = payload.get("pic", {})
	management_details = payload.get("managementDetails", {})

	messages = []

	if len(period) != 6 or not period.isdigit():
		messages.append("Period not valid")

	active_rows = [p for p in persero if p.get("active")]
	e_signer_count = sum(1 for p in active_rows if p.get("signerEcontract"))
	if active_rows and e_signer_count == 0:
		messages.append("Signer On E-Contract wajib dipilih salah satu")
	if e_signer_count > 1:
		messages.append("Signer On E-Contract hanya boleh dipilih satu")

	if messages:
		return jsonify({"success": False, "messages": messages})

	def detail_columns(name):
		d = management_details.get(name)
		if not d:
			return {
				"detail_name": "", "gender": "", "kecamatan": "", "kelurahan": "", "citizen": "",
				"nationality": "", "passportno": "", "address": "", "city": "", "id_card": "",
				"place_of_birth": "", "date_of_birth": None, "post_code": "", "id_type": "",
				"no_expire_date": "", "certain_period": None, "post_code_npwp": "",
				"mobile_phone": "", "email": "",
			}
		outside = d.get("areaCd") == "9999"
		return {
			"detail_name": d.get("nameWithoutTitle", ""),
			"gender": d.get("gender", ""),
			"kecamatan": "999999" if outside else d.get("kecamatan", ""),
			"kelurahan": "9999999999" if outside else d.get("kelurahan", ""),
			"citizen": d.get("citizen", ""),
			"nationality": "ID" if d.get("citizen") == "WNI" else d.get("nationality", ""),
			"passportno": d.get("passportNo", "") if d.get("citizen") == "WNA" else "",
			"address": d.get("address", ""),
			"city": "9999" if outside else d.get("city", ""),
			"id_card": d.get("idCard", ""),
			"place_of_birth": d.get("placeOfBirth", "") or "",
			"date_of_birth": _parse_ddmmyyyy(d.get("dateOfBirth")),
			"post_code": d.get("postCode", ""),
			"id_type": d.get("idType", ""),
			"no_expire_date": d.get("noExpireDate", ""),
			"certain_period": _parse_ddmmyyyy(d.get("certainPeriod")),
			"post_code_npwp": d.get("postCodeNpwp", ""),
			"mobile_phone": d.get("mobilePhone", ""),
			"email": d.get("email", ""),
		}

	with db.engine.begin() as conn:
		if is_new:
			existing = conn.execute(text(
				"SELECT 1 FROM CAFORGSTRUCT WITH (NOLOCK) WHERE APLESS = :apless AND PERIOD = :period"
			), {"apless": apless, "period": period}).first()
			if existing:
				return jsonify({"success": False, "message": "Data already exists"})

			other_signer = contract_signer.get("other", "") if contract_signer.get("selected") == "10" else ""
			pic_value = "" if pic.get("sameAsE") else pic.get("name", "")
			conn.execute(text("""
				INSERT INTO CAFORGSTRUCT (APLESS, PERIOD, CONTRACT_SIGNER, OTHER_SIGNER, PIC)
				VALUES (:apless, :period, :signer, :other_signer, :pic)
			"""), {"apless": apless, "period": period, "signer": contract_signer.get("selected", ""),
				"other_signer": other_signer, "pic": pic_value})
		else:
			other_signer = contract_signer.get("other", "") if contract_signer.get("selected") == "10" else ""
			pic_value = "" if pic.get("sameAsE") else pic.get("name", "")
			conn.execute(text("""
				UPDATE CAFORGSTRUCT SET CONTRACT_SIGNER = :signer, OTHER_SIGNER = :other_signer, PIC = :pic
				WHERE APLESS = :apless AND PERIOD = :period
			"""), {"apless": apless, "period": period, "signer": contract_signer.get("selected", ""),
				"other_signer": other_signer, "pic": pic_value})
			conn.execute(text(
				"DELETE FROM CAFORGSTRUCT_DETAIL WHERE APLESS = :apless AND PERIOD = :period AND OS_CODE IN ('CV01', 'CV02', 'CV03')"
			), {"apless": apless, "period": period})

		for p in persero:
			name = p.get("name")
			if not name:
				continue
			if p.get("active"):
				os_code = "CV01"
				pos = p.get("other", "") if p["active"] == ACTIVE_OTHER_VALUE else p["active"]
			elif p.get("limited"):
				os_code = "CV02"
				pos = p.get("other", "") if p["limited"] == LIMITED_OTHER_VALUE else p["limited"]
			else:
				continue
			dc = detail_columns(name)
			conn.execute(text("""
				INSERT INTO CAFORGSTRUCT_DETAIL (
					APLESS, PERIOD, OS_CODE, MANAGEMENT_NM, POS_DEEDNO, SIGNER, OWNER, SIGNER_ECONTRACT,
					name, gender, kecamatan, kelurahan, CITIZEN, NATIONALITY, PASSPORTNO, [ADDRESS], CITY,
					ID_CARD, PlaceOfBirth, DateOfBirth, PostCode, IDType, NoExpireDate, ValidityCertainPeriod,
					PostCode_NPWP, MobilePhone, Email
				) VALUES (
					:apless, :period, :os_code, :name, :pos, :signer, :owner, :signer_econtract,
					:detail_name, :gender, :kecamatan, :kelurahan, :citizen, :nationality, :passportno,
					:address, :city, :id_card, :place_of_birth, :date_of_birth, :post_code, :id_type,
					:no_expire_date, :certain_period, :post_code_npwp, :mobile_phone, :email
				)
			"""), {
				"apless": apless, "period": period, "os_code": os_code, "name": name, "pos": pos,
				"signer": "1" if p.get("signer") else "0", "owner": "1" if p.get("owner") else "0",
				"signer_econtract": "1" if p.get("signerEcontract") else "0",
				**dc,
			})

		for d in deeds:
			if not d.get("deedNo"):
				continue
			conn.execute(text("""
				INSERT INTO CAFORGSTRUCT_DETAIL (APLESS, PERIOD, OS_CODE, POS_DEEDNO, DATE_OF_DEED, NOTARY_NM, CERTIFICATE)
				VALUES (:apless, :period, 'CV03', :deed_no, :deed_date, :notary, :certificate)
			"""), {
				"apless": apless, "period": period, "deed_no": d["deedNo"],
				"deed_date": _parse_ddmmyyyy(d.get("deedDate")), "notary": d.get("notaryName", ""),
				"certificate": d.get("certificate", ""),
			})

		conn.execute(text(
			"DELETE FROM CAFDEV WHERE APPL_NO = :applno AND DEVIATION_CD IN ('2202')"
		), {"applno": applno})
		for d in deeds:
			if d.get("certificate") != "9":
				continue
			dev_cd = "2202"
			existing_dev = conn.execute(text(
				"SELECT 1 FROM CAFDEV WITH (NOLOCK) WHERE APPL_NO = :applno AND DEVIATION_CD = :dev_cd"
			), {"applno": applno, "dev_cd": dev_cd}).first()
			if existing_dev:
				continue
			desc_row = conn.execute(text(
				"SELECT DEVIATION_DESC, STANDARD_DESC FROM MSTDEVIATION WITH (NOLOCK) WHERE DEVIATION_CD = :dev_cd"
			), {"dev_cd": dev_cd}).mappings().first()
			if desc_row:
				conn.execute(text("""
					INSERT INTO CAFDEV (APPL_NO, DEVIATION_CD, REASON, DEVIATION_DESC, STANDARD_DESC, INPUT_DT)
					VALUES (:applno, :dev_cd, '', :desc, :standard, SYSDATETIME())
				"""), {"applno": applno, "dev_cd": dev_cd, "desc": desc_row["DEVIATION_DESC"], "standard": desc_row["STANDARD_DESC"]})

	return jsonify({"success": True, "apless": apless, "applno": applno})

def _fetch_lookups_koperasi(conn):
	pengurus_positions = conn.execute(text(
		"SELECT ID_OS_POSITION AS value, [DESC] AS label FROM MSTOS_POSITION WITH (NOLOCK) WHERE OS_CODE = 'CO01'"
	)).mappings().all()
	certificate_options = conn.execute(text(
		"SELECT ID_OS_CERTIFICATE AS value, CERT_CODE AS label FROM MSTOS_CERTIFICATE WITH (NOLOCK) WHERE CUST_TYPE = 'CO'"
	)).mappings().all()
	contract_signer_options = conn.execute(text(
		"SELECT ID_OS_SIGNER AS value, [DESC] AS label FROM MSTOS_SIGNER WITH (NOLOCK) WHERE CUST_TYPE = 'CO'"
	)).mappings().all()
	area_options = conn.execute(text(
		"SELECT AREA_CD AS value, Propinsi + ' - ' + Kabupaten AS label FROM UMFAREA WITH (NOLOCK) WHERE FLAG_DEL = 0 ORDER BY Propinsi, Kabupaten"
	)).mappings().all()
	nationality_options = conn.execute(text(
		"SELECT ID2digit AS value, Name AS label FROM Mst_Country WITH (NOLOCK) ORDER BY Name"
	)).mappings().all()
	return {
		"pengurusPositions": [dict(r) for r in pengurus_positions],
		"certificateOptions": [dict(r) for r in certificate_options],
		"contractSignerOptions": [dict(r) for r in contract_signer_options],
		"areaOptions": [dict(r) for r in area_options],
		"nationalityOptions": [dict(r) for r in nationality_options],
	}

def _fetch_name_options(conn, apless: str):
	rows = conn.execute(text("""
		SELECT Id AS value, Nama AS label
		FROM TEMP_CAFLESS_OCR
		WHERE Prechecking_Id = (SELECT Prechecking_Id FROM CAFLESS WHERE APLESS = :apless)
	"""), {"apless": apless}).mappings().all()
	return [dict(r) for r in rows]

def _load_management_details_koperasi(conn, apless: str, period: str):
	rows = conn.execute(text("""
		SELECT DISTINCT MANAGEMENT_NM, ID_CARD, [ADDRESS], CITY, name, gender, kecamatan, kelurahan,
		       cod.PASSPORTNO, CITIZEN, NATIONALITY, ua.Propinsi, ua.AREA_CD,
		       PlaceOfBirth, DateOfBirth, PostCode, IDType, NoExpireDate, ValidityCertainPeriod,
		       PostCode_NPWP, MobilePhone, Email
		FROM CAFORGSTRUCT_DETAIL cod WITH (NOLOCK)
		    LEFT JOIN UMFAREA ua WITH (NOLOCK) ON ua.KABUPATEN = CITY
		WHERE cod.APLESS = :apless AND PERIOD = :period AND OS_CODE IN ('CO01', 'CO02')
	"""), {"apless": apless, "period": period}).mappings().all()

	def fmt_date(v):
		return v.strftime("%d-%m-%Y") if isinstance(v, (date, datetime)) else ""

	result = {}
	for r in rows:
		name = r["MANAGEMENT_NM"]
		if not name:
			continue
		city_outside = r["CITY"] == "9999"
		result[name] = {
			"nameWithoutTitle": r["name"] or "",
			"gender": r["gender"] or "",
			"placeOfBirth": r["PlaceOfBirth"] or "",
			"dateOfBirth": fmt_date(r["DateOfBirth"]),
			"address": r["ADDRESS"] or "",
			"areaCd": "9999" if city_outside else (r["AREA_CD"] or ""),
			"province": "Di Luar Wilayah Indonesia" if city_outside else (r["Propinsi"] or ""),
			"city": "Di Luar Wilayah Indonesia" if city_outside else (r["CITY"] or ""),
			"kecamatan": r["kecamatan"] or "",
			"kelurahan": r["kelurahan"] or "",
			"postCode": r["PostCode"] or "",
			"citizen": r["CITIZEN"] or "",
			"nationality": r["NATIONALITY"] or "",
			"idCard": r["ID_CARD"] or "",
			"passportNo": r["PASSPORTNO"] or "",
			"idType": r["IDType"] or "",
			"noExpireDate": str(r["NoExpireDate"]) if r["NoExpireDate"] is not None else "",
			"certainPeriod": fmt_date(r["ValidityCertainPeriod"]),
			"mobilePhone": _normalize_phone(r["MobilePhone"]),
			"email": r["Email"] or "",
			"nameInNpwp": "", "establishPlace": "", "establishDate": "", "addressNpwp": "",
			"areaCdNpwp": "", "provinceNpwp": "", "cityNpwp": "", "kecamatanNpwp": "",
			"kelurahanNpwp": "", "npwp": "", "postCodeNpwp": r["PostCode_NPWP"] or "",
		}
	return result

def _load_period_data_koperasi(conn, apless: str, period: str):
	capital_row = conn.execute(text("""
		SELECT CONTRACT_SIGNER, OTHER_SIGNER, PIC
		FROM CAFORGSTRUCT WITH (NOLOCK) WHERE APLESS = :apless AND PERIOD = :period
	"""), {"apless": apless, "period": period}).mappings().first()

	def load_group(os_code, has_econtract=False):
		rows = conn.execute(text(f"""
			SELECT MANAGEMENT_NM AS name, POS_DEEDNO AS position, SIGNER AS signer, OWNER AS owner
			{", SIGNER_ECONTRACT AS signerEcontract" if has_econtract else ""}
			FROM CAFORGSTRUCT_DETAIL WITH (NOLOCK)
			WHERE APLESS = :apless AND PERIOD = :period AND OS_CODE = :os_code
			ORDER BY ID_DETAIL
		"""), {"apless": apless, "period": period, "os_code": os_code}).mappings().all()
		result = []
		for r in rows:
			row = {
				"name": r["name"] or "", "position": r["position"] or "",
				"owner": bool(r["owner"] == "1"), "signer": bool(r["signer"] == "1"),
			}
			if has_econtract:
				row["signerEcontract"] = bool(r["signerEcontract"] == "1")
			result.append(row)
		return result

	deeds_raw = conn.execute(text("""
		SELECT POS_DEEDNO AS deedNo, DATE_OF_DEED AS deedDate, NOTARY_NM AS notaryName, CERTIFICATE AS certificate
		FROM CAFORGSTRUCT_DETAIL WITH (NOLOCK)
		WHERE APLESS = :apless AND PERIOD = :period AND OS_CODE = 'CO03'
		ORDER BY ID_DETAIL
	"""), {"apless": apless, "period": period}).mappings().all()
	deeds = [{
		"deedNo": d["deedNo"] or "",
		"deedDate": d["deedDate"].strftime("%d-%m-%Y") if isinstance(d["deedDate"], (date, datetime)) else "",
		"notaryName": d["notaryName"] or "",
		"certificate": d["certificate"] or "",
	} for d in deeds_raw]

	return {
		"pengurus": load_group("CO01", has_econtract=True),
		"pengawas": load_group("CO02"),
		"deeds": deeds,
		"contractSignerSelected": (capital_row["CONTRACT_SIGNER"] if capital_row else "") or "",
		"contractSignerOther": (capital_row["OTHER_SIGNER"] if capital_row else "") or "",
		"picSameAsE": not bool(capital_row and capital_row["PIC"]),
		"picName": (capital_row["PIC"] if capital_row else "") or "",
		"managementDetails": _load_management_details_koperasi(conn, apless, period),
	}

@cam_edit_bp.route("/organization-structure-koperasi", methods=["GET"])
@login_required
def get_organization_structure_koperasi():
	apless = request.args.get("apless", "")
	applno = request.args.get("applno", "")
	period_override = request.args.get("period")

	with db.engine.connect() as conn:
		creation_ym = _creation_yyyymm(conn, apless, applno)
		period_options = _period_options(conn, apless, creation_ym)
		has_any = len(period_options) > 0

		period = period_override if period_override else (period_options[0] if period_options else "")
		period_data = _load_period_data_koperasi(conn, apless, period) if period else {
			"pengurus": [], "pengawas": [], "deeds": [],
			"contractSignerSelected": "", "contractSignerOther": "",
			"picSameAsE": True, "picName": "", "managementDetails": {},
		}
		lookups = _fetch_lookups_koperasi(conn)
		name_options = _fetch_name_options(conn, apless)

	return jsonify({
		"periodOptions": period_options,
		"period": period,
		"hasAnyExistingPeriod": has_any,
		"nameOptions": name_options,
		**lookups,
		**period_data,
	})

@cam_edit_bp.route("/organization-structure-koperasi/period-check", methods=["GET"])
@login_required
def check_organization_structure_period_koperasi():
	apless = request.args.get("apless", "")
	applno = request.args.get("applno", "")
	period = request.args.get("period", "")

	if len(period) != 6 or not period.isdigit():
		return jsonify({"code": None})

	with db.engine.connect() as conn:
		creation_ym = _creation_yyyymm(conn, apless, applno)

	tahun, bulan = int(creation_ym[:4]), int(creation_ym[4:6])
	year_new, month_new = int(period[:4]), int(period[4:6])

	code = None
	try:
		if tahun == year_new or year_new > tahun:
			if date(year_new, month_new, 1) > date(tahun, bulan, 1):
				code = "0"
		else:
			if date(tahun - 1, bulan, 1) > date(year_new, month_new, 1):
				code = "9"
	except ValueError:
		code = "0"

	return jsonify({"code": code})

@cam_edit_bp.route("/organization-structure-koperasi", methods=["POST"])
@login_required
def save_organization_structure_koperasi():
	payload = request.get_json(force=True)
	apless = payload.get("apless", "")
	applno = payload.get("applno", "")
	period = payload.get("period", "")
	is_new = payload.get("isNew", False)
	pengurus = payload.get("pengurus", [])
	pengawas = payload.get("pengawas", [])
	deeds = payload.get("deeds", [])
	contract_signer = payload.get("contractSigner", {})
	pic = payload.get("pic", {})
	management_details = payload.get("managementDetails", {})

	messages = []

	if len(period) != 6 or not period.isdigit():
		messages.append("Period not valid")

	for i, d in enumerate(deeds, start=1):
		if d.get("deedNo") and not d.get("deedDate"):
			messages.append(f"Date of Deed number {i} must not empty")

	pengurus_with_position = [p for p in pengurus if p.get("position")]
	e_signer_count = sum(1 for p in pengurus_with_position if p.get("signerEcontract"))
	if pengurus_with_position and e_signer_count == 0:
		messages.append("Signer On E-Contract wajib dipilih salah satu")
	if e_signer_count > 1:
		messages.append("Signer On E-Contract hanya boleh dipilih satu")

	if messages:
		return jsonify({"success": False, "messages": messages})

	def detail_columns(name):
		d = management_details.get(name)
		if not d:
			return {
				"detail_name": "", "gender": "", "kecamatan": "", "kelurahan": "", "citizen": "",
				"nationality": "", "passportno": "", "address": "", "city": "", "id_card": "",
				"place_of_birth": "", "date_of_birth": None, "post_code": "", "id_type": "",
				"no_expire_date": "", "certain_period": None, "post_code_npwp": "",
				"mobile_phone": "", "email": "",
			}
		outside = d.get("areaCd") == "9999"
		return {
			"detail_name": d.get("nameWithoutTitle", ""),
			"gender": d.get("gender", ""),
			"kecamatan": "999999" if outside else d.get("kecamatan", ""),
			"kelurahan": "9999999999" if outside else d.get("kelurahan", ""),
			"citizen": d.get("citizen", ""),
			"nationality": "ID" if d.get("citizen") == "WNI" else d.get("nationality", ""),
			"passportno": d.get("passportNo", "") if d.get("citizen") == "WNA" else "",
			"address": d.get("address", ""),
			"city": "9999" if outside else d.get("city", ""),
			"id_card": d.get("idCard", ""),
			"place_of_birth": d.get("placeOfBirth", "") or "",
			"date_of_birth": _parse_ddmmyyyy(d.get("dateOfBirth")),
			"post_code": d.get("postCode", ""),
			"id_type": d.get("idType", ""),
			"no_expire_date": d.get("noExpireDate", ""),
			"certain_period": _parse_ddmmyyyy(d.get("certainPeriod")),
			"post_code_npwp": d.get("postCodeNpwp", ""),
			"mobile_phone": d.get("mobilePhone", ""),
			"email": d.get("email", ""),
		}

	with db.engine.begin() as conn:
		if is_new:
			existing = conn.execute(text(
				"SELECT 1 FROM CAFORGSTRUCT WITH (NOLOCK) WHERE APLESS = :apless AND PERIOD = :period"
			), {"apless": apless, "period": period}).first()
			if existing:
				return jsonify({"success": False, "message": "Data already exists"})

			other_signer = contract_signer.get("other", "") if contract_signer.get("selected") == "14" else ""
			pic_value = "" if pic.get("sameAsE") else pic.get("name", "")
			conn.execute(text("""
				INSERT INTO CAFORGSTRUCT (APLESS, PERIOD, CONTRACT_SIGNER, OTHER_SIGNER, PIC)
				VALUES (:apless, :period, :signer, :other_signer, :pic)
			"""), {"apless": apless, "period": period, "signer": contract_signer.get("selected", ""),
				"other_signer": other_signer, "pic": pic_value})
		else:
			other_signer = contract_signer.get("other", "") if contract_signer.get("selected") == "14" else ""
			pic_value = "" if pic.get("sameAsE") else pic.get("name", "")
			conn.execute(text("""
				UPDATE CAFORGSTRUCT SET CONTRACT_SIGNER = :signer, OTHER_SIGNER = :other_signer, PIC = :pic
				WHERE APLESS = :apless AND PERIOD = :period
			"""), {"apless": apless, "period": period, "signer": contract_signer.get("selected", ""),
				"other_signer": other_signer, "pic": pic_value})
			conn.execute(text(
				"DELETE FROM CAFORGSTRUCT_DETAIL WHERE APLESS = :apless AND PERIOD = :period AND OS_CODE IN ('CO01', 'CO02', 'CO03')"
			), {"apless": apless, "period": period})

		def insert_member(os_code, name, position, owner, signer, signer_econtract=None):
			dc = detail_columns(name)
			cols = "APLESS, PERIOD, OS_CODE, MANAGEMENT_NM, POS_DEEDNO, SIGNER, OWNER"
			vals = ":apless, :period, :os_code, :name, :pos, :signer, :owner"
			params = {
				"apless": apless, "period": period, "os_code": os_code, "name": name, "pos": position,
				"signer": "1" if signer else "0", "owner": "1" if owner else "0", **dc,
			}
			if signer_econtract is not None:
				cols += ", SIGNER_ECONTRACT"
				vals += ", :signer_econtract"
				params["signer_econtract"] = "1" if signer_econtract else "0"
			cols += (", name, gender, kecamatan, kelurahan, CITIZEN, NATIONALITY, PASSPORTNO, [ADDRESS], CITY, "
				"ID_CARD, PlaceOfBirth, DateOfBirth, PostCode, IDType, NoExpireDate, ValidityCertainPeriod, "
				"PostCode_NPWP, MobilePhone, Email")
			vals += (", :detail_name, :gender, :kecamatan, :kelurahan, :citizen, :nationality, :passportno, "
				":address, :city, :id_card, :place_of_birth, :date_of_birth, :post_code, :id_type, "
				":no_expire_date, :certain_period, :post_code_npwp, :mobile_phone, :email")
			conn.execute(text(f"INSERT INTO CAFORGSTRUCT_DETAIL ({cols}) VALUES ({vals})"), params)

		for p in pengurus:
			if p.get("name"):
				insert_member("CO01", p["name"], p.get("position", ""), p.get("owner"), p.get("signer"), p.get("signerEcontract"))
		for p in pengawas:
			if p.get("name"):
				insert_member("CO02", p["name"], p.get("position", ""), p.get("owner"), p.get("signer"))

		for d in deeds:
			if not d.get("deedNo"):
				continue
			conn.execute(text("""
				INSERT INTO CAFORGSTRUCT_DETAIL (APLESS, PERIOD, OS_CODE, POS_DEEDNO, DATE_OF_DEED, NOTARY_NM, CERTIFICATE)
				VALUES (:apless, :period, 'CO03', :deed_no, :deed_date, :notary, :certificate)
			"""), {
				"apless": apless, "period": period, "deed_no": d["deedNo"],
				"deed_date": _parse_ddmmyyyy(d.get("deedDate")), "notary": d.get("notaryName", ""),
				"certificate": d.get("certificate", ""),
			})

		conn.execute(text(
			"DELETE FROM CAFDEV WHERE APPL_NO = :applno AND DEVIATION_CD IN ('2302', '2303', '2304')"
		), {"applno": applno})
		cert_to_dev = {"13": "2302", "14": "2303", "15": "2304"}
		for d in deeds:
			dev_cd = cert_to_dev.get(d.get("certificate", ""))
			if not dev_cd:
				continue
			existing_dev = conn.execute(text(
				"SELECT 1 FROM CAFDEV WITH (NOLOCK) WHERE APPL_NO = :applno AND DEVIATION_CD = :dev_cd"
			), {"applno": applno, "dev_cd": dev_cd}).first()
			if existing_dev:
				continue
			desc_row = conn.execute(text(
				"SELECT DEVIATION_DESC, STANDARD_DESC FROM MSTDEVIATION WITH (NOLOCK) WHERE DEVIATION_CD = :dev_cd"
			), {"dev_cd": dev_cd}).mappings().first()
			if desc_row:
				conn.execute(text("""
					INSERT INTO CAFDEV (APPL_NO, DEVIATION_CD, REASON, DEVIATION_DESC, STANDARD_DESC, INPUT_DT)
					VALUES (:applno, :dev_cd, '', :desc, :standard, SYSDATETIME())
				"""), {"applno": applno, "dev_cd": dev_cd, "desc": desc_row["DEVIATION_DESC"], "standard": desc_row["STANDARD_DESC"]})

	return jsonify({"success": True, "apless": apless, "applno": applno})

@cam_edit_bp.route("/customer-document/list", methods=["GET"])
@login_required
def get_customer_document_list():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")
    organization_type = request.args.get("organizationType", "")
    if not (apless and applno and organization_type):
        return jsonify({"success": False, "message": "apless, applno and organizationType must not empty"}), 400
    return jsonify({"success": True, "data": list_customer_documents(applno, apless, organization_type)})

@cam_edit_bp.route("/customer-document/lessee-category", methods=["GET"])
@login_required
def get_customer_document_lessee_category():
    
    apless = request.args.get("apless", "")
    if not apless:
        return jsonify({"success": False, "message": "apless must not empty"}), 400
    return jsonify({"success": True, "data": {"lessee_cat": get_lessee_cat(apless)}})

@cam_edit_bp.route("/customer-document/upload", methods=["POST"])
@login_required
def post_customer_document_upload():
    form = request.form
    apless = form.get("apless", "")
    applno = form.get("applno", "")
    organization_type = form.get("organizationType", "")
    document_type = form.get("documentType", "")
    prefix = form.get("prefix", "")
    subfolder = form.get("subfolder", "")
    grnid = form.get("grnid", "")
    max_file_size_mb = float(form.get("maxFileSizeMb") or 0)

    if not (apless and applno and organization_type and document_type):
        return jsonify({"success": False, "message": "apless, applno, organizationType and documentType must not empty"}), 400

    file_storage = request.files.get("file")
    error, doc = upload_customer_document(
        file_storage=file_storage,
        document_type=document_type,
        prefix=prefix,
        applno=applno,
        apless=apless,
        organization_type=organization_type,
        subfolder=subfolder,
        username=session.get("username", ""),
        grnid=grnid,
        max_file_size_mb=max_file_size_mb,
    )
    if error:
        return jsonify({"success": False, "message": error}), 400
    return jsonify({"success": True, "data": doc})

@cam_edit_bp.route("/customer-document/delete", methods=["POST"])
@login_required
def post_customer_document_delete():
    d = request.get_json(silent=True) or {}
    doc_id = d.get("id")
    if not doc_id:
        return jsonify({"success": False, "message": "id must not empty"}), 400

    deleted = delete_customer_document(int(doc_id))
    if not deleted:
        return jsonify({"success": False, "message": "Document not found"}), 404
    return jsonify({"success": True})

@cam_edit_bp.route("/customer-document/view/<int:doc_id>", methods=["GET"])
@login_required
def get_customer_document_view(doc_id: int):
    url = get_document_view_url(doc_id)
    if not url:
        return jsonify({"success": False, "message": "Document not found"}), 404
    return redirect(url)

@cam_edit_bp.route("/customer-document/download/<int:doc_id>", methods=["GET"])
@login_required
def get_customer_document_download(doc_id: int):
    url = get_document_view_url(doc_id)
    if not url:
        return jsonify({"success": False, "message": "Document not found"}), 404
    return redirect(url)

@cam_edit_bp.route("/cam-create/context", methods=["GET"])
@login_required
def get_cam_create_context():
    lessee_tp = request.args.get("lesseeTp", "")
    limit_check = get_portfolio_limit_check()
    return jsonify({
        "success": True,
        "data": {
            "indCor": "1" if lessee_tp == "PR" else "2",
            "purposeOfFinanceOptions": get_purpose_of_finance_options(),
            "limitCheck": {
                "totalMitsuiD": limit_check.total_mitsui_d,
                "totalMitsuiM": limit_check.total_mitsui_m,
                "limitBisa": limit_check.limit_bisa,
                "blocksFinTypeD": limit_check.ok_lanjut_d,
                "blocksFinTypeMOrW": limit_check.ok_lanjut_m,
            },
        },
    })

@cam_edit_bp.route("/cam-create/finance-types", methods=["GET"])
@login_required
def get_cam_create_finance_types():
    purpoffinc = request.args.get("purpoffinc", "")
    lessee_tp = request.args.get("lesseeTp", "")
    return jsonify({"success": True, "data": get_finance_type_options(purpoffinc, lessee_tp)})

@cam_edit_bp.route("/cam-create/dp-info", methods=["GET"])
@login_required
def get_cam_create_dp_info():
    return jsonify({"success": True, "data": get_dp_ratio_info()})

@cam_edit_bp.route("/cam-create/save", methods=["POST"])
@login_required
def post_cam_create_save():
    d = request.get_json(silent=True) or {}

    emp_id = session.get("emp_id", "")
    branch_cd = session.get("branchcode", "")

    try:
        result = create_new_cam(
            apless=d.get("apless", ""),
            prechecking_id=d.get("precheckingId", ""),
            lessee_tp=d.get("lesseeTp", ""),
            purpoffinc=d.get("purpoffinc", ""),
            fin_type=d.get("finType", ""),
            guarantor=d.get("guarantor", ""),
            new_car=d.get("newCar", ""),
            repeat=d.get("repeat", "1"),
            public=d.get("public", ""),
            boa=d.get("boa", ""),
            bot=d.get("bot", ""),
            emp_id=emp_id,
            branch_cd=branch_cd,
        )
    except CamCreationError as exc:
        return jsonify({"success": False, "message": exc.message, "errors": exc.field_errors}), 400

    return jsonify({"success": True, "data": result})

@cam_edit_bp.route("/guarantor", methods=["GET"])
@login_required
def get_guarantor_list():
	applno = request.args.get("applno", "")
	with db.engine.connect() as conn:
		rows = conn.execute(text("""
			SELECT GRNID, GRNNAME, GRNTP, GRNOCCUPATION, GRNRELATION, CON_SIGNPOS
			FROM CAFGUARN WITH (NOLOCK) WHERE APPL_NO = :applno ORDER BY GRNID DESC
		"""), {"applno": applno}).mappings().all()

	guarantors = []
	for r in rows:
		occupation = r["GRNOCCUPATION"] if r["GRNTP"] == "PR" else (r["CON_SIGNPOS"] if r["GRNTP"] == "PT" else "")
		guarantors.append({
			"grnId": r["GRNID"],
			"name": r["GRNNAME"] or "",
			"type": r["GRNTP"] or "",
			"occupation": occupation or "",
			"relation": r["GRNRELATION"] or "",
		})
	return jsonify({"guarantors": guarantors})

@cam_edit_bp.route("/guarantor", methods=["DELETE"])
@login_required
def delete_guarantor():
	grn_id = request.args.get("grnId", "")
	grn_tp = request.args.get("grnTp", "")
	applno = request.args.get("applno", "")

	with db.engine.begin() as conn:
		doc_rows = conn.execute(text("""
			SELECT AWSKey FROM CUSTOMER_DOCUMENT
			WHERE appl_no = :applno AND doc_type = 'guarn' AND GRNID = :grn_id
		"""), {"applno": applno, "grn_id": grn_id}).mappings().all()
		for d in doc_rows:
			delete_object(d["AWSKey"])

		conn.execute(text("DELETE FROM CAFGUARN WHERE GRNID = :grn_id AND GRNTP = :grn_tp"),
			{"grn_id": grn_id, "grn_tp": grn_tp})
		conn.execute(text("DELETE FROM CAFGUARNBANK WHERE GRNID = :grn_id"), {"grn_id": grn_id})
		conn.execute(text("DELETE FROM GUARANTOR_BANK_STATEMENT_DOCUMENT WHERE GuarantorId = :grn_id"), {"grn_id": grn_id})

		if grn_tp == "PR":
			conn.execute(text("DELETE FROM CAFSURV_PR WHERE appl_no = :applno"), {"applno": applno})
		elif grn_tp == "PT":
			conn.execute(text("DELETE FROM CAFSURV_PT WHERE appl_no = :applno"), {"applno": applno})

		conn.execute(text("""
			DELETE FROM CUSTOMER_DOCUMENT WHERE appl_no = :applno AND doc_type = 'guarn' AND GRNID = :grn_id
		"""), {"applno": applno, "grn_id": grn_id})

	return jsonify({"success": True})

def _disburse(conn, applno: str, lessee_no: str, cons_leas: str, create_date: date, apless: str):
	if cons_leas != "T":
		contracts = conn.execute(text("""
			SELECT EXECUTION, LEASE_NO FROM CLFCONT WITH (NOLOCK)
			WHERE EXECUTION IS NOT NULL AND UPD_STAT = 'Y' AND FLGDEL = '0'
			AND LESSEE_NO = :lessee_no AND Cons_Leas = :cons_leas
		"""), {"lessee_no": lessee_no, "cons_leas": cons_leas}).mappings().all()
	else:
		contracts = conn.execute(text("""
			SELECT EXECUTION, LEASE_NO FROM CLFCONT WITH (NOLOCK)
			WHERE EXECUTION IS NOT NULL AND UPD_STAT = 'Y' AND FLGDEL = '0'
			AND LESSEE_NO = :lessee_no AND Cons_Leas NOT IN ('C', 'L')
		"""), {"lessee_no": lessee_no}).mappings().all()

	tot_out = 0.0
	tot_unit = 0

	for c in contracts:
		lease_no = c["LEASE_NO"]

		crossno_row = conn.execute(text("""
			SELECT crossno FROM TACrossNo WITH (NOLOCK)
			WHERE appl_no IN (SELECT appl_no FROM CAFCONT WITH (NOLOCK) WHERE apless = :apless)
			AND crossno IS NOT NULL AND crossno <> '' AND crossno = :lease_no
		"""), {"apless": apless, "lease_no": lease_no}).mappings().first()
		if crossno_row:
			continue

		execution = c["EXECUTION"]
		if isinstance(execution, datetime):
			execution = execution.date()
		if not (isinstance(execution, date) and execution <= create_date):
			continue

		terminate_row = conn.execute(text("""
			SELECT TOP 1 a.[status], b.TENOR FROM BGiro a WITH (NOLOCK)
			INNER JOIN CLFCONT b WITH (NOLOCK) ON a.LEASE_NO = b.LEASE_NO
			WHERE a.LEASE_NO = :lease_no ORDER BY a.payment DESC, a.period DESC
		"""), {"lease_no": lease_no}).mappings().first()

		if terminate_row and terminate_row["status"] == "T":
			jlh_byr = terminate_row["TENOR"]
		else:
			cnt_row = conn.execute(text("""
				SELECT COUNT(a.payment) AS jlh_byr, b.ADV_ARR FROM BGiro a WITH (NOLOCK)
				INNER JOIN CLFCONT b WITH (NOLOCK) ON a.LEASE_NO = b.LEASE_NO
				WHERE a.LEASE_NO = :lease_no AND a.payment IS NOT NULL AND a.[status] NOT IN ('T', 'P')
				GROUP BY b.ADV_ARR
			"""), {"lease_no": lease_no}).mappings().first()
			jlh_byr = (cnt_row["jlh_byr"] if cnt_row else 0) or 0
			adv_arr = cnt_row["ADV_ARR"] if cnt_row else None
			if adv_arr == "V":
				jlh_byr += 1
			else:
				adv_arr_row = conn.execute(text(
					"SELECT ADV_ARR FROM CLFCONT WITH (NOLOCK) WHERE LEASE_NO = :lease_no"
				), {"lease_no": lease_no}).mappings().first()
				if adv_arr_row and adv_arr_row["ADV_ARR"] == "V":
					jlh_byr += 1

		has_payment = conn.execute(text(
			"SELECT 1 FROM CLFPAY WITH (NOLOCK) WHERE LEASE_NO = :lease_no AND DATE_PAY <> ''"
		), {"lease_no": lease_no}).first() is not None

		if has_payment:
			out_row = conn.execute(text(
				"SELECT OUTS_PRINC FROM CLFPAY WITH (NOLOCK) WHERE LEASE_NO = :lease_no AND period = :period"
			), {"lease_no": lease_no, "period": jlh_byr}).mappings().first()
			out = float(out_row["OUTS_PRINC"]) if out_row and out_row["OUTS_PRINC"] is not None else 0.0

			partial_row = conn.execute(text("""
				SELECT TOP 1 [status], nominal FROM BGiro WITH (NOLOCK)
				WHERE LEASE_NO = :lease_no AND payment IS NOT NULL ORDER BY payment DESC
			"""), {"lease_no": lease_no}).mappings().first()
			if partial_row and partial_row["status"] == "p":
				out += float(partial_row["nominal"] or 0)
		else:
			ntf_row = conn.execute(text("""
				SELECT b.Net_Finance AS ntf FROM CLFCONT a WITH (NOLOCK)
				INNER JOIN V_NetFinance b WITH (NOLOCK) ON a.LEASE_NO = b.LEASE_NO
				WHERE a.LEASE_NO = :lease_no
			"""), {"lease_no": lease_no}).mappings().first()
			out = float(ntf_row["ntf"]) if ntf_row and ntf_row["ntf"] is not None else 0.0

		tot_out += out
		tot_unit += 1

		marketprice_row = conn.execute(text(
			"EXEC USP_CALC_MARKETPRICE :empty, :lease_no"
		), {"empty": "", "lease_no": lease_no}).mappings().first()
		marketprice = marketprice_row["marketprice"] if marketprice_row else None

		conn.execute(text("""
			INSERT INTO CAFLR (APPL_NO, LEASE_NO, TERM, MARKETPRICE, OUTSTANDING, TYPE)
			VALUES (:applno, :lease_no, :term, :marketprice, :outstanding, '1')
		"""), {"applno": applno, "lease_no": lease_no, "term": jlh_byr, "marketprice": marketprice, "outstanding": out})

	return tot_out, tot_unit

@cam_edit_bp.route("/guarantor/exposure", methods=["GET"])
@login_required
def get_guarantor_exposure():

	lessee_no = request.args.get("lesseeNo", "")
	applno = request.args.get("applno", "")
	apless = request.args.get("apless", "")

	with db.engine.connect() as conn:
		create_date_row = conn.execute(text(
			"SELECT CREATE_DATE FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :applno"
		), {"applno": applno}).mappings().first()
		create_date = create_date_row["CREATE_DATE"] if create_date_row else None
		if isinstance(create_date, datetime):
			create_date = create_date.date()
		if not isinstance(create_date, date):
			create_date = datetime.now().date()

		cf_out, cf_unit = _disburse(conn, applno, lessee_no, "C", create_date, apless)
		fl_out, fl_unit = _disburse(conn, applno, lessee_no, "L", create_date, apless)

	return jsonify({
		"totalExposure": cf_out + fl_out,
		"cashFinanceExposure": cf_out,
		"cashFinanceUnits": cf_unit,
		"leasingExposure": fl_out,
		"leasingUnits": fl_unit,
	})

GUARANTOR_LOOKBACK_DAYS = 60
GUARANTOR_ACTIVE_DAYS = 30

def _json_safe(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return None
    if hasattr(value, "quantize"):
        return float(value)
    return value

_GUARANTOR_CANDIDATE_SELECT = """
    SELECT
        mg.GRNID, mg.GRNNAME, mg.GRNTP,
        tcl.FINAL_APLESS, tcl.Prechecking_Id,
        CASE WHEN tcl.CustomerType = 'PR' THEN ISNULL(tcl.IdCardNo, '') ELSE ISNULL(tcl.NPWP, '') END AS ID_CARD,
        CASE WHEN DATEDIFF(d, da.LastActionDate, GETDATE()) <= :active_days THEN 'active' ELSE 'inactive' END AS status,
        da.CreatedBy, da.LastActionDate
    FROM Mst_Guarantor mg WITH (NOLOCK)
        INNER JOIN TEMP_CAFLESS tcl WITH (NOLOCK) ON mg.Prechecking_Id = tcl.Prechecking_Id
        INNER JOIN DocumentApproval da WITH (NOLOCK) ON da.DocumentNumber = mg.Prechecking_Id
    WHERE da.LastActionDate >= DATEADD(day, -:lookback, CAST(GETDATE() AS date))
      AND da.LastActionDate < DATEADD(day, 1, CAST(GETDATE() AS date))
"""

def _guarantor_candidate_row(r) -> dict:
    return {
        "grnId": r["GRNID"],
        "name": r["GRNNAME"] or "",
        "type": r["GRNTP"] or "",
        "idCard": r["ID_CARD"] or "",
        "status": r["status"],
        "cmo": r["CreatedBy"] or "",
        "lastActionDate": _json_safe(r["LastActionDate"]),
        "finalApless": r["FINAL_APLESS"] or "",
        "precheckingId": r["Prechecking_Id"],
    }

@cam_edit_bp.route("/guarantor/candidates", methods=["GET"])
@login_required
def get_guarantor_candidates():
    search_by = request.args.get("search_by", "")
    search_val = (request.args.get("search_val", "") or "").strip()

    sql = _GUARANTOR_CANDIDATE_SELECT
    params = {"active_days": GUARANTOR_ACTIVE_DAYS, "lookback": GUARANTOR_LOOKBACK_DAYS}
    if search_val and search_by == "1":
        sql += " AND mg.GRNID = :val"
        params["val"] = search_val
    elif search_val and search_by == "2":
        sql += " AND mg.GRNNAME LIKE :val"
        params["val"] = f"%{search_val}%"
    sql += " ORDER BY da.LastActionDate DESC, mg.GRNID DESC"

    rows = db.session.execute(text(sql), params).mappings().all()
    return jsonify({"guarantors": [_guarantor_candidate_row(r) for r in rows]})

_SQL_IDENT_RE = re.compile(r"^[A-Za-z0-9_]+$")

def _table_columns(table: str) -> dict:
    rows = db.session.execute(text("""
        SELECT c.COLUMN_NAME AS name,
               COLUMNPROPERTY(OBJECT_ID(:tbl), c.COLUMN_NAME, 'IsIdentity') AS is_identity,
               COLUMNPROPERTY(OBJECT_ID(:tbl), c.COLUMN_NAME, 'IsComputed') AS is_computed,
               c.DATA_TYPE AS data_type,
               c.IS_NULLABLE AS is_nullable,
               c.COLUMN_DEFAULT AS col_default
        FROM INFORMATION_SCHEMA.COLUMNS c
        WHERE c.TABLE_NAME = :tbl
    """), {"tbl": table}).mappings().all()
    return {r["name"].upper(): r for r in rows}

def _copy_guarantor_documents(prechecking_id: str, applno: str, final_apless: str) -> list:
    warnings = []
    try:
        db.session.execute(text("EXEC USP_Copy_Document :pid, :applno"), {"pid": prechecking_id, "applno": applno})
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("USP_Copy_Document failed (pid=%s applno=%s)", prechecking_id, applno)
        warnings.append("Document records could not be copied (USP_Copy_Document failed).")
        return warnings

    try:
        docs = db.session.execute(text("""
            SELECT DISTINCT cd.Apless, cd.Prechecking_Id, cd.DocumentName, cd.AWSKey
            FROM TEMP_CUSTOMER_DOCUMENT cd WITH (NOLOCK)
            INNER JOIN TEMP_CAFLESS cl WITH (NOLOCK) ON cl.Apless = cd.Apless AND cd.Prechecking_Id = cl.Prechecking_Id
            WHERE cd.Prechecking_Id = :pid
        """), {"pid": prechecking_id}).mappings().all()
    except Exception:
        current_app.logger.exception("Reading TEMP_CUSTOMER_DOCUMENT failed (pid=%s)", prechecking_id)
        return ["Prechecking documents could not be read."]

    failed = 0
    for d in docs:
        old_key = d["AWSKey"]
        if not old_key:
            continue
        try:
            new_name = (d["DocumentName"] or "").replace(d["Prechecking_Id"], applno).replace(d["Apless"], final_apless)
            m = re.search(r"DATA_GUARANTOR/([^/]+)/", old_key)
            folder = m.group(1) if m else ""
            new_key = f"upload_doc/{final_apless}/{applno}/DATA_GUARANTOR/{folder}/{new_name}"
            _s3_client().copy_object(
                Bucket=_s3_bucket(), Key=new_key, CopySource={"Bucket": _s3_bucket(), "Key": old_key},
            )
        except Exception:
            failed += 1
            current_app.logger.exception("Copy of guarantor document failed: %s", old_key)
    if failed:
        warnings.append(f"{failed} document file(s) could not be copied.")
    return warnings

@cam_edit_bp.route("/guarantor/select", methods=["POST"])
@login_required
def select_guarantor():
    body = request.get_json(silent=True) or {}
    applno = (body.get("applno") or "").strip()
    prechecking_id = (body.get("prechecking_id") or "").strip()
    if not applno or not prechecking_id:
        return jsonify({"success": False, "message": "applno and prechecking_id are required"}), 400

    try:
        cam = db.session.execute(
            text("SELECT APLESS FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :applno"),
            {"applno": applno},
        ).mappings().first()
        if not cam:
            return jsonify({"success": False, "message": "CAM not found"}), 404

        blocked, message = _check_cam_editable(applno)
        if blocked:
            return jsonify({"success": False, "message": message}), 403

        row = db.session.execute(
            text(_GUARANTOR_CANDIDATE_SELECT + " AND mg.Prechecking_Id = :pid"),
            {"active_days": GUARANTOR_ACTIVE_DAYS, "lookback": GUARANTOR_LOOKBACK_DAYS, "pid": prechecking_id},
        ).mappings().first()
        if not row:
            return jsonify({"success": False, "message": "Guarantor not found in the last 1000 days"}), 404
        if row["status"] != "active":
            return jsonify({"success": False, "message": "Guarantor prechecking is inactive. Use Repeat Order."}), 400

        dup = db.session.execute(text("""
            SELECT TOP 1 1 AS x FROM CAFGUARN WITH (NOLOCK)
            WHERE APPL_NO = :applno AND GRNNAME = :name AND GRNTP = :tp
        """), {"applno": applno, "name": row["GRNNAME"], "tp": row["GRNTP"]}).first()
        if dup:
            return jsonify({"success": False, "message": "This guarantor is already added to this CAM"}), 409

        target = _table_columns("CAFGUARN")
        source = _table_columns("Mst_Guarantor")
        if "APPL_NO" not in target:
            return jsonify({"success": False, "message": "CAFGUARN has no APPL_NO column"}), 500
        cols = [
            t["name"] for key, t in target.items()
            if key in source and key != "APPL_NO"
            and not t["is_identity"] and not t["is_computed"] and t["data_type"] != "timestamp"
            and _SQL_IDENT_RE.match(t["name"])
        ]
        missing_required = [
            t["name"] for key, t in target.items()
            if key not in source and key not in ("APPL_NO", "APLESS")
            and t.get("is_nullable") == "NO" and t.get("col_default") is None
            and not t["is_identity"] and not t["is_computed"] and t["data_type"] != "timestamp"
        ]
        if missing_required:
            return jsonify({"success": False,
                            "message": "CAFGUARN requires columns not present in Mst_Guarantor: " + ", ".join(missing_required)}), 500
        if not cols:
            return jsonify({"success": False, "message": "No matching columns between Mst_Guarantor and CAFGUARN"}), 500

        col_sql = ", ".join(f"[{c}]" for c in cols)
        ins_cols, sel_cols = "APPL_NO", ":applno"
        params = {"applno": applno, "pid": prechecking_id}
        if "APLESS" in target:
            ins_cols += ", APLESS"; sel_cols += ", :apless"
            params["apless"] = cam["APLESS"]
            cols = [c for c in cols if c.upper() != "APLESS"]
            col_sql = ", ".join(f"[{c}]" for c in cols)
        db.session.execute(text(f"""
            INSERT INTO CAFGUARN ({ins_cols}, {col_sql})
            SELECT {sel_cols}, {col_sql} FROM Mst_Guarantor WHERE Prechecking_Id = :pid
        """), params)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("select_guarantor failed")
        detail = str(getattr(e, "orig", None) or e)[:500]
        return jsonify({"success": False, "message": "Failed to add the guarantor to this CAM",
                        "detail": detail}), 500

    warnings = _copy_guarantor_documents(prechecking_id, applno, cam["APLESS"] or "")
    return jsonify({"success": True, "applno": applno, "apless": cam["APLESS"] or "",
                    "candidate": _guarantor_candidate_row(row), "warnings": warnings})
    
def _g_phone_display(phone) -> str:
    if not phone:
        return ""
    p = re.sub(r"[^0-9xX]", "", str(phone))
    m = re.match(r"^([0-9]+)([xX]*)$", p)
    number, mask = (m.group(1), m.group(2)) if m else ("", "")
    if number.startswith("62"):
        number = number[2:]
    if number.startswith("0"):
        number = number[1:]
    return number + mask

def _g_phone_db(phone):
    if not phone:
        return None
    p = re.sub(r"[^0-9xX]", "", str(phone))
    if not p:
        return None
    if p.startswith("62"):
        return p
    if p.startswith("0"):
        p = p[1:]
    return "62" + p

def _g_iso(value) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]

def _g_parse_date(value):
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Invalid date: {value}")

def _g_clean(value, limit=None) -> str:
    s = (value if value is not None else "")
    s = str(s).strip()
    return s[:limit] if limit else s

def _g_own(applno: str, grn_id: str):
    return db.session.execute(text("""
        SELECT GRNID, GRNTP, GRNCITIZEN, APLESS FROM CAFGUARN WITH (NOLOCK)
        WHERE APPL_NO = :applno AND GRNID = :grn_id
    """), {"applno": applno, "grn_id": grn_id}).mappings().first()

_GUARANTOR_INFO_SELECT = """
    SELECT LESSEE_NO, GRNCAT, GRNTP, GRNNAME, GRNDOB, GRNADD, GRNCITY, GRNPHONE, GRNRELATION, GRNOCCUPATION,
           GRNTTL, GRNIDCARD, GRNIDVAL, GRNZIPCODE, GRNFAX, GRNLOB, GRNContact, CON_SIGNPOS, GRNSpouse, GRNStatus,
           GRNSPOUSEADD, GRNSPOUSECITY, GRNSPOUSECODE, GRNNAME_WITHOUT_TITLE, GRNNPWP, GRNCITIZEN, GRNNATIONALITY,
           GRNPASSPORTNO, GRN_BITYPE, GRNNAME_NPWP, GRNCITY_NPWP, GRNZIPCODE_NPWP, GRNADD_NPWP, Gender, Marital,
           GRNSPOUSEIDCARD, GRNEMAIL, GRNSpouseMobilePhone, GRNSpouseEmail, GRNConSignerMobilePhone,
           GRNConSignerEmail, GRNSpouseCitizenship, GRNSpouseNationality, APLESS
    FROM CAFGUARN WITH (NOLOCK)
    WHERE GRNID = :grn_id AND APPL_NO = :applno
"""

def _g_info_row(r) -> dict:
    return {
        "lesseeNo": r["LESSEE_NO"] or "",
        "grnCat": r["GRNCAT"] or "",
        "grnTp": r["GRNTP"] or "",
        "grnName": r["GRNNAME"] or "",
        "grnNameNpwp": r["GRNNAME_NPWP"] or "",
        "grnNameId": r["GRNNAME_WITHOUT_TITLE"] or "",
        "grnDob": _g_iso(r["GRNDOB"]),
        "grnAdd": r["GRNADD"] or "",
        "grnCity": r["GRNCITY"] or "",
        "grnZipcode": r["GRNZIPCODE"] or "",
        "grnFax": r["GRNFAX"] or "",
        "grnPhone": _g_phone_display(r["GRNPHONE"]),
        "grnRelation": r["GRNRELATION"] or "",
        "grnOccupation": r["GRNOCCUPATION"] or "",
        "grnTtl": float(r["GRNTTL"] or 0),
        "grnIdCard": r["GRNIDCARD"] or "",
        "grnIdVal": _g_iso(r["GRNIDVAL"]),
        "grnLob": r["GRNLOB"] or "",
        "grnContact": r["GRNContact"] or "",
        "conSignPos": r["CON_SIGNPOS"] or "",
        "grnSpouse": r["GRNSpouse"] or "",
        "spouseSts": r["GRNStatus"] or "",
        "grnSpouseAdd": r["GRNSPOUSEADD"] or "",
        "grnSpouseCity": r["GRNSPOUSECITY"] or "",
        "grnSpouseCode": r["GRNSPOUSECODE"] or "",
        "npwp": r["GRNNPWP"] or "",
        "citizen": r["GRNCITIZEN"] or "",
        "nationality": r["GRNNATIONALITY"] or "",
        "passportNo": r["GRNPASSPORTNO"] or "",
        "custType": r["GRN_BITYPE"] or "",
        "addrNpwp": r["GRNADD_NPWP"] or "",
        "cityNpwp": r["GRNCITY_NPWP"] or "",
        "postNpwp": r["GRNZIPCODE_NPWP"] or "",
        "gender": r["Gender"] or "",
        "marital": r["Marital"] or "",
        "idCardSpouse": r["GRNSPOUSEIDCARD"] or "",
        "grnEmail": r["GRNEMAIL"] or "",
        "spouseMobilePhone": _g_phone_display(r["GRNSpouseMobilePhone"]),
        "spouseEmail": r["GRNSpouseEmail"] or "",
        "conSignerMobilePhone": _g_phone_display(r["GRNConSignerMobilePhone"]),
        "conSignerEmail": r["GRNConSignerEmail"] or "",
        "spouseCitizenship": r["GRNSpouseCitizenship"] or "",
        "spouseNationality": r["GRNSpouseNationality"] or "",
    }

def _g_options(grn_id: str) -> dict:
    def q(sql, params=None):
        return db.session.execute(text(sql), params or {}).mappings().all()

    signers = q("""
        SELECT Nama, NIK, Citizen FROM TEMP_CAFLESS_OCR WITH (NOLOCK)
        WHERE Prechecking_Id = (SELECT TOP 1 Prechecking_Id FROM Mst_Guarantor WITH (NOLOCK) WHERE GRNID = :g)
    """, {"g": grn_id})
    return {
        "categories": [{"value": r["Code"], "label": r["Name"]} for r in q("SELECT Code, Name FROM MSTCATEGORY WITH (NOLOCK)")],
        "maritals": [{"value": r["Marital"], "label": r["name"]} for r in q("SELECT Marital, name FROM MSTMARITAL")],
        "genders": [{"value": r["VALUE"], "label": r["DESC_VALUE"]} for r in
                    q("SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH (NOLOCK) WHERE CAT_VALUE = 'Gender'")],
        "biTypes": [{"value": r["OJK_Code"], "label": r["MLCI_Desc"]} for r in
                    q("SELECT OJK_Code, MLCI_Desc FROM UMFBITYP_LBPP WITH (NOLOCK) WHERE OJK_Code IS NOT NULL ORDER BY MLCI_Desc")],
        "countries": [{"value": r["ID2digit"], "label": r["Name"]} for r in q("SELECT ID2digit, Name FROM Mst_Country")],
        "signers": [{"name": r["Nama"] or "", "idCard": r["NIK"] or "", "citizen": r["Citizen"] or ""} for r in signers],
    }

@cam_edit_bp.route("/guarantor/info", methods=["GET"])
@login_required
def get_guarantor_info():
    applno = request.args.get("applno", "").strip()
    grn_id = request.args.get("grnId", "").strip()
    if not applno or not grn_id:
        return jsonify({"success": False, "message": "applno and grnId are required"}), 400

    row = db.session.execute(text(_GUARANTOR_INFO_SELECT), {"grn_id": grn_id, "applno": applno}).mappings().first()
    if not row:
        return jsonify({"success": False, "message": "Guarantor not found in this CAM"}), 404

    blocked, message = _check_cam_editable(applno)
    return jsonify({
        "success": True,
        "blocked": bool(blocked),
        "blockedMessage": message if blocked else "",
        "guarantor": _g_info_row(row),
        "options": _g_options(grn_id),
    })

@cam_edit_bp.route("/guarantor/info", methods=["PUT"])
@login_required
def update_guarantor_info():
    b = request.get_json(silent=True) or {}
    applno = _g_clean(b.get("applno"))
    grn_id = _g_clean(b.get("grnId"))
    if not applno or not grn_id:
        return jsonify({"success": False, "message": "applno and grnId are required"}), 400

    try:
        own = _g_own(applno, grn_id)
        if not own:
            return jsonify({"success": False, "message": "Guarantor not found in this CAM"}), 404

        blocked, message = _check_cam_editable(applno)
        if blocked:
            return jsonify({"success": False, "message": message}), 403

        grn_tp = own["GRNTP"]
        errors = []

        try:
            dob = _g_parse_date(b.get("grnDob"))
        except ValueError:
            return jsonify({"success": False, "message": "Date is not valid"}), 400

        zipcode = _g_clean(b.get("grnZipcode"), 5)
        if zipcode and len(zipcode) != 5:
            errors.append("Post Code not valid")
        if grn_tp == "PR" and dob and (date.today().year - dob.year) <= 17:
            errors.append("Age Not Qualified to Guarantor")

        for field, label in (("grnCat", "Guarantor Category"), ("grnName", "Guarantor Name"),
                             ("grnNameId", "Guarantor Name Without Title"), ("grnAdd", "Address"), ("grnCity", "City"),
                             ("custType", "BI Customer Type"), ("grnPhone", "Mobile Phone No.")):
            if not _g_clean(b.get(field)):
                errors.append(f"{label} is required")
        if not dob:
            errors.append("Date is required")

        citizen = _g_clean(b.get("citizen"), 3)
        nationality = "ID" if citizen == "WNI" else _g_clean(b.get("nationality"), 2)
        if grn_tp == "PR" and citizen == "WNA" and not (nationality and _g_clean(b.get("passportNo"))):
            errors.append("Nationality and Passport No. are required for WNA")

        if errors:
            return jsonify({"success": False, "message": "<br>".join(dict.fromkeys(errors))}), 400

        ttl = _g_clean(b.get("grnTtl") or "0").replace(",", "")
        try:
            ttl_val = float(ttl or 0)
        except ValueError:
            return jsonify({"success": False, "message": "Total Exposure is not valid"}), 400

        params = {
            "applno": applno, "grn_id": grn_id, "grn_tp": grn_tp,
            "cat": _g_clean(b.get("grnCat"), 10), "name": _g_clean(b.get("grnName"), 100), "dob": dob,
            "add": _g_clean(b.get("grnAdd"), 250), "city": _g_clean(b.get("grnCity"), 30),
            "phone": _g_phone_db(b.get("grnPhone")), "relation": _g_clean(b.get("grnRelation"), 100),
            "ttl": ttl_val, "zip": zipcode, "fax": _g_clean(b.get("grnFax"), 20),
            "name_id": _g_clean(b.get("grnNameId"), 100), "cust_type": _g_clean(b.get("custType"), 20),
            "citizen": citizen, "nationality": nationality,
            "idcard": _g_clean(b.get("grnIdCard"), 30),
        }

        if grn_tp == "PR":
            id_val = None
            if _g_clean(b.get("validity")) == "0":
                try:
                    id_val = _g_parse_date(b.get("grnIdVal"))
                except ValueError:
                    return jsonify({"success": False, "message": "Validity ID Card date is not valid"}), 400
            sp_cit = _g_clean(b.get("spouseCitizenship"), 3)
            params.update({
                "occupation": _g_clean(b.get("grnOccupation"), 100), "idval": id_val,
                "spouse": _g_clean(b.get("grnSpouse"), 50), "spouse_sts": _g_clean(b.get("spouseSts"), 100),
                "spouse_add": _g_clean(b.get("grnSpouseAdd"), 250), "spouse_city": _g_clean(b.get("grnSpouseCity"), 50),
                "spouse_code": _g_clean(b.get("grnSpouseCode"), 5), "gender": _g_clean(b.get("gender"), 5),
                "marital": _g_clean(b.get("marital"), 5), "spouse_idcard": _g_clean(b.get("idCardSpouse"), 100),
                "email": _g_clean(b.get("grnEmail"), 100),
                "spouse_mobile": _g_phone_db(b.get("spouseMobilePhone")),
                "spouse_email": _g_clean(b.get("spouseEmail"), 100),
                "spouse_cit": sp_cit,
                "spouse_nat": "ID" if sp_cit == "WNI" else _g_clean(b.get("spouseNationality"), 2),
                "passport": _g_clean(b.get("passportNo"), 30) if citizen != "WNI" else "",
            })
            sql = """
                UPDATE CAFGUARN SET GRNCAT=:cat, GRNNAME=:name, GRNDOB=:dob, GRNADD=:add, GRNCITY=:city,
                    GRNPHONE=:phone, GRNRELATION=:relation, GRNOCCUPATION=:occupation, GRNTTL=:ttl,
                    GRNIDCARD=:idcard, GRNIDVAL=:idval, GRNZIPCODE=:zip, GRNFAX=:fax,
                    GRNSpouse=:spouse, GRNStatus=:spouse_sts, GRNSPOUSEADD=:spouse_add, GRNSPOUSECITY=:spouse_city,
                    GRNSPOUSECODE=:spouse_code, GRNNAME_WITHOUT_TITLE=:name_id, GRNCITIZEN=:citizen,
                    GRNNATIONALITY=:nationality, GRNPASSPORTNO=:passport, GRN_BITYPE=:cust_type, Gender=:gender,
                    Marital=:marital, GRNSPOUSEIDCARD=:spouse_idcard, GRNEMAIL=:email,
                    GRNSpouseMobilePhone=:spouse_mobile, GRNSpouseEmail=:spouse_email,
                    GRNSpouseCitizenship=:spouse_cit, GRNSpouseNationality=:spouse_nat
                WHERE GRNID=:grn_id AND GRNTP=:grn_tp AND APPL_NO=:applno
            """
        else:
            npwp = re.sub(r"\D", "", _g_clean(b.get("npwp")))[:16]
            params.update({
                "name_npwp": _g_clean(b.get("grnNameNpwp"), 100), "npwp": npwp,
                "addr_npwp": _g_clean(b.get("addrNpwp"), 250), "city_npwp": _g_clean(b.get("cityNpwp"), 50),
                "post_npwp": _g_clean(b.get("postNpwp"), 5), "lob": _g_clean(b.get("grnLob"), 100),
                "contact": _g_clean(b.get("grnContact"), 100), "signpos": _g_clean(b.get("conSignPos"), 100),
                "signer_mobile": _g_phone_db(b.get("conSignerMobilePhone")),
                "signer_email": _g_clean(b.get("conSignerEmail"), 100),
            })
            sql = """
                UPDATE CAFGUARN SET GRNCAT=:cat, GRNNAME=:name, GRNNAME_NPWP=:name_npwp, GRNDOB=:dob, GRNADD=:add,
                    GRNCITY=:city, GRNPHONE=:phone, GRNRELATION=:relation, GRNTTL=:ttl, GRNIDCARD=:idcard,
                    GRNZIPCODE=:zip, GRNFAX=:fax, GRNLOB=:lob, GRNContact=:contact, CON_SIGNPOS=:signpos,
                    GRNNAME_WITHOUT_TITLE=:name_id, GRNNPWP=:npwp, GRNCITIZEN=:citizen, GRNNATIONALITY=:nationality,
                    GRN_BITYPE=:cust_type, GRNADD_NPWP=:addr_npwp, GRNCITY_NPWP=:city_npwp,
                    GRNZIPCODE_NPWP=:post_npwp, GRNConSignerMobilePhone=:signer_mobile,
                    GRNConSignerEmail=:signer_email
                WHERE GRNID=:grn_id AND GRNTP=:grn_tp AND APPL_NO=:applno
            """
        db.session.execute(text(sql), params)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("update_guarantor_info failed")
        return jsonify({"success": False, "message": "Failed to save guarantor information",
                        "detail": str(getattr(e, "orig", None) or e)[:500]}), 500

    return jsonify({"success": True})

_BANK_TABLE = "GUARANTOR_BANK_STATEMENT_DOCUMENT"
_BANK_SUBFOLDER = "DATA_GUARANTOR/BANK_STATEMENT"
_BANK_TAG = "GUARANTOR_BANK_STATEMENT"

def _bank_cols() -> dict:
    cols = {k: v["name"] for k, v in _table_columns(_BANK_TABLE).items()}
    applno_col = cols.get("APPL_NO") or cols.get("APPLNO")
    return {"all": cols, "applno": applno_col}

def _bank_list(applno: str, grn_id: str) -> list:
    c = _bank_cols()
    if not c["applno"]:
        return []
    created = c["all"].get("CREATEDDATE")
    rows = db.session.execute(text(f"""
        SELECT Id, DocumentName, AWSKey FROM {_BANK_TABLE} WITH (NOLOCK)
        WHERE [{c['applno']}] = :applno AND GuarantorId = :grn_id
        ORDER BY {('[' + created + '] DESC') if created else 'Id DESC'}
    """), {"applno": applno, "grn_id": grn_id}).mappings().all()
    return [{"id": r["Id"], "documentName": r["DocumentName"] or "",
             "downloadUrl": _generate_download_url(r["AWSKey"], r["DocumentName"]) or ""}
            for r in rows if r["DocumentName"] and r["DocumentName"] != "-"]

@cam_edit_bp.route("/guarantor/bank", methods=["GET"])
@login_required
def get_guarantor_bank():
    applno = request.args.get("applno", "").strip()
    grn_id = request.args.get("grnId", "").strip()
    if not applno or not grn_id:
        return jsonify({"success": False, "message": "applno and grnId are required"}), 400
    if not _g_own(applno, grn_id):
        return jsonify({"success": False, "message": "Guarantor not found in this CAM"}), 404
    blocked, message = _check_cam_editable(applno)
    return jsonify({"success": True, "blocked": bool(blocked), "blockedMessage": message if blocked else "",
                    "files": _bank_list(applno, grn_id)})

@cam_edit_bp.route("/guarantor/bank/upload", methods=["POST"])
@login_required
def upload_guarantor_bank():
    applno = (request.form.get("applno") or "").strip()
    grn_id = (request.form.get("grnId") or "").strip()
    if not applno or not grn_id:
        return jsonify({"success": False, "message": "applno and grnId are required"}), 400

    own = _g_own(applno, grn_id)
    if not own:
        return jsonify({"success": False, "message": "Guarantor not found in this CAM"}), 404
    blocked, message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"success": False, "message": message}), 403

    files = [f for f in request.files.getlist("files") if f and f.filename]
    if not files:
        return jsonify({"success": False, "message": "No file selected."}), 400

    apless = own["APLESS"] or ""
    username = session.get("username", "") or session.get("emp_id", "") or ""
    c = _bank_cols()
    if not c["applno"]:
        return jsonify({"success": False, "message": f"{_BANK_TABLE} has no ApplNo column"}), 500

    uploaded_keys = []
    try:
        stamp = int(time.time())
        for i, f in enumerate(files):
            error = _validate_cam_file(f.mimetype, _file_size(f))
            if error:
                raise ValueError(f"{f.filename}: {error}")
            name = _build_document_name(applno, _BANK_TAG, stamp + i, f.filename)
            key = _build_s3_key(apless, applno, _BANK_SUBFOLDER, name)
            ctype = f.mimetype or "application/octet-stream"
            _s3_client().upload_fileobj(f, _s3_bucket(), key, ExtraArgs={"ContentType": ctype})
            uploaded_keys.append(key)

            cols = {c["applno"]: applno, "GuarantorId": grn_id, "DocumentName": name, "AWSKey": key}
            all_cols = c["all"]
            if "APLESS" in all_cols:
                cols[all_cols["APLESS"]] = apless
            if "CREATEDBY" in all_cols:
                cols[all_cols["CREATEDBY"]] = username
            names = list(cols)
            db.session.execute(text(
                f"INSERT INTO {_BANK_TABLE} ({', '.join('[' + n + ']' for n in names)}"
                f"{', [' + all_cols['CREATEDDATE'] + ']' if 'CREATEDDATE' in all_cols else ''}) "
                f"VALUES ({', '.join(':p' + str(j) for j in range(len(names)))}"
                f"{', GETDATE()' if 'CREATEDDATE' in all_cols else ''})"
            ), {f"p{j}": cols[n] for j, n in enumerate(names)})
        db.session.commit()
    except ValueError as e:
        db.session.rollback()
        for k in uploaded_keys:
            try: delete_object(k)
            except Exception: pass
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        for k in uploaded_keys:
            try: delete_object(k)
            except Exception: pass
        current_app.logger.exception("upload_guarantor_bank failed")
        return jsonify({"success": False, "message": "Upload failed. Please try again.",
                        "detail": str(getattr(e, "orig", None) or e)[:500]}), 500

    return jsonify({"success": True, "files": _bank_list(applno, grn_id)})

@cam_edit_bp.route("/guarantor/bank", methods=["DELETE"])
@login_required
def delete_guarantor_bank():
    applno = request.args.get("applno", "").strip()
    grn_id = request.args.get("grnId", "").strip()
    doc_id = request.args.get("id", "").strip()
    if not applno or not grn_id or not doc_id.isdigit():
        return jsonify({"success": False, "message": "applno, grnId and id are required"}), 400
    blocked, message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"success": False, "message": message}), 403

    try:
        row = db.session.execute(text(f"""
            SELECT AWSKey FROM {_BANK_TABLE} WITH (NOLOCK) WHERE Id = :id AND GuarantorId = :grn_id
        """), {"id": int(doc_id), "grn_id": grn_id}).mappings().first()
        if not row:
            return jsonify({"success": False, "message": "File not found"}), 404
        if row["AWSKey"]:
            delete_object(row["AWSKey"])
        db.session.execute(text(f"DELETE FROM {_BANK_TABLE} WHERE Id = :id AND GuarantorId = :grn_id"),
                           {"id": int(doc_id), "grn_id": grn_id})
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("delete_guarantor_bank failed")
        return jsonify({"success": False, "message": "Delete failed. Please try again."}), 500
    return jsonify({"success": True})


_GUARANTOR_DOC_PR = {
    "guarantor-spouse-kk": ("GUARANTOR_SPOUSE_KK", "DATA_DIRI/SPOUSE_KK"),
    "guarantor-ktp": ("GUARANTOR_KTP", "DATA_DIRI/KTP"),
    "guarantor-kitas": ("GUARANTOR_KITAS", "DATA_DIRI/KITAS"),
    "guarantor-spouse-ktp": ("GUARANTOR_SPOUSE_KTP", "DATA_DIRI/SPOUSE_KTP"),
    "guarantor-kk": ("GUARANTOR_KK", "DATA_DIRI/KK"),
    "guarantor-npwp": ("GUARANTOR_NPWP", "DATA_DIRI/NPWP"),
    "guarantor-marriage-or-death-statement": ("GUARANTOR_MARRIAGE_OR_DEATH_STATEMENT", "DATA_DIRI/MARRIAGE_OR_DEATH_STATEMENT"),
}
_GUARANTOR_DOC_PT = {
    "corp-guarantor-kk": ("CORP_GUARANTOR_KK", "DATA_DIRI/KK_PENGURUS"),
    "corp-guarantor-akta": ("CORP_GUARANTOR_AKTA", "DATA_DIRI/AKTA_PENGURUS"),
    "corp-guarantor-sk-akta": ("CORP_GUARANTOR_SK_AKTA", "DATA_DIRI/SK_AKTA_PENGURUS"),
    "corp-guarantor-akta-terakhir": ("CORP_GUARANTOR_AKTA_TERAKHIR", "DATA_DIRI/AKTA_TERAKHIR_PENGURUS"),
    "corp-guarantor-sk-akta-terakhir": ("CORP_GUARANTOR_SK_AKTA_TERAKHIR", "DATA_DIRI/SK_AKTA_TERAKHIR_PENGURUS"),
    "corp-guarantor-npwp": ("CORP_GUARANTOR_NPWP", "DATA_DIRI/NPWP_PENGURUS"),
}
_GUARANTOR_BOARD_PREFIXES = ("corp-guarantor-ocr-ktp_", "wna-corp-guarantor-board_")
_GUARANTOR_BOARD_EXACT = ("corp-ktp-akta-terakhir",)
_GUARANTOR_BOARD_TOKEN = re.compile(r"^[A-Za-z0-9_.\-]{1,100}$")

def _guarantor_doc_meta(grn_tp: str, document_type: str):
    table = _GUARANTOR_DOC_PR if grn_tp == "PR" else _GUARANTOR_DOC_PT if grn_tp == "PT" else {}
    if document_type in table:
        return table[document_type]
    if grn_tp == "PT":
        if document_type in _GUARANTOR_BOARD_EXACT:
            return ("CORP_KTP_AKTA_TERAKHIR", "DATA_GUARANTOR/KTP_PENGURUS")
        for p in _GUARANTOR_BOARD_PREFIXES:
            if document_type.startswith(p) and _GUARANTOR_BOARD_TOKEN.match(document_type):
                return ("CORP_GUARANTOR_BOARD", "DATA_GUARANTOR/KTP_PENGURUS")
    return None

def _guarantor_docs(applno: str, grn_id: str) -> dict:
    rows = db.session.execute(text("""
        SELECT id_customer_document, AWSKey, file_document, DocumentType
        FROM CUSTOMER_DOCUMENT WITH (NOLOCK)
        WHERE doc_type = 'guarn' AND APPL_NO = :applno AND GRNID = :grn_id AND APLESS IS NOT NULL
        ORDER BY DocumentType, Upload_Dt DESC
    """), {"applno": applno, "grn_id": grn_id}).mappings().all()
    out: dict = {}
    for r in rows:
        if not r["file_document"] or r["file_document"] == "-":
            continue
        out.setdefault(r["DocumentType"], []).append({
            "id": r["id_customer_document"],
            "documentName": r["file_document"],
            "downloadUrl": _generate_download_url(r["AWSKey"], r["file_document"]) or "",
        })
    return out

@cam_edit_bp.route("/guarantor/document", methods=["GET"])
@login_required
def get_guarantor_document():
    applno = request.args.get("applno", "").strip()
    grn_id = request.args.get("grnId", "").strip()
    if not applno or not grn_id:
        return jsonify({"success": False, "message": "applno and grnId are required"}), 400
    own = _g_own(applno, grn_id)
    if not own:
        return jsonify({"success": False, "message": "Guarantor not found in this CAM"}), 404
    blocked, message = _check_cam_editable(applno)
    return jsonify({
        "success": True, "blocked": bool(blocked), "blockedMessage": message if blocked else "",
        "guarantorType": own["GRNTP"] or "", "citizen": own["GRNCITIZEN"] or "",
        "files": _guarantor_docs(applno, grn_id),
    })

@cam_edit_bp.route("/guarantor/document/upload", methods=["POST"])
@login_required
def upload_guarantor_document():
    applno = (request.form.get("applno") or "").strip()
    grn_id = (request.form.get("grnId") or "").strip()
    document_type = (request.form.get("documentType") or "").strip()
    if not applno or not grn_id or not document_type:
        return jsonify({"success": False, "message": "applno, grnId and documentType are required"}), 400

    own = _g_own(applno, grn_id)
    if not own:
        return jsonify({"success": False, "message": "Guarantor not found in this CAM"}), 404
    meta = _guarantor_doc_meta(own["GRNTP"], document_type)
    if not meta:
        return jsonify({"success": False, "message": "Invalid document type."}), 400
    blocked, message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"success": False, "message": message}), 403

    files = [f for f in request.files.getlist("files") if f and f.filename]
    if not files:
        return jsonify({"success": False, "message": "No file selected."}), 400

    tag, subfolder = meta
    apless = own["APLESS"] or ""
    org_type = "GUARN" + (own["GRNTP"] or "")
    uploaded_keys = []
    try:
        stamp = int(time.time())
        for i, f in enumerate(files):
            error = _validate_cam_file(f.mimetype, _file_size(f))
            if error:
                raise ValueError(f"{f.filename}: {error}")
            name = _build_document_name(applno, tag, stamp + i, f.filename)
            key = _build_s3_key(apless, applno, subfolder, name)
            ctype = f.mimetype or "application/octet-stream"
            _s3_client().upload_fileobj(f, _s3_bucket(), key, ExtraArgs={"ContentType": ctype})
            uploaded_keys.append(key)
            db.session.execute(text("""
                INSERT INTO CUSTOMER_DOCUMENT
                    (appl_no, APLESS, DocumentType, doc_type, organization_type, file_document, AWSKey, Upload_Dt, GRNID)
                VALUES (:applno, :apless, :dt, 'guarn', :org, :name, :key, GETDATE(), :grn_id)
            """), {"applno": applno, "apless": apless, "dt": document_type, "org": org_type,
                   "name": name, "key": key, "grn_id": grn_id})
        db.session.commit()
    except ValueError as e:
        db.session.rollback()
        for k in uploaded_keys:
            try: delete_object(k)
            except Exception: pass
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        for k in uploaded_keys:
            try: delete_object(k)
            except Exception: pass
        current_app.logger.exception("upload_guarantor_document failed")
        return jsonify({"success": False, "message": "Upload failed. Please try again.",
                        "detail": str(getattr(e, "orig", None) or e)[:500]}), 500

    return jsonify({"success": True, "files": _guarantor_docs(applno, grn_id).get(document_type, [])})

@cam_edit_bp.route("/guarantor/document", methods=["DELETE"])
@login_required
def delete_guarantor_document():
    applno = request.args.get("applno", "").strip()
    grn_id = request.args.get("grnId", "").strip()
    doc_id = request.args.get("id", "").strip()
    if not applno or not grn_id or not doc_id.isdigit():
        return jsonify({"success": False, "message": "applno, grnId and id are required"}), 400
    blocked, message = _check_cam_editable(applno)
    if blocked:
        return jsonify({"success": False, "message": message}), 403

    try:
        row = db.session.execute(text("""
            SELECT AWSKey FROM CUSTOMER_DOCUMENT WITH (NOLOCK)
            WHERE id_customer_document = :id AND appl_no = :applno AND GRNID = :grn_id AND doc_type = 'guarn'
        """), {"id": int(doc_id), "applno": applno, "grn_id": grn_id}).mappings().first()
        if not row:
            return jsonify({"success": False, "message": "File not found"}), 404
        if row["AWSKey"]:
            delete_object(row["AWSKey"])
        db.session.execute(text("""
            DELETE FROM CUSTOMER_DOCUMENT
            WHERE id_customer_document = :id AND appl_no = :applno AND GRNID = :grn_id AND doc_type = 'guarn'
        """), {"id": int(doc_id), "applno": applno, "grn_id": grn_id})
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("delete_guarantor_document failed")
        return jsonify({"success": False, "message": "Delete failed. Please try again."}), 500
    return jsonify({"success": True})