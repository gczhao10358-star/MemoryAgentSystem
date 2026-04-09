"""
会议记录专用分析器
使用LLM提取结构化信息
"""
import json
import asyncio
from typing import AsyncGenerator, Dict, Any, List
from datetime import datetime

from .models import MeetingAnalysisResult, ProcessingStatus


class MeetingAnalyzer:
    """
    会议记录分析器

    分两个阶段：
    1. 全局分析：提取摘要、会议信息、关键决策
    2. 详细分析：逐块提取待办、偏好等
    """

    def __init__(self, llm_client):
        self.llm_client = llm_client

    async def analyze_stream(
        self,
        chunks: List[str],
        user_id: str,
        context: Dict[str, Any] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式分析会议记录

        Yields:
            {
                "stage": str,           # 当前阶段
                "progress": float,      # 进度 0-1
                "data": Any,            # 阶段数据
                "status": str,          # "processing" | "completed" | "error"
            }
        """
        start_time = datetime.now()
        total_chunks = len(chunks)
        context = context or {}

        try:
            # ===== 阶段1: 全局分析 =====
            yield {
                "stage": "global_analysis",
                "progress": 0.0,
                "data": {"message": "正在分析会议整体结构..."},
                "status": "processing"
            }

            # 取前几块和最后一块做全局分析
            global_text = self._prepare_global_text(chunks)
            global_result = await self._analyze_global(global_text, context)

            yield {
                "stage": "global_analysis",
                "progress": 0.2,
                "data": global_result,
                "status": "completed"
            }

            # ===== 阶段2: 逐块详细分析 =====
            all_action_items = []
            all_preferences = []
            all_memory_suggestions = []

            for i, chunk in enumerate(chunks):
                progress = 0.2 + (0.6 * (i + 1) / total_chunks)

                yield {
                    "stage": "chunk_analysis",
                    "progress": progress,
                    "data": {
                        "current_chunk": i + 1,
                        "total_chunks": total_chunks,
                        "message": f"正在分析第 {i+1}/{total_chunks} 部分..."
                    },
                    "status": "processing"
                }

                chunk_result = await self._analyze_chunk(chunk, global_result, user_id)

                all_action_items.extend(chunk_result.get('action_items', []))
                all_preferences.extend(chunk_result.get('preferences', []))
                all_memory_suggestions.extend(chunk_result.get('memory_suggestions', []))

                # 每处理完一块，yield中间结果
                yield {
                    "stage": "chunk_result",
                    "progress": progress,
                    "data": {
                        "chunk_index": i,
                        "action_items_found": len(chunk_result.get('action_items', [])),
                        "preferences_found": len(chunk_result.get('preferences', [])),
                    },
                    "status": "processing"
                }

            # ===== 阶段3: 整合去重 =====
            yield {
                "stage": "consolidation",
                "progress": 0.85,
                "data": {"message": "正在整合分析结果..."},
                "status": "processing"
            }

            # 去重和合并
            final_action_items = self._deduplicate_action_items(all_action_items)
            final_preferences = self._deduplicate_preferences(all_preferences)
            final_memories = self._consolidate_memories(all_memory_suggestions)

            # ===== 阶段4: 生成最终结果 =====
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

            result = MeetingAnalysisResult(
                summary=global_result.get('summary', ''),
                meeting_title=global_result.get('meeting_title'),
                meeting_date=global_result.get('meeting_date'),
                meeting_location=global_result.get('location'),
                participants=global_result.get('participants', []),
                key_decisions=global_result.get('key_decisions', []),
                action_items=final_action_items,
                discussed_topics=global_result.get('topics', []),
                user_preferences=final_preferences,
                memory_suggestions=final_memories,
                confidence_score=global_result.get('confidence', 0.8),
                processing_time_ms=processing_time
            )

            yield {
                "stage": "completed",
                "progress": 1.0,
                "data": result.to_dict(),
                "status": "completed"
            }

        except Exception as e:
            yield {
                "stage": "error",
                "progress": 0,
                "data": {"error": str(e)},
                "status": "error"
            }

    async def _analyze_global(self, text: str, context: Dict) -> Dict:
        """全局分析"""
        import asyncio

        prompt = f"""请分析以下会议记录，提取整体信息。

【上下文】
用户ID: {context.get('user_id', 'unknown')}
上传时间: {context.get('upload_time', 'unknown')}

【会议记录内容】
{text[:4000]}

请提取以下信息，以JSON格式返回：
{{
    "summary": "会议整体摘要（100字以内）",
    "meeting_title": "会议标题（如有）",
    "meeting_date": "会议日期（YYYY-MM-DD格式，如有）",
    "location": "会议地点（如有）",
    "participants": ["参会人员1", "参会人员2"],
    "key_decisions": ["决策1", "决策2"],
    "topics": ["讨论主题1", "讨论主题2"],
    "confidence": 0.95
}}

注意：
1. 如果某项信息不存在，设为null或空数组
2. summary必须是完整、通顺的中文句子
3. 只返回JSON，不要其他文字
"""

        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = await asyncio.wait_for(
                    self.llm_client.chat([
                        {"role": "system", "content": "你是专业的会议记录分析助手，擅长提取关键信息。"},
                        {"role": "user", "content": prompt}
                    ]),
                    timeout=30.0
                )
                return self._extract_json(response)
            except asyncio.TimeoutError:
                print(f"[MeetingAnalyzer] Global analysis timeout (attempt {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    return {
                        "summary": "会议记录分析超时",
                        "meeting_title": None,
                        "meeting_date": None,
                        "location": None,
                        "participants": [],
                        "key_decisions": [],
                        "topics": [],
                        "confidence": 0.0
                    }
            except Exception as e:
                print(f"[MeetingAnalyzer] Global analysis error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    return {
                        "summary": "会议记录分析失败",
                        "meeting_title": None,
                        "meeting_date": None,
                        "location": None,
                        "participants": [],
                        "key_decisions": [],
                        "topics": [],
                        "confidence": 0.0
                    }

        return {
            "summary": "会议记录分析失败",
            "meeting_title": None,
            "meeting_date": None,
            "location": None,
            "participants": [],
            "key_decisions": [],
            "topics": [],
            "confidence": 0.0
        }

    async def _analyze_chunk(self, chunk: str, global_info: Dict, user_id: str) -> Dict:
        """分析单个切片"""
        import asyncio

        prompt = f"""请分析以下会议记录片段，提取具体信息。

【会议背景】
会议主题: {global_info.get('meeting_title', '未知')}
参会人员: {', '.join(global_info.get('participants', []))}

【当前片段内容】
{chunk}

请提取以下信息，以JSON格式返回：
{{
    "action_items": [
        {{
            "content": "待办事项具体内容",
            "assignee": "负责人（如有）",
            "deadline": "截止日期描述（如有）",
            "priority": "high/medium/low",
            "should_remind": true/false,
            "suggested_reminder_time": "建议提醒时间描述"
        }}
    ],
    "preferences": [
        {{
            "type": "time/location/work_style/other",
            "content": "用户偏好描述",
            "confidence": 0.8
        }}
    ],
    "memory_suggestions": [
        {{
            "content": "建议存储的记忆内容",
            "memory_type": "fact/event/task",
            "importance": 0.7,
            "reason": "存储理由"
        }}
    ]
}}

注意：
1. 只提取明确提及的信息，不要推测
2. should_remind为true时，表示这是需要提醒的任务
3. 只返回JSON，不要其他文字
"""

        max_retries = 2
        for attempt in range(max_retries):
            try:
                # 使用超时，避免无限等待
                response = await asyncio.wait_for(
                    self.llm_client.chat([
                        {"role": "system", "content": "你是专业的信息提取助手，擅长从会议记录中提取待办事项和用户偏好。"},
                        {"role": "user", "content": prompt}
                    ]),
                    timeout=30.0  # 30秒超时
                )
                return self._extract_json(response)
            except asyncio.TimeoutError:
                print(f"[MeetingAnalyzer] Chunk analysis timeout (attempt {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    return {"action_items": [], "preferences": [], "memory_suggestions": []}
            except Exception as e:
                print(f"[MeetingAnalyzer] Chunk analysis error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    return {"action_items": [], "preferences": [], "memory_suggestions": []}

        return {"action_items": [], "preferences": [], "memory_suggestions": []}

    def _prepare_global_text(self, chunks: List[str]) -> str:
        """准备全局分析的文本"""
        if len(chunks) <= 3:
            return "\n\n".join(chunks)

        # 取前2块和最后1块
        return "\n\n".join(chunks[:2] + ["..."] + chunks[-1:])

    def _extract_json(self, text: str) -> Dict:
        """从文本中提取JSON"""
        import re
        try:
            # 尝试直接解析
            return json.loads(text)
        except:
            # 尝试提取JSON块
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
            # 返回空结果
            return {}

    def _deduplicate_action_items(self, items: List[Dict]) -> List[Dict]:
        """去重待办事项"""
        seen = set()
        result = []
        for item in items:
            key = item.get('content', '').strip()[:50]  # 取前50字作为key
            if key and key not in seen:
                seen.add(key)
                result.append(item)
        return result

    def _deduplicate_preferences(self, prefs: List[Dict]) -> List[Dict]:
        """去重偏好"""
        seen = set()
        result = []
        for pref in prefs:
            key = pref.get('content', '').strip()[:30]
            if key and key not in seen:
                seen.add(key)
                result.append(pref)
        return result

    def _consolidate_memories(self, memories: List[Dict]) -> List[Dict]:
        """整合记忆建议"""
        # 按重要性排序
        sorted_mems = sorted(memories, key=lambda x: x.get('importance', 0.5), reverse=True)
        # 去重并限制数量
        seen = set()
        result = []
        for mem in sorted_mems[:20]:  # 最多20条
            key = mem.get('content', '').strip()[:50]
            if key and key not in seen:
                seen.add(key)
                result.append(mem)
        return result
