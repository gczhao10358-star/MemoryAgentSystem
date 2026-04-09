"""
嵌入模型
用于生成文本的向量表示
"""
import asyncio
import os
from typing import List, Optional
import numpy as np
import openai


class EmbeddingModel:
    """嵌入模型类"""

    def __init__(self, api_key: str = None, base_url: str = None,
                 model: str = "text-embedding-v3", dimension: int = 1024):
        self.api_key = api_key or os.getenv("EMBEDDING_API_KEY") or os.getenv("LLM_API_KEY")
        self.base_url = base_url or os.getenv("EMBEDDING_BASE_URL") or os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.model = model or os.getenv("EMBEDDING_MODEL", "text-embedding-v3")
        self.dimension = dimension

        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    async def encode(self, text: str) -> Optional[List[float]]:
        """
        编码单个文本

        Args:
            text: 输入文本

        Returns:
            向量表示
        """
        try:
            # 使用同步客户端在异步环境中调用
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.embeddings.create(
                    model=self.model,
                    input=text
                )
            )

            embedding = response.data[0].embedding

            # 如果维度不匹配，进行调整
            if len(embedding) != self.dimension:
                embedding = self._adjust_dimension(embedding)

            return embedding

        except Exception as e:
            print(f"Error encoding text: {e}")
            return None

    async def encode_batch(self, texts: List[str],
                          batch_size: int = 32) -> List[Optional[List[float]]]:
        """
        批量编码文本

        Args:
            texts: 文本列表
            batch_size: 批处理大小

        Returns:
            向量列表
        """
        results = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            try:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.client.embeddings.create(
                        model=self.model,
                        input=batch
                    )
                )

                embeddings = [d.embedding for d in response.data]

                # 调整维度
                embeddings = [self._adjust_dimension(e) for e in embeddings]

                results.extend(embeddings)

            except Exception as e:
                print(f"Error encoding batch: {e}")
                # 填充None
                results.extend([None] * len(batch))

        return results

    def _adjust_dimension(self, embedding: List[float]) -> List[float]:
        """调整向量维度"""
        current_dim = len(embedding)

        if current_dim == self.dimension:
            return embedding

        if current_dim < self.dimension:
            # 填充零
            return embedding + [0.0] * (self.dimension - current_dim)
        else:
            # 截断
            return embedding[:self.dimension]

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        v1 = np.array(vec1)
        v2 = np.array(vec2)

        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(np.dot(v1, v2) / (norm1 * norm2))


class SimpleEmbeddingModel:
    """
    简单的本地嵌入模型（用于测试，无需API）
    使用随机投影生成向量，不具备语义意义
    """

    def __init__(self, dimension: int = 1024):
        self.dimension = dimension
        self.vocab = {}
        self.random_projections = None

    async def encode(self, text: str) -> List[float]:
        """生成简单的哈希向量"""
        import hashlib

        # 使用文本哈希作为随机种子
        hash_val = hashlib.md5(text.encode()).hexdigest()
        seed = int(hash_val[:8], 16)
        np.random.seed(seed)

        # 生成伪随机向量
        vec = np.random.randn(self.dimension).astype(np.float32)

        # L2归一化
        vec = vec / np.linalg.norm(vec)

        return vec.tolist()

    async def encode_batch(self, texts: List[str],
                          batch_size: int = 32) -> List[List[float]]:
        """批量编码"""
        results = []
        for text in texts:
            vec = await self.encode(text)
            results.append(vec)
        return results
