"""
混合检索引擎
整合稠密检索、稀疏检索和个性化重排序
"""
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from collections import defaultdict
import time
import math

from ..storage.memory_storage import MemoryStorage
from ..utils.embedding import EmbeddingModel
from ..utils.text_processor import text_processor
from ..models.memory import MemoryEntry
from .sparse_retrieval import SparseRetrieval


@dataclass
class RetrievalResult:
    """检索结果"""
    memory: MemoryEntry
    final_score: float
    dense_score: float = 0.0
    sparse_score: float = 0.0
    temporal_score: float = 0.0
    personalized_score: float = 0.0


class HybridRetrievalEngine:
    """混合检索引擎"""

    def __init__(self,
                 memory_storage: MemoryStorage,
                 embedding_model: EmbeddingModel,
                 rrf_k: int = 60):
        self.memory_storage = memory_storage
        self.embedding_model = embedding_model
        self.sparse_retrieval = SparseRetrieval()
        self.rrf_k = rrf_k  # RRF平滑参数

        # 检索配置
        self.dense_top_k = 50
        self.sparse_top_k = 50
        self.rrf_top_k = 20

    async def retrieve(self,
                       query: str,
                       user_id: str,
                       top_k: int = 10,
                       use_personalization: bool = True,
                       user_profile: Optional[Dict] = None) -> List[RetrievalResult]:
        """
        混合检索主流程

        Args:
            query: 查询文本
            user_id: 用户ID
            top_k: 返回结果数量
            use_personalization: 是否使用个性化
            user_profile: 用户画像

        Returns:
            检索结果列表
        """
        start_time = time.time()

        # 1. 生成查询向量
        query_vector = await self.embedding_model.encode(query)

        # 2. 并行执行多种检索
        dense_results = await self._dense_search(query_vector, user_id)
        sparse_results = await self._sparse_search(query, user_id)

        # 3. RRF结果融合
        fused_results = self._reciprocal_rank_fusion(
            dense_results, sparse_results
        )

        # 4. 个性化重排序
        if use_personalization and user_profile:
            reranked_results = await self._personalize_rank(
                fused_results, user_profile, query
            )
        else:
            reranked_results = fused_results

        # 5. 加载完整记忆信息
        final_results = []
        for item in reranked_results[:top_k]:
            memory = await self.memory_storage.get_memory(item['memory_id'])
            if memory:
                final_results.append(RetrievalResult(
                    memory=memory,
                    final_score=item['score'],
                    dense_score=item.get('dense_score', 0),
                    sparse_score=item.get('sparse_score', 0),
                ))

        elapsed_time = time.time() - start_time
        print(f"Retrieval completed in {elapsed_time:.3f}s, found {len(final_results)} results")

        return final_results

    async def _dense_search(self, query_vector: List[float],
                           user_id: str) -> List[Dict[str, Any]]:
        """稠密检索（向量相似度）"""
        if not query_vector:
            return []

        results = await self.memory_storage.retrieve_by_vector(
            query_vector,
            user_id,
            top_k=self.dense_top_k
        )

        return [
            {
                'memory_id': r['entry'].memory_id,
                'score': r['vector_score'],
                'entry': r['entry'],
            }
            for r in results
        ]

    async def _sparse_search(self, query: str, user_id: str) -> List[Dict[str, Any]]:
        """稀疏检索（关键词匹配）"""
        # 从元数据中检索
        keyword_results = await self.memory_storage.retrieve_by_content(
            user_id, query, limit=self.sparse_top_k
        )

        return [
            {
                'memory_id': entry.memory_id,
                'score': 0.5,  # 基础分数，实际应计算BM25
                'entry': entry,
            }
            for entry in keyword_results
        ]

    def _reciprocal_rank_fusion(self,
                                 dense_results: List[Dict],
                                 sparse_results: List[Dict]) -> List[Dict]:
        """
        RRF (Reciprocal Rank Fusion) 结果融合

        公式: score(d) = Σ(1 / (k + rank(d, result_set_i)))
        """
        # 构建排名映射
        dense_ranks = {r['memory_id']: i + 1 for i, r in enumerate(dense_results)}
        sparse_ranks = {r['memory_id']: i + 1 for i, r in enumerate(sparse_results)}

        # 收集所有记忆ID
        all_memory_ids = set(dense_ranks.keys()) | set(sparse_ranks.keys())

        # 计算RRF分数
        rrf_scores = defaultdict(float)

        for memory_id in all_memory_ids:
            score = 0.0

            # 稠密检索贡献
            if memory_id in dense_ranks:
                score += 1.0 / (self.rrf_k + dense_ranks[memory_id])

            # 稀疏检索贡献
            if memory_id in sparse_ranks:
                score += 1.0 / (self.rrf_k + sparse_ranks[memory_id])

            rrf_scores[memory_id] = score

        # 排序并返回
        sorted_results = sorted(
            [{'memory_id': mid, 'score': score} for mid, score in rrf_scores.items()],
            key=lambda x: x['score'],
            reverse=True
        )

        # 添加原始分数用于调试
        for result in sorted_results:
            mid = result['memory_id']
            result['dense_score'] = 1.0 / (self.rrf_k + dense_ranks.get(mid, 999))
            result['sparse_score'] = 1.0 / (self.rrf_k + sparse_ranks.get(mid, 999))

        return sorted_results[:self.rrf_top_k]

    async def _personalize_rank(self,
                                results: List[Dict],
                                user_profile: Dict,
                                query: str) -> List[Dict]:
        """
        个性化重排序
        """
        topic_preferences = {p['topic']: p['weight']
                            for p in user_profile.get('topic_preferences', [])}

        query_keywords = set(text_processor.extract_keywords(query, top_k=10))

        scored_results = []

        for result in results:
            base_score = result['score']

            # 加载记忆详情
            memory = await self.memory_storage.get_memory(result['memory_id'])
            if not memory:
                continue

            # 1. 话题匹配度
            topic_match = 0.0
            memory_keywords = set(memory.tags)

            for keyword in memory_keywords:
                if keyword in topic_preferences:
                    topic_match += topic_preferences[keyword]

            # 2. 查询-内容相似度
            content_overlap = len(query_keywords & memory_keywords) / len(query_keywords) if query_keywords else 0

            # 3. 记忆质量加权
            quality_score = memory.confidence * memory.importance * (0.5 + memory.weight / 2)

            # 4. 时效性加权 (越新的记忆权重越高)
            from datetime import datetime
            days_old = (datetime.now() - memory.created_at).days
            recency_score = math.exp(-days_old / 30.0)  # 30天衰减到1/e

            # 综合分数
            final_score = (
                base_score * 0.4 +
                topic_match * 0.2 +
                content_overlap * 0.15 +
                quality_score * 0.15 +
                recency_score * 0.1
            )

            scored_results.append({
                'memory_id': result['memory_id'],
                'score': final_score,
                'base_score': base_score,
                'topic_match': topic_match,
            })

        # 按最终分数排序
        scored_results.sort(key=lambda x: x['score'], reverse=True)

        return scored_results

    async def refresh_sparse_index(self, user_id: str):
        """刷新稀疏检索索引"""
        # 获取用户所有记忆
        memories = await self.memory_storage.get_user_memories(user_id, limit=10000)

        # 清空并重建索引
        self.sparse_retrieval.clear()

        for memory in memories:
            self.sparse_retrieval.add_document(
                memory.memory_id,
                memory.content,
                {
                    'user_id': memory.user_id,
                    'memory_type': memory.memory_type.value,
                    'created_at': memory.created_at.isoformat(),
                }
            )

        print(f"Refreshed sparse index with {len(memories)} documents for user {user_id}")
