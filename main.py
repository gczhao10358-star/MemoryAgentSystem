#!/usr/bin/env python3
"""
智忆助理 (MemoryMate) - 主程序入口
"""
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from memory_assistant.core.memory_mate_agent import MemoryMateAgent
from memory_assistant.utils.config_loader import load_config


async def interactive_mode(agent: MemoryMateAgent, user_id: str):
    """交互模式"""
    print(f"\n{'='*50}")
    print("欢迎使用 智忆助理 (MemoryMate)!")
    print("输入 'quit' 或 'exit' 退出")
    print("输入 'stats' 查看记忆统计")
    print("输入 'clear' 清空对话")
    print(f"{'='*50}\n")

    while True:
        try:
            user_input = input(f"[{user_id}] > ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("再见!")
                break

            if user_input.lower() == 'stats':
                stats = await agent.get_user_stats(user_id)
                print(f"\n记忆统计:")
                print(f"  总记忆数: {stats['memory'].get('total_memories', 0)}")
                print(f"  会话记忆轮次: {stats['memory'].get('session_turns', 0)}")
                print(f"  近期缓存条目: {stats['memory'].get('cache_entries', 0)}")
                print(f"  平均可信度: {stats['memory'].get('avg_confidence', 0):.2f}")
                print(f"  话题偏好数: {stats['profile'].get('topic_count', 0)}")
                print()
                continue

            if user_input.lower() == 'clear':
                await agent.clear_conversation(user_id)
                print("对话已清空\n")
                continue

            # 处理用户输入
            print("\n智忆助理: ", end="", flush=True)
            response = await agent.chat(user_id, user_input)
            print(response)
            print()

        except KeyboardInterrupt:
            print("\n再见!")
            break
        except Exception as e:
            print(f"错误: {e}")


async def demo_mode(agent: MemoryMateAgent, user_id: str):
    """演示模式"""
    print(f"\n{'='*50}")
    print("智忆助理 - 演示模式")
    print(f"{'='*50}\n")

    demo_conversations = [
        "你好，我叫李明，是一名软件工程师",
        "我喜欢研究人工智能和机器学习",
        "最近在学习大语言模型的应用",
        "能帮我总结一下刚才我说了什么吗？",
        "我的兴趣是什么？",
        "我在哪个领域工作？",
    ]

    for message in demo_conversations:
        print(f"[{user_id}] > {message}")
        print("\n智忆助理: ", end="", flush=True)
        response = await agent.chat(user_id, message)
        print(response)
        print()
        await asyncio.sleep(1)

    # 显示统计
    print("\n" + "="*50)
    print("演示完成! 查看记忆统计:")
    stats = await agent.get_user_stats(user_id)
    print(f"  总记忆数: {stats['memory'].get('total_memories', 0)}")
    print(f"  话题偏好: {[t['topic'] for t in stats['profile'].get('top_topics', [])]}")
    print("="*50 + "\n")


async def main():
    """主函数"""
    # 加载配置
    config = load_config()

    # 初始化Agent
    agent = MemoryMateAgent(config)
    await agent.initialize()

    # 默认用户ID
    user_id = "user_001"

    # 选择模式
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        await demo_mode(agent, user_id)
    else:
        await interactive_mode(agent, user_id)

    # 关闭
    await agent.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序已终止")
        sys.exit(0)
