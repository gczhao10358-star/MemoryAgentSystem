"""
原始文件存储管理
"""
import os
import shutil
import hashlib
import json
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
        original_filename: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
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
                 mime_type, doc_type, uploaded_at, source, metadata, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                json.dumps(metadata or {}, ensure_ascii=False),
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
        analysis_result: Optional[Dict] = None,
        metadata_updates: Optional[Dict[str, Any]] = None
    ):
        """更新处理状态"""
        with sqlite3.connect(self.db_path) as conn:
            existing_metadata: Dict[str, Any] = {}
            if metadata_updates:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT metadata FROM documents WHERE document_id = ?",
                    (document_id,)
                ).fetchone()
                if row:
                    existing_metadata = self._parse_json_field(row["metadata"], {})
                existing_metadata.update(metadata_updates)

            if analysis_result:
                if metadata_updates:
                    conn.execute("""
                        UPDATE documents
                        SET status = ?, analysis_result = ?, metadata = ?
                        WHERE document_id = ?
                    """, (
                        status,
                        json.dumps(analysis_result, ensure_ascii=False),
                        json.dumps(existing_metadata, ensure_ascii=False),
                        document_id,
                    ))
                else:
                    conn.execute("""
                        UPDATE documents
                        SET status = ?, analysis_result = ?
                        WHERE document_id = ?
                    """, (status, json.dumps(analysis_result, ensure_ascii=False), document_id))
            else:
                if metadata_updates:
                    conn.execute("""
                        UPDATE documents
                        SET status = ?, metadata = ?
                        WHERE document_id = ?
                    """, (
                        status,
                        json.dumps(existing_metadata, ensure_ascii=False),
                        document_id,
                    ))
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
            if not row:
                return None
            result = dict(row)
            result["metadata"] = self._parse_json_field(result.get("metadata"), {})
            return result

    def _parse_json_field(self, value: Optional[str], default: Any) -> Any:
        """解析JSON字段，失败时返回默认值。"""
        if not value:
            return default
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return default
