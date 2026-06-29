import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")

    _db_url = os.environ.get("DATABASE_URL", "sqlite:///" + os.path.join(basedir, "instance", "techpro.db"))
    # Some providers (Render's own managed Postgres, old Heroku-style URLs) hand out
    # connection strings starting with "postgres://" - SQLAlchemy 1.4+ requires
    # "postgresql://" and raises on the old scheme. Neon already gives the correct
    # scheme, but this guards against any provider that doesn't.
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    # pool_pre_ping avoids "server closed the connection unexpectedly" errors against a
    # remote DB that may idle-disconnect (e.g. Neon's scale-to-zero). pool_recycle keeps
    # connections fresh. Keep the pool small per shop location - if multiple shop
    # computers each run this app against one shared cloud Postgres, every location's
    # pool adds up against the database's total connection limit, so there's no reason
    # to keep many idle connections open per location.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "pool_size": int(os.environ.get("DB_POOL_SIZE", "5")),
        "max_overflow": int(os.environ.get("DB_MAX_OVERFLOW", "5")),
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    WTF_CSRF_ENABLED = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)

    SHOP_NAME_DEFAULT = os.environ.get("SHOP_NAME", "Tech-Pro+ Repairs")
    SHOP_PROVINCE_DEFAULT = os.environ.get("SHOP_PROVINCE", "ON")
    SHOP_CURRENCY_DEFAULT = os.environ.get("SHOP_CURRENCY", "$")

    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER", "")

    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_FROM = os.environ.get("SMTP_FROM", "")


class DevConfig(Config):
    DEBUG = True


class ProdConfig(Config):
    DEBUG = False


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


config_by_name = {
    "development": DevConfig,
    "production": ProdConfig,
    "testing": TestConfig,
}
