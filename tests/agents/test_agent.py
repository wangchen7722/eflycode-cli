import unittest
from unittest.mock import MagicMock, patch
from echo.agents.agent import Agent, AgentResponse, AgentCapability
from echo.llms.llm_engine import LLMEngine
from echo.tools import BaseTool


class TestAgent(unittest.TestCase):
    def setUp(self):
        self.llm_engine = MagicMock(spec=LLMEngine)
        self.agent = Agent(
            name="test_agent",
            llm_engine=self.llm_engine,
            capabilities=[AgentCapability.USE_TOOL],
            tools=[]
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

        # 验证流式输出结果
        for chunk in response.stream():
            ...
        content = response.content
        self.assertEqual(content, "第一部分回复")
        self.assertEqual(response.content, "第一部分回复")
        self.assertEqual(response.finish_reason, "stop")

    def test_run_stream_mode_with_tool_calls(self):
        """测试流式模式下的工具调用场景"""
        from echo.llms import ChatCompletionChunk
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
        for chunk in response.stream():
            ...
        tool_calls = response.tool_calls
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0]["function"]["name"], "test_tool")
        self.assertEqual(tool_calls[0]["function"]["arguments"], "{\"arg\": \"a\"}")

        # 场景2：多个工具调用
        mock_message2 = "<test_tool><arg>a</arg></test_tool><test_tool><arg>b</arg></test_tool>"
        self.llm_engine.generate.return_value = stream_generator(mock_message2)
        response = self.agent.run("使用多个工具", stream=True)
        for chunk in response.stream():
            ...
        tool_calls = response.tool_calls
        self.assertEqual(len(tool_calls), 2)
        self.assertEqual(tool_calls[0]["function"]["arguments"], "{\"arg\": \"a\"}")
        self.assertEqual(tool_calls[1]["function"]["arguments"], "{\"arg\": \"b\"}")

        # 场景3：工具调用与普通消息混合
        mock_message3 = "测试工具a<test_tool><arg>a</arg></test_tool>测试工具b<test_tool><arg>b</arg></test_tool>测试工具c<test_tool><arg>c</arg></test_tool>"
        self.llm_engine.generate.return_value = stream_generator(mock_message3)
        response = self.agent.run("混合场景", stream=True)
        for chunk in response.stream():
            ...
        content = response.content
        tool_calls = response.tool_calls
        self.assertEqual(content, mock_message3)
        self.assertEqual(len(tool_calls), 3)
        self.assertEqual(tool_calls[0]["function"]["arguments"], "{\"arg\": \"a\"}")
        self.assertEqual(tool_calls[1]["function"]["arguments"], "{\"arg\": \"b\"}")
        self.assertEqual(tool_calls[2]["function"]["arguments"], "{\"arg\": \"c\"}")


if __name__ == "__main__":
    unittest.main()
