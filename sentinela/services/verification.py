"""Protótipo 1:1 com vetores artificiais. Não recebe nem reconhece rostos reais."""
import json
import math
import os
import secrets
from datetime import timedelta
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app
from sqlalchemy import exists, func, select, update

from ..extensions import db
from ..models import AccessCredential, VerificationChallenge, VerificationEnrollment, VerificationPolicy, VerificationRecord, utcnow
from .access import check_credential, decide_for_credential, lookup_credential
from .schedules import as_utc

MODEL = 'synthetic-vector-v1'
OUTCOMES = {'approved': 'Verificação simulada aprovada', 'not_approved': 'Verificação simulada não aprovada',
            'quality': 'Qualidade insuficiente (teste)', 'retry': 'Nova tentativa necessária (teste)',
            'unavailable': 'Cadastro de teste indisponível', 'invalid': 'Credencial ou permissão inválida',
            'limited': 'Limite temporário; método alternativo disponível'}


class VerificationUnavailable(Exception):
    pass


def cipher():
    if current_app.config['ENVIRONMENT'] == 'production':
        raise VerificationUnavailable('O protótipo sintético não é habilitado em produção.')
    key = current_app.config.get('BIOMETRIC_TEST_KEY')
    if not key:
        path = Path(current_app.instance_path) / 'verification-test-key'
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(Fernet.generate_key())
        key = path.read_bytes().strip()
    try:
        return Fernet(key)
    except (ValueError, TypeError):
        raise VerificationUnavailable('Chave do teste indisponível.') from None


def policy_for(organization_id):
    return db.session.scalar(select(VerificationPolicy).where(VerificationPolicy.organization_id == organization_id))


def usable(enrollment, policy, now):
    return bool(policy and policy.enabled and policy.model_version == MODEL and enrollment and enrollment.ciphertext and
                not enrollment.revoked_at and as_utc(enrollment.expires_at) > as_utc(now) and
                enrollment.policy_version == policy.version and enrollment.model_version == MODEL)


def enroll(subject, policy, actor_id, authorization_reference, now=None):
    if not policy.enabled or policy.model_version != MODEL or subject.organization_id != policy.organization_id or not subject.active:
        raise VerificationUnavailable('Política de teste ou cadastro indisponível.')
    now = now or utcnow()
    # Dados artificiais independentes de qualquer imagem ou característica humana.
    vector = [secrets.randbelow(20001) / 10000 - 1 for _ in range(32)]
    payload = cipher().encrypt(json.dumps({'model': MODEL, 'vector': vector}).encode())
    row = db.session.scalar(select(VerificationEnrollment).where(VerificationEnrollment.organization_id == subject.organization_id,
                                                               VerificationEnrollment.subject_id == subject.id))
    row = row or VerificationEnrollment(organization_id=subject.organization_id, subject_id=subject.id)
    row.policy_version, row.model_version, row.ciphertext = policy.version, MODEL, payload
    row.authorization_reference, row.enrolled_by, row.enrolled_at = authorization_reference, actor_id, now
    row.expires_at, row.revoked_at = now + timedelta(days=policy.retention_days), None
    db.session.add(row); db.session.flush()
    return row


def erase(enrollment, now=None):
    enrollment.ciphertext = None
    enrollment.authorization_reference = ''
    enrollment.revoked_at = now or utcnow()


def synthetic_compare(ciphertext, scenario, threshold):
    """Compara exclusivamente a referência declarada. Não há busca em galeria."""
    if scenario == 'quality': return 'quality'
    if scenario == 'retry': return 'retry'
    try:
        payload = json.loads(cipher().decrypt(ciphertext))
        reference = payload['vector']
        if payload['model'] != MODEL or len(reference) != 32 or not all(math.isfinite(v) for v in reference):
            return 'unavailable'
        # Fixtures de captura artificiais; nunca são apresentadas como prova de vida.
        probe = list(reference) if scenario == 'match' else [-v for v in reference]
        norm = math.sqrt(sum(v*v for v in reference) * sum(v*v for v in probe))
        if not norm: return 'quality'
        similarity = sum(a*b for a,b in zip(reference, probe)) / norm
        return 'approved' if similarity >= threshold else 'not_approved'
    except (VerificationUnavailable, InvalidToken, ValueError, KeyError, TypeError):
        return 'unavailable'


def attempts_limited(organization_id, credential_id, now):
    if credential_id is None: return False
    count = db.session.scalar(select(func.count()).select_from(VerificationRecord).where(
        VerificationRecord.organization_id == organization_id, VerificationRecord.credential_id == credential_id,
        VerificationRecord.occurred_at >= now-timedelta(minutes=10)))
    return count >= 3


def record_result(point, credential, actor_id, outcome, now, enrollment=None, policy=None):
    denial = {'not_approved': 'verification_failed', 'quality': 'verification_quality', 'retry': 'verification_retry',
              'unavailable': 'verification_unavailable', 'limited': 'verification_limited', 'invalid': 'invalid'}.get(outcome)
    guards=()
    if outcome=='approved':
        guards=(exists(select(VerificationEnrollment.id).where(VerificationEnrollment.id==enrollment.id,
                VerificationEnrollment.revoked_at.is_(None),VerificationEnrollment.expires_at>now,
                VerificationEnrollment.ciphertext==enrollment.ciphertext,VerificationEnrollment.policy_version==policy.version)),
                exists(select(VerificationPolicy.id).where(VerificationPolicy.id==policy.id,VerificationPolicy.enabled.is_(True),
                VerificationPolicy.version==policy.version,VerificationPolicy.model_version==MODEL)))
    event = decide_for_credential(point=point, credential=credential, actor_id=actor_id, now=now, denial_reason=denial,
                                  method='synthetic_1to1',consume_conditions=guards)
    if event.decision != 'allowed' and outcome == 'approved': outcome = 'invalid'
    row = VerificationRecord(organization_id=point.organization_id, site_id=point.site_id, access_event_id=event.id,
                             credential_id=credential.id if credential else None, outcome=outcome, occurred_at=now)
    db.session.add(row); db.session.flush()
    return row


def start(point, token, actor_id, now=None):
    now = now or utcnow()
    credential = lookup_credential(point, token)
    reason, subject, _, _ = check_credential(point, credential, now)
    policy = policy_for(point.organization_id)
    enrollment = db.session.scalar(select(VerificationEnrollment).where(VerificationEnrollment.organization_id == point.organization_id,
                 VerificationEnrollment.subject_id == subject.id)) if subject else None
    outcome = 'invalid' if reason != 'allowed' else 'limited' if attempts_limited(point.organization_id, credential.id, now) else \
              'unavailable' if current_app.config['ENVIRONMENT'] == 'production' or not usable(enrollment, policy, now) else None
    if outcome:
        return None, record_result(point, credential, actor_id, outcome, now)
    challenge = VerificationChallenge(organization_id=point.organization_id, site_id=point.site_id, point_id=point.id,
                  credential_id=credential.id, actor_id=actor_id, expires_at=now+timedelta(minutes=2))
    db.session.add(challenge); db.session.flush()
    return challenge, None


def finish(challenge, point, actor_id, scenario, now=None):
    now = now or utcnow()
    if challenge.actor_id != actor_id or challenge.point_id != point.id or challenge.organization_id != point.organization_id:
        raise VerificationUnavailable('Teste indisponível.')
    claimed = db.session.execute(update(VerificationChallenge).where(VerificationChallenge.id == challenge.id,
        VerificationChallenge.used_at.is_(None), VerificationChallenge.expires_at > now).values(used_at=now).execution_options(synchronize_session=False).returning(VerificationChallenge.id)).scalar()
    if not claimed: raise VerificationUnavailable('Teste vencido ou já utilizado. Apresente a credencial novamente.')
    credential = db.session.get(AccessCredential, challenge.credential_id)
    reason, subject, _, _ = check_credential(point, credential, now)
    policy = policy_for(point.organization_id)
    enrollment = db.session.scalar(select(VerificationEnrollment).where(VerificationEnrollment.organization_id == point.organization_id,
                 VerificationEnrollment.subject_id == subject.id)) if subject else None
    if reason != 'allowed': outcome = 'invalid'
    elif attempts_limited(point.organization_id, credential.id, now): outcome = 'limited'
    elif current_app.config['ENVIRONMENT'] == 'production' or not usable(enrollment, policy, now): outcome = 'unavailable'
    else: outcome = synthetic_compare(enrollment.ciphertext, scenario, policy.threshold)
    return record_result(point, credential, actor_id, outcome, now, enrollment, policy)
