import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'fallback-dev-key'
    ENV = os.environ.get('FLASK_ENV', 'development')
    DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    
    DB_SERVER = os.environ.get('DB_SERVER')
    DB_DATABASE = os.environ.get('DB_DATABASE')
    DB_USERNAME = os.environ.get('DB_USERNAME')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
    
    SQLALCHEMY_DATABASE_URI = (
        f"mssql+pyodbc://{DB_USERNAME}:{DB_PASSWORD}@{DB_SERVER}"
        f"/{DB_DATABASE}?driver=ODBC+Driver+17+for+SQL+Server"
    )
    
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 10,
        "max_overflow": 20,
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    BCRYPT_LOG_ROUNDS = 13
    DEBUG_TB_INTERCEPT_REDIRECTS = False
    CACHE_TYPE = 'simple'
    
    CORS_ORIGIN_WHITELIST = [os.environ.get('REACT_DEV')] if os.environ.get('REACT_DEV') else []
    
    API_VERSION = os.environ.get('API_VERSION', 'v1')
    API_VERSIONS = os.environ.get('API_VERSIONS', 'v1').split(',')
    DEPRECATED_VERSIONS = os.environ.get('DEPRECATED_VERSIONS', '').split(',') if os.environ.get('DEPRECATED_VERSIONS') else []
    
    MAINTENANCE_MODE = os.environ.get('MAINTENANCE_MODE', 'false').lower() == 'true'
    MAINTENANCE_MESSAGE = os.environ.get('MAINTENANCE_MESSAGE', 'System under maintenance. Please try again later.')
    MAINTENANCE_RETRY_AFTER = int(os.environ.get('MAINTENANCE_RETRY_AFTER', '300'))  # seconds
    MAINTENANCE_WHITELIST = os.environ.get('MAINTENANCE_WHITELIST', '').split(',') if os.environ.get('MAINTENANCE_WHITELIST') else []
    MAINTENANCE_BYPASS_TOKEN = os.environ.get('MAINTENANCE_BYPASS_TOKEN', 'change-this-in-production')
    
    APP_NAME = os.environ.get('APP_NAME', 'Genie Finance API')
    APP_VERSION = os.environ.get('APP_VERSION', '1.0.0')
    COMPANY_NAME = os.environ.get('COMPANY_NAME', 'PT Genie Finance Indonesia')

class ProdConfig(Config):
    ENV = 'production'
    DEBUG = False

class DevConfig(Config):
    ENV = 'development'
    DEBUG = True

class TestConfig(Config):
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {}
    MAINTENANCE_MODE = False

config = {
    'development': DevConfig,
    'production': ProdConfig,
    'testing': TestConfig,
    'default': DevConfig,
}