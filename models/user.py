from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from enum import Enum

class UserRole(Enum):
    MEMBER = "member"
    FACILITATOR = "facilitator"
    MANAGER = "manager"

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(200), nullable=False)
    role = db.Column(db.Enum(UserRole), default=UserRole.MEMBER, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    timezone = db.Column(db.String(50), default='UTC')
    
    # Privacy settings
    emotion_tracking_enabled = db.Column(db.Boolean, default=True)
    voice_analysis_enabled = db.Column(db.Boolean, default=True)
    facial_analysis_enabled = db.Column(db.Boolean, default=False)
    journal_analysis_enabled = db.Column(db.Boolean, default=True)
    
    # Relationships
    team_memberships = db.relationship('TeamMembership', backref='user', lazy='dynamic')
    emotions = db.relationship('EmotionData', backref='user', lazy='dynamic')
    journals = db.relationship('Journal', backref='user', lazy='dynamic')
    chat_messages = db.relationship('ChatMessage', backref='sender', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self, include_sensitive=False):
        data = {
            'id': self.id,
            'email': self.email,
            'username': self.username,
            'full_name': self.full_name,
            'role': self.role.value,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'timezone': self.timezone
        }
        if include_sensitive:
            data.update({
                'emotion_tracking_enabled': self.emotion_tracking_enabled,
                'voice_analysis_enabled': self.voice_analysis_enabled,
                'facial_analysis_enabled': self.facial_analysis_enabled,
                'journal_analysis_enabled': self.journal_analysis_enabled
            })
        return data

class Team(db.Model):
    __tablename__ = 'teams'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    memberships = db.relationship('TeamMembership', backref='team', lazy='dynamic')
    sessions = db.relationship('Session', backref='team', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat(),
            'is_active': self.is_active,
            'member_count': self.memberships.filter_by(is_active=True).count()
        }

class TeamMembership(db.Model):
    __tablename__ = 'team_memberships'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    role = db.Column(db.Enum(UserRole), default=UserRole.MEMBER)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'team_id'),)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'team_id': self.team_id,
            'role': self.role.value,
            'joined_at': self.joined_at.isoformat(),
            'is_active': self.is_active
        }
