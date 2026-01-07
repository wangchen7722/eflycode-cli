# 快速开始

本文档将帮助您快速安装和开始使用 Eflycode。

## 安装

### 使用 uv 安装（推荐）

```bash
# 克隆项目
git clone <repository-url>
cd eflycode-cli

# 使用 uv 安装依赖
uv sync
```

### 使用 pip 安装

```bash
# 克隆项目
git clone <repository-url>
cd eflycode-cli

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Linux/macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# 安装依赖
pip install -e .
```

## 初始化配置

首次使用前，需要初始化配置文件：

```bash
python -m eflycode.cli init
```

这将在当前目录或工作区创建 `.eflycode/config.yaml` 配置文件。

## 配置 API 密钥

编辑 `.eflycode/config.yaml` 文件，设置您的 API 密钥：

```yaml
model:
  default: gpt-4
  entries:
    - model: gpt-4
      name: GPT-4
      provider: openai
      api_key: YOUR_API_KEY_HERE
      base_url: null
      max_context_length: 8192
      temperature: 0.7
      supports_native_tool_call: true
```

## 启动交互式 CLI

配置完成后，启动交互式 CLI：

```bash
python -m eflycode.cli
```

或者直接运行：

```bash
python -m eflycode.cli
```

## 基本使用

### 交互式对话

启动 CLI 后，您可以直接输入问题或任务：

```
> 帮我创建一个 Python 函数来计算斐波那契数列
```

### 使用 CLI 命令

Eflycode 提供了多个 CLI 命令来管理配置和 MCP 服务器：

```bash
# 初始化配置
python -m eflycode.cli init

# 列出 MCP 服务器
python -m eflycode.cli mcp list

# 添加 MCP 服务器
python -m eflycode.cli mcp add <name> <command> [args...]

# 移除 MCP 服务器
python -m eflycode.cli mcp remove <name>
```

## 下一步

- 查看 [CLI 命令参考](cli-commands.md) 了解所有可用命令
- 阅读 [配置指南](configuration.md) 了解详细配置选项
- 查看 [MCP 服务器配置](mcp-servers.md) 了解如何集成 MCP 服务器

