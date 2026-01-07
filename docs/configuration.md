# 配置指南

本文档说明 Eflycode 的配置文件结构和配置选项。

## 配置文件位置

Eflycode 按以下顺序查找配置文件：

1. 当前目录及向上 2 级目录的 `.eflycode/config.yaml`
2. 用户主目录的 `.eflycode/config.yaml`

如果都未找到，将使用默认配置。

## 配置文件结构

配置文件使用 YAML 格式，包含以下主要部分：

```yaml
logger:
  # 日志配置

model:
  # 模型配置

workspace:
  # 工作区配置

context:
  # 上下文管理配置
```

## Logger 配置

控制日志记录行为。

```yaml
logger:
  dirpath: logs                    # 日志目录
  filename: eflycode.log          # 日志文件名
  level: INFO                      # 日志级别：DEBUG、INFO、WARNING、ERROR
  format: "{time:YYYY-MM-DD HH:mm:ss} | {level} | {file}:{function}:{line} | {message}"
  rotation: 10 MB                  # 日志文件轮转大小
  retention: 14 days               # 日志保留时间
  encoding: utf-8                  # 文件编码
```

### 配置项说明

- `dirpath`：日志文件存储目录，相对于工作区目录
- `filename`：日志文件名
- `level`：日志级别，可选值：`DEBUG`、`INFO`、`WARNING`、`ERROR`
- `format`：日志格式字符串
- `rotation`：当日志文件达到指定大小时轮转
- `retention`：日志文件保留时间
- `encoding`：文件编码

## Model 配置

配置大语言模型提供商和模型参数。

```yaml
model:
  default: gpt-4                   # 默认使用的模型名称
  entries:
    - model: gpt-4                 # 模型标识符
      name: GPT-4                  # 模型显示名称
      provider: openai              # 提供商：openai
      api_key: YOUR_API_KEY         # API 密钥，支持 ${VAR_NAME} 格式
      base_url: null                # API 基础 URL，null 使用默认
      max_context_length: 8192      # 最大上下文长度
      temperature: 0.7              # 温度参数
      supports_native_tool_call: true # 是否支持原生工具调用
```

### 配置项说明

- `default`：默认使用的模型名称，必须与 `entries` 中某个模型的 `model` 字段匹配
- `entries`：模型配置列表
  - `model`：模型标识符，用于在配置中引用
  - `name`：模型显示名称
  - `provider`：提供商，目前支持 `openai`
  - `api_key`：API 密钥，支持使用 `${VAR_NAME}` 格式引用环境变量
  - `base_url`：API 基础 URL，`null` 使用提供商默认 URL
  - `max_context_length`：最大上下文长度（token 数）
  - `temperature`：温度参数，控制输出的随机性
  - `supports_native_tool_call`：是否支持原生工具调用

### 环境变量支持

API 密钥支持使用环境变量：

```yaml
api_key: ${OPENAI_API_KEY}
```

系统会从环境变量中读取 `OPENAI_API_KEY` 的值。

## Workspace 配置

配置工作区相关设置。

```yaml
workspace:
  workspace_dir: /path/to/workspace  # 工作区根目录
  settings_dir: /path/to/.eflycode    # 设置目录
  settings_file: /path/to/config.yaml # 配置文件路径
```

### 配置项说明

- `workspace_dir`：工作区根目录路径
- `settings_dir`：设置目录路径，通常为 `.eflycode`
- `settings_file`：配置文件完整路径

**注意：** 这些配置项通常在运行 `init` 命令时自动生成，一般不需要手动修改。

## Context 配置

配置上下文管理策略。

```yaml
context:
  strategy: sliding_window          # 策略类型：sliding_window 或 summary
  summary:
    threshold: 0.8                  # 摘要触发阈值
    keep_recent: 10                 # 保留最近的消息数
    model: null                     # 用于摘要的模型，null 使用默认模型
  sliding_window:
    size: 20                        # 滑动窗口大小
```

### 策略类型

#### sliding_window（滑动窗口）

保留最近的 N 条消息，超出窗口的消息会被丢弃。

- `size`：窗口大小，即保留的消息数量

#### summary（摘要压缩）

当上下文达到阈值时，将旧消息压缩为摘要。

- `threshold`：触发摘要的阈值（0.0-1.0）
- `keep_recent`：保留最近的消息数量
- `model`：用于生成摘要的模型，`null` 使用默认模型

## 配置文件示例

完整的配置文件示例：

```yaml
logger:
  dirpath: logs
  filename: eflycode.log
  level: INFO
  format: "{time:YYYY-MM-DD HH:mm:ss} | {level} | {file}:{function}:{line} | {message}"
  rotation: 10 MB
  retention: 14 days
  encoding: utf-8

model:
  default: gpt-4
  entries:
    - model: gpt-4
      name: GPT-4
      provider: openai
      api_key: ${OPENAI_API_KEY}
      base_url: null
      max_context_length: 8192
      temperature: 0.7
      supports_native_tool_call: true
    - model: gpt-3.5-turbo
      name: GPT-3.5 Turbo
      provider: openai
      api_key: ${OPENAI_API_KEY}
      base_url: null
      max_context_length: 4096
      temperature: 0.7
      supports_native_tool_call: true

workspace:
  workspace_dir: /path/to/workspace
  settings_dir: /path/to/workspace/.eflycode
  settings_file: /path/to/workspace/.eflycode/config.yaml

context:
  strategy: sliding_window
  summary:
    threshold: 0.8
    keep_recent: 10
    model: null
  sliding_window:
    size: 20
```

## 环境变量

以下环境变量可以在配置文件中使用：

- `OPENAI_API_KEY`：OpenAI API 密钥
- `EFLYCODE_API_KEY`：Eflycode API 密钥（备用）

在配置文件中使用 `${VAR_NAME}` 格式引用环境变量。

## 配置验证

启动时，Eflycode 会验证配置文件：

- 检查必需字段是否存在
- 验证字段类型和格式
- 如果配置无效，将使用默认配置并记录警告

## 故障排除

### 配置文件未找到

如果配置文件未找到，Eflycode 会使用默认配置。要创建配置文件，运行：

```bash
python -m eflycode.cli init
```

### 配置加载失败

如果配置文件格式错误，Eflycode 会：

1. 记录错误日志
2. 使用默认配置继续运行
3. 在日志中显示警告信息

检查日志文件以获取详细错误信息。

