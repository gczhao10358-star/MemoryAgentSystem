"""
记忆管理器
协调三级记忆系统的存取
"""
import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from collections import deque

from ..models.memory import MemoryEntry, MemoryType, MemoryState
from ..storage.memory_storage import MemoryStorage
from ..utils.embedding import EmbeddingModel
from ..utils.text_processor import text_processor
from ..utils.time_parser import time_parser


class WorkingMemory:
    """工作记忆 - 当前会话上下文"""

    def __init__(self, max_turns: int = 20):
        self.max_turns = max_turns
        self.conversation_history: deque = deque(maxlen=max_turns)
        self.current_context: Dict[str, Any] = {}

    def add_turn(self, role: str, content: str):
        """添加对话轮次"""
        self.conversation_history.append({
            'role': role,
            'content': content,
            'timestamp': datetime.now(),
        })

    def get_context(self, turns: int = None) -> List[Dict]:
        """获取对话上下文"""
        if turns is None:
            return list(self.conversation_history)
        return list(self.conversation_history)[-turns:]

    def clear(self):
        """清空工作记忆"""
        self.conversation_history.clear()
        self.current_context.clear()


class ShortTermMemory:
    """短期记忆 - 近期高频访问记忆"""

    def __init__(self, max_entries: int = 100, ttl_days: int = 7):
        self.max_entries = max_entries
        self.ttl = timedelta(days=ttl_days)
        self.cache: Dict[str, Dict] = {}

    async def store(self, entry: MemoryEntry):
        """存储到短期记忆"""
        self.cache[entry.memory_id] = {
            'entry': entry,
            'cached_at': datetime.now(),
            'access_count': 0,
        }

        # 清理过期或超量的条目
        await self._cleanup()

    async def get(self, memory_id: str) -> Optional[MemoryEntry]:
        """从短期记忆获取"""
        item = self.cache.get(memory_id)
        if item:
            # 检查TTL
            if datetime.now() - item['cached_at'] < self.ttl:
                item['access_count'] += 1
                return item['entry']
            else:
                del self.cache[memory_id]
        return None

    async def get_recent(self, limit: int = 20) -> List[MemoryEntry]:
        """获取最近的记忆"""
        # 按缓存时间排序
        sorted_items = sorted(
            self.cache.values(),
            key=lambda x: x['cached_at'],
            reverse=True
        )
        return [item['entry'] for item in sorted_items[:limit]]

    async def _cleanup(self):
        """清理过期和超量的条目"""
        now = datetime.now()

        # 移除过期条目
        expired = [
            mid for mid, item in self.cache.items()
            if now - item['cached_at'] > self.ttl
        ]
        for mid in expired:
            del self.cache[mid]

        # 如果仍超量，移除访问最少的
        if len(self.cache) > self.max_entries:
            sorted_items = sorted(
                self.cache.items(),
                key=lambda x: (x[1]['access_count'], x[1]['cached_at'])
            )
            to_remove = len(self.cache) - self.max_entries
            for mid, _ in sorted_items[:to_remove]:
                del self.cache[mid]


class LongTermMemory:
    """长期记忆 - 永久存储"""

    def __init__(self, storage: MemoryStorage):
        self.storage = storage
        self.pending_writes: List[MemoryEntry] = []
        self.batch_size = 10

    async def store(self, entry: MemoryEntry) -> bool:
        """存储到长期记忆"""
        # 立即写入
        success = await self.storage.store(entry)

        if not success:
            # 如果失败，加入待写入队列
            self.pending_writes.append(entry)

            # 如果队列满了，批量写入
            if len(self.pending_writes) >= self.batch_size:
                await self._flush_pending()

        return success

    async def retrieve(self, query_vector: List[float],
                      user_id: str, top_k: int = 10) -> List[Dict]:
        """向量检索"""
        return await self.storage.retrieve_by_vector(
            query_vector, user_id, top_k
        )

    async def search_by_content(self, user_id: str,
                                keyword: str, limit: int = 20) -> List[MemoryEntry]:
        """内容搜索"""
        return await self.storage.retrieve_by_content(
            user_id, keyword, limit
        )

    async def _flush_pending(self):
        """刷新待写入队列"""
        for entry in self.pending_writes:
            await self.storage.store(entry)
        self.pending_writes.clear()

    async def get_memory(self, memory_id: str) -> Optional[MemoryEntry]:
        """获取单个记忆"""
        return await self.storage.get_memory(memory_id)


class MemoryManager:
    """
    记忆管理器 - 协调三级记忆系统
    """

    def __init__(self,
                 storage: MemoryStorage,
                 embedding_model: EmbeddingModel,
                 working_memory_max_turns: int = 20,
                 short_term_max_entries: int = 100):
        self.working_memory = WorkingMemory(working_memory_max_turns)
        self.short_term_memory = ShortTermMemory(short_term_max_entries)
        self.long_term_memory = LongTermMemory(storage)
        self.embedding_model = embedding_model

    async def memorize(self, content: str,
                      user_id: str,
                      memory_type: MemoryType = MemoryType.CHAT,
                      metadata: Dict = None,
                      source: str = "user") -> MemoryEntry:
        """
        记忆存储主流程

        Args:
            content: 记忆内容
            user_id: 用户ID
            memory_type: 记忆类型
            metadata: 元数据
            source: 来源

        Returns:
            记忆条目
        """
        # 1. 解析时间信息
        clean_content, event_time = time_parser.extract_time_info(content)

        # 2. 生成向量嵌入（使用清洗后的内容）
        embedding = await self.embedding_model.encode(clean_content)

        # 3. 提取关键词和实体
        keywords = text_processor.extract_keywords(clean_content, top_k=10)
        entities = text_processor.extract_entities(clean_content)

        # 4. 准备元数据
        meta = metadata or {}
        if event_time:
            meta['event_time'] = event_time.isoformat()
            meta['event_time_formatted'] = time_parser.format_time(event_time, 'human')
        meta['original_content'] = content

        # 5. 创建记忆条目
        entry = MemoryEntry(
            content=clean_content,
            user_id=user_id,
            memory_type=memory_type,
            embedding=embedding,
            tags=keywords,
            related_entities=entities,
            source=source,
            metadata=meta,
        )

        # 6. 评估可信度
        entry.confidence = self._assess_confidence(content, source)

        # 7. 评估重要性
        entry.importance = self._assess_importance(content, keywords, entities)

        # 8. 三级存储
        # L1: 工作记忆 (同步)
        self.working_memory.add_turn("user" if source == "user" else "system", content)

        # L2: 短期记忆 (异步)
        asyncio.create_task(self.short_term_memory.store(entry))

        # L3: 长期记忆 (异步)
        asyncio.create_task(self.long_term_memory.store(entry))

        return entry

    async def recall(self, query: str,
                    user_id: str,
                    top_k: int = 10,
                    use_vector: bool = True) -> List[Dict]:
        """
        记忆检索主流程

        Args:
            query: 查询文本
            user_id: 用户ID
            top_k: 返回数量
            use_vector: 是否使用向量检索

        Returns:
            检索结果
        """
        results = []

        # 1. 先从短期记忆检索
        short_term_results = await self.short_term_memory.get_recent(limit=top_k)
        results.extend([{'entry': e, 'source': 'short_term'} for e in short_term_results])

        # 2. 从长期记忆检索
        if use_vector:
            query_vector = await self.embedding_model.encode(query)
            long_term_results = await self.long_term_memory.retrieve(
                query_vector, user_id, top_k
            )
            results.extend(long_term_results)
        else:
            long_term_results = await self.long_term_memory.search_by_content(
                user_id, query, top_k
            )
            results.extend([{'entry': e, 'source': 'long_term'} for e in long_term_results])

        # 3. 去重并排序
        seen_ids = set()
        unique_results = []
        for r in results:
            entry = r.get('entry')
            if entry and entry.memory_id not in seen_ids:
                seen_ids.add(entry.memory_id)
                unique_results.append(r)

        return unique_results[:top_k]

    async def update_memory(self, memory_id: str,
                           updates: Dict[str, Any]) -> bool:
        """更新记忆"""
        entry = await self.long_term_memory.get_memory(memory_id)
        if not entry:
            return False

        # 应用更新
        if 'weight' in updates:
            entry.update_weight(updates['weight'])
        if 'tags' in updates:
            entry.tags = updates['tags']
        if 'metadata' in updates:
            entry.metadata.update(updates['metadata'])

        entry.touch()

        return await self.long_term_memory.storage.update_memory(entry)

    def _assess_confidence(self, content: str, source: str) -> float:
        """评估记忆可信度"""
        base_confidence = 0.5

        # 来源权重
        source_weights = {
            'user': 0.9,
            'system': 0.8,
            'inferred': 0.5,
            'imported': 0.7,
        }
        base_confidence *= source_weights.get(source, 0.5)

        # 内容长度加权
        if len(content) > 50:
            base_confidence += 0.1

        return min(base_confidence, 1.0)

    def _assess_importance(self, content: str,
                          keywords: List[str],
                          entities: List[str]) -> float:
        """评估记忆重要性"""
        importance = 0.5

        # 关键词数量加权
        importance += min(len(keywords) * 0.02, 0.1)

        # 实体数量加权
        importance += min(len(entities) * 0.05, 0.15)

        # 内容长度加权（适中长度更重要）
        length = len(content)
        if 50 <= length <= 500:
            importance += 0.1

        return min(importance, 1.0)

    async def get_stats(self, user_id: str) -> Dict[str, Any]:
        """获取记忆统计"""
        memories = await self.long_term_memory.storage.get_user_memories(user_id)

        return {
            'total_memories': len(memories),
            'working_memory_turns': len(self.working_memory.conversation_history),
            'short_term_entries': len(self.short_term_memory.cache),
            'memory_types': {
                mtype.value: sum(1 for m in memories if m.memory_type == mtype)
                for mtype in MemoryType
            },
            'avg_confidence': sum(m.confidence for m in memories) / len(memories) if memories else 0,
            'avg_importance': sum(m.importance for m in memories) / len(memories) if memories else 0,
        }
