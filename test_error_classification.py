#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试工具错误分类体系
"""

from echo.tools import BaseTool, ToolError, ToolParameterError, ToolExecutionError
from typing import Any, Dict


class TestTool(BaseTool):
    """用于测试错误分类的工具"""
    
    @property
    def name(self) -> str:
        return "test_tool"
    
    @property
    def description(self) -> str:
        return "用于测试错误分类的工具"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型"
                },
                "value": {
                    "type": "integer",
                    "description": "数值参数",
                    "default": 0
                }
            },
            "required": ["action"]
        }
    
    def do_run(self, action: str, value: int = 0) -> str:
        # 参数校验错误
        if action == "param_error":
            raise ToolParameterError(
                message="这是一个参数校验错误",
                tool_name=self.name,
                error_details={"action": action}
            )
        
        # 执行错误
        elif action == "exec_error":
            raise ToolExecutionError(
                message="这是一个执行错误",
                tool_name=self.name,
                error_details={"action": action, "value": value}
            )
        
        # 运行时错误（会被自动包装）
        elif action == "runtime_error":
            raise ValueError("这是一个运行时错误")
        
        # 除零错误（会被自动包装）
        elif action == "divide":
            return f"结果: {100 / value}"
        
        # 成功情况
        elif action == "success":
            return "操作成功"
        
        else:
            raise RuntimeError(f"未知操作: {action}")


def test_error_classification():
    """测试错误分类"""
    tool = TestTool()
    
    print("=== 测试工具错误分类体系 ===")
    print()
    
    # 1. 测试参数类型转换错误（自动捕获）
    print("1. 测试参数类型转换错误:")
    try:
        result = tool.run(action=123)  # 传入非字符串类型
    except ToolParameterError as e:
        print(f"   ✓ 捕获到ToolParameterError: {e}")
        print(f"   工具名称: {e.tool_name}")
        print(f"   原始异常: {type(e.__cause__).__name__}")
    except Exception as e:
        print(f"   ✗ 意外异常: {type(e).__name__}: {e}")
    print()
    
    # 2. 测试主动抛出的参数错误
    print("2. 测试主动抛出的参数错误:")
    try:
        result = tool.run(action="param_error")
    except ToolParameterError as e:
        print(f"   ✓ 捕获到ToolParameterError: {e}")
        print(f"   工具名称: {e.tool_name}")
        print(f"   错误详情: {e.error_details}")
    except Exception as e:
        print(f"   ✗ 意外异常: {type(e).__name__}: {e}")
    print()
    
    # 3. 测试主动抛出的执行错误
    print("3. 测试主动抛出的执行错误:")
    try:
        result = tool.run(action="exec_error", value=42)
    except ToolExecutionError as e:
        print(f"   ✓ 捕获到ToolExecutionError: {e}")
        print(f"   工具名称: {e.tool_name}")
        print(f"   错误详情: {e.error_details}")
    except Exception as e:
        print(f"   ✗ 意外异常: {type(e).__name__}: {e}")
    print()
    
    # 4. 测试自动包装的运行时错误
    print("4. 测试自动包装的运行时错误:")
    try:
        result = tool.run(action="runtime_error")
    except ToolExecutionError as e:
        print(f"   ✓ 捕获到ToolExecutionError: {e}")
        print(f"   工具名称: {e.tool_name}")
        print(f"   原始异常: {type(e.__cause__).__name__}: {e.__cause__}")
    except Exception as e:
        print(f"   ✗ 意外异常: {type(e).__name__}: {e}")
    print()
    
    # 5. 测试除零错误（自动包装）
    print("5. 测试除零错误（自动包装）:")
    try:
        result = tool.run(action="divide", value=0)
    except ToolExecutionError as e:
        print(f"   ✓ 捕获到ToolExecutionError: {e}")
        print(f"   工具名称: {e.tool_name}")
        print(f"   原始异常: {type(e.__cause__).__name__}: {e.__cause__}")
    except Exception as e:
        print(f"   ✗ 意外异常: {type(e).__name__}: {e}")
    print()
    
    # 6. 测试成功情况
    print("6. 测试成功情况:")
    try:
        result = tool.run(action="success")
        print(f"   ✓ 成功执行: {result}")
    except Exception as e:
        print(f"   ✗ 意外异常: {type(e).__name__}: {e}")
    print()
    
    # 7. 测试异常继承关系
    print("7. 测试异常继承关系:")
    try:
        tool.run(action="param_error")
    except ToolError as e:
        print(f"   ✓ ToolParameterError 是 ToolError 的子类")
        print(f"   异常类型: {type(e).__name__}")
    except Exception as e:
        print(f"   ✗ 意外异常: {type(e).__name__}: {e}")
    
    try:
        tool.run(action="exec_error")
    except ToolError as e:
        print(f"   ✓ ToolExecutionError 是 ToolError 的子类")
        print(f"   异常类型: {type(e).__name__}")
    except Exception as e:
        print(f"   ✗ 意外异常: {type(e).__name__}: {e}")
    print()
    
    print("=== 测试完成 ===")


if __name__ == "__main__":
    test_error_classification()