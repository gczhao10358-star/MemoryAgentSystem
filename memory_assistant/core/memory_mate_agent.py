"""
智忆助理主程序
集成记忆管理、用户画像和对话生成
"""
import asyncio
from typing import List, Dict, Optional, Any, AsyncGenerator
from datetime import datetime

from ..utils.llm_client import LLMClient
from ..utils.embedding import EmbeddingModel
from ..utils.text_processor import text_processor
from ..utils.datetime_tools import DateTimeTools, get_now, get_weekday_name
from ..storage.memory_storage import MemoryStorage
from ..storage.vector_store import FaissVectorStore
from ..storage.metadata_store import SQLiteMetadataStore
from ..retrieval.hybrid_retrieval import HybridRetrievalEngine
from ..profile.profile_manager import ProfileManager
from ..profile.profile_learner import ProfileLearner
from ..core.memory_manager import MemoryManager
from ..core.evolution_engine import MemoryEvolutionEngine
from ..core.content_filter import ContentFilter, should_remember, get_memory_type
from ..core.structured_memory import MemoryCRUD
from ..core.workflow_engine import MemoryWorkflowEngine, IntentType
from ..core.precise_scheduler import PreciseScheduler, get_precise_scheduler
from ..models.memory import MemoryEntry, MemoryType


class MemoryMateAgent:
    """
    智忆助理主类
    个性化长期记忆智能体
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}

        # 初始化LLM客户端
        llm_config = self.config.get('llm', {})
        self.llm_client = LLMClient(
            api_key=llm_config.get('api_key'),
            base_url=llm_config.get('base_url'),
            model=llm_config.get('model')
        )

        # 初始化嵌入模型
        embedding_config = self.config.get('embedding', {})
        self.embedding_model = EmbeddingModel(
            api_key=embedding_config.get('api_key') or llm_config.get('api_key'),
            base_url=embedding_config.get('base_url') or llm_config.get('base_url'),
            model=embedding_config.get('model', 'text-embedding-v3'),
            dimension=embedding_config.get('dimension', 1024)
        )

        # 初始化存储
        storage_config = self.config.get('storage', {})
        data_dir = storage_config.get('data_dir', './data')

        vector_store = FaissVectorStore(
            dimension=embedding_config.get('dimension', 1024),
            index_path=f"{data_dir}/vector_index"
        )
        metadata_store = SQLiteMetadataStore(
            db_path=f"{data_dir}/memory.db"
        )
        self.memory_storage = MemoryStorage(vector_store, metadata_store)

        # 初始化记忆管理器
        memory_config = self.config.get('memory', {})
        self.memory_manager = MemoryManager(
            storage=self.memory_storage,
            embedding_model=self.embedding_model,
            working_memory_max_turns=memory_config.get('working_memory', {}).get('max_turns', 20),
            short_term_max_entries=memory_config.get('short_term_memory', {}).get('max_entries', 100)
        )

        # 初始化检索引擎
        retrieval_config = self.config.get('retrieval', {})
        self.retrieval_engine = HybridRetrievalEngine(
            memory_storage=self.memory_storage,
            embedding_model=self.embedding_model,
            rrf_k=retrieval_config.get('rrf', {}).get('k', 60)
        )

        # 初始化用户画像
        self.profile_manager = ProfileManager(data_dir=data_dir)
        self.profile_learner = ProfileLearner(
            learning_rate=self.config.get('profile', {}).get('learning_rate', 0.1)
        )

        # 初始化演化引擎
        evolution_config = memory_config.get('evolution', {})
        self.evolution_engine = MemoryEvolutionEngine(
            metadata_store=metadata_store,
            decay_rate=evolution_config.get('decay_rate', 0.05),
            reinforcement_rate=evolution_config.get('reinforcement_rate', 0.1),
            forget_threshold=evolution_config.get('forget_threshold', 0.15),
        )

        # 初始化结构化记忆CRUD
        self.memory_crud = MemoryCRUD(
            memory_storage=self.memory_storage,
            embedding_model=self.embedding_model,
            llm_client=self.llm_client
        )

        # 初始化工作流引擎
        self.workflow_engine = MemoryWorkflowEngine(
            llm_client=self.llm_client,
            memory_crud=self.memory_crud,
            datetime_tools=DateTimeTools
        )

        # 初始化精准任务调度器
        self.precise_scheduler = get_precise_scheduler(metadata_store)
        self.workflow_engine.set_task_scheduler(self.precise_scheduler)

        # 保存待确认的工作流上下文
        self.pending_confirmations: Dict[str, Any] = {}

        self.current_user_id: Optional[str] = None

    async def initialize(self):
        """初始化系统"""
        print("Initializing MemoryMate...")

        # 初始化存储
        await self.memory_storage.initialize()

        # 注册任务回调（不在这里初始化调度器，由api.py控制）
        self.precise_scheduler.register_callback(self._on_task_triggered)
        print("[MemoryMate] 已注册 _on_task_triggered 回调")

        print("MemoryMate initialized successfully!")

    async def chat(self,
                   user_id: str,
                   message: str,
                   stream: bool = False) -> str:
        """
        主对话接口 - 使用工作流引擎

        Args:
            user_id: 用户ID
            message: 用户消息
            stream: 是否流式输出

        Returns:
            回复内容
        """
        self.current_user_id = user_id

        # 检查是否是确认回复
        confirm_key = f"{user_id}:confirm"
        if confirm_key in self.pending_confirmations:
            return await self._handle_confirmation(user_id, message)

        # 使用工作流引擎处理请求
        current_time = get_now()
        context = await self.workflow_engine.process(user_id, message, current_time)

        # 如果需要用户确认，保存上下文并返回确认消息
        if context.needs_user_confirm:
            self.pending_confirmations[confirm_key] = context
            return context.confirm_message + '\n\n（请回复"确认"或"取消"）'

        # 如果有错误，返回错误信息
        if context.error:
            return f"抱歉，处理您的请求时出现错误：{context.error}"

        # 如果有结果，直接返回
        if context.result:
            # 检查是否需要直接执行任务（不需要确认的情况）
            intent = context.get('intent')
            if intent == IntentType.EXECUTE_TASK and not context.needs_user_confirm:
                pending_reminder = context.get('pending_reminder')
                if pending_reminder and hasattr(self, 'precise_scheduler') and self.precise_scheduler:
                    task = await self.precise_scheduler.create_reminder(
                        user_id=user_id,
                        content=pending_reminder['content'],
                        reminder_time=pending_reminder['time'],
                        title=pending_reminder['title'],
                        metadata={'source': 'chat'}
                    )
                    print(f"[Agent] 任务已自动创建: task_id={task.task_id}")

                    # 同时将提醒存储为记忆
                    await self.memory_crud.create(
                        user_id=user_id,
                        content=f"设置了提醒: {pending_reminder['content']} 时间: {pending_reminder['time'].strftime('%Y-%m-%d %H:%M')}",
                        current_time=current_time,
                        memory_type='reminder'
                    )

            # 记录到工作记忆
            self.memory_manager.working_memory.add_turn("user", message)
            self.memory_manager.working_memory.add_turn("assistant", context.result)

            # 存储用户查询为记忆并更新画像（根据意图类型）
            if intent == IntentType.STORE:
                # 存储类型的意图，存储记忆并更新画像
                print(f"[Agent] STORE意图，准备存储交互...")
                asyncio.create_task(self._store_interaction(
                    user_id, message, context.result
                ))
            elif intent == IntentType.CHAT:
                # 对话类型的意图，尝试存储记忆（内容过滤器判断）并更新画像
                print(f"[Agent] CHAT意图，准备存储交互...")
                asyncio.create_task(self._store_interaction(
                    user_id, message, context.result
                ))
            elif intent in (IntentType.RETRIEVE, IntentType.EXECUTE_TASK):
                # 检索和任务意图，不存储记忆但更新画像
                print(f"[Agent] {intent.name}意图，更新画像...")
                asyncio.create_task(self._update_profile_only(
                    user_id, message, context.result
                ))

            return context.result

        # 如果没有结果，使用原有流程（备用）
        return await self._legacy_chat(user_id, message, stream)

    async def _handle_confirmation(self, user_id: str, message: str) -> str:
        """处理用户的确认回复"""
        confirm_key = f"{user_id}:confirm"
        context = self.pending_confirmations.pop(confirm_key, None)

        if not context:
            return "抱歉，我忘记了我们在确认什么。请重新告诉我您的需求。"

        message_lower = message.lower().strip()

        if message_lower in ['确认', '是的', '是', '确定', 'ok', 'yes']:
            # 用户确认，执行相应操作
            from ..core.workflow_engine import IntentType
            intent = context.get('intent')

            if intent == IntentType.EXECUTE_TASK:
                # 创建提醒任务
                pending_reminder = context.get('pending_reminder')
                print(f"[Agent] EXECUTE_TASK: user_id={user_id}, pending_reminder={pending_reminder}")
                # 使用精准调度器创建任务
                if pending_reminder and hasattr(self, 'precise_scheduler') and self.precise_scheduler:
                    task = await self.precise_scheduler.create_reminder(
                        user_id=user_id,
                        content=pending_reminder['content'],
                        reminder_time=pending_reminder['time'],
                        title=pending_reminder['title'],
                        metadata={'source': 'chat'}
                    )
                    print(f"[Agent] 任务已创建: task_id={task.task_id}, task_user_id={task.user_id}")
                else:
                    print(f"[Agent] 警告: 无法创建提醒任务，precise_scheduler 不可用")

                    # 同时将提醒存储为记忆
                    await self.memory_crud.create(
                        user_id=user_id,
                        content=f"设置了提醒: {pending_reminder['content']} 时间: {pending_reminder['time'].strftime('%Y-%m-%d %H:%M')}",
                        current_time=context.current_time,
                        memory_type='reminder'
                    )

                    from ..utils.time_parser import time_parser
                    time_str = time_parser.format_time(pending_reminder['time'], 'human')
                    return f"✅ 已确认！我会在 {time_str} 提醒您：{pending_reminder['content']}"
            elif intent == IntentType.STORE:
                # 存储记忆（即使有时间冲突）
                polished = context.get('polished_content', context.message)
                time_info = context.get('time_info', {})
                has_time = time_info and time_info.get('event_date')

                # 获取提取的内容（如果没有则使用原始消息）
                content_for_check = context.get('extracted_content') or context.message

                # 判断是否包含个人属性关键词（无时间的信息）
                is_personal = self._is_personal_attribute(content_for_check)

                if is_personal and not has_time:
                    # 存储为个人属性（FACT类型）
                    result = await self.memory_crud.create(
                        user_id=user_id,
                        content=polished,
                        current_time=context.current_time,
                        memory_type='fact'
                    )
                    # 同时更新用户画像
                    await self._update_profile_with_attribute(user_id, content_for_check)
                else:
                    result = await self.memory_crud.create(
                        user_id=user_id,
                        content=polished,
                        current_time=context.current_time,
                        memory_type='auto'
                    )

                if result['success']:
                    return f"已记录：{result['structured'].get('structured_content', polished)}"
                else:
                    return "记录失败，请重试。"

            elif intent == IntentType.DELETE:
                # 执行删除
                memories = context.get('memories_to_delete', [])
                count = 0
                for mem in memories:
                    if await self.memory_crud.delete(mem['memory_id']):
                        count += 1

                date_str = context.get('delete_date', '')
                date_display = date_str.replace('-', '年', 1).replace('-', '月') + '日'
                return f"已删除 {date_display} 的 {count} 条安排。"

            else:
                return "已确认。"

        elif message_lower in ['取消', '否', '不', 'no', '算了']:
            return "已取消操作。"

        else:
            # 重新放回待确认队列
            self.pending_confirmations[confirm_key] = context
            return '请回复"确认"或"取消"。'

    async def _legacy_chat(self, user_id: str, message: str, stream: bool = False) -> str:
        """原有的聊天流程（备用）"""
        # 1. 记录用户输入到工作记忆
        self.memory_manager.working_memory.add_turn("user", message)

        # 2. 检索相关记忆
        retrieval_results = await self.retrieval_engine.retrieve(
            query=message,
            user_id=user_id,
            top_k=5,
            use_personalization=True,
            user_profile=(await self.profile_manager.get_profile(user_id)).to_dict()
        )

        # 3. 获取用户画像
        profile = await self.profile_manager.get_profile(user_id)

        # 4. 构建系统提示
        system_prompt = await self._build_system_prompt(
            profile, retrieval_results, message
        )

        # 5. 构建对话历史
        messages = [{"role": "system", "content": system_prompt}]

        # 添加工作记忆中的对话历史
        for turn in self.memory_manager.working_memory.get_context():
            messages.append({
                "role": turn['role'],
                "content": turn['content']
            })

        # 6. 调用LLM生成回复
        if stream:
            response_text = ""
            async for chunk in self.llm_client.chat_stream(messages):
                response_text += chunk
            return response_text
        else:
            response_text = await self.llm_client.chat(messages)

        # 7. 记录系统回复到工作记忆
        self.memory_manager.working_memory.add_turn("assistant", response_text)

        # 8. 存储用户查询为记忆
        asyncio.create_task(self._store_interaction(
            user_id, message, response_text
        ))

        return response_text

    async def _store_interaction(self, user_id: str, query: str, response: str):
        """存储交互到记忆系统（使用结构化记忆）"""
        # 先更新用户画像（无论是否存储记忆）
        await self._update_profile_only(user_id, query, response)

        # 使用内容过滤器判断是否应该存储
        should_store, metadata = ContentFilter.should_store_memory(query)

        if not should_store:
            # 记录过滤原因但不存储
            reason = metadata.get('filtered_reason', 'unknown')
            print(f"[内容过滤] 未存储查询 (原因: {reason}): {query[:50]}...")
            return

        # 获取记忆类型
        mem_type = metadata.get('memory_type', 'fact')

        # 使用结构化记忆创建
        current_time = get_now()
        result = await self.memory_crud.create(
            user_id=user_id,
            content=query,
            current_time=current_time,
            memory_type=mem_type
        )

        if result['success']:
            structured = result['structured']
            print(f"[结构化记忆] 已存储 {mem_type} 类型记忆: {structured.get('title', query[:30])}")
            if structured.get('datetime'):
                print(f"  时间: {structured['datetime']}")
            if structured.get('location'):
                print(f"  地点: {structured['location']}")
            if structured.get('people'):
                print(f"  人物: {', '.join(structured['people'])}")

            # 同时存储到短期记忆（缓存）
            from ..models.memory import MemoryEntry, MemoryType
            entry = MemoryEntry(
                user_id=user_id,
                content=structured.get('structured_content', query),
                memory_type=MemoryType(mem_type),
                importance=structured.get('importance', 0.5)
            )
            entry.metadata = {
                'raw_content': query,
                'title': structured.get('title'),
                'datetime': structured.get('datetime'),
                'tags': structured.get('tags', []),
            }
            # 存储到短期记忆 - 使用await确保立即执行
            await self.memory_manager.short_term_memory.store(entry)
            print(f"[短期记忆] 已存储，当前条目数: {len(self.memory_manager.short_term_memory.cache)}")
        else:
            print(f"[结构化记忆] 存储失败: {query[:50]}...")

    async def _update_profile_only(self, user_id: str, query: str, response: str):
        """仅更新用户画像（不存储记忆）"""
        try:
            profile = await self.profile_manager.get_profile(user_id)
            await self.profile_learner.learn_from_interaction(
                profile=profile,
                query=query,
                response=response
            )
            await self.profile_manager.save_profile(profile)
            print(f"[画像更新] 用户 {user_id} 画像已更新")
        except Exception as e:
            print(f"[画像更新] 更新失败: {e}")

    async def _handle_delete_command(self, user_id: str, message: str) -> str:
        """
        处理删除/取消指令

        Args:
            user_id: 用户ID
            message: 用户消息

        Returns:
            回复内容
        """
        # 提取要删除的日期
        date_str = ContentFilter.extract_delete_date(message)

        if not date_str:
            return "抱歉，我没有理解您想删除哪个日期的安排。请明确指定日期，比如'3月15日'或'15号'。"

        # 确认是否要删除
        import re
        is_all = bool(re.search(r'(所有|全部|一切)', message))

        # 确定要删除的记忆类型
        memory_types = ['event', 'task', 'reminder']
        if re.search(r'(会议)', message):
            memory_types = ['event']
        elif re.search(r'(任务|待办)', message):
            memory_types = ['task']

        # 使用结构化记忆CRUD删除
        deleted_count = await self.memory_crud.delete_by_date(
            user_id=user_id,
            date_str=date_str,
            memory_types=memory_types
        )

        # 构建回复
        date_display = date_str.replace('-', '年', 1).replace('-', '月') + '日'

        if deleted_count > 0:
            return f"已为您删除 {date_display} 的 {deleted_count} 条安排。"
        else:
            return f"没有找到 {date_display} 的安排，无需删除。"

    async def _build_system_prompt(self,
                                   profile,
                                   retrieval_results: List[Any],
                                   user_message: str = "") -> str:
        """构建系统提示"""
        # 获取当前时间信息
        now = get_now()

        prompt_parts = [
            "你是智忆助理(MemoryMate)，一个具备长期记忆能力的AI助手。",
            "你会记住用户的信息，并在对话中利用这些记忆提供个性化的帮助。",
            "",
            f"【当前时间信息】",
            f"今天是: {now['date']} {now['weekday_name']}",
            f"当前时间: {now['time']}",
            f"年份: {now['year']}年, 月份: {now['month']}月",
        ]

        # 解析用户消息中的日期引用，帮助理解日期关系
        if user_message:
            resolved_date = DateTimeTools.resolve_date_reference(user_message)
            if resolved_date:
                weekday = get_weekday_name(resolved_date)
                date_str = resolved_date.strftime('%Y-%m-%d')
                prompt_parts.append(f"用户提到的日期解析: {date_str} ({weekday})")

        # 添加用户画像信息
        if profile.topic_preferences:
            top_topics = sorted(
                profile.topic_preferences,
                key=lambda x: x.weight,
                reverse=True
            )[:3]
            topics_str = ", ".join([t.topic for t in top_topics])
            prompt_parts.append(f"\n用户感兴趣的话题: {topics_str}")

        # 添加专业领域
        if profile.expertise_areas:
            expertise = [e.domain for e in profile.expertise_areas[:3]]
            prompt_parts.append(f"用户的专业领域: {', '.join(expertise)}")

        # 添加交互风格偏好
        style = profile.interaction_style
        if style.preferred_response_length == "short":
            prompt_parts.append("用户偏好简洁的回答。")
        elif style.preferred_response_length == "long":
            prompt_parts.append("用户偏好详细的回答。")

        if style.preferred_formality == "formal":
            prompt_parts.append("请使用正式礼貌的语言。")
        elif style.preferred_formality == "casual":
            prompt_parts.append("可以使用轻松随意的语言。")

        # 添加相关记忆
        if retrieval_results:
            prompt_parts.append("\n以下是相关的历史记忆，请参考这些信息回答:")
            for i, result in enumerate(retrieval_results[:5], 1):
                memory = result.memory
                prompt_parts.append(f"{i}. [{memory.memory_type.value}] {memory.content[:100]}")

        return "\n".join(prompt_parts)

    async def remember(self,
                       user_id: str,
                       content: str,
                       memory_type: str = "auto",
                       importance: float = 0.5) -> bool:
        """
        显式存储记忆（使用结构化记忆）

        Args:
            user_id: 用户ID
            content: 记忆内容
            memory_type: 记忆类型（auto表示自动识别）
            importance: 重要性

        Returns:
            是否成功
        """
        # 使用结构化记忆创建
        current_time = get_now()
        result = await self.memory_crud.create(
            user_id=user_id,
            content=content,
            current_time=current_time,
            memory_type=memory_type
        )

        if result['success']:
            structured = result['structured']
            print(f"[显式存储] 成功: {structured.get('title', content[:30])}")
            return True
        else:
            print(f"[显式存储] 失败: {content[:50]}...")
            return False

    async def search_memories(self,
                              user_id: str,
                              query: str,
                              top_k: int = 10) -> List[Dict]:
        """
        搜索记忆

        Args:
            user_id: 用户ID
            query: 查询
            top_k: 返回数量

        Returns:
            记忆列表
        """
        results = await self.retrieval_engine.retrieve(
            query=query,
            user_id=user_id,
            top_k=top_k,
            use_personalization=True,
            user_profile=(await self.profile_manager.get_profile(user_id)).to_dict()
        )

        return [
            {
                'memory_id': r.memory.memory_id,
                'content': r.memory.content,
                'type': r.memory.memory_type.value,
                'created_at': r.memory.created_at.isoformat(),
                'score': r.final_score,
            }
            for r in results
        ]

    async def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """获取用户统计"""
        memory_stats = await self.memory_manager.get_stats(user_id)
        profile_stats = await self.profile_manager.get_profile_stats(user_id)

        return {
            'memory': memory_stats,
            'profile': profile_stats,
        }

    async def run_evolution(self) -> Dict[str, Any]:
        """运行记忆演化"""
        results = await self.evolution_engine.batch_evolve()

        state_transitions = {}
        for r in results:
            transition = f"{r.old_state.value}_to_{r.new_state.value}"
            state_transitions[transition] = state_transitions.get(transition, 0) + 1

        return {
            'total_evolved': len(results),
            'state_transitions': state_transitions,
        }

    async def clear_conversation(self, user_id: str):
        """清空当前对话"""
        self.memory_manager.working_memory.clear()

    async def close(self):
        """关闭系统"""
        # 关闭精准任务调度器
        if hasattr(self, 'precise_scheduler') and self.precise_scheduler:
            await self.precise_scheduler.shutdown()
        # 关闭存储
        await self.memory_storage.close()

    async def _on_task_triggered(self, task):
        """任务触发时的回调 - 快速执行，避免阻塞"""
        print(f"[任务触发] 用户 {task.user_id}: {task.content}")

        try:
            # 将提醒记录到工作记忆（快速操作）
            reminder_message = f"[提醒] {task.content}"
            self.memory_manager.working_memory.add_turn("assistant", reminder_message)
            print(f"[任务触发] 已添加到工作记忆")
        except Exception as e:
            print(f"[任务触发] 添加到工作记忆失败: {e}")

        # 后台异步存储记忆（不阻塞回调）
        async def store_reminder_memory():
            try:
                await self.memory_crud.create(
                    user_id=task.user_id,
                    content=f"提醒已触发: {task.content}",
                    current_time=get_now(),
                    memory_type='reminder'
                )
                print(f"[任务触发] 已存储提醒记忆")
            except Exception as e:
                print(f"[任务触发] 存储记忆失败: {e}")

        # 启动后台任务，不等待完成
        asyncio.create_task(store_reminder_memory())

    def _is_personal_attribute(self, message: str) -> bool:
        """判断是否为个人属性（无时间的个人特征）"""
        import re
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
            profile = await self.profile_manager.get_profile(user_id)

            # 识别话题偏好
            import re
            if re.search(r'[(喜欢|爱好|感兴趣|热衷于)]', message):
                topic_match = re.search(r'喜欢.*?([\u4e00-\u9fa5]{2,10})', message)
                if topic_match:
                    topic = topic_match.group(1)
                    profile.add_or_update_topic(topic, 0.8)
                    await self.profile_manager.save_profile(profile)
        except Exception as e:
            print(f"[更新画像] 失败: {e}")
