from flask_login import current_user

from ..extensions import db
from ..models import AuditLog


def audit(action, resource, organization_id=None):
    """Sem payload livre: não registra credenciais nem URLs de conexão."""
    db.session.add(AuditLog(organization_id=organization_id or current_user.organization_id,
                            actor_id=current_user.id, action=action,
                            resource_type=resource.__class__.__name__, resource_id=resource.id))
