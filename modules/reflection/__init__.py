from flask import Blueprint

reflection_bp = Blueprint('reflection', __name__)

from . import routes
