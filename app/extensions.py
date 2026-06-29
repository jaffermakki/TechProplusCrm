from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

login_manager.login_view = "auth.pin_login"
login_manager.login_message = "Please sign in with your PIN to continue."
login_manager.login_message_category = "amber"
