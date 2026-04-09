"""
中文语义切片器
针对会议记录结构特点优化
"""
import re
from typing import List, Optional


class ChineseRecursiveTextSplitter:
    """
    递归字符切片器（中文优化版）

    特点：
    1. 优先按会议结构切片（议程、决议、待办等关键词）
    2. 保留中文标点边界
    3. 支持重叠区域防止上下文断裂
    """

    # 会议相关的语义分隔符（按优先级排序）
    SEPARATORS = [
        # 一级分隔：主要章节
        "\n## ", "\n# ",  # Markdown标题
        "\n【", "\n[",      # 结构化标记
        "\n一、", "\n二、", "\n三、", "\n四、", "\n五、",  # 中文数字标题
        "\n1.", "\n2.", "\n3.",  # 数字列表
        "\n1、", "\n2、", "\n3、",

        # 二级分隔：会议特定关键词
        "\n会议主题", "\n会议议程", "\n讨论内容",
        "\n决议事项", "\n决议：", "\n决议:",
        "\n行动计划", "\n待办事项", "\n下一步：", "\n下一步:",
        "\n行动项", "\nTODO", "\n待办：",
        "\n参会人员", "\n与会人员", "\n出席：",
        "\n会议记录", "\n会议纪要",

        # 三级分隔：段落级
        "\n\n", "\n",  # 段落

        # 四级分隔：句子级（中文标点）
        "。", "；", "！", "？",  # 中文句末
        ". ", "; ", "! ", "? ",  # 英文句末

        # 最后手段
        " ", "",
    ]

    def __init__(
        self,
        chunk_size: int = 800,      # 每块目标字数（考虑中文）
        chunk_overlap: int = 100,    # 重叠字数（约12.5%）
        separators: Optional[List[str]] = None
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or self.SEPARATORS

    def split_text(self, text: str) -> List[str]:
        """将文本切片为语义块"""
        return self._recursive_split(text, self.separators)

    def _recursive_split(self, text: str, separators: List[str]) -> List[str]:
        """递归切片"""
        # 清理文本
        text = self._clean_text(text)

        # 终止条件：文本足够短
        if len(text) <= self.chunk_size:
            return [text] if text.strip() else []

        # 尝试使用当前分隔符
        separator = separators[0] if separators else ""
        next_separators = separators[1:] if len(separators) > 1 else []

        # 按分隔符分割
        parts = self._split_with_separator(text, separator)

        # 如果分割后块太多且太小，尝试合并
        chunks = []
        current_chunk = ""

        for part in parts:
            # 如果当前部分已经很大，直接递归处理
            if len(part) > self.chunk_size:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""

                # 递归切片大块
                sub_chunks = self._recursive_split(part, next_separators)
                chunks.extend(sub_chunks)
                continue

            # 尝试添加到当前块
            if len(current_chunk) + len(part) + len(separator) <= self.chunk_size:
                current_chunk = (current_chunk + separator + part) if current_chunk else part
            else:
                # 当前块已满，保存并开始新块
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = part

        # 保存最后一块
        if current_chunk:
            chunks.append(current_chunk)

        # 处理重叠
        return self._add_overlap(chunks)

    def _split_with_separator(self, text: str, separator: str) -> List[str]:
        """使用分隔符分割文本"""
        if not separator:
            # 无分隔符，按字符切分
            return list(text)

        # 处理正则特殊字符
        escaped_sep = re.escape(separator)
        pattern = f'({escaped_sep})'
        parts = re.split(pattern, text)

        # 重组：将分隔符与后续内容结合
        result = []
        i = 0
        while i < len(parts):
            if i + 1 < len(parts) and parts[i+1] in separator:
                # 当前是内容，下一个是分隔符
                result.append(parts[i] + parts[i+1])
                i += 2
            else:
                if parts[i].strip():
                    result.append(parts[i])
                i += 1

        return result

    def _add_overlap(self, chunks: List[str]) -> List[str]:
        """添加重叠区域"""
        if not chunks or len(chunks) == 1:
            return chunks

        result = [chunks[0]]

        for i in range(1, len(chunks)):
            prev_chunk = chunks[i-1]
            current_chunk = chunks[i]

            # 计算重叠内容（从上一块末尾取）
            overlap_start = max(0, len(prev_chunk) - self.chunk_overlap)
            overlap_text = prev_chunk[overlap_start:]

            # 如果当前块没有以重叠内容开头，添加它
            if not current_chunk.startswith(overlap_text.strip()):
                # 智能裁剪：找到句子边界
                sentences = re.split(r'([。；！？\n])', overlap_text)
                meaningful_overlap = "".join(sentences[-4:])  # 最后2个句子左右

                current_chunk = meaningful_overlap + current_chunk

            result.append(current_chunk)

        return result

    def _clean_text(self, text: str) -> str:
        """清理文本"""
        # 移除多余空白
        text = re.sub(r'\r\n', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text.strip()
