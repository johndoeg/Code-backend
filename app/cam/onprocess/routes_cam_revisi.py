import math
import os
import shutil
import boto3

from datetime import date, datetime
from flask import Blueprint, jsonify, request, current_app, session
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text

revisi_cam_bp = Blueprint("revisi_cam_bp", __name__, url_prefix="/CAM")

def _get_session_ctx() -> dict:
    return {
        "emp_id":   session.get("emp_id", ""),
        "username": session.get("username", ""),
    }

def _php_round(value):
    if value is None:
        return 0
    return math.floor(value + 0.5) if value >= 0 else math.ceil(value - 0.5)

def _s(v):
    return "" if v is None else str(v)

def _fmt_date(v):
    if v is None:
        return None
    if isinstance(v, (date, datetime)):
        return v.strftime("%Y-%m-%d")
    return str(v)

def _next_revision_info(applno: str):
    row = db.session.execute(
        text("SELECT REVISI, First_Appl_No FROM MCMOREVISI WITH (NOLOCK) WHERE NEWAPPL_NO = :appl"),
        {"appl": applno}
    ).mappings().first()
    if row:
        return str(int(row["REVISI"]) + 1), row["First_Appl_No"]
    return "1", applno

def _check_ratio_allowed(cons_leas: str):
    row = db.session.execute(text("EXEC USP_CHECK_RATIO ''")).mappings().first()
    hasil = (row or {}).get("hasil")
    if hasil == "Not Allowed" and cons_leas == "W":
        return False
    return True

@revisi_cam_bp.route("/revisi/init")
@login_required
def get_revisi_init():
    apless = request.args.get("apless", "")
    applno = request.args.get("applno", "")

    if not apless or not applno:
        return jsonify({"error": "Missing apless/applno"}), 400

    try:
        lessee = db.session.execute(
            text("SELECT LESSEE_NM, LESSEE_TP FROM CAFLESS WITH (NOLOCK) WHERE APLESS = :apless"),
            {"apless": apless}
        ).mappings().first() or {}

        contfin = db.session.execute(
            text("""
                SELECT a.Cons_Leas, b.name
                FROM CAFCONT a WITH (NOLOCK)
                    INNER JOIN MSTCFFL b WITH (NOLOCK) ON a.Cons_Leas = b.Cons_Leas
                WHERE a.APPL_NO = :appl
            """),
            {"appl": applno}
        ).mappings().first() or {}
        cons_leas = contfin.get("Cons_Leas")
        cons_leas_name = contfin.get("name")

        allowed = _check_ratio_allowed(cons_leas)
        if not allowed:
            return jsonify({
                "blocked": True,
                "message": f"{cons_leas_name} is not allowed",
            })

        next_revision, _first_appl_no = _next_revision_info(applno)

        return jsonify({
            "blocked": False,
            "appl_no": applno,
            "lessee_nm": lessee.get("LESSEE_NM", ""),
            "cons_leas_name": cons_leas_name,
            "next_revision": next_revision,
        })

    except Exception:
        current_app.logger.exception("CAM revisi init error")
        return jsonify({"error": "Failed to load"}), 500

def _allocate_new_appl_no(emp_idd: str):
    applno_cmo = f"APPL_NO{emp_idd}"
    row = db.session.execute(
        text("""
            SELECT NextNumber, CONVERT(VARCHAR(7), [LastUpdate], 126) AS LastUpdate
            FROM TANUMBER WITH (NOLOCK)
            WHERE PropertyGroupName = :grp
        """),
        {"grp": applno_cmo}
    ).mappings().first()

    if not row:
        raise ValueError("Cannot copy or revise CAM, please call helpdesk")

    applno_cmo1 = row["NextNumber"]
    thnbln = row["LastUpdate"]
    thnblnskrg = datetime.now().strftime("%Y-%m")

    if thnblnskrg != thnbln:
        applno_cmo1 = 1

    applno_cmo2 = str(applno_cmo1).rjust(3, "0")
    applno_cmo_brkt = int(applno_cmo1) + 1
    now = datetime.now()
    applno_baru = f"{emp_idd}{now.strftime('%y')}{now.strftime('%m')}{applno_cmo2}"

    db.session.execute(
        text("UPDATE TANUMBER SET NextNumber = :next_no, LastUpdate = GETDATE() WHERE PropertyGroupName = :grp"),
        {"next_no": applno_cmo_brkt, "grp": applno_cmo}
    )
    return applno_baru

def _clone_simple(old_appl, new_appl, table, columns, appl_col="APPL_NO"):
    col_list = ", ".join(columns)
    sql = f"""
        INSERT INTO {table} ({appl_col}, {col_list})
        SELECT :new_appl, {col_list}
        FROM {table} WITH (NOLOCK)
        WHERE {appl_col} = :old_appl
    """
    db.session.execute(text(sql), {"new_appl": new_appl, "old_appl": old_appl})

_CAFCONT_CLONE_COLUMNS = [
    "CURR_CODE", "L_AMOUNT", "SECURITY", "RESIDUAL", "DECLRATE", "FLATRATE", "OVERATE", "REBATE",
    "COL_TYPE", "ADV_ARR", "L_TYPE", "FIX_FLOAT", "FLOAT_CYC", "DL_SLB", "TENOR", "PAY_CYCLE",
    "RENTAL", "MLCIDECL", "MLCIFLAT", "MLCIRENT", "MLCITAX", "Gross", "OTHERFEE", "G_TERM",
    "G_PERIOD", "G_INT_RATE", "G_INT_AMT", "Corp_Ret", "Cons_Leas", "CMO", "ContSts",
    "OutStanding", "Out_Amount", "COL_TYPE_Supp", "Refund_Supp", "REMARK", "Nbr_Contract",
    "Disc_Cust", "Disc_MLCI", "AdmFee", "PURPOFFINC", "BRANCH_CD", "Otherloan", "DECLRATE1000",
    "FLATRATE1000", "TENOR1000", "Notary_no", "Notary", "Fiduciary", "HAS_GUARANTOR", "Disb_Type",
    "Cont_type", "SUBSIDY", "FLAGCOM", "NOTES", "PENDING_NOTES", "CAM_NOTES", "PROVISION",
    "COMM_PROVISION", "Incentive", "BusinessTrip_Fee", "Subsidy_Supp", "Max_Fee", "BaseAdmFee",
    "BaseInterestFee", "InterestIncome", "prechecking_id",
]

def _clone_cafcont(old_appl, new_appl, apless):
    col_list = ", ".join(_CAFCONT_CLONE_COLUMNS)
    db.session.execute(text(f"""
        INSERT INTO CAFCONT ([APPL_NO], [APLESS], {col_list}, [CREATE_DATE])
        SELECT :new_appl, :apless, {col_list}, GETDATE()
        FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :old_appl AND APLESS = :apless
    """), {"new_appl": new_appl, "old_appl": old_appl, "apless": apless})

def _clone_cafdev(old_appl, new_appl):
    rows = db.session.execute(
        text("SELECT DEVIATION_CD, REASON, DEVIATION_DESC, STANDARD_DESC FROM CAFDEV WITH (NOLOCK) WHERE APPL_NO = :appl"),
        {"appl": old_appl}
    ).mappings().all()
    for row in rows:
        db.session.execute(text("""
            INSERT INTO CAFDEV (APPL_NO, DEVIATION_CD, REASON, DEVIATION_DESC, STANDARD_DESC, INPUT_DT)
            VALUES (:new_appl, :dev_cd, :reason, :deviation, :standard, GETDATE())
        """), {
            "new_appl": new_appl,
            "dev_cd": row["DEVIATION_CD"],
            "reason": row["REASON"],
            "deviation": row["DEVIATION_DESC"],
            "standard": row["STANDARD_DESC"],
        })

def _next_cafequip_id():
    row = db.session.execute(
        text("SELECT NextNumber FROM TANUMBER WITH (NOLOCK) WHERE PropertyGroupName = 'CAFEQUIP_ID'")
    ).mappings().first()
    cafequip_id = row["NextNumber"]
    db.session.execute(
        text("UPDATE TANUMBER SET NextNumber = :next_id, LastUpdate = GETDATE() WHERE PropertyGroupName = 'CAFEQUIP_ID'"),
        {"next_id": int(cafequip_id) + 1}
    )
    return cafequip_id

def _clone_equipment(old_appl, new_appl, messages):
    valid = True
    id_map = {}

    rows = db.session.execute(text("""
        SELECT b.Cont_type, b.Cons_Leas, a.CAFEQUIP_ID, a.APPL_NO, a.TYPE_CD, a.BRAND, a.[TYPE], a.MODEL,
               a.TAHUN, a.SUPP, a.CHASIS, a.ENGINE, a.COLOUR, a.[CONDITION], a.POLICENO, a.BPKB_NO,
               a.BPKB_AN_TP, a.BPKB_AN, a.BPKB_ADDR, a.CITY_BPKB, a.FORMA, a.REMARK, a.USERUSAGE,
               a.PURPOSE, a.PARK_LOC, a.CITY_PARK, a.BPKB_AN_FAM, a.KM, a.KM_DATE, a.KM_TIME,
               a.Relation, a.Fdc_Area, a.BPKB_AN_STS, a.KAROSERI, a.STNK_VALIDDT, a.KAROSERI_SUPP,
               a.TAX_FREE, a.ACCESSORIES_SUPP, a.OTHER_SUPP, a.WHEELS, a.INSURANCE_AREA,
               a.BPKB_AREA_CD, a.BPKB_PLACEBIRTH, a.BPKB_TGLBIRTH, a.FUND_PURPOSE
        FROM CAFEQUIP a WITH (NOLOCK)
            LEFT JOIN CAFCONT b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
        WHERE a.APPL_NO = :appl
    """), {"appl": old_appl}).mappings().all()

    for row in rows:
        if not row.get("TYPE_CD"):
            valid = False
            messages.append("Type of Equipment must not empty")
        if not row.get("BRAND"):
            valid = False
            messages.append("Brand must not empty")
        if row.get("Cons_Leas") not in ("S", "D", "M", "W") and not row.get("SUPP"):
            valid = False
            messages.append("Supplier must not empty")

        new_cafequip_id = _next_cafequip_id()
        old_cafequip_id = row.get("CAFEQUIP_ID")
        if old_cafequip_id is not None:
            id_map[old_cafequip_id] = new_cafequip_id

        wheels = row.get("WHEELS") or 0
        supp = row.get("SUPP") or None
        karo_supp = row.get("KAROSERI_SUPP") or None
        acce_supp = row.get("ACCESSORIES_SUPP") or None
        oth_supp = row.get("OTHER_SUPP") or None
        km_date = _fmt_date(row.get("KM_DATE"))
        bpkbtgl = _fmt_date(row.get("BPKB_TGLBIRTH"))
        is_new = (row.get("CONDITION") or "").strip() == "NEW"

        params = {
            "cafequip_id": new_cafequip_id, "new_appl": new_appl,
            "type_cd": row.get("TYPE_CD"), "brand": row.get("BRAND"), "type_": row.get("TYPE"),
            "model": row.get("MODEL"), "tahun": row.get("TAHUN"), "supp": supp,
            "chasis": row.get("CHASIS"), "engine": row.get("ENGINE"), "colour": row.get("COLOUR"),
            "condition_": row.get("CONDITION"), "policeno": row.get("POLICENO"), "bpkb_no": row.get("BPKB_NO"),
            "bpkb_an_tp": row.get("BPKB_AN_TP"), "bpkb_an": row.get("BPKB_AN"), "bpkb_addr": row.get("BPKB_ADDR"),
            "city_bpkb": row.get("CITY_BPKB"), "forma": row.get("FORMA"), "remark": row.get("REMARK"),
            "userusage": row.get("USERUSAGE"), "purpose": row.get("PURPOSE"), "park_loc": row.get("PARK_LOC"),
            "city_park": row.get("CITY_PARK"), "bpkb_an_fam": row.get("BPKB_AN_FAM"), "km": row.get("KM"),
            "km_date": km_date, "km_time": row.get("KM_TIME"), "relation": row.get("Relation"),
            "fdc_area": row.get("Fdc_Area"), "bpkb_an_sts": row.get("BPKB_AN_STS"), "karoseri": row.get("KAROSERI"),
            "karo_supp": karo_supp, "tax_free": row.get("TAX_FREE"), "wheels": wheels,
            "insurance_area": row.get("INSURANCE_AREA"), "acce_supp": acce_supp, "oth_supp": oth_supp,
            "bpkb_area_cd": row.get("BPKB_AREA_CD"), "fund_purpose": row.get("FUND_PURPOSE"),
            "stnk_validdt": row.get("STNK_VALIDDT"),
            "bpkb_placebirth": row.get("BPKB_PLACEBIRTH"), "bpkbtgl": bpkbtgl,
        }

        if is_new:
            db.session.execute(text("""
                INSERT INTO CAFEQUIP (
                    [CAFEQUIP_ID],[APPL_NO],[TYPE_CD],[BRAND],[TYPE],[MODEL],[TAHUN],[SUPP],[CHASIS],[ENGINE],
                    [COLOUR],[CONDITION],[POLICENO],[BPKB_NO],[BPKB_AN_TP],[BPKB_AN],[BPKB_ADDR],[CITY_BPKB],
                    [FORMA],[REMARK],[USERUSAGE],[PURPOSE],[PARK_LOC],[CITY_PARK],[BPKB_AN_FAM],[KM],[KM_DATE],
                    [KM_TIME],[Relation],[Fdc_Area],[BPKB_AN_STS],[KAROSERI],[KAROSERI_SUPP],[TAX_FREE],
                    [WHEELS],[INSURANCE_AREA],ACCESSORIES_SUPP,OTHER_SUPP,BPKB_AREA_CD,BPKB_PLACEBIRTH,
                    BPKB_TGLBIRTH,[FUND_PURPOSE]
                ) VALUES (
                    :cafequip_id,:new_appl,:type_cd,:brand,:type_,:model,:tahun,:supp,:chasis,:engine,
                    :colour,:condition_,:policeno,:bpkb_no,:bpkb_an_tp,:bpkb_an,:bpkb_addr,:city_bpkb,
                    :forma,:remark,:userusage,:purpose,:park_loc,:city_park,:bpkb_an_fam,:km,:km_date,
                    :km_time,:relation,:fdc_area,:bpkb_an_sts,:karoseri,:karo_supp,:tax_free,
                    :wheels,:insurance_area,:acce_supp,:oth_supp,:bpkb_area_cd,:bpkb_placebirth,
                    :bpkbtgl,:fund_purpose
                )
            """), params)
        else:
            db.session.execute(text("""
                INSERT INTO CAFEQUIP (
                    [CAFEQUIP_ID],[APPL_NO],[TYPE_CD],[BRAND],[TYPE],[MODEL],[TAHUN],[SUPP],[CHASIS],[ENGINE],
                    [COLOUR],[CONDITION],[POLICENO],[BPKB_NO],[BPKB_AN_TP],[BPKB_AN],[BPKB_ADDR],[CITY_BPKB],
                    [FORMA],[REMARK],[USERUSAGE],[PURPOSE],[PARK_LOC],[CITY_PARK],[BPKB_AN_FAM],[KM],[KM_DATE],
                    [KM_TIME],[Relation],[Fdc_Area],[BPKB_AN_STS],[KAROSERI],[STNK_VALIDDT],[KAROSERI_SUPP],
                    [TAX_FREE],[WHEELS],[INSURANCE_AREA],ACCESSORIES_SUPP,OTHER_SUPP,BPKB_AREA_CD,[FUND_PURPOSE]
                ) VALUES (
                    :cafequip_id,:new_appl,:type_cd,:brand,:type_,:model,:tahun,:supp,:chasis,:engine,
                    :colour,:condition_,:policeno,:bpkb_no,:bpkb_an_tp,:bpkb_an,:bpkb_addr,:city_bpkb,
                    :forma,:remark,:userusage,:purpose,:park_loc,:city_park,:bpkb_an_fam,:km,:km_date,
                    :km_time,:relation,:fdc_area,:bpkb_an_sts,:karoseri,:stnk_validdt,:karo_supp,
                    :tax_free,:wheels,:insurance_area,:acce_supp,:oth_supp,:bpkb_area_cd,:fund_purpose
                )
            """), params)

    return valid, id_map

def _clone_cafequip_detail(old_appl, new_appl, cafequip_id_map):
    rows = db.session.execute(text("""
        SELECT Cafequip_ID, FIN_PURPOSE, OJK_Fin_Goods, OJK_Fin_Goods_Detail,
               OJK_Coll_Goods, OJK_Coll_Goods_Detail, IsRedCode, GPS_Vendor
        FROM Cafequip_Detail WITH (NOLOCK)
        WHERE APPL_NO = :appl
    """), {"appl": old_appl}).mappings().all()

    for row in rows:
        new_cafequip_id = cafequip_id_map.get(row["Cafequip_ID"])
        if new_cafequip_id is None:
            current_app.logger.warning(
                "Cafequip_Detail row references CAFEQUIP_ID %s with no matching "
                "clone for APPL_NO %s - skipped", row["Cafequip_ID"], old_appl
            )
            continue
        db.session.execute(text("""
            INSERT INTO Cafequip_Detail (
                Cafequip_ID, APPL_NO, FIN_PURPOSE, OJK_Fin_Goods, OJK_Fin_Goods_Detail,
                OJK_Coll_Goods, OJK_Coll_Goods_Detail, IsRedCode, GPS_Vendor
            ) VALUES (
                :cafequip_id, :new_appl, :fin_purpose, :ojk_fin_goods, :ojk_fin_goods_detail,
                :ojk_coll_goods, :ojk_coll_goods_detail, :is_red_code, :gps_vendor
            )
        """), {
            "cafequip_id": new_cafequip_id, "new_appl": new_appl,
            "fin_purpose": row["FIN_PURPOSE"], "ojk_fin_goods": row["OJK_Fin_Goods"],
            "ojk_fin_goods_detail": row["OJK_Fin_Goods_Detail"], "ojk_coll_goods": row["OJK_Coll_Goods"],
            "ojk_coll_goods_detail": row["OJK_Coll_Goods_Detail"], "is_red_code": row["IsRedCode"],
            "gps_vendor": row["GPS_Vendor"],
        })

def _clone_cafequip_bpkbstatus(old_appl, new_appl):
    _clone_simple(old_appl, new_appl, "CAFEQUIP_BPKBSTATUS", [
        "ID", "BPKB_MARITAL_STATUS", "BPKB_SPOUSE_NAME", "BPKB_SPOUSE_ADDRESS",
        "POA_NAME", "POA_OCCUPATION", "POA_ADDRESS", "BPKB_SPOUSE_STATUS",
    ])

def _clone_clfsupp1(old_appl, new_appl, fin_type, messages):
    valid = True
    rows = db.session.execute(text("""
        SELECT [NAME],[ADDRESS],[CITY],[ZipCode],[PHONE],[ACCNO],[Bank],[AccNoName],[BankBranch],
               [DealerCd],[Contact],[Occupation],[SUPP_TYPE],[SUPP_CAT],[LESSEE_NO]
        FROM CLFSUPP1 WITH (NOLOCK) WHERE SUPP = :old_appl
    """), {"old_appl": old_appl}).mappings().all()

    for row in rows:
        if not row["SUPP_TYPE"] and fin_type != "W":
            valid = False
            messages.append("Supplier Type must not empty")
        if not row["SUPP_CAT"] and fin_type != "W":
            valid = False
            messages.append("Supplier Category must not empty")

        db.session.execute(text("""
            INSERT INTO CLFSUPP1 ([SUPP],[NAME],[ADDRESS],[CITY],[ZipCode],[PHONE],[ACCNO],[Bank],
                [AccNoName],[BankBranch],[DealerCd],[Contact],[Occupation],[SUPP_TYPE],[SUPP_CAT],[LESSEE_NO])
            VALUES (:new_appl,:name,:address,:city,:zip,:phone,:accno,:bank,:accnoname,:bankbranch,
                :dealercd,:contact,:occupation,:supp_type,:supp_cat,:lessee_no)
        """), {
            "new_appl": new_appl, "name": row["NAME"], "address": row["ADDRESS"], "city": row["CITY"],
            "zip": row["ZipCode"], "phone": row["PHONE"], "accno": row["ACCNO"], "bank": row["Bank"],
            "accnoname": row["AccNoName"], "bankbranch": row["BankBranch"], "dealercd": row["DealerCd"],
            "contact": row["Contact"], "occupation": row["Occupation"], "supp_type": row["SUPP_TYPE"],
            "supp_cat": row["SUPP_CAT"], "lessee_no": row["LESSEE_NO"],
        })
    return valid

def _clone_guarantors(old_appl, new_appl, apless):
    rows = db.session.execute(text("""
        SELECT APLESS, GRNID, LESSEE_NO, GRNNAME, GRNADD, GRNTP, GRNSpouse, GRNStatus, GRNAkte,
               GRNContact, GRNOccupation, GRNTTL, GRNCAT, CONVERT(date, GRNDOB, 105) AS GRNDOB,
               GRNCITY, GRNZIPCODE, GRNFAX, GRNPHONE, GRNRELATION, GRNIDCARD, GRNIDFILE,
               CONVERT(date, GRNIDVAL, 105) AS GRNIDVAL, GRNLOB, NOOFBANK, CON_SIGNPOS, GRNSPOUSEADD,
               GRNSPOUSECITY, GRNSPOUSECODE, GRNNAME_Without_Title, GRNPASSPORTNO, GRNCITIZEN,
               GRNNATIONALITY, GRNNPWP, GRN_BITYPE, GRNNAME_NPWP, GRNADD_NPWP, Gender, Marital,
               GRNSPOUSEIDCARD, GRNCITY_NPWP, GRNZIPCODE_NPWP
        FROM CAFGUARN WITH (NOLOCK)
        WHERE APPL_NO = :appl
    """), {"appl": old_appl}).mappings().all()

    max_by_grntp = {}
    last_nourut = ""
    count_urut = 1
    for row in rows:
        grntp = row["GRNTP"]
        if grntp not in max_by_grntp:
            max_row = db.session.execute(text("""
                SELECT MAX(RIGHT(GRNID, 6)) AS nourut FROM CAFGUARN WITH (NOLOCK)
                WHERE GRNTP = :grntp GROUP BY GRNTP
            """), {"grntp": grntp}).mappings().first()
            max_by_grntp[grntp] = int((max_row or {}).get("nourut") or 0)

        nourut = str(max_by_grntp[grntp] + count_urut).rjust(6, "0")
        last_nourut = nourut

        db.session.execute(text("""
            INSERT INTO CAFGUARN (APPL_NO, APLESS, GRNID, LESSEE_NO, GRNNAME, GRNADD, GRNTP, GRNSpouse,
                GRNStatus, GRNAkte, GRNContact, GRNOccupation, GRNTTL, GRNCAT, GRNDOB, GRNCITY, GRNZIPCODE,
                GRNFAX, GRNPHONE, GRNRELATION, GRNIDCARD, GRNIDFILE, GRNIDVAL, GRNLOB, NOOFBANK,
                CON_SIGNPOS, GRNSPOUSEADD, GRNSPOUSECITY, GRNSPOUSECODE, [GRNNAME_Without_Title],
                [GRNPASSPORTNO], [GRNCITIZEN], [GRNNATIONALITY], [GRNNPWP], Gender, Marital,
                GRNSPOUSEIDCARD, [GRN_BITYPE], [GRNNAME_NPWP], [GRNADD_NPWP], [GRNCITY_NPWP], [GRNZIPCODE_NPWP])
            VALUES (:new_appl, :apless, :nourut, :lessee_no, :name, :add_, :grntp, :spouse, :status, :akte,
                :contact, :occupation, :ttl, :cat, :dob, :city, :zip, :fax, :phone, :relation, :idcard,
                :idfile, :idval, :lob, :noofbank, :signpos, :spouseadd, :spousecity, :spousecode,
                :name_wo_title, :passportno, :citizen, :nationality, :npwp, :gender, :marital, :spouseidcard,
                :bitype, :name_npwp, :add_npwp, :city_npwp, :zip_npwp)
        """), {
            "new_appl": new_appl, "apless": row["APLESS"], "nourut": nourut, "lessee_no": row["LESSEE_NO"],
            "name": row["GRNNAME"], "add_": row["GRNADD"], "grntp": grntp, "spouse": row["GRNSpouse"],
            "status": row["GRNStatus"], "akte": row["GRNAkte"], "contact": row["GRNContact"],
            "occupation": row["GRNOccupation"], "ttl": row["GRNTTL"], "cat": row["GRNCAT"],
            "dob": _fmt_date(row["GRNDOB"]), "city": row["GRNCITY"], "zip": row["GRNZIPCODE"],
            "fax": row["GRNFAX"], "phone": row["GRNPHONE"], "relation": row["GRNRELATION"],
            "idcard": row["GRNIDCARD"], "idfile": row["GRNIDFILE"], "idval": _fmt_date(row["GRNIDVAL"]),
            "lob": row["GRNLOB"], "noofbank": row["NOOFBANK"], "signpos": row["CON_SIGNPOS"],
            "spouseadd": row["GRNSPOUSEADD"], "spousecity": row["GRNSPOUSECITY"], "spousecode": row["GRNSPOUSECODE"],
            "name_wo_title": row["GRNNAME_Without_Title"], "passportno": row["GRNPASSPORTNO"],
            "citizen": row["GRNCITIZEN"], "nationality": row["GRNNATIONALITY"], "npwp": row["GRNNPWP"],
            "gender": row["Gender"], "marital": row["Marital"], "spouseidcard": row["GRNSPOUSEIDCARD"],
            "bitype": row["GRN_BITYPE"], "name_npwp": row["GRNNAME_NPWP"], "add_npwp": row["GRNADD_NPWP"],
            "city_npwp": row["GRNCITY_NPWP"], "zip_npwp": row["GRNZIPCODE_NPWP"],
        })
        count_urut += 1

    return last_nourut

def _clone_customer_document(old_appl, new_appl, apless, nourut):
    rows = db.session.execute(text("""
        SELECT FILE_DOCUMENT, ORGANIZATION_TYPE, DOC_NO, DOC_TYPE, APLESS, AWSKey, DocumentType
        FROM CUSTOMER_DOCUMENT WITH (NOLOCK)
        WHERE APPL_NO = :appl
    """), {"appl": old_appl}).mappings().all()

    for row in rows:
        db.session.execute(text("""
            INSERT INTO CUSTOMER_DOCUMENT (APPL_NO, FILE_DOCUMENT, ORGANIZATION_TYPE, DOC_NO, DOC_TYPE,
                APLESS, UPLOAD_Dt, GRNID, AWSKey, DocumentType)
            VALUES (:new_appl, :file_doc, :org_type, :doc_no, :doc_type, :apless, GETDATE(), :nourut,
                :aws_key, :doc_type2)
        """), {
            "new_appl": new_appl, "file_doc": row["FILE_DOCUMENT"], "org_type": row["ORGANIZATION_TYPE"],
            "doc_no": row["DOC_NO"], "doc_type": row["DOC_TYPE"], "apless": row["APLESS"] or apless,
            "nourut": nourut, "aws_key": row["AWSKey"], "doc_type2": row["DocumentType"],
        })
    return rows 

def _clone_bank_statement_document(old_appl, new_appl):
    rows = db.session.execute(text("""
        SELECT Apless, DocumentName, AWSKey, CreatedDate, CreatedBy
        FROM BANK_STATEMENT_DOCUMENT WITH (NOLOCK)
        WHERE ApplNo = :appl
    """), {"appl": old_appl}).mappings().all()
    for row in rows:
        db.session.execute(text("""
            INSERT INTO BANK_STATEMENT_DOCUMENT (ApplNo, Apless, DocumentName, AWSKey, CreatedDate, CreatedBy)
            VALUES (:new_appl, :apless, :doc_name, :aws_key, :created_date, :created_by)
        """), {
            "new_appl": new_appl, "apless": row["Apless"], "doc_name": row["DocumentName"],
            "aws_key": row["AWSKey"], "created_date": row["CreatedDate"], "created_by": row["CreatedBy"],
        })
    return rows

def _clone_survey_file(old_appl, new_appl, apless):
    rows = db.session.execute(text("""
        SELECT DocumentName, DocumentType, AWSKey, SurveyType, CreatedBy, CreatedDate
        FROM SURVEY_FILE WITH (NOLOCK) WHERE ApplNo = :appl
    """), {"appl": old_appl}).mappings().all()
    for row in rows:
        db.session.execute(text("""
            INSERT INTO SURVEY_FILE (ApplNo, Apless, DocumentName, DocumentType, AWSKey, SurveyType, CreatedBy, CreatedDate)
            VALUES (:new_appl, :apless, :doc_name, :doc_type, :aws_key, :survey_type, :created_by, :created_date)
        """), {
            "new_appl": new_appl, "apless": apless, "doc_name": row["DocumentName"], "doc_type": row["DocumentType"],
            "aws_key": row["AWSKey"], "survey_type": row["SurveyType"], "created_by": row["CreatedBy"],
            "created_date": row["CreatedDate"],
        })
    return rows

def _clone_sik_checking_document(old_appl, new_appl):
    _clone_simple(old_appl, new_appl, "SIK_CHECKING_DOCUMENT", [
        "Subject", "Description", "CreditBureau", "RelatedParty", "Status", "Type",
        "Score", "Grade", "Pefindo", "Cabpefindo", "AWSKey", "DocumentType", "CreatedBy", "CreatedDate",
    ], appl_col="ApplNo")

def _clone_cafstep(old_appl, new_appl):
    _clone_simple(old_appl, new_appl, "CAFSTEP", ["STEP", "NO_STEP", "PMT_STEP", "MLCI_STEP"])

def _clone_insurance(old_appl, new_appl, fin_type, messages):
    valid = True
    rows = db.session.execute(text("""
        SELECT INS_CD, PAY_METHOD, CREDITAMT, REMARK, CommAdmFee, Police_No, MODEL, [Condition],
               Total_Seat, [USAGE], INS_CD_AREA, SpecialRate
        FROM CAFINSU WITH (NOLOCK)
        WHERE APPL_NO = :appl
    """), {"appl": old_appl}).mappings().all()

    ins_pol_new = f"{new_appl}1"
    for row in rows:
        if not row["INS_CD"] and fin_type != "W":
            valid = False
            messages.append("Insurance Company must not empty")

        special_rate = row["SpecialRate"]
        special_rate = None if special_rate in (None, "", "NULL") else str(special_rate).replace("'", "")

        db.session.execute(text("""
            INSERT INTO CAFINSU ([INS_POL],[APPL_NO],[INS_CD],[PAY_METHOD],[CREDITAMT],[REMARK],[CommAdmFee],
                [Police_No],[MODEL],[Condition],[Total_Seat],[USAGE],[INS_CD_AREA],[SpecialRate])
            VALUES (:ins_pol,:new_appl,:ins_cd,:pay_method,:creditamt,:remark,:comm_admfee,:police_no,
                :model,:condition_,:total_seat,:usage_,:ins_cd_area,:special_rate)
        """), {
            "ins_pol": ins_pol_new, "new_appl": new_appl, "ins_cd": row["INS_CD"], "pay_method": row["PAY_METHOD"],
            "creditamt": row["CREDITAMT"], "remark": row["REMARK"], "comm_admfee": row["CommAdmFee"],
            "police_no": row["Police_No"], "model": row["MODEL"], "condition_": row["Condition"],
            "total_seat": row["Total_Seat"], "usage_": row["USAGE"], "ins_cd_area": row["INS_CD_AREA"],
            "special_rate": special_rate,
        })

    ins_pol_old = f"{old_appl}1"
    insud_rows = db.session.execute(text("""
        SELECT INS_AMT, YEAR_NO, TPL_AMT, TLO_AR, CLAUSE, PRER_AMT, PREP_AMT, Rate_Premi, Rate_Premicla
        FROM CAFINSUD WITH (NOLOCK) WHERE INS_POL = :ins_pol
    """), {"ins_pol": ins_pol_old}).mappings().all()

    for row in insud_rows:
        if not row["INS_AMT"] and fin_type != "W":
            valid = False
            messages.append("Insurance Amount must not empty")
        if not row["YEAR_NO"] and fin_type != "W":
            valid = False
            messages.append("Year must not empty")

        db.session.execute(text("""
            INSERT INTO CAFINSUD ([INS_POL],[INS_AMT],[YEAR_NO],[TPL_AMT],[TLO_AR],[CLAUSE],[PRER_AMT],
                [PREP_AMT], Rate_Premi, Rate_Premicla)
            VALUES (:ins_pol,:ins_amt,:year_no,:tpl_amt,:tlo_ar,:clause,:prer_amt,:prep_amt,:rate_premi,:rate_premicla)
        """), {
            "ins_pol": ins_pol_new, "ins_amt": row["INS_AMT"], "year_no": row["YEAR_NO"], "tpl_amt": row["TPL_AMT"],
            "tlo_ar": row["TLO_AR"], "clause": row["CLAUSE"], "prer_amt": row["PRER_AMT"], "prep_amt": row["PREP_AMT"],
            "rate_premi": row["Rate_Premi"], "rate_premicla": row["Rate_Premicla"],
        })

    clause_rows = db.session.execute(text("""
        SELECT Year_No, Clause, Premi FROM CAFINSUD_Clause WITH (NOLOCK) WHERE Ins_Pol = :ins_pol
    """), {"ins_pol": ins_pol_old}).mappings().all()
    for row in clause_rows:
        db.session.execute(text("""
            INSERT INTO CAFINSUD_Clause (Appl_No, Ins_Pol, Year_No, Clause, Premi)
            VALUES (:new_appl, :ins_pol, :year_no, :clause, :premi)
        """), {
            "new_appl": new_appl, "ins_pol": ins_pol_new, "year_no": row["Year_No"],
            "clause": row["Clause"], "premi": row["Premi"],
        })

    return valid

def _clone_disb(old_appl, new_appl):
    _clone_simple(old_appl, new_appl, "CAFDISB", [
        "GROSS_PREM", "NET_COM", "DISB_INSC", "ADMFEE", "FIRST_INST", "DP", "Prov", "SPLIT",
        "L_AMOUNT", "SPLIT_OTHERS", "SERVICE_AGENCY_FEE", "BBN_FEE", "Notary_Fee",
        "BusinessTrip_Fee", "Agency_Fee", "SurveyFeeGross_Cigna",
    ])
    rows = db.session.execute(text("""
        SELECT BANK, ACC_NO, ACC_NM, AMOUNT, BANK_BRANCH, SPLIT FROM CAFDISBACC WITH (NOLOCK) WHERE APPL_NO = :appl
    """), {"appl": old_appl}).mappings().all()
    for row in rows:
        db.session.execute(text("""
            INSERT INTO CAFDISBACC ([APPL_NO],[BANK],[ACC_NO],[ACC_NM],[AMOUNT],[BANK_BRANCH],SPLIT)
            VALUES (:new_appl,:bank,:acc_no,:acc_nm,:amount,:bank_branch,:split)
        """), {
            "new_appl": new_appl, "bank": row["BANK"], "acc_no": row["ACC_NO"], "acc_nm": row["ACC_NM"],
            "amount": row["AMOUNT"], "bank_branch": row["BANK_BRANCH"], "split": row["SPLIT"],
        })

def _check_sales_inactive(old_appl):
    rows = db.session.execute(text("""
        SELECT b.[Status] FROM CAFKOMIS a WITH (NOLOCK)
        INNER JOIN CLFSALES b ON a.SALES_NO = b.SALES_NO WHERE APPL_NO = :appl
    """), {"appl": old_appl}).mappings().all()
    if any(r["Status"] != "A" for r in rows):
        return "Sales Inactive will not copy to New CAM Number"
    return None

def _clone_komisi(old_appl, new_appl, messages):
    valid = True
    rows = db.session.execute(text("""
        SELECT a.SALES_NO, a.FEE, a.GrossAmount, a.SD_TYPE, a.TaxAmount, a.PPNAmount, a.Last_Update,
               xx.DateStart, xx.TFFrom, xx.TFTo, xx.PPN, cc.Amount, a.Incentive, a.PaidBy
        FROM CAFKOMIS a WITH (NOLOCK)
            INNER JOIN CafkomisACC cc ON cc.APPL_No = a.APPL_NO AND cc.Sales_No = a.SALES_NO
            INNER JOIN CLFSALES b ON cc.SALES_NO = b.SALES_NO
            INNER JOIN BeneficiaryTax xx ON xx.BeneficiaryID = a.SALES_NO
        WHERE a.APPL_NO = :appl AND b.[Status] = 'A' AND a.SD_TYPE = 'S' AND xx.Category = 'SALES'
        
        UNION
        
        SELECT a.SALES_NO, a.FEE, a.GrossAmount, a.SD_TYPE, a.TaxAmount, a.PPNAmount, a.Last_Update,
               xx.DateStart, xx.TFFrom, xx.TFTo, xx.PPN, cc.Amount, a.Incentive, a.PaidBy
        FROM CAFKOMIS a WITH (NOLOCK)
            INNER JOIN CafkomisACC cc ON cc.APPL_No = a.APPL_NO AND cc.Sales_No = a.SALES_NO
            INNER JOIN BeneficiaryTax xx ON xx.BeneficiaryID = a.SALES_NO
        WHERE a.APPL_NO = :appl AND a.SD_TYPE = 'D' AND xx.Category = 'DEALER'
    """), {"appl": old_appl}).mappings().all()

    today = date.today()

    for row in rows:
        ppn = row["PPN"]
        fee_amount = row["FEE"]
        tax_amount = row["TaxAmount"]
        ppn_amount = row["PPNAmount"]
        feekomis = row["FEE"]

        last_update = row["Last_Update"] or datetime.now()

        if ppn == "1":
            tf_from = row["TFFrom"]
            tf_to = row["TFTo"]
            ppn_dt_from = row["DateStart"]
            ppn_year = ppn_dt_from.year if ppn_dt_from else None
            amount = row["Amount"] or 0

            in_tax_window = bool(tf_from and tf_to and tf_from <= today <= tf_to)
            ppn_active = bool(ppn_dt_from and ppn_year != 1900 and ppn_dt_from <= today)
            ppn_date_valid = bool(ppn_dt_from and ppn_year != 1900)

            if row["SD_TYPE"] == "D":
                if in_tax_window:
                    if ppn_active:
                        sisa_max_fee = amount / 1.11
                        max_fee_net = _php_round(sisa_max_fee)
                        tax_amount = 0
                        ppn_amount = amount - max_fee_net
                        feekomis = max_fee_net + ppn_amount
                        fee_amount = _php_round(sisa_max_fee)
                else:
                    if ppn_active:
                        sisa_max_fee = _php_round(amount / 1.11)
                        persen = math.floor(sisa_max_fee * 2 / 100)
                        max_fee_net = amount - persen
                        tax_amount = math.floor(persen)
                        ppn_amount = amount - sisa_max_fee
                        fee_amount = sisa_max_fee
                        feekomis = fee_amount - tax_amount + ppn_amount

            elif row["SD_TYPE"] == "S":
                sales_tax = db.session.execute(text("""
                    SELECT a.Sales_Type, a.NPWP_Type, b.NPWP_No FROM CLFSALES a WITH (NOLOCK)
                        INNER JOIN BeneficiaryTax b ON a.SALES_NO = b.BeneficiaryID
                    WHERE a.SALES_NO = :sales_no AND a.Category = 'SALES'
                """), {"sales_no": row["SALES_NO"]}).mappings().first() or {}
                npwp_type = sales_tax.get("NPWP_Type")
                npwp_no = sales_tax.get("NPWP_No")

                if npwp_type == "PT" and npwp_no:
                    if in_tax_window:
                        if ppn_active:
                            sisa_max_fee = amount / 1.11
                            max_fee_net = _php_round(sisa_max_fee)
                            tax_amount = 0
                            ppn_amount = amount - max_fee_net
                            feekomis = max_fee_net + ppn_amount
                            fee_amount = _php_round(sisa_max_fee)
                    else:
                        if ppn_active:
                            sisa_max_fee = _php_round(amount / 1.11)
                            persen = math.floor(sisa_max_fee * 2 / 100)
                            max_fee_net = amount - persen
                            tax_amount = math.floor(persen)
                            ppn_amount = amount - sisa_max_fee
                            fee_amount = sisa_max_fee
                            feekomis = fee_amount - tax_amount + ppn_amount
                else:
                    if ppn_date_valid and ppn == "1":
                        sisa_max_fee = amount / 1.11
                        max_fee_net = _php_round(sisa_max_fee)
                        tax_amount = 0
                        ppn_amount = amount - max_fee_net
                        feekomis = max_fee_net + ppn_amount
                        fee_amount = _php_round(sisa_max_fee)

            db.session.execute(text("""
                INSERT INTO CAFKOMIS ([APPL_NO],[SALES_NO],[FEE],[GrossAmount],[SD_TYPE],
                    [TaxAmount],[PPNAmount],[Last_Update],[Incentive],[PaidBy])
                VALUES (:new_appl,:sales_no,:fee,:gross,:sd_type,:tax,:ppn_amt,:last_update,:incentive,:paidby)
            """), {
                "new_appl": new_appl, "sales_no": row["SALES_NO"], "fee": feekomis, "gross": fee_amount,
                "sd_type": row["SD_TYPE"], "tax": tax_amount, "ppn_amt": ppn_amount, "last_update": last_update,
                "incentive": row["Incentive"], "paidby": row["PaidBy"],
            })
        else:
            if not row["SALES_NO"]:
                valid = False
                messages.append("Sales Name must not empty")
            if not row["SD_TYPE"]:
                valid = False
                messages.append("Commission To must not empty")

            db.session.execute(text("""
                INSERT INTO CAFKOMIS ([APPL_NO],[SALES_NO],[FEE],[GrossAmount],[SD_TYPE],
                    [TaxAmount],[PPNAmount],[Last_Update],[Incentive],[PaidBy])
                VALUES (:new_appl,:sales_no,:fee,:gross,:sd_type,:tax,:ppn_amt,:last_update,:incentive,:paidby)
            """), {
                "new_appl": new_appl, "sales_no": row["SALES_NO"], "fee": row["FEE"], "gross": row["GrossAmount"],
                "sd_type": row["SD_TYPE"], "tax": row["TaxAmount"], "ppn_amt": row["PPNAmount"],
                "last_update": last_update, "incentive": row["Incentive"], "paidby": row["PaidBy"],
            })

    return valid

def _clone_komisi_acc(old_appl, new_appl):
    rows = db.session.execute(text("""
        SELECT a.Sales_No, a.SD_Type, a.ACC_NO, a.ACC_NM, a.ACC_Bank, a.ACC_BankBranch, a.Amount
        FROM CafkomisACC a WITH (NOLOCK)
            LEFT JOIN CLFSALES b ON a.SALES_NO = b.SALES_NO
        WHERE a.APPL_NO = :appl AND b.[Status] = 'A'
        
        UNION
        
        SELECT Sales_No, SD_Type, ACC_NO, ACC_NM, ACC_Bank, ACC_BankBranch, Amount
        FROM CafkomisACC WITH (NOLOCK)
        WHERE APPL_NO = :appl AND SD_TYPE = 'D'
    """), {"appl": old_appl}).mappings().all()
    for row in rows:
        db.session.execute(text("""
            INSERT INTO CafkomisACC ([APPL_NO],[Sales_No],[SD_Type],[ACC_NO],[ACC_NM],[ACC_Bank],[ACC_BankBranch],[Amount])
            VALUES (:new_appl,:sales_no,:sd_type,:acc_no,:acc_nm,:acc_bank,:acc_bankbranch,:amount)
        """), {
            "new_appl": new_appl, "sales_no": row["Sales_No"], "sd_type": row["SD_Type"], "acc_no": row["ACC_NO"],
            "acc_nm": row["ACC_NM"], "acc_bank": row["ACC_Bank"], "acc_bankbranch": row["ACC_BankBranch"],
            "amount": row["Amount"],
        })

def _clone_cust_outs(old_appl, new_appl, messages):
    valid = True
    rows = db.session.execute(text("""
        SELECT ASOF, CONS_LEAS, [TYPE], OUTS, UNIT FROM CAFCUST_OUTS WITH (NOLOCK) WHERE APPL_NO = :appl
    """), {"appl": old_appl}).mappings().all()
    for row in rows:
        if not row["CONS_LEAS"]:
            valid = False
            messages.append("Finance Type must not empty")
        db.session.execute(text("""
            INSERT INTO CAFCUST_OUTS ([APPL_NO],[ASOF],[CONS_LEAS],[TYPE],[OUTS],[UNIT])
            VALUES (:new_appl,:asof,:cons_leas,:type_,:outs,:unit)
        """), {
            "new_appl": new_appl, "asof": _fmt_date(row["ASOF"]), "cons_leas": row["CONS_LEAS"],
            "type_": row["TYPE"], "outs": row["OUTS"], "unit": row["UNIT"],
        })
    return valid

def _clone_survey(old_appl, new_appl, lessee_tp):
    if lessee_tp == "PR":
        _clone_simple(old_appl, new_appl, "CAFSURV_PR", [
            "CREDIT_HIS", "REF", "WORK_EXP", "NOTE_CHAR", "LIVING", "LIVING_STS", "CAR_OWN", "DEPOSIT",
            "BANK_STAT", "DEPOSIT_AMT", "BANK_STAT_AMT", "NOTE_CAPITAL", "FIX_INC", "JOB", "TOT_OTH_INC",
            "TOT_INC", "TOT_CREDIT", "NOTE_CAPACITY", "DP", "PMT", "NOTE_COLLATERAL", "INSURANCE",
            "FIX_INC_SOURCE", "TOT_OTH_INC_SOURCE", "FIX_SOURCE_REMARK", "OTH_SOURCE_REMARK",
            "File_SID_CHECKING", "NOTE_SID_CHECKING", "SIDCHECK", "SID_SUBJECT", "SID_RELATEDPARTY",
            "SID_KETERANGAN", "SID_CREDITBUREAU", "SID_STATUS", "SID_SCORE", "SID_GRADE",
            "TOT_INC_YEAR", "SID_Type",
        ])
    elif lessee_tp == "PT":
        _clone_simple(old_appl, new_appl, "CAFSURV_PT", [
            "CREDIT_HIS", "REF", "WORK_EXP", "COMP_STS", "SCALE", "NOTE_CHAR", "BUS_LOC", "UNIT_OWN",
            "UNIT_FREE", "DEPOSIT", "BANK_STAT", "DEPOSIT_AMT", "BANK_STAT_AMT", "NOTE_CAPITAL",
            "MONTH_PROFIT", "MONTH_SALES", "NET_PROFIT", "TOT_CREDIT", "NOTE_CAPACITY", "DP", "PMT",
            "NOTE_COLLATERAL", "INSURANCE", "MONTH_PROFIT_SOURCE", "MONTH_PROFIT_REMARK",
            "File_SID_CHECKING", "NOTE_SID_CHECKING", "SIDCHECK", "SID_SUBJECT", "SID_RELATEDPARTY",
            "SID_KETERANGAN", "SID_CREDITBUREAU", "SID_STATUS", "SID_SCORE", "SID_GRADE", "SID_Type",
        ])

def _clone_remaining_simple_tables(old_appl, new_appl):
    _clone_simple(old_appl, new_appl, "CAFLR", ["LEASE_NO", "MARKETPRICE", "PAYMENTSTATUS", "TERM", "OUTSTANDING", "[TYPE]"])
    _clone_simple(old_appl, new_appl, "CAFCROSSCOLL", [
        "LEASE_NO", "CROSS_COLL", "REMARK", "DELETE_DATE", "DELETE_BY",
        "INSTALLMENT", "UPLOAD_NM", "UPLOAD_DATE", "MEMONUMBER",
    ])
    _clone_simple(old_appl, new_appl, "TACrossNo", ["LEASE_NO", "CROSSNO", "CROSS_TYPE", "AMOUNT", "PURPOSE"])
    _clone_simple(old_appl, new_appl, "BBN", [
        "BBNVia", "PaidBy", "ServiceAgencyNM", "BBNLoan", "BBN_FEE", "ServiceAgencyFee", "NettServiceAgencyFee",
    ], appl_col="APPL_No")
    _clone_simple(old_appl, new_appl, "Provision_Loan", ["Prov_Loan"], appl_col="APPL_No")
    _clone_simple(old_appl, new_appl, "COMM_PARTY", ["TOTAL_INCOME", "COMM_THIRDPARTY", "[Percentage]"])
    _clone_simple(old_appl, new_appl, "CafcontSubsidyDetail", ["SubsidyType", "AmountType", "Amount"])
    _clone_simple(old_appl, new_appl, "CAFBANKSTM", [
        "APLESS", "Period", "BegBal", "Debet", "Credit", "EndBal", "Bank",
        "ACC_No", "Curr_code", "NOTES", "ACC_NM", "NOTES_REK", "Bank_Branch",
    ])
    _clone_simple(old_appl, new_appl, "BENEFICIARY_LINK", ["BO_ID", "BO_TYPE"])
    _clone_simple(old_appl, new_appl, "CIGNA_FEE", [
        "Survey_Fee_Cigna", "Survey_Base_Rate_Cigna", "Survey_Loan_Cigna", "Credit_Protection", "GuarantedAcceptance",
    ])
    _clone_simple(old_appl, new_appl, "CAFCONT_RESTRUCTURING", ["[RESTRUCTURING_CHANGE]"])
    _clone_simple(old_appl, new_appl, "Kuisioner_EDD", ["EDD_Customer", "EDD_BO"], appl_col="Appl_No")
    _clone_simple(old_appl, new_appl, "SURVEY_NOTES", [
        "SurveyType", "Notes", "CreatedBy", "CreatedDate", "UpdatedBy", "UpdatedDate",
    ], appl_col="ApplNo")

def _copy_local_asset(base_path, aws_key_old, old_appl, new_appl):
    if not aws_key_old or not base_path:
        return
    source_file = os.path.join(base_path, aws_key_old)
    destination = source_file.replace(old_appl, new_appl)
    
    try:
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        if os.path.exists(source_file):
            shutil.copy2(source_file, destination)
    except OSError:
        current_app.logger.exception("Local asset copy failed for %s", source_file)

def _copy_s3_asset(bucket, aws_key_old, old_appl, new_appl):
    if not aws_key_old or not bucket:
        return
    aws_key_new = aws_key_old.replace(old_appl, new_appl)
    try:
        
        boto3.client("s3").copy_object(
            Bucket=bucket, CopySource={"Bucket": bucket, "Key": aws_key_old}, Key=aws_key_new,
        )
    except Exception:
        current_app.logger.exception("S3 asset copy failed for %s", aws_key_old)

def _copy_assets_and_finalize(old_appl, new_appl, username, customer_doc_rows, bank_stmt_rows, survey_file_rows):
    base_path = current_app.config.get("CAM_UPLOAD_BASE_PATH")
    bucket = current_app.config.get("AWS_S3_BUCKET")

    for row in customer_doc_rows:
        _copy_local_asset(base_path, row["AWSKey"], old_appl, new_appl)
        _copy_s3_asset(bucket, row["AWSKey"], old_appl, new_appl)
    for row in bank_stmt_rows:
        _copy_local_asset(base_path, row["AWSKey"], old_appl, new_appl)
        _copy_s3_asset(bucket, row["AWSKey"], old_appl, new_appl)
    for row in survey_file_rows:
        _copy_local_asset(base_path, row["AWSKey"], old_appl, new_appl)
        _copy_s3_asset(bucket, row["AWSKey"], old_appl, new_appl)

    db.session.execute(text("""
        UPDATE CUSTOMER_DOCUMENT
        SET AWSKey = REPLACE(AWSKey, :old_appl, :new_appl),
            file_document = REPLACE(file_document, :old_appl, :new_appl), Upload_Dt = GETDATE()
        WHERE APPL_NO = :new_appl
    """), {"old_appl": old_appl, "new_appl": new_appl})

    db.session.execute(text("""
        UPDATE BANK_STATEMENT_DOCUMENT
        SET AWSKey = REPLACE(AWSKey, :old_appl, :new_appl),
            DocumentName = REPLACE(DocumentName, :old_appl, :new_appl),
            UpdatedBy = :username, UpdatedDate = GETDATE()
        WHERE ApplNo = :new_appl
    """), {"old_appl": old_appl, "new_appl": new_appl, "username": username})

    db.session.execute(text("""
        UPDATE SURVEY_FILE
        SET AWSKey = REPLACE(AWSKey, :old_appl, :new_appl),
            DocumentName = REPLACE(DocumentName, :old_appl, :new_appl),
            UpdatedBy = :username, UpdatedDate = GETDATE()
        WHERE ApplNo = :new_appl
    """), {"old_appl": old_appl, "new_appl": new_appl, "username": username})

    db.session.commit()

@revisi_cam_bp.route("/revisi", methods=["POST"])
@login_required
def post_revisi():
    ctx = _get_session_ctx()
    emp_id = ctx["emp_id"]
    username = ctx["username"]

    body = request.get_json(force=True) or {}
    apless = body.get("apless", "")
    applno = body.get("applno", "")
    revisi_note = (body.get("revisi_note") or "").strip()

    if not apless or not applno:
        return jsonify({"success": False, "message": "Missing apless/applno"}), 400
    if not revisi_note:
        return jsonify({"success": False, "message": "Note must not empty"})

    emp_idd = applno[:4]

    try:
        contfin = db.session.execute(
            text("SELECT Cons_Leas FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :appl"), {"appl": applno}
        ).mappings().first() or {}
        cons_leas = contfin.get("Cons_Leas")

        if not _check_ratio_allowed(cons_leas):
            return jsonify({"success": False, "message": "This finance type is not allowed for revision right now"})

        str_revisi, first_appl_no = _next_revision_info(applno)

        lessee = db.session.execute(
            text("SELECT LESSEE_TP FROM CAFLESS WITH (NOLOCK) WHERE APLESS = :apless"), {"apless": apless}
        ).mappings().first() or {}
        lessee_tp = lessee.get("LESSEE_TP")

        fin_type = cons_leas

        try:
            applno_baru = _allocate_new_appl_no(emp_idd)
        except ValueError as exc:
            return jsonify({"success": False, "message": str(exc)})

        messages = []
        valid = True

        db.session.execute(text("INSERT INTO MCMORevisi (OldAppl_No, NewAppl_No, First_Appl_No, Revisi, Revisi_note, CreateUser, CreateDate) VALUES (:old_appl, :new_appl, :first_appl_no, :revisi, :note, :username, GETDATE())"), {
            "old_appl": applno, "new_appl": applno_baru, "first_appl_no": first_appl_no,
            "revisi": str_revisi, "note": revisi_note, "username": username,
        })

        _clone_cafcont(applno, applno_baru, apless)
        _clone_cafdev(applno, applno_baru)

        eq_valid, cafequip_id_map = _clone_equipment(applno, applno_baru, messages)
        valid = valid and eq_valid
        _clone_cafequip_detail(applno, applno_baru, cafequip_id_map)
        _clone_cafequip_bpkbstatus(applno, applno_baru)

        supp_valid = _clone_clfsupp1(applno, applno_baru, fin_type, messages)
        valid = valid and supp_valid

        last_nourut = _clone_guarantors(applno, applno_baru, apless)

        customer_doc_rows = _clone_customer_document(applno, applno_baru, apless, last_nourut)

        _clone_cafstep(applno, applno_baru)

        ins_valid = _clone_insurance(applno, applno_baru, fin_type, messages)
        valid = valid and ins_valid

        _clone_disb(applno, applno_baru)

        sales_inactive_note = _check_sales_inactive(applno)

        komisi_valid = _clone_komisi(applno, applno_baru, messages)
        valid = valid and komisi_valid
        _clone_komisi_acc(applno, applno_baru)

        outs_valid = _clone_cust_outs(applno, applno_baru, messages)
        valid = valid and outs_valid

        _clone_survey(applno, applno_baru, lessee_tp)

        _clone_sik_checking_document(applno, applno_baru)
        bank_stmt_rows = _clone_bank_statement_document(applno, applno_baru)
        survey_file_rows = _clone_survey_file(applno, applno_baru, apless)

        _clone_remaining_simple_tables(applno, applno_baru)

        if not valid:
            db.session.rollback()
            return jsonify({"success": False, "message": "; ".join(messages)})

        db.session.commit()

        _copy_assets_and_finalize(applno, applno_baru, username, customer_doc_rows, bank_stmt_rows, survey_file_rows)

        message = f"CAM No {applno} is revised to New CAM No: {applno_baru}"
        if sales_inactive_note:
            message += f" \n{sales_inactive_note}"

        return jsonify({"success": True, "message": message, "new_appl_no": applno_baru})

    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("CAM revisi error")
        return jsonify({"success": False, "message": str(exc)}), 500