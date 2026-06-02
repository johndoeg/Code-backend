from flask import Blueprint, jsonify, request, current_app, session
from app import db
from sqlalchemy import text
from datetime import datetime, timezone, timedelta

group_bp = Blueprint('group', __name__, url_prefix='/MasterData')

WIB = timezone(timedelta(hours=7))

def now_wib() -> str:
    return datetime.now(WIB).strftime('%Y-%m-%d %H:%M:%S')

@group_bp.route('/api/group')
def get_group():
    page       = request.args.get('page', 1, type=int)
    limit      = request.args.get('limit', 25, type=int)
    search_by  = request.args.get('search_by', '').strip()
    search_val = request.args.get('search_val', '').strip()

    try:
        if search_val:
            if search_by == '1':
                where_clause = "FLGDEL = '0' AND GrpCode LIKE :search_val"
                params = {"search_val": search_val}
            elif search_by == '2':
                where_clause = "FLGDEL = '0' AND GrpName LIKE :search_val"
                params = {"search_val": f"%{search_val}%"}
            else:
                where_clause = "FLGDEL = '0'"
                params = {}
        else:
            where_clause = "FLGDEL = '0'"
            params = {}

        total = db.session.execute(
            text(f"SELECT COUNT(*) as total FROM CLFGROUP WITH(NOLOCK) WHERE {where_clause}"),
            params
        ).fetchone().total

        offset = (page - 1) * limit
        result = db.session.execute(text(f"""
            SELECT
                GrpCode,
                GrpName
            FROM CLFGROUP WITH(NOLOCK)
            WHERE {where_clause}
            ORDER BY GrpCode
            OFFSET :offset ROWS
            FETCH NEXT :limit ROWS ONLY
        """), {**params, "offset": offset, "limit": limit})

        data = [
            {"GrpCode": row.GrpCode or "", "GrpName": row.GrpName or ""}
            for row in result.fetchall()
        ]

        return jsonify({
            "data":  data,
            "total": total,
            "page":  page,
            "limit": limit,
            "akses": session.get("accesslevel", "")
        })

    except Exception as e:
        current_app.logger.exception("Group list error")
        return jsonify({"data": [], "total": 0, "error": str(e)}), 500

@group_bp.route('/api/group/next-code')
def get_next_group_code():
    try:
        result = db.session.execute(
            text("SELECT ISNULL(MAX(CAST(GrpCode AS NUMERIC)), 0) + 1 AS GrpCode FROM CLFGROUP WITH(NOLOCK)")
        ).fetchone()
        next_code = str(int(result.GrpCode)).zfill(3)
        return jsonify({"next_code": next_code})
    except Exception as e:
        current_app.logger.exception("Next group code error")
        return jsonify({"error": str(e)}), 500


@group_bp.route('/api/group/sipp-options')
def get_sipp_options():
    try:
        result = db.session.execute(
            text("SELECT GROUPCODELBPP, GROUPCODEDESC FROM MSTLBPPGROUPCODE WITH(NOLOCK) ORDER BY GROUPCODELBPP")
        )
        return jsonify({
            "data": [{"value": r.GROUPCODELBPP, "label": r.GROUPCODEDESC} for r in result.fetchall()]
        })
    except Exception as e:
        current_app.logger.exception("SIPP options error")
        return jsonify({"data": [], "error": str(e)}), 500


@group_bp.route('/api/group/slik-options')
def get_slik_options():
    try:
        result = db.session.execute(
            text("SELECT SlikGroupCode, SlikGroupDesc FROM MstSlikGroupCode WITH(NOLOCK) ORDER BY SlikGroupCode")
        )
        return jsonify({
            "data": [{"value": r.SlikGroupCode, "label": r.SlikGroupDesc} for r in result.fetchall()]
        })
    except Exception as e:
        current_app.logger.exception("SLIK options error")
        return jsonify({"data": [], "error": str(e)}), 500


@group_bp.route('/api/group', methods=['POST'])
def save_group():
    data         = request.get_json()
    grpcode      = (data.get('grpcode')      or '').strip()
    grpname      = (data.get('grpname')      or '').strip()
    grpdesc      = (data.get('grpdesc')      or '').strip()
    grptype      = (data.get('grptype')      or '').strip()
    grppasscode  = (data.get('grppasscode')  or '').strip()
    slikgroupcode = (data.get('slikgroupcode') or '').strip()
    username     = session.get('username', '')

    errors = []
    if not grpname:
        errors.append("Group Name must not be empty")
    if not grpdesc:
        errors.append("Group Description must not be empty")
    if not grptype:
        errors.append("Group Type must not be empty")
    if errors:
        return jsonify({"success": False, "message": errors}), 400

    try:
        db.session.execute(text("""
            INSERT INTO CLFGROUP
                (GrpCode, GrpName, GrpDesc, GrpType, INPUT_DT, UPDATE_BY, FLGDEL, GROUPCODELBPP, SlikGroupCode)
            VALUES
                (:grpcode, :grpname, :grpdesc, :grptype, :input_dt, :update_by, '0', :grppasscode, :slikgroupcode)
        """), {
            "grpcode":       grpcode,
            "grpname":       grpname,
            "grpdesc":       grpdesc,
            "grptype":       grptype,
            "input_dt":      now_wib(),
            "update_by":     username,
            "grppasscode":   grppasscode,
            "slikgroupcode": slikgroupcode,
        })
        db.session.commit()
        return jsonify({"success": True, "message": "Successful"})

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Group save error")
        return jsonify({"success": False, "message": "Failed", "error": str(e)}), 500


@group_bp.route('/api/group/<string:grpcode>', methods=['DELETE'])
def delete_group(grpcode):
    
    username = session.get('username', '')
    try:
        db.session.execute(text("""
            UPDATE CLFGROUP
            SET FLGDEL = '1', INPUT_DT = :dt, UPDATE_BY = :user
            WHERE GrpCode = :code AND FLGDEL = '0'
        """), {"dt": now_wib(), "user": username, "code": grpcode})

        db.session.execute(text("""
            UPDATE CAFLESS SET GrpCode = '' WHERE GrpCode = :code
        """), {"code": grpcode})

        db.session.commit()
        return jsonify({"success": True, "message": "Successful"})

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Group delete error")
        return jsonify({"success": False, "message": "Failed", "error": str(e)}), 500