"""
话题偏好清洗工具
"""
from __future__ import annotations

import re
from typing import Iterable, List

MIN_TOPIC_WEIGHT_FOR_DISPLAY = 0.6
MIN_TOPIC_INTERACTION_COUNT_FOR_DISPLAY = 2


GENERIC_TOPIC_STOPWORDS = {
    '提醒', '喝水', '分钟', '记住', '信息', '内容', '事情', '东西', '问题', '情况',
    '消息', '记录', '一下', '一个', '一些', '这个', '那个', '这里', '那里',
    '可以', '需要', '想要', '希望', '帮我', '帮忙', '告诉', '设置', '添加',
    '创建', '查看', '分析', '整理', '处理', '确认', '完成', '结果', '详情',
    '今天', '明天', '现在', '刚刚', '时候', '时间'
}

TIME_OR_MEASURE_PATTERN = re.compile(
    r'^(\d+|[一二三四五六七八九十两几半]+)(秒|分钟|小时|天|周|月|年|次|条|个)$'
)
PURE_NUMBER_PATTERN = re.compile(r'^[\d\W_]+$')
COMMON_SUFFIX_PATTERN = re.compile(r'.*(内容|信息|事情|东西|问题|情况|消息|结果|详情)$')


def normalize_topic(topic: str) -> str:
    if not topic:
        return ''
    topic = topic.strip()
    topic = re.sub(r'^[\s\W_]+|[\s\W_]+$', '', topic)
    topic = re.sub(r'\s+', ' ', topic)
    return topic


def is_meaningful_topic(topic: str) -> bool:
    topic = normalize_topic(topic)
    if not topic:
        return False

    if len(topic) < 2 or len(topic) > 16:
        return False

    lowered = topic.lower()
    if lowered in GENERIC_TOPIC_STOPWORDS:
        return False

    if PURE_NUMBER_PATTERN.fullmatch(topic):
        return False

    if TIME_OR_MEASURE_PATTERN.fullmatch(topic):
        return False

    if COMMON_SUFFIX_PATTERN.fullmatch(topic) and len(topic) <= 4:
        return False

    if topic.startswith(('帮我', '请帮', '给我', '让我')):
        return False

    return True


def sanitize_topic_preferences(topic_preferences: Iterable) -> List:
    deduped = {}
    for pref in topic_preferences:
        topic = normalize_topic(getattr(pref, 'topic', ''))
        if not is_meaningful_topic(topic):
            continue
        pref.topic = topic
        existing = deduped.get(topic)
        if existing is None or getattr(pref, 'weight', 0.0) > getattr(existing, 'weight', 0.0):
            deduped[topic] = pref

    return sorted(
        deduped.values(),
        key=lambda item: (getattr(item, 'weight', 0.0), getattr(item, 'interaction_count', 0)),
        reverse=True
    )


def filter_displayable_topic_preferences(
    topic_preferences: Iterable,
    min_weight: float = MIN_TOPIC_WEIGHT_FOR_DISPLAY,
    min_interaction_count: int = MIN_TOPIC_INTERACTION_COUNT_FOR_DISPLAY
) -> List:
    sanitized = sanitize_topic_preferences(topic_preferences)
    return [
        pref for pref in sanitized
        if getattr(pref, 'weight', 0.0) >= min_weight
        and getattr(pref, 'interaction_count', 0) >= min_interaction_count
    ]
