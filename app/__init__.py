from datetime import timedelta

from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flasgger import Swagger
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import text
from app.middleware.maintenance import MaintenanceMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from werkzeug.exceptions import HTTPException
from config import config
from app.utils.helpers.daily_log_handler import DailyFileHandler
from logging.handlers import TimedRotatingFileHandler

import logging
import os

db = SQLAlchemy()

def configure_logger(app: Flask) -> None:
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(module)s:%(lineno)d — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = DailyFileHandler(log_dir=log_dir, prefix="flask", backup_days=14)
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)

    app.logger.setLevel(logging.DEBUG)
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.propagate = False
    
def start_db_keepalive(app: Flask) -> None:
    scheduler = BackgroundScheduler()

    def ping():
        with app.app_context():
            try:
                db.session.execute(text("SELECT 1"))
                db.session.commit()
            except Exception:
                db.session.rollback()
                app.logger.warning("DB keep-alive ping failed", exc_info=True)

    scheduler.add_job(ping, "interval", minutes=2, id="db_keepalive", replace_existing=True)
    scheduler.start()

def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV")
        if not config_name:
            raise RuntimeError(
                "FLASK_ENV must be set explicitly to 'development', 'production', "
                "or 'testing' — refusing to guess a default."
            )

    app = Flask(__name__)
    app.config.from_object(config[config_name])
    app.secret_key = app.config["SECRET_KEY"]

    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("SESSION_COOKIE_SECURE", config_name == "production")
    app.config.setdefault("PERMANENT_SESSION_LIFETIME", timedelta(hours=8))

    CORS(app, origins=app.config.get("CORS_ORIGIN_WHITELIST"), supports_credentials=True)

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc):
        return jsonify({"success": False, "message": exc.description}), exc.code

    @app.errorhandler(Exception)
    def handle_unhandled_exception(exc):
        app.logger.exception("Unhandled exception")
        return jsonify({"success": False, "message": str(exc)}), 500

    db.init_app(app)
    
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        start_db_keepalive(app)     

    configure_logger(app)

    app.wsgi_app = MaintenanceMiddleware(app.wsgi_app, app)
    app.wsgi_app = SecurityHeadersMiddleware(app.wsgi_app)

    from .settings.blueprints import register_blueprints

    api_version = app.config.get("API_VERSION", "v1")
    register_blueprints(app, version=api_version)

    if config_name == "development":
        Swagger(app)

    @app.route("/")
    def home():
        return {"message": "Backend running!", "version": api_version}

    return app