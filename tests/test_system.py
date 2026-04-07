#!/usr/bin/env python3
"""
智忆助理 - 系统测试脚本
用于验证各模块是否正常工作
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml
from datetime import datetime


async def test_embedding():
    """测试嵌入模型"""
    print("\n[Test] 嵌入模型...")
    try:
        from memory_assistant.utils.embedding import SimpleEmbeddingModel

        model = SimpleEmbeddingModel(dimension=1024)
        vector = await model.encode("这是一个测试文本")

        assert len(vector) == 1024, "向量维度不正确"
        assert all(isinstance(x, float) for x in vector), "向量元素类型错误"

        print("  ✓ 嵌入模型工作正常")
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
        assert len(words) > 0, "分词结果为空"

        # 测试关键词提取
        keywords = text_processor.extract_keywords("人工智能和机器学习是当今最热门的技术领域")
        assert len(keywords) > 0, "关键词提取失败"

        # 测试文本分块
        chunks = text_processor.chunk_text("这是一段很长的文本。" * 50, chunk_size=100)
        assert len(chunks) > 1, "文本分块失败"

        print("  ✓ 文本处理器工作正常")
        return True
    except Exception as e:
        print(f"  ✗ 文本处理器错误: {e}")
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
        assert entry.weight == 0.5, "默认权重不正确"

        # 测试序列化
        data = entry.to_dict()
        assert data['content'] == "这是一个测试记忆", "序列化失败"

        # 测试反序列化
        entry2 = MemoryEntry.from_dict(data)
        assert entry2.content == entry.content, "反序列化失败"

        print("  ✓ 记忆模型工作正常")
        return True
    except Exception as e:
        print(f"  ✗ 记忆模型错误: {e}")
        return False


async def test_user_profile():
    """测试用户画像"""
    print("\n[Test] 用户画像...")
    try:
        from memory_assistant.models.user_profile import UserProfile

        profile = UserProfile(user_id="test_user")

        # 测试添加话题偏好
        profile.add_or_update_topic("人工智能", 0.8)
        assert len(profile.topic_preferences) == 1, "话题偏好添加失败"

        # 测试更新
        profile.add_or_update_topic("人工智能", 0.9)
        pref = profile.get_topic_preference("人工智能")
        assert pref.weight > 0.8, "话题权重更新失败"

        print("  ✓ 用户画像工作正常")
        return True
    except Exception as e:
        print(f"  ✗ 用户画像错误: {e}")
        return False


async def test_storage():
    """测试存储模块"""
    print("\n[Test] 存储模块...")
    try:
        from memory_assistant.storage.vector_store import FaissVectorStore
        from memory_assistant.storage.metadata_store import SQLiteMetadataStore

        # 测试向量存储
        vector_store = FaissVectorStore(dimension=1024, index_path="./test_data/vector_index")
        await vector_store.initialize()

        test_vector = [0.1] * 1024
        success = await vector_store.add("test_id", test_vector, {"user_id": "test"})
        assert success, "向量添加失败"

        results = await vector_store.search(test_vector, top_k=1)
        assert len(results) > 0, "向量搜索失败"

        # 清理
        import shutil
        if os.path.exists("./test_data"):
            shutil.rmtree("./test_data")

        print("  ✓ 存储模块工作正常")
        return True
    except Exception as e:
        print(f"  ✗ 存储模块错误: {e}")
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
        assert results[0]['id'] == "doc1", "搜索结果不正确"

        print("  ✓ 稀疏检索工作正常")
        return True
    except Exception as e:
        print(f"  ✗ 稀疏检索错误: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_profile_manager():
    """测试用户画像管理器"""
    print("\n[Test] 用户画像管理器...")
    try:
        from memory_assistant.profile.profile_manager import ProfileManager

        manager = ProfileManager(data_dir="./test_data")

        # 获取画像（自动创建）
        profile = await manager.get_profile("test_user")
        assert profile.user_id == "test_user", "画像创建失败"

        # 保存画像
        profile.add_or_update_topic("测试话题", 0.7)
        success = await manager.save_profile(profile)
        assert success, "画像保存失败"

        # 重新加载
        profile2 = await manager.get_profile("test_user")
        assert len(profile2.topic_preferences) == 1, "画像加载失败"

        # 清理
        import shutil
        if os.path.exists("./test_data"):
            shutil.rmtree("./test_data")

        print("  ✓ 用户画像管理器工作正常")
        return True
    except Exception as e:
        print(f"  ✗ 用户画像管理器错误: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_evolution_engine():
    """测试记忆演化引擎"""
    print("\n[Test] 记忆演化引擎...")
    try:
        from memory_assistant.core.evolution_engine import MemoryEvolutionEngine
        from memory_assistant.models.memory import MemoryEntry, MemoryState

        # 创建一个模拟的metadata_store
        class MockMetadataStore:
            async def update_memory(self, entry):
                return True

        engine = MemoryEvolutionEngine(MockMetadataStore())

        # 创建测试记忆
        entry = MemoryEntry(
            content="测试记忆",
            user_id="test_user",
        )
        entry.weight = 0.5
        entry.importance = 0.6
        entry.access_count = 5

        # 演化
        result = await engine.evolve_single(entry)

        assert result.old_weight == 0.5, "旧权重记录错误"
        assert result.new_weight != result.old_weight, "权重未变化"
        assert result.new_state is not None, "状态未设置"

        print("  ✓ 记忆演化引擎工作正常")
        return True
    except Exception as e:
        print(f"  ✗ 记忆演化引擎错误: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_all_tests():
    """运行所有测试"""
    print("="*50)
    print("智忆助理 - 系统测试")
    print("="*50)

    tests = [
        ("嵌入模型", test_embedding),
        ("文本处理器", test_text_processor),
        ("记忆模型", test_memory_models),
        ("用户画像", test_user_profile),
        ("存储模块", test_storage),
        ("稀疏检索", test_sparse_retrieval),
        ("用户画像管理器", test_profile_manager),
        ("记忆演化引擎", test_evolution_engine),
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
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查错误信息。")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
