import click
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from dotenv import load_dotenv

from .config import Config

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()
migrate = Migrate()


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    db.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Bitte melde dich an."
    login_manager.login_message_category = "info"

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from .auth import auth_bp
    from .main import main_bp
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(main_bp)

    @app.cli.command("create-admin")
    @click.option("--username", required=True)
    @click.option("--password", required=True)
    @click.option("--email", required=True)
    @click.option("--if-none", "if_none", is_flag=True, default=False)
    def create_admin(username, password, email, if_none):
        if if_none and User.query.first():
            click.echo("User bereits vorhanden – übersprungen.")
            return
        if User.query.filter_by(username=username).first():
            click.echo(f"User '{username}' bereits vorhanden – übersprungen.")
            return
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        user.get_gpx_dir().mkdir(parents=True, exist_ok=True)
        user.get_maps_dir().mkdir(parents=True, exist_ok=True)
        click.echo(f"User '{username}' erstellt.")

    return app
