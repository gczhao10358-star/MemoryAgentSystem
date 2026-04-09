"""
日期时间工具
提供当前时间获取和日期计算功能
"""
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import calendar


class DateTimeTools:
    """日期时间工具类"""

    @staticmethod
    def get_current_time() -> Dict[str, any]:
        """
        获取当前详细时间信息

        Returns:
            {
                'datetime': datetime对象,
                'iso': ISO格式字符串,
                'date': '2026-03-15',
                'time': '14:30:00',
                'year': 2026,
                'month': 3,
                'day': 15,
                'hour': 14,
                'minute': 30,
                'weekday': 6,  # 0=周一, 6=周日
                'weekday_name': '周日',
                'weekday_en': 'Sunday',
                'is_weekend': True,
                'week_of_year': 11,
                'day_of_year': 74
            }
        """
        now = datetime.now()
        weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        weekday_en = ['Monday', 'Tuesday', 'Wednesday', 'Thursday',
                      'Friday', 'Saturday', 'Sunday']

        return {
            'datetime': now,
            'iso': now.isoformat(),
            'date': now.strftime('%Y-%m-%d'),
            'time': now.strftime('%H:%M:%S'),
            'year': now.year,
            'month': now.month,
            'day': now.day,
            'hour': now.hour,
            'minute': now.minute,
            'weekday': now.weekday(),  # 0-6, 0=周一
            'weekday_name': weekday_names[now.weekday()],
            'weekday_en': weekday_en[now.weekday()],
            'is_weekend': now.weekday() >= 5,
            'week_of_year': now.isocalendar()[1],
            'day_of_year': now.timetuple().tm_yday
        }

    @staticmethod
    def get_relative_date(reference: datetime, days_offset: int) -> Dict[str, any]:
        """
        获取相对日期的详细信息

        Args:
            reference: 参考日期
            days_offset: 天数偏移（负数表示过去）

        Returns:
            同 get_current_time 格式的字典
        """
        target_date = reference + timedelta(days=days_offset)
        weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

        return {
            'datetime': target_date,
            'iso': target_date.isoformat(),
            'date': target_date.strftime('%Y-%m-%d'),
            'time': target_date.strftime('%H:%M:%S'),
            'year': target_date.year,
            'month': target_date.month,
            'day': target_date.day,
            'hour': target_date.hour,
            'minute': target_date.minute,
            'weekday': target_date.weekday(),
            'weekday_name': weekday_names[target_date.weekday()],
            'is_weekend': target_date.weekday() >= 5,
            'week_of_year': target_date.isocalendar()[1],
            'day_of_year': target_date.timetuple().tm_yday
        }

    @staticmethod
    def find_date_by_weekday(target_weekday: str, reference: Optional[datetime] = None) -> Optional[datetime]:
        """
        根据星期几找到最近的日期

        Args:
            target_weekday: '周日', '周一', '周二', etc.
            reference: 参考日期，默认为今天

        Returns:
            匹配的日期
        """
        weekday_map = {
            '周一': 0, '星期二': 1, '周二': 1,
            '周三': 2, '星期三': 2,
            '周四': 3, '星期四': 3,
            '周五': 4, '星期五': 4,
            '周六': 5, '星期六': 5,
            '周日': 6, '星期天': 6, '星期日': 6
        }

        if reference is None:
            reference = datetime.now()

        target_num = weekday_map.get(target_weekday)
        if target_num is None:
            return None

        current_weekday = reference.weekday()
        days_diff = (target_num - current_weekday) % 7

        if days_diff == 0:
            # 如果就是今天，返回今天
            return reference

        return reference + timedelta(days=days_diff)

    @staticmethod
    def resolve_date_reference(text: str, reference: Optional[datetime] = None) -> Optional[datetime]:
        """
        解析日期引用，如"15号"、"周日"、"这周五"

        Args:
            text: 日期描述文本
            reference: 参考日期，默认为今天

        Returns:
            解析出的日期
        """
        if reference is None:
            reference = datetime.now()

        import re

        # 匹配 "X号"
        day_match = re.search(r'(\d{1,2})\s*[号日]', text)
        if day_match:
            day = int(day_match.group(1))
            if 1 <= day <= 31:
                # 判断是本月还是下月
                if day >= reference.day:
                    # 本月
                    try:
                        return reference.replace(day=day)
                    except ValueError:
                        return None
                else:
                    # 下月
                    try:
                        next_month = reference.replace(month=reference.month + 1, day=day)
                        return next_month
                    except ValueError:
                        # 12月情况
                        if reference.month == 12:
                            return reference.replace(year=reference.year + 1, month=1, day=day)
                        return None

        # 匹配星期几 - 处理 "这周五"、"下周三" 等
        weekday_pattern = r'(这[个]?)?(下[个]?)?(周[一二三四五六日]|星期[一二三四五六日]|星期[天日])'
        weekday_match = re.search(weekday_pattern, text)
        if weekday_match:
            weekday_str = weekday_match.group(3)
            is_next_week = weekday_match.group(2) is not None  # 是否匹配到"下周"

            result_date = DateTimeTools.find_date_by_weekday(weekday_str, reference)

            # 如果是"下周X"，加7天
            if is_next_week and result_date:
                result_date = result_date + timedelta(days=7)

            return result_date

        return None

    @staticmethod
    def format_datetime(dt: datetime, format_type: str = 'full') -> str:
        """格式化日期时间"""
        formats = {
            'full': '%Y年%m月%d日 %H:%M %a',
            'date': '%Y年%m月%d日',
            'time': '%H:%M',
            'weekday': '%a',
            'iso': '%Y-%m-%d %H:%M:%S'
        }
        fmt = formats.get(format_type, '%Y-%m-%d %H:%M:%S')

        # 中文星期
        result = dt.strftime(fmt)
        weekday_map = {
            'Mon': '周一', 'Tue': '周二', 'Wed': '周三',
            'Thu': '周四', 'Fri': '周五', 'Sat': '周六', 'Sun': '周日'
        }
        for en, cn in weekday_map.items():
            result = result.replace(en, cn)

        return result


# 便捷函数
def get_now() -> Dict[str, any]:
    """获取当前时间信息"""
    return DateTimeTools.get_current_time()


def get_today() -> str:
    """获取今天日期字符串"""
    return datetime.now().strftime('%Y-%m-%d')


def get_weekday_name(date: Optional[datetime] = None) -> str:
    """获取星期几名称"""
    if date is None:
        date = datetime.now()
    names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    return names[date.weekday()]


def is_same_day(dt1: datetime, dt2: datetime) -> bool:
    """判断是否为同一天"""
    return dt1.year == dt2.year and dt1.month == dt2.month and dt1.day == dt2.day


def days_between(dt1: datetime, dt2: datetime) -> int:
    """计算两个日期之间的天数差"""
    return (dt2.date() - dt1.date()).days
