"""
统一记忆服务
收敛会话记忆、持久记忆 CRUD 和检索入口。
"""
from datetime import datetime
import uuid
from typing import Any, Dict, List, Optional

from ..models.memory import MemoryEntry
from ..models.memory import MemoryType


class MemoryService:
    """统一的记忆访问门面。"""

    def __init__(self, memory_manager, memory_crud, retrieval_engine):
        self.memory_manager = memory_manager
        self.memory_crud = memory_crud
        self.retrieval_engine = retrieval_engine

    def add_session_turn(self,
                         user_id: str,
                         session_id: Optional[str],
                         role: str,
                         content: str,
                         turn_id: Optional[str] = None):
        self.memory_manager.add_session_turn(user_id, session_id, role, content, turn_id)

    def get_session_context(self,
                            user_id: str,
                            session_id: Optional[str],
                            turns: Optional[int] = None) -> List[Dict[str, Any]]:
        return self.memory_manager.get_session_context(user_id, session_id, turns)

    def clear_session(self, user_id: str, session_id: Optional[str] = None):
        self.memory_manager.clear_session(user_id, session_id)

    async def create_session(self,
                             user_id: str,
                             title: Optional[str] = None,
                             session_id: Optional[str] = None) -> Dict[str, Any]:
        normalized_session_id = session_id or f"sess_{uuid.uuid4().hex[:12]}"
        session_title = title or "新对话"
        await self.memory_crud.storage.metadata_store.create_session(
            user_id=user_id,
            session_id=normalized_session_id,
            title=session_title,
            status="active",
        )
        session = await self.memory_crud.storage.metadata_store.get_session(user_id, normalized_session_id)
        return session or {
            "session_id": normalized_session_id,
            "user_id": user_id,
            "title": session_title,
            "status": "active",
            "message_count": 0,
        }

    async def list_sessions(self,
                            user_id: str,
                            limit: int = 50,
                            include_archived: bool = False) -> List[Dict[str, Any]]:
        return await self.memory_crud.storage.metadata_store.list_sessions(
            user_id=user_id,
            limit=limit,
            include_archived=include_archived,
        )

    async def get_session_messages(self,
                                   user_id: str,
                                   session_id: str,
                                   limit: int = 200) -> List[Dict[str, Any]]:
        rows = await self.memory_crud.storage.metadata_store.get_session_messages(
            user_id=user_id,
            session_id=session_id,
            limit=limit,
        )
        return [
            {
                "id": row["message_id"],
                "turn_id": row.get("turn_id"),
                "session_id": row["session_id"],
                "role": row["role"],
                "content": row["content"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    async def record_session_turn(self,
                                  user_id: str,
                                  session_id: Optional[str],
                                  role: str,
                                  content: str,
                                  turn_id: Optional[str] = None,
                                  created_at: Optional[datetime] = None,
                                  message_id: Optional[str] = None):
        normalized_session_id = session_id or "default"
        message_id = message_id or f"msg_{uuid.uuid4().hex[:12]}"
        inserted = await self.memory_crud.storage.metadata_store.append_session_message(
            user_id=user_id,
            session_id=normalized_session_id,
            message_id=message_id,
            role=role,
            content=content,
            turn_id=turn_id,
            created_at=created_at,
        )
        if inserted:
            self.add_session_turn(user_id, normalized_session_id, role, content, turn_id)

    async def archive_session(self, user_id: str, session_id: str) -> bool:
        return await self.memory_crud.storage.metadata_store.update_session_status(
            user_id=user_id,
            session_id=session_id,
            status="archived",
        )

    async def update_session(self,
                             user_id: str,
                             session_id: str,
                             title: Optional[str] = None,
                             summary: Optional[str] = None,
                             preview: Optional[str] = None,
                             status: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return await self.memory_crud.storage.metadata_store.update_session(
            user_id=user_id,
            session_id=session_id,
            title=title,
            summary=summary,
            preview=preview,
            status=status,
        )

    async def delete_session(self, user_id: str, session_id: str) -> bool:
        self.clear_session(user_id, session_id)
        return await self.memory_crud.storage.metadata_store.delete_session(
            user_id=user_id,
            session_id=session_id,
        )

    async def store_memory(self,
                           user_id: str,
                           content: str,
                           current_time: Dict[str, Any],
                           memory_type: str = "auto",
                           session_id: Optional[str] = None,
                           turn_id: Optional[str] = None,
                           scope: str = "user",
                           status: str = "active",
                           source: str = "user") -> Dict[str, Any]:
        result = await self.memory_crud.create(
            user_id=user_id,
            content=content,
            current_time=current_time,
            memory_type=memory_type,
            session_id=session_id,
            turn_id=turn_id,
            scope=scope,
            status=status,
            source=source,
        )

        if result.get("success"):
            entry = await self.memory_crud.storage.get_memory(result["memory_id"])
            if entry:
                await self.memory_manager.memory_cache.store(entry)

        return result

    async def read_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        return await self.memory_crud.read(memory_id)

    async def update_memory(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        return await self.memory_crud.update(memory_id, updates)

    async def delete_memory(self, memory_id: str) -> bool:
        return await self.memory_crud.delete(memory_id)

    async def delete_memories_by_date(self, user_id: str, date_str: str,
                                      memory_types: Optional[List[str]] = None) -> int:
        return await self.memory_crud.delete_by_date(user_id, date_str, memory_types)

    async def search_memories(self,
                              user_id: str,
                              query: str,
                              top_k: int = 10,
                              filters: Optional[Dict[str, Any]] = None,
                              user_profile: Optional[Dict[str, Any]] = None,
                              use_personalization: bool = True) -> List[Dict[str, Any]]:
        if not query or not query.strip():
            return await self.memory_crud.search(
                user_id=user_id,
                query=None,
                filters=filters,
                top_k=top_k,
            )

        raw_results = await self.retrieval_engine.retrieve(
            query=query,
            user_id=user_id,
            top_k=top_k,
            use_personalization=use_personalization,
            user_profile=user_profile,
        )

        results = [
            self._retrieval_result_to_dict(item)
            for item in raw_results
            if self._is_durable_memory_entry(item.memory)
        ]
        if not filters:
            return results
        return [entry for entry in results if self._matches_filters(entry, filters)]

    async def search_memories_by_date(self, user_id: str, date_str: str,
                                      memory_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        return await self.memory_crud.search_by_date(user_id, date_str, memory_types)

    async def get_pinned_memories(self, user_id: str, limit: int = 5) -> List[MemoryEntry]:
        memories = await self.memory_crud.storage.get_user_memories(user_id, limit=200)
        pinned_candidates = [
            memory for memory in memories
            if memory.memory_type.value in {"fact", "task", "reminder"} or memory.importance >= 0.75
        ]
        pinned_candidates.sort(
            key=lambda memory: (memory.importance, memory.access_count, memory.updated_at),
            reverse=True,
        )
        return pinned_candidates[:limit]

    async def build_context_bundle(self,
                                   user_id: str,
                                   session_id: Optional[str],
                                   query: str,
                                   top_k: int = 5,
                                   user_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raw_results = await self.retrieval_engine.retrieve(
            query=query,
            user_id=user_id,
            top_k=top_k,
            use_personalization=True,
            user_profile=user_profile,
        )
        relevant_memories = [
            item for item in raw_results
            if self._is_durable_memory_entry(item.memory)
        ]

        return {
            "session": self.get_session_context(user_id, session_id),
            "pinned": await self.get_pinned_memories(user_id),
            "relevant": relevant_memories,
        }

    async def get_stats(self, user_id: str) -> Dict[str, Any]:
        return await self.memory_manager.get_stats(user_id)

    def _retrieval_result_to_dict(self, result) -> Dict[str, Any]:
        memory = result.memory
        return {
            "memory_id": memory.memory_id,
            "user_id": memory.user_id,
            "content": memory.content,
            "memory_type": memory.memory_type.value,
            "scope": memory.scope,
            "session_id": memory.session_id,
            "turn_id": memory.turn_id,
            "status": memory.status,
            "importance": memory.importance,
            "created_at": memory.created_at.isoformat(),
            "updated_at": memory.updated_at.isoformat(),
            "metadata": memory.metadata,
            "tags": memory.tags,
            "score": result.final_score,
        }

    def _matches_filters(self, entry: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        metadata = entry.get("metadata", {})
        for key, value in filters.items():
            if key == "type" and entry.get("memory_type") != value:
                return False
            if key == "date" and value not in metadata.get("datetime", ""):
                return False
            if key == "tag" and value not in metadata.get("tags", []):
                return False
            if key == "location" and metadata.get("location") != value:
                return False
            if key == "person" and value not in metadata.get("people", []):
                return False
        return True

    def _is_durable_memory_entry(self, memory: MemoryEntry) -> bool:
        return memory.memory_type != MemoryType.CHAT
