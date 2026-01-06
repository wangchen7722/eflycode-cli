import time
from typing import Dict, Optional

from eflycode.core.agent.base import BaseAgent, ChatConversation, TaskConversation, TaskStatistics
from eflycode.core.tool.errors import ToolExecutionError
from eflycode.core.utils.logger import logger


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
        self.agent.event_bus.emit("agent.task.start", agent=self.agent, user_input=user_input)

        statistics = TaskStatistics()
        last_conversation = None

        try:
            while self.current_iteration < self.max_iterations:
                self.current_iteration += 1
                statistics.iterations = self.current_iteration

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

                tool_call = self._parse_tool_call(conversation.completion)
                if not tool_call:
                    statistics.tool_calls_count = self.current_iteration - 1
                    self.agent.event_bus.emit("agent.task.stop", agent=self.agent, result=response_content)
                    return TaskConversation(conversation=conversation, statistics=statistics)

                tool_name = tool_call.get("name")
                arguments = tool_call.get("arguments", {})
                tool_call_id = tool_call.get("id", "")

                if not tool_name:
                    continue

                # 特殊处理 finish_task 工具
                if tool_name == "finish_task":
                    content = arguments.get("content", "")
                    logger.info("调用 finish_task 工具，任务完成")

                    # 将工具执行结果作为工具消息添加到 session 中
                    # 当 assistant 消息包含 tool_calls 时，必须紧接着发送工具消息
                    self.agent.session.add_message("tool", content="", tool_call_id=tool_call_id)

                    # 流式输出 content
                    if content:
                        # 通过事件系统流式输出 content
                        # 按块输出，每块 20 个字符，模拟流式效果
                        chunk_size = 20
                        for i in range(0, len(content), chunk_size):
                            chunk = content[i:i + chunk_size]
                            self.agent.event_bus.emit(
                                "agent.message.delta",
                                agent=self.agent,
                                delta=chunk,
                            )
                            # 添加小延迟，模拟流式输出效果
                            time.sleep(0.05)
                        # 触发消息结束事件
                        self.agent.event_bus.emit("agent.message.stop", agent=self.agent, response=conversation.completion)
                    
                    statistics.tool_calls_count = self.current_iteration
                    # 触发任务结束事件，这会立即输出任务完成
                    self.agent.event_bus.emit("agent.task.stop", agent=self.agent, result=content)
                    return TaskConversation(conversation=conversation, statistics=statistics)

                logger.info(f"执行工具: {tool_name}, 参数: {arguments}")

                statistics.tool_calls_count += 1
                tool_result = self._execute_tool(tool_name, arguments, tool_call_id)
                
                logger.info(f"工具 {tool_name} 执行完成，结果长度: {len(tool_result)} 字符")

                # 将工具执行结果作为工具消息添加到 session 中
                # 这是 OpenAI API 的要求：当 assistant 消息包含 tool_calls 时，必须紧接着发送工具消息
                self.agent.session.add_message("tool", content=tool_result, tool_call_id=tool_call_id)

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

        从 ChatCompletion 的 tool_calls 中提取工具调用信息

        Args:
            completion: ChatCompletion 对象

        Returns:
            Optional[Dict]: 工具调用信息，格式为 {"name": str, "arguments": dict, "id": str}，如果不存在则返回 None
        """
        if completion.message.tool_calls:
            tool_call = completion.message.tool_calls[0]
            try:
                arguments = tool_call.function.arguments_dict
                return {
                    "name": tool_call.function.name,
                    "arguments": arguments,
                    "id": tool_call.id,
                }
            except Exception:
                pass

        return None

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

