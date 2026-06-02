from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from app.middleware.maintenance import MaintenanceMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from config import config
import os

db = SQLAlchemy()
limiter = Limiter(key_func=get_remote_address)

def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "default")

    app = Flask(__name__)
    app.config.from_object(config[config_name])
    app.secret_key = app.config["SECRET_KEY"]

    CORS(app, origins=app.config.get("CORS_ORIGIN_WHITELIST"), supports_credentials=True)

    db.init_app(app)
    limiter.init_app(app)

    app.wsgi_app = MaintenanceMiddleware(app.wsgi_app)
    app.wsgi_app = SecurityHeadersMiddleware(app.wsgi_app)

    from .settings.blueprints import register_blueprints
    register_blueprints(app)

    @app.route("/")
    def home():
        return {"message": "Backend running!", "version": "v1"}

    return app