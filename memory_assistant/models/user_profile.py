"""
用户画像数据模型
定义用户画像的核心数据结构
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import math

from ..utils.topic_utils import is_meaningful_topic, normalize_topic, sanitize_topic_preferences


@dataclass
class TopicPreference:
    """话题偏好"""
    topic: str
    weight: float = 0.5
    confidence: float = 0.3
    first_seen: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    trend: str = "stable"  # 'rising', 'stable', 'declining'
    interaction_count: int = 0

    def update_weight(self, interaction_signal: float, learning_rate: float = 0.1):
        """基于交互更新权重"""
        old_weight = self.weight
        self.weight = self.weight * (1 - learning_rate) + interaction_signal * learning_rate
        self.weight = max(0.0, min(1.0, self.weight))
        self.last_active = datetime.now()
        self.interaction_count += 1

        # 更新置信度
        self.confidence = min(1.0, self.confidence + 0.01)

        # 计算趋势
        if self.weight > old_weight * 1.1:
            self.trend = "rising"
        elif self.weight < old_weight * 0.9:
            self.trend = "declining"
        else:
            self.trend = "stable"


@dataclass
class InteractionStyle:
    """交互风格偏好"""
    preferred_response_length: str = "medium"  # short/medium/long
    preferred_detail_level: str = "balanced"   # concise/balanced/detailed
    preferred_formality: str = "neutral"       # casual/neutral/formal
    proactivity_level: str = "balanced"        # reactive/balanced/proactive
    expressiveness: str = "moderate"           # minimal/moderate/expressive


@dataclass
class TimeWindow:
    """时间窗口"""
    start_hour: int
    end_hour: int
    activity_level: float


@dataclass
class TemporalProfile:
    """时间特征画像"""
    hourly_activity_distribution: List[float] = field(default_factory=lambda: [0.0] * 24)
    weekday_pattern: Optional[Dict[str, Any]] = None
    weekend_pattern: Optional[Dict[str, Any]] = None
    avg_response_time: timedelta = field(default_factory=lambda: timedelta(seconds=30))
    response_time_variability: float = 0.0
    optimal_interaction_windows: List[TimeWindow] = field(default_factory=list)


@dataclass
class QueryPattern:
    """查询模式"""
    query_type: str
    frequency: int
    avg_length: int
    common_keywords: List[str]
    typical_time: Optional[int] = None  # 小时


@dataclass
class ExpertiseArea:
    """专业领域"""
    domain: str
    level: str = "beginner"  # beginner/intermediate/advanced/expert
    confirmed: bool = False
    evidence_count: int = 0


@dataclass
class BehaviorStatistics:
    """行为统计"""
    total_interactions: int = 0
    total_queries: int = 0
    total_memories_created: int = 0
    avg_session_duration: timedelta = field(default_factory=lambda: timedelta(minutes=10))
    last_interaction: Optional[datetime] = None
    daily_active_days: int = 0


@dataclass
class UserProfile:
    """用户画像主类"""
    user_id: str
    username: Optional[str] = None
    name: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # 偏好模型
    topic_preferences: List[TopicPreference] = field(default_factory=list)
    interaction_style: InteractionStyle = field(default_factory=InteractionStyle)
    temporal_profile: TemporalProfile = field(default_factory=TemporalProfile)

    # 行为模式
    query_patterns: List[QueryPattern] = field(default_factory=list)
    behavior_stats: BehaviorStatistics = field(default_factory=BehaviorStatistics)

    # 知识领域
    expertise_areas: List[ExpertiseArea] = field(default_factory=list)
    learning_topics: List[str] = field(default_factory=list)

    def get_topic_preference(self, topic: str) -> Optional[TopicPreference]:
        """获取话题偏好"""
        for pref in self.topic_preferences:
            if pref.topic == topic:
                return pref
        return None

    def add_or_update_topic(self, topic: str, interaction_signal: float = 0.5):
        """添加或更新话题偏好"""
        topic = normalize_topic(topic)
        if not is_meaningful_topic(topic):
            return

        pref = self.get_topic_preference(topic)
        if pref:
            pref.update_weight(interaction_signal)
        else:
            self.topic_preferences.append(TopicPreference(
                topic=topic,
                weight=interaction_signal,
                confidence=0.3,
                interaction_count=1
            ))
        self.topic_preferences = sanitize_topic_preferences(self.topic_preferences)
        self.updated_at = datetime.now()

    def update_behavior_stats(self, interaction_type: str = "query"):
        """更新行为统计"""
        self.behavior_stats.total_interactions += 1
        if interaction_type == "query":
            self.behavior_stats.total_queries += 1
        self.behavior_stats.last_interaction = datetime.now()
        self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'user_id': self.user_id,
            'username': self.username,
            'name': self.name,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'topic_preferences': [
                {
                    'topic': p.topic,
                    'weight': p.weight,
                    'confidence': p.confidence,
                    'trend': p.trend,
                    'interaction_count': p.interaction_count,
                }
                for p in self.topic_preferences
            ],
            'interaction_style': {
                'preferred_response_length': self.interaction_style.preferred_response_length,
                'preferred_detail_level': self.interaction_style.preferred_detail_level,
                'preferred_formality': self.interaction_style.preferred_formality,
                'proactivity_level': self.interaction_style.proactivity_level,
                'expressiveness': self.interaction_style.expressiveness,
            },
            'behavior_stats': {
                'total_interactions': self.behavior_stats.total_interactions,
                'total_queries': self.behavior_stats.total_queries,
                'total_memories_created': self.behavior_stats.total_memories_created,
                'last_interaction': self.behavior_stats.last_interaction.isoformat()
                if self.behavior_stats.last_interaction else None,
            },
            'expertise_areas': [
                {
                    'domain': e.domain,
                    'level': e.level,
                    'confirmed': e.confirmed,
                    'evidence_count': e.evidence_count,
                }
                for e in self.expertise_areas
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserProfile':
        """从字典创建"""
        profile = cls(
            user_id=data['user_id'],
            username=data.get('username'),
            name=data.get('name'),
        )

        # 解析话题偏好
        for tp_data in data.get('topic_preferences', []):
            profile.topic_preferences.append(TopicPreference(
                topic=tp_data['topic'],
                weight=tp_data.get('weight', 0.5),
                confidence=tp_data.get('confidence', 0.3),
                trend=tp_data.get('trend', 'stable'),
                interaction_count=tp_data.get('interaction_count', 0),
            ))

        # 解析交互风格
        style_data = data.get('interaction_style', {})
        profile.interaction_style = InteractionStyle(
            preferred_response_length=style_data.get('preferred_response_length', 'medium'),
            preferred_detail_level=style_data.get('preferred_detail_level', 'balanced'),
            preferred_formality=style_data.get('preferred_formality', 'neutral'),
            proactivity_level=style_data.get('proactivity_level', 'balanced'),
            expressiveness=style_data.get('expressiveness', 'moderate'),
        )

        # 解析行为统计
        stats_data = data.get('behavior_stats', {})
        profile.behavior_stats = BehaviorStatistics(
            total_interactions=stats_data.get('total_interactions', 0),
            total_queries=stats_data.get('total_queries', 0),
            total_memories_created=stats_data.get('total_memories_created', 0),
        )
        if stats_data.get('last_interaction'):
            try:
                profile.behavior_stats.last_interaction = datetime.fromisoformat(
                    stats_data['last_interaction']
                )
            except Exception:
                profile.behavior_stats.last_interaction = None

        # 解析专业领域
        for exp_data in data.get('expertise_areas', []):
            profile.expertise_areas.append(ExpertiseArea(
                domain=exp_data['domain'],
                level=exp_data.get('level', 'beginner'),
                confirmed=exp_data.get('confirmed', False),
                evidence_count=exp_data.get('evidence_count', 0),
            ))

        return profile
