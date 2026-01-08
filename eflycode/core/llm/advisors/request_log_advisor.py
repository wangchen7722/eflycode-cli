"""LLM 请求日志 Advisor

在 verbose 模式下记录所有 LLM 请求和响应
"""

import datetime
from pathlib import Path
from typing import Dict, List, Optional

from eflycode.core.constants import EFLYCODE_DIR, VERBOSE_DIR, REQUESTS_DIR
from eflycode.core.llm.advisor import Advisor
from eflycode.core.llm.protocol import (
    ChatCompletion,
    ChatCompletionChunk,
    LLMRequest,
    Message,
)


class RequestLogAdvisor(Advisor):
    """请求日志 Advisor，记录所有 LLM 请求和响应到日志文件"""

    def __init__(self, session_id: str):
        """初始化 RequestLogAdvisor

        Args:
            session_id: 会话 ID，用于生成日志文件名
        """
        self.session_id = session_id
        self.log_file = self._get_log_file_path()
        self._request_count = 0
        # 用于流式响应的状态：累积完整响应
        self._stream_states: Dict[str, "_StreamLogState"] = {}
        
        # 确保日志目录存在
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def _get_log_file_path(self) -> Path:
        """获取日志文件路径

        Returns:
            Path: 日志文件路径
        """
        # 延迟导入以避免循环导入
        from eflycode.core.config.config_manager import resolve_workspace_dir
        
        workspace_dir = resolve_workspace_dir()
        return workspace_dir / EFLYCODE_DIR / VERBOSE_DIR / REQUESTS_DIR / f"{self.session_id}.log"

    def _get_timestamp(self) -> str:
        """获取当前时间戳

        Returns:
            str: 格式化的时间戳
        """
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _format_messages(self, messages: List[Message]) -> str:
        """格式化消息列表

        Args:
            messages: 消息列表

        Returns:
            str: 格式化的消息字符串
        """
        lines = []
        for msg in messages:
            role = msg.role
            content = msg.content or ""
            
            # 处理多行内容
            content_lines = content.split("\n")
            if len(content_lines) > 1:
                first_line = content_lines[0]
                lines.append(f"  [{role}] {first_line}")
                for line in content_lines[1:]:
                    lines.append(f"          {line}")
            else:
                lines.append(f"  [{role}] {content}")
            
            # 如果有工具调用，记录工具调用信息
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    lines.append(f"    -> Tool: {tc.function.name}")
                    args = tc.function.arguments
                    if len(args) > 200:
                        args = args[:200] + "..."
                    lines.append(f"       Args: {args}")
            
            # 如果是工具响应，记录工具调用 ID
            if msg.tool_call_id:
                lines.append(f"    (tool_call_id: {msg.tool_call_id})")
        
        return "\n".join(lines)

    def _format_tool_calls(self, tool_calls: Optional[List]) -> str:
        """格式化工具调用列表

        Args:
            tool_calls: 工具调用列表

        Returns:
            str: 格式化的工具调用字符串
        """
        if not tool_calls:
            return "None"
        
        lines = []
        for tc in tool_calls:
            lines.append(f"  - {tc.function.name}")
            args = tc.function.arguments
            if len(args) > 200:
                args = args[:200] + "..."
            lines.append(f"    Args: {args}")
        
        return "\n".join(lines)

    def _write_log(self, content: str) -> None:
        """写入日志

        Args:
            content: 日志内容
        """
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(content)
            f.write("\n")

    def _log_request(self, request: LLMRequest) -> None:
        """记录请求

        Args:
            request: LLM 请求
        """
        self._request_count += 1
        
        log_content = f"""
{'=' * 60}
=== LLM Request #{self._request_count} ===
{'=' * 60}
Time: {self._get_timestamp()}
Model: {request.model}
Messages ({len(request.messages)} total):
{self._format_messages(request.messages)}
Tools: {len(request.tools) if request.tools else 0} available
"""
        self._write_log(log_content)

    def _log_response(self, response: ChatCompletion) -> None:
        """记录响应

        Args:
            response: LLM 响应
        """
        content = response.message.content or ""
        
        # 获取 token 使用情况
        usage_str = "N/A"
        if response.usage:
            usage_str = f"prompt={response.usage.prompt_tokens}, completion={response.usage.completion_tokens}, total={response.usage.total_tokens}"
        
        log_content = f"""
{'=' * 60}
=== LLM Response #{self._request_count} ===
{'=' * 60}
Time: {self._get_timestamp()}
Tokens: {usage_str}
Finish Reason: {response.finish_reason or 'N/A'}
Content:
{content}
Tool Calls:
{self._format_tool_calls(response.message.tool_calls)}
"""
        self._write_log(log_content)

    def before_call(self, request: LLMRequest) -> LLMRequest:
        """在请求发送前记录请求

        Args:
            request: LLM请求

        Returns:
            LLMRequest: 原始请求（不修改）
        """
        self._log_request(request)
        return request

    def after_call(self, request: LLMRequest, response: ChatCompletion) -> ChatCompletion:
        """在响应接收后记录响应

        Args:
            request: LLM请求
            response: LLM响应

        Returns:
            ChatCompletion: 原始响应（不修改）
        """
        self._log_response(response)
        return response

    def before_stream(self, request: LLMRequest) -> LLMRequest:
        """在流式请求发送前记录请求

        Args:
            request: LLM请求

        Returns:
            LLMRequest: 原始请求（不修改）
        """
        self._log_request(request)
        
        # 初始化流式状态
        request_id = self._get_request_id(request)
        self._stream_states[request_id] = _StreamLogState()
        
        return request

    def after_stream(self, request: LLMRequest, chunk: ChatCompletionChunk) -> ChatCompletionChunk:
        """在流式响应接收后累积响应内容

        Args:
            request: LLM请求
            chunk: LLM流式响应块

        Returns:
            ChatCompletionChunk: 原始响应块
        """
        request_id = self._get_request_id(request)
        state = self._stream_states.get(request_id)
        
        if state is None:
            return chunk
        
        # 累积内容
        if chunk.delta and chunk.delta.content:
            state.content += chunk.delta.content
        
        # 累积工具调用
        if chunk.delta and chunk.delta.tool_calls:
            for delta_tc in chunk.delta.tool_calls:
                index = delta_tc.index
                if index not in state.tool_calls:
                    state.tool_calls[index] = {
                        "id": delta_tc.id or "",
                        "name": "",
                        "arguments": "",
                    }
                
                tc_state = state.tool_calls[index]
                if delta_tc.function:
                    if delta_tc.function.name:
                        tc_state["name"] = delta_tc.function.name
                    if delta_tc.function.arguments:
                        tc_state["arguments"] += delta_tc.function.arguments
        
        # 记录 finish_reason
        if chunk.finish_reason:
            state.finish_reason = chunk.finish_reason
        
        # 如果流式响应结束，记录完整响应
        if chunk.finish_reason is not None:
            self._log_stream_response(state)
            self._stream_states.pop(request_id, None)
        
        return chunk

    def _log_stream_response(self, state: "_StreamLogState") -> None:
        """记录流式响应的完整内容

        Args:
            state: 流式状态
        """
        content = state.content
        
        # 格式化工具调用
        tool_calls_str = "None"
        if state.tool_calls:
            lines = []
            for index in sorted(state.tool_calls.keys()):
                tc = state.tool_calls[index]
                lines.append(f"  - {tc['name']}")
                args = tc["arguments"]
                if len(args) > 200:
                    args = args[:200] + "..."
                lines.append(f"    Args: {args}")
            tool_calls_str = "\n".join(lines)
        
        log_content = f"""
{'=' * 60}
=== LLM Response #{self._request_count} (Stream) ===
{'=' * 60}
Time: {self._get_timestamp()}
Tokens: N/A (stream mode)
Finish Reason: {state.finish_reason or 'N/A'}
Content:
{content}
Tool Calls:
{tool_calls_str}
"""
        self._write_log(log_content)

    def _get_request_id(self, request: LLMRequest) -> str:
        """获取请求的唯一标识

        Args:
            request: LLM请求

        Returns:
            str: 请求ID
        """
        import hashlib

        messages_str = str([(msg.role, msg.content) for msg in request.messages])
        return hashlib.md5(messages_str.encode()).hexdigest()


class _StreamLogState:
    """流式响应日志状态"""

    def __init__(self):
        """初始化流式状态"""
        self.content: str = ""
        self.tool_calls: Dict[int, Dict[str, str]] = {}  # index -> {id, name, arguments}
        self.finish_reason: Optional[str] = None

