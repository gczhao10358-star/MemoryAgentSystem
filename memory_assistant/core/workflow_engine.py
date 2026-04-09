"""
Agent工作流引擎
管理用户请求的完整处理流程
"""
import json
import re
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum


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
    def __init__(self, user_id: str, message: str, current_time: Dict[str, Any]):
        self.user_id = user_id
        self.message = message
        self.current_time = current_time
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

    def __init__(self, llm_client, memory_crud, datetime_tools):
        self.llm_client = llm_client
        self.memory_crud = memory_crud
        self.datetime_tools = datetime_tools

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

    async def process(self, user_id: str, message: str, current_time: Dict[str, Any]) -> WorkflowContext:
        """
        处理用户请求

        Returns:
            WorkflowContext: 包含处理结果或需要用户确认的信息
        """
        # 0. 先检查是否是简单问候（预设回复）
        simple_response = await self._generate_simple_response(message)
        if simple_response:
            context = WorkflowContext(user_id, message, current_time)
            context.result = simple_response
            return context

        # 1. 识别意图
        intent, thought, extracted_content = await self._recognize_intent(message)

        # 2. 创建上下文
        context = WorkflowContext(user_id, message, current_time)
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
        识别用户意图 - 主要由大模型判断

        Returns:
            (intent_type, thought, extracted_content)
        """
        import re
        import json

        # 只保留最明显的删除规则
        message_clean = message.strip().lower()
        delete_patterns = [r'^删除', r'^移除', r'^清空']
        if any(re.search(p, message_clean) for p in delete_patterns):
            print(f"[意图识别] 规则匹配 DELETE: '{message[:30]}...'")
            return IntentType.DELETE, "规则匹配：删除记忆", message

        # 其他全部由大模型判断
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

    async def _generate_simple_response(self, message: str) -> str:
        """为简单问候生成回复"""
        import re
        message_lower = message.lower().strip()

        # 简单问候的预设回复
        if re.search(r'你好|您好|^hi$|^hello$', message_lower):
            return "你好！我是智忆助理，很高兴为你服务。有什么我可以帮你的吗？"
        elif re.search(r'在吗|在么', message_lower):
            return "在的！有什么可以帮你的吗？"
        elif re.search(r'你是什么|你是谁|叫什么|怎么称呼', message_lower):
            return "我是智忆助理(MemoryMate)，一个具备长期记忆能力的AI助手。我会记住你的信息，为你提供个性化的帮助。"
        elif re.search(r'你会什么|你能做什么|帮助', message_lower):
            return "我可以帮你：1) 记录重要信息、计划和待办事项；2) 回答关于你过往记忆的问题；3) 进行日常对话和知识问答。有什么想记录或查询的吗？"
        else:
            # 其他简单问候，返回空字符串，让后续流程处理
            return ""

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
        """生成普通回复"""
        system_prompt = """你是智忆助理(MemoryMate)，一个具备长期记忆能力的AI助手。

你的特点：
1. 你会记住用户告诉你的信息，在后续对话中使用这些信息提供个性化帮助
2. 你可以帮用户记录日程安排、重要事项、个人偏好等
3. 你可以回答关于用户过往记忆的问题
4. 你可以进行日常对话和知识问答

当用户问你是谁时，请介绍自己是智忆助理(MemoryMate)。
当用户问你能做什么时，请介绍你的记忆能力和服务功能。

请用友好、自然的语气回复。"""
        response = await self.llm_client.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": ctx.message}
        ])
        ctx.result = response
        return ctx

    # ========== 存储工作流步骤 ==========

    async def _step_extract_time(self, ctx: WorkflowContext) -> WorkflowContext:
        """提取并计算具体时间"""
        current_date = ctx.current_time['date']  # YYYY-MM-DD
        current_weekday = ctx.current_time['weekday_name']

        # 使用提取的内容（如果没有则使用原始消息）
        content = ctx.get('extracted_content') or ctx.message

        prompt = f"""当前日期：{current_date} ({current_weekday})
用户输入："{content}"

请提取事件的时间信息，返回JSON格式：
{{
    "event_date": "YYYY-MM-DD格式的日期",
    "event_time": "HH:MM格式的时间或null",
    "date_description": "自然语言描述的日期和时间",
    "time_confidence": "high/medium/low"
}}

注意：
1. "明天" = 当前日期 + 1天
2. "后天" = 当前日期 + 2天
3. "下周X" = 下个星期X
4. "15号" = 本月或下月的15号（根据当前日期判断）
5. **重要**：时间必须包含小时和分钟，如 "16:15"、"09:30"
6. 如果用户说"16:15"，event_time 必须是 "16:15"
7. 如果用户说"下午3点半"，event_time 是 "15:30"
8. 只返回JSON，不要其他文字"""

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
        """润色内容，总结成完整句子"""
        time_info = ctx.get('time_info')

        prompt_parts = ["请润色以下记忆内容，总结成一句完整通顺的话。"]

        if time_info:
            date_desc = time_info.get('date_description', '')
            event_time = time_info.get('event_time', '')
            if date_desc:
                prompt_parts.append(f"日期：{date_desc}")
            if event_time:
                prompt_parts.append(f"时间：{event_time}")

        # 使用提取的内容（如果没有则使用原始消息）
        content = ctx.get('extracted_content') or ctx.message
        prompt_parts.append(f"\n原始内容：{content}")
        prompt_parts.append("\n要求：")
        prompt_parts.append("1. 包含完整的主体（谁）、事件（做什么）")
        prompt_parts.append("2. 包含具体时间")
        prompt_parts.append("3. 包含地点（如果有）")
        prompt_parts.append("4. 一句话总结，简洁明了")
        prompt_parts.append("\n只返回润色后的句子，不要其他内容。")

        try:
            response = await self.llm_client.chat([
                {"role": "system", "content": "你是内容润色助手。"},
                {"role": "user", "content": "\n".join(prompt_parts)}
            ])

            polished = response.strip()
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

        return ctx

    async def _step_check_conflict(self, ctx: WorkflowContext) -> WorkflowContext:
        """检查时间冲突"""
        event_date = ctx.get('event_date')
        if not event_date:
            return ctx

        # 搜索该日期的所有事件
        date_str = event_date.strftime('%Y-%m-%d')
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

        if is_personal_attribute and not has_time:
            # 存储为个人属性（FACT类型，高重要性）
            result = await self.memory_crud.create(
                user_id=ctx.user_id,
                content=polished,
                current_time=ctx.current_time,
                memory_type='fact'
            )
            # 同时更新用户画像
            await self._update_profile_with_attribute(ctx.user_id, content_for_check)
        else:
            # 存储为普通记忆（自动识别类型）
            result = await self.memory_crud.create(
                user_id=ctx.user_id,
                content=polished,
                current_time=ctx.current_time,
                memory_type='auto'
            )

        if result['success']:
            structured = result['structured']
            ctx.result = f"已记录：{structured.get('structured_content', polished)}"
        else:
            ctx.result = "记录失败，请重试。"

        return ctx

    def _is_personal_attribute(self, message: str) -> bool:
        """判断是否为个人属性（无时间的个人特征）"""
        import re
        # 个人属性关键词模式
        attribute_patterns = [
            r'[(我|本人)].*[(喜欢|讨厌|反感|厌恶|不爱|不爱吃)]',
            r'[(我|本人)].*[(过敏|不能吃|不能吃|忌口)]',
            r'[(我|本人)].*[(擅长|不擅长|会|不会)]',
            r'[(我|本人)].*[(习惯|经常|总是|从不)]',
            r'[(我|本人)].*[(是|为)].*[(身份|职业|职位)]',
            r'[(我的|本人)].*[(名字|姓名|称呼|昵称)]',
            r'[(我|本人)].*[(住|居住|工作)].*[(在|于)]',
            r'[(我|本人)].*[(爱好|兴趣|热衷于)]',
        ]
        for pattern in attribute_patterns:
            if re.search(pattern, message):
                return True
        return False

    async def _update_profile_with_attribute(self, user_id: str, message: str):
        """从个人属性消息中更新用户画像"""
        try:
            # 提取偏好或属性
            from ..profile.profile_manager import ProfileManager
            profile_manager = ProfileManager()
            profile = await profile_manager.get_profile(user_id)

            # 识别话题偏好
            import re
            if re.search(r'[(喜欢|爱好|感兴趣|热衷于)]', message):
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
        """计算检索的日期范围"""
        current_date = ctx.current_time['date']

        # 使用提取的内容（如果没有则使用原始消息）
        content = ctx.get('extracted_content') or ctx.message

        prompt = f"""当前日期：{current_date}
用户查询："{content}"

请分析用户要查询的日期范围，返回JSON格式：
{{
    "start_date": "YYYY-MM-DD格式的开始日期",
    "end_date": "YYYY-MM-DD格式的结束日期",
    "date_description": "自然语言描述，如'最近一周'、'3月份'等"
}}

注意：
1. "最近" = 过去7天到今天
2. "这周" = 本周一到周日
3. "下周" = 下周一到周日
4. "3月15日" = 仅3月15日当天
5. "15号" = 本月15号当天

只返回JSON，不要其他文字。"""

        try:
            response = await self.llm_client.chat([
                {"role": "system", "content": "你是日期解析助手，只返回JSON。"},
                {"role": "user", "content": prompt}
            ])

            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                date_range = json.loads(json_match.group())
                ctx.set('date_range', date_range)

                # 验证日期
                try:
                    start = datetime.strptime(date_range['start_date'], '%Y-%m-%d')
                    end = datetime.strptime(date_range['end_date'], '%Y-%m-%d')
                    ctx.set('start_date', start)
                    ctx.set('end_date', end)
                except:
                    pass

        except Exception as e:
            print(f"Error calculating date range: {e}")
            # 默认最近7天
            end = datetime.strptime(current_date, '%Y-%m-%d')
            start = end - timedelta(days=7)
            ctx.set('start_date', start)
            ctx.set('end_date', end)
            ctx.set('date_range', {
                'start_date': start.strftime('%Y-%m-%d'),
                'end_date': end.strftime('%Y-%m-%d'),
                'date_description': '最近一周'
            })

        return ctx

    async def _step_search_memories(self, ctx: WorkflowContext) -> WorkflowContext:
        """搜索记忆"""
        start_date = ctx.get('start_date')
        end_date = ctx.get('end_date')

        all_memories = []

        # 1. 按日期范围搜索
        if start_date and end_date:
            current = start_date
            while current <= end_date:
                memories = await self.memory_crud.search_by_date(
                    user_id=ctx.user_id,
                    date_str=current.strftime('%Y-%m-%d'),
                    memory_types=['event', 'task', 'reminder']
                )
                all_memories.extend(memories)
                current += timedelta(days=1)

        # 2. 语义搜索补充
        # 使用提取的内容进行搜索
        search_query = ctx.get('extracted_content') or ctx.message
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

        ctx.set('memories', all_memories)
        return ctx

    async def _step_generate_answer(self, ctx: WorkflowContext) -> WorkflowContext:
        """生成回答"""
        memories = ctx.get('memories', [])
        date_range = ctx.get('date_range', {})

        if not memories:
            date_desc = date_range.get('date_description', '该时间段')
            ctx.result = f"{date_desc}没有找到相关安排。"
            return ctx

        # 构建记忆信息
        memory_texts = []
        for i, mem in enumerate(memories[:10], 1):  # 最多10条
            metadata = mem.get('metadata', {})
            datetime_str = metadata.get('datetime', '')
            content = mem.get('content', '')
            memory_texts.append(f"{i}. {datetime_str}: {content}")

        memories_str = "\n".join(memory_texts)
        date_desc = date_range.get('date_description', '该时间段')

        # 使用提取的内容
        query_content = ctx.get('extracted_content') or ctx.message

        prompt = f"""根据以下记忆信息，回答用户的查询。

用户查询："{query_content}"
查询范围：{date_desc}

记忆信息：
{memories_str}

要求：
1. 直接回答用户的问题
2. 按时间顺序组织信息
3. 如果没有相关信息，明确说明
4. 语气友好自然

请生成回答："""

        try:
            response = await self.llm_client.chat([
                {"role": "system", "content": "你是智忆助理，根据记忆信息回答用户问题。"},
                {"role": "user", "content": prompt}
            ])
            ctx.result = response.strip()
        except Exception as e:
            print(f"Error generating answer: {e}")
            ctx.result = f"查询到 {len(memories)} 条记忆，但生成回答时出错。"

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

        prompt = f"""当前日期：{current_date} ({current_weekday})
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
1. "明天" = 当前日期 + 1天
2. "后天" = 当前日期 + 2天
3. "2分钟后" = 当前时间 + 2分钟，event_date = 今天, event_time = 当前时间+2分钟
4. "1小时后" = 当前时间 + 1小时，event_date = 今天, event_time = 当前时间+1小时
5. "每天早上/每天下午" = is_recurring: true, recurring_pattern: "daily"
6. "每周X" = is_recurring: true, recurring_pattern: "weekly"
7. **重要**：event_time 必须精确到分钟！如 "16:15"、"09:30"
8. 如果用户说"16:15"，event_time = "16:15"
9. 如果用户说"3点半"，event_time = "15:30"
10. 如果用户说"3点整"，event_time = "15:00"
11. 只返回JSON，不要其他文字"""

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
