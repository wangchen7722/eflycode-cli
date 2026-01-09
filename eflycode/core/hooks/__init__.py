"""Hooks 系统

提供在 Agent 执行流程的关键节点执行外部命令的能力
"""

from eflycode.core.hooks.system import HookSystem
from eflycode.core.hooks.types import (
    HookEventName,
    CommandHook,
    HookGroup,
    HookExecutionResult,
    HookOutput,
    AggregatedHookResult,
)

__all__ = [
    "HookSystem",
    "HookEventName",
    "CommandHook",
    "HookGroup",
    "HookExecutionResult",
    "HookOutput",
    "AggregatedHookResult",
]

