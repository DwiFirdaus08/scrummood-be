from flask import Blueprint

suggestion_bp = Blueprint('suggestion_engine', __name__)

from . import routes
