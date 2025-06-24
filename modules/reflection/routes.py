from flask import request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.emotion import EmotionData
from models.session import Session, SessionParticipant
from models.user import User
from models.journal import Journal
from app import db
from . import reflection_bp
from modules.suggestion_engine.suggestion_generator import SuggestionGenerator
from datetime import datetime, timedelta
import statistics

# Initialize suggestion generator for reflection capabilities
suggestion_generator = SuggestionGenerator()

@reflection_bp.route('/personal/<int:session_id>', methods=['GET'])
@jwt_required()
def get_personal_reflection(session_id):
    try:
        current_user_id = get_jwt_identity()
        
        # Verify session access
        session = Session.query.get(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Verify user participated in session
        participant = SessionParticipant.query.filter_by(
            session_id=session_id,
            user_id=current_user_id
        ).first()
        
        if not participant:
            return jsonify({'error': 'You did not participate in this session'}), 403
        
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
        
        # Get user's journal entry for this session if it exists
        journal = Journal.query.filter_by(
            user_id=current_user_id,
            session_id=session_id
        ).first()
        
        if journal:
            reflection['journal'] = {
                'id': journal.id,
                'title': journal.title,
                'content': journal.content,
                'created_at': journal.created_at.isoformat(),
                'updated_at': journal.updated_at.isoformat()
            }
        
        return jsonify(reflection), 200
        
    except Exception as e:
        current_app.logger.error(f"Get personal reflection error: {str(e)}")
        return jsonify({'error': 'Failed to generate personal reflection'}), 500

@reflection_bp.route('/team/<int:session_id>', methods=['GET'])
@jwt_required()
def get_team_reflection(session_id):
    try:
        current_user_id = get_jwt_identity()
        
        # Verify session access
        session = Session.query.get(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Verify user is facilitator or has appropriate permissions
        if session.facilitator_id != current_user_id:
            # Check if user is team lead or manager
            user = User.query.get(current_user_id)
            if not user or user.role.value not in ['facilitator', 'manager']:
                return jsonify({'error': 'You do not have permission to view team reflections'}), 403
        
        # Get all participants
        participants = SessionParticipant.query.filter_by(session_id=session_id).all()
        
        # Get all emotions for this session
        emotions = EmotionData.query.filter_by(session_id=session_id).all()
        
        # Group emotions by user
        emotions_by_user = {}
        for emotion in emotions:
            if emotion.user_id not in emotions_by_user:
                emotions_by_user[emotion.user_id] = []
            emotions_by_user[emotion.user_id].append(emotion)
        
        # Generate anonymized team reflection
        team_reflection = {
            'session_id': session_id,
            'session_title': session.title,
            'session_date': session.actual_start.isoformat() if session.actual_start else session.scheduled_start.isoformat(),
            'participant_count': len(participants),
            'emotion_count': len(emotions),
            'team_emotion_summary': _generate_team_emotion_summary(emotions),
            'participant_insights': [],
            'team_insights': _generate_team_insights(emotions, participants),
            'generated_at': datetime.utcnow().isoformat()
        }
        
        # Generate anonymized insights for each participant
        for participant in participants:
            user_emotions = emotions_by_user.get(participant.user_id, [])
            
            # Skip if no emotions recorded
            if not user_emotions:
                continue
                
            # Create anonymized participant reflection
            participant_reflection = {
                'participant_id': f"P{participant.id}",  # Anonymized ID
                'emotion_count': len(user_emotions),
                'dominant_emotion': _get_dominant_emotion(user_emotions),
                'participation_score': participant.participation_score,
                'message_count': participant.message_count,
                'joined_at': participant.joined_at.isoformat() if participant.joined_at else None,
                'left_at': participant.left_at.isoformat() if participant.left_at else None
            }
            
            team_reflection['participant_insights'].append(participant_reflection)
        
        return jsonify(team_reflection), 200
        
    except Exception as e:
        current_app.logger.error(f"Get team reflection error: {str(e)}")
        return jsonify({'error': 'Failed to generate team reflection'}), 500

@reflection_bp.route('/journal/<int:session_id>', methods=['POST'])
@jwt_required()
def create_journal_reflection(session_id):
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        # Verify session access
        session = Session.query.get(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Verify user participated in session
        participant = SessionParticipant.query.filter_by(
            session_id=session_id,
            user_id=current_user_id
        ).first()
        
        if not participant:
            return jsonify({'error': 'You did not participate in this session'}), 403
        
        # Check if journal already exists
        existing_journal = Journal.query.filter_by(
            user_id=current_user_id,
            session_id=session_id
        ).first()
        
        if existing_journal:
            # Update existing journal
            existing_journal.title = data.get('title', existing_journal.title)
            existing_journal.content = data.get('content', existing_journal.content)
            existing_journal.updated_at = datetime.utcnow()
            
            if 'is_private' in data:
                existing_journal.is_private = data['is_private']
            if 'allow_ai_analysis' in data:
                existing_journal.allow_ai_analysis = data['allow_ai_analysis']
            if 'share_insights' in data:
                existing_journal.share_insights = data['share_insights']
            
            db.session.commit()
            
            return jsonify({
                'message': 'Journal updated successfully',
                'journal': existing_journal.to_dict()
            }), 200
        else:
            # Create new journal
            if not data.get('content'):
                return jsonify({'error': 'Journal content is required'}), 400
            
            journal = Journal(
                user_id=current_user_id,
                session_id=session_id,
                title=data.get('title', f"Reflection on {session.title}"),
                content=data['content'],
                is_private=data.get('is_private', True),
                allow_ai_analysis=data.get('allow_ai_analysis', True),
                share_insights=data.get('share_insights', False)
            )
            
            db.session.add(journal)
            db.session.commit()
            
            # If AI analysis is allowed, queue it for processing
            if journal.allow_ai_analysis:
                # This would typically be handled by a background task
                # For now, we'll just set a flag
                journal.analysis_completed = False
                db.session.commit()
            
            return jsonify({
                'message': 'Journal created successfully',
                'journal': journal.to_dict()
            }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Create journal reflection error: {str(e)}")
        return jsonify({'error': 'Failed to create journal reflection'}), 500

@reflection_bp.route('/journal/<int:session_id>', methods=['GET'])
@jwt_required()
def get_journal_reflection(session_id):
    try:
        current_user_id = get_jwt_identity()
        
        # Verify session access
        session = Session.query.get(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Get journal entry
        journal = Journal.query.filter_by(
            user_id=current_user_id,
            session_id=session_id
        ).first()
        
        if not journal:
            return jsonify({
                'message': 'No journal entry found for this session',
                'has_journal': False
            }), 200
        
        # Get personal reflection to combine with journal
        emotions = EmotionData.query.filter_by(
            user_id=current_user_id,
            session_id=session_id
        ).all()
        
        reflection = suggestion_generator.generate_personal_reflection(
            current_user_id, 
            session_id, 
            emotions
        )
        
        return jsonify({
            'has_journal': True,
            'journal': journal.to_dict(include_analysis=True),
            'reflection': reflection
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get journal reflection error: {str(e)}")
        return jsonify({'error': 'Failed to get journal reflection'}), 500

def _generate_team_emotion_summary(emotions):
    """Generate a summary of team emotions"""
    if not emotions:
        return {}
    
    # Calculate emotion distribution
    emotion_counts = {}
    for emotion in emotions:
        emotion_type = emotion.emotion_type.value
        if emotion_type not in emotion_counts:
            emotion_counts[emotion_type] = 0
        emotion_counts[emotion_type] += 1
    
    total_emotions = len(emotions)
    emotion_distribution = {
        emotion: (count / total_emotions) * 100 
        for emotion, count in emotion_counts.items()
    }
    
    # Calculate emotional stability
    intensities = [e.intensity for e in emotions]
    emotional_stability = 1.0 - (statistics.stdev(intensities) if len(intensities) > 1 else 0)
    
    # Determine dominant emotion
    dominant_emotion = max(emotion_counts, key=emotion_counts.get) if emotion_counts else "neutral"
    
    return {
        'total_emotions_tracked': total_emotions,
        'dominant_emotion': dominant_emotion,
        'emotion_distribution': emotion_distribution,
        'emotional_stability': round(emotional_stability, 2),
        'average_intensity': round(statistics.mean(intensities), 2) if intensities else 0
    }

def _generate_team_insights(emotions, participants):
    """Generate insights about team dynamics"""
    if not emotions or not participants:
        return []
    
    insights = []
    
    # Calculate participation metrics
    participation_scores = [p.participation_score for p in participants if p.participation_score > 0]
    if participation_scores:
        avg_participation = sum(participation_scores) / len(participation_scores)
        participation_variance = statistics.stdev(participation_scores) if len(participation_scores) > 1 else 0
        
        if participation_variance > 0.3:
            insights.append("There was significant variance in participation levels across the team.")
        elif avg_participation > 0.7:
            insights.append("The team showed strong overall engagement during this session.")
        elif avg_participation < 0.4:
            insights.append("Team engagement was lower than optimal during this session.")
    
    # Analyze emotion patterns
    positive_emotions = [e for e in emotions if e.emotion_type.value in ["happy", "excited"]]
    negative_emotions = [e for e in emotions if e.emotion_type.value in ["sad", "angry", "stressed"]]
    
    positive_percentage = len(positive_emotions) / len(emotions) if emotions else 0
    negative_percentage = len(negative_emotions) / len(emotions) if emotions else 0
    
    if positive_percentage > 0.7:
        insights.append("The team experienced predominantly positive emotions.")
    elif negative_percentage > 0.7:
        insights.append("The team experienced predominantly negative emotions.")
    
    return insights

def _get_dominant_emotion(emotions):
    if not emotions:
        return "neutral"
    emotion_counts = {}
    for e in emotions:
        emotion = getattr(e, 'emotion', None)
        if emotion:
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
    return max(emotion_counts, key=emotion_counts.get) if emotion_counts else "neutral"
