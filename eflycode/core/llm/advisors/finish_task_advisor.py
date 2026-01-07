import json
from typing import Dict, Optional

from eflycode.core.llm.advisor import Advisor
from eflycode.core.llm.protocol import (
    ChatCompletion,
    ChatCompletionChunk,
    DeltaMessage,
    DeltaToolCall,
    LLMRequest,
    Message,
)


class FinishTaskAdvisor(Advisor):
    """FinishTask Advisor，将 finish_task 工具调用转换为普通 assistant 消息"""

    def __init__(self):
        """初始化 FinishTaskAdvisor"""
        # 延迟导入以避免循环导入
        from eflycode.core.tool.finish_task_tool import FinishTaskTool
        
        self._finish_task_tool = FinishTaskTool()
        # 用于流式响应的状态：request_id -> state
        self._stream_states: Dict[str, "_StreamState"] = {}

    def before_call(self, request: LLMRequest) -> LLMRequest:
        """在请求发送前注入 finish_task 工具

        Args:
            request: LLM请求

        Returns:
            LLMRequest: 修改后的请求
        """
        if request.tools is None:
            request.tools = []

        # 检查是否已有 finish_task 工具
        has_finish_task = any(
            tool.function.name == "finish_task" for tool in request.tools
        )
        if not has_finish_task:
            request.tools.append(self._finish_task_tool.definition)

        return request

    def before_stream(self, request: LLMRequest) -> LLMRequest:
        """在流式请求发送前注入 finish_task 工具

        Args:
            request: LLM请求

        Returns:
            LLMRequest: 修改后的请求
        """
        # 初始化流式状态
        request_id = self._get_request_id(request)
        self._stream_states[request_id] = _StreamState()

        return self.before_call(request)

    def after_call(self, request: LLMRequest, response: ChatCompletion) -> ChatCompletion:
        """在响应接收后转换 finish_task 工具调用

        Args:
            request: LLM请求
            response: LLM响应

        Returns:
            ChatCompletion: 修改后的响应
        """
        if response.message.tool_calls:
            for tool_call in response.message.tool_calls:
                if tool_call.function.name == "finish_task":
                    content = tool_call.function.arguments_dict.get("content", "")
                    # 转换为普通 assistant 消息
                    response.message.content = content
                    response.message.tool_calls = None
                    break

        return response

    def after_stream(
        self, request: LLMRequest, chunk: ChatCompletionChunk
    ) -> ChatCompletionChunk:
        """在流式响应接收后处理 finish_task 工具调用

        Args:
            request: LLM请求
            chunk: LLM流式响应块

        Returns:
            ChatCompletionChunk: 修改后的响应块
        """
        request_id = self._get_request_id(request)
        state = self._stream_states.get(request_id)

        if state is None:
            return chunk

        # 如果已经完成转换，继续输出 content
        if state.converted:
            result_chunk = self._emit_content_chunk(chunk, state)
            # 如果流式响应结束，清理状态
            if chunk.finish_reason is not None:
                self._stream_states.pop(request_id, None)
            return result_chunk

        # 处理 tool_calls delta
        if chunk.delta and chunk.delta.tool_calls:
            for delta_tc in chunk.delta.tool_calls:
                index = delta_tc.index

                # 初始化工具调用状态
                if index not in state.tool_calls:
                    state.tool_calls[index] = {
                        "id": delta_tc.id or "",
                        "name": "",
                        "arguments": "",
                    }

                tc_state = state.tool_calls[index]

                # 累积 name
                if delta_tc.function and delta_tc.function.name:
                    tc_state["name"] = delta_tc.function.name

                # 累积 arguments
                if delta_tc.function and delta_tc.function.arguments:
                    tc_state["arguments"] += delta_tc.function.arguments

                # 检测到 finish_task 工具调用
                if tc_state["name"] == "finish_task":
                    state.detected_finish_task = True
                    state.finish_task_index = index

                    # 尝试解析 arguments
                    try:
                        arguments_dict = json.loads(tc_state["arguments"])
                        content = arguments_dict.get("content", "")
                        if content:
                            state.content = content
                            state.converted = True
                            # 移除 tool_calls delta，返回第一个 content chunk
                            chunk.delta.tool_calls = None
                            return self._emit_content_chunk(chunk, state)
                    except (json.JSONDecodeError, KeyError):
                        # arguments 还不完整，继续累积
                        # 移除 tool_calls delta，避免显示工具调用信息
                        chunk.delta.tool_calls = None
                        pass

        # 如果已检测到 finish_task 但 arguments 还不完整，继续累积
        if state.detected_finish_task and not state.converted:
            index = state.finish_task_index
            if index in state.tool_calls:
                tc_state = state.tool_calls[index]
                try:
                    arguments_dict = json.loads(tc_state["arguments"])
                    content = arguments_dict.get("content", "")
                    if content:
                        state.content = content
                        state.converted = True
                        # 移除 tool_calls delta
                        if chunk.delta:
                            chunk.delta.tool_calls = None
                        return self._emit_content_chunk(chunk, state)
                except (json.JSONDecodeError, KeyError):
                    # arguments 还不完整，移除 tool_calls delta，等待下一个 chunk
                    if chunk.delta:
                        chunk.delta.tool_calls = None
                    return chunk

        # 如果已转换，移除 tool_calls delta
        if state.converted and chunk.delta and chunk.delta.tool_calls:
            chunk.delta.tool_calls = None

        # 清理：如果流式响应结束，清理状态
        if chunk.finish_reason is not None:
            self._stream_states.pop(request_id, None)

        return chunk

    def _emit_content_chunk(
        self, chunk: ChatCompletionChunk, state: "_StreamState"
    ) -> ChatCompletionChunk:
        """输出 content 的 chunk

        Args:
            chunk: 原始响应块
            state: 流式状态

        Returns:
            ChatCompletionChunk: 修改后的响应块
        """
        if not state.content:
            return chunk

        # 计算本次要输出的内容
        remaining = state.content[state.content_index :]
        if not remaining:
            # 内容已全部输出，返回原始 chunk，可能是 finish_reason
            return chunk

        # 如果 finish_reason 不为 None，输出所有剩余内容，避免内容丢失
        # 否则每次输出一小块，模拟流式效果
        if chunk.finish_reason is not None:
            # 流式响应结束，输出所有剩余内容
            content_chunk = remaining
            state.content_index = len(state.content)
        else:
            # 每次输出一小块，模拟流式效果
            chunk_size = min(20, len(remaining))
            content_chunk = remaining[:chunk_size]
            state.content_index += chunk_size

        # 创建新的 delta，只包含 content
        if chunk.delta is None:
            from eflycode.core.llm.protocol import DeltaMessage

            chunk.delta = DeltaMessage()
        chunk.delta.content = content_chunk
        chunk.delta.tool_calls = None

        return chunk

    def _get_request_id(self, request: LLMRequest) -> str:
        """获取请求的唯一标识

        Args:
            request: LLM请求

        Returns:
            str: 请求ID
        """
        # 使用消息列表的哈希作为请求ID
        import hashlib

        messages_str = str([(msg.role, msg.content) for msg in request.messages])
        return hashlib.md5(messages_str.encode()).hexdigest()


class _StreamState:
    """流式响应状态"""

    def __init__(self):
        """初始化流式状态"""
        self.tool_calls: Dict[int, Dict[str, str]] = {}  # index -> {id, name, arguments}
        self.detected_finish_task: bool = False
        self.finish_task_index: Optional[int] = None
        self.content: str = ""
        self.content_index: int = 0
        self.converted: bool = False

