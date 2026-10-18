"""Credenciais de leitura do gateway cifradas; nenhuma URL RTSP é persistida."""
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app

from ..extensions import db
from ..models import ConnectionSecret


class SecretUnavailable(Exception):
    pass


def cipher():
    key = current_app.config.get("CAMERA_ENCRYPTION_KEY")
    if not key:
        if current_app.config["ENVIRONMENT"] == "production":
            raise SecretUnavailable("Configure CAMERA_ENCRYPTION_KEY antes de salvar credenciais.")
        path = Path(current_app.instance_path) / "camera-key"
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "wb") as stream:
                stream.write(Fernet.generate_key())
        key = path.read_bytes().strip()
    try:
        return Fernet(key)
    except (ValueError, TypeError):
        raise SecretUnavailable("Chave de conexão indisponível.") from None


def save_credentials(camera, username, password):
    secret = get_secret(camera)
    payload = cipher().encrypt(json.dumps({"username": username, "password": password}).encode())
    if secret:
        secret.ciphertext = payload
    else:
        secret = ConnectionSecret(organization_id=camera.organization_id, ciphertext=payload)
        db.session.add(secret)
        db.session.flush()
        camera.connection_secret_reference = secret.id


def get_secret(camera):
    if not camera.connection_secret_reference:
        return None
    return db.session.scalar(db.select(ConnectionSecret).where(ConnectionSecret.id == camera.connection_secret_reference,
                                                               ConnectionSecret.organization_id == camera.organization_id))


def credentials(camera):
    secret = get_secret(camera)
    if camera.connection_secret_reference and not secret:
        raise SecretUnavailable("Credencial de conexão indisponível.")
    if not secret:
        return None
    try:
        payload = json.loads(cipher().decrypt(secret.ciphertext))
        return payload["username"], payload["password"]
    except (InvalidToken, ValueError, KeyError):
        raise SecretUnavailable("Credencial de conexão indisponível.") from None


def clear_credentials(camera):
    secret = get_secret(camera)
    camera.connection_secret_reference = None
    db.session.flush()
    if secret:
        db.session.delete(secret)
