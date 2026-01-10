"""配置模块

包含配置管理和忽略文件管理功能
"""

# 导入配置管理功能
from eflycode.core.config.config_manager import (
    ConfigManager,
    find_config_files,
    get_max_context_length,
    get_model_display_name_from_config,
    get_model_name_from_config,
    get_user_config_dir,
    load_config_from_file,
    parse_context_config,
    parse_model_config,
    resolve_workspace_dir,
)
from eflycode.core.config.models import Config

# 导入忽略文件管理功能
from eflycode.core.config.ignore import (
    find_gitignore_file,
    find_ignore_file,
    load_all_ignore_patterns,
    load_gitignore_patterns,
    load_ignore_patterns,
    should_ignore_path,
)

__all__ = [
    # 配置管理
    "Config",
    "ConfigManager",
    "find_config_files",
    "get_max_context_length",
    "get_model_display_name_from_config",
    "get_model_name_from_config",
    "get_user_config_dir",
    "load_config_from_file",
    "parse_context_config",
    "parse_model_config",
    "resolve_workspace_dir",
    # 忽略文件管理
    "find_gitignore_file",
    "find_ignore_file",
    "load_all_ignore_patterns",
    "load_gitignore_patterns",
    "load_ignore_patterns",
    "should_ignore_path",
]

