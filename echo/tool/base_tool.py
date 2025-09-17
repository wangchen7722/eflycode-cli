from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from echo.schema.tool import (
    ToolCallSchema,
    ToolExecutionError, ToolFunctionParametersSchema,
    ToolParameterError, ToolSchema,
)


def _convert_basic_type(data, schema):
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


def convert_data(data, schema):
    schema_type = schema.get("type")

    if schema_type == "object":
        return _convert_object(data, schema)
    elif schema_type == "array":
        return _convert_array(data, schema)
    else:
        return _convert_basic_type(data, schema)


def _convert_array(data, schema):
    if not isinstance(data, list):
        return data
    items_schema = schema.get("items", {})
    return [convert_data(item, items_schema) for item in data]


def _convert_object(data, schema):
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
    def should_approval(self) -> bool:
        """工具是否需要审批"""
        return True

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""
        pass

    def display(self, **kwargs) -> str:
        """工具显示名称"""
        return "使用此工具"

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, ToolFunctionParametersSchema]:
        """工具参数"""
        pass

    @property
    def examples(self) -> Optional[Dict[str, ToolCallSchema]]:
        """工具示例"""
        return None

    @property
    def schema(self) -> ToolSchema:
        """获取工具的schema定义"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": [
                        param_name 
                        for param_name, param_schema in self.parameters.items()
                        if param_schema.get("required", False)
                    ]
                },
            },
        }

    def _convert_type(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        # 参数名 -> 参数类型
        try:
            typed_params = {}
            for param_name, param_value in parameters.items():
                if param_name in self.parameters:
                    typed_params[param_name] = convert_data(
                        param_value, self.parameters[param_name]
                    )
            return typed_params
        except Exception as e:
            raise ToolParameterError(
                message=f"参数类型转换失败: {str(e)}",
                tool_name=self.name,
                error_details=e
            ) from e

    @abstractmethod
    def do_run(self, *args, **kwargs) -> str:
        """执行工具的核心方法，需要被子类重写

        Args:
            **kwargs: 工具执行所需的参数

        Returns:
            str: 工具执行结果
        """
        raise NotImplementedError("Tool must implement do method")

    def run(self, *args, **kwargs) -> str:
        """执行工具的包装方法，会先转换参数类型，然后调用 do_run 方法

        Args:
            **kwargs: 工具执行所需的参数

        Returns:
            str: 工具执行结果
            
        Raises:
            ToolExecutionError: 当工具执行失败时抛出
        """
        try:
            return self.do_run(*args, **self._convert_type(kwargs))
        except (ToolParameterError, ToolExecutionError):
            # 如果已经是工具相关异常，直接重新抛出
            raise
        except Exception as e:
            # 将其他异常包装为ToolExecutionError
            raise ToolExecutionError(
                message=str(e),
                tool_name=self.name,
                error_details=e
            ) from e

    def __call__(self, *args, **kwargs) -> str:
        """使工具实例可以像函数一样被调用

        Args:
            **kwargs: 工具执行所需的参数

        Returns:
            str: 工具执行结果
        """
        return self.run(**kwargs)
