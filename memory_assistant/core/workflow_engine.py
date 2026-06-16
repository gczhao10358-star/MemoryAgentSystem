"""
Agent工作流引擎
管理用户请求的完整处理流程
"""
import json
import re
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum

from .content_filter import ContentFilter, get_memory_type


class WorkflowStep:
    """工作流步骤"""
    def __init__(self, name: str, func: Callable, condition: Optional[Callable] = None):
        self.name = name
        self.func = func
        self.condition = condition

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行步骤"""
        if self.condition and not self.condition(context):
            return context
        return await self.func(context)


class WorkflowContext:
    """工作流上下文"""
    def __init__(self,
                 user_id: str,
                 message: str,
                 current_time: Dict[str, Any],
                 session_id: Optional[str] = None,
                 turn_id: Optional[str] = None):
        self.user_id = user_id
        self.message = message
        self.current_time = current_time
        self.session_id = session_id
        self.turn_id = turn_id
        self.data = {}  # 中间数据存储
        self.result = None
        self.error = None
        self.needs_user_confirm = False
        self.confirm_message = None

    def set(self, key: str, value: Any):
        """设置数据"""
        self.data[key] = value

    def get(self, key: str, default=None):
        """获取数据"""
        return self.data.get(key, default)


class IntentType(Enum):
    """意图类型"""
    CHAT = "chat"  # 普通聊天
    STORE = "store"  # 存储记忆
    RETRIEVE = "retrieve"  # 检索记忆
    DELETE = "delete"  # 删除记忆
    EXECUTE_TASK = "execute_task"  # 执行任务/设置提醒


class MemoryWorkflowEngine:
    """记忆工作流引擎"""

    def __init__(self, llm_client, memory_crud, datetime_tools, memory_service=None, profile_manager=None):
        self.llm_client = llm_client
        self.memory_crud = memory_crud
        self.datetime_tools = datetime_tools
        self.memory_service = memory_service
        self.profile_manager = profile_manager

        # 注册工作流
        self.workflows = {
            IntentType.CHAT: self._create_chat_workflow(),
            IntentType.STORE: self._create_store_workflow(),
            IntentType.RETRIEVE: self._create_retrieve_workflow(),
            IntentType.DELETE: self._create_delete_workflow(),
            IntentType.EXECUTE_TASK: self._create_execute_task_workflow(),
        }

        # 任务调度器（可选）
        self.task_scheduler = None

    async def process(self,
                      user_id: str,
                      message: str,
                      current_time: Dict[str, Any],
                      session_id: Optional[str] = None,
                      turn_id: Optional[str] = None) -> WorkflowContext:
        """
        处理用户请求

        Returns:
            WorkflowContext: 包含处理结果或需要用户确认的信息
        """
        # 1. 识别意图（已移除硬编码"快速回复"，所有消息都走正常工作流，避免误抢答）
        intent, thought, extracted_content = await self._recognize_intent(message)

        # 2. 创建上下文
        context = WorkflowContext(user_id, message, current_time, session_id=session_id, turn_id=turn_id)
        context.set('intent', intent)
        context.set('thought', thought)
        context.set('extracted_content', extracted_content)

        # 3. 执行对应工作流（让所有意图都执行工作流，确保CHAT也走完整流程生成回答）
        workflow = self.workflows.get(intent)
        if workflow:
            for step in workflow:
                try:
                    context = await step.execute(context)
                    if context.needs_user_confirm:
                        return context
                except Exception as e:
                    context.error = str(e)
                    return context
        else:
            # 如果没有对应工作流，使用extracted_content作为fallback
            if extracted_content:
                context.result = extracted_content

        return context

    async def _recognize_intent(self, message: str) -> tuple[IntentType, str, str]:
        """
        识别用户意图 - 高置信度规则前置，未命中再调 LLM。

        Returns:
            (intent_type, thought, extracted_content)
        """
        import re
        import json

        message_clean = message.strip()
        message_lower = message_clean.lower()

        # ---------- 规则前置（高置信度场景跳过 LLM，省一次调用）----------

        # 1. 删除类
        if re.match(r'^(删除|移除|清空|去掉|删掉|忘掉|忘记)', message_clean):
            print(f"[意图识别|规则] DELETE: '{message[:30]}...'")
            return IntentType.DELETE, "规则匹配：删除记忆", message

        # 2. 提醒类（必须同时含时间词或时间短语）
        reminder_kw = ['提醒我', '记得提醒', '叫我', '到点叫', '到时叫', '设个提醒',
                       '设置提醒', '设个闹钟', '定个闹钟', '记得叫']
        has_reminder_kw = any(kw in message_clean for kw in reminder_kw)
        if has_reminder_kw:
            print(f"[意图识别|规则] EXECUTE_TASK: '{message[:30]}...'")
            return IntentType.EXECUTE_TASK, "规则匹配：包含提醒/闹钟关键词", message

        # 3. 闲聊/问候/能力问询（不需要走 LLM 意图识别）
        chitchat_patterns = [
            r'^(你好|您好|hi|hello|嗨|哈喽)[\s!！。.?？]*$',
            r'^(在吗|在么|在不在)[?？]?$',
            r'^(谢谢|多谢|感谢|thanks|thank\s*you)[\s!！。.]*$',
            r'^(再见|拜拜|bye|goodbye)[\s!！。.]*$',
            r'^(好的|ok|okay|嗯|嗯嗯|好|行)[\s!！。.]*$',
        ]
        for p in chitchat_patterns:
            if re.match(p, message_lower):
                print(f"[意图识别|规则] CHAT(闲聊): '{message[:30]}...'")
                return IntentType.CHAT, "规则匹配：闲聊/问候", message

        # 4. 明确的"询问/查询"短句（强信号 → RETRIEVE）
        retrieve_patterns = [
            r'(我叫|我的名字|我是谁|我喜欢|我讨厌|我擅长|我的爱好|我的工作)',
            r'(我哪天|我什么时候|我.*?(几月|几号|几点))',
            r'(我.*?有什么(安排|计划|事情|任务))',
            r'(回忆一下|回想一下|查一下|查询一下|搜索一下).*?(我|之前)',
        ]
        for p in retrieve_patterns:
            if re.search(p, message_clean) and ('?' in message_clean or '？' in message_clean
                                                 or re.search(r'(吗|呢|啥|什么|哪|几)', message_clean)):
                print(f"[意图识别|规则] RETRIEVE: '{message[:30]}...'")
                return IntentType.RETRIEVE, "规则匹配：明确询问个人信息", message

        # 其他场景由大模型判断
        system_prompt = """# Role
你是智忆助理(MemoryMate)的意图识别专家。分析用户输入，判断应该执行以下哪种操作：

## 可选分支

1. **memory_storage** (存储记忆/日程安排)：用户告知个人信息、计划安排、事件记录等需要记住的内容
   - 例："我3月15日要去上海"、"我喜欢喝浓缩咖啡"、"明天中午12点去吃麦当劳"
   - 特征：陈述一个事实或计划，**没有明确说"提醒"**

2. **memory_retrieval** (检索记忆)：用户询问之前记住的信息
   - 例："我哪天去上海？"、"我喜欢喝什么？"、"我明天有什么安排？"

3. **execute_task** (设置提醒)：用户**明确要求**到时间提醒他做某事
   - 例："明天下午3点提醒我开会"、"18点04分提醒我去吃饭"、"记得叫我起床"
   - **关键特征**：必须包含"提醒"、"叫我"、"记得叫我"、"闹钟"等明确关键词
   - 反例（不是提醒）："明天中午12点去吃麦当劳"（这只是陈述计划，没有要求提醒）

4. **direct_chat** (直接回答)：闲聊、问候、常识问答等不需要记忆操作的情况
   - 例："你好"、"今天天气怎么样"、"帮我写一首诗"

## 重要判断标准（关键区分）

**是否是 execute_task（设置提醒）？**
- ✅ 必须同时满足：
  1. 有具体时间
  2. **明确说了** "提醒"、"叫我"、"记得叫我"、"闹钟"等关键词
- ❌ 如果只是说"明天中午12点去吃麦当劳" → 这是 **memory_storage**（存储日程）
- ❌ 如果只是说"3月15日我要去上海" → 这是 **memory_storage**（存储计划）

**简单判断法**：
- 用户说"记得/提醒/叫我做某事" → execute_task
- 用户只说"我什么时候要做某事" → memory_storage

## 输出格式（必须是JSON）
{
  "intent": "memory_storage" | "memory_retrieval" | "execute_task" | "direct_chat",
  "thought": "判断理由",
  "extracted_content": "提取的关键信息（存储/提醒内容） 或 直接回答的内容"
}"""

        user_prompt = f"# User Input\n{message}"

        try:
            response = await self.llm_client.chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ])

            # 解析JSON响应
            try:
                # 尝试提取JSON
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    result = json.loads(response)

                intent_str = result.get('intent', 'direct_chat').lower()
                thought = result.get('thought', '未提供理由')
                extracted_content = result.get('extracted_content', message)

                print(f"[意图识别] 用户: '{message[:30]}...' -> {intent_str} | {thought}")

                # 映射到IntentType
                if 'storage' in intent_str or 'store' in intent_str:
                    return IntentType.STORE, thought, extracted_content
                elif 'retrieval' in intent_str or 'retrieve' in intent_str:
                    return IntentType.RETRIEVE, thought, extracted_content
                elif 'execute' in intent_str or 'task' in intent_str:
                    return IntentType.EXECUTE_TASK, thought, extracted_content
                else:
                    return IntentType.CHAT, thought, extracted_content

            except json.JSONDecodeError as e:
                print(f"[意图识别] JSON解析失败: {e}, 原始响应: {response}")
                # 降级到规则匹配
                return self._fallback_intent_recognition(message)

        except Exception as e:
            print(f"[意图识别错误] {e}, 使用fallback规则")
            return self._fallback_intent_recognition(message)

    def _fallback_intent_recognition(self, message: str) -> tuple[IntentType, str, str]:
        """意图识别降级方案"""
        message_lower = message.lower()
        if any(kw in message for kw in ['删除', '取消', '清空']):
            return IntentType.DELETE, "规则匹配：删除记忆", message
        elif any(kw in message for kw in ['提醒我', '记得提醒我', '叫我', '设置提醒']):
            return IntentType.EXECUTE_TASK, "规则匹配：设置提醒/任务", message
        elif any(kw in message for kw in ['我明天', '我后天', '我最近', '我有什么', '我的']):
            return IntentType.RETRIEVE, "规则匹配：检索记忆", message
        elif any(kw in message for kw in ['记录', '安排', '记得', '计划', '喜欢', '讨厌', '过敏', '擅长']):
            return IntentType.STORE, "规则匹配：存储记忆", message
        else:
            return IntentType.CHAT, "规则匹配：直接对话", message

    def _create_chat_workflow(self) -> List[WorkflowStep]:
        """创建工作流：普通聊天"""
        return [
            WorkflowStep("generate_response", self._step_chat_generate),
        ]

    def _create_store_workflow(self) -> List[WorkflowStep]:
        """创建工作流：存储记忆"""
        return [
            WorkflowStep("extract_time", self._step_extract_time),
            WorkflowStep("polish_content", self._step_polish_content),
            WorkflowStep("check_conflict", self._step_check_conflict),
            WorkflowStep("confirm_or_store", self._step_confirm_or_store),
        ]

    def _create_retrieve_workflow(self) -> List[WorkflowStep]:
        """创建工作流：检索记忆"""
        return [
            WorkflowStep("calculate_date_range", self._step_calculate_date_range),
            WorkflowStep("search_memories", self._step_search_memories),
            WorkflowStep("rerank_memories", self._step_rerank_memories),
            WorkflowStep("generate_answer", self._step_generate_answer),
        ]

    def _create_delete_workflow(self) -> List[WorkflowStep]:
        """创建工作流：删除记忆"""
        return [
            WorkflowStep("extract_date", self._step_extract_delete_date),
            WorkflowStep("find_memories", self._step_find_memories_to_delete),
            WorkflowStep("confirm_delete", self._step_confirm_delete),
        ]

    # ========== 聊天工作流步骤 ==========

    async def _step_chat_generate(self, ctx: WorkflowContext) -> WorkflowContext:
        """生成普通回复 — 同时注入用户画像、相关记忆与会话历史，避免\"无记忆感\"。"""
        agent = getattr(self, 'agent_ref', None)

        system_prompt: Optional[str] = None
        retrieval_results: list = []
        pinned_memories: list = []

        # 1) 如果 agent 在线，复用它的高级能力（画像、pinned、检索）
        if agent is not None:
            try:
                profile = await agent.profile_manager.get_profile(ctx.user_id)

                # 检索 top_k 条相关记忆（含语义 + BM25 + RRF）
                try:
                    retrieval_results = await agent.retrieval_engine.search(
                        query=ctx.message,
                        user_id=ctx.user_id,
                        top_k=5,
                    )
                except Exception as e:
                    print(f"[chat_generate] retrieval 失败: {e}")
                    retrieval_results = []

                # 拉取用户置顶/核心信息记忆
                try:
                    pinned_memories = await agent.memory_service.get_pinned_memories(ctx.user_id, limit=5)
                except Exception:
                    pinned_memories = []

                system_prompt = await agent._build_system_prompt(
                    profile=profile,
                    retrieval_results=retrieval_results,
                    user_message=ctx.message,
                    pinned_memories=pinned_memories,
                )
            except Exception as e:
                print(f"[chat_generate] 构建增强 system prompt 失败，回退基础版: {e}")
                system_prompt = None

        # 2) 兜底基础 system prompt（agent 不在或上面失败时）
        if not system_prompt:
            today = ctx.current_time.get('date', '')
            weekday = ctx.current_time.get('weekday_name', '')
            system_prompt = (
                "你是智忆助理(MemoryMate)，具备持久记忆和会话上下文能力。\n"
                f"今天是 {today} {weekday}。\n"
                "当用户问你是谁时，介绍自己是智忆助理。\n"
                "请用友好、自然的语气回复。"
            )

        # 3) 拼会话历史（最近 N 轮），让多轮上下文连贯
        history_messages: list = []
        if agent is not None and ctx.session_id:
            try:
                ctx_msgs = agent.memory_service.get_session_context(
                    user_id=ctx.user_id,
                    session_id=ctx.session_id,
                    turns=8,
                )
                for m in ctx_msgs[-8:]:
                    role = m.get('role') or 'user'
                    content = m.get('content') or ''
                    if role in ('user', 'assistant') and content:
                        history_messages.append({'role': role, 'content': content})
            except Exception as e:
                print(f"[chat_generate] 获取会话上下文失败: {e}")

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history_messages)
        messages.append({"role": "user", "content": ctx.message})

        try:
            response = await self.llm_client.chat(messages)
            from ..utils.llm_client import is_llm_error_message
            if is_llm_error_message(response):
                ctx.result = response  # 错误消息原样回显给用户，但不会入库（已有过滤）
            else:
                ctx.result = response
        except Exception as e:
            print(f"Error in chat_generate: {e}")
            ctx.result = f"抱歉，回复生成时出现问题：{e}"

        return ctx

    # ========== 存储工作流步骤 ==========

    async def _step_extract_time(self, ctx: WorkflowContext) -> WorkflowContext:
        """提取并计算具体时间，优先使用本地解析器保证相对日期稳定。"""
        current_date = ctx.current_time['date']  # YYYY-MM-DD
        current_weekday = ctx.current_time['weekday_name']

        # 使用提取的内容（如果没有则使用原始消息）
        content = ctx.get('extracted_content') or ctx.message

        # 先用本地解析器，避免“明天/后天/今天下午3点”这类表达被模型漂移
        try:
            from ..utils.time_parser import time_parser

            base_time = datetime.fromisoformat(ctx.current_time['iso'])
            parsed_time = time_parser.parse(content, base_time)
            if parsed_time:
                has_explicit_time = bool(re.search(
                    r'(\d{1,2}[:：]\d{2}|\d{1,2}\s*[点时](半|整|\d{1,2}分?)?|早上|早晨|上午|中午|下午|傍晚|晚上|夜间)',
                    content
                ))
                date_description = time_parser.format_time(parsed_time, 'human') if has_explicit_time else parsed_time.strftime('%Y年%m月%d日')
                time_info = {
                    'event_date': parsed_time.strftime('%Y-%m-%d'),
                    'event_time': parsed_time.strftime('%H:%M') if has_explicit_time else None,
                    'date_description': date_description,
                    'time_confidence': 'high'
                }
                ctx.set('time_info', time_info)
                ctx.set('event_date', parsed_time.replace(hour=0, minute=0, second=0, microsecond=0))
                return ctx
        except Exception as e:
            print(f"Error parsing time locally: {e}")

        # 预计算相对日期，避免 LLM 自行加减天数引起漂移
        _today_dt = datetime.fromisoformat(ctx.current_time['iso'])
        _date_yesterday = (_today_dt - timedelta(days=1)).strftime('%Y-%m-%d')
        _date_tomorrow = (_today_dt + timedelta(days=1)).strftime('%Y-%m-%d')
        _date_day_after = (_today_dt + timedelta(days=2)).strftime('%Y-%m-%d')

        # 预计算本周/下周各星期的具体日期
        _cur_wd = _today_dt.weekday()  # 周一=0
        _this_monday = _today_dt - timedelta(days=_cur_wd)
        _wd_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        _this_week_lines = "\n".join(
            f"- 本周{_wd_names[i]} = {(_this_monday + timedelta(days=i)).strftime('%Y-%m-%d')}"
            for i in range(7)
        )
        _next_week_lines = "\n".join(
            f"- 下周{_wd_names[i]} = {(_this_monday + timedelta(days=7 + i)).strftime('%Y-%m-%d')}"
            for i in range(7)
        )

        prompt = f"""当前日期：{current_date} ({current_weekday})

【相对日期对照表（必须严格遵守，不要自行计算）】
- 昨天 = {_date_yesterday}
- 今天 = {current_date}
- 明天 = {_date_tomorrow}
- 后天 = {_date_day_after}

【本周对照表】
{_this_week_lines}

【下周对照表】
{_next_week_lines}

用户输入："{content}"

请提取事件的时间信息，返回JSON格式：
{{
    "event_date": "YYYY-MM-DD格式的日期",
    "event_time": "HH:MM格式的时间或null",
    "date_description": "自然语言描述的日期和时间",
    "time_confidence": "high/medium/low"
}}

注意：
1. event_date 必须严格按照上面的对照表填写，不要自行加减天数。
2. 用户写"周X/星期X/礼拜X"且未带"下周/下下周"前缀时：
   - 若该日尚未过去（含今天），按【本周对照表】取；
   - 若该日已经过去，按【下周对照表】取。
3. **小时必须忠实**：用户写"17点"就是 17:00；写"23点"就是 23:00；不要把 24 小时制的数字再 +12。
4. 用户写"下午3点半"才转换为 "15:30"；用户写"下午17点"也只能是 17:00（不要变 14:00、29:00）。
5. event_time 必须是 HH:MM 24 小时制；用户没说具体时刻就填 null。
6. 节假日名（如"端午节/中秋节/春节"）只是事件主题，不是时间，不要因为节日名调整 event_date 或 event_time。
7. 只返回JSON，不要其他文字。"""

        try:
            response = await self.llm_client.chat([
                {"role": "system", "content": "你是时间解析助手，只返回JSON。"},
                {"role": "user", "content": prompt}
            ])

            # 提取JSON
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                time_info = json.loads(json_match.group())
                ctx.set('time_info', time_info)

                # 验证日期
                try:
                    event_date = datetime.strptime(time_info['event_date'], '%Y-%m-%d')
                    ctx.set('event_date', event_date)
                except:
                    ctx.set('event_date', None)

        except Exception as e:
            print(f"Error extracting time: {e}")
            ctx.set('time_info', None)
            ctx.set('event_date', None)

        return ctx

    async def _step_polish_content(self, ctx: WorkflowContext) -> WorkflowContext:
        """润色内容，总结成完整句子（必须忠实于原文，不可改写时间或新增信息）"""
        time_info = ctx.get('time_info')

        prompt_parts = ["请把下面这条用户消息整理为一句完整通顺的中文记忆。"]

        if time_info:
            date_desc = time_info.get('date_description', '')
            event_time = time_info.get('event_time', '')
            event_date = time_info.get('event_date', '')
            if event_date:
                prompt_parts.append(f"已解析日期：{event_date}（请直接采用，不要自行换算）")
            if date_desc:
                prompt_parts.append(f"日期描述：{date_desc}")
            if event_time:
                prompt_parts.append(f"已解析时间：{event_time}（24小时制，请直接采用）")

        # 使用提取的内容（如果没有则使用原始消息）
        content = ctx.get('extracted_content') or ctx.message
        prompt_parts.append(f"\n原始内容：{content}")
        prompt_parts.append("\n严格要求：")
        prompt_parts.append("1. 必须忠实于原始内容，保留全部细节（事件、地点、人物、节日名、原因/状态等）。")
        prompt_parts.append("2. **严禁改写或推断时间数字**：用户写17点就是17:00，写23点就是23:00；如果上面提供了\"已解析时间\"，必须原样使用。")
        prompt_parts.append("3. **严禁新增用户没有说过的信息**：不要补\"庆祝/为了/由于/因为\"等因果，不要添加\"打算/准备\"等推测语气词。")
        prompt_parts.append("4. 节日名（如端午节、中秋节、春节）只能照抄，不可当作事件目的或原因。")
        prompt_parts.append("5. 仅做语序整理和语法补全，不要替换近义词，不要丢失任何用户提到的关键词。")
        prompt_parts.append("6. 输出一句话；如确需多个分句，最多两个短句，用中文逗号连接。")
        prompt_parts.append("\n只返回润色后的句子本身，不要任何前后缀、解释或引号。")

        try:
            response = await self.llm_client.chat([
                {"role": "system", "content": "你是忠实的记忆整理助手：只做语序整理，不改写任何事实细节。"},
                {"role": "user", "content": "\n".join(prompt_parts)}
            ])

            polished = response.strip()
            # 如果润色调用本身失败，回退到原始消息，避免把错误字符串作为记忆内容入库
            from ..utils.llm_client import is_llm_error_message
            if is_llm_error_message(polished):
                print(f"[polish] LLM 调用失败，回退使用原始内容；error={polished[:120]}")
                polished = content
                ctx.set('llm_polish_failed', True)
            ctx.set('polished_content', polished)

            # 提取更多元数据
            ctx.set('structured_data', {
                'original': content,
                'polished': polished,
                'time_info': time_info,
                'extracted_at': ctx.current_time['iso']
            })

        except Exception as e:
            print(f"Error polishing content: {e}")
            ctx.set('polished_content', ctx.message)
            ctx.set('llm_polish_failed', True)

        return ctx

    async def _step_check_conflict(self, ctx: WorkflowContext) -> WorkflowContext:
        """检查时间冲突"""
        event_date = ctx.get('event_date')
        if not event_date:
            return ctx

        # 搜索该日期的所有事件
        date_str = event_date.strftime('%Y-%m-%d')
        if self.memory_service:
            existing_memories = await self.memory_service.search_memories_by_date(
                user_id=ctx.user_id,
                date_str=date_str,
                memory_types=['event', 'task', 'reminder']
            )
        else:
            existing_memories = await self.memory_crud.search_by_date(
                user_id=ctx.user_id,
                date_str=date_str,
                memory_types=['event', 'task', 'reminder']
            )

        if existing_memories:
            # 检查时间重叠
            time_info = ctx.get('time_info', {})
            new_time = time_info.get('event_time')

            # 如果新任务没有指定时间，不进行冲突检测
            if not new_time:
                return ctx

            conflicts = []
            for mem in existing_memories:
                mem_time = mem.get('metadata', {}).get('datetime', '')
                if mem_time:
                    # 检查时间是否重叠（简单实现：同一小时视为冲突）
                    # 更精确的实现应该比较时间段
                    conflicts.append({
                        'content': mem.get('content', ''),
                        'time': mem_time
                    })

            if conflicts:
                ctx.set('conflicts', conflicts)
                ctx.needs_user_confirm = True

                # 构建确认消息
                conflict_list = "\n".join([f"- {c['time']}: {c['content'][:30]}" for c in conflicts])
                ctx.confirm_message = f"该时间段已有以下安排：\n{conflict_list}\n\n是否仍要添加新的安排？"

        return ctx

    async def _step_confirm_or_store(self, ctx: WorkflowContext) -> WorkflowContext:
        """确认或存储"""
        if ctx.needs_user_confirm:
            return ctx

        # 直接存储
        polished = ctx.get('polished_content', ctx.message)
        time_info = ctx.get('time_info', {})

        # 判断是否包含时间信息
        has_time = time_info and time_info.get('event_date')

        # 判断是否包含个人属性关键词（无时间的信息）
        # 使用提取的内容（如果没有则使用原始消息）
        content_for_check = ctx.get('extracted_content') or ctx.message
        is_personal_attribute = self._is_personal_attribute(content_for_check)
        classified_type = get_memory_type(content_for_check)

        # ★ 入库查重：对于无时间的 fact（如\"我叫山田\"），如果已经存在相似度 >= 0.85 的记忆
        #   就不要重复落库，避免反复说同一件事产生 N 条相同 fact。
        if not has_time and is_personal_attribute and self.memory_service is not None:
            try:
                existing = await self.memory_service.search_memories(
                    user_id=ctx.user_id,
                    query=content_for_check,
                    top_k=3,
                    use_personalization=False,
                )
                dup = self._find_duplicate(existing, polished)
                if dup is not None:
                    dup_id = dup.get('memory_id')
                    print(f"[去重] 命中相似记忆 {dup_id}，跳过新增")
                    # 标记为已记（提升 access_count 通过 retrieval_engine 在搜索时已自动做）
                    ctx.result = f"已记录（与既有记忆相似，已合并到原记忆）：{polished}"
                    return ctx
            except Exception as e:
                print(f"[去重] 查重失败，按新增处理: {e}")

        if is_personal_attribute and not has_time:
            target_memory_type = 'fact'
        elif classified_type in {'event', 'task', 'reminder'}:
            target_memory_type = classified_type
        else:
            target_memory_type = 'auto'

        if target_memory_type == 'fact':
            # 存储为个人属性（FACT类型，高重要性）
            if self.memory_service:
                result = await self.memory_service.store_memory(
                    user_id=ctx.user_id,
                    content=polished,
                    current_time=ctx.current_time,
                    memory_type=target_memory_type,
                    session_id=ctx.session_id,
                    turn_id=ctx.turn_id,
                    scope='user',
                    status='active',
                    source='user',
                )
            else:
                result = await self.memory_crud.create(
                    user_id=ctx.user_id,
                    content=polished,
                    current_time=ctx.current_time,
                    memory_type=target_memory_type
                )
            # 同时更新用户画像
            await self._update_profile_with_attribute(ctx.user_id, content_for_check)
        else:
            # 存储为普通记忆（优先使用启发式类型，兜底再交给 auto）
            if self.memory_service:
                result = await self.memory_service.store_memory(
                    user_id=ctx.user_id,
                    content=polished,
                    current_time=ctx.current_time,
                    memory_type=target_memory_type,
                    session_id=ctx.session_id,
                    turn_id=ctx.turn_id,
                    scope='user',
                    status='active',
                    source='user',
                )
            else:
                result = await self.memory_crud.create(
                    user_id=ctx.user_id,
                    content=polished,
                    current_time=ctx.current_time,
                    memory_type=target_memory_type
                )

        if result['success']:
            structured = result['structured']
            ctx.result = f"已记录：{structured.get('structured_content', polished)}"
        else:
            ctx.result = "记录失败，请重试。"

        return ctx

    def _is_personal_attribute(self, message: str) -> bool:
        """判断是否为个人属性（无时间的个人特征）"""
        return ContentFilter.is_personal_attribute(message)

    @staticmethod
    def _find_duplicate(existing: list, new_content: str, threshold: float = 0.85):
        """在已有记忆中寻找与 new_content 相似度 >= threshold 的条目；
        - 如果检索结果带有 score >= threshold 直接采纳；
        - 否则用最朴素的字符 Jaccard 相似度兜底。
        """
        if not existing or not new_content:
            return None

        # 先看检索打分
        for mem in existing:
            score = mem.get('score') or mem.get('hybrid_score') or mem.get('similarity')
            if score is not None:
                try:
                    if float(score) >= threshold:
                        return mem
                except Exception:
                    pass

        # 退化为字符级 Jaccard
        def _norm(s: str) -> set:
            s = re.sub(r'[\s\W_]+', '', (s or '').lower())
            return set(s)

        new_set = _norm(new_content)
        if not new_set:
            return None

        for mem in existing:
            mem_set = _norm(mem.get('content', ''))
            if not mem_set:
                continue
            inter = len(new_set & mem_set)
            union = len(new_set | mem_set)
            if union > 0 and inter / union >= threshold:
                return mem
        return None

    async def _update_profile_with_attribute(self, user_id: str, message: str):
        """从个人属性消息中更新用户画像"""
        try:
            # 提取偏好或属性
            if not self.profile_manager:
                return

            profile_manager = self.profile_manager
            profile = await profile_manager.get_profile(user_id)

            # 识别话题偏好
            import re
            if re.search(r'(?:喜欢|爱好|感兴趣|热衷于)', message):
                # 提取喜欢的事物作为话题
                topic_match = re.search(r'喜欢.*?([\u4e00-\u9fa5]{2,10})', message)
                if topic_match:
                    topic = topic_match.group(1)
                    profile.add_or_update_topic(topic, 0.8)
                    await profile_manager.save_profile(profile)
        except Exception as e:
            print(f"[更新画像] 失败: {e}")

    # ========== 检索工作流步骤 ==========

    async def _step_calculate_date_range(self, ctx: WorkflowContext) -> WorkflowContext:
        """计算检索的日期范围。仅在用户提到时间词时才计算；纯实体查询直接跳过。"""
        current_date = ctx.current_time['date']

        # 使用提取的内容（如果没有则使用原始消息）
        content = ctx.get('extracted_content') or ctx.message

        # 快速预判：用户消息里是否带任何时间词
        has_temporal = ContentFilter.has_temporal_reference(content)
        if not has_temporal:
            # 纯实体/属性类查询（如"我叫什么名字""我喜欢什么"），不走日期遍历
            ctx.set('date_range', {'date_description': '无日期约束'})
            return ctx

        # 预计算相对日期
        _today_dt = datetime.fromisoformat(ctx.current_time['iso'])
        _date_yesterday = (_today_dt - timedelta(days=1)).strftime('%Y-%m-%d')
        _date_tomorrow = (_today_dt + timedelta(days=1)).strftime('%Y-%m-%d')
        _date_day_after = (_today_dt + timedelta(days=2)).strftime('%Y-%m-%d')
        _date_7d_ago = (_today_dt - timedelta(days=7)).strftime('%Y-%m-%d')

        prompt = f"""当前日期：{current_date}

【相对日期对照表（必须严格遵守，不要自行计算）】
- 昨天 = {_date_yesterday}
- 今天 = {current_date}
- 明天 = {_date_tomorrow}
- 后天 = {_date_day_after}
- 7天前 = {_date_7d_ago}

用户查询："{content}"

请分析用户要查询的日期范围，返回JSON格式：
{{
    "start_date": "YYYY-MM-DD格式的开始日期，如果用户没问日期则填 null",
    "end_date": "YYYY-MM-DD格式的结束日期，如果用户没问日期则填 null",
    "date_description": "自然语言描述，如'最近一周'、'3月份'等"
}}

注意：
1. **如果用户的问题与时间/日期无关（如"我叫什么名字"、"我喜欢什么"），start_date/end_date 都填 null。**
2. start_date / end_date 必须严格按照上面的"相对日期对照表"填写。
3. "最近" = 7天前 到 今天，即 {_date_7d_ago} 到 {current_date}
4. "这周" = 本周一到周日
5. "下周" = 下周一到周日
6. "3月15日" = 仅3月15日当天
7. "15号" = 本月15号当天

只返回JSON，不要其他文字。"""

        try:
            response = await self.llm_client.chat([
                {"role": "system", "content": "你是日期解析助手，只返回JSON。"},
                {"role": "user", "content": prompt}
            ])

            from ..utils.llm_client import is_llm_error_message
            if is_llm_error_message(response):
                # LLM 调用失败 -> 不强加日期范围，让语义检索去匹配
                ctx.set('date_range', {'date_description': '无日期约束'})
                return ctx

            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                date_range = json.loads(json_match.group())
                ctx.set('date_range', date_range)

                # 验证日期，null/空则跳过日期遍历
                start_raw = date_range.get('start_date')
                end_raw = date_range.get('end_date')
                if start_raw and end_raw and start_raw != 'null' and end_raw != 'null':
                    try:
                        start = datetime.strptime(start_raw, '%Y-%m-%d')
                        end = datetime.strptime(end_raw, '%Y-%m-%d')
                        ctx.set('start_date', start)
                        ctx.set('end_date', end)
                    except Exception:
                        pass

        except Exception as e:
            print(f"Error calculating date range: {e}")
            ctx.set('date_range', {'date_description': '无日期约束'})

        return ctx

    async def _step_search_memories(self, ctx: WorkflowContext) -> WorkflowContext:
        """搜索记忆。同时覆盖 fact / event / task / reminder 等所有非 chat 类型。"""
        start_date = ctx.get('start_date')
        end_date = ctx.get('end_date')

        all_memories = []
        # 关注的记忆类型：把 fact 也加进来，不要漏掉"我叫XX""我喜欢XX"这类身份/属性记忆
        memory_types_for_date = ['event', 'task', 'reminder', 'fact']

        # 1. 仅当用户问了具体时间/日期时才按日期遍历
        if start_date and end_date:
            current = start_date
            while current <= end_date:
                if self.memory_service:
                    memories = await self.memory_service.search_memories_by_date(
                        user_id=ctx.user_id,
                        date_str=current.strftime('%Y-%m-%d'),
                        memory_types=memory_types_for_date
                    )
                else:
                    memories = await self.memory_crud.search_by_date(
                        user_id=ctx.user_id,
                        date_str=current.strftime('%Y-%m-%d'),
                        memory_types=memory_types_for_date
                    )
                all_memories.extend(memories)
                current += timedelta(days=1)

        # 2. 语义/关键字检索（任何情况下都做，是身份类问题的主要召回路径）
        search_query = ctx.get('extracted_content') or ctx.message
        if self.memory_service:
            semantic_results = await self.memory_service.search_memories(
                user_id=ctx.user_id,
                query=search_query,
                top_k=10,
                use_personalization=False,
            )
        else:
            semantic_results = await self.memory_crud.search(
                user_id=ctx.user_id,
                query=search_query,
                top_k=10
            )

        # 合并去重
        seen_ids = {m['memory_id'] for m in all_memories}
        for mem in semantic_results:
            if mem['memory_id'] not in seen_ids:
                all_memories.append(mem)

        # 3. 兜底：如果以上都没召回，直接拉用户最近的非 chat 记忆（让 LLM 自己挑）
        if not all_memories and self.memory_service:
            try:
                recent_entries = await self.memory_crud.storage.metadata_store.get_memories_by_user(
                    user_id=ctx.user_id,
                    limit=20,
                    offset=0,
                )
                for entry in recent_entries:
                    mtype = entry.memory_type.value if hasattr(entry.memory_type, 'value') else str(entry.memory_type)
                    if mtype == 'chat':
                        continue
                    all_memories.append({
                        'memory_id': entry.memory_id,
                        'content': entry.content,
                        'memory_type': mtype,
                        'metadata': entry.metadata or {},
                        'importance': entry.importance,
                        'created_at': entry.created_at.isoformat() if entry.created_at else '',
                    })
            except Exception as e:
                print(f"[retrieve fallback] 拉取最近记忆失败: {e}")

        ctx.set('memories', all_memories)
        return ctx

    async def _step_rerank_memories(self, ctx: WorkflowContext) -> WorkflowContext:
        """LLM 轻量 rerank：从 top_k 候选中挑出最相关的 5 条，提升 _step_generate_answer 的命中率。

        - 候选 <= 3 条时直接跳过（rerank 没意义）
        - LLM 失败时不影响主流程，直接保留原序
        """
        memories = ctx.get('memories', [])
        if len(memories) <= 3:
            return ctx

        # 太多候选时只取前 12 条参与 rerank，避免 prompt 过长
        candidates = memories[:12]

        query = ctx.get('extracted_content') or ctx.message
        lines = []
        for i, mem in enumerate(candidates):
            content = (mem.get('content') or '').replace('\n', ' ')[:120]
            mtype = mem.get('memory_type', '')
            lines.append(f"[{i}] ({mtype}) {content}")

        prompt = (
            "你是相关性打分助手。下面是若干候选记忆和一个用户查询。\n"
            "请输出最多 5 个、按相关性从高到低排序的候选索引。\n\n"
            f"用户查询：\"{query}\"\n\n"
            "候选记忆：\n" + "\n".join(lines) + "\n\n"
            "只返回 JSON 数组，例如 [3,0,5]，不要任何额外解释。"
        )

        try:
            response = await self.llm_client.chat([
                {"role": "system", "content": "你是相关性排序助手，只返回 JSON 数组。"},
                {"role": "user", "content": prompt},
            ])
            from ..utils.llm_client import is_llm_error_message
            if is_llm_error_message(response):
                return ctx

            json_match = re.search(r'\[[\s\d,，\s]*\]', response)
            if not json_match:
                return ctx

            raw = json_match.group().replace('，', ',')
            indices = json.loads(raw)
            if not isinstance(indices, list):
                return ctx

            ranked = []
            seen = set()
            for idx in indices:
                if isinstance(idx, int) and 0 <= idx < len(candidates) and idx not in seen:
                    ranked.append(candidates[idx])
                    seen.add(idx)
                if len(ranked) >= 5:
                    break

            # 把没参与排序的剩余记忆追加在后面，保留全量信息
            tail = [m for i, m in enumerate(candidates) if i not in seen]
            tail += memories[12:]

            if ranked:
                print(f"[rerank] 重排前 {len(memories)} 条 -> 前 {len(ranked)} 条精选")
                ctx.set('memories', ranked + tail)
        except Exception as e:
            print(f"[rerank] 失败: {e}")

        return ctx

    async def _step_generate_answer(self, ctx: WorkflowContext) -> WorkflowContext:
        """生成回答"""
        memories = ctx.get('memories', [])
        date_range = ctx.get('date_range', {})
        query_content = ctx.get('extracted_content') or ctx.message

        # 拉一下用户画像，拼到 prompt 里，便于回答"我叫什么/我喜欢什么"等身份类问题
        profile_summary = ""
        if self.profile_manager:
            try:
                profile = await self.profile_manager.get_profile(ctx.user_id)
                parts = []
                if getattr(profile, 'name', None):
                    parts.append(f"用户名字：{profile.name}")
                if getattr(profile, 'username', None) and profile.username != getattr(profile, 'name', None):
                    parts.append(f"用户名：{profile.username}")
                top_topics = getattr(profile, 'topic_preferences', None) or []
                try:
                    top_topics = sorted(top_topics, key=lambda x: getattr(x, 'weight', 0), reverse=True)[:5]
                    if top_topics:
                        parts.append("感兴趣话题：" + ", ".join(getattr(t, 'topic', str(t)) for t in top_topics))
                except Exception:
                    pass
                expertise = getattr(profile, 'expertise_areas', None) or []
                if expertise:
                    parts.append("专业领域：" + ", ".join(getattr(e, 'domain', str(e)) for e in expertise[:3]))
                if parts:
                    profile_summary = "\n".join(parts)
            except Exception as e:
                print(f"[generate_answer] 拉取画像失败: {e}")

        # 构造记忆段
        if memories:
            memory_texts = []
            for i, mem in enumerate(memories[:10], 1):
                metadata = mem.get('metadata', {})
                datetime_str = metadata.get('datetime', '') or mem.get('created_at', '')
                content = mem.get('content', '')
                memory_texts.append(f"{i}. [{datetime_str}] {content}")
            memories_str = "\n".join(memory_texts)
        else:
            memories_str = "（暂无相关记忆）"

        # 如果用户画像和记忆都没有任何线索，就让 LLM 老实承认不知道（而不是说"没找到安排"）
        has_any_context = bool(memories) or bool(profile_summary)

        date_desc = date_range.get('date_description', '')

        prompt_parts = [
            "请根据下面提供的「用户画像」和「相关记忆」回答用户的问题。",
            "",
            f"用户问题：\"{query_content}\"",
        ]
        if date_desc and date_desc != '无日期约束':
            prompt_parts.append(f"查询范围：{date_desc}")
        if profile_summary:
            prompt_parts.append("\n用户画像：\n" + profile_summary)
        prompt_parts.append("\n相关记忆：\n" + memories_str)
        prompt_parts.append("""
回答要求：
1. 直接、自然地回答用户的问题，语气友好。
2. 如果是身份/属性类问题（如"我叫什么"），优先用「用户画像」与含名字/喜好等信息的记忆作答。
3. 如果是日程/事件类问题，按时间顺序整理「相关记忆」中匹配的内容。
4. 如果以上信息确实回答不了用户的问题，就坦率地说"暂时没有这条信息"，不要编造，也不要说"该时间段没有安排"这种与问题无关的话。""")

        prompt = "\n".join(prompt_parts)

        try:
            response = await self.llm_client.chat([
                {"role": "system", "content": "你是智忆助理，根据用户画像与历史记忆回答用户的问题。"},
                {"role": "user", "content": prompt}
            ])
            from ..utils.llm_client import is_llm_error_message
            if is_llm_error_message(response):
                # LLM 故障时，用画像 + 记忆做最朴素的兜底，避免回那句误导性的"没找到安排"
                if profile_summary or memories:
                    ctx.result = "（智能回复暂不可用，以下是你已记录的相关信息）\n" + (profile_summary or "") + ("\n" + memories_str if memories else "")
                else:
                    ctx.result = "暂时没有找到相关信息。"
            else:
                ctx.result = response.strip()
        except Exception as e:
            print(f"Error generating answer: {e}")
            if has_any_context:
                ctx.result = "（生成回答时出错，但根据你的记录）\n" + (profile_summary or memories_str)
            else:
                ctx.result = "暂时没有找到相关信息。"

        return ctx

    # ========== 删除工作流步骤 ==========

    async def _step_extract_delete_date(self, ctx: WorkflowContext) -> WorkflowContext:
        """提取要删除的日期"""
        from ..core.content_filter import ContentFilter
        # 使用提取的内容
        content = ctx.get('extracted_content') or ctx.message
        date_str = ContentFilter.extract_delete_date(content)

        if date_str:
            ctx.set('delete_date', date_str)
        else:
            ctx.error = "无法识别要删除的日期"

        return ctx

    async def _step_find_memories_to_delete(self, ctx: WorkflowContext) -> WorkflowContext:
        """查找要删除的记忆"""
        date_str = ctx.get('delete_date')
        if not date_str:
            return ctx

        if self.memory_service:
            memories = await self.memory_service.search_memories_by_date(
                user_id=ctx.user_id,
                date_str=date_str,
                memory_types=['event', 'task', 'reminder']
            )
        else:
            memories = await self.memory_crud.search_by_date(
                user_id=ctx.user_id,
                date_str=date_str,
                memory_types=['event', 'task', 'reminder']
            )

        ctx.set('memories_to_delete', memories)

        if not memories:
            date_display = date_str.replace('-', '年', 1).replace('-', '月') + '日'
            ctx.result = f"没有找到 {date_display} 的安排。"

        return ctx

    async def _step_confirm_delete(self, ctx: WorkflowContext) -> WorkflowContext:
        """确认或执行删除"""
        memories = ctx.get('memories_to_delete', [])

        if not memories:
            return ctx

        # 如果有多个记忆，需要确认
        if len(memories) > 1:
            ctx.needs_user_confirm = True
            memory_list = "\n".join([f"- {m.get('content', '')[:40]}" for m in memories[:5]])
            ctx.confirm_message = f"找到以下 {len(memories)} 条安排：\n{memory_list}\n\n确认全部删除吗？"
            ctx.set('pending_delete_count', len(memories))
        else:
            # 只有一条，直接删除
            for mem in memories:
                if self.memory_service:
                    await self.memory_service.delete_memory(mem['memory_id'])
                else:
                    await self.memory_crud.delete(mem['memory_id'])

            date_str = ctx.get('delete_date', '')
            date_display = date_str.replace('-', '年', 1).replace('-', '月') + '日'
            ctx.result = f"已删除 {date_display} 的 {len(memories)} 条安排。"

        return ctx

    def _create_execute_task_workflow(self) -> List[WorkflowStep]:
        """创建工作流：执行任务/设置提醒"""
        return [
            WorkflowStep("parse_task_time", self._step_parse_task_time),
            WorkflowStep("extract_task_content", self._step_extract_task_content),
            WorkflowStep("create_reminder", self._step_create_reminder),
        ]

    async def _step_parse_task_time(self, ctx: WorkflowContext) -> WorkflowContext:
        """解析任务时间 - 先用本地解析器，失败再用大模型"""
        from datetime import datetime
        from ..utils.time_parser import time_parser

        # 使用提取的内容（如果没有则使用原始消息）
        content = ctx.get('extracted_content') or ctx.message

        # 首先尝试用本地 time_parser 解析（更可靠）
        try:
            base_time = datetime.now()
            parsed_time = time_parser.parse(content, base_time)

            if parsed_time:
                print(f"[任务工作流] 本地解析时间成功: {parsed_time}")
                time_info = {
                    'event_date': parsed_time.strftime('%Y-%m-%d'),
                    'event_time': parsed_time.strftime('%H:%M'),
                    'date_description': time_parser.format_time(parsed_time, 'human'),
                    'time_description': parsed_time.strftime('%H:%M'),
                    'is_recurring': False,
                    'recurring_pattern': None
                }
                ctx.set('task_time_info', time_info)
                ctx.set('reminder_time', parsed_time)
                return ctx
        except Exception as e:
            print(f"[任务工作流] 本地解析时间失败: {e}")

        # 本地解析失败，使用大模型兜底
        current_date = ctx.current_time['date']
        current_weekday = ctx.current_time['weekday_name']

        # 预计算相对日期
        _today_dt = datetime.fromisoformat(ctx.current_time['iso'])
        _date_tomorrow = (_today_dt + timedelta(days=1)).strftime('%Y-%m-%d')
        _date_day_after = (_today_dt + timedelta(days=2)).strftime('%Y-%m-%d')

        prompt = f"""当前日期：{current_date} ({current_weekday})

【相对日期对照表（必须严格遵守，不要自行计算）】
- 今天 = {current_date}
- 明天 = {_date_tomorrow}
- 后天 = {_date_day_after}

用户输入："{content}"

请提取提醒/任务的时间信息，返回JSON格式：
{{
    "event_date": "YYYY-MM-DD格式的日期",
    "event_time": "HH:MM格式的时间（必须包含分钟）",
    "date_description": "自然语言描述的日期和时间",
    "time_description": "自然语言描述的时间",
    "is_recurring": false,
    "recurring_pattern": null
}}

注意：
1. event_date 必须严格按照上面的"相对日期对照表"填写。
2. "2分钟后" = 当前时间 + 2分钟，event_date = 今天, event_time = 当前时间+2分钟
3. "1小时后" = 当前时间 + 1小时，event_date = 今天, event_time = 当前时间+1小时
4. "每天早上/每天下午" = is_recurring: true, recurring_pattern: "daily"
5. "每周X" = is_recurring: true, recurring_pattern: "weekly"
6. **重要**：event_time 必须精确到分钟！如 "16:15"、"09:30"
7. 如果用户说"16:15"，event_time = "16:15"
8. 如果用户说"3点半"，event_time = "15:30"
9. 如果用户说"3点整"，event_time = "15:00"
10. 只返回JSON，不要其他文字"""

        try:
            response = await self.llm_client.chat([
                {"role": "system", "content": "你是时间解析助手，只返回JSON。"},
                {"role": "user", "content": prompt}
            ])

            # 提取JSON
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                time_info = json.loads(json_match.group())
                ctx.set('task_time_info', time_info)

                # 构建datetime对象
                try:
                    date_str = time_info['event_date']
                    time_str = time_info.get('event_time', '09:00')
                    reminder_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                    ctx.set('reminder_time', reminder_time)
                    print(f"[任务工作流] 大模型解析时间成功: {reminder_time}")
                except:
                    ctx.set('reminder_time', None)

        except Exception as e:
            print(f"[任务工作流] 大模型解析时间错误: {e}")
            ctx.set('task_time_info', None)
            ctx.set('reminder_time', None)

        return ctx

    async def _step_extract_task_content(self, ctx: WorkflowContext) -> WorkflowContext:
        """提取任务内容"""
        content = ctx.get('extracted_content') or ctx.message
        time_info = ctx.get('task_time_info', {})

        prompt = f"""用户输入："{content}"
时间信息：{time_info}

请提取用户需要被提醒的具体事项（去除时间描述），返回JSON格式：
{{
    "task_title": "简短的任务标题（10字以内）",
    "task_content": "完整的提醒内容",
    "is_recurring": false,
    "recurring_description": null
}}

注意：
1. task_content 应该是完整的提醒语句，如"记得看论文"
2. 如果用户说"明天下午3点提醒我开会"，task_content应该是"开会"
3. 如果是周期性任务，is_recurring设为true
4. 只返回JSON，不要其他文字"""

        try:
            response = await self.llm_client.chat([
                {"role": "system", "content": "你是任务解析助手，只返回JSON。"},
                {"role": "user", "content": prompt}
            ])

            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                task_info = json.loads(json_match.group())
                ctx.set('task_info', task_info)
            else:
                ctx.set('task_info', {
                    'task_title': '提醒',
                    'task_content': content,
                    'is_recurring': False
                })

        except Exception as e:
            print(f"[任务工作流] 提取任务内容错误: {e}")
            ctx.set('task_info', {
                'task_title': '提醒',
                'task_content': content,
                'is_recurring': False
            })

        return ctx

    async def _step_create_reminder(self, ctx: WorkflowContext) -> WorkflowContext:
        """创建提醒"""
        reminder_time = ctx.get('reminder_time')
        task_info = ctx.get('task_info', {})

        if not reminder_time:
            ctx.result = "抱歉，我无法理解您想设置提醒的时间。请明确指定时间，如'明天下午3点'。"
            return ctx

        # 检查时间是否已过
        from datetime import datetime
        if reminder_time < datetime.now():
            ctx.result = "提醒时间已经过啦！请设置一个未来的时间。"
            return ctx

        # 保存任务信息到上下文
        ctx.set('pending_reminder', {
            'time': reminder_time,
            'title': task_info.get('task_title', '提醒'),
            'content': task_info.get('task_content', ''),
            'is_recurring': task_info.get('is_recurring', False)
        })

        # 构建确认消息
        from ..utils.time_parser import time_parser
        time_str = time_parser.format_time(reminder_time, 'human')

        if task_info.get('is_recurring'):
            ctx.confirm_message = f"我将为您设置周期性提醒：{task_info.get('recurring_description', '定期')}\n提醒内容：{task_info.get('task_content', '')}"
        else:
            content = task_info.get('task_content', '')
            ctx.confirm_message = f"为您设置提醒📅\n\n时间：{time_str}\n内容：{content}\n\n到时间我会通过系统通知提醒您！"

        # 同时设置 result，这样 agent 会创建任务
        ctx.result = ctx.confirm_message

        return ctx

    def set_task_scheduler(self, scheduler):
        """设置任务调度器"""
        self.task_scheduler = scheduler
