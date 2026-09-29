import os
from flask import Blueprint, request, session, redirect, url_for, send_from_directory, current_app

health_bp = Blueprint("health_bp", __name__)

@health_bp.route("/health")
def health_check():
    return {"status": "ok"}, 200

@health_bp.route("/maintenance")
def maintenance_page():
    static_dir = os.path.join(health_bp.root_path, "..", "static")
    return send_from_directory(static_dir, "maintenance.html")

@health_bp.route("/maintenance-bypass")
def maintenance_bypass():
    key = request.args.get("key")
    if key and key == current_app.config.get("MAINTENANCE_BYPASS_TOKEN"):
        session["maintenance_bypass"] = True
        session.permanent = True
        return redirect(url_for("auth.login"))
    return {"error": "Invalid or missing bypass key"}, 403