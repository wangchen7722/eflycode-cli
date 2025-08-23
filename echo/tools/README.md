# Echo AI Tools

这个模块包含了Echo AI系统中使用的各种工具类。

## 工具异常处理

本模块提供了统一的工具异常处理机制，通过分层的异常类来处理工具使用过程中的不同类型错误。

### 异常类层次结构

```
ToolError (基类)
├── ToolParameterError (参数相关错误)
└── ToolExecutionError (执行相关错误)
```

### 异常类说明

#### ToolError
工具相关错误的基类，包含通用的错误信息。

#### ToolParameterError
工具参数错误，包括：
- 参数传递错误
- 参数类型校验错误
- 参数格式转换错误

#### ToolExecutionError
工具执行过程中的错误，包括：
- 业务逻辑执行失败
- 外部依赖调用失败
- 运行时异常

### 功能特性

- **分类异常处理**: 区分参数错误和执行错误，便于精确处理
- **详细错误信息**: 包含工具名称、错误消息和详细错误信息
- **异常链**: 保留原始异常信息，便于调试
- **自动分类**: `BaseTool` 自动将不同阶段的异常分类处理
- **灵活使用**: 工具可以主动抛出特定类型异常或让 `BaseTool` 自动处理

### 使用示例

```python
from echo.tools import BaseTool, ToolParameterError, ToolExecutionError

class MyTool(BaseTool):
    @property
    def name(self) -> str:
        return "my_tool"
    
    @property
    def type(self) -> str:
        return "function"
    
    @property
    def description(self) -> str:
        return "示例工具"
    
    @property
    def parameters(self):
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
        # 参数校验（可选，BaseTool会自动处理类型转换错误）
        if not isinstance(action, str):
            raise ToolParameterError(
                message="action参数必须是字符串类型",
                tool_name=self.name
            )
        
        if action == "success":
            return "操作成功"
        elif action == "divide":
            if value == 0:
                # 业务逻辑错误
                raise ToolExecutionError(
                    message="除数不能为零",
                    tool_name=self.name,
                    error_details={"action": action, "value": value}
                )
            return f"结果: {100 / value}"
        elif action == "runtime_error":
            # 这个错误会被 BaseTool 自动包装为 ToolExecutionError
            raise ValueError("运行时错误")
        else:
            raise RuntimeError("未知操作")

# 使用工具
tool = MyTool()

# 1. 参数类型错误（自动捕获）
try:
    result = tool.run(action=123)  # 传入非字符串类型
except ToolParameterError as e:
    print(f"参数错误: {e}")

# 2. 业务逻辑错误
try:
    result = tool.run(action="divide", value=0)
except ToolExecutionError as e:
    print(f"执行错误: {e}")
    print(f"错误详情: {e.error_details}")

# 3. 自动包装的运行时错误
try:
    result = tool.run(action="runtime_error")
except ToolExecutionError as e:
    print(f"执行错误: {e}")
    print(f"原始异常: {e.__cause__}")
```

### 异常属性

所有工具异常都包含以下属性：
- `message`: 错误消息
- `tool_name`: 相关的工具名称
- `error_details`: 详细的错误信息（可以是任何类型）

### 自动异常处理

`BaseTool` 在不同阶段自动处理异常：

1. **参数转换阶段**: 捕获类型转换异常，包装为 `ToolParameterError`
2. **执行阶段**: 
   - 如果捕获到 `ToolParameterError` 或 `ToolExecutionError`，直接重新抛出
   - 如果捕获到其他异常，自动包装为 `ToolExecutionError`

### 最佳实践

1. **参数校验**: 在工具中进行复杂参数校验时，主动抛出 `ToolParameterError`
2. **业务逻辑**: 在业务逻辑执行失败时，主动抛出 `ToolExecutionError`
3. **异常捕获**: 根据异常类型进行不同的处理策略
4. **错误信息**: 提供清晰、有用的错误消息和详细信息

这确保了所有工具执行错误都有统一且分类的处理方式，便于上层代码进行精确的错误处理和日志记录。