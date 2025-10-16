import json
from typing import Generator, Optional
from eflycode.schema.llm import ChatCompletionChunk, ChatCompletion, ToolCall, ToolCallFunction, Usage
from eflycode.schema.agent import AgentResponseChunk, AgentResponseChunkType, AgentResponse


class AgentResponseConverter:
    """
    将底层 LLM 的流式响应转换为统一Agent Response格式
    - 普通文本直接转发
    - 工具调用参数增量合并，只输出一次工具名，参数完整后输出完整工具调用
    """
    def __init__(self):
        self.active_tool_name: Optional[str] = None
        self.active_tool_call_index: Optional[int] = None
        self.active_tool_call_id: Optional[str] = None
        self.active_tool_call_type: Optional[str] = None
        self.accumulated_arguments: str = ""
        self.tool_call_in_progress: bool = False

    def convert(
            self, chat_completion: ChatCompletion
    ) -> AgentResponse:
        self._reset_state()
        return AgentResponse(
            messages=[chat_completion.choices[0].message] if chat_completion.choices else [],
            content=chat_completion.choices[0].message.content if chat_completion.choices else "",
            finish_reason=chat_completion.choices[0].finish_reason if chat_completion.choices else None,
            tool_calls=chat_completion.choices[0].message.tool_calls if chat_completion.choices and chat_completion.choices[0].message.tool_calls else None,
            usage=chat_completion.usage,
            metadata={"model": chat_completion.model} if chat_completion.model else {}
        )

    def convert_stream(
            self, chat_completion_chunk_stream: Generator[ChatCompletionChunk, None, None]
    ) -> Generator[AgentResponseChunk, None, None]:
        """将 ChatCompletionChunk 转换为 AgentResponseChunk"""
        self._reset_state()
        for chunk in chat_completion_chunk_stream:
            choice = chunk.choices[0]
            delta = choice.delta
            finish_reason = choice.finish_reason

            if finish_reason == "tool_calls":
                if self.active_tool_name and self._is_valid_json(self.accumulated_arguments):
                    yield self._make_tool_call_chunk(AgentResponseChunkType.TOOL_CALL_END, self.active_tool_call_id, self.active_tool_call_type, self.active_tool_name, self.accumulated_arguments, chunk)
                yield AgentResponseChunk(
                    type=AgentResponseChunkType.DONE,
                    content="",
                    finish_reason="tool_calls",
                    tool_calls=None,
                    usage=self._convert_usage(chunk),
                    metadata=self._convert_metadata(chunk),
                )
                self._reset_state()
                continue

            # 文本流
            if not delta.tool_calls:
                if delta.content:
                    yield AgentResponseChunk(
                        type=AgentResponseChunkType.TEXT,
                        content=delta.content,
                        finish_reason=finish_reason,
                        tool_calls=None,
                        usage=self._convert_usage(chunk),
                        metadata={"model": chunk.model},
                    )
                continue

            # 工具流
            for tool_delta in delta.tool_calls:
                tool_call_index = tool_delta.index
                tool_call_id = tool_delta.id
                tool_call_name = tool_delta.function.name
                tool_call_type = str(tool_delta.type)
                tool_call_args = tool_delta.function.arguments
                
                # 新的工具调用开始，重置状态
                if tool_call_name and tool_call_index != self.active_tool_call_index:
                    # 如果有之前的工具调用在进行中，先结束它
                    if self.active_tool_name and self._is_valid_json(self.accumulated_arguments):
                        yield self._make_tool_call_chunk(AgentResponseChunkType.TOOL_CALL_END, self.active_tool_call_id, self.active_tool_call_type, self.active_tool_name, self.accumulated_arguments, chunk)
                    
                    # 开始新的工具调用
                    self.active_tool_name = tool_call_name
                    self.active_tool_call_index = tool_call_index
                    self.active_tool_call_id = tool_call_id
                    self.active_tool_call_type = tool_call_type
                    self.accumulated_arguments = ""
                    self.tool_call_in_progress = True
                    yield self._make_tool_call_chunk(AgentResponseChunkType.TOOL_CALL_START, self.active_tool_call_id, self.active_tool_call_type,
                                                     self.active_tool_name, tool_call_args, chunk)

                if tool_call_args:
                    self.accumulated_arguments += tool_call_args

    def _make_tool_call_chunk(self, type: AgentResponseChunkType, tool_call_id: str, tool_call_type: str, tool_call_name: str, tool_call_args: str, chunk: ChatCompletionChunk) -> AgentResponseChunk:
        """构造一个 TOOL_CALL 类型的响应块"""
        return AgentResponseChunk(
            type=type,
            content="",
            finish_reason=None,
            tool_calls=[
                ToolCall(
                    id=tool_call_id,
                    type=tool_call_type,
                    function=ToolCallFunction(
                        name=tool_call_name,
                        arguments=tool_call_args,
                    ),
                )
            ],
            usage=self._convert_usage(chunk),
            metadata=self._convert_metadata(chunk)
        )

    def _reset_state(self):
        self.active_tool_name = None
        self.active_tool_call_id = None
        self.active_tool_call_type = None
        self.active_tool_call_index = None
        self.accumulated_arguments = ""
        self.tool_call_in_progress = False

    @staticmethod
    def _is_valid_json(text: str) -> bool:
        try:
            json.loads(text)
            return True
        except Exception:
            return False

    @staticmethod
    def _convert_usage(completion) -> Optional[Usage]:
        if not completion.usage:
            return None
        return Usage(
            prompt_tokens=getattr(completion.usage, "prompt_tokens", 0),
            completion_tokens=getattr(completion.usage, "completion_tokens", 0),
            total_tokens=getattr(completion.usage, "total_tokens", 0),
        )

    @staticmethod
    def _convert_metadata(completion) -> dict:
        if not completion.model:
            return {}
        return {
            "model": completion.model
        }
