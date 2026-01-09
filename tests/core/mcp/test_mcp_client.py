"""MCP客户端测试"""

import unittest
from unittest.mock import MagicMock

from eflycode.core.mcp.client import MCPClient
from eflycode.core.mcp.config import MCPServerConfig
from eflycode.core.mcp.errors import MCPConnectionError


class TestMCPClient(unittest.TestCase):
    """MCP客户端测试类"""

    def setUp(self):
        """设置测试环境"""
        self.server_config = MCPServerConfig(
            name="test_server",
            transport="stdio",
            command="npx",
            args=["-y", "test-server"],
        )

    def tearDown(self):
        """清理测试环境"""
        pass

    def test_init(self):
        """测试初始化"""
        client = MCPClient(self.server_config)
        self.assertEqual(client.server_name, "test_server")
        self.assertFalse(client._connected)
        self.assertIsNone(client._session)
        self.assertIsNone(client._tools_cache)

    def test_connect_success(self):
        """测试成功连接

        由于MCP客户端使用队列和线程，完整测试需要mock整个异步流程
        这里只测试基本的初始化逻辑
        """
        client = MCPClient(self.server_config)
        self.assertFalse(client._connected)
        self.assertIsNotNone(client._request_queue)
        self.assertIsNotNone(client._response_queue)

    def test_connect_already_connected(self):
        """测试重复连接"""
        client = MCPClient(self.server_config)
        client._connected = True

        # 应该直接返回，不抛出异常
        client.connect()
        self.assertTrue(client._connected)

    def test_disconnect_not_connected(self):
        """测试断开未连接的客户端"""
        client = MCPClient(self.server_config)
        client._connected = False

        # 应该直接返回，不抛出异常
        client.disconnect()
        self.assertFalse(client._connected)

    def test_list_tools_not_connected(self):
        """测试未连接时列出工具"""
        client = MCPClient(self.server_config)
        client._connected = False

        with self.assertRaises(MCPConnectionError) as context:
            client.list_tools()

        self.assertIn("未连接", str(context.exception.message))

    def test_list_tools_cached(self):
        """测试使用缓存的工具列表"""
        client = MCPClient(self.server_config)
        client._connected = True
        cached_tools = [
            {"name": "tool1", "description": "Tool 1", "inputSchema": {}},
            {"name": "tool2", "description": "Tool 2", "inputSchema": {}},
        ]
        client._tools_cache = cached_tools

        result = client.list_tools()
        self.assertEqual(result, cached_tools)

    def test_call_tool_not_connected(self):
        """测试未连接时调用工具"""
        client = MCPClient(self.server_config)
        client._connected = False

        with self.assertRaises(MCPConnectionError) as context:
            client.call_tool("test_tool", {})

        self.assertIn("未连接", str(context.exception.message))

    def test_context_manager(self):
        """测试上下文管理器"""
        client = MCPClient(self.server_config)

        # 测试上下文管理器接口
        self.assertTrue(hasattr(client, "__enter__"))
        self.assertTrue(hasattr(client, "__exit__"))


class TestMCPTool(unittest.TestCase):
    """MCP工具测试类"""

    def setUp(self):
        """设置测试环境"""
        self.server_config = MCPServerConfig(
            name="test_server",
            transport="stdio",
            command="npx",
            args=["-y", "test-server"],
        )

    def test_tool_name_with_namespace(self):
        """测试工具名称包含命名空间前缀"""
        from eflycode.core.mcp.tool import MCPTool

        # 创建模拟客户端
        mock_client = MagicMock()
        mock_client.server_name = "test_server"

        tool = MCPTool(
            client=mock_client,
            tool_name="test_tool",
            description="Test tool",
            input_schema={"type": "object", "properties": {}},
        )

        # 验证工具名称包含命名空间前缀，使用下划线分隔
        self.assertEqual(tool.name, "test_server_test_tool")

    def test_tool_name_sanitization(self):
        """测试工具名称清理，处理特殊字符"""
        from eflycode.core.mcp.tool import MCPTool

        # 测试包含特殊字符的服务器名称和工具名称
        mock_client = MagicMock()
        mock_client.server_name = "test-server@v1.0"

        tool = MCPTool(
            client=mock_client,
            tool_name="tool-name.with-special",
            description="Test tool",
            input_schema={"type": "object", "properties": {}},
        )

        # 验证特殊字符被替换为下划线
        self.assertEqual(tool.name, "test_server_v1_0_tool_name_with_special")

    def test_tool_parameters(self):
        """测试工具参数转换"""
        from eflycode.core.mcp.tool import MCPTool

        mock_client = MagicMock()
        mock_client.server_name = "test_server"

        input_schema = {
            "type": "object",
            "properties": {
                "param1": {"type": "string"},
                "param2": {"type": "number"},
            },
            "required": ["param1"],
        }

        tool = MCPTool(
            client=mock_client,
            tool_name="test_tool",
            description="Test tool",
            input_schema=input_schema,
        )

        params = tool.parameters
        self.assertEqual(params.type, "object")
        self.assertIn("param1", params.properties)
        self.assertIn("param2", params.properties)
        self.assertIn("param1", params.required)

    def test_tool_run_with_positional_args(self):
        """测试工具执行时使用位置参数"""
        from eflycode.core.mcp.tool import MCPTool, MCPToolError

        mock_client = MagicMock()
        mock_client.server_name = "test_server"

        tool = MCPTool(
            client=mock_client,
            tool_name="test_tool",
            description="Test tool",
            input_schema={"type": "object", "properties": {}},
        )

        # MCP工具不支持位置参数
        with self.assertRaises(MCPToolError) as context:
            tool.do_run("arg1", "arg2")

        self.assertIn("不支持位置参数", str(context.exception.message))

    def test_tool_run_success(self):
        """测试工具执行成功"""
        from eflycode.core.mcp.tool import MCPTool

        mock_client = MagicMock()
        mock_client.server_name = "test_server"
        mock_client.call_tool.return_value = "执行结果"

        tool = MCPTool(
            client=mock_client,
            tool_name="test_tool",
            description="Test tool",
            input_schema={"type": "object", "properties": {}},
        )

        result = tool.do_run(param1="value1")
        self.assertEqual(result, "执行结果")
        mock_client.call_tool.assert_called_once_with("test_tool", {"param1": "value1"})


class TestMCPToolGroup(unittest.TestCase):
    """MCP工具组测试类"""

    def setUp(self):
        """设置测试环境"""
        self.server_config = MCPServerConfig(
            name="test_server",
            transport="stdio",
            command="npx",
            args=["-y", "test-server"],
        )

    def test_tool_group_init(self):
        """测试工具组初始化"""
        from eflycode.core.mcp.tool import MCPToolGroup

        mock_client = MagicMock()
        mock_client.server_name = "test_server"
        mock_client._connected = True
        mock_client.list_tools.return_value = [
            {
                "name": "tool1",
                "description": "Tool 1",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "tool2",
                "description": "Tool 2",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]

        tool_group = MCPToolGroup(mock_client)

        self.assertEqual(tool_group.name, "mcp_test_server")
        self.assertEqual(len(tool_group.tools), 2)
        self.assertEqual(tool_group.tools[0].name, "test_server_tool1")
        self.assertEqual(tool_group.tools[1].name, "test_server_tool2")

    def test_tool_group_empty_tools(self):
        """测试工具组没有工具"""
        from eflycode.core.mcp.tool import MCPToolGroup

        mock_client = MagicMock()
        mock_client.server_name = "test_server"
        mock_client._connected = True
        mock_client.list_tools.return_value = []

        tool_group = MCPToolGroup(mock_client)

        self.assertEqual(len(tool_group.tools), 0)

    def test_tool_group_disconnect(self):
        """测试工具组断开连接"""
        from eflycode.core.mcp.tool import MCPToolGroup

        mock_client = MagicMock()
        mock_client.server_name = "test_server"
        mock_client._connected = True
        mock_client.list_tools.return_value = []

        tool_group = MCPToolGroup(mock_client)
        tool_group.disconnect()

        mock_client.disconnect.assert_called_once()


if __name__ == "__main__":
    unittest.main()

