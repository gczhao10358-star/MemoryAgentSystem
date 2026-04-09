"""
稀疏检索模块
基于BM25的关键词检索
"""
from typing import List, Dict, Any, Optional
from collections import defaultdict
import math
import jieba

from ..utils.text_processor import text_processor


class SparseRetrieval:
    """基于BM25的稀疏检索器"""

    def __init__(self):
        self.documents: Dict[str, Dict[str, Any]] = {}  # 文档存储
        self.tokenized_docs: Dict[str, List[str]] = {}  # 分词后的文档
        self.inverted_index: Dict[str, set] = defaultdict(set)  # 倒排索引
        self.doc_count = 0
        self.avg_doc_length = 0.0

        # BM25参数
        self.k1 = 1.5  # 词频饱和度参数
        self.b = 0.75  # 文档长度归一化参数

    def add_document(self, doc_id: str, text: str, metadata: Dict = None):
        """添加文档"""
        # 分词
        tokens = text_processor.segment(text, remove_stopwords=True)

        self.documents[doc_id] = {
            'text': text,
            'tokens': tokens,
            'metadata': metadata or {},
            'length': len(tokens)
        }
        self.tokenized_docs[doc_id] = tokens

        # 更新倒排索引
        for token in set(tokens):
            self.inverted_index[token].add(doc_id)

        # 更新统计信息
        self._update_stats()

    def add_documents(self, docs: List[tuple]):
        """批量添加文档"""
        for doc_id, text, metadata in docs:
            self.add_document(doc_id, text, metadata)

    def _update_stats(self):
        """更新统计信息"""
        self.doc_count = len(self.documents)

        if self.doc_count > 0:
            total_length = sum(doc['length'] for doc in self.documents.values())
            self.avg_doc_length = total_length / self.doc_count

    def search(self, query: str, top_k: int = 10,
               filter_dict: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        BM25检索

        Args:
            query: 查询文本
            top_k: 返回结果数量
            filter_dict: 过滤条件

        Returns:
            检索结果列表
        """
        # 分词
        query_tokens = text_processor.segment(query, remove_stopwords=True)

        if not query_tokens:
            return []

        # 计算每个文档的BM25分数
        scores = defaultdict(float)

        for token in query_tokens:
            # 包含该词的文档
            doc_ids = self.inverted_index.get(token, set())

            if not doc_ids:
                continue

            # 计算IDF
            idf = self._calculate_idf(token)

            for doc_id in doc_ids:
                # 应用过滤器
                if filter_dict:
                    metadata = self.documents[doc_id]['metadata']
                    skip = False
                    for key, value in filter_dict.items():
                        if metadata.get(key) != value:
                            skip = True
                            break
                    if skip:
                        continue

                # 计算BM25分数
                score = self._calculate_bm25(token, doc_id)
                scores[doc_id] += idf * score

        # 排序并返回Top-K
        sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        results = []
        for doc_id, score in sorted_results[:top_k]:
            doc = self.documents[doc_id]
            results.append({
                'id': doc_id,
                'score': score,
                'text': doc['text'],
                'metadata': doc['metadata'],
            })

        return results

    def _calculate_idf(self, token: str) -> float:
        """计算IDF值"""
        # 包含该词的文档数
        n = len(self.inverted_index.get(token, set()))

        if n == 0:
            return 0.0

        # IDF公式
        return math.log((self.doc_count - n + 0.5) / (n + 0.5) + 1.0)

    def _calculate_bm25(self, token: str, doc_id: str) -> float:
        """计算BM25分数分量"""
        doc = self.documents[doc_id]

        # 词频
        tf = doc['tokens'].count(token)

        # 文档长度归一化
        doc_length = doc['length']
        length_ratio = doc_length / self.avg_doc_length if self.avg_doc_length > 0 else 1.0

        # BM25公式
        numerator = tf * (self.k1 + 1)
        denominator = tf + self.k1 * (1 - self.b + self.b * length_ratio)

        return numerator / denominator if denominator > 0 else 0.0

    def remove_document(self, doc_id: str):
        """删除文档"""
        if doc_id not in self.documents:
            return

        # 从倒排索引中移除
        for token in self.tokenized_docs[doc_id]:
            self.inverted_index[token].discard(doc_id)

        # 删除文档
        del self.documents[doc_id]
        del self.tokenized_docs[doc_id]

        # 更新统计
        self._update_stats()

    def clear(self):
        """清空所有文档"""
        self.documents.clear()
        self.tokenized_docs.clear()
        self.inverted_index.clear()
        self.doc_count = 0
        self.avg_doc_length = 0.0
