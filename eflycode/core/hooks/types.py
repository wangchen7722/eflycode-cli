"""Hooks 系统类型定义"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class HookEventName(str, Enum):
    """Hook 事件名称枚举"""

    SESSION_START = "SessionStart"
    SESSION_END = "SessionEnd"
    BEFORE_AGENT = "BeforeAgent"
    AFTER_AGENT = "AfterAgent"
    BEFORE_MODEL = "BeforeModel"
    AFTER_MODEL = "AfterModel"
    BEFORE_TOOL_SELECTION = "BeforeToolSelection"
    BEFORE_TOOL = "BeforeTool"
    AFTER_TOOL = "AfterTool"
    PRE_COMPRESS = "PreCompress"
    NOTIFICATION = "Notification"


@dataclass
class CommandHook:
    """命令 Hook 定义

    Attributes:
        name: Hook 名称，用于标识和日志
        command: 要执行的命令，可以是脚本路径或命令
        timeout: 超时时间（毫秒），默认 60000 毫秒
        matcher: 匹配器（正则表达式或通配符），用于匹配工具名，None 或 "*" 表示匹配所有
    """

    name: str
    command: str
    timeout: int = 60000  # 默认 60 秒
    matcher: Optional[str] = None

    def matches_tool(self, tool_name: str) -> bool:
        """检查是否匹配指定的工具名

        Args:
            tool_name: 工具名称

        Returns:
            bool: 是否匹配
        """
        if not self.matcher or self.matcher == "*":
            return True

        import re

        try:
            # 尝试作为正则表达式匹配
            pattern = re.compile(self.matcher)
            return bool(pattern.match(tool_name))
        except re.error:
            # 如果正则表达式无效，作为通配符匹配
            import fnmatch

            return fnmatch.fnmatch(tool_name, self.matcher)


@dataclass
class HookGroup:
    """Hook 组定义

    Attributes:
        matcher: 匹配器，用于匹配工具名
        sequential: 是否串行执行，默认为 False（并行执行）
        hooks: Hook 列表
    """

    matcher: Optional[str] = None
    sequential: bool = False
    hooks: List[CommandHook] = field(default_factory=list)

    def matches_tool(self, tool_name: str) -> bool:
        """检查是否匹配指定的工具名

        Args:
            tool_name: 工具名称

        Returns:
            bool: 是否匹配
        """
        if not self.matcher or self.matcher == "*":
            return True

        import re

        try:
            # 尝试作为正则表达式匹配
            pattern = re.compile(self.matcher)
            return bool(pattern.match(tool_name))
        except re.error:
            # 如果正则表达式无效，作为通配符匹配
            import fnmatch

            return fnmatch.fnmatch(tool_name, self.matcher)


@dataclass
class HookExecutionResult:
    """单个 Hook 执行结果

    Attributes:
        hook_name: Hook 名称
        stdout: 标准输出
        stderr: 标准错误
        exit_code: 退出码
        duration_ms: 执行耗时（毫秒）
        success: 是否成功（exit_code == 0）
    """

    hook_name: str
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    success: bool

    @property
    def is_blocking(self) -> bool:
        """是否为阻断错误（exit_code == 2）

        Returns:
            bool: 是否为阻断错误
        """
        return self.exit_code == 2

    @property
    def is_warning(self) -> bool:
        """是否为警告（exit_code != 0 且 != 2）

        Returns:
            bool: 是否为警告
        """
        return self.exit_code != 0 and self.exit_code != 2


@dataclass
class HookOutput:
    """Hook 输出解析结果

    Attributes:
        decision: 决策（allow/deny/ask/block），用于 BeforeTool 等场景
        continue_: 是否继续执行，False 时终止代理循环
        system_message: 注入给用户的消息
        hook_specific_output: 事件特定的输出（如 llm_request 覆盖、toolConfig 调整等）
    """

    decision: Optional[str] = None  # allow, deny, ask, block
    continue_: bool = True
    system_message: Optional[str] = None
    hook_specific_output: Optional[Dict[str, Any]] = None

    @classmethod
    def from_json(cls, json_str: str) -> "HookOutput":
        """从 JSON 字符串解析 HookOutput

        Args:
            json_str: JSON 字符串

        Returns:
            HookOutput: 解析后的 HookOutput 对象
        """
        import json

        try:
            data = json.loads(json_str)
            return cls(
                decision=data.get("decision"),
                continue_=data.get("continue", True),
                system_message=data.get("systemMessage"),
                hook_specific_output=data.get("hookSpecificOutput"),
            )
        except (json.JSONDecodeError, TypeError):
            # 如果不是有效的 JSON，返回默认值
            return cls()


@dataclass
class AggregatedHookResult:
    """聚合后的 Hook 结果

    Attributes:
        decision: 最终决策（block > deny > ask > allow）
        continue_: 是否继续执行
        system_messages: 系统消息列表（多个消息会拼接）
        hook_specific_output: 事件特定的输出（后执行的覆盖前面的）
        execution_results: 所有 Hook 的执行结果
    """

    decision: Optional[str] = None
    continue_: bool = True
    system_messages: List[str] = field(default_factory=list)
    hook_specific_output: Optional[Dict[str, Any]] = None
    execution_results: List[HookExecutionResult] = field(default_factory=list)

    @property
    def system_message(self) -> Optional[str]:
        """获取合并后的系统消息

        Returns:
            Optional[str]: 合并后的系统消息，如果没有则返回 None
        """
        if not self.system_messages:
            return None
        return "\n".join(self.system_messages)

    def merge(self, other: "AggregatedHookResult") -> None:
        """合并另一个聚合结果

        Args:
            other: 另一个聚合结果
        """
        # 合并决策（优先级：block > deny > ask > allow）
        decision_priority = {"block": 4, "deny": 3, "ask": 2, "allow": 1}

        def get_priority(d: Optional[str]) -> int:
            return decision_priority.get(d or "", 0)

        if get_priority(other.decision) > get_priority(self.decision):
            self.decision = other.decision

        # 合并 continue（如果任何一个为 False，则整体为 False）
        if not other.continue_:
            self.continue_ = False

        # 合并系统消息
        if other.system_message:
            self.system_messages.append(other.system_message)

        # 合并 hook_specific_output（后面的覆盖前面的）
        if other.hook_specific_output:
            if self.hook_specific_output is None:
                self.hook_specific_output = {}
            self.hook_specific_output.update(other.hook_specific_output)

        # 合并执行结果
        self.execution_results.extend(other.execution_results)

