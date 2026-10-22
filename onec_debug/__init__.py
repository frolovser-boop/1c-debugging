# -*- coding: utf-8 -*-
"""
1C Debug (onec-debug): Универсальный инструментарий отладки 1С:Предприятия.
Поддерживает автономную работу (Headless RDBG) и интеграцию с VS Code / AI-агентами через MCP.
"""

__version__ = "1.0.0"

from .detector import detect_platform, list_known_bases, resolve_base, BaseInfo
from .rdbg import RdbgClient
from .session import DebugSession

__all__ = [
    "detect_platform",
    "list_known_bases",
    "resolve_base",
    "BaseInfo",
    "RdbgClient",
    "DebugSession",
]
