import re
import google.generativeai as genai
import os
from dotenv import load_dotenv
from typing import Dict, Any, Optional
from datetime import datetime
from models.emotion import *
from models.session import Session
from models.user import UserRole
from app import db
from flask import current_app
import json

class EmotionAnalyzer:
    """
    Emotion analysis engine for ScrumMood
    This is a simplified implementation - in production, you would integrate
    with actual ML models for emotion detection
    """
    
    def __init__(self):
        load_dotenv()
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
        # Initialize emotion patterns and weights
        self.emotion_patterns = {
            'happy': [
                r'\b(happy|joy|excited|great|awesome|fantastic|amazing|wonderful|good|excellent|love|like)\b',
                r'(😊|😃|😄|😁|😆|🥳|🎉|👍|❤️|💖)'
            ],
            'sad': [
                r'\b(sad|disappointed|down|depressed|unhappy|terrible|awful|bad|hate|dislike)\b',
                r'(😢|😭|😞|😔|💔|😿)'
            ],
            'angry': [
                r'\b(angry|mad|furious|annoyed|frustrated|irritated|pissed|rage)\b',
                r'(😠|😡|🤬|💢|😤)'
            ],
            'stressed': [
                r'\b(stressed|overwhelmed|pressure|deadline|rush|panic|anxious|worried|nervous)\b',
                r'(😰|😥|😓|🤯|😖)'
            ],
            'confused': [
                r'\b(confused|unclear|lost|don\'t understand|what|why|how|puzzled)\b',
                r'(😕|😵|🤔|😯|❓)'
            ],
            'neutral': [
                r'\b(okay|fine|normal|usual|regular|standard|average)\b',
                r'(😐|😑|🙂)'
            ]
        }
        
        # Intensity modifiers
        self.intensity_modifiers = {
            'very': 1.5,
            'really': 1.4,
            'extremely': 1.8,
            'super': 1.6,
            'quite': 1.2,
            'somewhat': 0.8,
            'a bit': 0.7,
            'slightly': 0.6,
            'not': -0.5,
            'barely': 0.3
        }
    
    def analyze_text(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Analyze emotion from text input
        """
        try:
            model = genai.GenerativeModel('gemini-pro')
            prompt_content = f'''
Analyze the sentiment and dominant emotion of the following text.
Provide the output in a JSON format. The JSON should have the following keys:
- "emotion": The single dominant emotion (string, one of: happy, sad, angry, stressed, neutral, confused, excited).
- "intensity": The intensity of the dominant emotion (float, 0.0 to 1.0).
- "confidence": The confidence of your analysis (float, 0.0 to 1.0).
- "sentiment_score": The overall sentiment score (-1.0 for very negative, 1.0 for very positive, 0.0 for neutral).
- "all_emotions_breakdown": An optional dictionary showing scores for all emotions (e.g., {"happy": 0.7, "neutral": 0.2, ...}). If not available, omit or leave empty.
- "explanation": A short textual explanation of the analysis.

Text: "{text}"
'''
            response = model.generate_content(prompt_content)
            response_text = response.text.strip()
            parsed_json = json.loads(response_text)
            return {
                'emotion': parsed_json.get('emotion', 'neutral'),
                'intensity': parsed_json.get('intensity', 0.5),
                'confidence': parsed_json.get('confidence', 0.5),
                'sentiment_score': parsed_json.get('sentiment_score', 0.0),
                'all_emotions': parsed_json.get('all_emotions_breakdown', {}),
                'metadata': {
                    'gemini_raw_response': response_text,
                    'explanation': parsed_json.get('explanation', 'No explanation provided.'),
                    'analysis_timestamp': datetime.utcnow().isoformat(),
                    'analyzer_version': 'Gemini-1.0'
                }
            }
        except Exception as e:
            current_app.logger.error(f"Error during Gemini text analysis: {e}")
            return {
                'emotion': 'neutral',
                'intensity': 0.5,
                'confidence': 0.1,
                'sentiment_score': 0.0,
                'all_emotions': {},
                'metadata': {
                    'error': str(e),
                    'analysis_timestamp': datetime.utcnow().isoformat(),
                    'analyzer_version': 'Fallback-1.0'
                }
            }
    
    def analyze_voice(self, audio_features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Analyze emotion from voice/audio features
        This is a placeholder - in production, you would use actual audio processing
        """
        # Placeholder implementation
        # In reality, you would analyze pitch, tone, speaking rate, etc.
        
        # Extract mock features
        pitch = audio_features.get('pitch', 0.5)
        energy = audio_features.get('energy', 0.5)
        speaking_rate = audio_features.get('speaking_rate', 0.5)
        
        # Simple heuristic-based emotion detection
        if energy > 0.8 and pitch > 0.7:
            emotion = 'excited' if speaking_rate > 0.6 else 'happy'
            intensity = min(energy, 0.9)
        elif energy < 0.3 and pitch < 0.4:
            emotion = 'sad'
            intensity = 1.0 - energy
        elif speaking_rate > 0.8 and energy > 0.6:
            emotion = 'stressed'
            intensity = speaking_rate * 0.8
        else:
            emotion = 'neutral'
            intensity = 0.5
        
        return {
            'emotion': emotion,
            'intensity': round(intensity, 3),
            'confidence': 0.7,  # Lower confidence for voice analysis
            'metadata': {
                'audio_features': audio_features,
                'analysis_timestamp': datetime.utcnow().isoformat(),
                'analyzer_type': 'voice',
                'analyzer_version': '1.0.0'
            }
        }
    
    def analyze_facial(self, facial_features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Analyze emotion from facial expression features
        This is a placeholder - in production, you would use actual computer vision
        """
        # Placeholder implementation
        # In reality, you would analyze facial landmarks, expressions, etc.
        
        # Extract mock features
        smile_score = facial_features.get('smile', 0.5)
        eyebrow_position = facial_features.get('eyebrow_position', 0.5)
        eye_openness = facial_features.get('eye_openness', 0.5)
        
        # Simple heuristic-based emotion detection
        if smile_score > 0.7:
            emotion = 'happy'
            intensity = smile_score
        elif eyebrow_position < 0.3 and eye_openness < 0.4:
            emotion = 'sad'
            intensity = 1.0 - eye_openness
        elif eyebrow_position < 0.2:
            emotion = 'angry'
            intensity = 1.0 - eyebrow_position
        else:
            emotion = 'neutral'
            intensity = 0.5
        
        return {
            'emotion': emotion,
            'intensity': round(intensity, 3),
            'confidence': 0.8,  # Higher confidence for facial analysis
            'metadata': {
                'facial_features': facial_features,
                'analysis_timestamp': datetime.utcnow().isoformat(),
                'analyzer_type': 'facial',
                'analyzer_version': '1.0.0'
            }
        }
    
    def get_emotion_insights(self, emotions_list: list) -> Dict[str, Any]:
        """
        Generate insights from a list of emotions
        """
        if not emotions_list:
            return {}
        
        # Calculate overall emotion distribution
        emotion_counts = {}
        total_intensity = {}
        
        for emotion_data in emotions_list:
            emotion_type = emotion_data['emotion_type']
            intensity = emotion_data['intensity']
            
            if emotion_type not in emotion_counts:
                emotion_counts[emotion_type] = 0
                total_intensity[emotion_type] = 0.0
            
            emotion_counts[emotion_type] += 1
            total_intensity[emotion_type] += intensity
        
        # Calculate percentages and averages
        total_emotions = len(emotions_list)
        insights = {
            'emotion_distribution': {},
            'dominant_emotion': None,
            'average_intensity': 0.0,
            'emotional_stability': 0.0,
            'recommendations': []
        }
        
        for emotion_type in emotion_counts:
            count = emotion_counts[emotion_type]
            avg_intensity = total_intensity[emotion_type] / count
            percentage = (count / total_emotions) * 100
            
            insights['emotion_distribution'][emotion_type] = {
                'count': count,
                'percentage': round(percentage, 2),
                'average_intensity': round(avg_intensity, 3)
            }
        
        # Find dominant emotion
        if emotion_counts:
            insights['dominant_emotion'] = max(emotion_counts, key=emotion_counts.get)
        
        # Calculate overall average intensity
        all_intensities = [e['intensity'] for e in emotions_list]
        insights['average_intensity'] = round(sum(all_intensities) / len(all_intensities), 3)
        
        # Calculate emotional stability (lower variance = more stable)
        intensity_variance = sum((i - insights['average_intensity']) ** 2 for i in all_intensities) / len(all_intensities)
        insights['emotional_stability'] = round(1.0 - min(intensity_variance, 1.0), 3)
        
        # Generate recommendations
        insights['recommendations'] = self._generate_recommendations(insights)
        
        return insights
    
    def _generate_recommendations(self, insights: Dict[str, Any]) -> list:
        """
        Generate recommendations based on emotion insights
        """
        recommendations = []
        dominant_emotion = insights.get('dominant_emotion')
        emotion_dist = insights.get('emotion_distribution', {})
        
        # High stress detection
        stress_percentage = emotion_dist.get('stressed', {}).get('percentage', 0)
        if stress_percentage > 30:
            recommendations.append({
                'type': 'break',
                'priority': 'high',
                'message': 'Team stress levels are elevated. Consider taking a 5-minute break.'
            })
        
        # Low engagement detection
        neutral_percentage = emotion_dist.get('neutral', {}).get('percentage', 0)
        if neutral_percentage > 60:
            recommendations.append({
                'type': 'energizer',
                'priority': 'medium',
                'message': 'Team energy seems low. Consider a quick team energizer activity.'
            })
        
        # Negative emotion detection
        negative_emotions = ['sad', 'angry', 'stressed']
        negative_percentage = sum(emotion_dist.get(e, {}).get('percentage', 0) for e in negative_emotions)
        if negative_percentage > 40:
            recommendations.append({
                'type': 'check_in',
                'priority': 'high',
                'message': 'Negative emotions detected. Consider checking in with team members individually.'
            })
        
        # Low emotional stability
        if insights.get('emotional_stability', 1.0) < 0.5:
            recommendations.append({
                'type': 'discussion',
                'priority': 'medium',
                'message': 'Emotional fluctuations detected. Consider addressing team concerns.'
            })
        
        return recommendations
