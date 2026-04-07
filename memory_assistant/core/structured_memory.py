"""
结构化记忆处理器
使用LLM将用户输入转换为结构化记忆数据
"""
import json
import re
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from ..utils.llm_client import LLMClient


class StructuredMemoryExtractor:
    """结构化记忆提取器"""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    async def extract(self, content: str, current_time: Dict[str, Any]) -> Dict[str, Any]:
        """
        从用户输入中提取结构化记忆

        Args:
            content: 用户输入内容
            current_time: 当前时间信息

        Returns:
            结构化记忆数据
        """
        prompt = f"""请将用户的输入转换为结构化的记忆数据。

当前时间：{current_time['date']} {current_time['weekday_name']} {current_time['time']}

用户输入："{content}"

请分析并提取以下信息，以JSON格式返回：
{{
    "type": "事件类型(event/task/fact/reminder)",
    "title": "简短的标题（10字以内）",
    "description": "详细描述",
    "datetime": "具体时间(ISO格式YYYY-MM-DD HH:MM，如果没有具体时间则为YYYY-MM-DD)",
    "location": "地点（如果有）",
    "people": ["相关人员（如果有）"],
    "tags": ["标签1", "标签2"],
    "importance": "重要性(0-1之间的数字)",
    "structured_content": "润色后的完整记忆内容，包含时间、地点、人物、事件"
}}

注意：
1. 时间要转换为具体日期（如"明天"转为{current_time['date']}的第二天）
2. 如果没有某个字段，设为null或空数组
3. structured_content应该是完整、通顺的句子
4. 只返回JSON，不要其他文字
"""

        try:
            response = await self.llm_client.chat([
                {"role": "system", "content": "你是一个记忆结构化助手，专门从用户输入中提取时间、地点、人物、事件等信息。"},
                {"role": "user", "content": prompt}
            ])

            # 提取JSON
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                structured = json.loads(json_match.group())
                return structured
            else:
                return self._fallback_extract(content, current_time)

        except Exception as e:
            print(f"Error extracting structured memory: {e}")
            return self._fallback_extract(content, current_time)

    def _fallback_extract(self, content: str, current_time: Dict[str, Any]) -> Dict[str, Any]:
        """备用提取方法"""
        return {
            "type": "fact",
            "title": content[:10] + "..." if len(content) > 10 else content,
            "description": content,
            "datetime": current_time.get('date'),
            "location": None,
            "people": [],
            "tags": [],
            "importance": 0.5,
            "structured_content": content
        }


class MemoryCRUD:
    """记忆增删改查操作"""

    def __init__(self, memory_storage, embedding_model, llm_client):
        self.storage = memory_storage
        self.embedding_model = embedding_model
        self.extractor = StructuredMemoryExtractor(llm_client)
        self.merge_candidate_window = timedelta(minutes=10)

    async def create(self,
                     user_id: str,
                     content: str,
                     current_time: Dict[str, Any],
                     memory_type: str = "auto",
                     session_id: Optional[str] = None,
                     turn_id: Optional[str] = None,
                     scope: str = "user",
                     status: str = "active",
                     source: str = "user") -> Dict[str, Any]:
        """
        创建新记忆

        Args:
            user_id: 用户ID
            content: 原始内容
            current_time: 当前时间
            memory_type: 记忆类型（auto表示自动识别）

        Returns:
            创建的记忆信息
        """
        # 1. 提取结构化数据
        structured = await self.extractor.extract(content, current_time)

        # 2. 如果指定了类型，覆盖自动识别的类型
        if memory_type != "auto":
            # 转换 meeting -> event (兼容性处理)
            if memory_type == "meeting":
                memory_type = "event"
            structured["type"] = memory_type
        else:
            # 自动识别的类型也可能是 meeting，需要转换
            if structured.get("type") == "meeting":
                structured["type"] = "event"

        duplicate_entry = await self._find_recent_duplicate_entry(
            user_id=user_id,
            structured=structured,
            raw_content=content,
            session_id=session_id,
        )
        if duplicate_entry:
            updated = await self._merge_into_existing_entry(
                entry=duplicate_entry,
                structured=structured,
                raw_content=content,
                importance=structured.get('importance', 0.5),
            )
            return {
                'success': updated,
                'memory_id': duplicate_entry.memory_id,
                'structured': structured
            }

        # 3. 生成嵌入向量
        embedding_text = f"{structured['title']} {structured['description']} {structured.get('structured_content', '')}"
        embedding = await self.embedding_model.encode(embedding_text)

        # 4. 创建记忆条目
        from ..models.memory import MemoryEntry, MemoryType

        entry = MemoryEntry(
            user_id=user_id,
            content=structured['structured_content'],
            memory_type=MemoryType(structured['type']),
            importance=structured.get('importance', 0.5),
            embedding=embedding,
            scope=scope,
            session_id=session_id,
            turn_id=turn_id,
            status=status,
            source=source,
        )

        # 5. 存储元数据
        entry.metadata = {
            'raw_content': content,
            'title': structured.get('title'),
            'datetime': structured.get('datetime'),
            'location': structured.get('location'),
            'people': structured.get('people', []),
            'tags': structured.get('tags', []),
            'structured': True
        }

        # 6. 保存到存储
        success = await self.storage.store(entry)

        return {
            'success': success,
            'memory_id': entry.memory_id,
            'structured': structured
        }

    async def _find_recent_duplicate_entry(self,
                                           user_id: str,
                                           structured: Dict[str, Any],
                                           raw_content: str,
                                           session_id: Optional[str]) -> Optional[Any]:
        """查找近期同主题的事件/任务，命中后改为更新而非重复新增。"""
        memory_type = structured.get("type")
        if memory_type not in {"event", "task", "reminder"}:
            return None

        recent_entries = await self.storage.get_user_memories(user_id, limit=50)
        now = datetime.now()
        incoming_signature = self._build_duplicate_signature(
            structured.get("title"),
            structured.get("structured_content") or structured.get("description"),
            raw_content,
        )
        incoming_datetime = str(structured.get("datetime") or "")

        for entry in recent_entries:
            if entry.memory_type.value != memory_type:
                continue
            if session_id and entry.session_id and entry.session_id != session_id:
                continue
            if now - entry.created_at > self.merge_candidate_window:
                continue

            metadata = entry.metadata or {}
            existing_signature = self._build_duplicate_signature(
                metadata.get("title"),
                entry.content,
                metadata.get("raw_content"),
            )
            if not self._should_merge_signatures(incoming_signature, existing_signature):
                continue

            existing_datetime = str(metadata.get("datetime") or "")
            if (
                incoming_datetime
                and existing_datetime
                and incoming_datetime != existing_datetime
                and not session_id
            ):
                continue

            return entry

        return None

    def _build_duplicate_signature(self,
                                   title: Optional[str],
                                   content: Optional[str],
                                   raw_content: Optional[str]) -> List[str]:
        """提取用于判重的核心主题词，尽量忽略日期和口语壳子。"""
        combined = " ".join([
            str(title or ""),
            str(content or ""),
            str(raw_content or ""),
        ])
        normalized = combined.lower()
        normalized = re.sub(r'\d{4}[年/-]?\d{0,2}[月/-]?\d{0,2}日?', ' ', normalized)
        normalized = re.sub(r'\d{1,2}[:：]\d{2}', ' ', normalized)
        normalized = re.sub(r'(明天|后天|今天|下周|本周|上午|下午|晚上|参加|将|我要|我将|有个|一次|目前|尚未|确定)', ' ', normalized)
        tokens = re.findall(r'[\u4e00-\u9fa5A-Za-z]{2,}', normalized)
        stopwords = {
            "我的", "我们", "你们", "他们", "安排", "事项", "事情", "计划", "记录", "一下",
            "这个", "那个", "进行", "准备", "完成", "相关", "信息"
        }
        filtered = [token for token in tokens if token not in stopwords]
        deduped = []
        for token in filtered:
            if token not in deduped:
                deduped.append(token)
        return deduped[:8]

    def _should_merge_signatures(self, incoming: List[str], existing: List[str]) -> bool:
        """判断两个事件签名是否足够接近。"""
        if not incoming or not existing:
            return False

        incoming_set = set(incoming)
        existing_set = set(existing)
        overlap = incoming_set & existing_set
        if not overlap:
            return False

        overlap_ratio = len(overlap) / max(min(len(incoming_set), len(existing_set)), 1)
        if overlap_ratio >= 0.6:
            return True

        if len(overlap) == 1:
            token = next(iter(overlap))
            if token in {"会议", "开会", "面试", "考试", "聚会", "约会"}:
                return True

        return False

    async def _merge_into_existing_entry(self,
                                         entry,
                                         structured: Dict[str, Any],
                                         raw_content: str,
                                         importance: float) -> bool:
        """将新信息合并到已有记忆中。"""
        metadata = entry.metadata or {}
        merged_people = list(dict.fromkeys((metadata.get('people') or []) + (structured.get('people') or [])))
        merged_tags = list(dict.fromkeys((metadata.get('tags') or []) + (structured.get('tags') or [])))

        new_content = str(structured.get('structured_content') or entry.content).strip() or entry.content
        if len(new_content) < len(entry.content):
            new_content = entry.content

        metadata.update({
            'raw_content': raw_content,
            'title': structured.get('title') or metadata.get('title'),
            'datetime': structured.get('datetime') or metadata.get('datetime'),
            'location': structured.get('location') or metadata.get('location'),
            'people': merged_people,
            'tags': merged_tags,
            'structured': True,
            'merged_at': datetime.now().isoformat(),
        })

        entry.content = new_content
        entry.importance = max(entry.importance, importance)
        entry.updated_at = datetime.now()
        entry.metadata = metadata

        return await self.storage.update_memory(entry)

    async def read(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """读取记忆"""
        entry = await self.storage.get_memory(memory_id)
        if entry:
            return self._entry_to_dict(entry)
        return None

    async def update(self, memory_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新记忆

        Args:
            memory_id: 记忆ID
            updates: 要更新的字段
        """
        entry = await self.storage.get_memory(memory_id)
        if not entry:
            return False

        # 更新内容
        if 'content' in updates:
            entry.content = updates['content']
            # 重新生成嵌入
            embedding = await self.embedding_model.encode(updates['content'])
            entry.embedding = embedding

        # 更新元数据
        if 'metadata' in updates:
            entry.metadata.update(updates['metadata'])

        # 更新重要性
        if 'importance' in updates:
            entry.importance = updates['importance']

        entry.updated_at = datetime.now()

        # 保存
        return await self.storage.update_memory(entry)

    async def delete(self, memory_id: str) -> bool:
        """删除记忆"""
        return await self.storage.delete_memory(memory_id)

    async def search(self, user_id: str, query: str = None,
                    filters: Dict[str, Any] = None, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        搜索记忆

        Args:
            user_id: 用户ID
            query: 查询词
            filters: 过滤条件（如时间范围、类型、标签等）
            top_k: 返回数量
        """
        results = []

        # 1. 如果有查询词，使用向量+文本混合搜索
        if query:
            from ..retrieval.hybrid_retrieval import HybridRetrievalEngine

            retrieval = HybridRetrievalEngine(
                memory_storage=self.storage,
                embedding_model=self.embedding_model
            )

            raw_results = await retrieval.retrieve(
                query=query,
                user_id=user_id,
                top_k=top_k
            )

            for r in raw_results:
                results.append(self._entry_to_dict(r.memory))
        else:
            entries = await self.storage.get_user_memories(user_id, limit=top_k)
            results = [self._entry_to_dict(entry) for entry in entries]

        # 2. 应用过滤器
        if filters:
            filtered_results = []
            for r in results:
                if self._matches_filters(r, filters):
                    filtered_results.append(r)
            results = filtered_results

        return results

    async def search_by_date(self, user_id: str, date_str: str,
                            memory_types: List[str] = None) -> List[Dict[str, Any]]:
        """
        按日期搜索记忆

        Args:
            user_id: 用户ID
            date_str: 日期 (YYYY-MM-DD)
            memory_types: 记忆类型过滤
        """
        # 解析日期
        from datetime import datetime
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d')
            month, day = target_date.month, target_date.day

            # 构建搜索查询
            queries = [
                f"{month}月{day}日",
                f"{month}月{day}号",
                date_str
            ]

            found = {}
            for query in queries:
                results = await self.search(user_id, query, None, 50)
                for r in results:
                    found[r['memory_id']] = r

            # 过滤日期
            filtered = []
            date_patterns = [f"{month}月{day}日", f"{month}月{day}号", f"{month}.{day}", date_str]

            for entry in found.values():
                content = entry.get('content', '')
                metadata = entry.get('metadata', {})

                # 检查类型
                if memory_types and entry.get('memory_type') not in memory_types:
                    continue

                # 检查日期（内容或元数据中）
                has_date = any(p in content for p in date_patterns)
                meta_date = metadata.get('datetime', '')
                if date_str in meta_date:
                    has_date = True

                if has_date:
                    filtered.append(entry)

            return filtered

        except Exception as e:
            print(f"Error searching by date: {e}")
            return []

    async def delete_by_date(self, user_id: str, date_str: str,
                            memory_types: List[str] = None) -> int:
        """按日期删除记忆"""
        entries = await self.search_by_date(user_id, date_str, memory_types)
        deleted = 0
        for entry in entries:
            if await self.delete(entry['memory_id']):
                deleted += 1
        return deleted

    def _entry_to_dict(self, entry) -> Dict[str, Any]:
        """将MemoryEntry转换为字典"""
        return {
            'memory_id': entry.memory_id,
            'user_id': entry.user_id,
            'content': entry.content,
            'memory_type': entry.memory_type.value,
            'scope': entry.scope,
            'session_id': entry.session_id,
            'turn_id': entry.turn_id,
            'status': entry.status,
            'importance': entry.importance,
            'created_at': entry.created_at.isoformat(),
            'updated_at': entry.updated_at.isoformat(),
            'metadata': entry.metadata,
            'tags': entry.tags
        }

    def _matches_filters(self, entry: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """检查条目是否匹配过滤器"""
        metadata = entry.get('metadata', {})

        for key, value in filters.items():
            if key == 'type' and entry.get('memory_type') != value:
                return False
            if key == 'date' and value not in metadata.get('datetime', ''):
                return False
            if key == 'tag' and value not in metadata.get('tags', []):
                return False
            if key == 'location' and metadata.get('location') != value:
                return False
            if key == 'person' and value not in metadata.get('people', []):
                return False

        return True
