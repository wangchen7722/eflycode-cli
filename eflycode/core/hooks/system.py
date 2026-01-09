"""Hook 系统主类

整合所有组件并提供统一接口
"""

from pathlib import Path
from typing import Optional

from eflycode.core.hooks.aggregator import HookAggregator
from eflycode.core.hooks.event_handler import HookEventHandler
from eflycode.core.hooks.planner import HookPlanner
from eflycode.core.hooks.registry import HookRegistry
from eflycode.core.hooks.runner import HookRunner
from typing import Any

from eflycode.core.hooks.types import (
    AggregatedHookResult,
    CommandHook,
    HookEventName,
    HookGroup,
)
from eflycode.core.llm.protocol import LLMRequest, ToolDefinition


class HookSystem:
    """Hook 系统主类

    管理所有 hooks 并提供统一的事件触发接口
    """

    def __init__(self, workspace_dir: Optional[Path] = None):
        """初始化 Hook 系统

        Args:
            workspace_dir: 工作区目录
        """
        self.workspace_dir = workspace_dir or Path.cwd()
        self.registry = HookRegistry()
        self.runner = HookRunner(workspace_dir=self.workspace_dir)
        self.planner = HookPlanner()
        self.aggregator = HookAggregator()
        self.event_handler = HookEventHandler(
            registry=self.registry,
            runner=self.runner,
            planner=self.planner,
            aggregator=self.aggregator,
        )
        self._enabled = True

    def get_event_handler(self) -> HookEventHandler:
        """获取事件处理器

        Returns:
            HookEventHandler: 事件处理器实例
        """
        return self.event_handler

    def register_hook(
        self,
        event_name: HookEventName,
        hook: CommandHook,
        group_matcher: Optional[str] = None,
        sequential: bool = False,
    ) -> None:
        """注册一个 hook

        Args:
            event_name: 事件名称
            hook: Hook 定义
            group_matcher: Hook 组的匹配器
            sequential: 是否串行执行
        """
        self.registry.register_hook(
            event_name, hook, group_matcher, sequential
        )

    def register_hook_group(
        self, event_name: HookEventName, group: HookGroup
    ) -> None:
        """注册一个 hook 组

        Args:
            event_name: 事件名称
            group: Hook 组
        """
        self.registry.register_hook_group(event_name, group)

    def is_enabled(self) -> bool:
        """检查 hooks 是否启用

        Returns:
            bool: 是否启用
        """
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        """设置 hooks 是否启用

        Args:
            enabled: 是否启用
        """
        self._enabled = enabled

    # 便捷方法：触发各种事件

    def fire_session_start_event(
        self, session_id: str, workspace_dir: Optional[Path] = None
    ) -> AggregatedHookResult:
        """触发会话开始事件

        Args:
            session_id: 会话 ID
            workspace_dir: 工作区目录

        Returns:
            AggregatedHookResult: 聚合结果
        """
        if not self._enabled:
            return AggregatedHookResult()

        workspace = workspace_dir or self.workspace_dir
        return self.event_handler.handle_session_start(session_id, workspace)

    def fire_before_agent_event(
        self, user_input: str, session_id: str, workspace_dir: Optional[Path] = None
    ) -> AggregatedHookResult:
        """触发 BeforeAgent 事件

        Args:
            user_input: 用户输入
            session_id: 会话 ID
            workspace_dir: 工作区目录

        Returns:
            AggregatedHookResult: 聚合结果
        """
        if not self._enabled:
            return AggregatedHookResult()

        workspace = workspace_dir or self.workspace_dir
        return self.event_handler.handle_before_agent(user_input, session_id, workspace)

    def fire_after_agent_event(
        self,
        user_input: str,
        result: str,
        session_id: str,
        workspace_dir: Optional[Path] = None,
    ) -> AggregatedHookResult:
        """触发 AfterAgent 事件

        Args:
            user_input: 用户输入
            result: 任务结果
            session_id: 会话 ID
            workspace_dir: 工作区目录

        Returns:
            AggregatedHookResult: 聚合结果
        """
        if not self._enabled:
            return AggregatedHookResult()

        workspace = workspace_dir or self.workspace_dir
        return self.event_handler.handle_after_agent(
            user_input, result, session_id, workspace
        )

    def fire_session_end_event(
        self, session_id: str, workspace_dir: Optional[Path] = None
    ) -> AggregatedHookResult:
        """触发会话结束事件

        Args:
            session_id: 会话 ID
            workspace_dir: 工作区目录

        Returns:
            AggregatedHookResult: 聚合结果
        """
        if not self._enabled:
            return AggregatedHookResult()

        workspace = workspace_dir or self.workspace_dir
        return self.event_handler.handle_session_end(session_id, workspace)

    def fire_before_model_event(
        self,
        llm_request: LLMRequest,
        session_id: str,
        workspace_dir: Optional[Path] = None,
    ) -> tuple[AggregatedHookResult, Optional[LLMRequest]]:
        """触发 BeforeModel 事件

        Args:
            llm_request: LLM 请求
            session_id: 会话 ID
            workspace_dir: 工作区目录

        Returns:
            tuple[AggregatedHookResult, Optional[LLMRequest]]: 聚合结果和修改后的请求
        """
        if not self._enabled:
            return AggregatedHookResult(), None

        workspace = workspace_dir or self.workspace_dir
        return self.event_handler.handle_before_model(
            llm_request, session_id, workspace
        )

    def fire_after_model_event(
        self,
        llm_request: LLMRequest,
        llm_response: Any,
        session_id: str,
        workspace_dir: Optional[Path] = None,
    ) -> AggregatedHookResult:
        """触发 AfterModel 事件

        Args:
            llm_request: LLM 请求
            llm_response: LLM 响应
            session_id: 会话 ID
            workspace_dir: 工作区目录

        Returns:
            AggregatedHookResult: 聚合结果
        """
        if not self._enabled:
            return AggregatedHookResult()

        workspace = workspace_dir or self.workspace_dir
        return self.event_handler.handle_after_model(
            llm_request, llm_response, session_id, workspace
        )

    def fire_before_tool_selection_event(
        self,
        tools: list[ToolDefinition],
        session_id: str,
        workspace_dir: Optional[Path] = None,
    ) -> tuple[AggregatedHookResult, list[ToolDefinition]]:
        """触发 BeforeToolSelection 事件

        Args:
            tools: 工具列表
            session_id: 会话 ID
            workspace_dir: 工作区目录

        Returns:
            tuple[AggregatedHookResult, list[ToolDefinition]]: 聚合结果和修改后的工具列表
        """
        if not self._enabled:
            return AggregatedHookResult(), tools

        workspace = workspace_dir or self.workspace_dir
        return self.event_handler.handle_before_tool_selection(
            tools, session_id, workspace
        )

    def fire_before_tool_event(
        self,
        tool_name: str,
        tool_input: dict,
        session_id: str,
        workspace_dir: Optional[Path] = None,
    ) -> AggregatedHookResult:
        """触发 BeforeTool 事件

        Args:
            tool_name: 工具名称
            tool_input: 工具输入参数
            session_id: 会话 ID
            workspace_dir: 工作区目录

        Returns:
            AggregatedHookResult: 聚合结果
        """
        if not self._enabled:
            return AggregatedHookResult()

        workspace = workspace_dir or self.workspace_dir
        return self.event_handler.handle_before_tool(
            tool_name, tool_input, session_id, workspace
        )

    def fire_after_tool_event(
        self,
        tool_name: str,
        tool_input: dict,
        tool_result: str,
        session_id: str,
        workspace_dir: Optional[Path] = None,
    ) -> AggregatedHookResult:
        """触发 AfterTool 事件

        Args:
            tool_name: 工具名称
            tool_input: 工具输入参数
            tool_result: 工具执行结果
            session_id: 会话 ID
            workspace_dir: 工作区目录

        Returns:
            AggregatedHookResult: 聚合结果
        """
        if not self._enabled:
            return AggregatedHookResult()

        workspace = workspace_dir or self.workspace_dir
        return self.event_handler.handle_after_tool(
            tool_name, tool_input, tool_result, session_id, workspace
        )

    def fire_pre_compress_event(
        self, session_id: str, workspace_dir: Optional[Path] = None
    ) -> AggregatedHookResult:
        """触发 PreCompress 事件

        Args:
            session_id: 会话 ID
            workspace_dir: 工作区目录

        Returns:
            AggregatedHookResult: 聚合结果
        """
        if not self._enabled:
            return AggregatedHookResult()

        workspace = workspace_dir or self.workspace_dir
        return self.event_handler.handle_pre_compress(session_id, workspace)

