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
