# 架构设计

本文档说明 Eflycode 的架构设计和核心组件。

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    CLI 入口层                            │
│  (eflycode/cli/__main__.py, main.py)                   │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│                  Agent 层                                │
│  (eflycode/core/agent/)                                 │
│  - BaseAgent: 核心 Agent 实现                           │
│  - Session: 会话管理                                    │
│  - RunLoop: 运行循环                                    │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
┌───────▼──────┐ ┌──▼──────┐ ┌──▼──────────┐
│   LLM 层     │ │ 工具层   │ │ 上下文层    │
│              │ │          │ │             │
│ - Provider   │ │ - Tools  │ │ - Manager   │
│ - Advisors   │ │ - MCP   │ │ - Strategies│
└──────────────┘ └──────────┘ └─────────────┘
```

## 核心组件

### 1. CLI 层

**位置：** `eflycode/cli/`

**职责：**

- 命令行参数解析
- 命令路由和执行
- 交互式 CLI 界面
- 用户输入处理

**主要模块：**

- `__main__.py`：CLI 入口点，参数解析
- `main.py`：交互式 CLI 主循环
- `commands/`：命令实现
  - `init.py`：初始化配置命令
  - `mcp.py`：MCP 管理命令

### 2. Agent 层

**位置：** `eflycode/core/agent/`

**职责：**

- Agent 核心逻辑
- 任务执行和协调
- 消息流管理
- 工具调用协调

**主要类：**

- `BaseAgent`：Agent 基类，核心实现
- `Session`：会话管理，维护对话历史
- `AgentRunLoop`：运行循环，处理任务执行

### 3. LLM 层

**位置：** `eflycode/core/llm/`

**职责：**

- LLM 提供商抽象
- API 调用封装
- 响应处理
- Advisor 集成

**主要组件：**

- `OpenAiProvider`：OpenAI 兼容的 LLM 提供商
- `FinishTaskAdvisor`：任务完成 Advisor

### 4. 工具层

**位置：** `eflycode/core/tool/`

**职责：**

- 工具抽象和基类
- 内置工具实现
- MCP 工具集成
- 工具调用管理

**主要组件：**

- `BaseTool`：工具基类
- `ToolGroup`：工具组管理
- `FileSystemTool`：文件系统操作工具
- `ExecuteCommandTool`：命令执行工具
- `MCPTool`：MCP 工具包装器
- `MCPToolGroup`：MCP 工具组

### 5. MCP 层

**位置：** `eflycode/core/mcp/`

**职责：**

- MCP 客户端实现
- MCP 服务器连接管理
- 工具加载和注册
- 配置管理

**主要组件：**

- `MCPClient`：MCP 客户端，封装 MCP SDK
- `MCPServerConfig`：服务器配置类
- `MCPTool`：MCP 工具包装器
- `MCPToolGroup`：MCP 工具组

### 6. 上下文管理层

**位置：** `eflycode/core/context/`

**职责：**

- 上下文策略实现
- 消息历史管理
- 上下文压缩和优化

**主要组件：**

- `ContextManager`：上下文管理器
- `ContextStrategy`：上下文策略接口
- `SlidingWindowStrategy`：滑动窗口策略
- `SummaryCompressionStrategy`：摘要压缩策略

### 7. UI 层

**位置：** `eflycode/core/ui/`

**职责：**

- 用户界面渲染
- 事件处理
- 输出格式化

**主要组件：**

- `Renderer`：渲染器
- `EventBridge`：事件桥接
- `UIEventQueue`：UI 事件队列
- `TerminalOutput`：终端输出

### 8. 配置层

**位置：** `eflycode/core/config/`

**职责：**

- 配置文件加载和解析
- 配置验证
- 默认配置管理

**主要组件：**

- `Config`：配置类
- `load_config`：配置加载函数
- `find_config_files`：配置文件查找，返回用户配置和项目配置

## 数据流

### 用户输入处理流程

```
用户输入
  ↓
CLI 接收 (main.py)
  ↓
Agent 处理 (BaseAgent)
  ↓
LLM 调用 (Provider)
  ↓
工具调用 (Tools)
  ↓
结果返回
  ↓
UI 渲染 (Renderer)
  ↓
用户看到输出
```

### MCP 工具调用流程

```
Agent 请求工具
  ↓
查找工具 (ToolGroup)
  ↓
MCPTool 执行
  ↓
MCPClient 调用
  ↓
MCP 服务器处理
  ↓
返回结果
  ↓
Agent 接收结果
```

## 线程模型

Eflycode 使用多线程架构：

1. **主线程**：CLI 交互和 UI 渲染
2. **Agent 线程**：Agent 任务执行
3. **MCP 事件循环线程**：每个 MCP 客户端有独立的事件循环线程

### 线程通信

- 使用 `queue.Queue` 进行线程间通信
- 主线程通过队列发送请求到 MCP 线程
- MCP 线程通过队列返回结果到主线程

## 配置管理

### 配置文件查找

1. 从当前目录向上查找 2 级，查找 `.eflycode/config.yaml`
2. 如果未找到，从用户主目录查找 `.eflycode/config.yaml`
3. 如果都未找到，使用默认配置

### MCP 配置查找

1. 从工作区目录查找 `.eflycode/mcp.json`
2. 如果未找到，从用户主目录查找 `.eflycode/mcp.json`
3. 如果未找到，返回空列表

## 错误处理

### 错误类型

- `MCPError`：MCP 相关错误的基类
  - `MCPConnectionError`：连接错误
  - `MCPProtocolError`：协议错误
  - `MCPToolError`：工具执行错误
  - `MCPConfigError`：配置错误

### 错误处理策略

- 配置加载失败：使用默认配置，记录警告
- MCP 连接失败：跳过该服务器，继续加载其他服务器
- 工具执行失败：返回错误信息给 Agent
- Agent 错误：记录日志，继续运行

## 扩展点

### 添加新的 LLM 提供商

1. 实现 `LLMProvider` 接口
2. 在 `create_agent` 中使用新的 Provider

### 添加新的工具

1. 继承 `BaseTool` 类
2. 实现必需的方法
3. 在 `create_agent` 中注册工具

### 添加新的上下文策略

1. 继承 `ContextStrategy` 类
2. 实现策略逻辑
3. 在配置中指定策略类型

## 性能考虑

- **异步处理**：MCP 客户端使用异步 I/O，不阻塞主线程
- **连接池**：MCP 连接在启动时建立，复用连接
- **上下文优化**：使用滑动窗口或摘要压缩减少上下文大小
- **工具缓存**：MCP 工具列表在首次加载后缓存

## 安全考虑

- **输入验证**：所有用户输入都经过验证
- **命令限制**：命令执行工具限制可执行的命令
- **环境变量**：敏感信息通过环境变量传递
- **权限控制**：工具具有权限标识，控制操作范围

