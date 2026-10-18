from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField
from wtforms.validators import Length

STATUSES = {"new": "Novo", "acknowledged": "Reconhecido", "in_review": "Em análise", "resolved": "Resolvido", "discarded": "Descartado"}


class AlertForm(FlaskForm):
    status = SelectField("Status", choices=list(STATUSES.items()))
    assigned_to = SelectField("Responsável", coerce=int)
    note = StringField("Comentário / justificativa (obrigatória para resolver ou descartar)", validators=[Length(max=500)])
    submit = SubmitField("Registrar providência")
