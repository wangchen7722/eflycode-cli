"""init 命令实现

初始化 .eflycode/config.yaml 配置文件
"""

import sys
from pathlib import Path

import yaml

from eflycode.core.config.config_manager import find_config_files
from eflycode.core.constants import (
    EFLYCODE_DIR,
    CONFIG_FILE,
    LOG_DIR,
    LOG_FILE,
    LOG_LEVEL,
    LOG_ROTATION,
    LOG_RETENTION,
    LOG_ENCODING,
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_CONTEXT_LENGTH_INIT,
)
from eflycode.core.context.strategies import (
    SUMMARY_THRESHOLD,
    SUMMARY_KEEP_RECENT,
)


def init_command(args) -> None:
    """初始化配置文件命令
    
    Args:
        args: argparse 参数对象
    """
    # 查找是否已存在配置文件
    user_config, project_config, workspace_dir = find_config_files()
    config_path = project_config or user_config
    
    if config_path and config_path.exists():
        print(f"错误: 配置文件已存在: {config_path}", file=sys.stderr)
        print("如果确实要重新初始化，请先删除现有配置文件", file=sys.stderr)
        sys.exit(1)
    
    # 确定工作区目录
    if workspace_dir:
        workspace_path = workspace_dir
    else:
        workspace_path = Path.cwd().resolve()
    
    # 创建 .eflycode 目录
    eflycode_dir = workspace_path / EFLYCODE_DIR
    eflycode_dir.mkdir(exist_ok=True)
    
    # 创建默认配置
    default_config = {
        "logger": {
            "dirpath": LOG_DIR,
            "filename": LOG_FILE,
            "level": LOG_LEVEL,
            "format": "{time:YYYY-MM-DD HH:mm:ss} | {level} | {file}:{function}:{line} | {message}",
            "rotation": LOG_ROTATION,
            "retention": LOG_RETENTION,
            "encoding": LOG_ENCODING,
        },
        "model": {
            "default": DEFAULT_MODEL,
            "entries": [
                {
                    "model": DEFAULT_MODEL,
                    "name": "GPT-4",
                    "provider": "openai",
                    "api_key": "${OPENAI_API_KEY}",
                    "base_url": None,
                    "max_context_length": DEFAULT_MAX_CONTEXT_LENGTH_INIT,
                    "temperature": DEFAULT_TEMPERATURE,
                    "supports_native_tool_call": True,
                }
            ],
        },
        "workspace": {
            "workspace_dir": str(workspace_path),
            "settings_dir": str(eflycode_dir),
            "settings_file": str(eflycode_dir / CONFIG_FILE),
        },
        "context": {
            "strategy": "sliding_window",
            "summary": {
                "threshold": SUMMARY_THRESHOLD,
                "keep_recent": SUMMARY_KEEP_RECENT,
                "model": None,
            },
            "sliding_window": {
                "size": 20,
            },
        },
    }
    
    # 写入配置文件
    config_file = eflycode_dir / CONFIG_FILE
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    print(f"配置文件已创建: {config_file}")
    print("请编辑配置文件以设置您的 API 密钥和其他选项")

