import math
import re

from flask_wtf import FlaskForm
from wtforms import BooleanField, FloatField, IntegerField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, ValidationError

from ..core.forms import ConfirmationForm


def validate_clock(form, field):
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", field.data or ""):
        raise ValidationError("Use HH:MM, de 00:00 a 23:59.")


def validate_days(form, field):
    if not re.fullmatch(r"[0-6](?:,[0-6])*", field.data or "") or len(set(field.data.split(','))) != len(field.data.split(',')):
        raise ValidationError("Use dias únicos de 0 (segunda) a 6 (domingo), separados por vírgula.")


class ScheduleForm(FlaskForm):
    start_time = StringField("Horário inicial local (HH:MM)", default="00:00", validators=[validate_clock])
    end_time = StringField("Horário final local (igual ao inicial = 24h)", default="00:00", validators=[validate_clock])
    weekdays = StringField("Dias da semana (0=segunda, 6=domingo)", default="0,1,2,3,4,5,6", validators=[Length(max=13), validate_days])


class PolicyForm(ScheduleForm):
    enabled = BooleanField("Ativar análise autorizada de amostras desta câmera")
    motion_enabled = BooleanField("Detectar movimento (sem identificação de pessoas)", default=True)
    obstruction_enabled = BooleanField("Sinalizar possível obstrução ou imagem uniforme", default=True)
    motion_ratio = FloatField("Fração mínima de pixels alterados (0.001 a 1)", default=.03, validators=[InputRequired(), NumberRange(min=.001, max=1)])
    roi_x = FloatField("Área: posição X (0 a 1)", default=0, validators=[InputRequired(), NumberRange(min=0, max=1)])
    roi_y = FloatField("Área: posição Y (0 a 1)", default=0, validators=[InputRequired(), NumberRange(min=0, max=1)])
    roi_w = FloatField("Área: largura (0.01 a 1)", default=1, validators=[InputRequired(), NumberRange(min=.01, max=1)])
    roi_h = FloatField("Área: altura (0.01 a 1)", default=1, validators=[InputRequired(), NumberRange(min=.01, max=1)])
    cooldown_seconds = IntegerField("Intervalo mínimo entre eventos iguais (segundos)", default=60, validators=[InputRequired(), NumberRange(min=10, max=3600)])
    authorized = BooleanField("Autorizo a análise desta área e o uso de uma amostra temporária, descartada ao concluir; sem gravação permanente", validators=[DataRequired()])
    submit = SubmitField("Salvar análise")

    def validate(self, extra_validators=None):
        valid = super().validate(extra_validators)
        values = [self.roi_x.data, self.roi_y.data, self.roi_w.data, self.roi_h.data, self.motion_ratio.data]
        if any(value is None or not math.isfinite(value) for value in values):
            self.roi_w.errors = ["Use números finitos válidos."]
            return False
        if self.roi_x.data + self.roi_w.data > 1.000001 or self.roi_y.data + self.roi_h.data > 1.000001:
            self.roi_w.errors = ["A área precisa caber inteiramente na imagem."]
            return False
        return valid


class JobForm(ConfirmationForm):
    mode = SelectField("Execução", choices=[("now", "Analisar agora (somente vídeo sintético)"), ("queue", "Enfileirar para processamento local")])
    submit = SubmitField("Executar análise autorizada")


class YouTubeObservationForm(FlaskForm):
    site_id = SelectField("Unidade responsável pelo teste", coerce=int, validators=[DataRequired()])
    result = SelectField("Resultado observado por você", choices=[("youtube_playback_observed", "Confirmei a reprodução visualmente"),
                         ("youtube_playback_error", "O player exibiu um erro / não reproduziu"), ("youtube_test_ended", "Encerrei o teste")])
    confirm = BooleanField("Confirmo que este é um relato manual do player, sem análise automática das imagens", validators=[DataRequired()])
    submit = SubmitField("Registrar resultado do teste YouTube")
