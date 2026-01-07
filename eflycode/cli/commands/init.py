"""init 命令实现

初始化 .eflycode/config.yaml 配置文件
"""

import sys
from pathlib import Path

import yaml


def init_command(args) -> None:
    """初始化配置文件命令
    
    Args:
        args: argparse 参数对象
    """
    # 延迟导入以避免循环导入
    from eflycode.core.config.config_manager import find_config_file
    
    # 查找是否已存在配置文件
    config_path, workspace_dir = find_config_file()
    
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
    eflycode_dir = workspace_path / ".eflycode"
    eflycode_dir.mkdir(exist_ok=True)
    
    # 创建默认配置
    default_config = {
        "logger": {
            "dirpath": "logs",
            "filename": "eflycode.log",
            "level": "INFO",
            "format": "{time:YYYY-MM-DD HH:mm:ss} | {level} | {file}:{function}:{line} | {message}",
            "rotation": "10 MB",
            "retention": "14 days",
            "encoding": "utf-8",
        },
        "model": {
            "default": "gpt-4",
            "entries": [
                {
                    "model": "gpt-4",
                    "name": "GPT-4",
                    "provider": "openai",
                    "api_key": "${OPENAI_API_KEY}",
                    "base_url": None,
                    "max_context_length": 8192,
                    "temperature": 0.7,
                    "supports_native_tool_call": True,
                }
            ],
        },
        "workspace": {
            "workspace_dir": str(workspace_path),
            "settings_dir": str(eflycode_dir),
            "settings_file": str(eflycode_dir / "config.yaml"),
        },
        "context": {
            "strategy": "sliding_window",
            "summary": {
                "threshold": 0.8,
                "keep_recent": 10,
                "model": None,
            },
            "sliding_window": {
                "size": 20,
            },
        },
    }
    
    # 写入配置文件
    config_file = eflycode_dir / "config.yaml"
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    print(f"配置文件已创建: {config_file}")
    print("请编辑配置文件以设置您的 API 密钥和其他选项")

