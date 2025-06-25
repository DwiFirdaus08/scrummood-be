from app import db
from models.user import User, UserRole
from models.session import *
from flask import Blueprint, request, jsonify, make_response
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta

session_scheduler_bp = Blueprint('session_scheduler', __name__)

@session_scheduler_bp.route('/sessions/create', methods=['POST'])
@jwt_required()
def create_session():
    data = request.get_json()
    required_fields = ['title', 'team_id', 'scheduled_start', 'scheduled_duration']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user or user.role != UserRole.FACILITATOR:
        return jsonify({'error': 'Only facilitators can create sessions'}), 403

    try:
        scheduled_start = datetime.fromisoformat(data['scheduled_start'])
    except Exception:
        return jsonify({'error': 'Invalid scheduled_start format'}), 400

    session = Session(
        title=data['title'],
        team_id=data['team_id'],
        facilitator_id=user_id,
        scheduled_start=scheduled_start,
        scheduled_duration=data['scheduled_duration']
    )
    db.session.add(session)
    db.session.commit()
    return jsonify({'message': 'Session created', 'session': {
        'id': session.id,
        'title': session.title,
        'team_id': session.team_id,
        'facilitator_id': session.facilitator_id,
        'scheduled_start': session.scheduled_start.isoformat(),
        'scheduled_duration': session.scheduled_duration
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