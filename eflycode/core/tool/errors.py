class ToolExecutionError(Exception):
    """工具执行错误异常"""

    def __init__(self, message: str, tool_name: str = "", error_details: Exception = None):
        """初始化工具执行错误

        Args:
            message: 错误消息
            tool_name: 工具名称
            error_details: 原始异常详情
        """
        self.message = message
        self.tool_name = tool_name
        self.error_details = error_details
        super().__init__(self.message)

    def __str__(self) -> str:
        """返回错误字符串表示"""
        if self.tool_name:
            return f"[{self.tool_name}] {self.message}"
        return self.message


class ToolParameterError(ToolExecutionError):
    """工具参数错误异常"""

    def __init__(self, message: str, tool_name: str = "", error_details: Exception = None):
        """初始化工具参数错误

        Args:
            message: 错误消息
            tool_name: 工具名称
            error_details: 原始异常详情
        """
        super().__init__(f"参数错误: {message}", tool_name, error_details)

