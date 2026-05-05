from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo, Email


class RegisterForm(FlaskForm):
    username = StringField("Benutzername", validators=[DataRequired(), Length(3, 80)])
    email = StringField("E-Mail", validators=[DataRequired(), Email()])
    password = PasswordField("Passwort", validators=[DataRequired(), Length(min=8)])
    confirm = PasswordField("Passwort wiederholen", validators=[DataRequired(), EqualTo("password")])
    submit = SubmitField("Registrieren")


class LoginForm(FlaskForm):
    username = StringField("Benutzername", validators=[DataRequired()])
    password = PasswordField("Passwort", validators=[DataRequired()])
    submit = SubmitField("Anmelden")
