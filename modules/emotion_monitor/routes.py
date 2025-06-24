from flask import request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.emotion import EmotionData, EmotionType, AnalysisSource
from models.session import Session
from models.user import User, UserRole
from app import db, socketio
from . import emotion_bp
from .emotion_analyzer import EmotionAnalyzer
from datetime import datetime
import json

# Initialize emotion analyzer
emotion_analyzer = EmotionAnalyzer()

@emotion_bp.route('/submit', methods=['POST'])
@jwt_required()
def submit_emotion():
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['content', 'source']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Validate source
        try:
            source = AnalysisSource(data['source'])
        except ValueError:
            return jsonify({'error': 'Invalid source type'}), 400
        
        # Get session if provided
        session_id = data.get('session_id')
        if session_id:
            session = Session.query.get(session_id)
            if not session:
                return jsonify({'error': 'Session not found'}), 404
        
        # Analyze emotion based on source
        analysis_result = None
        if source == AnalysisSource.TEXT:
            analysis_result = emotion_analyzer.analyze_text(data['content'])
        elif source == AnalysisSource.VOICE:
            # Handle voice data (would need audio processing)
            analysis_result = emotion_analyzer.analyze_voice(data.get('audio_features', {}))
        elif source == AnalysisSource.FACIAL:
            # Handle facial data (would need image processing)
            analysis_result = emotion_analyzer.analyze_facial(data.get('facial_features', {}))
        elif source == AnalysisSource.MANUAL:
            # Manual input - validate emotion type and intensity
            if not data.get('emotion_type') or not data.get('intensity'):
                return jsonify({'error': 'emotion_type and intensity required for manual input'}), 400
            analysis_result = {
                'emotion': data['emotion_type'],
                'intensity': float(data['intensity']),
                'confidence': 1.0
            }
        
        if not analysis_result:
            return jsonify({'error': 'Failed to analyze emotion'}), 500
        
        # Validate emotion type
        try:
            emotion_type = EmotionType(analysis_result['emotion'])
        except ValueError:
            return jsonify({'error': 'Invalid emotion type detected'}), 400
        
        # Calculate session timestamp if in active session
        session_timestamp = None
        if session and session.actual_start:
            delta = datetime.utcnow() - session.actual_start
            session_timestamp = int(delta.total_seconds())
        
        # Create emotion record
        emotion_data = EmotionData(
            user_id=current_user_id,
            session_id=session_id,
            emotion_type=emotion_type,
            intensity=analysis_result['intensity'],
            confidence=analysis_result['confidence'],
            source=source,
            raw_data={'content': data['content']},
            analysis_metadata=analysis_result.get('metadata', {}),
            session_timestamp=session_timestamp,
            context=data.get('context')
        )
        
        db.session.add(emotion_data)
        db.session.commit()
        
        # Emit real-time update to session participants
        if session_id:
            socketio.emit('emotion_update', {
                'session_id': session_id,
                'user_id': current_user_id,
                'emotion': emotion_data.to_dict()
            }, room=f'session_{session_id}')
        
        return jsonify({
            'message': 'Emotion recorded successfully',
            'emotion': emotion_data.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Submit emotion error: {str(e)}")
        return jsonify({'error': 'Failed to record emotion'}), 500

@emotion_bp.route('/session/<int:session_id>/emotions', methods=['GET'])
@jwt_required()
def get_session_emotions(session_id):
    try:
        current_user_id = get_jwt_identity()
        
        # Verify session access
        session = Session.query.get(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Get query parameters
        user_id = request.args.get('user_id', type=int)
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')
        emotion_type = request.args.get('emotion_type')
        
        # Build query
        query = EmotionData.query.filter_by(session_id=session_id)
        
        if user_id:
            query = query.filter_by(user_id=user_id)
        if start_time:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            query = query.filter(EmotionData.timestamp >= start_dt)
        if end_time:
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            query = query.filter(EmotionData.timestamp <= end_dt)
        if emotion_type:
            try:
                emotion_enum = EmotionType(emotion_type)
                query = query.filter_by(emotion_type=emotion_enum)
            except ValueError:
                return jsonify({'error': 'Invalid emotion type'}), 400
        
        # Order by timestamp
        emotions = query.order_by(EmotionData.timestamp.asc()).all()
        
        return jsonify({
            'emotions': [emotion.to_dict() for emotion in emotions],
            'count': len(emotions)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get session emotions error: {str(e)}")
        return jsonify({'error': 'Failed to get emotions'}), 500

@emotion_bp.route('/session/<int:session_id>/summary', methods=['GET'])
@jwt_required()
def get_emotion_summary(session_id):
    try:
        current_user_id = get_jwt_identity()
        
        # Verify session access
        session = Session.query.get(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Get emotion summary
        summary = EmotionData.get_emotion_summary(session_id=session_id)
        
        # Get per-user summaries
        participants = session.participants.all()
        user_summaries = {}
        
        for participant in participants:
            user_summary = EmotionData.get_emotion_summary(
                user_id=participant.user_id,
                session_id=session_id
            )
            if user_summary:
                user_summaries[participant.user_id] = user_summary
        
        return jsonify({
            'session_summary': summary,
            'user_summaries': user_summaries,
            'session_id': session_id
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get emotion summary error: {str(e)}")
        return jsonify({'error': 'Failed to get emotion summary'}), 500

@emotion_bp.route('/user/history', methods=['GET'])
@jwt_required()
def get_user_emotion_history():
    try:
        current_user_id = get_jwt_identity()
        
        # Get query parameters
        days = request.args.get('days', default=7, type=int)
        emotion_type = request.args.get('emotion_type')
        
        # Calculate date range
        from datetime import timedelta
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        # Build query
        query = EmotionData.query.filter_by(user_id=current_user_id)
        query = query.filter(EmotionData.timestamp >= start_time)
        query = query.filter(EmotionData.timestamp <= end_time)
        
        if emotion_type:
            try:
                emotion_enum = EmotionType(emotion_type)
                query = query.filter_by(emotion_type=emotion_enum)
            except ValueError:
                return jsonify({'error': 'Invalid emotion type'}), 400
        
        # Get emotions ordered by time
        emotions = query.order_by(EmotionData.timestamp.asc()).all()
        
        # Get summary for the period
        summary = EmotionData.get_emotion_summary(
            user_id=current_user_id,
            start_time=start_time,
            end_time=end_time
        )
        
        return jsonify({
            'emotions': [emotion.to_dict() for emotion in emotions],
            'summary': summary,
            'period': {
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'days': days
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get user emotion history error: {str(e)}")
        return jsonify({'error': 'Failed to get emotion history'}), 500

@emotion_bp.route('/analyze/batch', methods=['POST'])
@jwt_required()
def analyze_batch_emotions():
    """Analyze multiple emotions in batch for better performance"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data.get('emotions') or not isinstance(data['emotions'], list):
            return jsonify({'error': 'emotions array is required'}), 400
        
        results = []
        for emotion_input in data['emotions']:
            try:
                # Validate each emotion input
                if not emotion_input.get('content') or not emotion_input.get('source'):
                    continue
                
                # Analyze emotion
                source = AnalysisSource(emotion_input['source'])
                if source == AnalysisSource.TEXT:
                    analysis_result = emotion_analyzer.analyze_text(emotion_input['content'])
                    if analysis_result:
                        results.append({
                            'original_content': emotion_input['content'],
                            'analysis': analysis_result
                        })
            except Exception as e:
                current_app.logger.warning(f"Failed to analyze emotion in batch: {str(e)}")
                continue
        
        return jsonify({
            'results': results,
            'processed_count': len(results),
            'total_count': len(data['emotions'])
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Batch emotion analysis error: {str(e)}")
        return jsonify({'error': 'Failed to analyze emotions'}), 500
