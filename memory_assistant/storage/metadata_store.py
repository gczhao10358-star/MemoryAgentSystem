"""
元数据存储模块
基于SQLite的元数据存储实现
"""
import json
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Optional, Any
from ..models.memory import MemoryEntry, MemoryType, MemoryState


class MetadataStore(ABC):
    """元数据存储抽象基类"""

    @abstractmethod
    async def save_memory(self, entry: MemoryEntry) -> bool:
        """保存记忆"""
        pass

    @abstractmethod
    async def get_memory(self, memory_id: str) -> Optional[MemoryEntry]:
        """获取记忆"""
        pass

    @abstractmethod
    async def get_memories_by_user(self, user_id: str, limit: int = 100,
                                   offset: int = 0) -> List[MemoryEntry]:
        """获取用户的所有记忆"""
        pass

    @abstractmethod
    async def update_memory(self, entry: MemoryEntry) -> bool:
        """更新记忆"""
        pass

    @abstractmethod
    async def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        pass


class SQLiteMetadataStore(MetadataStore):
    """基于SQLite的元数据存储实现"""

    def __init__(self, db_path: str = "./data/memory.db"):
        self.db_path = db_path
        self.conn = None

    async def initialize(self):
        """初始化数据库连接和表结构"""
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        # 创建记忆表
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                memory_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                content TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                scope TEXT DEFAULT 'user',
                session_id TEXT,
                turn_id TEXT,
                status TEXT DEFAULT 'active',
                state TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confidence REAL DEFAULT 0.5,
                importance REAL DEFAULT 0.5,
                weight REAL DEFAULT 0.5,
                access_count INTEGER DEFAULT 0,
                tags TEXT,
                related_entities TEXT,
                source TEXT DEFAULT 'user',
                metadata TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # 创建用户表
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_interactions INTEGER DEFAULT 0,
                total_queries INTEGER DEFAULT 0,
                total_memories_created INTEGER DEFAULT 0,
                last_interaction TIMESTAMP,
                preferred_response_length TEXT,
                preferred_detail_level TEXT,
                preferred_formality TEXT,
                proactivity_level TEXT,
                expressiveness TEXT,
                profile_data TEXT
            )
        """)

        # 创建会话表
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT,
                summary TEXT,
                preview TEXT,
                status TEXT DEFAULT 'active',
                message_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 创建会话消息表
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS session_messages (
                message_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                turn_id TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.commit()
        await self._ensure_compatible_schema()

        # 创建索引
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_user_time
            ON memories(user_id, created_at)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_user_session_time
            ON memories(user_id, session_id, created_at)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_scope_status
            ON memories(scope, status)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_user_updated
            ON sessions(user_id, updated_at)
        """)
        self.conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username
            ON users(username)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_messages_session_time
            ON session_messages(session_id, created_at)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_user_weight
            ON memories(user_id, weight)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_state
            ON memories(state)
        """)

        self.conn.commit()

    async def _ensure_compatible_schema(self):
        """为已有数据库补充新增字段。"""
        cursor = self.conn.execute("PRAGMA table_info(memories)")
        existing_memory_columns = {row["name"] for row in cursor.fetchall()}

        memory_column_definitions = {
            "scope": "TEXT DEFAULT 'user'",
            "session_id": "TEXT",
            "turn_id": "TEXT",
            "status": "TEXT DEFAULT 'active'",
        }

        for column_name, column_definition in memory_column_definitions.items():
            if column_name in existing_memory_columns:
                continue
            self.conn.execute(
                f"ALTER TABLE memories ADD COLUMN {column_name} {column_definition}"
            )

        cursor = self.conn.execute("PRAGMA table_info(users)")
        existing_user_columns = {row["name"] for row in cursor.fetchall()}
        user_column_definitions = {
            "username": "TEXT",
            "name": "TEXT",
            "total_interactions": "INTEGER DEFAULT 0",
            "total_queries": "INTEGER DEFAULT 0",
            "total_memories_created": "INTEGER DEFAULT 0",
            "last_interaction": "TIMESTAMP",
            "preferred_response_length": "TEXT",
            "preferred_detail_level": "TEXT",
            "preferred_formality": "TEXT",
            "proactivity_level": "TEXT",
            "expressiveness": "TEXT",
        }

        for column_name, column_definition in user_column_definitions.items():
            if column_name in existing_user_columns:
                continue
            self.conn.execute(
                f"ALTER TABLE users ADD COLUMN {column_name} {column_definition}"
            )

        self.conn.commit()

    def _extract_user_profile_columns(self, profile_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """从画像快照中提取便于查询的用户列。"""
        profile_data = profile_data or {}
        interaction_style = profile_data.get("interaction_style") or {}
        behavior_stats = profile_data.get("behavior_stats") or {}

        return {
            "username": profile_data.get("username"),
            "name": profile_data.get("name"),
            "total_interactions": behavior_stats.get("total_interactions", 0),
            "total_queries": behavior_stats.get("total_queries", 0),
            "total_memories_created": behavior_stats.get("total_memories_created", 0),
            "last_interaction": behavior_stats.get("last_interaction"),
            "preferred_response_length": interaction_style.get("preferred_response_length"),
            "preferred_detail_level": interaction_style.get("preferred_detail_level"),
            "preferred_formality": interaction_style.get("preferred_formality"),
            "proactivity_level": interaction_style.get("proactivity_level"),
            "expressiveness": interaction_style.get("expressiveness"),
        }

    async def save_memory(self, entry: MemoryEntry) -> bool:
        """保存记忆"""
        try:
            cursor = self.conn.execute("""
                INSERT INTO memories (
                    memory_id, user_id, content, memory_type, scope, session_id, turn_id, status, state,
                    created_at, updated_at, last_accessed,
                    confidence, importance, weight, access_count,
                    tags, related_entities, source, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.memory_id,
                entry.user_id,
                entry.content,
                entry.memory_type.value,
                entry.scope,
                entry.session_id,
                entry.turn_id,
                entry.status,
                entry.state.value,
                entry.created_at.isoformat(),
                entry.updated_at.isoformat(),
                entry.last_accessed.isoformat(),
                entry.confidence,
                entry.importance,
                entry.weight,
                entry.access_count,
                json.dumps(entry.tags),
                json.dumps(entry.related_entities),
                entry.source,
                json.dumps(entry.metadata),
            ))
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error saving memory: {e}")
            return False

    async def get_memory(self, memory_id: str) -> Optional[MemoryEntry]:
        """获取记忆"""
        try:
            cursor = self.conn.execute(
                "SELECT * FROM memories WHERE memory_id = ?",
                (memory_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_entry(row)
            return None
        except Exception as e:
            print(f"Error getting memory: {e}")
            return None

    async def get_memories_by_user(self, user_id: str, limit: int = 100,
                                   offset: int = 0) -> List[MemoryEntry]:
        """获取用户的所有记忆"""
        try:
            cursor = self.conn.execute(
                """SELECT * FROM memories
                   WHERE user_id = ? AND state != 'forgotten'
                   ORDER BY created_at DESC
                   LIMIT ? OFFSET ?""",
                (user_id, limit, offset)
            )
            return [self._row_to_entry(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting memories: {e}")
            return []

    async def get_memories_for_evolution(self, min_weight: float = 0.0,
                                         max_weight: float = 1.0,
                                         limit: int = 1000) -> List[MemoryEntry]:
        """获取需要演化的记忆"""
        try:
            cursor = self.conn.execute(
                """SELECT * FROM memories
                   WHERE weight BETWEEN ? AND ?
                   AND state NOT IN ('forgotten', 'core')
                   ORDER BY last_accessed ASC
                   LIMIT ?""",
                (min_weight, max_weight, limit)
            )
            return [self._row_to_entry(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting memories for evolution: {e}")
            return []

    async def update_memory(self, entry: MemoryEntry) -> bool:
        """更新记忆"""
        try:
            cursor = self.conn.execute("""
                UPDATE memories SET
                    content = ?,
                    memory_type = ?,
                    scope = ?,
                    session_id = ?,
                    turn_id = ?,
                    status = ?,
                    state = ?,
                    updated_at = ?,
                    last_accessed = ?,
                    confidence = ?,
                    importance = ?,
                    weight = ?,
                    access_count = ?,
                    tags = ?,
                    related_entities = ?,
                    metadata = ?
                WHERE memory_id = ?
            """, (
                entry.content,
                entry.memory_type.value,
                entry.scope,
                entry.session_id,
                entry.turn_id,
                entry.status,
                entry.state.value,
                entry.updated_at.isoformat(),
                entry.last_accessed.isoformat(),
                entry.confidence,
                entry.importance,
                entry.weight,
                entry.access_count,
                json.dumps(entry.tags),
                json.dumps(entry.related_entities),
                json.dumps(entry.metadata),
                entry.memory_id,
            ))
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error updating memory: {e}")
            return False

    async def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        try:
            cursor = self.conn.execute(
                "DELETE FROM memories WHERE memory_id = ?",
                (memory_id,)
            )
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error deleting memory: {e}")
            return False

    async def delete_memories_by_date(self, user_id: str, date_str: str,
                                       memory_types: List[str] = None) -> int:
        """
        按日期删除用户的记忆

        Args:
            user_id: 用户ID
            date_str: 日期字符串 (YYYY-MM-DD)
            memory_types: 要删除的记忆类型列表，默认为 ['event', 'task', 'reminder']

        Returns:
            删除的记忆数量
        """
        if memory_types is None:
            memory_types = ['event', 'task', 'reminder']

        try:
            # 构建类型过滤条件
            type_placeholders = ', '.join(['?' for _ in memory_types])

            # 删除指定日期和类型的记忆
            # 使用 content LIKE 来匹配包含该日期的记忆
            query = f"""
                DELETE FROM memories
                WHERE user_id = ?
                AND memory_type IN ({type_placeholders})
                AND (
                    content LIKE ? OR
                    content LIKE ? OR
                    content LIKE ? OR
                    metadata LIKE ?
                )
                AND state != 'forgotten'
            """

            # 准备日期匹配模式
            date_patterns = [
                f"%{date_str}%",  # 完整日期格式
                f"%{date_str.replace('-', '年').replace('-', '月')}%",  # 中文格式
                f"%{date_str.split('-')[1]}月{date_str.split('-')[2]}%",  # MM月DD
                f"%{date_str}%",  # metadata 中的日期
            ]

            params = [user_id] + memory_types + date_patterns

            cursor = self.conn.execute(query, params)
            self.conn.commit()
            deleted_count = cursor.rowcount

            print(f"[删除记忆] 用户 {user_id} 在 {date_str} 删除了 {deleted_count} 条记忆")
            return deleted_count

        except Exception as e:
            print(f"Error deleting memories by date: {e}")
            return 0

    async def search_by_content(self, user_id: str, keyword: str,
                                limit: int = 20) -> List[MemoryEntry]:
        """全文搜索记忆内容"""
        try:
            cursor = self.conn.execute(
                """SELECT * FROM memories
                   WHERE user_id = ? AND content LIKE ?
                   AND state != 'forgotten'
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (user_id, f"%{keyword}%", limit)
            )
            return [self._row_to_entry(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error searching memories: {e}")
            return []

    async def search_by_time_range(self, user_id: str,
                                   start_time: datetime,
                                   end_time: datetime,
                                   limit: int = 100) -> List[MemoryEntry]:
        """
        按时间范围搜索记忆
        优先搜索 event_time，如果不存在则搜索 created_at
        """
        try:
            cursor = self.conn.execute(
                """SELECT * FROM memories
                   WHERE user_id = ?
                   AND state != 'forgotten'
                   AND (
                       -- 检查 event_time 是否在范围内
                       (
                           json_extract(metadata, '$.event_time') IS NOT NULL
                           AND json_extract(metadata, '$.event_time') >= ?
                           AND json_extract(metadata, '$.event_time') <= ?
                       )
                       OR
                       -- 或者 created_at 在范围内
                       (
                           json_extract(metadata, '$.event_time') IS NULL
                           AND created_at >= ?
                           AND created_at <= ?
                       )
                   )
                   ORDER BY
                       CASE
                           WHEN json_extract(metadata, '$.event_time') IS NOT NULL
                           THEN json_extract(metadata, '$.event_time')
                           ELSE created_at
                       END DESC
                   LIMIT ?""",
                (user_id,
                 start_time.isoformat(), end_time.isoformat(),
                 start_time.isoformat(), end_time.isoformat(),
                 limit)
            )
            return [self._row_to_entry(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error searching by time range: {e}")
            return []

    async def search_memories(self, user_id: str,
                              keyword: Optional[str] = None,
                              start_time: Optional[datetime] = None,
                              end_time: Optional[datetime] = None,
                              memory_type: Optional[str] = None,
                              limit: int = 50) -> List[MemoryEntry]:
        """
        综合搜索记忆
        支持关键词、时间范围、记忆类型筛选
        """
        try:
            conditions = ["user_id = ?", "state != 'forgotten'"]
            params = [user_id]

            if keyword:
                conditions.append("content LIKE ?")
                params.append(f"%{keyword}%")

            if memory_type:
                conditions.append("memory_type = ?")
                params.append(memory_type)

            if start_time and end_time:
                # 时间范围筛选
                time_condition = """(
                    (json_extract(metadata, '$.event_time') IS NOT NULL
                     AND json_extract(metadata, '$.event_time') >= ?
                     AND json_extract(metadata, '$.event_time') <= ?)
                    OR
                    (json_extract(metadata, '$.event_time') IS NULL
                     AND created_at >= ?
                     AND created_at <= ?)
                )"""
                conditions.append(time_condition)
                params.extend([
                    start_time.isoformat(), end_time.isoformat(),
                    start_time.isoformat(), end_time.isoformat()
                ])

            where_clause = " AND ".join(conditions)

            sql = f"""SELECT * FROM memories
                      WHERE {where_clause}
                      ORDER BY created_at DESC
                      LIMIT ?"""
            params.append(limit)

            cursor = self.conn.execute(sql, params)
            return [self._row_to_entry(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error in comprehensive search: {e}")
            return []

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        """将数据库行转换为MemoryEntry"""
        entry = MemoryEntry(
            content=row['content'],
            user_id=row['user_id'],
            memory_type=MemoryType(row['memory_type']),
            memory_id=row['memory_id'],
            scope=row['scope'] if 'scope' in row.keys() and row['scope'] else 'user',
            session_id=row['session_id'] if 'session_id' in row.keys() else None,
            turn_id=row['turn_id'] if 'turn_id' in row.keys() else None,
            status=row['status'] if 'status' in row.keys() and row['status'] else 'active',
        )
        entry.state = MemoryState(row['state'])
        entry.confidence = row['confidence']
        entry.importance = row['importance']
        entry.weight = row['weight']
        entry.access_count = row['access_count']
        entry.source = row['source']

        # 解析时间
        for field_name in ['created_at', 'updated_at', 'last_accessed']:
            try:
                setattr(entry, field_name,
                        datetime.fromisoformat(row[field_name]))
            except:
                setattr(entry, field_name, datetime.now())

        # 解析JSON字段
        try:
            entry.tags = json.loads(row['tags']) if row['tags'] else []
        except:
            entry.tags = []

        try:
            entry.related_entities = json.loads(row['related_entities']) if row['related_entities'] else []
        except:
            entry.related_entities = []

        try:
            entry.metadata = json.loads(row['metadata']) if row['metadata'] else {}
        except:
            entry.metadata = {}

        return entry

    async def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()

    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """按用户 ID 获取用户记录。"""
        try:
            cursor = self.conn.execute(
                """SELECT * FROM users WHERE user_id = ?""",
                (user_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            print(f"Error getting user: {e}")
            return None

    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """按用户名获取用户记录。"""
        try:
            cursor = self.conn.execute(
                """SELECT * FROM users WHERE username = ?""",
                (username,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            print(f"Error getting user by username: {e}")
            return None

    async def list_users(self,
                         limit: int = 50,
                         offset: int = 0,
                         keyword: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取用户列表。"""
        try:
            params: List[Any] = []
            where_clause = ""
            if keyword:
                where_clause = """
                    WHERE user_id LIKE ? OR username LIKE ? OR name LIKE ?
                """
                keyword_pattern = f"%{keyword}%"
                params.extend([keyword_pattern, keyword_pattern, keyword_pattern])

            params.extend([limit, offset])
            cursor = self.conn.execute(
                f"""SELECT * FROM users
                    {where_clause}
                    ORDER BY updated_at DESC, created_at DESC
                    LIMIT ? OFFSET ?""",
                params,
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error listing users: {e}")
            return []

    async def count_users(self, keyword: Optional[str] = None) -> int:
        """统计用户数量。"""
        try:
            params: List[Any] = []
            where_clause = ""
            if keyword:
                where_clause = """
                    WHERE user_id LIKE ? OR username LIKE ? OR name LIKE ?
                """
                keyword_pattern = f"%{keyword}%"
                params.extend([keyword_pattern, keyword_pattern, keyword_pattern])

            cursor = self.conn.execute(
                f"SELECT COUNT(*) AS total FROM users {where_clause}",
                params,
            )
            row = cursor.fetchone()
            return int(row["total"]) if row else 0
        except Exception as e:
            print(f"Error counting users: {e}")
            return 0

    async def create_user(self,
                          user_id: str,
                          username: str,
                          profile_data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """创建用户记录。"""
        now = datetime.now().isoformat()
        profile_columns = self._extract_user_profile_columns(profile_data)
        try:
            self.conn.execute("""
                INSERT INTO users (
                    user_id, username, name, created_at, updated_at,
                    total_interactions, total_queries, total_memories_created, last_interaction,
                    preferred_response_length, preferred_detail_level, preferred_formality,
                    proactivity_level, expressiveness, profile_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                username,
                profile_columns["name"],
                now,
                now,
                profile_columns["total_interactions"],
                profile_columns["total_queries"],
                profile_columns["total_memories_created"],
                profile_columns["last_interaction"],
                profile_columns["preferred_response_length"],
                profile_columns["preferred_detail_level"],
                profile_columns["preferred_formality"],
                profile_columns["proactivity_level"],
                profile_columns["expressiveness"],
                json.dumps(profile_data, ensure_ascii=False) if profile_data else None,
            ))
            self.conn.commit()
            return await self.get_user(user_id)
        except sqlite3.IntegrityError:
            existing = await self.get_user_by_username(username)
            if existing:
                return existing
            existing = await self.get_user(user_id)
            return existing
        except Exception as e:
            print(f"Error creating user: {e}")
            return None

    async def update_user_profile_data(self, user_id: str, profile_data: Dict[str, Any]) -> bool:
        """更新用户画像快照。"""
        profile_columns = self._extract_user_profile_columns(profile_data)
        try:
            cursor = self.conn.execute("""
                UPDATE users
                SET username = COALESCE(?, username),
                    name = ?,
                    total_interactions = ?,
                    total_queries = ?,
                    total_memories_created = ?,
                    last_interaction = ?,
                    preferred_response_length = ?,
                    preferred_detail_level = ?,
                    preferred_formality = ?,
                    proactivity_level = ?,
                    expressiveness = ?,
                    profile_data = ?,
                    updated_at = ?
                WHERE user_id = ?
            """, (
                profile_columns["username"],
                profile_columns["name"],
                profile_columns["total_interactions"],
                profile_columns["total_queries"],
                profile_columns["total_memories_created"],
                profile_columns["last_interaction"],
                profile_columns["preferred_response_length"],
                profile_columns["preferred_detail_level"],
                profile_columns["preferred_formality"],
                profile_columns["proactivity_level"],
                profile_columns["expressiveness"],
                json.dumps(profile_data, ensure_ascii=False),
                datetime.now().isoformat(),
                user_id,
            ))
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error updating user profile data: {e}")
            return False

    async def clear_user_profile_data(self, user_id: str) -> bool:
        """清空用户画像快照。"""
        try:
            cursor = self.conn.execute("""
                UPDATE users
                SET name = NULL,
                    total_interactions = 0,
                    total_queries = 0,
                    total_memories_created = 0,
                    last_interaction = NULL,
                    preferred_response_length = NULL,
                    preferred_detail_level = NULL,
                    preferred_formality = NULL,
                    proactivity_level = NULL,
                    expressiveness = NULL,
                    profile_data = NULL,
                    updated_at = ?
                WHERE user_id = ?
            """, (
                datetime.now().isoformat(),
                user_id,
            ))
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error clearing user profile data: {e}")
            return False

    async def create_session(self,
                             user_id: str,
                             session_id: str,
                             title: Optional[str] = None,
                             summary: Optional[str] = None,
                             status: str = "active") -> bool:
        """创建会话。"""
        now = datetime.now().isoformat()
        try:
            self.conn.execute("""
                INSERT OR IGNORE INTO sessions (
                    session_id, user_id, title, summary, preview, status,
                    message_count, created_at, updated_at, last_message_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
            """, (
                session_id,
                user_id,
                title or "新对话",
                summary,
                "",
                status,
                now,
                now,
                now,
            ))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error creating session: {e}")
            return False

    async def get_session(self, user_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        """获取单个会话。"""
        try:
            cursor = self.conn.execute(
                """SELECT * FROM sessions WHERE user_id = ? AND session_id = ?""",
                (user_id, session_id)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            print(f"Error getting session: {e}")
            return None

    async def list_sessions(self,
                            user_id: str,
                            limit: int = 50,
                            include_archived: bool = False) -> List[Dict[str, Any]]:
        """列出用户会话。"""
        try:
            if include_archived:
                cursor = self.conn.execute(
                    """SELECT * FROM sessions
                       WHERE user_id = ?
                       ORDER BY last_message_at DESC, updated_at DESC
                       LIMIT ?""",
                    (user_id, limit)
                )
            else:
                cursor = self.conn.execute(
                    """SELECT * FROM sessions
                       WHERE user_id = ? AND status != 'archived'
                       ORDER BY last_message_at DESC, updated_at DESC
                       LIMIT ?""",
                    (user_id, limit)
                )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error listing sessions: {e}")
            return []

    async def touch_session(self,
                            user_id: str,
                            session_id: str,
                            preview: Optional[str] = None,
                            title: Optional[str] = None,
                            status: Optional[str] = None,
                            increment_message_count: bool = True):
        """更新会话元信息。"""
        existing = await self.get_session(user_id, session_id)
        if not existing:
            await self.create_session(user_id, session_id, title=title, status=status or "active")
            existing = await self.get_session(user_id, session_id)

        if not existing:
            return

        now = datetime.now().isoformat()
        next_title = existing.get("title") or title or "新对话"
        if title and (not existing.get("title") or existing.get("title") == "新对话"):
            next_title = title

        next_status = status or existing.get("status") or "active"
        next_preview = preview if preview is not None else existing.get("preview", "")
        next_count = (existing.get("message_count") or 0) + (1 if increment_message_count else 0)

        try:
            self.conn.execute("""
                UPDATE sessions SET
                    title = ?,
                    preview = ?,
                    status = ?,
                    message_count = ?,
                    updated_at = ?,
                    last_message_at = ?
                WHERE user_id = ? AND session_id = ?
            """, (
                next_title,
                next_preview,
                next_status,
                next_count,
                now,
                now,
                user_id,
                session_id,
            ))
            self.conn.commit()
        except Exception as e:
            print(f"Error touching session: {e}")

    async def append_session_message(self,
                                     user_id: str,
                                     session_id: str,
                                     message_id: str,
                                     role: str,
                                     content: str,
                                     turn_id: Optional[str] = None,
                                     created_at: Optional[datetime] = None):
        """追加会话消息。"""
        timestamp = (created_at or datetime.now()).isoformat()
        title = content[:24] if role == "user" else None

        await self.create_session(user_id, session_id, title=title)

        try:
            cursor = self.conn.execute("""
                INSERT OR IGNORE INTO session_messages (
                    message_id, session_id, user_id, turn_id, role, content, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                message_id,
                session_id,
                user_id,
                turn_id,
                role,
                content,
                timestamp,
            ))
            self.conn.commit()
        except Exception as e:
            print(f"Error appending session message: {e}")
            return False

        if cursor.rowcount <= 0:
            return False

        await self.touch_session(
            user_id=user_id,
            session_id=session_id,
            preview=content[:120],
            title=title,
            status="active",
            increment_message_count=True,
        )
        return True

    async def get_session_messages(self,
                                   user_id: str,
                                   session_id: str,
                                   limit: int = 200) -> List[Dict[str, Any]]:
        """获取会话消息列表。"""
        try:
            cursor = self.conn.execute(
                """SELECT * FROM session_messages
                   WHERE user_id = ? AND session_id = ?
                   ORDER BY created_at ASC
                   LIMIT ?""",
                (user_id, session_id, limit)
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting session messages: {e}")
            return []

    async def count_user_session_turns(self, user_id: str) -> int:
        """统计用户历史会话轮次，优先按 turn_id 去重。"""
        try:
            cursor = self.conn.execute(
                """
                SELECT COUNT(DISTINCT COALESCE(NULLIF(turn_id, ''), message_id)) AS total
                FROM session_messages
                WHERE user_id = ?
                """,
                (user_id,)
            )
            row = cursor.fetchone()
            return int(row["total"]) if row and row["total"] is not None else 0
        except Exception as e:
            print(f"Error counting user session turns: {e}")
            return 0

    async def update_session_status(self, user_id: str, session_id: str, status: str) -> bool:
        """更新会话状态。"""
        try:
            cursor = self.conn.execute(
                """UPDATE sessions
                   SET status = ?, updated_at = ?
                   WHERE user_id = ? AND session_id = ?""",
                (status, datetime.now().isoformat(), user_id, session_id)
            )
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error updating session status: {e}")
            return False

    async def update_session(self,
                             user_id: str,
                             session_id: str,
                             title: Optional[str] = None,
                             summary: Optional[str] = None,
                             preview: Optional[str] = None,
                             status: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """更新会话基础信息。"""
        existing = await self.get_session(user_id, session_id)
        if not existing:
            return None

        now = datetime.now().isoformat()
        next_title = existing.get("title") if title is None else (title.strip() or "新对话")
        next_summary = existing.get("summary") if summary is None else summary
        next_preview = existing.get("preview") if preview is None else preview
        next_status = existing.get("status") if status is None else status

        try:
            self.conn.execute("""
                UPDATE sessions SET
                    title = ?,
                    summary = ?,
                    preview = ?,
                    status = ?,
                    updated_at = ?
                WHERE user_id = ? AND session_id = ?
            """, (
                next_title,
                next_summary,
                next_preview,
                next_status,
                now,
                user_id,
                session_id,
            ))
            self.conn.commit()
            return await self.get_session(user_id, session_id)
        except Exception as e:
            print(f"Error updating session: {e}")
            return None

    async def delete_session(self, user_id: str, session_id: str) -> bool:
        """删除会话及其消息。"""
        try:
            self.conn.execute(
                """DELETE FROM session_messages
                   WHERE user_id = ? AND session_id = ?""",
                (user_id, session_id)
            )
            cursor = self.conn.execute(
                """DELETE FROM sessions
                   WHERE user_id = ? AND session_id = ?""",
                (user_id, session_id)
            )
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error deleting session: {e}")
            return False
