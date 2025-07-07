from extensions import db
from datetime import datetime
from enum import Enum

class ReminderType(Enum):
    SESSION_START = "session_start"
    BREAK_TIME = "break_time"
    CHECK_IN = "check_in"
    FOLLOW_UP = "follow_up"
    ENERGIZER = "energizer"

class ReminderStatus(Enum):
    SCHEDULED = "scheduled"
    SENT = "sent"
    DISMISSED = "dismissed"
    CANCELLED = "cancelled"

class Reminder(db.Model):
    __tablename__ = 'reminders'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.id'))
    
    # Reminder details
    reminder_type = db.Column(db.Enum(ReminderType), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    
    # Timing
    scheduled_time = db.Column(db.DateTime, nullable=False, index=True)
    sent_at = db.Column(db.DateTime)
    
    # Status
    status = db.Column(db.Enum(ReminderStatus), default=ReminderStatus.SCHEDULED)
    
    # Delivery options
    notify_email = db.Column(db.Boolean, default=False)
    notify_push = db.Column(db.Boolean, default=True)
    notify_in_app = db.Column(db.Boolean, default=True)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    extra_data = db.Column('metadata', db.JSON)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'reminder_type': self.reminder_type.value,
            'title': self.title,
            'message': self.message,
            'scheduled_time': self.scheduled_time.isoformat(),
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'status': self.status.value,
            'notify_email': self.notify_email,
            'notify_push': self.notify_push,
            'notify_in_app': self.notify_in_app,
            'created_at': self.created_at.isoformat(),
            'metadata': self.extra_data
        }
