import unittest
import json
from typing import List, Generator

from echo.parsers.stream_parser import StreamResponseParser
from echo.agents.schema import AgentResponseChunk, AgentResponseChunkType, ToolCall


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
        self.assertIsNone(chunks[0].tool_call)
    
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
            "<tool_call_start>\n"
            "<tool_call_name_start>search_files</tool_call_name_end>\n"
            "<tool_call_params_start>\n"
            '{"query": "test", "path": "/home"}\n'
            "</tool_call_params_end>\n"
            "</tool_call_end>"
        )
        chunks = self._parse_stream(content)
        
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].type, AgentResponseChunkType.TOOL_CALL)
        self.assertIsNotNone(chunks[0].tool_call)
        self.assertEqual(chunks[0].tool_call.name, "search_files")
        self.assertEqual(chunks[0].tool_call.parameters["query"], "test")
        self.assertEqual(chunks[0].tool_call.parameters["path"], "/home")
    
    def test_mixed_content_text_then_tool(self):
        """测试文本后跟工具调用的混合内容"""
        content = (
            "我需要搜索一些文件。\n\n"
            "<tool_call_start>\n"
            "<tool_call_name_start>search_files</tool_call_name_end>\n"
            "<tool_call_params_start>\n"
            '{"query": "*.py"}\n'
            "</tool_call_params_end>\n"
            "</tool_call_end>"
        )
        chunks = self._parse_stream(content)
        
        self.assertEqual(len(chunks), 2)
        
        # 第一个chunk是文本
        self.assertEqual(chunks[0].type, AgentResponseChunkType.TEXT)
        self.assertEqual(chunks[0].content, "我需要搜索一些文件。\n\n")
        
        # 第二个chunk是工具调用
        self.assertEqual(chunks[1].type, AgentResponseChunkType.TOOL_CALL)
        self.assertEqual(chunks[1].tool_call.name, "search_files")
        self.assertEqual(chunks[1].tool_call.parameters["query"], "*.py")
    
    def test_mixed_content_tool_then_text(self):
        """测试工具调用后跟文本的混合内容"""
        content = (
            "<tool_call_start>\n"
            "<tool_call_name_start>get_weather</tool_call_name_end>\n"
            "<tool_call_params_start>\n"
            '{"city": "北京"}\n'
            "</tool_call_params_end>\n"
            "</tool_call_end>\n\n"
            "根据查询结果，今天天气不错。"
        )
        chunks = self._parse_stream(content)
        
        self.assertEqual(len(chunks), 2)
        
        # 第一个chunk是工具调用
        self.assertEqual(chunks[0].type, AgentResponseChunkType.TOOL_CALL)
        self.assertEqual(chunks[0].tool_call.name, "get_weather")
        
        # 第二个chunk是文本
        self.assertEqual(chunks[1].type, AgentResponseChunkType.TEXT)
        self.assertEqual(chunks[1].content, "\n\n根据查询结果，今天天气不错。")
    
    def test_multiple_tool_calls(self):
        """测试多个工具调用"""
        content = (
            "<tool_call_start>\n"
            "<tool_call_name_start>tool1</tool_call_name_end>\n"
            "<tool_call_params_start>\n"
            '{"param1": "value1"}\n'
            "</tool_call_params_end>\n"
            "</tool_call_end>\n\n"
            "<tool_call_start>\n"
            "<tool_call_name_start>tool2</tool_call_name_end>\n"
            "<tool_call_params_start>\n"
            '{"param2": "value2"}\n'
            "</tool_call_params_end>\n"
            "</tool_call_end>"
        )
        chunks = self._parse_stream(content)
        
        self.assertEqual(len(chunks), 3)  # 两个工具调用 + 中间的文本
        
        # 第一个工具调用
        self.assertEqual(chunks[0].type, AgentResponseChunkType.TOOL_CALL)
        self.assertEqual(chunks[0].tool_call.name, "tool1")
        
        # 中间的文本
        self.assertEqual(chunks[1].type, AgentResponseChunkType.TEXT)
        self.assertEqual(chunks[1].content, "\n\n")
        
        # 第二个工具调用
        self.assertEqual(chunks[2].type, AgentResponseChunkType.TOOL_CALL)
        self.assertEqual(chunks[2].tool_call.name, "tool2")
    
    def test_complex_mixed_content(self):
        """测试复杂的混合内容：文本、HTML、工具调用"""
        content = (
            "<h1>分析报告</h1>\n"
            "<p>我将为您分析数据：</p>\n\n"
            "<tool_call_start>\n"
            "<tool_call_name_start>analyze_data</tool_call_name_end>\n"
            "<tool_call_params_start>\n"
            '{"dataset": "sales.csv", "type": "summary"}\n'
            "</tool_call_params_end>\n"
            "</tool_call_end>\n\n"
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
        self.assertEqual(chunks[1].tool_call.name, "analyze_data")
        
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
        self.assertEqual(chunks[0].tool_call.name, "custom_tool")
        self.assertEqual(chunks[0].tool_call.parameters["test"], "value")
    
    def test_streaming_behavior(self):
        """测试流式处理行为"""
        # 模拟逐字符输入
        content = "Hello <tool_call_start><tool_call_name_start>test</tool_call_name_end><tool_call_params_start>{}</tool_call_params_end></tool_call_end> World"
        
        parser = StreamResponseParser(tools=[])
        chunks = []
        
        # 逐字符添加内容
        for i in range(1, len(content) + 1):
            partial_content = content[:i]
            new_chunks = list(parser.parse_text(partial_content))
            # 只添加新的chunks
            if len(new_chunks) > len(chunks):
                chunks.extend(new_chunks[len(chunks):])
        
        # 验证最终结果
        self.assertGreaterEqual(len(chunks), 2)  # 至少有文本和工具调用
        
        # 找到工具调用chunk
        tool_chunks = [c for c in chunks if c.type == AgentResponseChunkType.TOOL_CALL]
        self.assertEqual(len(tool_chunks), 1)
        self.assertEqual(tool_chunks[0].tool_call.name, "test")


if __name__ == '__main__':
    unittest.main()