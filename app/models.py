from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    """Local admin users."""
    __tablename__ = "users"

    id           = db.Column(db.Integer, primary_key=True)
    callsign     = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin     = db.Column(db.Boolean, default=True)
    is_active    = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.callsign}>"


class Submission(db.Model):
    """A simplex contact submission."""
    __tablename__ = "submissions"

    id              = db.Column(db.Integer, primary_key=True)

    submitted_by    = db.Column(db.String(20), nullable=False)
    contact_call    = db.Column(db.String(20), nullable=False)
    submitted_at    = db.Column(db.DateTime, default=datetime.utcnow)

    mode_type       = db.Column(db.String(10))   # 'voice' | 'digital'
    is_pota         = db.Column(db.Boolean, default=False)
    pota_park       = db.Column(db.String(20))
    digital_mode    = db.Column(db.String(20))

    frequency       = db.Column(db.Float)
    notes           = db.Column(db.String(500))

    is_deleted      = db.Column(db.Boolean, default=False)
    deleted_at      = db.Column(db.DateTime)
    deleted_by      = db.Column(db.String(20))
    delete_reason   = db.Column(db.String(255))

    def __repr__(self):
        return f"<Submission {self.id} {self.submitted_by}→{self.contact_call}>"


class ScoreMultiplier(db.Model):
    """Admin-applied bonus multipliers per operator per day."""
    __tablename__ = "score_multipliers"

    id          = db.Column(db.Integer, primary_key=True)
    operator    = db.Column(db.String(20), nullable=False)
    date        = db.Column(db.Date, nullable=False)
    multiplier  = db.Column(db.Float, nullable=False, default=1.0)
    reason      = db.Column(db.String(255))

    def __repr__(self):
        return f"<ScoreMultiplier {self.operator} {self.date} ×{self.multiplier}>"