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

async def test_chat(user_id: str):
    """测试对话"""
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
        else:
            print(f"错误: {data.get('error')}")
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
        return data.get("success")

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

    results.append(("对话", await test_chat(user_id)))
    results.append(("存储记忆", await test_remember(user_id)))
    results.append(("搜索记忆", await test_search(user_id)))
    results.append(("获取统计", await test_get_stats(user_id)))
    results.append(("获取记忆列表", await test_get_memories(user_id)))

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
