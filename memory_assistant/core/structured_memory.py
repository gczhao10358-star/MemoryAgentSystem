"""
结构化记忆处理器 v2.1
- 使用 LLM 将用户输入转换为结构化记忆数据
- LLM 驱动的记忆演化决策（借鉴 Mem0: ADD/UPDATE/DELETE/NONE）
- 重要性评分 + 类别推断
"""
import json
import re
from typing import Dict, Optional, Any, List, Tuple
from datetime import datetime, timedelta
from ..utils.llm_client import LLMClient
from ..models.memory import MemoryCategory, EVERGREEN_CATEGORIES
from .content_filter import ContentFilter


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
        # 预计算相对日期，避免让 LLM 做日期算术
        today_dt = current_time.get('datetime') or datetime.now()
        if isinstance(today_dt, str):
            try:
                today_dt = datetime.fromisoformat(today_dt)
            except Exception:
                today_dt = datetime.now()
        date_today = today_dt.strftime('%Y-%m-%d')
        date_tomorrow = (today_dt + timedelta(days=1)).strftime('%Y-%m-%d')
        date_day_after = (today_dt + timedelta(days=2)).strftime('%Y-%m-%d')
        date_yesterday = (today_dt - timedelta(days=1)).strftime('%Y-%m-%d')

        prompt = f"""请将用户的输入转换为结构化的记忆数据。

当前时间：{date_today} {current_time['weekday_name']} {current_time['time']}

【相对日期对照表（必须严格遵守，不要自行计算）】
- 昨天 = {date_yesterday}
- 今天 = {date_today}
- 明天 = {date_tomorrow}
- 后天 = {date_day_after}

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
    "importance": "重要性(0-1之间的数字，关键身份信息应>=0.8)",
    "category": "信息类别(identity/preference/knowledge/event/temporal/relation)",
    "structured_content": "润色后的完整记忆内容，包含时间、地点、人物、事件"
}}

注意：
1. 时间字段必须严格按照上面的"相对日期对照表"填写
2. structured_content 中如果出现时间，也要写成具体日期（如"{date_tomorrow}"），而不是"明天"
3. category 字段判断标准：
   - identity: 用户的姓名、职业、身份等基本信息
   - preference: 用户的喜好、习惯、偏爱
   - knowledge: 用户的技能、知识、擅长领域
   - event: 具体事件、会议、安排
   - temporal: 临时信息、一次性事务
   - relation: 人际关系信息
4. 如果没有某个字段，设为null或空数组
5. 只返回JSON，不要其他文字
"""

        try:
            response = await self.llm_client.chat([
                {"role": "system", "content": "你是一个记忆结构化助手，专门从用户输入中提取时间、地点、人物、事件等信息。"},
                {"role": "user", "content": prompt}
            ])

            from ..utils.llm_client import is_llm_error_message
            if is_llm_error_message(response):
                print(f"[structured_memory] LLM 调用失败，走 fallback：{response[:120]}")
                return self._fallback_extract(content, current_time)

            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                structured = json.loads(json_match.group())
                # 确保 category 字段存在
                if 'category' not in structured:
                    structured['category'] = ContentFilter.infer_category(content, structured.get('type'))
                return structured
            else:
                return self._fallback_extract(content, current_time)

        except Exception as e:
            print(f"Error extracting structured memory: {e}")
            return self._fallback_extract(content, current_time)

    def _fallback_extract(self, content: str, current_time: Dict[str, Any]) -> Dict[str, Any]:
        """备用提取方法"""
        inferred_category = ContentFilter.infer_category(content)
        return {
            "type": "fact",
            "title": content[:10] + "..." if len(content) > 10 else content,
            "description": content,
            "datetime": current_time.get('date'),
            "location": None,
            "people": [],
            "tags": [],
            "importance": 0.5,
            "category": inferred_category.value,
            "structured_content": content
        }


class MemoryCRUD:
    """记忆增删改查操作 v2.1 — 集成演化决策引擎"""

    def __init__(self, memory_storage, embedding_model, llm_client,
                 evolution_engine=None, vector_store=None):
        self.storage = memory_storage
        self.embedding_model = embedding_model
        self.extractor = StructuredMemoryExtractor(llm_client)
        self.evolution_engine = evolution_engine
        self.vector_store = vector_store
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
        创建新记忆 — v2.1 演化决策版

        处理流程:
        1. 提取结构化数据 (含 category)
        2. 计算重要性分数
        3. 检索 top-N 相似旧记忆
        4. 如果存在演化引擎，调用 LLM 决策 ADD/UPDATE/DELETE/NONE
        5. 否则走原有去重+合并逻辑
        6. 创建/更新记忆条目
        """
        # 1. 提取结构化数据
        structured = await self.extractor.extract(content, current_time)

        # 2. 类型规范化
        if memory_type != "auto":
            if memory_type == "meeting":
                memory_type = "event"
            structured["type"] = memory_type
        else:
            if structured.get("type") == "meeting":
                structured["type"] = "event"

        # 3. 获取/计算 importance 和 category
        importance = structured.get('importance', 0.5)
        if isinstance(importance, str):
            try:
                importance = float(importance)
            except (ValueError, TypeError):
                importance = 0.5
        importance = max(0.0, min(1.0, importance))

        category_str = structured.get('category', 'event')
        try:
            category = MemoryCategory(category_str)
        except (ValueError, KeyError):
            category = ContentFilter.infer_category(content, structured.get('type'))

        # 规则兜底：提高 importance 下限
        rule_importance = ContentFilter.calculate_importance_score(content, structured.get('type'))
        importance = max(importance, rule_importance)

        # 4. 生成嵌入向量
        embedding_text = f"{structured['title']} {structured['description']} {structured.get('structured_content', '')}"
        embedding = await self.embedding_model.encode(embedding_text)

        # 5. 检索相似旧记忆（用于演化决策）
        new_fact = structured.get('structured_content') or content
        similar_memories = await self._retrieve_similar_memories(
            user_id=user_id,
            embedding=embedding,
            new_fact=new_fact,
            top_k=5,
        )

        # 6. LLM 演化决策（如果演化引擎可用且有 LLM 客户端）
        if self.evolution_engine and self.evolution_engine.llm_client and similar_memories:
            print(f"[MemoryCRUD] 触发演化决策: 新事实='{new_fact[:50]}...' 找到 {len(similar_memories)} 条相似记忆")
            operations = await self.evolution_engine.decide_evolution_operation(
                new_fact=new_fact,
                existing_memories=similar_memories,
            )
            result = await self.evolution_engine.apply_evolution_operations(
                operations=operations,
                user_id=user_id,
                new_fact=new_fact,
                embedding=embedding,
                category=category,
                importance=importance,
            )
            print(f"[MemoryCRUD] 演化决策结果: ADD={result['added']} UPDATE={result['updated']} DELETE={result['deleted']} NONE={result['none']}")
            return {
                'success': True,
                'evolved': True,
                'operations': result,
                'memory_id': None,
                'structured': structured,
            }

        # 7. 降级：原有去重逻辑
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
                importance=importance,
            )
            return {
                'success': updated,
                'memory_id': duplicate_entry.memory_id,
                'structured': structured,
            }

        # 8. 创建记忆条目
        from ..models.memory import MemoryEntry, MemoryType

        entry = MemoryEntry(
            user_id=user_id,
            content=structured['structured_content'],
            memory_type=MemoryType(structured['type']),
            importance=importance,
            embedding=embedding,
            scope=scope,
            session_id=session_id,
            turn_id=turn_id,
            status=status,
            source=source,
            category=category,
        )

        # 元数据
        entry.metadata = {
            'raw_content': content,
            'title': structured.get('title'),
            'datetime': structured.get('datetime'),
            'location': structured.get('location'),
            'people': structured.get('people', []),
            'tags': structured.get('tags', []),
            'structured': True,
            'category': category.value,
        }

        # 保存
        success = await self.storage.store(entry)

        return {
            'success': success,
            'memory_id': entry.memory_id,
            'structured': structured,
        }

    async def _retrieve_similar_memories(
        self,
        user_id: str,
        embedding: List[float],
        new_fact: str,
        top_k: int = 5,
    ) -> List:
        """检索与新事实语义相似的旧记忆"""
        if self.vector_store:
            try:
                results = await self.vector_store.search(embedding, user_id=user_id, k=top_k)
                return [r for r in results if hasattr(r, 'memory_id')]
            except Exception as e:
                print(f"[MemoryCRUD] 向量检索相似记忆失败: {e}")

        # 降级：从 storage 获取最近记忆
        try:
            recent = await self.storage.get_user_memories(user_id, limit=50)
            return recent[:top_k]
        except Exception:
            return []


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
