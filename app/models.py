from datetime import datetime
from pathlib import Path
from flask import current_app
from flask_login import UserMixin
from . import db, bcrypt


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tours = db.relationship("Tour", backref="user", lazy=True, cascade="all, delete-orphan")
    map_caches = db.relationship("MapCache", backref="user", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def get_gpx_dir(self) -> Path:
        return current_app.config["USER_DATA_DIR"] / str(self.id) / "gpx"

    def get_maps_dir(self) -> Path:
        return current_app.config["USER_DATA_DIR"] / str(self.id) / "maps"


class Tour(db.Model):
    __tablename__ = "tour"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    gpx_path = db.Column(db.String(512), nullable=False)
    tour_date = db.Column(db.Date, nullable=True, index=True)
    distance_km = db.Column(db.Float, nullable=True)
    duration_min = db.Column(db.Float, nullable=True)
    avg_speed_kmh = db.Column(db.Float, nullable=True)
    ascent_m = db.Column(db.Float, nullable=True)
    descent_m = db.Column(db.Float, nullable=True)
    min_ele_m = db.Column(db.Float, nullable=True)
    max_ele_m = db.Column(db.Float, nullable=True)
    num_points = db.Column(db.Integer, nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_hidden = db.Column(db.Boolean, nullable=False, default=False,
                          server_default=db.false(), index=True)

    def to_dict(self):
        return {
            "filename": self.filename,
            "date": datetime.combine(self.tour_date, datetime.min.time()) if self.tour_date else None,
            "distance_km": self.distance_km or 0.0,
            "duration_min": self.duration_min,
            "avg_speed_kmh": self.avg_speed_kmh,
            "ascent_m": self.ascent_m or 0.0,
            "descent_m": self.descent_m or 0.0,
            "min_ele_m": self.min_ele_m,
            "max_ele_m": self.max_ele_m,
            "num_points": self.num_points or 0,
        }


class MapCache(db.Model):
    __tablename__ = "map_cache"
    __table_args__ = (db.UniqueConstraint("user_id", "map_type", "year"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    map_type = db.Column(db.String(20), nullable=False)
    year = db.Column(db.Integer, nullable=True)
    html_path = db.Column(db.String(512), nullable=False)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
