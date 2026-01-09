# 测试文件组织结构

测试文件已按照功能模块进行划分，每个模块对应 `eflycode/core/` 下的相应模块。

## 目录结构

```
tests/core/
├── agent/              # Agent 模块测试
│   ├── test_agent.py
│   └── test_run_loop.py
├── config/             # 配置管理模块测试
│   ├── test_config.py
│   └── test_config_manager.py
├── context/            # 上下文管理模块测试
│   ├── test_context_manager.py
│   ├── test_context_session.py
│   ├── test_context_strategies.py
│   └── test_tokenizer.py
├── event/              # 事件系统模块测试
│   └── test_event_bus.py
├── hooks/              # Hooks 系统测试
│   ├── test_types.py
│   ├── test_registry.py
│   ├── test_runner.py
│   ├── test_planner.py
│   ├── test_aggregator.py
│   ├── test_event_handler.py
│   ├── test_system.py
│   └── test_integration.py
├── llm/                # LLM 模块测试
│   ├── test_openai_provider.py
│   └── test_finish_task_advisor.py
├── mcp/                # MCP 模块测试
│   ├── test_mcp_client.py
│   └── test_mcp_config.py
├── prompt/             # Prompt 模块测试
│   ├── test_prompt_loader.py
│   ├── test_prompt_variables.py
│   └── test_system_prompt_advisor.py
├── tool/               # 工具模块测试
│   ├── test_execute_command_tool.py
│   └── test_file_system_tool.py
├── ui/                 # UI 模块测试
│   ├── test_bridge.py
│   ├── test_renderer.py
│   └── test_ui_event_queue.py
└── utils/              # 工具函数模块测试
    └── test_checkpointing.py
```

## 运行测试

### 运行所有测试
```bash
python -m unittest discover tests/core
```

### 运行特定模块的测试
```bash
# Agent 模块
python -m unittest discover tests/core/agent

# UI 模块
python -m unittest discover tests/core/ui

# Config 模块
python -m unittest discover tests/core/config

# Context 模块
python -m unittest discover tests/core/context

# Event 模块
python -m unittest discover tests/core/event

# Hooks 模块
python -m unittest discover tests/core/hooks

# LLM 模块
python -m unittest discover tests/core/llm

# MCP 模块
python -m unittest discover tests/core/mcp

# Prompt 模块
python -m unittest discover tests/core/prompt

# Tool 模块
python -m unittest discover tests/core/tool

# Utils 模块
python -m unittest discover tests/core/utils
```

### 运行单个测试文件
```bash
python -m unittest tests.core.agent.test_agent
python -m unittest tests.core.ui.test_bridge
# ... 等等
```

## 模块对应关系

| 测试目录 | 对应源码模块 | 说明 |
|---------|-------------|------|
| `agent/` | `eflycode/core/agent/` | Agent 核心功能、运行循环、会话管理 |
| `config/` | `eflycode/core/config/` | 配置加载、解析、合并 |
| `context/` | `eflycode/core/context/` | 上下文管理、策略、压缩 |
| `event/` | `eflycode/core/event/` | 事件总线 |
| `hooks/` | `eflycode/core/hooks/` | Hooks 系统 |
| `llm/` | `eflycode/core/llm/` | LLM Provider、Advisor |
| `mcp/` | `eflycode/core/mcp/` | MCP 客户端、配置 |
| `prompt/` | `eflycode/core/prompt/` | Prompt 加载、变量、Advisor |
| `tool/` | `eflycode/core/tool/` | 工具实现 |
| `ui/` | `eflycode/core/ui/` | UI 渲染、事件队列、桥接 |
| `utils/` | `eflycode/core/utils/` | 工具函数（如 checkpointing） |

