from flask import Blueprint, jsonify, request, current_app, session
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text
from datetime import datetime, timezone, timedelta

group_bp = Blueprint("group", __name__, url_prefix="/MasterData")

WIB = timezone(timedelta(hours=7))

def now_wib() -> str:
    return datetime.now(WIB).strftime("%Y-%m-%d %H:%M:%S")

@group_bp.route("/group")
@login_required
def get_group():
    page       = request.args.get("page",       1,  type=int)
    limit      = request.args.get("limit",      25, type=int)
    search_by  = request.args.get("search_by",  "").strip()
    search_val = request.args.get("search_val", "").strip()
    akses      = session.get("akses", "9")

    try:
        params: dict = {}
        if search_val and search_by:
            if search_by == "1":
                where  = "FLGDEL='0' AND GrpCode LIKE :exact_val"
                params = {"exact_val": search_val}
            elif search_by == "2":
                where  = "FLGDEL='0' AND GrpName LIKE :like_val"
                params = {"like_val": f"%{search_val}%"}
            else:
                where = "FLGDEL='0'"
        else:
            where = "FLGDEL='0'"

        total = db.session.execute(text(
            f"SELECT COUNT(*) FROM CLFGROUP WITH(NOLOCK) WHERE {where}"
        ), params).scalar() or 0

        offset = (page - 1) * limit
        rows = db.session.execute(text(f"""
            SELECT GrpCode, GrpName
            FROM CLFGROUP WITH(NOLOCK)
            WHERE {where}
            ORDER BY GrpCode
            OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
        """), {**params, "offset": offset, "limit": limit}).mappings().all()

        return jsonify({
            "data":  [dict(r) for r in rows],
            "total": total, "page": page, "limit": limit, "akses": akses,
        })
    except Exception:
        current_app.logger.exception("Group list error")
        return jsonify({"data": [], "total": 0}), 500

@group_bp.route("/group/next-code")
@login_required
def get_next_group_code():
    try:
        row = db.session.execute(text(
            "SELECT ISNULL(MAX(CAST(GrpCode AS NUMERIC)),0)+1 AS n FROM CLFGROUP WITH(NOLOCK)"
        )).first()
        return jsonify({"next_code": str(int(row[0])).zfill(3)})
    except Exception:
        current_app.logger.exception("Next group code error")
        return jsonify({"error": "Failed"}), 500

@group_bp.route("/group/sipp-options")
@login_required
def get_sipp_options():
    try:
        rows = db.session.execute(text(
            "SELECT GROUPCODELBPP, GROUPCODEDESC FROM MSTLBPPGROUPCODE WITH(NOLOCK) ORDER BY GROUPCODELBPP"
        )).mappings().all()
        return jsonify({"data": [{"value": r["GROUPCODELBPP"], "label": r["GROUPCODEDESC"]} for r in rows]})
    except Exception:
        current_app.logger.exception("SIPP options error")
        return jsonify({"data": []}), 500

@group_bp.route("/group/slik-options")
@login_required
def get_slik_options():
    try:
        rows = db.session.execute(text(
            "SELECT SlikGroupCode, SlikGroupDesc FROM MstSlikGroupCode WITH(NOLOCK) ORDER BY SlikGroupCode"
        )).mappings().all()
        return jsonify({"data": [{"value": r["SlikGroupCode"], "label": r["SlikGroupDesc"]} for r in rows]})
    except Exception:
        current_app.logger.exception("SLIK options error")
        return jsonify({"data": []}), 500

@group_bp.route("/group/customer-search")
@login_required
def customer_search():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify({"data": []})
    try:
        rows = db.session.execute(text("""
            SELECT TOP 30 APLESS, LESSEE_NM, ADDRESS1, ADDRESS2, LESSEE_TP, GrpCode
            FROM CAFLESS WITH(NOLOCK)
            WHERE LESSEE_NM LIKE :q
            ORDER BY LESSEE_NM
        """), {"q": f"%{q}%"}).mappings().all()
        return jsonify({"data": [{
            "APLESS":     r["APLESS"]     or "",
            "LESSEE_NM":  r["LESSEE_NM"]  or "",
            "address":    r["ADDRESS1"] if r["LESSEE_TP"] == "PR" else (r["ADDRESS2"] or ""),
            "GrpCode":    r["GrpCode"]    or "",
        } for r in rows]})
    except Exception:
        current_app.logger.exception("Customer search error")
        return jsonify({"data": []}), 500

@group_bp.route("/group/<string:grpcode>")
@login_required
def get_group_detail(grpcode):
    try:
        row = db.session.execute(text("""
            SELECT g.GrpCode, g.GrpName, g.GrpDesc, g.GrpType,
                   g.GROUPCODELBPP, s.GROUPCODEDESC AS sipp_desc,
                   g.SlikGroupCode,  k.SlikGroupDesc  AS slik_desc
            FROM CLFGROUP g WITH(NOLOCK)
                LEFT JOIN MSTLBPPGROUPCODE s WITH(NOLOCK)
                    ON g.GROUPCODELBPP = s.GROUPCODELBPP
                LEFT JOIN MstSlikGroupCode k WITH(NOLOCK)
                    ON g.SlikGroupCode = k.SlikGroupCode
            WHERE g.GrpCode=:c AND g.FLGDEL='0'
        """), {"c": grpcode}).first()
        if not row:
            return jsonify({"error": "Not found"}), 404
        return jsonify({
            "grpcode":   row[0] or "",
            "grpname":   row[1] or "",
            "grpdesc":   row[2] or "",
            "grptype":   row[3] or "",
            "sipp_code": row[4] or "",
            "sipp_desc": row[5] or "",
            "slik_code": row[6] or "",
            "slik_desc": row[7] or "",
        })
    except Exception:
        current_app.logger.exception("Group detail error")
        return jsonify({"error": "Failed"}), 500

@group_bp.route("/group", methods=["POST"])
@login_required
def save_group():
    d = request.get_json(force=True) or {}
    grpcode       = (d.get("grpcode")       or "").strip()
    grpname       = (d.get("grpname")       or "").strip()
    grpdesc       = (d.get("grpdesc")       or "").strip()
    grptype       = (d.get("grptype")       or "").strip()
    grppasscode   = (d.get("grppasscode")   or "").strip()
    slikgroupcode = (d.get("slikgroupcode") or "").strip()
    username      = session.get("username", "")

    errors = []
    if not grpname: errors.append("Group Name must not be empty.")
    if not grpdesc: errors.append("Group Description must not be empty.")
    if not grptype: errors.append("Group Type must not be empty.")
    if errors:
        return jsonify({"success": False, "message": " ".join(errors)}), 400

    try:
        db.session.execute(text("""
            INSERT INTO CLFGROUP
                (GrpCode, GrpName, GrpDesc, GrpType, INPUT_DT, UPDATE_BY,
                 FLGDEL, GROUPCODELBPP, SlikGroupCode)
            VALUES
                (:code,:name,:desc,:type,:dt,:user,'0',:sipp,:slik)
        """), {"code":grpcode,"name":grpname,"desc":grpdesc,"type":grptype,
               "dt":now_wib(),"user":username,"sipp":grppasscode,"slik":slikgroupcode})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Group save error")
        return jsonify({"success": False, "message": "Save failed"}), 500

@group_bp.route("/group/<string:grpcode>", methods=["PUT"])
@login_required
def update_group(grpcode):
    d = request.get_json(force=True) or {}
    grpname       = (d.get("grpname")       or "").strip()
    grpdesc       = (d.get("grpdesc")       or "").strip()
    grptype       = (d.get("grptype")       or "").strip()
    grppasscode   = (d.get("grppasscode")   or "").strip()
    slikgroupcode = (d.get("slikgroupcode") or "").strip()
    username      = session.get("username", "")

    errors = []
    if not grpname: errors.append("Group Name must not be empty.")
    if not grpdesc: errors.append("Group Description must not be empty.")
    if not grptype: errors.append("Group Type must not be empty.")
    if errors:
        return jsonify({"success": False, "message": " ".join(errors)}), 400

    try:
        db.session.execute(text("""
            UPDATE CLFGROUP SET
                GrpName=:name, GrpDesc=:desc, GrpType=:type,
                INPUT_DT=:dt, UPDATE_BY=:user, FLGDEL='0',
                GROUPCODELBPP=:sipp, SlikGroupCode=:slik
            WHERE GrpCode=:code AND FLGDEL='0'
        """), {"code":grpcode,"name":grpname,"desc":grpdesc,"type":grptype,
               "dt":now_wib(),"user":username,"sipp":grppasscode,"slik":slikgroupcode})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Group update error")
        return jsonify({"success": False, "message": "Update failed"}), 500

@group_bp.route("/group/<string:grpcode>", methods=["DELETE"])
@login_required
def delete_group(grpcode):
    username = session.get("username", "")
    try:
        db.session.execute(text("""
            UPDATE CLFGROUP SET FLGDEL='1', INPUT_DT=:dt, UPDATE_BY=:user
            WHERE GrpCode=:code AND FLGDEL='0'
        """), {"dt": now_wib(), "user": username, "code": grpcode})
        db.session.execute(text(
            "UPDATE CAFLESS SET GrpCode='' WHERE GrpCode=:code"
        ), {"code": grpcode})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Group delete error")
        return jsonify({"success": False, "message": "Delete failed"}), 500

@group_bp.route("/group/<string:grpcode>/members")
@login_required
def get_members(grpcode):
    page       = request.args.get("page",       1,  type=int)
    limit      = request.args.get("limit",      25, type=int)
    lessee_nm  = request.args.get("lessee_nm",  "").strip()
    akses      = session.get("akses", "9")

    try:
        params: dict = {"code": grpcode}
        name_filter = ""
        if lessee_nm:
            name_filter = "AND LESSEE_NM LIKE :nm"
            params["nm"] = f"%{lessee_nm}%"

        total = db.session.execute(text(
            f"SELECT COUNT(*) FROM CAFLESS WITH(NOLOCK) WHERE GrpCode=:code {name_filter}"
        ), params).scalar() or 0

        offset = (page - 1) * limit
        rows = db.session.execute(text(f"""
            SELECT APLESS, LESSEE_NM, ADDRESS1, ADDRESS2, LESSEE_TP
            FROM CAFLESS WITH(NOLOCK)
            WHERE GrpCode=:code {name_filter}
            ORDER BY LESSEE_NM
            OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
        """), {**params, "offset": offset, "limit": limit}).mappings().all()

        return jsonify({
            "data": [{
                "APLESS":    r["APLESS"]    or "",
                "LESSEE_NM": r["LESSEE_NM"] or "",
                "address":   r["ADDRESS1"] if r["LESSEE_TP"] == "PR"
                             else (r["ADDRESS2"] or ""),
            } for r in rows],
            "total": total, "page": page, "limit": limit, "akses": akses,
        })
    except Exception:
        current_app.logger.exception("Member list error")
        return jsonify({"data": [], "total": 0}), 500

@group_bp.route("/group/<string:grpcode>/members", methods=["POST"])
@login_required
def add_member(grpcode):
    d      = request.get_json(force=True) or {}
    apless = (d.get("apless") or "").strip()
    if not apless:
        return jsonify({"success": False, "message": "Customer is required."}), 400
    try:
        db.session.execute(text(
            "UPDATE CAFLESS SET GrpCode=:code WHERE APLESS=:apless"
        ), {"code": grpcode, "apless": apless})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Add member error")
        return jsonify({"success": False, "message": "Add failed"}), 500

@group_bp.route("/group/<string:grpcode>/members/<string:apless>", methods=["DELETE"])
@login_required
def remove_member(grpcode, apless):
    try:
        db.session.execute(text(
            "UPDATE CAFLESS SET GrpCode='' WHERE APLESS=:apless"
        ), {"apless": apless})
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Remove member error")
        return jsonify({"success": False, "message": "Remove failed"}), 500