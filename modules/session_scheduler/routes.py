from app import db
from models.user import User, UserRole
from models.session import *
from models.emotion import EmotionData
from models.suggestion import AISuggestion
from flask import Blueprint, request, jsonify, make_response
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from uuid import uuid4
import requests
import os
from dateutil.parser import isoparse

session_scheduler_bp = Blueprint('session_scheduler', __name__)

@session_scheduler_bp.route('/create', methods=['POST', 'OPTIONS'])
@jwt_required(optional=True)  # Allow OPTIONS without auth for CORS
def create_session():
    if request.method == 'OPTIONS':
        return make_response('', 200)
    data = request.get_json()
    required_fields = ['title', 'scheduled_start', 'scheduled_duration']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    # Allow all authenticated users to create sessions, not just facilitators

    try:
        scheduled_start = isoparse(data['scheduled_start'])
        # Konversi ke UTC jika aware datetime
        if scheduled_start.tzinfo is not None:
            from datetime import timezone
            scheduled_start = scheduled_start.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return jsonify({'error': 'Invalid scheduled_start format'}), 400

    session = Session(
        title=data['title'],
        team_id=None,  # No team required
        facilitator_id=user_id,
        scheduled_start=scheduled_start,
        scheduled_duration=data['scheduled_duration'],
        created_by=user_id,
        join_token=str(uuid4())
    )
    db.session.add(session)
    db.session.commit()
    join_link = f"http://localhost:8088/join/{session.join_token}"
    return jsonify({'message': 'Session created', 'session': {
        'id': session.id,
        'title': session.title,
        'team_id': session.team_id,
        'facilitator_id': session.facilitator_id,
        'scheduled_start': session.scheduled_start.isoformat(),
        'scheduled_duration': session.scheduled_duration,
        'join_link': join_link
    }}), 201

@session_scheduler_bp.route('/today', methods=['GET', 'OPTIONS'])
def get_today_sessions():
    if request.method == 'OPTIONS':
        return make_response('', 200)
    from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
    verify_jwt_in_request()
    user_id = get_jwt_identity()
    # Ambil offset timezone dari query param (dalam menit), default 0 (UTC)
    try:
        tz_offset = int(request.args.get('tz_offset', '0'))
    except Exception:
        tz_offset = 0
    now_utc = datetime.utcnow()
    # Hitung waktu lokal user
    now_local = now_utc + timedelta(minutes=tz_offset)
    start_local = datetime(now_local.year, now_local.month, now_local.day)
    end_local = start_local + timedelta(days=1)
    # Konversi kembali ke UTC untuk query DB
    start_utc = start_local - timedelta(minutes=tz_offset)
    end_utc = end_local - timedelta(minutes=tz_offset)
    sessions = Session.query.filter(
        Session.scheduled_start >= start_utc,
        Session.scheduled_start < end_utc
    ).order_by(Session.scheduled_start.asc()).all()
    return jsonify({'sessions': [s.to_dict() for s in sessions]}), 200

@session_scheduler_bp.route('/join/<join_token>', methods=['GET'])
@jwt_required()
def join_session(join_token):
    user_id = get_jwt_identity()
    session = Session.query.filter_by(join_token=join_token).first()
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    # Hapus pembatasan: siapa pun yang punya link bisa join
    return jsonify({'session': session.to_dict()}), 200

@session_scheduler_bp.route('/end_session', methods=['POST'])
@jwt_required()
def end_session():
    data = request.get_json()
    session_id = data.get('session_id')
    user_id = get_jwt_identity()
    session = Session.query.get(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    session.status = SessionStatus.COMPLETED
    session.actual_end = datetime.utcnow()
    db.session.commit()
    # Trigger AI summary otomatis setelah sesi selesai
    try:
        trigger_gamini_summary_internal(session.id)
    except Exception as e:
        print(f"Failed to trigger summary: {e}")
    return jsonify({'message': 'Session ended and data saved.'}), 200

# Helper function to call summary logic directly
from flask import current_app

def trigger_gamini_summary_internal(session_id):
    session = Session.query.get(session_id)
    if not session:
        return
    gamini_url = os.environ.get('GAMINI_API_URL')
    gamini_key = os.environ.get('GAMINI_API_KEY')
    if not gamini_url or not gamini_key:
        print('GAMINI_API_URL or GAMINI_API_KEY not set')
        return
    payload = {
        'session_id': session_id,
        'emotions': [e.to_dict() for e in getattr(session, 'emotions', [])],
        'chat': [m.to_dict() for m in getattr(session, 'chat_messages', [])],
        'agenda': session.agenda,
        'participants': [p.user_id for p in getattr(session, 'participants', [])]
    }
    headers = {'Authorization': f'Bearer {gamini_key}'}
    try:
        resp = requests.post(gamini_url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        if 'suggestions' in result:
            for s in result['suggestions']:
                suggestion = AISuggestion(
                    session_id=session_id,
                    suggestion_type=s.get('type', 'discussion'),
                    title=s.get('title', 'AI Suggestion'),
                    description=s.get('description', ''),
                    priority=s.get('priority', 1),
                    trigger_emotions=s.get('trigger_emotions'),
                    affected_users=s.get('affected_users'),
                    suggested_duration=s.get('suggested_duration'),
                    implementation_steps=s.get('implementation_steps'),
                )
                db.session.add(suggestion)
            db.session.commit()
    except Exception as e:
        print(f"Failed to call Gamini API: {e}")

@session_scheduler_bp.route('/session_summary/<int:session_id>', methods=['GET'])
@jwt_required()
def session_summary(session_id):
    session = Session.query.get(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    # Get emotion summary
    emotion_summary = EmotionData.get_emotion_summary(session_id=session_id)
    # Get AI suggestions
    ai_suggestions = [s.to_dict() for s in session.suggestions]
    # Optionally: get chat summary, etc.
    return jsonify({
        'session': session.to_dict(include_details=True),
        'emotion_summary': emotion_summary,
        'ai_suggestions': ai_suggestions
    }), 200

@session_scheduler_bp.route('/trigger_gamini_summary', methods=['POST'])
@jwt_required()
def trigger_gamini_summary():
    data = request.get_json()
    session_id = data.get('session_id')
    session = Session.query.get(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    # Compose payload for Gamini API
    gamini_url = os.environ.get('GAMINI_API_URL')
    gamini_key = os.environ.get('GAMINI_API_KEY')
    payload = {
        'session_id': session_id,
        'emotions': [e.to_dict() for e in session.emotions],
        'chat': [m.to_dict() for m in session.chat_messages],
        'agenda': session.agenda,
        'participants': [p.user_id for p in session.participants]
    }
    headers = {'Authorization': f'Bearer {gamini_key}'}
    try:
        resp = requests.post(gamini_url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        # Save summary/suggestions to DB if present
        if 'suggestions' in result:
            for s in result['suggestions']:
                suggestion = AISuggestion(
                    session_id=session_id,
                    suggestion_type=s.get('type', 'discussion'),
                    title=s.get('title', 'AI Suggestion'),
                    description=s.get('description', ''),
                    priority=s.get('priority', 1),
                    trigger_emotions=s.get('trigger_emotions'),
                    affected_users=s.get('affected_users'),
                    suggested_duration=s.get('suggested_duration'),
                    implementation_steps=s.get('implementation_steps'),
                )
                db.session.add(suggestion)
            db.session.commit()
        return jsonify({'message': 'Gamini summary/suggestions saved', 'result': result}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@session_scheduler_bp.route('/session_history', methods=['GET'])
@jwt_required()
def session_history():
    user_id = get_jwt_identity()
    # Show all sessions where user is a participant or facilitator
    sessions = Session.query.filter(
        (Session.facilitator_id == user_id) | (Session.participants.any(SessionParticipant.user_id == user_id)),
        Session.status == SessionStatus.COMPLETED
    ).order_by(Session.scheduled_start.desc()).all()
    result = []
    for s in sessions:
        summary = EmotionData.get_emotion_summary(session_id=s.id)
        ai_suggestions = [a.to_dict() for a in s.suggestions]
        result.append({
            **s.to_dict(include_details=True),
            'emotion_summary': summary,
            'ai_suggestions': ai_suggestions
        })
    return jsonify({'sessions': result}), 200