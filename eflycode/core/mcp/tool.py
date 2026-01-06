"""MCP工具包装器

将MCP工具转换为BaseTool，自动添加命名空间前缀
"""

from typing import Any, Dict, List

from eflycode.core.llm.protocol import ToolFunctionParameters
from eflycode.core.mcp.client import MCPClient
from eflycode.core.mcp.errors import MCPToolError
from eflycode.core.tool.base import BaseTool, ToolGroup, ToolType


class MCPTool(BaseTool):
    """MCP工具包装器

    将MCP工具转换为BaseTool，自动添加命名空间前缀，格式为服务器名称加冒号加工具名称
    """

    def __init__(
        self,
        client: MCPClient,
        tool_name: str,
        description: str,
        input_schema: Dict[str, Any],
    ):
        """初始化MCP工具

        Args:
            client: MCP客户端实例
            tool_name: 原始工具名称，不包含命名空间前缀
            description: 工具描述
            input_schema: 工具输入schema，使用JSON Schema格式
        """
        self._client = client
        self._original_tool_name = tool_name
        self._description = description
        self._input_schema = input_schema

        # 工具名称添加命名空间前缀，使用下划线分隔符以符合API规范
        # 将服务器名称和工具名称中的特殊字符替换为下划线
        safe_server_name = self._sanitize_name(client.server_name)
        safe_tool_name = self._sanitize_name(tool_name)
        self._full_name = f"{safe_server_name}_{safe_tool_name}"

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """清理名称，只保留字母、数字和下划线

        Args:
            name: 原始名称

        Returns:
            str: 清理后的名称
        """
        import re
        # 将非字母数字字符替换为下划线
        sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name)
        # 移除连续的下划线
        sanitized = re.sub(r"_+", "_", sanitized)
        # 移除开头和结尾的下划线
        sanitized = sanitized.strip("_")
        # 确保不为空
        if not sanitized:
            sanitized = "unnamed"
        return sanitized

    @property
    def name(self) -> str:
        """工具名称，带命名空间前缀"""
        return self._full_name

    @property
    def type(self) -> str:
        """工具类型"""
        return ToolType.FUNCTION

    @property
    def permission(self) -> str:
        """工具的操作权限

        MCP工具默认是read权限，具体权限由MCP服务器决定
        """
        return "read"

    @property
    def description(self) -> str:
        """工具描述"""
        return self._description

    @property
    def parameters(self) -> ToolFunctionParameters:
        """工具参数

        将MCP的inputSchema转换为ToolFunctionParameters
        """
        properties = self._input_schema.get("properties", {})
        required = self._input_schema.get("required", [])

        return ToolFunctionParameters(
            type="object",
            properties=properties,
            required=required if required else None,
        )

    def do_run(self, *args, **kwargs) -> str:
        """执行工具的核心方法

        Args:
            *args: 位置参数，MCP工具不支持位置参数，传入位置参数会抛出异常
            **kwargs: 工具执行所需的参数

        Returns:
            str: 工具执行结果

        Raises:
            MCPToolError: 当工具执行失败时抛出
        """
        if args:
            raise MCPToolError(
                message="MCP工具不支持位置参数",
                tool_name=self.name,
            )

        try:
            # 调用MCP客户端执行工具，使用原始工具名，不包含前缀
            result = self._client.call_tool(self._original_tool_name, kwargs)
            return result
        except Exception as e:
            if isinstance(e, MCPToolError):
                raise
            raise MCPToolError(
                message=f"MCP工具执行失败: {str(e)}",
                tool_name=self.name,
                error_details=e,
            ) from e


class MCPToolGroup(ToolGroup):
    """MCP工具组

    管理来自同一MCP服务器的工具集合
    """

    def __init__(self, client: MCPClient):
        """初始化MCP工具组

        Args:
            client: MCP客户端实例
        """
        self.client = client
        self.server_name = client.server_name

        # 从MCP服务器获取工具列表并创建MCPTool实例
        tools = self._load_tools()
        super().__init__(
            name=f"mcp_{self.server_name}",
            description=f"MCP服务器工具组: {self.server_name}",
            tools=tools,
        )

    def _load_tools(self) -> List[MCPTool]:
        """从MCP服务器加载工具

        Returns:
            List[MCPTool]: MCP工具列表
        """
        try:
            # 连接到MCP服务器，如果未连接则先连接
            if not self.client._connected:
                # 如果连接未启动，先启动异步连接
                if not self.client._connecting and self.client._loop is None:
                    self.client.start_connect()
                # 等待连接完成
                self.client.connect()

            # 获取工具列表
            tools_data = self.client.list_tools()

            # 创建MCPTool实例
            mcp_tools = []
            for tool_data in tools_data:
                tool_name = tool_data.get("name", "")
                if not tool_name:
                    continue

                description = tool_data.get("description", "")
                input_schema = tool_data.get("inputSchema", {})

                try:
                    mcp_tool = MCPTool(
                        client=self.client,
                        tool_name=tool_name,
                        description=description,
                        input_schema=input_schema,
                    )
                    mcp_tools.append(mcp_tool)
                except Exception as e:
                    from eflycode.core.utils.logger import logger

                    logger.warning(
                        f"创建MCP工具失败: {self.server_name}_{tool_name}，错误: {e}，跳过"
                    )
                    continue

            return mcp_tools
        except Exception as e:
            from eflycode.core.utils.logger import logger

            logger.error(f"从MCP服务器加载工具失败: {self.server_name}，错误: {e}")
            return []

    def disconnect(self) -> None:
        """断开MCP服务器连接"""
        self.client.disconnect()

