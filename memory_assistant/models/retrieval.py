"""
检索相关数据模型
"""
from dataclasses import dataclass
from typing import Dict, Any, Optional

from .memory import MemoryEntry


@dataclass
class SearchResult:
    """搜索结果"""
    memory_id: str
    score: float
    entry: Optional[MemoryEntry] = None
    metadata: Dict[str, Any] = None


@dataclass
class FusedResult:
    """RRF融合结果"""
    memory_id: str
    score: float
    dense_score: float = 0.0
    sparse_score: float = 0.0


@dataclass
class RetrievalResult:
    """检索结果"""
    memory: MemoryEntry
    final_score: float
    dense_score: float = 0.0
    sparse_score: float = 0.0
    temporal_score: float = 0.0
    personalized_score: float = 0.0
