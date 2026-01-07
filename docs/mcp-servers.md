# MCP 服务器配置指南

本文档说明如何配置和管理 Model Context Protocol (MCP) 服务器。

## 什么是 MCP

Model Context Protocol (MCP) 是一个标准化协议，用于连接 AI 模型与外部数据源和工具。通过 MCP，Eflycode 可以访问各种外部服务和工具，扩展其功能。

## 配置文件位置

MCP 服务器配置存储在 `.eflycode/mcp.json` 文件中。

配置文件查找顺序：

1. 工作区目录的 `.eflycode/mcp.json`
2. 用户主目录的 `.eflycode/mcp.json`

## 配置文件格式

```json
{
  "mcpServers": {
    "stdio-server": {
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@package/name"],
      "env": {
        "API_KEY": "your-api-key"
      }
    },
    "http-server": {
      "transport": "http",
      "url": "https://example.com/mcp"
    }
  }
}
```

### 配置项说明

- `mcpServers`：MCP 服务器配置对象
  - 键：服务器名称，用于标识服务器
  - 值：服务器配置对象
    - `transport`：传输类型，`stdio` 或 `http`，默认为 `stdio`（可选）
    - **stdio 传输配置**：
      - `command`：启动命令，例如 `npx`、`python`、`node` 等
      - `args`：命令参数数组
      - `env`：环境变量对象（可选），支持 `${VAR_NAME}` 格式引用系统环境变量
    - **http 传输配置**：
      - `url`：MCP 服务器端点 URL，例如 `https://example.com/mcp`

## 使用 CLI 管理 MCP 服务器

### 列出所有服务器

```bash
python -m eflycode.cli mcp list
```

### 添加服务器

#### 添加 stdio 服务器

```bash
python -m eflycode.cli mcp add <name> <command> [args...] [--env KEY=VALUE]...
```

**示例：**

```bash
# 添加 Context7 服务器
python -m eflycode.cli mcp add context7 npx -y @upstash/context7-mcp --api-key YOUR_API_KEY

# 添加带环境变量的服务器
python -m eflycode.cli mcp add my-server npx -y @some/package --env API_KEY=xxx --env TIMEOUT=30
```

#### 添加 HTTP 服务器

```bash
python -m eflycode.cli mcp add <name> --transport http --url <URL>
```

**示例：**

```bash
# 添加 HTTP 服务器
python -m eflycode.cli mcp add http-server --transport http --url https://example.com/mcp
```

### 移除服务器

```bash
python -m eflycode.cli mcp remove <name>
```

**示例：**

```bash
python -m eflycode.cli mcp remove context7
```

## 传输类型

Eflycode 支持两种 MCP 传输类型：

### stdio 传输

通过标准输入输出与 MCP 服务器进程通信。服务器作为子进程启动。

**适用场景：**
- 本地运行的 MCP 服务器
- 通过命令行工具启动的服务器
- 需要进程管理的场景

**配置示例：**
```json
{
  "transport": "stdio",
  "command": "npx",
  "args": ["-y", "@package/mcp"],
  "env": {
    "API_KEY": "your-key"
  }
}
```

### HTTP 传输（Streamable HTTP）

通过 HTTP POST/GET 和 Server-Sent Events (SSE) 与远程 MCP 服务器通信。

**适用场景：**
- 远程 MCP 服务器
- 需要支持多个客户端连接的服务器
- 需要会话管理和可恢复性的场景

**配置示例：**
```json
{
  "transport": "http",
  "url": "https://example.com/mcp"
}
```

**HTTP 传输特性：**
- 支持 HTTP POST 发送 JSON-RPC 消息
- 支持 HTTP GET 建立 SSE 流
- 自动处理协议版本头和会话管理
- 支持连接恢复和消息重传

## 常用 MCP 服务器配置

### Context7（stdio）

Context7 提供实时文档查询功能。

```bash
python -m eflycode.cli mcp add context7 npx -y @upstash/context7-mcp --api-key YOUR_API_KEY
```

### Playwright（stdio）

Playwright MCP 提供浏览器自动化功能。

```bash
python -m eflycode.cli mcp add playwright npx @playwright/mcp@latest --isolated --no-sandbox
```

### GitHub（stdio）

GitHub MCP 提供 GitHub 仓库操作功能。

```bash
python -m eflycode.cli mcp add github npx -y @modelcontextprotocol/server-github --env GITHUB_PERSONAL_ACCESS_TOKEN=YOUR_TOKEN
```

### HTTP 服务器示例

如果您的 MCP 服务器支持 HTTP 传输：

```bash
python -m eflycode.cli mcp add remote-server --transport http --url https://mcp.example.com/api
```

## 环境变量支持

MCP 配置支持使用环境变量，使用 `${VAR_NAME}` 格式：

```json
{
  "mcpServers": {
    "my-server": {
      "command": "npx",
      "args": ["-y", "@package/name"],
      "env": {
        "API_KEY": "${MY_API_KEY}"
      }
    }
  }
}
```

系统会自动从环境变量中读取 `MY_API_KEY` 的值。

## 工具命名规则

MCP 工具会自动添加命名空间前缀，格式为：`{server_name}_{tool_name}`

例如，如果 `context7` 服务器提供了 `query-docs` 工具，在 Eflycode 中的工具名称为 `context7_query_docs`。

这样可以避免不同 MCP 服务器的工具名称冲突。

## 服务器连接

Eflycode 在启动时会自动连接所有配置的 MCP 服务器：

1. 读取 `.eflycode/mcp.json` 配置文件
2. 为每个服务器启动后台连接
3. 等待连接完成（最多 5 秒）
4. 加载服务器提供的工具
5. 将工具注册到 Agent

如果某个服务器连接失败，Eflycode 会：

- 记录警告日志
- 跳过该服务器
- 继续加载其他服务器

## 故障排除

### 服务器连接失败

检查以下事项：

1. **命令是否正确**：确保 `command` 和 `args` 配置正确
2. **依赖是否安装**：确保所需的命令（如 `npx`、`python`）已安装
3. **环境变量**：检查环境变量是否正确设置
4. **网络连接**：确保可以访问所需的网络资源

查看日志文件获取详细错误信息：

```bash
cat logs/eflycode.log
```

### 工具未加载

如果服务器连接成功但工具未加载：

1. 检查服务器是否提供了工具
2. 查看日志中的警告信息
3. 确认服务器实现符合 MCP 协议规范

### 工具名称冲突

如果遇到工具名称冲突：

- Eflycode 会自动为每个 MCP 工具添加服务器名称前缀
- 工具名称格式：`{server_name}_{tool_name}`
- 特殊字符会自动替换为下划线

## 手动编辑配置文件

您也可以直接编辑 `.eflycode/mcp.json` 文件：

```json
{
  "mcpServers": {
    "my-server": {
      "command": "python",
      "args": ["-m", "my_mcp_server"],
      "env": {
        "API_KEY": "your-key",
        "TIMEOUT": "30"
      }
    }
  }
}
```

编辑后，重启 Eflycode 以加载新配置。

## 最佳实践

1. **使用有意义的服务器名称**：选择清晰、描述性的名称
2. **使用环境变量存储敏感信息**：不要在配置文件中硬编码 API 密钥
3. **测试连接**：添加服务器后，使用 `mcp list` 验证连接状态
4. **定期更新**：保持 MCP 服务器包为最新版本
5. **查看日志**：遇到问题时，查看日志文件获取详细信息

