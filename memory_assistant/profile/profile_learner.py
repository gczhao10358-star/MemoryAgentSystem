"""
用户画像学习器
从用户交互中自动学习用户特征
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import Counter
import re

from ..models.user_profile import UserProfile, TopicPreference, ExpertiseArea
from ..utils.text_processor import text_processor


class ProfileLearner:
    """用户画像学习器"""

    def __init__(self, learning_rate: float = 0.1):
        self.learning_rate = learning_rate
        self.min_interactions_for_pattern = 3

    async def learn_from_interaction(self,
                                     profile: UserProfile,
                                     query: str,
                                     response: str,
                                     interaction_type: str = "query") -> UserProfile:
        """
        从单次交互中学习

        Args:
            profile: 用户画像
            query: 用户查询
            response: 系统回复
            interaction_type: 交互类型

        Returns:
            更新后的画像
        """
        # 1. 更新行为统计
        profile.update_behavior_stats(interaction_type)

        # 2. 提取话题并更新偏好
        await self._update_topic_preferences(profile, query, response)

        # 3. 学习时间模式
        self._update_temporal_pattern(profile)

        # 4. 推断专业知识
        await self._infer_expertise(profile, query)

        # 5. 分析交互风格
        await self._analyze_interaction_style(profile, query, response)

        return profile

    async def _update_topic_preferences(self,
                                       profile: UserProfile,
                                       query: str,
                                       response: str):
        """更新话题偏好"""
        # 提取查询中的关键词
        keywords = text_processor.extract_keywords(query, top_k=5)

        # 更新每个关键词的权重
        for keyword in keywords:
            # 计算交互信号（基于关键词在查询中的重要性）
            interaction_signal = 0.6  # 基础信号

            # 如果查询以关键词开头，增加权重
            if query.startswith(keyword):
                interaction_signal = 0.8

            profile.add_or_update_topic(keyword, interaction_signal)

    def _update_temporal_pattern(self, profile: UserProfile):
        """更新时间模式"""
        current_hour = datetime.now().hour

        # 更新小时活跃度分布
        total_interactions = profile.behavior_stats.total_interactions
        if total_interactions > 0:
            # 使用指数移动平均
            alpha = 0.1
            old_value = profile.temporal_profile.hourly_activity_distribution[current_hour]
            new_value = old_value * (1 - alpha) + alpha * 1.0
            profile.temporal_profile.hourly_activity_distribution[current_hour] = new_value

    async def _infer_expertise(self, profile: UserProfile, query: str):
        """推断用户专业知识"""
        # 提取查询中的专业术语
        # 这里使用简单的启发式方法，生产环境可以使用更复杂的模型

        # 检测专业词汇模式
        expertise_indicators = [
            r'如何优化|性能调优|架构设计|mysql|sql|数据库|查询|索引',  # 技术
            r'市场分析|ROI|用户增长',       # 商业
            r'深度学习|神经网络|模型训练',  # AI
            r'财务报表|资产负债表|现金流',  # 财务
        ]

        for indicator in expertise_indicators:
            if re.search(indicator, query):
                domain = self._get_domain_from_pattern(indicator)

                # 查找或创建专业知识领域
                existing = next((e for e in profile.expertise_areas
                                if e.domain == domain), None)

                if existing:
                    existing.evidence_count += 1
                    # 升级逻辑
                    if existing.evidence_count >= 50:
                        existing.level = "expert"
                    elif existing.evidence_count >= 20:
                        existing.level = "advanced"
                    elif existing.evidence_count >= 5:
                        existing.level = "intermediate"
                    # 否则保持 beginner
                else:
                    profile.expertise_areas.append(ExpertiseArea(
                        domain=domain,
                        level="beginner",
                        evidence_count=1
                    ))

    def _get_domain_from_pattern(self, pattern: str) -> str:
        """从模式获取领域名称"""
        if '优化' in pattern or '架构' in pattern:
            return "技术"
        elif '市场' in pattern or 'ROI' in pattern:
            return "商业"
        elif '深度学习' in pattern or '模型' in pattern:
            return "人工智能"
        elif '财务' in pattern or '资产' in pattern:
            return "财务"
        return "其他"

    async def _analyze_interaction_style(self,
                                        profile: UserProfile,
                                        query: str,
                                        response: str):
        """分析交互风格"""
        # 查询长度分析
        query_length = len(query)

        if query_length < 20:
            # 短查询，用户可能喜欢简洁回答
            profile.interaction_style.preferred_response_length = "short"
        elif query_length > 100:
            # 长查询，用户可能喜欢详细回答
            profile.interaction_style.preferred_response_length = "long"

        # 分析正式程度
        # 使用敬语/正式词汇的检测
        formal_indicators = ['请', '谢谢', '您好', '请问', '能否']
        casual_indicators = ['嗨', '嘿', '帮忙', '看一下']

        formal_count = sum(1 for w in formal_indicators if w in query)
        casual_count = sum(1 for w in casual_indicators if w in query)

        if formal_count > casual_count:
            profile.interaction_style.preferred_formality = "formal"
        elif casual_count > formal_count:
            profile.interaction_style.preferred_formality = "casual"

    async def batch_learn(self,
                         profile: UserProfile,
                         interactions: List[Dict[str, Any]]) -> UserProfile:
        """
        批量学习 - 深度分析历史交互

        Args:
            profile: 用户画像
            interactions: 历史交互列表

        Returns:
            更新后的画像
        """
        if len(interactions) < self.min_interactions_for_pattern:
            return profile

        # 1. 挖掘查询模式
        query_types = [i.get('type', 'query') for i in interactions]
        type_counter = Counter(query_types)

        # 2. 分析时间模式
        timestamps = [i.get('timestamp') for i in interactions if i.get('timestamp')]
        if timestamps:
            # 找出最活跃的时段
            hour_distribution = Counter([t.hour for t in timestamps])
            most_active_hours = [h for h, c in hour_distribution.most_common(3)]

            # 更新最优交互窗口
            profile.temporal_profile.optimal_interaction_windows = [
                {"hour": h, "activity": hour_distribution[h] / len(timestamps)}
                for h in most_active_hours
            ]

        # 3. 话题趋势分析
        topic_trends = {}
        for interaction in interactions:
            query = interaction.get('query', '')
            keywords = text_processor.extract_keywords(query, top_k=3)

            for kw in keywords:
                if kw not in topic_trends:
                    topic_trends[kw] = []
                topic_trends[kw].append(interaction.get('timestamp'))

        # 识别上升趋势的话题
        for topic, times in topic_trends.items():
            if len(times) >= 3:
                # 检查是否最近频繁出现
                recent_count = sum(1 for t in times
                                 if (datetime.now() - t).days <= 7)
                if recent_count >= 2:
                    pref = profile.get_topic_preference(topic)
                    if pref:
                        pref.trend = "rising"

        return profile

    def get_learning_summary(self, profile: UserProfile) -> Dict[str, Any]:
        """
        获取学习摘要

        Args:
            profile: 用户画像

        Returns:
            学习摘要
        """
        return {
            'user_id': profile.user_id,
            'learned_topics': len(profile.topic_preferences),
            'top_interests': [
                p.topic for p in sorted(profile.topic_preferences,
                                       key=lambda x: x.weight, reverse=True)[:5]
            ],
            'expertise_areas': [e.domain for e in profile.expertise_areas],
            'interaction_style': {
                'response_length': profile.interaction_style.preferred_response_length,
                'formality': profile.interaction_style.preferred_formality,
            },
            'active_hours': [
                i for i, v in enumerate(profile.temporal_profile.hourly_activity_distribution)
                if v > 0.3
            ],
        }
