import json
import unittest
from unittest.mock import MagicMock, patch

from eflycode.core.llm.advisors.finish_task_advisor import FinishTaskAdvisor, _StreamState
from eflycode.core.llm.protocol import (
    ChatCompletion,
    ChatCompletionChunk,
    DeltaMessage,
    DeltaToolCall,
    DeltaToolCallFunction,
    LLMRequest,
    Message,
    ToolCall,
    ToolCallFunction,
    Usage,
)


class TestFinishTaskAdvisor(unittest.TestCase):
    """FinishTaskAdvisor 测试类"""

    def setUp(self):
        """设置测试环境"""
        self.advisor = FinishTaskAdvisor()
        self.request = LLMRequest(
            model="gpt-4",
            messages=[
                Message(role="user", content="Hello, world!"),
            ],
        )

    def test_init(self):
        """测试初始化"""
        advisor = FinishTaskAdvisor()
        self.assertIsNotNone(advisor._finish_task_tool)
        self.assertEqual(advisor._finish_task_tool.name, "finish_task")
        self.assertEqual(len(advisor._stream_states), 0)

    def test_before_call_injects_finish_task_tool(self):
        """测试 before_call 注入 finish_task 工具"""
        request = LLMRequest(
            model="gpt-4",
            messages=[Message(role="user", content="test")],
            tools=None,
        )

        result = self.advisor.before_call(request)

        self.assertIsNotNone(result.tools)
        self.assertEqual(len(result.tools), 1)
        self.assertEqual(result.tools[0].function.name, "finish_task")

    def test_before_call_with_existing_tools(self):
        """测试 before_call 在已有工具列表中添加 finish_task"""
        from eflycode.core.llm.protocol import ToolDefinition, ToolFunction

        existing_tool = ToolDefinition(
            type="function",
            function=ToolFunction(
                name="other_tool",
                description="Another tool",
                parameters={"type": "object", "properties": {}},
            ),
        )

        request = LLMRequest(
            model="gpt-4",
            messages=[Message(role="user", content="test")],
            tools=[existing_tool],
        )

        result = self.advisor.before_call(request)

        self.assertEqual(len(result.tools), 2)
        tool_names = [tool.function.name for tool in result.tools]
        self.assertIn("finish_task", tool_names)
        self.assertIn("other_tool", tool_names)

    def test_before_call_does_not_duplicate_finish_task(self):
        """测试 before_call 不会重复添加 finish_task 工具"""
        request = self.advisor.before_call(self.request)
        result = self.advisor.before_call(request)

        finish_task_count = sum(
            1 for tool in result.tools if tool.function.name == "finish_task"
        )
        self.assertEqual(finish_task_count, 1)

    def test_before_stream_initializes_state(self):
        """测试 before_stream 初始化流式状态"""
        request_id = self.advisor._get_request_id(self.request)
        self.assertNotIn(request_id, self.advisor._stream_states)

        result = self.advisor.before_stream(self.request)

        self.assertIn(request_id, self.advisor._stream_states)
        self.assertIsNotNone(result.tools)
        self.assertEqual(len(result.tools), 1)
        self.assertEqual(result.tools[0].function.name, "finish_task")

    def test_after_call_converts_finish_task_tool_call(self):
        """测试 after_call 转换 finish_task 工具调用为普通消息"""
        content = "这是最终回答"
        tool_call = ToolCall(
            id="call_123",
            type="function",
            function=ToolCallFunction(
                name="finish_task",
                arguments=json.dumps({"content": content}),
            ),
        )

        response = ChatCompletion(
            id="chatcmpl-123",
            object="chat.completion",
            created=1234567890,
            model="gpt-4",
            message=Message(
                role="assistant",
                content=None,
                tool_calls=[tool_call],
            ),
        )

        result = self.advisor.after_call(self.request, response)

        self.assertIsNone(result.message.tool_calls)
        self.assertEqual(result.message.content, content)

    def test_after_call_ignores_non_finish_task_tool_call(self):
        """测试 after_call 忽略非 finish_task 工具调用"""
        tool_call = ToolCall(
            id="call_123",
            type="function",
            function=ToolCallFunction(
                name="other_tool",
                arguments=json.dumps({"param": "value"}),
            ),
        )

        response = ChatCompletion(
            id="chatcmpl-123",
            object="chat.completion",
            created=1234567890,
            model="gpt-4",
            message=Message(
                role="assistant",
                content=None,
                tool_calls=[tool_call],
            ),
        )

        result = self.advisor.after_call(self.request, response)

        self.assertIsNotNone(result.message.tool_calls)
        self.assertEqual(len(result.message.tool_calls), 1)
        self.assertEqual(result.message.tool_calls[0].function.name, "other_tool")

    def test_after_call_handles_no_tool_calls(self):
        """测试 after_call 处理没有工具调用的情况"""
        response = ChatCompletion(
            id="chatcmpl-123",
            object="chat.completion",
            created=1234567890,
            model="gpt-4",
            message=Message(role="assistant", content="普通回答"),
        )

        result = self.advisor.after_call(self.request, response)

        self.assertEqual(result.message.content, "普通回答")
        self.assertIsNone(result.message.tool_calls)

    def test_after_stream_detects_finish_task_and_converts(self):
        """测试 after_stream 检测 finish_task 并转换"""
        # 初始化状态
        request_id = self.advisor._get_request_id(self.request)
        self.advisor._stream_states[request_id] = _StreamState()

        # 第一个 chunk：包含 tool_call 的 name
        chunk1 = ChatCompletionChunk(
            id="chatcmpl-123",
            object="chat.completion.chunk",
            created=1234567890,
            model="gpt-4",
            delta=DeltaMessage(
                tool_calls=[
                    DeltaToolCall(
                        index=0,
                        id="call_123",
                        type="function",
                        function=DeltaToolCallFunction(name="finish_task", arguments=None),
                    )
                ]
            ),
        )

        result1 = self.advisor.after_stream(self.request, chunk1)

        state = self.advisor._stream_states[request_id]
        self.assertTrue(state.detected_finish_task)
        self.assertEqual(state.finish_task_index, 0)
        self.assertIsNone(result1.delta.tool_calls)

        # 第二个 chunk：包含 arguments 的一部分
        chunk2 = ChatCompletionChunk(
            id="chatcmpl-123",
            object="chat.completion.chunk",
            created=1234567890,
            model="gpt-4",
            delta=DeltaMessage(
                tool_calls=[
                    DeltaToolCall(
                        index=0,
                        id="call_123",
                        type="function",
                        function=DeltaToolCallFunction(
                            name=None, arguments='{"content": "这是'
                        ),
                    )
                ]
            ),
        )

        result2 = self.advisor.after_stream(self.request, chunk2)

        state = self.advisor._stream_states[request_id]
        self.assertFalse(state.converted)  # 还未转换，因为 arguments 不完整
        self.assertIsNone(result2.delta.tool_calls)  # tool_calls 已被移除

        # 第三个 chunk：包含完整的 arguments
        chunk3 = ChatCompletionChunk(
            id="chatcmpl-123",
            object="chat.completion.chunk",
            created=1234567890,
            model="gpt-4",
            delta=DeltaMessage(
                tool_calls=[
                    DeltaToolCall(
                        index=0,
                        id="call_123",
                        type="function",
                        function=DeltaToolCallFunction(
                            name=None, arguments='最终回答"}'
                        ),
                    )
                ]
            ),
        )

        result3 = self.advisor.after_stream(self.request, chunk3)

        state = self.advisor._stream_states[request_id]
        self.assertTrue(state.converted)
        self.assertEqual(state.content, "这是最终回答")
        self.assertIsNotNone(result3.delta)
        self.assertIsNotNone(result3.delta.content)
        self.assertIn("这是", result3.delta.content)

    def test_after_stream_emits_content_in_chunks(self):
        """测试 after_stream 按块输出 content"""
        # 使用更长的内容，确保可以分块输出
        long_content = "这是一个很长的回答内容，需要分块输出，这样才能测试分块输出的功能是否正常工作。"
        content_length = len(long_content)
        
        # 初始化状态并设置已转换
        request_id = self.advisor._get_request_id(self.request)
        state = _StreamState()
        state.converted = True
        state.content = long_content
        state.content_index = 0
        self.advisor._stream_states[request_id] = state

        # 第一个 chunk
        chunk1 = ChatCompletionChunk(
            id="chatcmpl-123",
            object="chat.completion.chunk",
            created=1234567890,
            model="gpt-4",
            delta=DeltaMessage(),
        )

        result1 = self.advisor.after_stream(self.request, chunk1)

        self.assertIsNotNone(result1.delta)
        self.assertIsNotNone(result1.delta.content)
        # 第一次应该输出前20个字符（或全部，如果不足20个）
        expected_first_chunk = long_content[:20]
        self.assertEqual(result1.delta.content, expected_first_chunk)
        self.assertEqual(state.content_index, len(expected_first_chunk))

        # 第二个 chunk
        chunk2 = ChatCompletionChunk(
            id="chatcmpl-123",
            object="chat.completion.chunk",
            created=1234567890,
            model="gpt-4",
            delta=DeltaMessage(),
        )
        result2 = self.advisor.after_stream(self.request, chunk2)

        # 检查剩余内容
        remaining_after_first = long_content[state.content_index:]
        if remaining_after_first:
            self.assertIsNotNone(result2.delta)
            self.assertIsNotNone(result2.delta.content)
            # 第二次应该输出接下来的20个字符（或全部剩余内容，如果不足20个）
            expected_second_chunk = remaining_after_first[:20]
            self.assertEqual(result2.delta.content, expected_second_chunk)
            # content_index 应该是第一次输出的长度加上第二次输出的长度
            expected_total_index = len(expected_first_chunk) + len(expected_second_chunk)
            self.assertEqual(state.content_index, expected_total_index)
        else:
            # 如果第一次已经输出完所有内容，第二次应该返回原始 chunk
            self.assertEqual(result2, chunk2)

        # 第三个 chunk（内容已全部输出，返回原始 chunk）
        chunk3 = ChatCompletionChunk(
            id="chatcmpl-123",
            object="chat.completion.chunk",
            created=1234567890,
            model="gpt-4",
            delta=DeltaMessage(),
            finish_reason="stop",
        )
        result3 = self.advisor.after_stream(self.request, chunk3)

        # 内容已全部输出，应该返回原始 chunk（可能包含 finish_reason）
        # 但需要检查是否还有剩余内容需要输出
        remaining = long_content[state.content_index:]
        if remaining:
            # 如果还有剩余内容，应该继续输出
            self.assertIsNotNone(result3.delta)
            self.assertIsNotNone(result3.delta.content)
        else:
            # 如果内容已全部输出，应该返回原始 chunk
            self.assertEqual(result3.finish_reason, "stop")

    def test_after_stream_cleans_up_state_on_finish(self):
        """测试 after_stream 在流式响应结束时清理状态"""
        request_id = self.advisor._get_request_id(self.request)
        state = _StreamState()
        state.converted = True
        state.content = "测试内容"
        state.content_index = len(state.content)  # 内容已全部输出
        self.advisor._stream_states[request_id] = state

        chunk = ChatCompletionChunk(
            id="chatcmpl-123",
            object="chat.completion.chunk",
            created=1234567890,
            model="gpt-4",
            delta=DeltaMessage(),
            finish_reason="stop",
        )

        self.advisor.after_stream(self.request, chunk)

        # 状态应该被清理（因为 finish_reason 不为 None）
        self.assertNotIn(request_id, self.advisor._stream_states)

    def test_after_stream_handles_multiple_tool_calls(self):
        """测试 after_stream 处理多个工具调用的情况"""
        request_id = self.advisor._get_request_id(self.request)
        self.advisor._stream_states[request_id] = _StreamState()

        # 包含两个工具调用的 chunk
        chunk = ChatCompletionChunk(
            id="chatcmpl-123",
            object="chat.completion.chunk",
            created=1234567890,
            model="gpt-4",
            delta=DeltaMessage(
                tool_calls=[
                    DeltaToolCall(
                        index=0,
                        id="call_1",
                        type="function",
                        function=DeltaToolCallFunction(name="other_tool", arguments=None),
                    ),
                    DeltaToolCall(
                        index=1,
                        id="call_2",
                        type="function",
                        function=DeltaToolCallFunction(
                            name="finish_task",
                            arguments=json.dumps({"content": "最终回答"}),
                        ),
                    ),
                ]
            ),
        )

        result = self.advisor.after_stream(self.request, chunk)

        state = self.advisor._stream_states[request_id]
        self.assertTrue(state.converted)
        self.assertEqual(state.content, "最终回答")
        self.assertIsNone(result.delta.tool_calls)

    def test_get_request_id(self):
        """测试 _get_request_id 生成唯一请求ID"""
        request1 = LLMRequest(
            model="gpt-4",
            messages=[Message(role="user", content="test1")],
        )
        request2 = LLMRequest(
            model="gpt-4",
            messages=[Message(role="user", content="test2")],
        )
        request3 = LLMRequest(
            model="gpt-4",
            messages=[Message(role="user", content="test1")],
        )

        id1 = self.advisor._get_request_id(request1)
        id2 = self.advisor._get_request_id(request2)
        id3 = self.advisor._get_request_id(request3)

        self.assertNotEqual(id1, id2)
        self.assertEqual(id1, id3)  # 相同消息应该生成相同ID

    def test_stream_state_initialization(self):
        """测试 _StreamState 初始化"""
        state = _StreamState()

        self.assertEqual(len(state.tool_calls), 0)
        self.assertFalse(state.detected_finish_task)
        self.assertIsNone(state.finish_task_index)
        self.assertEqual(state.content, "")
        self.assertEqual(state.content_index, 0)
        self.assertFalse(state.converted)


if __name__ == "__main__":
    unittest.main()

