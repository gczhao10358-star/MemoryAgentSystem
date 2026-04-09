"""
向量存储模块
基于FAISS的向量数据库实现
"""
import os
import pickle
import numpy as np
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple, Any
import faiss


class VectorStore(ABC):
    """向量存储抽象基类"""

    @abstractmethod
    async def add(self, id: str, vector: List[float], metadata: Dict[str, Any]) -> bool:
        """添加向量"""
        pass

    @abstractmethod
    async def add_batch(self, ids: List[str], vectors: List[List[float]],
                        metadatas: List[Dict[str, Any]]) -> bool:
        """批量添加向量"""
        pass

    @abstractmethod
    async def search(self, query_vector: List[float], top_k: int = 10,
                     filter_dict: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """搜索相似向量"""
        pass

    @abstractmethod
    async def delete(self, id: str) -> bool:
        """删除向量"""
        pass

    @abstractmethod
    async def get(self, id: str) -> Optional[Dict[str, Any]]:
        """获取向量"""
        pass


class FaissVectorStore(VectorStore):
    """基于FAISS的向量存储实现"""

    def __init__(self, dimension: int = 1024, index_path: Optional[str] = None):
        self.dimension = dimension
        self.index_path = index_path
        self.index = None
        self.id_to_vector_id: Dict[str, int] = {}
        self.vector_id_to_id: Dict[int, str] = {}
        self.metadata: Dict[str, Dict[str, Any]] = {}
        self.next_vector_id = 0

    async def initialize(self):
        """初始化向量索引"""
        if self.index_path and os.path.exists(self.index_path):
            await self.load()
        else:
            # 创建新的FAISS索引 (使用内积作为相似度度量)
            self.index = faiss.IndexFlatIP(self.dimension)
            # 如果需要使用GPU加速，可以在这里添加

    async def add(self, id: str, vector: List[float],
                  metadata: Dict[str, Any] = None) -> bool:
        """添加单个向量"""
        try:
            vector_array = np.array([vector], dtype=np.float32)

            # L2归一化 (用于内积计算余弦相似度)
            faiss.normalize_L2(vector_array)

            # 添加到索引
            self.index.add(vector_array)

            # 记录映射关系
            self.id_to_vector_id[id] = self.next_vector_id
            self.vector_id_to_id[self.next_vector_id] = id
            self.metadata[id] = metadata or {}
            self.next_vector_id += 1

            return True
        except Exception as e:
            print(f"Error adding vector: {e}")
            return False

    async def add_batch(self, ids: List[str], vectors: List[List[float]],
                        metadatas: List[Dict[str, Any]] = None) -> bool:
        """批量添加向量"""
        try:
            vectors_array = np.array(vectors, dtype=np.float32)

            # L2归一化
            faiss.normalize_L2(vectors_array)

            # 批量添加到索引
            self.index.add(vectors_array)

            # 记录映射关系
            for i, id in enumerate(ids):
                self.id_to_vector_id[id] = self.next_vector_id + i
                self.vector_id_to_id[self.next_vector_id + i] = id
                self.metadata[id] = metadatas[i] if metadatas else {}

            self.next_vector_id += len(ids)
            return True
        except Exception as e:
            print(f"Error adding batch vectors: {e}")
            return False

    async def search(self, query_vector: List[float], top_k: int = 10,
                     filter_dict: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """搜索相似向量"""
        try:
            query_array = np.array([query_vector], dtype=np.float32)
            faiss.normalize_L2(query_array)

            # 搜索 (获取更多结果以便过滤)
            fetch_k = top_k * 3 if filter_dict else top_k
            scores, indices = self.index.search(query_array, fetch_k)

            results = []
            for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
                if idx == -1:  # FAISS返回-1表示无更多结果
                    break

                id = self.vector_id_to_id.get(int(idx))
                if not id:
                    continue

                metadata = self.metadata.get(id, {})

                # 应用过滤条件
                if filter_dict:
                    skip = False
                    for key, value in filter_dict.items():
                        if metadata.get(key) != value:
                            skip = True
                            break
                    if skip:
                        continue

                results.append({
                    'id': id,
                    'score': float(score),
                    'metadata': metadata,
                })

                if len(results) >= top_k:
                    break

            return results
        except Exception as e:
            print(f"Error searching vectors: {e}")
            return []

    async def delete(self, id: str) -> bool:
        """删除向量 (FAISS不支持直接删除，使用标记删除)"""
        if id in self.metadata:
            self.metadata[id]['_deleted'] = True
            return True
        return False

    async def get(self, id: str) -> Optional[Dict[str, Any]]:
        """获取向量元数据"""
        return self.metadata.get(id)

    async def save(self):
        """保存索引到磁盘"""
        if self.index_path:
            os.makedirs(os.path.dirname(self.index_path), exist_ok=True)

            # 保存FAISS索引
            faiss.write_index(self.index, f"{self.index_path}.faiss")

            # 保存映射关系和元数据
            data = {
                'id_to_vector_id': self.id_to_vector_id,
                'vector_id_to_id': self.vector_id_to_id,
                'metadata': self.metadata,
                'next_vector_id': self.next_vector_id,
                'dimension': self.dimension,
            }
            with open(f"{self.index_path}.pkl", 'wb') as f:
                pickle.dump(data, f)

    async def load(self):
        """从磁盘加载索引"""
        if os.path.exists(f"{self.index_path}.faiss"):
            self.index = faiss.read_index(f"{self.index_path}.faiss")

            with open(f"{self.index_path}.pkl", 'rb') as f:
                data = pickle.load(f)
                self.id_to_vector_id = data['id_to_vector_id']
                self.vector_id_to_id = data['vector_id_to_id']
                self.metadata = data['metadata']
                self.next_vector_id = data['next_vector_id']
                self.dimension = data['dimension']

    def count(self) -> int:
        """获取向量数量"""
        return self.index.ntotal if self.index else 0