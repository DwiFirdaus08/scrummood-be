from app import db
from datetime import datetime

class Journal(db.Model):
    __tablename__ = 'journals'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.id'))
    
    # Content
    title = db.Column(db.String(200))
    content = db.Column(db.Text, nullable=False)
    reflection_prompts = db.Column(db.JSON)  # Store prompts used
    
    # Analysis
    sentiment_score = db.Column(db.Float)  # -1.0 to 1.0
    emotion_analysis = db.Column(db.JSON)  # Store detected emotions
    keywords = db.Column(db.JSON)  # Store extracted keywords
    analysis_completed = db.Column(db.Boolean, default=False)
    
    # Privacy
    is_private = db.Column(db.Boolean, default=True)
    allow_ai_analysis = db.Column(db.Boolean, default=True)
    share_insights = db.Column(db.Boolean, default=False)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self, include_analysis=False):
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'title': self.title,
            'content': self.content,
            'is_private': self.is_private,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        
        if include_analysis and self.analysis_completed:
            data.update({
                'sentiment_score': self.sentiment_score,
                'emotion_analysis': self.emotion_analysis,
                'keywords': self.keywords,
                'analysis_completed': self.analysis_completed
            })
        
        return data
