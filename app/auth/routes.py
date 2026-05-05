from flask import render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from .. import db
from ..models import User
from . import auth_bp
from .forms import RegisterForm, LoginForm


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash("Benutzername bereits vergeben.", "danger")
            return render_template("auth/register.html", form=form)
        if User.query.filter_by(email=form.email.data).first():
            flash("E-Mail bereits registriert.", "danger")
            return render_template("auth/register.html", form=form)
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        user.get_gpx_dir().mkdir(parents=True, exist_ok=True)
        user.get_maps_dir().mkdir(parents=True, exist_ok=True)
        flash(f"Willkommen, {user.username}! Du kannst dich jetzt anmelden.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for("main.dashboard"))
        flash("Benutzername oder Passwort falsch.", "danger")
    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
