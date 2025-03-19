from typing import Any, Dict, Optional, TypedDict, Literal, List


class ToolFunctionParametersSchema(TypedDict):
    """工具函数参数的schema定义"""
    type: str
    properties: Dict[str, Dict[str, Any]]
    required: Optional[List[str]]


class ToolFunctionSchema(TypedDict):
    """工具函数的schema定义"""
    name: str
    description: str
    parameters: ToolFunctionParametersSchema


class ToolSchema(TypedDict):
    """工具的schema定义"""
    type: Literal["function"]
    function: ToolFunctionSchema


class BaseTool:
    """工具基类，定义了所有工具的基本属性和执行接口"""

    NAME: str
    """工具名称"""
    DESCRIPTION: str
    """工具描述"""
    PARAMETERS: ToolFunctionParametersSchema
    """工具参数"""
    EXAMPLES: Optional[List[Dict[str, ToolSchema]]]
    """工具示例"""

    @property
    def name(self) -> str:
        """获取工具名称"""
        return self.NAME

    @property
    def description(self) -> str:
        """获取工具描述"""
        return self.DESCRIPTION

    @property
    def parameters(self) -> ToolFunctionParametersSchema:
        """获取工具参数"""
        return self.PARAMETERS

    @property
    def schema(self) -> ToolSchema:
        """获取工具的schema定义"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }

    def run(self, *args, **kwargs) -> str:
        """执行工具的核心方法，需要被子类重写
        
        Args:
            **kwargs: 工具执行所需的参数
            
        Returns:
            str: 工具执行结果
        """
        raise NotImplementedError("Tool must implement run method")

    def __call__(self, *args, **kwargs) -> str:
        """使工具实例可以像函数一样被调用
        
        Args:
            **kwargs: 工具执行所需的参数
            
        Returns:
            str: 工具执行结果
        """
        return self.run(*args, **kwargs)
