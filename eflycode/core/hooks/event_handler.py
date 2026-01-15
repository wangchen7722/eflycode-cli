"""Hook 事件处理器

处理各种事件类型并应用结果
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import ValidationError

from eflycode.core.hooks.aggregator import HookAggregator
from eflycode.core.hooks.planner import HookPlanner
from eflycode.core.hooks.registry import HookRegistry
from eflycode.core.hooks.runner import HookRunner
from eflycode.core.hooks.types import (
    AggregatedHookResult,
    HookEventName,
    HookGroup,
)
from eflycode.core.llm.protocol import LLMRequest, ToolDefinition
from eflycode.core.utils.logger import logger


class HookEventHandler:
    """Hook 事件处理器"""

    def __init__(
        self,
        registry: HookRegistry,
        runner: HookRunner,
        planner: HookPlanner,
        aggregator: HookAggregator,
    ):
        """初始化事件处理器

        Args:
            registry: Hook 注册表
            runner: Hook 执行器
            planner: Hook 计划器
            aggregator: Hook 聚合器
        """
        self.registry = registry
        self.runner = runner
        self.planner = planner
        self.aggregator = aggregator

    def handle_session_start(
        self, session_id: str, workspace_dir: Path
    ) -> AggregatedHookResult:
        """处理会话开始事件

        Args:
            session_id: 会话 ID
            workspace_dir: 工作区目录

        Returns:
            AggregatedHookResult: 聚合结果
        """
        hook_groups = self.registry.get_all_hooks_for_event(
            HookEventName.SESSION_START
        )
        return self._execute_hooks(
            hook_groups,
            HookEventName.SESSION_START,
            {},
            session_id,
            workspace_dir,
        )

    def handle_before_agent(
        self, user_input: str, session_id: str, workspace_dir: Path
    ) -> AggregatedHookResult:
        """处理 BeforeAgent 事件

        Args:
            user_input: 用户输入
            session_id: 会话 ID
            workspace_dir: 工作区目录

        Returns:
            AggregatedHookResult: 聚合结果
        """
        hook_groups = self.registry.get_all_hooks_for_event(
            HookEventName.BEFORE_AGENT
        )
        return self._execute_hooks(
            hook_groups,
            HookEventName.BEFORE_AGENT,
            {"user_input": user_input},
            session_id,
            workspace_dir,
        )

    def handle_after_agent(
        self, user_input: str, result: str, session_id: str, workspace_dir: Path
    ) -> AggregatedHookResult:
        """处理 AfterAgent 事件

        Args:
            user_input: 用户输入
            result: 任务结果
            session_id: 会话 ID
            workspace_dir: 工作区目录

        Returns:
            AggregatedHookResult: 聚合结果
        """
        hook_groups = self.registry.get_all_hooks_for_event(
            HookEventName.AFTER_AGENT
        )
        return self._execute_hooks(
            hook_groups,
            HookEventName.AFTER_AGENT,
            {"user_input": user_input, "result": result},
            session_id,
            workspace_dir,
        )

    def handle_session_end(
        self, session_id: str, workspace_dir: Path
    ) -> AggregatedHookResult:
        """处理会话结束事件

        Args:
            session_id: 会话 ID
            workspace_dir: 工作区目录

        Returns:
            AggregatedHookResult: 聚合结果
        """
        hook_groups = self.registry.get_all_hooks_for_event(
            HookEventName.SESSION_END
        )
        return self._execute_hooks(
            hook_groups,
            HookEventName.SESSION_END,
            {},
            session_id,
            workspace_dir,
        )

    def handle_before_model(
        self,
        llm_request: LLMRequest,
        session_id: str,
        workspace_dir: Path,
    ) -> tuple[AggregatedHookResult, Optional[LLMRequest]]:
        """处理 BeforeModel 事件

        Args:
            llm_request: LLM 请求
            session_id: 会话 ID
            workspace_dir: 工作区目录

        Returns:
            tuple[AggregatedHookResult, Optional[LLMRequest]]: 聚合结果和修改后的请求（如果有）
        """
        hook_groups = self.registry.get_all_hooks_for_event(
            HookEventName.BEFORE_MODEL
        )

        # 将 LLMRequest 转换为字典
        request_dict = self._serialize_llm_request(llm_request)

        result = self._execute_hooks(
            hook_groups,
            HookEventName.BEFORE_MODEL,
            {"llm_request": request_dict},
            session_id,
            workspace_dir,
        )

        # 如果 hook 返回了修改后的 llm_request，应用修改
        modified_request = None
        if result.hook_specific_output and "llm_request" in result.hook_specific_output:
            modified_request = self._deserialize_llm_request(
                result.hook_specific_output["llm_request"]
            )

        return result, modified_request

    def handle_after_model(
        self,
        llm_request: LLMRequest,
        llm_response: Any,
        session_id: str,
        workspace_dir: Path,
    ) -> AggregatedHookResult:
        """处理 AfterModel 事件

        Args:
            llm_request: LLM 请求
            llm_response: LLM 响应
            session_id: 会话 ID
            workspace_dir: 工作区目录

        Returns:
            AggregatedHookResult: 聚合结果
        """
        hook_groups = self.registry.get_all_hooks_for_event(
            HookEventName.AFTER_MODEL
        )

        request_dict = self._serialize_llm_request(llm_request)
        response_dict = self._serialize_llm_response(llm_response)

        return self._execute_hooks(
            hook_groups,
            HookEventName.AFTER_MODEL,
            {"llm_request": request_dict, "llm_response": response_dict},
            session_id,
            workspace_dir,
        )

    def handle_before_tool_selection(
        self,
        tools: List[ToolDefinition],
        session_id: str,
        workspace_dir: Path,
    ) -> tuple[AggregatedHookResult, List[ToolDefinition]]:
        """处理 BeforeToolSelection 事件

        Args:
            tools: 工具列表
            session_id: 会话 ID
            workspace_dir: 工作区目录

        Returns:
            tuple[AggregatedHookResult, List[ToolDefinition]]: 聚合结果和修改后的工具列表
        """
        hook_groups = self.registry.get_all_hooks_for_event(
            HookEventName.BEFORE_TOOL_SELECTION
        )

        tools_dict = [self._serialize_tool_definition(tool) for tool in tools]

        result = self._execute_hooks(
            hook_groups,
            HookEventName.BEFORE_TOOL_SELECTION,
            {"tools": tools_dict},
            session_id,
            workspace_dir,
        )

        # 如果 hook 返回了修改后的 tools，应用修改
        modified_tools = tools
        if result.hook_specific_output and "tools" in result.hook_specific_output:
            modified_tools = [
                self._deserialize_tool_definition(tool_dict)
                for tool_dict in result.hook_specific_output["tools"]
            ]

        return result, modified_tools

    def handle_before_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        session_id: str,
        workspace_dir: Path,
    ) -> AggregatedHookResult:
        """处理 BeforeTool 事件

        Args:
            tool_name: 工具名称
            tool_input: 工具输入参数
            session_id: 会话 ID
            workspace_dir: 工作区目录

        Returns:
            AggregatedHookResult: 聚合结果，包含 decision 字段
        """
        hook_groups = self.registry.get_hooks_for_event(
            HookEventName.BEFORE_TOOL, tool_name
        )

        return self._execute_hooks(
            hook_groups,
            HookEventName.BEFORE_TOOL,
            {"tool_name": tool_name, "tool_input": tool_input},
            session_id,
            workspace_dir,
        )

    def handle_after_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_result: str,
        session_id: str,
        workspace_dir: Path,
    ) -> AggregatedHookResult:
        """处理 AfterTool 事件

        Args:
            tool_name: 工具名称
            tool_input: 工具输入参数
            tool_result: 工具执行结果
            session_id: 会话 ID
            workspace_dir: 工作区目录

        Returns:
            AggregatedHookResult: 聚合结果
        """
        hook_groups = self.registry.get_hooks_for_event(
            HookEventName.AFTER_TOOL, tool_name
        )

        return self._execute_hooks(
            hook_groups,
            HookEventName.AFTER_TOOL,
            {
                "tool_name": tool_name,
                "tool_input": tool_input,
                "tool_result": tool_result,
            },
            session_id,
            workspace_dir,
        )

    def handle_pre_compress(
        self, session_id: str, workspace_dir: Path
    ) -> AggregatedHookResult:
        """处理 PreCompress 事件

        Args:
            session_id: 会话 ID
            workspace_dir: 工作区目录

        Returns:
            AggregatedHookResult: 聚合结果
        """
        hook_groups = self.registry.get_all_hooks_for_event(
            HookEventName.PRE_COMPRESS
        )
        return self._execute_hooks(
            hook_groups,
            HookEventName.PRE_COMPRESS,
            {},
            session_id,
            workspace_dir,
        )

    def _execute_hooks(
        self,
        hook_groups: List[HookGroup],
        event_name: HookEventName,
        input_data: Dict[str, Any],
        session_id: str,
        workspace_dir: Path,
    ) -> AggregatedHookResult:
        """执行 hooks 的内部方法

        Args:
            hook_groups: Hook 组列表
            event_name: 事件名称
            input_data: 输入数据
            session_id: 会话 ID
            workspace_dir: 工作区目录

        Returns:
            AggregatedHookResult: 聚合结果
        """
        if not hook_groups:
            logger.debug(f"没有 hooks 需要执行: event={event_name}")
            return AggregatedHookResult()

        total_hooks = sum(len(group.hooks) for group in hook_groups)
        groups_count = len(hook_groups)
        logger.debug(f"开始执行 hooks: event={event_name}, groups={groups_count}, total_hooks={total_hooks}")

        # 制定执行计划
        execution_plan = self.planner.plan_execution(hook_groups)

        all_results = []
        current_input = input_data.copy()

        # 执行每个组
        for hooks, sequential in execution_plan.groups:
            hooks_count = len(hooks)
            logger.debug(f"执行 hook 组: hooks_count={hooks_count}, sequential={sequential}")
            if sequential:
                # 串行执行
                results = self.runner.execute_hooks_sequential(
                    hooks, event_name, current_input, session_id, workspace_dir
                )
                # 更新输入，将最后一个 hook 的输出合并到输入中
                if results and results[-1].success and results[-1].stdout:
                    try:
                        from eflycode.core.hooks.types import HookOutput

                        hook_output = HookOutput.from_json(results[-1].stdout)
                        if hook_output.hook_specific_output:
                            current_input.update(hook_output.hook_specific_output)
                    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
                        logger.warning(f"解析 hook 输出失败: {e}")
            else:
                # 并行执行
                results = self.runner.execute_hooks_parallel(
                    hooks, event_name, current_input, session_id, workspace_dir
                )

            all_results.extend(results)

        # 聚合所有结果
        aggregated = self.aggregator.aggregate_results(all_results)
        total_results_count = len(all_results)
        logger.debug(f"Hooks 执行完成: event={event_name}, total_results={total_results_count}, continue={aggregated.continue_}")
        return aggregated

    def _serialize_llm_request(self, request: LLMRequest) -> Dict[str, Any]:
        """将 LLMRequest 转换为字典，使用 Pydantic 原生方法

        Args:
            request: LLM 请求

        Returns:
            Dict[str, Any]: 字典表示
        """
        # 使用 Pydantic 的 model_dump 进行序列化
        # exclude_none=True 排除 None 值
        # mode='json' 确保与 JSON 序列化兼容，自动处理嵌套的 Pydantic 模型
        return request.model_dump(exclude_none=True, mode="json")

    def _deserialize_llm_request(self, data: Dict[str, Any]) -> LLMRequest:
        """从字典创建 LLMRequest，包含输入验证和异常处理

        Args:
            data: 字典数据

        Returns:
            LLMRequest: LLM 请求对象

        Raises:
            ValueError: 如果输入数据格式无效
        """
        from eflycode.core.llm.protocol import Message, ToolCall, ToolCallFunction

        if not isinstance(data, dict):
            raise ValueError(f"期望输入为字典类型，实际为: {type(data)}")

        # 验证并转换 messages
        messages_data = data.get("messages", [])
        if not isinstance(messages_data, list):
            raise ValueError(f"messages 必须是列表，实际为: {type(messages_data)}")

        messages = []
        for i, msg_dict in enumerate(messages_data):
            if not isinstance(msg_dict, dict):
                logger.warning(f"消息格式无效，跳过索引 {i}: {msg_dict}")
                continue

            try:
                # 验证必需字段
                if "role" not in msg_dict:
                    logger.warning(f"消息缺少 role 字段，跳过索引 {i}")
                    continue

                # 解析 tool_calls
                tool_calls = None
                if "tool_calls" in msg_dict and msg_dict["tool_calls"]:
                    tool_calls_data = msg_dict["tool_calls"]
                    if isinstance(tool_calls_data, list):
                        tool_calls = []
                        for tc in tool_calls_data:
                            if isinstance(tc, dict) and "id" in tc and "function" in tc:
                                try:
                                    tool_calls.append(
                                        ToolCall(
                                            id=tc["id"],
                                            type=tc.get("type", "function"),
                                            function=ToolCallFunction(
                                                name=tc["function"]["name"],
                                                arguments=tc["function"].get("arguments", ""),
                                            ),
                                        )
                                    )
                                except (KeyError, TypeError, ValueError) as e:
                                    logger.warning(f"解析 tool_call 失败，跳过: {e}")

                messages.append(
                    Message(
                        role=msg_dict["role"],
                        content=msg_dict.get("content"),
                        tool_calls=tool_calls,
                    )
                )
            except (KeyError, TypeError, ValueError) as e:
                logger.warning(f"创建消息失败，跳过索引 {i}: {e}")

        if not messages:
            raise ValueError("至少需要一条有效消息")

        # 转换 tools（可选）
        tools = None
        if "tools" in data:
            tools_data = data["tools"]
            if isinstance(tools_data, list):
                try:
                    tools = [
                        self._deserialize_tool_definition(tool_dict)
                        for tool_dict in tools_data
                    ]
                except (ValueError, TypeError) as e:
                    logger.warning(f"转换 tools 失败: {e}")

        return LLMRequest(
            model=data.get("model", ""),
            messages=messages,
            tools=tools,
            generate_config=data.get("generate_config"),
        )

    def _serialize_tool_definition(self, tool: ToolDefinition) -> Dict[str, Any]:
        """将 ToolDefinition 转换为字典，使用 Pydantic 原生方法

        Args:
            tool: 工具定义

        Returns:
            Dict[str, Any]: 字典表示
        """
        return tool.model_dump()

    def _deserialize_tool_definition(self, data: Dict[str, Any]) -> ToolDefinition:
        """从字典创建 ToolDefinition，使用 Pydantic model_validate 方法

        Args:
            data: 字典数据

        Returns:
            ToolDefinition: 工具定义对象

        Raises:
            ValueError: 如果输入数据格式无效
        """
        if not isinstance(data, dict):
            raise ValueError(f"期望输入为字典类型，实际为: {type(data)}")

        try:
            return ToolDefinition.model_validate(data)
        except ValidationError as e:
            raise ValueError(f"验证 ToolDefinition 失败: {e}") from e

    def _serialize_llm_response(self, response: Any) -> Dict[str, Any]:
        """将 LLM 响应转换为字典

        Args:
            response: LLM 响应对象

        Returns:
            Dict[str, Any]: 字典表示
        """
        # 简化处理，只提取关键字段
        result = {
            "id": getattr(response, "id", None),
            "model": getattr(response, "model", None),
            "created": getattr(response, "created", None),
        }

        if hasattr(response, "message"):
            msg = response.message
            result["message"] = {
                "role": getattr(msg, "role", None),
                "content": getattr(msg, "content", None),
            }

        if hasattr(response, "usage"):
            usage = response.usage
            result["usage"] = {
                "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                "completion_tokens": getattr(usage, "completion_tokens", 0),
                "total_tokens": getattr(usage, "total_tokens", 0),
            }

        return result

