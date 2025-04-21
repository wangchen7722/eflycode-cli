import unittest
from unittest.mock import MagicMock

from echoai.cli.tools.code_tool import ListCodeDefinitionsTool
from echoai.cli.tools.command_tool import ExecuteCommandTool
from echoai.cli.tools.file_tool import (
    CreateFileTool,
    EditFileTool,
    InsertFileTool,
    ListFilesTool,
    ReadFileTool,
    SearchFilesTool,
)
from echoai.core.agents.agent import Agent, AgentResponse, AgentResponseChunkType
from echoai.core.llms.llm_engine import ChatCompletionChunk, LLMEngine
from echoai.core.tools.base_tool import BaseTool


class TestAgent(unittest.TestCase):
    def setUp(self):
        self.llm_engine = MagicMock(spec=LLMEngine)
        self.agent = Agent(
            name="test_agent",
            llm_engine=self.llm_engine,
            tools=[ReadFileTool(), EditFileTool(), SearchFilesTool(), CreateFileTool(), InsertFileTool(),
                   ListFilesTool(), ListCodeDefinitionsTool(), ExecuteCommandTool()]
        )

    def test_run_normal_message(self):
        """测试普通消息处理"""
        # 模拟LLM返回结果
        mock_response = {
            "choices": [{
                "message": {"content": "测试回复"},
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        }
        self.llm_engine.generate.return_value = mock_response

        # 执行run方法
        response = self.agent.run("测试消息", stream=False)

        # 验证结果
        self.assertIsInstance(response, AgentResponse)
        self.assertEqual(response.content, "测试回复")
        self.assertEqual(response.finish_reason, "stop")
        self.assertEqual(response.usage, {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30})

    def test_run_with_tool_calls(self):
        """测试带工具调用的消息处理"""
        # 创建测试工具
        test_tool = MagicMock(spec=BaseTool)
        test_tool.NAME = "test_tool"
        self.agent._tools = [test_tool]

        # 模拟LLM返回带工具调用的结果
        mock_response = {
            "choices": [{
                "message": {
                    "content": None,
                    "tool_calls": [{
                        "id": "test_tool_call",
                        "type": "function",
                        "function": {
                            "name": "test_tool",
                            "arguments": "{\"arg\": \"value\"}"
                        }
                    }]
                },
                "finish_reason": "tool_calls"
            }],
            "usage": {"prompt_tokens": 15, "completion_tokens": 25, "total_tokens": 40}
        }
        self.llm_engine.generate.return_value = mock_response

        # 执行run方法
        response = self.agent.run("使用工具", stream=False)

        # 验证结果
        self.assertIsInstance(response, AgentResponse)
        self.assertIsNone(response.content)
        self.assertEqual(response.finish_reason, "tool_calls")
        self.assertIsNotNone(response.tool_calls)
        self.assertEqual(len(response.tool_calls), 1)
        self.assertEqual(response.tool_calls[0]["function"]["name"], "test_tool")

    def test_run_stream_mode(self):
        """测试流式输出模式"""
        # 模拟流式输出的返回结果
        mock_chunks = [
            {"choices": [{"delta": {"content": "第一"}, "finish_reason": None}]},
            {"choices": [{"delta": {"content": "部分"}, "finish_reason": None}]},
            {"choices": [{"delta": {"content": "回复"}, "finish_reason": "stop"}]}
        ]
        self.llm_engine.generate.return_value = iter(mock_chunks)

        # 执行run方法（流式模式）
        response = self.agent.run("测试消息", stream=True)
        response_content = ""
        last_chunk = None
        # 验证流式输出结果
        for chunk in response:
            if chunk.content:
                response_content += chunk.content
            last_chunk = chunk
        self.assertEqual(response_content, "第一部分回复")
        self.assertEqual(last_chunk.finish_reason, "stop")

    def test_run_stream_mode_with_tool_call_with_html(self):
        """测试流式输出模式下的HTML标签处理"""

        def stream_generator(message):
            for i in range(0, len(message), 3):
                if i >= len(message) - 3:
                    char = message[i:]
                    finish_reason = "stop"
                    usage = {
                        "prompt_tokens": 10,
                        "completion_tokens": 20,
                        "total_tokens": 30
                    }
                else:
                    char = message[i:i + 3]
                    finish_reason = None
                    usage = None
                yield ChatCompletionChunk(**{
                    "id": "123",
                    "choices": [
                        {
                            "delta": {
                                "content": char
                            },
                            "finish_reason": finish_reason,
                            "tool_calls": None
                        },
                    ],
                    "usage": usage
                })
        mock_message1 = "<edit_file><path>/path/to/file</path><old_string><!DOCTYPE html>\n<html lang=\"zh-CN\" class=\"h-full\">\n\n<head>\n    <link href=\"https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css\" rel=\"stylesheet\">\n    <link href=\"https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css\" rel=\"stylesheet\">\n    <meta charset=\"UTF-8\">\n    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n    <title>运动健康APP</title>\n    <script src=\"script.js\"></script>\n</head>\n\n<body class=\"bg-gray-100 h-full\">\n    <div class=\"container mx-auto p-4 w-[375px] h-[812px] overflow-auto\">\n        <div class=\"bg-blue-600 text-white p-4 flex justify-between items-center\">\n            <div class=\"text-xl font-bold\">运动健康APP</div>\n            <div class=\"flex space-x-4\">\n                <a href=\"home.html\" class=\"text-white hover:text-gray-200\">首页</a>\n                <a href=\"activity.html\" class=\"text-white hover:text-gray-200\">运动记录</a>\n                </old_string><new_string><a href=\"profile.html\" class=\"text-white hover:text-gray-200\">个人中心</a>\n                <a href=\"settings.html\" class=\"text-white hover:text-gray-200\">设置</a>\n            </div>\n        </div>\n        <div class=\"grid grid-cols-2 gap-4\">\n            <iframe src=\"home.html\" style=\"width: 375px; height: 812px;\" class=\"border rounded-lg shadow-md\"></iframe>\n            <iframe src=\"profile.html\" style=\"width: 375px; height: 812px;\"\n                class=\"border rounded-lg shadow-md\"></iframe>\n            <iframe src=\"activity.html\" style=\"width: 375px; height: 812px;\"\n                class=\"border rounded-lg shadow-md\"></iframe>\n            <iframe src=\"settings.html\" style=\"width: 375px; height: 812px;\"\n                class=\"border rounded-lg shadow-md\"></iframe>\n        </div>\n    </div>\n</body>\n\n</html></new_string></edit_file>"
        self.llm_engine.generate.return_value = stream_generator(mock_message1)
        # 执行run方法（流式模式）
        response = self.agent.run("测试消息", stream=True)
        response_content = ""
        for chunk in response:
            if chunk.content:
                response_content += chunk.content
        self.assertEqual(response_content, mock_message1)

    def test_run_stream_mode_with_tool_calls(self):
        """测试流式模式下的工具调用场景"""
        # 创建测试工具
        test_tool = MagicMock(spec=BaseTool)
        test_tool.name = "test_tool"
        test_tool.parameters = {
            "arg": {
                "type": "string",
                "description": "测试参数"
            }
        }
        self.agent._tools = [test_tool]

        def stream_generator(message):
            for i in range(0, len(message), 3):
                char = message[i:i + 3]
                yield ChatCompletionChunk(**{
                    "id": "123",
                    "choices": [
                        {
                            "delta": {
                                "content": char
                            },
                            "finish_reason": None,
                            "tool_calls": None
                        }
                    ]
                })

        # 场景1：单个工具调用
        mock_message1 = "<test_tool><arg>a</arg></test_tool>"
        self.llm_engine.generate.return_value = stream_generator(mock_message1)
        response = self.agent.run("使用单个工具", stream=True)
        tool_calls = []
        for chunk in response:
            print(chunk)
            if chunk.type == AgentResponseChunkType.TOOL_CALL and chunk.finish_reason == "tool_calls":
                tool_calls.extend(chunk.tool_calls)
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0]["function"]["name"], "test_tool")
        self.assertEqual(tool_calls[0]["function"]["arguments"], "{\"arg\": \"a\"}")

        # 场景2：多个工具调用
        mock_message2 = "<test_tool><arg>a</arg></test_tool><test_tool><arg>b</arg></test_tool>"
        self.llm_engine.generate.return_value = stream_generator(mock_message2)
        response = self.agent.run("使用多个工具", stream=True)
        tool_calls = []
        for chunk in response:
            if chunk.type == AgentResponseChunkType.TOOL_CALL and chunk.finish_reason == "tool_calls":
                tool_calls.extend(chunk.tool_calls)
        self.assertEqual(len(tool_calls), 2)
        self.assertEqual(tool_calls[0]["function"]["arguments"], "{\"arg\": \"a\"}")
        self.assertEqual(tool_calls[1]["function"]["arguments"], "{\"arg\": \"b\"}")

        # 场景3：工具调用与普通消息混合
        mock_message3 = "测试工具a<test_tool><arg>a</arg></test_tool>测试工具b<test_tool><arg>b</arg></test_tool>测试工具c<test_tool><arg>c</arg></test_tool>"
        self.llm_engine.generate.return_value = stream_generator(mock_message3)
        response = self.agent.run("混合场景", stream=True)
        response_content = ""
        tool_calls = []
        for chunk in response:
            if chunk.type == AgentResponseChunkType.TOOL_CALL and chunk.finish_reason == "tool_calls":
                tool_calls.extend(chunk.tool_calls)
            if chunk.content:
                response_content += chunk.content
        self.assertEqual(response_content, mock_message3)
        self.assertEqual(len(tool_calls), 3)
        self.assertEqual(tool_calls[0]["function"]["arguments"], "{\"arg\": \"a\"}")
        self.assertEqual(tool_calls[1]["function"]["arguments"], "{\"arg\": \"b\"}")
        self.assertEqual(tool_calls[2]["function"]["arguments"], "{\"arg\": \"c\"}")


if __name__ == "__main__":
    unittest.main()
