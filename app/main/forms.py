from flask_wtf import FlaskForm
from flask_wtf.file import MultipleFileField
from wtforms import SubmitField
from wtforms.validators import DataRequired


class UploadForm(FlaskForm):
    gpx_files = MultipleFileField("GPX-Dateien", validators=[DataRequired()])
    submit = SubmitField("Hochladen")
