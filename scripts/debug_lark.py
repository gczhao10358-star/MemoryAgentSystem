#!/usr/bin/env python3
"""
飞书机器人配置调试脚本

运行方式:
  LARK_APP_ID=cli_xxx LARK_APP_SECRET=xxx .venv/bin/python scripts/debug_lark.py
"""

import os

import requests


BASE_URL = "https://open.feishu.cn/open-apis"
APP_ID = os.getenv("LARK_APP_ID", "")
APP_SECRET = os.getenv("LARK_APP_SECRET", "")


def check_bot_status():
    print("=" * 50)
    print("飞书机器人配置检查")
    print("=" * 50)

    print("\n[1/4] 获取 Access Token...")
    token_url = f"{BASE_URL}/auth/v3/tenant_access_token/internal"
    resp = requests.post(token_url, json={"app_id": APP_ID, "app_secret": APP_SECRET})
    token_data = resp.json()

    if token_data.get("code") != 0:
        print(f"失败: {token_data.get('msg')}")
        print("请检查环境变量 LARK_APP_ID 和 LARK_APP_SECRET 是否正确")
        return

    token = token_data["tenant_access_token"]
    print("Token 获取成功")

    headers = {"Authorization": f"Bearer {token}"}

    print("\n[2/4] 检查机器人配置...")
    bot_url = f"{BASE_URL}/bot/v3/info"
    resp = requests.get(bot_url, headers=headers)
    bot_info = resp.json()

    if bot_info.get("code") == 230006:
        print("机器人能力未启用 (code=230006)")
        print("\n解决方法:")
        print("  1. 打开 https://open.feishu.cn/app")
        print("  2. 进入应用详情页")
        print("  3. 点击左侧【机器人】菜单")
        print("  4. 开启【启用机器人】开关")
        print("  5. 保存并重新发布应用")
        print("  6. 等待 2 到 5 分钟后重试")
        return
    if bot_info.get("code") == 11205:
        print("应用没有配置机器人 (code=11205)")
        print("\n解决方法:")
        print("  1. 打开 https://open.feishu.cn/app")
        print("  2. 进入应用")
        print("  3. 左侧菜单选择【应用能力】→【机器人】")
        print("  4. 创建或启用机器人")
        print("  5. 创建新版本并发布")
        return
    if bot_info.get("code") == 0:
        print("机器人能力已启用")
        bot_name = bot_info.get("data", {}).get("bot", {}).get("name", "未知")
        print(f"机器人名称: {bot_name}")
    else:
        print(f"其他错误: {bot_info.get('msg')} (code={bot_info.get('code')})")

    print("\n[3/4] 检查权限...")
    perm_url = f"{BASE_URL}/application/v2/app-permissions"
    resp = requests.get(perm_url, headers=headers)
    perm_info = resp.json()

    if perm_info.get("code") == 0:
        permissions = perm_info.get("data", {}).get("permissions", [])
        has_send_msg = any("message:send" in p for p in permissions)
        if has_send_msg:
            print("已开通消息发送权限")
        else:
            print("未找到消息发送权限")
            print("请添加权限: im:message:send_as_bot")

    print("\n[4/4] 测试发送消息...")
    print("需要 receive_id 才能测试")
    print("请在前端配置后点击【测试连接】")

    print("\n" + "=" * 50)
    print("检查完成")
    print("=" * 50)


if __name__ == "__main__":
    if not APP_ID or not APP_SECRET:
        print("请先设置环境变量 LARK_APP_ID 和 LARK_APP_SECRET")
        print(
            "\n示例:\n"
            "  LARK_APP_ID=cli_xxx LARK_APP_SECRET=xxx "
            ".venv/bin/python scripts/debug_lark.py"
        )
        raise SystemExit(1)

    check_bot_status()
