"""
统一记忆存储接口
整合向量存储和元数据存储
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from .vector_store import FaissVectorStore
from .metadata_store import SQLiteMetadataStore
from ..models.memory import MemoryEntry


class MemoryStorage:
    """统一记忆存储类"""

    def __init__(self, vector_store: FaissVectorStore,
                 metadata_store: SQLiteMetadataStore):
        self.vector_store = vector_store
        self.metadata_store = metadata_store

    async def initialize(self):
        """初始化存储"""
        await self.vector_store.initialize()
        await self.metadata_store.initialize()

    async def store(self, entry: MemoryEntry) -> bool:
        """存储记忆（同时保存向量和元数据）"""
        success = True

        # 1. 保存到向量存储（如果包含向量）
        if entry.embedding:
            vector_success = await self.vector_store.add(
                entry.memory_id,
                entry.embedding,
                {
                    'user_id': entry.user_id,
                    'memory_type': entry.memory_type.value,
                    'created_at': entry.created_at.isoformat(),
                }
            )
            if not vector_success:
                print(f"Warning: Failed to store vector for memory {entry.memory_id}")
                success = False

        # 2. 保存到元数据存储
        metadata_success = await self.metadata_store.save_memory(entry)
        if not metadata_success:
            print(f"Error: Failed to store metadata for memory {entry.memory_id}")
            success = False

        return success

    async def retrieve_by_vector(self, query_vector: List[float], user_id: str,
                                 top_k: int = 10) -> List[Dict[str, Any]]:
        """通过向量搜索检索记忆"""
        # 在向量存储中搜索
        vector_results = await self.vector_store.search(
            query_vector,
            top_k=top_k,
            filter_dict={'user_id': user_id}
        )

        # 获取完整的记忆信息
        results = []
        for vr in vector_results:
            entry = await self.metadata_store.get_memory(vr['id'])
            if entry:
                results.append({
                    'entry': entry,
                    'vector_score': vr['score'],
                })

        return results

    async def retrieve_by_content(self, user_id: str, keyword: str,
                                  limit: int = 20) -> List[MemoryEntry]:
        """通过内容关键词检索记忆"""
        return await self.metadata_store.search_by_content(user_id, keyword, limit)

    async def get_memory(self, memory_id: str) -> Optional[MemoryEntry]:
        """获取单个记忆"""
        return await self.metadata_store.get_memory(memory_id)

    async def update_memory(self, entry: MemoryEntry) -> bool:
        """更新记忆"""
        return await self.metadata_store.update_memory(entry)

    async def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        # 标记删除向量
        await self.vector_store.delete(memory_id)
        # 删除元数据
        return await self.metadata_store.delete_memory(memory_id)

    async def delete_memories_by_date(self, user_id: str, date_str: str,
                                       memory_types: List[str] = None) -> int:
        """
        按日期删除用户的记忆
        注意：这个函数需要先搜索相关记忆，建议在agent层调用retrieve后再删除

        Args:
            user_id: 用户ID
            date_str: 日期字符串 (YYYY-MM-DD)
            memory_types: 要删除的记忆类型列表

        Returns:
            删除的记忆数量
        """
        from datetime import datetime

        try:
            # 解析目标日期
            target_date = datetime.strptime(date_str, '%Y-%m-%d')

            # 构建多种日期格式用于匹配
            month = target_date.month
            day = target_date.day
            date_patterns = [
                f"{month}月{day}日",
                f"{month}月{day}号",
                f"{month}.{day}",
                f"{month}-{day}",
                date_str,  # YYYY-MM-DD
                date_str.replace('-', '/'),  # YYYY/MM/DD
            ]

            # 方法1: 通过内容搜索找到包含日期的记忆
            found_entries = {}

            # 搜索不同格式的日期
            content_entries = await self.metadata_store.search_by_content(
                user_id, f"{month}月{day}日", limit=100
            )
            for entry in content_entries:
                found_entries[entry.memory_id] = entry

            content_entries = await self.metadata_store.search_by_content(
                user_id, f"{month}月{day}号", limit=100
            )
            for entry in content_entries:
                found_entries[entry.memory_id] = entry

            # 方法2: 获取用户所有记忆并过滤
            all_entries = await self.metadata_store.get_memories_by_user(user_id, limit=10000)
            for entry in all_entries:
                content = entry.content
                for pattern in date_patterns:
                    if pattern in content:
                        found_entries[entry.memory_id] = entry
                        break

            # 过滤需要删除的记忆
            to_delete = []
            for entry in found_entries.values():
                # 检查类型
                if memory_types and entry.memory_type.value not in memory_types:
                    continue

                # 再次确认内容中包含日期
                content = entry.content
                for pattern in date_patterns:
                    if pattern in content:
                        to_delete.append(entry)
                        break

            # 删除这些记忆
            deleted_count = 0
            for entry in to_delete:
                success = await self.delete_memory(entry.memory_id)
                if success:
                    deleted_count += 1
                    print(f"[删除记忆] {entry.memory_id}: {entry.content[:50]}...")

            return deleted_count

        except Exception as e:
            print(f"Error in delete_memories_by_date: {e}")
            import traceback
            traceback.print_exc()
            return 0

    async def get_user_memories(self, user_id: str, limit: int = 100) -> List[MemoryEntry]:
        """获取用户的所有记忆"""
        return await self.metadata_store.get_memories_by_user(user_id, limit)

    async def retrieve_by_time_range(self, user_id: str,
                                     start_time: datetime,
                                     end_time: datetime,
                                     limit: int = 100) -> List[MemoryEntry]:
        """按时间范围检索记忆"""
        return await self.metadata_store.search_by_time_range(
            user_id, start_time, end_time, limit
        )

    async def search_memories(self, user_id: str,
                             keyword: Optional[str] = None,
                             start_time: Optional[datetime] = None,
                             end_time: Optional[datetime] = None,
                             memory_type: Optional[str] = None,
                             limit: int = 50) -> List[MemoryEntry]:
        """综合搜索记忆"""
        return await self.metadata_store.search_memories(
            user_id, keyword, start_time, end_time, memory_type, limit
        )

    async def save(self):
        """保存向量索引"""
        await self.vector_store.save()

    async def close(self):
        """关闭存储"""
        await self.vector_store.save()
        await self.metadata_store.close()
