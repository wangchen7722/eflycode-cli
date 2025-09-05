import unittest
import json
from typing import List

from echo.parsers.stream_parser import StreamResponseParser
from echo.agents.schema import AgentResponseChunk, AgentResponseChunkType


class TestStreamResponseParser(unittest.TestCase):
    """StreamResponseParser的测试用例"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.parser = StreamResponseParser(tools=[])
    
    def _parse_stream(self, content: str) -> List[AgentResponseChunk]:
        """辅助方法：解析流内容并返回所有chunk"""
        chunks = []
        for chunk in self.parser.parse_text(content):
            chunks.append(chunk)
        return chunks
    
    def test_pure_text_output(self):
        """测试纯文本输出"""
        content = "这是一段纯文本内容，没有任何工具调用。"
        chunks = self._parse_stream(content)
        
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].type, AgentResponseChunkType.TEXT)
        self.assertEqual(chunks[0].content, content)
        self.assertIsNone(chunks[0].tool_calls)
    
    def test_html_content(self):
        """测试HTML内容解析"""
        content = "<div>这是HTML内容</div><p>包含多个标签</p>"
        chunks = self._parse_stream(content)
        
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].type, AgentResponseChunkType.TEXT)
        self.assertEqual(chunks[0].content, content)
    
    def test_tool_call_only(self):
        """测试仅有工具调用的场景"""
        content = (
            "<tool_call>\n"
            "<tool_name>search_files</tool_name>\n"
            "<tool_params>\n"
            '{"query": "test", "path": "/home"}\n'
            "</tool_params>\n"
            "</tool_call>"
        )
        chunks = self._parse_stream(content)
        print(chunks)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].type, AgentResponseChunkType.TOOL_CALL)
        self.assertIsNotNone(chunks[0].tool_calls)
        self.assertEqual(chunks[0].tool_calls[0]["function"]["name"], "search_files")
        self.assertEqual(json.loads(chunks[0].tool_calls[0]["function"]["arguments"])["query"], "test")
        self.assertEqual(json.loads(chunks[0].tool_calls[0]["function"]["arguments"])["path"], "/home")
    
    def test_mixed_content_text_then_tool(self):
        """测试文本后跟工具调用的混合内容"""
        content = (
            "我需要搜索一些文件。\n\n"
            "<tool_call>\n"
            "<tool_name>search_files</tool_name>\n"
            "<tool_params>\n"
            '{"query": "*.py"}\n'
            "</tool_params>\n"
            "</tool_call>"
        )
        chunks = self._parse_stream(content)
        
        self.assertEqual(len(chunks), 2)
        
        # 第一个chunk是文本
        self.assertEqual(chunks[0].type, AgentResponseChunkType.TEXT)
        self.assertEqual(chunks[0].content, "我需要搜索一些文件。\n\n")
        
        # 第二个chunk是工具调用
        self.assertEqual(chunks[1].type, AgentResponseChunkType.TOOL_CALL)
        self.assertEqual(chunks[1].tool_calls[0]["function"]["name"], "search_files")
        self.assertEqual(json.loads(chunks[1].tool_calls[0]["function"]["arguments"])["query"], "*.py")
    
    def test_mixed_content_tool_then_text(self):
        """测试工具调用后跟文本的混合内容"""
        content = (
            "<tool_call>\n"
            "<tool_name>get_weather</tool_name>\n"
            "<tool_params>\n"
            '{"city": "北京"}\n'
            "</tool_params>\n"
            "</tool_call>\n\n"
            "根据查询结果，今天天气不错。"
        )
        chunks = self._parse_stream(content)
        
        self.assertEqual(len(chunks), 2)
        
        # 第一个chunk是工具调用
        self.assertEqual(chunks[0].type, AgentResponseChunkType.TOOL_CALL)
        self.assertEqual(chunks[0].tool_calls[0]["function"]["name"], "get_weather")
        
        # 第二个chunk是文本
        self.assertEqual(chunks[1].type, AgentResponseChunkType.TEXT)
        self.assertEqual(chunks[1].content, "\n\n根据查询结果，今天天气不错。")
    
    def test_multiple_tool_calls(self):
        """测试多个工具调用"""
        content = (
            "<tool_call>\n"
            "<tool_name>tool1</tool_name>\n"
            "<tool_params>\n"
            '{"param1": "value1"}\n'
            "</tool_params>\n"
            "</tool_call>\n\n"
            "<tool_call>\n"
            "<tool_name>tool2</tool_name>\n"
            "<tool_params>\n"
            '{"param2": "value2"}\n'
            "</tool_params>\n"
            "</tool_call>"
        )
        chunks = self._parse_stream(content)
        
        self.assertEqual(len(chunks), 3)  # 两个工具调用 + 中间的文本
        
        # 第一个工具调用
        self.assertEqual(chunks[0].type, AgentResponseChunkType.TOOL_CALL)
        self.assertEqual(chunks[0].tool_calls[0]["function"]["name"], "tool1")
        
        # 中间的文本
        self.assertEqual(chunks[1].type, AgentResponseChunkType.TEXT)
        self.assertEqual(chunks[1].content, "\n\n")
        
        # 第二个工具调用
        self.assertEqual(chunks[2].type, AgentResponseChunkType.TOOL_CALL)
        self.assertEqual(chunks[2].tool_calls[0]["function"]["name"], "tool2")
    
    def test_complex_mixed_content(self):
        """测试复杂的混合内容：文本、HTML、工具调用"""
        content = (
            "<h1>分析报告</h1>\n"
            "<p>我将为您分析数据：</p>\n\n"
            "<tool_call>\n"
            "<tool_name>analyze_data</tool_name>\n"
            "<tool_params>\n"
            '{"dataset": "sales.csv", "type": "summary"}\n'
            "</tool_params>\n"
            "</tool_call>\n\n"
            "<div class=\"result\">\n"
            "分析完成，结果如上所示。\n"
            "</div>"
        )
        chunks = self._parse_stream(content)
        
        self.assertEqual(len(chunks), 3)
        
        # 第一个chunk：HTML文本
        self.assertEqual(chunks[0].type, AgentResponseChunkType.TEXT)
        self.assertIn("<h1>分析报告</h1>", chunks[0].content)
        
        # 第二个chunk：工具调用
        self.assertEqual(chunks[1].type, AgentResponseChunkType.TOOL_CALL)
        self.assertEqual(chunks[1].tool_calls[0]["function"]["name"], "analyze_data")
        
        # 第三个chunk：HTML文本
        self.assertEqual(chunks[2].type, AgentResponseChunkType.TEXT)
        self.assertIn("<div class=\"result\">", chunks[2].content)
    
    def test_malformed_json_parameters(self):
        """测试格式错误的JSON参数"""
        content = (
            "<tool_call_start>\n"
            "<tool_call_name_start>test_tool</tool_call_name_end>\n"
            "<tool_call_params_start>\n"
            '{"invalid": json}\n'  # 无效的JSON
            "</tool_call_params_end>\n"
            "</tool_call_end>"
        )
        chunks = self._parse_stream(content)
        
        # 应该将整个内容作为文本处理，因为JSON解析失败
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].type, AgentResponseChunkType.TEXT)
    
    def test_incomplete_tool_call(self):
        """测试不完整的工具调用"""
        content = (
            "<tool_call_start>\n"
            "<tool_call_name_start>incomplete_tool</tool_call_name_end>\n"
            "<tool_call_params_start>\n"
            '{"param": "value"}'  # 缺少结束标签
        )
        chunks = self._parse_stream(content)
        
        # 不完整的工具调用应该作为文本处理
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].type, AgentResponseChunkType.TEXT)
    
    def test_nested_tags_in_text(self):
        """测试文本中包含类似工具调用标签的内容"""
        content = (
            "这里有一些示例代码：\n"
            "```xml\n"
            "<tool_call_start>\n"
            "<tool_call_name_start>example</tool_call_name_end>\n"
            "</tool_call_end>\n"
            "```\n"
            "这不应该被解析为工具调用。"
        )
        chunks = self._parse_stream(content)
        
        # 应该全部作为文本处理
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].type, AgentResponseChunkType.TEXT)
        self.assertEqual(chunks[0].content, content)
    
    def test_empty_content(self):
        """测试空内容"""
        content = ""
        chunks = self._parse_stream(content)
        
        self.assertEqual(len(chunks), 0)
    
    def test_whitespace_only(self):
        """测试仅包含空白字符的内容"""
        content = "   \n\t  \n  "
        chunks = self._parse_stream(content)
        
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].type, AgentResponseChunkType.TEXT)
        self.assertEqual(chunks[0].content, content)
    
    def test_custom_tag_format(self):
        """测试自定义标签格式"""
        # 使用方括号格式的解析器
        custom_parser = StreamResponseParser(
            tools=[],
            tool_call_start="[tool_call]",
            tool_call_end="[/tool_call]",
            tool_name_start="[tool_name]",
            tool_name_end="[/tool_name]",
            params_start="[parameters]",
            params_end="[/parameters]"
        )
        
        content = (
            "[tool_call]\n"
            "[tool_name]custom_tool[/tool_name]\n"
            "[parameters]\n"
            '{"test": "value"}\n'
            "[/parameters]\n"
            "[/tool_call]"
        )
        
        chunks = list(custom_parser.parse_text(content))
        
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].type, AgentResponseChunkType.TOOL_CALL)
        self.assertEqual(chunks[0].tool_calls[0]["function"]["name"], "custom_tool")
        self.assertEqual(json.loads(chunks[0].tool_calls[0]["function"]["arguments"])["test"], "value")
    
    def test_streaming_behavior(self):
        """测试流式处理行为"""
        # 测试完整内容的解析
        content = "Hello <tool_call><tool_name>test</tool_name><tool_params>{}</tool_params></tool_call> World"
        
        parser = StreamResponseParser(tools=[])
        chunks = list(parser.parse_text(content))
        
        # 验证最终结果
        self.assertGreaterEqual(len(chunks), 2)  # 至少有文本和工具调用
        
        # 找到工具调用chunk
        tool_chunks = [c for c in chunks if c.type == AgentResponseChunkType.TOOL_CALL]
        self.assertEqual(len(tool_chunks), 1)
        self.assertEqual(tool_chunks[0].tool_calls[0]["function"]["name"], "test")


    def test_nested_html_tags(self):
        """测试嵌套HTML标签的解析"""
        content = (
            '<div class="container">'
            '  <h1>标题</h1>'
            '  <p>段落 <span>内联元素</span> 继续段落</p>'
            '</div>'
        )
        chunks = self._parse_stream(content)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].type, AgentResponseChunkType.TEXT)
        self.assertEqual(chunks[0].content, content)

    def test_html_with_tool_like_content(self):
        """测试包含类似工具调用标签的HTML内容"""
        content = (
            "<article>"
            "  <section>"
            "    <tool_example>这是一个示例，不是真实工具调用</tool_example>"
            "  </section>"
            "</article>"
        )
        chunks = self._parse_stream(content)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].type, AgentResponseChunkType.TEXT)
        self.assertEqual(chunks[0].content, content)

    def test_mixed_html_and_tool_call(self):
        """测试HTML与工具调用的混合内容"""
        content = (
            "<div>HTML开始</div>"
            "<tool_call>"
            "  <tool_name>example_tool</tool_name>"
            "  <tool_params>{\"param\": \"value\"}</tool_params>"
            "</tool_call>"
            "<p>HTML继续</p>"
        )
        chunks = self._parse_stream(content)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0].type, AgentResponseChunkType.TEXT)
        self.assertEqual(chunks[1].type, AgentResponseChunkType.TOOL_CALL)
        self.assertEqual(chunks[2].type, AgentResponseChunkType.TEXT)
        self.assertEqual(chunks[1].tool_calls[0]["function"]["name"], "example_tool")

    def test_custom_tags(self):
        """测试自定义标签格式的工具调用解析"""
        # 使用自定义标签格式创建解析器
        custom_parser = StreamResponseParser(
            tools=[],
            tool_call_start="[CALL]",
            tool_call_end="[/CALL]",
            tool_name_start="[NAME]",
            tool_name_end="[/NAME]",
            params_start="[PARAMS]",
            params_end="[/PARAMS]"
        )
        
        # 测试使用自定义标签的工具调用
        content = (
            "这是一些文本内容。"
            "[CALL]"
            "[NAME]search_files[/NAME]"
            "[PARAMS]{\"query\": \"test\", \"path\": \"/home\"}[/PARAMS]"
            "[/CALL]"
            "这是更多文本内容。"
        )
        
        chunks = []
        for chunk in custom_parser.parse_text(content):
            chunks.append(chunk)
        
        # 验证解析结果
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0].type, AgentResponseChunkType.TEXT)
        self.assertEqual(chunks[0].content, "这是一些文本内容。")
        
        self.assertEqual(chunks[1].type, AgentResponseChunkType.TOOL_CALL)
        self.assertIsNotNone(chunks[1].tool_calls)
        self.assertEqual(len(chunks[1].tool_calls), 1)
        self.assertEqual(chunks[1].tool_calls[0]["function"]["name"], "search_files")
        
        self.assertEqual(chunks[2].type, AgentResponseChunkType.TEXT)
        self.assertEqual(chunks[2].content, "这是更多文本内容。")

if __name__ == '__main__':
    unittest.main()