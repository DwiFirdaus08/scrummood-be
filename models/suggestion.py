from app import db
from datetime import datetime
from enum import Enum

class SuggestionType(Enum):
    BREAK = "break"
    DISCUSSION = "discussion"
    BREATHING = "breathing"
    ENERGIZER = "energizer"
    CHECK_IN = "check_in"
    RESTRUCTURE = "restructure"
    SUPPORT = "support"

class SuggestionStatus(Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"
    IMPLEMENTED = "implemented"

class AISuggestion(db.Model):
    __tablename__ = 'ai_suggestions'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.id'), nullable=False)
    
    # Suggestion details
    suggestion_type = db.Column(db.Enum(SuggestionType), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    priority = db.Column(db.Integer, default=1)  # 1=low, 2=medium, 3=high
    
    # Trigger information
    trigger_emotions = db.Column(db.JSON)  # Store emotion data that triggered this
    trigger_threshold = db.Column(db.Float)
    affected_users = db.Column(db.JSON)  # List of user IDs affected
    
    # Implementation
    suggested_duration = db.Column(db.Integer)  # minutes
    implementation_steps = db.Column(db.JSON)
    
    # Status tracking
    status = db.Column(db.Enum(SuggestionStatus), default=SuggestionStatus.PENDING)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    responded_at = db.Column(db.DateTime)
    responded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Feedback
    effectiveness_rating = db.Column(db.Integer)  # 1-5 stars
    feedback_notes = db.Column(db.Text)
    
    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'suggestion_type': self.suggestion_type.value,
            'title': self.title,
            'description': self.description,
            'priority': self.priority,
            'trigger_emotions': self.trigger_emotions,
            'affected_users': self.affected_users,
            'suggested_duration': self.suggested_duration,
            'implementation_steps': self.implementation_steps,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'responded_at': self.responded_at.isoformat() if self.responded_at else None,
            'responded_by': self.responded_by,
            'effectiveness_rating': self.effectiveness_rating,
            'feedback_notes': self.feedback_notes
        }
