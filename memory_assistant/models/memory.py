"""
记忆数据模型
定义记忆系统的核心数据结构
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Any
import uuid


class MemoryType(Enum):
    """记忆类型"""
    CHAT = "chat"           # 兼容历史数据，新的长期记忆不再使用
    DOCUMENT = "document"   # 文档内容
    EVENT = "event"         # 事件记录
    FACT = "fact"           # 事实知识
    TASK = "task"           # 任务事项
    REMINDER = "reminder"   # 提醒事项


class MemoryState(Enum):
    """记忆状态"""
    NEW = "new"                     # 新建
    ACTIVE = "active"               # 活跃
    REINFORCED = "reinforced"       # 强化
    CORE = "core"                   # 核心记忆
    DECAYING = "decaying"           # 衰退中
    ARCHIVED = "archived"           # 已归档
    FORGOTTEN = "forgotten"         # 已遗忘


@dataclass
class MemoryEntry:
    """
    记忆条目 - 统一记忆数据结构
    """
    content: str
    user_id: str
    memory_type: MemoryType = MemoryType.FACT
    memory_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    scope: str = "user"
    session_id: Optional[str] = None
    turn_id: Optional[str] = None
    status: str = "active"

    # 时间属性
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)

    # 质量属性
    confidence: float = 0.5         # 可信度 (0-1)
    importance: float = 0.5         # 重要性 (0-1)
    weight: float = 0.5             # 当前权重 (0-1)
    access_count: int = 0           # 访问次数
    state: MemoryState = MemoryState.NEW

    # 关联属性
    tags: List[str] = field(default_factory=list)
    related_entities: List[str] = field(default_factory=list)
    source: str = "user"            # 来源

    # 向量表示 (用于语义检索)
    embedding: Optional[List[float]] = None

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'memory_id': self.memory_id,
            'user_id': self.user_id,
            'content': self.content,
            'memory_type': self.memory_type.value,
            'scope': self.scope,
            'session_id': self.session_id,
            'turn_id': self.turn_id,
            'status': self.status,
            'state': self.state.value,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'last_accessed': self.last_accessed.isoformat(),
            'confidence': self.confidence,
            'importance': self.importance,
            'weight': self.weight,
            'access_count': self.access_count,
            'tags': self.tags,
            'related_entities': self.related_entities,
            'source': self.source,
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemoryEntry':
        """从字典创建"""
        entry = cls(
            content=data['content'],
            user_id=data['user_id'],
            memory_type=MemoryType(data.get('memory_type', 'fact')),
            memory_id=data.get('memory_id', str(uuid.uuid4())),
            scope=data.get('scope', 'user'),
            session_id=data.get('session_id'),
            turn_id=data.get('turn_id'),
            status=data.get('status', 'active'),
        )
        entry.state = MemoryState(data.get('state', 'new'))
        entry.confidence = data.get('confidence', 0.5)
        entry.importance = data.get('importance', 0.5)
        entry.weight = data.get('weight', 0.5)
        entry.access_count = data.get('access_count', 0)
        entry.tags = data.get('tags', [])
        entry.related_entities = data.get('related_entities', [])
        entry.source = data.get('source', 'user')
        entry.metadata = data.get('metadata', {})

        # 解析时间
        for field_name in ['created_at', 'updated_at', 'last_accessed']:
            if field_name in data:
                try:
                    setattr(entry, field_name, datetime.fromisoformat(data[field_name]))
                except:
                    setattr(entry, field_name, datetime.now())

        return entry

    def touch(self):
        """更新访问时间和计数"""
        self.last_accessed = datetime.now()
        self.access_count += 1
        self.updated_at = datetime.now()

    def update_weight(self, new_weight: float):
        """更新权重"""
        self.weight = max(0.0, min(1.0, new_weight))
        self.updated_at = datetime.now()
