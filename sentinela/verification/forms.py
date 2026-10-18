import math

from flask_wtf import FlaskForm
from wtforms import BooleanField, FloatField, IntegerField, PasswordField, SelectField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, ValidationError

from ..core.forms import text


class PolicyForm(FlaskForm):
    enabled = BooleanField('Habilitar exclusivamente o protótipo com dados sintéticos')
    purpose = TextAreaField('Finalidade documentada', validators=[DataRequired(), Length(max=500)])
    controller = text('Responsável pelo tratamento e pelo teste')
    legal_review = TextAreaField('Referência da avaliação de base legal (não presume consentimento suficiente)', validators=[DataRequired(), Length(max=500)])
    necessity_review = TextAreaField('Referência da avaliação de necessidade e proporcionalidade', validators=[DataRequired(), Length(max=500)])
    risk_review = TextAreaField('Referência da avaliação de riscos / RIPD quando cabível', validators=[DataRequired(), Length(max=500)])
    workplace_review = TextAreaField('Referência da revisão do contexto trabalhista', validators=[DataRequired(), Length(max=500)])
    alternative = TextAreaField('Procedimento alternativo não biométrico e revisão humana', default='Credencial temporária de uso único em Controle de Acesso; revisão pelo administrador.', validators=[DataRequired(), Length(max=500)])
    retention_days = IntegerField('Retenção máxima dos dados artificiais (dias)', default=7, validators=[InputRequired(), NumberRange(min=1,max=30)])
    threshold = FloatField('Limiar do comparador sintético (não validado para rostos reais)', default=.95, validators=[InputRequired(),NumberRange(min=.5,max=1)])
    confirm = BooleanField('Confirmo que este ambiente usará somente dados artificiais, sem fotografias ou biometria real', validators=[DataRequired()])
    submit = SubmitField('Salvar política de teste')

    def validate_threshold(self, field):
        if field.data is None or not math.isfinite(field.data): raise ValidationError('Use um limiar finito.')


class EnrollmentForm(FlaskForm):
    subject_id = SelectField('Pessoa previamente cadastrada', coerce=int, validators=[DataRequired()])
    authorization_reference = text('Referência do registro de autorização para o teste', 240)
    confirm = BooleanField('Confirmo autorização documentada e cadastro assistido exclusivamente com dados artificiais', validators=[DataRequired()])
    submit = SubmitField('Criar referência sintética cifrada')


class StartForm(FlaskForm):
    point_id = SelectField('Ponto de acesso simulado', coerce=int, validators=[DataRequired()])
    token = PasswordField('Credencial temporária apresentada', validators=[DataRequired(),Length(max=128)])
    confirm = BooleanField('Confirmo teste 1:1 com dados artificiais, sem captura de câmera ou comando a hardware', validators=[DataRequired()])
    submit = SubmitField('Validar credencial e iniciar teste 1:1')


class CaptureForm(FlaskForm):
    scenario = SelectField('Amostra artificial de teste', choices=[('match','Correspondente à referência declarada'),('mismatch','Amostra diferente'),('quality','Qualidade insuficiente'),('retry','Captura incompleta / nova tentativa')])
    confirm = BooleanField('Confirmo que a amostra é uma fixture artificial; este teste não comprova identidade nem presença real', validators=[DataRequired()])
    submit = SubmitField('Comparar somente a referência declarada')
