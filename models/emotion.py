from app import db
from datetime import datetime
from enum import Enum

class EmotionType(Enum):
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    FEAR = "fear"
    SURPRISE = "surprise"
    DISGUST = "disgust"
    NEUTRAL = "neutral"
    STRESSED = "stressed"
    EXCITED = "excited"
    CONFUSED = "confused"

class AnalysisSource(Enum):
    TEXT = "text"
    VOICE = "voice"
    FACIAL = "facial"
    MANUAL = "manual"

class EmotionData(db.Model):
    __tablename__ = 'emotion_data'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.id'))
    
    # Emotion information
    emotion_type = db.Column(db.Enum(EmotionType), nullable=False)
    intensity = db.Column(db.Float, nullable=False)  # 0.0 to 1.0
    confidence = db.Column(db.Float, default=0.0)  # AI confidence score
    
    # Analysis details
    source = db.Column(db.Enum(AnalysisSource), nullable=False)
    raw_data = db.Column(db.JSON)  # Store original input (text, audio features, etc.)
    analysis_metadata = db.Column(db.JSON)  # Store AI model outputs, features, etc.
    
    # Timing
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    session_timestamp = db.Column(db.Integer)  # Seconds from session start
    
    # Context
    context = db.Column(db.String(500))  # Optional context description
    is_processed = db.Column(db.Boolean, default=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'emotion_type': self.emotion_type.value,
            'intensity': self.intensity,
            'confidence': self.confidence,
            'source': self.source.value,
            'timestamp': self.timestamp.isoformat(),
            'session_timestamp': self.session_timestamp,
            'context': self.context,
            'raw_data': self.raw_data,
            'analysis_metadata': self.analysis_metadata
        }
    
    @staticmethod
    def get_emotion_summary(user_id=None, session_id=None, start_time=None, end_time=None):
        """Get aggregated emotion statistics"""
        query = EmotionData.query
        
        if user_id:
            query = query.filter(EmotionData.user_id == user_id)
        if session_id:
            query = query.filter(EmotionData.session_id == session_id)
        if start_time:
            query = query.filter(EmotionData.timestamp >= start_time)
        if end_time:
            query = query.filter(EmotionData.timestamp <= end_time)
        
        emotions = query.all()
        
        if not emotions:
            return {}
        
        # Calculate emotion distribution
        emotion_counts = {}
        total_intensity = {}
        
        for emotion in emotions:
            emotion_type = emotion.emotion_type.value
            if emotion_type not in emotion_counts:
                emotion_counts[emotion_type] = 0
                total_intensity[emotion_type] = 0.0
            
            emotion_counts[emotion_type] += 1
            total_intensity[emotion_type] += emotion.intensity
        
        # Calculate averages and percentages
        total_emotions = len(emotions)
        summary = {}
        
        for emotion_type in emotion_counts:
            count = emotion_counts[emotion_type]
            avg_intensity = total_intensity[emotion_type] / count
            percentage = (count / total_emotions) * 100
            
            summary[emotion_type] = {
                'count': count,
                'percentage': round(percentage, 2),
                'average_intensity': round(avg_intensity, 3)
            }
        
        return summary
