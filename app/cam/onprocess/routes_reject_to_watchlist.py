from flask import Blueprint, request, jsonify, current_app, session
from sqlalchemy import text

from app import db
from app.auth.decorators import login_required

cam_reject_watchlist_bp = Blueprint('cam_reject_watchlist', __name__, url_prefix='/CAM/RejectWatchlist')

@cam_reject_watchlist_bp.route('/init', methods=['GET'])
@login_required
def get_reject_watchlist_init():
    apless = request.args.get('apless', '')
    appl_no = request.args.get('applno', '')

    lessee = db.session.execute(text("""
        SELECT LESSEE_NM FROM CAFLESS WITH (NOLOCK) WHERE APLESS = :apless
    """), {"apless": apless}).mappings().first() or {}

    return jsonify({
        "applNo": appl_no,
        "lesseeName": lessee.get("LESSEE_NM") or "",
    })

def _next_watchlist_no():
    row = db.session.execute(text("""
        SELECT MAX(No) AS no FROM MCMOWatchList WITH (NOLOCK)
    """)).mappings().first()
    return int((row or {}).get("no") or 0) + 1

def _next_alias_id():
    row = db.session.execute(text("""
        SELECT COUNT(ID) AS id FROM MCMOWATCHLIST_ALIASNM WITH (NOLOCK)
    """)).mappings().first()
    return int((row or {}).get("id") or 0) + 1

def _insert_alias_if_needed(no, apless, existing_watchlist_no=None):
    if existing_watchlist_no is not None:
        already = db.session.execute(text("""
            SELECT TOP 1 1 FROM MCMOWATCHLIST_ALIASNM WITH (NOLOCK) WHERE No = :no
        """), {"no": existing_watchlist_no}).first()
        if already:
            return

    alias_row = db.session.execute(text("""
        SELECT ALIAS_NAME FROM CAFLESS WITH (NOLOCK) WHERE APLESS = :apless
    """), {"apless": apless}).mappings().first() or {}
    alias_name = (alias_row.get("ALIAS_NAME") or "").strip()
    if not alias_name:
        return

    db.session.execute(text("""
        INSERT INTO MCMOWATCHLIST_ALIASNM (NO, ID, NAME) VALUES (:no, :id, :name)
    """), {"no": no, "id": _next_alias_id(), "name": alias_name})

def _archive_reason_history(apless):
    existing = db.session.execute(text("""
        SELECT No, Reason, CreateDate, LastUpdate FROM MCMOWatchList WITH (NOLOCK)
        WHERE APLESS = :apless AND FlagDel = '0'
    """), {"apless": apless}).mappings().first()

    if not existing:
        return None

    reason_date = existing.get("LastUpdate") or existing.get("CreateDate")
    db.session.execute(text("""
        INSERT INTO MCMOWATCHLIST_REASONHISTORY (APLESS, FirstCreateDate, ReasonDate, Reason)
        VALUES (:apless, :first_create, :reason_date, :reason)
    """), {
        "apless": apless,
        "first_create": existing.get("CreateDate"),
        "reason_date": reason_date,
        "reason": existing.get("Reason"),
    })

    return existing

@cam_reject_watchlist_bp.route('/submit', methods=['POST'])
@login_required
def submit_reject_watchlist():
    body = request.get_json(force=True) or {}
    apless = body.get("apless") or ""
    appl_no = body.get("applno") or ""
    reason = (body.get("reason") or "").strip()
    username = session.get("username", "")

    if not reason:
        return jsonify({"success": False, "message": "Reason must not empty"})

    try:
        db.session.execute(text("""
            INSERT INTO mcmocamstatus
                (APPL_NO, APPR_STS, APPR_ID, APPR_DATE, COMMENT, APPR_ID_FROM, APPR_ID_TO, DownloadFlag, CreateDate)
            VALUES (:appl_no, 'RW', :username, GETDATE(), :reason, :username, '', 0, GETDATE())
        """), {"appl_no": appl_no, "username": username, "reason": reason})

        db.session.execute(text("""
            INSERT INTO MCMOCAMCOMPLETELIST (APPL_NO, AdmSts, AdmDate) VALUES (:appl_no, '0', GETDATE())
        """), {"appl_no": appl_no})

        lesse = db.session.execute(text("""
            SELECT LESSEE_TP FROM CAFLESS WITH (NOLOCK) WHERE APLESS = :apless
        """), {"apless": apless}).mappings().first() or {}
        lesse_tp = lesse.get("LESSEE_TP")

        no = _next_watchlist_no()

        if lesse_tp == "PR":
            existing = _archive_reason_history(apless)
            if existing:
                db.session.execute(text("""
                    UPDATE MCMOWatchList SET LastUser = :username, LastUpdate = GETDATE(), Reason = :reason
                    WHERE APLESS = :apless AND FlagDel = '0'
                """), {"username": username, "reason": reason, "apless": apless})
                _insert_alias_if_needed(no, apless, existing_watchlist_no=existing["No"])
            else:
                db.session.execute(text("""
                    INSERT INTO MCMOWatchList
                        (No, Name, Address, ID_Card, Phone, ContactPerson, ContactAddress,
                         CreateUser, CreateDate, Reason, DOB, Flag_type, apless, FlagDel,
                         Mother, Reason_Category, Customer_Type, Spouse_Name, NPWP)
                    SELECT :no, LESSEE_NM, ADDRESS1, ID_CARD, PHONE2, Contact, '',
                           :username, GETDATE(), :reason, TGLBIRTH, 'W', :apless, '0',
                           Mother, '10', LESSEE_TP, Spouse, NPWP
                    FROM cafless WITH (NOLOCK) WHERE APLESS = :apless
                """), {"no": no, "username": username, "reason": reason, "apless": apless})
                _insert_alias_if_needed(no, apless)
        else:
            existing = _archive_reason_history(apless)
            if existing:
                db.session.execute(text("""
                    UPDATE MCMOWatchList SET LastUser = :username, LastUpdate = GETDATE(), Reason = :reason
                    WHERE APLESS = :apless AND FlagDel = '0'
                """), {"username": username, "reason": reason, "apless": apless})
            else:
                db.session.execute(text("""
                    INSERT INTO MCMOWatchList
                        (No, Name, Address, ID_Card, Phone, ContactPerson, ContactAddress,
                         CreateUser, CreateDate, Reason, DOB, Flag_type, apless, FlagDel,
                         Reason_Category, Customer_Type, Spouse_Name, NPWP)
                    SELECT :no, LESSEE_NM, ADDRESS2, ID_CARD, PHONE1, Contact, '',
                           :username, GETDATE(), :reason, TGLBIRTH, 'W', :apless, '0',
                           '10', LESSEE_TP, Spouse, NPWP
                    FROM cafless WITH (NOLOCK) WHERE APLESS = :apless
                """), {"no": no, "username": username, "reason": reason, "apless": apless})

                db.session.execute(text("""
                    INSERT INTO MCMOWATCHLIST_REASONHISTORY (APLESS, FirstCreateDate, ReasonDate, Reason)
                    VALUES (:apless, GETDATE(), GETDATE(), :reason)
                """), {"apless": apless, "reason": reason})

        db.session.commit()
        return jsonify({"success": True, "message": "Reject to Watchlist success"})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("submit_reject_watchlist error (appl_no=%s)", appl_no)
        return jsonify({"success": False, "message": "Failed to reject to watchlist. Please try again."})