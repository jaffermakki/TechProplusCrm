import os
from flask import Flask

from app.config import config_by_name
from app.extensions import db, migrate, login_manager, csrf


def create_app(config_name=None):
    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_by_name[config_name])

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.models.staff import Staff

    @login_manager.user_loader
    def load_user(user_id):
        return Staff.query.get(int(user_id))

    _register_blueprints(app)
    _register_template_helpers(app)
    _register_error_handlers(app)

    return app


def _register_blueprints(app):
    from app.blueprints.auth.routes import bp as auth_bp
    from app.blueprints.dashboard.routes import bp as dashboard_bp
    from app.blueprints.pos.routes import bp as pos_bp
    from app.blueprints.repairs.routes import bp as repairs_bp
    from app.blueprints.inventory.routes import bp as inventory_bp
    from app.blueprints.customers.routes import bp as customers_bp
    from app.blueprints.reports.routes import bp as reports_bp
    from app.blueprints.cashup.routes import bp as cashup_bp
    from app.blueprints.refunds.routes import bp as refunds_bp
    from app.blueprints.staff.routes import bp as staff_bp
    from app.blueprints.audit.routes import bp as audit_bp
    from app.blueprints.settings.routes import bp as settings_bp
    from app.blueprints.api.routes import bp as api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(pos_bp)
    app.register_blueprint(repairs_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(cashup_bp)
    app.register_blueprint(refunds_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(api_bp)


def _register_template_helpers(app):
    from app.utils.formatting import fmt_money, fmt_date, fmt_datetime
    from app.models.settings import ShopSettings
    from app.models.repair import STATUS_LABELS, STATUS_ORDER

    @app.context_processor
    def inject_globals():
        try:
            settings = ShopSettings.get()
        except Exception:
            settings = None
        return {
            "shop_settings": settings,
            "STATUS_LABELS": STATUS_LABELS,
            "STATUS_ORDER": STATUS_ORDER,
        }

    app.jinja_env.filters["money"] = lambda v: fmt_money(v, app_currency())
    app.jinja_env.filters["date"] = fmt_date
    app.jinja_env.filters["datetime"] = fmt_datetime


def app_currency():
    from app.models.settings import ShopSettings

    try:
        return ShopSettings.get().currency
    except Exception:
        return "$"


def _register_error_handlers(app):
    from flask import render_template

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500
