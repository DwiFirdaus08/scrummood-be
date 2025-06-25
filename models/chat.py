from models import db
from datetime import datetime
from enum import Enum

class MessageType(Enum):
    TEXT = "text"
    EMOJI = "emoji"
    SYSTEM = "system"
    EMOTION_ALERT = "emotion_alert"

class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # NULL for system messages
    
    # Message content
    content = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.Enum(MessageType), default=MessageType.TEXT)
    extra_data = db.Column('metadata', db.JSON)  # Store additional data (emotion info, etc.)
    
    # Analysis
    emotion_detected = db.Column(db.String(50))
    sentiment_score = db.Column(db.Float)
    
    # Metadata
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    session_timestamp = db.Column(db.Integer)  # Seconds from session start
    is_edited = db.Column(db.Boolean, default=False)
    edited_at = db.Column(db.DateTime)
    
    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'sender_id': self.sender_id,
            'content': self.content,
            'message_type': self.message_type.value,
            'metadata': self.extra_data,
            'emotion_detected': self.emotion_detected,
            'sentiment_score': self.sentiment_score,
            'timestamp': self.timestamp.isoformat(),
            'session_timestamp': self.session_timestamp,
            'is_edited': self.is_edited,
            'edited_at': self.edited_at.isoformat() if self.edited_at else None
        }
