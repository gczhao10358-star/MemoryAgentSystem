#!/usr/bin/env python3
"""
记忆架构回归测试
覆盖 session memory / durable memory / pinned view 以及兼容字段。
"""
import asyncio
import os
import sys
import tempfile
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from memory_assistant.core.memory_manager import MemoryManager
from memory_assistant.core.memory_mate_agent import MemoryMateAgent
from memory_assistant.core.memory_service import MemoryService
from memory_assistant.models.memory import MemoryEntry, MemoryType
from memory_assistant.models.user_profile import InteractionStyle
from memory_assistant.profile.profile_manager import ProfileManager
from memory_assistant.storage.metadata_store import SQLiteMetadataStore
from memory_assistant.utils.embedding import SimpleEmbeddingModel


class FakeStorage:
    """最小可用的持久存储桩。"""

    def __init__(self):
        self.entries = {}
        self.memory_cache = None

    def set_memory_cache(self, memory_cache):
        self.memory_cache = memory_cache

    async def store(self, entry):
        self.entries[entry.memory_id] = entry
        return True

    async def retrieve_by_vector(self, query_vector, user_id, top_k=10):
        matched = [
            {"entry": entry, "vector_score": 1.0}
            for entry in self.entries.values()
            if entry.user_id == user_id
        ]
        return matched[:top_k]

    async def retrieve_by_content(self, user_id, keyword, limit=20):
        return [
            entry
            for entry in self.entries.values()
            if entry.user_id == user_id and keyword in entry.content
        ][:limit]

    async def get_memory(self, memory_id):
        return self.entries.get(memory_id)

    async def update_memory(self, entry):
        self.entries[entry.memory_id] = entry
        return True

    async def get_user_memories(self, user_id, limit=100):
        return [entry for entry in self.entries.values() if entry.user_id == user_id][:limit]


class FakeMemoryCRUD:
    def __init__(self, memories):
        self.storage = type("StorageStub", (), {"get_user_memories": self.get_user_memories})()
        self._memories = memories

    async def get_user_memories(self, user_id, limit=200):
        return [memory for memory in self._memories if memory.user_id == user_id][:limit]


class MemoryArchitectureTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.storage = FakeStorage()
        self.embedding_model = SimpleEmbeddingModel(dimension=16)
        self.manager = MemoryManager(
            storage=self.storage,
            embedding_model=self.embedding_model,
            session_memory_max_turns=6,
            cache_max_entries=20,
            cache_ttl_days=7,
        )

    async def test_new_and_legacy_names_point_to_same_objects(self):
        self.assertIs(self.manager.session_memory, self.manager.working_memory)
        self.assertIs(self.manager.memory_cache, self.manager.short_term_memory)
        self.assertIs(self.manager.durable_memory, self.manager.long_term_memory)

    async def test_session_memory_is_isolated_by_session_id(self):
        self.manager.add_session_turn("user_1", "sess_a", "user", "A1", "turn_a1")
        self.manager.add_session_turn("user_1", "sess_b", "user", "B1", "turn_b1")
        self.manager.add_session_turn("user_1", "sess_a", "assistant", "A2", "turn_a1")

        session_a = self.manager.get_session_context("user_1", "sess_a")
        session_b = self.manager.get_session_context("user_1", "sess_b")

        self.assertEqual([item["content"] for item in session_a], ["A1", "A2"])
        self.assertEqual([item["content"] for item in session_b], ["B1"])

    async def test_stats_expose_new_and_legacy_fields(self):
        durable_entry = MemoryEntry(
            content="用户喜欢咖啡",
            user_id="user_1",
            memory_type=MemoryType.FACT,
        )
        legacy_chat_entry = MemoryEntry(
            content="历史对话",
            user_id="user_1",
            memory_type=MemoryType.CHAT,
        )
        self.storage.entries[durable_entry.memory_id] = durable_entry
        self.storage.entries[legacy_chat_entry.memory_id] = legacy_chat_entry

        self.manager.add_session_turn("user_1", "sess_stats", "user", "你好", "turn_1")
        await self.manager.memory_cache.store(durable_entry)

        stats = await self.manager.get_stats("user_1")

        self.assertEqual(stats["total_memories"], 1)
        self.assertEqual(stats["session_turns"], 1)
        self.assertEqual(stats["cache_entries"], 1)
        self.assertEqual(stats["working_memory_turns"], stats["session_turns"])
        self.assertEqual(stats["short_term_entries"], stats["cache_entries"])
        self.assertNotIn("chat", stats["memory_types"])
        self.assertEqual(stats["memory_types"]["fact"], 1)

        legacy = {
            "working_memory_turns": stats["working_memory_turns"],
            "short_term_entries": stats["short_term_entries"],
        }
        self.assertEqual(legacy["working_memory_turns"], stats["session_turns"])
        self.assertEqual(legacy["short_term_entries"], stats["cache_entries"])

    async def test_pinned_view_is_derived_from_durable_memory(self):
        memories = [
            MemoryEntry(content="普通文档说明", user_id="user_1", memory_type=MemoryType.DOCUMENT, importance=0.2),
            MemoryEntry(content="用户喜欢拿铁", user_id="user_1", memory_type=MemoryType.FACT, importance=0.4),
            MemoryEntry(content="周五交付项目", user_id="user_1", memory_type=MemoryType.TASK, importance=0.6),
            MemoryEntry(content="高重要事件", user_id="user_1", memory_type=MemoryType.EVENT, importance=0.95),
        ]
        memory_crud = FakeMemoryCRUD(memories)
        service = MemoryService(
            memory_manager=self.manager,
            memory_crud=memory_crud,
            retrieval_engine=None,
        )

        pinned = await service.get_pinned_memories("user_1", limit=5)
        pinned_contents = [item.content for item in pinned]

        self.assertIn("用户喜欢拿铁", pinned_contents)
        self.assertIn("周五交付项目", pinned_contents)
        self.assertIn("高重要事件", pinned_contents)
        self.assertNotIn("普通文档说明", pinned_contents)


class StylePromptTests(unittest.TestCase):
    def test_style_prompt_covers_all_interaction_dimensions(self):
        style = InteractionStyle(
            preferred_response_length="long",
            preferred_detail_level="detailed",
            preferred_formality="formal",
            proactivity_level="proactive",
        )

        prompt = MemoryMateAgent._build_style_prompt(style)

        self.assertIn("允许回答较完整地展开", prompt)
        self.assertIn("正式、礼貌、稳重", prompt)
        self.assertIn("系统讲清原理、步骤、边界条件、风险和取舍", prompt)
        self.assertIn("主动补充风险点、替代方案、下一步行动", prompt)


class SessionRegistryTests(unittest.IsolatedAsyncioTestCase):
    async def test_profile_manager_uses_database_as_primary_source(self):
        tmpdir = tempfile.mkdtemp(prefix="memoryassistant_profiles_")
        db_path = os.path.join(tmpdir, "memory.db")
        store = SQLiteMetadataStore(db_path=db_path)
        await store.initialize()
        await store.create_user(
            user_id="user_profile",
            username="profile_user",
            profile_data={
                "user_id": "user_profile",
                "username": "profile_user",
                "topic_preferences": [],
            },
        )

        manager = ProfileManager(data_dir=tmpdir, metadata_store=store)
        profile = await manager.get_profile("user_profile")
        profile.username = "profile_user_renamed"
        profile.name = "画像用户"
        profile.interaction_style.preferred_response_length = "long"
        profile.add_or_update_topic("数据库画像", 0.9)
        profile.update_behavior_stats("query")
        saved = await manager.save_profile(profile)

        self.assertTrue(saved)
        self.assertFalse(os.path.exists(os.path.join(tmpdir, "user_profile_profile.json")))

        user_record = await store.get_user("user_profile")
        self.assertIsNotNone(user_record)
        self.assertEqual(user_record["username"], "profile_user_renamed")
        self.assertIn("数据库画像", user_record["profile_data"])
        self.assertEqual(user_record["name"], "画像用户")
        self.assertEqual(user_record["total_interactions"], 1)
        self.assertEqual(user_record["total_queries"], 1)
        self.assertEqual(user_record["preferred_response_length"], "long")
        self.assertIsNotNone(user_record["last_interaction"])

        await store.close()

    async def test_sqlite_user_registry_reuses_username(self):
        tmpdir = tempfile.mkdtemp(prefix="memoryassistant_users_")
        db_path = os.path.join(tmpdir, "memory.db")
        store = SQLiteMetadataStore(db_path=db_path)
        await store.initialize()

        created = await store.create_user(
            user_id="user_alice",
            username="alice",
            profile_data={"user_id": "user_alice", "username": "alice"},
        )
        self.assertIsNotNone(created)
        self.assertEqual(created["username"], "alice")

        fetched = await store.get_user_by_username("alice")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["user_id"], "user_alice")

        duplicate = await store.create_user(
            user_id="user_other",
            username="alice",
            profile_data={"user_id": "user_other", "username": "alice"},
        )
        self.assertIsNotNone(duplicate)
        self.assertEqual(duplicate["user_id"], "user_alice")

        await store.close()

    async def test_sqlite_session_registry_lifecycle(self):
        tmpdir = tempfile.mkdtemp(prefix="memoryassistant_registry_")
        db_path = os.path.join(tmpdir, "memory.db")
        store = SQLiteMetadataStore(db_path=db_path)
        await store.initialize()

        user_id = "user_registry"
        session_id = "sess_registry"

        await store.create_session(user_id=user_id, session_id=session_id, title="初始标题")
        await store.append_session_message(
            user_id=user_id,
            session_id=session_id,
            message_id="msg_1",
            role="user",
            content="第一条消息",
            turn_id="turn_1",
        )

        updated = await store.update_session(
            user_id=user_id,
            session_id=session_id,
            title="重命名后的会话",
            status="active",
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated["title"], "重命名后的会话")

        archived = await store.update_session_status(user_id=user_id, session_id=session_id, status="archived")
        self.assertTrue(archived)
        self.assertEqual(await store.list_sessions(user_id=user_id), [])

        all_sessions = await store.list_sessions(user_id=user_id, include_archived=True)
        self.assertEqual(len(all_sessions), 1)
        self.assertEqual(all_sessions[0]["status"], "archived")

        deleted = await store.delete_session(user_id=user_id, session_id=session_id)
        self.assertTrue(deleted)
        self.assertEqual(await store.get_session_messages(user_id=user_id, session_id=session_id), [])

        await store.close()

    async def test_stats_can_recover_session_turns_from_sqlite(self):
        tmpdir = tempfile.mkdtemp(prefix="memoryassistant_stats_")
        db_path = os.path.join(tmpdir, "memory.db")
        store = SQLiteMetadataStore(db_path=db_path)
        await store.initialize()

        user_id = "user_stats"
        session_id = "sess_stats"
        await store.create_session(user_id=user_id, session_id=session_id, title="统计恢复")
        await store.append_session_message(
            user_id=user_id,
            session_id=session_id,
            message_id="msg_user_1",
            role="user",
            content="第一轮用户消息",
            turn_id="turn_1",
        )
        await store.append_session_message(
            user_id=user_id,
            session_id=session_id,
            message_id="msg_assistant_1",
            role="assistant",
            content="第一轮助手消息",
            turn_id="turn_1",
        )
        await store.append_session_message(
            user_id=user_id,
            session_id=session_id,
            message_id="msg_user_2",
            role="user",
            content="第二轮用户消息",
            turn_id="turn_2",
        )

        manager = MemoryManager(
            storage=FakeStorage(),
            embedding_model=SimpleEmbeddingModel(dimension=16),
            metadata_store=store,
            session_memory_max_turns=6,
            cache_max_entries=20,
            cache_ttl_days=7,
        )

        stats = await manager.get_stats(user_id)
        self.assertEqual(stats["session_turns"], 2)
        self.assertEqual(stats["working_memory_turns"], 2)

        await store.close()


if __name__ == "__main__":
    unittest.main()
