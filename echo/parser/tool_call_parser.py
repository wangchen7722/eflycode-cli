import json
import uuid
from typing import Generator, Optional, Sequence, List
from echo.schema.llm import ChatCompletionChunk, DeltaToolCallFunction, StreamChoice, ToolCall, DeltaToolCall, \
    ToolDefinition, ToolFunction, Message, DeltaMessage, \
    ToolCallFunction, ChatCompletion
from echo.parser.base_parser import ChatCompletionStreamParser, ChatCompletionParser


class ToolCallStreamParser(ChatCompletionStreamParser):
    """流式响应解析器，支持解析工具调用"""

    # 状态常量
    STATE_TEXT = "TEXT"
    STATE_POTENTIAL_TAG = "POTENTIAL_TAG"
    STATE_TOOL_NAME = "TOOL_NAME"
    STATE_PARAMS = "PARAMS"

    def __init__(
            self,
            tools: Sequence[ToolDefinition],
            tool_call_start: str = "<tool_call>",
            tool_call_end: str = "</tool_call>",
            tool_name_start: str = "<tool_name>",
            tool_name_end: str = "</tool_name>",
            tool_params_start: str = "<tool_params>",
            tool_params_end: str = "</tool_params>",
    ):
        """
        初始化解析器

        Args:
            tools: 可用的工具列表
            tool_call_start: 工具调用开始标签
            tool_call_end: 工具调用结束标签
            tool_name_start: 工具名开始标签
            tool_name_end: 工具名结束标签
            tool_params_start: 参数开始标签
            tool_params_end: 参数结束标签
        """
        super().__init__(tools)

        # 标签属性
        self.tool_call_start = tool_call_start
        self.tool_call_end = tool_call_end
        self.tool_name_start = tool_name_start
        self.tool_name_end = tool_name_end
        self.tool_params_start = tool_params_start
        self.tool_params_end = tool_params_end

        # 预计算候选标签（在设置标签属性后）
        self._build_candidate_tags()

        # 状态变量
        self._reset_state()

        # OpenAI 格式相关状态
        self.tool_call_index = 0

    def _build_candidate_tags(self):
        """构建候选标签映射"""
        self.candidate_tags = {
            # 工具调用标签
            self.tool_call_start: self.tool_call_start,
            self.tool_call_end: self.tool_call_end,
            # 工具名标签
            self.tool_name_start: self.tool_name_start,
            self.tool_name_end: self.tool_name_end,
            # 参数标签
            self.tool_params_start: self.tool_params_start,
            self.tool_params_end: self.tool_params_end,
        }

    def _reset_state(self):
        """重置解析器状态"""
        self.state = self.STATE_TEXT
        self.tag_buffer = ""
        self.tag_context = None
        self.tool_call = None
        self.tool_name_buffer = ""
        self.params_buffer = ""
        self.text_buffer = ""

    def parse_stream(
            self, chat_completion_chunk_stream: Generator[ChatCompletionChunk, None, None]
    ) -> Generator[ChatCompletionChunk, None, None]:
        """
        状态机解析器，支持可配置的工具调用分隔符

        Args:
            chat_completion_chunk_stream: 聊天完成块的流式生成器

        Yields:
            ChatCompletionChunk: 解析后的响应块
        """
        raw_content = ""
        last_chunk = None

        # 主循环：逐个 chunk 处理
        for chunk in chat_completion_chunk_stream:
            if chunk is None:
                continue
            last_chunk = chunk
            chunk_content = chunk.choices[0].delta.content
            raw_content += chunk_content

            for char in chunk_content:
                yield from self._process_character(char, chunk)

        # 流结束后处理残留数据
        yield from self._handle_stream_end(last_chunk)

    def parse_text(self, text: str, chunk: ChatCompletionChunk) -> Generator[ChatCompletionChunk, None, None]:
        """解析纯文本内容（用于测试）

        Args:
            text: 要解析的文本内容

        Yields:
            ChatCompletionChunk: 解析后的响应块
        """
        self._reset_state()

        for char in text:
            yield from self._process_character(char, chunk)

        # 处理残留数据
        yield from self._handle_stream_end(chunk)

    def _process_character(
            self, char: str, chunk: ChatCompletionChunk
    ) -> Generator[ChatCompletionChunk, None, None]:
        """
        处理单个字符

        Args:
            char: 当前字符
            chunk: 当前的 ChatCompletionChunk
        """
        if self.state == self.STATE_TEXT:
            yield from self._handle_text_state(char, chunk)
        elif self.state == self.STATE_POTENTIAL_TAG:
            yield from self._handle_potential_tag_state(char, chunk)
        elif self.state == self.STATE_TOOL_NAME:
            yield from self._handle_tool_name_state(char, chunk)
        elif self.state == self.STATE_PARAMS:
            yield from self._handle_params_state(char, chunk)

    def _handle_text_state(
            self, char: str, chunk: ChatCompletionChunk
    ) -> Generator[ChatCompletionChunk, None, None]:
        """处理TEXT状态"""
        if char == self.tool_call_start[0]:  # 检查工具调用开始标记的第一个字符
            # 进入潜在标签状态
            self.state = self.STATE_POTENTIAL_TAG
            self.tag_buffer = char
        else:
            if self.tool_call:
                self.tool_call["content"] += char
            else:
                # 立即输出单个字符，实现真正的流式输出
                yield ChatCompletionChunk(
                    id=chunk.id,
                    object=chunk.object,
                    created=chunk.created,
                    model=chunk.model,
                    choices=[StreamChoice(
                        index=0,
                        delta=DeltaMessage(
                            role=chunk.choices[0].delta.role,
                            content=char,
                        ),
                        finish_reason=None,
                    )],
                    usage=None,
                )

    def _handle_potential_tag_state(
            self, char: str, chunk: ChatCompletionChunk
    ) -> Generator[ChatCompletionChunk, None, None]:
        """处理POTENTIAL_TAG状态"""
        self.tag_buffer += char
        candidates = self._get_candidates()

        if not candidates or not self._is_prefix(self.tag_buffer, candidates):
            # 不是有效标签前缀，恢复到之前状态
            if self.tool_call:
                self.tool_call["content"] += self.tag_buffer
            else:
                self.text_buffer += self.tag_buffer
            self.state = self.STATE_TEXT
            self.tag_buffer = ""
            self.tag_context = None
        else:
            # 检查是否完全匹配
            matched_candidate = self._exact_match(self.tag_buffer, candidates)
            if matched_candidate:
                # 在处理匹配的标签之前，输出累积的文本（如果有的话）
                if matched_candidate == self.tool_call_start and self.text_buffer:
                    yield ChatCompletionChunk(
                        id=chunk.id,
                        object=chunk.object,
                        created=chunk.created,
                        model=chunk.model,
                        choices=[StreamChoice(
                            index=0,
                            delta=DeltaMessage(
                                role=chunk.choices[0].delta.role,
                                content=self.text_buffer,
                            ),
                            finish_reason=None,
                        )],
                        usage=None,
                    )
                    self.text_buffer = ""
                yield from self._handle_matched_tag(matched_candidate, chunk)

    def _handle_tool_name_state(
            self, char: str, chunk: ChatCompletionChunk
    ) -> Generator[ChatCompletionChunk, None, None]:
        """处理工具名状态"""
        if char == self.tool_name_end[0]:  # 检查工具名结束标签的第一个字符
            self.tag_buffer = char
            self.tag_context = "TOOL_NAME"
            self.state = self.STATE_POTENTIAL_TAG
        else:
            # 累积工具名内容
            self.tool_name_buffer += char

        # 转换成生成器
        if False:
            yield

    def _handle_params_state(
            self, char: str, chunk: ChatCompletionChunk
    ) -> Generator[ChatCompletionChunk, None, None]:
        """处理参数状态"""
        if char == self.tool_params_end[0]:  # 检查参数结束标签的第一个字符
            self.tag_buffer = char
            self.tag_context = "PARAMS"
            self.state = self.STATE_POTENTIAL_TAG
        else:
            # 累积参数内容
            self.params_buffer += char
            yield ChatCompletionChunk(
                id=chunk.id,
                object=chunk.object,
                created=chunk.created,
                model=chunk.model,
                choices=[StreamChoice(
                    index=0,
                    delta=DeltaMessage(
                        role="assistant",
                        content="",
                        tool_calls=[
                            DeltaToolCall(
                                index=self.tool_call_index,
                                function=DeltaToolCallFunction(
                                    arguments=char,
                                ),
                            )
                        ]
                    ),
                    finish_reason=None,
                )],
                usage=None,
            )

    def get_tool_by_name(self, name: str) -> Optional[ToolFunction]:
        """
        根据名称获取工具

        Args:
            name: 工具名称

        Returns:
            对应的工具实例，如果不存在则返回None
        """
        return self.tool_map.get(name)

    def get_tool_parameters(self, tool_name: str) -> List[str]:
        """
        获取工具的参数列表

        Args:
            tool_name: 工具名称

        Returns:
            工具参数名称列表
        """
        tool = self.get_tool_by_name(tool_name)
        return list(tool.parameters.properties.keys()) if tool else []

    def is_valid_tool(self, tool_name: str) -> bool:
        """
        检查是否为有效的工具名称

        Args:
            tool_name: 工具名称

        Returns:
            是否为有效工具
        """
        return tool_name in self.tool_map

    def is_valid_parameter(self, tool_name: str, param_name: str) -> bool:
        """
        检查是否为工具的有效参数

        Args:
            tool_name: 工具名称
            param_name: 参数名称

        Returns:
            是否为有效参数
        """
        tool = self.get_tool_by_name(tool_name)
        return param_name in tool.parameters if tool else False

    def _get_candidates(self) -> List[str]:
        """根据当前上下文获取候选标签"""
        if self.tag_context is None:
            # 初始状态，只能匹配工具调用开始标签
            return [self.tool_call_start]
        elif self.tag_context == "TOOL_CALL":
            return [self.tool_name_start, self.tool_call_end]
        elif self.tag_context == "TOOL_NAME":
            return [self.tool_name_end]
        elif self.tag_context == "TOOL_AFTER_NAME":
            return [self.tool_params_start, self.tool_call_end]
        elif self.tag_context == "PARAMS":
            return [self.tool_params_end]
        elif self.tag_context == "TOOL_AFTER_PARAMS":
            return [self.tool_call_end]
        return list(self.candidate_tags.keys())

    def _is_prefix(self, s: str, candidates: List[str]) -> bool:
        """判断字符串是否为候选标签的前缀"""
        return any(candidate.startswith(s) for candidate in candidates)

    def _exact_match(self, s: str, candidates: List[str]) -> Optional[str]:
        """判断字符串是否与候选标签完全匹配"""
        for candidate in candidates:
            if s == candidate:
                return candidate
        return None

    def _handle_matched_tag(
            self, matched_tag: str, chunk: ChatCompletionChunk
    ) -> Generator[ChatCompletionChunk, None, None]:
        """处理匹配的标签"""
        if matched_tag == self.tool_call_start:
            # 工具调用开始
            self.tool_call = {
                "name": "",
                "arguments": {},
                "content": matched_tag,
            }
            self.tag_context = "TOOL_CALL"
            self.state = self.STATE_TEXT
            # 不立即输出，等到工具调用结束时再输出
        elif matched_tag == self.tool_name_start:
            # 工具名开始
            self.tag_context = "TOOL_NAME"
            self.state = self.STATE_TOOL_NAME
            self.tool_name_buffer = ""
            if self.tool_call:
                self.tool_call["content"] += matched_tag
            # 不立即输出，等到工具调用结束时再输出
        elif matched_tag == self.tool_name_end:
            # 工具名结束
            if self.tool_call:
                self.tool_call["name"] = self.tool_name_buffer.strip()
                self.tool_call["content"] += matched_tag
            self.tag_context = "TOOL_AFTER_NAME"
            self.state = self.STATE_TEXT
            yield ChatCompletionChunk(
                id=chunk.id,
                object=chunk.object,
                created=chunk.created,
                model=chunk.model,
                choices=[StreamChoice(
                    index=0,
                    delta=DeltaMessage(
                        role="assistant",
                        content="",
                        tool_calls=[DeltaToolCall(
                            index=self.tool_call_index,
                            function=DeltaToolCallFunction(
                                name=self.tool_name_buffer.strip(),
                                arguments="",
                            ),
                        )]
                    ),
                    finish_reason=None,
                )],
                usage=None,
            )
        elif matched_tag == self.tool_params_start:
            # 参数开始
            self.tag_context = "PARAMS"
            self.state = self.STATE_PARAMS
            self.params_buffer = ""
            if self.tool_call:
                self.tool_call["content"] += matched_tag
            # 不立即输出，等到工具调用结束时再输出
        elif matched_tag == self.tool_params_end:
            # 参数结束
            if self.tool_call:
                try:
                    # 解析JSON参数
                    params_json = self.params_buffer.strip()
                    if params_json:
                        self.tool_call["arguments"] = json.loads(params_json)
                except json.JSONDecodeError:
                    # 如果JSON解析失败，保持空参数
                    self.tool_call["arguments"] = {}
                self.tool_call["content"] += matched_tag
            self.tag_context = "TOOL_AFTER_PARAMS"
            self.state = self.STATE_TEXT
            # 不立即输出，等到工具调用结束时再输出
        elif matched_tag == self.tool_call_end:
            # 工具调用结束
            if self.tool_call:
                yield ChatCompletionChunk(
                    id=chunk.id,
                    object=chunk.object,
                    created=chunk.created,
                    model=chunk.model,
                    choices=[StreamChoice(
                        index=0,
                        delta=DeltaMessage(role="assistant", content=""),
                        finish_reason="tool_calls",
                    )],
                    usage=None,
                )
            self.tool_call = None
            self.tag_context = None
            self.state = self.STATE_TEXT

        # 重置标签相关状态
        self.tag_buffer = ""
        if matched_tag == self.tool_call_end:
            self.tag_context = None

    def _handle_stream_end(
            self, last_chunk: ChatCompletionChunk
    ) -> Generator[ChatCompletionChunk, None, None]:
        """处理流结束时的残留数据"""
        # 处理未完成的标签缓冲区
        if self.state == self.STATE_POTENTIAL_TAG:
            if self.tag_context in ["TOOL", "PARAM"] and self.tool_call:
                self.tool_call["content"] += self.tag_buffer
                if self.tag_context == "PARAM":
                    self.params_buffer += self.tag_buffer
                yield ChatCompletionChunk(
                    id=last_chunk.id,
                    object=last_chunk.object,
                    created=last_chunk.created,
                    model=last_chunk.model,
                    choices=[StreamChoice(
                        index=0,
                        delta=DeltaMessage(
                            role="assistant",
                            content=self.tag_buffer,
                        ),
                        finish_reason=last_chunk.choices[0].finish_reason,
                        tool_calls=None,
                    )],
                    usage=last_chunk.usage,
                )
            else:
                # 将未完成的标签缓冲区内容添加到文本缓冲区
                self.text_buffer += self.tag_buffer

        # 输出剩余的文本缓冲区内容
        if self.text_buffer:
            yield ChatCompletionChunk(
                id=last_chunk.id,
                object=last_chunk.object,
                created=last_chunk.created,
                model=last_chunk.model,
                choices=[StreamChoice(
                    index=0,
                    delta=DeltaMessage(
                        role="assistant",
                        content=self.text_buffer,
                    ),
                    finish_reason=last_chunk.choices[0].finish_reason,
                    tool_calls=None,
                )],
                usage=last_chunk.usage,
            )
        elif self.state == self.STATE_TOOL_NAME and self.tool_call:
            yield ChatCompletionChunk(
                id=last_chunk.id,
                object=last_chunk.object,
                created=last_chunk.created,
                model=last_chunk.model,
                choices=[StreamChoice(
                    index=0,
                    delta=DeltaMessage(
                        role="assistant",
                        content=self.tool_call["content"],
                    ),
                    finish_reason=last_chunk.choices[0].finish_reason,
                    tool_calls=None,
                )],
                usage=last_chunk.usage,
            )
        # 移除未定义的self.current_param相关代码
        elif self.state == self.STATE_PARAMS and self.tool_call:
            # 假设参数已处理
            try:
                params_json = self.params_buffer.strip()
                if params_json:
                    self.tool_call["arguments"] = json.loads(params_json)
            except json.JSONDecodeError:
                self.tool_call["arguments"] = {}
            yield ChatCompletionChunk(
                id=last_chunk.id,
                object=last_chunk.object,
                created=last_chunk.created,
                model=last_chunk.model,
                choices=[StreamChoice(
                    index=0,
                    delta=DeltaMessage(
                        role="assistant",
                        content=self.tool_call["content"],
                    ),
                    finish_reason=last_chunk.choices[0].finish_reason,
                    tool_calls=None,
                )],
                usage=last_chunk.usage,
            )


class ToolCallParser(ChatCompletionParser):
    """非流式工具调用解析器"""

    def __init__(
            self,
            tools: List[ToolDefinition],
            tool_call_start: str = "<tool_call>",
            tool_call_end: str = "</tool_call>",
            tool_name_start: str = "<tool_name>",
            tool_name_end: str = "</tool_name>",
            tool_params_start: str = "<tool_params>",
            tool_params_end: str = "</tool_params>",
    ):
        """初始化非流式工具调用解析器
        
        Args:
            tools: 支持的工具函数列表
            tool_call_start: 工具调用开始标签
            tool_call_end: 工具调用结束标签
            tool_name_start: 工具名称开始标签
            tool_name_end: 工具名称结束标签
            tool_params_start: 工具参数开始标签
            tool_params_end: 工具参数结束标签
        """
        super().__init__(tools)
        self.tool_call_start = tool_call_start
        self.tool_call_end = tool_call_end
        self.tool_name_start = tool_name_start
        self.tool_name_end = tool_name_end
        self.tool_params_start = tool_params_start
        self.tool_params_end = tool_params_end

    def parse(self, completion: ChatCompletion) -> ChatCompletion:
        """
        解析非流式响应中的工具调用

        Args:
            completion: ChatCompletion 响应对象

        Returns:
            带解析后工具调用的 ChatCompletion
        """
        for choice in completion.choices:
            msg: Message = choice.message

            # 如果已经有 tool_calls，直接返回
            if msg.tool_calls:
                continue

            if msg.content:
                tool_calls = self._parse_content(msg.content)
                if tool_calls:
                    msg.tool_calls = tool_calls
                    msg.content = ""
        return completion

    def _parse_content(self, text: str) -> Optional[List[ToolCall]]:
        """从 message.content 里解析工具调用"""
        calls: List[ToolCall] = []

        start = 0
        while True:
            start_idx = text.find(self.tool_call_start, start)
            if start_idx == -1:
                break
            end_idx = text.find(self.tool_call_end, start_idx)
            if end_idx == -1:
                break

            call_block = text[start_idx + len(self.tool_call_start): end_idx]

            tool_name = self._extract_between(call_block, self.tool_name_start, self.tool_name_end)
            params_str = self._extract_between(call_block, self.tool_params_start, self.tool_params_end)

            try:
                arguments = json.loads(params_str) if params_str else {}
            except json.JSONDecodeError:
                arguments = {}

            if tool_name:
                calls.append(
                    ToolCall(
                        id=uuid.uuid4().hex,
                        type="function",
                        function=ToolCallFunction(
                            name=tool_name,
                            arguments=json.dumps(arguments),
                        ),
                    )
                )
            start = end_idx + len(self.tool_call_end)

        return calls or None

    def _extract_between(self, text: str, start_tag: str, end_tag: str) -> str:
        """提取两个标签之间的内容"""
        start_idx = text.find(start_tag)
        end_idx = text.find(end_tag, start_idx + len(start_tag))
        if start_idx == -1 or end_idx == -1:
            return ""
        return text[start_idx + len(start_tag): end_idx].strip()
