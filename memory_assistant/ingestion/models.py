"""
会议记录文档解析 - 数据模型
定义文档摄取模块的核心数据结构
"""
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
    # 基础文件信息（无默认值）
    filename: str
    file_size: int
    mime_type: str
    doc_type: DocumentType
    uploaded_at: datetime
    source: str  # "web", "lark"
    uploaded_by: str  # user_id

    # 可选的扩展元数据（有默认值）
    file_created_at: Optional[datetime] = None  # 文件系统创建时间
    file_modified_at: Optional[datetime] = None  # 文件最后修改时间
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
