"""
核心模块
包含记忆管理器和Agent主程序
"""
from .memory_manager import MemoryManager
from .memory_service import MemoryService
from .evolution_engine import MemoryEvolutionEngine, EvolutionResult
from .memory_mate_agent import MemoryMateAgent

__all__ = ['MemoryManager', 'MemoryService', 'MemoryEvolutionEngine', 'EvolutionResult', 'MemoryMateAgent']
