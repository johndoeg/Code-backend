from app import db
from flask import Blueprint, request, jsonify, session, current_app
from datetime import datetime, timedelta
from config import is_dev_login_bypass_enabled
from app.auth.active_sessions import set_active_session, clear_active_session

import secrets
import requests
import threading
import uuid

auth_bp = Blueprint('auth', __name__)

PIN_LENGTH = 6
PIN_EXPIRY_MINUTES = 5
MAX_PIN_ATTEMPTS = 3
OTP_REQUEST_TYPE = 'CAM'

def _client_ip() -> str:
    return request.headers.get('X-Forwarded-For', request.remote_addr) or ''

def _get_audit_sid() -> str:
    sid = session.get('audit_sid')
    if not sid:
        sid = uuid.uuid4().hex
        session['audit_sid'] = sid
    return sid

def _insert_audit_log(user_id: str, event: str) -> None:
    app = current_app._get_current_object()
    ip = _client_ip()
    host = request.host or ""
    sid = _get_audit_sid()
    browser = (request.user_agent.string or "")[:255] if request.user_agent else ""
    waktu = datetime.now()

    def _write():
        with app.app_context():
            try:
                db.session.execute(db.text("""
                    INSERT INTO MCMOUSERAUDIT (USERID, WAKTU, [EVENT], USER_IP, SERVER_ADDR, SESSIONID, USER_BROWSER)
                    VALUES (:userid, :waktu, :event, :ip, :server_addr, :sessionid, :browser)
                """), {
                    "userid": user_id,
                    "waktu": waktu,
                    "event": event,
                    "ip": ip,
                    "server_addr": host,
                    "sessionid": sid,
                    "browser": browser,
                })
                db.session.commit()
            except Exception:
                db.session.rollback()
                app.logger.exception("Failed to write login audit log for %s", user_id)
            finally:
                db.session.remove()

    threading.Thread(target=_write, daemon=True).start()

def _send_telegram_pin(chat_id: str, pin: str, expires_in_minutes: int) -> bool:
    bot_token = current_app.config.get("TELEGRAM_BOT_TOKEN")
    if not bot_token or not chat_id:
        current_app.logger.error("Telegram send skipped: missing bot token or chat_id")
        return False

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": (
                    f"Your CAM login PIN is: {pin}\n"
                    f"This code expires in {expires_in_minutes} minute"
                    f"{'s' if expires_in_minutes != 1 else ''}."
                ),
            },
            timeout=10,
        )
        return resp.ok
    except Exception:
        current_app.logger.exception("Telegram send failed")
        return False

@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"message": "Invalid JSON"}), 400

        username = (data.get('username') or '').strip()
        password = (data.get('password') or '').strip()

        if not username or not password:
            return jsonify({"message": "Username and password required"}), 400

        dev_bypass = (
            current_app.config.get("ENV_NAME") != "production"
            and is_dev_login_bypass_enabled()
        )

        base_select = """
            SELECT
                a.USERNAME,
                a.EMPLOYEE_ID,
                a.ACCESSCAM,
                a.BRANCHCODE,
                b.NICKNAME    AS branch_call,
                c.TELEGRAMID  AS TELEGRAM_CHAT_ID,
                a.FULLNAME    AS FULL_NAME,
                b.BRANCH_NAME AS BRANCH_NAME
            FROM APP_USRMST a WITH (NOLOCK)
                LEFT JOIN UMFBRANCH b WITH (NOLOCK) ON a.BRANCHCODE = b.BRANCH_CD
                INNER JOIN EMPLOYEE_DATA c WITH (NOLOCK) ON a.EMPLOYEE_ID = c.EMPLOYEE_ID
            WHERE a.USERNAME   = :username
                AND a.RECSTATUS  = 'A'
        """

        if dev_bypass:
            user_query = base_select
            params = {"username": username}
            current_app.logger.warning(
                "DEV_LOGIN_BYPASS active - password check skipped for username=%s", username
            )
        else:
            user_query = base_select + "    AND a.PASSWORD   = CONVERT(VARCHAR(64), HASHBYTES('SHA2_256', :password), 2)\n"
            params = {"username": username, "password": password}

        result = db.session.execute(db.text(user_query), params)
        user = result.fetchone()

        if not user:
            _insert_audit_log(username, "Login failed")
            return jsonify({"message": "Username/Password incorrect"}), 401

        db_username, emp_id, accesscam, branchcode, branch_call, telegram_chat_id, full_name, branch_name = user

        if not emp_id:
            _insert_audit_log(username, "Login failed")
            return jsonify({"message": "User has no employee ID"}), 403

        if not accesscam:
            _insert_audit_log(db_username, "Your Access Cam is still empty, please contact helpdesk")
            return jsonify({
                "message": "Your Access Cam is still empty, please contact helpdesk"
            }), 403

        if not telegram_chat_id:
            _insert_audit_log(db_username, "Login failed - no Telegram chat ID on file")
            return jsonify({"message": "No Telegram account linked to this user. Please contact helpdesk."}), 403

        pin = str(secrets.randbelow(10 ** PIN_LENGTH)).zfill(PIN_LENGTH)
        now = datetime.now()
        id_no = str(db_username)

        otp_row = db.session.execute(db.text("""
            INSERT INTO Datalog..OTP (RequestType, RequestDt, Lessee_Tp, Id_No, Lessee_No, OTP)
            OUTPUT inserted.ID, inserted.ExpireDt
            VALUES (:request_type, :request_dt, :lessee_tp, :id_no, :lessee_no, :otp)
        """), {
            "request_type": OTP_REQUEST_TYPE,
            "request_dt": now,
            "lessee_tp": "",
            "id_no": id_no,
            "lessee_no": None,
            "otp": pin,
        }).fetchone()
        db.session.commit()

        otp_id, expiry_date = otp_row
        expires_in_seconds = int((expiry_date - now).total_seconds()) if expiry_date else PIN_EXPIRY_MINUTES * 60
        expires_in_minutes = max(1, round(expires_in_seconds / 60))

        if not _send_telegram_pin(telegram_chat_id, pin, expires_in_minutes):
            _insert_audit_log(db_username, "Login failed - Telegram send failed")
            return jsonify({"message": "Failed to send PIN via Telegram. Please try again."}), 500

        session['pending_username']     = db_username
        session['pending_emp_id']       = emp_id
        session['pending_id_no']        = id_no
        session['pending_accesscam']    = accesscam
        session['pending_branchcode']   = branchcode
        session['pending_branch_call']  = branch_call
        session['pending_fullname']     = full_name
        session['pending_branch_name']  = branch_name
        session['pending_otp_id']       = otp_id
        session['pending_pin_attempts'] = 0

        _insert_audit_log(db_username, "Login step 1 successful - PIN sent")

        return jsonify({
            "message": "PIN sent",
            "pin_required": True,
            "pin_length": PIN_LENGTH,
            "expires_in": expires_in_seconds,
        }), 200

    except Exception:
        current_app.logger.exception("Login error")
        return jsonify({"message": "Internal server error"}), 500

@auth_bp.route('/verify-pin', methods=['POST'])
def verify_pin():
    try:
        pending_username = session.get('pending_username')
        otp_id = session.get('pending_otp_id')
        id_no = session.get('pending_id_no')

        if not pending_username or not otp_id or not id_no:
            return jsonify({"message": "No login in progress. Please log in again."}), 400

        data = request.get_json()
        if not data:
            return jsonify({"message": "Invalid JSON"}), 400

        submitted_pin = (data.get('pin') or '').strip()
        if not submitted_pin or len(submitted_pin) != PIN_LENGTH:
            return jsonify({"message": f"Please enter the {PIN_LENGTH}-digit PIN"}), 400

        attempts = session.get('pending_pin_attempts', 0)
        if attempts >= MAX_PIN_ATTEMPTS:
            _insert_audit_log(pending_username, "Login failed - too many PIN attempts")
            session.clear()
            return jsonify({"message": "Too many incorrect attempts. Please log in again."}), 400

        row = db.session.execute(db.text("""
            SELECT TOP 1 ID, OTP, ExpireDt
            FROM Datalog..OTP
            WHERE ID          = :otp_id
                AND RequestType = :request_type
                AND Lessee_Tp   = ''
                AND Id_No       = :id_no
                AND Lessee_No IS NULL
        """), {"otp_id": otp_id, "request_type": OTP_REQUEST_TYPE, "id_no": id_no}).fetchone()

        if not row:
            return jsonify({"message": "No PIN found. Please log in again."}), 400

        _, stored_pin, expiry_date = row

        if expiry_date and datetime.now() > expiry_date:
            return jsonify({"message": "PIN has expired. Please log in again."}), 400

        if submitted_pin != stored_pin:
            session['pending_pin_attempts'] = attempts + 1
            _insert_audit_log(pending_username, "Login failed - incorrect PIN")
            return jsonify({"message": "Incorrect PIN"}), 401

        session['logged_in']    = True
        session['username']     = pending_username
        session['accesslevel']  = session.pop('pending_accesscam', None)
        session['emp_id']       = session.pop('pending_emp_id', None)
        session['branchcode']   = session.pop('pending_branchcode', None)
        session['branch_call']  = session.pop('pending_branch_call', None)
        session['fullname']     = session.pop('pending_fullname', None)
        session['branch_name']  = session.pop('pending_branch_name', None)
        session.pop('pending_username', None)
        session.pop('pending_id_no', None)
        session.pop('pending_otp_id', None)
        session.pop('pending_pin_attempts', None)

        token = uuid.uuid4().hex
        session['session_token'] = token
        set_active_session(pending_username, token)

        _insert_audit_log(pending_username, "Login")

        return jsonify({"message": "Login successful"}), 200

    except Exception:
        current_app.logger.exception("PIN verification error")
        return jsonify({"message": "Internal server error"}), 500

@auth_bp.route('/user-info')
def user_info():
    if not session.get('logged_in'):
        return jsonify({"authenticated": False}), 200

    if session.get('fullname') and session.get('branch_name'):
        return jsonify({
            "authenticated": True,
            "username": session['fullname'],
            "branch_name": session['branch_name'],
            "accesslevel": session.get('accesslevel'),
            "emp_id": session.get('emp_id'),
        })

    try:
        branch_cd   = session.get('branchcode')
        employee_id = session.get('emp_id')

        if not branch_cd or not employee_id:
            return jsonify({
                "authenticated": True,
                "username":    session.get('username', 'User'),
                "branch_name": "Unknown Branch",
                "accesslevel": session.get('accesslevel'),
                "emp_id": session.get('emp_id'),
            })

        query = """
            SELECT a.BRANCH_NAME, b.FULLNAME
            FROM UMFBRANCH a
                INNER JOIN APP_USRMST b ON a.BRANCH_CD = b.BRANCHCODE
            WHERE a.BRANCH_CD   = :branch_cd
              AND b.EMPLOYEE_ID = :employee_id
        """
        result = db.session.execute(
            db.text(query),
            {"branch_cd": branch_cd, "employee_id": employee_id},
        ).fetchone()

        if result:
            branch_name, fullname = result
            username = fullname or session.get('username', 'User')
            session['fullname'] = username
            session['branch_name'] = branch_name
        else:
            username    = session.get('username', 'User')
            branch_name = session.get('branch_call', 'Unknown Branch')

        return jsonify({
            "authenticated": True,
            "username": username,
            "branch_name": branch_name,
            "accesslevel": session.get('accesslevel'),
            "emp_id": session.get('emp_id'),
        })

    except Exception:
        current_app.logger.exception("User info fetch error")
        return jsonify({
            "authenticated": True,
            "username":    session.get('username', 'User'),
            "branch_name": session.get('branch_call', 'Branch Info Unavailable'),
            "accesslevel": session.get('accesslevel'),
            "emp_id": session.get('emp_id'),
        })

@auth_bp.route('/logout', methods=['POST'])
def logout():
    try:
        username = session.get('username')
        if username:
            clear_active_session(username)
            _insert_audit_log(username, "Logout")
        session.clear()
        return jsonify({"message": "Logged out successfully"}), 200
    except Exception:
        current_app.logger.exception("Logout error")
        return jsonify({"message": "Internal server error"}), 500