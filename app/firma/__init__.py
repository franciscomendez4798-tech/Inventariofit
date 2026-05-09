from flask import Blueprint

firma_bp = Blueprint('firma', __name__)

from . import routes  # noqa: E402, F401
