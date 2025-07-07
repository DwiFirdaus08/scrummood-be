from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO

# Inisialisasi semua ekstensi di sini, tanpa menghubungkannya ke aplikasi
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
socketio = SocketIO(async_mode="eventlet")