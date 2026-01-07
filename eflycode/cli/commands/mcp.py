"""MCP 管理命令实现

管理 MCP 服务器配置
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional


def find_or_create_mcp_config(workspace_dir: Optional[Path] = None) -> Path:
    """查找或创建 MCP 配置文件
    
    Args:
        workspace_dir: 工作区目录，如果为None则使用当前工作目录
        
    Returns:
        Path: MCP 配置文件路径
    """
    if workspace_dir is None:
        # 尝试从配置文件获取工作区目录
        from eflycode.core.config.config_manager import find_config_file
        _, config_workspace_dir = find_config_file()
        if config_workspace_dir:
            workspace_dir = config_workspace_dir
        else:
            workspace_dir = Path.cwd().resolve()
    
    # 查找现有配置文件
    from eflycode.core.mcp.config import find_mcp_config_file
    config_path = find_mcp_config_file(workspace_dir)
    if config_path:
        return config_path
    
    # 如果不存在，创建工作区目录下的配置文件
    eflycode_dir = workspace_dir / ".eflycode"
    eflycode_dir.mkdir(exist_ok=True)
    config_path = eflycode_dir / "mcp.json"
    
    # 创建空配置
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump({"mcpServers": {}}, f, indent=2, ensure_ascii=False)
    
    return config_path


def load_mcp_config_dict(workspace_dir: Optional[Path] = None) -> Dict:
    """加载 MCP 配置为字典
    
    Args:
        workspace_dir: 工作区目录，如果为None则使用当前工作目录
        
    Returns:
        Dict: MCP 配置字典
    """
    # 延迟导入以避免循环导入
    config_path = find_or_create_mcp_config(workspace_dir)
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"错误: MCP 配置文件格式错误: {config_path}", file=sys.stderr)
        print(f"详情: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"错误: 读取 MCP 配置文件失败: {config_path}", file=sys.stderr)
        print(f"详情: {e}", file=sys.stderr)
        sys.exit(1)
    
    if "mcpServers" not in config_data:
        config_data["mcpServers"] = {}
    
    return config_data


def save_mcp_config(config_path: Path, mcp_servers: Dict) -> None:
    """保存 MCP 配置到文件
    
    Args:
        config_path: 配置文件路径
        mcp_servers: MCP 服务器配置字典
    """
    config_data = {"mcpServers": mcp_servers}
    
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2, ensure_ascii=False)


def mcp_list(args) -> None:
    """列出所有 MCP 服务器
    
    Args:
        args: argparse 参数对象
    """
    # 延迟导入以避免循环导入
    from eflycode.core.config.config_manager import find_config_file
    from eflycode.core.mcp.config import find_mcp_config_file
    
    # 获取工作区目录
    _, workspace_dir = find_config_file()
    if not workspace_dir:
        workspace_dir = Path.cwd().resolve()
    
    # 加载配置
    config_path = find_mcp_config_file(workspace_dir)
    if not config_path or not config_path.exists():
        print("未找到 MCP 配置文件")
        print(f"配置文件位置: {workspace_dir / '.eflycode' / 'mcp.json'}")
        print("使用 'eflycode mcp add' 命令添加 MCP 服务器")
        return
    
    config_data = load_mcp_config_dict(workspace_dir)
    mcp_servers = config_data.get("mcpServers", {})
    
    if not mcp_servers:
        print("未配置任何 MCP 服务器")
        print("使用 'eflycode mcp add' 命令添加 MCP 服务器")
        return
    
    print(f"MCP 服务器配置 ({len(mcp_servers)} 个):")
    print()
    
    for name, server_config in mcp_servers.items():
        print(f"{name}:")
        print(f"  命令: {server_config.get('command', 'N/A')}")
        args_list = server_config.get("args", [])
        if args_list:
            # 隐藏敏感信息（API密钥等）
            args_display = []
            for arg in args_list:
                if "key" in arg.lower() or "token" in arg.lower() or "secret" in arg.lower():
                    args_display.append("***")
                else:
                    args_display.append(arg)
            print(f"  参数: {' '.join(args_display)}")
        env = server_config.get("env")
        if env:
            print(f"  环境变量: {len(env)} 个")
        print()


def mcp_add(args) -> None:
    """添加 MCP 服务器
    
    Args:
        args: argparse 参数对象，包含 name, command, args, env
    """
    # 延迟导入以避免循环导入
    from eflycode.core.config.config_manager import find_config_file
    
    # 获取工作区目录
    _, workspace_dir = find_config_file()
    if not workspace_dir:
        workspace_dir = Path.cwd().resolve()
    
    # 加载配置
    config_data = load_mcp_config_dict(workspace_dir)
    mcp_servers = config_data.get("mcpServers", {})
    
    # 检查服务器名称是否已存在
    if args.name in mcp_servers:
        print(f"错误: MCP 服务器 '{args.name}' 已存在", file=sys.stderr)
        print(f"使用 'eflycode mcp remove {args.name}' 先移除现有配置", file=sys.stderr)
        sys.exit(1)
    
    # 解析环境变量（先从 args.env 获取）
    env_dict = {}
    if args.env:
        for env_str in args.env:
            if "=" not in env_str:
                print(f"错误: 环境变量格式错误: {env_str}", file=sys.stderr)
                print("正确格式: 键=值", file=sys.stderr)
                sys.exit(1)
            key, value = env_str.split("=", 1)
            env_dict[key] = value
    
    # 处理命令参数，移除 --env 及其值（如果它们被包含在 args.args 中）
    command_args = []
    if args.args:
        i = 0
        while i < len(args.args):
            if args.args[i] == "--env" and i + 1 < len(args.args):
                # 跳过 --env 和它的值，但将值添加到 env_dict
                env_value = args.args[i + 1]
                if "=" in env_value:
                    key, value = env_value.split("=", 1)
                    env_dict[key] = value
                i += 2
            else:
                command_args.append(args.args[i])
                i += 1
    
    # 创建服务器配置
    server_config = {
        "command": args.command,
        "args": command_args,
    }
    
    if env_dict:
        server_config["env"] = env_dict
    
    # 添加到配置
    mcp_servers[args.name] = server_config
    
    # 保存配置
    config_path = find_or_create_mcp_config(workspace_dir)
    save_mcp_config(config_path, mcp_servers)
    
    print(f"MCP 服务器 '{args.name}' 已添加")
    print(f"配置文件: {config_path}")


def mcp_remove(args) -> None:
    """移除 MCP 服务器
    
    Args:
        args: argparse 参数对象，包含 name
    """
    # 延迟导入以避免循环导入
    from eflycode.core.config.config_manager import find_config_file
    
    # 获取工作区目录
    _, workspace_dir = find_config_file()
    if not workspace_dir:
        workspace_dir = Path.cwd().resolve()
    
    # 加载配置
    config_data = load_mcp_config_dict(workspace_dir)
    mcp_servers = config_data.get("mcpServers", {})
    
    # 检查服务器名称是否存在
    if args.name not in mcp_servers:
        print(f"错误: MCP 服务器 '{args.name}' 不存在", file=sys.stderr)
        sys.exit(1)
    
    # 移除服务器
    del mcp_servers[args.name]
    
    # 保存配置
    config_path = find_or_create_mcp_config(workspace_dir)
    save_mcp_config(config_path, mcp_servers)
    
    print(f"MCP 服务器 '{args.name}' 已移除")
    print(f"配置文件: {config_path}")

