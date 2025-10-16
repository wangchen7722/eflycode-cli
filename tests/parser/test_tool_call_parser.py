import unittest
import json
from eflycode.parser.tool_call_parser import ToolCallParser
from eflycode.schema.llm import ChatCompletion, Message, Choice, Usage, ToolDefinition, ToolFunction


class TestToolCallParser(unittest.TestCase):
    """
    测试 ToolCallParser 类（非流式解析）
    """

    def setUp(self):
        """初始化解析器"""
        self.mock_tool_function = ToolDefinition(
            type="function",
            function=ToolFunction(
                name="my_tool",
                description="A test tool",
                parameters={"type": "object", "properties": {"param1": {"type": "string"}}}
            )
        )
        self.parser = ToolCallParser(tools=[self.mock_tool_function])

    def _create_completion(self, content: str, finish_reason: str = None) -> ChatCompletion:
        """辅助方法：构造一个 ChatCompletion"""
        return ChatCompletion(
            id="chatcmpl-test",
            object="chat.completion",
            created=1678886400,
            model="gpt-4",
            choices=[
                Choice(
                    index=0,
                    message=Message(role="assistant", content=content),
                    finish_reason=finish_reason,
                )
            ],
            usage=Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )

    def test_pure_text_output(self):
        """测试纯文本输出"""
        content = "这是一段纯文本内容。"
        completion = self._create_completion(content)
        parsed = self.parser.parse(completion)

        msg = parsed.choices[0].message
        self.assertEqual(msg.content, content)
        self.assertIsNone(msg.tool_calls)

    def test_single_tool_call(self):
        """测试单个工具调用"""
        tool_name = "search_tool"
        arguments = {"query": "天气"}
        content = f"<tool_call><tool_name>{tool_name}</tool_name><tool_params>{json.dumps(arguments)}</tool_params></tool_call>"

        completion = self._create_completion(content)
        parsed = self.parser.parse(completion)

        msg = parsed.choices[0].message
        self.assertEqual(msg.content, "")
        self.assertIsNotNone(msg.tool_calls)
        self.assertEqual(msg.tool_calls[0].function.name, tool_name)
        self.assertEqual(msg.tool_calls[0].function.arguments, json.dumps(arguments))

    def test_multiple_tool_calls(self):
        """测试多个工具调用"""
        tool_name1 = "tool1"
        args1 = {"a": 1}
        tool_name2 = "tool2"
        args2 = {"b": 2}
        content = (
            f"<tool_call><tool_name>{tool_name1}</tool_name><tool_params>{json.dumps(args1)}</tool_params></tool_call>"
            f"<tool_call><tool_name>{tool_name2}</tool_name><tool_params>{json.dumps(args2)}</tool_params></tool_call>"
        )

        completion = self._create_completion(content)
        parsed = self.parser.parse(completion)

        msg = parsed.choices[0].message
        self.assertEqual(msg.content, "")
        self.assertEqual(len(msg.tool_calls), 2)
        self.assertEqual(msg.tool_calls[0].function.name, tool_name1)
        self.assertEqual(msg.tool_calls[1].function.name, tool_name2)

    def test_mixed_text_then_tool(self):
        """测试文本 + 工具调用"""
        text_content = "请调用工具："
        tool_name = "toolA"
        args = {"param": "value"}
        content = (
            text_content
            + f"<tool_call><tool_name>{tool_name}</tool_name><tool_params>{json.dumps(args)}</tool_params></tool_call>"
        )

        completion = self._create_completion(content)
        parsed = self.parser.parse(completion)

        msg = parsed.choices[0].message
        # 工具调用覆盖原始内容
        self.assertEqual(msg.content, "")
        self.assertIsNotNone(msg.tool_calls)
        self.assertEqual(msg.tool_calls[0].function.name, tool_name)

    def test_mixed_tool_then_text(self):
        """测试工具调用 + 文本"""
        tool_name = "toolB"
        args = {"param": 42}
        text_content = "这是调用后的文本。"
        content = (
            f"<tool_call><tool_name>{tool_name}</tool_name><tool_params>{json.dumps(args)}</tool_params></tool_call>"
            + text_content
        )

        completion = self._create_completion(content)
        parsed = self.parser.parse(completion)

        msg = parsed.choices[0].message
        # 工具调用覆盖原始内容
        self.assertEqual(msg.content, "")
        self.assertIsNotNone(msg.tool_calls)
        self.assertEqual(msg.tool_calls[0].function.name, tool_name)

    def test_incomplete_tool_call(self):
        """测试不完整的工具调用"""
        content = "<tool_call><tool_name>bad_tool</tool_name><tool_params>{\"x\":1}"
        completion = self._create_completion(content)
        parsed = self.parser.parse(completion)

        msg = parsed.choices[0].message
        # 作为普通文本处理
        self.assertEqual(msg.content, content)
        self.assertIsNone(msg.tool_calls)

    def test_empty_content(self):
        """测试空内容"""
        completion = self._create_completion("")
        parsed = self.parser.parse(completion)

        msg = parsed.choices[0].message
        self.assertEqual(msg.content, "")
        self.assertIsNone(msg.tool_calls)

    def test_whitespace_only(self):
        """测试仅空白字符"""
        content = "   \n\t   "
        completion = self._create_completion(content)
        parsed = self.parser.parse(completion)

        msg = parsed.choices[0].message
        self.assertEqual(msg.content, content)
        self.assertIsNone(msg.tool_calls)


if __name__ == "__main__":
    unittest.main()
