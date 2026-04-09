"""
记忆演化引擎
实现记忆的动态遗忘与强化
"""
import math
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from ..models.memory import MemoryEntry, MemoryState
from ..storage.metadata_store import SQLiteMetadataStore


@dataclass
class EvolutionResult:
    """演化结果"""
    memory_id: str
    old_weight: float
    new_weight: float
    old_state: MemoryState
    new_state: MemoryState
    factors: Dict[str, float]


class MemoryEvolutionEngine:
    """记忆演化引擎"""

    def __init__(self,
                 metadata_store: SQLiteMetadataStore,
                 decay_rate: float = 0.05,
                 reinforcement_rate: float = 0.1,
                 forget_threshold: float = 0.15,
                 archive_threshold: float = 0.3,
                 core_threshold: float = 0.8):
        self.metadata_store = metadata_store
        self.decay_rate = decay_rate
        self.reinforcement_rate = reinforcement_rate
        self.forget_threshold = forget_threshold
        self.archive_threshold = archive_threshold
        self.core_threshold = core_threshold

    async def evolve_single(self, memory: MemoryEntry) -> EvolutionResult:
        """
        单条记忆演化

        Args:
            memory: 记忆条目

        Returns:
            演化结果
        """
        old_weight = memory.weight
        old_state = memory.state

        # 计算时间衰减
        days_inactive = (datetime.now() - memory.last_accessed).days
        time_decay = math.exp(-self.decay_rate * days_inactive)

        # 计算访问强化
        access_boost = math.log1p(memory.access_count) * self.reinforcement_rate

        # 重要性基准
        base_importance = memory.importance

        # 可信度调整
        confidence_factor = 0.5 + memory.confidence / 2

        # 计算新权重
        new_weight = base_importance * time_decay * (1 + access_boost) * confidence_factor
        new_weight = max(0.0, min(1.0, new_weight))

        # 判定新状态
        new_state = self._determine_state(new_weight, memory)

        # 更新记忆
        memory.weight = new_weight
        memory.state = new_state
        memory.updated_at = datetime.now()

        # 保存更新
        await self.metadata_store.update_memory(memory)

        return EvolutionResult(
            memory_id=memory.memory_id,
            old_weight=old_weight,
            new_weight=new_weight,
            old_state=old_state,
            new_state=new_state,
            factors={
                'time_decay': time_decay,
                'access_boost': access_boost,
                'confidence_factor': confidence_factor,
                'base_importance': base_importance,
            }
        )

    def _determine_state(self, weight: float, memory: MemoryEntry) -> MemoryState:
        """判定记忆状态"""
        # 遗忘判断
        if weight < self.forget_threshold:
            return MemoryState.FORGOTTEN

        # 归档判断
        if weight < self.archive_threshold:
            return MemoryState.ARCHIVED

        # 核心记忆判断
        if weight > self.core_threshold and memory.access_count > 10:
            return MemoryState.CORE

        # 强化判断
        if memory.access_count >= 5 and weight > 0.6:
            return MemoryState.REINFORCED

        # 衰退判断
        if weight < memory.importance * 0.5:
            return MemoryState.DECAYING

        return MemoryState.ACTIVE

    async def batch_evolve(self, batch_size: int = 1000) -> List[EvolutionResult]:
        """
        批量演化处理

        Args:
            batch_size: 批处理大小

        Returns:
            演化结果列表
        """
        results = []
        offset = 0

        while True:
            # 获取待演化记忆
            memories = await self.metadata_store.get_memories_for_evolution(
                min_weight=0.0,
                max_weight=1.0,
                limit=batch_size
            )

            if not memories:
                break

            # 并行演化
            tasks = [self.evolve_single(m) for m in memories]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    print(f"Error evolving memory: {result}")
                else:
                    results.append(result)

            offset += batch_size

            if len(memories) < batch_size:
                break

        return results

    async def handle_state_transition(self, evolution: EvolutionResult):
        """处理状态变更"""
        if evolution.new_state == evolution.old_state:
            return

        memory_id = evolution.memory_id

        if evolution.new_state == MemoryState.FORGOTTEN:
            print(f"Memory {memory_id} forgotten (weight: {evolution.new_weight:.3f})")
            # 可以在这里执行物理删除或归档

        elif evolution.new_state == MemoryState.ARCHIVED:
            print(f"Memory {memory_id} archived (weight: {evolution.new_weight:.3f})")
            # 迁移到冷存储

        elif evolution.new_state == MemoryState.CORE:
            print(f"Memory {memory_id} promoted to core (weight: {evolution.new_weight:.3f})")
            # 提升存储优先级

    async def get_evolution_stats(self) -> Dict[str, Any]:
        """获取演化统计"""
        # 各状态的记忆数量
        state_counts = {}
        for state in MemoryState:
            # 这里应该查询数据库获取实际统计
            state_counts[state.value] = 0

        return {
            'state_distribution': state_counts,
            'decay_rate': self.decay_rate,
            'reinforcement_rate': self.reinforcement_rate,
            'forget_threshold': self.forget_threshold,
        }
