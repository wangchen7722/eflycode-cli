"""CLI 包入口点

使 eflycode.cli 可以作为模块运行：
    python -m eflycode.cli
    python -m eflycode.cli init
    python -m eflycode.cli mcp list
"""

import argparse
import sys
from pathlib import Path

from eflycode.cli.commands.init import init_command
from eflycode.cli.commands.mcp import mcp_add, mcp_list, mcp_remove
from eflycode.cli.main import run_interactive_cli


def main() -> None:
    """主入口函数，解析命令行参数并执行相应命令"""
    parser = argparse.ArgumentParser(
        prog="eflycode",
        description="Eflycode CLI，AI 驱动的编程助手",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # init 命令
    init_parser = subparsers.add_parser("init", help="初始化配置文件")
    init_parser.set_defaults(func=init_command)
    
    # mcp 子命令
    mcp_parser = subparsers.add_parser("mcp", help="管理 MCP 服务器配置")
    mcp_subparsers = mcp_parser.add_subparsers(dest="mcp_command", help="MCP 子命令")
    
    # mcp list
    mcp_list_parser = mcp_subparsers.add_parser("list", help="列出所有 MCP 服务器")
    mcp_list_parser.set_defaults(func=mcp_list)
    
    # mcp add
    mcp_add_parser = mcp_subparsers.add_parser("add", help="添加 MCP 服务器")
    mcp_add_parser.add_argument("name", help="服务器名称")
    mcp_add_parser.add_argument("command", help="启动命令")
    mcp_add_parser.add_argument(
        "--env",
        action="append",
        metavar="键=值",
        help="环境变量，可以多次使用",
    )
    mcp_add_parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="命令参数，所有剩余参数",
    )
    mcp_add_parser.set_defaults(func=mcp_add)
    
    # mcp remove
    mcp_remove_parser = mcp_subparsers.add_parser("remove", help="移除 MCP 服务器")
    mcp_remove_parser.add_argument("name", help="服务器名称")
    mcp_remove_parser.set_defaults(func=mcp_remove)
    
    # 解析参数
    args = parser.parse_args()
    
    # 如果没有提供命令，运行交互式 CLI
    if args.command is None:
        run_interactive_cli()
    else:
        # 执行对应的命令函数
        if hasattr(args, "func"):
            try:
                args.func(args)
            except Exception as e:
                print(f"错误: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            parser.print_help()
            sys.exit(1)


if __name__ == "__main__":
    main()
