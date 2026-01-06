"""配置模块

包含配置管理和忽略文件管理功能
"""

# 导入配置管理功能
from eflycode.core.config.config_manager import (
    Config,
    find_config_file,
    get_max_context_length,
    get_model_name_from_config,
    load_config,
    load_config_from_file,
    parse_context_config,
    parse_model_config,
)

# 导入忽略文件管理功能
from eflycode.core.config.ignore import (
    find_ignore_file,
    load_ignore_patterns,
    should_ignore_path,
)

__all__ = [
    # 配置管理
    "Config",
    "find_config_file",
    "get_max_context_length",
    "get_model_name_from_config",
    "load_config",
    "load_config_from_file",
    "parse_context_config",
    "parse_model_config",
    # 忽略文件管理
    "find_ignore_file",
    "load_ignore_patterns",
    "should_ignore_path",
]

