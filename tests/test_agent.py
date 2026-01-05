import unittest

from eflycode.core.agent.base import BaseAgent, ChatConversation, TaskConversation, TaskStatistics
from eflycode.core.agent.run_loop import AgentRunLoop
from eflycode.core.agent.session import Session
from eflycode.core.llm.protocol import (
    ChatCompletion,
    Message,
    Usage,
)
from eflycode.core.llm.providers.base import LLMProvider
from eflycode.core.tool.base import BaseTool, ToolGroup
from eflycode.core.tool.errors import ToolExecutionError


class MockProvider(LLMProvider):
    """Mock LLM Provider 用于测试"""

    def __init__(self):
        self._capabilities = None
        self._call_count = 0

    @property
    def capabilities(self):
        from eflycode.core.llm.providers.base import ProviderCapabilities
        return ProviderCapabilities(supports_streaming=True, supports_tools=True)

    def call(self, request):
        self._call_count += 1
        return ChatCompletion(
            id=f"chatcmpl-{self._call_count}",
            object="chat.completion",
            created=1234567890,
            model="gpt-4",
            message=Message(role="assistant", content=f"Response {self._call_count}"),
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

    def stream(self, request):
        from eflycode.core.llm.protocol import ChatCompletionChunk, DeltaMessage, Usage, DeltaToolCall, DeltaToolCallFunction
        # 根据 request 中的消息推断期望的响应内容
        content = "chunk"  # 默认内容
        if request.messages:
            last_user_msg = None
            for msg in reversed(request.messages):
                if msg.role == "user":
                    last_user_msg = msg.content
                    break
            if last_user_msg == "Hello":
                content = "Done"
            elif last_user_msg == "Use tool":
                # 第一次调用返回工具调用
                if self._call_count == 1:
                    yield ChatCompletionChunk(
                        id=f"chatcmpl-{self._call_count}",
                        object="chat.completion.chunk",
                        created=1234567890,
                        model="gpt-4",
                        delta=DeltaMessage(
                            tool_calls=[
                                DeltaToolCall(
                                    index=0,
                                    id="call_1",
                                    type="function",
                                    function=DeltaToolCallFunction(name="test_tool", arguments="{}")
                                )
                            ]
                        ),
                        finish_reason="tool_calls",
                    )
                    return
                else:
                    content = "Task completed"
            elif last_user_msg and "Test" in last_user_msg:
                # 对于工具调用场景，第一次返回工具调用，后续返回完成消息
                if self._call_count <= 3:
                    # 返回工具调用
                    yield ChatCompletionChunk(
                        id=f"chatcmpl-{self._call_count}",
                        object="chat.completion.chunk",
                        created=1234567890,
                        model="gpt-4",
                        delta=DeltaMessage(
                            tool_calls=[
                                DeltaToolCall(
                                    index=0,
                                    id=f"call_{self._call_count}",
                                    type="function",
                                    function=DeltaToolCallFunction(name="test_tool", arguments="{}")
                                )
                            ]
                        ),
                        finish_reason="tool_calls",
                    )
                    return
                else:
                    content = f"Response {self._call_count}"
            elif last_user_msg and "工具" in last_user_msg:
                # 工具执行后的响应
                content = f"Response {self._call_count}"
        
        # 将内容分块返回
        for i, char in enumerate(content):
            yield ChatCompletionChunk(
                id=f"chatcmpl-{self._call_count}",
                object="chat.completion.chunk",
                created=1234567890,
                model="gpt-4",
                delta=DeltaMessage(content=char),
                finish_reason="stop" if i == len(content) - 1 else None,
                usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15) if i == len(content) - 1 else None,
            )


class MockTool(BaseTool):
    """Mock 工具用于测试"""

    def __init__(self, name: str = "mock_tool", result: str = "success"):
        self._name = name
        self._result = result
        from eflycode.core.llm.protocol import ToolFunctionParameters
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
        return self._result


class TestSession(unittest.TestCase):
    """Session 测试类"""

    def setUp(self):
        """设置测试环境"""
        self.session = Session()

    def test_add_message(self):
        """测试添加消息"""
        self.session.add_message("user", "Hello")
        self.session.add_message("assistant", "Hi")

        messages = self.session.get_messages()
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].role, "user")
        self.assertEqual(messages[0].content, "Hello")
        self.assertEqual(messages[1].role, "assistant")
        self.assertEqual(messages[1].content, "Hi")

    def test_clear(self):
        """测试清空会话"""
        self.session.add_message("user", "Hello")
        self.session.clear()

        messages = self.session.get_messages()
        self.assertEqual(len(messages), 0)

    def test_get_context(self):
        """测试获取上下文"""
        self.session.add_message("user", "Hello")
        self.session.add_message("assistant", "Hi")

        context = self.session.get_context("gpt-4")
        self.assertEqual(context.model, "gpt-4")
        self.assertEqual(len(context.messages), 2)


class TestBaseAgent(unittest.TestCase):
    """BaseAgent 测试类"""

    def setUp(self):
        """设置测试环境"""
        self.provider = MockProvider()
        self.agent = BaseAgent(provider=self.provider, model="gpt-4")

    def tearDown(self):
        """清理测试环境"""
        self.agent.shutdown()

    def test_init(self):
        """测试初始化"""
        self.assertIsNotNone(self.agent.provider)
        self.assertIsNotNone(self.agent.event_bus)
        self.assertIsNotNone(self.agent.session)
        self.assertEqual(self.agent.model_name, "gpt-4")

    def test_init_with_tools(self):
        """测试带工具的初始化"""
        tool1 = MockTool("tool1")
        tool2 = MockTool("tool2")
        agent = BaseAgent(provider=self.provider, tools=[tool1, tool2], model="gpt-4")

        tools = agent.get_available_tools()
        self.assertEqual(len(tools), 2)
        agent.shutdown()

    def test_init_with_tool_groups(self):
        """测试带工具组的初始化"""
        tool1 = MockTool("tool1")
        tool2 = MockTool("tool2")
        group = ToolGroup("test_group", "Test group", [tool1, tool2])
        agent = BaseAgent(provider=self.provider, tool_groups=[group], model="gpt-4")

        tools = agent.get_available_tools()
        self.assertEqual(len(tools), 2)
        self.assertIsNotNone(agent.get_tool("tool1"))
        self.assertIsNotNone(agent.get_tool("tool2"))
        agent.shutdown()

    def test_chat(self):
        """测试聊天功能"""
        conversation = self.agent.chat("Hello")

        self.assertIsInstance(conversation, ChatConversation)
        self.assertIn("Response", conversation.content)
        self.assertEqual(len(conversation.messages), 2)

    def test_chat_with_tool_calls(self):
        """测试带工具调用的聊天"""
        tool = MockTool("test_tool")
        self.agent.add_tool(tool)

        provider = MockProvider()
        provider._call_count = 0

        def mock_call(request):
            provider._call_count += 1
            if provider._call_count == 1:
                from eflycode.core.llm.protocol import ToolCall, ToolCallFunction
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
            else:
                return ChatCompletion(
                    id="chatcmpl-2",
                    object="chat.completion",
                    created=1234567890,
                    model="gpt-4",
                    message=Message(role="assistant", content="Done"),
                )

        provider.call = mock_call
        agent = BaseAgent(provider=provider, tools=[tool], model="gpt-4")

        conversation = agent.chat("Use tool")
        agent.shutdown()

        self.assertIsInstance(conversation, ChatConversation)

    def test_add_tool(self):
        """测试添加工具"""
        tool = MockTool("new_tool")
        self.agent.add_tool(tool)

        self.assertIsNotNone(self.agent.get_tool("new_tool"))
        tools = self.agent.get_available_tools()
        self.assertEqual(len(tools), 1)

    def test_remove_tool(self):
        """测试移除工具"""
        tool = MockTool("temp_tool")
        self.agent.add_tool(tool)

        self.assertTrue(self.agent.remove_tool("temp_tool"))
        self.assertIsNone(self.agent.get_tool("temp_tool"))

    def test_run_tool(self):
        """测试执行工具"""
        tool = MockTool("test_tool", result="tool_result")
        self.agent.add_tool(tool)

        result = self.agent.run_tool("test_tool")
        self.assertEqual(result, "tool_result")

    def test_run_tool_nonexistent(self):
        """测试执行不存在的工具"""
        with self.assertRaises(ToolExecutionError):
            self.agent.run_tool("nonexistent_tool")

    def test_add_tool_group(self):
        """测试添加工具组"""
        tool1 = MockTool("tool1")
        tool2 = MockTool("tool2")
        group = ToolGroup("group1", "Group 1", [tool1, tool2])

        self.agent.add_tool_group(group)

        self.assertIsNotNone(self.agent.get_tool("tool1"))
        self.assertIsNotNone(self.agent.get_tool("tool2"))

    def test_remove_tool_group(self):
        """测试移除工具组"""
        tool1 = MockTool("tool1")
        tool2 = MockTool("tool2")
        group = ToolGroup("group1", "Group 1", [tool1, tool2])

        self.agent.add_tool_group(group)
        self.assertTrue(self.agent.remove_tool_group("group1"))

        self.assertIsNone(self.agent.get_tool("tool1"))
        self.assertIsNone(self.agent.get_tool("tool2"))


class TestAgentRunLoop(unittest.TestCase):
    """AgentRunLoop 测试类"""

    def setUp(self):
        """设置测试环境"""
        self.provider = MockProvider()
        self.agent = BaseAgent(provider=self.provider, model="gpt-4")

    def tearDown(self):
        """清理测试环境"""
        self.agent.shutdown()

    def test_run_simple(self):
        """测试简单运行"""
        provider = MockProvider()
        provider._call_count = 0

        def mock_call(request):
            provider._call_count += 1
            return ChatCompletion(
                id=f"chatcmpl-{provider._call_count}",
                object="chat.completion",
                created=1234567890,
                model="gpt-4",
                message=Message(role="assistant", content="Done"),
                usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            )

        provider.call = mock_call
        agent = BaseAgent(provider=provider, model="gpt-4")
        run_loop = AgentRunLoop(agent)

        result = run_loop.run("Hello")
        agent.shutdown()

        self.assertIsInstance(result, TaskConversation)
        self.assertEqual(result.content, "Done")
        self.assertEqual(result.statistics.iterations, 1)
        self.assertEqual(result.statistics.total_tokens, 15)

    def test_run_with_tool_call(self):
        """测试带工具调用的运行"""
        tool = MockTool("test_tool", result="tool_result")
        provider = MockProvider()
        provider._call_count = 0

        def mock_call(request):
            provider._call_count += 1
            if provider._call_count == 1:
                from eflycode.core.llm.protocol import ToolCall, ToolCallFunction
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

        provider.call = mock_call
        agent = BaseAgent(provider=provider, tools=[tool], model="gpt-4")
        run_loop = AgentRunLoop(agent)

        result = run_loop.run("Use tool", stream=False)
        agent.shutdown()

        self.assertIsInstance(result, TaskConversation)
        self.assertEqual(result.content, "Task completed")
        self.assertEqual(result.statistics.iterations, 2)
        self.assertEqual(result.statistics.tool_calls_count, 1)
        self.assertEqual(result.statistics.total_tokens, 30)

    def test_run_max_iterations(self):
        """测试达到最大迭代次数"""
        provider = MockProvider()
        provider._call_count = 0

        def mock_call(request):
            provider._call_count += 1
            from eflycode.core.llm.protocol import ToolCall, ToolCallFunction
            return ChatCompletion(
                id=f"chatcmpl-{provider._call_count}",
                object="chat.completion",
                created=1234567890,
                model="gpt-4",
                message=Message(
                    role="assistant",
                    content=None,
                    tool_calls=[
                        ToolCall(
                            id=f"call_{provider._call_count}",
                            function=ToolCallFunction(name="test_tool", arguments="{}"),
                        )
                    ],
                ),
                usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            )

        provider.call = mock_call
        tool = MockTool("test_tool")
        agent = BaseAgent(provider=provider, tools=[tool], model="gpt-4")
        run_loop = AgentRunLoop(agent)
        run_loop.max_iterations = 3

        result = run_loop.run("Test")
        agent.shutdown()

        self.assertIsInstance(result, TaskConversation)
        self.assertEqual(result.statistics.iterations, 3)


class TestTaskStatistics(unittest.TestCase):
    """TaskStatistics 测试类"""

    def test_init(self):
        """测试初始化"""
        stats = TaskStatistics()
        self.assertEqual(stats.total_tokens, 0)
        self.assertEqual(stats.prompt_tokens, 0)
        self.assertEqual(stats.completion_tokens, 0)
        self.assertEqual(stats.iterations, 0)
        self.assertEqual(stats.tool_calls_count, 0)

    def test_add_usage(self):
        """测试添加使用量"""
        stats = TaskStatistics()
        usage = Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15)

        stats.add_usage(usage)

        self.assertEqual(stats.prompt_tokens, 10)
        self.assertEqual(stats.completion_tokens, 5)
        self.assertEqual(stats.total_tokens, 15)

    def test_add_multiple_usage(self):
        """测试添加多个使用量"""
        stats = TaskStatistics()
        usage1 = Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        usage2 = Usage(prompt_tokens=20, completion_tokens=10, total_tokens=30)

        stats.add_usage(usage1)
        stats.add_usage(usage2)

        self.assertEqual(stats.prompt_tokens, 30)
        self.assertEqual(stats.completion_tokens, 15)
        self.assertEqual(stats.total_tokens, 45)


class TestChatConversation(unittest.TestCase):
    """ChatConversation 测试类"""

    def test_init(self):
        """测试初始化"""
        completion = ChatCompletion(
            id="chatcmpl-1",
            object="chat.completion",
            created=1234567890,
            model="gpt-4",
            message=Message(role="assistant", content="Hello"),
        )
        messages = [Message(role="user", content="Hi"), Message(role="assistant", content="Hello")]

        conversation = ChatConversation(completion=completion, messages=messages)

        self.assertEqual(conversation.content, "Hello")
        self.assertEqual(len(conversation.messages), 2)


class TestTaskConversation(unittest.TestCase):
    """TaskConversation 测试类"""

    def test_init(self):
        """测试初始化"""
        completion = ChatCompletion(
            id="chatcmpl-1",
            object="chat.completion",
            created=1234567890,
            model="gpt-4",
            message=Message(role="assistant", content="Done"),
        )
        messages = [Message(role="user", content="Task"), Message(role="assistant", content="Done")]
        chat_conv = ChatConversation(completion=completion, messages=messages)
        stats = TaskStatistics(total_tokens=100, iterations=5, tool_calls_count=2)

        task_conv = TaskConversation(conversation=chat_conv, statistics=stats)

        self.assertEqual(task_conv.content, "Done")
        self.assertEqual(len(task_conv.messages), 2)
        self.assertEqual(task_conv.statistics.total_tokens, 100)
        self.assertEqual(task_conv.statistics.iterations, 5)
        self.assertEqual(task_conv.statistics.tool_calls_count, 2)


if __name__ == "__main__":
    unittest.main()

