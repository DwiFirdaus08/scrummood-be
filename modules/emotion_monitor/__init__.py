from flask import Blueprint

emotion_bp = Blueprint('emotion_monitor', __name__)

from . import routes
from . import socket_events  # Import Socket.IO handlers for emotion updates
