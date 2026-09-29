import requests

from flask import Blueprint, request, jsonify, current_app, session
from sqlalchemy import text
from app import db
from app.auth.decorators import login_required
from app.utils.helpers.irr import hitung_irr

from app.utils.helpers.approver_helpers import (
    current_approval_level,
    get_next_available_approver,
    approver_option_from_raw,
)

cam_send_cmo_bp = Blueprint('cam_send_cmo', __name__, url_prefix='/CAM/SendCmo')

def _split_appl_nos(raw):
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return [x.strip() for x in str(raw or '').split(',') if x.strip()]

def _in_params(appl_nos, prefix="a"):
    keys = [f"{prefix}{i}" for i in range(len(appl_nos))]
    clause = ", ".join(f":{k}" for k in keys)
    params = {k: v for k, v in zip(keys, appl_nos)}
    return clause, params

def _check_privy() -> bool:
    row = db.session.execute(text(
        "SELECT [VALUE] FROM MSTCOMBO WHERE CAT_VALUE = 'PRIVY'"
    )).mappings().first()
    return bool(row and row.get("VALUE") == '1')

def _check_econtract_period(appl_no) -> bool:
    row = db.session.execute(text(
        "SELECT TOP 1 ContractSign FROM MstContractSign ORDER BY ChangeFrom DESC"
    )).mappings().first()
    return bool(row and row.get("ContractSign") == 'E')

def register_privy(appl_no):
    if not _check_privy():
        return ""
    if not _check_econtract_period(appl_no):
        return ""
    try:
        response = requests.post(
            "http://10.31.1.139:9002/RegisterPRIVY",
            data={"appl_no": appl_no},
            timeout=30,
        )
        return response.text.strip("\"' \r\n\t")
    except requests.RequestException:
        current_app.logger.exception("register_privy call failed (appl_no=%s)", appl_no)
        return ""

def _watchlist_message(apless, lessee):
    less_tp = lessee.get("LESSEE_TP")
    address = lessee.get("ADDRESS1") if less_tp == "PR" else lessee.get("ADDRESS2")

    wl = None
    if address:
        wl = db.session.execute(text("""
            SELECT TOP 1 NAME, Reason FROM MCMOWATCHLIST WITH (NOLOCK)
            WHERE Address LIKE :addr AND FlagDel = '0' AND Flag_Type = 'W'
        """), {"addr": f"%{address}%"}).mappings().first()

    if not wl and lessee.get("LESSEE_NM") and lessee.get("ADDRESS1"):
        wl = db.session.execute(text("""
            SELECT TOP 1 NAME, Reason FROM MCMOWATCHLIST WITH (NOLOCK)
            WHERE Name LIKE :nm AND Address LIKE :addr AND FlagDel = '0' AND Flag_Type = 'W'
        """), {"nm": f"%{lessee['LESSEE_NM']}%", "addr": lessee["ADDRESS1"]}).mappings().first()

    if not wl and less_tp == "PR" and lessee.get("ID_CARD"):
        wl = db.session.execute(text("""
            SELECT TOP 1 NAME, Reason FROM MCMOWATCHLIST WITH (NOLOCK)
            WHERE ID_card LIKE :idc AND FlagDel = '0' AND Flag_Type = 'W'
        """), {"idc": f"%{lessee['ID_CARD']}%"}).mappings().first()

    if wl:
        return f"This Customer has been listed on watchlist — {wl['Reason']}"
    return None

def _check_simple_split(appl_no, split_name):
    exists = db.session.execute(text("""
        SELECT 1 FROM CAFDISB WITH (NOLOCK) WHERE APPL_NO = :a AND split = :s
    """), {"a": appl_no, "s": split_name}).first()
    if not exists:
        return True

    row = db.session.execute(text("""
        SELECT L_AMOUNT, FIRST_INST, DP, Prov, surveyfeegross_cigna
        FROM CAFDISB WITH (NOLOCK) WHERE APPL_NO = :a AND split = :s
    """), {"a": appl_no, "s": split_name}).mappings().first() or {}

    netfin = (float(row.get("L_AMOUNT") or 0) - float(row.get("DP") or 0)
              - float(row.get("FIRST_INST") or 0) - float(row.get("Prov") or 0)
              - float(row.get("surveyfeegross_cigna") or 0))

    total = db.session.execute(text("""
        SELECT SUM(AMOUNT) AS total FROM CAFDISBACC WITH (NOLOCK)
        WHERE APPL_NO = :a AND split = :s
    """), {"a": appl_no, "s": split_name}).mappings().first()
    total_amt = float((total or {}).get("total") or 0)

    return abs(netfin - total_amt) < 0.01

def _check_dealer_split(appl_no):
    exists = db.session.execute(text("""
        SELECT 1 FROM CAFDISB WITH (NOLOCK) WHERE APPL_NO = :a AND split = 'Dealer'
    """), {"a": appl_no}).first()
    if not exists:
        return True

    disb = db.session.execute(text("""
        SELECT L_AMOUNT, FIRST_INST, DP, Prov, surveyfeegross_cigna, Notary_Fee
        FROM CAFDISB WITH (NOLOCK) WHERE APPL_NO = :a AND split = 'Dealer'
    """), {"a": appl_no}).mappings().first() or {}

    cont = db.session.execute(text("""
        SELECT Gross, AdmFee, BusinessTrip_Fee, Subsidy_Supp, Refund_Supp
        FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :a
    """), {"a": appl_no}).mappings().first() or {}

    notary_fee = disb.get("Notary_Fee")
    if notary_fee in (None, ''):
        notary_fee = cont.get("Gross") or 0

    creditamt_row = db.session.execute(text("""
        SELECT DISB_INSC FROM CAFDISB WITH (NOLOCK) WHERE APPL_NO = :a AND Split = 'Dealer'
    """), {"a": appl_no}).mappings().first()
    creditamt = float((creditamt_row or {}).get("DISB_INSC") or 0)

    bbn = db.session.execute(text("""
        SELECT bbnvia, paidby, BBN_FEE, ServiceAgencyFee AS OCCUPATION
        FROM BBN WITH (NOLOCK) WHERE appl_no = :a
    """), {"a": appl_no}).mappings().first() or {}
    birjat, bbnt = 0.0, 0.0
    if bbn.get("paidby") == "Deduct from disbursement":
        birjat = float(bbn.get("OCCUPATION") or 0)
        bbnt = float(bbn.get("BBN_FEE") or 0)

    netfindel = (
        float(disb.get("L_AMOUNT") or 0) - float(disb.get("DP") or 0) - float(disb.get("FIRST_INST") or 0)
        - float(disb.get("Prov") or 0) - float(notary_fee or 0) - float(cont.get("AdmFee") or 0)
        - float(cont.get("BusinessTrip_Fee") or 0) - creditamt - float(cont.get("Subsidy_Supp") or 0)
        + float(cont.get("Refund_Supp") or 0) - birjat - bbnt - float(disb.get("surveyfeegross_cigna") or 0)
    )

    acc_total = db.session.execute(text("""
        SELECT SUM(AMOUNT) AS total FROM CAFDISBACC WITH (NOLOCK)
        WHERE APPL_NO = :a AND split IN ('Dealer', 'Customer')
    """), {"a": appl_no}).mappings().first()
    cross_total = db.session.execute(text("""
        SELECT SUM(AMOUNT) AS total FROM TACROSSNO WITH (NOLOCK)
        WHERE APPL_NO = :a AND CROSS_TYPE = 'CD'
    """), {"a": appl_no}).mappings().first()

    total = float((acc_total or {}).get("total") or 0) + float((cross_total or {}).get("total") or 0)
    return abs(netfindel - total) < 0.01

def _validate_appl_no(appl_no, red_code, gps_vendor):
    
    equip = db.session.execute(text("""
        SELECT BPKB_AN_TP FROM CAFEQUIP WITH (NOLOCK) WHERE APPL_NO = :a
    """), {"a": appl_no}).mappings().first() or {}
    if not (equip.get("BPKB_AN_TP") or "").strip():
        return "BPKB Name Type is empty"

    spouse = db.session.execute(text("""
        SELECT cc.MARITAL, cd.SPOUSE_MobilePhone, cd.SPOUSE_Email
        FROM CAFCONT c WITH (NOLOCK)
            INNER JOIN CAFLESS cc WITH (NOLOCK) ON cc.APLESS = c.APLESS
            LEFT JOIN CAFLESS_DETAIL cd WITH (NOLOCK) ON cd.APLESS = cc.APLESS
        WHERE c.APPL_NO = :a
    """), {"a": appl_no}).mappings().first() or {}
    if spouse.get("MARITAL") == "M":
        if not (spouse.get("SPOUSE_MobilePhone") or "").strip():
            return "Spouse Mobile Phone No. must not be empty"
        if not (spouse.get("SPOUSE_Email") or "").strip():
            return "Spouse Email must not be empty"

    email_row = db.session.execute(text("""
        SELECT EMAIL1 FROM CAFLESS WITH (NOLOCK)
        WHERE APLESS = (SELECT APLESS FROM CAFCONT WHERE APPL_NO = :a)
    """), {"a": appl_no}).mappings().first() or {}
    if not (email_row.get("EMAIL1") or "").strip():
        return "Email 1 must not be empty"

    signers = db.session.execute(text("""
        SELECT Phone, Email FROM V_ContractSigner WHERE appl_no = :a
    """), {"a": appl_no}).mappings().all()
    for signer in signers:
        if not (signer.get("Phone") or "").strip():
            return "Mobile Phone No. must not be empty"
        if not (signer.get("Email") or "").strip():
            return "Email must not be empty"

    cont = db.session.execute(text("""
        SELECT Cons_Leas, cont_type, Notary_no, ISNULL(Notary, 0) AS Notary,
               ISNULL(Fiduciary, 0) AS Fiduciary, ISNULL(Gross, 0) AS Gross
        FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :a
    """), {"a": appl_no}).mappings().first() or {}
    if not (cont.get("cont_type") or "").strip():
        return "Contract Type is empty please check"

    if cont.get("Cons_Leas") != 'F':
        if (cont.get("Notary_no") or "").strip():
            if float(cont.get("Gross") or 0) <= 0:
                return "Gross Amount must more than 0 please check"
        else:
            return "please next Notary in Equipment BPKB"

    has_outs = db.session.execute(text("""
        SELECT 1 FROM CAFCUST_OUTS WITH (NOLOCK) WHERE APPL_NO = :a
    """), {"a": appl_no}).first()
    if not has_outs:
        return "Calculate Total Outstanding first!"

    if not _check_dealer_split(appl_no):
        return "Total bank amount isn`t same with the disbursement to dealer amount"
    for split_name in ("Accessories", "Karoseri", "Others"):
        if not _check_simple_split(appl_no, split_name):
            return "Total bank amount isn`t same with the disbursement to dealer amount"

    msgs = []

    dev = db.session.execute(text("""
        SELECT down_payment, base_rate FROM deviation_dp WHERE appl_no = :a
    """), {"a": appl_no}).mappings().first() or {}
    down_payment = dev.get("down_payment")
    bebasbase = dev.get("base_rate")

    investasi = multiguna = tgl_acuan = npf = None
    if down_payment == '1':
        dp_row = db.session.execute(
            text("EXEC USP_CHECK_DEVIASI_DP :a"), {"a": appl_no}
        ).mappings().first() or {}
        investasi, multiguna = dp_row.get("I"), dp_row.get("M")
        tgl_acuan, npf = dp_row.get("tgl_acuan"), dp_row.get("npf")

    if investasi in (None, '') or multiguna in (None, ''):
        dp_row = db.session.execute(
            text("EXEC USP_CHECK_DP :a"), {"a": appl_no}
        ).mappings().first() or {}
        investasi, multiguna = dp_row.get("I"), dp_row.get("M")
        tgl_acuan, npf = dp_row.get("tgl_acuan"), dp_row.get("npf")

    notif = f"NPF as of {tgl_acuan} is {npf}%, then Min. DP which allowed is "

    cont2 = db.session.execute(text("""
        SELECT purpoffinc, cons_leas, ROUND((security / NULLIF(l_amount, 0)) * 100, 0) AS security_persen, BaseAdmFee
        FROM cafcont WHERE appl_no = :a
    """), {"a": appl_no}).mappings().first() or {}
    purpoffinc = cont2.get("purpoffinc")
    fin_type = cont2.get("cons_leas")
    security_persen = float(cont2.get("security_persen") or 0)
    basesurv = float(cont2.get("BaseAdmFee") or 0)

    if not down_payment and purpoffinc == "4" and security_persen < 10:
        msgs.append(notif + "10%")
    if purpoffinc == "3" and investasi not in (None, '') and security_persen < float(investasi):
        msgs.append(notif + f"{investasi}%")
    if purpoffinc == "5" and multiguna not in (None, '') and security_persen < float(multiguna):
        msgs.append(notif + f"{multiguna}%")
    if bebasbase != '1' and fin_type != 'W' and basesurv < 1_500_000:
        msgs.append("Minimum Survey Fee is 1,500,000")

    ins_loan_row = db.session.execute(text("""
        SELECT CREDITAMT FROM CAFINSU WITH (NOLOCK) WHERE APPL_NO = :a
    """), {"a": appl_no}).mappings().first() or {}
    ins_loan = float(ins_loan_row.get("CREDITAMT") or 0)

    gross_row = db.session.execute(text("""
        SELECT GROSS_PREM, SUM(DISB_INSC) AS DISB_INSC
        FROM CAFDISB WITH (NOLOCK) WHERE APPL_NO = :a GROUP BY GROSS_PREM, NET_COM
    """), {"a": appl_no}).mappings().first() or {}
    gross_prem = float(gross_row.get("GROSS_PREM") or 0)
    disb_insc = gross_row.get("DISB_INSC")
    disb_insc = float(disb_insc) if disb_insc not in (None, '') else (gross_prem - ins_loan)

    if ins_loan + disb_insc > gross_prem:
        msgs.append("Insurance loan + insurance disbursement cannot more than gross insurance premium")

    bpkb = db.session.execute(text("""
        SELECT BPKB_AN, model FROM cafequip WITH (NOLOCK) WHERE APPL_NO = :a
    """), {"a": appl_no}).mappings().first() or {}
    fin_row = db.session.execute(text("""
        SELECT cons_leas, SECURITY, L_AMOUNT, Notary_no FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :a
    """), {"a": appl_no}).mappings().first() or {}
    fin_type2 = fin_row.get("cons_leas")
    l_amount2 = float(fin_row.get("L_AMOUNT") or 0)
    security_persen2 = round((float(fin_row.get("SECURITY") or 0) * 100) / l_amount2, 2) if l_amount2 else 0
    notary_no = fin_row.get("Notary_no")

    if not (notary_no or "").strip() and (bpkb.get("BPKB_AN") or "") and fin_type2 == "S":
        passenger_model = db.session.execute(text("""
            SELECT model FROM umfmodel WITH (NOLOCK)
            WHERE model IN ('03','02','01','21') AND model = :m
        """), {"m": bpkb.get("model")}).mappings().first()
        if passenger_model and security_persen2 < 40:
            msgs.append("The DP is less than 40% and the vehicle type is passenger. Fiducia is a must.")
        elif not passenger_model:
            msgs.append("The vehicle type is Commercial. Fiducia is a must.")

    lesse = db.session.execute(text("""
        SELECT a.LESSEE_TP, a.NPWP FROM cafless a WITH (NOLOCK)
        INNER JOIN cafcont b WITH (NOLOCK) ON a.APLESS = b.APLESS WHERE b.APPL_NO = :a
    """), {"a": appl_no}).mappings().first() or {}
    if fin_type2 == "S" and lesse.get("LESSEE_TP") == "PT" and not (lesse.get("NPWP") or "").strip():
        msgs.append("You must fill the NPWP first")

    if red_code and not gps_vendor:
        msgs.append("Please select GPS Vendor")

    if msgs:
        return "; ".join(msgs)

    return None

@cam_send_cmo_bp.route('/prepare', methods=['POST'])
@login_required
def prepare_send():
    body = request.get_json(force=True) or {}
    appl_nos = _split_appl_nos(body.get("appl_nos"))
    multiple = bool(body.get("multiple"))

    if not appl_nos:
        return jsonify({"success": False, "message": "Check it first please"})

    if multiple:
        clause, params = _in_params(appl_nos)
        rows = db.session.execute(text(f"""
            SELECT DISTINCT LTRIM(RTRIM(b.APLESS)) AS APLESS, LTRIM(RTRIM(a.SUPP)) AS DEALER,
                   LTRIM(RTRIM(a.PARK_LOC)) AS PARKING_LOCATION,
                   b.ADV_ARR, b.APLESS, b.TENOR, c.ins_cd, LTRIM(RTRIM(zz.acc_no)) AS acc_no,
                   LTRIM(RTRIM(zz.acc_nm)) AS acc_nm, LTRIM(RTRIM(zz.BANK)) AS BANK
            FROM CAFEQUIP a WITH (NOLOCK)
                INNER JOIN CAFCONT b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
                INNER JOIN CAFINSU c WITH (NOLOCK) ON b.APPL_NO = c.APPL_NO
                INNER JOIN cafdisbacc zz ON zz.APPL_NO = a.appl_no
            WHERE b.APPL_NO IN ({clause}) AND zz.SPLIT = 'Dealer'
        """), params).mappings().all()

        if len(rows) != 1:
            return jsonify({
                "success": False,
                "message": ("Multiple CAM requires Customer, Dealer, First Installment Payment, "
                             "Parking Location, Tenor, Contract Type, Insurance Company, "
                             "Dealer Bank Account must be the same"),
            })

    return jsonify({"success": True, "appl_nos": appl_nos})

@cam_send_cmo_bp.route('/init', methods=['GET'])
@login_required
def get_send_cmo_init():
    appl_nos = _split_appl_nos(request.args.get('appl_nos', ''))
    multiple = request.args.get('multiple', '0') == '1'
    username = session.get('username', '')
    branch_cd = session.get('branchcode', '')

    if not appl_nos:
        return jsonify({"error": "No CAM selected."}), 400

    try:
        items = []
        watchlist_message = None
        purpose_condition = None
        purpose_value = None
        show_purpose_edit = False
        purpose_notice = None
        lessee_type = None

        for appl_no in appl_nos:
            cont = db.session.execute(text("""
                SELECT APLESS, Cons_Leas FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :a
            """), {"a": appl_no}).mappings().first()
            if not cont:
                continue
            apless = cont["APLESS"]

            lessee = db.session.execute(text("""
                SELECT LESSEE_NM, ADDRESS1, ADDRESS2, ID_CARD, LESSEE_TP, BUSINESS_SIZE
                FROM CAFLESS WITH (NOLOCK) WHERE APLESS = :apless
            """), {"apless": apless}).mappings().first() or {}
            less_tp = lessee.get("LESSEE_TP")
            lessee_type = less_tp

            if not lessee.get("BUSINESS_SIZE"):
                return jsonify({
                    "success": False,
                    "blocking": True,
                    "message": "Please select Business Size first!",
                })

            wl_msg = _watchlist_message(apless, lessee)
            if wl_msg:
                watchlist_message = wl_msg

            purpo_row = db.session.execute(text("""
                SELECT PURPOFFINC FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :a
            """), {"a": appl_no}).mappings().first() or {}
            purpose_condition = purpo_row.get("PURPOFFINC")
            purpose_value = purpose_condition

            if less_tp == "PT":
                cc = db.session.execute(text("""
                    SELECT PURPOFFINC, Cons_Leas FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :a
                """), {"a": appl_no}).mappings().first() or {}
                purpof = cc.get("PURPOFFINC")
                cons_leas = cc.get("Cons_Leas")
                business_size = lessee.get("BUSINESS_SIZE")
                if purpof == '5' and cons_leas == 'I' and business_size != 4:
                    db.session.execute(text("""
                        UPDATE CAFCONT SET PURPOFFINC = '3' WHERE APPL_NO = :a
                    """), {"a": appl_no})
                    purpof = '3'
                    purpose_notice = "Purpose of Finance has been adjusted to Investment per SLIK rules"
                    show_purpose_edit = True
                purpose_value = purpof

            row = db.session.execute(text("""
                SELECT b.LESSEE_NM, c.USERNAME
                FROM CAFCONT a WITH (NOLOCK)
                LEFT JOIN CAFLESS b WITH (NOLOCK) ON a.APLESS = b.APLESS
                LEFT JOIN APP_USRMST c WITH (NOLOCK) ON a.CMO = c.EMPLOYEE_ID
                WHERE a.APPL_NO = :a
            """), {"a": appl_no}).mappings().first() or {}

            revisi_row = db.session.execute(text("""
                SELECT REVISI FROM MCMOREVISI WITH (NOLOCK) WHERE NEWAPPL_NO = :a
            """), {"a": appl_no}).mappings().first()
            str_revisi = f"R{revisi_row['REVISI']}" if revisi_row else ""

            items.append({
                "applNo": appl_no,
                "strRevisi": str_revisi,
                "lesseeName": row.get("LESSEE_NM") or "",
                "cmoUsername": row.get("USERNAME") or "",
            })

        db.session.commit()

        clause, params = _in_params(appl_nos)
        netfin_row = db.session.execute(text(f"""
            SELECT MAX(Net_Finance) AS Net_Finance FROM V_NetFinance WHERE APPL_NO IN ({clause})
        """), params).mappings().first()
        total_net_finance_external = float((netfin_row or {}).get("Net_Finance") or 0)

        level = current_approval_level(appl_nos[0])
        cmh = get_next_available_approver(branch_cd, username, current_approval_level=level, approval_form_id=1, appr_plafond='0')
        approver = approver_option_from_raw(cmh)

        gps_vendors = [
            {"value": r["SUPP"], "label": r["NAME"]}
            for r in db.session.execute(text("""
                SELECT SUPP, NAME FROM VENDOR WITH (NOLOCK) WHERE Supp_Category = 'GPS' ORDER BY NAME
            """)).mappings().all()
        ]

        purpose_options = [
            {"value": r["PURPOFFINC"], "label": r["DESC"]}
            for r in db.session.execute(text("""
                SELECT PURPOFFINC, [DESC] FROM MSTPURPOFFINC WITH (NOLOCK) WHERE Flag_Active = '1'
            """)).mappings().all()
        ]

        return jsonify({
            "success": True,
            "ketMultiple": "Multiple" if multiple else "Not Multiple",
            "items": items,
            "watchlistMessage": watchlist_message,
            "approverOptions": [approver] if approver else [],
            "gpsVendorOptions": gps_vendors,
            "showPurposeOfFinanceEdit": show_purpose_edit,
            "purposeOfFinanceValue": purpose_value,
            "purposeOfFinanceOptions": purpose_options,
            "purposeOfFinanceNotice": purpose_notice,
            "purposeOfFinanceCondition": purpose_condition,
            "totalNetFinanceExternal": total_net_finance_external,
            "lesseeType": lessee_type,
        })
    except Exception:
        db.session.rollback()
        current_app.logger.exception("get_send_cmo_init error")
        return jsonify({"error": "Failed to load send-to-CMO data"}), 500

@cam_send_cmo_bp.route('/confirm', methods=['POST'])
@login_required
def confirm_send_cmo():
    body = request.get_json(force=True) or {}
    appl_nos = _split_appl_nos(body.get("appl_nos"))
    multiple = bool(body.get("multiple"))
    approval_raw = body.get("approval") or ""
    comment = (body.get("comment") or "").replace("'", "`")
    red_code = bool(body.get("redCode"))
    gps_vendor = body.get("gpsVendor") or ""
    username = session.get('username', '')
    emp_id = session.get('emp_id', '')
    branch_cd = session.get('branchcode', '')

    if not appl_nos:
        return jsonify({"success": False, "message": "No CAM selected."})

    approval_parts = approval_raw.split("|")
    approval = approval_parts[0] if approval_parts else ""
    approver_access_level = approval_parts[1] if len(approval_parts) > 1 else ""
    if not approval:
        return jsonify({"success": False, "message": "Please choose an approver."})

    try:
        if multiple:
            nomer_row = db.session.execute(text("""
                SELECT MAX(SUBSTRING(MSTR_CA, 5, 6)) AS nomer FROM TAMASTER WITH (NOLOCK)
                WHERE SUBSTRING(MSTR_CA, 1, 4) = :emp_id
            """), {"emp_id": emp_id}).mappings().first()
            nomer = int((nomer_row or {}).get("nomer") or 0) + 1
            mstr_ca = f"{emp_id}{nomer:06d}"
            for appl_no in appl_nos:
                hitung_irr(db, appl_no)
                db.session.execute(text("""
                    INSERT INTO TAMASTER (APPL_NO, MSTR_CA, BRANCH_CD) VALUES (:a, :m, :b)
                """), {"a": appl_no, "m": mstr_ca, "b": branch_cd})

        privy_messages = []
        for appl_no in appl_nos:
            hitung_irr(db, appl_no)

            error = _validate_appl_no(appl_no, red_code, gps_vendor)
            if error:
                db.session.rollback()
                return jsonify({"success": False, "message": error})

            lesse = db.session.execute(text("""
                SELECT LESSEE_TP FROM cafless WITH (NOLOCK)
                WHERE APLESS = (SELECT APLESS FROM cafcont WHERE APPL_NO = :a)
            """), {"a": appl_no}).mappings().first() or {}
            lestp = lesse.get("LESSEE_TP")

            db.session.execute(text("""
                EXEC USP_CAM_SENTBYCMO :a, :username, :comment, :approval, :approver_access_level
            """), {
                "a": appl_no, "username": username, "comment": comment,
                "approval": approval, "approver_access_level": approver_access_level,
            })

            if lestp == 'PT':
                privy_msg = register_privy(appl_no)
                if privy_msg:
                    privy_messages.append(privy_msg)

            db.session.execute(text("""
                UPDATE CAFCONT SET CORP_RET = :val WHERE APPL_NO = :a
            """), {"val": "M" if multiple else "R", "a": appl_no})

            db.session.execute(text("""
                UPDATE CAFEQUIP_DETAIL SET IsRedCode = :rc, GPS_Vendor = :gv WHERE APPL_NO = :a
            """), {"rc": "1" if red_code else "0", "gv": gps_vendor, "a": appl_no})

        db.session.commit()

        message = "Approval has been sent successfully."
        if privy_messages:
            message += "\n\nRegister PRIVY Information:\n" + "\n".join(privy_messages)

        return jsonify({"success": True, "message": message})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("confirm_send_cmo error")
        return jsonify({"success": False, "message": "Failed to submit approval. Please try again."})