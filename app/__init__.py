import os
from flask import Flask
from datetime import timedelta
from dotenv import load_dotenv
from .models import db

load_dotenv()


def create_app():
    app = Flask(__name__, instance_relative_config=True)

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    db_path = os.path.join(app.instance_path, "simplex.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "devkey-change-in-production")
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    from datetime import datetime

    @app.template_filter("datetimeformat")
    def datetimeformat(value):
        if value is None:
            return ""
        return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M")

    from .routing import bp as main_bp
    app.register_blueprint(main_bp)

    print("Using DB:", db_path)
    return app