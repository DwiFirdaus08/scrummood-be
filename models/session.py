from app import db
from datetime import datetime
from enum import Enum

class SessionStatus(Enum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class Session(db.Model):
    __tablename__ = 'sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    facilitator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Timing
    scheduled_start = db.Column(db.DateTime, nullable=False)
    scheduled_duration = db.Column(db.Integer, default=15)  # minutes
    actual_start = db.Column(db.DateTime)
    actual_end = db.Column(db.DateTime)
    
    # Status and metadata
    status = db.Column(db.Enum(SessionStatus), default=SessionStatus.SCHEDULED)
    description = db.Column(db.Text)
    agenda = db.Column(db.JSON)  # Store agenda items
    
    # Session settings
    emotion_tracking_enabled = db.Column(db.Boolean, default=True)
    auto_suggestions_enabled = db.Column(db.Boolean, default=True)
    recording_enabled = db.Column(db.Boolean, default=False)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relationships
    participants = db.relationship('SessionParticipant', backref='session', lazy='dynamic')
    emotions = db.relationship('EmotionData', backref='session', lazy='dynamic')
    chat_messages = db.relationship('ChatMessage', backref='session', lazy='dynamic')
    suggestions = db.relationship('AISuggestion', backref='session', lazy='dynamic')
    
    def to_dict(self, include_details=False):
        data = {
            'id': self.id,
            'title': self.title,
            'team_id': self.team_id,
            'facilitator_id': self.facilitator_id,
            'scheduled_start': self.scheduled_start.isoformat(),
            'scheduled_duration': self.scheduled_duration,
            'status': self.status.value,
            'description': self.description,
            'created_at': self.created_at.isoformat()
        }
        
        if include_details:
            data.update({
                'actual_start': self.actual_start.isoformat() if self.actual_start else None,
                'actual_end': self.actual_end.isoformat() if self.actual_end else None,
                'agenda': self.agenda,
                'emotion_tracking_enabled': self.emotion_tracking_enabled,
                'auto_suggestions_enabled': self.auto_suggestions_enabled,
                'recording_enabled': self.recording_enabled,
                'participant_count': self.participants.count(),
                'emotion_count': self.emotions.count(),
                'message_count': self.chat_messages.count()
            })
        
        return data
    
    def get_duration_minutes(self):
        """Get actual session duration in minutes"""
        if self.actual_start and self.actual_end:
            delta = self.actual_end - self.actual_start
            return int(delta.total_seconds() / 60)
        return None

class SessionParticipant(db.Model):
    __tablename__ = 'session_participants'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Participation details
    joined_at = db.Column(db.DateTime)
    left_at = db.Column(db.DateTime)
    is_present = db.Column(db.Boolean, default=False)
    
    # Engagement metrics
    message_count = db.Column(db.Integer, default=0)
    emotion_entries = db.Column(db.Integer, default=0)
    participation_score = db.Column(db.Float, default=0.0)  # 0.0 to 1.0
    
    __table_args__ = (db.UniqueConstraint('session_id', 'user_id'),)
    
    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'joined_at': self.joined_at.isoformat() if self.joined_at else None,
            'left_at': self.left_at.isoformat() if self.left_at else None,
            'is_present': self.is_present,
            'message_count': self.message_count,
            'emotion_entries': self.emotion_entries,
            'participation_score': self.participation_score
        }
