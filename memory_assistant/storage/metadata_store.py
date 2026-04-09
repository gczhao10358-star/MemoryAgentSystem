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
                source_id TEXT,
                vector_id TEXT,
                metadata TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # 创建用户表
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                profile_data TEXT
            )
        """)

        # 创建索引
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_user_time
            ON memories(user_id, created_at)
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

    async def save_memory(self, entry: MemoryEntry) -> bool:
        """保存记忆"""
        try:
            cursor = self.conn.execute("""
                INSERT INTO memories (
                    memory_id, user_id, content, memory_type, state,
                    created_at, updated_at, last_accessed,
                    confidence, importance, weight, access_count,
                    tags, related_entities, source, source_id, vector_id, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.memory_id,
                entry.user_id,
                entry.content,
                entry.memory_type.value,
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
                entry.source_id,
                entry.vector_id,
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
        )
        entry.state = MemoryState(row['state'])
        entry.confidence = row['confidence']
        entry.importance = row['importance']
        entry.weight = row['weight']
        entry.access_count = row['access_count']
        entry.source = row['source']
        entry.source_id = row['source_id']
        entry.vector_id = row['vector_id']

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
