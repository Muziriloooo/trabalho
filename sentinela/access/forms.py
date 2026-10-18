from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length

from ..core.forms import text
from ..events.forms import ScheduleForm


class SubjectForm(FlaskForm):
    display_name = text("Nome da pessoa autorizada")
    external_reference = text("Referência interna (sem documentos sensíveis)", 64)
    active = BooleanField("Cadastro ativo", default=True)
    submit = SubmitField("Salvar pessoa autorizada")


class PointForm(FlaskForm):
    name = text("Nome do ponto de acesso")
    site_id = SelectField("Unidade", coerce=int, validators=[DataRequired()])
    enabled = BooleanField("Ponto ativo", default=True)
    submit = SubmitField("Salvar ponto simulado")


class PermissionForm(ScheduleForm):
    subject_id = SelectField("Pessoa autorizada", coerce=int, validators=[DataRequired()])
    site_id = SelectField("Unidade", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Conceder permissão de acesso")


class IssueForm(FlaskForm):
    subject_id = SelectField("Pessoa autorizada", coerce=int, validators=[DataRequired()])
    ttl = SelectField("Validade", coerce=int, choices=[(60, "1 minuto"), (300, "5 minutos"), (900, "15 minutos")])
    submit = SubmitField("Emitir credencial de uso único")


class DecisionForm(FlaskForm):
    point_id = SelectField("Ponto de acesso simulado", coerce=int, validators=[DataRequired()])
    token = PasswordField("Credencial temporária (não use nome ou matrícula)", validators=[DataRequired(), Length(max=128)])
    confirm = BooleanField("Confirmo que esta é uma decisão simulada, sem acionar fechadura ou outro hardware", validators=[DataRequired()])
    submit = SubmitField("Simular decisão de acesso")
