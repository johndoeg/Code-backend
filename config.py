import os
from datetime import timedelta
from urllib.parse import quote_plus
from dotenv import load_dotenv, dotenv_values

_DOTENV_PATH = os.environ.get("DOTENV_PATH") or os.path.join(os.getcwd(), ".env")

load_dotenv(_DOTENV_PATH)

_dotenv_cache = {"mtime": None, "values": {}}

def _live_dotenv_values():
    try:
        mtime = os.path.getmtime(_DOTENV_PATH)
    except OSError:
        return _dotenv_cache["values"]
    if mtime != _dotenv_cache["mtime"]:
        _dotenv_cache["values"] = dotenv_values(_DOTENV_PATH)
        _dotenv_cache["mtime"] = mtime
    return _dotenv_cache["values"]

def is_dev_login_bypass_enabled() -> bool:
    raw = _live_dotenv_values().get("DEV_LOGIN_BYPASS", "false")
    return (raw or "").strip().lower() in {"1", "true", "yes", "on"}

def _env(name, default=None):
    v = os.environ.get(name, default)
    return v.strip() if isinstance(v, str) else v

def _bool(name, default="false"):
    return (_env(name, default) or "").lower() in {"1", "true", "yes", "on"}

def _int(name, default):
    return int(_env(name, str(default)))

def _list(name, default=""):
    return [x.strip() for x in (_env(name, default) or "").split(",") if x.strip()]

def _odbc_val(v):
    return "{" + (v or "").replace("}", "}}") + "}"

_DB_SERVER = _env("DB_SERVER")
_DB_PORT = _env("DB_PORT")
_DB_DATABASE = _env("DB_DATABASE")
_DB_USERNAME = _env("DB_USERNAME")
_DB_PASSWORD = os.environ.get("DB_PASSWORD")
_DB_ENCRYPT = _bool("DB_ENCRYPT", "true")
_DB_TRUST_CERT = _bool("DB_TRUST_SERVER_CERT", "false")

_server = f"tcp:{_DB_SERVER},{_DB_PORT}" if _DB_PORT else f"tcp:{_DB_SERVER}"
_ODBC = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    f"SERVER={_server};"
    f"DATABASE={_odbc_val(_DB_DATABASE)};"
    f"UID={_odbc_val(_DB_USERNAME)};"
    f"PWD={_odbc_val(_DB_PASSWORD)};"
    f"Encrypt={'yes' if _DB_ENCRYPT else 'no'};"
    f"TrustServerCertificate={'yes' if _DB_TRUST_CERT else 'no'};"
    "MARS_Connection=Yes;"
)

class Config:
    ENV_NAME = "base"
    SECRET_KEY = os.environ.get("SECRET_KEY")
    DEBUG = False
    TESTING = False

    SQLALCHEMY_DATABASE_URI = "mssql+pyodbc:///?odbc_connect=" + quote_plus(_ODBC)
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": _int("DB_POOL_SIZE", 5),
        "max_overflow": _int("DB_MAX_OVERFLOW", 5),
        "connect_args": {"timeout": _int("DB_LOGIN_TIMEOUT", 10)},
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DEFAULT_MAX_FILE_SIZE_MB = 2
    MAX_CONTENT_LENGTH = _int("MAX_REQUEST_MB", 20) * 1024 * 1024

    # AWS S3
    AWS_ACCESS_KEY_ID = _env("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = _env("AWS_SECRET_ACCESS_KEY")
    AWS_REGION = _env("AWS_REGION", "ap-southeast-1")
    AWS_S3_BUCKET = _env("AWS_S3_BUCKET")
    REGION_NAME = _env("REGION_NAME")
    ENDPOINT_URL = _env("ENDPOINT_URL")

    # Directories
    CAM_UPLOAD_PATH = _env("CAM_UPLOAD_PATH")
    CAM_UPLOAD_BASE_PATH = _env("CAM_UPLOAD_BASE_PATH")
    SALES_UPLOAD_DIR = _env("SALES_UPLOAD_DIR")
    PPATK_UPLOAD_DIR = _env("PPATK_UPLOAD_DIR")
    UPLOAD_FOLDER = _env("UPLOAD_FOLDER")
    UPLOAD_FOLDER_BLACKLIST = _env("UPLOAD_FOLDER_BLACKLIST")
    UPLOAD_FOLDER_DEVIATION = _env("UPLOAD_FOLDER_DEVIATION")
    REDIS_URL = _env("REDIS_URL")

    # Glair
    GLAIR_USERNAME = _env("GLAIR_USERNAME")
    GLAIR_PASSWORD = os.environ.get("GLAIR_PASSWORD")
    GLAIR_API_KEY = _env("GLAIR_API_KEY")
    GLAIR_API_URL = _env("GLAIR_API_URL")
    GLAIR_ENDPOINT_QUALITIES = _env("GLAIR_ENDPOINT_QUALITIES")
    GLAIR_ENDPOINT_OCR = _env("GLAIR_ENDPOINT_OCR")
    GLAIR_ENDPOINT_DUKCAPIL = _env("GLAIR_ENDPOINT_DUKCAPIL")

    TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN")

    # H2H Insurance
    INSURANCE_H2H_URLS = {
        "01": _env("INSURANCE_H2H_URL_01", ""),
        "02": _env("INSURANCE_H2H_URL_02", ""),
    }
    INSURANCE_H2H_VERIFY_SSL = _bool("INSURANCE_H2H_VERIFY_SSL", "true")
    INSURANCE_H2H_CA_BUNDLE = _env("INSURANCE_H2H_CA_BUNDLE")
    INSURANCE_H2H_TIMEOUT = float(_env("INSURANCE_H2H_TIMEOUT", "30"))

    BCRYPT_LOG_ROUNDS = 13
    CACHE_TYPE = "simple"

    CORS_ORIGIN_WHITELIST = _list("FE_ORIGINS")

    API_VERSION = _env("API_VERSION", "v1")
    API_VERSIONS = _list("API_VERSIONS", "v1")
    DEPRECATED_VERSIONS = _list("DEPRECATED_VERSIONS")

    MAINTENANCE_MODE = _bool("MAINTENANCE_MODE")
    MAINTENANCE_MESSAGE = _env("MAINTENANCE_MESSAGE", "System under maintenance. Please try again later.")
    MAINTENANCE_RETRY_AFTER = _int("MAINTENANCE_RETRY_AFTER", 300)
    MAINTENANCE_WHITELIST = _list("MAINTENANCE_WHITELIST")
    MAINTENANCE_BYPASS_TOKEN = _env("MAINTENANCE_BYPASS_TOKEN")

    APP_NAME = _env("APP_NAME", "Genie Finance API")
    APP_VERSION = _env("APP_VERSION", "1.0.0")
    COMPANY_NAME = _env("COMPANY_NAME", "PT Genie Finance Indonesia")

    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=_int("SESSION_HOURS", 8))

class ProdConfig(Config):
    ENV_NAME = "production"

class DevConfig(Config):
    ENV_NAME = "development"
    DEBUG = True
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-only-not-for-production"
    SESSION_COOKIE_SECURE = False # http://localhost
    DEBUG_TB_INTERCEPT_REDIRECTS = False

class TestConfig(Config):
    ENV_NAME = "testing"
    TESTING = True
    DEBUG = True
    SECRET_KEY = "test-only-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    SESSION_COOKIE_SECURE = False
    MAINTENANCE_MODE = False

config = {
    "development": DevConfig,
    "production": ProdConfig,
    "testing": TestConfig,
    "default": ProdConfig,
}

def get_config():
    name = (_env("APP_ENV") or "production").lower()
    if name not in config:
        raise RuntimeError(f"Unknown APP_ENV '{name}'")
    return config[name]

_REQUIRED = (
    "SECRET_KEY", "DB_SERVER", "DB_DATABASE", "DB_USERNAME", "DB_PASSWORD",
    "MAINTENANCE_BYPASS_TOKEN", "REDIS_URL", "FE_ORIGINS", "SALES_UPLOAD_DIR",
)
_PLACEHOLDERS = {"1", "changeme", "fallback-dev-key", "change-this-in-production"}

def validate_config(app):
    if app.config.get("TESTING"):
        return

    problems = [
        k for k in _REQUIRED
        if not (os.environ.get(k) or "").strip()
        or os.environ[k].strip() in _PLACEHOLDERS
    ]
    if len(os.environ.get("SECRET_KEY", "")) < 32:
        problems.append("SECRET_KEY shorter than 32 chars")
    if not app.config["INSURANCE_H2H_VERIFY_SSL"] and not app.config["INSURANCE_H2H_CA_BUNDLE"]:
        problems.append("INSURANCE_H2H TLS verification disabled")

    strict = app.config.get("ENV_NAME") == "production"
    if strict and app.debug:
        raise RuntimeError("DEBUG must be off in production")
    if strict and _DB_TRUST_CERT:
        problems.append("DB_TRUST_SERVER_CERT=true in production")
    if strict and _bool("DEV_LOGIN_BYPASS", "false"):
        app.logger.warning("DEV_LOGIN_BYPASS=true is set in the environment but is ignored in production")

    if not problems:
        return
    msg = "Insecure/missing config: " + ", ".join(problems)
    if strict:
        raise RuntimeError(msg)
    app.logger.warning(msg)