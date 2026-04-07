#!/usr/bin/env python3
"""
会议解析器回归测试
重点防止待办事项因截止日期描述不同而重复展示。
"""
import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from memory_assistant.ingestion.meeting_analyzer import MeetingAnalyzer


class MeetingAnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.analyzer = MeetingAnalyzer(llm_client=None)

    def test_action_items_with_and_without_deadline_are_deduplicated(self):
        items = [
            {
                "content": "完成用户登录接口开发",
                "assignee": "李开发",
                "deadline": "",
                "priority": "medium",
                "should_remind": True,
            },
            {
                "content": "完成用户登录接口开发，截止4月5日",
                "assignee": "李开发",
                "deadline": "4月5日",
                "priority": "medium",
                "should_remind": True,
            },
        ]

        deduped = self.analyzer._deduplicate_action_items(items)

        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["content"], "完成用户登录接口开发")
        self.assertEqual(deduped[0]["deadline"], "4月5日")

    def test_deadline_clause_is_removed_from_normalized_content(self):
        normalized = self.analyzer._normalize_action_item({
            "content": "编写测试用例，截止4月6日",
            "assignee": "王测试",
            "deadline": "4月6日",
            "priority": "medium",
            "should_remind": True,
        })

        self.assertEqual(normalized["content"], "编写测试用例")
        self.assertEqual(normalized["deadline"], "4月6日")


if __name__ == "__main__":
    unittest.main()
