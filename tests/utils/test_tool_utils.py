import unittest

from echoai.core.llms.schema import ToolCall, ToolCallFunction
from echoai.core.utils.tool_utils import (
    _apply_tool_call_template,
    apply_tool_calls_template,
)


class TestToolUtils(unittest.TestCase):
    def test_apply_tool_call_template_single(self):
        """测试单个工具调用的模板转换"""
        tool_call = ToolCall(
            id="1",
            type="function",
            function=ToolCallFunction(
                name="test_tool",
                arguments='{"arg1": "value1", "arg2": 123}'
            )
        )
        result = _apply_tool_call_template(tool_call)
        expected = '<test_tool><arg1>value1</arg1><arg2>123</arg2></test_tool>'
        self.assertEqual(result, expected)

    def test_apply_tool_call_template_empty_args(self):
        """测试空参数的工具调用"""
        tool_call = ToolCall(
            id="2",
            type="function",
            function=ToolCallFunction(
                name="empty_tool",
                arguments='{}'
            )
        )
        result = _apply_tool_call_template(tool_call)
        expected = '<empty_tool></empty_tool>'
        self.assertEqual(result, expected)

    def test_apply_tool_calls_template_multiple(self):
        """测试多个工具调用的组合"""
        tool_calls = [
            ToolCall(
                id="3",
                type="function",
                function=ToolCallFunction(
                    name="tool1",
                    arguments='{"param1": "test"}'
                )
            ),
            ToolCall(
                id="4",
                type="function",
                function=ToolCallFunction(
                    name="tool2",
                    arguments='{"param2": true}'
                )
            )
        ]
        result = apply_tool_calls_template(tool_calls)
        expected = '<tool1><param1>test</param1></tool1>\n<tool2><param2>True</param2></tool2>'
        self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()