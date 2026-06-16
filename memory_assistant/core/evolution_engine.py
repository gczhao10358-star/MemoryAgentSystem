"""
记忆演化引擎 v2.1
- 类别感知的差异化时间衰减（借鉴 OpenClaw 的半衰期模型）
- 常青记忆豁免（借鉴 OpenClaw Evergreen Memory）
- LLM 驱动的记忆演化决策（借鉴 Mem0 的 ADD/UPDATE/DELETE/NONE）
"""
import math
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

from ..models.memory import (
    MemoryEntry, MemoryState, MemoryCategory,
    CATEGORY_HALF_LIFE, EVERGREEN_CATEGORIES,
)
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


@dataclass
class MemoryOperation:
    """LLM 记忆操作决策结果"""
    memory_id: str       # 现有记忆 ID（UPDATE/DELETE/NONE 时）或 新 ID（ADD 时）
    text: str            # 记忆内容
    event: str           # ADD | UPDATE | DELETE | NONE
    old_memory: Optional[str] = None  # 旧内容（仅 UPDATE 时）


class MemoryEvolutionEngine:
    """记忆演化引擎 v2.1"""

    def __init__(self,
                 metadata_store: SQLiteMetadataStore,
                 decay_rate: float = 0.05,
                 reinforcement_rate: float = 0.1,
                 forget_threshold: float = 0.15,
                 archive_threshold: float = 0.3,
                 core_threshold: float = 0.8,
                 llm_client: Optional[Any] = None,
                 embedding_model: Optional[Any] = None):
        self.metadata_store = metadata_store
        self.decay_rate = decay_rate          # 基础衰减率（会被类别覆盖）
        self.reinforcement_rate = reinforcement_rate
        self.forget_threshold = forget_threshold
        self.archive_threshold = archive_threshold
        self.core_threshold = core_threshold
        self.llm_client = llm_client
        self.embedding_model = embedding_model

    # —————— 类别感知衰减 ——————

    def _get_category_half_life(self, memory: MemoryEntry) -> float:
        """获取该记忆类别对应的半衰期（天），常青类别返回无限大。"""
        if memory.category in EVERGREEN_CATEGORIES:
            return float('inf')  # 常青记忆不衰减
        return CATEGORY_HALF_LIFE.get(memory.category, 30)

    def _compute_decay_factor(self, memory: MemoryEntry) -> float:
        """
        计算基于类别半衰期的时间衰减因子。
        公式: decay = 0.5^(days_inactive / half_life)
        常青记忆: decay = 1.0（不衰减）
        """
        half_life = self._get_category_half_life(memory)
        if half_life == float('inf'):
            return 1.0  # 常青记忆不衰减

        days_inactive = (datetime.now() - memory.last_accessed).days
        if days_inactive <= 0:
            return 1.0

        decay = math.pow(0.5, days_inactive / half_life)
        # 保底：即使非常久远，也保留最低权重
        return max(decay, 0.05)

    async def evolve_single(self, memory: MemoryEntry) -> EvolutionResult:
        """
        单条记忆演化 — 类别感知版

        Args:
            memory: 记忆条目

        Returns:
            演化结果
        """
        old_weight = memory.weight
        old_state = memory.state

        # 1. 计算类别感知的时间衰减
        time_decay = self._compute_decay_factor(memory)

        # 2. 计算访问强化
        # 使用 log1p 平滑增长，避免被刷访问量刷爆
        access_boost = math.log1p(memory.access_count) * self.reinforcement_rate

        # 3. 重要性基准
        base_importance = memory.importance

        # 4. 可信度调整
        confidence_factor = 0.5 + memory.confidence / 2

        # 5. 类别加权（常青类别有天然加成）
        category_bonus = 0.15 if memory.category in EVERGREEN_CATEGORIES else 0.0

        # 6. 计算新权重
        new_weight = (base_importance + category_bonus) * time_decay * (1 + access_boost) * confidence_factor
        new_weight = max(0.0, min(1.0, new_weight))

        # 7. 判定新状态
        new_state = self._determine_state(new_weight, memory)

        # 8. 更新记忆
        memory.weight = new_weight
        memory.state = new_state
        memory.updated_at = datetime.now()

        # 9. 保存更新
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
                'category_bonus': category_bonus,
                'category': memory.category.value,
                'half_life_days': self._get_category_half_life(memory),
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

    # —————— 批量演化 ——————

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
            memories = await self.metadata_store.get_memories_for_evolution(
                min_weight=0.0,
                max_weight=1.0,
                limit=batch_size
            )

            if not memories:
                break

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

    # —————— 状态转换处理 ——————

    async def handle_state_transition(self, evolution: EvolutionResult):
        """处理状态变更"""
        if evolution.new_state == evolution.old_state:
            return

        memory_id = evolution.memory_id

        if evolution.new_state == MemoryState.FORGOTTEN:
            print(f"[Evolution] Memory {memory_id} FORGOTTEN (weight: {evolution.new_weight:.3f})")

        elif evolution.new_state == MemoryState.ARCHIVED:
            print(f"[Evolution] Memory {memory_id} ARCHIVED (weight: {evolution.new_weight:.3f})")

        elif evolution.new_state == MemoryState.CORE:
            print(f"[Evolution] Memory {memory_id} promoted to CORE (weight: {evolution.new_weight:.3f})")

    # —————— LLM 驱动的记忆演化决策（Mem0 核心思想）——————

    async def decide_evolution_operation(
        self,
        new_fact: str,
        existing_memories: List[MemoryEntry],
    ) -> List[MemoryOperation]:
        """
        利用 LLM 对比新事实与现有记忆，决定 ADD / UPDATE / DELETE / NONE。
        这是 Mem0 架构的精髓：让 LLM 自己判断记忆应该如何演化。

        Args:
            new_fact: 新提取的事实
            existing_memories: 向量检索到的 top-N 相关旧记忆

        Returns:
            操作决策列表
        """
        if not self.llm_client:
            # 无 LLM 时降级：新事实直接 ADD
            if new_fact.strip():
                return [MemoryOperation(
                    memory_id="new",
                    text=new_fact,
                    event="ADD",
                )]
            return []

        if not existing_memories:
            return [MemoryOperation(
                memory_id="new",
                text=new_fact,
                event="ADD",
            )]

        # 构建旧记忆上下文
        old_memories_text = ""
        for i, mem in enumerate(existing_memories[:5]):
            old_memories_text += (
                f"[{i}] ID: {mem.memory_id}\n"
                f"    内容: {mem.content}\n"
                f"    类型: {mem.memory_type.value}\n"
                f"    重要性: {mem.importance}\n\n"
            )

        prompt = f"""你是记忆演化决策专家。请对比"新事实"和"现有记忆"，决定应该执行什么操作。

## 现有记忆：
{old_memories_text}

## 新事实：
{new_fact}

## 决策规则：
- **ADD**: 新事实是完全新的信息，和现有记忆无关。
- **UPDATE**: 新事实是对某条现有记忆的更新/修正（如：地址变了、职位变了、计划日期变了）。
  使用该记忆的 ID，保留同一 ID。
- **DELETE**: 新事实和某条现有记忆冲突，旧记忆已失效（如：用户说"我不再喜欢咖啡了"）。
- **NONE**: 新事实和某条现有记忆几乎完全一致，无需操作。

## 输出格式（必须是 JSON 数组）：
[
  {{
    "id": "记忆ID 或 'new'（ADD时）",
    "text": "处理后的记忆内容",
    "event": "ADD|UPDATE|DELETE|NONE",
    "old_memory": "旧内容（仅 UPDATE 时需要，用于记录变更历史）"
  }}
]

只返回 JSON，不要其他文字。"""

        try:
            response = await self.llm_client.chat([
                {"role": "system", "content": "你是一个记忆演化决策专家。"},
                {"role": "user", "content": prompt}
            ])

            # 提取 JSON
            import re
            import json
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                ops = json.loads(json_match.group())
                return [MemoryOperation(
                    memory_id=op.get("id", "new"),
                    text=op.get("text", new_fact),
                    event=op.get("event", "ADD"),
                    old_memory=op.get("old_memory"),
                ) for op in ops]

        except Exception as e:
            print(f"[Evolution] LLM 决策失败: {e}，降级为 ADD")

        # 降级：直接 ADD
        return [MemoryOperation(
            memory_id="new",
            text=new_fact,
            event="ADD",
        )]

    async def apply_evolution_operations(
        self,
        operations: List[MemoryOperation],
        user_id: str,
        new_fact: str,
        embedding: Optional[List[float]] = None,
        category: MemoryCategory = MemoryCategory.EVENT,
        importance: float = 0.5,
    ) -> Dict[str, Any]:
        """
        执行 LLM 决策的演化操作。

        Returns:
            操作结果摘要
        """
        results = {"added": 0, "updated": 0, "deleted": 0, "none": 0}

        for op in operations:
            if op.event == "ADD":
                # 创建新记忆
                    entry = MemoryEntry(
                        content=op.text,
                        user_id=user_id,
                        memory_type=self._infer_memory_type_from_text(op.text),
                        importance=importance,
                        category=category,
                        embedding=embedding,
                        state=MemoryState.NEW,
                    )
                    await self.metadata_store.save_memory(entry)
                    results["added"] += 1

            elif op.event == "UPDATE":
                try:
                    existing = await self.metadata_store.get_memory(op.memory_id)
                    if existing:
                        # 记录变更历史
                        metadata = existing.metadata or {}
                        history = metadata.get("update_history", [])
                        history.append({
                            "old_content": existing.content,
                            "new_content": op.text,
                            "updated_at": datetime.now().isoformat(),
                        })
                        metadata["update_history"] = history[-10:]  # 最多保留 10 条变更记录

                        existing.content = op.text
                        existing.metadata = metadata
                        existing.importance = max(existing.importance, importance)
                        existing.updated_at = datetime.now()
                        if embedding:
                            existing.embedding = embedding
                        await self.metadata_store.update_memory(existing)
                        results["updated"] += 1
                except Exception as e:
                    print(f"[Evolution] UPDATE 失败 {op.memory_id}: {e}")

            elif op.event == "DELETE":
                try:
                    await self.metadata_store.delete_memory(op.memory_id)
                    results["deleted"] += 1
                except Exception as e:
                    print(f"[Evolution] DELETE 失败 {op.memory_id}: {e}")

            elif op.event == "NONE":
                results["none"] += 1

        return results

    def _infer_memory_type_from_text(self, text: str):
        """从文本推断 MemoryType"""
        from ..models.memory import MemoryType
        from .content_filter import ContentFilter
        inferred = ContentFilter.classify_memory_type(text)
        type_map = {
            'fact': MemoryType.FACT,
            'event': MemoryType.EVENT,
            'task': MemoryType.TASK,
            'reminder': MemoryType.REMINDER,
        }
        return type_map.get(inferred, MemoryType.FACT)

    # —————— 统计 ——————

    async def get_evolution_stats(self) -> Dict[str, Any]:
        """获取演化统计（含类别分布）"""
        state_counts = {}
        category_counts = {}

        for state in MemoryState:
            state_counts[state.value] = 0
        for cat in MemoryCategory:
            category_counts[cat.value] = 0

        return {
            'state_distribution': state_counts,
            'category_distribution': category_counts,
            'decay_rate': self.decay_rate,
            'reinforcement_rate': self.reinforcement_rate,
            'forget_threshold': self.forget_threshold,
            'category_half_lives': {
                cat.value: days
                for cat, days in CATEGORY_HALF_LIFE.items()
            },
            'evergreen_categories': [cat.value for cat in EVERGREEN_CATEGORIES],
        }
