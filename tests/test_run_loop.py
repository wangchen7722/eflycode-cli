"""AgentRunLoop 测试用例"""

import unittest

from eflycode.core.agent.base import BaseAgent, TaskConversation
from eflycode.core.agent.run_loop import AgentRunLoop
from eflycode.core.llm.protocol import (
    ChatCompletion,
    ChatCompletionChunk,
    DeltaMessage,
    Message,
    ToolCall,
    ToolCallFunction,
    Usage,
    ToolFunctionParameters,
        DeltaToolCall,
    DeltaToolCallFunction,
)
from eflycode.core.llm.providers.base import LLMProvider, ProviderCapabilities
from eflycode.core.tool.base import BaseTool


class MockStreamProvider(LLMProvider):
    """支持流式的 Mock Provider"""

    def __init__(self, responses=None):
        self._capabilities = ProviderCapabilities(supports_streaming=True, supports_tools=True)
        self._call_count = 0
        self._stream_count = 0
        self._responses = responses or []

    @property
    def capabilities(self):
        return self._capabilities

    def call(self, request):
        self._call_count += 1
        if self._responses:
            return self._responses.pop(0)
        return ChatCompletion(
            id=f"chatcmpl-{self._call_count}",
            object="chat.completion",
            created=1234567890,
            model="gpt-4",
            message=Message(role="assistant", content=f"Response {self._call_count}"),
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

    def stream(self, request):
        self._stream_count += 1
        if self._responses:
            response = self._responses.pop(0)
            if isinstance(response, ChatCompletion):
                # 将 ChatCompletion 转换为流式 chunks
                content = response.message.content or ""
                for i, char in enumerate(content):
                    yield ChatCompletionChunk(
                        id=response.id,
                        object="chat.completion.chunk",
                        created=response.created,
                        model=response.model,
                        delta=DeltaMessage(content=char),
                        finish_reason=None if i < len(content) - 1 else response.finish_reason,
                        usage=response.usage if i == len(content) - 1 else None,
                    )
            else:
                # 直接 yield chunks
                for chunk in response:
                    yield chunk
        else:
            yield ChatCompletionChunk(
                id="chatcmpl-1",
                object="chat.completion.chunk",
                created=1234567890,
                model="gpt-4",
                delta=DeltaMessage(content="chunk"),
            )


class MockTool(BaseTool):
    """Mock 工具"""

    def __init__(self, name: str = "mock_tool", result: str = "success", raise_error=False):
        self._name = name
        self._result = result
        self._raise_error = raise_error
        self._parameters = ToolFunctionParameters(properties={})

    @property
    def name(self) -> str:
        return self._name

    @property
    def type(self) -> str:
        return "function"

    @property
    def permission(self) -> str:
        return "read"

    @property
    def description(self) -> str:
        return "Mock tool for testing"

    @property
    def parameters(self):
        return self._parameters

    def do_run(self, **kwargs) -> str:
        if self._raise_error:
            raise Exception("Tool execution failed")
        return self._result


class TestAgentRunLoopDetailed(unittest.TestCase):
    """AgentRunLoop 详细测试"""

    def setUp(self):
        """设置测试环境"""
        self.provider = MockStreamProvider()
        self.agent = BaseAgent(provider=self.provider, model="gpt-4")
        self.run_loop = AgentRunLoop(self.agent)

    def tearDown(self):
        """清理测试环境"""
        self.agent.shutdown()

    def test_run_streaming_mode(self):
        """测试流式模式运行"""
        # 设置流式响应
        self.provider._responses = [
            ChatCompletion(
                id="chatcmpl-1",
                object="chat.completion",
                created=1234567890,
                model="gpt-4",
                message=Message(role="assistant", content="Hello World"),
                usage=Usage(prompt_tokens=10, completion_tokens=2, total_tokens=12),
            )
        ]

        result = self.run_loop.run("Hello", stream=True)

        self.assertIsInstance(result, TaskConversation)
        self.assertEqual(result.content, "Hello World")
        self.assertEqual(self.provider._stream_count, 1)
        self.assertEqual(self.provider._call_count, 0)

    def test_run_non_streaming_mode(self):
        """测试非流式模式运行"""
        result = self.run_loop.run("Hello", stream=False)

        self.assertIsInstance(result, TaskConversation)
        self.assertEqual(self.provider._call_count, 1)
        self.assertEqual(self.provider._stream_count, 0)

    def test_run_with_tool_call_streaming(self):
        """测试流式模式下的工具调用"""
        tool = MockTool("test_tool", result="tool_result")
        self.agent.add_tool(tool)

        # 第一次响应：工具调用
        tool_call_chunk = ChatCompletionChunk(
            id="chatcmpl-1",
            object="chat.completion.chunk",
            created=1234567890,
            model="gpt-4",
            delta=DeltaMessage(
                content=None,
                tool_calls=[
                    DeltaToolCall(
                        index=0,
                        id="call_1",
                        type="function",
                        function=DeltaToolCallFunction(name="test_tool", arguments="{}"),
                    )
                ],
            ),
            finish_reason="tool_calls",
        )

        # 第二次响应：最终结果
        final_response = ChatCompletion(
            id="chatcmpl-2",
            object="chat.completion",
            created=1234567890,
            model="gpt-4",
            message=Message(role="assistant", content="Task completed"),
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

        def mock_stream(request):
            yield tool_call_chunk
            # 模拟第二次调用
            content = final_response.message.content or ""
            for char in content:
                yield ChatCompletionChunk(
                    id=final_response.id,
                    object="chat.completion.chunk",
                    created=final_response.created,
                    model=final_response.model,
                    delta=DeltaMessage(content=char),
                    finish_reason=None if char != content[-1] else final_response.finish_reason,
                    usage=final_response.usage if char == content[-1] else None,
                )

        self.provider.stream = mock_stream

        # 监听事件
        events = []
        def event_handler(**kwargs):
            events.append(kwargs)

        self.agent.event_bus.subscribe("agent.tool.call", event_handler)
        self.agent.event_bus.subscribe("agent.tool.result", event_handler)

        self.run_loop.run("Use tool", stream=True)

        # 验证工具调用事件被触发
        tool_call_events = [e for e in events if "tool_name" in e]
        self.assertGreater(len(tool_call_events), 0, "工具调用事件应该被触发")

    def test_run_with_tool_call_non_streaming(self):
        """测试非流式模式下的工具调用"""
        tool = MockTool("test_tool", result="tool_result")
        self.agent.add_tool(tool)

        call_count = [0]

        def mock_call(request):
            call_count[0] += 1
            if call_count[0] == 1:
                return ChatCompletion(
                    id="chatcmpl-1",
                    object="chat.completion",
                    created=1234567890,
                    model="gpt-4",
                    message=Message(
                        role="assistant",
                        content=None,
                        tool_calls=[
                            ToolCall(
                                id="call_1",
                                function=ToolCallFunction(name="test_tool", arguments="{}"),
                            )
                        ],
                    ),
                    usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
                )
            else:
                return ChatCompletion(
                    id="chatcmpl-2",
                    object="chat.completion",
                    created=1234567890,
                    model="gpt-4",
                    message=Message(role="assistant", content="Task completed"),
                    usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
                )

        self.provider.call = mock_call

        # 监听事件
        events = []
        def event_handler(**kwargs):
            events.append(kwargs)

        self.agent.event_bus.subscribe("agent.tool.call", event_handler)
        self.agent.event_bus.subscribe("agent.tool.result", event_handler)

        result = self.run_loop.run("Use tool", stream=False)

        # 验证工具调用事件被触发
        tool_call_events = [e for e in events if "tool_name" in e and e.get("tool_name") == "test_tool"]
        self.assertGreater(len(tool_call_events), 0, "工具调用事件应该被触发")
        self.assertEqual(result.content, "Task completed")
        self.assertEqual(result.statistics.iterations, 2)
        self.assertEqual(result.statistics.tool_calls_count, 1)

    def test_run_with_multiple_tool_calls(self):
        """测试多次工具调用"""
        tool1 = MockTool("tool1", result="result1")
        tool2 = MockTool("tool2", result="result2")
        self.agent.add_tool(tool1)
        self.agent.add_tool(tool2)

        call_count = [0]

        def mock_call(request):
            call_count[0] += 1
            if call_count[0] == 1:
                return ChatCompletion(
                    id="chatcmpl-1",
                    object="chat.completion",
                    created=1234567890,
                    model="gpt-4",
                    message=Message(
                        role="assistant",
                        content=None,
                        tool_calls=[
                            ToolCall(
                                id="call_1",
                                function=ToolCallFunction(name="tool1", arguments="{}"),
                            )
                        ],
                    ),
                )
            elif call_count[0] == 2:
                return ChatCompletion(
                    id="chatcmpl-2",
                    object="chat.completion",
                    created=1234567890,
                    model="gpt-4",
                    message=Message(
                        role="assistant",
                        content=None,
                        tool_calls=[
                            ToolCall(
                                id="call_2",
                                function=ToolCallFunction(name="tool2", arguments="{}"),
                            )
                        ],
                    ),
                )
            else:
                return ChatCompletion(
                    id="chatcmpl-3",
                    object="chat.completion",
                    created=1234567890,
                    model="gpt-4",
                    message=Message(role="assistant", content="All done"),
                )

        self.provider.call = mock_call

        result = self.run_loop.run("Use tools", stream=False)

        self.assertEqual(result.statistics.iterations, 3)
        self.assertEqual(result.statistics.tool_calls_count, 2)

    def test_run_tool_execution_error(self):
        """测试工具执行错误"""
        tool = MockTool("test_tool", raise_error=True)
        self.agent.add_tool(tool)

        def mock_call(request):
            return ChatCompletion(
                id="chatcmpl-1",
                object="chat.completion",
                created=1234567890,
                model="gpt-4",
                message=Message(
                    role="assistant",
                    content=None,
                    tool_calls=[
                        ToolCall(
                            id="call_1",
                            function=ToolCallFunction(name="test_tool", arguments="{}"),
                        )
                    ],
                ),
            )

        self.provider.call = mock_call

        # 监听错误事件
        error_events = []
        def error_handler(**kwargs):
            error_events.append(kwargs)

        self.agent.event_bus.subscribe("agent.error", error_handler)
        self.agent.event_bus.subscribe("agent.tool.error", error_handler)

        # 工具执行错误会被捕获并继续，不会抛出异常
        result = self.run_loop.run("Use tool", stream=False)

        # 验证错误事件被触发
        self.assertGreater(len(error_events), 0, "错误事件应该被触发")
        # 验证任务正常完成
        self.assertIsNotNone(result)

    def test_run_max_iterations(self):
        """测试达到最大迭代次数"""
        tool = MockTool("test_tool")
        self.agent.add_tool(tool)

        def mock_call(request):
            return ChatCompletion(
                id="chatcmpl-1",
                object="chat.completion",
                created=1234567890,
                model="gpt-4",
                message=Message(
                    role="assistant",
                    content=None,
                    tool_calls=[
                        ToolCall(
                            id="call_1",
                            function=ToolCallFunction(name="test_tool", arguments="{}"),
                        )
                    ],
                ),
            )

        self.provider.call = mock_call
        self.run_loop.max_iterations = 3

        result = self.run_loop.run("Test", stream=False)

        self.assertEqual(result.statistics.iterations, 3)
        # 验证达到最大迭代次数
        self.assertIsNotNone(result)
        self.assertEqual(result.statistics.iterations, 3)

    def test_parse_tool_call_from_tool_calls(self):
        """测试从 tool_calls 解析工具调用"""
        completion = ChatCompletion(
            id="chatcmpl-1",
            object="chat.completion",
            created=1234567890,
            model="gpt-4",
            message=Message(
                role="assistant",
                content=None,
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        function=ToolCallFunction(name="test_tool", arguments='{"arg1": "value1"}'),
                    )
                ],
            ),
        )

        tool_call = self.run_loop._parse_tool_call(completion)

        self.assertIsNotNone(tool_call)
        self.assertEqual(tool_call["name"], "test_tool")
        self.assertEqual(tool_call["arguments"]["arg1"], "value1")


    def test_parse_tool_call_none(self):
        """测试解析不到工具调用"""
        completion = ChatCompletion(
            id="chatcmpl-1",
            object="chat.completion",
            created=1234567890,
            model="gpt-4",
            message=Message(role="assistant", content="Just a message"),
        )

        tool_call = self.run_loop._parse_tool_call(completion)

        self.assertIsNone(tool_call)

    def test_execute_tool(self):
        """测试执行工具"""
        tool = MockTool("test_tool", result="tool_result")
        self.agent.add_tool(tool)

        result = self.run_loop._execute_tool("test_tool", {})

        self.assertEqual(result, "tool_result")

    def test_event_emission_task_start_stop(self):
        """测试任务开始和结束事件"""
        events = []

        def start_handler(**kw):
            events.append("task.start")
        def stop_handler(**kw):
            events.append("task.stop")

        self.agent.event_bus.subscribe("agent.task.start", start_handler)
        self.agent.event_bus.subscribe("agent.task.stop", stop_handler)

        # 确保 mock provider 返回一个没有工具调用的响应，这样任务会正常结束
        original_call = self.provider.call
        def mock_call(request):
            msg = Message(role="assistant", content="Hello response")
            return ChatCompletion(
                id="chatcmpl-1",
                object="chat.completion",
                created=1234567890,
                model="gpt-4",
                message=msg,
                usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            )
        self.provider.call = mock_call

        # 确保 run_loop 使用非流式模式
        original_capabilities = self.provider._capabilities
        self.provider._capabilities = ProviderCapabilities(supports_streaming=False, supports_tools=True)
        
        # 同时 mock stream 方法，确保即使被调用也不会影响测试
        original_stream = self.provider.stream
        def mock_stream(request):
            from eflycode.core.llm.protocol import ChatCompletionChunk, DeltaMessage
            yield ChatCompletionChunk(
                id="chatcmpl-1",
                object="chat.completion.chunk",
                created=1234567890,
                model="gpt-4",
                delta=DeltaMessage(content="Hello"),
                finish_reason=None,
                usage=None,
            )
        self.provider.stream = mock_stream
        
        try:
            result = self.run_loop.run("Hello", stream=False)

            # 等待事件处理完成（EventBus 是异步的）
            import time
            max_wait = 1.0
            wait_time = 0.0
            while "task.stop" not in events and wait_time < max_wait:
                time.sleep(0.01)
                wait_time += 0.01

            self.assertIn("task.start", events)
            # task.stop 会在消息完成后触发
            self.assertIn("task.stop", events, f"事件列表: {events}, result: {result}")
            # 验证任务正常完成
            self.assertIsNotNone(result)
        finally:
            self.provider._capabilities = original_capabilities
            self.provider.stream = original_stream
            self.provider.call = original_call

    def test_statistics_accumulation(self):
        """测试统计信息累积"""
        usage1 = Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        usage2 = Usage(prompt_tokens=20, completion_tokens=10, total_tokens=30)

        def mock_call(request):
            self.provider._call_count += 1
            return ChatCompletion(
                id=f"chatcmpl-{self.provider._call_count}",
                object="chat.completion",
                created=1234567890,
                model="gpt-4",
                message=Message(role="assistant", content="Done"),
                usage=usage1 if self.provider._call_count == 1 else usage2,
            )

        self.provider.call = mock_call

        result = self.run_loop.run("Hello", stream=False)

        # 验证统计信息被正确记录
        self.assertEqual(result.statistics.total_tokens, 15)


if __name__ == "__main__":
    unittest.main()

