import platform
from pathlib import Path
from datetime import datetime

def system_info():
    """获取系统环境信息"""
    current_time = datetime.now()
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
        "home_dir": Path.cwd().as_posix(),
        "current_time": current_time.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": current_time.astimezone().tzname()
    }
    return system_info