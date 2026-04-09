"""
平台适配器模块
支持飞书、钉钉等第三方平台接入
"""
from .lark_adapter import LarkAdapter, LarkConfig

__all__ = ['LarkAdapter', 'LarkConfig']
