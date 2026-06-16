"""
时间解析工具
支持自然语言时间转换为具体时间戳
"""
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple
import jieba


class TimeParser:
    """自然语言时间解析器"""

    def __init__(self):
        # 时间关键词映射
        self.time_keywords = {
            # 今天
            '今天': 0,
            '今日': 0,
            # 明天
            '明天': 1,
            '明日': 1,
            '次日': 1,
            '后天': 2,
            '后日': 2,
            # 昨天
            '昨天': -1,
            '昨日': -1,
            '前天': -2,
            # 时间
            '早上': 'morning',
            '早晨': 'morning',
            '上午': 'morning',
            '中午': 'noon',
            '下午': 'afternoon',
            '傍晚': 'evening',
            '晚上': 'evening',
            '夜间': 'night',
            '深夜': 'night',
        }

        # 时间段对应的小时范围
        self.time_periods = {
            'morning': (8, 12),
            'noon': (12, 14),
            'afternoon': (14, 18),
            'evening': (18, 22),
            'night': (22, 6),  # 跨天
        }

        # 数字映射
        self.number_map = {
            '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
            '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
            '十一': 11, '十二': 12, '两': 2,
        }

    def parse(self, text: str, base_time: Optional[datetime] = None) -> Optional[datetime]:
        """
        解析自然语言时间为具体时间

        Args:
            text: 自然语言时间描述，如"今天下午3点"、"明天早上"、"3天后"、"周五下午17点"
            base_time: 基准时间，默认为当前时间

        Returns:
            解析后的 datetime 对象，解析失败返回 None
        """
        if base_time is None:
            base_time = datetime.now()

        text = text.strip()

        # 0. 首先尝试解析 ISO 8601 格式（前端 toISOString 返回的格式）
        result = self._parse_iso8601(text)
        if result:
            return result

        text_lower = text.lower()

        # 尝试各种解析模式
        result = None

        # 1a. 解析星期/周X+时间（如"周五下午17点"、"下周一上午9点"）
        result = self._parse_weekday_datetime(text, base_time)
        if result:
            return result

        # 1. 解析相对日期+时间
        result = self._parse_relative_datetime(text, base_time)
        if result:
            return result

        # 2. 解析绝对时间
        result = self._parse_absolute_time(text, base_time)
        if result:
            return result

        # 3. 解析相对时间（分钟/小时/天/周/月后）
        result = self._parse_relative_time(text, base_time)
        if result:
            return result

        # 4. 解析特殊格式
        result = self._parse_special_formats(text, base_time)
        if result:
            return result

        return None

    def _parse_iso8601(self, text: str) -> Optional[datetime]:
        """解析 ISO 8601 格式时间（如 2026-03-15T10:00:00.000Z 或 2026-03-15T10:00:00+08:00）"""
        import re
        from datetime import timezone

        # 匹配 ISO 8601 格式
        # 2026-03-15T10:00:00.000Z
        # 2026-03-15T10:00:00Z
        # 2026-03-15T10:00:00+08:00
        # 2026-03-15T10:00:00.000+08:00
        pattern = r'^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:?\d{2})?$'

        match = re.match(pattern, text)
        if match:
            try:
                year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                hour, minute, second = int(match.group(4)), int(match.group(5)), int(match.group(6))

                tz_str = match.group(8)

                dt = datetime(year, month, day, hour, minute, second)

                if tz_str:
                    if tz_str == 'Z' or tz_str == 'z':
                        # UTC 时间，转换为本地时间（东八区）
                        from pytz import timezone
                        sh = timezone('Asia/Shanghai')
                        dt = dt.replace(tzinfo=timezone('UTC')).astimezone(sh)
                        return dt.replace(tzinfo=None)
                    elif tz_str.startswith('+') or tz_str.startswith('-'):
                        # 带时区偏移，转换为本地时间
                        from pytz import timezone
                        sh = timezone('Asia/Shanghai')
                        # 解析时区偏移
                        sign = 1 if tz_str[0] == '+' else -1
                        tz_str = tz_str[1:].replace(':', '')
                        tz_hours = int(tz_str[:2])
                        tz_minutes = int(tz_str[2:]) if len(tz_str) > 2 else 0
                        from datetime import timedelta
                        offset = timedelta(hours=sign * tz_hours, minutes=sign * tz_minutes)
                        from datetime import timezone as dt_timezone
                        dt = dt.replace(tzinfo=dt_timezone(offset)).astimezone(sh)
                        return dt.replace(tzinfo=None)

                return dt
            except (ValueError, TypeError):
                return None

        return None

    # 中文星期对应的 weekday() 数值（周一=0 ... 周日=6）
    _WEEKDAY_MAP = {
        '一': 0, '1': 0, '壹': 0,
        '二': 1, '2': 1, '贰': 1, '两': 1,
        '三': 2, '3': 2, '叁': 2,
        '四': 3, '4': 3, '肆': 3,
        '五': 4, '5': 4, '伍': 4,
        '六': 5, '6': 5, '陆': 5,
        '日': 6, '天': 6, '七': 6, '7': 6,
    }

    def _parse_weekday_datetime(self, text: str, base_time: datetime) -> Optional[datetime]:
        """解析"(本周|这周|下周|下下周)?周X/星期X/礼拜X (上午|下午|...)? (N点|HH:MM)?"。

        默认语义：未带"本周/下周"前缀时，"周X"指"本周X"；若该日已过则视为"下周X"。
        """
        # 优先尝试带前缀（下下周/下周/上周/这周/本周）的匹配
        prefix_pattern = re.compile(
            r'(下下周|下周|这周|本周|上周)\s*'
            r'(?:周|星期|礼拜)?\s*([一二三四五六日天1234567])'
            r'(?:[\s,，的]*?(早上|早晨|清晨|上午|中午|下午|傍晚|晚上|夜间|深夜))?'
            r'(?:[\s,，的]*?(\d{1,2}|[一二三四五六七八九十两])\s*(?:[点时])\s*(半|整|\d{1,2})?\s*分?)?'
            r'(?:[\s,，的]*?(\d{1,2})[:：](\d{2}))?'
        )
        # 无前缀匹配（"周X/星期X/礼拜X"）
        bare_pattern = re.compile(
            r'(?:周|星期|礼拜)\s*([一二三四五六日天1234567])'
            r'(?:[\s,，的]*?(早上|早晨|清晨|上午|中午|下午|傍晚|晚上|夜间|深夜))?'
            r'(?:[\s,，的]*?(\d{1,2}|[一二三四五六七八九十两])\s*(?:[点时])\s*(半|整|\d{1,2})?\s*分?)?'
            r'(?:[\s,，的]*?(\d{1,2})[:：](\d{2}))?'
        )

        match = prefix_pattern.search(text)
        if match:
            week_offset_word = match.group(1)
            wd_char = match.group(2)
            period_word = match.group(3)
            hour_word = match.group(4)
            minute_word = match.group(5)
            colon_hour = match.group(6)
            colon_minute = match.group(7)
        else:
            match = bare_pattern.search(text)
            if not match:
                return None
            week_offset_word = None
            wd_char = match.group(1)
            period_word = match.group(2)
            hour_word = match.group(3)
            minute_word = match.group(4)
            colon_hour = match.group(5)
            colon_minute = match.group(6)

        target_weekday = self._WEEKDAY_MAP.get(wd_char)
        if target_weekday is None:
            return None

        # 计算目标日期
        today = base_time.replace(hour=0, minute=0, second=0, microsecond=0)
        cur_weekday = today.weekday()

        if week_offset_word == '上周':
            # 上周对应的同星期
            base_monday = today - timedelta(days=cur_weekday + 7)
            target_date = base_monday + timedelta(days=target_weekday)
        elif week_offset_word == '下周':
            base_monday = today - timedelta(days=cur_weekday) + timedelta(days=7)
            target_date = base_monday + timedelta(days=target_weekday)
        elif week_offset_word == '下下周':
            base_monday = today - timedelta(days=cur_weekday) + timedelta(days=14)
            target_date = base_monday + timedelta(days=target_weekday)
        elif week_offset_word in ('这周', '本周'):
            base_monday = today - timedelta(days=cur_weekday)
            target_date = base_monday + timedelta(days=target_weekday)
        else:
            # 未带前缀：默认本周；若该日已过则顺延到下周
            base_monday = today - timedelta(days=cur_weekday)
            target_date = base_monday + timedelta(days=target_weekday)
            if target_date < today:
                target_date = target_date + timedelta(days=7)

        # 解析小时/分钟
        hour: Optional[int] = None
        minute: int = 0

        if colon_hour is not None:
            try:
                hour = int(colon_hour)
                minute = int(colon_minute)
            except (TypeError, ValueError):
                hour = None
        elif hour_word is not None:
            hour = self._parse_number(hour_word)
            if minute_word:
                if minute_word == '半':
                    minute = 30
                elif minute_word == '整':
                    minute = 0
                else:
                    try:
                        minute = int(minute_word)
                    except (TypeError, ValueError):
                        minute = 0

        # 处理 12 小时制：仅当用户给的小时数 < 12 且明确是下午/晚上/傍晚时，才 +12
        # 用户写"17点"、"15:30" 等 24h 数字时不要再次 +12
        if hour is not None and period_word in ('下午', '傍晚', '晚上', '夜间', '深夜'):
            if hour < 12:
                hour += 12

        # 如果只有时段（如"下午"）没具体小时，使用时段起始小时
        if hour is None and period_word:
            period_key = self.time_keywords.get(period_word)
            if period_key and period_key in self.time_periods:
                hour = self.time_periods[period_key][0]

        if hour is None:
            # 没有任何时间信息，返回当日 00:00（保留日期信息也算成功）
            return target_date

        if not (0 <= hour <= 23) or not (0 <= minute <= 59):
            return None

        return target_date.replace(hour=hour, minute=minute)

    def _parse_relative_datetime(self, text: str, base_time: datetime) -> Optional[datetime]:
        """解析相对日期+时间，如'今天下午3点'"""
        # 匹配模式：日期 + 时间段/时间点
        patterns = [
            # 今天/明天/后天 + 上午/下午/晚上 + 数字 + 点
            r'(今天|今日|明天|明日|后天|昨日|昨天)\s*(早上|早晨|上午|中午|下午|傍晚|晚上|夜间)?\s*(\d+|[一二三四五六七八九十两])?\s*[点时]?',
            # 数字 + 天后 + 时间段
            r'(\d+|[一二三四五六七八九十两])\s*天\s*后\s*(早上|早晨|上午|中午|下午|傍晚|晚上|夜间)?',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                result_time = base_time.replace(minute=0, second=0, microsecond=0)

                # 解析日期偏移
                if groups[0] in self.time_keywords:
                    day_offset = self.time_keywords[groups[0]]
                    if isinstance(day_offset, int):
                        result_time += timedelta(days=day_offset)

                # 解析时间段
                if len(groups) > 1 and groups[1]:
                    period = self.time_keywords.get(groups[1])
                    if period and period in self.time_periods:
                        hour = self.time_periods[period][0]
                        result_time = result_time.replace(hour=hour)

                # 解析具体小时
                if len(groups) > 2 and groups[2]:
                    hour = self._parse_number(groups[2])
                    if hour is not None and 0 <= hour <= 23:
                        # 处理下午/晚上时间：仅当用户写的是 12 小时制（hour<12）时才 +12
                        # 用户写"17点"/"23点"等 24 小时制不要再次 +12
                        if len(groups) > 1 and groups[1] in ['下午', '傍晚', '晚上', '夜间', '深夜']:
                            if hour < 12:
                                hour += 12
                        result_time = result_time.replace(hour=hour)

                return result_time

        return None

    def _parse_absolute_time(self, text: str, base_time: datetime) -> Optional[datetime]:
        """解析绝对时间，如'2024年3月15日下午3点'"""
        patterns = [
            # 2024年3月15日
            r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?\s*(\d{1,2})?\s*[点时]?',
            # 2024-03-15 或 2024/03/15
            r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s*(\d{1,2})?:?\s*(\d{2})?',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                try:
                    year = int(groups[0])
                    month = int(groups[1])
                    day = int(groups[2])
                    hour = int(groups[3]) if len(groups) > 3 and groups[3] else 0
                    minute = int(groups[4]) if len(groups) > 4 and groups[4] else 0

                    return datetime(year, month, day, hour, minute)
                except (ValueError, TypeError):
                    continue

        return None

    def _parse_relative_time(self, text: str, base_time: datetime) -> Optional[datetime]:
        """解析相对时间，如'3分钟后'、'2小时后'、'3天后'"""
        patterns = [
            # N分钟后
            (r'(\d+|[一二三四五六七八九十两])\s*分钟?\s*后', 'minutes'),
            # N小时后
            (r'(\d+|[一二三四五六七八九十两])\s*小时\s*后', 'hours'),
            # N天后
            (r'(\d+|[一二三四五六七八九十两])\s*天\s*后', 'days'),
            # N周后
            (r'(\d+|[一二三四五六七八九十两])\s*[周星期]\s*后', 'weeks'),
            # N月后
            (r'(\d+|[一二三四五六七八九十两])\s*个?\s*月\s*后', 'months'),
        ]

        for pattern, unit in patterns:
            match = re.search(pattern, text)
            if match:
                num = self._parse_number(match.group(1))
                if num is None:
                    continue

                if unit == 'minutes':
                    return base_time + timedelta(minutes=num)
                elif unit == 'hours':
                    return base_time + timedelta(hours=num)
                elif unit == 'days':
                    return base_time + timedelta(days=num)
                elif unit == 'weeks':
                    return base_time + timedelta(weeks=num)
                elif unit == 'months':
                    return base_time + timedelta(days=num * 30)

        return None

    def _parse_special_formats(self, text: str, base_time: datetime) -> Optional[datetime]:
        """解析特殊格式"""
        result_time = base_time.replace(minute=0, second=0, microsecond=0)

        # 仅时间段，如"下午"、"晚上"
        for keyword, value in self.time_keywords.items():
            if keyword in text and isinstance(value, str) and value in self.time_periods:
                hour = self.time_periods[value][0]
                result_time = result_time.replace(hour=hour)
                return result_time

        # 仅日期，如"今天"、"明天"
        for keyword, value in self.time_keywords.items():
            if keyword == text and isinstance(value, int):
                result_time += timedelta(days=value)
                return result_time

        return None

    def _parse_number(self, text: str) -> Optional[int]:
        """解析中文数字"""
        if text.isdigit():
            return int(text)

        return self.number_map.get(text)

    def extract_time_info(self, text: str) -> Tuple[str, Optional[datetime]]:
        """
        从文本中提取时间信息

        Returns:
            (去除时间描述后的文本, 解析出的时间)
        """
        time_patterns = [
            r'今天|今日|明天|明日|后天|昨天|昨日|后天|后日|前天|前日',
            r'早上|早晨|上午|中午|下午|傍晚|晚上|夜间|深夜',
            r'\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日?',
            r'\d{1,2}\s*[点时]',
            r'\d+\s*天\s*后',
            r'\d+\s*[周星期]\s*后',
        ]

        parsed_time = None
        clean_text = text

        for pattern in time_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                time_str = match.group()
                if not parsed_time:
                    parsed_time = self.parse(time_str)
                clean_text = clean_text.replace(time_str, '')

        return clean_text.strip(), parsed_time

    def format_time(self, dt: datetime, format_type: str = 'full') -> str:
        """格式化时间输出"""
        formats = {
            'full': '%Y-%m-%d %H:%M:%S',
            'date': '%Y-%m-%d',
            'time': '%H:%M',
            'human': None
        }

        if format_type == 'human':
            now = datetime.now()
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            date = dt.replace(hour=0, minute=0, second=0, microsecond=0)

            diff_days = (date - today).days

            if diff_days == 0:
                date_str = '今天'
            elif diff_days == 1:
                date_str = '明天'
            elif diff_days == -1:
                date_str = '昨天'
            else:
                date_str = dt.strftime('%Y年%m月%d日')

            hour = dt.hour
            minute = dt.minute

            if 6 <= hour < 12:
                period = '上午'
            elif 12 <= hour < 14:
                period = '中午'
            elif 14 <= hour < 18:
                period = '下午'
            elif 18 <= hour < 22:
                period = '晚上'
            else:
                period = '夜间'

            # 格式化时间，包含分钟
            hour_12 = hour % 12 if hour % 12 != 0 else 12
            if minute == 0:
                time_str = f"{hour_12}点"
            else:
                time_str = f"{hour_12}点{minute}分"

            return f"{date_str}{period}{time_str}"

        return dt.strftime(formats.get(format_type, '%Y-%m-%d %H:%M:%S'))


# 全局实例
time_parser = TimeParser()


def parse_time(text: str, base_time: Optional[datetime] = None) -> Optional[datetime]:
    """便捷函数：解析时间"""
    return time_parser.parse(text, base_time)


def extract_time(text: str) -> Tuple[str, Optional[datetime]]:
    """便捷函数：提取时间信息"""
    return time_parser.extract_time_info(text)


def format_time(dt: datetime, format_type: str = 'full') -> str:
    """便捷函数：格式化时间"""
    return time_parser.format_time(dt, format_type)
