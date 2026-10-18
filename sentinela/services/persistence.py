from flask import flash
from sqlalchemy.exc import IntegrityError

from ..extensions import db


def commit():
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Identificador ou e-mail já utilizado, ou relação inválida. Revise os dados.", "error")
        return False
    return True
