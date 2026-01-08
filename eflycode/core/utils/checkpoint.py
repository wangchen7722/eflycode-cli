"""Checkpoint 存储和捕获工具

提供 shadow git 历史仓库、临时目录、checkpoint 文件目录的路径计算与创建，
以及在执行编辑类工具前捕获项目快照的功能。
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from eflycode.core.config.config_manager import ConfigManager
from eflycode.core.constants import (
    CHECKPOINTS_DIR,
    EFLYCODE_DIR,
    HISTORY_DIR,
    TMP_DIR,
)
from eflycode.core.utils.logger import logger


def _hash_workspace_dir(workspace_dir: Path) -> str:
    """使用 workspace 绝对路径计算 SHA256 哈希（十六进制字符串）"""
    resolved = workspace_dir.resolve()
    return hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()


def get_history_dir(workspace_dir: Path) -> Path:
    """获取 shadow git 历史仓库目录"""
    workspace_hash = _hash_workspace_dir(workspace_dir)
    return Path.home() / EFLYCODE_DIR / HISTORY_DIR / workspace_hash


def get_project_tmp_dir(workspace_dir: Path) -> Path:
    """获取项目临时目录"""
    workspace_hash = _hash_workspace_dir(workspace_dir)
    return Path.home() / EFLYCODE_DIR / TMP_DIR / workspace_hash


def get_checkpoints_dir(workspace_dir: Path) -> Path:
    """获取 checkpoint JSON 文件存储目录"""
    return get_project_tmp_dir(workspace_dir) / CHECKPOINTS_DIR


def ensure_checkpoint_dirs(workspace_dir: Path) -> tuple[Path, Path]:
    """确保历史仓库目录和 checkpoint 目录存在

    Returns:
        (history_dir, checkpoints_dir)
    """
    history_dir = get_history_dir(workspace_dir)
    checkpoints_dir = get_checkpoints_dir(workspace_dir)

    history_dir.mkdir(parents=True, exist_ok=True)
    checkpoints_dir.mkdir(parents=True, exist_ok=True)

    return history_dir, checkpoints_dir


def _build_checkpoint_filename(file_path: Optional[str], tool_name: str) -> str:
    """构建 checkpoint 文件名

    Args:
        file_path: 文件路径
        tool_name: 工具名称

    Returns:
        str: checkpoint 文件名
    """
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S_%fZ")
    base = Path(file_path).name if file_path else "unknown"
    return f"{timestamp}-{base}-{tool_name}.json"


def capture_tool_checkpoint(
    tool_name: str,
    tool_args: Dict[str, Any],
    message_id: Optional[str] = None,
) -> Optional[Path]:
    """捕获编辑工具的 checkpoint

    Args:
        tool_name: 工具名称
        tool_args: 工具参数字典
        message_id: 可选的消息 ID（如果调用链有）

    Returns:
        Optional[Path]: 写入的 checkpoint 文件路径，失败返回 None
    """
    config = ConfigManager.get_instance().get_config()
    if not getattr(config, "checkpointing_enabled", False):
        return None

    workspace_dir = config.workspace_dir
    if not workspace_dir:
        return None

    # 确保目录存在
    _, checkpoints_dir = ensure_checkpoint_dirs(workspace_dir)

    commit_hash: Optional[str] = None
    try:
        # 延迟导入以避免循环导入
        from eflycode.core.services.git_service import CheckpointError, GitService
        
        git_service = GitService(workspace_dir)
        commit_hash = git_service.create_snapshot(tool_name)
    except CheckpointError as e:
        logger.debug(f"创建 checkpoint 快照失败（忽略）：{e}")
    except Exception as e:
        logger.debug(f"创建 checkpoint 时发生异常（忽略）：{e}")

    # 生成文件名
    file_path = (
        tool_args.get("file_path")
        or tool_args.get("filepath")
        or tool_args.get("path")
    )
    checkpoint_file = get_checkpoints_dir(workspace_dir) / _build_checkpoint_filename(
        file_path, tool_name
    )

    payload = {
        "commitHash": commit_hash,
        "toolCall": {"name": tool_name, "args": tool_args},
        "messageId": message_id,
        # 保留字段：未来可加入 chat/ui 历史
        "history": [],
        "clientHistory": [],
    }

    try:
        checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return checkpoint_file
    except Exception as e:
        logger.debug(f"写入 checkpoint 文件失败（忽略）：{e}")
        return None

