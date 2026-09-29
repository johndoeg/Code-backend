from __future__ import annotations

from flask import Blueprint, jsonify, request

from app import db
from app.auth.decorators import login_required

from .subsidy_service import (
    SubsidyError,
    add_subsidy,
    delete_subsidy,
    fetch_grid,
    fetch_totals,
    reset_survey_fee_2,
)

subsidies_bp = Blueprint("financing_subsidies", __name__)

def _survey_fee_2_enabled(raw) -> bool:
    return str(raw if raw is not None else "").strip() != "0"

def _snapshot(applno: str, survey_fee_2_enabled: bool, survinc2):
    return {
        "grid": fetch_grid(applno, survey_fee_2_enabled),
        "totals": fetch_totals(applno, survinc2),
    }

@subsidies_bp.route("/subsidies", methods=["GET"])
@login_required
def list_subsidies():
    applno = request.args.get("applno", "").strip()
    if not applno:
        return jsonify({"error": "applno is required"}), 400
    enabled = _survey_fee_2_enabled(request.args.get("yesno"))
    return jsonify(_snapshot(applno, enabled, request.args.get("survinc2")))

@subsidies_bp.route("/subsidies", methods=["POST"])
@login_required
def create_subsidy():
    payload = request.get_json(silent=True) or {}
    applno = str(payload.get("applno", "")).strip()
    if not applno:
        return jsonify({"error": "applno is required"}), 400

    try:
        add_subsidy(applno, payload.get("dealer"), payload.get("paymentFor"), payload.get("amount"))
        db.session.commit()
    except SubsidyError as error:
        db.session.rollback()
        return jsonify({"error": error.message}), 422
    except Exception:
        db.session.rollback()
        raise

    enabled = _survey_fee_2_enabled(payload.get("yesno"))
    return jsonify(_snapshot(applno, enabled, payload.get("survinc2")))

@subsidies_bp.route("/subsidies", methods=["DELETE"])
@login_required
def remove_subsidy():
    payload = request.get_json(silent=True) or {}
    applno = str(payload.get("applno", "")).strip()
    if not applno:
        return jsonify({"error": "applno is required"}), 400

    try:
        delete_subsidy(
            applno,
            payload.get("subsidyType"),
            payload.get("amountType"),
            payload.get("amount"),
        )
        db.session.commit()
    except SubsidyError as error:
        db.session.rollback()
        return jsonify({"error": error.message}), 422
    except Exception:
        db.session.rollback()
        raise

    enabled = _survey_fee_2_enabled(payload.get("yesno"))
    return jsonify(_snapshot(applno, enabled, payload.get("survinc2")))

@subsidies_bp.route("/subsidies/reset-survey-fee2", methods=["POST"])
@login_required
def reset_subsidy_survey_fee_2():
    payload = request.get_json(silent=True) or {}
    applno = str(payload.get("applno", "")).strip()
    if not applno:
        return jsonify({"error": "applno is required"}), 400

    try:
        reset_survey_fee_2(applno)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    enabled = _survey_fee_2_enabled(payload.get("yesno"))
    return jsonify(_snapshot(applno, enabled, payload.get("survinc2")))