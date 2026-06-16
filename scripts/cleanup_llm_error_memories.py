"""清理已经写入数据库的 LLM 错误记忆。"""
import os
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "memory.db")

def main():
    if not os.path.exists(DB_PATH):
        print(f"db not found: {DB_PATH}")
        return 0
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        """
        SELECT memory_id, user_id, content FROM memories
        WHERE content LIKE '%调用语言模型时出错%'
           OR content LIKE '%[LLM_ERROR]%'
           OR content LIKE '%Error code: 4%'
           OR content LIKE '%Incorrect API key%'
           OR content LIKE '%invalid_api_key%'
        """
    )
    rows = cur.fetchall()
    print(f"Found {len(rows)} dirty memories")
    for r in rows:
        snippet = (r[2] or "")[:80].replace("\n", " ")
        print(f" - id={r[0]} user={r[1]} content={snippet}")
    if rows:
        cur.executemany(
            "DELETE FROM memories WHERE memory_id=?",
            [(r[0],) for r in rows],
        )
        con.commit()
        print(f"Deleted {len(rows)} rows from memories table")
    con.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
