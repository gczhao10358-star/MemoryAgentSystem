"""
记忆内容过滤策略
判断哪些内容值得存入长期记忆
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
        r'^嗯+[。！]?$',
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
        r'^[请问]?.*[是什么|在哪里|怎么做|为什么|有多少].*[？?]$',
        r'^[请问]?.*[(查询|搜索|查找|检索)].*[？?]?$',
        r'^[(帮我|给我|可以)].*[看看|看看|查一下|找一下].*',
        r'.*[(查询|查找|搜索)]我的.*',
    ]

    # 值得记忆的内容模式
    VALUABLE_PATTERNS = [
        # 安排/计划 - 放宽匹配条件
        r'[(明天|后天|下周|周日|周一|周二|周三|周四|周五|周六|周日|周1|周2|周3|周4|周5|周6|周7|星期)].*[(要|需要|计划|准备|去|参加|做|有个)]',
        r'[(会议|约会|活动|考试|面试|报告|演讲|聚会|聚餐|见面|差旅|出差|旅行|旅游)].*[(在|定于|安排|是|明天|后天|下周)]',
        r'[(提交|截止|到期|完成|截止)].*[日前|号|周]',
        r'[(记得|别忘了|提醒|记住)].*[(做|去|参加|交|完成|拿|取|买)]',

        # 重要信息
        r'[(生日|纪念日|节日)].*[(是|在)]',
        r'[(账号|密码|地址|电话|邮箱|身份证号)]',
        r'[(喜欢|讨厌|感兴趣|爱好|热衷|痴迷|不喜欢|反感|厌恶|擅长|精通|不擅长|不会)]',
        r'[(工作|职业|公司|职位|专业|岗位)]',
        r'[(住址|地址|位置|地点|住在)]',
        r'[(姓名|名字|称呼|叫)]',

        # 待办任务 - 放宽匹配
        r'[(待办|任务|todo|TODO|提醒|需要)].*[:：]',
        r'[(帮我|我要|我需要)].*[(记录|记一下|设置|添加|创建)].*[(任务|提醒|待办)]',
        r'^\s*[-•·]\s+.*[(完成|处理|做|准备|买|拿|取)]',
        r'[(清单|列表)].*[:：]',
        r'[(记得|别忘了)].*[(做|去|参加|交|完成|拿|取|买)]',
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
        r'[(取消|删除|移除|清空|清除)].*[(所有|全部|一切)].*[(安排|计划|日程|任务|待办)]',
        r'[(取消|删除|移除|清空|清除)].*\d{1,2}[月\-\.]?\d{1,2}[日号]?.*[(安排|计划|日程|任务|待办)]',
        r'\d{1,2}[月\-\.]?\d{1,2}[日号]?.*[(所有|全部)].*[(取消|删除|清空)]',
        r'[(取消|删除|移除|清空)].*(?:明天|后天|今天|昨天|下周|这周|本周)',
        r'[(取消|删除|移除|清空)].*[(会议|约会|活动|考试|面试|报告|演讲|聚会|任务|待办|安排)]',
        r'^\s*[(删除|取消|移除|清空)].*\d{1,2}[号日].*',
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
        if re.search(r'[(查|看看|找)].*[(我的|我)].*[(记忆|记得|安排|计划|日程|待办)]', content):
            return True
        if re.search(r'[(我的|我)].*[(记忆|安排|计划|日程|待办)].*[(是|有)].*[什么|哪些]', content):
            return True
        # 检查 "X号我要做什么" 这类查询 - 更严格的匹配
        if re.search(r'\d{1,2}[号日].*[(我要|我有什么)].*[(做|安排|干嘛)]', content):
            return True
        # 检查 "X号有什么安排" 这类查询
        if re.search(r'\d{1,2}[号日].*[(有什么|有哪些)].*[(安排|计划)]', content):
            return True
        # 检查其他询问模式（但排除以"我"开头的陈述）
        if re.search(r'^[请问]', content):
            for pattern in ContentFilter.QUERY_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE):
                    return True
        # 以问号结尾的短句通常也是询问（但排除"我要..."这样的陈述）
        if (content.endswith('?') or content.endswith('？')) and not re.search(r'^我[要|想|需要]', content):
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

        # 3. 检查是否是会议纪要（高价值）
        if ContentFilter.is_meeting_notes(content):
            return True, 'event', 0.9

        # 4. 检查其他有价值内容
        for pattern in ContentFilter.VALUABLE_PATTERNS:
            if re.search(pattern, content):
                # 判断具体类型 - 更宽松的匹配
                if re.search(r'[(会议|约会|活动|考试|面试|报告|演讲|聚会|聚餐|见面|差旅|出差|旅行|旅游|提交|截止|到期)]', content):
                    return True, 'event', 0.8
                elif re.search(r'[(生日|纪念日|节日)]', content):
                    return True, 'event', 0.85
                elif re.search(r'[(记得|别忘了|提醒|记住)].*[(做|去|拿|取|买|参加|交|完成)]', content):
                    return True, 'reminder', 0.75
                elif re.search(r'[(待办|任务|清单|列表)]', content):
                    return True, 'task', 0.7
                elif re.search(r'[(需要|我要|帮我)].*[(做|去|拿|取|买|准备)]', content):
                    return True, 'task', 0.65
                else:
                    return True, 'fact', 0.6

        # 5. 内容长度判断（适中长度且有意义）- 放宽条件
        if 15 <= len(content) <= 500:
            # 检查是否包含具体信息
            if re.search(r'[(是|在|有|需要|准备|喜欢|讨厌|擅长)].*[(做|去|参加|完成|提交|吃|玩|用)]', content):
                return True, 'fact', 0.5

        # 6. 对话类记忆（只要不是闲聊和查询，短对话也可以作为chat类型存储）
        if 10 <= len(content) <= 200:
            # 检查是否包含一些实质性内容
            if re.search(r'[(我|我们|我的)].*[(觉得|认为|想|感觉|看法)]', content):
                return True, 'chat', 0.4

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
    is_valuable, mem_type, _ = ContentFilter.is_valuable(content)
    return mem_type if is_valuable else None
