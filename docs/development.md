# 开发指南

本文档为开发者提供项目开发、测试和贡献指南。

## 开发环境设置

### 1. 克隆项目

```bash
git clone <repository-url>
cd eflycode-cli
```

### 2. 安装依赖

使用 uv（推荐）：

```bash
uv sync
```

或使用 pip：

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate  # Windows

pip install -e ".[dev]"
```

### 3. 运行测试

```bash
# 运行所有测试
python -m unittest discover tests

# 运行特定测试文件
python -m unittest tests.test_cli_init
python -m unittest tests.test_cli_mcp

# 运行特定测试类
python -m unittest tests.test_cli_init.TestInitCommand

# 运行特定测试方法
python -m unittest tests.test_cli_init.TestInitCommand.test_init_creates_config_file
```

## 项目结构

```
eflycode-cli/
├── eflycode/                 # 主代码目录
│   ├── cli/                  # CLI 相关代码
│   │   ├── __main__.py       # CLI 入口点
│   │   ├── main.py           # 交互式 CLI
│   │   └── commands/         # CLI 命令
│   │       ├── init.py       # init 命令
│   │       └── mcp.py         # mcp 命令
│   └── core/                 # 核心功能
│       ├── agent/            # Agent 实现
│       ├── config/            # 配置管理
│       ├── context/           # 上下文管理
│       ├── llm/               # LLM 提供商
│       ├── mcp/               # MCP 集成
│       ├── tool/              # 工具实现
│       └── ui/                # UI 组件
├── tests/                     # 测试代码
│   ├── test_cli_init.py      # init 命令测试
│   ├── test_cli_mcp.py       # mcp 命令测试
│   └── ...                    # 其他测试
├── docs/                      # 文档
│   ├── README.md             # 文档索引
│   ├── getting-started.md    # 快速开始
│   ├── cli-commands.md       # CLI 命令参考
│   ├── configuration.md     # 配置指南
│   ├── mcp-servers.md        # MCP 服务器配置
│   ├── architecture.md       # 架构设计
│   └── development.md        # 开发指南（本文档）
├── pyproject.toml            # 项目配置
└── README.md                 # 项目 README
```

## 代码规范

### 命名规范

- **模块名**：小写字母，使用下划线分隔，例如 `mcp_client.py`
- **类名**：大驼峰命名，例如 `MCPClient`
- **函数名**：小写字母，使用下划线分隔，例如 `load_mcp_config`
- **常量名**：全大写，使用下划线分隔，例如 `DEFAULT_TIMEOUT`
- **变量名**：小写字母，使用下划线分隔，例如 `server_name`

### 注释规范

- 使用中文注释和文档字符串
- 文档字符串使用三引号格式
- 避免在注释中使用括号解释，使用逗号或短句
- 公共 API 必须有文档字符串

### 类型提示

- 所有函数参数和返回值都应该有类型提示
- 使用 `typing` 模块的类型，例如 `List[str]`、`Optional[Path]`

### 代码格式

- 使用 4 个空格缩进
- 每行最大长度：120 字符
- 使用空行分隔逻辑块

## 测试规范

### 测试文件组织

- 测试文件以 `test_` 开头
- 测试类以 `Test` 开头
- 测试方法以 `test_` 开头

### 测试编写要求

- 每个功能都应该有对应的测试
- 测试应该覆盖正常情况、边界情况和异常情况
- 使用 `setUp` 和 `tearDown` 进行测试准备和清理
- 测试应该独立，不依赖其他测试的执行顺序

### 测试示例

```python
class TestMyFeature(unittest.TestCase):
    """功能测试类"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_feature_works(self):
        """测试功能正常工作"""
        # 测试代码
        pass
```

## 添加新功能

### 1. 添加新的 CLI 命令

1. 在 `eflycode/cli/commands/` 创建新文件
2. 实现命令函数
3. 在 `eflycode/cli/__main__.py` 注册命令
4. 编写测试用例

### 2. 添加新的工具

1. 在 `eflycode/core/tool/` 创建新文件
2. 继承 `BaseTool` 类
3. 实现必需的方法
4. 在 `create_agent` 中注册工具
5. 编写测试用例

### 3. 添加新的 LLM 提供商

1. 在 `eflycode/core/llm/providers/` 创建新文件
2. 实现 `LLMProvider` 接口
3. 在配置中添加提供商支持
4. 编写测试用例

## 调试技巧

### 启用调试日志

在配置文件中设置日志级别为 `DEBUG`：

```yaml
logger:
  level: DEBUG
```

### 查看日志

日志文件位于 `logs/eflycode.log`：

```bash
tail -f logs/eflycode.log
```

### 使用调试器

在代码中添加断点：

```python
import pdb; pdb.set_trace()
```

或使用 IDE 的调试功能。

## 提交代码

### 提交前检查

1. 运行所有测试确保通过
2. 检查 linter 错误
3. 确保代码符合规范
4. 更新相关文档

### 提交信息格式

使用清晰的提交信息：

```
类型: 简短描述

详细说明（可选）
```

类型包括：
- `feat`：新功能
- `fix`：修复 bug
- `docs`：文档更新
- `test`：测试相关
- `refactor`：重构
- `chore`：构建/工具相关

示例：

```
feat: 添加 MCP 服务器管理命令

- 实现 mcp add/list/remove 命令
- 添加 MCP 配置管理功能
- 更新相关文档
```

## 常见问题

### 循环导入问题

如果遇到循环导入：

1. 使用延迟导入（在函数内部导入）
2. 重构代码结构，减少模块间依赖
3. 使用类型提示的字符串形式

### 测试失败

检查：

1. 测试环境是否正确设置
2. 临时文件是否清理
3. 是否有并发测试冲突
4. 查看测试输出获取详细错误信息

### 配置加载问题

检查：

1. 配置文件路径是否正确
2. YAML 格式是否正确
3. 必需字段是否存在
4. 查看日志获取详细错误

## 贡献指南

### 报告问题

在提交 issue 时，请包含：

- 问题描述
- 复现步骤
- 预期行为
- 实际行为
- 环境信息（Python 版本、操作系统等）

### 提交 Pull Request

1. Fork 项目
2. 创建功能分支
3. 实现功能并添加测试
4. 确保所有测试通过
5. 提交 Pull Request

### 代码审查

- 保持代码简洁清晰
- 遵循项目代码规范
- 添加必要的注释和文档
- 确保测试覆盖充分

## 资源

- [Python 官方文档](https://docs.python.org/3/)
- [unittest 文档](https://docs.python.org/3/library/unittest.html)
- [MCP 协议文档](https://modelcontextprotocol.io/)

