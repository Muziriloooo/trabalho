from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, Regexp, ValidationError
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

REQUIRED = DataRequired(message="Preencha este campo.")
IDENTIFIER = Regexp(r"^[a-zA-Z0-9_-]+$", message="Use somente letras, números, hífen e sublinhado.")


def text(label, length=120, required=True):
    return StringField(label, filters=[lambda v: v.strip() if v else v], validators=[REQUIRED if required else Optional(), Length(max=length, message=f"Use até {length} caracteres.")])


class OrganizationForm(FlaskForm):
    name = text("Nome da organização")
    identifier = StringField("Identificador", validators=[REQUIRED, Length(max=64), IDENTIFIER])
    responsible = text("Responsável")
    status = SelectField("Status", choices=[("active", "Ativa"), ("inactive", "Inativa")])
    confirm = BooleanField("Confirmo a desativação da organização e a interrupção do acesso dos seus usuários")
    submit = SubmitField("Salvar organização")


class SiteForm(FlaskForm):
    name = text("Nome da unidade")
    identifier = StringField("Identificador", validators=[REQUIRED, Length(max=64), IDENTIFIER])
    responsible = text("Responsável")
    address = text("Endereço comercial (opcional)", 255, False)
    location_description = text("Descrição do local (opcional)", 255, False)
    timezone = StringField("Fuso horário IANA", default="America/Sao_Paulo", validators=[REQUIRED, Length(max=64)])
    status = SelectField("Status", choices=[("active", "Ativa"), ("inactive", "Inativa")])
    confirm = BooleanField("Confirmo a desativação da unidade e a interrupção de suas transmissões")
    submit = SubmitField("Salvar unidade")

    def validate_timezone(self, field):
        try:
            ZoneInfo(field.data)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValidationError("Informe um fuso IANA válido, como America/Sao_Paulo.")


class MemberForm(FlaskForm):
    email = text("E-mail", 254)
    password = PasswordField("Senha inicial (12 a 128 caracteres)", validators=[REQUIRED, Length(min=12, max=128)])
    role = SelectField("Perfil", choices=[("operator", "Operador"), ("supervisor", "Supervisor")])
    submit = SubmitField("Cadastrar usuário")

    def validate_email(self, field):
        field.data = field.data.lower()
        if len(field.data.split("@")) != 2 or not all(field.data.split("@")) or any(c.isspace() for c in field.data):
            raise ValidationError("Informe um e-mail válido.")


class AssignmentForm(FlaskForm):
    user_id = SelectField("Usuário", coerce=int, validators=[REQUIRED])
    site_id = SelectField("Escopo", coerce=int)
    role = SelectField("Papel no escopo", choices=[("operator", "Operador"), ("supervisor", "Supervisor")])
    submit = SubmitField("Conceder acesso")


class ConfirmationForm(FlaskForm):
    confirm = BooleanField("Confirmo esta operação", validators=[REQUIRED])
    submit = SubmitField("Confirmar")


class CameraForm(FlaskForm):
    name = text("Nome da câmera")
    identifier = StringField("Identificador interno", validators=[REQUIRED, Length(max=64), IDENTIFIER])
    site_id = SelectField("Unidade", coerce=int, validators=[REQUIRED])
    manufacturer = text("Fabricante (opcional)", 80, False)
    model = text("Modelo (opcional)", 80, False)
    location_description = text("Local de instalação", 255)
    protocol = SelectField("Fonte", choices=[("demo", "Demonstração — vídeo sintético"), ("rtsp", "RTSP via gateway HTTPS"), ("rtsps", "RTSPS via gateway HTTPS")])
    gateway_path = StringField("Identificador do caminho no gateway (somente fonte real)", validators=[Length(max=64), Regexp(r"^[A-Za-z0-9_-]*$", message="Use somente letras, números, hífen e sublinhado.")])
    gateway_username = text("Usuário de leitura do gateway (opcional)", 120, False)
    gateway_password = PasswordField("Senha de leitura do gateway (não será exibida novamente)", validators=[Length(max=512)])
    clear_credentials = BooleanField("Remover a credencial salva do gateway")
    authorized = BooleanField("Confirmo que a operação desta câmera e deste local foi autorizada pelo responsável legítimo", validators=[REQUIRED])
    submit = SubmitField("Salvar câmera")

    def validate_gateway_path(self, field):
        if self.protocol.data != "demo" and not field.data:
            raise ValidationError("Informe o caminho previamente configurado pelo administrador do gateway.")

    def validate_gateway_password(self, field):
        if bool(self.gateway_username.data) != bool(field.data):
            raise ValidationError("Para substituir a credencial, preencha usuário e senha juntos.")
        if self.clear_credentials.data and (field.data or self.gateway_username.data):
            raise ValidationError("Escolha substituir ou remover a credencial.")


class DeleteCameraForm(FlaskForm):
    identifier = StringField("Digite o identificador da câmera para confirmar", validators=[REQUIRED, Length(max=64)])
    submit = SubmitField("Remover câmera e histórico")
