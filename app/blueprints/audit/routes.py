from flask import Blueprint, render_template, request
from flask_login import login_required

from app.models.audit import AuditLog
from app.utils.decorators import role_required

bp = Blueprint("audit", __name__, url_prefix="/audit")


@bp.route("/")
@login_required
@role_required("owner", "manager")
def index():
    page = request.args.get("page", 1, type=int)
    pagination = AuditLog.query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=50)
    return render_template("audit/index.html", pagination=pagination)
