"""
记忆管理器
负责用户级会话记忆、近期缓存和持久记忆访问。
"""
import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Deque, Dict, List, Optional

from ..models.memory import MemoryEntry, MemoryType
from ..storage.memory_storage import MemoryStorage
from ..utils.embedding import EmbeddingModel
from ..utils.text_processor import text_processor
from ..utils.time_parser import time_parser


DEFAULT_SESSION_KEY = "default"


@dataclass
class SessionMemory:
    """单用户会话记忆。"""
    user_id: str
    session_id: str
    max_turns: int
    conversation_history: Deque[Dict[str, Any]] = field(init=False)
    current_context: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.conversation_history = deque(maxlen=self.max_turns)

    def add_turn(self, role: str, content: str, turn_id: Optional[str] = None):
        self.conversation_history.append({
            "role": role,
            "content": content,
            "turn_id": turn_id,
            "timestamp": datetime.now(),
        })

    def get_context(self, turns: Optional[int] = None) -> List[Dict[str, Any]]:
        history = list(self.conversation_history)
        if turns is None:
            return history
        return history[-turns:]

    def clear(self):
        self.conversation_history.clear()
        self.current_context.clear()


class WorkingMemory:
    """按用户隔离的会话记忆存储。"""

    def __init__(self, max_turns: int = 20):
        self.max_turns = max_turns
        self._sessions: Dict[str, SessionMemory] = {}

    def _normalize_user_id(self, user_id: Optional[str]) -> str:
        return user_id or DEFAULT_SESSION_KEY

    def _normalize_session_id(self, session_id: Optional[str]) -> str:
        return session_id or DEFAULT_SESSION_KEY

    def _build_session_key(self, user_id: Optional[str], session_id: Optional[str]) -> str:
        return f"{self._normalize_user_id(user_id)}:{self._normalize_session_id(session_id)}"

    def _get_session(self, user_id: Optional[str] = None, session_id: Optional[str] = None) -> SessionMemory:
        normalized_user_id = self._normalize_user_id(user_id)
        normalized_session_id = self._normalize_session_id(session_id)
        session_key = self._build_session_key(normalized_user_id, normalized_session_id)
        if session_key not in self._sessions:
            self._sessions[session_key] = SessionMemory(
                user_id=normalized_user_id,
                session_id=normalized_session_id,
                max_turns=self.max_turns,
            )
        return self._sessions[session_key]

    def add_turn(self, *args):
        """兼容 add_turn(role, content) / add_turn(user_id, role, content) / add_turn(user_id, session_id, role, content, turn_id)。"""
        if len(args) == 5:
            user_id, session_id, role, content, turn_id = args
        elif len(args) == 4:
            user_id, session_id, role, content = args
            turn_id = None
        elif len(args) == 3:
            user_id, role, content = args
            session_id = None
            turn_id = None
        elif len(args) == 2:
            user_id = None
            session_id = None
            role, content = args
            turn_id = None
        else:
            raise TypeError("add_turn expects (role, content), (user_id, role, content), or (user_id, session_id, role, content[, turn_id])")

        self._get_session(user_id, session_id).add_turn(role, content, turn_id=turn_id)

    def get_context(self,
                    turns: Optional[int] = None,
                    user_id: Optional[str] = None,
                    session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._get_session(user_id, session_id).get_context(turns)

    def set_context_value(self, user_id: str, session_id: str, key: str, value: Any):
        self._get_session(user_id, session_id).current_context[key] = value

    def get_context_value(self, user_id: str, session_id: str, key: str, default: Any = None) -> Any:
        return self._get_session(user_id, session_id).current_context.get(key, default)

    def clear(self, user_id: Optional[str] = None, session_id: Optional[str] = None):
        if user_id is None and session_id is None:
            self._sessions.clear()
            return
        if user_id is not None and session_id is None:
            user_prefix = f"{self._normalize_user_id(user_id)}:"
            keys_to_delete = [key for key in self._sessions if key.startswith(user_prefix)]
            for key in keys_to_delete:
                del self._sessions[key]
            return
        self._sessions.pop(self._build_session_key(user_id, session_id), None)

    def turn_count(self, user_id: str, session_id: Optional[str] = None) -> int:
        if session_id is None:
            user_prefix = f"{self._normalize_user_id(user_id)}:"
            return sum(
                len(session.conversation_history)
                for key, session in self._sessions.items()
                if key.startswith(user_prefix)
            )
        session = self._sessions.get(self._build_session_key(user_id, session_id))
        return len(session.conversation_history) if session else 0


class MemoryCache:
    """用户级近期记忆缓存，用于性能优化而非业务真相源。"""

    def __init__(self, max_entries: int = 100, ttl_days: int = 7):
        self.max_entries = max_entries
        self.ttl = timedelta(days=ttl_days)
        self._cache_by_user: Dict[str, Dict[str, Dict[str, Any]]] = {}

    @property
    def cache(self) -> Dict[str, Dict[str, Any]]:
        merged: Dict[str, Dict[str, Any]] = {}
        for user_cache in self._cache_by_user.values():
            merged.update(user_cache)
        return merged

    def _get_user_cache(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        if user_id not in self._cache_by_user:
            self._cache_by_user[user_id] = {}
        return self._cache_by_user[user_id]

    def _purge_expired(self, user_id: Optional[str] = None):
        now = datetime.now()
        caches = []
        if user_id is None:
            caches = list(self._cache_by_user.values())
        else:
            caches = [self._cache_by_user.get(user_id, {})]

        for user_cache in caches:
            expired_ids = [
                memory_id for memory_id, item in user_cache.items()
                if now - item["cached_at"] >= self.ttl
            ]
            for memory_id in expired_ids:
                del user_cache[memory_id]

    async def store(self, entry: MemoryEntry):
        user_cache = self._get_user_cache(entry.user_id)
        user_cache[entry.memory_id] = {
            "entry": entry,
            "cached_at": datetime.now(),
            "access_count": 0,
        }
        await self._cleanup(entry.user_id)

    async def get(self, memory_id: str, user_id: Optional[str] = None) -> Optional[MemoryEntry]:
        search_spaces = []
        if user_id is not None:
            search_spaces.append(self._get_user_cache(user_id))
        else:
            search_spaces.extend(self._cache_by_user.values())

        for user_cache in search_spaces:
            item = user_cache.get(memory_id)
            if not item:
                continue
            if datetime.now() - item["cached_at"] >= self.ttl:
                del user_cache[memory_id]
                continue
            item["access_count"] += 1
            return item["entry"]
        return None

    async def get_recent(self, limit: int = 20, user_id: Optional[str] = None) -> List[MemoryEntry]:
        caches = []
        if user_id is not None:
            caches.append(self._get_user_cache(user_id))
        else:
            caches.extend(self._cache_by_user.values())

        items: List[Dict[str, Any]] = []
        for user_cache in caches:
            for memory_id, item in list(user_cache.items()):
                if datetime.now() - item["cached_at"] >= self.ttl:
                    del user_cache[memory_id]
                    continue
                items.append(item)

        items.sort(key=lambda item: item["cached_at"], reverse=True)
        return [item["entry"] for item in items[:limit]]

    async def _cleanup(self, user_id: str):
        user_cache = self._get_user_cache(user_id)
        now = datetime.now()

        expired_ids = [
            memory_id for memory_id, item in user_cache.items()
            if now - item["cached_at"] > self.ttl
        ]
        for memory_id in expired_ids:
            del user_cache[memory_id]

        if len(user_cache) <= self.max_entries:
            return

        sorted_items = sorted(
            user_cache.items(),
            key=lambda item: (item[1]["access_count"], item[1]["cached_at"]),
        )
        overflow_count = len(user_cache) - self.max_entries
        for memory_id, _ in sorted_items[:overflow_count]:
            del user_cache[memory_id]

    def clear(self, user_id: Optional[str] = None):
        if user_id is None:
            self._cache_by_user.clear()
            return
        self._cache_by_user.pop(user_id, None)

    def remove(self, memory_id: str, user_id: Optional[str] = None):
        if user_id is not None:
            user_cache = self._cache_by_user.get(user_id)
            if user_cache and memory_id in user_cache:
                del user_cache[memory_id]
            return

        for user_cache in self._cache_by_user.values():
            if memory_id in user_cache:
                del user_cache[memory_id]
                return

    def count(self, user_id: Optional[str] = None, include_chat: bool = False) -> int:
        self._purge_expired(user_id)
        if user_id is None:
            if include_chat:
                return sum(len(cache) for cache in self._cache_by_user.values())
            return sum(
                sum(1 for item in cache.values() if item["entry"].memory_type != MemoryType.CHAT)
                for cache in self._cache_by_user.values()
            )

        user_cache = self._cache_by_user.get(user_id, {})
        if include_chat:
            return len(user_cache)
        return sum(1 for item in user_cache.values() if item["entry"].memory_type != MemoryType.CHAT)


class ShortTermMemory(MemoryCache):
    """兼容旧命名，实际为缓存层。"""


class LongTermMemory:
    """兼容旧命名，实际为持久记忆存储层。"""

    def __init__(self, storage: MemoryStorage):
        self.storage = storage
        self.pending_writes: List[MemoryEntry] = []
        self.batch_size = 10

    async def store(self, entry: MemoryEntry) -> bool:
        success = await self.storage.store(entry)
        if not success:
            self.pending_writes.append(entry)
            if len(self.pending_writes) >= self.batch_size:
                await self._flush_pending()
        return success

    async def retrieve(self, query_vector: List[float], user_id: str, top_k: int = 10) -> List[Dict[str, Any]]:
        return await self.storage.retrieve_by_vector(query_vector, user_id, top_k)

    async def search_by_content(self, user_id: str, keyword: str, limit: int = 20) -> List[MemoryEntry]:
        return await self.storage.retrieve_by_content(user_id, keyword, limit)

    async def _flush_pending(self):
        for entry in self.pending_writes:
            await self.storage.store(entry)
        self.pending_writes.clear()

    async def get_memory(self, memory_id: str) -> Optional[MemoryEntry]:
        return await self.storage.get_memory(memory_id)


class MemoryManager:
    """协调会话记忆、近期缓存和持久记忆。"""

    def __init__(self,
                 storage: MemoryStorage,
                 embedding_model: EmbeddingModel,
                 metadata_store: Optional[Any] = None,
                 working_memory_max_turns: int = 20,
                 short_term_max_entries: int = 100,
                 short_term_ttl_days: int = 7,
                 session_memory_max_turns: Optional[int] = None,
                 cache_max_entries: Optional[int] = None,
                 cache_ttl_days: Optional[int] = None):
        session_turns = session_memory_max_turns or working_memory_max_turns
        cache_entries = cache_max_entries or short_term_max_entries
        cache_ttl = cache_ttl_days or short_term_ttl_days

        self.session_memory = WorkingMemory(session_turns)
        self.memory_cache = ShortTermMemory(cache_entries, cache_ttl)
        self.durable_memory = LongTermMemory(storage)
        storage.set_memory_cache(self.memory_cache)

        # 兼容旧命名，逐步迁移到 session_memory / memory_cache / durable_memory。
        self.working_memory = self.session_memory
        self.short_term_memory = self.memory_cache
        self.long_term_memory = self.durable_memory
        self.embedding_model = embedding_model
        self.metadata_store = metadata_store

    async def memorize(self,
                       content: str,
                       user_id: str,
                       memory_type: MemoryType = MemoryType.FACT,
                       metadata: Optional[Dict[str, Any]] = None,
                       source: str = "user") -> MemoryEntry:
        clean_content, event_time = time_parser.extract_time_info(content)
        embedding = await self.embedding_model.encode(clean_content)
        keywords = text_processor.extract_keywords(clean_content, top_k=10)
        entities = text_processor.extract_entities(clean_content)

        meta = metadata or {}
        if event_time:
            meta["event_time"] = event_time.isoformat()
            meta["event_time_formatted"] = time_parser.format_time(event_time, "human")
        meta["original_content"] = content

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
        entry.confidence = self._assess_confidence(content, source)
        entry.importance = self._assess_importance(content, keywords, entities)

        self.session_memory.add_turn(user_id, "user" if source == "user" else "system", content)
        asyncio.create_task(self.memory_cache.store(entry))
        asyncio.create_task(self.durable_memory.store(entry))
        return entry

    async def recall(self,
                     query: str,
                     user_id: str,
                     top_k: int = 10,
                     use_vector: bool = True) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        if use_vector:
            query_vector = await self.embedding_model.encode(query)
            durable_results = await self.durable_memory.retrieve(query_vector, user_id, top_k)
            results.extend(durable_results)
        else:
            durable_results = await self.durable_memory.search_by_content(user_id, query, top_k)
            results.extend([{"entry": entry, "source": "durable"} for entry in durable_results])

        seen_ids = set()
        unique_results = []
        for result in results:
            entry = result.get("entry")
            if not entry or entry.memory_id in seen_ids:
                continue
            seen_ids.add(entry.memory_id)
            unique_results.append(result)

        return unique_results[:top_k]

    async def update_memory(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        entry = await self.durable_memory.get_memory(memory_id)
        if not entry:
            return False

        if "weight" in updates:
            entry.update_weight(updates["weight"])
        if "tags" in updates:
            entry.tags = updates["tags"]
        if "metadata" in updates:
            entry.metadata.update(updates["metadata"])

        entry.touch()
        return await self.durable_memory.storage.update_memory(entry)

    def add_session_turn(self, user_id: str, session_id: Optional[str], role: str, content: str, turn_id: Optional[str] = None):
        self.session_memory.add_turn(user_id, session_id, role, content, turn_id)

    def get_session_context(self,
                            user_id: str,
                            session_id: Optional[str] = None,
                            turns: Optional[int] = None) -> List[Dict[str, Any]]:
        return self.session_memory.get_context(turns=turns, user_id=user_id, session_id=session_id)

    def clear_session(self, user_id: str, session_id: Optional[str] = None):
        self.session_memory.clear(user_id, session_id)
        self.memory_cache.clear(user_id)

    def _assess_confidence(self, content: str, source: str) -> float:
        base_confidence = 0.5
        source_weights = {
            "user": 0.9,
            "system": 0.8,
            "inferred": 0.5,
            "imported": 0.7,
        }
        base_confidence *= source_weights.get(source, 0.5)
        if len(content) > 50:
            base_confidence += 0.1
        return min(base_confidence, 1.0)

    def _assess_importance(self, content: str, keywords: List[str], entities: List[str]) -> float:
        importance = 0.5
        importance += min(len(keywords) * 0.02, 0.1)
        importance += min(len(entities) * 0.05, 0.15)
        if 50 <= len(content) <= 500:
            importance += 0.1
        return min(importance, 1.0)

    async def get_stats(self, user_id: str) -> Dict[str, Any]:
        memories = await self.durable_memory.storage.get_user_memories(user_id)
        durable_memories = [memory for memory in memories if memory.memory_type != MemoryType.CHAT]
        durable_memory_ids = {memory.memory_id for memory in durable_memories}
        in_memory_session_turns = self.session_memory.turn_count(user_id)
        persisted_session_turns = 0
        if self.metadata_store:
            persisted_session_turns = await self.metadata_store.count_user_session_turns(user_id)
        session_turns = max(in_memory_session_turns, persisted_session_turns)
        cached_memories = await self.memory_cache.get_recent(limit=self.memory_cache.max_entries, user_id=user_id)
        cache_entries = sum(
            1
            for memory in cached_memories
            if memory.memory_type != MemoryType.CHAT and memory.memory_id in durable_memory_ids
        )
        return {
            "total_memories": len(durable_memories),
            "session_turns": session_turns,
            "cache_entries": cache_entries,
            # 兼容旧字段，避免前端和脚本立刻失效。
            "working_memory_turns": session_turns,
            "short_term_entries": cache_entries,
            "memory_types": {
                memory_type.value: sum(1 for memory in durable_memories if memory.memory_type == memory_type)
                for memory_type in MemoryType
                if memory_type != MemoryType.CHAT
            },
            "avg_confidence": sum(memory.confidence for memory in durable_memories) / len(durable_memories) if durable_memories else 0,
            "avg_importance": sum(memory.importance for memory in durable_memories) / len(durable_memories) if durable_memories else 0,
        }
