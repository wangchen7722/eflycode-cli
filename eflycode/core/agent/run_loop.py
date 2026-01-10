from typing import Dict, Optional

from eflycode.core.agent.base import BaseAgent, ChatConversation, TaskConversation, TaskStatistics
from eflycode.core.tool.errors import ToolExecutionError
from eflycode.core.utils.logger import logger

# Agent 运行配置常量
AGENT_MAX_ITERATIONS = 50


class AgentRunLoop:
    """Agent 运行循环，处理用户输入、工具调用和对话流程"""

    def __init__(self, agent: BaseAgent):
        """初始化运行循环

        Args:
            agent: Agent 实例
        """
        self.agent = agent
        self.max_iterations = AGENT_MAX_ITERATIONS
        self.current_iteration = 0

    def run(self, user_input: str, stream: bool = True) -> TaskConversation:
        """主运行循环

        Args:
            user_input: 用户输入
            stream: 是否使用流式对话，默认为 True

        Returns:
            TaskConversation: 包含最终响应、全部对话信息和任务统计的会话对象
        """
        logger.info(f"开始执行任务，流式模式: {stream}")
        
        self.current_iteration = 0

        # 触发 SessionStart 和 BeforeAgent hooks
        if self.agent.hook_system:
            logger.debug(f"触发 SessionStart hook: session_id={self.agent.session.id}")
            from pathlib import Path
            from eflycode.core.config.config_manager import ConfigManager

            config_manager = ConfigManager.get_instance()
            workspace_dir = config_manager.get_workspace_dir() or Path.cwd()

            # SessionStart
            self.agent.hook_system.fire_session_start_event(
                self.agent.session.id, workspace_dir
            )

            # BeforeAgent
            logger.debug(f"触发 BeforeAgent hook: session_id={self.agent.session.id}")
            hook_result = self.agent.hook_system.fire_before_agent_event(
                user_input, self.agent.session.id, workspace_dir
            )

            # 如果 hook 要求停止，直接返回
            if not hook_result.continue_:
                logger.warning(f"BeforeAgent hook 要求停止执行: reason={hook_result.system_message}")
                from eflycode.core.llm.protocol import ChatCompletion, Message
                # 创建一个空的 completion 表示任务被停止
                completion = ChatCompletion(
                    id="",
                    object="chat.completion",
                    created=0,
                    model=self.agent.model_name,
                    message=Message(role="assistant", content=hook_result.system_message or "Task stopped by hook"),
                )
                conversation = ChatConversation(completion=completion, messages=self.agent.session.get_messages())
                statistics = TaskStatistics()
                self.agent.event_bus.emit("agent.task.stop", agent=self.agent, result=hook_result.system_message or "Stopped by hook")
                return TaskConversation(conversation=conversation, statistics=statistics)

        self.agent.event_bus.emit("agent.task.start", agent=self.agent, user_input=user_input)

        statistics = TaskStatistics()
        last_conversation = None

        try:
            while self.current_iteration < self.max_iterations:
                self.current_iteration += 1
                statistics.iterations = self.current_iteration
                logger.debug(f"开始迭代 {self.current_iteration}/{self.max_iterations}")

                if stream:
                    # 使用流式对话
                    full_content = ""
                    last_chunk = None
                    
                    for chunk in self.agent.stream(user_input if self.current_iteration == 1 else ""):
                        if chunk.delta and chunk.delta.content:
                            full_content += chunk.delta.content
                        if chunk.usage:
                            statistics.add_usage(chunk.usage)
                        last_chunk = chunk
                    
                    # 流式完成后，从 session 获取最后的消息来构建 completion
                    # BaseAgent.stream 已经将完整内容添加到 session 并触发了 stop 事件
                    messages = self.agent.session.get_messages()
                    if messages and last_chunk:
                        # 获取最后一条 assistant 消息
                        last_message = None
                        for msg in reversed(messages):
                            if msg.role == "assistant":
                                last_message = msg
                                break
                        
                        if last_message:
                            from eflycode.core.llm.protocol import ChatCompletion
                            completion = ChatCompletion(
                                id=last_chunk.id,
                                object="chat.completion",
                                created=last_chunk.created,
                                model=last_chunk.model,
                                message=last_message,
                                finish_reason=last_chunk.finish_reason,
                                usage=last_chunk.usage,
                            )
                            conversation = ChatConversation(completion=completion, messages=messages)
                            last_conversation = conversation
                            response_content = full_content or last_message.content or ""
                        else:
                            # 回退到非流式
                            conversation = self.agent.chat(user_input if self.current_iteration == 1 else "")
                            last_conversation = conversation
                            response_content = conversation.content
                            if conversation.completion.usage:
                                statistics.add_usage(conversation.completion.usage)
                    else:
                        # 如果没有流式响应，回退到非流式
                        conversation = self.agent.chat(user_input if self.current_iteration == 1 else "")
                        last_conversation = conversation
                        response_content = conversation.content
                        if conversation.completion.usage:
                            statistics.add_usage(conversation.completion.usage)
                else:
                    # 使用非流式对话
                    conversation = self.agent.chat(user_input if self.current_iteration == 1 else "")
                    last_conversation = conversation
                    response_content = conversation.content
                    if conversation.completion.usage:
                        statistics.add_usage(conversation.completion.usage)

                tool_calls = self._parse_tool_calls(conversation.completion)
                if not tool_calls:
                    statistics.tool_calls_count = self.current_iteration - 1
                    result_content = response_content

                    # 触发 AfterAgent hook
                    if self.agent.hook_system:
                        logger.debug(f"触发 AfterAgent hook: session_id={self.agent.session.id}")
                        from pathlib import Path
                        from eflycode.core.config.config_manager import ConfigManager

                        config_manager = ConfigManager.get_instance()
                        workspace_dir = config_manager.get_workspace_dir() or Path.cwd()

                        hook_result = self.agent.hook_system.fire_after_agent_event(
                            user_input, result_content, self.agent.session.id, workspace_dir
                        )

                        # 如果 hook 有系统消息，添加到结果中
                        if hook_result.system_message:
                            message_length = len(hook_result.system_message)
                            logger.debug(f"AfterAgent hook 添加系统消息: message_length={message_length}")
                            result_content = hook_result.system_message

                    logger.info(f"任务完成: iterations={statistics.iterations}, tool_calls={statistics.tool_calls_count}, total_tokens={statistics.total_tokens}")
                    self.agent.event_bus.emit("agent.task.stop", agent=self.agent, result=result_content)
                    return TaskConversation(conversation=conversation, statistics=statistics)

                tool_results = []
                for tool_call in tool_calls:
                    tool_name = tool_call.get("name")
                    arguments = tool_call.get("arguments", {})
                    tool_call_id = tool_call.get("id", "")

                    if not tool_name:
                        continue

                    logger.info(f"执行工具: {tool_name}, 参数: {arguments}")

                    statistics.tool_calls_count += 1
                    tool_result = self._execute_tool(tool_name, arguments, tool_call_id)

                    tool_result_length = len(tool_result)
                    logger.info(f"工具 {tool_name} 执行完成，结果长度: {tool_result_length} 字符")

                    # 将工具执行结果作为工具消息添加到 session 中
                    # 这是 OpenAI API 的要求：当 assistant 消息包含 tool_calls 时，必须紧接着发送工具消息
                    self.agent.session.add_message("tool", content=tool_result, tool_call_id=tool_call_id)
                    tool_results.append((tool_name, tool_result))

                results_text = "\n\n".join(
                    f"工具 {name} 的执行结果：\n{result}" for name, result in tool_results
                )
                user_input = f"{results_text}\n\n请根据工具执行结果继续处理任务。"

            if last_conversation:
                statistics.tool_calls_count = self.current_iteration - 1
                logger.warning(f"达到最大迭代次数: iterations={self.current_iteration}, tool_calls={statistics.tool_calls_count}")
                self.agent.event_bus.emit("agent.task.stop", agent=self.agent, result="达到最大迭代次数")
                return TaskConversation(conversation=last_conversation, statistics=statistics)

            final_conversation = self.agent.chat("")
            if final_conversation.completion.usage:
                statistics.add_usage(final_conversation.completion.usage)
            statistics.tool_calls_count = self.current_iteration - 1
            logger.warning(f"达到最大迭代次数: iterations={self.current_iteration}, tool_calls={statistics.tool_calls_count}")
            self.agent.event_bus.emit("agent.task.stop", agent=self.agent, result="达到最大迭代次数")
            return TaskConversation(conversation=final_conversation, statistics=statistics)

        except Exception as e:
            error_type = type(e).__name__
            error_message = str(e)
            logger.error(f"任务执行失败: iteration={self.current_iteration}, error={error_type}: {error_message}", exc_info=True)
            self.agent.event_bus.emit("agent.task.error", agent=self.agent, error=e)
            if last_conversation:
                return TaskConversation(conversation=last_conversation, statistics=statistics)
            raise
        finally:
            # 触发 SessionEnd hook
            if self.agent.hook_system:
                logger.debug(f"触发 SessionEnd hook: session_id={self.agent.session.id}")
                from pathlib import Path
                from eflycode.core.config.config_manager import ConfigManager

                config_manager = ConfigManager.get_instance()
                workspace_dir = config_manager.get_workspace_dir() or Path.cwd()

                self.agent.hook_system.fire_session_end_event(
                    self.agent.session.id, workspace_dir
                )

    def _parse_tool_calls(self, completion) -> Optional[list[Dict]]:
        """解析响应中的工具调用

        从 ChatCompletion 的 tool_calls 中提取工具调用信息

        Args:
            completion: ChatCompletion 对象

        Returns:
            Optional[list[Dict]]: 工具调用信息列表，格式为 {"name": str, "arguments": dict, "id": str}，如果不存在则返回 None
        """
        tool_calls = completion.message.tool_calls or []
        if not tool_calls:
            return None

        parsed_calls = []
        for tool_call in tool_calls:
            try:
                arguments = tool_call.function.arguments_dict
                parsed_calls.append(
                    {
                        "name": tool_call.function.name,
                        "arguments": arguments,
                        "id": tool_call.id,
                    }
                )
            except Exception:
                continue

        return parsed_calls or None

    def _execute_tool(self, tool_name: str, arguments: Dict, tool_call_id: str = "") -> str:
        """执行工具

        Args:
            tool_name: 工具名称
            arguments: 工具参数
            tool_call_id: 工具调用 ID

        Returns:
            str: 工具执行结果，如果执行失败则返回错误信息

        Raises:
            Exception: 如果不是 ToolExecutionError，则重新抛出异常
        """
        try:
            return self.agent.run_tool(tool_name, tool_call_id=tool_call_id, **arguments)
        except ToolExecutionError as e:
            # 捕获工具执行错误，将错误信息作为结果返回给模型
            error_message = str(e)
            logger.error(f"工具 {tool_name} 执行失败: {e}")
            return error_message
        except Exception as e:
            # 其他异常，如代码 bug，应该直接抛出，让程序报错
            logger.error(f"工具 {tool_name} 执行时发生意外错误: {e}", exc_info=True)
            raise

    def _should_continue(self) -> bool:
        """判断是否继续循环

        Returns:
            bool: 是否继续
        """
        return self.current_iteration < self.max_iterations

