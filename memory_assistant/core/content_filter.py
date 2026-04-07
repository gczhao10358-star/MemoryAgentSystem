"""
记忆内容过滤策略
判断哪些内容值得存入持久记忆
"""
import re
from typing import Tuple, Optional, List
from datetime import datetime


class ContentFilter:
    """内容过滤器 - 判断记忆的价值"""

    # 闲聊/无意义内容的模式
    CHITCHAT_PATTERNS = [
        r'^你好[啊吗]?[。！]?$',
        r'^在吗[？?]$',
        r'^谢谢[。！]?$',
        r'^再见[。！]?$',
        r'^好的?$',
        r'^好吧[。！]?$',
        r'^行吧[。！]?$',
        r'^可以[。！]?$',
        r'^嗯+[。！]?$',
        r'^嗯嗯+[。！]?$',
        r'^哦+[。！]?$',
        r'^哈哈+$',
        r'^拜拜+$',
        r'^你是谁[？?]$',
        r'^你能做什么[？?]$',
        r'^最近好吗[？?]$',
        r'^吃了吗[？?]$',
        r'^天气怎么样[？?]$',
    ]

    # 询问类内容的模式
    QUERY_PATTERNS = [
        r'^(?:请问)?.*(?:是什么|在哪里|怎么做|为什么|有多少).*[？?]$',
        r'^(?:请问)?.*(?:查询|搜索|查找|检索).*[？?]?$',
        r'^(?:帮我|给我|可以).*(?:看看|查一下|找一下).*',
        r'.*(?:查询|查找|搜索)我的.*',
    ]

    REMINDER_PATTERNS = [
        r'(?:提醒我|记得提醒我|叫我|闹钟|到时候提醒我)',
        r'(?:记得|别忘了|提醒|记住).*(?:做|去|参加|交|完成|拿|取|买)',
    ]

    EVENT_PATTERNS = [
        r'(?:明天|后天|下周|周日|周一|周二|周三|周四|周五|周六|周天|周[1-7]|星期(?:一|二|三|四|五|六|日|天)?).*(?:去|参加|出席|有个|安排了)',
        r'(?:会议|约会|活动|考试|面试|报告|演讲|聚会|聚餐|见面|差旅|出差|旅行|旅游).*(?:在|定于|安排|是|明天|后天|下周|今天|周)',
        r'(?:生日|纪念日|节日).*(?:是|在)',
    ]

    TASK_PATTERNS = [
        r'^(?:待办|任务|todo|TODO)[:：]?\s*\S+',
        r'(?:清单|列表).*[:：]',
        r'^\s*[-•·]\s+',
        r'(?:提交|截止|到期).*(?:前|之前|日前|号|本周|这周|下周)',
        r'(?:周[一二三四五六日天]|下周|本周|这周|\d{1,2}[号日]).{0,4}(?:前|之前).*(?:提交|完成|处理|整理|准备|联系|跟进|修复|确认)',
        r'^(?:我|我们)(?:还)?(?:要|得|需要|准备|计划|打算)?(?:把|将)?[\u4e00-\u9fa5A-Za-z0-9_，、\s]{0,20}(?:完成|处理|整理|准备|编写|提交|联系|跟进|修复|安排|确认|补充|学习|复习|制作|更新)',
        r'^(?:先|需要|还得|得)\S{0,20}(?:完成|处理|整理|准备|提交|联系|跟进|修复|安排|确认)',
        r'(?:帮我|我要|我需要).*(?:记录|记一下|设置|添加|创建).*(?:任务|待办)',
    ]

    FACT_PATTERNS = [
        r'(?:账号|密码|地址|电话|邮箱|身份证号)',
        r'(?:喜欢|讨厌|感兴趣|爱好|热衷|痴迷|不喜欢|反感|厌恶|擅长|精通|不擅长|不会)',
        r'(?:工作|职业|公司|职位|专业|岗位)',
        r'(?:住址|地址|位置|地点|住在)',
        r'(?:姓名|名字|称呼|叫)',
        r'(?:过敏|不能吃|忌口)',
        r'(?:习惯|经常|总是|从不)',
    ]

    PERSONAL_ATTRIBUTE_PATTERNS = [
        r'(?:我|本人).*(?:喜欢|讨厌|反感|厌恶|不爱|不爱吃)',
        r'(?:我|本人).*(?:过敏|不能吃|忌口)',
        r'(?:我|本人).*(?:擅长|不擅长|会|不会)',
        r'(?:我|本人).*(?:习惯|经常|总是|从不)',
        r'(?:我|本人).*(?:是|为).*(?:学生|老师|工程师|程序员|产品经理|设计师|职业|职位|身份)',
        r'(?:我的|本人).*(?:名字|姓名|称呼|昵称)',
        r'(?:我|本人).*(?:住|居住|工作).*(?:在|于)',
        r'(?:我|本人).*(?:爱好|兴趣|热衷于)',
    ]

    # 会议纪要特征
    MEETING_PATTERNS = [
        r'会议纪要[：:]',
        r'会议记录[：:]',
        r'会议主题[：:]',
        r'会议时间[：:]',
        r'参会人员[：:]',
        r'会议内容[：:]',
        r'待办事项[：:]',
        r'\d{4}[年/-]\d{1,2}[月/-]\d{1,2}[日]?.*会议',
    ]

    # 删除/取消指令模式
    DELETE_PATTERNS = [
        r'(?:取消|删除|移除|清空|清除).*(?:所有|全部|一切).*(?:安排|计划|日程|任务|待办)',
        r'(?:取消|删除|移除|清空|清除).*\d{1,2}[月\-\.]?\d{1,2}[日号]?.*(?:安排|计划|日程|任务|待办)',
        r'\d{1,2}[月\-\.]?\d{1,2}[日号]?.*(?:所有|全部).*(?:取消|删除|清空)',
        r'(?:取消|删除|移除|清空).*(?:明天|后天|今天|昨天|下周|这周|本周)',
        r'(?:取消|删除|移除|清空).*(?:会议|约会|活动|考试|面试|报告|演讲|聚会|任务|待办|安排)',
        r'^\s*(?:删除|取消|移除|清空).*\d{1,2}[号日].*',
    ]

    TEMPORAL_PATTERNS = [
        r'(?:今天|明天|后天|昨天|下周|本周|这周|周[一二三四五六日天]|星期[一二三四五六日天])',
        r'\d{1,2}[月/.-]\d{1,2}[日号]?',
        r'\d{4}[年/.-]\d{1,2}[月/.-]\d{1,2}[日号]?',
        r'\d{1,2}[:：]\d{2}',
        r'\d{1,2}\s*(?:点|时)(?:半|整|\d{1,2}分?)?',
        r'(?:上午|下午|中午|晚上|凌晨|傍晚)',
    ]

    @staticmethod
    def is_delete_command(content: str) -> bool:
        """判断是否为删除/取消指令"""
        content = content.strip()
        for pattern in ContentFilter.DELETE_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def extract_delete_date(content: str) -> Optional[str]:
        """
        从删除指令中提取日期
        返回: YYYY-MM-DD 格式或 None
        """
        import re
        from datetime import datetime, timedelta

        now = datetime.now()
        content = content.strip()

        # 匹配 "X月X日" 或 "X.X" 或 "X-X"
        date_match = re.search(r'(\d{1,2})[月\-\.](\d{1,2})[日号]?', content)
        if date_match:
            month = int(date_match.group(1))
            day = int(date_match.group(2))
            year = now.year
            # 如果月份小于当前月，可能是明年
            if month < now.month:
                year += 1
            try:
                return datetime(year, month, day).strftime('%Y-%m-%d')
            except ValueError:
                pass

        # 匹配 "X号" 或 "X日"
        day_match = re.search(r'(\d{1,2})[号日]', content)
        if day_match:
            day = int(day_match.group(1))
            if day >= now.day:
                # 本月
                try:
                    return now.replace(day=day).strftime('%Y-%m-%d')
                except ValueError:
                    pass
            else:
                # 下月
                try:
                    if now.month == 12:
                        return now.replace(year=now.year+1, month=1, day=day).strftime('%Y-%m-%d')
                    else:
                        return now.replace(month=now.month+1, day=day).strftime('%Y-%m-%d')
                except ValueError:
                    pass

        # 匹配相对日期
        if re.search(r'今天', content):
            return now.strftime('%Y-%m-%d')
        if re.search(r'明天', content):
            return (now + timedelta(days=1)).strftime('%Y-%m-%d')
        if re.search(r'后天', content):
            return (now + timedelta(days=2)).strftime('%Y-%m-%d')

        return None

    @staticmethod
    def is_chitchat(content: str) -> bool:
        """判断是否为闲聊"""
        content = content.strip()
        for pattern in ContentFilter.CHITCHAT_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def is_query(content: str) -> bool:
        """判断是否为询问/查询"""
        content = content.strip()
        # 检查是否是询问记忆库 - 明确查询意图
        if re.search(r'(?:查|看看|找).*(?:我的|我).*(?:记忆|记得|安排|计划|日程|待办)', content):
            return True
        if re.search(r'(?:我的|我).*(?:记忆|安排|计划|日程|待办).*(?:是|有).*(?:什么|哪些)', content):
            return True
        # 检查 "X号我要做什么" 这类查询 - 更严格的匹配
        if re.search(r'\d{1,2}[号日].*(?:我要|我有什么).*(?:做|安排|干嘛)', content):
            return True
        # 检查 "X号有什么安排" 这类查询
        if re.search(r'\d{1,2}[号日].*(?:有什么|有哪些).*(?:安排|计划)', content):
            return True
        # 检查其他询问模式（但排除以"我"开头的陈述）
        if re.search(r'^请问', content):
            for pattern in ContentFilter.QUERY_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE):
                    return True
        # 以问号结尾的短句通常也是询问（但排除"我要..."这样的陈述）
        if (content.endswith('?') or content.endswith('？')) and not re.search(r'^我(?:要|想|需要)', content):
            return True
        return False

    @staticmethod
    def is_meeting_notes(content: str) -> bool:
        """判断是否为会议纪要"""
        content = content.strip()
        for pattern in ContentFilter.MEETING_PATTERNS:
            if re.search(pattern, content):
                return True
        return False

    @staticmethod
    def _matches_any(content: str, patterns: List[str]) -> bool:
        return any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns)

    @staticmethod
    def is_personal_attribute(content: str) -> bool:
        content = content.strip()
        return ContentFilter._matches_any(content, ContentFilter.PERSONAL_ATTRIBUTE_PATTERNS)

    @staticmethod
    def has_temporal_reference(content: str) -> bool:
        content = content.strip()
        return ContentFilter._matches_any(content, ContentFilter.TEMPORAL_PATTERNS)

    @staticmethod
    def classify_memory_type(content: str, has_time: bool = False) -> Optional[str]:
        content = content.strip()
        if not content:
            return None

        if ContentFilter.is_chitchat(content) or ContentFilter.is_query(content):
            return None
        if ContentFilter.is_meeting_notes(content):
            return "event"
        if ContentFilter._matches_any(content, ContentFilter.REMINDER_PATTERNS):
            return "reminder"
        if ContentFilter._matches_any(content, ContentFilter.EVENT_PATTERNS):
            return "event"
        if ContentFilter._matches_any(content, ContentFilter.TASK_PATTERNS):
            return "task"
        if ContentFilter.is_personal_attribute(content) and not has_time:
            return "fact"
        if ContentFilter._matches_any(content, ContentFilter.FACT_PATTERNS):
            return "fact"
        if 15 <= len(content) <= 500 and re.search(r'(?:是|在|有).*(?:做|去|参加|吃|玩|用)', content):
            return "fact"
        return None

    @staticmethod
    def is_valuable(content: str) -> Tuple[bool, Optional[str], float]:
        """
        判断内容是否值得记忆

        Returns:
            (是否值得记忆, 记忆类型, 重要性分数)
        """
        content = content.strip()

        # 1. 首先排除闲聊
        if ContentFilter.is_chitchat(content):
            return False, None, 0.0

        # 2. 排除查询类
        if ContentFilter.is_query(content):
            return False, None, 0.0

        memory_type = ContentFilter.classify_memory_type(content)
        if memory_type == 'event':
            importance = 0.9 if ContentFilter.is_meeting_notes(content) else 0.8
            return True, memory_type, importance
        if memory_type == 'reminder':
            return True, memory_type, 0.75
        if memory_type == 'task':
            return True, memory_type, 0.7
        if memory_type == 'fact':
            return True, memory_type, 0.6

        return False, None, 0.0

    @staticmethod
    def should_store_memory(content: str, context: dict = None) -> Tuple[bool, dict]:
        """
        综合判断是否应该存储记忆

        Returns:
            (是否存储, 存储元数据)
        """
        is_valuable, mem_type, importance = ContentFilter.is_valuable(content)

        metadata = {
            'should_store': is_valuable,
            'memory_type': mem_type,
            'importance': importance,
            'filtered_reason': None
        }

        if not is_valuable:
            if ContentFilter.is_chitchat(content):
                metadata['filtered_reason'] = 'chitchat'
            elif ContentFilter.is_query(content):
                metadata['filtered_reason'] = 'query'
            else:
                metadata['filtered_reason'] = 'low_value'

        return is_valuable, metadata

    @staticmethod
    def extract_memories_from_text(content: str) -> List[dict]:
        """
        从长文本中提取多个记忆点
        例如从会议纪要中提取多个待办事项
        """
        memories = []

        # 提取待办事项
        todo_pattern = r'(?:待办|TODO|任务)[:：]\s*(.*?)(?=\n\n|$)'
        todo_match = re.search(todo_pattern, content, re.DOTALL | re.IGNORECASE)
        if todo_match:
            todos = todo_match.group(1).strip().split('\n')
            for todo in todos:
                todo = todo.strip().strip('-').strip('•').strip()
                if todo and len(todo) > 5:
                    memories.append({
                        'content': todo,
                        'type': 'task',
                        'importance': 0.7
                    })

        # 提取关键决定
        decision_pattern = r'(?:决定|决议|结论)[:：]\s*(.*?)(?=\n\n|$)'
        decision_match = re.search(decision_pattern, content, re.DOTALL | re.IGNORECASE)
        if decision_match:
            decisions = decision_match.group(1).strip().split('\n')
            for decision in decisions:
                decision = decision.strip().strip('-').strip('•').strip()
                if decision and len(decision) > 5:
                    memories.append({
                        'content': decision,
                        'type': 'fact',
                        'importance': 0.8
                    })

        # 如果没有提取到具体项，但整体是会议纪要，存储整体
        if not memories and ContentFilter.is_meeting_notes(content):
            memories.append({
                'content': content,
                'type': 'event',
                'importance': 0.9
            })

        return memories


# 便捷函数
def should_remember(content: str) -> bool:
    """快速判断是否应该记住"""
    should_store, _ = ContentFilter.should_store_memory(content)
    return should_store


def get_memory_type(content: str) -> Optional[str]:
    """获取内容应该被分类的记忆类型"""
    return ContentFilter.classify_memory_type(content)
