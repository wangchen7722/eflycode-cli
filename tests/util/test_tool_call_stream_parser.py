import unittest
import json
import uuid
from typing import List, Dict, Any

from echo.parser.tool_call_parser import ToolCallStreamParser
from echo.schema.llm import ChatCompletionChunk, StreamChoice, ToolCall, ToolDefinition, Message, ToolFunction


class TestToolCallStreamParser(unittest.TestCase):
    """
    测试 ToolCallStreamParser 类
    """

    def setUp(self):
        """
        设置测试环境
        """
        self.mock_tool_function = ToolDefinition(
            type="function",
            function=ToolFunction(
                name="my_tool",
                description="A test tool",
                parameters={"type": "object", "properties": {"param1": {"type": "string"}}}
            )
        )
        self.parser = ToolCallStreamParser(tools=[self.mock_tool_function])

    def _create_chunk(self, content: str, finish_reason: str = None) -> ChatCompletionChunk:
        """
        创建一个 ChatCompletionChunk 模拟对象
        """
        return ChatCompletionChunk(
            id="chatcmpl-test",
            object="chat.completion.chunk",
            created=1678886400,
            model="gpt-4",
            choices=[StreamChoice(
                index=0,
                delta=Message(role="assistant", content=content),
                finish_reason=finish_reason,
            )],
            usage=None,
        )

    def _create_tool_call_chunk(self, tool_name: str, arguments: Dict[str, Any], finish_reason: str = None) -> ChatCompletionChunk:
        """
        创建一个包含工具调用的 ChatCompletionChunk 模拟对象
        """
        return ChatCompletionChunk(
            id="chatcmpl-test",
            object="chat.completion.chunk",
            created=1678886400,
            model="gpt-4",
            choices=[StreamChoice(
                index=0,
                delta=Message(
                    role="assistant",
                    content="",
                ),
                finish_reason="tool_calls",
                tool_calls=[
                    ToolCall(
                        id=uuid.uuid4().hex,
                        type="function",
                        function={
                            "name": tool_name,
                            "arguments": arguments,
                        },
                    )
                ],
            )],
            usage=None,
        )

    def _parse_stream(self, stream_input: List[ChatCompletionChunk]) -> List[ChatCompletionChunk]:
        """
        辅助方法：解析流内容并返回所有chunk
        """
        chunks = []
        for chunk in self.parser.parse_stream(iter(stream_input)):
            chunks.append(chunk)
        return chunks

    def test_pure_text_output(self):
        """
        测试纯文本输出
        """
        content = "这是一段纯文本内容，没有任何工具调用。"
        stream_input = [self._create_chunk(content)]
        parsed_chunks = self._parse_stream(stream_input)

        self.assertEqual(len(parsed_chunks), 1)
        self.assertIsNotNone(parsed_chunks[0].choices[0].delta.content)
        self.assertEqual(parsed_chunks[0].choices[0].delta.content, content)
        self.assertIsNone(parsed_chunks[0].choices[0].delta.tool_calls)

    def test_tool_call_only(self):
        """
        测试仅有工具调用的场景
        """
        tool_name = "my_tool"
        arguments = {"param1": "value1"}
        stream_input = [
            self._create_chunk("<tool_call>"),
            self._create_chunk(f"<tool_name>{tool_name}</tool_name>"),
            self._create_chunk(f"<tool_params>{json.dumps(arguments)}</tool_params>"),
            self._create_chunk("</tool_call>"),
        ]
        parsed_chunks = self._parse_stream(stream_input)

        self.assertEqual(len(parsed_chunks), 1)
        self.assertIsNotNone(parsed_chunks[0].choices[0].delta.tool_calls)
        self.assertEqual(parsed_chunks[0].choices[0].delta.tool_calls[0].function.name, tool_name)
        self.assertEqual(parsed_chunks[0].choices[0].delta.tool_calls[0].function.arguments, json.dumps(arguments))

    def test_mixed_content_text_then_tool(self):
        """
        测试文本后跟工具调用的混合内容
        """
        text_content = "我需要搜索一些文件。"
        tool_name = "my_tool"
        arguments = {"query": "*.py"}
        stream_input = [
            self._create_chunk(text_content),
            self._create_chunk("<tool_call>"),
            self._create_chunk(f"<tool_name>{tool_name}</tool_name>"),
            self._create_chunk(f"<tool_params>{json.dumps(arguments)}</tool_params>"),
            self._create_chunk("</tool_call>"),
        ]
        parsed_chunks = self._parse_stream(stream_input)

        self.assertEqual(len(parsed_chunks), 2)

        # 第一个chunk是文本
        self.assertIsNotNone(parsed_chunks[0].choices[0].delta.content)
        self.assertEqual(parsed_chunks[0].choices[0].delta.content, text_content)
        self.assertIsNone(parsed_chunks[0].choices[0].delta.tool_calls)

        # 第二个chunk是工具调用
        self.assertEqual(parsed_chunks[1].choices[0].delta.content, "")
        self.assertIsNotNone(parsed_chunks[1].choices[0].delta.tool_calls)
        self.assertEqual(parsed_chunks[1].choices[0].delta.tool_calls[0].function.name, tool_name)
        self.assertEqual(parsed_chunks[1].choices[0].delta.tool_calls[0].function.arguments, json.dumps(arguments))

    def test_mixed_content_tool_then_text(self):
        """
        测试工具调用后跟文本的混合内容
        """
        tool_name = "my_tool"
        arguments = {"city": "北京"}
        text_content = "根据查询结果，今天天气不错。"
        stream_input = [
            self._create_chunk("<tool_call>"),
            self._create_chunk(f"<tool_name>{tool_name}</tool_name>"),
            self._create_chunk(f"<tool_params>{json.dumps(arguments)}</tool_params>"),
            self._create_chunk("</tool_call>"),
            self._create_chunk(text_content),
        ]
        parsed_chunks = self._parse_stream(stream_input)

        self.assertEqual(len(parsed_chunks), 2)

        # 第一个chunk是工具调用
        self.assertEqual(parsed_chunks[0].choices[0].delta.content, "")
        self.assertIsNotNone(parsed_chunks[0].choices[0].delta.tool_calls)
        self.assertEqual(parsed_chunks[0].choices[0].delta.tool_calls[0].function.name, tool_name)
        self.assertEqual(parsed_chunks[0].choices[0].delta.tool_calls[0].function.arguments, json.dumps(arguments))

        # 第二个chunk是文本
        self.assertIsNotNone(parsed_chunks[1].choices[0].delta.content)
        self.assertEqual(parsed_chunks[1].choices[0].delta.content, text_content)
        self.assertIsNone(parsed_chunks[1].choices[0].delta.tool_calls)

    def test_multiple_tool_calls(self):
        """
        测试多个工具调用
        """
        tool_name1 = "tool1"
        arguments1 = {"param1": "value1"}
        tool_name2 = "tool2"
        arguments2 = {"param2": "value2"}
        stream_input = [
            self._create_chunk("<tool_call>"),
            self._create_chunk(f"<tool_name>{tool_name1}</tool_name>"),
            self._create_chunk(f"<tool_params>{json.dumps(arguments1)}</tool_params>"),
            self._create_chunk("</tool_call>"),
            self._create_chunk("<tool_call>"),
            self._create_chunk(f"<tool_name>{tool_name2}</tool_name>"),
            self._create_chunk(f"<tool_params>{json.dumps(arguments2)}</tool_params>"),
            self._create_chunk("</tool_call>"),
        ]
        parsed_chunks = self._parse_stream(stream_input)

        self.assertEqual(len(parsed_chunks), 2)

        # 第一个工具调用
        self.assertEqual(parsed_chunks[0].choices[0].delta.content, "")
        self.assertIsNotNone(parsed_chunks[0].choices[0].delta.tool_calls)
        self.assertEqual(parsed_chunks[0].choices[0].delta.tool_calls[0].function.name, tool_name1)
        self.assertEqual(parsed_chunks[0].choices[0].delta.tool_calls[0].function.arguments, json.dumps(arguments1))

        # 第二个工具调用
        self.assertEqual(parsed_chunks[1].choices[0].delta.content, "")
        self.assertIsNotNone(parsed_chunks[1].choices[0].delta.tool_calls)
        self.assertEqual(parsed_chunks[1].choices[0].delta.tool_calls[0].function.name, tool_name2)
        self.assertEqual(parsed_chunks[1].choices[0].delta.tool_calls[0].function.arguments, json.dumps(arguments2))

    def test_incomplete_tool_call(self):
        """
        测试不完整的工具调用
        """
        content = (
            "<tool_call>" +
            "<tool_name>incomplete_tool</tool_name>" +
            "<tool_params>{\"param\": \"value\"}"  # 缺少结束标签
        )
        stream_input = [self._create_chunk(content)]
        parsed_chunks = self._parse_stream(stream_input)

        # 不完整的工具调用应该作为文本处理
        self.assertEqual(len(parsed_chunks), 1)
        self.assertIsNotNone(parsed_chunks[0].choices[0].delta.content)
        self.assertEqual(parsed_chunks[0].choices[0].delta.content, content)
        self.assertIsNone(parsed_chunks[0].choices[0].delta.tool_calls)

    def test_empty_content(self):
        """
        测试空内容
        """
        stream_input = [self._create_chunk("")]
        parsed_chunks = self._parse_stream(stream_input)
        self.assertEqual(len(parsed_chunks), 0)

    def test_whitespace_only(self):
        """
        测试仅包含空白字符的内容
        """
        content = "   \n\t  \n  "
        stream_input = [self._create_chunk(content)]
        parsed_chunks = self._parse_stream(stream_input)

        self.assertEqual(len(parsed_chunks), 1)
        self.assertIsNotNone(parsed_chunks[0].choices[0].delta.content)
        self.assertEqual(parsed_chunks[0].choices[0].delta.content, content)
        self.assertIsNone(parsed_chunks[0].choices[0].delta.tool_calls)

    def test_mixed_content_text_and_tool_call(self):
        """
        测试混合文本和工具调用的流
        """
        stream_input = [
            self._create_chunk("Hello, this is some text. "),
            self._create_chunk("<tool_call><tool_name>my_tool</tool_name>"),
            self._create_chunk('<tool_params>{"param1": "value1"}</tool_params></tool_call>'),
            self._create_chunk(" And this is more text.", finish_reason="stop"),
        ]

        parsed_chunks = list(self.parser.parse_stream(iter(stream_input)))

        self.assertEqual(len(parsed_chunks), 3)

        # 验证第一个文本块
        self.assertIsNotNone(parsed_chunks[0].choices[0].delta.content)
        self.assertEqual(parsed_chunks[0].choices[0].delta.content, "Hello, this is some text. ")
        self.assertIsNone(parsed_chunks[0].choices[0].delta.tool_calls)

        # 验证工具调用块
        self.assertEqual(parsed_chunks[1].choices[0].delta.content, "")
        self.assertIsNotNone(parsed_chunks[1].choices[0].delta.tool_calls)
        self.assertEqual(len(parsed_chunks[1].choices[0].delta.tool_calls), 1)
        self.assertEqual(parsed_chunks[1].choices[0].delta.tool_calls[0].function.name, "my_tool")
        self.assertEqual(parsed_chunks[1].choices[0].delta.tool_calls[0].function.arguments, json.dumps({"param1": "value1"}))

        # 验证第二个文本块
        self.assertIsNotNone(parsed_chunks[2].choices[0].delta.content)
        self.assertEqual(parsed_chunks[2].choices[0].delta.content, " And this is more text.")
        self.assertIsNone(parsed_chunks[2].choices[0].delta.tool_calls)
        self.assertEqual(parsed_chunks[2].choices[0].finish_reason, "stop")

if __name__ == "__main__":
    unittest.main()