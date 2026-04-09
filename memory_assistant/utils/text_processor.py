"""
文本处理工具
包含分词、分块、关键词提取等功能
"""
import re
from typing import List
import jieba
import jieba.analyse


class TextProcessor:
    """文本处理器"""

    # 停用词
    STOPWORDS = set([
        '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也',
        '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这', '那',
        '啊', '哦', '呢', '吧', '吗', '嗯', '这个', '那个', '什么', '怎么', '为什么', '如何',
        '咋', '怎样', '怎么样', '哪里', '哪些', '谁', '多少', '几', '个', '些',
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
        'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'
    ])

    def __init__(self):
        # 添加自定义词典（如果需要）
        pass

    def segment(self, text: str, remove_stopwords: bool = True) -> List[str]:
        """
        中文分词

        Args:
            text: 输入文本
            remove_stopwords: 是否移除停用词

        Returns:
            分词结果列表
        """
        words = jieba.lcut(text)

        if remove_stopwords:
            words = [w.strip() for w in words
                     if w.strip() and w.strip() not in self.STOPWORDS and len(w.strip()) > 1]
        else:
            words = [w.strip() for w in words if w.strip()]

        return words

    def extract_keywords(self, text: str, top_k: int = 10) -> List[str]:
        """
        提取关键词

        Args:
            text: 输入文本
            top_k: 提取数量

        Returns:
            关键词列表
        """
        keywords = jieba.analyse.extract_tags(
            text,
            topK=top_k,
            withWeight=False
        )
        # 过滤停用词
        keywords = [kw for kw in keywords if kw not in self.STOPWORDS]
        return keywords

    def extract_keywords_textrank(self, text: str, top_k: int = 10) -> List[str]:
        """
        使用TextRank算法提取关键词

        Args:
            text: 输入文本
            top_k: 提取数量

        Returns:
            关键词列表
        """
        keywords = jieba.analyse.textrank(
            text,
            topK=top_k,
            withWeight=False
        )
        # 过滤停用词
        keywords = [kw for kw in keywords if kw not in self.STOPWORDS]
        return keywords

    def chunk_text(self, text: str,
                   chunk_size: int = 500,
                   chunk_overlap: int = 100) -> List[str]:
        """
        递归文本分块

        Args:
            text: 输入文本
            chunk_size: 块大小
            chunk_overlap: 重叠大小

        Returns:
            文本块列表
        """
        if len(text) <= chunk_size:
            return [text]

        # 定义分隔符（按优先级）
        separators = ['\n\n', '\n', '。', '，', '. ', ', ', ' ', '']

        chunks = []

        for separator in separators:
            if not separator:
                # 字符级分割（最后一个选项）
                for i in range(0, len(text), chunk_size - chunk_overlap):
                    chunk = text[i:i + chunk_size]
                    if chunk:
                        chunks.append(chunk)
                return chunks

            if separator in text:
                parts = text.split(separator)

                current_chunk = []
                current_length = 0

                for part in parts:
                    part_length = len(part)

                    if part_length > chunk_size:
                        # 单个部分超过chunk_size，需要递归处理
                        if current_chunk:
                            chunks.append(separator.join(current_chunk))
                            current_chunk = []
                            current_length = 0

                        # 递归分割这个长部分
                        sub_chunks = self.chunk_text(part, chunk_size, chunk_overlap)
                        chunks.extend(sub_chunks)

                    elif current_length + part_length > chunk_size:
                        # 保存当前块
                        chunks.append(separator.join(current_chunk))

                        # 保留重叠部分
                        if current_chunk:
                            overlap_start = max(0, len(current_chunk) - 3)
                            current_chunk = current_chunk[overlap_start:] + [part]
                            current_length = sum(len(p) for p in current_chunk)
                        else:
                            current_chunk = [part]
                            current_length = part_length
                    else:
                        current_chunk.append(part)
                        current_length += part_length

                # 添加最后一个块
                if current_chunk:
                    chunks.append(separator.join(current_chunk))

                return chunks

        return [text]

    def clean_text(self, text: str) -> str:
        """
        清洗文本

        Args:
            text: 输入文本

        Returns:
            清洗后的文本
        """
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)

        # 移除特殊字符
        text = re.sub(r'[^\w\s\u4e00-\u9fff。.，,!?！？:：""''()]', '', text)

        # 移除URL
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)

        # 移除邮箱
        text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '', text)

        return text.strip()

    def extract_entities(self, text: str) -> List[str]:
        """
        简单实体提取（基于规则和词典）

        注意：这是一个简化版本，生产环境建议使用NLP模型

        Args:
            text: 输入文本

        Returns:
            实体列表
        """
        entities = set()

        # 简单的人名识别（姓氏+名字）
        # 常见中文姓氏
        surnames = ['王', '李', '张', '刘', '陈', '杨', '黄', '赵', '吴', '周',
                   '徐', '孙', '马', '朱', '胡', '郭', '林', '何', '高', '罗']

        for surname in surnames:
            pattern = surname + '[\u4e00-\u9fff]{1,2}'
            matches = re.findall(pattern, text)
            entities.update(matches)

        # 数字+单位模式（时间、金额等）
        number_patterns = [
            r'\d+年',           # 年份
            r'\d+月',           # 月份
            r'\d+日',           # 日期
            r'\d+:\d+',         # 时间
            r'\d+[\.\d]*元',    # 金额
            r'\d+[\.\d]*%',     # 百分比
        ]

        for pattern in number_patterns:
            matches = re.findall(pattern, text)
            entities.update(matches)

        return list(entities)

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        计算两段文本的相似度（基于关键词重叠）

        Args:
            text1: 文本1
            text2: 文本2

        Returns:
            相似度分数 (0-1)
        """
        # 提取关键词
        keywords1 = set(self.extract_keywords(text1, top_k=20))
        keywords2 = set(self.extract_keywords(text2, top_k=20))

        if not keywords1 or not keywords2:
            return 0.0

        # 计算Jaccard相似度
        intersection = len(keywords1 & keywords2)
        union = len(keywords1 | keywords2)

        return intersection / union if union > 0 else 0.0


# 全局文本处理器实例
text_processor = TextProcessor()
