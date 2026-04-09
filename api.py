#!/usr/bin/env python3
"""
智忆助理 (MemoryMate) - FastAPI 后端服务
提供 RESTful API 接口供前端调用
"""
import asyncio
import json
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Set

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from memory_assistant.core.memory_mate_agent import MemoryMateAgent
from memory_assistant.models.memory import MemoryType
from memory_assistant.utils.time_parser import time_parser
from memory_assistant.utils.datetime_tools import get_now
from memory_assistant.utils.config_loader import load_config
from datetime import datetime, timedelta

# 全局Agent实例
agent: Optional[MemoryMateAgent] = None

# WebSocket连接管理
class ConnectionManager:
    def __init__(self, max_offline_messages: int = 100):
        self.active_connections: Dict[str, WebSocket] = {}
        # 离线消息暂存：user_id -> list of messages
        self.offline_messages: Dict[str, List[Dict]] = {}
        self.max_offline_messages = max_offline_messages
        # 连接统计
        self.connection_stats: Dict[str, Dict] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket

        # 更新连接统计
        if user_id not in self.connection_stats:
            self.connection_stats[user_id] = {
                "connect_count": 0,
                "last_connect": None,
                "last_disconnect": None
            }
        self.connection_stats[user_id]["connect_count"] += 1
        self.connection_stats[user_id]["last_connect"] = datetime.now().isoformat()

        print(f"[WebSocket] 用户 {user_id} 已连接 (第{self.connection_stats[user_id]['connect_count']}次连接)")

        # 发送离线期间缓存的消息
        await self._send_offline_messages(user_id, websocket)

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

        if user_id in self.connection_stats:
            self.connection_stats[user_id]["last_disconnect"] = datetime.now().isoformat()

        print(f"[WebSocket] 用户 {user_id} 已断开")

    async def _send_offline_messages(self, user_id: str, websocket: WebSocket):
        """发送用户离线期间缓存的消息"""
        if user_id in self.offline_messages and self.offline_messages[user_id]:
            messages = self.offline_messages[user_id].copy()
            print(f"[WebSocket] 用户 {user_id} 有 {len(messages)} 条离线消息待同步")

            sent_count = 0
            for msg in messages:
                try:
                    # 添加标记表示这是离线消息
                    msg["is_offline_message"] = True
                    msg["synced_at"] = datetime.now().isoformat()
                    await websocket.send_json(msg)
                    sent_count += 1
                except Exception as e:
                    print(f"[WebSocket] 发送离线消息失败: {e}")
                    break

            # 清空已发送的消息
            self.offline_messages[user_id] = self.offline_messages[user_id][sent_count:]
            if not self.offline_messages[user_id]:
                del self.offline_messages[user_id]

            print(f"[WebSocket] 已同步 {sent_count} 条离线消息给用户 {user_id}")

    async def send_personal_message(self, user_id: str, message: dict):
        """发送消息给用户，如果用户离线则缓存"""
        print(f"[WebSocket] 尝试发送消息给 {user_id}, 当前连接数: {len(self.active_connections)}")

        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(message)
                print(f"[WebSocket] 消息发送成功给 {user_id}")
                return True
            except Exception as e:
                print(f"[WebSocket] 发送消息失败，将缓存消息: {e}")
                self._cache_offline_message(user_id, message)
                # 从活跃连接中移除（连接可能已断开）
                self.disconnect(user_id)
                return False
        else:
            print(f"[WebSocket] 用户 {user_id} 不在线，缓存消息以待重连")
            self._cache_offline_message(user_id, message)
            print(f"[WebSocket] 当前活跃用户: {list(self.active_connections.keys())}")
            return False

    def _cache_offline_message(self, user_id: str, message: dict):
        """缓存离线消息"""
        if user_id not in self.offline_messages:
            self.offline_messages[user_id] = []

        # 添加时间戳
        message["cached_at"] = datetime.now().isoformat()

        self.offline_messages[user_id].append(message)

        # 限制缓存大小，避免内存无限增长
        if len(self.offline_messages[user_id]) > self.max_offline_messages:
            self.offline_messages[user_id] = self.offline_messages[user_id][-self.max_offline_messages:]
            print(f"[WebSocket] 用户 {user_id} 离线消息过多，已丢弃最早的消息")

        print(f"[WebSocket] 已缓存消息给用户 {user_id}，当前缓存数: {len(self.offline_messages[user_id])}")

    def get_offline_message_count(self, user_id: str) -> int:
        """获取用户离线消息数量"""
        return len(self.offline_messages.get(user_id, []))

    async def broadcast(self, message: dict):
        """广播消息给所有在线用户"""
        disconnected = []
        for user_id, connection in self.active_connections.items():
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"[WebSocket] 广播消息给用户 {user_id} 失败: {e}")
                disconnected.append(user_id)

        # 清理断开的连接
        for user_id in disconnected:
            self.disconnect(user_id)

manager = ConnectionManager()
# 全局平台管理器
platform_manager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global agent, platform_manager

    # 启动时初始化
    print("正在初始化智忆助理...")
    config = load_config()
    agent = MemoryMateAgent(config)
    await agent.initialize()

    # 初始化平台管理器
    from memory_assistant.platform.lark_adapter import get_platform_manager
    from memory_assistant.core.precise_scheduler import get_precise_scheduler
    print(f"[平台管理器] 初始化中，metadata_store={agent.memory_storage.metadata_store}")
    platform_manager = get_platform_manager(agent.memory_storage.metadata_store)
    print(f"[平台管理器] 实例创建完成: {platform_manager}")
    await platform_manager.initialize()
    print("[平台管理器] 初始化完成")

    # 初始化精准定时调度器
    precise_scheduler = get_precise_scheduler(agent.memory_storage.metadata_store)
    print(f"[精准调度器] 实例创建完成: {precise_scheduler}")

    # 注册WebSocket通知回调（必须在initialize之前注册！）
    async def notify_user(task):
        """任务触发时通知用户（WebSocket + 第三方平台）"""
        print(f"[notify_user] 回调被触发! task_id={task.task_id}, user_id={task.user_id}, content={task.content}")

        # 1. WebSocket 通知（支持离线消息缓存）
        websocket_sent = False
        try:
            websocket_sent = await manager.send_personal_message(
                task.user_id,
                {
                    "type": "reminder",
                    "task_id": task.task_id,
                    "title": task.title or "提醒",
                    "content": task.content,
                    "triggered_at": datetime.now().isoformat()
                }
            )
            if websocket_sent:
                print(f"[notify_user] WebSocket 通知已实时发送给用户 {task.user_id}")
            else:
                print(f"[notify_user] 用户 {task.user_id} 不在线，提醒已缓存，将在重连时推送")
        except Exception as e:
            print(f"[notify_user] WebSocket 通知异常: {e}")

        # 2. 飞书通知
        if platform_manager:
            try:
                print(f"[notify_user] 开始调用飞书通知...")
                result = await platform_manager.send_notification(
                    user_id=task.user_id,
                    title=task.title or "提醒",
                    content=task.content
                )
                print(f"[notify_user] 飞书通知结果: {result}")
            except Exception as e:
                print(f"[notify_user] 飞书通知异常: {e}")
                import traceback
                traceback.print_exc()

        # 3. 存储"收到提醒"的记忆（后台异步，不阻塞回调）
        async def store_reminder_memory():
            try:
                from memory_assistant.utils.datetime_tools import get_now
                await agent.memory_crud.create(
                    user_id=task.user_id,
                    content=f"收到提醒: {task.content}",
                    current_time=get_now(),
                    memory_type='reminder'
                )
                print(f"[notify_user] 已存储'收到提醒'记忆")
            except Exception as e:
                print(f"[notify_user] 存储记忆失败: {e}")

        # 启动后台任务，不等待完成
        asyncio.create_task(store_reminder_memory())

    # 先注册回调，再初始化！这很重要！
    precise_scheduler.register_callback(notify_user)
    print(f"[精准调度器] 已注册 notify_user 回调")

    # 现在初始化调度器，会加载数据库中的任务
    await precise_scheduler.initialize()
    print(f"[精准调度器] 初始化完成")

    # 保存到 agent 以便其他地方使用
    agent.precise_scheduler = precise_scheduler
    print(f"[Agent] precise_scheduler 已绑定: {agent.precise_scheduler}")

    print("智忆助理初始化完成!")

    yield

    # 关闭时清理
    print("正在关闭智忆助理...")
    if agent:
        await agent.close()
    print("智忆助理已关闭")


# 创建FastAPI应用
app = FastAPI(
    title="智忆助理 API",
    description="MemoryMate - 具备长期记忆能力的AI助手",
    version="1.0.0",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Pydantic 模型 ==============

class ChatRequest(BaseModel):
    """聊天请求"""
    user_id: str = Field(..., description="用户ID")
    message: str = Field(..., description="用户消息")
    stream: bool = Field(False, description="是否流式输出")


class ChatResponse(BaseModel):
    """聊天响应"""
    success: bool
    data: Optional[str] = None
    error: Optional[str] = None


class RememberRequest(BaseModel):
    """存储记忆请求"""
    user_id: str = Field(..., description="用户ID")
    content: str = Field(..., description="记忆内容")
    memory_type: str = Field("fact", description="记忆类型 (chat/document/event/fact/task/reminder)")
    importance: float = Field(0.5, ge=0.0, le=1.0, description="重要性 (0-1)")


class RememberResponse(BaseModel):
    """存储记忆响应"""
    success: bool
    memory_id: Optional[str] = None
    error: Optional[str] = None


class SearchRequest(BaseModel):
    """搜索记忆请求"""
    user_id: str = Field(..., description="用户ID")
    query: str = Field(..., description="搜索关键词")
    top_k: int = Field(10, ge=1, le=50, description="返回数量")


class MemoryItem(BaseModel):
    """记忆项"""
    memory_id: str
    content: str
    type: str
    created_at: str
    score: float


class SearchResponse(BaseModel):
    """搜索记忆响应"""
    success: bool
    data: List[MemoryItem] = []
    total: int = 0
    error: Optional[str] = None


class UserStats(BaseModel):
    """用户统计"""
    memory: Dict[str, Any]
    profile: Dict[str, Any]


class StatsResponse(BaseModel):
    """统计响应"""
    success: bool
    data: Optional[UserStats] = None
    error: Optional[str] = None


class EvolutionResponse(BaseModel):
    """记忆演化响应"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class CreateUserRequest(BaseModel):
    """创建用户请求"""
    username: str = Field(..., description="用户名")


class CreateUserResponse(BaseModel):
    """创建用户响应"""
    success: bool
    user_id: Optional[str] = None
    username: Optional[str] = None
    error: Optional[str] = None


class ClearConversationRequest(BaseModel):
    """清空对话请求"""
    user_id: str = Field(..., description="用户ID")


class ClearConversationResponse(BaseModel):
    """清空对话响应"""
    success: bool
    message: str
    error: Optional[str] = None


class StructuredMemoryResponse(BaseModel):
    """结构化记忆响应"""
    memory_id: str
    content: str
    memory_type: str
    structured_content: str
    datetime: Optional[str] = None
    location: Optional[str] = None
    people: List[str] = []
    tags: List[str] = []
    importance: float
    created_at: str


class SearchStructuredRequest(BaseModel):
    """搜索结构化记忆请求"""
    user_id: str = Field(..., description="用户ID")
    query: Optional[str] = Field(None, description="查询词")
    date: Optional[str] = Field(None, description="日期过滤 (YYYY-MM-DD)")
    location: Optional[str] = Field(None, description="地点过滤")
    person: Optional[str] = Field(None, description="人物过滤")
    memory_type: Optional[str] = Field(None, description="记忆类型")
    top_k: int = Field(10, ge=1, le=50, description="返回数量")


class SearchStructuredResponse(BaseModel):
    """搜索结构化记忆响应"""
    success: bool
    data: List[StructuredMemoryResponse] = []
    total: int = 0
    error: Optional[str] = None


class UpdateMemoryRequest(BaseModel):
    """更新记忆请求"""
    user_id: str = Field(..., description="用户ID")
    memory_id: str = Field(..., description="记忆ID")
    content: Optional[str] = Field(None, description="新内容")
    memory_type: Optional[str] = Field(None, description="记忆类型")
    importance: Optional[float] = Field(None, ge=0.0, le=1.0, description="重要性")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class UpdateMemoryResponse(BaseModel):
    """更新记忆响应"""
    success: bool
    message: str
    error: Optional[str] = None


class ParseTimeRequest(BaseModel):
    """解析时间请求"""
    text: str = Field(..., description="包含时间描述的自然语言文本，如'今天下午3点'、'明天早上'")


class ParseTimeResponse(BaseModel):
    """解析时间响应"""
    success: bool
    original_text: str
    parsed_time: Optional[str] = None
    formatted_time: Optional[str] = None
    clean_text: Optional[str] = None
    error: Optional[str] = None


class TimeRangeSearchRequest(BaseModel):
    """时间范围搜索请求"""
    user_id: str = Field(..., description="用户ID")
    start_time: Optional[str] = Field(None, description="开始时间 (ISO格式或自然语言如'昨天')")
    end_time: Optional[str] = Field(None, description="结束时间 (ISO格式或自然语言如'今天')")
    keyword: Optional[str] = Field(None, description="关键词搜索")
    memory_type: Optional[str] = Field(None, description="记忆类型过滤")
    limit: int = Field(50, ge=1, le=200, description="返回数量限制")


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    version: str
    timestamp: str


class NowResponse(BaseModel):
    """当前时间响应"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class DeleteByDateRequest(BaseModel):
    """按日期删除记忆请求"""
    user_id: str = Field(..., description="用户ID")
    date: str = Field(..., description="日期 (YYYY-MM-DD 或自然语言如'3月15日')")
    memory_types: Optional[List[str]] = Field(None, description="要删除的记忆类型，默认为['event', 'task', 'reminder']")


class DeleteByDateResponse(BaseModel):
    """按日期删除记忆响应"""
    success: bool
    deleted_count: int = 0
    message: str
    error: Optional[str] = None


class CreateTaskRequest(BaseModel):
    """创建任务请求"""
    user_id: str = Field(..., description="用户ID")
    content: str = Field(..., description="任务/提醒内容")
    reminder_time: str = Field(..., description="提醒时间 (ISO格式或自然语言如'明天下午3点')")
    title: Optional[str] = Field(None, description="任务标题")


class CreateTaskResponse(BaseModel):
    """创建任务响应"""
    success: bool
    task_id: Optional[str] = None
    scheduled_time: Optional[str] = None
    message: str
    error: Optional[str] = None


class TaskItem(BaseModel):
    """任务项"""
    task_id: str
    task_type: str
    content: str
    title: Optional[str] = None
    scheduled_time: Optional[str] = None
    status: str
    is_recurring: bool = False


class ListTasksResponse(BaseModel):
    """获取任务列表响应"""
    success: bool
    data: List[TaskItem] = []
    total: int = 0
    error: Optional[str] = None


class CancelTaskResponse(BaseModel):
    """取消任务响应"""
    success: bool
    message: str
    error: Optional[str] = None


class LarkConfigRequest(BaseModel):
    """飞书配置请求"""
    user_id: str = Field(..., description="用户ID")
    app_id: str = Field(..., description="飞书应用 App ID")
    app_secret: str = Field(..., description="飞书应用 App Secret")
    receive_id: str = Field(..., description="接收者ID (open_id/user_id/union_id)")
    receive_id_type: str = Field("open_id", description="接收者ID类型")
    encrypt_key: Optional[str] = Field(None, description="加密密钥（可选）")
    verification_token: Optional[str] = Field(None, description="验证令牌（可选）")


class LarkConfigResponse(BaseModel):
    """飞书配置响应"""
    success: bool
    message: str
    error: Optional[str] = None


class LarkTestResponse(BaseModel):
    """飞书测试响应"""
    success: bool
    message: str
    error: Optional[str] = None


class LarkSendRequest(BaseModel):
    """飞书发送消息请求"""
    user_id: str = Field(..., description="用户ID")
    content: str = Field(..., description="消息内容")
    title: Optional[str] = Field(None, description="消息标题")


class PlatformStatusResponse(BaseModel):
    """平台状态响应"""
    success: bool
    lark: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ============== 文档上传相关模型 ==============

class UploadDocumentResponse(BaseModel):
    """上传文档响应"""
    success: bool
    document_id: Optional[str] = None
    message: str
    error: Optional[str] = None
    is_duplicate: bool = False  # 是否重复文件


class ConfirmActionItemsRequest(BaseModel):
    """确认待办事项请求"""
    user_id: str = Field(..., description="用户ID")
    document_id: str = Field(..., description="文档ID")
    selected_indices: List[int] = Field(..., description="选中的待办索引")
    reminder_times: Dict[str, str] = Field(default_factory=dict, description="待办索引->提醒时间")


class DocumentListItem(BaseModel):
    """文档列表项"""
    document_id: str
    filename: str
    file_size: int
    uploaded_at: str
    status: str
    source: str
    doc_type: str


class DocumentListResponse(BaseModel):
    """文档列表响应"""
    success: bool
    data: List[DocumentListItem] = []
    total: int = 0
    error: Optional[str] = None


# ============== API 路由 ==============

# ============== WebSocket 接口 ==============

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """
    WebSocket 连接端点

    用于实时接收提醒通知
    支持断线重连和离线消息同步
    """
    await manager.connect(user_id, websocket)

    # 发送连接成功消息和离线消息数量
    offline_count = manager.get_offline_message_count(user_id)
    await websocket.send_json({
        "type": "connected",
        "user_id": user_id,
        "timestamp": datetime.now().isoformat(),
        "offline_messages": offline_count,
        "message": f"连接成功{'，有 ' + str(offline_count) + ' 条离线消息' if offline_count > 0 else ''}"
    })

    print(f"[WebSocket] 用户 {user_id} 已连接{'，有 ' + str(offline_count) + ' 条离线消息' if offline_count > 0 else ''}，等待消息...")

    try:
        while True:
            # 接收心跳消息
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                print(f"[WebSocket] 收到来自 {user_id} 的消息: {data}")

                # 解析客户端消息
                try:
                    msg = json.loads(data) if data.startswith('{') else {"type": "text", "data": data}
                except:
                    msg = {"type": "text", "data": data}

                # 处理不同类型的消息
                if msg.get("type") == "ping" or data == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": datetime.now().isoformat()})
                elif msg.get("type") == "get_status":
                    # 返回连接状态
                    await websocket.send_json({
                        "type": "status",
                        "connected": True,
                        "offline_messages": manager.get_offline_message_count(user_id),
                        "timestamp": datetime.now().isoformat()
                    })
                else:
                    # 默认回复pong
                    await websocket.send_json({"type": "pong", "timestamp": datetime.now().isoformat()})

            except asyncio.TimeoutError:
                # 60秒没有消息，发送心跳保持连接
                print(f"[WebSocket] 用户 {user_id} 60秒无消息，发送心跳")
                try:
                    await websocket.send_json({"type": "ping", "timestamp": datetime.now().isoformat()})
                    print(f"[WebSocket] 心跳已发送给用户 {user_id}")
                except Exception as e:
                    print(f"[WebSocket] 发送心跳失败，连接可能已断开: {e}")
                    break
    except WebSocketDisconnect as e:
        print(f"[WebSocket] 用户 {user_id} 断开连接 (code: {e.code if hasattr(e, 'code') else 'unknown'})")
    except Exception as e:
        print(f"[WebSocket] 用户 {user_id} 连接异常: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        manager.disconnect(user_id)


# ============== API 路由 ==============

@app.get("/", response_model=HealthResponse)
async def root():
    """根路径 - 返回服务状态"""
    return HealthResponse(
        status="running",
        version="1.0.0",
        timestamp=datetime.now().isoformat()
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查接口"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now().isoformat()
    )


@app.get("/api/now", response_model=NowResponse)
async def get_current_time():
    """
    获取当前时间信息

    返回当前日期、时间、星期几等详细信息
    """
    try:
        now = get_now()
        return NowResponse(
            success=True,
            data=now
        )
    except Exception as e:
        return NowResponse(success=False, error=str(e))


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    对话接口

    与智忆助理进行对话，系统会自动存储对话记忆
    """
    try:
        response = await agent.chat(
            user_id=request.user_id,
            message=request.message,
            stream=request.stream
        )
        return ChatResponse(success=True, data=response)
    except Exception as e:
        return ChatResponse(success=False, error=str(e))


@app.post("/api/remember", response_model=RememberResponse)
async def remember(request: RememberRequest):
    """
    显式存储记忆

    将重要信息显式存储到长期记忆中
    """
    try:
        success = await agent.remember(
            user_id=request.user_id,
            content=request.content,
            memory_type=request.memory_type,
            importance=request.importance
        )

        # 生成一个记忆ID (实际系统中应从存储返回)
        memory_id = f"mem_{uuid.uuid4().hex[:8]}"

        return RememberResponse(
            success=success,
            memory_id=memory_id if success else None
        )
    except Exception as e:
        return RememberResponse(success=False, error=str(e))


@app.post("/api/search", response_model=SearchResponse)
async def search_memories(request: SearchRequest):
    """
    搜索记忆

    根据查询词搜索用户的历史记忆
    """
    try:
        results = await agent.search_memories(
            user_id=request.user_id,
            query=request.query,
            top_k=request.top_k
        )

        memories = [
            MemoryItem(
                memory_id=r['memory_id'],
                content=r['content'],
                type=r['type'],
                created_at=r['created_at'],
                score=r['score']
            )
            for r in results
        ]

        return SearchResponse(
            success=True,
            data=memories,
            total=len(memories)
        )
    except Exception as e:
        return SearchResponse(success=False, error=str(e))


@app.get("/api/stats/{user_id}", response_model=StatsResponse)
async def get_user_stats(user_id: str):
    """
    获取用户统计

    获取用户的记忆统计和画像信息
    """
    try:
        stats = await agent.get_user_stats(user_id)
        return StatsResponse(
            success=True,
            data=UserStats(
                memory=stats['memory'],
                profile=stats['profile']
            )
        )
    except Exception as e:
        return StatsResponse(success=False, error=str(e))


@app.post("/api/clear", response_model=ClearConversationResponse)
async def clear_conversation(request: ClearConversationRequest):
    """
    清空当前对话

    清空工作记忆，开始新的对话
    """
    try:
        await agent.clear_conversation(request.user_id)
        return ClearConversationResponse(
            success=True,
            message="对话已清空"
        )
    except Exception as e:
        return ClearConversationResponse(success=False, message="", error=str(e))


@app.post("/api/evolution", response_model=EvolutionResponse)
async def run_evolution(background_tasks: BackgroundTasks):
    """
    触发记忆演化

    手动触发记忆演化过程（通常由定时任务自动执行）
    """
    try:
        result = await agent.run_evolution()
        return EvolutionResponse(success=True, data=result)
    except Exception as e:
        return EvolutionResponse(success=False, error=str(e))


@app.post("/api/users", response_model=CreateUserResponse)
async def create_user(request: CreateUserRequest):
    """
    创建用户

    根据用户名查找或创建用户。如果用户名已存在，返回现有用户ID。
    """
    try:
        # 先根据用户名查找现有用户
        data_dir = agent.config.get('storage', {}).get('data_dir', './data')
        username = request.username.strip()

        # 扫描现有用户画像文件
        import os
        existing_user_id = None
        for filename in os.listdir(data_dir):
            if filename.endswith('_profile.json'):
                # 从文件名提取用户ID (格式: {user_id}_profile.json)
                file_user_id = filename.replace('_profile.json', '')

                # 如果文件名直接匹配用户名，使用这个用户
                if file_user_id == username:
                    existing_user_id = file_user_id
                    print(f"[用户登录] 文件名匹配: {username} -> {existing_user_id}")
                    break

                # 否则检查文件内容中的用户名
                profile_path = os.path.join(data_dir, filename)
                try:
                    with open(profile_path, 'r', encoding='utf-8') as f:
                        profile_data = json.load(f)
                        # 检查用户名是否匹配 (支持 name 或 username 字段)
                        profile_name = profile_data.get('name') or profile_data.get('username')
                        if profile_name == username:
                            existing_user_id = profile_data.get('user_id') or file_user_id
                            print(f"[用户登录] 文件内容匹配: {username} -> {existing_user_id}")
                            break
                except Exception:
                    continue

        if existing_user_id:
            # 返回现有用户
            return CreateUserResponse(
                success=True,
                user_id=existing_user_id,
                username=username
            )

        # 生成新用户ID
        user_id = f"user_{uuid.uuid4().hex[:8]}"

        # 初始化用户画像
        profile = await agent.profile_manager.get_profile(user_id)
        profile.name = username
        await agent.profile_manager.save_profile(profile)

        print(f"[用户登录] 创建新用户: {username} -> {user_id}")

        return CreateUserResponse(
            success=True,
            user_id=user_id,
            username=username
        )
    except Exception as e:
        return CreateUserResponse(success=False, error=str(e))


def memory_entry_to_dict(entry) -> Dict[str, Any]:
    """将MemoryEntry转换为字典"""
    return {
        "memory_id": entry.memory_id,
        "user_id": entry.user_id,
        "content": entry.content,
        "memory_type": entry.memory_type.value,
        "state": entry.state.value,
        "created_at": entry.created_at.isoformat(),
        "updated_at": entry.updated_at.isoformat(),
        "last_accessed": entry.last_accessed.isoformat(),
        "confidence": entry.confidence,
        "importance": entry.importance,
        "weight": entry.weight,
        "access_count": entry.access_count,
        "tags": entry.tags,
        "related_entities": entry.related_entities,
        "source": entry.source,
        "metadata": entry.metadata,
    }


@app.get("/api/users/{user_id}/memories")
async def get_user_memories(
    user_id: str,
    memory_type: Optional[str] = Query(None, description="记忆类型过滤"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    获取用户记忆列表

    分页获取用户的记忆列表
    """
    try:
        # 从元数据存储获取记忆
        entries = await agent.memory_storage.metadata_store.get_memories_by_user(
            user_id=user_id,
            limit=limit,
            offset=offset
        )

        # 转换为字典列表
        memories = [memory_entry_to_dict(entry) for entry in entries]

        # 根据类型过滤
        if memory_type:
            memories = [m for m in memories if m["memory_type"] == memory_type]

        return {
            "success": True,
            "data": memories,
            "total": len(memories),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/parse-time", response_model=ParseTimeResponse)
async def parse_time_endpoint(request: ParseTimeRequest):
    """
    解析自然语言时间为具体时间

    支持格式如：今天下午3点、明天早上、2024年3月15日下午、3天后
    """
    try:
        # 提取时间信息
        clean_text, parsed_time = time_parser.extract_time_info(request.text)

        if parsed_time:
            return ParseTimeResponse(
                success=True,
                original_text=request.text,
                parsed_time=parsed_time.isoformat(),
                formatted_time=time_parser.format_time(parsed_time, 'human'),
                clean_text=clean_text
            )
        else:
            return ParseTimeResponse(
                success=False,
                original_text=request.text,
                error="无法从文本中解析出时间信息"
            )
    except Exception as e:
        return ParseTimeResponse(
            success=False,
            original_text=request.text,
            error=str(e)
        )


@app.post("/api/search-by-time")
async def search_by_time(request: TimeRangeSearchRequest):
    """
    按时间范围搜索记忆

    支持自然语言时间描述，如开始时间='昨天'，结束时间='今天'
    """
    try:
        # 解析开始时间
        start_time = None
        if request.start_time:
            start_time = time_parser.parse(request.start_time)
            if not start_time:
                # 尝试作为ISO格式解析
                try:
                    start_time = datetime.fromisoformat(request.start_time)
                except ValueError:
                    return {"success": False, "error": f"无法解析开始时间: {request.start_time}"}

        # 解析结束时间
        end_time = None
        if request.end_time:
            end_time = time_parser.parse(request.end_time)
            if not end_time:
                try:
                    end_time = datetime.fromisoformat(request.end_time)
                except ValueError:
                    return {"success": False, "error": f"无法解析结束时间: {request.end_time}"}

        # 如果没有提供结束时间，默认为现在
        if not end_time:
            end_time = datetime.now()

        # 如果没有提供开始时间，默认为7天前
        if not start_time:
            start_time = end_time - timedelta(days=7)

        # 执行搜索
        entries = await agent.memory_storage.search_memories(
            user_id=request.user_id,
            keyword=request.keyword,
            start_time=start_time,
            end_time=end_time,
            memory_type=request.memory_type,
            limit=request.limit
        )

        memories = [memory_entry_to_dict(entry) for entry in entries]

        return {
            "success": True,
            "data": memories,
            "total": len(memories),
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat()
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/delete-by-date", response_model=DeleteByDateResponse)
async def delete_memories_by_date(request: DeleteByDateRequest):
    """
    按日期删除记忆

    删除指定日期的所有安排、任务等记忆
    支持自然语言日期，如"3月15日"、"明天"、"今天"
    """
    try:
        # 解析日期
        from memory_assistant.core.content_filter import ContentFilter

        date_str = ContentFilter.extract_delete_date(request.date)

        if not date_str:
            # 尝试直接解析 ISO 格式
            try:
                dt = datetime.fromisoformat(request.date)
                date_str = dt.strftime('%Y-%m-%d')
            except ValueError:
                return DeleteByDateResponse(
                    success=False,
                    deleted_count=0,
                    message="",
                    error=f"无法解析日期: {request.date}"
                )

        # 确定要删除的记忆类型
        memory_types = request.memory_types
        if not memory_types:
            memory_types = ['event', 'task', 'reminder']

        # 执行删除
        deleted_count = await agent.memory_storage.delete_memories_by_date(
            user_id=request.user_id,
            date_str=date_str,
            memory_types=memory_types
        )

        # 构建日期显示
        date_display = date_str.replace('-', '年', 1).replace('-', '月') + '日'

        if deleted_count > 0:
            message = f"已删除 {date_display} 的 {deleted_count} 条安排。"
        else:
            message = f"没有找到 {date_display} 的安排，无需删除。"

        return DeleteByDateResponse(
            success=True,
            deleted_count=deleted_count,
            message=message
        )

    except Exception as e:
        return DeleteByDateResponse(
            success=False,
            deleted_count=0,
            message="",
            error=str(e)
        )


@app.post("/api/structured-search", response_model=SearchStructuredResponse)
async def search_structured_memories(request: SearchStructuredRequest):
    """
    搜索结构化记忆

    支持基于时间、地点、人物、类型等元数据的精确搜索
    """
    try:
        # 构建过滤器
        filters = {}
        if request.memory_type:
            filters['type'] = request.memory_type
        if request.date:
            filters['date'] = request.date
        if request.location:
            filters['location'] = request.location
        if request.person:
            filters['person'] = request.person

        # 使用结构化记忆CRUD搜索
        results = await agent.memory_crud.search(
            user_id=request.user_id,
            query=request.query,
            filters=filters if filters else None,
            top_k=request.top_k
        )

        # 转换为响应格式
        memories = []
        for r in results:
            metadata = r.get('metadata', {})
            memories.append(StructuredMemoryResponse(
                memory_id=r['memory_id'],
                content=r['content'],
                memory_type=r['memory_type'],
                structured_content=metadata.get('structured_content', r['content']),
                datetime=metadata.get('datetime'),
                location=metadata.get('location'),
                people=metadata.get('people', []),
                tags=metadata.get('tags', []),
                importance=r.get('importance', 0.5),
                created_at=r.get('created_at', '')
            ))

        return SearchStructuredResponse(
            success=True,
            data=memories,
            total=len(memories)
        )

    except Exception as e:
        return SearchStructuredResponse(
            success=False,
            error=str(e)
        )


@app.put("/api/memories/{memory_id}", response_model=UpdateMemoryResponse)
async def update_memory(memory_id: str, request: UpdateMemoryRequest):
    """
    更新记忆

    修改已有记忆的内容、类型或元数据
    """
    try:
        # 验证记忆归属
        memory = await agent.memory_crud.read(memory_id)
        if not memory:
            return UpdateMemoryResponse(
                success=False,
                message="",
                error="记忆不存在"
            )

        if memory.get('user_id') != request.user_id:
            return UpdateMemoryResponse(
                success=False,
                message="",
                error="无权修改此记忆"
            )

        # 构建更新数据
        updates = {}
        if request.content is not None:
            updates['content'] = request.content
        if request.importance is not None:
            updates['importance'] = request.importance
        if request.metadata is not None:
            updates['metadata'] = request.metadata

        # 执行更新
        success = await agent.memory_crud.update(memory_id, updates)

        if success:
            return UpdateMemoryResponse(
                success=True,
                message="记忆更新成功"
            )
        else:
            return UpdateMemoryResponse(
                success=False,
                message="",
                error="更新失败"
            )

    except Exception as e:
        return UpdateMemoryResponse(
            success=False,
            message="",
            error=str(e)
        )


@app.delete("/api/memories/{memory_id}")
async def delete_memory_endpoint(memory_id: str, user_id: str):
    """
    删除单条记忆
    """
    try:
        # 验证记忆归属
        memory = await agent.memory_crud.read(memory_id)
        if not memory:
            return {"success": False, "error": "记忆不存在"}

        if memory.get('user_id') != user_id:
            return {"success": False, "error": "无权删除此记忆"}

        # 执行删除
        success = await agent.memory_crud.delete(memory_id)

        if success:
            return {"success": True, "message": "记忆已删除"}
        else:
            return {"success": False, "error": "删除失败"}

    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/tasks", response_model=CreateTaskResponse)
async def create_task(request: CreateTaskRequest):
    """
    创建定时任务/提醒

    支持自然语言时间描述，如"明天下午3点"
    """
    try:
        # 解析时间
        from memory_assistant.utils.time_parser import time_parser
        from datetime import datetime

        reminder_time = None
        parsed_from_nl = False

        # 尝试作为自然语言解析
        reminder_time = time_parser.parse(request.reminder_time)
        if reminder_time:
            parsed_from_nl = True
        else:
            # 尝试作为ISO格式解析
            try:
                reminder_time = datetime.fromisoformat(request.reminder_time)
            except ValueError:
                pass

        if not reminder_time:
            return CreateTaskResponse(
                success=False,
                message="",
                error=f"无法解析时间: {request.reminder_time}。请使用自然语言（如'明天下午3点'）或ISO格式"
            )

        # 检查时间是否已过
        if reminder_time < datetime.now():
            return CreateTaskResponse(
                success=False,
                message="",
                error="提醒时间已经过期，请设置未来的时间"
            )

        # 创建任务
        task = await agent.precise_scheduler.create_reminder(
            user_id=request.user_id,
            content=request.content,
            reminder_time=reminder_time,
            title=request.title or "提醒",
            metadata={'source': 'api'}
        )

        # 同时存储为记忆
        from memory_assistant.utils.datetime_tools import get_now
        await agent.memory_crud.create(
            user_id=request.user_id,
            content=f"设置了提醒: {request.content} 时间: {reminder_time.strftime('%Y-%m-%d %H:%M')}",
            current_time=get_now(),
            memory_type='reminder'
        )

        time_str = time_parser.format_time(reminder_time, 'human')

        return CreateTaskResponse(
            success=True,
            task_id=task.task_id,
            scheduled_time=reminder_time.isoformat(),
            message=f"已设置提醒：{time_str} - {request.content}"
        )

    except Exception as e:
        return CreateTaskResponse(success=False, message="", error=str(e))


@app.get("/api/tasks/{user_id}", response_model=ListTasksResponse)
async def list_user_tasks(
    user_id: str,
    status: Optional[str] = Query(None, description="状态过滤 (pending/scheduled/running/completed)"),
    limit: int = Query(50, ge=1, le=100)
):
    """
    获取用户的任务列表

    获取该用户设置的所有定时提醒和任务
    """
    try:
        from memory_assistant.core.precise_scheduler import TaskStatus

        # 转换状态
        status_filter = None
        if status:
            try:
                status_filter = TaskStatus(status)
            except ValueError:
                return ListTasksResponse(success=False, error=f"无效的状态: {status}")

        tasks = await agent.precise_scheduler.get_user_tasks(
            user_id=user_id,
            status=status_filter,
            limit=limit
        )

        task_items = []
        for task in tasks:
            task_items.append(TaskItem(
                task_id=task.task_id,
                task_type=task.task_type.value,
                content=task.content,
                title=task.title,
                scheduled_time=task.scheduled_time.isoformat() if task.scheduled_time else None,
                status=task.status.value,
                is_recurring=task.is_recurring
            ))

        return ListTasksResponse(
            success=True,
            data=task_items,
            total=len(task_items)
        )

    except Exception as e:
        return ListTasksResponse(success=False, error=str(e))


@app.delete("/api/tasks/{task_id}", response_model=CancelTaskResponse)
async def cancel_task(task_id: str, user_id: str = Query(..., description="用户ID")):
    """
    取消任务

    取消指定的定时提醒或任务
    """
    try:
        # 验证任务归属
        task = await agent.precise_scheduler.get_task(task_id)
        if not task:
            return CancelTaskResponse(success=False, message="", error="任务不存在")

        if task.user_id != user_id:
            return CancelTaskResponse(success=False, message="", error="无权取消此任务")

        # 取消任务
        success = await agent.precise_scheduler.cancel_task(task_id)

        if success:
            return CancelTaskResponse(success=True, message="任务已取消")
        else:
            return CancelTaskResponse(success=False, message="", error="取消任务失败")

    except Exception as e:
        return CancelTaskResponse(success=False, message="", error=str(e))


@app.post("/api/platform/lark/config", response_model=LarkConfigResponse)
async def save_lark_config(request: LarkConfigRequest):
    """
    保存飞书配置

    配置飞书机器人，用于接收提醒消息
    """
    try:
        from memory_assistant.platform.lark_adapter import LarkConfig

        # 创建配置对象（包含receive_id）
        config = LarkConfig(
            app_id=request.app_id,
            app_secret=request.app_secret,
            receive_id=request.receive_id,
            receive_id_type=request.receive_id_type,
            encrypt_key=request.encrypt_key,
            verification_token=request.verification_token,
            enabled=True
        )

        # 保存到数据库
        success = await platform_manager.save_lark_config(request.user_id, config)

        if success:
            return LarkConfigResponse(
                success=True,
                message="飞书配置已保存"
            )
        else:
            return LarkConfigResponse(
                success=False,
                message="",
                error="保存配置失败"
            )

    except Exception as e:
        return LarkConfigResponse(success=False, message="", error=str(e))


@app.post("/api/platform/lark/test", response_model=LarkTestResponse)
async def test_lark_connection(request: LarkSendRequest):
    """
    测试飞书连接

    发送测试消息验证飞书配置是否正确
    """
    try:
        # 获取用户的飞书适配器
        adapter = await platform_manager.get_lark_adapter(request.user_id)

        if not adapter:
            return LarkTestResponse(
                success=False,
                message="",
                error="未找到飞书配置，请先配置飞书"
            )

        # 获取配置
        config = await platform_manager.get_lark_config(request.user_id)
        if not config:
            return LarkTestResponse(
                success=False,
                message="",
                error="配置不存在"
            )

        if not config.receive_id:
            return LarkTestResponse(
                success=False,
                message="",
                error="未设置接收者ID"
            )

        # 发送测试消息
        content = request.content or "这是一条测试消息，来自智忆助理！"
        success, error_msg = await adapter.send_message(
            receive_id=config.receive_id,
            content=f"【测试】{content}",
            msg_type="text"
        )

        if success:
            return LarkTestResponse(
                success=True,
                message="测试消息已发送，请检查飞书"
            )
        else:
            return LarkTestResponse(
                success=False,
                message="",
                error=f"发送失败: {error_msg}"
            )

    except Exception as e:
        return LarkTestResponse(success=False, message="", error=str(e))


@app.get("/api/platform/status", response_model=PlatformStatusResponse)
async def get_platform_status(user_id: str = Query(..., description="用户ID")):
    """
    获取平台接入状态

    查看用户已配置的第三方平台
    """
    try:
        # 获取飞书配置
        lark_config = await platform_manager.get_lark_config(user_id)

        result = {
            "success": True,
            "lark": None
        }

        if lark_config:
            result["lark"] = {
                "enabled": lark_config.enabled,
                "app_id": lark_config.app_id[:8] + "..." if lark_config.app_id else None,
                "receive_id_type": lark_config.receive_id_type,
                "created_at": lark_config.created_at
            }

        return PlatformStatusResponse(**result)

    except Exception as e:
        return PlatformStatusResponse(success=False, error=str(e))


@app.delete("/api/platform/lark/config")
async def delete_lark_config(user_id: str = Query(..., description="用户ID")):
    """
    删除飞书配置
    """
    try:
        success = await platform_manager.delete_config(user_id, "lark")

        if success:
            return {"success": True, "message": "飞书配置已删除"}
        else:
            return {"success": False, "error": "删除失败"}

    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/platform/lark/status")
async def get_lark_status(user_id: str = Query(..., description="用户ID")):
    """
    获取用户飞书配置状态

    前端可以在设置待办前调用此接口检查用户是否已配置飞书
    """
    try:
        if not platform_manager:
            return {"success": False, "error": "平台管理器未初始化"}

        config = await platform_manager.get_lark_config(user_id)

        if config and config.enabled and config.receive_id:
            return {
                "success": True,
                "data": {
                    "configured": True,
                    "receive_id_type": config.receive_id_type,
                    # 不返回敏感信息如 app_secret
                    "app_id": config.app_id[:8] + "..." if config.app_id else None
                }
            }
        else:
            return {
                "success": True,
                "data": {
                    "configured": False,
                    "message": "用户尚未配置飞书通知，任务创建后不会收到飞书提醒"
                }
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


# ============== 文档上传相关接口 =============="

@app.post("/api/documents/upload", response_model=UploadDocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    source: str = Form("web")
):
    """
    上传会议记录文档

    支持格式: PDF, DOCX, TXT, MD
    文件会被保存，然后异步处理
    """
    try:
        # 保存临时文件
        temp_dir = "./temp/uploads"
        os.makedirs(temp_dir, exist_ok=True)

        temp_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{file.filename}")

        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # 保存到文档存储
        from memory_assistant.storage.document_store import DocumentStore
        doc_store = DocumentStore(agent.config.get('storage', {}).get('data_dir', './data'))

        save_result = await doc_store.save_file(
            file_path=temp_path,
            user_id=user_id,
            source=source,
            original_filename=file.filename
        )

        # 清理临时文件
        os.remove(temp_path)

        if save_result["is_duplicate"]:
            return UploadDocumentResponse(
                success=True,
                document_id=save_result["document_id"],
                message="该文件已存在，将使用已有解析结果",
                is_duplicate=True
            )

        return UploadDocumentResponse(
            success=True,
            document_id=save_result["document_id"],
            message="文件上传成功，请使用WebSocket连接处理进度",
            is_duplicate=False
        )

    except Exception as e:
        return UploadDocumentResponse(success=False, message="", error=str(e))


@app.websocket("/ws/documents/{document_id}")
async def document_processing_websocket(websocket: WebSocket, document_id: str):
    """
    WebSocket流式处理文档

    实时返回解析进度和结果
    """
    await websocket.accept()

    try:
        # 获取文档信息
        from memory_assistant.storage.document_store import DocumentStore
        from memory_assistant.ingestion.document_processor import DocumentProcessor
        import asyncio

        doc_store = DocumentStore(agent.config.get('storage', {}).get('data_dir', './data'))
        doc_info = await doc_store.get_document(document_id)

        if not doc_info:
            await websocket.send_json({
                "stage": "error",
                "status": "error",
                "data": {"error": "文档不存在"}
            })
            await websocket.close()
            return

        # 检查文档是否已处理完成
        if doc_info.get('status') == 'completed' and doc_info.get('analysis_result'):
            import json
            import asyncio
            print(f"[WebSocket] 文档 {document_id} 已处理完成，直接返回结果")
            await websocket.send_json({
                "stage": "loading",
                "progress": 0.1,
                "data": {"message": "文档已存在，加载解析结果..."},
                "status": "completed"
            })
            await asyncio.sleep(0.5)  # 给前端时间接收消息
            await websocket.send_json({
                "stage": "completed",
                "progress": 1.0,
                "data": {
                    "document_id": document_id,
                    "result": json.loads(doc_info['analysis_result']),
                    "pending_actions": {
                        "action_items": 0,
                        "need_confirmation": True
                    }
                },
                "status": "completed"
            })
            await asyncio.sleep(0.5)  # 给前端时间接收消息
            await websocket.close()
            return

        # 创建消息队列
        message_queue = asyncio.Queue()
        processing_complete = asyncio.Event()

        # 文档处理任务
        async def process_document():
            try:
                print(f"[WebSocket] 开始处理文档: {document_id}")
                processor = DocumentProcessor(agent)
                event_count = 0
                async for event in processor.process_file(
                    file_path=doc_info["file_path"],
                    user_id=doc_info["user_id"],
                    metadata={
                        "document_id": document_id,
                        "filename": doc_info["filename"],
                        "source": doc_info["source"]
                    },
                    document_store=doc_store
                ):
                    event_count += 1
                    print(f"[WebSocket] 生成事件 #{event_count}: {event.get('stage')}")
                    await message_queue.put(event)
                    if event["stage"] in ["error", "completed"]:
                        print(f"[WebSocket] 处理结束: {event.get('stage')}")
                        break
                print(f"[WebSocket] 共生成 {event_count} 个事件")
            except Exception as e:
                print(f"[WebSocket] 处理异常: {e}")
                import traceback
                traceback.print_exc()
                await message_queue.put({
                    "stage": "error",
                    "status": "error",
                    "data": {"error": str(e)}
                })
            finally:
                processing_complete.set()

        # 启动处理任务
        process_task = asyncio.create_task(process_document())

        # 发送消息到客户端
        try:
            while True:
                # 等待消息或处理完成
                try:
                    event = await asyncio.wait_for(
                        message_queue.get(),
                        timeout=1.0
                    )
                    await websocket.send_json(event)
                    if event["stage"] in ["error", "completed"]:
                        break
                except asyncio.TimeoutError:
                    # 检查处理是否完成
                    if processing_complete.is_set() and message_queue.empty():
                        break
                    # 发送心跳保持连接
                    try:
                        await websocket.send_json({
                            "stage": "heartbeat",
                            "status": "processing"
                        })
                    except Exception as e:
                        print(f"[WebSocket] 发送心跳失败: {e}")
                        break

                if processing_complete.is_set() and message_queue.empty():
                    break
        except Exception as e:
            print(f"[WebSocket] 发送消息失败: {e}")

        # 清理
        process_task.cancel()
        try:
            await process_task
        except asyncio.CancelledError:
            pass

        await websocket.close()

    except Exception as e:
        print(f"[WebSocket] 异常: {e}")
        try:
            await websocket.send_json({
                "stage": "error",
                "status": "error",
                "data": {"error": str(e)}
            })
            await websocket.close()
        except:
            pass


@app.post("/api/documents/confirm-actions")
async def confirm_action_items(request: ConfirmActionItemsRequest):
    """
    确认并创建会议待办任务

    用户在前端选择要创建的待办事项和提醒时间
    """
    try:
        from memory_assistant.storage.document_store import DocumentStore
        from memory_assistant.ingestion.document_processor import DocumentProcessor

        # 检查用户是否配置了飞书（如果配置了平台管理器）
        lark_config = None
        if platform_manager:
            lark_config = await platform_manager.get_lark_config(request.user_id)
            print(f"[confirm-actions] 用户 {request.user_id} 飞书配置: {'已配置' if lark_config else '未配置'}")

        doc_store = DocumentStore(agent.config.get('storage', {}).get('data_dir', './data'))
        processor = DocumentProcessor(agent)

        result = await processor.confirm_action_items(
            user_id=request.user_id,
            document_id=request.document_id,
            selected_items=request.selected_indices,
            reminder_times=request.reminder_times,
            document_store=doc_store
        )

        # 如果有任务创建成功但没有飞书配置，添加警告
        warning = None
        if result.get("created_count", 0) > 0 and not lark_config:
            warning = "提醒任务已创建，但您尚未配置飞书通知。任务到期时不会收到飞书提醒，请先在设置中配置飞书应用。"
            print(f"[confirm-actions] 警告: {warning}")

        return {
            "success": True,
            "data": result,
            "warning": warning
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/documents/{user_id}", response_model=DocumentListResponse)
async def list_user_documents(
    user_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """获取用户的文档列表"""
    try:
        from memory_assistant.storage.document_store import DocumentStore
        doc_store = DocumentStore(agent.config.get('storage', {}).get('data_dir', './data'))

        documents = await doc_store.get_user_documents(user_id, limit, offset)

        # 转换为响应格式
        items = []
        for doc in documents:
            items.append(DocumentListItem(
                document_id=doc["document_id"],
                filename=doc["filename"],
                file_size=doc["file_size"],
                uploaded_at=doc["uploaded_at"],
                status=doc["status"],
                source=doc["source"],
                doc_type=doc["doc_type"]
            ))

        return DocumentListResponse(
            success=True,
            data=items,
            total=len(items)
        )

    except Exception as e:
        return DocumentListResponse(success=False, error=str(e))


# ============== 静态文件服务 ==============

# 前端静态文件路径配置
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "frontend", "dist")
FRONTEND_SRC = os.path.join(os.path.dirname(__file__), "frontend", "src")

# 挂载前端静态文件 (仅当存在构建后的 dist 目录时)
if os.path.exists(FRONTEND_DIST) and os.path.exists(os.path.join(FRONTEND_DIST, "index.html")):
    # Vue 生产构建版本 - 挂载 assets 到 /app/assets
    from fastapi.staticfiles import StaticFiles
    app.mount("/app/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/app", response_class=FileResponse)
    async def serve_frontend_root():
        """服务前端主页面"""
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

    @app.get("/app/{path:path}", response_class=FileResponse)
    async def serve_frontend_spa(path: str):
        """服务前端 SPA 路由"""
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

    print(f"[前端] 使用构建版本: {FRONTEND_DIST}")
else:
    print(f"[前端] 警告: 未找到构建后的前端文件，请运行: cd frontend && npm install && npm run build")
    print(f"[前端] 或直接访问: http://localhost:5173 (开发服务器)")

    @app.get("/app")
    async def frontend_not_built():
        """提示前端未构建"""
        return {
            "status": "error",
            "message": "前端未构建",
            "instructions": [
                "1. cd frontend",
                "2. npm install",
                "3. npm run build",
                "或者直接使用开发服务器: npm run dev (访问 http://localhost:5173)"
            ]
        }


# ============== 主入口 ==============

if __name__ == "__main__":
    import uvicorn

    print("启动智忆助理服务...")
    print("API文档: http://localhost:8000/docs")
    print("前端界面: http://localhost:8000/app")

    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
