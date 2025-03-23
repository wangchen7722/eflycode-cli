import platform
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any


def get_system_info():
    """获取系统环境信息"""
    current_time = datetime.now()
    timezone_offset = int(current_time.astimezone().tzinfo.utcoffset(None).total_seconds() / 3600)
    os_type = platform.system()
    if os_type == "Windows":
        default_shell = "cmd"
    elif os_type == "Linux":
        default_shell = "bash"
    elif os_type == "Darwin":
        default_shell = "bash"
    else:
        default_shell = "unknown"
    system_info = {
        "os_type": platform.system(),
        "os_release": platform.release(),
        "default_shell": default_shell,
        "work_dir": Path.cwd().as_posix(),
        "current_time": current_time.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": f"UTC{timezone_offset:+d}",
    }
    return system_info

def _is_ignored(path: Path, ignores: List[str]) -> bool:
    """判断文件或文件夹是否被忽略"""
    return any(part in ignores for part in path.parts)

def get_workspace_info(path: Optional[str] = None, ignores: Optional[List[str]] = None) -> Dict[str, Any]:
    """获取工作区文件"""
    if ignores is None:
        ignores = [".git", ".idea", "__pycache__", ".vscode", "venv"]
    if path is None:
        workspace_path = Path.cwd()
    else:
        workspace_path = Path(path)
    workspace_files = [
        file.as_posix() 
        for file in workspace_path.rglob("*") 
        if file.is_file() and not _is_ignored(file, ignores)
    ]
    return {
        "path": workspace_path.as_posix(),
        "files": workspace_files,
    }

if __name__ == "__main__":
    system_info = get_system_info()
    workspace_info = get_workspace_info()
    print("System info:", system_info)
    # print("Workspace info:", workspace_info)