
from app import db
from flask import Blueprint, request, jsonify
from sqlalchemy import text
from app.auth.decorators import login_required

cam_combo_bp = Blueprint("cam_combo", __name__, url_prefix="/CAM/Combo")

@cam_combo_bp.route("/provinces-and-cities", methods=["GET"])
@login_required
def provinces_and_cities():
    rows = db.session.execute(text("""
        SELECT AREA_CD, Propinsi, Kabupaten FROM UMFAREA WITH(NOLOCK)
        WHERE FLAG_DEL = 0 ORDER BY Propinsi, Kabupaten
    """)).fetchall()
    return jsonify([
        {"value": r.AREA_CD, "label": f"{r.Propinsi} - {r.Kabupaten}"} for r in rows
    ])

@cam_combo_bp.route("/province-city", methods=["GET"])
@login_required
def province_city():
    area_cd = request.args.get("areaCd", "")
    row = db.session.execute(text("""
        SELECT Propinsi, Kabupaten FROM UMFAREA WITH(NOLOCK) WHERE AREA_CD = :area_cd AND FLAG_DEL = 0
    """), {"area_cd": area_cd}).fetchone()
    if not row:
        return jsonify({"province": "", "city": ""})
    return jsonify({"province": row.Propinsi, "city": row.Kabupaten})

@cam_combo_bp.route("/kecamatan", methods=["GET"])
@login_required
def kecamatan():
    area_cd = request.args.get("areaCd", "")
    rows = db.session.execute(text("""
        SELECT Kecamatan_CD, Desc_Name FROM MST_KECAMATAN WITH(NOLOCK)
        WHERE Area_CD = :area_cd ORDER BY Desc_Name
    """), {"area_cd": area_cd}).fetchall()
    return jsonify([{"value": r.Kecamatan_CD, "label": r.Desc_Name} for r in rows])

@cam_combo_bp.route("/kelurahan", methods=["GET"])
@login_required
def kelurahan():
    kecamatan_cd = request.args.get("kecamatanCd", "")
    rows = db.session.execute(text("""
        SELECT Kelurahan_CD, Desc_Name FROM MST_KELURAHAN WITH(NOLOCK)
        WHERE Kecamatan_CD = :kecamatan_cd ORDER BY Desc_Name
    """), {"kecamatan_cd": kecamatan_cd}).fetchall()
    return jsonify([{"value": r.Kelurahan_CD, "label": r.Desc_Name} for r in rows])

@cam_combo_bp.route("/business-type-detail", methods=["GET"])
@login_required
def business_type_detail():
    cust_type = request.args.get("custType", "")
    cat_map = {
        "EM": "PEP",
        "EN": "USAHA_HIGH_RISK",
        "CV": "USAHA_HIGH_RISK",
        "PT": "USAHA_HIGH_RISK",
        "CO": "KOPERASI_HIGH_RISK",
    }
    cat_value = cat_map.get(cust_type)
    if not cat_value:
        return jsonify([])
    rows = db.session.execute(text("""
        SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE = :cat ORDER BY DESC_VALUE
    """), {"cat": cat_value}).fetchall()
    return jsonify([{"value": r.VALUE, "label": r.DESC_VALUE} for r in rows])

@cam_combo_bp.route("/industry-codes", methods=["GET"])
@login_required
def industry_codes():
    level = request.args.get("level", "1")
    parent = request.args.get("parent", "")

    if level == "1":
        rows = db.session.execute(text("""
            SELECT Header, MLCI_Code, Descrip FROM MstIndustry_lbpp WITH(NOLOCK)
            WHERE MLCI_Code = '' ORDER BY Descrip
        """)).fetchall()
        return jsonify([{"value": r.Header, "label": r.Descrip} for r in rows])

    rows = db.session.execute(text("""
        SELECT MLCI_Code, Descrip, Header FROM MstIndustry_lbpp WITH(NOLOCK)
        WHERE Parent = :parent ORDER BY MLCI_Code
    """), {"parent": parent}).fetchall()
    return jsonify([
        {"value": f"{r.MLCI_Code}|{r.Header}", "label": f"{r.MLCI_Code}-{r.Descrip}"} for r in rows
    ])

@cam_combo_bp.route("/industry-code-path", methods=["GET"])
@login_required
def industry_code_path():
    leaf_code = request.args.get("code", "")
    if not leaf_code:
        return jsonify([])

    path = []
    current = db.session.execute(text("""
        SELECT MLCI_Code, Descrip, Header, Parent FROM MstIndustry_lbpp WITH(NOLOCK)
        WHERE MLCI_Code = :code
    """), {"code": leaf_code}).fetchone()

    while current:
        path.insert(0, {
            "value": f"{current.MLCI_Code}|{current.Header}" if current.MLCI_Code else current.Header,
            "label": f"{current.MLCI_Code}-{current.Descrip}" if current.MLCI_Code else current.Descrip,
        })
        if not current.Parent:
            break
        current = db.session.execute(text("""
            SELECT MLCI_Code, Descrip, Header, Parent FROM MstIndustry_lbpp WITH(NOLOCK)
            WHERE MLCI_Code = :p OR Header = :p
        """), {"p": current.Parent}).fetchone()

    return jsonify(path)