from datetime import datetime, timedelta, timezone

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import BooleanField, DateField, SelectField, SubmitField
from wtforms.validators import DataRequired, InputRequired

from ..core.forms import text

SOURCES = {'all':'Todas (origens separadas)','gateway':'Gateway autorizado','synthetic':'Vídeo sintético',
           'youtube_client':'Relato manual do YouTube','access_simulation':'Acesso simulado'}
KINDS = {'availability':'Disponibilidade observada de câmeras','failures':'Falhas técnicas','alerts':'Alertas por período',
         'events':'Eventos por unidade','resolution':'Tempos de reconhecimento e resolução','access':'Resumo agregado de acesso',
         'audit':'Auditoria administrativa (restrita)'}


class FilterForm(FlaskForm):
    start = DateField('Data inicial (UTC)',default=lambda:datetime.now(timezone.utc).date()-timedelta(days=6),validators=[DataRequired()])
    end = DateField('Data final (UTC)',default=lambda:datetime.now(timezone.utc).date(),validators=[DataRequired()])
    site_id = SelectField('Unidade',coerce=int,default=0)
    source = SelectField('Fonte',choices=list(SOURCES.items()),default='all')
    submit = SubmitField('Aplicar filtros')

    def validate(self,extra_validators=None):
        valid=super().validate(extra_validators)
        if self.start.data and self.end.data:
            if self.end.data < self.start.data or (self.end.data-self.start.data).days>91:
                self.end.errors=['Escolha um período de 1 a 92 dias.'];valid=False
            if self.end.data>datetime.now(timezone.utc).date():
                self.end.errors=['A data final não pode estar no futuro.'];valid=False
        return valid


class ReportForm(FilterForm):
    kind = SelectField('Tipo de relatório',choices=list(KINDS.items()))
    purpose = text('Finalidade da geração (sem dados pessoais)',240)
    submit = SubmitField('Gerar relatório')


class LogoForm(FlaskForm):
    logo = FileField('Logo da organização (PNG/JPEG até 48 KiB, 512 × 512)',validators=[FileAllowed(['png','jpg','jpeg'],'Use PNG ou JPEG.')])
    remove = BooleanField('Remover logo personalizado')
    submit = SubmitField('Salvar logo')


class ExportForm(FlaskForm):
    submit = SubmitField('Exportar')
