#!/usr/bin/env python3
"""
智忆助理 API 测试脚本
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx

BASE_URL = "http://localhost:8000"

async def test_health():
    """测试健康检查"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")
        print(f"健康检查: {response.status_code}")
        print(f"响应: {response.json()}")
        return response.status_code == 200

async def test_create_user():
    """测试创建用户"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/users",
            json={"username": "测试用户"}
        )
        print(f"\n创建用户: {response.status_code}")
        data = response.json()
        print(f"响应: {data}")
        return data.get("user_id") if data.get("success") else None


async def test_get_user(user_id: str):
    """测试获取用户详情"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/users/{user_id}")
        print(f"\n获取用户详情: {response.status_code}")
        data = response.json()
        print(f"响应: {data}")
        if not data.get("success"):
            return False

        required_fields = {
            "user_id",
            "username",
            "name",
            "total_interactions",
            "interaction_style",
            "has_profile",
        }
        return required_fields.issubset(set((data.get("data") or {}).keys()))


async def test_list_users():
    """测试获取用户列表"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/users", params={"limit": 10, "offset": 0})
        print(f"\n获取用户列表: {response.status_code}")
        data = response.json()
        print(f"响应: {data}")
        if not data.get("success"):
            return False

        users = data.get("data") or []
        if users:
            required_fields = {"user_id", "username", "name", "interaction_style", "has_profile"}
            return required_fields.issubset(set(users[0].keys()))
        return True


async def test_update_user(user_id: str):
    """测试更新用户"""
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{BASE_URL}/api/users/{user_id}",
            json={
                "name": "测试用户-已更新",
                "interaction_style": {
                    "preferred_response_length": "long",
                    "preferred_formality": "formal",
                },
            },
        )
        print(f"\n更新用户: {response.status_code}")
        data = response.json()
        print(f"响应: {data}")
        if not data.get("success"):
            return False

        user = data.get("data") or {}
        style = user.get("interaction_style") or {}
        return (
            user.get("name") == "测试用户-已更新"
            and style.get("preferred_response_length") == "long"
            and style.get("preferred_formality") == "formal"
        )

async def test_chat(user_id: str):
    """测试对话"""
    session_id = None
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/chat",
            json={
                "user_id": user_id,
                "message": "你好，请介绍一下你自己",
                "stream": False
            },
            timeout=60.0
        )
        print(f"\n对话测试: {response.status_code}")
        data = response.json()
        print(f"成功: {data.get('success')}")
        if data.get('success'):
            print(f"回复: {data.get('data')[:100]}...")
            session_id = data.get("session_id")
        else:
            print(f"错误: {data.get('error')}")
        return data.get("success"), session_id


async def test_create_session(user_id: str):
    """测试创建会话"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/sessions",
            json={
                "user_id": user_id,
                "title": "API测试会话"
            }
        )
        print(f"\n创建会话: {response.status_code}")
        data = response.json()
        print(f"响应: {data}")
        if data.get("success") and data.get("data"):
            return data["data"].get("session_id")
        return None


async def test_list_sessions(user_id: str):
    """测试获取会话列表"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/users/{user_id}/sessions")
        print(f"\n获取会话列表: {response.status_code}")
        data = response.json()
        print(f"成功: {data.get('success')}")
        print(f"会话数量: {data.get('total', 0)}")
        if not data.get("success"):
            return False

        sessions = data.get("data") or []
        if sessions:
            required_fields = {"session_id", "user_id", "title", "status", "message_count"}
            return required_fields.issubset(set(sessions[0].keys()))
        return True


async def test_get_session_messages(user_id: str, session_id: str):
    """测试获取会话消息"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/users/{user_id}/sessions/{session_id}/messages")
        print(f"\n获取会话消息: {response.status_code}")
        data = response.json()
        print(f"成功: {data.get('success')}")
        print(f"消息数量: {data.get('total', 0)}")
        if not data.get("success"):
            return False

        messages = data.get("data") or []
        if messages:
            required_fields = {"id", "session_id", "role", "content", "created_at"}
            return required_fields.issubset(set(messages[0].keys()))
        return True


async def test_rename_session(user_id: str, session_id: str):
    """测试重命名会话"""
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{BASE_URL}/api/users/{user_id}/sessions/{session_id}",
            json={"title": "重命名后的API会话"}
        )
        print(f"\n重命名会话: {response.status_code}")
        data = response.json()
        print(f"响应: {data}")
        return data.get("success")


async def test_archive_session(user_id: str, session_id: str):
    """测试归档会话"""
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{BASE_URL}/api/users/{user_id}/sessions/{session_id}",
            json={"status": "archived"}
        )
        print(f"\n归档会话: {response.status_code}")
        data = response.json()
        print(f"响应: {data}")
        return data.get("success")


async def test_delete_session(user_id: str, session_id: str):
    """测试删除会话"""
    async with httpx.AsyncClient() as client:
        response = await client.delete(f"{BASE_URL}/api/users/{user_id}/sessions/{session_id}")
        print(f"\n删除会话: {response.status_code}")
        data = response.json()
        print(f"响应: {data}")
        return data.get("success")

async def test_remember(user_id: str):
    """测试存储记忆"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/remember",
            json={
                "user_id": user_id,
                "content": "我喜欢阅读科幻小说",
                "memory_type": "fact",
                "importance": 0.8
            }
        )
        print(f"\n存储记忆: {response.status_code}")
        data = response.json()
        print(f"响应: {data}")
        return data.get("success")

async def test_search(user_id: str):
    """测试搜索记忆"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/search",
            json={
                "user_id": user_id,
                "query": "科幻小说",
                "top_k": 10
            }
        )
        print(f"\n搜索记忆: {response.status_code}")
        data = response.json()
        print(f"成功: {data.get('success')}")
        print(f"结果数量: {data.get('total', 0)}")
        return data.get("success")

async def test_get_stats(user_id: str):
    """测试获取统计"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/stats/{user_id}")
        print(f"\n获取统计: {response.status_code}")
        data = response.json()
        print(f"成功: {data.get('success')}")
        if data.get('success'):
            print(f"统计: {data.get('data')}")
            memory = (data.get("data") or {}).get("memory") or {}
            required_new_fields = {
                "total_memories",
                "session_turns",
                "cache_entries",
                "memory_types",
                "avg_confidence",
                "avg_importance",
                "legacy",
            }
            if not required_new_fields.issubset(set(memory.keys())):
                return False

            legacy = memory.get("legacy") or {}
            required_legacy_fields = {"working_memory_turns", "short_term_entries"}
            return required_legacy_fields.issubset(set(legacy.keys()))
        return False

async def test_get_memories(user_id: str):
    """测试获取记忆列表"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/users/{user_id}/memories")
        print(f"\n获取记忆列表: {response.status_code}")
        data = response.json()
        print(f"成功: {data.get('success')}")
        print(f"记忆数量: {data.get('total', 0)}")
        return data.get("success")

async def main():
    """运行所有测试"""
    print("="*50)
    print("智忆助理 API 测试")
    print("="*50)

    # 测试健康检查
    if not await test_health():
        print("\n[错误] 服务未启动，请先运行: python api.py")
        return

    # 测试创建用户
    user_id = await test_create_user()
    if not user_id:
        print("\n[错误] 创建用户失败")
        return

    print(f"\n用户ID: {user_id}")

    # 测试各功能
    results = []

    results.append(("获取用户详情", await test_get_user(user_id)))
    results.append(("获取用户列表", await test_list_users()))
    results.append(("更新用户", await test_update_user(user_id)))
    chat_success, chat_session_id = await test_chat(user_id)
    results.append(("对话", chat_success))
    results.append(("存储记忆", await test_remember(user_id)))
    results.append(("搜索记忆", await test_search(user_id)))
    results.append(("获取统计", await test_get_stats(user_id)))
    results.append(("获取记忆列表", await test_get_memories(user_id)))

    created_session_id = await test_create_session(user_id)
    results.append(("创建会话", bool(created_session_id)))
    results.append(("获取会话列表", await test_list_sessions(user_id)))

    if chat_session_id:
        results.append(("获取会话消息", await test_get_session_messages(user_id, chat_session_id)))

    if created_session_id:
        results.append(("重命名会话", await test_rename_session(user_id, created_session_id)))
        results.append(("归档会话", await test_archive_session(user_id, created_session_id)))
        results.append(("删除会话", await test_delete_session(user_id, created_session_id)))

    # 测试结果汇总
    print("\n" + "="*50)
    print("测试结果汇总")
    print("="*50)
    for name, result in results:
        status = "通过" if result else "失败"
        symbol = "✓" if result else "✗"
        print(f"{symbol} {name}: {status}")

    passed = sum(1 for _, r in results if r)
    total = len(results)
    print(f"\n总计: {passed}/{total} 通过")

if __name__ == "__main__":
    asyncio.run(main())
