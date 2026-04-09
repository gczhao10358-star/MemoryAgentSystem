# 会议记录文档解析功能 - 详细实现方案

## 一、目录结构设计

```
memory_assistant/
├── ingestion/                      # 新增：文档摄取模块
│   ├── __init__.py
│   ├── document_processor.py       # 核心处理器（整合流水线）
│   ├── file_loaders.py             # 文件加载器（PDF/DOCX/TXT/MD）
│   ├── text_splitter.py            # 中文语义切片器
│   ├── meeting_analyzer.py         # 会议记录专用分析器
│   └── models.py                   # 数据模型定义
├── storage/
│   └── document_store.py           # 新增：原始文件存储管理
└── ...
```

---

## 二、核心组件详细设计

### 1. 数据模型 (`ingestion/models.py`)

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Any
import uuid


class DocumentType(Enum):
    """支持的文档类型"""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MARKDOWN = "md"


class ProcessingStatus(Enum):
    """处理状态"""
    PENDING = "pending"           # 等待处理
    EXTRACTING = "extracting"     # 内容提取中
    CHUNKING = "chunking"         # 切片中
    ANALYZING = "analyzing"       # LLM分析中
    COMPLETED = "completed"       # 完成
    FAILED = "failed"             # 失败


@dataclass
class DocumentMetadata:
    """文档元数据（丰富的上下文信息）"""
    # 基础文件信息
    filename: str
    file_size: int
    mime_type: str
    doc_type: DocumentType

    # 时间信息
    uploaded_at: datetime
    file_created_at: Optional[datetime] = None  # 文件系统创建时间
    file_modified_at: Optional[datetime] = None  # 文件最后修改时间

    # 来源信息
    source: str  # "web", "lark"
    uploaded_by: str  # user_id

    # 可选的扩展元数据
    original_path: Optional[str] = None
    file_hash: Optional[str] = None  # SHA256，用于去重
    author: Optional[str] = None     # 文档作者（从PDF/DOCX元数据提取）
    title: Optional[str] = None      # 文档标题
    page_count: Optional[int] = None # PDF页数
    word_count: Optional[int] = None # 预估字数

    def to_dict(self) -> Dict[str, Any]:
        return {
            'filename': self.filename,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'doc_type': self.doc_type.value,
            'uploaded_at': self.uploaded_at.isoformat(),
            'file_created_at': self.file_created_at.isoformat() if self.file_created_at else None,
            'file_modified_at': self.file_modified_at.isoformat() if self.file_modified_at else None,
            'source': self.source,
            'uploaded_by': self.uploaded_by,
            'original_path': self.original_path,
            'file_hash': self.file_hash,
            'author': self.author,
            'title': self.title,
            'page_count': self.page_count,
            'word_count': self.word_count,
        }


@dataclass
class MeetingAnalysisResult:
    """会议解析结果"""
    # 整体摘要
    summary: str
    meeting_title: Optional[str] = None
    meeting_date: Optional[str] = None
    meeting_location: Optional[str] = None
    participants: List[str] = field(default_factory=list)

    # 核心内容
    key_decisions: List[str] = field(default_factory=list)  # 关键决策
    action_items: List[Dict[str, Any]] = field(default_factory=list)  # 待办任务
    discussed_topics: List[str] = field(default_factory=list)  # 讨论主题

    # 用户偏好提取
    user_preferences: List[Dict[str, Any]] = field(default_factory=list)

    # 记忆建议
    memory_suggestions: List[Dict[str, Any]] = field(default_factory=list)

    # 元数据
    confidence_score: float = 0.0  # LLM置信度
    processing_time_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'summary': self.summary,
            'meeting_title': self.meeting_title,
            'meeting_date': self.meeting_date,
            'meeting_location': self.meeting_location,
            'participants': self.participants,
            'key_decisions': self.key_decisions,
            'action_items': self.action_items,
            'discussed_topics': self.discussed_topics,
            'user_preferences': self.user_preferences,
            'memory_suggestions': self.memory_suggestions,
            'confidence_score': self.confidence_score,
            'processing_time_ms': self.processing_time_ms,
        }


@dataclass
class ProcessingResult:
    """完整处理结果"""
    document_id: str
    status: ProcessingStatus
    metadata: DocumentMetadata
    analysis: Optional[MeetingAnalysisResult] = None
    stored_memory_ids: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
```

---

### 2. 文件加载器 (`ingestion/file_loaders.py`)

```python
"""
文件加载器 - 支持多种文档格式
"""
import os
import hashlib
from abc import ABC, abstractmethod
from typing import Optional, Tuple
from datetime import datetime

from .models import DocumentMetadata, DocumentType


class BaseLoader(ABC):
    """加载器基类"""

    @abstractmethod
    def load(self, file_path: str) -> Tuple[str, dict]:
        """返回 (文本内容, 提取的元数据)"""
        pass

    @abstractmethod
    def supports(self, file_path: str) -> bool:
        """检查是否支持该文件"""
        pass


class PDFLoader(BaseLoader):
    """PDF加载器（仅支持文本型PDF）"""

    def __init__(self):
        try:
            import fitz  # PyMuPDF
            self.fitz = fitz
        except ImportError:
            raise ImportError("请安装 PyMuPDF: pip install PyMuPDF")

    def supports(self, file_path: str) -> bool:
        return file_path.lower().endswith('.pdf')

    def load(self, file_path: str) -> Tuple[str, dict]:
        doc = self.fitz.open(file_path)

        # 提取文本
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())

        # 提取元数据
        metadata = {
            'page_count': len(doc),
            'author': doc.metadata.get('author'),
            'title': doc.metadata.get('title'),
            'subject': doc.metadata.get('subject'),
        }

        doc.close()
        return "\n\n".join(text_parts), metadata


class DocxLoader(BaseLoader):
    """Word文档加载器"""

    def __init__(self):
        try:
            from docx import Document
            self.Document = Document
        except ImportError:
            raise ImportError("请安装 python-docx: pip install python-docx")

    def supports(self, file_path: str) -> bool:
        return file_path.lower().endswith('.docx')

    def load(self, file_path: str) -> Tuple[str, dict]:
        doc = self.Document(file_path)

        # 提取段落
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]

        # 提取表格（会议记录可能包含表格）
        tables_text = []
        for table in doc.tables:
            table_rows = []
            for row in table.rows:
                row_text = [cell.text for cell in row.cells]
                table_rows.append(" | ".join(row_text))
            tables_text.append("\n".join(table_rows))

        all_text = "\n\n".join(paragraphs)
        if tables_text:
            all_text += "\n\n【表格内容】\n" + "\n\n".join(tables_text)

        # 提取元数据
        metadata = {
            'author': doc.core_properties.author,
            'title': doc.core_properties.title,
            'paragraph_count': len(paragraphs),
        }

        return all_text, metadata


class TextLoader(BaseLoader):
    """纯文本/Markdown加载器"""

    def supports(self, file_path: str) -> bool:
        ext = file_path.lower()
        return ext.endswith('.txt') or ext.endswith('.md') or ext.endswith('.markdown')

    def load(self, file_path: str) -> Tuple[str, dict]:
        # 自动检测编码
        import chardet
        with open(file_path, 'rb') as f:
            raw = f.read()
            encoding = chardet.detect(raw)['encoding'] or 'utf-8'

        content = raw.decode(encoding, errors='ignore')

        # 简单统计
        metadata = {
            'line_count': content.count('\n') + 1,
            'char_count': len(content),
        }

        return content, metadata


class FileLoaderFactory:
    """加载器工厂"""

    _loaders = [
        PDFLoader(),
        DocxLoader(),
        TextLoader(),
    ]

    @classmethod
    def get_loader(cls, file_path: str) -> Optional[BaseLoader]:
        for loader in cls._loaders:
            if loader.supports(file_path):
                return loader
        return None

    @classmethod
    def load_file(cls, file_path: str) -> Tuple[str, dict, DocumentType]:
        loader = cls.get_loader(file_path)
        if not loader:
            raise ValueError(f"不支持的文件格式: {file_path}")

        content, metadata = loader.load(file_path)

        # 确定文档类型
        ext = os.path.splitext(file_path)[1].lower()
        type_map = {
            '.pdf': DocumentType.PDF,
            '.docx': DocumentType.DOCX,
            '.txt': DocumentType.TXT,
            '.md': DocumentType.MARKDOWN,
            '.markdown': DocumentType.MARKDOWN,
        }
        doc_type = type_map.get(ext, DocumentType.TXT)

        return content, metadata, doc_type
```

---

### 3. 中文语义切片器 (`ingestion/text_splitter.py`)

```python
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
```

---

### 4. 会议分析器 (`ingestion/meeting_analyzer.py`)

```python
"""
会议记录专用分析器
使用LLM提取结构化信息
"""
import json
import asyncio
from typing import AsyncGenerator, Dict, Any, List
from datetime import datetime

from .models import MeetingAnalysisResult, ProcessingStatus


class MeetingAnalyzer:
    """
    会议记录分析器

    分两个阶段：
    1. 全局分析：提取摘要、会议信息、关键决策
    2. 详细分析：逐块提取待办、偏好等
    """

    def __init__(self, llm_client):
        self.llm_client = llm_client

    async def analyze_stream(
        self,
        chunks: List[str],
        user_id: str,
        context: Dict[str, Any] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式分析会议记录

        Yields:
            {
                "stage": str,           # 当前阶段
                "progress": float,      # 进度 0-1
                "data": Any,            # 阶段数据
                "status": str,          # "processing" | "completed" | "error"
            }
        """
        start_time = datetime.now()
        total_chunks = len(chunks)
        context = context or {}

        try:
            # ===== 阶段1: 全局分析 =====
            yield {
                "stage": "global_analysis",
                "progress": 0.0,
                "data": {"message": "正在分析会议整体结构..."},
                "status": "processing"
            }

            # 取前几块和最后一块做全局分析
            global_text = self._prepare_global_text(chunks)
            global_result = await self._analyze_global(global_text, context)

            yield {
                "stage": "global_analysis",
                "progress": 0.2,
                "data": global_result,
                "status": "completed"
            }

            # ===== 阶段2: 逐块详细分析 =====
            all_action_items = []
            all_preferences = []
            all_memory_suggestions = []

            for i, chunk in enumerate(chunks):
                progress = 0.2 + (0.6 * (i + 1) / total_chunks)

                yield {
                    "stage": "chunk_analysis",
                    "progress": progress,
                    "data": {
                        "current_chunk": i + 1,
                        "total_chunks": total_chunks,
                        "message": f"正在分析第 {i+1}/{total_chunks} 部分..."
                    },
                    "status": "processing"
                }

                chunk_result = await self._analyze_chunk(chunk, global_result, user_id)

                all_action_items.extend(chunk_result.get('action_items', []))
                all_preferences.extend(chunk_result.get('preferences', []))
                all_memory_suggestions.extend(chunk_result.get('memory_suggestions', []))

                # 每处理完一块，yield中间结果
                yield {
                    "stage": "chunk_result",
                    "progress": progress,
                    "data": {
                        "chunk_index": i,
                        "action_items_found": len(chunk_result.get('action_items', [])),
                        "preferences_found": len(chunk_result.get('preferences', [])),
                    },
                    "status": "processing"
                }

            # ===== 阶段3: 整合去重 =====
            yield {
                "stage": "consolidation",
                "progress": 0.85,
                "data": {"message": "正在整合分析结果..."},
                "status": "processing"
            }

            # 去重和合并
            final_action_items = self._deduplicate_action_items(all_action_items)
            final_preferences = self._deduplicate_preferences(all_preferences)
            final_memories = self._consolidate_memories(all_memory_suggestions)

            # ===== 阶段4: 生成最终结果 =====
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

            result = MeetingAnalysisResult(
                summary=global_result.get('summary', ''),
                meeting_title=global_result.get('meeting_title'),
                meeting_date=global_result.get('meeting_date'),
                meeting_location=global_result.get('location'),
                participants=global_result.get('participants', []),
                key_decisions=global_result.get('key_decisions', []),
                action_items=final_action_items,
                discussed_topics=global_result.get('topics', []),
                user_preferences=final_preferences,
                memory_suggestions=final_memories,
                confidence_score=global_result.get('confidence', 0.8),
                processing_time_ms=processing_time
            )

            yield {
                "stage": "completed",
                "progress": 1.0,
                "data": result.to_dict(),
                "status": "completed"
            }

        except Exception as e:
            yield {
                "stage": "error",
                "progress": 0,
                "data": {"error": str(e)},
                "status": "error"
            }

    async def _analyze_global(self, text: str, context: Dict) -> Dict:
        """全局分析"""
        prompt = f"""请分析以下会议记录，提取整体信息。

【上下文】
用户ID: {context.get('user_id', 'unknown')}
上传时间: {context.get('upload_time', 'unknown')}

【会议记录内容】
{text[:4000]}  # 限制长度避免token超限

请提取以下信息，以JSON格式返回：
{{
    "summary": "会议整体摘要（100字以内）",
    "meeting_title": "会议标题（如有）",
    "meeting_date": "会议日期（YYYY-MM-DD格式，如有）",
    "location": "会议地点（如有）",
    "participants": ["参会人员1", "参会人员2"],
    "key_decisions": ["决策1", "决策2"],
    "topics": ["讨论主题1", "讨论主题2"],
    "confidence": 0.95
}}

注意：
1. 如果某项信息不存在，设为null或空数组
2. summary必须是完整、通顺的中文句子
3. 只返回JSON，不要其他文字
"""

        response = await self.llm_client.chat([
            {"role": "system", "content": "你是专业的会议记录分析助手，擅长提取关键信息。"},
            {"role": "user", "content": prompt}
        ])

        # 解析JSON
        return self._extract_json(response)

    async def _analyze_chunk(self, chunk: str, global_info: Dict, user_id: str) -> Dict:
        """分析单个切片"""
        prompt = f"""请分析以下会议记录片段，提取具体信息。

【会议背景】
会议主题: {global_info.get('meeting_title', '未知')}
参会人员: {', '.join(global_info.get('participants', []))}

【当前片段内容】
{chunk}

请提取以下信息，以JSON格式返回：
{{
    "action_items": [
        {{
            "content": "待办事项具体内容",
            "assignee": "负责人（如有）",
            "deadline": "截止日期描述（如有）",
            "priority": "high/medium/low",
            "should_remind": true/false,
            "suggested_reminder_time": "建议提醒时间描述"
        }}
    ],
    "preferences": [
        {{
            "type": "time/location/work_style/other",
            "content": "用户偏好描述",
            "confidence": 0.8
        }}
    ],
    "memory_suggestions": [
        {{
            "content": "建议存储的记忆内容",
            "memory_type": "fact/event/task",
            "importance": 0.7,
            "reason": "存储理由"
        }}
    ]
}}

注意：
1. 只提取明确提及的信息，不要推测
2. should_remind为true时，表示这是需要提醒的任务
3. 只返回JSON，不要其他文字
"""

        response = await self.llm_client.chat([
            {"role": "system", "content": "你是专业的信息提取助手，擅长从会议记录中提取待办事项和用户偏好。"},
            {"role": "user", "content": prompt}
        ])

        return self._extract_json(response)

    def _prepare_global_text(self, chunks: List[str]) -> str:
        """准备全局分析的文本"""
        if len(chunks) <= 3:
            return "\n\n".join(chunks)

        # 取前2块和最后1块
        return "\n\n".join(chunks[:2] + ["..."] + chunks[-1:])

    def _extract_json(self, text: str) -> Dict:
        """从文本中提取JSON"""
        import re
        try:
            # 尝试直接解析
            return json.loads(text)
        except:
            # 尝试提取JSON块
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
            # 返回空结果
            return {}

    def _deduplicate_action_items(self, items: List[Dict]) -> List[Dict]:
        """去重待办事项"""
        seen = set()
        result = []
        for item in items:
            key = item.get('content', '').strip()[:50]  # 取前50字作为key
            if key and key not in seen:
                seen.add(key)
                result.append(item)
        return result

    def _deduplicate_preferences(self, prefs: List[Dict]) -> List[Dict]:
        """去重偏好"""
        seen = set()
        result = []
        for pref in prefs:
            key = pref.get('content', '').strip()[:30]
            if key and key not in seen:
                seen.add(key)
                result.append(pref)
        return result

    def _consolidate_memories(self, memories: List[Dict]) -> List[Dict]:
        """整合记忆建议"""
        # 按重要性排序
        sorted_mems = sorted(memories, key=lambda x: x.get('importance', 0.5), reverse=True)
        # 去重并限制数量
        seen = set()
        result = []
        for mem in sorted_mems[:20]:  # 最多20条
            key = mem.get('content', '').strip()[:50]
            if key and key not in seen:
                seen.add(key)
                result.append(mem)
        return result
```

---

### 5. 文档存储管理 (`storage/document_store.py`)

```python
"""
原始文件存储管理
"""
import os
import shutil
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any, List
import sqlite3


class DocumentStore:
    """
    文档存储管理器

    功能：
    1. 保存上传的原始文件
    2. 管理文件元数据
    3. 支持文件去重（基于hash）
    """

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = data_dir
        self.documents_dir = os.path.join(data_dir, "documents")
        os.makedirs(self.documents_dir, exist_ok=True)

        self.db_path = os.path.join(data_dir, "documents.db")
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER,
                    file_hash TEXT,
                    mime_type TEXT,
                    doc_type TEXT,
                    uploaded_at TIMESTAMP,
                    source TEXT,
                    metadata TEXT,  -- JSON
                    status TEXT,    -- processing/completed/failed
                    analysis_result TEXT,  -- JSON
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_id ON documents(user_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_hash ON documents(file_hash)
            """)

    async def save_file(
        self,
        file_path: str,
        user_id: str,
        source: str = "web",
        original_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        保存文件并记录元数据

        Returns:
            {
                "document_id": str,
                "file_path": str,
                "file_hash": str,
                "is_duplicate": bool,  # 是否重复上传
            }
        """
        # 计算文件hash
        file_hash = self._calculate_hash(file_path)
        file_size = os.path.getsize(file_path)

        # 检查是否已存在
        existing = self._get_by_hash(file_hash, user_id)
        if existing:
            return {
                "document_id": existing["document_id"],
                "file_path": existing["file_path"],
                "file_hash": file_hash,
                "is_duplicate": True,
            }

        # 生成document_id
        import uuid
        doc_id = f"doc_{uuid.uuid4().hex[:12]}"

        # 确定存储路径
        ext = os.path.splitext(original_filename or file_path)[1]
        storage_filename = f"{doc_id}{ext}"
        storage_path = os.path.join(self.documents_dir, storage_filename)

        # 复制文件
        shutil.copy2(file_path, storage_path)

        # 记录到数据库
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO documents
                (document_id, user_id, filename, file_path, file_size, file_hash,
                 mime_type, doc_type, uploaded_at, source, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                doc_id,
                user_id,
                original_filename or os.path.basename(file_path),
                storage_path,
                file_size,
                file_hash,
                self._guess_mime_type(ext),
                ext.lstrip('.'),
                datetime.now().isoformat(),
                source,
                "processing"
            ))

        return {
            "document_id": doc_id,
            "file_path": storage_path,
            "file_hash": file_hash,
            "is_duplicate": False,
        }

    async def update_status(
        self,
        document_id: str,
        status: str,
        analysis_result: Optional[Dict] = None
    ):
        """更新处理状态"""
        with sqlite3.connect(self.db_path) as conn:
            if analysis_result:
                import json
                conn.execute("""
                    UPDATE documents
                    SET status = ?, analysis_result = ?
                    WHERE document_id = ?
                """, (status, json.dumps(analysis_result, ensure_ascii=False), document_id))
            else:
                conn.execute("""
                    UPDATE documents SET status = ? WHERE document_id = ?
                """, (status, document_id))

    def _calculate_hash(self, file_path: str) -> str:
        """计算文件SHA256"""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()[:32]  # 取前32位足够

    def _get_by_hash(self, file_hash: str, user_id: str) -> Optional[Dict]:
        """根据hash查询"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM documents WHERE file_hash = ? AND user_id = ?",
                (file_hash, user_id)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def _guess_mime_type(self, ext: str) -> str:
        """猜测MIME类型"""
        type_map = {
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.txt': 'text/plain',
            '.md': 'text/markdown',
        }
        return type_map.get(ext.lower(), 'application/octet-stream')

    async def get_user_documents(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict]:
        """获取用户的文档列表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """SELECT document_id, filename, file_size, uploaded_at,
                          status, source, doc_type
                   FROM documents
                   WHERE user_id = ?
                   ORDER BY uploaded_at DESC
                   LIMIT ? OFFSET ?""",
                (user_id, limit, offset)
            )
            return [dict(row) for row in cursor.fetchall()]

    async def get_document(self, document_id: str) -> Optional[Dict]:
        """获取单个文档详情"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM documents WHERE document_id = ?",
                (document_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
```

---

### 6. 核心处理器 (`ingestion/document_processor.py`)

```python
"""
文档处理核心类
整合整个ETL流水线
"""
import os
from typing import AsyncGenerator, Dict, Any, Optional
from datetime import datetime

from .models import DocumentMetadata, DocumentType, ProcessingStatus, ProcessingResult
from .file_loaders import FileLoaderFactory
from .text_splitter import ChineseRecursiveTextSplitter
from .meeting_analyzer import MeetingAnalyzer


class DocumentProcessor:
    """
    文档处理器

    处理流水线：
    1. 文件加载 -> 2. 内容提取 -> 3. 语义切片 -> 4. LLM分析 -> 5. 结果存储
    """

    def __init__(
        self,
        agent,  # MemoryMateAgent实例
        chunk_size: int = 800,
        chunk_overlap: int = 100
    ):
        self.agent = agent
        self.llm_client = agent.llm_client
        self.text_splitter = ChineseRecursiveTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        self.analyzer = MeetingAnalyzer(self.llm_client)

    async def process_file(
        self,
        file_path: str,
        user_id: str,
        metadata: Dict[str, Any],
        document_store=None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        处理文档的主入口

        Yields:
            流式处理状态和结果
        """
        start_time = datetime.now()
        document_id = metadata.get('document_id', f"doc_{datetime.now().timestamp()}")

        try:
            # ===== 阶段1: 文件加载 =====
            yield {
                "stage": "loading",
                "progress": 0.05,
                "data": {"message": "正在读取文档..."},
                "status": "processing"
            }

            content, extracted_meta, doc_type = FileLoaderFactory.load_file(file_path)

            # 丰富元数据
            doc_metadata = DocumentMetadata(
                filename=metadata.get('filename', os.path.basename(file_path)),
                file_size=metadata.get('file_size', os.path.getsize(file_path)),
                mime_type=metadata.get('mime_type', 'application/octet-stream'),
                doc_type=doc_type,
                uploaded_at=metadata.get('uploaded_at', datetime.now()),
                source=metadata.get('source', 'web'),
                uploaded_by=user_id,
                original_path=file_path,
                author=extracted_meta.get('author'),
                title=extracted_meta.get('title'),
                page_count=extracted_meta.get('page_count'),
                word_count=len(content)
            )

            yield {
                "stage": "loading",
                "progress": 0.1,
                "data": {
                    "document_id": document_id,
                    "doc_type": doc_type.value,
                    "word_count": len(content),
                    "page_count": extracted_meta.get('page_count')
                },
                "status": "completed"
            }

            # ===== 阶段2: 语义切片 =====
            yield {
                "stage": "chunking",
                "progress": 0.15,
                "data": {"message": "正在分析文档结构..."},
                "status": "processing"
            }

            chunks = self.text_splitter.split_text(content)

            yield {
                "stage": "chunking",
                "progress": 0.2,
                "data": {
                    "chunk_count": len(chunks),
                    "avg_chunk_size": len(content) // len(chunks) if chunks else 0
                },
                "status": "completed"
            }

            # ===== 阶段3: LLM分析（流式） =====
            analysis_result = None

            async for analysis_event in self.analyzer.analyze_stream(
                chunks=chunks,
                user_id=user_id,
                context={
                    "user_id": user_id,
                    "upload_time": datetime.now().isoformat(),
                    "document_title": doc_metadata.title
                }
            ):
                # 转发分析事件，调整进度比例
                adjusted_progress = 0.2 + (analysis_event["progress"] * 0.6)
                yield {
                    "stage": analysis_event["stage"],
                    "progress": adjusted_progress,
                    "data": analysis_event["data"],
                    "status": analysis_event["status"]
                }

                if analysis_event["stage"] == "completed":
                    analysis_result = MeetingAnalysisResult(**analysis_event["data"])

            # ===== 阶段4: 存储记忆建议（不自动创建任务）=====
            yield {
                "stage": "storing",
                "progress": 0.85,
                "data": {"message": "正在保存记忆..."},
                "status": "processing"
            }

            stored_memory_ids = []

            # 存储摘要作为文档记忆
            summary_memory = await self.agent.remember(
                user_id=user_id,
                content=f"【会议记录】{analysis_result.meeting_title or doc_metadata.filename}\n\n{analysis_result.summary}",
                memory_type="document",
                importance=0.7
            )
            if summary_memory:
                stored_memory_ids.append("summary_memory")

            # 存储关键决策
            for decision in analysis_result.key_decisions[:5]:  # 最多5条
                mem_id = await self.agent.remember(
                    user_id=user_id,
                    content=f"【会议决策】{decision}",
                    memory_type="fact",
                    importance=0.75
                )
                if mem_id:
                    stored_memory_ids.append(f"decision:{decision[:20]}")

            # 存储用户偏好（高重要性）
            for pref in analysis_result.user_preferences[:3]:
                if pref.get('confidence', 0) > 0.7:
                    await self.agent.remember(
                        user_id=user_id,
                        content=f"【用户偏好】{pref['content']}",
                        memory_type="fact",
                        importance=0.8
                    )

            yield {
                "stage": "storing",
                "progress": 0.95,
                "data": {"stored_memories": len(stored_memory_ids)},
                "status": "completed"
            }

            # ===== 阶段5: 完成 =====
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

            final_result = ProcessingResult(
                document_id=document_id,
                status=ProcessingStatus.COMPLETED,
                metadata=doc_metadata,
                analysis=analysis_result,
                stored_memory_ids=stored_memory_ids
            )

            # 更新文档存储状态
            if document_store:
                await document_store.update_status(
                    document_id=document_id,
                    status="completed",
                    analysis_result=final_result.analysis.to_dict() if final_result.analysis else None
                )

            yield {
                "stage": "completed",
                "progress": 1.0,
                "data": {
                    "document_id": document_id,
                    "result": final_result.analysis.to_dict() if final_result.analysis else {},
                    "pending_actions": {
                        "action_items": len(analysis_result.action_items) if analysis_result else 0,
                        "need_confirmation": True
                    }
                },
                "status": "completed"
            }

        except Exception as e:
            # 更新文档状态为失败
            if document_store:
                await document_store.update_status(
                    document_id=document_id,
                    status="failed"
                )

            yield {
                "stage": "error",
                "progress": 0,
                "data": {"error": str(e)},
                "status": "error"
            }

    async def confirm_action_items(
        self,
        user_id: str,
        document_id: str,
        selected_items: list,
        reminder_times: Dict[int, str]
    ) -> Dict[str, Any]:
        """
        用户确认后创建提醒任务

        Args:
            user_id: 用户ID
            document_id: 文档ID
            selected_items: 用户选中的待办索引列表
            reminder_times: 索引->提醒时间的映射
        """
        # 从存储中获取分析结果
        # 实际实现中需要查询document_store获取analysis_result

        created_tasks = []

        for idx in selected_items:
            # 获取对应的action_item和提醒时间
            reminder_time_str = reminder_times.get(idx)
            if not reminder_time_str:
                continue

            # 解析时间
            from ..utils.time_parser import time_parser
            reminder_time = time_parser.parse(reminder_time_str)

            if reminder_time:
                # 创建任务
                task = await self.agent.precise_scheduler.create_reminder(
                    user_id=user_id,
                    content=f"【会议待办】{selected_items[idx].get('content', '')}",
                    reminder_time=reminder_time,
                    title="会议待办提醒",
                    metadata={
                        'source': 'meeting_document',
                        'document_id': document_id
                    }
                )
                created_tasks.append({
                    'task_id': task.task_id,
                    'content': selected_items[idx].get('content'),
                    'reminder_time': reminder_time.isoformat()
                })

        return {
            "success": True,
            "created_count": len(created_tasks),
            "tasks": created_tasks
        }
```

---

## 三、API接口设计

### 文件上传接口 (`api.py` 新增)

```python
# ============== 新增：文档上传相关接口 ==============

class UploadDocumentRequest(BaseModel):
    """上传文档请求"""
    user_id: str = Field(..., description="用户ID")
    source: str = Field("web", description="来源: web/lark")


class UploadDocumentResponse(BaseModel):
    """上传文档响应"""
    success: bool
    document_id: Optional[str] = None
    message: str
    error: Optional[str] = None


class ConfirmActionItemsRequest(BaseModel):
    """确认待办事项请求"""
    user_id: str = Field(..., description="用户ID")
    document_id: str = Field(..., description="文档ID")
    selected_indices: List[int] = Field(..., description="选中的待办索引")
    reminder_times: Dict[str, str] = Field(default_factory=dict, description="待办索引->提醒时间")


@app.post("/api/documents/upload", response_model=UploadDocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    source: str = Form("web")
):
    """
    上传会议记录文档

    支持格式: PDF, DOCX, TXT, MD
    文件会被保存，然后异步处理
    """
    try:
        # 保存临时文件
        temp_dir = "./temp/uploads"
        os.makedirs(temp_dir, exist_ok=True)

        temp_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{file.filename}")

        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # 保存到文档存储
        from memory_assistant.storage.document_store import DocumentStore
        doc_store = DocumentStore(agent.config.get('storage', {}).get('data_dir', './data'))

        save_result = await doc_store.save_file(
            file_path=temp_path,
            user_id=user_id,
            source=source,
            original_filename=file.filename
        )

        # 清理临时文件
        os.remove(temp_path)

        if save_result["is_duplicate"]:
            return UploadDocumentResponse(
                success=True,
                document_id=save_result["document_id"],
                message="该文件已存在，将使用已有解析结果"
            )

        return UploadDocumentResponse(
            success=True,
            document_id=save_result["document_id"],
            message="文件上传成功，请使用WebSocket连接处理进度"
        )

    except Exception as e:
        return UploadDocumentResponse(success=False, message="", error=str(e))


@app.websocket("/ws/documents/{document_id}")
async def document_processing_websocket(websocket: WebSocket, document_id: str):
    """
    WebSocket流式处理文档

    实时返回解析进度和结果
    """
    await websocket.accept()

    try:
        # 获取文档信息
        from memory_assistant.storage.document_store import DocumentStore
        from memory_assistant.ingestion.document_processor import DocumentProcessor

        doc_store = DocumentStore(agent.config.get('storage', {}).get('data_dir', './data'))
        doc_info = await doc_store.get_document(document_id)

        if not doc_info:
            await websocket.send_json({
                "stage": "error",
                "status": "error",
                "data": {"error": "文档不存在"}
            })
            await websocket.close()
            return

        # 创建处理器
        processor = DocumentProcessor(agent)

        # 开始处理
        async for event in processor.process_file(
            file_path=doc_info["file_path"],
            user_id=doc_info["user_id"],
            metadata={
                "document_id": document_id,
                "filename": doc_info["filename"],
                "source": doc_info["source"]
            },
            document_store=doc_store
        ):
            await websocket.send_json(event)

            # 如果出错或完成，关闭连接
            if event["status"] in ["error", "completed"]:
                break

        await websocket.close()

    except Exception as e:
        await websocket.send_json({
            "stage": "error",
            "status": "error",
            "data": {"error": str(e)}
        })
        await websocket.close()


@app.post("/api/documents/confirm-actions")
async def confirm_action_items(request: ConfirmActionItemsRequest):
    """
    确认并创建会议待办任务

    用户在前端选择要创建的待办事项和提醒时间
    """
    try:
        from memory_assistant.ingestion.document_processor import DocumentProcessor
        processor = DocumentProcessor(agent)

        result = await processor.confirm_action_items(
            user_id=request.user_id,
            document_id=request.document_id,
            selected_items=request.selected_indices,
            reminder_times=request.reminder_times
        )

        return {
            "success": True,
            "data": result
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/documents/{user_id}")
async def list_user_documents(
    user_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """获取用户的文档列表"""
    try:
        from memory_assistant.storage.document_store import DocumentStore
        doc_store = DocumentStore(agent.config.get('storage', {}).get('data_dir', './data'))

        documents = await doc_store.get_user_documents(user_id, limit, offset)

        return {
            "success": True,
            "data": documents,
            "total": len(documents)
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
```

---

## 四、飞书集成

### 飞书文件消息处理 (`platform/lark_adapter.py` 新增)

```python
# 在 LarkAdapter 类中添加

async def handle_file_message(self, user_id: str, file_info: dict) -> str:
    """
    处理飞书收到的文件消息

    Args:
        user_id: 用户ID
        file_info: 文件信息，包含 file_key, file_name 等
    """
    file_key = file_info.get('file_key')
    file_name = file_info.get('file_name', 'unknown')

    try:
        # 1. 下载文件
        file_path = await self._download_file(file_key, file_name)

        # 2. 保存到文档存储
        from ..storage.document_store import DocumentStore
        from ..ingestion.document_processor import DocumentProcessor

        doc_store = DocumentStore(self.data_dir)
        save_result = await doc_store.save_file(
            file_path=file_path,
            user_id=user_id,
            source="lark",
            original_filename=file_name
        )

        # 3. 异步处理文档
        processor = DocumentProcessor(self.agent)

        # 收集所有结果
        results = []
        async for event in processor.process_file(
            file_path=file_path,
            user_id=user_id,
            metadata={
                "document_id": save_result["document_id"],
                "filename": file_name,
                "source": "lark"
            },
            document_store=doc_store
        ):
            if event["status"] == "completed":
                results.append(event["data"])

        # 4. 构建回复消息
        if results and "result" in results[-1]:
            result = results[-1]["result"]

            message = f"""📄 会议记录解析完成！

📌 会议主题：{result.get('meeting_title', '未识别')}

📝 摘要：
{result.get('summary', '')}

✅ 关键决策：
"""
            for i, decision in enumerate(result.get('key_decisions', []), 1):
                message += f"{i}. {decision}\n"

            action_items = result.get('action_items', [])
            if action_items:
                message += f"\n📋 发现 {len(action_items)} 项待办任务：\n"
                for i, item in enumerate(action_items, 1):
                    message += f"{i}. {item.get('content', '')}"
                    if item.get('assignee'):
                        message += f" (负责人：{item['assignee']})"
                    message += "\n"

                message += "\n💡 请在前端界面确认要添加的待办事项和提醒时间。"

            return message
        else:
            return "文档解析失败，请稍后重试。"

    except Exception as e:
        return f"处理文件时出错：{str(e)}"

async def _download_file(self, file_key: str, file_name: str) -> str:
    """从飞书下载文件"""
    import aiohttp

    # 获取文件下载URL
    url = f"{self.BASE_URL}/im/v1/files/{file_key}"
    headers = {"Authorization": f"Bearer {self._get_access_token()}"}

    temp_dir = "./temp/lark_files"
    os.makedirs(temp_dir, exist_ok=True)
    file_path = os.path.join(temp_dir, file_name)

    # 下载文件
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                with open(file_path, 'wb') as f:
                    f.write(await response.read())
                return file_path
            else:
                raise Exception(f"下载文件失败: {response.status}")
```

---

## 五、依赖更新

```txt
# requirements.txt 新增
PyMuPDF>=1.23.0       # PDF处理
python-docx>=0.8.11   # Word处理
chardet>=5.0.0        # 编码检测
aiofiles>=23.0.0      # 异步文件操作（已存在）
```

---

## 六、方案总结

| 特性 | 实现方案 |
|------|----------|
| **文档格式** | PDF(文本型)、DOCX、TXT、Markdown |
| **文件存储** | 本地存储 + SQLite元数据管理，支持SHA256去重 |
| **中文切片** | 递归语义切片，优先按会议结构切分，10-15%重叠 |
| **LLM分析** | 两阶段分析：全局摘要 + 逐块提取，流式输出 |
| **任务创建** | 用户确认后批量创建，不自动创建 |
| **多渠道** | Web: REST API + WebSocket; 飞书: 文件消息回调 |
| **元数据** | 文件名、大小、创建/修改/上传时间、作者、标题、页数、hash、来源等 |
