# 测试目录结构

测试目录按照功能模块进行组织，分为 `cli` 和 `core` 两个子目录。

## 目录结构

```
tests/
├── __init__.py          # 测试包初始化文件
├── cli/                 # CLI 相关测试
│   ├── __init__.py
│   ├── test_cli_init.py    # init 命令测试
│   └── test_cli_mcp.py     # mcp 命令测试
└── core/                # Core 功能测试
    ├── __init__.py
    ├── test_agent.py              # Agent 测试
    ├── test_bridge.py             # EventBridge 测试
    ├── test_config.py             # 配置管理测试
    ├── test_context_manager.py    # 上下文管理器测试
    ├── test_context_session.py    # 上下文会话测试
    ├── test_context_strategies.py # 上下文策略测试
    ├── test_event_bus.py         # 事件总线测试
    ├── test_execute_command_tool.py # 命令执行工具测试
    ├── test_file_tool.py          # 文件工具测试
    ├── test_finish_task_advisor.py # FinishTaskAdvisor 测试
    ├── test_mcp_client.py         # MCP 客户端测试
    ├── test_mcp_config.py         # MCP 配置测试
    ├── test_openai_provider.py     # OpenAI Provider 测试
    ├── test_renderer.py           # 渲染器测试
    ├── test_run_loop.py           # 运行循环测试
    ├── test_tokenizer.py          # 分词器测试
    └── test_ui_event_queue.py     # UI 事件队列测试
```

## 运行测试

### 运行所有测试

```bash
python -m unittest discover tests
```

### 运行 CLI 测试

```bash
python -m unittest discover tests/cli
```

### 运行 Core 测试

```bash
python -m unittest discover tests/core
```

### 运行特定测试文件

```bash
# CLI 测试
python -m unittest tests.cli.test_cli_init
python -m unittest tests.cli.test_cli_mcp

# Core 测试
python -m unittest tests.core.test_agent
python -m unittest tests.core.test_config
```

### 运行特定测试类或方法

```bash
python -m unittest tests.cli.test_cli_init.TestInitCommand
python -m unittest tests.cli.test_cli_init.TestInitCommand.test_init_creates_config_file
```

## 测试分类说明

### CLI 测试 (`tests/cli/`)

测试命令行接口相关的功能：

- **test_cli_init.py**: 测试 `init` 命令，包括配置文件创建、目录创建等
- **test_cli_mcp.py**: 测试 `mcp` 命令，包括 list、add、remove 子命令

### Core 测试 (`tests/core/`)

测试核心功能模块：

- **Agent**: Agent 核心逻辑、运行循环
- **配置管理**: 配置文件加载、解析、验证
- **上下文管理**: 上下文管理器、会话、策略
- **工具**: 文件工具、命令执行工具
- **LLM**: OpenAI Provider、Advisor
- **MCP**: MCP 客户端、配置
- **UI**: 渲染器、事件队列、事件桥接
- **其他**: 事件总线、分词器等

## 测试规范

- 所有测试使用 `unittest` 框架
- 测试文件以 `test_` 开头
- 测试类以 `Test` 开头
- 测试方法以 `test_` 开头
- 使用 `setUp` 和 `tearDown` 进行测试准备和清理
- 测试应该独立，不依赖其他测试的执行顺序

