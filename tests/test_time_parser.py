#!/usr/bin/env python3
"""
时间解析工具测试脚本
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from memory_assistant.utils.time_parser import time_parser, parse_time, extract_time, format_time

def test_parse_time():
    """测试时间解析功能"""
    print("=" * 50)
    print("时间解析功能测试")
    print("=" * 50)

    test_cases = [
        "今天下午3点",
        "明天早上",
        "后天晚上8点",
        "昨天",
        "3天后",
        "一周后",
        "2024年3月15日下午",
        "早上",
        "晚上",
    ]

    print("\n测试解析:")
    for text in test_cases:
        result = parse_time(text)
        if result:
            formatted = format_time(result, 'full')
            human = format_time(result, 'human')
            print(f"  [OK] '{text}' -> {formatted} ({human})")
        else:
            print(f"  [FAIL] '{text}' -> 解析失败")


def test_extract_time():
    """测试时间提取功能"""
    print("\n" + "=" * 50)
    print("时间提取功能测试")
    print("=" * 50)

    test_cases = [
        "今天下午3点开会讨论项目",
        "明天早上记得去买菜",
        "我昨天去了图书馆",
        "3天后是朋友的生日",
    ]

    print("\n测试提取:")
    for text in test_cases:
        clean_text, parsed_time = extract_time(text)
        if parsed_time:
            formatted = format_time(parsed_time, 'human')
            print(f"  原文: '{text}'")
            print(f"  清洗: '{clean_text}'")
            print(f"  时间: {formatted}")
            print()
        else:
            print(f"  ✗ '{text}' -> 未提取到时间\n")


def test_api_endpoint():
    """测试API端点"""
    print("=" * 50)
    print("API端点测试 (需要先启动服务)")
    print("=" * 50)

    import httpx

    base_url = "http://localhost:8000"

    try:
        # 测试解析时间API
        response = httpx.post(
            f"{base_url}/api/parse-time",
            json={"text": "今天下午3点开会"},
            timeout=5.0
        )
        print(f"\n解析时间API:")
        print(f"  状态码: {response.status_code}")
        print(f"  响应: {response.json()}")

        # 测试时间范围搜索API (需要用户ID)
        print(f"\n时间范围搜索API (示例):")
        print(f"  POST {base_url}/api/search-by-time")
        print(f"  请求体: {{")
        print(f"    'user_id': 'user_001',")
        print(f"    'start_time': '昨天',")
        print(f"    'end_time': '今天',")
        print(f"    'keyword': '会议'")
        print(f"  }}")

    except Exception as e:
        print(f"  ✗ API测试失败: {e}")
        print("  请确保服务已启动: python api.py")


if __name__ == "__main__":
    test_parse_time()
    test_extract_time()
    print("\n[OK] 所有测试完成!")
