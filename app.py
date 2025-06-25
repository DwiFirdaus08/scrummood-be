from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_socketio import SocketIO
from config import Config
import logging
from datetime import datetime
from dotenv import load_dotenv

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
socketio = SocketIO()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    # Perbaiki CORS agar mengizinkan frontend di 8088 dan 3000, serta semua method dan header
    CORS(
        app,
        supports_credentials=True,
        origins=["http://localhost:8088", "http://localhost:3000", "https://xeroon.xyz"],
        allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    )
    socketio.init_app(app, cors_allowed_origins="*")
    
    # Configure logging
    if not app.debug:
        logging.basicConfig(level=logging.INFO)
    
    # Register blueprints
    from modules.auth import auth_bp
    from modules.emotion_monitor import emotion_bp
    from modules.suggestion_engine import suggestion_bp
    from modules.chat_handler import chat_bp
    from modules.reflection import reflection_bp
    from modules.session_scheduler.routes import session_scheduler_bp
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(emotion_bp, url_prefix='/api/emotions')
    app.register_blueprint(suggestion_bp, url_prefix='/api/suggestions')
    app.register_blueprint(chat_bp, url_prefix='/api/chat')
    app.register_blueprint(reflection_bp, url_prefix='/api/reflections')
    app.register_blueprint(session_scheduler_bp, url_prefix='/api/sessions')
    
    # Health check endpoint
    @app.route('/api/health')
    def health_check():
        return {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0'
        }
    
    return app

if __name__ == '__main__':
    load_dotenv()
    app = create_app()
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
