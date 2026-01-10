"""智能命令补全器

统一处理所有命令的补全和执行
"""

import asyncio
from typing import Callable, Dict, Iterable, Optional

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document

from eflycode.core.utils.file_manager import get_file_manager
from eflycode.cli.command_registry import get_command_registry


class SmartCompleter(Completer):
    """智能命令补全器，统一处理所有命令"""

    def __init__(self):
        """初始化 SmartCompleter"""
        self._commands = get_command_registry().list_commands()

    def register_command(
        self,
        command: str,
        description: str,
        handler: Optional[Callable[[str], bool]] = None,
    ) -> None:
        """注册新命令

        Args:
            command: 命令字符串，如 "/model"
            description: 命令描述
            handler: 命令处理函数，接收命令字符串，返回是否已处理
        """
        get_command_registry().register_command(command, description, handler)

    def get_completions(
        self, document: Document, complete_event
    ) -> Iterable[Completion]:
        """获取补全建议

        Args:
            document: 当前文档
            complete_event: 补全事件

        Yields:
            Completion: 补全建议
        """
        text = document.text_before_cursor
        token = self._get_current_token(text)

        # TODO: 扩展为支持 @ 的补全匹配逻辑
        if token.startswith("/"):
            # 如果已经输入了完整命令，不提供补全
            if token in self._commands:
                return
            
            # 查找匹配的命令
            for command, info in self._commands.items():
                if command.startswith(token):
                    # 使用完整命令替换当前输入片段
                    start_pos = -len(token)

                    yield Completion(
                        text=command,
                        start_position=start_pos,
                        display=command,
                        display_meta=info["description"],
                    )
        elif token.startswith("#"):
            query = token[1:]
            start_pos = -len(token)
            for path in self._iter_project_files(query=query):
                yield Completion(
                    text=f"#{path}",
                    start_position=start_pos,
                    display=f"#{path}",
                    display_meta="file",
                )
        # 如果输入为空，不提供补全，让用户自己输入 /
        elif text.strip() == "":
            return

    @staticmethod
    def _get_current_token(text: str) -> str:
        if not text:
            return ""
        stripped = text.rstrip()
        if not stripped:
            return ""
        idx = stripped.rfind(" ")
        return stripped[idx + 1 :]

    def _iter_project_files(self, query: str) -> Iterable[str]:
        file_manager = get_file_manager()
        return file_manager.fuzzy_find(query, limit=200)

    def handle_command(self, command: str) -> bool:
        """处理命令

        Args:
            command: 命令字符串

        Returns:
            bool: 如果命令已处理返回 True，否则返回 False
        """
        command = command.strip()
        if command in self._commands:
            handler = get_command_registry().get_command_handler(command)
            if handler:
                return handler(command)
        return False

    async def handle_command_async(self, command: str) -> bool:
        """异步处理命令"""
        command = command.strip()
        if command in self._commands:
            handler = self._commands[command].get("handler")
            if handler:
                if asyncio.iscoroutinefunction(handler):
                    return bool(await handler(command))
                result = handler(command)
                if asyncio.iscoroutine(result):
                    return bool(await result)
                return bool(result)
        return False

    def get_command_handler(self, command: str) -> Optional[Callable[[str], bool]]:
        """获取命令处理函数

        Args:
            command: 命令字符串

        Returns:
            Optional[Callable]: 命令处理函数，如果不存在返回 None
        """
        if command in self._commands:
            return get_command_registry().get_command_handler(command)
        return None

    def set_command_handler(self, command: str, handler: Callable[[str], bool]) -> None:
        """设置命令处理函数

        Args:
            command: 命令字符串
            handler: 命令处理函数
        """
        get_command_registry().set_command_handler(command, handler)

