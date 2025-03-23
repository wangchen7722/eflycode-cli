from typing import Any, Dict, Optional, Literal, List, Required
from typing_extensions import TypedDict


class ToolFunctionParametersSchema(TypedDict, total=False):
    """工具函数参数的schema定义"""
    type: Required[str]
    properties: Required[Dict[str, Dict[str, Any]]]
    required: Required[Optional[List[str]]]


class ToolFunctionSchema(TypedDict, total=False):
    """工具函数的schema定义"""
    name: Required[str]
    description: Required[str]
    parameters: Required[ToolFunctionParametersSchema]


class ToolSchema(TypedDict, total=False):
    """工具的schema定义"""
    type: Required[Literal["function"]]
    function: Required[ToolFunctionSchema]


class ToolCallSchema(TypedDict, total=False):
    """工具的schema定义"""
    type: Required[Literal["function"]]
    name: Required[str]
    arguments: Required[Dict[str, Any]]


class BaseTool:
    """工具基类，定义了所有工具的基本属性和执行接口"""

    NAME: str
    """工具名称"""
    DESCRIPTION: str
    """工具描述"""
    DISPLAY: str = "{agent_name} want to use this tool"
    """工具显示名称"""
    PARAMETERS: ToolFunctionParametersSchema
    """工具参数"""
    EXAMPLES: Optional[Dict[str, ToolCallSchema]]
    """工具示例"""

    @property
    def name(self) -> str:
        """获取工具名称"""
        return self.NAME.strip()

    @property
    def description(self) -> str:
        """获取工具描述"""
        return "\n".join([line.strip() for line in self.DESCRIPTION.strip().split("\n")])

    def display(self, agent_name) -> str:
        """获取工具显示名称"""
        return self.DISPLAY.format(agent_name=agent_name).strip()

    @property
    def raw_parameters(self) -> ToolFunctionParametersSchema:
        """获取工具参数"""
        return self.PARAMETERS

    @property
    def parameters(self) -> Dict[str, Any]:
        """获取工具参数"""
        required = self.PARAMETERS["required"] or []
        return {
            param_name: {
                "type": param_schema["type"],
                "description": "\n".join(
                    [line.strip() for line in param_schema.get("description", "").strip().split("\n")]),
                "required": param_name in required
            }
            for param_name, param_schema in self.PARAMETERS["properties"].items()
        }

    @property
    def examples(self) -> Dict[str, ToolCallSchema]:
        return {
            example_name.strip(): example_tool_call
            for example_name, example_tool_call in self.EXAMPLES.items()
        } if self.EXAMPLES else {}

    @property
    def schema(self) -> ToolSchema:
        """获取工具的schema定义"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.raw_parameters
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
