import eventlet
eventlet.monkey_patch()

from flask import Flask
from flask_cors import CORS
from config import Config
import logging
from datetime import datetime
from dotenv import load_dotenv
import os

# 1. Impor ekstensi dari file extensions.py
from extensions import db, migrate, jwt, socketio

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # 2. Inisialisasi ekstensi dengan aplikasi
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    CORS(
        app,
        supports_credentials=True,
        origins=["http://localhost:8088", "http://localhost:3000", "https://xeroon.xyz"],
        allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    )
    socketio.init_app(app, cors_allowed_origins=["http://localhost:8088", "http://localhost:3000", "https://xeroon.xyz"])
    
    # Configure logging
    if not app.debug:
        logging.basicConfig(level=logging.INFO)
    
    # 3. Impor dan daftarkan blueprint di sini
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

# Buat instance aplikasi untuk digunakan oleh server seperti Gunicorn
app = create_app()

if __name__ == '__main__':
    load_dotenv()
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)