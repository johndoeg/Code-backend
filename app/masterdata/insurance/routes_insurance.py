from flask import Blueprint, jsonify, request, current_app, session
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text

insurance_master_bp = Blueprint("insurance_master", __name__, url_prefix="/MasterData")

@insurance_master_bp.route("/insurance")
@login_required
def get_insurance():
    page       = request.args.get("page",       1,  type=int)
    limit      = request.args.get("limit",      25, type=int)
    search_by  = request.args.get("search_by",  "1").strip()
    search_val = request.args.get("search_val", "").strip()
    akses      = session.get("akses", "9")

    try:
        params: dict = {}
        if search_val:
            if search_by == "1":
                where, params = "INS_CD = :exact_val", {"exact_val": search_val}
            else:
                where, params = "INS_CO LIKE :like_val", {"like_val": f"%{search_val}%"}
        else:
            where = "1=1"

        total = db.session.execute(text(
            f"SELECT COUNT(*) FROM UMFINSCD WITH(NOLOCK) WHERE {where}"
        ), params).scalar() or 0

        offset = (page - 1) * limit
        rows = db.session.execute(text(f"""
            SELECT INS_CD, INS_CO FROM UMFINSCD WITH(NOLOCK)
            WHERE {where} ORDER BY INS_CO
            OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
        """), {**params, "offset": offset, "limit": limit}).mappings().all()

        return jsonify({
            "data": [dict(r) for r in rows],
            "total": total, "page": page, "limit": limit, "akses": akses,
        })
    except Exception:
        current_app.logger.exception("Insurance list error")
        return jsonify({"data": [], "total": 0}), 500

@insurance_master_bp.route("/insurance/next-code")
@login_required
def get_next_ins_code():
    try:
        row = db.session.execute(text(
            "SELECT MAX(CONVERT(int, INS_CD))+1 AS n FROM UMFINSCD WITH(NOLOCK)"
        )).first()
        return jsonify({"next_code": str(row[0] or 1).zfill(2)})
    except Exception:
        current_app.logger.exception("Insurance next-code error")
        return jsonify({"error": "Failed"}), 500

@insurance_master_bp.route("/insurance/prem-options")
@login_required
def get_prem_options():
    try:
        areas = db.session.execute(text(
            "SELECT Code, Name FROM MSTINSURANCEAREA WITH(NOLOCK) ORDER BY Name"
        )).mappings().all()
        models = db.session.execute(text(
            "SELECT [VALUE] AS MODEL, DESC_VALUE AS MODEL_NM FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE = 'MODEL_ASURANSI' ORDER BY DESC_VALUE"
        )).mappings().all()
        coverages = db.session.execute(text(
            "SELECT CODE, NAME FROM mstTLOAR WITH(NOLOCK)"
        )).mappings().all()
        clauses = db.session.execute(text(
            "SELECT CODE, NAME FROM mstCLAUSE WITH(NOLOCK) ORDER BY NAME"
        )).mappings().all()
        return jsonify({
            "areas":     [{"value": r["Code"],  "label": r["Name"]}     for r in areas],
            "models":    [{"value": r["MODEL"], "label": r["MODEL_NM"]} for r in models],
            "coverages": [{"value": r["CODE"],  "label": r["NAME"]}     for r in coverages],
            "clauses":   [{"value": r["CODE"],  "label": r["NAME"]}     for r in clauses],
        })
    except Exception:
        current_app.logger.exception("Prem options error")
        return jsonify({"areas": [], "models": [], "coverages": [], "clauses": []}), 500

@insurance_master_bp.route("/insurance/<string:ins_cd>")
@login_required
def get_insurance_detail(ins_cd):
    try:
        row = db.session.execute(text("""
            SELECT INS_CD, INS_CO, Stamp_Duty, Stamp_DutyIns,
                   Address, City, Zipcode, Phone, Fax, Contact
            FROM UMFINSCD WITH(NOLOCK) WHERE INS_CD=:c
        """), {"c": ins_cd}).first()
        if not row:
            return jsonify({"error": "Not found"}), 404
        return jsonify({
            "ins_cd":        row[0] or "",
            "ins_co":        row[1] or "",
            "stamp_duty":    str(int(row[2])) if row[2] else "0",
            "stamp_dutyins": str(int(row[3])) if row[3] else "0",
            "address":       row[4] or "",
            "city":          row[5] or "",
            "zipcode":       row[6] or "",
            "phone":         row[7] or "",
            "fax":           row[8] or "",
            "contact":       row[9] or "",
        })
    except Exception:
        current_app.logger.exception("Insurance detail error")
        return jsonify({"error": "Failed"}), 500

@insurance_master_bp.route("/insurance", methods=["POST"])
@login_required
def create_insurance():
    d = request.get_json(force=True) or {}
    zipcode = d.get("zipcode", "").strip()
    if zipcode and len(zipcode) != 5:
        return jsonify({"success": False, "message": "Post Code not valid."}), 400
    try:
        sd  = d.get("stamp_duty",    "0").replace(",", "")
        sdi = d.get("stamp_dutyins", "0").replace(",", "")
        db.session.execute(text("""
            INSERT INTO UMFINSCD
                (INS_CD, INS_CO, Stamp_Duty, Stamp_DutyIns,
                 BRANCH_CD, Address, City, Zipcode, Phone, Fax, Contact,
                 COACODE, INSURANCE_AREA, isactive)
            VALUES (:cd,:co,:sd,:sdi,'10',:addr,:city,:zip,:phone,:fax,:contact,'','','1')
        """), {"cd":d.get("ins_cd",""),"co":d.get("ins_co",""),"sd":sd,"sdi":sdi,
               "addr":d.get("address",""),"city":d.get("city",""),"zip":zipcode,
               "phone":d.get("phone",""),"fax":d.get("fax",""),"contact":d.get("contact","")})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Insurance create error")
        return jsonify({"success": False, "message": "Save failed"}), 500

@insurance_master_bp.route("/insurance/<string:ins_cd>", methods=["PUT"])
@login_required
def update_insurance(ins_cd):
    d = request.get_json(force=True) or {}
    zipcode = d.get("zipcode", "").strip()
    if zipcode and len(zipcode) != 5:
        return jsonify({"success": False, "message": "Post Code not valid."}), 400
    try:
        sd  = d.get("stamp_duty",    "0").replace(",", "")
        sdi = d.get("stamp_dutyins", "0").replace(",", "")
        db.session.execute(text("""
            UPDATE UMFINSCD SET
                INS_CO=:co, Stamp_Duty=:sd, Stamp_DutyIns=:sdi,
                Address=:addr, City=:city, Zipcode=:zip,
                Phone=:phone, Fax=:fax, Contact=:contact
            WHERE INS_CD=:c
        """), {"c":ins_cd,"co":d.get("ins_co",""),"sd":sd,"sdi":sdi,
               "addr":d.get("address",""),"city":d.get("city",""),"zip":zipcode,
               "phone":d.get("phone",""),"fax":d.get("fax",""),"contact":d.get("contact","")})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Insurance update error")
        return jsonify({"success": False, "message": "Update failed"}), 500

@insurance_master_bp.route("/insurance/<string:ins_cd>", methods=["DELETE"])
@login_required
def delete_insurance(ins_cd):
    try:
        for tbl in ["CLFINSPRE","CLFINSTPL","CLFINSCLA",
                    "CLFINSPA","CLFINSSEAT","CLFINSLR"]:
            db.session.execute(
                text(f"DELETE FROM {tbl} WHERE INS_CD=:c"), {"c": ins_cd}
            )
        db.session.execute(text("DELETE FROM UMFINSCD WHERE INS_CD=:c"), {"c": ins_cd})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Insurance delete error")
        return jsonify({"success": False, "message": "Delete failed"}), 500

@insurance_master_bp.route("/insurance/<string:ins_cd>/premiums")
@login_required
def get_premiums(ins_cd):
    try:
        rows = db.session.execute(text("""
            SELECT a.[ID], a.INSURANCE_AREA, d.Name AS area_name,
                   a.MODEL, b.DESC_VALUE AS model_nm, a.L_AMOUNT,
                   a.TLO_AR, c.NAME AS tlo_name,
                   a.NET_PREMI, a.NET_REC_NEW, a.NET_REC_USED, a.PREMI
            FROM CLFINSPRE a WITH(NOLOCK)
                LEFT JOIN MSTCOMBO b WITH(NOLOCK)
                    ON a.MODEL=b.VALUE AND b.CAT_VALUE='MODEL_ASURANSI'
                LEFT JOIN mstTLOAR c WITH(NOLOCK) ON a.TLO_AR=c.CODE
                LEFT JOIN MSTINSURANCEAREA d WITH(NOLOCK) ON a.INSURANCE_AREA=d.Code
            WHERE a.INS_CD=:c
            ORDER BY d.Name, b.DESC_VALUE, a.L_AMOUNT
        """), {"c": ins_cd}).mappings().all()
        return jsonify({"data": [{
            "ID":            r["ID"],
            "insurance_area":r["INSURANCE_AREA"] or "",
            "area_name":     r["area_name"]       or "",
            "model":         r["MODEL"]            or "",
            "model_nm":      r["model_nm"]         or "",
            "l_amount":      str(r["L_AMOUNT"]  or "0"),
            "tlo_ar":        r["TLO_AR"]           or "",
            "tlo_name":      r["tlo_name"]         or "",
            "net_premi":     str(r["NET_PREMI"]   or ""),
            "net_rec_new":   str(r["NET_REC_NEW"] or ""),
            "net_rec_used":  str(r["NET_REC_USED"]or ""),
            "premi":         str(r["PREMI"]        or ""),
        } for r in rows]})
    except Exception:
        current_app.logger.exception("Premium list error")
        return jsonify({"data": []}), 500

@insurance_master_bp.route("/insurance/<string:ins_cd>/premiums", methods=["POST"])
@login_required
def add_premium(ins_cd):
    d = request.get_json(force=True) or {}
    try:
        db.session.execute(text("""
            INSERT INTO CLFINSPRE
                (INS_CD,INSURANCE_AREA,MODEL,L_AMOUNT,TLO_AR,
                 NET_PREMI,NET_REC_NEW,NET_REC_USED,PREMI)
            VALUES (:ins,:area,:model,:amt,:tlo,:np,:nrn,:nru,:pr)
        """), {"ins":ins_cd,"area":d.get("insurance_area",""),"model":d.get("model",""),
               "amt":d.get("l_amount","0").replace(",",""),"tlo":d.get("tlo_ar",""),
               "np":d.get("net_premi",""),"nrn":d.get("net_rec_new",""),
               "nru":d.get("net_rec_used",""),"pr":d.get("premi","")})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Premium add error")
        return jsonify({"success": False, "message": "Save failed"}), 500

@insurance_master_bp.route("/insurance/<string:ins_cd>/premiums/<int:prem_id>", methods=["PUT"])
@login_required
def update_premium(ins_cd, prem_id):
    d = request.get_json(force=True) or {}
    try:
        db.session.execute(text("""
            UPDATE CLFINSPRE
            SET L_AMOUNT=:amt, TLO_AR=:tlo,
                NET_PREMI=:np, NET_REC_NEW=:nrn, NET_REC_USED=:nru, PREMI=:pr
            WHERE INS_CD=:ins AND [ID]=:id
        """), {"ins":ins_cd,"id":prem_id,
               "amt":d.get("l_amount","0").replace(",",""),"tlo":d.get("tlo_ar",""),
               "np":d.get("net_premi",""),"nrn":d.get("net_rec_new",""),
               "nru":d.get("net_rec_used",""),"pr":d.get("premi","")})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Premium update error")
        return jsonify({"success": False, "message": "Update failed"}), 500

@insurance_master_bp.route("/insurance/<string:ins_cd>/premiums/<int:prem_id>", methods=["DELETE"])
@login_required
def delete_premium(ins_cd, prem_id):
    try:
        db.session.execute(text(
            "DELETE FROM CLFINSPRE WHERE INS_CD=:ins AND [ID]=:id"
        ), {"ins": ins_cd, "id": prem_id})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Premium delete error")
        return jsonify({"success": False, "message": "Delete failed"}), 500

@insurance_master_bp.route("/insurance/<string:ins_cd>/third-party")
@login_required
def get_third_party(ins_cd):
    try:
        rows = db.session.execute(text("""
            SELECT a.ID_INSTPL, a.MODEL, b.DESC_VALUE AS model_nm,
                   a.TPL_AMT, a.TPL_FEE, a.TPL_FEE2
            FROM CLFINSTPL a WITH(NOLOCK)
                LEFT JOIN MSTCOMBO b WITH(NOLOCK)
                    ON a.MODEL=b.VALUE AND b.CAT_VALUE='MODEL_ASURANSI'
            WHERE a.INS_CD=:c
            ORDER BY b.DESC_VALUE
        """), {"c": ins_cd}).mappings().all()
        return jsonify({"data": [{
            "ID_INSTPL": r["ID_INSTPL"],
            "model":     r["MODEL"]    or "",
            "model_nm":  r["model_nm"] or "",
            "tpl_amt":   str(r["TPL_AMT"]  or "0"),
            "tpl_fee":   str(r["TPL_FEE"]  or "0"),
            "tpl_fee2":  str(r["TPL_FEE2"] or "0"),
        } for r in rows]})
    except Exception:
        current_app.logger.exception("Third party list error")
        return jsonify({"data": []}), 500

@insurance_master_bp.route("/insurance/<string:ins_cd>/third-party", methods=["POST"])
@login_required
def add_third_party(ins_cd):
    d = request.get_json(force=True) or {}
    try:
        db.session.execute(text("""
            INSERT INTO CLFINSTPL (INS_CD, MODEL, TPL_AMT, TPL_FEE, TPL_FEE2)
            VALUES (:ins, :model, :amt, :fee, :fee2)
        """), {"ins":ins_cd,"model":d.get("model",""),
               "amt":d.get("tpl_amt","0").replace(",",""),
               "fee":d.get("tpl_fee","0").replace(",",""),
               "fee2":d.get("tpl_fee2","0").replace(",","")})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Third party add error")
        return jsonify({"success": False, "message": "Save failed"}), 500

@insurance_master_bp.route("/insurance/<string:ins_cd>/third-party/<int:tpl_id>",
                           methods=["PUT"])
@login_required
def update_third_party(ins_cd, tpl_id):
    d = request.get_json(force=True) or {}
    try:
        db.session.execute(text("""
            UPDATE CLFINSTPL SET TPL_AMT=:amt, TPL_FEE=:fee, TPL_FEE2=:fee2
            WHERE INS_CD=:ins AND [ID_INSTPL]=:id
        """), {"ins":ins_cd,"id":tpl_id,
               "amt":d.get("tpl_amt","0").replace(",",""),
               "fee":d.get("tpl_fee","0").replace(",",""),
               "fee2":d.get("tpl_fee2","0").replace(",","")})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Third party update error")
        return jsonify({"success": False, "message": "Update failed"}), 500

@insurance_master_bp.route("/insurance/<string:ins_cd>/third-party/<int:tpl_id>", methods=["DELETE"])
@login_required
def delete_third_party(ins_cd, tpl_id):
    try:
        db.session.execute(text(
            "DELETE FROM CLFINSTPL WHERE INS_CD=:ins AND [ID_INSTPL]=:id"
        ), {"ins": ins_cd, "id": tpl_id})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Third party delete error")
        return jsonify({"success": False, "message": "Delete failed"}), 500

@insurance_master_bp.route("/insurance/<string:ins_cd>/clauses")
@login_required
def get_clauses(ins_cd):
    try:
        rows = db.session.execute(text("""
            SELECT a.INSURANCE_AREA, d.NAME AS area_name,
                   a.CLAUSE, b.NAME AS clause_name,
                   a.TLO_AR, c.NAME AS tlo_name,
                   a.NET_PREMI, a.NET_REC_NEW, a.NET_REC_USED, a.PREMI
            FROM CLFINSCLA a WITH(NOLOCK)
                LEFT JOIN mstCLAUSE b WITH(NOLOCK) ON a.CLAUSE=b.CODE
                LEFT JOIN mstTLOAR c WITH(NOLOCK) ON a.TLO_AR=c.CODE
                LEFT JOIN MSTINSURANCEAREA d WITH(NOLOCK) ON a.Insurance_Area=d.Code
            WHERE a.INS_CD=:c
            ORDER BY d.NAME, b.NAME
        """), {"c": ins_cd}).mappings().all()
        return jsonify({"data": [{
            "insurance_area": r["INSURANCE_AREA"] or "",
            "area_name":      r["area_name"]       or "",
            "clause":         r["CLAUSE"]           or "",
            "clause_name":    r["clause_name"]      or "",
            "tlo_ar":         r["TLO_AR"]           or "",
            "tlo_name":       r["tlo_name"]         or "",
            "net_premi":      str(r["NET_PREMI"]   or ""),
            "net_rec_new":    str(r["NET_REC_NEW"] or ""),
            "net_rec_used":   str(r["NET_REC_USED"]or ""),
            "premi":          str(r["PREMI"]        or ""),
        } for r in rows]})
    except Exception:
        current_app.logger.exception("Clause list error")
        return jsonify({"data": []}), 500

@insurance_master_bp.route("/insurance/<string:ins_cd>/clauses", methods=["POST"])
@login_required
def add_clause(ins_cd):
    d = request.get_json(force=True) or {}
    try:
        db.session.execute(text("""
            INSERT INTO CLFINSCLA
                (INS_CD, INSURANCE_AREA, CLAUSE, TLO_AR,
                 NET_PREMI, NET_REC_NEW, NET_REC_USED, PREMI)
            VALUES (:ins,:area,:clause,:tlo,:np,:nrn,:nru,:pr)
        """), {"ins":ins_cd,"area":d.get("insurance_area",""),
               "clause":d.get("clause",""),"tlo":d.get("tlo_ar",""),
               "np":d.get("net_premi",""),"nrn":d.get("net_rec_new",""),
               "nru":d.get("net_rec_used",""),"pr":d.get("premi","")})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Clause add error")
        return jsonify({"success": False, "message": "Save failed"}), 500

@insurance_master_bp.route("/insurance/<string:ins_cd>/clauses/<string:area>/<string:clause>/<string:tlo_ar>", methods=["PUT"])
@login_required
def update_clause(ins_cd, area, clause, tlo_ar):
    d = request.get_json(force=True) or {}
    try:
        db.session.execute(text("""
            UPDATE CLFINSCLA SET
                NET_PREMI=:np, NET_REC_NEW=:nrn, NET_REC_USED=:nru, PREMI=:pr
            WHERE INS_CD=:ins AND Insurance_Area=:area
              AND CLAUSE=:clause AND TLO_AR=:tlo
        """), {"ins":ins_cd,"area":area,"clause":clause,"tlo":tlo_ar,
               "np":d.get("net_premi",""),"nrn":d.get("net_rec_new",""),
               "nru":d.get("net_rec_used",""),"pr":d.get("premi","")})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Clause update error")
        return jsonify({"success": False, "message": "Update failed"}), 500

@insurance_master_bp.route("/insurance/<string:ins_cd>/clauses/<string:area>/<string:clause>/<string:tlo_ar>", methods=["DELETE"])
@login_required
def delete_clause(ins_cd, area, clause, tlo_ar):
    try:
        db.session.execute(text("""
            DELETE FROM CLFINSCLA
            WHERE INS_CD=:ins AND Insurance_Area=:area
              AND CLAUSE=:clause AND TLO_AR=:tlo
        """), {"ins":ins_cd,"area":area,"clause":clause,"tlo":tlo_ar})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Clause delete error")
        return jsonify({"success": False, "message": "Delete failed"}), 500

@insurance_master_bp.route("/insurance/<string:ins_cd>/driver")
@login_required
def get_driver(ins_cd):
    try:
        rows = db.session.execute(text("""
            SELECT PA_AMOUNT, DRIVER_FEE_INS, DRIVER_FEE_CUST
            FROM CLFINSPA WITH(NOLOCK)
            WHERE INS_CD=:c ORDER BY PA_AMOUNT
        """), {"c": ins_cd}).mappings().all()
        return jsonify({"data": [{
            "pa_amount":       str(r["PA_AMOUNT"]       or "0"),
            "driver_fee_ins":  str(r["DRIVER_FEE_INS"]  or "0"),
            "driver_fee_cust": str(r["DRIVER_FEE_CUST"] or "0"),
        } for r in rows]})
    except Exception:
        current_app.logger.exception("Driver list error")
        return jsonify({"data": []}), 500

@insurance_master_bp.route("/insurance/<string:ins_cd>/driver", methods=["POST"])
@login_required
def add_driver(ins_cd):
    d = request.get_json(force=True) or {}
    try:
        db.session.execute(text("""
            INSERT INTO CLFINSPA (INS_CD, PA_AMOUNT, DRIVER_FEE_INS, DRIVER_FEE_CUST)
            VALUES (:ins, :pa, :fi, :fc)
        """), {"ins": ins_cd,
               "pa":  d.get("pa_amount",      "0").replace(",", ""),
               "fi":  d.get("driver_fee_ins", "0").replace(",", ""),
               "fc":  d.get("driver_fee_cust","0").replace(",", "")})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Driver add error")
        return jsonify({"success": False, "message": "Save failed"}), 500

@insurance_master_bp.route("/insurance/<string:ins_cd>/driver/<string:pa_amount>", methods=["PUT"])
@login_required
def update_driver(ins_cd, pa_amount):
    d = request.get_json(force=True) or {}
    try:
        db.session.execute(text("""
            UPDATE CLFINSPA
            SET DRIVER_FEE_INS=:fi, DRIVER_FEE_CUST=:fc
            WHERE INS_CD=:ins AND PA_AMOUNT=:pa
        """), {"ins": ins_cd, "pa": pa_amount,
               "fi": d.get("driver_fee_ins", "0").replace(",", ""),
               "fc": d.get("driver_fee_cust","0").replace(",", "")})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Driver update error")
        return jsonify({"success": False, "message": "Update failed"}), 500

@insurance_master_bp.route("/insurance/<string:ins_cd>/driver/<string:pa_amount>", methods=["DELETE"])
@login_required
def delete_driver(ins_cd, pa_amount):
    try:
        db.session.execute(text(
            "DELETE FROM CLFINSPA WHERE INS_CD=:ins AND PA_AMOUNT=:pa"
        ), {"ins": ins_cd, "pa": pa_amount})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Driver delete error")
        return jsonify({"success": False, "message": "Delete failed"}), 500

@insurance_master_bp.route("/insurance/<string:ins_cd>/passenger")
@login_required
def get_passenger(ins_cd):
    try:
        rows = db.session.execute(text("""
            SELECT SEAT_AMOUNT, SEAT, SEAT_FEE_INS, SEAT_FEE_CUST
            FROM CLFINSSEAT WITH(NOLOCK)
            WHERE INS_CD=:c ORDER BY SEAT_AMOUNT
        """), {"c": ins_cd}).mappings().all()
        return jsonify({"data": [{
            "seat_amount":  str(r["SEAT_AMOUNT"]  or "0"),
            "seat":         str(r["SEAT"]          or ""),
            "seat_fee_ins": str(r["SEAT_FEE_INS"]  or "0"),
            "seat_fee_cust":str(r["SEAT_FEE_CUST"] or "0"),
        } for r in rows]})
    except Exception:
        current_app.logger.exception("Passenger list error")
        return jsonify({"data": []}), 500

@insurance_master_bp.route("/insurance/<string:ins_cd>/passenger", methods=["POST"])
@login_required
def add_passenger(ins_cd):
    d = request.get_json(force=True) or {}
    try:
        db.session.execute(text("""
            INSERT INTO CLFINSSEAT
                (INS_CD, SEAT_AMOUNT, SEAT, SEAT_FEE_INS, SEAT_FEE_CUST)
            VALUES (:ins, :sa, :seat, :fi, :fc)
        """), {"ins":  ins_cd,
               "sa":   d.get("seat_amount",  "0").replace(",", ""),
               "seat": d.get("seat",         ""),
               "fi":   d.get("seat_fee_ins", "0").replace(",", ""),
               "fc":   d.get("seat_fee_cust","0").replace(",", "")})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Passenger add error")
        return jsonify({"success": False, "message": "Save failed"}), 500

@insurance_master_bp.route("/insurance/<string:ins_cd>/passenger/<string:seat_amount>/<string:seat>", methods=["PUT"])
@login_required
def update_passenger(ins_cd, seat_amount, seat):
    d = request.get_json(force=True) or {}
    try:
        db.session.execute(text("""
            UPDATE CLFINSSEAT
            SET SEAT_FEE_INS=:fi, SEAT_FEE_CUST=:fc
            WHERE INS_CD=:ins AND SEAT_AMOUNT=:sa AND SEAT=:seat
        """), {"ins": ins_cd, "sa": seat_amount, "seat": seat,
               "fi":  d.get("seat_fee_ins", "0").replace(",", ""),
               "fc":  d.get("seat_fee_cust","0").replace(",", "")})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Passenger update error")
        return jsonify({"success": False, "message": "Update failed"}), 500

@insurance_master_bp.route("/insurance/<string:ins_cd>/passenger/<string:seat_amount>/<string:seat>", methods=["DELETE"])
@login_required
def delete_passenger(ins_cd, seat_amount, seat):
    try:
        db.session.execute(text("""
            DELETE FROM CLFINSSEAT
            WHERE INS_CD=:ins AND SEAT_AMOUNT=:sa AND SEAT=:seat
        """), {"ins": ins_cd, "sa": seat_amount, "seat": seat})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Passenger delete error")
        return jsonify({"success": False, "message": "Delete failed"}), 500

@insurance_master_bp.route("/insurance/<string:ins_cd>/loading")
@login_required
def get_loading(ins_cd):
    try:
        rows = db.session.execute(text("""
            SELECT a.[ID], a.MODEL, b.DESC_VALUE AS model_nm, a.LR_AGE, a.LR_NEXT
            FROM CLFINSLR a WITH(NOLOCK)
                LEFT JOIN MSTCOMBO b WITH(NOLOCK)
                    ON a.MODEL=b.VALUE AND b.CAT_VALUE='MODEL_ASURANSI'
            WHERE a.INS_CD=:c
            ORDER BY b.DESC_VALUE
        """), {"c": ins_cd}).mappings().all()
        return jsonify({"data": [{
            "ID":       r["ID"],
            "model":    r["MODEL"]    or "",
            "model_nm": r["model_nm"] or "",
            "lr_age":   str(r["LR_AGE"]  or ""),
            "lr_next":  bool(r["LR_NEXT"]),
        } for r in rows]})
    except Exception:
        current_app.logger.exception("Loading list error")
        return jsonify({"data": []}), 500

@insurance_master_bp.route("/insurance/<string:ins_cd>/loading", methods=["POST"])
@login_required
def add_loading(ins_cd):
    d = request.get_json(force=True) or {}
    try:
        next_id = db.session.execute(text(
            "SELECT ISNULL(MAX(CONVERT(int, [ID])), 0)+1 FROM CLFINSLR WITH(NOLOCK)"
        )).scalar() or 1

        lr_next = 1 if d.get("lr_next") else 0
        db.session.execute(text("""
            INSERT INTO CLFINSLR ([ID], INS_CD, MODEL, LR_AGE, LR_NEXT)
            VALUES (:id, :ins, :model, :age, :next)
        """), {"id":    next_id,
               "ins":   ins_cd,
               "model": d.get("model",  ""),
               "age":   d.get("lr_age", ""),
               "next":  lr_next})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Loading add error")
        return jsonify({"success": False, "message": "Save failed"}), 500

@insurance_master_bp.route("/insurance/<string:ins_cd>/loading/<int:lr_id>", methods=["PUT"])
@login_required
def update_loading(ins_cd, lr_id):
    d = request.get_json(force=True) or {}
    try:
        lr_next = 1 if d.get("lr_next") else 0
        db.session.execute(text("""
            UPDATE CLFINSLR SET LR_AGE=:age, LR_NEXT=:next
            WHERE INS_CD=:ins AND [ID]=:id
        """), {"ins": ins_cd, "id": lr_id,
               "age":  d.get("lr_age", ""),
               "next": lr_next})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Loading update error")
        return jsonify({"success": False, "message": "Update failed"}), 500

@insurance_master_bp.route("/insurance/<string:ins_cd>/loading/<int:lr_id>", methods=["DELETE"])
@login_required
def delete_loading(ins_cd, lr_id):
    try:
        db.session.execute(text(
            "DELETE FROM CLFINSLR WHERE [ID]=:id AND INS_CD=:ins"
        ), {"id": lr_id, "ins": ins_cd})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Loading delete error")
        return jsonify({"success": False, "message": "Delete failed"}), 500