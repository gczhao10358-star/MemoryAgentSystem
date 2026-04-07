#!/usr/bin/env python3
"""
批量重分类历史记忆类型。

优先使用 metadata.raw_content 作为分类依据，避免被历史润色内容误导。
默认跳过 document / reminder。
"""
import argparse
import asyncio
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from memory_assistant.core.content_filter import ContentFilter
from memory_assistant.models.memory import MemoryType
from memory_assistant.storage.memory_storage import MemoryStorage
from memory_assistant.storage.metadata_store import SQLiteMetadataStore
from memory_assistant.storage.vector_store import FaissVectorStore


SKIP_TYPES = {"document", "reminder"}


def choose_target_type(entry) -> str | None:
    raw_content = (entry.metadata or {}).get("raw_content")
    source_text = (raw_content or entry.content or "").strip()
    if not source_text:
        return None

    has_time = ContentFilter.has_temporal_reference(source_text)
    target_type = ContentFilter.classify_memory_type(source_text, has_time=has_time)
    if target_type:
        return target_type

    # 没有命中新规则时，保留原类型
    return None


async def main():
    parser = argparse.ArgumentParser(description="Reclassify historical memory types")
    parser.add_argument("--db-path", default=str(ROOT_DIR / "data" / "memory.db"))
    parser.add_argument("--index-path", default=str(ROOT_DIR / "data" / "vector_index"))
    parser.add_argument("--apply", action="store_true", help="Actually write changes")
    args = parser.parse_args()

    metadata_store = SQLiteMetadataStore(db_path=args.db_path)
    vector_store = FaissVectorStore(index_path=args.index_path)
    storage = MemoryStorage(vector_store=vector_store, metadata_store=metadata_store)
    await storage.initialize()

    cursor = metadata_store.conn.execute(
        """
        SELECT memory_id
        FROM memories
        WHERE memory_type NOT IN ('document', 'reminder')
        ORDER BY created_at DESC
        """
    )
    memory_ids = [row["memory_id"] for row in cursor.fetchall()]

    total = 0
    changed = 0
    skipped = 0

    for memory_id in memory_ids:
        entry = await storage.get_memory(memory_id)
        if not entry:
            skipped += 1
            continue

        current_type = entry.memory_type.value
        if current_type in SKIP_TYPES:
            skipped += 1
            continue

        total += 1
        target_type = choose_target_type(entry)
        if not target_type or target_type == current_type:
            continue

        print(f"{memory_id}: {current_type} -> {target_type} | {(entry.metadata or {}).get('raw_content') or entry.content}")

        if args.apply:
            entry.memory_type = MemoryType(target_type)
            entry.metadata = dict(entry.metadata or {})
            entry.metadata["reclassified_from"] = current_type
            entry.metadata["reclassified_by"] = "scripts/reclassify_memory_types.py"
            if await storage.update_memory(entry):
                changed += 1

    if args.apply:
        await storage.save()
    await storage.close()

    print(
        f"done total={total} changed={changed} skipped={skipped} apply={args.apply} db={args.db_path}"
    )


if __name__ == "__main__":
    asyncio.run(main())
