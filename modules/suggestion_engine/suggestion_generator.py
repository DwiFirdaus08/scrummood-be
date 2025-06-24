from typing import List, Dict, Any
from models.emotion import EmotionData, EmotionType
from models.session import Session
from models.suggestion import *
from datetime import datetime, timedelta
import statistics
from app import db

class SuggestionGenerator:
    """
    AI-powered suggestion generator for ScrumMood
    Analyzes team emotions and generates contextual recommendations
    """
    
    def __init__(self):
        self.suggestion_templates = {
            # Team-level suggestions
            'break': {
                'title': 'Take a Break',
                'description': 'Team stress levels are elevated. A short break can help reset and improve focus.',
                'default_duration': 5,
                'steps': [
                    'Pause the current discussion',
                    'Allow team members to step away from their screens',
                    'Encourage light stretching or deep breathing',
                    'Return refreshed and focused'
                ]
            },
            'breathing': {
                'title': 'Breathing Exercise',
                'description': 'Guide the team through a quick breathing exercise to reduce tension.',
                'default_duration': 2,
                'steps': [
                    'Ask everyone to sit comfortably',
                    'Guide 4-7-8 breathing: inhale for 4, hold for 7, exhale for 8',
                    'Repeat 3-4 cycles',
                    'Return to the discussion with renewed focus'
                ]
            },
            'energizer': {
                'title': 'Team Energizer',
                'description': 'Team energy is low. A quick energizing activity can boost engagement.',
                'default_duration': 3,
                'steps': [
                    'Choose a quick icebreaker or energizer game',
                    'Get everyone to participate actively',
                    'Keep it light and fun',
                    'Transition back to work topics'
                ]
            },
            'check_in': {
                'title': 'Individual Check-in',
                'description': 'Some team members may need individual attention. Consider private follow-ups.',
                'default_duration': 0,
                'steps': [
                    'Note team members showing signs of distress',
                    'Schedule brief 1-on-1 conversations after the meeting',
                    'Ask open-ended questions about their well-being',
                    'Offer support and resources as needed'
                ]
            },
            'discussion': {
                'title': 'Open Discussion',
                'description': 'Address team concerns through structured discussion.',
                'default_duration': 10,
                'steps': [
                    'Acknowledge that you sense some team tension',
                    'Ask for feedback on current processes or challenges',
                    'Listen actively and validate concerns',
                    'Collaborate on solutions'
                ]
            },
            'restructure': {
                'title': 'Restructure Meeting',
                'description': 'Consider changing the meeting format to better suit current team needs.',
                'default_duration': 0,
                'steps': [
                    'Assess if the current agenda is causing stress',
                    'Consider postponing non-urgent items',
                    'Focus on essential topics only',
                    'Schedule follow-up meetings for complex discussions'
                ]
            },
            
            # Individual-level suggestions
            'personal_break': {
                'title': 'Take a Personal Break',
                'description': 'Your stress levels appear elevated. Consider taking a short personal break.',
                'default_duration': 5,
                'steps': [
                    'Step away from your screen for a few minutes',
                    'Practice deep breathing or stretching',
                    'Get a glass of water',
                    'Return when you feel more centered'
                ],
                'is_personal': True
            },
            'stress_management': {
                'title': 'Stress Management Technique',
                'description': 'Try this quick stress management technique to help you regain focus.',
                'default_duration': 2,
                'steps': [
                    'Take 5 deep breaths',
                    'Identify what\'s causing your stress',
                    'Focus on what you can control',
                    'Set a small, achievable goal for the next few minutes'
                ],
                'is_personal': True
            },
            'engagement_boost': {
                'title': 'Boost Your Engagement',
                'description': 'Your engagement appears to be lower than usual. Here are some ways to reconnect.',
                'default_duration': 0,
                'steps': [
                    'Ask a question about the current topic',
                    'Share a relevant insight or experience',
                    'Take notes to help focus your attention',
                    'Consider if there\'s something specific causing your disengagement'
                ],
                'is_personal': True
            },
            'emotional_regulation': {
                'title': 'Emotional Regulation',
                'description': 'Your emotions appear to be fluctuating. Try these techniques to find balance.',
                'default_duration': 0,
                'steps': [
                    'Label your emotions specifically (not just "upset" but "frustrated" or "disappointed")',
                    'Accept your emotions without judgment',
                    'Consider the trigger for your emotional response',
                    'Choose a constructive way to express your feelings'
                ],
                'is_personal': True
            },
            'communication_adjustment': {
                'title': 'Adjust Your Communication',
                'description': 'Consider adjusting your communication style to better express your thoughts.',
                'default_duration': 0,
                'steps': [
                    'Use "I" statements to express your perspective',
                    'Be specific about your concerns',
                    'Ask clarifying questions',
                    'Acknowledge others\' viewpoints before sharing yours'
                ],
                'is_personal': True
            }
        }
        
        # Thresholds for triggering suggestions
        self.thresholds = {
            'stress_high': 0.7,
            'stress_team_percentage': 0.3,  # 30% of team showing stress
            'negative_emotions_percentage': 0.4,  # 40% negative emotions
            'low_energy_percentage': 0.6,  # 60% neutral/low energy
            'emotional_volatility': 0.5,
            
            # Individual thresholds
            'individual_stress_high': 0.65,
            'individual_negative_high': 0.6,
            'individual_low_energy': 0.7,
            'individual_volatility': 0.4
        }
    
    def analyze_and_suggest(self, emotions: List[EmotionData], session: Session) -> List[Dict[str, Any]]:
        """
        Analyze emotions and generate appropriate suggestions for both team and individuals
        """
        if not emotions:
            return []
        
        suggestions = []
        
        # Analyze current emotional state
        analysis = self._analyze_emotions(emotions)
        
        # Generate team-level suggestions based on analysis
        if analysis['high_stress_users']:
            suggestions.extend(self._generate_stress_suggestions(analysis, session))
        
        if analysis['low_energy_percentage'] > self.thresholds['low_energy_percentage']:
            suggestions.extend(self._generate_energy_suggestions(analysis, session))
        
        if analysis['negative_percentage'] > self.thresholds['negative_emotions_percentage']:
            suggestions.extend(self._generate_support_suggestions(analysis, session))
        
        if analysis['emotional_volatility'] > self.thresholds['emotional_volatility']:
            suggestions.extend(self._generate_stability_suggestions(analysis, session))
        
        # Generate individual-level suggestions
        individual_suggestions = self._generate_individual_suggestions(analysis, session)
        suggestions.extend(individual_suggestions)
        
        # Remove duplicates and prioritize
        team_suggestions = self._prioritize_suggestions([s for s in suggestions if not s.get('is_personal', False)])
        personal_suggestions = [s for s in suggestions if s.get('is_personal', False)]
        
        # Combine and return
        return team_suggestions[:2] + personal_suggestions  # Return top 2 team suggestions + all personal ones
    
    def _analyze_emotions(self, emotions: List[EmotionData]) -> Dict[str, Any]:
        """
        Analyze emotion data to extract insights for both team and individuals
        """
        emotion_by_user = {}
        all_emotions = []
        
        # Group emotions by user
        for emotion in emotions:
            user_id = emotion.user_id
            if user_id not in emotion_by_user:
                emotion_by_user[user_id] = []
            emotion_by_user[user_id].append(emotion)
            all_emotions.append(emotion)
        
        # Calculate team statistics
        stress_emotions = [e for e in all_emotions if e.emotion_type == EmotionType.STRESSED]
        negative_emotions = [e for e in all_emotions if e.emotion_type in [EmotionType.SAD, EmotionType.ANGRY, EmotionType.STRESSED]]
        neutral_emotions = [e for e in all_emotions if e.emotion_type == EmotionType.NEUTRAL]
        
        # Identify high-stress users
        high_stress_users = []
        
        # Calculate individual user metrics
        user_metrics = {}
        for user_id, user_emotions in emotion_by_user.items():
            # Calculate stress metrics
            user_stress_emotions = [e for e in user_emotions if e.emotion_type == EmotionType.STRESSED]
            avg_stress_intensity = statistics.mean([e.intensity for e in user_stress_emotions]) if user_stress_emotions else 0
            
            # Calculate negative emotion metrics
            user_negative_emotions = [e for e in user_emotions if e.emotion_type in [EmotionType.SAD, EmotionType.ANGRY, EmotionType.STRESSED]]
            negative_percentage = len(user_negative_emotions) / len(user_emotions) if user_emotions else 0
            
            # Calculate neutral/low energy metrics
            user_neutral_emotions = [e for e in user_emotions if e.emotion_type == EmotionType.NEUTRAL]
            neutral_percentage = len(user_neutral_emotions) / len(user_emotions) if user_emotions else 0
            
            # Calculate emotional volatility
            user_intensities = [e.intensity for e in user_emotions]
            user_volatility = statistics.stdev(user_intensities) if len(user_intensities) > 1 else 0
            
            # Store user metrics
            user_metrics[user_id] = {
                'stress_level': avg_stress_intensity,
                'negative_percentage': negative_percentage,
                'neutral_percentage': neutral_percentage,
                'emotional_volatility': user_volatility,
                'emotion_count': len(user_emotions),
                'dominant_emotion': self._get_dominant_emotion(user_emotions),
                'needs_attention': False  # Will be set based on thresholds
            }
            
            # Check if user needs attention
            if avg_stress_intensity > self.thresholds['individual_stress_high']:
                high_stress_users.append({
                    'user_id': user_id,
                    'stress_level': avg_stress_intensity,
                    'emotion_count': len(user_emotions)
                })
                user_metrics[user_id]['needs_attention'] = True
            elif negative_percentage > self.thresholds['individual_negative_high']:
                user_metrics[user_id]['needs_attention'] = True
            elif neutral_percentage > self.thresholds['individual_low_energy']:
                user_metrics[user_id]['needs_attention'] = True
            elif user_volatility > self.thresholds['individual_volatility']:
                user_metrics[user_id]['needs_attention'] = True
        
        # Calculate team emotional volatility
        intensities = [e.intensity for e in all_emotions]
        emotional_volatility = statistics.stdev(intensities) if len(intensities) > 1 else 0
        
        return {
            'total_emotions': len(all_emotions),
            'unique_users': len(emotion_by_user),
            'stress_count': len(stress_emotions),
            'negative_count': len(negative_emotions),
            'neutral_count': len(neutral_emotions),
            'negative_percentage': len(negative_emotions) / len(all_emotions) if all_emotions else 0,
            'low_energy_percentage': len(neutral_emotions) / len(all_emotions) if all_emotions else 0,
            'high_stress_users': high_stress_users,
            'emotional_volatility': emotional_volatility,
            'average_intensity': statistics.mean(intensities) if intensities else 0,
            'user_metrics': user_metrics  # Individual user metrics
        }
    
    def _get_dominant_emotion(self, emotions: List[EmotionData]) -> str:
        """
        Determine the dominant emotion from a list of emotions
        """
        if not emotions:
            return "neutral"
        
        emotion_counts = {}
        for emotion in emotions:
            emotion_type = emotion.emotion_type.value
            if emotion_type not in emotion_counts:
                emotion_counts[emotion_type] = 0
            emotion_counts[emotion_type] += 1
        
        return max(emotion_counts, key=emotion_counts.get)
    
    def _generate_stress_suggestions(self, analysis: Dict[str, Any], session: Session) -> List[Dict[str, Any]]:
        """
        Generate suggestions for high stress situations
        """
        suggestions = []
        
        stress_percentage = analysis['stress_count'] / analysis['total_emotions'] if analysis['total_emotions'] > 0 else 0
        
        if stress_percentage > self.thresholds['stress_team_percentage']:
            # Team-wide stress
            if stress_percentage > 0.5:  # Very high stress
                suggestions.append(self._create_suggestion(
                    'break',
                    priority=3,
                    trigger_emotions=analysis,
                    affected_users=[user['user_id'] for user in analysis['high_stress_users']]
                ))
            else:
                suggestions.append(self._create_suggestion(
                    'breathing',
                    priority=2,
                    trigger_emotions=analysis,
                    affected_users=[user['user_id'] for user in analysis['high_stress_users']]
                ))
        
        # Individual stress check-ins
        if len(analysis['high_stress_users']) > 0:
            suggestions.append(self._create_suggestion(
                'check_in',
                priority=2,
                trigger_emotions=analysis,
                affected_users=[user['user_id'] for user in analysis['high_stress_users']]
            ))
        
        return suggestions
    
    def _generate_energy_suggestions(self, analysis: Dict[str, Any], session: Session) -> List[Dict[str, Any]]:
        """
        Generate suggestions for low energy situations
        """
        suggestions = []
        
        if analysis['low_energy_percentage'] > self.thresholds['low_energy_percentage']:
            suggestions.append(self._create_suggestion(
                'energizer',
                priority=2,
                trigger_emotions=analysis,
                affected_users=list(analysis['user_metrics'].keys())  # Affects whole team
            ))
        
        return suggestions
    
    def _generate_support_suggestions(self, analysis: Dict[str, Any], session: Session) -> List[Dict[str, Any]]:
        """
        Generate suggestions for negative emotions
        """
        suggestions = []
        
        if analysis['negative_percentage'] > self.thresholds['negative_emotions_percentage']:
            suggestions.append(self._create_suggestion(
                'discussion',
                priority=3,
                trigger_emotions=analysis,
                affected_users=list(analysis['user_metrics'].keys())
            ))
        
        return suggestions
    
    def _generate_stability_suggestions(self, analysis: Dict[str, Any], session: Session) -> List[Dict[str, Any]]:
        """
        Generate suggestions for emotional volatility
        """
        suggestions = []
        
        if analysis['emotional_volatility'] > self.thresholds['emotional_volatility']:
            suggestions.append(self._create_suggestion(
                'restructure',
                priority=2,
                trigger_emotions=analysis,
                affected_users=list(analysis['user_metrics'].keys())
            ))
        
        return suggestions
    
    def _generate_individual_suggestions(self, analysis: Dict[str, Any], session: Session) -> List[Dict[str, Any]]:
        """
        Generate personalized suggestions for individual team members
        """
        suggestions = []
        
        for user_id, metrics in analysis['user_metrics'].items():
            if not metrics['needs_attention']:
                continue
                
            # Generate personalized suggestion based on dominant issue
            if metrics['stress_level'] > self.thresholds['individual_stress_high']:
                # High stress - suggest personal break or stress management
                suggestion_type = 'personal_break' if metrics['stress_level'] > 0.8 else 'stress_management'
                suggestions.append(self._create_personal_suggestion(
                    suggestion_type,
                    user_id,
                    metrics,
                    priority=3 if metrics['stress_level'] > 0.8 else 2
                ))
                
            elif metrics['neutral_percentage'] > self.thresholds['individual_low_energy']:
                # Low energy/engagement - suggest engagement boost
                suggestions.append(self._create_personal_suggestion(
                    'engagement_boost',
                    user_id,
                    metrics,
                    priority=2
                ))
                
            elif metrics['emotional_volatility'] > self.thresholds['individual_volatility']:
                # Emotional volatility - suggest emotional regulation
                suggestions.append(self._create_personal_suggestion(
                    'emotional_regulation',
                    user_id,
                    metrics,
                    priority=2
                ))
                
            elif metrics['negative_percentage'] > self.thresholds['individual_negative_high']:
                # High negative emotions - suggest communication adjustment
                suggestions.append(self._create_personal_suggestion(
                    'communication_adjustment',
                    user_id,
                    metrics,
                    priority=2
                ))
        
        return suggestions
    
    def _create_suggestion(self, suggestion_type: str, priority: int, trigger_emotions: Dict, affected_users: List[int]) -> Dict[str, Any]:
        """
        Create a team-level suggestion based on template and analysis
        """
        template = self.suggestion_templates[suggestion_type]
        
        return {
            'type': suggestion_type,
            'title': template['title'],
            'description': template['description'],
            'priority': priority,
            'duration': template['default_duration'],
            'steps': template['steps'],
            'trigger_emotions': {
                'total_emotions': trigger_emotions['total_emotions'],
                'negative_percentage': trigger_emotions['negative_percentage'],
                'stress_count': trigger_emotions['stress_count'],
                'emotional_volatility': trigger_emotions['emotional_volatility']
            },
            'affected_users': affected_users,
            'timestamp': datetime.utcnow().isoformat(),
            'is_personal': False
        }
    
    def _create_personal_suggestion(self, suggestion_type: str, user_id: int, metrics: Dict, priority: int) -> Dict[str, Any]:
        """
        Create a personalized suggestion for an individual user
        """
        template = self.suggestion_templates[suggestion_type]
        
        return {
            'type': suggestion_type,
            'title': template['title'],
            'description': template['description'],
            'priority': priority,
            'duration': template['default_duration'],
            'steps': template['steps'],
            'trigger_emotions': {
                'stress_level': metrics['stress_level'],
                'negative_percentage': metrics['negative_percentage'],
                'neutral_percentage': metrics['neutral_percentage'],
                'emotional_volatility': metrics['emotional_volatility'],
                'dominant_emotion': metrics['dominant_emotion']
            },
            'affected_users': [user_id],  # Only affects this specific user
            'user_id': user_id,  # Explicitly mark which user this is for
            'timestamp': datetime.utcnow().isoformat(),
            'is_personal': True  # Mark as a personal suggestion
        }
    
    def _prioritize_suggestions(self, suggestions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sort suggestions by priority and remove duplicates
        """
        # Remove duplicates by type
        seen_types = set()
        unique_suggestions = []
        
        for suggestion in suggestions:
            if suggestion['type'] not in seen_types:
                unique_suggestions.append(suggestion)
                seen_types.add(suggestion['type'])
        
        # Sort by priority (higher first)
        unique_suggestions.sort(key=lambda x: x['priority'], reverse=True)
        
        return unique_suggestions
    
    def generate_personal_reflection(self, user_id: int, session_id: int, emotions: List[EmotionData]) -> Dict[str, Any]:
        """
        Generate a personalized reflection for a user based on their emotions during a session
        """
        if not emotions:
            return {
                'user_id': user_id,
                'session_id': session_id,
                'has_data': False,
                'message': "Not enough emotion data was collected to generate a reflection."
            }
        
        # Analyze user's emotions
        user_emotions = [e for e in emotions if e.user_id == user_id]
        if not user_emotions:
            return {
                'user_id': user_id,
                'session_id': session_id,
                'has_data': False,
                'message': "No emotion data was collected for this user."
            }
        
        # Calculate emotion distribution
        emotion_counts = {}
        for emotion in user_emotions:
            emotion_type = emotion.emotion_type.value
            if emotion_type not in emotion_counts:
                emotion_counts[emotion_type] = 0
            emotion_counts[emotion_type] += 1
        
        total_emotions = len(user_emotions)
        emotion_distribution = {
            emotion: (count / total_emotions) * 100 
            for emotion, count in emotion_counts.items()
        }
        
        # Calculate emotional journey (changes over time)
        sorted_emotions = sorted(user_emotions, key=lambda e: e.timestamp)
        emotion_journey = []
        for emotion in sorted_emotions:
            emotion_journey.append({
                'timestamp': emotion.timestamp.isoformat(),
                'emotion': emotion.emotion_type.value,
                'intensity': emotion.intensity
            })
        
        # Calculate emotional stability
        intensities = [e.intensity for e in user_emotions]
        emotional_stability = 1.0 - (statistics.stdev(intensities) if len(intensities) > 1 else 0)
        
        # Determine dominant emotion
        dominant_emotion = max(emotion_counts, key=emotion_counts.get) if emotion_counts else "neutral"
        
        # Generate insights
        insights = self._generate_personal_insights(
            dominant_emotion, 
            emotion_distribution, 
            emotional_stability,
            sorted_emotions
        )
        
        # Generate action items
        action_items = self._generate_personal_action_items(
            dominant_emotion,
            emotion_distribution,
            emotional_stability
        )
        
        return {
            'user_id': user_id,
            'session_id': session_id,
            'has_data': True,
            'emotion_summary': {
                'total_emotions_tracked': total_emotions,
                'dominant_emotion': dominant_emotion,
                'emotion_distribution': emotion_distribution,
                'emotional_stability': round(emotional_stability, 2),
                'average_intensity': round(statistics.mean(intensities), 2) if intensities else 0
            },
            'emotion_journey': emotion_journey,
            'insights': insights,
            'action_items': action_items,
            'generated_at': datetime.utcnow().isoformat()
        }
    
    def _generate_personal_insights(self, dominant_emotion: str, emotion_distribution: Dict, emotional_stability: float, emotions: List[EmotionData]) -> List[str]:
        """
        Generate personalized insights based on emotion analysis
        """
        insights = []
        
        # Insight based on dominant emotion
        if dominant_emotion == "happy":
            insights.append("You maintained a positive emotional state throughout most of the session, which likely contributed to a constructive atmosphere.")
        elif dominant_emotion == "neutral":
            insights.append("You maintained a balanced emotional state during the session, which may indicate focused attention or reserved engagement.")
        elif dominant_emotion == "stressed":
            insights.append("You experienced elevated stress levels during this session. Consider what specific topics or interactions triggered this response.")
        elif dominant_emotion == "sad":
            insights.append("You expressed sadness during parts of this session. Reflecting on the causes may help address underlying concerns.")
        elif dominant_emotion == "angry":
            insights.append("You experienced frustration or anger during this session. Consider what specific issues triggered these emotions and how they might be addressed constructively.")
        
        # Insight based on emotional stability
        if emotional_stability > 0.8:
            insights.append("Your emotions remained quite stable throughout the session, suggesting good emotional regulation.")
        elif emotional_stability < 0.5:
            insights.append("Your emotions fluctuated significantly during the session, which may indicate strong reactions to different discussion points.")
        
        # Insight based on emotion trends
        if len(emotions) >= 3:
            # Check if emotions improved over time
            first_third = emotions[:len(emotions)//3]
            last_third = emotions[-len(emotions)//3:]
            
            positive_emotions = ["happy", "excited"]
            negative_emotions = ["sad", "angry", "stressed"]
            
            first_negative_count = sum(1 for e in first_third if e.emotion_type.value in negative_emotions)
            last_negative_count = sum(1 for e in last_third if e.emotion_type.value in negative_emotions)
            
            if first_negative_count > last_negative_count:
                insights.append("Your emotional state appeared to improve as the session progressed, suggesting effective engagement or resolution of concerns.")
            elif first_negative_count < last_negative_count:
                insights.append("Your emotional state appeared to decline as the session progressed, which might indicate growing concerns or fatigue.")
        
        # Add insight about participation if we have enough data
        if len(emotions) > 5:
            insights.append("Your consistent emotional tracking suggests active engagement throughout the session.")
        elif len(emotions) < 3:
            insights.append("Limited emotional data was collected, which may indicate periods of disengagement or technical issues.")
        
        return insights
    
    def _generate_personal_action_items(self, dominant_emotion: str, emotion_distribution: Dict, emotional_stability: float) -> List[str]:
        """
        Generate personalized action items based on emotion analysis
        """
        action_items = []
        
        # Action items based on dominant emotion
        if dominant_emotion == "happy":
            action_items.append("Share what aspects of the session you found most positive to help maintain this environment in future meetings.")
        elif dominant_emotion == "neutral":
            action_items.append("Reflect on what would increase your engagement and enthusiasm in future sessions.")
        elif dominant_emotion == "stressed":
            action_items.append("Identify specific stressors from this session and develop strategies to manage them in future meetings.")
            action_items.append("Consider discussing workload or deadline concerns with your team lead if these were contributing factors.")
        elif dominant_emotion == "sad":
            action_items.append("Take time to process any disappointing news or outcomes from the session.")
            action_items.append("Consider speaking with a team lead or trusted colleague about any concerns.")
        elif dominant_emotion == "angry":
            action_items.append("Identify specific triggers for your frustration and consider constructive ways to address these issues.")
            action_items.append("Practice communication techniques that help express concerns without escalating tension.")
        
        # Action items based on emotional stability
        if emotional_stability < 0.5:
            action_items.append("Practice mindfulness techniques to help maintain emotional balance during challenging discussions.")
        
        # General action items
        action_items.append("Set a personal goal for how you want to feel and participate in the next session.")
        
        # Limit to 3 action items
        return action_items[:3]
