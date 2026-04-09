"""
飞书(Lark)平台适配器
支持通过飞书机器人发送提醒消息
"""
import json
import asyncio
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime

try:
    import requests
except ImportError:
    requests = None


@dataclass
class LarkConfig:
    """飞书配置"""
    app_id: str
    app_secret: str
    encrypt_key: Optional[str] = None
    verification_token: Optional[str] = None
    receive_id_type: str = "open_id"  # open_id / user_id / union_id / email / chat_id
    receive_id: Optional[str] = None  # 接收者ID
    enabled: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'app_id': self.app_id,
            'app_secret': self.app_secret,
            'encrypt_key': self.encrypt_key,
            'verification_token': self.verification_token,
            'receive_id_type': self.receive_id_type,
            'receive_id': self.receive_id,
            'enabled': self.enabled,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LarkConfig':
        return cls(
            app_id=data.get('app_id', ''),
            app_secret=data.get('app_secret', ''),
            encrypt_key=data.get('encrypt_key'),
            verification_token=data.get('verification_token'),
            receive_id_type=data.get('receive_id_type', 'open_id'),
            receive_id=data.get('receive_id'),
            enabled=data.get('enabled', True),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )


class LarkAdapter:
    """
    飞书平台适配器

    使用方法:
    1. 在飞书开放平台创建应用: https://open.feishu.cn/app
    2. 获取 App ID 和 App Secret
    3. 给应用添加权限: im:message:send, im:message.group_msg
    4. 将用户添加到应用可见范围
    5. 获取用户的 open_id
    """

    BASE_URL = "https://open.feishu.cn/open-apis"

    def __init__(self, config: LarkConfig):
        self.config = config
        self._access_token: Optional[str] = None
        self._token_expire_time: Optional[datetime] = None

        if requests is None:
            raise ImportError("请先安装 requests: pip install requests")

    def _get_access_token(self) -> str:
        """获取飞书访问令牌（带缓存）"""
        # 检查缓存的token是否有效
        if self._access_token and self._token_expire_time:
            if datetime.now() < self._token_expire_time:
                return self._access_token

        # 重新获取token
        url = f"{self.BASE_URL}/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json"}
        data = {
            "app_id": self.config.app_id,
            "app_secret": self.config.app_secret
        }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)
            result = response.json()

            if result.get("code") == 0:
                self._access_token = result["tenant_access_token"]
                # token有效期通常是2小时，我们提前10分钟过期
                expire = result.get("expire", 7200)
                self._token_expire_time = datetime.now()
                return self._access_token
            else:
                raise Exception(f"获取token失败: {result}")

        except Exception as e:
            raise Exception(f"获取飞书token失败: {e}")

    async def send_message(self, receive_id: str, content: str, msg_type: str = "text") -> tuple[bool, str]:
        """
        发送消息到飞书

        Args:
            receive_id: 接收者ID (open_id/user_id/union_id/email/chat_id)
            content: 消息内容
            msg_type: 消息类型 (text/post/image/file等)

        Returns:
            (是否成功, 错误信息)
        """
        if not self.config.enabled:
            return False, "配置已禁用"

        try:
            # 在异步环境中调用同步requests
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                self._send_message_sync,
                receive_id,
                content,
                msg_type
            )
        except Exception as e:
            error_msg = str(e)
            print(f"[飞书适配器] 发送消息失败: {error_msg}")
            return False, error_msg

    def _send_message_sync(self, receive_id: str, content: str, msg_type: str) -> tuple[bool, str]:
        """同步发送消息"""
        url = f"{self.BASE_URL}/im/v1/messages"

        try:
            # 获取access token
            token = self._get_access_token()
        except Exception as e:
            return False, f"获取access token失败: {str(e)}"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        params = {"receive_id_type": self.config.receive_id_type}

        # 构建消息内容
        if msg_type == "text":
            content_json = json.dumps({"text": content})
        elif msg_type == "post":
            # 富文本消息
            content_json = json.dumps(content)
        else:
            content_json = json.dumps(content)

        data = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": content_json
        }

        try:
            response = requests.post(
                url,
                headers=headers,
                params=params,
                json=data,
                timeout=10
            )
            result = response.json()

            if result.get("code") == 0:
                print(f"[飞书适配器] 消息发送成功")
                return True, ""
            else:
                error_msg = f"飞书API返回错误: code={result.get('code')}, msg={result.get('msg', '未知错误')}"
                print(f"[飞书适配器] {error_msg}")
                return False, error_msg

        except Exception as e:
            error_msg = f"请求异常: {str(e)}"
            print(f"[飞书适配器] {error_msg}")
            return False, error_msg

    async def send_reminder_card(self, receive_id: str, title: str, content: str,
                                  task_time: Optional[str] = None) -> bool:
        """
        发送提醒卡片（富文本格式）

        Args:
            receive_id: 接收者ID
            title: 提醒标题
            content: 提醒内容
            task_time: 任务时间（可选）
        """
        # 构建富文本卡片
        card_content = {
            "zh_cn": {
                "title": {
                    "tag": "plain_text",
                    "content": f"[提醒] {title}"
                },
                "content": [
                    [
                        {
                            "tag": "text",
                            "text": content,
                            "style": ["bold"]
                        }
                    ]
                ]
            }
        }

        if task_time:
            card_content["zh_cn"]["content"].append([
                {
                    "tag": "text",
                    "text": f"\n时间: {task_time}",
                    "style": []
                }
            ])

        return await self.send_message(receive_id, card_content, msg_type="post")

    async def verify_connection(self) -> tuple[bool, str]:
        """
        验证飞书连接是否正常

        Returns:
            (是否成功, 错误信息)
        """
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._verify_connection_sync)
        except Exception as e:
            return False, str(e)

    async def handle_file_message(self, user_id: str, file_info: dict, agent=None) -> str:
        """
        处理飞书收到的文件消息

        Args:
            user_id: 用户ID
            file_info: 文件信息，包含 file_key, file_name 等
            agent: MemoryMateAgent 实例
        """
        file_key = file_info.get('file_key')
        file_name = file_info.get('file_name', 'unknown')

        try:
            # 1. 下载文件
            file_path = await self._download_file(file_key, file_name)

            # 2. 保存到文档存储
            from ..storage.document_store import DocumentStore
            from ..ingestion.document_processor import DocumentProcessor

            data_dir = "./data"
            doc_store = DocumentStore(data_dir)
            save_result = await doc_store.save_file(
                file_path=file_path,
                user_id=user_id,
                source="lark",
                original_filename=file_name
            )

            # 3. 异步处理文档
            if agent:
                processor = DocumentProcessor(agent)

                # 收集所有结果
                final_result = None
                async for event in processor.process_file(
                    file_path=file_path,
                    user_id=user_id,
                    metadata={
                        "document_id": save_result["document_id"],
                        "filename": file_name,
                        "source": "lark"
                    },
                    document_store=doc_store
                ):
                    if event["status"] == "completed":
                        final_result = event["data"]

                # 4. 构建回复消息
                if final_result and "result" in final_result:
                    result = final_result["result"]

                    message = f"""📄 会议记录解析完成！

📌 会议主题：{result.get('meeting_title', '未识别')}

📝 摘要：
{result.get('summary', '')}

✅ 关键决策：
"""
                    for i, decision in enumerate(result.get('key_decisions', []), 1):
                        message += f"{i}. {decision}\n"

                    action_items = result.get('action_items', [])
                    if action_items:
                        message += f"\n📋 发现 {len(action_items)} 项待办任务：\n"
                        for i, item in enumerate(action_items, 1):
                            message += f"{i}. {item.get('content', '')}"
                            if item.get('assignee'):
                                message += f" (负责人：{item['assignee']})"
                            message += "\n"

                        message += "\n💡 请在前端界面确认要添加的待办事项和提醒时间。"

                    return message
                else:
                    return "文档解析失败，请稍后重试。"
            else:
                return "文档已保存，但无法进行处理（Agent未配置）。"

        except Exception as e:
            return f"处理文件时出错：{str(e)}"

    async def _download_file(self, file_key: str, file_name: str) -> str:
        """从飞书下载文件"""
        import aiohttp
        import os

        # 获取文件下载URL
        url = f"{self.BASE_URL}/im/v1/files/{file_key}"
        headers = {"Authorization": f"Bearer {self._get_access_token()}"}

        temp_dir = "./temp/lark_files"
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, file_name)

        # 下载文件
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    with open(file_path, 'wb') as f:
                        f.write(await response.read())
                    return file_path
                else:
                    raise Exception(f"下载文件失败: {response.status}")

    def _verify_connection_sync(self) -> tuple[bool, str]:
        """同步验证连接"""
        try:
            token = self._get_access_token()
            if token:
                return True, "连接正常"
            return False, "无法获取访问令牌"
        except Exception as e:
            return False, str(e)

    async def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取用户信息

        Args:
            user_id: 用户ID
        """
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._get_user_info_sync, user_id)
        except Exception as e:
            print(f"[飞书适配器] 获取用户信息失败: {e}")
            return None

    def _get_user_info_sync(self, user_id: str) -> Optional[Dict[str, Any]]:
        """同步获取用户信息"""
        url = f"{self.BASE_URL}/contact/v3/users/{user_id}"
        headers = {"Authorization": f"Bearer {self._get_access_token()}"}

        try:
            response = requests.get(url, headers=headers, timeout=10)
            result = response.json()

            if result.get("code") == 0:
                return result.get("data", {}).get("user")
            return None
        except Exception as e:
            print(f"[飞书适配器] 获取用户信息失败: {e}")
            return None


class PlatformManager:
    """
    平台管理器
    管理用户的第三方平台配置
    """

    def __init__(self, metadata_store=None):
        self.metadata_store = metadata_store
        self._adapters: Dict[str, LarkAdapter] = {}

    async def initialize(self):
        """初始化，创建数据库表"""
        if self.metadata_store:
            await self._ensure_tables()

    async def _ensure_tables(self):
        """确保平台配置表存在"""
        try:
            conn = self.metadata_store.conn
            conn.execute("""
                CREATE TABLE IF NOT EXISTS platform_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    platform_type TEXT NOT NULL,  -- lark/dingtalk/wechat
                    config TEXT NOT NULL,         -- JSON格式
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, platform_type)
                )
            """)
            conn.commit()
        except Exception as e:
            print(f"[平台管理器] 创建表失败: {e}")

    async def save_lark_config(self, user_id: str, config: LarkConfig) -> bool:
        """保存飞书配置"""
        try:
            conn = self.metadata_store.conn
            config.updated_at = datetime.now().isoformat()
            if not config.created_at:
                config.created_at = datetime.now().isoformat()

            # 检查是否已存在
            cursor = conn.execute(
                "SELECT id FROM platform_configs WHERE user_id = ? AND platform_type = ?",
                (user_id, "lark")
            )
            existing = cursor.fetchone()

            if existing:
                # 更新
                conn.execute(
                    """UPDATE platform_configs
                       SET config = ?, updated_at = ?
                       WHERE user_id = ? AND platform_type = ?""",
                    (json.dumps(config.to_dict()), datetime.now().isoformat(), user_id, "lark")
                )
            else:
                # 插入
                conn.execute(
                    """INSERT INTO platform_configs (user_id, platform_type, config)
                       VALUES (?, ?, ?)""",
                    (user_id, "lark", json.dumps(config.to_dict()))
                )

            conn.commit()

            # 更新缓存
            self._adapters[f"{user_id}:lark"] = LarkAdapter(config)

            return True
        except Exception as e:
            print(f"[平台管理器] 保存飞书配置失败: {e}")
            return False

    async def get_lark_config(self, user_id: str) -> Optional[LarkConfig]:
        """获取飞书配置"""
        try:
            if not self.metadata_store:
                print(f"[平台管理器] 错误: metadata_store 未初始化")
                return None

            conn = self.metadata_store.conn
            cursor = conn.execute(
                "SELECT config FROM platform_configs WHERE user_id = ? AND platform_type = ?",
                (user_id, "lark")
            )
            row = cursor.fetchone()

            print(f"[平台管理器] 查询配置: user_id={user_id}, 找到={row is not None}")

            if row:
                config_dict = json.loads(row['config'])
                print(f"[平台管理器] 配置内容: {config_dict}")
                return LarkConfig.from_dict(config_dict)
            return None
        except Exception as e:
            print(f"[平台管理器] 获取飞书配置失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def get_lark_adapter(self, user_id: str) -> Optional[LarkAdapter]:
        """获取飞书适配器（带缓存）"""
        cache_key = f"{user_id}:lark"

        # 检查缓存
        if cache_key in self._adapters:
            return self._adapters[cache_key]

        # 从数据库加载
        config = await self.get_lark_config(user_id)
        if config and config.enabled:
            adapter = LarkAdapter(config)
            self._adapters[cache_key] = adapter
            return adapter

        return None

    async def send_notification(self, user_id: str, title: str, content: str) -> bool:
        """
        发送通知到用户配置的所有平台

        Returns:
            是否至少有一个平台发送成功
        """
        success = False
        print(f"[平台管理器] 开始发送通知给用户: {user_id}, 标题: {title}, 内容: {content}")

        # 尝试飞书
        lark_adapter = await self.get_lark_adapter(user_id)
        print(f"[平台管理器] 飞书适配器: {'已获取' if lark_adapter else '未获取'}")

        if lark_adapter:
            config = await self.get_lark_config(user_id)
            print(f"[平台管理器] 飞书配置: {'已获取' if config else '未获取'}")

            if config:
                print(f"[平台管理器] receive_id: {config.receive_id}")
                print(f"[平台管理器] enabled: {config.enabled}")

                if config.receive_id:
                    full_content = f"[提醒] {title}\n\n{content}"
                    result, error = await lark_adapter.send_message(config.receive_id, full_content)
                    print(f"[平台管理器] 飞书发送结果: {result}, 错误: {error}")
                    if result:
                        success = True
                else:
                    print(f"[平台管理器] 错误: receive_id 为空")
            else:
                print(f"[平台管理器] 错误: 未找到飞书配置")
        else:
            print(f"[平台管理器] 错误: 未找到飞书适配器，用户可能未配置飞书")

        return success

    async def delete_config(self, user_id: str, platform_type: str) -> bool:
        """删除平台配置"""
        try:
            conn = self.metadata_store.conn
            conn.execute(
                "DELETE FROM platform_configs WHERE user_id = ? AND platform_type = ?",
                (user_id, platform_type)
            )
            conn.commit()

            # 清除缓存
            cache_key = f"{user_id}:{platform_type}"
            if cache_key in self._adapters:
                del self._adapters[cache_key]

            return True
        except Exception as e:
            print(f"[平台管理器] 删除配置失败: {e}")
            return False


# 全局实例
_platform_manager: Optional[PlatformManager] = None

def get_platform_manager(metadata_store=None) -> PlatformManager:
    """获取平台管理器实例"""
    global _platform_manager
    if _platform_manager is None:
        _platform_manager = PlatformManager(metadata_store)
    return _platform_manager
