from app import db
from models.user import User, UserRole
from models.session import *
from flask import Blueprint, request, jsonify, make_response
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from uuid import uuid4

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
        scheduled_start = datetime.fromisoformat(data['scheduled_start'])
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
    now = datetime.utcnow()
    start = datetime(now.year, now.month, now.day)
    end = start + timedelta(days=1)
    sessions = Session.query.filter(
        Session.scheduled_start >= start,
        Session.scheduled_start < end
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