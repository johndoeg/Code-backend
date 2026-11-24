from flask import Blueprint, jsonify, request, current_app, session
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text

history_mrp_bp = Blueprint("history_mrp", __name__, url_prefix="/CAM/Others")

RESTRICTED_ROLES = ("CMO", "CMH", "BM")

def _show_appl_no() -> bool:
    return (session.get("accesslevel") or "").strip() not in RESTRICTED_ROLES

@history_mrp_bp.route("/HistoryMRP/brands")
@login_required
def get_brands():
    try:
        rows = db.session.execute(text("""
            SELECT BRAND, BRAND_NM FROM UMFBRAND WITH(NOLOCK)
            WHERE BRAND_NM NOT IN ('CBU', 'All Brand', 'Used Cars', 'Used Trucks')
            ORDER BY BRAND_NM
        """)).mappings().all()
        return jsonify([{"brand": r["BRAND"], "brand_nm": r["BRAND_NM"]} for r in rows])
    except Exception:
        current_app.logger.exception("Brands fetch error")
        return jsonify({"error": "Failed to load brands"}), 500

@history_mrp_bp.route("/HistoryMRP/models")
@login_required
def get_models():
    try:
        rows = db.session.execute(text("""
            SELECT MODEL, MODEL_NM FROM UMFMODEL WITH(NOLOCK)
            ORDER BY MODEL_NM
        """)).mappings().all()
        return jsonify([{"model": r["MODEL"], "model_nm": r["MODEL_NM"]} for r in rows])
    except Exception:
        current_app.logger.exception("Models fetch error")
        return jsonify({"error": "Failed to load models"}), 500

@history_mrp_bp.route("/HistoryMRP/types")
@login_required
def get_types():
  
    brand = request.args.get("brand", "").strip()
    model = request.args.get("model", "").strip()
    if not brand or not model:
        return jsonify([])
    try:
        rows = db.session.execute(text("""
            SELECT [TYPE], TYPE_NM FROM UMFTYPE WITH(NOLOCK)
            WHERE BRAND = :brand AND Model = :model AND isActive = 1
            ORDER BY TYPE_NM
        """), {"brand": brand, "model": model}).mappings().all()
        return jsonify([{"type": r["TYPE"], "type_nm": r["TYPE_NM"]} for r in rows])
    except Exception:
        current_app.logger.exception("Types fetch error")
        return jsonify({"error": "Failed to load types"}), 500

@history_mrp_bp.route("/HistoryMRP/data")
@login_required
def get_data():

    brand = request.args.get("brand", "").strip()
    model = request.args.get("model", "").strip()
    type_ = request.args.get("type",  "").strip()

    if not brand or not model:
        return jsonify({"error": "brand and model are required"}), 400

    sql = """
        SELECT
            ub.BRAND_NM,
            um.MODEL_NM,
            ut.TYPE_NM,
            uk.KAROSERI_DESC,
            ce.TAHUN,
            vdk.L_AMOUNT,
            vdk.ntf,
            vdk.EXECUTION,
            ubc.BRANCH_NAME,
            ce.APPL_NO,
            a.APLESS,
            a.Cons_Leas                                                                        AS fin_type,
            (CASE WHEN b.LESSEE_TP = 'PR' THEN '1' ELSE '2' END)                               AS ind_cor,
            (CASE WHEN a.HAS_GUARANTOR = '0' OR a.HAS_GUARANTOR IS NULL THEN '1' ELSE '2' END) AS guarantor,
            (CASE WHEN LTRIM(RTRIM(c.[CONDITION])) = 'NEW' THEN '2' ELSE '1' END)              AS new_car,
            (CASE WHEN c.SUPP = '999999' THEN '1' ELSE '0' END)                                AS c2c,
            a.PURPOFFINC,
            a.Cont_type
        FROM CLFEQUIP ce WITH(NOLOCK)
            LEFT JOIN UMFBRAND  ub  WITH(NOLOCK) ON ce.BRAND  = ub.BRAND
            LEFT JOIN UMFMODEL  um  WITH(NOLOCK) ON ce.MODEL  = um.MODEL
            LEFT JOIN UMFTYPE   ut  WITH(NOLOCK) ON ce.[TYPE] = ut.[TYPE]
                                                AND ce.BRAND  = ut.BRAND
                                                AND ce.MODEL  = ut.Model
            OUTER APPLY (
                SELECT TOP 1 KAROSERI_DESC
                FROM UMFKAROSERI WITH(NOLOCK)
                WHERE KAROSERI = ce.KAROSERI
            ) uk
            LEFT JOIN V_DataKredit vdk WITH(NOLOCK) ON vdk.LEASE_NO  = ce.LEASE_NO
            INNER JOIN UMFBRANCH   ubc WITH(NOLOCK) ON ubc.BRANCH_CD = ce.BRANCH_CD
            LEFT JOIN CAFCONT      a   WITH(NOLOCK) ON a.APPL_NO     = ce.APPL_NO
            LEFT JOIN CAFLESS      b   WITH(NOLOCK) ON a.APLESS      = b.APLESS
            OUTER APPLY (
                SELECT TOP 1 [CONDITION], SUPP
                FROM CAFEQUIP WITH(NOLOCK)
                WHERE APPL_NO = a.APPL_NO
                ORDER BY CAFEQUIP_ID DESC
            ) c
        WHERE ce.BRAND  = :brand
            AND ce.MODEL  = :model
            AND vdk.EXECUTION IS NOT NULL
            AND vdk.EXECUTION >= DATEADD(MONTH, -3,
                                    DATEADD(DAY, 1 - DAY(GETDATE()),
                                            CAST(GETDATE() AS DATE)))
            AND vdk.EXECUTION <  DATEADD(DAY, 1, CAST(GETDATE() AS DATE))
    """
    params: dict = {"brand": brand, "model": model}

    if type_:
        sql   += " AND ce.[TYPE] = :type_"
        params["type_"] = type_

    sql += " ORDER BY vdk.EXECUTION ASC"

    show_appl_no = _show_appl_no()

    try:
        rows = db.session.execute(text(sql), params).mappings().all()
        result = []
        for r in rows:
            ex = r["EXECUTION"]
            appl_no = r["APPL_NO"] or ""
            item = {
                "brand_nm":    r["BRAND_NM"]      or "",
                "model_nm":    r["MODEL_NM"]      or "",
                "type_nm":     r["TYPE_NM"]       or "",
                "karoseri":    r["KAROSERI_DESC"] or "",
                "tahun":       "" if r["TAHUN"] is None else str(r["TAHUN"]),
                "l_amount":    float(r["L_AMOUNT"] or 0),
                "net_finance": float(r["ntf"] or 0),
                "execution":   ex.strftime("%d-%b-%Y") if ex and hasattr(ex, "strftime") else (str(ex) if ex else ""),
                "branch_name": r["BRANCH_NAME"]   or "",
            }
            if show_appl_no:
                item["appl_no"] = appl_no
                item["cam_params"] = {
                    "id1":    r["fin_type"]   or "",
                    "id2":    r["ind_cor"]    or "",
                    "id3":    "1",
                    "id4":    r["guarantor"]  or "",
                    "id5":    r["new_car"]    or "",
                    "id6":    "Edit",
                    "id7":    r["PURPOFFINC"] or "",
                    "id8":    r["c2c"]        or "",
                    "id9":    r["Cont_type"]  or "",
                    "apless": r["APLESS"]     or "",
                    "applno": appl_no,
                }
            result.append(item)
        return jsonify({"rows": result, "show_appl_no": show_appl_no})
    except Exception:
        current_app.logger.exception("History MRP data error")
        return jsonify({"error": "Failed to load data"}), 500