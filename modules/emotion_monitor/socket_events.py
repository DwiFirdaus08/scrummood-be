# Socket.IO event handler for real-time emotion updates
from flask import request
from app import socketio, db
from models.emotion import EmotionData, EmotionType, AnalysisSource
from models.session import Session
from flask_jwt_extended import decode_token
from datetime import datetime
import json

# Add connect handler to ensure user_id is set for emotion events
@socketio.on('connect')
def handle_connect_emotion():
    token = request.args.get('token') or request.args.get('join_token')
    if not token:
        return False
    try:
        decoded = decode_token(token)
        user_id = decoded['sub']
        # Store user_id in request context for this socket
        request.sid_user_id = user_id
        return True
    except Exception as e:
        print(f"Emotion connect error: {e}")
        return False

@socketio.on('emotion_update')
def handle_emotion_update(data):
    """Handle real-time emotion update from frontend (face/voice detection)."""
    try:
        # Data expected: session_id, user_id, emotions (list or dict), source, [session_timestamp, context, confidence, intensity, raw_data, analysis_metadata]
        session_id = data.get('session_id')
        user_id = data.get('user_id') or getattr(request, 'sid_user_id', None)
        emotions = data.get('emotions')  # Can be a list of {emotion_type, intensity, confidence, ...}
        source = data.get('source')
        session_timestamp = data.get('session_timestamp')
        context = data.get('context')
        raw_data = data.get('raw_data')
        analysis_metadata = data.get('analysis_metadata')

        # Validate required fields
        if not (session_id and user_id and emotions and source):
            socketio.emit('error', {'message': 'Missing required emotion data'})
            return

        # Accept both single and multiple emotions
        if isinstance(emotions, dict):
            emotions = [emotions]

        records = []
        for emo in emotions:
            try:
                emotion_type = EmotionType(emo['emotion_type'])
            except Exception:
                continue  # skip invalid
            intensity = float(emo.get('intensity', 1.0))
            confidence = float(emo.get('confidence', 1.0))
            record = EmotionData(
                user_id=user_id,
                session_id=session_id,
                emotion_type=emotion_type,
                intensity=intensity,
                confidence=confidence,
                source=AnalysisSource(source),
                raw_data=raw_data or {},
                analysis_metadata=analysis_metadata or {},
                session_timestamp=session_timestamp,
                context=context
            )
            db.session.add(record)
            records.append(record)
        db.session.commit()

        # Optionally emit to session room for real-time dashboard update
        socketio.emit('emotion_update', {
            'session_id': session_id,
            'user_id': user_id,
            'emotions': [r.to_dict() for r in records]
        }, room=f'session_{session_id}')
    except Exception as e:
        db.session.rollback()
        socketio.emit('error', {'message': f'Failed to store emotion data: {str(e)}'})
