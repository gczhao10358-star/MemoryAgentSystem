"""
精准定时调度器
使用 asyncio.sleep 精确等待到指定时间
"""
import asyncio
import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass, field
from pytz import timezone


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskType(Enum):
    """任务类型"""
    REMINDER = "reminder"
    TASK = "task"
    MEETING = "meeting"
    RECURRING = "recurring"


@dataclass
class PreciseTask:
    """精准任务"""
    task_id: str
    user_id: str
    content: str
    scheduled_time: datetime
    title: Optional[str] = None
    task_type: TaskType = TaskType.REMINDER
    status: TaskStatus = TaskStatus.PENDING
    is_recurring: bool = False
    cron_expression: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    _cancel_event: Optional[asyncio.Event] = None

    def __post_init__(self):
        if self._cancel_event is None:
            self._cancel_event = asyncio.Event()

    def cancel(self):
        """取消任务"""
        if self._cancel_event:
            self._cancel_event.set()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set() if self._cancel_event else False


class PreciseScheduler:
    """
    精准定时调度器
    每个任务启动一个 asyncio Task，精准等待到执行时间
    """

    def __init__(self, metadata_store=None):
        self.tz = timezone('Asia/Shanghai')
        self.metadata_store = metadata_store
        self._tasks: Dict[str, PreciseTask] = {}
        self._callbacks: list[Callable[[PreciseTask], None]] = []
        self._async_tasks: Dict[str, asyncio.Task] = {}  # 存储 asyncio.Task

    def register_callback(self, callback: Callable[[PreciseTask], None]):
        """注册任务执行回调"""
        self._callbacks.append(callback)
        print(f"[精准调度器] 注册回调，当前回调数: {len(self._callbacks)}")

    async def initialize(self):
        """初始化，恢复持久化任务"""
        print("[精准调度器] 初始化...")
        if self.metadata_store:
            await self._restore_tasks()
        print(f"[精准调度器] 初始化完成，当前任务数: {len(self._tasks)}")

    async def shutdown(self):
        """关闭调度器，取消所有任务"""
        print("[精准调度器] 关闭...")
        for task_id, async_task in list(self._async_tasks.items()):
            async_task.cancel()
            try:
                await async_task
            except asyncio.CancelledError:
                pass
        self._async_tasks.clear()
        print("[精准调度器] 已关闭")

    async def create_reminder(
        self,
        user_id: str,
        content: str,
        reminder_time: datetime,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PreciseTask:
        """
        创建精准定时提醒
        """
        task_id = f"task_{uuid.uuid4().hex[:12]}"

        # 确保时间有时区
        if reminder_time.tzinfo is None:
            reminder_time = self.tz.localize(reminder_time)

        task = PreciseTask(
            task_id=task_id,
            user_id=user_id,
            content=content,
            scheduled_time=reminder_time,
            title=title or "提醒",
            metadata=metadata or {}
        )

        # 保存到数据库
        await self._save_task_to_db(task)

        # 启动定时任务
        self._tasks[task_id] = task
        async_task = asyncio.create_task(self._wait_and_execute(task))
        self._async_tasks[task_id] = async_task

        wait_seconds = (reminder_time - datetime.now(self.tz)).total_seconds()
        print(f"[精准调度器] 创建任务: {task_id}")
        print(f"[精准调度器] 执行时间: {reminder_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"[精准调度器] 将在 {wait_seconds:.1f} 秒后执行")

        return task

    async def _wait_and_execute(self, task: PreciseTask):
        """等待并执行任务"""
        try:
            now = datetime.now(self.tz)
            wait_seconds = (task.scheduled_time - now).total_seconds()

            if wait_seconds > 0:
                # 使用 wait_for 支持取消
                try:
                    await asyncio.wait_for(
                        task._cancel_event.wait(),
                        timeout=wait_seconds
                    )
                    # 如果 wait_for 返回，说明被取消了
                    print(f"[精准调度器] 任务被取消: {task.task_id}")
                    return
                except asyncio.TimeoutError:
                    # 正常超时，继续执行
                    pass

            # 检查是否被取消
            if task.is_cancelled():
                print(f"[精准调度器] 任务已取消，跳过执行: {task.task_id}")
                return

            # 执行回调
            await self._execute_callbacks(task)

            # 更新数据库状态
            await self._mark_completed(task)

        except asyncio.CancelledError:
            print(f"[精准调度器] 任务被取消: {task.task_id}")
        except Exception as e:
            print(f"[精准调度器] 任务执行异常: {task.task_id}, {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 清理
            self._tasks.pop(task.task_id, None)
            self._async_tasks.pop(task.task_id, None)

    async def _execute_callbacks(self, task: PreciseTask):
        """执行所有回调"""
        print(f"[精准调度器] 时间到！执行任务: {task.task_id}")
        print(f"[精准调度器] 用户: {task.user_id}, 内容: {task.content}")
        print(f"[精准调度器] 总回调数: {len(self._callbacks)}")

        for i, callback in enumerate(self._callbacks):
            try:
                print(f"[精准调度器] 调用回调 {i+1}/{len(self._callbacks)}: {callback.__name__}")
                if asyncio.iscoroutinefunction(callback):
                    # 添加5秒超时，防止回调挂起
                    await asyncio.wait_for(callback(task), timeout=5.0)
                else:
                    callback(task)
                print(f"[精准调度器] 回调 {i+1} 执行完成")
            except asyncio.TimeoutError:
                print(f"[精准调度器] 回调 {i+1} 执行超时")
            except Exception as e:
                print(f"[精准调度器] 回调 {i+1} 执行失败: {e}")
                import traceback
                traceback.print_exc()

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False

        task.cancel()

        # 取消 asyncio Task
        async_task = self._async_tasks.get(task_id)
        if async_task:
            async_task.cancel()

        await self._mark_cancelled(task)
        print(f"[精准调度器] 任务已取消: {task_id}")
        return True

    async def get_task(self, task_id: str) -> Optional[PreciseTask]:
        """获取单个任务"""
        return self._tasks.get(task_id)

    async def get_user_tasks(
        self,
        user_id: str,
        status: Optional[TaskStatus] = None,
        limit: int = 50
    ) -> List[PreciseTask]:
        """
        获取用户的任务列表

        Args:
            user_id: 用户ID
            status: 按状态过滤
            limit: 返回数量限制

        Returns:
            任务列表
        """
        tasks = []
        for task in self._tasks.values():
            if task.user_id == user_id:
                if status is None or task.status == status:
                    tasks.append(task)

        # 按创建时间排序（假设task_id包含时间戳）
        tasks.sort(key=lambda x: x.task_id, reverse=True)
        return tasks[:limit]

    async def _save_task_to_db(self, task: PreciseTask):
        """保存任务到数据库"""
        if not self.metadata_store:
            return
        try:
            await self._ensure_table()
            conn = self.metadata_store.conn
            conn.execute("""
                INSERT OR REPLACE INTO precise_tasks (
                    task_id, user_id, content, title, scheduled_time, status, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                task.task_id, task.user_id, task.content, task.title,
                task.scheduled_time.isoformat(), 'pending',
                json.dumps(task.metadata)
            ))
            conn.commit()
        except Exception as e:
            print(f"[精准调度器] 保存任务失败: {e}")

    async def _mark_completed(self, task: PreciseTask):
        """标记任务完成"""
        if not self.metadata_store:
            return
        try:
            conn = self.metadata_store.conn
            conn.execute(
                "UPDATE precise_tasks SET status = 'completed' WHERE task_id = ?",
                (task.task_id,)
            )
            conn.commit()
        except Exception as e:
            print(f"[精准调度器] 更新任务失败: {e}")

    async def _mark_cancelled(self, task: PreciseTask):
        """标记任务取消"""
        if not self.metadata_store:
            return
        try:
            conn = self.metadata_store.conn
            conn.execute(
                "UPDATE precise_tasks SET status = 'cancelled' WHERE task_id = ?",
                (task.task_id,)
            )
            conn.commit()
        except Exception as e:
            print(f"[精准调度器] 更新任务失败: {e}")

    async def _ensure_table(self):
        """确保表存在"""
        try:
            conn = self.metadata_store.conn
            conn.execute("""
                CREATE TABLE IF NOT EXISTS precise_tasks (
                    task_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    title TEXT,
                    scheduled_time TIMESTAMP,
                    status TEXT DEFAULT 'pending',
                    metadata TEXT
                )
            """)
            conn.commit()
        except Exception as e:
            print(f"[精准调度器] 创建表失败: {e}")

    async def _restore_tasks(self):
        """从数据库恢复未完成的任务"""
        try:
            await self._ensure_table()
            conn = self.metadata_store.conn
            cursor = conn.execute(
                "SELECT * FROM precise_tasks WHERE status = 'pending'"
            )
            restored = 0
            for row in cursor.fetchall():
                scheduled_time = datetime.fromisoformat(row['scheduled_time'])
                # 检查任务是否已过期
                if scheduled_time < datetime.now(self.tz):
                    conn.execute(
                        "UPDATE precise_tasks SET status = 'expired' WHERE task_id = ?",
                        (row['task_id'],)
                    )
                    continue

                task = PreciseTask(
                    task_id=row['task_id'],
                    user_id=row['user_id'],
                    content=row['content'],
                    title=row['title'],
                    scheduled_time=scheduled_time,
                    metadata=json.loads(row['metadata']) if row['metadata'] else {}
                )
                self._tasks[task.task_id] = task
                # 重新启动定时
                async_task = asyncio.create_task(self._wait_and_execute(task))
                self._async_tasks[task.task_id] = async_task
                restored += 1

            conn.commit()
            print(f"[精准调度器] 从数据库恢复 {restored} 个任务")
        except Exception as e:
            print(f"[精准调度器] 恢复任务失败: {e}")


# 全局实例
_scheduler: Optional[PreciseScheduler] = None


def get_precise_scheduler(metadata_store=None) -> PreciseScheduler:
    """获取全局调度器实例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = PreciseScheduler(metadata_store)
    return _scheduler
