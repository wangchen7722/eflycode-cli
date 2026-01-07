"""MCP相关错误定义"""


class MCPError(Exception):
    """MCP基础错误类"""

    def __init__(self, message: str, details: str = ""):
        """初始化MCP错误

        Args:
            message: 错误消息
            details: 错误详情
        """
        self.message = message
        self.details = details
        super().__init__(self.message)

    def __str__(self) -> str:
        """返回错误字符串"""
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class MCPConnectionError(MCPError):
    """MCP连接错误

    当无法连接到MCP服务器时抛出
    """

    pass


class MCPProtocolError(MCPError):
    """MCP协议错误

    当MCP协议通信出现问题时抛出
    """

    pass


class MCPToolError(MCPError):
    """MCP工具执行错误

    当MCP工具执行失败时抛出
    """

    def __init__(self, message: str, tool_name: str, error_details: Exception = None):
        """初始化MCP工具错误

        Args:
            message: 错误消息
            tool_name: 工具名称
            error_details: 原始错误详情
        """
        self.tool_name = tool_name
        self.error_details = error_details
        super().__init__(message=message, details=str(error_details) if error_details else "")


class MCPConfigError(MCPError):
    """MCP配置错误

    当MCP配置加载或解析失败时抛出
    """

    pass

