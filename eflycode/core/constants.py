"""项目常量定义

统一管理项目中的魔法数字和默认配置值
"""

# ============================================================================
# 路径和文件名常量
# ============================================================================

# 工作区目录名
EFLYCODE_DIR = ".eflycode"

# 配置文件
CONFIG_FILE = "config.yaml"
MCP_CONFIG_FILE = "mcp.json"
IGNORE_FILE = ".eflycodeignore"

# checkpointing 存储目录
HISTORY_DIR = "history"
TMP_DIR = "tmp"
CHECKPOINTS_DIR = "checkpoints"

# 日志和输出目录
LOG_DIR = "logs"
VERBOSE_DIR = "verbose"
REQUESTS_DIR = "requests"
SESSIONS_DIR = "sessions"

# ============================================================================
# 日志配置常量
# ============================================================================

LOG_LEVEL = "INFO"
LOG_FILE = "eflycode.log"
LOG_ROTATION = "10 MB"
LOG_RETENTION = "14 days"
LOG_COMPRESSION = "tar.gz"
LOG_ENCODING = "utf-8"

# 日志格式
LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "{thread.name}:{thread.id} | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)

# ============================================================================
# LLM 配置常量
# ============================================================================

# 默认最大上下文长度（64k tokens）
DEFAULT_MAX_CONTEXT_LENGTH = 65536
DEFAULT_TIMEOUT = 60.0  # 秒
DEFAULT_MAX_RETRIES = 3

# ============================================================================
# 配置管理常量
# ============================================================================

DEFAULT_SYSTEM_VERSION = "0.1.0"
WORKSPACE_SEARCH_MAX_DEPTH = 3

# ============================================================================
# 默认模型配置常量
# ============================================================================

DEFAULT_MODEL = "gpt-4o"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_CONTEXT_LENGTH_INIT = 8192  # init 命令中使用的默认值
