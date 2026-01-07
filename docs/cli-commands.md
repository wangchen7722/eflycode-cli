# CLI 命令参考

本文档详细说明 Eflycode CLI 的所有可用命令。

## 命令概览

```bash
python -m eflycode.cli [命令] [选项]
```

如果不提供任何命令，将启动交互式 CLI。

## init 命令

初始化配置文件。

### 用法

```bash
python -m eflycode.cli init
```

### 说明

- 在当前工作区创建 `.eflycode/config.yaml` 配置文件
- 如果配置文件已存在，将报错并退出
- 创建的配置文件包含默认的 logger、model、workspace 和 context 配置

### 示例

```bash
# 初始化配置
python -m eflycode.cli init
```

## mcp 命令

管理 MCP 服务器配置。

### 子命令

#### mcp list

列出所有已配置的 MCP 服务器。

```bash
python -m eflycode.cli mcp list
```

**输出示例：**

```
MCP 服务器配置 (2 个):

context7:
  命令: npx
  参数: -y @upstash/context7-mcp --api-key ***

playwright:
  命令: npx
  参数: @playwright/mcp@latest --isolated --no-sandbox
```

#### mcp add

添加新的 MCP 服务器。

```bash
python -m eflycode.cli mcp add <name> <command> [args...] [--env KEY=VALUE]...
```

**参数：**

- `name`：服务器名称，用于标识该服务器
- `command`：启动命令，例如 `npx`、`python` 等
- `args`：命令参数，所有剩余参数
- `--env KEY=VALUE`：环境变量，可以多次使用

**示例：**

```bash
# 添加 Context7 MCP 服务器
python -m eflycode.cli mcp add context7 npx -y @upstash/context7-mcp --api-key YOUR_API_KEY

# 添加带环境变量的服务器
python -m eflycode.cli mcp add my-server npx -y @some/package --env API_KEY=xxx --env TIMEOUT=30
```

**注意事项：**

- 服务器名称必须唯一
- 如果服务器已存在，将报错
- 环境变量支持 `${VAR_NAME}` 格式引用系统环境变量

#### mcp remove

移除指定的 MCP 服务器。

```bash
python -m eflycode.cli mcp remove <name>
```

**参数：**

- `name`：要移除的服务器名称

**示例：**

```bash
# 移除 context7 服务器
python -m eflycode.cli mcp remove context7
```

**注意事项：**

- 如果服务器不存在，将报错
- 移除操作会立即生效

## 交互式 CLI

如果不提供任何命令，将启动交互式 CLI：

```bash
python -m eflycode.cli
```

### 交互式使用

启动后，您可以：

- 输入问题或任务描述
- 按 `Ctrl+M` 提交
- 按 `Ctrl+D` 退出

### 示例

```
> 帮我写一个 Python 函数来读取 CSV 文件

> 分析当前项目的代码结构
```

## 帮助信息

查看命令帮助：

```bash
# 查看主帮助
python -m eflycode.cli --help

# 查看 mcp 命令帮助
python -m eflycode.cli mcp --help

# 查看具体子命令帮助
python -m eflycode.cli mcp add --help
```

