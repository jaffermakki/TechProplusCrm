from datetime import datetime
from app.extensions import db


class AuditLog(db.Model):
    """Append-only audit trail. The app's DB role should have no UPDATE/DELETE grant
    on this table in production - inserts only."""

    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=True)
    action = db.Column(db.String(80), nullable=False)
    detail = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @classmethod
    def record(cls, action, detail="", staff_id=None):
        from flask_login import current_user

        if staff_id is None:
            staff_id = getattr(current_user, "id", None) if current_user and current_user.is_authenticated else None
        entry = cls(action=action, detail=detail, staff_id=staff_id)
        db.session.add(entry)
        db.session.commit()
        return entry
