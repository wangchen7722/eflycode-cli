from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from eflycode.core.llm.protocol import ToolDefinition, ToolFunction, ToolFunctionParameters
from eflycode.core.tool.errors import ToolExecutionError, ToolParameterError


def _convert_basic_type(data: Any, schema: Dict[str, Any]) -> Any:
    """转换基本类型

    Args:
        data: 要转换的数据
        schema: JSON Schema 定义

    Returns:
        转换后的数据
    """
    schema_type = schema.get("type")
    try:
        if schema_type == "integer":
            return int(data)
        elif schema_type == "number":
            return float(data)
        elif schema_type == "boolean":
            if isinstance(data, str):
                return data.lower() in ["true", "1", "t", "yes"]
            else:
                return bool(data)
        elif schema_type == "string":
            return str(data)
        else:
            return data
    except (ValueError, TypeError):
        return data


def _convert_array(data: Any, schema: Dict[str, Any]) -> Any:
    """转换数组类型

    Args:
        data: 要转换的数据
        schema: JSON Schema 定义

    Returns:
        转换后的数据
    """
    if not isinstance(data, list):
        return data
    items_schema = schema.get("items", {})
    return [convert_data(item, items_schema) for item in data]


def _convert_object(data: Any, schema: Dict[str, Any]) -> Any:
    """转换对象类型

    Args:
        data: 要转换的数据
        schema: JSON Schema 定义

    Returns:
        转换后的数据
    """
    if not isinstance(data, dict):
        return data
    properties = schema.get("properties", {})
    converted = {}
    for key, value in data.items():
        if key in properties:
            prop_schema = properties[key]
            converted[key] = convert_data(value, prop_schema)
        else:
            converted[key] = value
    return converted


def convert_data(data: Any, schema: Dict[str, Any]) -> Any:
    """根据 JSON Schema 转换数据

    Args:
        data: 要转换的数据
        schema: JSON Schema 定义

    Returns:
        转换后的数据
    """
    schema_type = schema.get("type")

    if schema_type == "object":
        return _convert_object(data, schema)
    elif schema_type == "array":
        return _convert_array(data, schema)
    else:
        return _convert_basic_type(data, schema)


class ToolType:
    """工具类型"""

    FUNCTION = "function"
    MEMORY = "memory"


class BaseTool(ABC):
    """工具基类，定义了所有工具的基本属性和执行接口"""

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        pass

    @property
    @abstractmethod
    def type(self) -> str:
        """工具类型"""
        pass

    @property
    @abstractmethod
    def permission(self) -> str:
        """工具的操作权限：create、read、edit 或 delete"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""
        pass

    def display(self, **kwargs) -> str:
        """工具显示名称

        Args:
            **kwargs: 工具参数

        Returns:
            工具显示名称
        """
        return "使用此工具"

    @property
    @abstractmethod
    def parameters(self) -> ToolFunctionParameters:
        """工具参数"""
        pass

    @property
    def examples(self) -> Optional[Dict[str, ToolFunction]]:
        """工具示例"""
        return None

    @property
    def definition(self) -> ToolDefinition:
        """获取工具的 schema 定义

        Returns:
            ToolDefinition: 工具定义
        """
        return ToolDefinition(
            type="function",
            function=ToolFunction(
                name=self.name,
                description=self.description,
                parameters=self.parameters,
            ),
        )

    def _convert_type(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """转换参数类型

        Args:
            parameters: 原始参数字典

        Returns:
            转换后的参数字典

        Raises:
            ToolParameterError: 当参数类型转换失败时抛出
        """
        try:
            typed_params = {}
            for param_name, param_value in parameters.items():
                if param_name in self.parameters.properties:
                    typed_params[param_name] = convert_data(
                        param_value, self.parameters.properties[param_name]
                    )
            return typed_params
        except Exception as e:
            raise ToolParameterError(
                message=f"参数类型转换失败: {str(e)}",
                tool_name=self.name,
                error_details=e,
            ) from e

    @abstractmethod
    def do_run(self, *args, **kwargs) -> str:
        """执行工具的核心方法，需要被子类重写

        Args:
            *args: 位置参数
            **kwargs: 工具执行所需的参数

        Returns:
            str: 工具执行结果
        """
        raise NotImplementedError("Tool must implement do_run method")

    def run(self, *args, **kwargs) -> str:
        """执行工具的包装方法，会先转换参数类型，然后调用 do_run 方法

        Args:
            *args: 位置参数
            **kwargs: 工具执行所需的参数

        Returns:
            str: 工具执行结果

        Raises:
            ToolParameterError: 当参数错误时抛出
            ToolExecutionError: 当工具执行失败时抛出
        """
        try:
            return self.do_run(*args, **self._convert_type(kwargs))
        except (ToolParameterError, ToolExecutionError):
            raise
        except Exception as e:
            raise ToolExecutionError(
                message=str(e),
                tool_name=self.name,
                error_details=e,
            ) from e

    def __call__(self, *args, **kwargs) -> str:
        """使工具实例可以像函数一样被调用

        Args:
            *args: 位置参数
            **kwargs: 工具执行所需的参数

        Returns:
            str: 工具执行结果
        """
        return self.run(*args, **kwargs)


class ToolGroup:
    """工具组"""

    def __init__(self, name: str, description: str, tools: List[BaseTool]) -> None:
        """初始化工具组

        Args:
            name: 工具组名称
            description: 工具组描述
            tools: 工具列表
        """
        self.name = name
        self.description = description
        self.tools = tools

    def list_tools(self) -> List[BaseTool]:
        """获取工具组中所有工具的列表

        Returns:
            List[BaseTool]: 工具组中所有工具的列表
        """
        return self.tools

    def list_tool_definitions(self) -> List[ToolDefinition]:
        """获取工具组中所有工具的定义列表

        Returns:
            List[ToolDefinition]: 工具组中所有工具的定义列表
        """
        return [tool.definition for tool in self.tools]

