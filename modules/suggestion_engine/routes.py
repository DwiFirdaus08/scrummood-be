from flask import request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.suggestion import AISuggestion, SuggestionType, SuggestionStatus
from models.emotion import EmotionData
from models.session import Session
from models.user import User
from app import db, socketio
from . import suggestion_bp
from .suggestion_generator import SuggestionGenerator
from datetime import datetime, timedelta

# Initialize suggestion generator
suggestion_generator = SuggestionGenerator()

@suggestion_bp.route('/generate', methods=['POST'])
@jwt_required()
def generate_suggestions():
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        session_id = data.get('session_id')
        if not session_id:
            return jsonify({'error': 'session_id is required'}), 400
        
        # Verify session access
        session = Session.query.get(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Get recent emotions for the session
        time_window = datetime.utcnow() - timedelta(minutes=5)
        recent_emotions = EmotionData.query.filter(
            EmotionData.session_id == session_id,
            EmotionData.timestamp >= time_window
        ).all()
        
        if not recent_emotions:
            return jsonify({'message': 'No recent emotion data for suggestions'}), 200
        
        # Generate suggestions
        suggestions = suggestion_generator.analyze_and_suggest(recent_emotions, session)
        
        # Save suggestions to database
        saved_suggestions = []
        team_suggestions = []
        personal_suggestions = {}
        
        for suggestion_data in suggestions:
            is_personal = suggestion_data.get('is_personal', False)
            
            suggestion = AISuggestion(
                session_id=session_id,
                suggestion_type=SuggestionType(suggestion_data['type']),
                title=suggestion_data['title'],
                description=suggestion_data['description'],
                priority=suggestion_data['priority'],
                trigger_emotions=suggestion_data['trigger_emotions'],
                affected_users=suggestion_data['affected_users'],
                suggested_duration=suggestion_data.get('duration'),
                implementation_steps=suggestion_data.get('steps', [])
            )
            db.session.add(suggestion)
            saved_suggestions.append(suggestion)
            
            # Separate team and personal suggestions for real-time updates
            if is_personal:
                user_id = suggestion_data['user_id']
                if user_id not in personal_suggestions:
                    personal_suggestions[user_id] = []
                personal_suggestions[user_id].append(suggestion)
            else:
                team_suggestions.append(suggestion)
        
        db.session.commit()
        
        # Emit real-time team suggestions to all session participants
        if team_suggestions:
            socketio.emit('new_suggestions', {
                'session_id': session_id,
                'suggestions': [s.to_dict() for s in team_suggestions],
                'is_team_suggestion': True
            }, room=f'session_{session_id}')
        
        # Emit personal suggestions to specific users
        for user_id, user_suggestions in personal_suggestions.items():
            socketio.emit('new_personal_suggestions', {
                'session_id': session_id,
                'suggestions': [s.to_dict() for s in user_suggestions],
                'user_id': user_id
            }, room=f'user_{user_id}')
        
        return jsonify({
            'suggestions': [s.to_dict() for s in saved_suggestions],
            'count': len(saved_suggestions)
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Generate suggestions error: {str(e)}")
        return jsonify({'error': 'Failed to generate suggestions'}), 500

@suggestion_bp.route('/personal', methods=['GET'])
@jwt_required()
def get_personal_suggestions():
    try:
        current_user_id = get_jwt_identity()
        
        # Get query parameters
        session_id = request.args.get('session_id', type=int)
        limit = request.args.get('limit', default=10, type=int)
        
        # Build query for personal suggestions
        query = AISuggestion.query.filter(
            AISuggestion.affected_users.contains([current_user_id])
        )
        
        if session_id:
            query = query.filter_by(session_id=session_id)
        
        # Order by creation time (newest first)
        suggestions = query.order_by(
            AISuggestion.created_at.desc()
        ).limit(limit).all()
        
        return jsonify({
            'suggestions': [s.to_dict() for s in suggestions],
            'count': len(suggestions)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get personal suggestions error: {str(e)}")
        return jsonify({'error': 'Failed to get personal suggestions'}), 500

@suggestion_bp.route('/session/<int:session_id>', methods=['GET'])
@jwt_required()
def get_session_suggestions(session_id):
    try:
        current_user_id = get_jwt_identity()
        
        # Verify session access
        session = Session.query.get(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Get query parameters
        status = request.args.get('status')
        suggestion_type = request.args.get('type')
        personal_only = request.args.get('personal_only', type=bool, default=False)
        team_only = request.args.get('team_only', type=bool, default=False)
        limit = request.args.get('limit', default=20, type=int)
        
        # Build query
        query = AISuggestion.query.filter_by(session_id=session_id)
        
        if status:
            try:
                status_enum = SuggestionStatus(status)
                query = query.filter_by(status=status_enum)
            except ValueError:
                return jsonify({'error': 'Invalid status'}), 400
        
        if suggestion_type:
            try:
                type_enum = SuggestionType(suggestion_type)
                query = query.filter_by(suggestion_type=type_enum)
            except ValueError:
                return jsonify({'error': 'Invalid suggestion type'}), 400
        
        # Filter for personal or team suggestions
        if personal_only:
            query = query.filter(AISuggestion.affected_users.contains([current_user_id]))
        elif team_only:
            # Team suggestions typically affect multiple users or don't have the current user as the only affected user
            query = query.filter(~AISuggestion.affected_users.contains([current_user_id]) | 
                                (db.func.json_array_length(AISuggestion.affected_users) > 1))
        
        # Order by priority (high first) and creation time
        suggestions = query.order_by(
            AISuggestion.priority.desc(),
            AISuggestion.created_at.desc()
        ).limit(limit).all()
        
        return jsonify({
            'suggestions': [s.to_dict() for s in suggestions],
            'count': len(suggestions)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get session suggestions error: {str(e)}")
        return jsonify({'error': 'Failed to get suggestions'}), 500

@suggestion_bp.route('/<int:suggestion_id>/respond', methods=['POST'])
@jwt_required()
def respond_to_suggestion(suggestion_id):
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        suggestion = AISuggestion.query.get(suggestion_id)
        if not suggestion:
            return jsonify({'error': 'Suggestion not found'}), 404
        
        # Validate response
        response = data.get('response')
        if response not in ['accept', 'dismiss', 'implement']:
            return jsonify({'error': 'Invalid response. Must be accept, dismiss, or implement'}), 400
        
        # Update suggestion status
        if response == 'accept':
            suggestion.status = SuggestionStatus.ACCEPTED
        elif response == 'dismiss':
            suggestion.status = SuggestionStatus.DISMISSED
        elif response == 'implement':
            suggestion.status = SuggestionStatus.IMPLEMENTED
        
        suggestion.responded_at = datetime.utcnow()
        suggestion.responded_by = current_user_id
        
        # Add feedback if provided
        if data.get('feedback'):
            suggestion.feedback_notes = data['feedback']
        
        if data.get('rating'):
            suggestion.effectiveness_rating = data['rating']
        
        db.session.commit()
        
        # Determine if this is a personal or team suggestion
        is_personal = len(suggestion.affected_users) == 1 and suggestion.affected_users[0] == current_user_id
        
        # Emit update to appropriate recipients
        if is_personal:
            socketio.emit('suggestion_update', {
                'suggestion_id': suggestion_id,
                'status': suggestion.status.value,
                'responded_by': current_user_id,
                'is_personal': True
            }, room=f'user_{current_user_id}')
        else:
            socketio.emit('suggestion_update', {
                'suggestion_id': suggestion_id,
                'status': suggestion.status.value,
                'responded_by': current_user_id,
                'is_personal': False
            }, room=f'session_{suggestion.session_id}')
        
        return jsonify({
            'message': 'Response recorded successfully',
            'suggestion': suggestion.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Respond to suggestion error: {str(e)}")
        return jsonify({'error': 'Failed to respond to suggestion'}), 500

@suggestion_bp.route('/reflection/personal', methods=['GET'])
@jwt_required()
def get_personal_reflection():
    try:
        current_user_id = get_jwt_identity()
        
        # Get query parameters
        session_id = request.args.get('session_id', type=int)
        
        if not session_id:
            return jsonify({'error': 'session_id is required'}), 400
        
        # Verify session access
        session = Session.query.get(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Get all emotions for this user in this session
        emotions = EmotionData.query.filter_by(
            user_id=current_user_id,
            session_id=session_id
        ).all()
        
        # Generate personal reflection
        reflection = suggestion_generator.generate_personal_reflection(
            current_user_id, 
            session_id, 
            emotions
        )
        
        return jsonify(reflection), 200
        
    except Exception as e:
        current_app.logger.error(f"Get personal reflection error: {str(e)}")
        return jsonify({'error': 'Failed to generate personal reflection'}), 500

@suggestion_bp.route('/analytics', methods=['GET'])
@jwt_required()
def get_suggestion_analytics():
    try:
        current_user_id = get_jwt_identity()
        
        # Get query parameters
        days = request.args.get('days', default=30, type=int)
        team_id = request.args.get('team_id', type=int)
        
        # Calculate date range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        # Build base query
        query = AISuggestion.query.filter(
            AISuggestion.created_at >= start_time,
            AISuggestion.created_at <= end_time
        )
        
        # Filter by team if specified
        if team_id:
            query = query.join(Session).filter(Session.team_id == team_id)
        
        suggestions = query.all()
        
        # Calculate analytics
        analytics = {
            'total_suggestions': len(suggestions),
            'by_type': {},
            'by_status': {},
            'by_priority': {},
            'effectiveness': {},
            'response_rate': 0.0,
            'implementation_rate': 0.0,
            'personal_vs_team': {
                'personal': 0,
                'team': 0
            }
        }
        
        # Count by type and determine personal vs team
        for suggestion in suggestions:
            s_type = suggestion.suggestion_type.value
            s_status = suggestion.status.value
            s_priority = suggestion.priority
            
            analytics['by_type'][s_type] = analytics['by_type'].get(s_type, 0) + 1
            analytics['by_status'][s_status] = analytics['by_status'].get(s_status, 0) + 1
            analytics['by_priority'][s_priority] = analytics['by_priority'].get(s_priority, 0) + 1
            
            # Determine if personal or team suggestion
            if len(suggestion.affected_users) == 1:
                analytics['personal_vs_team']['personal'] += 1
            else:
                analytics['personal_vs_team']['team'] += 1
        
        # Calculate rates
        responded_suggestions = [s for s in suggestions if s.responded_at]
        implemented_suggestions = [s for s in suggestions if s.status == SuggestionStatus.IMPLEMENTED]
        
        if suggestions:
            analytics['response_rate'] = len(responded_suggestions) / len(suggestions)
            analytics['implementation_rate'] = len(implemented_suggestions) / len(suggestions)
        
        # Calculate effectiveness ratings
        rated_suggestions = [s for s in suggestions if s.effectiveness_rating]
        if rated_suggestions:
            ratings = [s.effectiveness_rating for s in rated_suggestions]
            analytics['effectiveness'] = {
                'average_rating': sum(ratings) / len(ratings),
                'total_rated': len(rated_suggestions),
                'rating_distribution': {}
            }
            
            for rating in range(1, 6):
                count = len([r for r in ratings if r == rating])
                analytics['effectiveness']['rating_distribution'][rating] = count
        
        return jsonify(analytics), 200
        
    except Exception as e:
        current_app.logger.error(f"Get suggestion analytics error: {str(e)}")
        return jsonify({'error': 'Failed to get analytics'}), 500
