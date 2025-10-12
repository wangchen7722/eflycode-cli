import unittest
import json
from typing import List, Generator
from echo.schema.agent import AgentResponseChunk, AgentResponseChunkType, AgentResponse
from echo.schema.llm import (
    ChatCompletionChunk, StreamChoice, DeltaMessage, DeltaToolCall, DeltaToolCallFunction,
    ChatCompletion, Choice, Message, ToolCall, ToolCallFunction, Usage
)
from echo.agent.core.response_converter import AgentResponseConverter


class TestAgentResponseConverter(unittest.TestCase):
    """AgentResponseConverter 测试用例"""

    def setUp(self):
        """初始化转换器"""
        self.converter = AgentResponseConverter()

    def _make_chunk(self, content: str = "", tool_name=None, tool_args=None, finish_reason=None, tool_id=None, tool_type="function") -> ChatCompletionChunk:
        """构造单个 ChatCompletionChunk"""
        tool_calls = None
        if tool_name or tool_args:
            tool_calls = [
                DeltaToolCall(
                    index=0,
                    id=tool_id,
                    type=tool_type if tool_type else None,
                    function=DeltaToolCallFunction(
                        name=tool_name,
                        arguments=tool_args or ""
                    )
                )
            ]

        delta = DeltaMessage(
            role="assistant",
            content=content if content is not None else "",
            tool_calls=tool_calls,
        )

        choice = StreamChoice(
            index=0,
            delta=delta,
            finish_reason=finish_reason
        )

        return ChatCompletionChunk(
            id="test",
            object="chat.completion.chunk",
            created=123,
            model="gpt-test",
            choices=[choice],
            usage=None
        )

    def _run_converter(self, chunks: List[ChatCompletionChunk]) -> List[AgentResponseChunk]:
        """运行转换器并收集输出"""
        return list(self.converter.convert_stream(iter(chunks)))

    def _make_completion(self, content: str = "", tool_calls: List[ToolCall] = None, finish_reason: str = None, usage: Usage = None) -> ChatCompletion:
        """构造单个 ChatCompletion"""
        message = Message(
            role="assistant",
            content=content,
            tool_calls=tool_calls
        )

        choice = Choice(
            index=0,
            message=message,
            finish_reason=finish_reason
        )

        return ChatCompletion(
            id="test",
            object="chat.completion",
            created=123,
            model="gpt-test",
            choices=[choice],
            usage=usage or Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        )

    def test_pure_text_output(self):
        """测试纯文本输出"""
        chunks = [self._make_chunk(content="你好，这是一段普通文本。")]
        result = self._run_converter(chunks)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].type, AgentResponseChunkType.TEXT)
        self.assertEqual(result[0].content, "你好，这是一段普通文本。")

    def test_tool_call_simple(self):
        """测试简单的工具调用（一次name+一次参数）"""
        chunks = [
            self._make_chunk(tool_name="search_files", tool_id="call_123"),
            self._make_chunk(tool_args='{"query": "test", "path": "/home"}'),
            self._make_chunk(finish_reason="tool_calls"),
        ]

        result = self._run_converter(chunks)
        tool_chunks = [r for r in result if r.type in [AgentResponseChunkType.TOOL_CALL_START, AgentResponseChunkType.TOOL_CALL_END]]

        self.assertGreaterEqual(len(tool_chunks), 1)
        # 检查工具调用开始块
        start_chunk = next((r for r in result if r.type == AgentResponseChunkType.TOOL_CALL_START), None)
        self.assertIsNotNone(start_chunk)
        self.assertEqual(start_chunk.tool_calls[0].function.name, "search_files")
        
        # 检查工具调用结束块
        end_chunk = next((r for r in result if r.type == AgentResponseChunkType.TOOL_CALL_END), None)
        self.assertIsNotNone(end_chunk)
        self.assertIn("/home", end_chunk.tool_calls[0].function.arguments)

    def test_mixed_text_and_tool(self):
        """测试混合内容（文本 + 工具调用）"""
        chunks = [
            self._make_chunk(content="我需要搜索文件"),
            self._make_chunk(tool_name="search_files", tool_id="call_456"),
            self._make_chunk(tool_args='{"query": "*.py"}'),
            self._make_chunk(finish_reason="tool_calls"),
        ]

        result = self._run_converter(chunks)

        self.assertEqual(result[0].type, AgentResponseChunkType.TEXT)
        self.assertIn("搜索文件", result[0].content)

        start_chunk = next((r for r in result if r.type == AgentResponseChunkType.TOOL_CALL_START), None)
        self.assertIsNotNone(start_chunk)
        self.assertEqual(start_chunk.tool_calls[0].function.name, "search_files")
        
        end_chunk = next((r for r in result if r.type == AgentResponseChunkType.TOOL_CALL_END), None)
        self.assertIsNotNone(end_chunk)
        self.assertIn("*.py", end_chunk.tool_calls[0].function.arguments)

    def test_multiple_tool_calls(self):
        """测试多个工具调用连续出现"""
        chunks = [
            self._make_chunk(tool_name="tool1", tool_id="call_1"),
            self._make_chunk(tool_args='{"param": "v1"}'),
            self._make_chunk(finish_reason="tool_calls"),

            self._make_chunk(tool_name="tool2", tool_id="call_2"),
            self._make_chunk(tool_args='{"param": "v2"}'),
            self._make_chunk(finish_reason="tool_calls"),
        ]

        result = self._run_converter(chunks)
        tool_start_chunks = [r for r in result if r.type == AgentResponseChunkType.TOOL_CALL_START]

        self.assertEqual(len(tool_start_chunks), 2)
        self.assertEqual(tool_start_chunks[0].tool_calls[0].function.name, "tool1")
        self.assertEqual(tool_start_chunks[1].tool_calls[0].function.name, "tool2")

    def test_incomplete_json(self):
        """测试不完整 JSON 参数不输出最终块"""
        chunks = [
            self._make_chunk(tool_name="broken_tool", tool_id="call_broken"),
            self._make_chunk(tool_args='{"param": "incomplete"'),  # 缺少右括号
        ]

        result = self._run_converter(chunks)
        # 应该有工具调用开始块，但没有结束块
        start_chunks = [r for r in result if r.type == AgentResponseChunkType.TOOL_CALL_START]
        end_chunks = [r for r in result if r.type == AgentResponseChunkType.TOOL_CALL_END]
        
        self.assertEqual(len(start_chunks), 1)
        self.assertEqual(len(end_chunks), 0)

    def test_done_chunk_output(self):
        """测试结束标志"""
        chunks = [self._make_chunk(finish_reason="tool_calls")]
        result = self._run_converter(chunks)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].type, AgentResponseChunkType.DONE)
        self.assertEqual(result[0].finish_reason, "tool_calls")

    # ========== convert 方法测试（非流式） ==========
    
    def test_convert_pure_text(self):
        """测试 convert 方法处理纯文本响应"""
        completion = self._make_completion(
            content="这是一个纯文本响应",
            finish_reason="stop"
        )
        
        result = self.converter.convert(completion)
        
        self.assertIsInstance(result, AgentResponse)
        self.assertEqual(result.content, "这是一个纯文本响应")
        self.assertEqual(result.finish_reason, "stop")
        self.assertIsNone(result.tool_calls)
        self.assertIsNotNone(result.usage)
        self.assertEqual(result.usage.total_tokens, 30)
        self.assertEqual(result.metadata["model"], "gpt-test")
        self.assertIsNotNone(result.messages)
        self.assertEqual(len(result.messages), 1)

    def test_convert_with_tool_calls(self):
        """测试 convert 方法处理工具调用响应"""
        tool_calls = [
            ToolCall(
                id="call_123",
                type="function",
                function=ToolCallFunction(
                    name="search_files",
                    arguments='{"query": "test.py", "path": "/home"}'
                )
            )
        ]
        
        completion = self._make_completion(
            content="",
            tool_calls=tool_calls,
            finish_reason="tool_calls"
        )
        
        result = self.converter.convert(completion)
        
        self.assertIsInstance(result, AgentResponse)
        self.assertEqual(result.content, "")
        self.assertEqual(result.finish_reason, "tool_calls")
        self.assertIsNotNone(result.tool_calls)
        self.assertEqual(len(result.tool_calls), 1)
        self.assertEqual(result.tool_calls[0].function.name, "search_files")
        self.assertIn("test.py", result.tool_calls[0].function.arguments)
        self.assertIsNotNone(result.messages)
        self.assertEqual(len(result.messages), 1)

    def test_convert_empty_response(self):
        """测试 convert 方法处理空响应"""
        completion = ChatCompletion(
            id="test",
            object="chat.completion",
            created=123,
            model="gpt-test",
            choices=[],
            usage=Usage(prompt_tokens=5, completion_tokens=0, total_tokens=5)
        )
        
        result = self.converter.convert(completion)
        
        self.assertIsInstance(result, AgentResponse)
        self.assertEqual(result.content, "")
        self.assertIsNone(result.finish_reason)
        self.assertIsNone(result.tool_calls)
        self.assertEqual(len(result.messages), 0)

    def test_convert_no_model(self):
        """测试 convert 方法处理无模型信息的响应"""
        completion = self._make_completion(content="测试内容")
        completion.model = None
        
        result = self.converter.convert(completion)
        
        self.assertEqual(result.metadata, {})
        self.assertIsNotNone(result.messages)
        self.assertEqual(len(result.messages), 1)

    # ========== 辅助方法测试 ==========
    
    def test_is_valid_json(self):
        """测试 _is_valid_json 方法"""
        # 有效的 JSON
        self.assertTrue(self.converter._is_valid_json('{"key": "value"}'))
        self.assertTrue(self.converter._is_valid_json('[]'))
        self.assertTrue(self.converter._is_valid_json('null'))
        self.assertTrue(self.converter._is_valid_json('"string"'))
        self.assertTrue(self.converter._is_valid_json('123'))
        
        # 无效的 JSON
        self.assertFalse(self.converter._is_valid_json('{"key": "value"'))  # 缺少右括号
        self.assertFalse(self.converter._is_valid_json('invalid'))
        self.assertFalse(self.converter._is_valid_json(''))
        self.assertFalse(self.converter._is_valid_json('{key: value}'))  # 键没有引号

    def test_convert_usage(self):
        """测试 _convert_usage 方法"""
        # 有 usage 信息的 completion
        completion_with_usage = ChatCompletion(
            id="test",
            object="chat.completion",
            created=123,
            model="gpt-test",
            choices=[
                Choice(
                    index=0,
                    message=Message(role="assistant", content="test"),
                    finish_reason="stop"
                )
            ],
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        )
        
        result = self.converter._convert_usage(completion_with_usage)
        self.assertIsNotNone(result)
        self.assertEqual(result.prompt_tokens, 10)
        self.assertEqual(result.completion_tokens, 5)
        self.assertEqual(result.total_tokens, 15)
        
        # 没有 usage 信息的 completion - 创建一个最小的 usage 对象
        completion_without_usage = ChatCompletion(
            id="test",
            object="chat.completion",
            created=123,
            model="gpt-test",
            choices=[
                Choice(
                    index=0,
                    message=Message(role="assistant", content="test"),
                    finish_reason="stop"
                )
            ],
            usage=Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
        )
        
        result = self.converter._convert_usage(completion_without_usage)
        self.assertIsNotNone(result)
        self.assertEqual(result.prompt_tokens, 0)

    def test_convert_metadata(self):
        """测试 _convert_metadata 方法"""
        # 有模型信息的 completion
        completion_with_model = ChatCompletion(
            id="test",
            object="chat.completion",
            created=123,
            model="gpt-4",
            choices=[
                Choice(
                    index=0,
                    message=Message(role="assistant", content="test"),
                    finish_reason="stop"
                )
            ],
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        )
        
        result = self.converter._convert_metadata(completion_with_model)
        self.assertEqual(result, {"model": "gpt-4"})
        
        # 没有模型信息的 completion
        completion_without_model = ChatCompletion(
            id="test",
            object="chat.completion",
            created=123,
            model="",
            choices=[
                Choice(
                    index=0,
                    message=Message(role="assistant", content="test"),
                    finish_reason="stop"
                )
            ],
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        )
        
        result = self.converter._convert_metadata(completion_without_model)
        self.assertEqual(result, {})

    # ========== 边界情况和错误处理测试 ==========
    
    def test_empty_content_chunks(self):
        """测试空内容的 chunk"""
        chunks = [
            self._make_chunk(content=""),
            self._make_chunk(content=None),
        ]
        
        result = self._run_converter(chunks)
        # 空内容不应该产生输出
        self.assertEqual(len(result), 0)

    def test_tool_call_without_name(self):
        """测试没有工具名的工具调用"""
        chunks = [
            self._make_chunk(tool_args='{"param": "value"}'),  # 只有参数，没有名称
        ]
        
        result = self._run_converter(chunks)
        # 没有工具名不应该产生工具调用块
        tool_chunks = [r for r in result if r.type in [AgentResponseChunkType.TOOL_CALL_START, AgentResponseChunkType.TOOL_CALL_END]]
        self.assertEqual(len(tool_chunks), 0)

    def test_tool_call_args_accumulation(self):
        """测试工具调用参数的累积"""
        chunks = [
            self._make_chunk(tool_name="test_tool", tool_id="call_123"),
            self._make_chunk(tool_args='{"param1": '),
            self._make_chunk(tool_args='"value1", '),
            self._make_chunk(tool_args='"param2": "value2"}'),
            self._make_chunk(finish_reason="tool_calls"),
        ]
        
        result = self._run_converter(chunks)
        end_chunk = next((r for r in result if r.type == AgentResponseChunkType.TOOL_CALL_END), None)
        
        self.assertIsNotNone(end_chunk)
        # 验证参数被正确累积
        args = end_chunk.tool_calls[0].function.arguments
        self.assertIn("value1", args)
        self.assertIn("value2", args)

    def test_multiple_finish_reasons(self):
        """测试不同的结束原因"""
        test_cases = [
            ("stop", AgentResponseChunkType.DONE),
            ("length", AgentResponseChunkType.DONE),
            ("content_filter", AgentResponseChunkType.DONE),
        ]
        
        for finish_reason, expected_type in test_cases:
            with self.subTest(finish_reason=finish_reason):
                chunks = [self._make_chunk(finish_reason=finish_reason)]
                result = self._run_converter(chunks)
                
                if finish_reason != "tool_calls":
                    # 非工具调用的结束原因不应该产生 DONE 块
                    done_chunks = [r for r in result if r.type == AgentResponseChunkType.DONE]
                    self.assertEqual(len(done_chunks), 0)

    def test_tool_call_with_different_types(self):
        """测试不同类型的工具调用"""
        chunks = [
            self._make_chunk(tool_name="custom_tool", tool_id="call_456", tool_type="function"),
            self._make_chunk(tool_args='{"data": "test"}'),
            self._make_chunk(finish_reason="tool_calls"),
        ]
        
        result = self._run_converter(chunks)
        start_chunk = next((r for r in result if r.type == AgentResponseChunkType.TOOL_CALL_START), None)
        
        self.assertIsNotNone(start_chunk)
        self.assertEqual(start_chunk.tool_calls[0].type, "function")

    # ========== 状态管理和重置功能测试 ==========
    
    def test_state_reset_after_tool_calls(self):
        """测试工具调用完成后状态重置"""
        chunks = [
            self._make_chunk(tool_name="test_tool", tool_id="call_123"),
            self._make_chunk(tool_args='{"param": "value"}'),
            self._make_chunk(finish_reason="tool_calls"),
        ]
        
        # 运行第一次转换
        result1 = self._run_converter(chunks)
        
        # 验证状态已重置
        self.assertIsNone(self.converter.active_tool_name)
        self.assertIsNone(self.converter.active_tool_call_id)
        self.assertIsNone(self.converter.active_tool_call_type)
        self.assertEqual(self.converter.accumulated_arguments, "")
        self.assertFalse(self.converter.tool_call_in_progress)
        
        # 运行第二次转换，应该正常工作
        result2 = self._run_converter(chunks)
        self.assertEqual(len(result1), len(result2))

    def test_state_persistence_during_tool_call(self):
        """测试工具调用过程中状态持久化"""
        # 开始工具调用
        chunks = [self._make_chunk(tool_name="persistent_tool", tool_id="call_456")]
        self._run_converter(chunks)
        
        # 验证状态被正确设置
        self.assertEqual(self.converter.active_tool_name, "persistent_tool")
        self.assertEqual(self.converter.active_tool_call_id, "call_456")
        self.assertTrue(self.converter.tool_call_in_progress)
        
        # 添加参数
        chunks = [self._make_chunk(tool_args='{"test": "data"}')]
        self._run_converter(chunks)
        
        # 验证参数被累积
        self.assertIn("test", self.converter.accumulated_arguments)

    def test_tool_call_index_change_triggers_reset(self):
        """测试工具调用索引变化触发状态重置"""
        # 第一个工具调用
        chunk1 = self._make_chunk(tool_name="tool1", tool_id="call_1")
        chunk1.choices[0].delta.tool_calls[0].index = 0
        
        # 第二个工具调用（不同索引）
        chunk2 = self._make_chunk(tool_name="tool2", tool_id="call_2")
        chunk2.choices[0].delta.tool_calls[0].index = 1
        
        chunks = [
            chunk1,
            self._make_chunk(tool_args='{"param1": "value1"}'),
            chunk2,
            self._make_chunk(tool_args='{"param2": "value2"}'),
            self._make_chunk(finish_reason="tool_calls"),
        ]
        
        result = self._run_converter(chunks)
        
        # 应该有两个工具调用开始块
        start_chunks = [r for r in result if r.type == AgentResponseChunkType.TOOL_CALL_START]
        self.assertEqual(len(start_chunks), 2)
        self.assertEqual(start_chunks[0].tool_calls[0].function.name, "tool1")
        self.assertEqual(start_chunks[1].tool_calls[0].function.name, "tool2")

    def test_manual_reset_state(self):
        """测试手动重置状态"""
        # 设置一些状态
        self.converter.active_tool_name = "test_tool"
        self.converter.active_tool_call_id = "call_123"
        self.converter.active_tool_call_type = "function"
        self.converter.accumulated_arguments = '{"param": "value"}'
        self.converter.tool_call_in_progress = True
        
        # 手动重置
        self.converter._reset_state()
        
        # 验证所有状态都被重置
        self.assertIsNone(self.converter.active_tool_name)
        self.assertIsNone(self.converter.active_tool_call_id)
        self.assertIsNone(self.converter.active_tool_call_type)
        self.assertEqual(self.converter.accumulated_arguments, "")
        self.assertFalse(self.converter.tool_call_in_progress)

if __name__ == "__main__":
    unittest.main()
