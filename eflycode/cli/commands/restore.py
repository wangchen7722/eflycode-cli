"""恢复 checkpoint 的命令"""

import json
from pathlib import Path

from eflycode.core.config.config_manager import ConfigManager
from eflycode.core.utils.checkpoint import get_checkpoints_dir
from eflycode.core.services.git_service import CheckpointError, GitService


def _list_checkpoints(checkpoints_dir: Path) -> list[str]:
    if not checkpoints_dir.exists():
        return []
    return sorted([f.name for f in checkpoints_dir.glob("*.json") if f.is_file()])


def restore_command(args) -> None:
    """恢复指定的 checkpoint"""
    config = ConfigManager.get_instance().get_config()
    if not getattr(config, "checkpointing_enabled", False):
        print("Checkpointing 未启用，无法执行恢复。")
        return

    workspace_dir = config.workspace_dir
    checkpoints_dir = get_checkpoints_dir(workspace_dir)

    # 列表模式
    if not getattr(args, "name", None):
        names = _list_checkpoints(checkpoints_dir)
        if not names:
            print("未找到可用的 checkpoint。")
            return
        print("可用 checkpoint：")
        for name in names:
            print(f"- {name[:-5] if name.endswith('.json') else name}")
        return

    # 具体恢复
    name = args.name
    if not name.endswith(".json"):
        name += ".json"
    target_file = checkpoints_dir / name
    if not target_file.exists():
        print(f"未找到 checkpoint: {name}")
        return

    try:
        data = json.loads(target_file.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"读取 checkpoint 失败: {e}")
        return

    commit_hash = data.get("commitHash")
    if not commit_hash:
        print("checkpoint 缺少 commitHash，无法恢复。")
        return

    try:
        git_service = GitService(workspace_dir)
        git_service.restore(commit_hash)
        print(f"已恢复到快照: {name}")
        tool_call = data.get("toolCall")
        if tool_call:
            print("原工具调用：")
            print(json.dumps(tool_call, ensure_ascii=False, indent=2))
    except CheckpointError as e:
        print(f"恢复失败: {e}")
    except Exception as e:
        print(f"恢复发生异常: {e}")

