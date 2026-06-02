from flask import Blueprint, request, jsonify, session, current_app
from sqlalchemy import text
from app import db

auth_bp = Blueprint('auth', __name__)

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

        user_query = """
            SELECT 
                a.USERNAME, 
                a.EMPLOYEE_ID, 
                a.ACCESSCAM, 
                a.BRANCHCODE,
                b.NICKNAME AS branch_call 
            FROM APP_USRMST a WITH (NOLOCK)
            LEFT JOIN UMFBRANCH b WITH (NOLOCK) ON a.BRANCHCODE = b.BRANCH_CD
            WHERE a.USERNAME = :username AND a.RECSTATUS = 'A'
        """
        result = db.session.execute(db.text(user_query), {"username": username})
        user = result.fetchone()

        if not user:
            return jsonify({"message": "Invalid credentials"}), 401

        db_username, emp_id, accesscam, branchcode, branch_call = user

        if not emp_id:
            return jsonify({"message": "User has no employee ID"}), 403

        if not accesscam:
            return jsonify({"message": "Your Access Cam is still empty, please contact helpdesk"}), 403

        branch_nickname = None
        if branchcode:
            branch_query = "SELECT NICKNAME FROM UMFBRANCH WITH (NOLOCK) WHERE BRANCH_CD = :branchcode"
            branch_result = db.session.execute(db.text(branch_query), {"branchcode": branchcode})
            branch_row = branch_result.fetchone()
            if branch_row:
                branch_nickname = branch_row[0]

        session.clear()

        session['logged_in'] = True
        session['username'] = db_username
        session['accesslevel'] = accesscam
        session['emp_id'] = emp_id
        session['branchcode'] = branchcode
        session['branch_call'] = branch_nickname

        return jsonify({"message": "Login successful"}), 200

    except Exception as e:
        current_app.logger.exception("Login error")
        return jsonify({"message": "Internal server error"}), 500

@auth_bp.route('/user-info')
def user_info():
    if not session.get('logged_in'):
        return jsonify({"message": "Unauthorized"}), 401

    try:
        branch_cd = session.get('branchcode')
        employee_id = session.get('emp_id')

        if not branch_cd or not employee_id:
            return jsonify({
                "username": session.get('username', 'User'),
                "branch_name": "Unknown Branch"
            })

        query = """
            SELECT a.BRANCH_NAME, b.FULLNAME 
            FROM UMFBRANCH a 
            INNER JOIN APP_USRMST b ON a.BRANCH_CD = b.BRANCHCODE 
            WHERE a.BRANCH_CD = :branch_cd 
            AND b.EMPLOYEE_ID = :employee_id
        """
        result = db.session.execute(
            db.text(query),
            {"branch_cd": branch_cd, "employee_id": employee_id}
        ).fetchone()

        if result:
            branch_name, fullname = result
            username = fullname or session.get('username', 'User')
        else:
            username = session.get('username', 'User')
            branch_name = session.get('branch_call', 'Unknown Branch')

        return jsonify({
            "username": username,
            "branch_name": branch_name
        })

    except Exception as e:
        current_app.logger.exception("User info fetch error")
        return jsonify({
            "username": session.get('username', 'User'),
            "branch_name": session.get('branch_call', 'Branch Info Unavailable')
        })
    
@auth_bp.route('/logout', methods=['POST'])
def logout():
    try:
        session.clear()
        return jsonify({"message": "Logged out successfully"}), 200
    except Exception as e:
        current_app.logger.exception("Logout error")
        return jsonify({"message": "Internal server error"}), 500