#!/usr/bin/env python3
"""
内容过滤器回归测试
重点防止短确认词被误判为事实记忆。
"""
import os
import sys
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from memory_assistant.core.content_filter import ContentFilter


class ContentFilterTests(unittest.TestCase):
    def test_confirmation_phrase_is_treated_as_chitchat(self):
        should_store, metadata = ContentFilter.should_store_memory("好吧")

        self.assertFalse(should_store)
        self.assertEqual(metadata["filtered_reason"], "chitchat")

    def test_short_confirmation_variants_are_filtered(self):
        for text in ["行吧", "可以", "嗯嗯"]:
            with self.subTest(text=text):
                should_store, metadata = ContentFilter.should_store_memory(text)
                self.assertFalse(should_store)
                self.assertEqual(metadata["filtered_reason"], "chitchat")

    def test_schedule_statement_is_still_valuable(self):
        should_store, metadata = ContentFilter.should_store_memory("明天有个会议")

        self.assertTrue(should_store)
        self.assertEqual(metadata["memory_type"], "event")

    def test_preference_statement_is_still_valuable(self):
        should_store, metadata = ContentFilter.should_store_memory("我喜欢喝拿铁")

        self.assertTrue(should_store)
        self.assertEqual(metadata["memory_type"], "fact")

    def test_identity_statement_is_classified_as_fact(self):
        should_store, metadata = ContentFilter.should_store_memory("我是一名大学生")

        self.assertTrue(should_store)
        self.assertEqual(metadata["memory_type"], "fact")

    def test_action_item_is_classified_as_task(self):
        should_store, metadata = ContentFilter.should_store_memory("我需要准备面试材料")

        self.assertTrue(should_store)
        self.assertEqual(metadata["memory_type"], "task")

    def test_deadline_delivery_is_classified_as_task(self):
        should_store, metadata = ContentFilter.should_store_memory("周五前提交周报")

        self.assertTrue(should_store)
        self.assertEqual(metadata["memory_type"], "task")

    def test_opinionated_statement_is_not_stored_as_durable_memory(self):
        should_store, metadata = ContentFilter.should_store_memory("我觉得这个方案风险有点大")

        self.assertFalse(should_store)
        self.assertEqual(metadata["filtered_reason"], "low_value")


if __name__ == "__main__":
    unittest.main()
