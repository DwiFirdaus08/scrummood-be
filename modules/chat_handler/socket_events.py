from flask import request
from flask_socketio import emit, join_room, leave_room
from flask_jwt_extended import decode_token
from app import socketio, db
from models.chat import ChatMessage, MessageType
from models.session import Session, SessionParticipant
from models.user import User
from modules.emotion_monitor.emotion_analyzer import EmotionAnalyzer
from datetime import datetime
import json

# Initialize emotion analyzer
emotion_analyzer = EmotionAnalyzer()

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    try:
        # Get token from request args
        token = request.args.get('token')
        if not token:
            return False  # Reject connection
        
        # Decode token to get user_id
        decoded = decode_token(token)
        user_id = decoded['sub']
        
        # Store user_id in session
        request.sid_user_id = user_id
        
        # Join user's personal room for private messages
        join_room(f'user_{user_id}')
        
        emit('connect_response', {'status': 'connected', 'user_id': user_id})
        return True
    except Exception as e:
        print(f"Connection error: {str(e)}")
        return False

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    pass

@socketio.on('join_session')
def handle_join_session(data):
    """Handle user joining a session"""
    try:
        user_id = getattr(request, 'sid_user_id', None)
        if not user_id:
            emit('error', {'message': 'Authentication required'})
            return
        
        session_id = data.get('session_id')
        if not session_id:
            emit('error', {'message': 'session_id is required'})
            return
        
        # Join session room
        join_room(f'session_{session_id}')
        
        # Update participant status
        participant = SessionParticipant.query.filter_by(
            session_id=session_id,
            user_id=user_id
        ).first()
        
        if participant:
            participant.is_present = True
            participant.joined_at = datetime.utcnow()
            db.session.commit()
        
        # Get user info
        user = User.query.get(user_id)
        
        # Notify others in the session
        emit('user_joined', {
            'user_id': user_id,
            'username': user.username if user else 'Unknown',
            'timestamp': datetime.utcnow().isoformat()
        }, room=f'session_{session_id}', include_self=False)
        
        emit('join_session_response', {'status': 'joined', 'session_id': session_id})
    except Exception as e:
        emit('error', {'message': f'Failed to join session: {str(e)}'})

@socketio.on('leave_session')
def handle_leave_session(data):
    """Handle user leaving a session"""
    try:
        user_id = getattr(request, 'sid_user_id', None)
        if not user_id:
            emit('error', {'message': 'Authentication required'})
            return
        
        session_id = data.get('session_id')
        if not session_id:
            emit('error', {'message': 'session_id is required'})
            return
        
        # Leave session room
        leave_room(f'session_{session_id}')
        
        # Update participant status
        participant = SessionParticipant.query.filter_by(
            session_id=session_id,
            user_id=user_id
        ).first()
        if participant:
            participant.is_present = False
            participant.left_at = datetime.utcnow()
            db.session.commit()
        
        # Notify others in the session
        user = User.query.get(user_id)
        emit('user_left', {
            'user_id': user_id,
            'username': user.username if user else 'Unknown',
            'timestamp': datetime.utcnow().isoformat()
        }, room=f'session_{session_id}', include_self=False)
        
        emit('leave_session_response', {'status': 'left', 'session_id': session_id})
    except Exception as e:
        emit('error', {'message': f'Failed to leave session: {str(e)}'})
@socketio.on('send_chat_message')
def handle_chat_message(data):
    """Menerima, menganalisis, menyimpan, dan menyiarkan pesan chat."""
    try:
        user_id = getattr(request, 'sid_user_id', None)
        if not user_id:
            emit('error', {'message': 'Autentikasi diperlukan'})
            return

        session_id = data.get('session_id')
        content = data.get('content')

        if not all([session_id, content]):
            emit('error', {'message': 'Session ID dan isi pesan diperlukan'})
            return

        # --- INTI LOGIKA AI DIMULAI DI SINI ---
        # 1. Analisis emosi dari teks chat
        analysis_result = emotion_analyzer.analyze_text(content)
        detected_emotion = 'neutral'
        sentiment_score = 0.0
        if analysis_result:
            detected_emotion = analysis_result.get('emotion', 'neutral')
            sentiment_score = analysis_result.get('sentiment_score', 0.0)
        # --- LOGIKA AI SELESAI ---

        # 2. Dapatkan info sesi untuk timestamp
        session = Session.query.get(session_id)
        session_timestamp = None
        if session and session.actual_start:
            delta = datetime.utcnow() - session.actual_start
            session_timestamp = int(delta.total_seconds())

        # 3. Buat dan simpan record ChatMessage ke database
        chat_message = ChatMessage(
            session_id=session_id,
            sender_id=user_id,
            content=content,
            message_type=MessageType.TEXT,
            emotion_detected=detected_emotion,
            sentiment_score=sentiment_score,
            session_timestamp=session_timestamp
        )
        db.session.add(chat_message)
        db.session.commit()

        # 4. Siapkan data untuk dikirim kembali ke semua klien
        user = User.query.get(user_id)
        message_to_broadcast = {
            'id': chat_message.id,
            'content': chat_message.content,
            'sender_id': user.id,
            'sender_name': user.full_name,
            'timestamp': chat_message.timestamp.isoformat(),
            'emotion': chat_message.emotion_detected # Kirim emosi ke frontend!
        }

        # 5. Siarkan pesan baru ke semua orang di room sesi
        emit('new_chat_message', message_to_broadcast, room=f'session_{session_id}')

    except Exception as e:
        db.session.rollback()
        print(f"Error handling chat message: {str(e)}") # Ganti dengan logger di produksi
        emit('error', {'message': 'Gagal memproses pesan chat'})