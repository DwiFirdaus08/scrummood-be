from flask import Blueprint

emotion_bp = Blueprint('emotion_monitor', __name__)

from . import routes
