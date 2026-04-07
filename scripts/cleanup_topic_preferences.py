#!/usr/bin/env python3
import json
import sqlite3
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from memory_assistant.models.user_profile import UserProfile
from memory_assistant.utils.topic_utils import sanitize_topic_preferences


def main() -> int:
    db_path = ROOT_DIR / 'data' / 'memory.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        "SELECT user_id, profile_data FROM users WHERE profile_data IS NOT NULL"
    ).fetchall()

    updated_users = 0
    removed_topics = 0

    for row in rows:
        raw_profile = row['profile_data']
        if not raw_profile:
            continue

        try:
            profile_data = json.loads(raw_profile)
            profile = UserProfile.from_dict(profile_data)
        except Exception as exc:
            print(f"[skip] {row['user_id']} profile_data parse failed: {exc}")
            continue

        before_topics = list(profile.topic_preferences)
        after_topics = sanitize_topic_preferences(before_topics)

        if len(after_topics) == len(before_topics) and all(
            before.topic == after.topic
            and before.weight == after.weight
            and before.interaction_count == after.interaction_count
            for before, after in zip(before_topics, after_topics)
        ):
            continue

        profile.topic_preferences = after_topics
        profile_dict = profile.to_dict()
        interaction_style = profile_dict.get('interaction_style') or {}
        behavior_stats = profile_dict.get('behavior_stats') or {}

        conn.execute(
            """
            UPDATE users
            SET username = COALESCE(?, username),
                name = ?,
                total_interactions = ?,
                total_queries = ?,
                total_memories_created = ?,
                last_interaction = ?,
                preferred_response_length = ?,
                preferred_detail_level = ?,
                preferred_formality = ?,
                proactivity_level = ?,
                expressiveness = ?,
                profile_data = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (
                profile_dict.get('username'),
                profile_dict.get('name'),
                behavior_stats.get('total_interactions', 0),
                behavior_stats.get('total_queries', 0),
                behavior_stats.get('total_memories_created', 0),
                behavior_stats.get('last_interaction'),
                interaction_style.get('preferred_response_length'),
                interaction_style.get('preferred_detail_level'),
                interaction_style.get('preferred_formality'),
                interaction_style.get('proactivity_level'),
                interaction_style.get('expressiveness'),
                json.dumps(profile_dict, ensure_ascii=False),
                row['user_id'],
            )
        )

        updated_users += 1
        removed_topics += max(0, len(before_topics) - len(after_topics))
        print(
            f"[cleaned] {row['user_id']}: {len(before_topics)} -> {len(after_topics)} topics"
        )

    conn.commit()
    conn.close()

    print(
        f"[done] updated_users={updated_users}, removed_topics={removed_topics}, db={db_path}"
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
