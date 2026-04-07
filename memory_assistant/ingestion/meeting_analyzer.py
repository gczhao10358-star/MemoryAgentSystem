"""
会议记录专用分析器
使用LLM提取结构化信息
"""
import json
import asyncio
import re
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
        self.action_section_keywords = (
            "待办事项", "待办", "行动项", "行动计划", "下一步", "后续工作", "后续安排",
            "todo", "to-do", "action items", "next steps"
        )
        self.non_action_section_keywords = (
            "会议摘要", "总结", "背景", "议题", "讨论", "风险", "问题", "备注", "决策", "结论"
        )
        self.action_verbs = (
            "负责", "完成", "跟进", "安排", "准备", "整理", "推进", "确认", "提交",
            "对接", "同步", "反馈", "评估", "制定", "输出", "补充", "更新", "处理",
            "落实", "协助", "汇总", "提供", "修复", "上线", "排查", "review", "follow up"
        )
        self.deadline_pattern = re.compile(
            r"("
            r"\d{4}[年/-]\d{1,2}[月/-]\d{1,2}日?"
            r"|\d{1,2}月\d{1,2}日"
            r"|今天|今日|明天|后天|今晚|明早|本周[一二三四五六日天]?"
            r"|下周[一二三四五六日天]?"
            r"|周[一二三四五六日天]"
            r"|月底|月初|月中|本月底|下月底"
            r"|会后|尽快|ASAP|asap"
            r")"
        )

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
                rule_action_items = self._extract_rule_based_action_items(chunk)

                all_action_items.extend(chunk_result.get('action_items', []))
                all_action_items.extend(rule_action_items)
                all_preferences.extend(chunk_result.get('preferences', []))
                all_memory_suggestions.extend(chunk_result.get('memory_suggestions', []))

                # 每处理完一块，yield中间结果
                yield {
                    "stage": "chunk_result",
                    "progress": progress,
                    "data": {
                        "chunk_index": i,
                        "action_items_found": len(chunk_result.get('action_items', [])) + len(rule_action_items),
                        "rule_action_items_found": len(rule_action_items),
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
        result = []
        index_by_key = {}
        for item in items:
            normalized = self._normalize_action_item(item)
            if not normalized:
                continue
            key = self._normalize_action_key(normalized.get('content', ''))
            if not key:
                continue
            existing_index = index_by_key.get(key)
            if existing_index is None:
                index_by_key[key] = len(result)
                result.append(normalized)
                continue
            result[existing_index] = self._merge_action_items(result[existing_index], normalized)
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

    def _extract_rule_based_action_items(self, chunk: str) -> List[Dict]:
        """基于显式规则提取待办事项，补强LLM漏召回场景。"""
        items = []
        lines = [line.rstrip() for line in chunk.splitlines()]
        idx = 0

        while idx < len(lines):
            line = lines[idx].strip()
            if not line:
                idx += 1
                continue

            if self._is_action_section_header(line):
                idx += 1
                consumed = 0
                while idx < len(lines) and consumed < 8:
                    candidate = lines[idx].strip()
                    if not candidate:
                        if consumed > 0:
                            break
                        idx += 1
                        continue
                    if self._is_action_section_header(candidate) or self._is_non_action_section_header(candidate):
                        break

                    item = self._build_action_item_from_line(candidate, allow_loose=True)
                    if item:
                        items.append(item)
                        consumed += 1
                    elif consumed > 0 and not self._looks_like_action_sentence(candidate):
                        break
                    idx += 1
                continue

            standalone_item = self._build_action_item_from_line(line, allow_loose=False)
            if standalone_item:
                items.append(standalone_item)
            idx += 1

        return self._deduplicate_action_items(items)

    def _build_action_item_from_line(self, line: str, allow_loose: bool) -> Dict[str, Any]:
        cleaned = self._clean_action_line(line)
        if not cleaned:
            return {}

        if allow_loose:
            if not self._is_explicit_task_line(cleaned):
                return {}
        elif not self._looks_like_action_sentence(cleaned):
            return {}

        assignee = self._extract_assignee(cleaned)
        deadline = self._extract_deadline(cleaned)
        content = self._normalize_action_content(cleaned)

        if not content or content in {"无", "暂无", "没有", "none"}:
            return {}

        should_remind = bool(deadline or assignee or self._looks_like_action_sentence(cleaned))
        return {
            "content": content,
            "assignee": assignee,
            "deadline": deadline,
            "priority": self._infer_priority(cleaned),
            "should_remind": should_remind,
            "suggested_reminder_time": deadline if deadline else ("会后提醒" if should_remind else None),
        }

    def _clean_action_line(self, line: str) -> str:
        line = re.sub(r"^\s*(\d+[.)、]|[-*•●]|[一二三四五六七八九十]+[、.])\s*", "", line.strip())
        line = re.sub(r"^\[\s*[xX]?\s*\]\s*", "", line)
        line = re.sub(r"^\[?\d{1,2}:\d{2}(?::\d{2})?\]?\s*", "", line)
        line = re.sub(r"^(TODO|Todo|todo|待办事项|待办|行动项|下一步|后续工作)\s*[:：-]\s*", "", line)
        line = re.sub(r"\s+", " ", line)
        return line.strip(" \t;；,，。")

    def _normalize_action_content(self, line: str) -> str:
        content = line
        content = re.sub(r"^\[\s*[xX]?\s*\]\s*", "", content)
        content = re.sub(r"^(由)?[@A-Za-z0-9_\u4e00-\u9fa5]{1,12}[：:]\s*", "", content)
        content = re.sub(r"^(请|需要|需|建议)\s*", "", content)
        content = re.sub(r"\s+", " ", content)
        return content.strip(" \t;；,，。")

    def _strip_deadline_clause(self, content: str, deadline: str) -> str:
        if not content or not deadline:
            return content

        normalized_deadline = deadline.strip()
        patterns = [
            rf"[，,、;\s]*截止\s*{re.escape(normalized_deadline)}$",
            rf"[，,、;\s]*于\s*{re.escape(normalized_deadline)}\s*(?:前|之前)?$",
            rf"[，,、;\s]*在\s*{re.escape(normalized_deadline)}\s*(?:前|之前)?$",
            rf"[，,、;\s]*{re.escape(normalized_deadline)}\s*(?:前|之前)?$",
        ]

        cleaned = content.strip()
        for pattern in patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip(" \t;；,，。")
        return cleaned

    def _is_action_section_header(self, line: str) -> bool:
        lowered = line.strip().lower().rstrip(":：")
        return any(keyword in lowered for keyword in self.action_section_keywords) and len(lowered) <= 24

    def _is_non_action_section_header(self, line: str) -> bool:
        normalized = line.strip().rstrip(":：")
        return any(keyword in normalized for keyword in self.non_action_section_keywords) and len(normalized) <= 20

    def _is_explicit_task_line(self, line: str) -> bool:
        if len(line) < 4 or len(line) > 120:
            return False
        if line in {"无", "暂无", "没有", "none"}:
            return False
        return (
            line.startswith("@")
            or "负责" in line
            or "TODO" in line.upper()
            or bool(re.match(r"^[A-Za-z0-9_\u4e00-\u9fa5]{1,20}[：:]", line))
            or self._looks_like_action_sentence(line)
        )

    def _looks_like_action_sentence(self, line: str) -> bool:
        if len(line) < 4 or len(line) > 120:
            return False
        lowered = line.lower()
        has_deadline = bool(self._extract_deadline(line))
        has_action_verb = any(verb in lowered for verb in self.action_verbs)
        has_assignment = bool(re.search(r"(@[\w\u4e00-\u9fa5-]+|由[\w\u4e00-\u9fa5-]{1,12}负责|[\w\u4e00-\u9fa5-]{1,12}负责|^[\w\u4e00-\u9fa5-]{1,20}[：:])", line))
        starts_with_task_prefix = bool(re.match(r"^(请|需要|需|建议|安排|跟进|完成|提交|确认|准备|整理)", line))
        return (has_action_verb and (has_deadline or has_assignment or starts_with_task_prefix)) or line.upper().startswith("TODO")

    def _extract_assignee(self, line: str) -> str:
        patterns = [
            r"@([\w\u4e00-\u9fa5-]{1,20})",
            r"由([\w\u4e00-\u9fa5-]{1,20})负责",
            r"([\w\u4e00-\u9fa5-]{1,20})负责",
            r"^([\w\u4e00-\u9fa5-]{1,20})[：:]",
            r"owner[:：]\s*([\w\u4e00-\u9fa5-]{1,20})",
        ]
        for pattern in patterns:
            match = re.search(pattern, line, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_deadline(self, line: str) -> str:
        deadline_match = re.search(
            r"(截止[^\s，。,；;]{0,16}|[^\s，。,；;]{0,12}(前|之前|内完成)|"
            + self.deadline_pattern.pattern[1:-1]
            + r")",
            line,
            flags=re.IGNORECASE,
        )
        if deadline_match:
            return deadline_match.group(1).strip()
        return ""

    def _infer_priority(self, line: str) -> str:
        lowered = line.lower()
        if any(keyword in lowered for keyword in ("紧急", "立即", "马上", "尽快", "今天", "今日", "asap")):
            return "high"
        if any(keyword in lowered for keyword in ("后续", "有空", "择期")):
            return "low"
        return "medium"

    def _normalize_action_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(item, dict):
            return {}

        content = str(item.get("content", "")).strip()
        if not content:
            return {}

        assignee = str(item.get("assignee", "") or "").strip()
        deadline = str(item.get("deadline", "") or "").strip()
        content = self._normalize_action_content(content)
        content = self._strip_deadline_clause(content, deadline)
        priority = str(item.get("priority", "") or "").strip().lower()
        if priority not in {"high", "medium", "low"}:
            priority = self._infer_priority(content)
        should_remind = item.get("should_remind")
        if should_remind is None:
            should_remind = bool(deadline)

        return {
            "content": content,
            "assignee": assignee,
            "deadline": deadline,
            "priority": priority,
            "should_remind": bool(should_remind),
            "suggested_reminder_time": str(item.get("suggested_reminder_time", "") or "").strip() or (deadline if deadline else None),
        }

    def _normalize_action_key(self, content: str) -> str:
        normalized = re.sub(r"[\s，。,；;：:、\-—_]+", "", content or "")
        return normalized[:60].lower()

    def _merge_action_items(self, base: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(base)
        for field in ("assignee", "deadline", "suggested_reminder_time"):
            if not merged.get(field) and incoming.get(field):
                merged[field] = incoming[field]

        priority_rank = {"high": 3, "medium": 2, "low": 1}
        if priority_rank.get(incoming.get("priority"), 0) > priority_rank.get(merged.get("priority"), 0):
            merged["priority"] = incoming["priority"]

        merged["should_remind"] = bool(base.get("should_remind") or incoming.get("should_remind"))
        if len(incoming.get("content", "")) > len(merged.get("content", "")):
            merged["content"] = incoming["content"]
        return merged
