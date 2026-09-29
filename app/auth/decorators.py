from functools import wraps
from flask import session, jsonify, redirect, url_for, request
from app.auth.active_sessions import get_active_session

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        username = session.get("username")
        token = session.get("session_token")

        if not username or not token or get_active_session(username) != token:
            session.clear()
            if request.path.startswith("/api"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper