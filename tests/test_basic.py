#!/usr/bin/env python3
"""
智忆助理 - 基础功能测试
验证核心模块是否正常工作
"""
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def test_embedding():
    """测试嵌入模型"""
    print("\n[Test] 嵌入模型...")
    try:
        from memory_assistant.utils.embedding import SimpleEmbeddingModel

        model = SimpleEmbeddingModel(dimension=1024)
        vector = await model.encode("这是一个测试文本")

        assert len(vector) == 1024, "向量维度不正确"
        print(f"  ✓ 嵌入模型工作正常 (维度: {len(vector)})")
        return True
    except Exception as e:
        print(f"  ✗ 嵌入模型错误: {e}")
        return False


async def test_text_processor():
    """测试文本处理器"""
    print("\n[Test] 文本处理器...")
    try:
        from memory_assistant.utils.text_processor import text_processor

        # 测试分词
        words = text_processor.segment("这是一个测试文本")
        print(f"  - 分词结果: {words[:5]}...")

        # 测试关键词提取
        keywords = text_processor.extract_keywords("人工智能和机器学习是当今最热门的技术领域")
        print(f"  - 关键词: {keywords[:3]}...")

        print("  ✓ 文本处理器工作正常")
        return True
    except Exception as e:
        print(f"  ✗ 文本处理器错误: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_memory_models():
    """测试记忆模型"""
    print("\n[Test] 记忆模型...")
    try:
        from memory_assistant.models.memory import MemoryEntry, MemoryType, MemoryState

        entry = MemoryEntry(
            content="这是一个测试记忆",
            user_id="test_user",
            memory_type=MemoryType.FACT,
        )

        assert entry.memory_id is not None, "记忆ID未生成"

        # 测试序列化
        data = entry.to_dict()
        assert data['content'] == "这是一个测试记忆", "序列化失败"

        # 测试反序列化
        entry2 = MemoryEntry.from_dict(data)
        assert entry2.content == entry.content, "反序列化失败"

        print(f"  ✓ 记忆模型工作正常 (ID: {entry.memory_id[:8]}...)")
        return True
    except Exception as e:
        print(f"  ✗ 记忆模型错误: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_user_profile():
    """测试用户画像"""
    print("\n[Test] 用户画像...")
    try:
        from memory_assistant.models.user_profile import UserProfile

        profile = UserProfile(user_id="test_user")

        # 测试添加话题偏好
        profile.add_or_update_topic("人工智能", 0.8)

        pref = profile.get_topic_preference("人工智能")
        assert pref is not None, "话题偏好添加失败"
        assert pref.topic == "人工智能", "话题名称错误"

        print(f"  ✓ 用户画像工作正常 (话题: {pref.topic}, 权重: {pref.weight:.2f})")
        return True
    except Exception as e:
        print(f"  ✗ 用户画像错误: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_sparse_retrieval():
    """测试稀疏检索"""
    print("\n[Test] 稀疏检索...")
    try:
        from memory_assistant.retrieval.sparse_retrieval import SparseRetrieval

        retriever = SparseRetrieval()

        # 添加文档
        retriever.add_document("doc1", "人工智能是一门研究如何让计算机模拟人类智能的学科")
        retriever.add_document("doc2", "机器学习是人工智能的一个重要分支")
        retriever.add_document("doc3", "深度学习在图像识别方面取得了巨大成功")

        # 搜索
        results = retriever.search("人工智能")
        assert len(results) > 0, "搜索失败"

        print(f"  ✓ 稀疏检索工作正常 (找到 {len(results)} 个结果)")
        return True
    except Exception as e:
        print(f"  ✗ 稀疏检索错误: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_all_tests():
    """运行所有测试"""
    print("="*50)
    print("智忆助理 - 基础功能测试")
    print("="*50)

    tests = [
        ("嵌入模型", test_embedding),
        ("文本处理器", test_text_processor),
        ("记忆模型", test_memory_models),
        ("用户画像", test_user_profile),
        ("稀疏检索", test_sparse_retrieval),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n[Test] {name} 发生未捕获异常: {e}")
            results.append((name, False))

    # 打印总结
    print("\n" + "="*50)
    print("测试结果总结")
    print("="*50)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {status}: {name}")

    print(f"\n总计: {passed}/{total} 通过")

    if passed == total:
        print("\n🎉 所有测试通过! 系统运行正常。")
        print("\n可以使用以下命令启动系统:")
        print("  uv run main.py")
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查错误信息。")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
