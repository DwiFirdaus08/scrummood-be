from models.user import User
from models.chat import ChatMessage
from models.session import Session
from app import db
from flask import Blueprint

chat_bp = Blueprint('chat', __name__)

# ...existing code...