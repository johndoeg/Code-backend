from flask import Blueprint, jsonify, request, session

from app.services.cam_creation_service import (
    CamCreationError,
    create_new_cam,
    get_dp_ratio_info,
    get_finance_type_options,
    get_portfolio_limit_check,
    get_purpose_of_finance_options,
)

cam_creation_bp = Blueprint("cam_creation", __name__, url_prefix="/cam/create")

@cam_creation_bp.get("/context")
def get_creation_context():
    lessee_tp = request.args.get("lessee_tp", "")
    limit_check = get_portfolio_limit_check()
    return jsonify(
        {
            "ind_cor": "1" if lessee_tp == "PR" else "2",
            "purpose_of_finance_options": get_purpose_of_finance_options(),
            "limit_check": {
                "total_mitsui_d": limit_check.total_mitsui_d,
                "total_mitsui_m": limit_check.total_mitsui_m,
                "limit_bisa": limit_check.limit_bisa,
                "blocks_fin_type_d": limit_check.ok_lanjut_d,
                "blocks_fin_type_m_or_w": limit_check.ok_lanjut_m,
            },
        }
    )

@cam_creation_bp.get("/finance-types")
def get_finance_types():
    purpoffinc = request.args.get("purpoffinc", "")
    lessee_tp = request.args.get("lessee_tp", "")
    return jsonify(get_finance_type_options(purpoffinc, lessee_tp))

@cam_creation_bp.get("/dp-info")
def get_dp_info():
    return jsonify(get_dp_ratio_info())

@cam_creation_bp.post("")
def post_create_new_cam():
    body = request.get_json(silent=True) or {}

    emp_id = session.get("emp_id", "")
    branch_cd = session.get("branchcode", "")

    try:
        result = create_new_cam(
            apless=body.get("apless", ""),
            prechecking_id=body.get("prechecking_id", ""),
            lessee_tp=body.get("lessee_tp", ""),
            purpoffinc=body.get("purpoffinc", ""),
            fin_type=body.get("fin_type", ""),
            guarantor=body.get("guarantor", ""),
            new_car=body.get("new_car", ""),
            repeat=body.get("repeat", "1"),
            public=body.get("public", ""),
            boa=body.get("boa", ""),
            bot=body.get("bot", ""),
            emp_id=emp_id,
            branch_cd=branch_cd,
        )
    except CamCreationError as exc:
        return jsonify({"errors": exc.field_errors}), 400

    return jsonify(result), 201