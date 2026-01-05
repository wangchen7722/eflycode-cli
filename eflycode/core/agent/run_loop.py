import json
import re
from typing import Dict, Optional

from eflycode.core.agent.base import BaseAgent, TaskConversation, TaskStatistics


class AgentRunLoop:
    """Agent 运行循环，处理用户输入、工具调用和对话流程"""

    def __init__(self, agent: BaseAgent):
        """初始化运行循环

        Args:
            agent: Agent 实例
        """
        self.agent = agent
        self.max_iterations = 50
        self.current_iteration = 0

    def run(self, user_input: str) -> TaskConversation:
        """主运行循环

        Args:
            user_input: 用户输入

        Returns:
            TaskConversation: 包含最终响应、全部对话信息和任务统计的会话对象
        """
        self.current_iteration = 0
        self.agent.event_bus.emit("agent.task.start", agent=self.agent, user_input=user_input)

        statistics = TaskStatistics()
        last_conversation = None

        try:
            while self.current_iteration < self.max_iterations:
                self.current_iteration += 1
                statistics.iterations = self.current_iteration

                conversation = self.agent.chat(user_input if self.current_iteration == 1 else "")
                last_conversation = conversation
                response_content = conversation.content

                if conversation.completion.usage:
                    statistics.add_usage(conversation.completion.usage)

                tool_call = self._parse_tool_call(conversation.completion)
                if not tool_call:
                    statistics.tool_calls_count = self.current_iteration - 1
                    self.agent.event_bus.emit("agent.task.stop", agent=self.agent, result=response_content)
                    return TaskConversation(conversation=conversation, statistics=statistics)

                tool_name = tool_call.get("name")
                arguments = tool_call.get("arguments", {})

                if not tool_name:
                    continue

                statistics.tool_calls_count += 1
                tool_result = self._execute_tool(tool_name, arguments)

                user_input = f"工具 {tool_name} 的执行结果：\n{tool_result}\n\n请根据工具执行结果继续处理任务。"

            if last_conversation:
                statistics.tool_calls_count = self.current_iteration - 1
                self.agent.event_bus.emit("agent.task.stop", agent=self.agent, result="达到最大迭代次数")
                return TaskConversation(conversation=last_conversation, statistics=statistics)

            final_conversation = self.agent.chat("")
            if final_conversation.completion.usage:
                statistics.add_usage(final_conversation.completion.usage)
            statistics.tool_calls_count = self.current_iteration - 1
            self.agent.event_bus.emit("agent.task.stop", agent=self.agent, result="达到最大迭代次数")
            return TaskConversation(conversation=final_conversation, statistics=statistics)

        except Exception as e:
            self.agent.event_bus.emit("agent.task.error", agent=self.agent, error=e)
            if last_conversation:
                return TaskConversation(conversation=last_conversation, statistics=statistics)
            raise

    def _parse_tool_call(self, completion) -> Optional[Dict]:
        """解析响应中的工具调用

        优先从 ChatCompletion 的 tool_calls 中提取，如果没有则从 content 中解析 JSON

        Args:
            completion: ChatCompletion 对象

        Returns:
            Optional[Dict]: 工具调用信息，格式为 {"name": str, "arguments": dict}，如果不存在则返回 None
        """
        if completion.message.tool_calls:
            tool_call = completion.message.tool_calls[0]
            try:
                arguments = tool_call.function.arguments_dict
                return {
                    "name": tool_call.function.name,
                    "arguments": arguments,
                }
            except Exception:
                pass

        content = completion.message.content or ""
        if not content:
            return None

        json_pattern = r"\{[^{}]*\"tool\"[^{}]*\"tool_name\"[^{}]*\}"
        json_match = re.search(json_pattern, content, re.IGNORECASE)
        if json_match:
            try:
                tool_call = json.loads(json_match.group())
                return {
                    "name": tool_call.get("tool") or tool_call.get("tool_name"),
                    "arguments": tool_call.get("arguments", {}),
                }
            except json.JSONDecodeError:
                pass

        tool_call_pattern = r"tool_call[:\s]*\{[^}]+\}"
        tool_call_match = re.search(tool_call_pattern, content, re.IGNORECASE)
        if tool_call_match:
            try:
                matched_content = tool_call_match.group()
                json_str = re.search(r"\{[^}]+\}", matched_content)
                if json_str:
                    tool_call = json.loads(json_str.group())
                    return {
                        "name": tool_call.get("name") or tool_call.get("tool"),
                        "arguments": tool_call.get("arguments", {}),
                    }
            except (json.JSONDecodeError, AttributeError):
                pass

        return None

    def _execute_tool(self, tool_name: str, arguments: Dict) -> str:
        """执行工具

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            str: 工具执行结果
        """
        return self.agent.run_tool(tool_name, **arguments)

    def _should_continue(self) -> bool:
        """判断是否继续循环

        Returns:
            bool: 是否继续
        """
        return self.current_iteration < self.max_iterations

