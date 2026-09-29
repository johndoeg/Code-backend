from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import text

from app import db
from app.auth.decorators import login_required
from app.utils.helpers.financial_formulas_ext import split_pipe, step_rental
from app.utils.helpers.php_compat import money_input, php_float, php_int, php_str

calculation_bp = Blueprint("financing_calculation", __name__)

DEFAULT_CURRENCY = "IDR"
DEFAULT_ROUNDING = 1

def _rounding_for(curr_code: str):
    row = db.session.execute(
        text("SELECT ROUNDING FROM UMFCURR WITH (NOLOCK) WHERE CURR_CODE = :curr_code"),
        {"curr_code": curr_code},
    ).fetchone()
    if row is None or row.ROUNDING is None:
        return DEFAULT_ROUNDING
    return row.ROUNDING

@calculation_bp.route("/agency-fee", methods=["GET"])
@login_required
def agency_fee():
    agent = php_str(request.args.get("agent"))
    row = db.session.execute(
        text("SELECT Agency_Fee FROM umf_agency WITH (NOLOCK) WHERE Agency_nm = :agent"),
        {"agent": agent},
    ).fetchone()
    if row is None or row.Agency_Fee is None:
        return jsonify({"fee": None, "feeText": ""})
    fee = php_float(row.Agency_Fee)
    return jsonify({"fee": fee, "feeText": php_str(row.Agency_Fee)})

@calculation_bp.route("/commission-flag", methods=["POST"])
@login_required
def set_commission_flag():
    payload = request.get_json(silent=True) or {}
    apless = php_str(payload.get("apless"))
    applno = php_str(payload.get("applno"))
    yesno = php_str(payload.get("yesno"))
    fee = payload.get("fee")

    if not apless or not applno:
        return jsonify({"error": "apless and applno are required"}), 400

    keys = {"applno": applno, "apless": apless}

    try:
        if yesno == "0":
            db.session.execute(
                text("UPDATE CAFCONT SET FLAGCOM = :yesno WHERE APPL_NO = :applno AND APLESS = :apless"),
                {**keys, "yesno": yesno},
            )
        elif php_str(fee) in ("", "0"):
            db.session.execute(
                text("UPDATE CAFCONT SET FLAGCOM = NULL WHERE APPL_NO = :applno AND APLESS = :apless"),
                keys,
            )
        else:
            db.session.execute(
                text("UPDATE CAFCONT SET FLAGCOM = :yesno WHERE APPL_NO = :applno AND APLESS = :apless"),
                {**keys, "yesno": yesno},
            )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify({"success": True})

@calculation_bp.route("/step-rental-last-payment", methods=["POST"])
@login_required
def step_rental_last_payment():
    payload = request.get_json(silent=True) or {}

    total_steps = php_int(payload.get("totalSteps"))
    no_step = total_steps - 1
    if no_step < 0:
        return jsonify({"error": "totalSteps must be at least 1"}), 422

    rentals = [money_input(value) for value in split_pipe(payload.get("rentals"))]
    months = [php_float(value) for value in split_pipe(payload.get("months"))]

    pay_cycle = php_float(payload.get("payCycle")) or 1
    curr_code = php_str(payload.get("currCode")) or DEFAULT_CURRENCY

    result = step_rental(
        no_step=no_step,
        rental_steps=rentals,
        tot_net_finance=money_input(payload.get("totalNetFinance")),
        months=months,
        decl_rate=php_float(payload.get("declRate")),
        mlci_decl=php_float(payload.get("mlciDecl")),
        adv_arr=php_str(payload.get("advArr")),
        pay_cycle=pay_cycle,
        rounding=_rounding_for(curr_code),
        mlci_fallback_to_rental=True,
        install=payload.get("installment"),
    )

    return jsonify(
        {
            "lastStepSellingRental": result.last_payment or "",
            "lastStepBaseRental": result.last_payment_mlci or "",
            "curValue": result.cur_value,
        }
    )