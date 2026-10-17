from functools import wraps

from flask import abort
from flask_login import current_user, login_required


def console_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        user = current_user
        if (user.role not in {"organization_admin", "supervisor", "operator"}
                or not user.organization or user.organization.status != "active"):
            abort(403)
        return view(*args, **kwargs)
    return wrapped
