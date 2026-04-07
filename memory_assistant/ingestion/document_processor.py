"""
文档处理核心类
整合整个ETL流水线
"""
import os
import re
from typing import AsyncGenerator, Dict, Any, Optional, List
from datetime import datetime

from .models import DocumentMetadata, DocumentType, ProcessingStatus, ProcessingResult
from .file_loaders import FileLoaderFactory
from .text_splitter import ChineseRecursiveTextSplitter
from .meeting_analyzer import MeetingAnalyzer


class DocumentProcessor:
    """
    文档处理器

    处理流水线：
    1. 文件加载 -> 2. 内容提取 -> 3. 语义切片 -> 4. LLM分析 -> 5. 结果存储
    """
    ANALYSIS_VERSION = "meeting-analysis-v2"

    def __init__(
        self,
        agent,  # MemoryMateAgent实例
        chunk_size: int = 800,
        chunk_overlap: int = 100
    ):
        self.agent = agent
        self.llm_client = agent.llm_client
        self.text_splitter = ChineseRecursiveTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        self.analyzer = MeetingAnalyzer(self.llm_client)

    async def process_file(
        self,
        file_path: str,
        user_id: str,
        metadata: Dict[str, Any],
        document_store=None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        处理文档的主入口

        Yields:
            流式处理状态和结果
        """
        start_time = datetime.now()
        document_id = metadata.get('document_id', f"doc_{datetime.now().timestamp()}")

        try:
            # ===== 阶段1: 文件加载 =====
            yield {
                "stage": "loading",
                "progress": 0.05,
                "data": {"message": "正在读取文档..."},
                "status": "processing"
            }

            content, extracted_meta, doc_type = FileLoaderFactory.load_file(file_path)

            # 丰富元数据
            doc_metadata = DocumentMetadata(
                filename=metadata.get('filename', os.path.basename(file_path)),
                file_size=metadata.get('file_size', os.path.getsize(file_path)),
                mime_type=metadata.get('mime_type', 'application/octet-stream'),
                doc_type=doc_type,
                uploaded_at=metadata.get('uploaded_at', datetime.now()),
                source=metadata.get('source', 'web'),
                uploaded_by=user_id,
                original_path=file_path,
                author=extracted_meta.get('author'),
                title=extracted_meta.get('title'),
                page_count=extracted_meta.get('page_count'),
                word_count=len(content)
            )

            yield {
                "stage": "loading",
                "progress": 0.1,
                "data": {
                    "document_id": document_id,
                    "doc_type": doc_type.value,
                    "word_count": len(content),
                    "page_count": extracted_meta.get('page_count')
                },
                "status": "completed"
            }

            # ===== 阶段2: 语义切片 =====
            yield {
                "stage": "chunking",
                "progress": 0.15,
                "data": {"message": "正在分析文档结构..."},
                "status": "processing"
            }

            chunks = self.text_splitter.split_text(content)

            yield {
                "stage": "chunking",
                "progress": 0.2,
                "data": {
                    "chunk_count": len(chunks),
                    "avg_chunk_size": len(content) // len(chunks) if chunks else 0
                },
                "status": "completed"
            }

            # ===== 阶段3: LLM分析（流式） =====
            analysis_result = None

            async for analysis_event in self.analyzer.analyze_stream(
                chunks=chunks,
                user_id=user_id,
                context={
                    "user_id": user_id,
                    "upload_time": datetime.now().isoformat(),
                    "document_title": doc_metadata.title
                }
            ):
                # 只转发非completed事件（completed事件由后面统一发送）
                if analysis_event["stage"] == "completed":
                    from .models import MeetingAnalysisResult
                    analysis_result = MeetingAnalysisResult(**analysis_event["data"])
                    # 发送一个进度消息但不包含完整数据
                    yield {
                        "stage": "consolidation",
                        "progress": 0.75,
                        "data": {"message": "正在整合分析结果..."},
                        "status": "completed"
                    }
                else:
                    # 转发分析事件，调整进度比例
                    adjusted_progress = 0.2 + (analysis_event["progress"] * 0.6)
                    yield {
                        "stage": analysis_event["stage"],
                        "progress": adjusted_progress,
                        "data": analysis_event["data"],
                        "status": analysis_event["status"]
                    }

            # ===== 阶段4: 存储记忆建议（不自动创建任务）=====
            yield {
                "stage": "storing",
                "progress": 0.85,
                "data": {"message": "正在保存记忆..."},
                "status": "processing"
            }

            stored_memory_ids = []

            # 存储摘要作为文档记忆
            if analysis_result:
                summary_content = f"【会议记录】{analysis_result.meeting_title or doc_metadata.filename}\n\n{analysis_result.summary}"
                summary_memory = await self.agent.remember(
                    user_id=user_id,
                    content=summary_content,
                    memory_type="document",
                    importance=0.7
                )
                if summary_memory:
                    stored_memory_ids.append("summary_memory")

                # 存储关键决策
                for decision in analysis_result.key_decisions[:5]:  # 最多5条
                    mem_id = await self.agent.remember(
                        user_id=user_id,
                        content=f"【会议决策】{decision}",
                        memory_type="fact",
                        importance=0.75
                    )
                    if mem_id:
                        stored_memory_ids.append(f"decision:{decision[:20]}")

                # 存储用户偏好（高重要性）
                for pref in analysis_result.user_preferences[:3]:
                    if pref.get('confidence', 0) > 0.7:
                        await self.agent.remember(
                            user_id=user_id,
                            content=f"【用户偏好】{pref['content']}",
                            memory_type="fact",
                            importance=0.8
                        )

            yield {
                "stage": "storing",
                "progress": 0.95,
                "data": {"stored_memories": len(stored_memory_ids)},
                "status": "completed"
            }

            # ===== 阶段5: 完成 =====
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

            final_result = ProcessingResult(
                document_id=document_id,
                status=ProcessingStatus.COMPLETED,
                metadata=doc_metadata,
                analysis=analysis_result,
                stored_memory_ids=stored_memory_ids
            )

            # 更新文档存储状态
            if document_store:
                await document_store.update_status(
                    document_id=document_id,
                    status="completed",
                    analysis_result=final_result.analysis.to_dict() if final_result.analysis else None,
                    metadata_updates={"analysis_version": self.ANALYSIS_VERSION},
                )

            await self.persist_analysis_completion_message(
                user_id=user_id,
                session_id=metadata.get("session_id"),
                document_id=document_id,
                analysis_result=final_result.analysis,
            )

            yield {
                "stage": "completed",
                "progress": 1.0,
                "data": {
                    "document_id": document_id,
                    "result": final_result.analysis.to_dict() if final_result.analysis else {},
                    "pending_actions": {
                        "action_items": len(analysis_result.action_items) if analysis_result else 0,
                        "need_confirmation": True
                    }
                },
                "status": "completed"
            }

        except Exception as e:
            # 更新文档状态为失败
            if document_store:
                await document_store.update_status(
                    document_id=document_id,
                    status="failed"
                )

            yield {
                "stage": "error",
                "progress": 0,
                "data": {"error": str(e)},
                "status": "error"
            }

    async def persist_analysis_completion_message(
        self,
        user_id: str,
        session_id: Optional[str],
        document_id: str,
        analysis_result,
    ) -> None:
        """将会议解析完成消息持久化到目标会话。"""
        if not session_id or not analysis_result:
            return

        content = self.build_analysis_completion_message(analysis_result)
        safe_session_id = re.sub(r"[^a-zA-Z0-9_-]", "_", session_id)
        await self.agent.memory_service.record_session_turn(
            user_id=user_id,
            session_id=session_id,
            role="assistant",
            content=content,
            turn_id=f"doc_analysis_{document_id}",
            message_id=f"msg_doc_analysis_{document_id}_{safe_session_id}",
        )

    def build_analysis_completion_message(self, analysis_result) -> str:
        """构造展示在会话历史中的会议解析完成消息。"""
        if hasattr(analysis_result, "to_dict"):
            result = analysis_result.to_dict()
        else:
            result = analysis_result or {}

        meeting_title = result.get("meeting_title") or "未识别"
        summary = (result.get("summary") or "").strip()
        if len(summary) > 200:
            summary = summary[:200].rstrip() + "..."
        if not summary:
            summary = "暂无摘要"

        action_count = len(result.get("action_items") or [])
        decision_count = len(result.get("key_decisions") or [])

        return (
            "📄 会议记录解析完成！\n\n"
            f"**主题：** {meeting_title}\n\n"
            f"**摘要：** {summary}\n\n"
            f"**提取结果：** {decision_count} 条关键决策，{action_count} 条待办事项\n\n"
            '> 点击上方"查看分析结果"按钮查看详情'
        )

    async def confirm_action_items(
        self,
        user_id: str,
        document_id: str,
        selected_items: List[int],
        reminder_times: Dict[str, str],
        document_store=None
    ) -> Dict[str, Any]:
        """
        用户确认后创建提醒任务

        Args:
            user_id: 用户ID
            document_id: 文档ID
            selected_items: 用户选中的待办索引列表
            reminder_times: 索引->提醒时间的映射
            document_store: 文档存储实例
        """
        # 从存储中获取分析结果
        analysis_result = None
        if document_store:
            doc_info = await document_store.get_document(document_id)
            if doc_info and doc_info.get('analysis_result'):
                import json
                analysis_result = json.loads(doc_info['analysis_result'])

        if not analysis_result:
            return {
                "success": False,
                "error": "未找到文档分析结果"
            }

        action_items = analysis_result.get('action_items', [])
        created_tasks = []

        for idx in selected_items:
            if idx < 0 or idx >= len(action_items):
                continue

            action_item = action_items[idx]
            reminder_time_str = reminder_times.get(str(idx))
            if not reminder_time_str:
                continue

            # 解析时间
            from ..utils.time_parser import time_parser
            reminder_time = time_parser.parse(reminder_time_str)

            if reminder_time:
                # 创建任务
                task = await self.agent.precise_scheduler.create_reminder(
                    user_id=user_id,
                    content=f"【会议待办】{action_item.get('content', '')}",
                    reminder_time=reminder_time,
                    title="会议待办提醒",
                    metadata={
                        'source': 'meeting_document',
                        'document_id': document_id
                    }
                )
                created_tasks.append({
                    'task_id': task.task_id,
                    'content': action_item.get('content'),
                    'reminder_time': reminder_time.isoformat()
                })

        return {
            "success": True,
            "created_count": len(created_tasks),
            "tasks": created_tasks
        }
